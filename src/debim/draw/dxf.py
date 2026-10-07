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
from debim.resolver import ResolvedManifest
from debim.schema import ProjectManifest


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

    # Layer Hierarchy Definitions (Layer Name, Color Code, Linetype)
    # ACI Colors: 1=Red, 2=Yellow, 3=Green, 4=Cyan, 5=Blue, 6=Magenta, 7=White/Black, 8=Dark Gray
    layers_def = [
        ("A-WALL", 7, "Continuous"),      # Wall cut lines
        ("S-COLS", 3, "Continuous"),      # Column profiles (Green)
        ("A-DOOR", 2, "Continuous"),      # Door leaf & swing arc (Yellow)
        ("A-WIND", 4, "Continuous"),      # Window frames & glazing (Cyan)
        ("A-GRID", 1, "CENTER"),          # Grid centerlines (Red, CENTER)
        ("A-DIMS", 5, "Continuous"),      # Dimensions & numeric text (Blue)
        ("A-FLOR", 8, "Continuous"),      # Floor slabs & steps (Gray)
        ("A-SANR", 6, "Continuous"),      # Sanitary fixtures (Magenta)
    ]

    for name, color, linetype in layers_def:
        if name not in doc.layers:
            doc.layers.add(name, color=color, linetype=linetype)


def export_2d_dxf(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
    output_path: Union[str, Path],
    storey_id: Optional[str] = None,
    cut_offset_z: float = 1.20,
    units: str = "mm",
) -> Path:
    """
    Export 2D projected floor plan elements into a deterministic AutoCAD DXF file.

    Parameters:
    -----------
    manifest_or_resolved : ProjectManifest or ResolvedManifest
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

    # Determine target storey if not provided
    if storey_id is None:
        if isinstance(manifest_or_resolved, ProjectManifest):
            storeys = manifest_or_resolved.spatial_structure.storeys
        else:
            storeys = manifest_or_resolved.manifest.spatial_structure.storeys

        if not storeys:
            raise ValueError("No storeys found in project manifest.")
        storey_id = storeys[0].id

    # Compute 2D Section Slice
    cut_plane: CutPlaneResult = slice_storey(
        manifest_or_resolved, storey_id=storey_id, cut_offset_z=cut_offset_z
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
    msp = doc.modelspace()

    # 1. Render Walls (`A-WALL`)
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcWall":
            for ring in elem.polygon_coords:
                if len(ring) < 2:
                    continue
                scaled_pts = [(x * scale, y * scale) for x, y in ring]
                msp.add_lwpolyline(scaled_pts, close=True, dxfattribs={"layer": "A-WALL"})

    # 2. Render Columns (`S-COLS`) with Solid Hatch
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcColumn":
            for ring in elem.polygon_coords:
                if len(ring) < 2:
                    continue
                scaled_pts = [(x * scale, y * scale) for x, y in ring]
                # Column boundary
                msp.add_lwpolyline(scaled_pts, close=True, dxfattribs={"layer": "S-COLS"})
                # Solid Hatch
                try:
                    hatch = msp.add_hatch(color=256, dxfattribs={"layer": "S-COLS"})
                    hatch.set_pattern_fill("SOLID")
                    hatch.paths.add_polyline_path(scaled_pts, is_closed=True)
                except Exception:
                    pass

    # 3. Render Doors (`A-DOOR`) with Frame, Leaf, and 90-Degree Swing Arc
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcDoor":
            # Draw frame box
            for ring in elem.polygon_coords:
                if len(ring) < 2:
                    continue
                scaled_pts = [(x * scale, y * scale) for x, y in ring]
                msp.add_lwpolyline(scaled_pts, close=True, dxfattribs={"layer": "A-DOOR"})

            # Calculate door leaf line & swing arc from geometry / properties
            width = elem.properties.get("width", 0.90) * scale
            coords = elem.polygon_coords[0] if elem.polygon_coords else []
            if len(coords) >= 4:
                # Frame box corners
                p0, p1, p2, p3 = coords[0], coords[1], coords[2], coords[3]
                # Center of short sides (hinge & lock ends)
                h_x = (p0[0] + p3[0]) / 2.0 * scale
                h_y = (p0[1] + p3[1]) / 2.0 * scale
                l_x = (p1[0] + p2[0]) / 2.0 * scale
                l_y = (p1[1] + p2[1]) / 2.0 * scale

                # Wall vector angle
                dx = l_x - h_x
                dy = l_y - h_y
                door_len = math.hypot(dx, dy)
                if door_len > 1e-4:
                    base_angle_rad = math.atan2(dy, dx)
                    base_angle_deg = math.degrees(base_angle_rad)

                    # Leaf tip rotated 90 degrees outward
                    open_angle_rad = base_angle_rad + math.pi / 2.0
                    tip_x = h_x + door_len * math.cos(open_angle_rad)
                    tip_y = h_y + door_len * math.sin(open_angle_rad)

                    # Add open door leaf line
                    msp.add_line((h_x, h_y), (tip_x, tip_y), dxfattribs={"layer": "A-DOOR"})

                    # Add 90-degree swing arc
                    start_deg = base_angle_deg
                    end_deg = base_angle_deg + 90.0
                    msp.add_arc(
                        center=(h_x, h_y),
                        radius=door_len,
                        start_angle=start_deg,
                        end_angle=end_deg,
                        dxfattribs={"layer": "A-DOOR"},
                    )

    # 4. Render Windows (`A-WIND`) Frame and Glazing Lines
    for elem in cut_plane.cut_elements:
        if elem.element_class == "IfcWindow":
            for ring in elem.polygon_coords:
                if len(ring) < 2:
                    continue
                scaled_pts = [(x * scale, y * scale) for x, y in ring]
                msp.add_lwpolyline(scaled_pts, close=True, dxfattribs={"layer": "A-WIND"})

            # Add central glazing line along window length
            coords = elem.polygon_coords[0] if elem.polygon_coords else []
            if len(coords) >= 4:
                p0, p1, p2, p3 = coords[0], coords[1], coords[2], coords[3]
                mid_start = ((p0[0] + p3[0]) / 2.0 * scale, (p0[1] + p3[1]) / 2.0 * scale)
                mid_end = ((p1[0] + p2[0]) / 2.0 * scale, (p1[1] + p2[1]) / 2.0 * scale)
                msp.add_line(mid_start, mid_end, dxfattribs={"layer": "A-WIND"})

    # 5. Render Floor Slabs & Steps (`A-FLOR`) and Sanitary Fixtures (`A-SANR`)
    for elem in cut_plane.projection_elements:
        target_layer = "A-SANR" if "Terminal" in elem.element_class else "A-FLOR"
        for ring in elem.polygon_coords:
            if len(ring) < 2:
                continue
            scaled_pts = [(x * scale, y * scale) for x, y in ring]
            msp.add_lwpolyline(scaled_pts, close=True, dxfattribs={"layer": target_layer})

    # 6. Render Grid Lines & Axis Bubbles (`A-GRID`)
    bubble_radius = 400.0 if is_mm else 0.40
    text_height = 250.0 if is_mm else 0.25

    for g in cut_plane.grid_lines:
        sx, sy = g.start[0] * scale, g.start[1] * scale
        ex, ey = g.end[0] * scale, g.end[1] * scale

        # Grid line centerline
        msp.add_line((sx, sy), (ex, ey), dxfattribs={"layer": "A-GRID", "linetype": "CENTER"})

        # Direction vector for extending bubble past bounds
        dx, dy = ex - sx, ey - sy
        g_len = math.hypot(dx, dy)
        if g_len > 1e-4:
            ux, uy = dx / g_len, dy / g_len
            b_start = (sx - ux * bubble_radius, sy - uy * bubble_radius)
            b_end = (ex + ux * bubble_radius, ey + uy * bubble_radius)

            # Bubble circles at start and end
            msp.add_circle(b_start, bubble_radius, dxfattribs={"layer": "A-GRID"})
            msp.add_circle(b_end, bubble_radius, dxfattribs={"layer": "A-GRID"})

            # Text labels inside bubbles
            msp.add_text(
                g.id,
                dxfattribs={
                    "layer": "A-GRID",
                    "style": "THAI",
                    "height": text_height,
                },
            ).set_placement(b_start, align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

            msp.add_text(
                g.id,
                dxfattribs={
                    "layer": "A-GRID",
                    "style": "THAI",
                    "height": text_height,
                },
            ).set_placement(b_end, align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    # 7. Render Dimension Lines & Numeric Text (`A-DIMS`)
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
        # Main dimension line
        x_first = grid_x[0].position * scale
        x_last = grid_x[-1].position * scale
        msp.add_line((x_first, dim_y), (x_last, dim_y), dxfattribs={"layer": "A-DIMS"})

        for i in range(len(grid_x) - 1):
            x1 = grid_x[i].position * scale
            x2 = grid_x[i + 1].position * scale
            dist = abs(x2 - x1)

            # Tick marks
            msp.add_line((x1 - tick_size, dim_y - tick_size), (x1 + tick_size, dim_y + tick_size), dxfattribs={"layer": "A-DIMS"})
            msp.add_line((x2 - tick_size, dim_y - tick_size), (x2 + tick_size, dim_y + tick_size), dxfattribs={"layer": "A-DIMS"})

            # Numeric dimension text
            val_str = f"{dist:.0f}" if is_mm else f"{dist / scale:.2f}"
            mid_x = (x1 + x2) / 2.0
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
        msp.add_line((dim_x, y_first), (dim_x, y_last), dxfattribs={"layer": "A-DIMS"})

        for i in range(len(grid_y) - 1):
            y1 = grid_y[i].position * scale
            y2 = grid_y[i + 1].position * scale
            dist = abs(y2 - y1)

            # Tick marks
            msp.add_line((dim_x - tick_size, y1 - tick_size), (dim_x + tick_size, y1 + tick_size), dxfattribs={"layer": "A-DIMS"})
            msp.add_line((dim_x - tick_size, y2 - tick_size), (dim_x + tick_size, y2 + tick_size), dxfattribs={"layer": "A-DIMS"})

            # Numeric dimension text
            val_str = f"{dist:.0f}" if is_mm else f"{dist / scale:.2f}"
            mid_y = (y1 + y2) / 2.0
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
