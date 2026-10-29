"""
4D Time-series Site Progress Tracking & Earned Value Scan Synchronization Engine.
Connects time-series weekly site scans (.ply) directly with debim.schedule.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from debim.compat import BaseModel
from debim.schedule.schema import CrashingActivity, CrashingManifest, ProgressLogEntry
from debim.schedule.solver import ScheduleResult, solve_schedule


@dataclass
class BoundingBox:
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    @property
    def volume(self) -> float:
        dx = max(0.0, self.max_x - self.min_x)
        dy = max(0.0, self.max_y - self.min_y)
        dz = max(0.0, self.max_z - self.min_z)
        return dx * dy * dz


class EVMMetrics(BaseModel):
    as_of_date: str
    budget_at_completion: float
    planned_value: float
    earned_value: float
    actual_cost: float
    schedule_variance: float
    cost_variance: float
    schedule_performance_index: float
    cost_performance_index: float


def evaluate_element_presence(
    element_bounding_box: Union[BoundingBox, Tuple[float, float, float, float, float, float], Dict[str, float]],
    scan_points: np.ndarray,
    min_point_density: float = 100.0,
) -> float:
    """
    Evaluates physical presence/completion ratio (0.0 - 1.0) of a building component
    (e.g., Column, Wall, Slab) based on 3D spatial scan point cloud density.

    Args:
        element_bounding_box: BoundingBox instance, 6-tuple (min_x, min_y, min_z, max_x, max_y, max_z), or dict.
        scan_points: (N, 3) float array of 3D point cloud scan coordinates.
        min_point_density: Expected point cloud density (points per m3) for 100% completion.

    Returns:
        float: Completion ratio in range [0.0, 1.0].
    """
    if isinstance(element_bounding_box, (tuple, list)) and len(element_bounding_box) == 6:
        bbox = BoundingBox(
            float(element_bounding_box[0]),
            float(element_bounding_box[1]),
            float(element_bounding_box[2]),
            float(element_bounding_box[3]),
            float(element_bounding_box[4]),
            float(element_bounding_box[5]),
        )
    elif isinstance(element_bounding_box, dict):
        bbox = BoundingBox(
            min_x=float(element_bounding_box["min_x"]),
            min_y=float(element_bounding_box["min_y"]),
            min_z=float(element_bounding_box["min_z"]),
            max_x=float(element_bounding_box["max_x"]),
            max_y=float(element_bounding_box["max_y"]),
            max_z=float(element_bounding_box["max_z"]),
        )
    elif isinstance(element_bounding_box, BoundingBox):
        bbox = element_bounding_box
    elif hasattr(element_bounding_box, "min_x"):
        bbox = BoundingBox(
            min_x=float(getattr(element_bounding_box, "min_x")),
            min_y=float(getattr(element_bounding_box, "min_y")),
            min_z=float(getattr(element_bounding_box, "min_z")),
            max_x=float(getattr(element_bounding_box, "max_x")),
            max_y=float(getattr(element_bounding_box, "max_y")),
            max_z=float(getattr(element_bounding_box, "max_z")),
        )
    else:
        raise TypeError(f"Invalid bounding box type: {type(element_bounding_box)}")

    vol = bbox.volume
    if vol <= 0.0 or min_point_density <= 0.0:
        return 0.0

    pts = np.asarray(scan_points, dtype=np.float64)
    if pts.size == 0 or pts.ndim != 2 or pts.shape[1] < 3:
        return 0.0

    in_box = (
        (pts[:, 0] >= bbox.min_x) & (pts[:, 0] <= bbox.max_x) &
        (pts[:, 1] >= bbox.min_y) & (pts[:, 1] <= bbox.max_y) &
        (pts[:, 2] >= bbox.min_z) & (pts[:, 2] <= bbox.max_z)
    )

    point_count = int(np.sum(in_box))
    density = point_count / vol
    ratio = min(1.0, max(0.0, density / min_point_density))
    return float(ratio)


def calculate_evm_metrics(
    manifest: CrashingManifest,
    schedule_res: Optional[ScheduleResult] = None,
) -> EVMMetrics:
    """
    Computes Earned Value Management (EVM) metrics for a construction schedule.

    Metrics computed:
      - Budget at Completion (BAC)
      - Planned Value (PV)
      - Earned Value (EV)
      - Actual Cost (AC)
      - Schedule Variance (SV = EV - PV)
      - Cost Variance (CV = EV - AC)
      - Schedule Performance Index (SPI = EV / PV)
      - Cost Performance Index (CPI = EV / AC)
    """
    if schedule_res is None:
        schedule_res = solve_schedule(manifest)

    bac = schedule_res.total_cost
    overall_actual_pct = schedule_res.overall_progress_percent
    ev = round((overall_actual_pct / 100.0) * bac, 2)

    sc = schedule_res.s_curve
    as_of_date_str = manifest.as_of_date or ""
    planned_pct = 0.0

    if sc and sc.dates:
        if as_of_date_str in sc.dates:
            idx = sc.dates.index(as_of_date_str)
            planned_pct = sc.planned_early_percent[idx] if idx < len(sc.planned_early_percent) else 0.0
        else:
            matched_pcts = [
                sc.planned_early_percent[idx]
                for idx, dt_str in enumerate(sc.dates)
                if dt_str <= as_of_date_str and idx < len(sc.planned_early_percent)
            ]
            if matched_pcts:
                planned_pct = matched_pcts[-1]
            elif sc.planned_early_percent:
                planned_pct = sc.planned_early_percent[0]

    pv = round((planned_pct / 100.0) * bac, 2)

    total_ac = 0.0
    for act in manifest.activities:
        res_act = schedule_res.activities.get(act.id)
        add_c = res_act.added_cost if res_act else 0.0
        c_cost = act.normal_cost + add_c
        act_pct = act.progress_percent
        total_ac += c_cost * (act_pct / 100.0)

    ac = round(total_ac, 2) if total_ac > 0 else ev

    sv = round(ev - pv, 2)
    cv = round(ev - ac, 2)
    spi = round(ev / pv, 4) if pv > 0 else 1.0
    cpi = round(ev / ac, 4) if ac > 0 else 1.0

    return EVMMetrics(
        as_of_date=as_of_date_str or "Day 0",
        budget_at_completion=bac,
        planned_value=pv,
        earned_value=ev,
        actual_cost=ac,
        schedule_variance=sv,
        cost_variance=cv,
        schedule_performance_index=spi,
        cost_performance_index=cpi,
    )


def sync_scan_to_schedule(
    manifest: Union[CrashingManifest, str, Path],
    scan_ply_path: Union[str, Path],
    scan_date: str,
    model_manifest: Optional[Union[Any, str, Path]] = None,
    min_point_density: float = 100.0,
) -> CrashingManifest:
    """
    Connects time-series site scans (.ply) directly with debim.schedule:
      1. Evaluates physical element completion ratios from point cloud scan density.
      2. Updates activity.progress_percent, status, and appends ProgressLogEntry.
      3. Sets manifest.as_of_date = scan_date.
      4. Re-evaluates payment milestones and updates S-Curve actual series.
    """
    if isinstance(manifest, (str, Path)):
        from debim.schedule.schema import load_schedule_yaml
        crashing_manifest = load_schedule_yaml(manifest)
    else:
        crashing_manifest = manifest

    from debim.scan.calibrator import load_ply
    pts, _ = load_ply(scan_ply_path)

    resolved_elems = []
    if model_manifest is not None:
        if isinstance(model_manifest, (str, Path)):
            from debim.schema import load_manifest
            from debim.resolver import resolve_manifest
            resolved_elems = resolve_manifest(load_manifest(model_manifest)).elements
        elif hasattr(model_manifest, "elements"):
            from debim.resolver import resolve_manifest
            resolved_elems = resolve_manifest(model_manifest).elements
    else:
        for def_p in [Path("project.yaml"), Path("project.debim")]:
            if def_p.exists():
                from debim.schema import load_manifest
                from debim.resolver import resolve_manifest
                resolved_elems = resolve_manifest(load_manifest(def_p)).elements
                break

    elem_map = {getattr(e, "tag", None): e for e in resolved_elems if getattr(e, "tag", None)}

    from debim.compliance import get_element_aabb

    for act in crashing_manifest.activities:
        if not act.element_ids:
            continue

        ratios = []
        for elem_tag in act.element_ids:
            if elem_tag in elem_map:
                elem = elem_map[elem_tag]
                aabb = get_element_aabb(elem)
                bbox = BoundingBox(*aabb)
                r = evaluate_element_presence(bbox, pts, min_point_density=min_point_density)
                ratios.append(r)

        if ratios:
            avg_ratio = sum(ratios) / len(ratios)
            detected_pct = round(avg_ratio * 100.0, 2)

            act.progress_percent = detected_pct
            if detected_pct >= 100.0:
                act.status = "COMPLETED"
                if not act.actual_finish:
                    act.actual_finish = scan_date
                if not act.actual_start:
                    act.actual_start = scan_date
            elif detected_pct > 0.0:
                act.status = "IN_PROGRESS"
                if not act.actual_start:
                    act.actual_start = scan_date
            else:
                act.status = "NOT_STARTED"

            # Append or update progress_log
            updated_log = False
            for entry in act.progress_log:
                if entry.date == scan_date:
                    entry.percent = detected_pct
                    entry.notes = f"Updated via site scan on {scan_date}"
                    updated_log = True
                    break

            if not updated_log:
                act.progress_log.append(
                    ProgressLogEntry(
                        date=scan_date,
                        percent=detected_pct,
                        notes=f"Detected via 4D site scan on {scan_date}",
                    )
                )

    crashing_manifest.as_of_date = scan_date

    # Solve schedule to re-evaluate milestones and S-curve actual series
    _ = solve_schedule(crashing_manifest)

    return crashing_manifest
