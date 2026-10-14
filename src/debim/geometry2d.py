"""
Pure-Python 2D Geometry Engine for debim.
Provides core polygon math functions (Shoelace area, perimeter, polygon inset/offset, point-in-polygon)
without external C/C++ or GIS dependencies like Shapely.
"""

import math
from typing import List, Sequence, Tuple, Union

Point2D = Tuple[float, float]
Point3D = Tuple[float, float, float]
PointAny = Union[Point2D, Point3D]


def _normalize_vertices(vertices: Sequence[PointAny]) -> List[Point2D]:
    """Extracts 2D (x, y) coordinates and removes redundant trailing closure point if present."""
    if not vertices:
        return []
    pts = [(float(v[0]), float(v[1])) for v in vertices]
    if len(pts) > 1 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 1e-9:
        pts.pop()
    return pts


def signed_shoelace_area(vertices: Sequence[PointAny]) -> float:
    """
    Calculates the signed area of a 2D polygon using the Shoelace formula.
    Returns positive value for counter-clockwise (CCW) winding,
    and negative value for clockwise (CW) winding.
    """
    pts = _normalize_vertices(vertices)
    n = len(pts)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return area / 2.0


def shoelace_area(vertices: Sequence[PointAny]) -> float:
    """Calculates the unsigned 2D surface area of a polygon using the Shoelace formula."""
    return abs(signed_shoelace_area(vertices))


def polygon_perimeter(vertices: Sequence[PointAny]) -> float:
    """Calculates the total perimeter length of a 2D polygon."""
    pts = _normalize_vertices(vertices)
    n = len(pts)
    if n < 2:
        return 0.0
    perim = 0.0
    for i in range(n):
        j = (i + 1) % n
        dx = pts[j][0] - pts[i][0]
        dy = pts[j][1] - pts[i][1]
        perim += math.hypot(dx, dy)
    return perim


def point_in_polygon(
    point: PointAny,
    vertices: Sequence[PointAny],
) -> bool:
    """
    Determines whether a 2D point lies inside or on the boundary of a polygon
    using ray casting (crossing number) algorithm.
    """
    pts = _normalize_vertices(vertices)
    n = len(pts)
    if n < 3:
        return False

    px, py = float(point[0]), float(point[1])
    inside = False

    for i in range(n):
        j = (i + 1) % n
        x1, y1 = pts[i]
        x2, y2 = pts[j]

        # Check vertex coincidence
        if (abs(x1 - px) < 1e-9 and abs(y1 - py) < 1e-9) or (abs(x2 - px) < 1e-9 and abs(y2 - py) < 1e-9):
            return True

        # Check edge collinearity
        dx = x2 - x1
        dy = y2 - y1
        if abs(dy) < 1e-9 and abs(y1 - py) < 1e-9:
            if min(x1, x2) - 1e-9 <= px <= max(x1, x2) + 1e-9:
                return True

        # Ray casting horizontal right ray
        if (y1 > py) != (y2 > py):
            x_cross = (x2 - x1) * (py - y1) / (y2 - y1) + x1
            if abs(px - x_cross) < 1e-9:
                return True  # Directly on sloped edge
            if px < x_cross:
                inside = not inside

    return inside


def polygon_inset(
    vertices: Sequence[PointAny],
    offset_distance: float,
) -> List[Point2D]:
    """
    Insets (or outsets) a 2D polygon boundary by `offset_distance`.
    - `offset_distance > 0`: Insets polygon (moves boundary inward toward interior).
    - `offset_distance < 0`: Outsets polygon (expands boundary outward).
    - `offset_distance == 0`: Returns normalized polygon.

    Uses parallel edge line intersections for exact corner offsets.
    """
    pts = _normalize_vertices(vertices)
    n = len(pts)
    if n < 3 or abs(offset_distance) < 1e-9:
        return [(p[0], p[1]) for p in pts]

    s_area = signed_shoelace_area(pts)
    is_ccw = s_area > 0.0

    # Calculate unit edge vectors u_i and inward normal vectors n_i for each edge
    u_vectors: List[Tuple[float, float]] = []
    n_vectors: List[Tuple[float, float]] = []

    for i in range(n):
        j = (i + 1) % n
        dx = pts[j][0] - pts[i][0]
        dy = pts[j][1] - pts[i][1]
        length = math.hypot(dx, dy)
        if length < 1e-9:
            u_vectors.append((1.0, 0.0))
            n_vectors.append((0.0, 1.0))
            continue

        ux = dx / length
        uy = dy / length
        u_vectors.append((ux, uy))

        # Left normal: (-uy, ux).
        # For CCW polygon, left normal points inward.
        # For CW polygon, left normal points outward (so invert to point inward).
        if is_ccw:
            n_vectors.append((-uy, ux))
        else:
            n_vectors.append((uy, -ux))

    # Calculate inset vertices by intersecting adjacent offset edge lines
    inset_pts: List[Point2D] = []
    d = offset_distance

    for i in range(n):
        prev_i = (i - 1) % n

        u_prev = u_vectors[prev_i]
        u_curr = u_vectors[i]

        n_prev = n_vectors[prev_i]
        n_curr = n_vectors[i]

        # Offset line 1 passes through A = P_i + d * n_prev in direction u_prev
        A_x = pts[i][0] + d * n_prev[0]
        A_y = pts[i][1] + d * n_prev[1]

        # Offset line 2 passes through B = P_i + d * n_curr in direction u_curr
        B_x = pts[i][0] + d * n_curr[0]
        B_y = pts[i][1] + d * n_curr[1]

        # Intersection of line 1 (A + t1 * u_prev) and line 2 (B + t2 * u_curr)
        # Cross product denominator D = u_prev_x * u_curr_y - u_prev_y * u_curr_x
        D = u_prev[0] * u_curr[1] - u_prev[1] * u_curr[0]

        if abs(D) < 1e-9:
            # Parallel or collinear edges
            inset_pts.append((A_x, A_y))
        else:
            # Solve for t1
            BA_x = B_x - A_x
            BA_y = B_y - A_y
            t1 = (BA_x * u_curr[1] - BA_y * u_curr[0]) / D

            px = A_x + t1 * u_prev[0]
            py = A_y + t1 * u_prev[1]
            inset_pts.append((round(px, 8), round(py, 8)))

    return inset_pts
