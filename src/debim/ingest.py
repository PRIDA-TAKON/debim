"""
Scaffolding ingestion assistant for CAD/DXF files for debim.
Extracts grid axes, labels, dimensions, and column coordinates from DXF into a project.debim manifest.
"""

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

import ezdxf


def _cluster_coordinates(coords: List[float], tolerance: float = 0.05) -> List[float]:
    """Group close coordinates within tolerance and return sorted cluster averages."""
    if not coords:
        return []
    sorted_coords = sorted(coords)
    clusters: List[List[float]] = []

    for c in sorted_coords:
        if not clusters:
            clusters.append([c])
        else:
            if c - clusters[-1][-1] <= tolerance:
                clusters[-1].append(c)
            else:
                clusters.append([c])

    means = [float(round(sum(group) / len(group), 2)) for group in clusters]
    return sorted(list(set(means)))


def _find_nearest_grid_label(val: float, grid_map: Dict[str, float], max_dist: float = 0.15) -> Optional[str]:
    """Find grid label closest to coordinate value val within max_dist."""
    best_label = None
    best_dist = float("inf")
    for label, pos in grid_map.items():
        dist = abs(val - pos)
        if dist <= max_dist and dist < best_dist:
            best_dist = dist
            best_label = label
    return best_label


def parse_dxf_grid_and_columns(dxf_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Parse DXF file using ezdxf to extract grid lines, text labels, dimension entities,
    and column coordinates.

    Returns dict with keys:
    - axes_x: Dict[str, float]
    - axes_y: Dict[str, float]
    - columns: List[Dict[str, Any]] (containing grid positions or coordinates)
    - units: str ("mm" or "m")
    """
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    # Determine unit scale factor to meters
    insunits = doc.header.get("$INSUNITS", 4)
    # 4 = mm, 5 = cm, 6 = m, 1 = inches, 2 = feet
    if insunits == 6:
        scale = 1.0
        unit_str = "METER"
    elif insunits == 5:
        scale = 0.01
        unit_str = "CENTIMETER"
    else:
        # Default assume mm
        scale = 0.001
        unit_str = "MILLIMETER"

    raw_x_coords: List[float] = []
    raw_y_coords: List[float] = []

    text_labels: List[Tuple[str, float, float]] = [] # (text, x_m, y_m)
    column_points: List[Tuple[float, float, float, float]] = [] # (cx, cy, w, d)

    # 1. Scan LINE / LWPOLYLINE / POLYLINE entities for grids and columns
    for entity in msp:
        etype = entity.dxftype()
        layer = entity.dxf.layer.upper() if entity.dxf.hasattr("layer") else ""

        if etype == "LINE":
            sx, sy = float(entity.dxf.start.x * scale), float(entity.dxf.start.y * scale)
            ex, ey = float(entity.dxf.end.x * scale), float(entity.dxf.end.y * scale)

            # Check if line is vertical (X-grid line) or horizontal (Y-grid line)
            if abs(sx - ex) < 0.01: # Vertical line
                raw_x_coords.append(sx)
            elif abs(sy - ey) < 0.01: # Horizontal line
                raw_y_coords.append(sy)

        elif etype in ("LWPOLYLINE", "POLYLINE"):
            try:
                pts = [(float(p[0] * scale), float(p[1] * scale)) for p in entity.get_points()]
            except Exception:
                pts = []

            if len(pts) >= 4 and ("COL" in layer or "S-COL" in layer or "COLUMN" in layer or entity.is_closed):
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                w = float(max_x - min_x)
                h = float(max_y - min_y)
                # Column candidates are usually reasonably sized (0.1m to 1.5m)
                if 0.10 <= w <= 1.50 and 0.10 <= h <= 1.50:
                    cx = float((min_x + max_x) / 2.0)
                    cy = float((min_y + max_y) / 2.0)
                    column_points.append((cx, cy, float(round(w, 2)), float(round(h, 2))))

        elif etype in ("TEXT", "MTEXT"):
            try:
                txt = entity.dxf.text.strip() if etype == "TEXT" else entity.text.strip()
            except Exception:
                txt = ""

            if txt:
                # Clean MTEXT formatting tags if any
                import re
                clean_txt = re.sub(r"\\[A-Za-z0-9]+;|\{|\}", "", txt).strip()
                if entity.dxf.hasattr("insert"):
                    tx, ty = float(entity.dxf.insert.x * scale), float(entity.dxf.insert.y * scale)
                    text_labels.append((clean_txt, tx, ty))

        elif etype == "DIMENSION":
            # Extract dimension extension/definition points if present
            if entity.dxf.hasattr("defpoint"):
                raw_x_coords.append(float(entity.dxf.defpoint.x * scale))
                raw_y_coords.append(float(entity.dxf.defpoint.y * scale))
            if entity.dxf.hasattr("defpoint2"):
                raw_x_coords.append(float(entity.dxf.defpoint2.x * scale))
                raw_y_coords.append(float(entity.dxf.defpoint2.y * scale))
            if entity.dxf.hasattr("defpoint3"):
                raw_x_coords.append(float(entity.dxf.defpoint3.x * scale))
                raw_y_coords.append(float(entity.dxf.defpoint3.y * scale))

        elif etype == "INSERT":
            # Block insertions on column layers
            if "COL" in layer or "S-COL" in layer or "COLUMN" in layer:
                if entity.dxf.hasattr("insert"):
                    cx, cy = float(entity.dxf.insert.x * scale), float(entity.dxf.insert.y * scale)
                    column_points.append((cx, cy, 0.20, 0.20))

    # Cluster raw grid line coordinates
    clustered_x = _cluster_coordinates(raw_x_coords, tolerance=0.08)
    clustered_y = _cluster_coordinates(raw_y_coords, tolerance=0.08)

    # Assign grid labels
    axes_x: Dict[str, float] = {}
    axes_y: Dict[str, float] = {}

    # Try mapping text labels near grid lines
    for i, x_val in enumerate(clustered_x):
        label = None
        # Look for text near x_val
        for txt, tx, ty in text_labels:
            if abs(tx - x_val) < 0.30:
                # Candidate label
                if txt.isalnum() or len(txt) <= 4:
                    label = txt
                    break
        if not label or label in axes_x:
            # Fallback label 1, 2, 3...
            label = str(i + 1)
        axes_x[label] = float(x_val)

    for j, y_val in enumerate(clustered_y):
        label = None
        for txt, tx, ty in text_labels:
            if abs(ty - y_val) < 0.30:
                if txt.isalnum() or len(txt) <= 4:
                    label = txt
                    break
        if not label or label in axes_y:
            # Fallback label A, B, C...
            label = chr(65 + (j % 26)) if j < 26 else f"Y{j+1}"
        axes_y[label] = float(y_val)

    # Deduplicate column points
    unique_cols: List[Tuple[float, float, float, float]] = []
    for cx, cy, w, h in column_points:
        is_dup = False
        for ocx, ocy, _, _ in unique_cols:
            if math.hypot(cx - ocx, cy - ocy) < 0.10:
                is_dup = True
                break
        if not is_dup:
            unique_cols.append((cx, cy, w, h))

    # Map column coordinates to grid labels
    columns: List[Dict[str, Any]] = []
    for idx, (cx, cy, w, h) in enumerate(unique_cols, start=1):
        lbl_x = _find_nearest_grid_label(cx, axes_x, max_dist=0.30)
        lbl_y = _find_nearest_grid_label(cy, axes_y, max_dist=0.30)

        col_dict: Dict[str, Any] = {
            "class": "IfcColumn",
            "tag": f"C{idx}",
            "material": "RC_CONCRETE",
            "profile": {
                "shape": "BOX",
                "width": float(w),
                "depth": float(h),
            },
        }

        if lbl_x and lbl_y:
            col_dict["placement"] = {
                "grid": [lbl_x, lbl_y],
                "base_storey": "FL1",
                "top_storey": "Roof",
            }
        else:
            col_dict["placement"] = {
                "coordinate": [float(round(cx, 2)), float(round(cy, 2))],
                "base_storey": "FL1",
                "top_storey": "Roof",
            }

        columns.append(col_dict)

    return {
        "axes_x": axes_x,
        "axes_y": axes_y,
        "columns": columns,
        "units": unit_str,
    }


def ingest_dxf_file(
    dxf_path: Union[str, Path],
    output_dir: Optional[Union[str, Path]] = None,
    output_name: str = "project.debim",
) -> Path:
    """
    Ingest DXF file and emit standard boilerplate project.debim manifest.
    """
    dxf_p = Path(dxf_path)
    if not dxf_p.exists():
        raise FileNotFoundError(f"CAD/DXF file '{dxf_path}' not found.")

    out_d = Path(output_dir) if output_dir else dxf_p.parent
    out_d.mkdir(parents=True, exist_ok=True)
    out_path = out_d / output_name

    parsed = parse_dxf_grid_and_columns(dxf_p)

    axes_x = parsed["axes_x"] or {"1": 0.00, "2": 4.00, "3": 8.00}
    axes_y = parsed["axes_y"] or {"A": 0.00, "B": 4.00, "C": 8.00}
    columns = parsed["columns"]

    manifest_data = {
        "schema": "IFC4-Minimal",
        "version": "0.8.1",
        "project": {
            "id": f"PRJ-{dxf_p.stem.upper()}",
            "name": f"Ingested Project ({dxf_p.name})",
            "units": {
                "length": "METER",
                "area": "SQUARE_METER",
                "volume": "CUBIC_METER",
            },
        },
        "spatial_structure": {
            "storeys": [
                {"id": "Ground", "name": "Ground Level", "elevation": 0.00, "height": 1.00},
                {"id": "FL1", "name": "First Floor", "elevation": 1.00, "height": 3.50},
                {"id": "Roof", "name": "Roof Level", "elevation": 4.50, "height": 0.50},
            ]
        },
        "grids": {
            "axes_x": axes_x,
            "axes_y": axes_y,
        },
        "materials": [
            {
                "id": "RC_CONCRETE",
                "name": "Reinforced Concrete 240 ksc",
                "category": "concrete",
                "unit_cost_ref": "MAT-CONC-240",
            }
        ],
        "elements": columns,
    }

    import yaml
    yaml_str = yaml.safe_dump(manifest_data, sort_keys=False, allow_unicode=True)

    header_comment = (
        f"# ==============================================================================\n"
        f"# Ingested from CAD/DXF: {dxf_p.name}\n"
        f"# Generated by debim Ingestion Scaffolding Assistant v0.8.1\n"
        f"# ==============================================================================\n\n"
    )

    out_path.write_text(header_comment + yaml_str, encoding="utf-8")
    return out_path.resolve()
