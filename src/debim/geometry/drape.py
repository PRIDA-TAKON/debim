"""
Terrain Auto-Drape Engine for Roads, Pathways, and Alignments.
Projects 2D/3D horizontal waypoints onto TIN terrain surface meshes using vertical
ray-casting / barycentric elevation lookup with configurable vertical offset and
dense polyline subdivision.
"""

import math
from typing import Any, List, Optional, Tuple


def subdivide_polyline(
    points: List[Tuple[float, float, float]],
    max_step_size: float = 2.0,
) -> List[Tuple[float, float, float]]:
    """
    Subdivides long polyline segments so that draped paths densely sample undulating terrain.
    """
    if not points or len(points) < 2 or max_step_size <= 0:
        return list(points) if points else []

    subdivided: List[Tuple[float, float, float]] = [points[0]]

    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i + 1]

        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        dz = p2[2] - p1[2]
        dist_2d = math.hypot(dx, dy)

        if dist_2d > max_step_size:
            n_steps = int(math.ceil(dist_2d / max_step_size))
            for k in range(1, n_steps):
                t = k / float(n_steps)
                sx = p1[0] + t * dx
                sy = p1[1] + t * dy
                sz = p1[2] + t * dz
                subdivided.append((round(sx, 6), round(sy, 6), round(sz, 6)))

        subdivided.append(p2)

    return subdivided


def drape_points_to_terrain(
    points: List[Tuple[float, float, float]],
    terrain_mesh: Any,
    offset_z: float = 0.05,
    max_step_size: float = 2.0,
) -> List[Tuple[float, float, float]]:
    """
    Projects 3D waypoints onto an underlying TIN terrain mesh using vertical elevation lookups.

    Parameters:
      points: List of 3D waypoints (x, y, z)
      terrain_mesh: TerrainMesh object with `get_elevation_at(x, y)` method
      offset_z: Vertical elevation offset to apply above terrain (default: 0.05m)
      max_step_size: Maximum segment length for polyline subdivision (default: 2.0m)

    Returns:
      List of draped 3D points (x, y, z_terrain + offset_z)
    """
    if not points:
        return []

    # Subdivide long polyline segments for accurate terrain contouring
    dense_points = subdivide_polyline(points, max_step_size=max_step_size)

    draped_points: List[Tuple[float, float, float]] = []

    for px, py, pz_orig in dense_points:
        if terrain_mesh is not None and hasattr(terrain_mesh, "get_elevation_at"):
            z_terrain = terrain_mesh.get_elevation_at(px, py, default=pz_orig)
            z_draped = z_terrain + offset_z
        else:
            z_draped = pz_orig + offset_z

        draped_points.append((round(px, 6), round(py, 6), round(z_draped, 6)))

    return draped_points
