"""
Architectural Door & Window Schedule & Hardware Specification Engine (แบบขยายประตู-หน้าต่าง) for debim.
Generates 2D vector elevation views, opening dimensions, hardware specifications,
and automated quantity take-offs fitted onto standard A3 drawing sheets (A-401).
"""

from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field

from debim.resolver import (
    ResolvedDoor,
    ResolvedManifest,
    ResolvedWindow,
    SpatialResolver,
)
from debim.schema import IfcDoor, IfcWall, IfcWindow, ProjectManifest


class HardwareSpec(BaseModel):
    """Hardware accessories specification for doors and windows."""
    hinges: Optional[str] = None
    lockset: Optional[str] = None
    handle: Optional[str] = None
    closer: Optional[str] = None
    flush_bolts: Optional[str] = None
    sliding_track: Optional[str] = None
    accessories: List[str] = Field(default_factory=list)


class OpeningScheduleItem(BaseModel):
    """Processed opening schedule entry (Door or Window type)."""
    type_tag: str  # e.g. D1, D2, D3, W1, W2, W3
    category: Literal["DOOR", "WINDOW"]
    width: float  # clear opening width (m)
    height: float  # clear opening height (m)
    sill_height: float  # sill height (m)
    quantity: int  # automated count from manifest
    instances: List[str] = Field(default_factory=list)  # list of element tags e.g. ["D-L1-01", "D-L1-02"]
    frame_material: str  # e.g. "Powder-Coated Aluminum (Dark Grey)" or "Hardwood (Teak)"
    panel_glazing: str  # e.g. "6mm Green Tinted Float Glass" or "Solid Core Teak Wood Panel"
    operation_type: str  # e.g. "SWING_SINGLE", "SLIDING_DOUBLE", "AWNING", "FIXED"
    hardware: HardwareSpec = Field(default_factory=HardwareSpec)
    remarks: Optional[str] = None


def _infer_frame_material(elem: Union[IfcDoor, IfcWindow, ResolvedDoor, ResolvedWindow]) -> str:
    mat = getattr(elem, "material", None)
    if not mat and hasattr(elem, "element") and getattr(elem.element, "material", None):
        mat = elem.element.material

    if mat:
        mat_upper = str(mat).upper()
        if "ALUMINUM" in mat_upper or "ALU" in mat_upper:
            return "Powder-Coated Aluminum Frame 1.8mm (Dark Grey)"
        if "TIMBER" in mat_upper or "WOOD" in mat_upper or "TEAK" in mat_upper:
            return "Hardwood Frame (Teak Wood 2\" x 4\")"
        if "UPVC" in mat_upper or "PVC" in mat_upper:
            return "High-Grade White uPVC Frame"
        if "STEEL" in mat_upper or "METAL" in mat_upper:
            return "Galvanized Steel Frame 1.6mm (Epoxy Painted)"
        return f"{mat} Frame"

    # Default fallback based on type
    is_door = isinstance(elem, (IfcDoor, ResolvedDoor)) or getattr(elem, "class_", "") == "IfcDoor"
    if is_door:
        return "Hardwood Frame (Teak Wood 2\" x 4\")"
    return "Powder-Coated Aluminum Frame 1.8mm (Dark Grey)"


def _infer_panel_glazing(elem: Union[IfcDoor, IfcWindow, ResolvedDoor, ResolvedWindow]) -> str:
    is_door = isinstance(elem, (IfcDoor, ResolvedDoor)) or getattr(elem, "class_", "") == "IfcDoor"
    op_type = (getattr(elem, "operation_type", None) or "").upper()
    tag = (getattr(elem, "tag", None) or "").upper()

    if is_door:
        if "GLASS" in op_type or "SLIDING" in op_type or "BALCONY" in tag:
            return "6mm Green Tinted Tempered Safety Glass in Aluminum Sash"
        if "BATH" in tag or "WC" in tag or "TOILET" in tag:
            return "PVC Waterproof Flush Panel with Louver"
        return "Solid Core Wood Panel (Teak Veneer / Painted)"
    else:
        if "FIXED" in op_type:
            return "6mm Clear Float Glass"
        return "6mm Green Tinted Float Glass in Aluminum Sash"


def _infer_hardware(
    elem: Union[IfcDoor, IfcWindow, ResolvedDoor, ResolvedWindow],
    category: Literal["DOOR", "WINDOW"],
    w: float,
    h: float,
) -> HardwareSpec:
    op_type = (getattr(elem, "operation_type", None) or "").upper()
    tag = (getattr(elem, "tag", None) or "").upper()

    if category == "DOOR":
        if "SLIDING" in op_type or "SLIDING" in tag or w >= 1.5:
            return HardwareSpec(
                sliding_track="Heavy Duty Overhead Sliding Track & Roller Assembly",
                lockset="Mortise Sliding Door Lockset with Cylinder",
                handle="Stainless Steel Flush Pull Handle 150mm",
                accessories=["Rubber Bumper", "Floor Guide Roller"],
            )
        elif "WC" in tag or "BATH" in tag or "TOILET" in tag or w <= 0.85:
            return HardwareSpec(
                hinges="Stainless Steel Hinges 4\" x 3\" x 2.0mm (3 Pcs)",
                lockset="Tubular Knob Lockset (Privacy / Bathroom)",
                accessories=["Door Stopper Rubber Head"],
            )
        else:
            has_closer = w >= 1.0 or "MAIN" in tag or "EXIT" in tag
            return HardwareSpec(
                hinges="Stainless Steel Ball Bearing Hinges 4\" x 3\" x 2.5mm (4 Pcs)",
                lockset="Lever Handle Lockset (Entrance / Office)",
                closer="Overhead Hydraulic Door Closer (EN3)" if has_closer else None,
                flush_bolts="Stainless Steel Flush Bolts 8\" / 12\" (Top/Bottom)" if w >= 1.2 else None,
                accessories=["Magnetic Door Holder / Stopper"],
            )
    else:  # WINDOW
        if "SLIDING" in op_type or w >= 1.2:
            return HardwareSpec(
                sliding_track="Heavy Duty Stainless Steel Window Track & Bearing Rollers",
                lockset="Crescent Lockset / Flush Latch Lock",
                handle="Integrated Frame Pull Handle",
                accessories=["Anti-Lift Block", "Insect Screen Mesh"],
            )
        elif "AWNING" in op_type or "HOPPER" in op_type or h <= 0.8:
            return HardwareSpec(
                hinges="Friction Stay Arms / Heavy Duty Awning Hinges (1 Pair)",
                lockset="Multi-Point Awning Handle Latch",
                accessories=["Insect Screen Mesh"],
            )
        else:
            return HardwareSpec(
                hinges="Friction Stay Hinges 12\" Stainless Steel (1 Pair)",
                lockset="Casement Window Handle Lock",
                accessories=["Insect Screen Mesh"],
            )


def extract_opening_schedule(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
) -> Tuple[List[OpeningScheduleItem], List[OpeningScheduleItem]]:
    """
    Extract, aggregate, and classify all doors and windows from project manifest or resolved model.
    Returns (door_schedules, window_schedules) with clean type tags (D1, D2..., W1, W2...).
    """
    if isinstance(manifest_or_resolved, ProjectManifest):
        resolved = SpatialResolver(manifest_or_resolved).resolve()
    else:
        resolved = manifest_or_resolved

    doors: List[Union[IfcDoor, ResolvedDoor]] = []
    windows: List[Union[IfcWindow, ResolvedWindow]] = []

    if getattr(resolved, "doors", None):
        doors.extend(resolved.doors)
    if getattr(resolved, "windows", None):
        windows.extend(resolved.windows)

    # Fallback to scanning walls and manifest elements if resolved lists are empty
    if not doors and not windows:
        for wall in resolved.walls:
            for child in wall.children:
                if isinstance(child, ResolvedDoor) or getattr(child, "element_class", "") == "IfcDoor":
                    doors.append(child)
                elif isinstance(child, ResolvedWindow) or getattr(child, "element_class", "") == "IfcWindow":
                    windows.append(child)

        for elem in resolved.manifest.elements:
            if isinstance(elem, IfcWall):
                for child in elem.children:
                    if isinstance(child, IfcDoor):
                        doors.append(child)
                    elif isinstance(child, IfcWindow):
                        windows.append(child)

    # Process Doors
    door_groups: Dict[Tuple[float, float, float, str, str], List[Union[IfcDoor, ResolvedDoor]]] = {}
    for d in doors:
        elem_obj = getattr(d, "element", d)
        w = round(float(getattr(elem_obj.dimensions, "width", getattr(d, "width", 0.9))), 2)
        h = round(float(getattr(elem_obj.dimensions, "height", getattr(d, "height", 2.0))), 2)
        sill = round(float(getattr(elem_obj, "sill_height", getattr(d, "sill_height", 0.0))), 2)
        op = (getattr(elem_obj, "operation_type", None) or "SWING").upper()
        mat = getattr(elem_obj, "material", None) or "WOOD"

        key = (w, h, sill, op, mat)
        door_groups.setdefault(key, []).append(d)

    door_schedules: List[OpeningScheduleItem] = []
    for idx, (key, instances) in enumerate(sorted(door_groups.items(), key=lambda k: (-k[0][0], -k[0][1])), start=1):
        w, h, sill, op, mat = key
        sample = instances[0]
        sample_elem = getattr(sample, "element", sample)
        tags = sorted([getattr(inst, "tag", f"D-{i}") for i, inst in enumerate(instances, 1)])

        frame_mat = _infer_frame_material(sample_elem)
        glazing_spec = _infer_panel_glazing(sample_elem)
        hw_spec = _infer_hardware(sample_elem, "DOOR", w, h)

        door_schedules.append(OpeningScheduleItem(
            type_tag=f"D{idx}",
            category="DOOR",
            width=w,
            height=h,
            sill_height=sill,
            quantity=len(instances),
            instances=tags,
            frame_material=frame_mat,
            panel_glazing=glazing_spec,
            operation_type=op if op != "SWING" else "Single Swing",
            hardware=hw_spec,
            remarks="Standard Interior / Exterior Door",
        ))

    # Process Windows
    window_groups: Dict[Tuple[float, float, float, str, str], List[Union[IfcWindow, ResolvedWindow]]] = {}
    for win in windows:
        elem_obj = getattr(win, "element", win)
        w = round(float(getattr(elem_obj.dimensions, "width", getattr(win, "width", 1.2))), 2)
        h = round(float(getattr(elem_obj.dimensions, "height", getattr(win, "height", 1.2))), 2)
        sill = round(float(getattr(elem_obj, "sill_height", getattr(win, "sill_height", 0.9))), 2)
        op = (getattr(elem_obj, "operation_type", None) or "SLIDING").upper()
        mat = getattr(elem_obj, "material", None) or "ALUMINUM"

        key = (w, h, sill, op, mat)
        window_groups.setdefault(key, []).append(win)

    window_schedules: List[OpeningScheduleItem] = []
    for idx, (key, instances) in enumerate(sorted(window_groups.items(), key=lambda k: (-k[0][0], -k[0][1])), start=1):
        w, h, sill, op, mat = key
        sample = instances[0]
        sample_elem = getattr(sample, "element", sample)
        tags = sorted([getattr(inst, "tag", f"W-{i}") for i, inst in enumerate(instances, 1)])

        frame_mat = _infer_frame_material(sample_elem)
        glazing_spec = _infer_panel_glazing(sample_elem)
        hw_spec = _infer_hardware(sample_elem, "WINDOW", w, h)

        window_schedules.append(OpeningScheduleItem(
            type_tag=f"W{idx}",
            category="WINDOW",
            width=w,
            height=h,
            sill_height=sill,
            quantity=len(instances),
            instances=tags,
            frame_material=frame_mat,
            panel_glazing=glazing_spec,
            operation_type=op if op != "SLIDING" else "Sliding Window",
            hardware=hw_spec,
            remarks="Standard Exterior Window",
        ))

    return door_schedules, window_schedules


def render_2d_opening_elevation_svg(
    item: OpeningScheduleItem,
    box_width_mm: float = 75.0,
    box_height_mm: float = 70.0,
) -> str:
    """
    Render 2D vector elevation view for a single door or window type (D1, W1, etc.)
    showing frame, panel, glass panes, swing direction dashed lines, handles, and dimensions.
    """
    w_m = item.width
    h_m = item.height
    is_door = item.category == "DOOR"

    # Margin inside drawing box
    pad_left_mm = 12.0
    pad_top_mm = 10.0
    pad_right_mm = 12.0
    pad_bot_mm = 18.0

    avail_w = box_width_mm - pad_left_mm - pad_right_mm
    avail_h = box_height_mm - pad_top_mm - pad_bot_mm

    # Scale to fit box
    scale_x = avail_w / max(w_m, 0.5)
    scale_y = avail_h / max(h_m, 0.5)
    scale = min(scale_x, scale_y) * 0.90

    drawing_w_mm = w_m * scale
    drawing_h_mm = h_m * scale

    x0 = pad_left_mm + (avail_w - drawing_w_mm) / 2.0
    y0 = pad_top_mm + (avail_h - drawing_h_mm) / 2.0

    svg_parts = [
        f'<g id="elevation-{item.type_tag}" class="schedule-elevation">',
        '  <!-- Background Box & Type Label -->',
        f'  <rect x="0" y="0" width="{box_width_mm:.1f}" height="{box_height_mm:.1f}" fill="none" stroke="#cbd5e1" stroke-width="0.3" rx="1.0" />',
        f'  <circle cx="{box_width_mm / 2.0:.1f}" cy="6.0" r="4.5" fill="#f8fafc" stroke="#0f172a" stroke-width="0.8" />',
        f'  <text x="{box_width_mm / 2.0:.1f}" y="7.2" class="opening-type-tag" font-family="Sarabun, sans-serif" font-size="3.8px" font-weight="bold" text-anchor="middle" fill="#0f172a">{item.type_tag}</text>',
    ]

    frame_thk_mm = max(1.2, 0.05 * scale)

    # 1. Outer Frame Box
    svg_parts.append(
        f'  <rect x="{x0:.2f}" y="{y0:.2f}" width="{drawing_w_mm:.2f}" height="{drawing_h_mm:.2f}" class="opening-frame" fill="#f1f5f9" stroke="#0f172a" stroke-width="0.8" />'
    )

    # 2. Inner Panel / Glass Box
    px0 = x0 + frame_thk_mm
    py0 = y0 + frame_thk_mm
    pw = max(1.0, drawing_w_mm - 2 * frame_thk_mm)
    ph = max(1.0, drawing_h_mm - (frame_thk_mm if is_door else 2 * frame_thk_mm))

    panel_fill = "#e0f2fe" if ("GLAZING" in item.panel_glazing.upper() or "GLASS" in item.panel_glazing.upper()) else "#fdf6e3"
    svg_parts.append(
        f'  <rect x="{px0:.2f}" y="{py0:.2f}" width="{pw:.2f}" height="{ph:.2f}" class="opening-panel" fill="{panel_fill}" stroke="#334155" stroke-width="0.5" />'
    )

    # 3. Sub-Mullions / Glass Panes & Swing Lines
    op_upper = item.operation_type.upper()

    if is_door:
        if w_m >= 1.5 or "DOUBLE" in op_upper or "SLIDING" in op_upper:
            # Double Leaf / Double Sliding Door
            mid_x = x0 + drawing_w_mm / 2.0
            svg_parts.append(
                f'  <line x1="{mid_x:.2f}" y1="{py0:.2f}" x2="{mid_x:.2f}" y2="{py0 + ph:.2f}" stroke="#0f172a" stroke-width="0.6" />'
            )
            if "SLIDING" in op_upper:
                # Sliding Arrows / Chevrons
                arr_y = py0 + ph / 2.0
                svg_parts.append(f'  <line x1="{px0 + pw*0.25:.2f}" y1="{arr_y:.2f}" x2="{px0 + pw*0.4:.2f}" y2="{arr_y:.2f}" stroke="#2563eb" stroke-width="0.6" stroke-dasharray="1 1" />')
                svg_parts.append(f'  <polygon points="{px0 + pw*0.4:.2f},{arr_y - 1.2:.2f} {px0 + pw*0.45:.2f},{arr_y:.2f} {px0 + pw*0.4:.2f},{arr_y + 1.2:.2f}" fill="#2563eb" />')
                svg_parts.append(f'  <line x1="{px0 + pw*0.75:.2f}" y1="{arr_y:.2f}" x2="{px0 + pw*0.6:.2f}" y2="{arr_y:.2f}" stroke="#2563eb" stroke-width="0.6" stroke-dasharray="1 1" />')
                svg_parts.append(f'  <polygon points="{px0 + pw*0.6:.2f},{arr_y - 1.2:.2f} {px0 + pw*0.55:.2f},{arr_y:.2f} {px0 + pw*0.6:.2f},{arr_y + 1.2:.2f}" fill="#2563eb" />')
            else:
                # Double Swing V-Dashed Lines
                svg_parts.append(f'  <line x1="{px0:.2f}" y1="{py0:.2f}" x2="{mid_x:.2f}" y2="{py0 + ph/2.0:.2f}" stroke="#64748b" stroke-width="0.4" stroke-dasharray="1.5 1.5" />')
                svg_parts.append(f'  <line x1="{px0:.2f}" y1="{py0 + ph:.2f}" x2="{mid_x:.2f}" y2="{py0 + ph/2.0:.2f}" stroke="#64748b" stroke-width="0.4" stroke-dasharray="1.5 1.5" />')
                svg_parts.append(f'  <line x1="{px0 + pw:.2f}" y1="{py0:.2f}" x2="{mid_x:.2f}" y2="{py0 + ph/2.0:.2f}" stroke="#64748b" stroke-width="0.4" stroke-dasharray="1.5 1.5" />')
                svg_parts.append(f'  <line x1="{px0 + pw:.2f}" y1="{py0 + ph:.2f}" x2="{mid_x:.2f}" y2="{py0 + ph/2.0:.2f}" stroke="#64748b" stroke-width="0.4" stroke-dasharray="1.5 1.5" />')

                # Handles
                h_y = py0 + ph * 0.55
                svg_parts.append(f'  <circle cx="{mid_x - 1.5:.2f}" cy="{h_y:.2f}" r="0.8" fill="#0f172a" />')
                svg_parts.append(f'  <circle cx="{mid_x + 1.5:.2f}" cy="{h_y:.2f}" r="0.8" fill="#0f172a" />')
        else:
            # Single Swing Door
            # Swing V-Dashed Line from hinges to handle midpoint
            h_x = px0 + pw * 0.85
            h_y = py0 + ph * 0.55
            svg_parts.append(f'  <line x1="{px0:.2f}" y1="{py0:.2f}" x2="{h_x:.2f}" y2="{h_y:.2f}" stroke="#64748b" stroke-width="0.4" stroke-dasharray="1.5 1.5" />')
            svg_parts.append(f'  <line x1="{px0:.2f}" y1="{py0 + ph:.2f}" x2="{h_x:.2f}" y2="{h_y:.2f}" stroke="#64748b" stroke-width="0.4" stroke-dasharray="1.5 1.5" />')

            # Lever Handle / Knob
            svg_parts.append(f'  <circle cx="{h_x:.2f}" cy="{h_y:.2f}" r="0.9" fill="#0f172a" />')
            svg_parts.append(f'  <line x1="{h_x:.2f}" y1="{h_y:.2f}" x2="{h_x + 2.0:.2f}" y2="{h_y:.2f}" stroke="#0f172a" stroke-width="0.6" />')

            # Panels or Glass Vision Lites if specified
            if "GLASS" in item.panel_glazing.upper():
                gl_y1 = py0 + ph * 0.15
                gl_h = ph * 0.70
                svg_parts.append(
                    f'  <rect x="{px0 + 3.0:.2f}" y="{gl_y1:.2f}" width="{pw - 6.0:.2f}" height="{gl_h:.2f}" fill="#38bdf8" fill-opacity="0.3" stroke="#0284c7" stroke-width="0.4" />'
                )

    else:  # WINDOW
        if "SLIDING" in op_upper or w_m >= 1.2:
            # 2-Panel Sliding Window
            mid_x = x0 + drawing_w_mm / 2.0
            svg_parts.append(f'  <line x1="{mid_x:.2f}" y1="{py0:.2f}" x2="{mid_x:.2f}" y2="{py0 + ph:.2f}" stroke="#0f172a" stroke-width="0.6" />')

            # Glass sheen lines
            svg_parts.append(f'  <line x1="{px0 + pw*0.15:.2f}" y1="{py0 + ph*0.2:.2f}" x2="{px0 + pw*0.35:.2f}" y2="{py0 + ph*0.6:.2f}" stroke="#ffffff" stroke-width="0.5" opacity="0.7" />')
            svg_parts.append(f'  <line x1="{px0 + pw*0.65:.2f}" y1="{py0 + ph*0.2:.2f}" x2="{px0 + pw*0.85:.2f}" y2="{py0 + ph*0.6:.2f}" stroke="#ffffff" stroke-width="0.5" opacity="0.7" />')

            # Sliding Arrows
            arr_y = py0 + ph / 2.0
            svg_parts.append(f'  <line x1="{px0 + pw*0.1:.2f}" y1="{arr_y:.2f}" x2="{px0 + pw*0.35:.2f}" y2="{arr_y:.2f}" stroke="#2563eb" stroke-width="0.5" stroke-dasharray="1 1" />')
            svg_parts.append(f'  <polygon points="{px0 + pw*0.35:.2f},{arr_y - 1.0:.2f} {px0 + pw*0.4:.2f},{arr_y:.2f} {px0 + pw*0.35:.2f},{arr_y + 1.0:.2f}" fill="#2563eb" />')
            svg_parts.append(f'  <line x1="{px0 + pw*0.9:.2f}" y1="{arr_y:.2f}" x2="{px0 + pw*0.65:.2f}" y2="{arr_y:.2f}" stroke="#2563eb" stroke-width="0.5" stroke-dasharray="1 1" />')
            svg_parts.append(f'  <polygon points="{px0 + pw*0.65:.2f},{arr_y - 1.0:.2f} {px0 + pw*0.6:.2f},{arr_y:.2f} {px0 + pw*0.65:.2f},{arr_y + 1.0:.2f}" fill="#2563eb" />')

        elif "AWNING" in op_upper or "HOPPER" in op_upper:
            # Awning Window Triangle Dashed Line
            top_mid = px0 + pw / 2.0
            bot_y = py0 + ph
            svg_parts.append(f'  <line x1="{top_mid:.2f}" y1="{py0:.2f}" x2="{px0:.2f}" y2="{bot_y:.2f}" stroke="#64748b" stroke-width="0.4" stroke-dasharray="1.5 1.5" />')
            svg_parts.append(f'  <line x1="{top_mid:.2f}" y1="{py0:.2f}" x2="{px0 + pw:.2f}" y2="{bot_y:.2f}" stroke="#64748b" stroke-width="0.4" stroke-dasharray="1.5 1.5" />')
            # Handle at bottom
            svg_parts.append(f'  <rect x="{top_mid - 1.5:.2f}" y="{bot_y - 1.5:.2f}" width="3.0" height="1.0" fill="#0f172a" />')

        elif "FIXED" in op_upper:
            # Fixed Window diagonal cross line or clear glass
            svg_parts.append(f'  <line x1="{px0 + pw*0.2:.2f}" y1="{py0 + ph*0.2:.2f}" x2="{px0 + pw*0.8:.2f}" y2="{py0 + ph*0.8:.2f}" stroke="#ffffff" stroke-width="0.6" opacity="0.8" />')

        else:  # Casement
            mid_y = py0 + ph / 2.0
            right_mid = px0 + pw
            svg_parts.append(f'  <line x1="{px0:.2f}" y1="{py0:.2f}" x2="{right_mid:.2f}" y2="{mid_y:.2f}" stroke="#64748b" stroke-width="0.4" stroke-dasharray="1.5 1.5" />')
            svg_parts.append(f'  <line x1="{px0:.2f}" y1="{py0 + ph:.2f}" x2="{right_mid:.2f}" y2="{mid_y:.2f}" stroke="#64748b" stroke-width="0.4" stroke-dasharray="1.5 1.5" />')

    # 4. Dimension Annotations
    # Width dimension line below
    dim_y = y0 + drawing_h_mm + 5.0
    svg_parts.append(f'  <line x1="{x0:.2f}" y1="{dim_y:.2f}" x2="{x0 + drawing_w_mm:.2f}" y2="{dim_y:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <line x1="{x0:.2f}" y1="{dim_y - 1.2:.2f}" x2="{x0:.2f}" y2="{dim_y + 1.2:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <line x1="{x0 + drawing_w_mm:.2f}" y1="{dim_y - 1.2:.2f}" x2="{x0 + drawing_w_mm:.2f}" y2="{dim_y + 1.2:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <text x="{x0 + drawing_w_mm/2.0:.2f}" y="{dim_y + 3.2:.2f}" font-family="Sarabun, sans-serif" font-size="2.6px" text-anchor="middle" fill="#0f172a">{w_m:.2f}</text>')

    # Height dimension line on left
    dim_x = x0 - 5.0
    svg_parts.append(f'  <line x1="{dim_x:.2f}" y1="{y0:.2f}" x2="{dim_x:.2f}" y2="{y0 + drawing_h_mm:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <line x1="{dim_x - 1.2:.2f}" y1="{y0:.2f}" x2="{dim_x + 1.2:.2f}" y2="{y0:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <line x1="{dim_x - 1.2:.2f}" y1="{y0 + drawing_h_mm:.2f}" x2="{dim_x + 1.2:.2f}" y2="{y0 + drawing_h_mm:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <text x="{dim_x - 1.5:.2f}" y="{y0 + drawing_h_mm/2.0:.2f}" font-family="Sarabun, sans-serif" font-size="2.6px" text-anchor="middle" transform="rotate(-90 {dim_x - 1.5:.2f} {y0 + drawing_h_mm/2.0:.2f})" fill="#0f172a">{h_m:.2f}</text>')

    svg_parts.append('</g>')
    return "\n".join(svg_parts)


def render_schedule_card_svg(
    item: OpeningScheduleItem,
    card_width_mm: float = 180.0,
    card_height_mm: float = 85.0,
) -> str:
    """
    Render complete Opening Schedule Card containing 2D vector elevation,
    dimension callouts, hardware specification table, and location tags.
    """
    elev_svg = render_2d_opening_elevation_svg(item, box_width_mm=70.0, box_height_mm=75.0)

    tbl_x = 74.0
    tbl_w = card_width_mm - tbl_x - 2.0

    inst_str = ", ".join(item.instances[:12]) + ("..." if len(item.instances) > 12 else "")

    hw_list = []
    if item.hardware.hinges:
        hw_list.append(f"Hinges: {item.hardware.hinges}")
    if item.hardware.lockset:
        hw_list.append(f"Lockset: {item.hardware.lockset}")
    if item.hardware.handle:
        hw_list.append(f"Handle: {item.hardware.handle}")
    if item.hardware.closer:
        hw_list.append(f"Closer: {item.hardware.closer}")
    if item.hardware.flush_bolts:
        hw_list.append(f"Flush Bolts: {item.hardware.flush_bolts}")
    if item.hardware.sliding_track:
        hw_list.append(f"Track: {item.hardware.sliding_track}")
    if item.hardware.accessories:
        hw_list.append("Accessories: " + ", ".join(item.hardware.accessories))

    hw_text = " | ".join(hw_list) if hw_list else "Standard Manufacturer Hardware Set"

    svg_lines = [
        f'<g id="card-{item.type_tag}" class="schedule-card">',
        f'  <rect x="0" y="0" width="{card_width_mm:.1f}" height="{card_height_mm:.1f}" fill="#ffffff" stroke="#94a3b8" stroke-width="0.5" rx="1.5" />',
        '  <!-- 2D Elevation Graphics -->',
        f'  <g transform="translate(2.0, 5.0)">',
        f'{elev_svg}',
        '  </g>',
        '  <!-- Specification Table -->',
        f'  <g transform="translate({tbl_x:.1f}, 5.0)">',
        '    <!-- Table Header -->',
        f'    <rect x="0" y="0" width="{tbl_w:.1f}" height="7.0" fill="#1e293b" rx="0.5" />',
        f'    <text x="4.0" y="4.8" font-family="Sarabun, sans-serif" font-size="3.5px" font-weight="bold" fill="#ffffff">แบบขยายประตู-หน้าต่าง / Opening Schedule Specification ({item.type_tag})</text>',
        f'    <text x="{tbl_w - 4.0:.1f}" y="4.8" font-family="Sarabun, sans-serif" font-size="3.2px" font-weight="bold" text-anchor="end" fill="#f8fafc">จำนวน {item.quantity} ชุด (QTY: {item.quantity})</text>',
    ]

    rows = [
        ("รายการ (ITEM):", f"สัญลักษณ์ {item.type_tag} ({item.category})"),
        ("ขนาดช่องเปิด (W x H):", f"{item.width:.2f} x {item.height:.2f} m. (สูงจากพื้น Sill: +{item.sill_height:.2f} m.)"),
        ("ลักษณะการเปิด (OPERATION):", item.operation_type),
        ("วงกบ (FRAME MATERIAL):", item.frame_material),
        ("บานประตู/หน้าต่าง (PANEL):", item.panel_glazing),
        ("อุปกรณ์ประกอบ (HARDWARE):", hw_text[:75] + ("..." if len(hw_text) > 75 else "")),
        ("ตำแหน่งที่ใช้ (LOCATION):", inst_str),
    ]

    row_y = 11.0
    row_h = 9.8

    for idx, (label, val) in enumerate(rows):
        bg_fill = "#f8fafc" if idx % 2 == 0 else "#ffffff"
        svg_lines.append(f'    <rect x="0" y="{row_y - 3.2:.1f}" width="{tbl_w:.1f}" height="{row_h:.1f}" fill="{bg_fill}" stroke="#e2e8f0" stroke-width="0.3" />')
        svg_lines.append(f'    <text x="3.0" y="{row_y + 2.8:.1f}" font-family="Sarabun, sans-serif" font-size="2.6px" font-weight="bold" fill="#334155">{label}</text>')
        svg_lines.append(f'    <text x="48.0" y="{row_y + 2.8:.1f}" font-family="Sarabun, sans-serif" font-size="2.6px" fill="#0f172a">{val}</text>')
        row_y += row_h

    svg_lines.append('  </g>')
    svg_lines.append('</g>')
    return "\n".join(svg_lines)


def render_opening_schedule_svg(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
    sheet_config: Optional[Any] = None,
) -> str:
    """
    Render complete Architectural Door & Window Schedule drawing sheet (A-401).
    Fits 2D elevations, dimensions, material & hardware specification tables,
    and automated quantity take-offs onto standard A3 Paper Space drawing sheet.
    """
    from debim.draw.renderer import SheetConfig, SheetRenderer

    if isinstance(manifest_or_resolved, ProjectManifest):
        resolved = SpatialResolver(manifest_or_resolved).resolve()
    else:
        resolved = manifest_or_resolved

    doors, windows = extract_opening_schedule(resolved)

    all_items = doors + windows

    if sheet_config is None:
        cfg = SheetConfig(
            id="A-401",
            title="Door and Window Schedule and Hardware Specifications",
            view_type="SCHEDULE",
            paper_size="A3",
            scale=1,
        )
    elif isinstance(sheet_config, SheetConfig):
        cfg = sheet_config
    else:
        cfg = SheetConfig.model_validate(sheet_config)

    paper_w, paper_h = cfg.get_paper_dimensions_mm()
    m_left, m_top, m_right, m_bottom = cfg.get_margins_mm()

    printable_x = m_left
    printable_y = m_top
    printable_w = paper_w - m_left - m_right
    printable_h = paper_h - m_top - m_bottom

    tb_width = cfg.title_block.width_mm if cfg.visibility.show_title_block else 0.0
    drawing_w = printable_w - tb_width - (5.0 if tb_width > 0 else 0.0)
    title_x = printable_x + printable_w - tb_width if tb_width > 0 else 0.0

    # Layout Schedule Cards into 2 Columns x N Rows
    card_w = min(182.0, (drawing_w - 6.0) / 2.0)
    card_h = 82.0

    cols = 2
    gap_x = (drawing_w - cols * card_w) / (cols + 1)
    gap_y = 6.0

    renderer = SheetRenderer(resolved, cfg)
    embedded_css = renderer._get_embedded_css() if hasattr(renderer, "_get_embedded_css") else ""

    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {paper_w:.1f} {paper_h:.1f}" width="{paper_w:.1f}mm" height="{paper_h:.1f}mm">',
        '  <defs>',
        '    <style type="text/css"><![CDATA[',
        f'{embedded_css}',
        '    ]]></style>',
        '  </defs>',
        '  <!-- Background -->',
        f'  <rect x="0" y="0" width="{paper_w:.1f}" height="{paper_h:.1f}" fill="#ffffff" />',
        '  <!-- Outer Sheet Border & Margin -->',
        f'  <rect x="{printable_x:.1f}" y="{printable_y:.1f}" width="{printable_w:.1f}" height="{printable_h:.1f}" class="sheet-border" fill="none" />',
        f'  <rect x="{printable_x + 2.0:.1f}" y="{printable_y + 2.0:.1f}" width="{printable_w - 4.0:.1f}" height="{printable_h - 4.0:.1f}" class="sheet-inner-border" fill="none" />',
        '  <!-- Drawing Viewport for Opening Schedule -->',
        f'  <g id="schedule-viewport" transform="translate({printable_x:.1f}, {printable_y:.1f})">',
        '    <!-- Drawing Sheet Header -->',
        '    <text x="5.0" y="10.0" font-family="Sarabun, sans-serif" font-size="5.5px" font-weight="bold" fill="#0f172a">แบบขยายประตู-หน้าต่าง และรายการอุปกรณ์ (DOOR &amp; WINDOW ELEVATIONS &amp; HARDWARE SCHEDULE)</text>',
        '    <line x1="5.0" y1="12.5" x2="320.0" y2="12.5" stroke="#0f172a" stroke-width="0.8" />',
    ]

    # Render Schedule Cards
    start_x = gap_x
    start_y = 16.0

    for idx, item in enumerate(all_items):
        c_idx = idx % cols
        r_idx = idx // cols

        cx = start_x + c_idx * (card_w + gap_x)
        cy = start_y + r_idx * (card_h + gap_y)

        if cy + card_h > printable_h - 5.0:
            break

        card_svg = render_schedule_card_svg(item, card_width_mm=card_w, card_height_mm=card_h)
        svg_lines.append(f'    <g transform="translate({cx:.1f}, {cy:.1f})">')
        svg_lines.append(card_svg)
        svg_lines.append('    </g>')

    svg_lines.append('  </g> <!-- End schedule-viewport -->')

    # Title Block
    if cfg.visibility.show_title_block:
        proj_name = cfg.project_name or resolved.manifest.project.name
        date_str = cfg.date or "2025-01-01"
        svg_lines.append(renderer._render_title_block_svg(title_x, printable_y, tb_width, printable_h, proj_name, date_str))

    svg_lines.append('</svg>')
    return "\n".join(svg_lines)
