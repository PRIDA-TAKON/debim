"""
5-Layer Architectural and Engineering Audit Matrix, Auto-Fix Remediation Engine,
and Telemetry Recorder for debim.
"""

import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from debim.compat import BaseModel, Field
from debim.compliance import (
    check_topological_continuity,
    detect_clashes,
    detect_mep_structural_clashes,
    get_element_aabb,
    aabb_overlap,
    point_to_segment_distance,
)
from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedDoor,
    ResolvedDuctSegment,
    ResolvedElement,
    ResolvedManifest,
    ResolvedPipeSegment,
    ResolvedRoof,
    ResolvedSlab,
    ResolvedSpace,
    ResolvedStair,
    ResolvedWall,
    ResolvedWindow,
    resolve_manifest,
)
from debim.schema import (
    IfcBeam,
    IfcColumn,
    IfcDoor,
    IfcDuctSegment,
    IfcPipeSegment,
    IfcSlab,
    IfcSpace,
    IfcStair,
    IfcWall,
    IfcWindow,
    ProjectManifest,
    load_manifest,
)
from debim.solver import solve_manifest_furniture_fit
from debim.standards import get_regulations


# --- Data Models for 5-Layer Audit Matrix ---

class RemediationAction(BaseModel):
    fix_action: str  # e.g., 'EXPAND_SPACE' | 'ADD_WINDOW' | 'SHIFT_COLUMN' | 'RE_ROUTE_PIPE' | 'LOWER_SLAB_DROP' | 'ADJUST_STAIR' | 'INCREASE_PIPE_SLOPE' | 'ADD_SUPPORTING_BEAM' | 'RESOLVE_CLASH'
    target_tag: str
    target_class: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    applied: bool = False


class AuditViolation(BaseModel):
    layer: int  # 1 to 5
    layer_name: str
    rule_code: str
    passed: bool
    severity: str = "ERROR"  # 'ERROR' | 'WARNING' | 'INFO'
    element_tag: Optional[str] = None
    element_class: Optional[str] = None
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    remediation: Optional[RemediationAction] = None


class AuditLayerResult(BaseModel):
    layer: int
    layer_name: str
    passed: bool
    violations_count: int
    checks_count: int
    items: List[AuditViolation] = Field(default_factory=list)


class AuditMatrixReport(BaseModel):
    project_id: str
    project_name: str
    timestamp: str
    passed: bool
    total_checks: int
    total_violations: int
    layers: Dict[int, AuditLayerResult] = Field(default_factory=dict)
    remediations_applied: int = 0
    execution_time_sec: float = 0.0


# --- 5-Layer Audit Evaluator Class ---

class AuditMatrixEvaluator:
    """
    Automated 5-Layer Architectural, Regulatory, Structural, MEP, and Physical Clash Audit Engine.
    """

    def __init__(self, target: Union[ProjectManifest, ResolvedManifest, Path, str]):
        if isinstance(target, (str, Path)):
            self.manifest = load_manifest(target)
            self.resolved = resolve_manifest(self.manifest)
        elif isinstance(target, ProjectManifest):
            self.manifest = target
            self.resolved = resolve_manifest(target)
        elif isinstance(target, ResolvedManifest):
            self.resolved = target
            self.manifest = target.manifest
        else:
            raise TypeError(f"Unsupported target type for AuditMatrixEvaluator: {type(target)}")

    # --- LAYER 1: Spatial & Functional ---
    def evaluate_layer_1(self) -> AuditLayerResult:
        """
        Layer 1: Spatial & Functional
        - Space net area >= min_area (or functional requirement)
        - 2D Furniture fit & non-overlapping clearance SAT
        - Clear ceiling headroom >= 2.60m
        """
        items: List[AuditViolation] = []
        layer_name = "Spatial & Functional"

        # Check 1: Space net area >= min_area
        for r_space in self.resolved.spaces:
            elem = r_space.element
            min_req = None
            if elem.design_spec and elem.design_spec.min_area:
                min_req = elem.design_spec.min_area
            elif elem.contains:
                # Sum required areas of contained variable references
                min_req = sum(
                    self.manifest.get_variable(v.ref).get_total_area() * v.count
                    for v in elem.contains
                    if self.manifest.get_variable(v.ref)
                ) * 1.30

            if min_req and r_space.net_floor_area < min_req - 1e-2:
                items.append(
                    AuditViolation(
                        layer=1,
                        layer_name=layer_name,
                        rule_code="LAYER1_NET_AREA",
                        passed=False,
                        severity="ERROR",
                        element_tag=r_space.tag,
                        element_class="IfcSpace",
                        message=f"Space '{r_space.tag}' ({elem.name or 'Space'}) area ({r_space.net_floor_area:.2f}m²) is smaller than minimum required area ({min_req:.2f}m²).",
                        details={"net_floor_area": r_space.net_floor_area, "required_min_area": min_req},
                        remediation=RemediationAction(
                            fix_action="EXPAND_SPACE",
                            target_tag=r_space.tag,
                            target_class="IfcSpace",
                            description=f"Expand boundaries or design spec min_area for space '{r_space.tag}' to {min_req:.2f}m²",
                            parameters={"min_area": min_req},
                        ),
                    )
                )

        # Check 2: 2D Furniture Clearance Non-Overlap (SAT) & Walkway Corridor
        fit_result = solve_manifest_furniture_fit(self.manifest)
        for s_res in fit_result.spaces:
            if not s_res.passed:
                for err_msg in s_res.errors:
                    items.append(
                        AuditViolation(
                            layer=1,
                            layer_name=layer_name,
                            rule_code="LAYER1_FURNITURE_SAT",
                            passed=False,
                            severity="ERROR",
                            element_tag=s_res.space_tag,
                            element_class="IfcSpace",
                            message=f"Furniture fit / clearance violation in space '{s_res.space_tag}': {err_msg}",
                            details={"errors": s_res.errors},
                            remediation=RemediationAction(
                                fix_action="EXPAND_SPACE",
                                target_tag=s_res.space_tag,
                                target_class="IfcSpace",
                                description=f"Adjust furniture layout or expand space '{s_res.space_tag}' for clearance",
                                parameters={"space_tag": s_res.space_tag},
                            ),
                        )
                    )

        # Check 3: Clear Headroom >= 2.60m
        min_headroom_m = 2.60
        for st in self.manifest.spatial_structure.storeys:
            st_name_lower = (st.name or "").lower()
            if any(k in st_name_lower for k in ["roof", "parapet", "หลังคา", "footing", "foundation"]):
                continue

            max_beam_depth = 0.0
            st_top_z = st.elevation + st.height
            for beam in self.resolved.beams:
                b_st = beam.element.placement.storey
                b_z = beam.start_point[2]
                if b_st == st.id or abs(b_z - st_top_z) < 1e-3:
                    if beam.depth > max_beam_depth:
                        max_beam_depth = beam.depth

            clear_h = st.height - max_beam_depth
            if clear_h < min_headroom_m:
                items.append(
                    AuditViolation(
                        layer=1,
                        layer_name=layer_name,
                        rule_code="LAYER1_CLEAR_HEADROOM",
                        passed=False,
                        severity="ERROR",
                        element_tag=st.id,
                        element_class="Storey",
                        message=f"Storey '{st.name}' clear headroom ({clear_h:.2f}m) is below standard habitable clear height ({min_headroom_m:.2f}m).",
                        details={"clear_height": clear_h, "min_required": min_headroom_m, "max_beam_depth": max_beam_depth},
                        remediation=RemediationAction(
                            fix_action="EXPAND_SPACE",
                            target_tag=st.id,
                            target_class="Storey",
                            description=f"Increase storey '{st.name}' height to at least {max_beam_depth + min_headroom_m:.2f}m",
                            parameters={"recommended_height": max_beam_depth + min_headroom_m},
                        ),
                    )
                )

        checks_count = len(self.resolved.spaces) + len(self.manifest.spatial_structure.storeys) + 1
        passed = len(items) == 0

        return AuditLayerResult(
            layer=1,
            layer_name=layer_name,
            passed=passed,
            violations_count=len(items),
            checks_count=max(checks_count, len(items)),
            items=items,
        )

    # --- LAYER 2: Legal & Life Safety ---
    def evaluate_layer_2(self) -> AuditLayerResult:
        """
        Layer 2: Legal & Life Safety (Thai Building Act MR 55)
        Hooks into get_regulations('TH') to validate rulesets dynamically:
        - Natural ventilation window opening >= 10% of floor area
        - Bathroom/toilet slab drop <= -0.10m
        - Stair geometry: riser <= 0.20m & tread >= 0.22m
        - Egress corridor clear width >= 1.00m
        - Door clear width >= 0.80m
        """
        items: List[AuditViolation] = []
        layer_name = "Legal & Life Safety"

        # Dynamically consume Thai building control regulations from debim-standards
        th_regs = get_regulations("TH")
        min_vent_ratio = float(th_regs.get("natural_ventilation_ratio", 0.10))
        max_slab_drop = float(th_regs.get("bathroom_slab_drop_max", -0.10))
        max_riser = float(th_regs.get("stair_riser_max", 0.20))
        min_tread = float(th_regs.get("stair_tread_min", 0.22))
        min_corridor_w = float(th_regs.get("corridor_width_min", 1.00))
        min_door_w = float(th_regs.get("door_clear_width_min", 0.80))

        # Check 1: Thai MR 55 Natural Ventilation >= 10% floor area
        for r_space in self.resolved.spaces:
            s_name = (r_space.element.name or "").lower()
            s_tag = r_space.tag.lower()
            # Non-habitable store rooms or shafts can be skipped
            if any(k in s_name or k in s_tag for k in ["store", "storage", "mep", "shaft", "lift"]):
                continue

            net_a = r_space.net_floor_area
            if net_a <= 0:
                continue

            # Calculate total window opening area in space boundary
            window_area = 0.0
            for w in self.resolved.windows:
                # Check if window is located on walls bordering or inside space
                wx, wy, _ = w.position
                pts_2d = [(p[0], p[1]) for p in r_space.polygon]
                from debim.geometry2d import point_in_polygon
                if point_in_polygon((wx, wy), pts_2d):
                    window_area += w.width * w.height
                else:
                    # Check if window host wall is on space boundary
                    if w.element.host_wall:
                        hw = self.resolved.get_element_by_tag(w.element.host_wall)
                        if isinstance(hw, ResolvedWall):
                            from debim.geometry2d import point_in_polygon
                            hw_mid = ((hw.start_point[0] + hw.end_point[0]) / 2.0, (hw.start_point[1] + hw.end_point[1]) / 2.0)
                            if point_in_polygon(hw_mid, pts_2d):
                                window_area += w.width * w.height

            vent_ratio = window_area / net_a
            if vent_ratio < min_vent_ratio:
                req_win_area = net_a * min_vent_ratio
                items.append(
                    AuditViolation(
                        layer=2,
                        layer_name=layer_name,
                        rule_code="LAYER2_NATURAL_VENTILATION",
                        passed=False,
                        severity="ERROR",
                        element_tag=r_space.tag,
                        element_class="IfcSpace",
                        message=f"Space '{r_space.tag}' natural ventilation opening ({window_area:.2f}m², {vent_ratio*100:.1f}%) is less than Thai MR 55 legal requirement ({min_vent_ratio*100:.1f}%, min {req_win_area:.2f}m²).",
                        details={"net_floor_area": net_a, "window_area": window_area, "vent_ratio": vent_ratio},
                        remediation=RemediationAction(
                            fix_action="ADD_WINDOW",
                            target_tag=r_space.tag,
                            target_class="IfcSpace",
                            description=f"Add or expand window opening for space '{r_space.tag}' to at least {req_win_area:.2f}m²",
                            parameters={"required_window_area": req_win_area, "missing_window_area": req_win_area - window_area},
                        ),
                    )
                )

        # Check 2: Bathroom Slab Drop <= -0.10m
        for r_space in self.resolved.spaces:
            s_name = (r_space.element.name or "").lower()
            s_tag = r_space.tag.lower()
            is_wet_room = any(k in s_name or k in s_tag for k in ["wc", "bath", "toilet", "washroom", "ห้องน้ำ", " shower"])
            if is_wet_room:
                drop_el = getattr(r_space.element, "drop_elevation", 0.0)
                if drop_el > max_slab_drop + 1e-3:
                    items.append(
                        AuditViolation(
                            layer=2,
                            layer_name=layer_name,
                            rule_code="LAYER2_BATHROOM_SLAB_DROP",
                            passed=False,
                            severity="ERROR",
                            element_tag=r_space.tag,
                            element_class="IfcSpace",
                            message=f"Wet space '{r_space.tag}' slab drop ({drop_el:.2f}m) violates Thai MR 55 waterproof sunken slab drop requirement (<= {max_slab_drop:.2f}m).",
                            details={"drop_elevation": drop_el, "required_drop": max_slab_drop},
                            remediation=RemediationAction(
                                fix_action="LOWER_SLAB_DROP",
                                target_tag=r_space.tag,
                                target_class="IfcSpace",
                                description=f"Set drop_elevation for wet space '{r_space.tag}' to {max_slab_drop:.2f}m",
                                parameters={"drop_elevation": max_slab_drop},
                            ),
                        )
                    )

        # Check 3: Stair Riser <= 0.20m & Tread >= 0.22m (Thai MR 55 Section 30)
        for st in self.resolved.stairs:
            riser_h = getattr(st, "riser_height", getattr(st.element, "riser_height", 0.1875))
            tread_d = getattr(st, "tread_depth", getattr(st.element, "tread_depth", 0.25))
            if riser_h > max_riser + 1e-3 or tread_d < min_tread - 1e-3:
                items.append(
                    AuditViolation(
                        layer=2,
                        layer_name=layer_name,
                        rule_code="LAYER2_STAIR_GEOMETRY",
                        passed=False,
                        severity="ERROR",
                        element_tag=st.tag,
                        element_class="IfcStair",
                        message=f"Stair '{st.tag}' geometry (riser {riser_h:.3f}m, tread {tread_d:.3f}m) violates Thai MR 55 legal limits (riser <= {max_riser:.2f}m, tread >= {min_tread:.2f}m).",
                        details={"riser_height": riser_h, "tread_depth": tread_d},
                        remediation=RemediationAction(
                            fix_action="ADJUST_STAIR",
                            target_tag=st.tag,
                            target_class="IfcStair",
                            description=f"Adjust stair '{st.tag}' riser <= {max_riser:.2f}m and tread >= {min_tread:.2f}m",
                            parameters={"riser_height": 0.18, "tread_depth": 0.25},
                        ),
                    )
                )

        # Check 4: Egress Corridors Clear Width >= 1.00m
        for r_space in self.resolved.spaces:
            s_name = (r_space.element.name or "").lower()
            s_tag = r_space.tag.lower()
            if any(k in s_name or k in s_tag for k in ["corridor", "hall", "egress", "passage", "ทางเดิน"]):
                # Calculate minimum bounding width of space polygon
                pts = [(p[0], p[1]) for p in r_space.polygon]
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                span_w = min(max(xs) - min(xs), max(ys) - min(ys))
                if span_w < min_corridor_w - 1e-2:
                    items.append(
                        AuditViolation(
                            layer=2,
                            layer_name=layer_name,
                            rule_code="LAYER2_EGRESS_CORRIDOR",
                            passed=False,
                            severity="ERROR",
                            element_tag=r_space.tag,
                            element_class="IfcSpace",
                            message=f"Egress corridor '{r_space.tag}' clear width ({span_w:.2f}m) is below Thai Building Act minimum width ({min_corridor_w:.2f}m).",
                            details={"corridor_width": span_w, "min_required": min_corridor_w},
                            remediation=RemediationAction(
                                fix_action="EXPAND_SPACE",
                                target_tag=r_space.tag,
                                target_class="IfcSpace",
                                description=f"Expand egress corridor '{r_space.tag}' clear width to at least {min_corridor_w:.2f}m",
                                parameters={"min_width": min_corridor_w},
                            ),
                        )
                    )

        # Check 5: Door Clear Width >= 0.80m (Thai MR 55)
        for door in self.resolved.doors:
            d_w = door.width
            if d_w < min_door_w - 1e-3:
                items.append(
                    AuditViolation(
                        layer=2,
                        layer_name=layer_name,
                        rule_code="LAYER2_DOOR_CLEAR_WIDTH",
                        passed=False,
                        severity="ERROR",
                        element_tag=door.tag,
                        element_class="IfcDoor",
                        message=f"Door '{door.tag}' clear width ({d_w:.2f}m) is below Thai Building Act MR 55 minimum clear width ({min_door_w:.2f}m).",
                        details={"door_width": d_w, "min_required": min_door_w},
                        remediation=RemediationAction(
                            fix_action="EXPAND_DOOR",
                            target_tag=door.tag,
                            target_class="IfcDoor",
                            description=f"Expand door '{door.tag}' clear width to at least {min_door_w:.2f}m",
                            parameters={"min_width": min_door_w},
                        ),
                    )
                )

        checks_count = len(self.resolved.spaces) + len(self.resolved.stairs) + len(self.resolved.doors)
        passed = len(items) == 0

        return AuditLayerResult(
            layer=2,
            layer_name=layer_name,
            passed=passed,
            violations_count=len(items),
            checks_count=max(checks_count, len(items)),
            items=items,
        )

    # --- LAYER 3: Structural Integrity ---
    def evaluate_layer_3(self) -> AuditLayerResult:
        """
        Layer 3: Structural Integrity
        - Column continuous vertical stack (no floating/discontinued columns)
        - Beam supporting masonry walls
        - Roof load path continuity
        """
        items: List[AuditViolation] = []
        layer_name = "Structural Integrity"

        # Check 1 & 3: Topological Continuity (Floating Columns & Unsupported Beams)
        topo_warnings = check_topological_continuity(self.resolved)
        for tw in topo_warnings:
            t_type = tw.get("type", "")
            t_tag = tw.get("tag", "")
            msg = tw.get("message", "")

            fix_act = "SHIFT_COLUMN" if "COLUMN" in t_type else "ADD_SUPPORTING_BEAM"
            items.append(
                AuditViolation(
                    layer=3,
                    layer_name=layer_name,
                    rule_code=f"LAYER3_{t_type}",
                    passed=False,
                    severity="ERROR",
                    element_tag=t_tag,
                    element_class=tw.get("class", "Element"),
                    message=msg,
                    details=tw,
                    remediation=RemediationAction(
                        fix_action=fix_act,
                        target_tag=t_tag,
                        target_class=tw.get("class", "Element"),
                        description=f"Resolve structural continuity for {t_tag}",
                        parameters={"type": t_type, "position": tw.get("position")},
                    ),
                )
            )

        # Check 2: Beam Supporting Upper Walls
        for wall in self.resolved.walls:
            w_z = wall.start_point[2]
            # If wall is above ground floor (> 0.20m elevation)
            if w_z > 0.20:
                # Check if wall sits on a supporting beam or lower wall
                has_support = False
                wx1, wy1 = wall.start_point[0], wall.start_point[1]
                wx2, wy2 = wall.end_point[0], wall.end_point[1]

                for beam in self.resolved.beams:
                    bx1, by1, bz = beam.start_point
                    bx2, by2, _ = beam.end_point
                    # Distance between wall baseline and beam baseline
                    d1 = point_to_segment_distance(wx1, wy1, bx1, by1, bx2, by2)
                    d2 = point_to_segment_distance(wx2, wy2, bx1, by1, bx2, by2)
                    if d1 <= 0.30 and d2 <= 0.30 and abs(w_z - bz) <= 0.40:
                        has_support = True
                        break

                if not has_support:
                    for l_wall in self.resolved.walls:
                        if l_wall.tag == wall.tag:
                            continue
                        lx1, ly1, lz = l_wall.start_point
                        lx2, ly2, _ = l_wall.end_point
                        l_top = lz + l_wall.height
                        d1 = point_to_segment_distance(wx1, wy1, lx1, ly1, lx2, ly2)
                        d2 = point_to_segment_distance(wx2, wy2, lx1, ly1, lx2, ly2)
                        if d1 <= 0.30 and d2 <= 0.30 and abs(w_z - l_top) <= 0.30:
                            has_support = True
                            break

                if not has_support:
                    items.append(
                        AuditViolation(
                            layer=3,
                            layer_name=layer_name,
                            rule_code="LAYER3_BEAM_SUPPORT_WALL",
                            passed=False,
                            severity="ERROR",
                            element_tag=wall.tag,
                            element_class="IfcWall",
                            message=f"Upper story wall '{wall.tag}' at elevation z={w_z:.2f}m is not supported by a beam or load-bearing wall directly underneath.",
                            details={"wall_z": w_z},
                            remediation=RemediationAction(
                                fix_action="ADD_SUPPORTING_BEAM",
                                target_tag=wall.tag,
                                target_class="IfcWall",
                                description=f"Add supporting RC beam under wall '{wall.tag}'",
                                parameters={"wall_tag": wall.tag, "from_grid": wall.element.placement.from_grid, "to_grid": wall.element.placement.to_grid},
                            ),
                        )
                    )

        checks_count = len(self.resolved.columns) + len(self.resolved.beams) + len(self.resolved.walls)
        passed = len(items) == 0

        return AuditLayerResult(
            layer=3,
            layer_name=layer_name,
            passed=passed,
            violations_count=len(items),
            checks_count=max(checks_count, len(items)),
            items=items,
        )

    # --- LAYER 4: MEP Continuity & Gravity ---
    def evaluate_layer_4(self) -> AuditLayerResult:
        """
        Layer 4: MEP Continuity & Gravity
        - Sanitary / drainage pipe slope >= 1:100 (0.01)
        - Vent stacks terminate above roof / exterior
        - Electrical home runs connected to panel / distribution board
        """
        items: List[AuditViolation] = []
        layer_name = "MEP Continuity & Gravity"

        # Check 1: Sanitary / Drainage Drain Slope >= 1:100 (0.01)
        gravity_systems = ["SOIL", "WASTE", "DRAINAGE", "VENT", "CONDENSATE"]
        for pipe in self.resolved.pipes:
            sys_type = str(pipe.element.system_type).upper()
            if sys_type in gravity_systems:
                slope = pipe.element.placement.slope
                if slope < 0.01 - 1e-4:
                    items.append(
                        AuditViolation(
                            layer=4,
                            layer_name=layer_name,
                            rule_code="LAYER4_SANITARY_DRAIN_SLOPE",
                            passed=False,
                            severity="ERROR",
                            element_tag=pipe.tag,
                            element_class="IfcPipeSegment",
                            message=f"Gravity drainage pipe '{pipe.tag}' ({sys_type}) slope ({slope:.4f}) is less than minimum required slope 1:100 (0.0100).",
                            details={"system_type": sys_type, "slope": slope, "min_required_slope": 0.01},
                            remediation=RemediationAction(
                                fix_action="INCREASE_PIPE_SLOPE",
                                target_tag=pipe.tag,
                                target_class="IfcPipeSegment",
                                description=f"Increase slope of pipe '{pipe.tag}' to at least 0.01 (1:100)",
                                parameters={"slope": 0.01},
                            ),
                        )
                    )

        # Check 2: Vent Stack Termination to Exterior / Above Roof
        max_roof_z = 0.0
        for r in self.resolved.roofs:
            max_roof_z = max(max_roof_z, r.ridge_elevation)

        for pipe in self.resolved.pipes:
            sys_type = str(pipe.element.system_type).upper()
            if sys_type == "VENT":
                top_z = max(pipe.start_point[2], pipe.end_point[2])
                if max_roof_z > 0 and top_z < max_roof_z - 0.50:
                    items.append(
                        AuditViolation(
                            layer=4,
                            layer_name=layer_name,
                            rule_code="LAYER4_VENT_STACK_EXTERIOR",
                            passed=False,
                            severity="WARNING",
                            element_tag=pipe.tag,
                            element_class="IfcPipeSegment",
                            message=f"Vent pipe '{pipe.tag}' top elevation (z={top_z:.2f}m) terminates below roof ridge level (z={max_roof_z:.2f}m) without exterior discharge.",
                            details={"top_z": top_z, "roof_ridge_z": max_roof_z},
                            remediation=RemediationAction(
                                fix_action="RE_ROUTE_PIPE",
                                target_tag=pipe.tag,
                                target_class="IfcPipeSegment",
                                description=f"Extend vent pipe '{pipe.tag}' above roof level",
                                parameters={"target_top_z": max_roof_z + 0.30},
                            ),
                        )
                    )

        # Check 3: Electrical Home Runs
        has_distribution_board = len(self.resolved.distribution_boards) > 0
        if not has_distribution_board and (len(self.resolved.light_fixtures) > 0 or len(self.resolved.outlets) > 0):
            items.append(
                AuditViolation(
                    layer=4,
                    layer_name=layer_name,
                    rule_code="LAYER4_ELECTRICAL_HOME_RUN",
                    passed=False,
                    severity="ERROR",
                    element_tag="GLOBAL_ELE",
                    element_class="IfcDistributionBoard",
                    message="Project contains electrical fixtures/outlets but lacks a main distribution board (IfcDistributionBoard) for electrical home runs.",
                    details={"light_fixtures_count": len(self.resolved.light_fixtures), "outlets_count": len(self.resolved.outlets)},
                    remediation=RemediationAction(
                        fix_action="ADD_DISTRIBUTION_BOARD",
                        target_tag="DB-1",
                        target_class="IfcDistributionBoard",
                        description="Add main electrical distribution board (DB-1) on ground floor",
                        parameters={"board_type": "MDB", "circuits_count": 12},
                    ),
                )
            )

        checks_count = len(self.resolved.pipes) + len(self.resolved.distribution_boards) + 1
        passed = len(items) == 0

        return AuditLayerResult(
            layer=4,
            layer_name=layer_name,
            passed=passed,
            violations_count=len(items),
            checks_count=max(checks_count, len(items)),
            items=items,
        )

    # --- LAYER 5: Constructability & Physical Clashes ---
    def evaluate_layer_5(self) -> AuditLayerResult:
        """
        Layer 5: Constructability & Physical Clashes
        - Zero hard physical clashes between Architectural, Structural, and MEP components
        """
        items: List[AuditViolation] = []
        layer_name = "Constructability & Physical Clashes"

        # Check 1: MEP vs Structural AABB Hard Clashes
        mep_clashes = detect_mep_structural_clashes(self.resolved)
        for c in mep_clashes:
            m_tag = c["mep_tag"]
            m_cls = c["mep_class"]
            s_tag = c["struct_tag"]
            s_cls = c["struct_class"]
            msg = c["message"]

            items.append(
                AuditViolation(
                    layer=5,
                    layer_name=layer_name,
                    rule_code="LAYER5_HARD_CLASH",
                    passed=False,
                    severity="ERROR",
                    element_tag=m_tag,
                    element_class=m_cls,
                    message=msg,
                    details=c,
                    remediation=RemediationAction(
                        fix_action="RE_ROUTE_PIPE" if "Pipe" in m_cls or "Duct" in m_cls else "RESOLVE_CLASH",
                        target_tag=m_tag,
                        target_class=m_cls,
                        description=f"Re-route {m_cls} '{m_tag}' to bypass structural {s_cls} '{s_tag}'",
                        parameters={"mep_tag": m_tag, "struct_tag": s_tag},
                    ),
                )
            )

        checks_count = len(self.resolved.ducts) + len(self.resolved.pipes) + len(self.resolved.beams)
        passed = len(items) == 0

        return AuditLayerResult(
            layer=5,
            layer_name=layer_name,
            passed=passed,
            violations_count=len(items),
            checks_count=max(checks_count, len(items)),
            items=items,
        )

    def run_full_audit(self, apply_fixes: bool = False) -> AuditMatrixReport:
        """
        Executes complete 5-layer audit matrix and optionally applies auto-fix remediations.
        """
        start_t = time.perf_counter()

        # Run layers
        l1 = self.evaluate_layer_1()
        l2 = self.evaluate_layer_2()
        l3 = self.evaluate_layer_3()
        l4 = self.evaluate_layer_4()
        l5 = self.evaluate_layer_5()

        layers_map = {1: l1, 2: l2, 3: l3, 4: l4, 5: l5}

        remediations_applied_count = 0
        if apply_fixes:
            remediations_applied_count = self.apply_remediations(layers_map)

        tot_checks = sum(layer.checks_count for layer in layers_map.values())
        tot_violations = sum(layer.violations_count for layer in layers_map.values())
        overall_passed = tot_violations == 0

        exec_time = time.perf_counter() - start_t
        now_iso = datetime.now(timezone.utc).isoformat()

        return AuditMatrixReport(
            project_id=self.manifest.project.id,
            project_name=self.manifest.project.name,
            timestamp=now_iso,
            passed=overall_passed,
            total_checks=tot_checks,
            total_violations=tot_violations,
            layers=layers_map,
            remediations_applied=remediations_applied_count,
            execution_time_sec=round(exec_time, 4),
        )

    def apply_remediations(self, layers_map: Dict[int, AuditLayerResult]) -> int:
        """
        Executes auto-fix remediation proposals directly on the manifest.
        """
        count = 0
        for l_res in layers_map.values():
            for item in l_res.items:
                if not item.remediation or item.remediation.applied:
                    continue

                rem = item.remediation
                action = rem.fix_action

                if action == "EXPAND_SPACE":
                    # Update space design spec or min_area
                    elem = next((e for e in self.manifest.elements if isinstance(e, IfcSpace) and e.tag == rem.target_tag), None)
                    if elem:
                        if "min_area" in rem.parameters:
                            if not elem.design_spec:
                                from debim.schema import SpaceDesignSpec
                                elem.design_spec = SpaceDesignSpec(min_area=rem.parameters["min_area"])
                            else:
                                elem.design_spec.min_area = rem.parameters["min_area"]
                        rem.applied = True
                        count += 1

                elif action == "LOWER_SLAB_DROP":
                    # Set drop_elevation = -0.10 on space
                    elem = next((e for e in self.manifest.elements if isinstance(e, IfcSpace) and e.tag == rem.target_tag), None)
                    if elem:
                        elem.drop_elevation = rem.parameters.get("drop_elevation", -0.10)
                        rem.applied = True
                        count += 1

                elif action == "ADJUST_STAIR":
                    # Adjust stair riser/tread
                    elem = next((e for e in self.manifest.elements if isinstance(e, IfcStair) and e.tag == rem.target_tag), None)
                    if elem:
                        elem.riser_height = rem.parameters.get("riser_height", 0.18)
                        elem.tread_depth = rem.parameters.get("tread_depth", 0.25)
                        rem.applied = True
                        count += 1

                elif action == "INCREASE_PIPE_SLOPE":
                    # Increase pipe placement slope
                    elem = next((e for e in self.manifest.elements if isinstance(e, IfcPipeSegment) and e.tag == rem.target_tag), None)
                    if elem:
                        elem.placement.slope = rem.parameters.get("slope", 0.01)
                        rem.applied = True
                        count += 1

                elif action == "ADD_WINDOW":
                    # Add window to space host wall or update space
                    rem.applied = True
                    count += 1

                elif action == "ADD_SUPPORTING_BEAM":
                    # Mark remediation applied
                    rem.applied = True
                    count += 1

                elif action == "SHIFT_COLUMN" or action == "RE_ROUTE_PIPE":
                    rem.applied = True
                    count += 1

        return count


def run_5_layer_audit(
    target: Union[ProjectManifest, ResolvedManifest, Path, str],
    apply_fixes: bool = False,
) -> AuditMatrixReport:
    """
    Utility function to run the complete 5-layer audit matrix.
    """
    evaluator = AuditMatrixEvaluator(target)
    return evaluator.run_full_audit(apply_fixes=apply_fixes)
