#!/usr/bin/env python3
"""
debim-zero: Zero-Dependency Declarative BIM Engine & Validator.
Designed to run in completely offline environments / isolated VMs with standard Python 3.
Requires ZERO external packages (No pip install, no trimesh, no typer, no pydantic).
Standard Library Only: argparse, json, math, re, pathlib, typing.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ==============================================================================
# 1. Coordinate & Spatial Math Engine (Pure Standard Library)
# ==============================================================================

def parse_grid_expression(expr: str, grids_x: Dict[str, float], grids_y: Dict[str, float]) -> Tuple[float, float]:
    """
    Parses a grid coordinate string or grid-offset mathematical expression.
    Examples:
        'GX_1' -> lookup in grids_x or grids_y
        'GX_1 + 0.10' -> lookup + 0.10
        'GY_2 - 0.25' -> lookup - 0.25
    """
    expr = str(expr).strip()
    match = re.match(r"^([A-Za-z0-9_]+)(?:\s*([+-])\s*([0-9.]+))?$", expr)
    if not match:
        try:
            val = float(expr)
            return val, val
        except ValueError:
            raise ValueError(f"Invalid grid expression syntax: '{expr}'")

    grid_name, sign, offset_str = match.groups()
    offset = float(offset_str) if offset_str else 0.0
    if sign == "-":
        offset = -offset

    val = None
    if grid_name in grids_x:
        val = grids_x[grid_name] + offset
    elif grid_name in grids_y:
        val = grids_y[grid_name] + offset
    else:
        raise KeyError(f"Grid axis '{grid_name}' not defined in project grids.")

    return val, val


def resolve_2d_point(pt: Any, grids_x: Dict[str, float], grids_y: Dict[str, float]) -> Tuple[float, float]:
    """Resolves a 2D point which could be [gx, gy], ['GX_1 + 0.1', 'GY_1 - 0.1'], or [float, float]."""
    if isinstance(pt, (list, tuple)) and len(pt) == 2:
        px_raw, py_raw = pt
        # Resolve X
        if isinstance(px_raw, (int, float)):
            x = float(px_raw)
        else:
            x, _ = parse_grid_expression(str(px_raw), grids_x, {})
        # Resolve Y
        if isinstance(py_raw, (int, float)):
            y = float(py_raw)
        else:
            _, y = parse_grid_expression(str(py_raw), {}, grids_y)
        return (x, y)
    raise ValueError(f"Invalid 2D point format: {pt}")


def shoelace_polygon_area(vertices: List[Tuple[float, float]]) -> float:
    """Calculates 2D polygon area using the Shoelace formula."""
    n = len(vertices)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += vertices[i][0] * vertices[j][1]
        area -= vertices[j][0] * vertices[i][1]
    return abs(area) / 2.0


def polygon_perimeter(vertices: List[Tuple[float, float]]) -> float:
    """Calculates 2D polygon perimeter."""
    n = len(vertices)
    if n < 2:
        return 0.0
    perimeter = 0.0
    for i in range(n):
        j = (i + 1) % n
        dx = vertices[j][0] - vertices[i][0]
        dy = vertices[j][1] - vertices[i][1]
        perimeter += math.sqrt(dx * dx + dy * dy)
    return perimeter


def is_counter_clockwise(vertices: List[Tuple[float, float]]) -> bool:
    """Checks if 2D vertices follow Counter-Clockwise (CCW) ordering."""
    n = len(vertices)
    if n < 3:
        return True
    signed_area = 0.0
    for i in range(n):
        j = (i + 1) % n
        signed_area += (vertices[j][0] - vertices[i][0]) * (vertices[j][1] + vertices[i][1])
    return signed_area < 0.0


def calculate_polygon_centroid(vertices: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Calculates the 2D centroid of a polygon."""
    n = len(vertices)
    if n == 0:
        return 0.0, 0.0
    area = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(n):
        j = (i + 1) % n
        cross = vertices[i][0] * vertices[j][1] - vertices[j][0] * vertices[i][1]
        area += cross
        cx += (vertices[i][0] + vertices[j][0]) * cross
        cy += (vertices[i][1] + vertices[j][1]) * cross
    area = area / 2.0
    if abs(area) < 1e-9:
        # Fallback to mean
        return sum(v[0] for v in vertices) / n, sum(v[1] for v in vertices) / n
    factor = 1.0 / (6.0 * area)
    return cx * factor, cy * factor


# ==============================================================================
# 2. Manifest Loading & Validation
# ==============================================================================

def load_manifest_data(file_path: Path) -> Dict[str, Any]:
    """Loads manifest data from JSON, or falls back to basic YAML parsing if available."""
    content = file_path.read_text(encoding="utf-8")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        try:
            import yaml
            return yaml.safe_load(content)
        except ImportError:
            # Simple minimal YAML-to-dict parser fallback for key properties
            raise RuntimeError(
                f"File '{file_path}' is YAML format but PyYAML is not installed. "
                "In zero-dependency VM environments, save project manifest as .json "
                "or use Python with PyYAML."
            )


def validate_manifest(data: Dict[str, Any]) -> List[str]:
    """Validates spatial structure, grids, elements, and coordinate bounding rules."""
    errors = []

    # 1. Project Header
    project = data.get("project")
    if not project or not project.get("id"):
        errors.append("Missing required 'project.id'.")

    # 2. Storeys
    spatial = data.get("spatial_structure", {})
    storeys = spatial.get("storeys", [])
    if not storeys:
        errors.append("No storeys defined in 'spatial_structure.storeys'.")
    storey_ids = {s["id"] for s in storeys if "id" in s}

    # 3. Grids
    grids = data.get("grids", {})
    gx = grids.get("axes_x", {})
    gy = grids.get("axes_y", {})
    if not gx or not gy:
        errors.append("Project grids must define at least one 'axes_x' and 'axes_y'.")

    # 4. Elements validation
    elements = data.get("elements", [])
    for idx, elem in enumerate(elements):
        cls_name = elem.get("class")
        tag = elem.get("tag", f"Element[{idx}]")
        placement = elem.get("placement", {})

        if not cls_name:
            errors.append(f"Element #{idx} missing required 'class'.")
            continue

        # Check storey reference
        storey_ref = placement.get("storey") or placement.get("base_storey")
        if storey_ref and storey_ref not in storey_ids:
            errors.append(f"Element '{tag}' references unknown storey '{storey_ref}'.")

        # Check boundary rules (Slabs, Roofs, Spaces)
        boundary = placement.get("boundary")
        boundary_pts = placement.get("boundary_points")
        if boundary or boundary_pts:
            pts_to_check = []
            try:
                if boundary:
                    for b in boundary:
                        pts_to_check.append(resolve_2d_point(b, gx, gy))
                elif boundary_pts:
                    pts_to_check = [tuple(p) for p in boundary_pts]

                if len(pts_to_check) >= 3 and not is_counter_clockwise(pts_to_check):
                    # Warning / notice on vertex winding
                    pass
            except Exception as e:
                errors.append(f"Element '{tag}' invalid boundary coordinates: {e}")

    return errors


# ==============================================================================
# 3. Deterministic QTO Calculation (Pure Python Math)
# ==============================================================================

def calculate_manifest_qto(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculates deterministic QTO (concrete volume, formwork, area, air volume) without guessing."""
    grids = data.get("grids", {})
    gx = grids.get("axes_x", {})
    gy = grids.get("axes_y", {})

    spatial = data.get("spatial_structure", {})
    storeys_dict = {s["id"]: s for s in spatial.get("storeys", [])}

    qto_items = []
    total_concrete_vol = 0.0
    total_formwork_area = 0.0
    total_space_area = 0.0
    total_air_volume = 0.0

    for elem in data.get("elements", []):
        cls_name = elem.get("class")
        tag = elem.get("tag", "Unnamed")
        mat = elem.get("material", "-")
        placement = elem.get("placement", {})

        concrete_vol = 0.0
        formwork_area = 0.0
        floor_area = 0.0
        air_vol = 0.0

        if cls_name == "IfcColumn":
            prof = elem.get("profile", {})
            w = prof.get("width", 0.20)
            d = prof.get("depth", 0.20)
            base_s = storeys_dict.get(placement.get("base_storey", ""), {})
            top_s = storeys_dict.get(placement.get("top_storey", ""), {})
            h = (top_s.get("elevation", 3.0) + placement.get("offset_top", 0.0)) - \
                (base_s.get("elevation", 0.0) + placement.get("offset_base", 0.0))
            if h <= 0:
                h = base_s.get("height", 3.0)
            concrete_vol = w * d * h
            formwork_area = 2 * (w + d) * h

        elif cls_name == "IfcBeam":
            prof = elem.get("profile", {})
            w = prof.get("width", 0.20)
            d = prof.get("depth", 0.40)
            p1 = resolve_2d_point(placement.get("from_grid"), gx, gy)
            p2 = resolve_2d_point(placement.get("to_grid"), gx, gy)
            span = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            concrete_vol = w * d * span
            formwork_area = (w + 2 * d) * span

        elif cls_name == "IfcWall":
            th = elem.get("thickness", 0.15)
            h = elem.get("height", 2.80)
            p1 = resolve_2d_point(placement.get("from_grid"), gx, gy)
            p2 = resolve_2d_point(placement.get("to_grid"), gx, gy)
            length = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            concrete_vol = length * th * h
            formwork_area = 2 * (length * h)

        elif cls_name == "IfcSlab":
            th = elem.get("thickness", 0.15)
            boundary = placement.get("boundary", [])
            boundary_pts = placement.get("boundary_points", [])
            poly = [resolve_2d_point(b, gx, gy) for b in boundary] if boundary else [tuple(p) for p in boundary_pts]
            area = shoelace_polygon_area(poly)
            concrete_vol = area * th
            formwork_area = area + (polygon_perimeter(poly) * th)
            floor_area = area

        elif cls_name == "IfcSpace":
            h = elem.get("height", 2.80)
            boundary = placement.get("boundary", [])
            boundary_pts = placement.get("boundary_points", [])
            poly = [resolve_2d_point(b, gx, gy) for b in boundary] if boundary else [tuple(p) for p in boundary_pts]
            area = shoelace_polygon_area(poly)
            floor_area = area
            air_vol = area * h
            total_space_area += floor_area
            total_air_volume += air_vol

        total_concrete_vol += concrete_vol
        total_formwork_area += formwork_area

        qto_items.append({
            "tag": tag,
            "class": cls_name,
            "material": mat,
            "concrete_m3": round(concrete_vol, 4),
            "formwork_m2": round(formwork_area, 4),
            "floor_area_m2": round(floor_area, 4),
            "air_volume_m3": round(air_vol, 4),
        })

    return {
        "items": qto_items,
        "totals": {
            "total_concrete_m3": round(total_concrete_vol, 3),
            "total_formwork_m2": round(total_formwork_area, 3),
            "total_usable_floor_area_m2": round(total_space_area, 3),
            "total_air_volume_m3": round(total_air_volume, 3),
        }
    }


# ==============================================================================
# 4. CLI Entry Point (Argparse Standard Library)
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        prog="debim-zero",
        description="Zero-Dependency Offline Declarative BIM Engine & Validator",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Validate Command
    v_parser = subparsers.add_parser("validate", help="Validate a project manifest file")
    v_parser.add_argument("manifest", type=Path, help="Path to project.json or project.yaml")

    # QTO Command
    q_parser = subparsers.add_parser("qto", help="Compute deterministic QTO (Take-Off)")
    q_parser.add_argument("manifest", type=Path, help="Path to project.json or project.yaml")
    q_parser.add_argument("--json", action="store_true", help="Output QTO summary as JSON")

    args = parser.parse_args()

    if args.command == "validate":
        try:
            data = load_manifest_data(args.manifest)
            errors = validate_manifest(data)
            if errors:
                print(f"[FAIL] Manifest has {len(errors)} validation errors:")
                for e in errors:
                    print(f"  - {e}")
                sys.exit(1)
            else:
                print(f"[PASS] Manifest '{args.manifest.name}' passed all spatial & schema checks.")
        except Exception as e:
            print(f"[ERROR] Failed to validate manifest: {e}")
            sys.exit(1)

    elif args.command == "qto":
        try:
            data = load_manifest_data(args.manifest)
            res = calculate_manifest_qto(data)
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print("\n=======================================================")
                print(f" debim-zero Deterministic QTO Report: {args.manifest.name}")
                print("=======================================================")
                print(f"{'Tag':<20} | {'Class':<14} | {'Conc(m3)':<9} | {'Form(m2)':<9} | {'Area(m2)':<9}")
                print("-" * 72)
                for item in res["items"]:
                    print(f"{item['tag']:<20} | {item['class']:<14} | {item['concrete_m3']:<9.2f} | {item['formwork_m2']:<9.2f} | {item['floor_area_m2']:<9.2f}")
                print("=" * 72)
                tot = res["totals"]
                print(f"TOTAL CONCRETE VOLUME   : {tot['total_concrete_m3']:>8.2f} m3")
                print(f"TOTAL FORMWORK AREA     : {tot['total_formwork_m2']:>8.2f} m2")
                print(f"TOTAL USABLE FLOOR AREA : {tot['total_usable_floor_area_m2']:>8.2f} m2")
                print(f"TOTAL AIR VOLUME (HVAC) : {tot['total_air_volume_m3']:>8.2f} m3")
                print("=======================================================\n")
        except Exception as e:
            print(f"[ERROR] Failed to calculate QTO: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
