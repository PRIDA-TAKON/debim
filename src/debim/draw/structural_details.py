"""
Structural RC Beam, Column, and Footing Detail Schedule Engine (แบบขยายโครงสร้าง คสล.) for debim.
Generates standard reinforced concrete detail sheets showing cross-sections,
rebar arrangements, dimension callouts, and material specifications fitted onto standard A3 drawing sheets (S-201).
"""

import math
import re
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, Field

from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedFooting,
    ResolvedManifest,
    SpatialResolver,
)
from debim.schema import IfcBeam, IfcColumn, IfcFooting, ProjectManifest


class BeamDetailItem(BaseModel):
    """Processed beam cross-section detail entry."""
    type_tag: str  # e.g. B1, B2, DB1
    category: Literal["BEAM"] = "BEAM"
    width: float  # cross-section width B (m)
    depth: float  # cross-section depth D (m)
    main_top: str  # e.g. "2-DB12"
    main_bottom: str  # e.g. "2-DB12" or "3-DB16"
    stirrups: str  # e.g. "RB9@0.15 m"
    covering: float = 0.03  # concrete covering (m)
    quantity: int = 1
    instances: List[str] = Field(default_factory=list)  # e.g. ["B-L1-01", "B-L1-02"]
    remarks: Optional[str] = "Standard RC Beam Cross-Section"


class ColumnDetailItem(BaseModel):
    """Processed column section detail entry."""
    type_tag: str  # e.g. C1, C2
    category: Literal["COLUMN"] = "COLUMN"
    section_shape: Literal["RECTANGULAR", "CIRCULAR"] = "RECTANGULAR"
    width: float  # width B or diameter (m)
    depth: float  # depth D or diameter (m)
    main_rebar: str  # e.g. "4-DB16" or "8-DB16"
    stirrups: str  # e.g. "RB9@0.15 m"
    covering: float = 0.03  # concrete covering (m)
    quantity: int = 1
    instances: List[str] = Field(default_factory=list)
    remarks: Optional[str] = "Standard RC Column Section"


class FootingDetailItem(BaseModel):
    """Processed footing detail entry."""
    type_tag: str  # e.g. F1, F2
    category: Literal["FOOTING"] = "FOOTING"
    footing_type: Literal["SPREAD", "PILE_CAP"] = "SPREAD"
    width: float  # W (m)
    depth: float  # D (m)
    thickness: float  # H (m)
    rebar_mat_x: str  # e.g. "DB12@0.15 m"
    rebar_mat_y: str  # e.g. "DB12@0.15 m"
    lean_thickness: float = 0.05  # lean concrete thickness (m)
    sand_thickness: float = 0.10  # compacted sand thickness (m)
    piles_count: int = 0
    pile_spec: Optional[str] = None  # e.g. "Hexagonal Pile 0.15m x 6m"
    quantity: int = 1
    instances: List[str] = Field(default_factory=list)
    remarks: Optional[str] = "Standard RC Spread Footing / Pile Cap"


StructuralDetailItem = Union[BeamDetailItem, ColumnDetailItem, FootingDetailItem]


def _parse_rebar_count(rebar_str: str, default_count: int = 2) -> int:
    """Extract integer rebar count from spec string like '4-DB16' or '2-DB12'."""
    if not rebar_str:
        return default_count
    match = re.search(r"^(\d+)\s*[-xX]", str(rebar_str).strip())
    if match:
        try:
            return max(1, int(match.group(1)))
        except ValueError:
            pass
    return default_count


def extract_structural_details(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
) -> Tuple[List[BeamDetailItem], List[ColumnDetailItem], List[FootingDetailItem]]:
    """
    Extract, aggregate, and classify all structural beams, columns, and footings.
    Returns (beam_details, column_details, footing_details) with clean type tags (B1, C1, F1, etc.).
    """
    if isinstance(manifest_or_resolved, ProjectManifest):
        resolved = SpatialResolver(manifest_or_resolved).resolve()
    else:
        resolved = manifest_or_resolved

    # 1. Process Beams
    beam_groups: Dict[Tuple[float, float, str, str, str], List[Union[IfcBeam, ResolvedBeam]]] = {}
    for bm in resolved.beams:
        elem_obj = getattr(bm, "element", bm)
        w = round(bm.width, 2) if hasattr(bm, "width") else round(float(getattr(elem_obj.profile, "width", 0.2)), 2)
        d = round(bm.depth, 2) if hasattr(bm, "depth") else round(float(getattr(elem_obj.profile, "depth", 0.4)), 2)

        reinf = getattr(elem_obj, "reinforcement", None)
        top = getattr(reinf, "main_top", "2-DB12") if reinf else "2-DB12"
        bot = getattr(reinf, "main_bottom", "2-DB12") if reinf else "2-DB12"
        st = getattr(reinf, "stirrups", "RB9@0.15 m") if reinf else "RB9@0.15 m"

        key = (w, d, top or "2-DB12", bot or "2-DB12", st or "RB9@0.15 m")
        beam_groups.setdefault(key, []).append(bm)

    # Fallback to manifest elements if resolved beams list is empty
    if not beam_groups:
        for elem in resolved.manifest.elements:
            if isinstance(elem, IfcBeam):
                w = round(float(getattr(elem.profile, "width", 0.20)), 2)
                d = round(float(getattr(elem.profile, "depth", 0.40)), 2)
                reinf = elem.reinforcement
                top = getattr(reinf, "main_top", "2-DB12") if reinf else "2-DB12"
                bot = getattr(reinf, "main_bottom", "2-DB12") if reinf else "2-DB12"
                st = getattr(reinf, "stirrups", "RB9@0.15 m") if reinf else "RB9@0.15 m"
                key = (w, d, top or "2-DB12", bot or "2-DB12", st or "RB9@0.15 m")
                beam_groups.setdefault(key, []).append(elem)

    beam_items: List[BeamDetailItem] = []
    for idx, (key, instances) in enumerate(sorted(beam_groups.items(), key=lambda k: (-k[0][0], -k[0][1])), start=1):
        w, d, top, bot, st = key
        tags = sorted([getattr(inst, "tag", f"B-{i}") for i, inst in enumerate(instances, 1)])
        beam_items.append(
            BeamDetailItem(
                type_tag=f"B{idx}",
                width=w,
                depth=d,
                main_top=top,
                main_bottom=bot,
                stirrups=st,
                covering=0.03,
                quantity=len(instances),
                instances=tags,
                remarks="Structural Concrete Beam Section",
            )
        )

    # 2. Process Columns
    column_groups: Dict[Tuple[str, float, float, str, str], List[Union[IfcColumn, ResolvedColumn]]] = {}
    for col in resolved.columns:
        elem_obj = getattr(col, "element", col)
        prof = getattr(elem_obj, "profile", None)
        shape_type = getattr(prof, "shape", "BOX").upper() if prof else "BOX"
        is_circ = shape_type in ("CIRCULAR", "CIRCLE")

        if is_circ:
            dia = round(float(getattr(prof, "width", 0.30)), 2)
            w, d = dia, dia
            sec_shape = "CIRCULAR"
        else:
            w = round(float(getattr(prof, "width", 0.30)), 2)
            d = round(float(getattr(prof, "depth", 0.30)), 2)
            sec_shape = "RECTANGULAR"

        reinf = getattr(elem_obj, "reinforcement", None)
        main = getattr(reinf, "main", "4-DB16" if sec_shape == "RECTANGULAR" else "6-DB16") if reinf else ("4-DB16" if sec_shape == "RECTANGULAR" else "6-DB16")
        st = getattr(reinf, "stirrups", "RB9@0.15 m") if reinf else "RB9@0.15 m"

        key = (sec_shape, w, d, main or "4-DB16", st or "RB9@0.15 m")
        column_groups.setdefault(key, []).append(col)

    if not column_groups:
        for elem in resolved.manifest.elements:
            if isinstance(elem, IfcColumn):
                prof = elem.profile
                shape_type = getattr(prof, "shape", "BOX").upper() if prof else "BOX"
                is_circ = shape_type in ("CIRCULAR", "CIRCLE")
                if is_circ:
                    dia = round(float(getattr(prof, "width", 0.30)), 2)
                    w, d = dia, dia
                    sec_shape = "CIRCULAR"
                else:
                    w = round(float(getattr(prof, "width", 0.30)), 2)
                    d = round(float(getattr(prof, "depth", 0.30)), 2)
                    sec_shape = "RECTANGULAR"
                reinf = elem.reinforcement
                main = getattr(reinf, "main", "4-DB16") if reinf else "4-DB16"
                st = getattr(reinf, "stirrups", "RB9@0.15 m") if reinf else "RB9@0.15 m"
                key = (sec_shape, w, d, main or "4-DB16", st or "RB9@0.15 m")
                column_groups.setdefault(key, []).append(elem)

    column_items: List[ColumnDetailItem] = []
    for idx, (key, instances) in enumerate(sorted(column_groups.items(), key=lambda k: (-k[0][1], -k[0][2])), start=1):
        sec_shape, w, d, main, st = key
        tags = sorted([getattr(inst, "tag", f"C-{i}") for i, inst in enumerate(instances, 1)])
        column_items.append(
            ColumnDetailItem(
                type_tag=f"C{idx}",
                section_shape=sec_shape,
                width=w,
                depth=d,
                main_rebar=main,
                stirrups=st,
                covering=0.03,
                quantity=len(instances),
                instances=tags,
                remarks="Structural RC Column Section",
            )
        )

    # 3. Process Footings
    footing_groups: Dict[Tuple[str, float, float, float, str, str, int, str], List[Union[IfcFooting, ResolvedFooting]]] = {}
    for ft in resolved.footings:
        elem_obj = getattr(ft, "element", ft)
        w = round(float(ft.width), 2) if hasattr(ft, "width") else round(float(getattr(elem_obj.profile, "width", 1.0)), 2)
        d = round(float(ft.depth), 2) if hasattr(ft, "depth") else round(float(getattr(elem_obj.profile, "depth", 1.0)), 2)
        h = round(float(ft.thickness), 2) if hasattr(ft, "thickness") else round(float(getattr(elem_obj.profile, "thickness", 0.3)), 2)

        reinf = getattr(elem_obj, "reinforcement", None)
        rx = getattr(reinf, "mesh_x", "DB12@0.15 m") if reinf else "DB12@0.15 m"
        ry = getattr(reinf, "mesh_y", "DB12@0.15 m") if reinf else "DB12@0.15 m"

        piles_obj = getattr(elem_obj, "piles", None)
        p_cnt = piles_obj.count if piles_obj else 0
        f_type = "PILE_CAP" if p_cnt > 0 else "SPREAD"
        p_spec = f"Piles: {p_cnt} Pcs ({getattr(piles_obj, 'length', 6.0)}m)" if p_cnt > 0 else "Spread Footing"

        key = (f_type, w, d, h, rx or "DB12@0.15 m", ry or "DB12@0.15 m", p_cnt, p_spec)
        footing_groups.setdefault(key, []).append(ft)

    if not footing_groups:
        for elem in resolved.manifest.elements:
            if isinstance(elem, IfcFooting):
                w = round(float(getattr(elem.profile, "width", 1.00)), 2)
                d = round(float(getattr(elem.profile, "depth", 1.00)), 2)
                h = round(float(getattr(elem.profile, "thickness", 0.30)), 2)
                reinf = elem.reinforcement
                rx = getattr(reinf, "mesh_x", "DB12@0.15 m") if reinf else "DB12@0.15 m"
                ry = getattr(reinf, "mesh_y", "DB12@0.15 m") if reinf else "DB12@0.15 m"
                piles_obj = elem.piles
                p_cnt = piles_obj.count if piles_obj else 0
                f_type = "PILE_CAP" if p_cnt > 0 else "SPREAD"
                p_spec = f"Piles: {p_cnt} Pcs ({getattr(piles_obj, 'length', 6.0)}m)" if p_cnt > 0 else "Spread Footing"
                key = (f_type, w, d, h, rx or "DB12@0.15 m", ry or "DB12@0.15 m", p_cnt, p_spec)
                footing_groups.setdefault(key, []).append(elem)

    footing_items: List[FootingDetailItem] = []
    for idx, (key, instances) in enumerate(sorted(footing_groups.items(), key=lambda k: (-k[0][1], -k[0][2])), start=1):
        f_type, w, d, h, rx, ry, p_cnt, p_spec = key
        tags = sorted([getattr(inst, "tag", f"F-{i}") for i, inst in enumerate(instances, 1)])
        footing_items.append(
            FootingDetailItem(
                type_tag=f"F{idx}",
                footing_type=f_type,
                width=w,
                depth=d,
                thickness=h,
                rebar_mat_x=rx,
                rebar_mat_y=ry,
                lean_thickness=0.05,
                sand_thickness=0.10,
                piles_count=p_cnt,
                pile_spec=p_spec,
                quantity=len(instances),
                instances=tags,
                remarks="RC Spread Footing / Foundation",
            )
        )

    return beam_items, column_items, footing_items


def render_beam_section_svg(
    item: BeamDetailItem,
    box_width_mm: float = 75.0,
    box_height_mm: float = 70.0,
) -> str:
    """
    Render 2D vector cross-section SVG for a single beam type (e.g. B1, DB1)
    showing concrete boundary ($B \times D$), stirrup tie rectangle,
    top/bottom main rebar circles, dimensions, and callout annotations.
    """
    w_m = item.width
    d_m = item.depth

    pad_left_mm = 14.0
    pad_top_mm = 10.0
    pad_right_mm = 14.0
    pad_bot_mm = 18.0

    avail_w = box_width_mm - pad_left_mm - pad_right_mm
    avail_h = box_height_mm - pad_top_mm - pad_bot_mm

    scale_x = avail_w / max(w_m, 0.15)
    scale_y = avail_h / max(d_m, 0.25)
    scale = min(scale_x, scale_y) * 0.88

    drawing_w_mm = w_m * scale
    drawing_h_mm = d_m * scale

    x0 = pad_left_mm + (avail_w - drawing_w_mm) / 2.0
    y0 = pad_top_mm + (avail_h - drawing_h_mm) / 2.0

    covering_mm = max(1.2, item.covering * scale)
    rebar_r_mm = max(1.0, 0.012 * scale / 2.0)

    top_count = _parse_rebar_count(item.main_top, 2)
    bot_count = _parse_rebar_count(item.main_bottom, 2)

    svg_parts = [
        f'<g id="beam-section-{item.type_tag}" class="structural-detail-section">',
        f'  <rect x="0" y="0" width="{box_width_mm:.1f}" height="{box_height_mm:.1f}" fill="none" stroke="#cbd5e1" stroke-width="0.3" rx="1.0" />',
        f'  <circle cx="{box_width_mm / 2.0:.1f}" cy="6.0" r="4.5" fill="#f8fafc" stroke="#0f172a" stroke-width="0.8" />',
        f'  <text x="{box_width_mm / 2.0:.1f}" y="7.2" class="detail-type-tag" font-family="Sarabun, sans-serif" font-size="3.8px" font-weight="bold" text-anchor="middle" fill="#0f172a">{item.type_tag}</text>',

        '  <!-- Concrete Cross-Section Outer Boundary -->',
        f'  <rect x="{x0:.2f}" y="{y0:.2f}" width="{drawing_w_mm:.2f}" height="{drawing_h_mm:.2f}" class="concrete-boundary" fill="#f1f5f9" stroke="#0f172a" stroke-width="0.9" />',

        '  <!-- Concrete Hatch Lines -->',
        f'  <line x1="{x0 + 2.0:.2f}" y1="{y0 + 3.0:.2f}" x2="{x0 + 6.0:.2f}" y2="{y0 + 7.0:.2f}" stroke="#cbd5e1" stroke-width="0.3" />',
        f'  <line x1="{x0 + drawing_w_mm - 6.0:.2f}" y1="{y0 + drawing_h_mm - 7.0:.2f}" x2="{x0 + drawing_w_mm - 2.0:.2f}" y2="{y0 + drawing_h_mm - 3.0:.2f}" stroke="#cbd5e1" stroke-width="0.3" />',

        '  <!-- Stirrup Tie Inner Loop -->',
        f'  <rect x="{x0 + covering_mm:.2f}" y="{y0 + covering_mm:.2f}" width="{max(1.0, drawing_w_mm - 2 * covering_mm):.2f}" height="{max(1.0, drawing_h_mm - 2 * covering_mm):.2f}" class="stirrup-tie" fill="none" stroke="#dc2626" stroke-width="0.6" rx="{covering_mm * 0.5:.1f}" />',
    ]

    # Top Rebar Dots
    top_y = y0 + covering_mm + rebar_r_mm + 0.5
    inner_w = drawing_w_mm - 2 * (covering_mm + rebar_r_mm + 0.5)
    for i in range(top_count):
        tx = (x0 + covering_mm + rebar_r_mm + 0.5) if top_count == 1 else (x0 + covering_mm + rebar_r_mm + 0.5 + i * (inner_w / (top_count - 1)))
        svg_parts.append(f'  <circle cx="{tx:.2f}" cy="{top_y:.2f}" r="{rebar_r_mm:.2f}" class="rebar-main" fill="#0f172a" stroke="#0f172a" stroke-width="0.2" />')

    # Bottom Rebar Dots
    bot_y = y0 + drawing_h_mm - (covering_mm + rebar_r_mm + 0.5)
    for j in range(bot_count):
        bx = (x0 + covering_mm + rebar_r_mm + 0.5) if bot_count == 1 else (x0 + covering_mm + rebar_r_mm + 0.5 + j * (inner_w / (bot_count - 1)))
        svg_parts.append(f'  <circle cx="{bx:.2f}" cy="{bot_y:.2f}" r="{rebar_r_mm:.2f}" class="rebar-main" fill="#0f172a" stroke="#0f172a" stroke-width="0.2" />')

    # Rebar Callout Annotation Lines & Text
    callout_x1 = x0 + drawing_w_mm + 2.0
    callout_x2 = box_width_mm - 2.0

    # Top Rebar Tag
    svg_parts.append(f'  <line x1="{x0 + drawing_w_mm - covering_mm:.2f}" y1="{top_y:.2f}" x2="{callout_x1:.2f}" y2="{top_y:.2f}" stroke="#2563eb" stroke-width="0.4" stroke-dasharray="1 1" />')
    svg_parts.append(f'  <text x="{callout_x1:.2f}" y="{top_y + 1.0:.2f}" font-family="Sarabun, sans-serif" font-size="2.4px" font-weight="bold" fill="#2563eb">{item.main_top} (Top)</text>')

    # Stirrup Tag
    mid_y = y0 + drawing_h_mm / 2.0
    svg_parts.append(f'  <line x1="{x0 + covering_mm:.2f}" y1="{mid_y:.2f}" x2="{x0 - 2.0:.2f}" y2="{mid_y:.2f}" stroke="#dc2626" stroke-width="0.4" stroke-dasharray="1 1" />')
    svg_parts.append(f'  <text x="{x0 - 2.5:.2f}" y="{mid_y + 1.0:.2f}" font-family="Sarabun, sans-serif" font-size="2.3px" font-weight="bold" text-anchor="end" fill="#dc2626">{item.stirrups}</text>')

    # Bottom Rebar Tag
    svg_parts.append(f'  <line x1="{x0 + drawing_w_mm - covering_mm:.2f}" y1="{bot_y:.2f}" x2="{callout_x1:.2f}" y2="{bot_y:.2f}" stroke="#2563eb" stroke-width="0.4" stroke-dasharray="1 1" />')
    svg_parts.append(f'  <text x="{callout_x1:.2f}" y="{bot_y + 1.0:.2f}" font-family="Sarabun, sans-serif" font-size="2.4px" font-weight="bold" fill="#2563eb">{item.main_bottom} (Bot)</text>')

    # Dimensions Below and Left
    dim_y = y0 + drawing_h_mm + 4.5
    svg_parts.append(f'  <line x1="{x0:.2f}" y1="{dim_y:.2f}" x2="{x0 + drawing_w_mm:.2f}" y2="{dim_y:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <line x1="{x0:.2f}" y1="{dim_y - 1.0:.2f}" x2="{x0:.2f}" y2="{dim_y + 1.0:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <line x1="{x0 + drawing_w_mm:.2f}" y1="{dim_y - 1.0:.2f}" x2="{x0 + drawing_w_mm:.2f}" y2="{dim_y + 1.0:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <text x="{x0 + drawing_w_mm/2.0:.2f}" y="{dim_y + 3.0:.2f}" font-family="Sarabun, sans-serif" font-size="2.5px" text-anchor="middle" fill="#0f172a">{w_m:.2f} m.</text>')

    dim_x = x0 - 4.5
    svg_parts.append(f'  <line x1="{dim_x:.2f}" y1="{y0:.2f}" x2="{dim_x:.2f}" y2="{y0 + drawing_h_mm:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <line x1="{dim_x - 1.0:.2f}" y1="{y0:.2f}" x2="{dim_x + 1.0:.2f}" y2="{y0:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <line x1="{dim_x - 1.0:.2f}" y1="{y0 + drawing_h_mm:.2f}" x2="{dim_x + 1.0:.2f}" y2="{y0 + drawing_h_mm:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <text x="{dim_x - 1.5:.2f}" y="{y0 + drawing_h_mm/2.0:.2f}" font-family="Sarabun, sans-serif" font-size="2.5px" text-anchor="middle" transform="rotate(-90 {dim_x - 1.5:.2f} {y0 + drawing_h_mm/2.0:.2f})" fill="#0f172a">{d_m:.2f} m.</text>')

    svg_parts.append('</g>')
    return "\n".join(svg_parts)


def render_column_section_svg(
    item: ColumnDetailItem,
    box_width_mm: float = 75.0,
    box_height_mm: float = 70.0,
) -> str:
    """
    Render 2D vector cross-section SVG for a rectangular or circular column (e.g. C1)
    showing concrete outer shape ($B \times D$), tie stirrup, longitudinal rebar dots,
    dimensions, and rebar callouts.
    """
    w_m = item.width
    d_m = item.depth
    is_circ = item.section_shape == "CIRCULAR"

    pad_left_mm = 14.0
    pad_top_mm = 10.0
    pad_right_mm = 14.0
    pad_bot_mm = 18.0

    avail_w = box_width_mm - pad_left_mm - pad_right_mm
    avail_h = box_height_mm - pad_top_mm - pad_bot_mm

    scale_x = avail_w / max(w_m, 0.20)
    scale_y = avail_h / max(d_m, 0.20)
    scale = min(scale_x, scale_y) * 0.88

    drawing_w_mm = w_m * scale
    drawing_h_mm = d_m * scale

    cx = box_width_mm / 2.0
    cy = pad_top_mm + avail_h / 2.0

    x0 = cx - drawing_w_mm / 2.0
    y0 = cy - drawing_h_mm / 2.0

    covering_mm = max(1.2, item.covering * scale)
    rebar_r_mm = max(1.0, 0.016 * scale / 2.0)

    total_bars = _parse_rebar_count(item.main_rebar, 4 if not is_circ else 6)

    svg_parts = [
        f'<g id="column-section-{item.type_tag}" class="structural-detail-section">',
        f'  <rect x="0" y="0" width="{box_width_mm:.1f}" height="{box_height_mm:.1f}" fill="none" stroke="#cbd5e1" stroke-width="0.3" rx="1.0" />',
        f'  <circle cx="{box_width_mm / 2.0:.1f}" cy="6.0" r="4.5" fill="#f8fafc" stroke="#0f172a" stroke-width="0.8" />',
        f'  <text x="{box_width_mm / 2.0:.1f}" y="7.2" class="detail-type-tag" font-family="Sarabun, sans-serif" font-size="3.8px" font-weight="bold" text-anchor="middle" fill="#0f172a">{item.type_tag}</text>',
    ]

    if is_circ:
        r_outer = drawing_w_mm / 2.0
        r_tie = max(1.0, r_outer - covering_mm)
        r_rebar_circle = max(1.0, r_tie - rebar_r_mm)

        svg_parts.append(f'  <circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r_outer:.2f}" class="concrete-boundary" fill="#f1f5f9" stroke="#0f172a" stroke-width="0.9" />')
        svg_parts.append(f'  <circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r_tie:.2f}" class="stirrup-tie" fill="none" stroke="#dc2626" stroke-width="0.6" />')

        # Distribute longitudinal rebar dots evenly around circle
        for i in range(total_bars):
            ang = 2.0 * math.pi * i / float(total_bars) - math.pi / 2.0
            bx = cx + r_rebar_circle * math.cos(ang)
            by = cy + r_rebar_circle * math.sin(ang)
            svg_parts.append(f'  <circle cx="{bx:.2f}" cy="{by:.2f}" r="{rebar_r_mm:.2f}" class="rebar-main" fill="#0f172a" stroke="#0f172a" stroke-width="0.2" />')

    else:  # RECTANGULAR
        svg_parts.append(f'  <rect x="{x0:.2f}" y="{y0:.2f}" width="{drawing_w_mm:.2f}" height="{drawing_h_mm:.2f}" class="concrete-boundary" fill="#f1f5f9" stroke="#0f172a" stroke-width="0.9" />')
        svg_parts.append(f'  <rect x="{x0 + covering_mm:.2f}" y="{y0 + covering_mm:.2f}" width="{max(1.0, drawing_w_mm - 2 * covering_mm):.2f}" height="{max(1.0, drawing_h_mm - 2 * covering_mm):.2f}" class="stirrup-tie" fill="none" stroke="#dc2626" stroke-width="0.6" rx="{covering_mm * 0.5:.1f}" />')

        # Corner and face rebar dots
        rx_min = x0 + covering_mm + rebar_r_mm + 0.5
        rx_max = x0 + drawing_w_mm - (covering_mm + rebar_r_mm + 0.5)
        ry_min = y0 + covering_mm + rebar_r_mm + 0.5
        ry_max = y0 + drawing_h_mm - (covering_mm + rebar_r_mm + 0.5)

        dots: List[Tuple[float, float]] = []

        if total_bars == 4:
            dots = [(rx_min, ry_min), (rx_max, ry_min), (rx_min, ry_max), (rx_max, ry_max)]
        elif total_bars == 6:
            dots = [
                (rx_min, ry_min), ((rx_min + rx_max) / 2.0, ry_min), (rx_max, ry_min),
                (rx_min, ry_max), ((rx_min + rx_max) / 2.0, ry_max), (rx_max, ry_max),
            ]
        elif total_bars == 8:
            dots = [
                (rx_min, ry_min), ((rx_min + rx_max) / 2.0, ry_min), (rx_max, ry_min),
                (rx_min, (ry_min + ry_max) / 2.0), (rx_max, (ry_min + ry_max) / 2.0),
                (rx_min, ry_max), ((rx_min + rx_max) / 2.0, ry_max), (rx_max, ry_max),
            ]
        else:
            # General distribution
            for i in range(total_bars):
                ang = 2.0 * math.pi * i / float(total_bars) - math.pi / 2.0
                rx = cx + (drawing_w_mm / 2.0 - covering_mm - rebar_r_mm) * math.cos(ang)
                ry = cy + (drawing_h_mm / 2.0 - covering_mm - rebar_r_mm) * math.sin(ang)
                dots.append((rx, ry))

        for bx, by in dots:
            svg_parts.append(f'  <circle cx="{bx:.2f}" cy="{by:.2f}" r="{rebar_r_mm:.2f}" class="rebar-main" fill="#0f172a" stroke="#0f172a" stroke-width="0.2" />')

    # Rebar Callout Tag
    callout_x = x0 + drawing_w_mm + 2.0
    svg_parts.append(f'  <line x1="{cx:.2f}" y1="{cy:.2f}" x2="{callout_x:.2f}" y2="{cy - 5.0:.2f}" stroke="#2563eb" stroke-width="0.4" stroke-dasharray="1 1" />')
    svg_parts.append(f'  <text x="{callout_x:.2f}" y="{cy - 6.0:.2f}" font-family="Sarabun, sans-serif" font-size="2.4px" font-weight="bold" fill="#2563eb">{item.main_rebar}</text>')
    svg_parts.append(f'  <text x="{callout_x:.2f}" y="{cy - 2.5:.2f}" font-family="Sarabun, sans-serif" font-size="2.2px" fill="#dc2626">{item.stirrups}</text>')

    # Dimensions Below
    dim_y = y0 + drawing_h_mm + 4.5
    svg_parts.append(f'  <line x1="{x0:.2f}" y1="{dim_y:.2f}" x2="{x0 + drawing_w_mm:.2f}" y2="{dim_y:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <line x1="{x0:.2f}" y1="{dim_y - 1.0:.2f}" x2="{x0:.2f}" y2="{dim_y + 1.0:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <line x1="{x0 + drawing_w_mm:.2f}" y1="{dim_y - 1.0:.2f}" x2="{x0 + drawing_w_mm:.2f}" y2="{dim_y + 1.0:.2f}" stroke="#0f172a" stroke-width="0.4" />')

    dim_str = f"Ø {w_m:.2f} m." if is_circ else f"{w_m:.2f} x {d_m:.2f} m."
    svg_parts.append(f'  <text x="{cx:.2f}" y="{dim_y + 3.0:.2f}" font-family="Sarabun, sans-serif" font-size="2.5px" text-anchor="middle" fill="#0f172a">{dim_str}</text>')

    svg_parts.append('</g>')
    return "\n".join(svg_parts)


def render_footing_detail_svg(
    item: FootingDetailItem,
    box_width_mm: float = 85.0,
    box_height_mm: float = 75.0,
) -> str:
    """
    Render 2D vector section view SVG for spread footing or pile cap (e.g. F1) showing:
    - Concrete footing pad ($W \times H$)
    - Compacted sand bedding (0.10m) with stipple hatch pattern
    - Lean concrete layer (0.05m)
    - Bottom reinforcement mat grid (lines & dots, e.g. DB12@0.15m)
    - Column stub starter bars (dowel bars)
    - Piles under footing if present
    - Dimensions and annotations.
    """
    w_m = item.width
    h_m = item.thickness
    sand_m = item.sand_thickness
    lean_m = item.lean_thickness

    pad_left_mm = 16.0
    pad_top_mm = 14.0
    pad_right_mm = 16.0
    pad_bot_mm = 18.0

    avail_w = box_width_mm - pad_left_mm - pad_right_mm
    tot_h_m = h_m + lean_m + sand_m + 0.30  # includes ground line and column stub
    avail_h = box_height_mm - pad_top_mm - pad_bot_mm

    scale_x = avail_w / max(w_m, 0.80)
    scale_y = avail_h / max(tot_h_m, 0.60)
    scale = min(scale_x, scale_y) * 0.88

    footing_w_mm = w_m * scale
    footing_h_mm = h_m * scale
    sand_h_mm = max(1.5, sand_m * scale)
    lean_h_mm = max(1.0, lean_m * scale)

    cx = box_width_mm / 2.0
    x0 = cx - footing_w_mm / 2.0

    # Vertical positioning from bottom up
    bot_y = box_height_mm - pad_bot_mm - 4.0
    sand_y0 = bot_y - sand_h_mm
    lean_y0 = sand_y0 - lean_h_mm
    footing_y0 = lean_y0 - footing_h_mm

    col_w_mm = max(6.0, 0.20 * scale)
    col_x0 = cx - col_w_mm / 2.0
    col_h_mm = max(8.0, 0.25 * scale)
    col_y0 = footing_y0 - col_h_mm

    ground_y = footing_y0 - 2.0

    svg_parts = [
        f'<g id="footing-detail-{item.type_tag}" class="structural-detail-section">',
        f'  <rect x="0" y="0" width="{box_width_mm:.1f}" height="{box_height_mm:.1f}" fill="none" stroke="#cbd5e1" stroke-width="0.3" rx="1.0" />',
        f'  <circle cx="{box_width_mm / 2.0:.1f}" cy="6.0" r="4.5" fill="#f8fafc" stroke="#0f172a" stroke-width="0.8" />',
        f'  <text x="{box_width_mm / 2.0:.1f}" y="7.2" class="detail-type-tag" font-family="Sarabun, sans-serif" font-size="3.8px" font-weight="bold" text-anchor="middle" fill="#0f172a">{item.type_tag}</text>',

        '  <!-- Ground Line -->',
        f'  <line x1="{x0 - 6.0:.2f}" y1="{ground_y:.2f}" x2="{x0 + footing_w_mm + 6.0:.2f}" y2="{ground_y:.2f}" stroke="#475569" stroke-width="0.6" stroke-dasharray="3 1" />',
        f'  <text x="{x0 - 7.0:.2f}" y="{ground_y + 1.0:.2f}" font-family="Sarabun, sans-serif" font-size="2.0px" fill="#475569" text-anchor="end">ระดับดินเดิม</text>',

        '  <!-- 1. Compacted Sand Bedding Layer (10 cm) -->',
        f'  <rect x="{x0 - 2.0:.2f}" y="{sand_y0:.2f}" width="{footing_w_mm + 4.0:.2f}" height="{sand_h_mm:.2f}" fill="#fef3c7" stroke="#334155" stroke-width="0.4" />',
        '  <!-- Sand Stipple Pattern -->',
        f'  <circle cx="{cx - 10.0:.2f}" cy="{sand_y0 + sand_h_mm/2.0:.2f}" r="0.3" fill="#d97706" />',
        f'  <circle cx="{cx:.2f}" cy="{sand_y0 + sand_h_mm/2.0:.2f}" r="0.3" fill="#d97706" />',
        f'  <circle cx="{cx + 10.0:.2f}" cy="{sand_y0 + sand_h_mm/2.0:.2f}" r="0.3" fill="#d97706" />',

        '  <!-- 2. Lean Concrete Layer (5 cm) -->',
        f'  <rect x="{x0 - 2.0:.2f}" y="{lean_y0:.2f}" width="{footing_w_mm + 4.0:.2f}" height="{lean_h_mm:.2f}" fill="#e2e8f0" stroke="#334155" stroke-width="0.4" />',

        '  <!-- 3. Concrete Footing Pad -->',
        f'  <rect x="{x0:.2f}" y="{footing_y0:.2f}" width="{footing_w_mm:.2f}" height="{footing_h_mm:.2f}" class="concrete-boundary" fill="#f1f5f9" stroke="#0f172a" stroke-width="0.9" />',

        '  <!-- Column Stub -->',
        f'  <rect x="{col_x0:.2f}" y="{col_y0:.2f}" width="{col_w_mm:.2f}" height="{col_h_mm:.2f}" class="concrete-boundary" fill="#f1f5f9" stroke="#0f172a" stroke-width="0.8" />',
    ]

    # 4. Piles if present
    if item.piles_count > 0:
        pile_w_mm = max(3.0, 0.15 * scale)
        pile_h_mm = 12.0
        p_offsets = [-footing_w_mm * 0.25, footing_w_mm * 0.25] if item.piles_count >= 2 else [0.0]
        for px_off in p_offsets:
            px_c = cx + px_off - pile_w_mm / 2.0
            svg_parts.append(f'  <rect x="{px_c:.2f}" y="{bot_y:.2f}" width="{pile_w_mm:.2f}" height="{pile_h_mm:.2f}" fill="#cbd5e1" stroke="#0f172a" stroke-width="0.6" />')
            svg_parts.append(f'  <polygon points="{px_c:.2f},{bot_y + pile_h_mm:.2f} {px_c + pile_w_mm/2.0:.2f},{bot_y + pile_h_mm + 3.0:.2f} {px_c + pile_w_mm:.2f},{bot_y + pile_h_mm:.2f}" fill="#0f172a" />')

    # 5. Bottom Reinforcement Mat (Grid Lines & Transverse Dots)
    rebar_y_line = lean_y0 - 3.0
    svg_parts.append(f'  <line x1="{x0 + 3.0:.2f}" y1="{rebar_y_line:.2f}" x2="{x0 + footing_w_mm - 3.0:.2f}" y2="{rebar_y_line:.2f}" stroke="#0f172a" stroke-width="0.8" />')
    # Hooks on both ends turning up
    svg_parts.append(f'  <line x1="{x0 + 3.0:.2f}" y1="{rebar_y_line:.2f}" x2="{x0 + 3.0:.2f}" y2="{rebar_y_line - 4.0:.2f}" stroke="#0f172a" stroke-width="0.8" />')
    svg_parts.append(f'  <line x1="{x0 + footing_w_mm - 3.0:.2f}" y1="{rebar_y_line:.2f}" x2="{x0 + footing_w_mm - 3.0:.2f}" y2="{rebar_y_line - 4.0:.2f}" stroke="#0f172a" stroke-width="0.8" />')

    # Transverse dots along bottom mat
    n_dots = 6
    dot_sp = (footing_w_mm - 8.0) / float(n_dots - 1)
    for i in range(n_dots):
        dot_x = x0 + 4.0 + i * dot_sp
        svg_parts.append(f'  <circle cx="{dot_x:.2f}" cy="{rebar_y_line - 1.2:.2f}" r="0.8" fill="#2563eb" stroke="#0f172a" stroke-width="0.2" />')

    # Dowel Starter Bars
    svg_parts.append(f'  <line x1="{col_x0 + 2.0:.2f}" y1="{col_y0:.2f}" x2="{col_x0 + 2.0:.2f}" y2="{rebar_y_line:.2f}" stroke="#0f172a" stroke-width="0.6" />')
    svg_parts.append(f'  <line x1="{col_x0 + 2.0:.2f}" y1="{rebar_y_line:.2f}" x2="{col_x0 - 3.0:.2f}" y2="{rebar_y_line:.2f}" stroke="#0f172a" stroke-width="0.6" />')

    svg_parts.append(f'  <line x1="{col_x0 + col_w_mm - 2.0:.2f}" y1="{col_y0:.2f}" x2="{col_x0 + col_w_mm - 2.0:.2f}" y2="{rebar_y_line:.2f}" stroke="#0f172a" stroke-width="0.6" />')
    svg_parts.append(f'  <line x1="{col_x0 + col_w_mm - 2.0:.2f}" y1="{rebar_y_line:.2f}" x2="{col_x0 + col_w_mm + 3.0:.2f}" y2="{rebar_y_line:.2f}" stroke="#0f172a" stroke-width="0.6" />')

    # Rebar & Substructure Annotations
    call_x = x0 + footing_w_mm + 2.0
    svg_parts.append(f'  <line x1="{x0 + footing_w_mm - 8.0:.2f}" y1="{rebar_y_line:.2f}" x2="{call_x:.2f}" y2="{rebar_y_line:.2f}" stroke="#2563eb" stroke-width="0.4" stroke-dasharray="1 1" />')
    svg_parts.append(f'  <text x="{call_x + 1.0:.2f}" y="{rebar_y_line + 1.0:.2f}" font-family="Sarabun, sans-serif" font-size="2.3px" font-weight="bold" fill="#2563eb">{item.rebar_mat_x} (2 ทาง)</text>')

    svg_parts.append(f'  <line x1="{x0 + footing_w_mm + 2.0:.2f}" y1="{lean_y0 + lean_h_mm/2.0:.2f}" x2="{call_x + 15.0:.2f}" y2="{lean_y0 + lean_h_mm/2.0:.2f}" stroke="#334155" stroke-width="0.3" />')
    svg_parts.append(f'  <text x="{call_x + 16.0:.2f}" y="{lean_y0 + lean_h_mm/2.0 + 0.8:.2f}" font-family="Sarabun, sans-serif" font-size="2.0px" fill="#334155">คอนกรีตหยาบ 1:3:5 ({item.lean_thickness*100:.0f} cm)</text>')

    svg_parts.append(f'  <line x1="{x0 + footing_w_mm + 2.0:.2f}" y1="{sand_y0 + sand_h_mm/2.0:.2f}" x2="{call_x + 15.0:.2f}" y2="{sand_y0 + sand_h_mm/2.0:.2f}" stroke="#d97706" stroke-width="0.3" />')
    svg_parts.append(f'  <text x="{call_x + 16.0:.2f}" y="{sand_y0 + sand_h_mm/2.0 + 0.8:.2f}" font-family="Sarabun, sans-serif" font-size="2.0px" fill="#d97706">ทรายหยาบอัดแน่น ({item.sand_thickness*100:.0f} cm)</text>')

    # Width Dimension below
    dim_y = bot_y + (14.0 if item.piles_count > 0 else 3.0)
    svg_parts.append(f'  <line x1="{x0:.2f}" y1="{dim_y:.2f}" x2="{x0 + footing_w_mm:.2f}" y2="{dim_y:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <line x1="{x0:.2f}" y1="{dim_y - 1.0:.2f}" x2="{x0:.2f}" y2="{dim_y + 1.0:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <line x1="{x0 + footing_w_mm:.2f}" y1="{dim_y - 1.0:.2f}" x2="{x0 + footing_w_mm:.2f}" y2="{dim_y + 1.0:.2f}" stroke="#0f172a" stroke-width="0.4" />')
    svg_parts.append(f'  <text x="{cx:.2f}" y="{dim_y + 3.0:.2f}" font-family="Sarabun, sans-serif" font-size="2.5px" text-anchor="middle" fill="#0f172a">{w_m:.2f} x {item.depth:.2f} m.</text>')

    svg_parts.append('</g>')
    return "\n".join(svg_parts)


def render_structural_detail_card_svg(
    item: StructuralDetailItem,
    card_width_mm: float = 180.0,
    card_height_mm: float = 85.0,
) -> str:
    """
    Render complete Structural Detail Card containing 2D vector detail graphics,
    dimension callouts, rebar arrangement, and specification table.
    """
    if isinstance(item, BeamDetailItem):
        sec_svg = render_beam_section_svg(item, box_width_mm=75.0, box_height_mm=75.0)
        item_title = "แบบขยายหน้าตัดคาน (BEAM DETAIL)"
        rebar_spec = f"บน: {item.main_top} | ล่าง: {item.main_bottom} | ปลอก: {item.stirrups}"
        dim_str = f"{item.width:.2f} x {item.depth:.2f} m."
        mat_str = f"คอนกรีต คสล. (Covering {item.covering*100:.0f} cm)"
    elif isinstance(item, ColumnDetailItem):
        sec_svg = render_column_section_svg(item, box_width_mm=75.0, box_height_mm=75.0)
        item_title = "แบบขยายหน้าตัดเสา (COLUMN DETAIL)"
        rebar_spec = f"เหล็กยืน: {item.main_rebar} | เหล็กปลอก: {item.stirrups}"
        dim_str = f"Ø {item.width:.2f} m." if item.section_shape == "CIRCULAR" else f"{item.width:.2f} x {item.depth:.2f} m."
        mat_str = f"คอนกรีต คสล. (Covering {item.covering*100:.0f} cm)"
    else:  # FootingDetailItem
        sec_svg = render_footing_detail_svg(item, box_width_mm=78.0, box_height_mm=75.0)
        item_title = "แบบขยายฐานราก (FOOTING DETAIL)"
        rebar_spec = f"ตะแกรงล่าง: {item.rebar_mat_x} (สองทาง)"
        dim_str = f"{item.width:.2f} x {item.depth:.2f} x {item.thickness:.2f} m."
        p_info = f" | {item.pile_spec}" if item.piles_count > 0 else ""
        mat_str = f"คอนกรีต คสล. + ทรายอัดแน่น 10cm + คอนกรีตหยาบ 5cm{p_info}"

    tbl_x = 80.0
    tbl_w = card_width_mm - tbl_x - 2.0

    inst_str = ", ".join(item.instances[:12]) + ("..." if len(item.instances) > 12 else "")

    svg_lines = [
        f'<g id="card-struct-{item.type_tag}" class="structural-detail-card">',
        f'  <rect x="0" y="0" width="{card_width_mm:.1f}" height="{card_height_mm:.1f}" fill="#ffffff" stroke="#94a3b8" stroke-width="0.5" rx="1.5" />',
        '  <!-- 2D Vector Section Graphics -->',
        f'  <g transform="translate(2.0, 5.0)">',
        f'{sec_svg}',
        '  </g>',
        '  <!-- Specification Table -->',
        f'  <g transform="translate({tbl_x:.1f}, 5.0)">',
        '    <!-- Table Header -->',
        f'    <rect x="0" y="0" width="{tbl_w:.1f}" height="7.0" fill="#0f172a" rx="0.5" />',
        f'    <text x="4.0" y="4.8" font-family="Sarabun, sans-serif" font-size="3.5px" font-weight="bold" fill="#ffffff">{item_title} ({item.type_tag})</text>',
        f'    <text x="{tbl_w - 4.0:.1f}" y="4.8" font-family="Sarabun, sans-serif" font-size="3.2px" font-weight="bold" text-anchor="end" fill="#f8fafc">จำนวน {item.quantity} ชุด (QTY: {item.quantity})</text>',
    ]

    rows = [
        ("รายการ (ITEM):", f"สัญลักษณ์โครงสร้าง {item.type_tag} ({item.category})"),
        ("ขนาดหน้าตัด (DIMENSION):", dim_str),
        ("การเสริมเหล็ก (REINFORCEMENT):", rebar_spec),
        ("สเปกวัสดุ (MATERIAL SPEC):", mat_str),
        ("ตำแหน่งที่ใช้ (LOCATION):", inst_str),
        ("หมายเหตุ (REMARKS):", item.remarks or "Standard Structural RC Detail"),
    ]

    row_y = 11.0
    row_h = 11.2

    for idx, (label, val) in enumerate(rows):
        bg_fill = "#f8fafc" if idx % 2 == 0 else "#ffffff"
        svg_lines.append(f'    <rect x="0" y="{row_y - 3.2:.1f}" width="{tbl_w:.1f}" height="{row_h:.1f}" fill="{bg_fill}" stroke="#e2e8f0" stroke-width="0.3" />')
        svg_lines.append(f'    <text x="3.0" y="{row_y + 3.0:.1f}" font-family="Sarabun, sans-serif" font-size="2.6px" font-weight="bold" fill="#334155">{label}</text>')
        svg_lines.append(f'    <text x="52.0" y="{row_y + 3.0:.1f}" font-family="Sarabun, sans-serif" font-size="2.6px" fill="#0f172a">{val}</text>')
        row_y += row_h

    svg_lines.append('  </g>')
    svg_lines.append('</g>')
    return "\n".join(svg_lines)


def render_structural_details_schedule_svg(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
    sheet_config: Optional[Any] = None,
) -> str:
    """
    Render complete Structural RC Detail Schedule drawing sheet (แบบขยายโครงสร้าง คสล. - S-201).
    Fits beam cross-sections, column sections, and footing details onto standard A3 Paper Space drawing sheet.
    """
    from debim.draw.renderer import SheetConfig, SheetRenderer

    if isinstance(manifest_or_resolved, ProjectManifest):
        resolved = SpatialResolver(manifest_or_resolved).resolve()
    else:
        resolved = manifest_or_resolved

    beams, columns, footings = extract_structural_details(resolved)
    all_items: List[StructuralDetailItem] = list(beams) + list(columns) + list(footings)

    if sheet_config is None:
        cfg = SheetConfig(
            id="S-201",
            title="Structural RC Beam Column Footing Details",
            view_type="STRUCTURAL_DETAILS",
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
        '  <!-- Drawing Viewport for Structural Details -->',
        f'  <g id="structural-schedule-viewport" transform="translate({printable_x:.1f}, {printable_y:.1f})">',
        '    <!-- Drawing Sheet Header -->',
        '    <text x="5.0" y="10.0" font-family="Sarabun, sans-serif" font-size="5.5px" font-weight="bold" fill="#0f172a">แบบขยายโครงสร้าง คสล. คาน เสา และฐานราก (STRUCTURAL RC BEAM, COLUMN &amp; FOOTING DETAILS)</text>',
        '    <line x1="5.0" y1="12.5" x2="320.0" y2="12.5" stroke="#0f172a" stroke-width="0.8" />',
    ]

    start_x = gap_x
    start_y = 16.0

    for idx, item in enumerate(all_items):
        c_idx = idx % cols
        r_idx = idx // cols

        cx = start_x + c_idx * (card_w + gap_x)
        cy = start_y + r_idx * (card_h + gap_y)

        if cy + card_h > printable_h - 5.0:
            break

        card_svg = render_structural_detail_card_svg(item, card_width_mm=card_w, card_height_mm=card_h)
        svg_lines.append(f'    <g transform="translate({cx:.1f}, {cy:.1f})">')
        svg_lines.append(card_svg)
        svg_lines.append('    </g>')

    svg_lines.append('  </g> <!-- End structural-schedule-viewport -->')

    if cfg.visibility.show_title_block:
        proj_name = cfg.project_name or resolved.manifest.project.name
        date_str = cfg.date or "2025-01-01"
        svg_lines.append(renderer._render_title_block_svg(title_x, printable_y, tb_width, printable_h, proj_name, date_str))

    svg_lines.append('</svg>')
    return "\n".join(svg_lines)
