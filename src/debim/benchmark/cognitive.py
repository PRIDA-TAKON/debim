"""
Round-Trip Cognitive Regression Benchmark Engine for debim.
Measures 2D architectural blueprint clarity and benchmarks AI Vision models
as autonomous architectural assistants.
"""

from dataclasses import dataclass
import json
import math
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import yaml

from pydantic import BaseModel, ConfigDict, Field

from debim.draw.renderer import SheetConfig, render_sheet
from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedCurtainWall,
    ResolvedDoor,
    ResolvedManifest,
    ResolvedPlate,
    ResolvedWall,
    ResolvedWindow,
    resolve_manifest,
)
from debim.schema import ProjectManifest, load_manifest


def _normalize_manifest(manifest_input: Union[ProjectManifest, dict, str, Path]) -> ProjectManifest:
    """Helper to convert any supported input into a validated ProjectManifest."""
    if isinstance(manifest_input, ProjectManifest):
        return manifest_input
    elif isinstance(manifest_input, dict):
        return ProjectManifest.model_validate(manifest_input)
    elif isinstance(manifest_input, (str, Path)):
        p = Path(manifest_input)
        if p.exists() and p.is_file():
            return load_manifest(p)
        elif isinstance(manifest_input, str) and ("\n" in manifest_input or "schema_version" in manifest_input or "project:" in manifest_input):
            data = yaml.safe_load(manifest_input) or {}
            return ProjectManifest.model_validate(data)
    raise ValueError(f"Unable to parse ProjectManifest from input type: {type(manifest_input)}")


@dataclass
class ElementRecord:
    """Internal element representation for spatial matching and metric calculation."""
    tag: str
    category: str
    center: Tuple[float, float, float]
    dimensions: Dict[str, float]
    raw: Any = None


def extract_element_records(manifest: ProjectManifest) -> List[ElementRecord]:
    """Extract element 3D spatial center coordinates and dimensions from ProjectManifest."""
    try:
        resolved = resolve_manifest(manifest)
    except Exception:
        resolved = None

    records: List[ElementRecord] = []

    # Process elements
    for elem in manifest.elements:
        elem_cls = getattr(elem, "class_", elem.__class__.__name__)
        tag = getattr(elem, "tag", f"{elem_cls}_UNTAGGED")

        # Check resolved manifest first
        res_obj = resolved.get_element_by_tag(tag) if resolved else None

        center = (0.0, 0.0, 0.0)
        dimensions: Dict[str, float] = {}

        if isinstance(res_obj, ResolvedColumn):
            cx = (res_obj.start_point[0] + res_obj.end_point[0]) / 2.0
            cy = (res_obj.start_point[1] + res_obj.end_point[1]) / 2.0
            cz = (res_obj.start_point[2] + res_obj.end_point[2]) / 2.0
            center = (cx, cy, cz)

            prof = getattr(res_obj.element, "profile", None)
            if prof is not None:
                if hasattr(prof, "width") and prof.width is not None:
                    dimensions["width"] = float(prof.width)
                if hasattr(prof, "depth") and prof.depth is not None:
                    dimensions["depth"] = float(prof.depth)
            dimensions["height"] = res_obj.height

        elif isinstance(res_obj, ResolvedWall):
            cx = (res_obj.start_point[0] + res_obj.end_point[0]) / 2.0
            cy = (res_obj.start_point[1] + res_obj.end_point[1]) / 2.0
            cz = res_obj.start_point[2] + res_obj.height / 2.0
            center = (cx, cy, cz)
            dimensions = {"thickness": res_obj.thickness, "height": res_obj.height, "length": res_obj.length}

            # Process wall children (doors/windows attached to wall)
            for child in getattr(elem, "doors", []) + getattr(elem, "windows", []) + getattr(elem, "children", []):
                c_cls = getattr(child, "class_", child.__class__.__name__)
                c_tag = getattr(child, "tag", f"{c_cls}_UNTAGGED")
                res_child = resolved.get_element_by_tag(c_tag) if resolved else None
                c_dim: Dict[str, float] = {}
                if hasattr(child, "dimensions") and child.dimensions is not None:
                    c_dim["width"] = getattr(child.dimensions, "width", 0.0)
                    c_dim["height"] = getattr(child.dimensions, "height", 0.0)

                c_center = (cx, cy, cz)
                if isinstance(res_child, (ResolvedDoor, ResolvedWindow)):
                    c_cx = (res_child.start_point[0] + res_child.end_point[0]) / 2.0
                    c_cy = (res_child.start_point[1] + res_child.end_point[1]) / 2.0
                    c_cz = res_child.elevation + res_child.height / 2.0
                    c_center = (c_cx, c_cy, c_cz)
                    c_dim["width"] = res_child.width
                    c_dim["height"] = res_child.height

                records.append(ElementRecord(tag=c_tag, category=c_cls, center=c_center, dimensions=c_dim, raw=child))

        elif isinstance(res_obj, ResolvedDoor):
            cx = (res_obj.start_point[0] + res_obj.end_point[0]) / 2.0
            cy = (res_obj.start_point[1] + res_obj.end_point[1]) / 2.0
            cz = res_obj.elevation + res_obj.height / 2.0
            center = (cx, cy, cz)
            dimensions = {"width": res_obj.width, "height": res_obj.height}
        elif isinstance(res_obj, ResolvedWindow):
            cx = (res_obj.start_point[0] + res_obj.end_point[0]) / 2.0
            cy = (res_obj.start_point[1] + res_obj.end_point[1]) / 2.0
            cz = res_obj.elevation + res_obj.height / 2.0
            center = (cx, cy, cz)
            dimensions = {"width": res_obj.width, "height": res_obj.height}
        elif isinstance(res_obj, ResolvedBeam):
            cx = (res_obj.start_point[0] + res_obj.end_point[0]) / 2.0
            cy = (res_obj.start_point[1] + res_obj.end_point[1]) / 2.0
            cz = res_obj.start_point[2]
            center = (cx, cy, cz)
            dimensions = {"width": res_obj.width, "height": res_obj.height, "length": res_obj.span_length}
        elif isinstance(res_obj, ResolvedCurtainWall):
            cx = (res_obj.start_point[0] + res_obj.end_point[0]) / 2.0
            cy = (res_obj.start_point[1] + res_obj.end_point[1]) / 2.0
            cz = res_obj.elevation + res_obj.height / 2.0
            center = (cx, cy, cz)
            dimensions = {"height": res_obj.height, "length": res_obj.length}
        elif isinstance(res_obj, ResolvedPlate):
            center = (getattr(res_obj, "center_x", 0.0), getattr(res_obj, "center_y", 0.0), res_obj.elevation)
            dimensions = {"thickness": res_obj.thickness, "width": getattr(res_obj, "width", 0.0), "depth": getattr(res_obj, "depth", 0.0)}
        else:
            # Fallback schema extraction
            if hasattr(elem, "dimensions") and elem.dimensions is not None:
                dimensions["width"] = getattr(elem.dimensions, "width", 0.0)
                dimensions["height"] = getattr(elem.dimensions, "height", 0.0)
                dimensions["depth"] = getattr(elem.dimensions, "depth", 0.0)
            if hasattr(elem, "thickness") and elem.thickness is not None:
                dimensions["thickness"] = float(elem.thickness)
            if hasattr(elem, "height") and elem.height is not None:
                dimensions["height"] = float(elem.height)

        records.append(ElementRecord(tag=tag, category=elem_cls, center=center, dimensions=dimensions, raw=elem))

    return records


class CognitiveBenchmarkResult(BaseModel):
    """Benchmark results and Cognitive Drafting Quality Score (CDQS) report."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    model_name: str = "default_model"
    scene_id: str = "scene_01"
    cdqs: float = Field(..., description="Cognitive Drafting Quality Score (0.0 - 100.0)")
    entity_retention_rate: float = Field(..., description="Overall element retention rate percentage")
    retention_by_category: Dict[str, float] = Field(default_factory=dict, description="Retention rate % breakdown per IFC element category")
    gt_element_count: int = 0
    reconstructed_element_count: int = 0
    matched_element_count: int = 0
    phantom_element_count: int = 0
    structural_fail_flag: bool = Field(False, description="Fail flag set if critical structural elements (columns/walls) vanish")
    coordinate_mae: float = Field(0.0, description="Mean Absolute Error in element center coordinates (meters)")
    dimension_mae: float = Field(0.0, description="Mean Absolute Error in element dimensions (meters)")
    hallucination_score: float = Field(0.0, description="Ratio of phantom / hallucinated elements relative to ground truth")
    execution_time_ms: float = Field(0.0, description="Vision model callback execution time in milliseconds")


class CognitiveBenchmarkEngine:
    """
    Round-Trip Cognitive Regression Benchmark Engine.
    Compiles BIM manifests into 2D Architectural SVG blueprints, interfaces with AI Vision models,
    and calculates deterministic cognitive performance metrics.
    """

    def __init__(
        self,
        agent_callback: Optional[Callable[[str], Union[ProjectManifest, dict, str, Path]]] = None,
        max_spatial_distance_m: float = 2.0,
    ):
        self.agent_callback = agent_callback
        self.max_spatial_distance_m = max_spatial_distance_m

    def render_blueprint(
        self,
        manifest: Union[ProjectManifest, dict, str, Path],
        sheet_config: Optional[Union[SheetConfig, dict, Path, str]] = None,
    ) -> str:
        """Compile ground truth ProjectManifest to 2D Architectural SVG Blueprint."""
        gt_manifest = _normalize_manifest(manifest)
        return render_sheet(gt_manifest, sheet_config=sheet_config)

    def evaluate(
        self,
        ground_truth: Union[ProjectManifest, dict, str, Path],
        reconstructed: Union[ProjectManifest, dict, str, Path],
        model_name: str = "unknown",
        scene_id: str = "scene_01",
        execution_time_ms: float = 0.0,
    ) -> CognitiveBenchmarkResult:
        """Deterministic comparison between Ground Truth and Reconstructed model."""
        gt_manifest = _normalize_manifest(ground_truth)
        rec_manifest = _normalize_manifest(reconstructed)

        gt_records = extract_element_records(gt_manifest)
        rec_records = extract_element_records(rec_manifest)

        gt_count = len(gt_records)
        rec_count = len(rec_records)

        # 1. Match Elements (Tag match first, then spatial proximity match)
        matched_pairs: List[Tuple[ElementRecord, ElementRecord]] = []
        matched_gt_indices = set()
        matched_rec_indices = set()

        # Step A: Tag & Category exact match
        for i, gt_rec in enumerate(gt_records):
            for j, rec_rec in enumerate(rec_records):
                if j in matched_rec_indices:
                    continue
                if gt_rec.tag == rec_rec.tag and gt_rec.category == rec_rec.category:
                    matched_pairs.append((gt_rec, rec_rec))
                    matched_gt_indices.add(i)
                    matched_rec_indices.add(j)
                    break

        # Step B: Spatial proximity match for remaining unmatched elements of same category
        for i, gt_rec in enumerate(gt_records):
            if i in matched_gt_indices:
                continue
            best_j = None
            best_dist = float("inf")
            for j, rec_rec in enumerate(rec_records):
                if j in matched_rec_indices:
                    continue
                if gt_rec.category == rec_rec.category:
                    dx = gt_rec.center[0] - rec_rec.center[0]
                    dy = gt_rec.center[1] - rec_rec.center[1]
                    dz = gt_rec.center[2] - rec_rec.center[2]
                    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if dist <= self.max_spatial_distance_m and dist < best_dist:
                        best_dist = dist
                        best_j = j

            if best_j is not None:
                matched_pairs.append((gt_rec, rec_records[best_j]))
                matched_gt_indices.add(i)
                matched_rec_indices.add(best_j)

        matched_count = len(matched_pairs)
        phantom_count = len(rec_records) - matched_count

        # 2. Entity Retention Rate & Category Breakdown
        entity_retention_rate = (matched_count / gt_count * 100.0) if gt_count > 0 else 100.0

        retention_by_category: Dict[str, float] = {}
        gt_by_cat: Dict[str, int] = {}
        matched_by_cat: Dict[str, int] = {}

        for gt_rec in gt_records:
            gt_by_cat[gt_rec.category] = gt_by_cat.get(gt_rec.category, 0) + 1

        for gt_rec, _ in matched_pairs:
            matched_by_cat[gt_rec.category] = matched_by_cat.get(gt_rec.category, 0) + 1

        for cat, count in gt_by_cat.items():
            m_count = matched_by_cat.get(cat, 0)
            retention_by_category[cat] = (m_count / count * 100.0) if count > 0 else 100.0

        # 3. Structural Fail Flag Check
        structural_fail = False
        critical_categories = ["IfcColumn", "IfcWall"]
        for crit_cat in critical_categories:
            if gt_by_cat.get(crit_cat, 0) > 0 and matched_by_cat.get(crit_cat, 0) == 0:
                structural_fail = True
                break

        # 4. Coordinate MAE Calculation (Meters)
        coord_errors: List[float] = []
        dim_errors: List[float] = []

        for gt_rec, rec_rec in matched_pairs:
            dx = gt_rec.center[0] - rec_rec.center[0]
            dy = gt_rec.center[1] - rec_rec.center[1]
            dz = gt_rec.center[2] - rec_rec.center[2]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            coord_errors.append(dist)

            # Common dimensions MAE
            common_keys = set(gt_rec.dimensions.keys()).intersection(set(rec_rec.dimensions.keys()))
            for k in common_keys:
                dim_err = abs(gt_rec.dimensions[k] - rec_rec.dimensions[k])
                dim_errors.append(dim_err)

        coord_mae = (sum(coord_errors) / len(coord_errors)) if coord_errors else 0.0
        dim_mae = (sum(dim_errors) / len(dim_errors)) if dim_errors else 0.0

        # 5. Hallucination / Clutter Score
        if gt_count > 0:
            hallucination_score = phantom_count / float(gt_count)
        else:
            hallucination_score = 1.0 if phantom_count > 0 else 0.0

        # 6. Composite Score: Cognitive Drafting Quality Score (CDQS)
        retention_score = entity_retention_rate  # 0 to 100
        coord_score = max(0.0, 100.0 * math.exp(-0.5 * coord_mae))
        clutter_score = max(0.0, 100.0 * (1.0 - min(1.0, hallucination_score)))

        raw_cdqs = 0.50 * retention_score + 0.35 * coord_score + 0.15 * clutter_score

        if structural_fail:
            cdqs = min(raw_cdqs, 20.0)
        else:
            cdqs = round(raw_cdqs, 2)

        return CognitiveBenchmarkResult(
            model_name=model_name,
            scene_id=scene_id,
            cdqs=cdqs,
            entity_retention_rate=round(entity_retention_rate, 2),
            retention_by_category={k: round(v, 2) for k, v in retention_by_category.items()},
            gt_element_count=gt_count,
            reconstructed_element_count=rec_count,
            matched_element_count=matched_count,
            phantom_element_count=phantom_count,
            structural_fail_flag=structural_fail,
            coordinate_mae=round(coord_mae, 4),
            dimension_mae=round(dim_mae, 4),
            hallucination_score=round(hallucination_score, 4),
            execution_time_ms=round(execution_time_ms, 2),
        )

    def run_roundtrip(
        self,
        ground_truth: Union[ProjectManifest, dict, str, Path],
        model_name: str = "unknown",
        scene_id: str = "scene_01",
        agent_callback: Optional[Callable[[str], Union[ProjectManifest, dict, str, Path]]] = None,
        sheet_config: Optional[Union[SheetConfig, dict, Path, str]] = None,
    ) -> CognitiveBenchmarkResult:
        """Closed-loop roundtrip evaluation from ground truth manifest through 2D SVG blueprint reconstruction."""
        cb = agent_callback or self.agent_callback
        if cb is None:
            raise ValueError("No agent_callback provided for round-trip cognitive benchmark execution.")

        gt_manifest = _normalize_manifest(ground_truth)

        # 1. Render Ground Truth to 2D Blueprint SVG
        blueprint_svg = self.render_blueprint(gt_manifest, sheet_config=sheet_config)

        # 2. Invoke Vision Model Callback & Measure Execution Time
        t0 = time.perf_counter()
        reconstructed_manifest_input = cb(blueprint_svg)
        t1 = time.perf_counter()
        exec_ms = (t1 - t0) * 1000.0

        # 3. Deterministic Evaluation
        return self.evaluate(
            ground_truth=gt_manifest,
            reconstructed=reconstructed_manifest_input,
            model_name=model_name,
            scene_id=scene_id,
            execution_time_ms=exec_ms,
        )


def run_cognitive_benchmark(
    ground_truth: Union[ProjectManifest, dict, str, Path],
    reconstructed_or_callback: Union[ProjectManifest, dict, str, Path, Callable],
    model_name: str = "vision_assistant",
    scene_id: str = "scene_01",
) -> CognitiveBenchmarkResult:
    """Convenience entry point for running Cognitive Regression Benchmark."""
    engine = CognitiveBenchmarkEngine()
    if callable(reconstructed_or_callback):
        return engine.run_roundtrip(
            ground_truth=ground_truth,
            model_name=model_name,
            scene_id=scene_id,
            agent_callback=reconstructed_or_callback,
        )
    else:
        return engine.evaluate(
            ground_truth=ground_truth,
            reconstructed=reconstructed_or_callback,
            model_name=model_name,
            scene_id=scene_id,
        )


def generate_json_report(
    results: Union[CognitiveBenchmarkResult, List[CognitiveBenchmarkResult]],
) -> str:
    """Export benchmark summary report in JSON format."""
    res_list = [results] if isinstance(results, CognitiveBenchmarkResult) else results
    dumped = [r.model_dump() for r in res_list]
    return json.dumps(dumped, indent=2)


def generate_markdown_report(
    results: Union[CognitiveBenchmarkResult, List[CognitiveBenchmarkResult]],
    title: str = "Cognitive Regression Benchmark Leaderboard",
) -> str:
    """Generate Markdown summary table and model leaderboard."""
    res_list = [results] if isinstance(results, CognitiveBenchmarkResult) else results
    sorted_results = sorted(res_list, key=lambda r: r.cdqs, reverse=True)

    lines = [
        f"# {title}",
        "",
        "| Rank | AI Model | Scene | CDQS Score | Retention % | Coord MAE (m) | Phantom Elems | Structural Fail | Time (ms) |",
        "| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for rank, r in enumerate(sorted_results, 1):
        fail_str = "**FAIL**" if r.structural_fail_flag else "PASS"
        lines.append(
            f"| {rank} | `{r.model_name}` | `{r.scene_id}` | **{r.cdqs:.2f}** | {r.entity_retention_rate:.1f}% | {r.coordinate_mae:.3f} | {r.phantom_element_count} | {fail_str} | {r.execution_time_ms:.1f} |"
        )

    lines.append("")
    return "\n".join(lines)
