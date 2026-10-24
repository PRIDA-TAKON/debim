"""
2D Multi-Discipline CAD Exporter for debim.
Slices 3D BIM models at 1.20m plan cut elevation and vertical section cut planes,
generating clean 2D DXF and SVG drawings for Architectural Floor Plans, Building Sections,
and MEP Layouts with auto-dimensioning, wall hatches, room area labels, and pipe annotation tags.
"""

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import ezdxf
from ezdxf.document import Drawing
from shapely.geometry import LineString, Polygon

from debim.draw.projection import CutPlaneResult, slice_storey
from debim.draw.section import SectionCutPlaneResult, slice_section
from debim.geometry2d import shoelace_area
from debim.resolver import ResolvedManifest, resolve_manifest
from debim.schema import ProjectManifest, load_manifest


class PlanCutGenerator:
    """Slices building model at 1.20m above each storey elevation."""

    def __init__(
        self,
        manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
        cut_offset_z: float = 1.20,
    ):
        if isinstance(manifest_or_resolved, (str, Path)):
            manifest_obj = load_manifest(Path(manifest_or_resolved))
            self.resolved = resolve_manifest(manifest_obj)
        elif isinstance(manifest_or_resolved, ProjectManifest):
            self.resolved = resolve_manifest(manifest_or_resolved)
        else:
            self.resolved = manifest_or_resolved

        self.cut_offset_z = cut_offset_z

    def slice_storey_plan(self, storey_id: Optional[str] = None) -> CutPlaneResult:
        """Slice specified storey (or first storey if None) at 1.20m cut elevation."""
        if storey_id is None:
            storeys = self.resolved.manifest.spatial_structure.storeys
            if not storeys:
                raise ValueError("No storeys defined in project spatial structure.")
            storey_id = storeys[0].id

        return slice_storey(
            self.resolved, storey_id=storey_id, cut_offset_z=self.cut_offset_z
        )


def _setup_dxf_layers_and_styles(doc: Drawing) -> None:
    """Define standard CAD layers, linetypes, colors, and text styles."""
    if "CENTER" not in doc.linetypes:
        doc.linetypes.new(
            "CENTER",
            dxfattribs={
                "description": "Center ---- _ ---- _ ----",
                "pattern": [1.25, 0.75, -0.25, 0.25, -0.25],
            },
        )
    if "DASHED" not in doc.linetypes:
        doc.linetypes.new(
            "DASHED",
            dxfattribs={"description": "Dashed -- -- -- --", "pattern": [0.75, 0.5, -0.25]},
        )

    styles = doc.styles
    if "THAI" not in styles:
        styles.add("THAI", font="Cordia New")
    if "TH_SARABUN" not in styles:
        styles.add("TH_SARABUN", font="THSarabunNew.ttf")

    # Layer definitions: (Layer Name, Color Code, Linetype, Lineweight)
    layers_def = [
        ("A-WALL", 7, "Continuous", 50),
        ("A-WALL-HATCH", 8, "Continuous", 13),
        ("S-COLS", 3, "Continuous", 50),
        ("S-BEAM", 4, "DASHED", 25),
        ("A-DOOR", 2, "Continuous", 25),
        ("A-GLAZ", 4, "Continuous", 25),
        ("A-ROOM-LABEL", 1, "Continuous", 20),
        ("DIM-ANNO", 5, "Continuous", 18),
        ("GRID-ANNO", 1, "CENTER", 18),
        ("A-FLOR", 8, "Continuous", 18),
        ("A-SANR", 6, "Continuous", 25),
        ("M-PIPE", 1, "Continuous", 35),
        ("M-ANNO", 2, "Continuous", 20),
    ]

    for name, color, linetype, lineweight in layers_def:
        if name not in doc.layers:
            doc.layers.add(name, color=color, linetype=linetype, lineweight=lineweight)


def export_cad_dxf(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    output_path: Union[str, Path],
    storey_id: Optional[str] = None,
    cut_offset_z: float = 1.20,
    drawing_type: str = "all",
    units: str = "mm",
) -> Path:
    """
    Export 2D multi-discipline CAD drawing (DXF format) with wall hatches, door swings,
    window openings, room labels with m2 area, auto-dimensioning, building sections, and MEP layouts.
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    cut_gen = PlanCutGenerator(manifest_or_resolved, cut_offset_z=cut_offset_z)
    resolved = cut_gen.resolved
    cut_plane = cut_gen.slice_storey_plan(storey_id=storey_id)

    is_mm = units.lower() in ("mm", "millimeter", "millimeters")
    scale = 1000.0 if is_mm else 1.0

    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4 if is_mm else 6
    doc.header["$MEASUREMENT"] = 1

    _setup_dxf_layers_and_styles(doc)
    msp = doc.modelspace()

    # 1. Architectural Floor Plan: Cut Walls & Wall Hatching
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcWall":
            for ring in elem.polygon_coords:
                if len(ring) < 2:
                    continue
                scaled_pts = [(x * scale, y * scale) for x, y in ring]
                msp.add_lwpolyline(
                    scaled_pts, close=True, dxfattribs={"layer": "A-WALL"}
                )
                try:
                    hatch = msp.add_hatch(color=256, dxfattribs={"layer": "A-WALL-HATCH"})
                    hatch.set_pattern_fill("ANSI31", scale=0.5 if is_mm else 0.0005)
                    hatch.paths.add_polyline_path(scaled_pts, is_closed=True)
                except Exception:
                    pass

    # 2. Architectural Floor Plan: Columns
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcColumn":
            for ring in elem.polygon_coords:
                if len(ring) < 2:
                    continue
                scaled_pts = [(x * scale, y * scale) for x, y in ring]
                msp.add_lwpolyline(
                    scaled_pts, close=True, dxfattribs={"layer": "S-COLS"}
                )

    # 3. Structural Beams
    processed_beams = set()
    for elem in list(cut_plane.cut_elements) + list(cut_plane.projection_elements):
        if elem.element_class == "IfcBeam" and elem.tag not in processed_beams:
            processed_beams.add(elem.tag)
            for ring in elem.polygon_coords:
                if len(ring) < 2:
                    continue
                scaled_pts = [(x * scale, y * scale) for x, y in ring]
                msp.add_lwpolyline(
                    scaled_pts, close=True, dxfattribs={"layer": "S-BEAM", "linetype": "DASHED"}
                )

    # 4. Doors: Frame, Leaf Line & 90-degree Swing Arc
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcDoor":
            coords = elem.polygon_coords[0] if elem.polygon_coords else []
            if len(coords) >= 4:
                p0, p1, p2, p3 = coords[0], coords[1], coords[2], coords[3]
                p0_s = (p0[0] * scale, p0[1] * scale)
                p1_s = (p1[0] * scale, p1[1] * scale)
                p2_s = (p2[0] * scale, p2[1] * scale)
                p3_s = (p3[0] * scale, p3[1] * scale)

                msp.add_lwpolyline([p0_s, p1_s, p2_s, p3_s], close=True, dxfattribs={"layer": "A-DOOR"})

                h_x = (p0[0] + p3[0]) / 2.0 * scale
                h_y = (p0[1] + p3[1]) / 2.0 * scale
                l_x = (p1[0] + p2[0]) / 2.0 * scale
                l_y = (p1[1] + p2[1]) / 2.0 * scale

                dx = l_x - h_x
                dy = l_y - h_y
                door_w = math.hypot(dx, dy)
                if door_w > 1e-4:
                    wall_ang = math.atan2(dy, dx)
                    # Leaf line open 90 degrees
                    leaf_end_x = h_x - door_w * math.sin(wall_ang)
                    leaf_end_y = h_y + door_w * math.cos(wall_ang)
                    msp.add_line((h_x, h_y), (leaf_end_x, leaf_end_y), dxfattribs={"layer": "A-DOOR"})

                    start_deg = math.degrees(wall_ang)
                    end_deg = start_deg + 90.0
                    msp.add_arc(
                        center=(h_x, h_y),
                        radius=door_w,
                        start_angle=start_deg,
                        end_angle=end_deg,
                        dxfattribs={"layer": "A-DOOR"},
                    )

    # 5. Windows: Frame, Central Glazing Line & Mullions
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcWindow":
            coords = elem.polygon_coords[0] if elem.polygon_coords else []
            if len(coords) >= 4:
                p0, p1, p2, p3 = coords[0], coords[1], coords[2], coords[3]
                p0_s = (p0[0] * scale, p0[1] * scale)
                p1_s = (p1[0] * scale, p1[1] * scale)
                p2_s = (p2[0] * scale, p2[1] * scale)
                p3_s = (p3[0] * scale, p3[1] * scale)

                msp.add_lwpolyline([p0_s, p1_s, p2_s, p3_s], close=True, dxfattribs={"layer": "A-GLAZ"})

                m01 = ((p0_s[0] + p3_s[0]) / 2.0, (p0_s[1] + p3_s[1]) / 2.0)
                m12 = ((p1_s[0] + p2_s[0]) / 2.0, (p1_s[1] + p2_s[1]) / 2.0)
                msp.add_line(m01, m12, dxfattribs={"layer": "A-GLAZ"})

                # Center mullion line
                m_center0 = ((p0_s[0] + p1_s[0]) / 2.0, (p0_s[1] + p1_s[1]) / 2.0)
                m_center1 = ((p3_s[0] + p2_s[0]) / 2.0, (p3_s[1] + p2_s[1]) / 2.0)
                msp.add_line(m_center0, m_center1, dxfattribs={"layer": "A-GLAZ"})

    # 6. Room Labels with m2 Area
    for space in getattr(resolved, "spaces", []) or []:
        s_pts_2d = [(p[0], p[1]) for p in space.polygon] if space.polygon else []
        if len(s_pts_2d) >= 3:
            s_area = getattr(space, "net_floor_area", 0.0) or shoelace_area(s_pts_2d)
            cx = sum(p[0] for p in s_pts_2d) / len(s_pts_2d) * scale
            cy = sum(p[1] for p in s_pts_2d) / len(s_pts_2d) * scale

            r_name = (space.name or space.tag or "ROOM").upper()
            txt_height = 250.0 if is_mm else 0.25

            msp.add_text(
                r_name,
                dxfattribs={
                    "layer": "A-ROOM-LABEL",
                    "style": "TH_SARABUN",
                    "height": txt_height,
                },
            ).set_placement((cx, cy + txt_height * 0.6), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

            msp.add_text(
                f"{s_area:.2f} m²",
                dxfattribs={
                    "layer": "A-ROOM-LABEL",
                    "style": "TH_SARABUN",
                    "height": txt_height * 0.85,
                },
            ).set_placement((cx, cy - txt_height * 0.6), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    # 7. Grid Axes & Multi-Tier Auto-Dimensioning
    grid_x = sorted([g for g in cut_plane.grid_lines if g.axis == "X"], key=lambda g: g.position)
    grid_y = sorted([g for g in cut_plane.grid_lines if g.axis == "Y"], key=lambda g: g.position)

    for g in cut_plane.grid_lines:
        sx, sy = g.start[0] * scale, g.start[1] * scale
        ex, ey = g.end[0] * scale, g.end[1] * scale
        msp.add_line((sx, sy), (ex, ey), dxfattribs={"layer": "GRID-ANNO", "linetype": "CENTER"})

        bubble_r = 400.0 if is_mm else 0.40
        txt_h = 250.0 if is_mm else 0.25
        msp.add_circle((sx, sy), radius=bubble_r, dxfattribs={"layer": "GRID-ANNO"})
        msp.add_circle((ex, ey), radius=bubble_r, dxfattribs={"layer": "GRID-ANNO"})
        msp.add_text(
            g.id,
            dxfattribs={"layer": "GRID-ANNO", "style": "TH_SARABUN", "height": txt_h},
        ).set_placement((sx, sy), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
        msp.add_text(
            g.id,
            dxfattribs={"layer": "GRID-ANNO", "style": "TH_SARABUN", "height": txt_h},
        ).set_placement((ex, ey), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    bx0, by0, bx1, by1 = cut_plane.bounds
    min_x, max_x = bx0 * scale, bx1 * scale
    min_y, max_y = by0 * scale, by1 * scale

    dim_offset = 1200.0 if is_mm else 1.20
    tick_size = 150.0 if is_mm else 0.15
    dim_text_h = 200.0 if is_mm else 0.20

    # Tier 1 & 2 X Dimensions
    if len(grid_x) >= 2:
        dim_y = max_y + dim_offset
        for i in range(len(grid_x) - 1):
            x1 = grid_x[i].position * scale
            x2 = grid_x[i + 1].position * scale
            dist = abs(x2 - x1)
            msp.add_line((x1, dim_y), (x2, dim_y), dxfattribs={"layer": "DIM-ANNO"})
            msp.add_line(
                (x1 - tick_size, dim_y - tick_size),
                (x1 + tick_size, dim_y + tick_size),
                dxfattribs={"layer": "DIM-ANNO"},
            )
            msp.add_line(
                (x2 - tick_size, dim_y - tick_size),
                (x2 + tick_size, dim_y + tick_size),
                dxfattribs={"layer": "DIM-ANNO"},
            )
            val_str = f"{dist:.0f}" if is_mm else f"{dist / scale:.2f}"
            msp.add_text(
                val_str,
                dxfattribs={"layer": "DIM-ANNO", "style": "TH_SARABUN", "height": dim_text_h},
            ).set_placement(
                ((x1 + x2) / 2.0, dim_y + dim_text_h * 0.5),
                align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER,
            )

    # Tier 1 & 2 Y Dimensions
    if len(grid_y) >= 2:
        dim_x = min_x - dim_offset
        for i in range(len(grid_y) - 1):
            y1 = grid_y[i].position * scale
            y2 = grid_y[i + 1].position * scale
            dist = abs(y2 - y1)
            msp.add_line((dim_x, y1), (dim_x, y2), dxfattribs={"layer": "DIM-ANNO"})
            msp.add_line(
                (dim_x - tick_size, y1 - tick_size),
                (dim_x + tick_size, y1 + tick_size),
                dxfattribs={"layer": "DIM-ANNO"},
            )
            msp.add_line(
                (dim_x - tick_size, y2 - tick_size),
                (dim_x + tick_size, y2 + tick_size),
                dxfattribs={"layer": "DIM-ANNO"},
            )
            val_str = f"{dist:.0f}" if is_mm else f"{dist / scale:.2f}"
            msp.add_text(
                val_str,
                dxfattribs={
                    "layer": "DIM-ANNO",
                    "style": "TH_SARABUN",
                    "height": dim_text_h,
                    "rotation": 90.0,
                },
            ).set_placement(
                (dim_x - dim_text_h * 0.5, (y1 + y2) / 2.0),
                align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER,
            )

    # 8. MEP Layouts: Single-Line Pipes, Rise/Drop Symbols & Annotation Tags
    for pipe in getattr(resolved, "pipes", []) or []:
        p_start = pipe.start_point
        p_end = pipe.end_point

        sx, sy, sz = p_start[0] * scale, p_start[1] * scale, p_start[2]
        ex, ey, ez = p_end[0] * scale, p_end[1] * scale, p_end[2]

        is_riser = math.hypot(ex - sx, ey - sy) < 1e-3 and abs(ez - sz) > 1e-3
        if is_riser:
            # Render Rise/Drop symbol (circle with dot or cross)
            r_radius = 150.0 if is_mm else 0.15
            msp.add_circle((sx, sy), radius=r_radius, dxfattribs={"layer": "M-PIPE"})
            if ez > sz:
                # Rise going up: dot
                msp.add_circle((sx, sy), radius=r_radius * 0.25, dxfattribs={"layer": "M-PIPE"})
            else:
                # Drop going down: cross
                msp.add_line((sx - r_radius, sy - r_radius), (sx + r_radius, sy + r_radius), dxfattribs={"layer": "M-PIPE"})
                msp.add_line((sx - r_radius, sy + r_radius), (sx + r_radius, sy - r_radius), dxfattribs={"layer": "M-PIPE"})
        else:
            msp.add_line((sx, sy), (ex, ey), dxfattribs={"layer": "M-PIPE"})

        # Pipe annotation tag
        mat = getattr(pipe, "material", None) or getattr(getattr(pipe, "element", None), "material", "PVC") or "PVC"
        dia_mm = int(pipe.nominal_diameter * 1000.0) if pipe.nominal_diameter > 0 else 100
        slope_val = getattr(pipe, "slope", 0.0) or 0.02
        slope_str = f" SLOPE 1:{int(round(1.0 / slope_val))}" if slope_val > 0 else ""
        tag_text = f"{mat} Ø{dia_mm}{slope_str}"

        mid_x = (sx + ex) / 2.0
        mid_y = (sy + ey) / 2.0
        msp.add_text(
            tag_text,
            dxfattribs={"layer": "M-ANNO", "style": "TH_SARABUN", "height": 180.0 if is_mm else 0.18},
        ).set_placement((mid_x, mid_y + (100.0 if is_mm else 0.10)), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)

    # 9. Building Sections (if drawing_type in ("section", "all"))
    if drawing_type in ("section", "all"):
        try:
            sec_res: SectionCutPlaneResult = slice_section(resolved, section_id="A-A", plane_axis="Y")
            sec_offset_y = (max_y - min_y) + 8000.0 if is_mm else 8.0

            for sec_elem in sec_res.cut_elements:
                for ring in sec_elem.polygon_coords:
                    if len(ring) < 2:
                        continue
                    scaled_sec_pts = [(u * scale, (z * scale) + sec_offset_y) for u, z in ring]
                    sec_layer = "S-COLS" if sec_elem.element_class in ("IfcColumn", "IfcBeam", "IfcFooting") else "A-WALL"
                    msp.add_lwpolyline(scaled_sec_pts, close=True, dxfattribs={"layer": sec_layer})

            for lvl in sec_res.level_markers:
                lz = (lvl.elevation * scale) + sec_offset_y
                msp.add_line((min_x - (2000.0 if is_mm else 2.0), lz), (max_x + (2000.0 if is_mm else 2.0), lz), dxfattribs={"layer": "DIM-ANNO", "linetype": "DASHED"})
                msp.add_text(
                    lvl.display_text,
                    dxfattribs={"layer": "DIM-ANNO", "style": "TH_SARABUN", "height": 220.0 if is_mm else 0.22},
                ).set_placement((max_x + (2200.0 if is_mm else 2.20), lz), align=ezdxf.enums.TextEntityAlignment.MIDDLE_LEFT)
        except Exception:
            pass

    doc.saveas(output_file)
    return output_file.resolve()


def export_cad_svg(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    output_path: Union[str, Path],
    storey_id: Optional[str] = None,
    cut_offset_z: float = 1.20,
    drawing_type: str = "all",
) -> Path:
    """
    Export 2D multi-discipline vector drawing in SVG format.
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    cut_gen = PlanCutGenerator(manifest_or_resolved, cut_offset_z=cut_offset_z)
    resolved = cut_gen.resolved
    cut_plane = cut_gen.slice_storey_plan(storey_id=storey_id)

    bx0, by0, bx1, by1 = cut_plane.bounds
    margin = 2.0
    vb_min_x, vb_max_x = bx0 - margin, bx1 + margin
    vb_min_y, vb_max_y = by0 - margin, by1 + margin
    vb_w = vb_max_x - vb_min_x
    vb_h = vb_max_y - vb_min_y

    svg_lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb_min_x:.2f} {-vb_max_y:.2f} {vb_w:.2f} {vb_h:.2f}" width="100%" height="100%">',
        '  <style>',
        '    .wall { fill: #cbd5e1; stroke: #0f172a; stroke-width: 0.05; }',
        '    .column { fill: #0284c7; stroke: #0369a1; stroke-width: 0.05; }',
        '    .door { fill: none; stroke: #d97706; stroke-width: 0.03; }',
        '    .window { fill: #e0f2fe; stroke: #0284c7; stroke-width: 0.03; }',
        '    .pipe { fill: none; stroke: #dc2626; stroke-width: 0.04; }',
        '    .room-label { font-family: sans-serif; font-size: 0.25px; fill: #1e293b; text-anchor: middle; }',
        '    .pipe-tag { font-family: sans-serif; font-size: 0.18px; fill: #b91c1c; text-anchor: middle; }',
        '    .grid-line { stroke: #94a3b8; stroke-width: 0.02; stroke-dasharray: 0.2,0.1; }',
        '    .dimension { stroke: #2563eb; stroke-width: 0.02; }',
        '  </style>',
    ]

    # Grid Lines
    for g in cut_plane.grid_lines:
        sx, sy = g.start
        ex, ey = g.end
        svg_lines.append(
            f'  <line x1="{sx:.2f}" y1="{-sy:.2f}" x2="{ex:.2f}" y2="{-ey:.2f}" class="grid-line" />'
        )

    # Cut Walls
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcWall":
            for ring in elem.polygon_coords:
                if len(ring) < 2:
                    continue
                pts_str = " ".join(f"{x:.2f},{-y:.2f}" for x, y in ring)
                svg_lines.append(f'  <polygon points="{pts_str}" class="wall" />')

    # Columns
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcColumn":
            for ring in elem.polygon_coords:
                if len(ring) < 2:
                    continue
                pts_str = " ".join(f"{x:.2f},{-y:.2f}" for x, y in ring)
                svg_lines.append(f'  <polygon points="{pts_str}" class="column" />')

    # Doors & Windows
    for elem in cut_plane.cut_elements:
        if elem.element_class in ("IfcDoor", "IfcWindow"):
            cls_name = "door" if elem.element_class == "IfcDoor" else "window"
            for ring in elem.polygon_coords:
                if len(ring) < 2:
                    continue
                pts_str = " ".join(f"{x:.2f},{-y:.2f}" for x, y in ring)
                svg_lines.append(f'  <polygon points="{pts_str}" class="{cls_name}" />')

    # Room Labels
    for space in getattr(resolved, "spaces", []) or []:
        s_pts_2d = [(p[0], p[1]) for p in space.polygon] if space.polygon else []
        if len(s_pts_2d) >= 3:
            s_area = getattr(space, "net_floor_area", 0.0) or shoelace_area(s_pts_2d)
            cx = sum(p[0] for p in s_pts_2d) / len(s_pts_2d)
            cy = sum(p[1] for p in s_pts_2d) / len(s_pts_2d)
            r_name = space.name or space.tag or "ROOM"
            svg_lines.append(
                f'  <text x="{cx:.2f}" y="{-cy:.2f}" class="room-label">{r_name} ({s_area:.2f} m²)</text>'
            )

    # Pipes & Annotations
    for pipe in getattr(resolved, "pipes", []) or ():
        sx, sy = pipe.start_point[0], pipe.start_point[1]
        ex, ey = pipe.end_point[0], pipe.end_point[1]
        svg_lines.append(
            f'  <line x1="{sx:.2f}" y1="{-sy:.2f}" x2="{ex:.2f}" y2="{-ey:.2f}" class="pipe" />'
        )

        mat = getattr(pipe, "material", None) or getattr(getattr(pipe, "element", None), "material", "PVC") or "PVC"
        dia_mm = int(pipe.nominal_diameter * 1000.0) if pipe.nominal_diameter > 0 else 100
        slope_val = getattr(pipe, "slope", 0.0) or 0.02
        slope_str = f" SLOPE 1:{int(round(1.0 / slope_val))}" if slope_val > 0 else ""
        tag_text = f"{mat} Ø{dia_mm}{slope_str}"

        mx, my = (sx + ex) / 2.0, (sy + ey) / 2.0
        svg_lines.append(
            f'  <text x="{mx:.2f}" y="{-my - 0.1:.2f}" class="pipe-tag">{tag_text}</text>'
        )

    svg_lines.append("</svg>")
    output_file.write_text("\n".join(svg_lines), encoding="utf-8")
    return output_file.resolve()
