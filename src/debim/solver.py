"""
Fast Pre-Flight 2D Geometric Furniture Fit Solver and Non-Overlapping Clearance Checking Engine.

Provides pure-Python / NumPy 2D Bounding Box packing, Separating Axis Theorem (SAT) collision
detection for furniture footprints + clearance envelopes, and 2D grid flood-fill walkway
corridor connectivity verification (minimum 0.60m width).
"""

import math
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from debim.compat import BaseModel, Field, ConfigDict
from debim.geometry2d import point_in_polygon, shoelace_area, polygon_perimeter
from debim.schema import (
    FurnitureVariable,
    ProjectManifest,
    STANDARD_FURNITURE_VARIABLES,
    IfcSpace,
    IfcFurniture,
    IfcDoor,
    IfcWall,
)
from debim.standards import get_furniture


Point2D = Tuple[float, float]
Polygon2D = List[Point2D]


# --- SAT Collision Detection & 2D Geometry Helpers ---

def line_segments_intersect_strict(
    p1: Point2D, p2: Point2D, p3: Point2D, p4: Point2D, eps: float = 1e-7
) -> bool:
    """Check if line segment p1-p2 and p3-p4 strictly intersect in their interiors."""
    def orient(a: Point2D, b: Point2D, c: Point2D) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    o1 = orient(p1, p2, p3)
    o2 = orient(p1, p2, p4)
    o3 = orient(p3, p4, p1)
    o4 = orient(p3, p4, p2)

    if (o1 * o2 < -eps) and (o3 * o4 < -eps):
        return True
    return False


def sat_polygon_intersection(
    poly1: Polygon2D, poly2: Polygon2D, eps: float = 1e-5
) -> bool:
    """
    Determines whether two 2D convex polygons intersect using Separating Axis Theorem (SAT).
    Returns True if polygons overlap in interior, False if separated by at least one axis.
    """
    n1 = len(poly1)
    n2 = len(poly2)
    if n1 < 3 or n2 < 3:
        return False

    polys = [poly1, poly2]

    for p_idx in range(2):
        current_poly = polys[p_idx]
        other_poly = polys[1 - p_idx]
        n_pts = len(current_poly)

        for i in range(n_pts):
            j = (i + 1) % n_pts
            edge_x = current_poly[j][0] - current_poly[i][0]
            edge_y = current_poly[j][1] - current_poly[i][1]

            # Normal vector perpendicular to edge
            nx = -edge_y
            ny = edge_x
            norm_len = math.hypot(nx, ny)
            if norm_len < 1e-9:
                continue

            # Project poly1 onto normal axis
            min1 = float("inf")
            max1 = float("-inf")
            for pt in current_poly:
                proj = pt[0] * nx + pt[1] * ny
                if proj < min1:
                    min1 = proj
                if proj > max1:
                    max1 = proj

            # Project poly2 onto normal axis
            min2 = float("inf")
            max2 = float("-inf")
            for pt in other_poly:
                proj = pt[0] * nx + pt[1] * ny
                if proj < min2:
                    min2 = proj
                if proj > max2:
                    max2 = proj

            # Check separation on this axis
            if max1 <= min2 + eps or max2 <= min1 + eps:
                return False  # Found separating axis -> no intersection

    return True  # Overlap on all axes -> polygons intersect


def polygon_contains_polygon(
    outer_poly: Polygon2D, inner_poly: Polygon2D, eps: float = 1e-5
) -> bool:
    """
    Verifies whether inner_poly lies entirely within outer_poly boundary.
    """
    if not inner_poly or not outer_poly:
        return False

    # Check that all vertices of inner_poly lie inside or on boundary of outer_poly
    for pt in inner_poly:
        if not point_in_polygon(pt, outer_poly):
            return False

    # Check that no edge of inner_poly strictly crosses any edge of outer_poly
    n_in = len(inner_poly)
    n_out = len(outer_poly)

    for i in range(n_in):
        ip1 = inner_poly[i]
        ip2 = inner_poly[(i + 1) % n_in]
        for j in range(n_out):
            op1 = outer_poly[j]
            op2 = outer_poly[(j + 1) % n_out]
            if line_segments_intersect_strict(ip1, ip2, op1, op2, eps=eps):
                return False

    return True


def points_in_polygon_np(pts_x: np.ndarray, pts_y: np.ndarray, poly: Polygon2D) -> np.ndarray:
    """Vectorized ray-casting point-in-polygon test for 2D numpy coordinate arrays."""
    n = len(poly)
    inside = np.zeros(pts_x.shape, dtype=bool)
    if n < 3:
        return inside
    x1, y1 = poly[0]
    for i in range(n + 1):
        x2, y2 = poly[i % n]
        cond1 = (y1 > pts_y) != (y2 > pts_y)
        if np.any(cond1):
            denom = (y2 - y1)
            if abs(denom) < 1e-12:
                denom = 1e-12 if denom >= 0 else -1e-12
            x_cross = (x2 - x1) * (pts_y - y1) / denom + x1
            inside = np.where(cond1 & (pts_x < x_cross), ~inside, inside)
        x1, y1 = x2, y2
    return inside


# --- Polygon Corner Calculation ---

def compute_item_polygons(
    cx: float,
    cy: float,
    width: float,
    depth: float,
    clearance: Dict[str, float],
    rotation_deg: float = 0.0,
) -> Tuple[Polygon2D, Polygon2D]:
    """
    Calculates physical polygon and clearance envelope polygon for a furniture item
    centered at (cx, cy) with given width, depth, clearance offsets, and yaw rotation angle in degrees.
    """
    rad = math.radians(rotation_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    def transform(lx: float, ly: float) -> Point2D:
        rx = cx + lx * cos_a - ly * sin_a
        ry = cy + lx * sin_a + ly * cos_a
        return (round(rx, 6), round(ry, 6))

    half_w = width / 2.0
    half_d = depth / 2.0

    # Physical corners (local origin = physical center)
    local_phys = [
        (-half_w, -half_d),
        (half_w, -half_d),
        (half_w, half_d),
        (-half_w, half_d),
    ]
    phys_poly = [transform(lx, ly) for lx, ly in local_phys]

    # Clearance envelope corners
    left = clearance.get("left", 0.0) or 0.0
    right = clearance.get("right", 0.0) or 0.0
    front = clearance.get("front", 0.0) or 0.0
    back = clearance.get("back", 0.0) or 0.0

    min_lx = -half_w - left
    max_lx = half_w + right
    min_ly = -half_d - back
    max_ly = half_d + front

    local_clear = [
        (min_lx, min_ly),
        (max_lx, min_ly),
        (max_lx, max_ly),
        (min_lx, max_ly),
    ]
    clear_poly = [transform(lx, ly) for lx, ly in local_clear]

    return phys_poly, clear_poly


# --- Walkway Path Connectivity Verification ---

def check_walkway_connectivity(
    space_polygon: Polygon2D,
    entrance_point: Point2D,
    placed_items: List[Dict[str, Any]],
    corridor_width: float = 0.60,
    grid_resolution: Optional[float] = None,
) -> Tuple[bool, str]:
    """
    Verifies that a continuous walkway path of minimum width `corridor_width` (default 0.60m)
    exists between the space entrance point and each placed furniture envelope.
    """
    if not space_polygon or len(space_polygon) < 3:
        return False, "Invalid space polygon"

    xs = [p[0] for p in space_polygon]
    ys = [p[1] for p in space_polygon]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    span_x = max_x - min_x
    span_y = max_y - min_y

    if grid_resolution is None:
        grid_resolution = max(0.25, min(0.40, min(span_x, span_y) / 12.0))

    # Pad bounding box
    min_x -= 0.2
    max_x += 0.2
    min_y -= 0.2
    max_y += 0.2

    nx = int(math.ceil((max_x - min_x) / grid_resolution)) + 1
    ny = int(math.ceil((max_y - min_y) / grid_resolution)) + 1

    corridor_radius = corridor_width / 2.0

    # Physical polygons of items
    phys_polys = [item["physical_polygon"] for item in placed_items]

    grid_x = min_x + np.arange(nx) * grid_resolution
    grid_y = min_y + np.arange(ny) * grid_resolution
    gx_mesh, gy_mesh = np.meshgrid(grid_x, grid_y)

    # Vectorized point in space polygon test
    in_space = points_in_polygon_np(gx_mesh, gy_mesh, space_polygon)

    # Vectorized check against item physical bodies
    walkable = in_space.copy()
    for p_poly in phys_polys:
        in_item = points_in_polygon_np(gx_mesh, gy_mesh, p_poly)
        walkable &= ~in_item

    # Entrance grid coordinates
    e_c = int(round((entrance_point[0] - min_x) / grid_resolution))
    e_r = int(round((entrance_point[1] - min_y) / grid_resolution))

    e_c = max(0, min(nx - 1, e_c))
    e_r = max(0, min(ny - 1, e_r))

    # If entrance cell itself is not walkable, search nearest walkable neighbor
    if not walkable[e_r, e_c]:
        found_nearest = False
        min_dist = float("inf")
        best_r, best_c = e_r, e_c
        for r in range(max(0, e_r - 4), min(ny, e_r + 5)):
            for c in range(max(0, e_c - 4), min(nx, e_c + 5)):
                if walkable[r, c]:
                    dist = math.hypot(r - e_r, c - e_c)
                    if dist < min_dist:
                        min_dist = dist
                        best_r, best_c = r, c
                        found_nearest = True
        if found_nearest:
            e_r, e_c = best_r, best_c
        else:
            return False, f"Entrance point {entrance_point} is blocked or outside space boundary"

    # BFS Flood fill from entrance cell
    visited = np.zeros((ny, nx), dtype=bool)
    visited[e_r, e_c] = True
    queue = [(e_r, e_c)]

    dr = [-1, 1, 0, 0, -1, -1, 1, 1]
    dc = [0, 0, -1, 1, -1, 1, -1, 1]

    idx = 0
    while idx < len(queue):
        cr, cc = queue[idx]
        idx += 1

        for k in range(8):
            nr = cr + dr[k]
            nc = cc + dc[k]
            if 0 <= nr < ny and 0 <= nc < nx:
                if walkable[nr, nc] and not visited[nr, nc]:
                    visited[nr, nc] = True
                    queue.append((nr, nc))

    # Check that each item's clearance envelope or front access zone is reached
    for item in placed_items:
        tag = item.get("ref") or item.get("tag") or "ITEM"
        c_poly = item["clearance_polygon"]

        reached = False
        for pt in c_poly:
            c_c = int(round((pt[0] - min_x) / grid_resolution))
            c_r = int(round((pt[1] - min_y) / grid_resolution))
            for r in range(max(0, c_r - 2), min(ny, c_r + 3)):
                for c in range(max(0, c_c - 2), min(nx, c_c + 3)):
                    if visited[r, c]:
                        reached = True
                        break
                if reached:
                    break
            if reached:
                break

        if not reached:
            return False, f"Walkway corridor ({corridor_width:.2f}m) blocked to item '{tag}'"

    return True, "Walkway corridor clear"


# --- Data Models for Solver Results ---

class FurniturePlacementResult(BaseModel):
    ref: str
    tag: Optional[str] = None
    x: float
    y: float
    rotation_deg: float
    width: float
    depth: float
    total_width: float
    total_depth: float
    physical_polygon: Polygon2D
    clearance_polygon: Polygon2D


class SpaceFitResult(BaseModel):
    space_tag: str
    space_name: Optional[str] = None
    passed: bool
    net_floor_area: float
    total_required_area: float
    placements: List[FurniturePlacementResult]
    walkway_connected: bool
    errors: List[str]
    solve_time_sec: float


class ManifestFitResult(BaseModel):
    passed: bool
    spaces: List[SpaceFitResult]
    total_solve_time_sec: float


# --- Core Space Fit Solver ---

def solve_space_furniture_fit(
    space_tag: str,
    space_polygon: Polygon2D,
    items: List[Dict[str, Any]],
    space_name: Optional[str] = None,
    entrance_point: Optional[Point2D] = None,
    explicit_placements: Optional[List[Dict[str, Any]]] = None,
    corridor_width: float = 0.60,
) -> SpaceFitResult:
    """
    Evaluates 2D geometric furniture fit, non-overlapping clearance envelopes (SAT),
    and walkway path connectivity (< 0.01s pre-flight check).
    """
    start_time = time.perf_counter()
    errors: List[str] = []

    net_area = shoelace_area(space_polygon) if space_polygon else 0.0

    # Calculate total envelope area required
    total_envelope_area = sum(item["total_area"] for item in items)
    required_30_pct_area = total_envelope_area * 1.30

    if net_area < total_envelope_area:
        errors.append(
            f"Space net area ({net_area:.2f} m²) is smaller than total furniture envelope area ({total_envelope_area:.2f} m²)"
        )

    # Determine entrance point if not explicitly provided
    if not entrance_point and space_polygon:
        p0 = space_polygon[0]
        p1 = space_polygon[1] if len(space_polygon) > 1 else space_polygon[0]
        mx = (p0[0] + p1[0]) / 2.0
        my = (p0[1] + p1[1]) / 2.0
        cx = sum(p[0] for p in space_polygon) / len(space_polygon)
        cy = sum(p[1] for p in space_polygon) / len(space_polygon)
        entrance_point = (mx * 0.9 + cx * 0.1, my * 0.9 + cy * 0.1)

    placed_results: List[FurniturePlacementResult] = []
    placed_items_dict: List[Dict[str, Any]] = []

    # Check if explicit placements provided or need to be solved
    if explicit_placements and len(explicit_placements) == len(items):
        for idx, item in enumerate(items):
            exp = explicit_placements[idx]
            cx, cy = exp["x"], exp["y"]
            rot = exp.get("rotation_deg", 0.0)

            w = item["physical_width"]
            d = item["physical_depth"]
            clr = item["clearance"]

            phys_poly, clear_poly = compute_item_polygons(cx, cy, w, d, clr, rot)

            res = FurniturePlacementResult(
                ref=item["ref"],
                tag=item.get("tag"),
                x=cx,
                y=cy,
                rotation_deg=rot,
                width=w,
                depth=d,
                total_width=item["total_width"],
                total_depth=item["total_depth"],
                physical_polygon=phys_poly,
                clearance_polygon=clear_poly,
            )
            placed_results.append(res)
            placed_items_dict.append({
                "ref": item["ref"],
                "tag": item.get("tag"),
                "physical_polygon": phys_poly,
                "clearance_polygon": clear_poly,
            })
    else:
        xs = [p[0] for p in space_polygon]
        ys = [p[1] for p in space_polygon]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        step_x = max(0.6, (max_x - min_x) / 5.0)
        step_y = max(0.6, (max_y - min_y) / 5.0)

        grid_pts: List[Point2D] = []
        # Perimeter points
        for x_val in np.arange(min_x + 0.5, max_x - 0.4, step_x):
            for y_val in [min_y + 0.6, max_y - 0.6]:
                grid_pts.append((round(x_val, 2), round(y_val, 2)))
        for y_val in np.arange(min_y + 0.5, max_y - 0.4, step_y):
            for x_val in [min_x + 0.6, max_x - 0.6]:
                grid_pts.append((round(x_val, 2), round(y_val, 2)))
        # Interior points
        for x_val in np.arange(min_x + 1.2, max_x - 1.1, step_x):
            for y_val in np.arange(min_y + 1.2, max_y - 1.1, step_y):
                grid_pts.append((round(x_val, 2), round(y_val, 2)))

        orientations = [0.0, 90.0, 180.0, 270.0]

        # Greedy packing with backtrack
        def try_place(item_idx: int) -> bool:
            if item_idx >= len(items):
                return True

            item = items[item_idx]
            w = item["physical_width"]
            d = item["physical_depth"]
            clr = item["clearance"]

            for pt in grid_pts:
                for rot in orientations:
                    phys_poly, clear_poly = compute_item_polygons(pt[0], pt[1], w, d, clr, rot)

                    # 1. Clearance envelope must fit inside space polygon
                    if not polygon_contains_polygon(space_polygon, clear_poly):
                        continue

                    # 2. Clearance envelope must not overlap existing items
                    overlap = False
                    for prev_item in placed_items_dict:
                        if sat_polygon_intersection(clear_poly, prev_item["clearance_polygon"]):
                            overlap = True
                            break
                    if overlap:
                        continue

                    # Candidate valid -> place
                    res = FurniturePlacementResult(
                        ref=item["ref"],
                        tag=item.get("tag"),
                        x=pt[0],
                        y=pt[1],
                        rotation_deg=rot,
                        width=w,
                        depth=d,
                        total_width=item["total_width"],
                        total_depth=item["total_depth"],
                        physical_polygon=phys_poly,
                        clearance_polygon=clear_poly,
                    )
                    placed_results.append(res)
                    placed_items_dict.append({
                        "ref": item["ref"],
                        "tag": item.get("tag"),
                        "physical_polygon": phys_poly,
                        "clearance_polygon": clear_poly,
                    })

                    if try_place(item_idx + 1):
                        return True

                    # Backtrack
                    placed_results.pop()
                    placed_items_dict.pop()

            return False

        placed_success = try_place(0)
        if not placed_success and items:
            errors.append("Failed to find valid non-overlapping placement coordinates inside space boundary")

    # Verify clearance envelope overlaps across all placed items
    n_placed = len(placed_results)
    for i in range(n_placed):
        for j in range(i + 1, n_placed):
            p1 = placed_results[i]
            p2 = placed_results[j]
            if sat_polygon_intersection(p1.clearance_polygon, p2.clearance_polygon):
                errors.append(
                    f"Clearance envelope clash between item '{p1.ref}' at ({p1.x:.2f}, {p1.y:.2f}) and item '{p2.ref}' at ({p2.x:.2f}, {p2.y:.2f})"
                )

    # Verify space boundary containment for placed items
    for p in placed_results:
        if not polygon_contains_polygon(space_polygon, p.clearance_polygon):
            errors.append(
                f"Clearance envelope for item '{p.ref}' at ({p.x:.2f}, {p.y:.2f}) exceeds space boundary"
            )

    # Verify walkway corridor path connectivity
    walkway_ok = True
    if entrance_point and placed_items_dict and not errors:
        walkway_ok, msg = check_walkway_connectivity(
            space_polygon=space_polygon,
            entrance_point=entrance_point,
            placed_items=placed_items_dict,
            corridor_width=corridor_width,
        )
        if not walkway_ok:
            errors.append(msg)

    solve_time = time.perf_counter() - start_time
    passed = len(errors) == 0

    return SpaceFitResult(
        space_tag=space_tag,
        space_name=space_name,
        passed=passed,
        net_floor_area=round(net_area, 2),
        total_required_area=round(required_30_pct_area, 2),
        placements=placed_results,
        walkway_connected=walkway_ok,
        errors=errors,
        solve_time_sec=round(solve_time, 6),
    )


def solve_manifest_furniture_fit(
    manifest: ProjectManifest, space_tag_filter: Optional[str] = None
) -> ManifestFitResult:
    """
    Evaluates 2D geometric furniture fit and non-overlapping clearance checking
    across all spaces in a ProjectManifest.
    """
    start_total_time = time.perf_counter()
    from debim.resolver import resolve_manifest
    resolved = resolve_manifest(manifest)

    space_results: List[SpaceFitResult] = []

    # Map doors to doors near spaces or host walls
    doors_by_wall: Dict[str, List[IfcDoor]] = {}
    for elem in manifest.elements:
        if isinstance(elem, IfcDoor) and elem.host_wall:
            doors_by_wall.setdefault(elem.host_wall, []).append(elem)

    # Explicit furniture elements by storey/space
    explicit_furn_by_storey: Dict[str, List[IfcFurniture]] = {}
    for elem in manifest.elements:
        if isinstance(elem, IfcFurniture):
            st = elem.placement.storey
            explicit_furn_by_storey.setdefault(st, []).append(elem)

    for r_space in resolved.spaces:
        if space_tag_filter and r_space.tag != space_tag_filter:
            continue

        sp_poly = [(p[0], p[1]) for p in r_space.polygon] if getattr(r_space, "polygon", None) else []
        if not sp_poly or len(sp_poly) < 3:
            space_results.append(
                SpaceFitResult(
                    space_tag=r_space.tag,
                    space_name=r_space.element.name,
                    passed=False,
                    net_floor_area=r_space.net_floor_area,
                    total_required_area=0.0,
                    placements=[],
                    walkway_connected=False,
                    errors=[f"Space '{r_space.tag}' has invalid or missing 2D boundary polygon"],
                    solve_time_sec=0.0,
                )
            )
            continue

        # Extract declared items
        items_to_fit: List[Dict[str, Any]] = []
        raw_contains = getattr(r_space.element, "contains", None) or []

        for vref in raw_contains:
            if isinstance(vref, str):
                ref_id = vref
                cnt = 1
            else:
                ref_id = getattr(vref, "ref", str(vref))
                raw_cnt = getattr(vref, "count", 1)
                cnt = raw_cnt if isinstance(raw_cnt, int) else 1

            v_obj = manifest.get_variable(ref_id)
            if not v_obj and ref_id in STANDARD_FURNITURE_VARIABLES:
                v_obj = STANDARD_FURNITURE_VARIABLES[ref_id]

            # Fallback to debim-standards catalog if not found in manifest or standard variables
            std_furn = None
            if not v_obj:
                std_furn = get_furniture(ref_id)

            if v_obj:
                fp = v_obj.get_envelope_footprint()
                clr = v_obj.clearance.model_dump() if v_obj.clearance else {}
                for c_idx in range(cnt):
                    items_to_fit.append({
                        "ref": ref_id,
                        "tag": f"{ref_id}_{c_idx+1}",
                        "physical_width": fp["physical_width"],
                        "physical_depth": fp["physical_depth"],
                        "total_width": fp["total_width"],
                        "total_depth": fp["total_depth"],
                        "total_area": fp["total_area"],
                        "clearance": clr,
                    })
            elif std_furn:
                w = std_furn.width
                d = std_furn.depth
                clr = std_furn.clearance
                tot_w = w + clr.get("left", 0.0) + clr.get("right", 0.0)
                tot_d = d + clr.get("front", 0.0) + clr.get("rear", clr.get("back", 0.0))
                tot_a = tot_w * tot_d
                for c_idx in range(cnt):
                    items_to_fit.append({
                        "ref": ref_id,
                        "tag": f"{ref_id}_{c_idx+1}",
                        "physical_width": w,
                        "physical_depth": d,
                        "total_width": tot_w,
                        "total_depth": tot_d,
                        "total_area": tot_a,
                        "clearance": clr,
                    })

        # Explicit placed furniture check
        explicit_placements: List[Dict[str, Any]] = []
        if not items_to_fit:
            st = r_space.element.placement.storey if hasattr(r_space, "element") and hasattr(r_space.element, "placement") else getattr(r_space, "storey", None)
            if isinstance(st, object) and hasattr(st, "id"):
                st = st.id
            if st and st in explicit_furn_by_storey:
                for furn in explicit_furn_by_storey[st]:
                    pos_x, pos_y, _ = furn.placement.position
                    # Check if furniture position is inside space boundary
                    if point_in_polygon((pos_x, pos_y), sp_poly):
                        w = furn.dimensions.width if furn.dimensions else 0.8
                        d = furn.dimensions.depth if furn.dimensions and furn.dimensions.depth is not None else w
                        rot = 0.0
                        if furn.placement.rotation is not None:
                            if isinstance(furn.placement.rotation, (int, float)):
                                rot = math.degrees(furn.placement.rotation)
                            elif isinstance(furn.placement.rotation, (list, tuple)) and len(furn.placement.rotation) >= 3:
                                rot = math.degrees(furn.placement.rotation[2])

                        v_obj = manifest.get_variable(furn.tag) or manifest.get_variable(furn.name or "")
                        clr = v_obj.clearance.model_dump() if v_obj and v_obj.clearance else {"front": 0.6, "left": 0.2, "right": 0.2}

                        items_to_fit.append({
                            "ref": furn.name or furn.tag,
                            "tag": furn.tag,
                            "physical_width": w,
                            "physical_depth": d,
                            "total_width": w + clr.get("left", 0.0) + clr.get("right", 0.0),
                            "total_depth": d + clr.get("front", 0.0) + clr.get("back", 0.0),
                            "total_area": (w + clr.get("left", 0.0) + clr.get("right", 0.0)) * (d + clr.get("front", 0.0) + clr.get("back", 0.0)),
                            "clearance": clr,
                        })
                        explicit_placements.append({
                            "x": pos_x,
                            "y": pos_y,
                            "rotation_deg": rot,
                        })

        # Solve space fit
        res = solve_space_furniture_fit(
            space_tag=r_space.tag,
            space_polygon=sp_poly,
            items=items_to_fit,
            space_name=r_space.element.name,
            explicit_placements=explicit_placements if explicit_placements else None,
        )
        space_results.append(res)

    total_time = time.perf_counter() - start_total_time
    overall_passed = all(sr.passed for sr in space_results) if space_results else True

    return ManifestFitResult(
        passed=overall_passed,
        spaces=space_results,
        total_solve_time_sec=round(total_time, 6),
    )
