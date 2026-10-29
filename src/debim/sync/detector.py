"""
debim.sync.detector

As-built change detection engine.
Compares resolved model elements against scan deviation measurements and generates ChangeProposal objects
for components that have shifted beyond a specified threshold.
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from debim.compat import BaseModel as CompatBaseModel, Field as CompatField


class ElementDeviation(CompatBaseModel):
    tag: str
    measured_position: Optional[Tuple[float, float, float]] = None
    measured_start: Optional[Tuple[float, float, float]] = None
    measured_end: Optional[Tuple[float, float, float]] = None
    measured_offset_x: Optional[float] = None
    measured_offset_y: Optional[float] = None
    measured_offset_distance: Optional[float] = None
    delta_x: Optional[float] = None
    delta_y: Optional[float] = None
    delta_z: Optional[float] = None
    mean_deviation_mm: Optional[float] = None
    signed_deviation_mm: Optional[float] = None
    absolute_error_mm: Optional[float] = None
    rms_error_mm: Optional[float] = None
    max_error_mm: Optional[float] = None
    point_count: Optional[int] = None


class DeviationResult(CompatBaseModel):
    deviations: List[ElementDeviation] = CompatField(default_factory=list)
    metadata: Dict[str, Any] = CompatField(default_factory=dict)


class ChangeProposal(CompatBaseModel):
    tag: str
    element_class: str
    field_name: str
    current_value: Any
    proposed_value: Any
    deviation_mm: float
    description: Optional[str] = None


def detect_asbuilt_discrepancies(
    model_elements: List[Any],
    scan_deviations: Union[DeviationResult, Dict[str, Any]],
    threshold_mm: float = 30.0,
) -> List[ChangeProposal]:
    """
    Detects spatial discrepancies between resolved model elements and scan deviations.

    Args:

        model_elements: List of resolved model elements (e.g. ResolvedColumn, ResolvedWall, etc.)
            or unresolved manifest elements.
        scan_deviations: DeviationResult object or dict containing element deviations.
        threshold_mm: Acceptable tolerance threshold in millimeters (default: 30.0 mm).

    Returns:
        List of ChangeProposal objects for components exceeding threshold_mm.
    """
    if isinstance(scan_deviations, dict):
        if "deviations" in scan_deviations:
            dev_list = [
                d if isinstance(d, ElementDeviation) else ElementDeviation(**d)
                for d in scan_deviations["deviations"]
            ]
            scan_dev = DeviationResult(
                deviations=dev_list,
                metadata=scan_deviations.get("metadata", {}),
            )
        else:
            # Map of tag -> deviation dict
            dev_list = []
            for tag, d_data in scan_deviations.items():
                if isinstance(d_data, dict):
                    dev_list.append(ElementDeviation(tag=tag, **d_data))
            scan_dev = DeviationResult(deviations=dev_list)
    else:
        scan_dev = scan_deviations

    dev_by_tag: Dict[str, ElementDeviation] = {
        d.tag: d for d in scan_dev.deviations
    }

    proposals: List[ChangeProposal] = []

    for elem in model_elements:
        tag = getattr(elem, "tag", None) or getattr(elem, "id", None)
        if not tag or tag not in dev_by_tag:
            continue

        dev = dev_by_tag[tag]
        elem_cls = getattr(elem, "element_class", None) or getattr(elem, "class_", None) or type(elem).__name__
        if elem_cls.startswith("Resolved"):
            elem_cls = "Ifc" + elem_cls[8:]

        # Check explicit delta_x / delta_y
        if dev.delta_x is not None or dev.delta_y is not None:
            dx = dev.delta_x or 0.0
            dy = dev.delta_y or 0.0
            dz = dev.delta_z or 0.0
            dist_m = math.sqrt(dx * dx + dy * dy + dz * dz)
            dist_mm = dist_m * 1000.0

            if dist_mm >= threshold_mm:
                curr_offset_x = 0.0
                curr_offset_y = 0.0
                placement = getattr(elem, "placement", None)
                if placement:
                    curr_offset_x = getattr(placement, "offset_x", 0.0) or 0.0
                    curr_offset_y = getattr(placement, "offset_y", 0.0) or 0.0

                if dx != 0.0:
                    new_offset_x = round(curr_offset_x + dx, 4)
                    proposals.append(
                        ChangeProposal(
                            tag=tag,
                            element_class=elem_cls,
                            field_name="offset_x",
                            current_value=curr_offset_x,
                            proposed_value=new_offset_x,
                            deviation_mm=round(dist_mm, 2),
                            description=f"Shifted by {dx*1000:.1f}mm along X axis",
                        )
                    )
                if dy != 0.0:
                    new_offset_y = round(curr_offset_y + dy, 4)
                    proposals.append(
                        ChangeProposal(
                            tag=tag,
                            element_class=elem_cls,
                            field_name="offset_y",
                            current_value=curr_offset_y,
                            proposed_value=new_offset_y,
                            deviation_mm=round(dist_mm, 2),
                            description=f"Shifted by {dy*1000:.1f}mm along Y axis",
                        )
                    )
            continue

        # Check measured_offset_x / measured_offset_y / measured_offset_distance
        if dev.measured_offset_x is not None or dev.measured_offset_y is not None:
            curr_offset_x = 0.0
            curr_offset_y = 0.0
            placement = getattr(elem, "placement", None)
            if placement:
                curr_offset_x = getattr(placement, "offset_x", 0.0) or 0.0
                curr_offset_y = getattr(placement, "offset_y", 0.0) or 0.0

            if dev.measured_offset_x is not None:
                diff_mm = abs(dev.measured_offset_x - curr_offset_x) * 1000.0
                if diff_mm >= threshold_mm:
                    proposals.append(
                        ChangeProposal(
                            tag=tag,
                            element_class=elem_cls,
                            field_name="offset_x",
                            current_value=curr_offset_x,
                            proposed_value=round(dev.measured_offset_x, 4),
                            deviation_mm=round(diff_mm, 2),
                            description=f"Offset X discrepancy: {diff_mm:.1f}mm",
                        )
                    )

            if dev.measured_offset_y is not None:
                diff_mm = abs(dev.measured_offset_y - curr_offset_y) * 1000.0
                if diff_mm >= threshold_mm:
                    proposals.append(
                        ChangeProposal(
                            tag=tag,
                            element_class=elem_cls,
                            field_name="offset_y",
                            current_value=curr_offset_y,
                            proposed_value=round(dev.measured_offset_y, 4),
                            deviation_mm=round(diff_mm, 2),
                            description=f"Offset Y discrepancy: {diff_mm:.1f}mm",
                        )
                    )

            continue

        if dev.measured_offset_distance is not None:
            curr_off_dist = getattr(elem, "offset_distance", 0.0) or 0.0
            diff_mm = abs(dev.measured_offset_distance - curr_off_dist) * 1000.0
            if diff_mm >= threshold_mm:
                proposals.append(
                    ChangeProposal(
                        tag=tag,
                        element_class=elem_cls,
                        field_name="offset_distance",
                        current_value=curr_off_dist,
                        proposed_value=round(dev.measured_offset_distance, 4),
                        deviation_mm=round(diff_mm, 2),
                        description=f"Offset distance discrepancy: {diff_mm:.1f}mm",
                    )
                )
            continue

        # Check measured_position vs start_point or center
        if dev.measured_position is not None:
            curr_pos = getattr(elem, "start_point", None) or getattr(elem, "center", None) or getattr(elem, "position", None)
            if curr_pos is not None and len(curr_pos) >= 2:
                mx, my = dev.measured_position[0], dev.measured_position[1]
                cx, cy = curr_pos[0], curr_pos[1]
                dx = mx - cx
                dy = my - cy
                dist_m = math.hypot(dx, dy)
                dist_mm = dist_m * 1000.0

                if dist_mm >= threshold_mm:
                    curr_offset_x = 0.0
                    curr_offset_y = 0.0
                    placement = getattr(elem, "placement", None)
                    if placement:
                        curr_offset_x = getattr(placement, "offset_x", 0.0) or 0.0
                        curr_offset_y = getattr(placement, "offset_y", 0.0) or 0.0

                    if abs(dx * 1000.0) >= threshold_mm:
                        proposals.append(
                            ChangeProposal(
                                tag=tag,
                                element_class=elem_cls,
                                field_name="offset_x",
                                current_value=curr_offset_x,
                                proposed_value=round(curr_offset_x + dx, 4),
                                deviation_mm=round(dist_mm, 2),
                                description=f"Relocated by {dx*1000:.1f}mm along X axis",
                            )
                        )
                    if abs(dy * 1000.0) >= threshold_mm:
                        proposals.append(
                            ChangeProposal(
                                tag=tag,
                                element_class=elem_cls,
                                field_name="offset_y",
                                current_value=curr_offset_y,
                                proposed_value=round(curr_offset_y + dy, 4),
                                deviation_mm=round(dist_mm, 2),
                                description=f"Relocated by {dy*1000:.1f}mm along Y axis",
                            )
                        )

    return proposals
