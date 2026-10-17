"""
2D AutoCAD DXF Exporter using ezdxf for debim.
Exports 2D projected architectural blueprints to industry-standard CAD layers.
"""

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import ezdxf
from ezdxf.document import Drawing

from debim.draw.projection import (
    CutElement,
    CutPlaneResult,
    GridLine2D,
    ProjectionElement,
    slice_storey,
)
from debim.resolver import ResolvedManifest, resolve_manifest
from debim.schema import ProjectManifest, load_manifest


def _setup_dxf_layers_and_styles(doc: Drawing) -> None:
    """Define standard CAD layers, colors, linetypes, and Thai text styles."""
    # Ensure standard metric units and linetypes are available
    if "CENTER" not in doc.linetypes:
        doc.linetypes.new("CENTER", dxfattribs={"description": "Center ---- _ ---- _ ----", "pattern": [1.25, 0.75, -0.25, 0.25, -0.25]})
    if "DASHED" not in doc.linetypes:
        doc.linetypes.new("DASHED", dxfattribs={"description": "Dashed -- -- -- --", "pattern": [0.75, 0.5, -0.25]})

    # Add Thai text styles
    styles = doc.styles
    if "THAI" not in styles:
        styles.add("THAI", font="Cordia New")
    if "TH_SARABUN" not in styles:
        styles.add("TH_SARABUN", font="THSarabunNew.ttf")

    # Layer Hierarchy Definitions (Layer Name, Color Code, Linetype, Lineweight in 100ths mm)
    # ACI Colors: 1=Red, 2=Yellow, 3=Green, 4=Cyan, 5=Blue, 6=Magenta, 7=White/Black, 8=Dark Gray
    layers_def = [
        ("A-WALL", 7, "Continuous", 50),     # Wall cut lines (0.50mm)
        ("S-COLS", 3, "Continuous", 50),     # Column profiles (0.50mm Green)
        ("S-BEAM", 4, "DASHED", 25),         # Structural beam framing (0.25mm Cyan)
        ("A-DOOR", 2, "Continuous", 25),     # Door frames, leaf & swing arc (0.25mm Yellow)
        ("A-GLAZ", 4, "Continuous", 25),     # Window frames & glazing (0.25mm Cyan)
        ("A-WIND", 4, "Continuous", 25),     # Window frames & glazing (legacy alias)
        ("DIM-ANNO", 5, "Continuous", 18),   # Dimensions & numeric text (0.18mm Blue)
        ("A-DIMS", 5, "Continuous", 18),     # Dimensions & numeric text (legacy alias)
        ("GRID-ANNO", 1, "CENTER", 18),      # Grid centerlines & bubbles (0.18mm Red, CENTER)
        ("A-GRID", 1, "CENTER", 18),         # Grid centerlines (legacy alias)
        ("A-FLOR", 8, "Continuous", 18),     # Floor slabs & steps (0.18mm Gray)
        ("A-SANR", 6, "Continuous", 25),     # Sanitary fixtures (0.25mm Magenta)
    ]

    for name, color, linetype, lineweight in layers_def:
        if name not in doc.layers:
            doc.layers.add(name, color=color, linetype=linetype, lineweight=lineweight)


def _setup_reusable_dxf_blocks(doc: Drawing, is_mm: bool) -> None:
    """Define reusable 2D CAD blocks for doors (D1, D2), windows (W1, W2), columns (C1), sanitary, and grid bubbles."""
    blocks = doc.blocks

    # 1. Door D1 (Single Leaf Door)
    if "D1" not in blocks:
        d1 = blocks.new("D1")
        # Jambs at hinge (0, 0) and lock end (1.0, 0)
        d1.add_lwpolyline([(0, -0.05), (0.05, -0.05), (0.05, 0.05), (0, 0.05)], close=True, dxfattribs={"layer": "A-DOOR"})
        d1.add_lwpolyline([(0.95, -0.05), (1.0, -0.05), (1.0, 0.05), (0.95, 0.05)], close=True, dxfattribs={"layer": "A-DOOR"})
        # Open door leaf line from hinge (0, 0) to (0, 1.0)
        d1.add_line((0.0, 0.0), (0.0, 1.0), dxfattribs={"layer": "A-DOOR"})
        # 90-degree swing arc from 0 to 90 deg
        d1.add_arc(center=(0.0, 0.0), radius=1.0, start_angle=0.0, end_angle=90.0, dxfattribs={"layer": "A-DOOR"})

    # 2. Door D2 (Double Leaf Door)
    if "D2" not in blocks:
        d2 = blocks.new("D2")
        # Jambs at outer ends
        d2.add_lwpolyline([(0, -0.05), (0.05, -0.05), (0.05, 0.05), (0, 0.05)], close=True, dxfattribs={"layer": "A-DOOR"})
        d2.add_lwpolyline([(0.95, -0.05), (1.0, -0.05), (1.0, 0.05), (0.95, 0.05)], close=True, dxfattribs={"layer": "A-DOOR"})
        # Left leaf line & arc
        d2.add_line((0.0, 0.0), (0.0, 0.5), dxfattribs={"layer": "A-DOOR"})
        d2.add_arc(center=(0.0, 0.0), radius=0.5, start_angle=0.0, end_angle=90.0, dxfattribs={"layer": "A-DOOR"})
        # Right leaf line & arc
        d2.add_line((1.0, 0.0), (1.0, 0.5), dxfattribs={"layer": "A-DOOR"})
        d2.add_arc(center=(1.0, 0.0), radius=0.5, start_angle=180.0, end_angle=90.0, dxfattribs={"layer": "A-DOOR"})

    # 3. Window W1 (Single Window)
    if "W1" not in blocks:
        w1 = blocks.new("W1")
        # Outer frame box
        w1.add_lwpolyline([(0, -0.5), (1.0, -0.5), (1.0, 0.5), (0, 0.5)], close=True, dxfattribs={"layer": "A-GLAZ"})
        # Central glazing line
        w1.add_line((0, 0), (1.0, 0), dxfattribs={"layer": "A-GLAZ"})

    # 4. Window W2 (Double / Mullion Window)
    if "W2" not in blocks:
        w2 = blocks.new("W2")
        # Outer frame box
        w2.add_lwpolyline([(0, -0.5), (1.0, -0.5), (1.0, 0.5), (0, 0.5)], close=True, dxfattribs={"layer": "A-GLAZ"})
        # Central glazing line
        w2.add_line((0, 0), (1.0, 0), dxfattribs={"layer": "A-GLAZ"})
        # Central mullion divider
        w2.add_line((0.5, -0.5), (0.5, 0.5), dxfattribs={"layer": "A-GLAZ"})

    # 5. Column C1 (Box Column Section)
    if "C1" not in blocks:
        c1 = blocks.new("C1")
        pts = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
        c1.add_lwpolyline(pts, close=True, dxfattribs={"layer": "S-COLS"})
        try:
            hatch = c1.add_hatch(color=256, dxfattribs={"layer": "S-COLS"})
            hatch.set_pattern_fill("SOLID")
            hatch.paths.add_polyline_path(pts, is_closed=True)
        except Exception:
            pass

    # 6. Sanitary WC Fixture
    if "SANR_WC" not in blocks:
        wc = blocks.new("SANR_WC")
        wc.add_lwpolyline([(-0.25, 0.10), (0.25, 0.10), (0.25, 0.35), (-0.25, 0.35)], close=True, dxfattribs={"layer": "A-SANR"})
        wc.add_circle((0.0, -0.10), radius=0.22, dxfattribs={"layer": "A-SANR"})

    # 7. Sanitary Basin Fixture
    if "SANR_BASIN" not in blocks:
        bs = blocks.new("SANR_BASIN")
        bs.add_lwpolyline([(-0.30, -0.25), (0.30, -0.25), (0.30, 0.25), (-0.30, 0.25)], close=True, dxfattribs={"layer": "A-SANR"})
        bs.add_circle((0.0, 0.0), radius=0.18, dxfattribs={"layer": "A-SANR"})

    # 8. Generic Sanitary Fixture
    if "SANR_FIXTURE" not in blocks:
        sf = blocks.new("SANR_FIXTURE")
        sf.add_lwpolyline([(-0.25, -0.25), (0.25, -0.25), (0.25, 0.25), (-0.25, 0.25)], close=True, dxfattribs={"layer": "A-SANR"})

    # 9. Grid Axis Bubble Block
    if "GRID_BUBBLE" not in blocks:
        gb = blocks.new("GRID_BUBBLE")
        b_radius = 400.0 if is_mm else 0.40
        t_height = 250.0 if is_mm else 0.25
        gb.add_circle((0, 0), radius=b_radius, dxfattribs={"layer": "GRID-ANNO"})
        gb.add_attdef(
            tag="GRID_ID",
            text="",
            dxfattribs={
                "height": t_height,
                "style": "TH_SARABUN",
                "layer": "GRID-ANNO",
            },
        ).set_placement((0, 0), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)


def export_2d_dxf(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    output_path: Union[str, Path],
    storey_id: Optional[str] = None,
    cut_offset_z: float = 1.20,
    units: str = "mm",
) -> Path:
    """
    Export 2D projected floor plan elements into a deterministic AutoCAD DXF file.

    Parameters:
    -----------
    manifest_or_resolved : ProjectManifest or ResolvedManifest or Path or str
        Input BIM project model.
    output_path : str or Path
        Target filepath for exported .dxf file.
    storey_id : str, optional
        Target storey ID to slice. Defaults to first storey if unspecified.
    cut_offset_z : float, default 1.20
        Elevation offset above storey elevation for cut-plane.
    units : str, default "mm"
        Output length unit ("mm" for millimeters, "m" for meters).

    Returns:
    --------
    Path : Absolute path of created DXF file.
    """
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(manifest_or_resolved, (str, Path)):
        manifest_path = Path(manifest_or_resolved)
        manifest_obj = load_manifest(manifest_path)
        resolved_manifest = resolve_manifest(manifest_obj)
    elif isinstance(manifest_or_resolved, ProjectManifest):
        resolved_manifest = resolve_manifest(manifest_or_resolved)
    else:
        resolved_manifest = manifest_or_resolved

    # Determine target storey if not provided
    if storey_id is None:
        storeys = resolved_manifest.manifest.spatial_structure.storeys
        if not storeys:
            raise ValueError("No storeys found in project manifest.")
        storey_id = storeys[0].id

    # Compute 2D Section Slice
    cut_plane: CutPlaneResult = slice_storey(
        resolved_manifest, storey_id=storey_id, cut_offset_z=cut_offset_z
    )

    # Unit scaling factor (BIM internal coordinates are in meters)
    is_mm = units.lower() in ("mm", "millimeter", "millimeters")
    scale = 1000.0 if is_mm else 1.0

    # Initialize ezdxf document (DXF R2010 format)
    doc = ezdxf.new("R2010", setup=True)

    # Header Settings
    doc.header["$INSUNITS"] = 4 if is_mm else 6  # 4 = Millimeters, 6 = Meters
    doc.header["$MEASUREMENT"] = 1                # 1 = Metric

    _setup_dxf_layers_and_styles(doc)
    _setup_reusable_dxf_blocks(doc, is_mm=is_mm)
    msp = doc.modelspace()

    # 1. Render Walls (`A-WALL`)
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcWall":
            for ring in elem.polygon_coords:
                if len(ring) < 2:
                    continue
                scaled_pts = [(x * scale, y * scale) for x, y in ring]
                msp.add_lwpolyline(scaled_pts, close=True, dxfattribs={"layer": "A-WALL"})

    # 2. Render Columns (`S-COLS`) using Reusable Block C1
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcColumn":
            coords = elem.polygon_coords[0] if elem.polygon_coords else []
            if len(coords) >= 4:
                xs = [p[0] * scale for p in coords]
                ys = [p[1] * scale for p in coords]
                cx = sum(xs) / len(xs)
                cy = sum(ys) / len(ys)
                width_c = max(xs) - min(xs)
                depth_c = max(ys) - min(ys)
                if width_c > 1e-4 and depth_c > 1e-4:
                    msp.add_blockref(
                        "C1",
                        (cx, cy),
                        dxfattribs={
                            "xscale": width_c,
                            "yscale": depth_c,
                            "layer": "S-COLS",
                        },
                    )

    # 2b. Render Structural Beams (`S-BEAM`) - Unique Beams
    processed_beam_tags = set()
    for elem in list(cut_plane.cut_elements) + list(cut_plane.projection_elements):
        if elem.element_class == "IfcBeam" and elem.tag not in processed_beam_tags:
            processed_beam_tags.add(elem.tag)
            for ring in elem.polygon_coords:
                if len(ring) < 2:
                    continue
                scaled_pts = [(x * scale, y * scale) for x, y in ring]
                msp.add_lwpolyline(scaled_pts, close=True, dxfattribs={"layer": "S-BEAM", "linetype": "DASHED"})

    # 3. Render Doors (`A-DOOR`) using Reusable Block (D1/D2)
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcDoor":
            width = elem.properties.get("width", 0.90) * scale
            coords = elem.polygon_coords[0] if elem.polygon_coords else []
            door_blk = "D2" if width > 1.1 * scale or elem.properties.get("is_double", False) else "D1"

            if len(coords) >= 4:
                p0, p1, p2, p3 = coords[0], coords[1], coords[2], coords[3]
                h_x = (p0[0] + p3[0]) / 2.0 * scale
                h_y = (p0[1] + p3[1]) / 2.0 * scale
                l_x = (p1[0] + p2[0]) / 2.0 * scale
                l_y = (p1[1] + p2[1]) / 2.0 * scale

                dx = l_x - h_x
                dy = l_y - h_y
                door_len = math.hypot(dx, dy)
                if door_len > 1e-4:
                    base_angle_rad = math.atan2(dy, dx)
                    base_angle_deg = math.degrees(base_angle_rad)

                    # Insert Reusable Door Block (D1 or D2)
                    msp.add_blockref(
                        door_blk,
                        (h_x, h_y),
                        dxfattribs={
                            "rotation": base_angle_deg,
                            "xscale": door_len,
                            "yscale": door_len,
                            "layer": "A-DOOR",
                        },
                    )

    # 4. Render Windows (`A-GLAZ` / `A-WIND`) using Reusable Block (W1/W2)
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcWindow":
            width = elem.properties.get("width", 1.20) * scale
            f_thick = elem.properties.get("frame_thickness", 0.10) * scale
            wind_blk = "W2" if width > 1.2 * scale else "W1"

            coords = elem.polygon_coords[0] if elem.polygon_coords else []
            if len(coords) >= 4:
                p0, p1, p2, p3 = coords[0], coords[1], coords[2], coords[3]
                mid_start = ((p0[0] + p3[0]) / 2.0 * scale, (p0[1] + p3[1]) / 2.0 * scale)
                mid_end = ((p1[0] + p2[0]) / 2.0 * scale, (p1[1] + p2[1]) / 2.0 * scale)
                dx = mid_end[0] - mid_start[0]
                dy = mid_end[1] - mid_start[1]
                w_len = math.hypot(dx, dy)
                if w_len > 1e-4:
                    wall_angle_deg = math.degrees(math.atan2(dy, dx))
                    # Insert Reusable Window Block W1 / W2
                    msp.add_blockref(
                        wind_blk,
                        mid_start,
                        dxfattribs={
                            "rotation": wall_angle_deg,
                            "xscale": w_len,
                            "yscale": f_thick,
                            "layer": "A-GLAZ",
                        },
                    )

    # 5. Render Floor Slabs (`A-FLOR`) and Sanitary Fixtures (`A-SANR`) with Blocks
    for elem in cut_plane.projection_elements:
        is_terminal = "Terminal" in elem.element_class
        if is_terminal:
            coords = elem.polygon_coords[0] if elem.polygon_coords else []
            if coords:
                xs = [p[0] * scale for p in coords]
                ys = [p[1] * scale for p in coords]
                cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)

                tag_u = elem.tag.upper()
                term_u = str(elem.properties.get("terminal_type", "")).upper()
                if "WC" in tag_u or "TOILET" in tag_u or "WC" in term_u:
                    sanr_blk = "SANR_WC"
                elif "BASIN" in tag_u or "SINK" in tag_u or "BASIN" in term_u:
                    sanr_blk = "SANR_BASIN"
                else:
                    sanr_blk = "SANR_FIXTURE"

                msp.add_blockref(
                    sanr_blk,
                    (cx, cy),
                    dxfattribs={
                        "xscale": scale,
                        "yscale": scale,
                        "layer": "A-SANR",
                    },
                )
        else:
            for ring in elem.polygon_coords:
                if len(ring) < 2:
                    continue
                scaled_pts = [(x * scale, y * scale) for x, y in ring]
                msp.add_lwpolyline(scaled_pts, close=True, dxfattribs={"layer": "A-FLOR"})

    # 6. Render Grid Lines & Axis Bubbles (`GRID-ANNO` and `A-GRID`) using GRID_BUBBLE Block
    bubble_radius = 400.0 if is_mm else 0.40

    for g in cut_plane.grid_lines:
        sx, sy = g.start[0] * scale, g.start[1] * scale
        ex, ey = g.end[0] * scale, g.end[1] * scale

        # Grid line centerlines
        msp.add_line((sx, sy), (ex, ey), dxfattribs={"layer": "GRID-ANNO", "linetype": "CENTER"})
        msp.add_line((sx, sy), (ex, ey), dxfattribs={"layer": "A-GRID", "linetype": "CENTER"})

        dx, dy = ex - sx, ey - sy
        g_len = math.hypot(dx, dy)
        if g_len > 1e-4:
            ux, uy = dx / g_len, dy / g_len
            b_start = (sx - ux * bubble_radius, sy - uy * bubble_radius)
            b_end = (ex + ux * bubble_radius, ey + uy * bubble_radius)

            # Insert Reusable GRID_BUBBLE Block Reference with ATTRIB
            try:
                br1 = msp.add_blockref("GRID_BUBBLE", b_start, dxfattribs={"layer": "GRID-ANNO"})
                br1.add_auto_attribs({"GRID_ID": g.id})
                br2 = msp.add_blockref("GRID_BUBBLE", b_end, dxfattribs={"layer": "GRID-ANNO"})
                br2.add_auto_attribs({"GRID_ID": g.id})
            except Exception:
                pass

    # 7. Render Dimension Lines & Numeric Text (`DIM-ANNO` and `A-DIMS`)
    grid_x = sorted([g for g in cut_plane.grid_lines if g.axis == "X"], key=lambda g: g.position)
    grid_y = sorted([g for g in cut_plane.grid_lines if g.axis == "Y"], key=lambda g: g.position)

    bx0, by0, bx1, by1 = cut_plane.bounds
    min_x, max_x = bx0 * scale, bx1 * scale
    min_y, max_y = by0 * scale, by1 * scale

    dim_offset = 1200.0 if is_mm else 1.20
    tick_size = 150.0 if is_mm else 0.15
    dim_text_h = 200.0 if is_mm else 0.20

    # Horizontal Dimension Line along X-Axes
    if len(grid_x) >= 2:
        dim_y = max_y + dim_offset
        x_first = grid_x[0].position * scale
        x_last = grid_x[-1].position * scale
        msp.add_line((x_first, dim_y), (x_last, dim_y), dxfattribs={"layer": "DIM-ANNO"})
        msp.add_line((x_first, dim_y), (x_last, dim_y), dxfattribs={"layer": "A-DIMS"})

        for i in range(len(grid_x) - 1):
            x1 = grid_x[i].position * scale
            x2 = grid_x[i + 1].position * scale
            dist = abs(x2 - x1)

            msp.add_line((x1 - tick_size, dim_y - tick_size), (x1 + tick_size, dim_y + tick_size), dxfattribs={"layer": "DIM-ANNO"})
            msp.add_line((x2 - tick_size, dim_y - tick_size), (x2 + tick_size, dim_y + tick_size), dxfattribs={"layer": "DIM-ANNO"})
            msp.add_line((x1 - tick_size, dim_y - tick_size), (x1 + tick_size, dim_y + tick_size), dxfattribs={"layer": "A-DIMS"})
            msp.add_line((x2 - tick_size, dim_y - tick_size), (x2 + tick_size, dim_y + tick_size), dxfattribs={"layer": "A-DIMS"})

            val_str = f"{dist:.0f}" if is_mm else f"{dist / scale:.2f}"
            mid_x = (x1 + x2) / 2.0
            msp.add_text(
                val_str,
                dxfattribs={
                    "layer": "DIM-ANNO",
                    "style": "TH_SARABUN",
                    "height": dim_text_h,
                },
            ).set_placement((mid_x, dim_y + dim_text_h * 0.5), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)

            msp.add_text(
                val_str,
                dxfattribs={
                    "layer": "A-DIMS",
                    "style": "TH_SARABUN",
                    "height": dim_text_h,
                },
            ).set_placement((mid_x, dim_y + dim_text_h * 0.5), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)

    # Vertical Dimension Line along Y-Axes
    if len(grid_y) >= 2:
        dim_x = min_x - dim_offset
        y_first = grid_y[0].position * scale
        y_last = grid_y[-1].position * scale
        msp.add_line((dim_x, y_first), (dim_x, y_last), dxfattribs={"layer": "DIM-ANNO"})
        msp.add_line((dim_x, y_first), (dim_x, y_last), dxfattribs={"layer": "A-DIMS"})

        for i in range(len(grid_y) - 1):
            y1 = grid_y[i].position * scale
            y2 = grid_y[i + 1].position * scale
            dist = abs(y2 - y1)

            msp.add_line((dim_x - tick_size, y1 - tick_size), (dim_x + tick_size, y1 + tick_size), dxfattribs={"layer": "DIM-ANNO"})
            msp.add_line((dim_x - tick_size, y2 - tick_size), (dim_x + tick_size, y2 + tick_size), dxfattribs={"layer": "DIM-ANNO"})
            msp.add_line((dim_x - tick_size, y1 - tick_size), (dim_x + tick_size, y1 + tick_size), dxfattribs={"layer": "A-DIMS"})
            msp.add_line((dim_x - tick_size, y2 - tick_size), (dim_x + tick_size, y2 + tick_size), dxfattribs={"layer": "A-DIMS"})

            val_str = f"{dist:.0f}" if is_mm else f"{dist / scale:.2f}"
            mid_y = (y1 + y2) / 2.0
            msp.add_text(
                val_str,
                dxfattribs={
                    "layer": "DIM-ANNO",
                    "style": "TH_SARABUN",
                    "height": dim_text_h,
                    "rotation": 90.0,
                },
            ).set_placement((dim_x - dim_text_h * 0.5, mid_y), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)

            msp.add_text(
                val_str,
                dxfattribs={
                    "layer": "A-DIMS",
                    "style": "TH_SARABUN",
                    "height": dim_text_h,
                    "rotation": 90.0,
                },
            ).set_placement((dim_x - dim_text_h * 0.5, mid_y), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)

    # Save output DXF document
    doc.saveas(output_file)
    return output_file.resolve()
