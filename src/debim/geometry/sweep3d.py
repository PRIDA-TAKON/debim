"""
3D Polyline / Spline Curve Sweeper with Rotation Minimizing Frame (RMF / Bishop Frame).
Provides gimbal-flip-free 3D coordinate frame transport along 3D waypoints and sweeps
2D road/pavement cross-sections into watertight 3D solid triangle meshes.
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union


def _vec_norm(v: Tuple[float, float, float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _normalize(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    length = _vec_norm(v)
    if length < 1e-12:
        return (1.0, 0.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def _dot(u: Tuple[float, float, float], v: Tuple[float, float, float]) -> float:
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def _cross(u: Tuple[float, float, float], v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )


def _add(u: Tuple[float, float, float], v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (u[0] + v[0], u[1] + v[1], u[2] + v[2])


def _sub(u: Tuple[float, float, float], v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (u[0] - v[0], u[1] - v[1], u[2] - v[2])


def _scale(v: Tuple[float, float, float], s: float) -> Tuple[float, float, float]:
    return (v[0] * s, v[1] * s, v[2] * s)


def compute_rmf_frames(points: List[Tuple[float, float, float]]) -> List[Dict[str, Any]]:
    """
    Computes Rotation Minimizing Frames (RMF / Bishop Frames) along a 3D path.
    Uses double reflection algorithm (Wang et al. 2008) to guarantee smooth
    frame transport without artificial twisting or gimbal flips even on steep slopes.

    Returns a list of dicts with keys:
      'station': float
      'position': (x, y, z)
      'tangent': (Tx, Ty, Tz)
      'normal': (Nx, Ny, Nz)
      'binormal': (Bx, By, Bz)
    """
    if not points or len(points) < 2:
        if not points:
            return []
        p = points[0]
        return [{
            "station": 0.0,
            "position": p,
            "tangent": (1.0, 0.0, 0.0),
            "normal": (0.0, 1.0, 0.0),
            "binormal": (0.0, 0.0, 1.0),
        }]

    n_pts = len(points)

    # 1. Compute tangents at each point
    tangents: List[Tuple[float, float, float]] = []
    stations: List[float] = [0.0]

    for i in range(n_pts - 1):
        p1 = points[i]
        p2 = points[i + 1]
        v = _sub(p2, p1)
        dist = _vec_norm(v)
        stations.append(stations[-1] + dist)

    for i in range(n_pts):
        if i == 0:
            t = _normalize(_sub(points[1], points[0]))
        elif i == n_pts - 1:
            t = _normalize(_sub(points[-1], points[-2]))
        else:
            v1 = _normalize(_sub(points[i], points[i - 1]))
            v2 = _normalize(_sub(points[i + 1], points[i]))
            t = _normalize(_add(v1, v2))
        tangents.append(t)

    # 2. Initial frame at point 0
    t0 = tangents[0]
    if abs(t0[2]) > 0.9:
        ref = (1.0, 0.0, 0.0)
    else:
        ref = (0.0, 0.0, 1.0)

    n0 = _normalize(_cross(ref, t0))
    b0 = _normalize(_cross(t0, n0))

    frames: List[Dict[str, Any]] = [{
        "station": stations[0],
        "position": points[0],
        "tangent": t0,
        "normal": n0,
        "binormal": b0,
    }]

    # 3. Propagate frames using Double Reflection
    for i in range(n_pts - 1):
        p_i = points[i]
        p_next = points[i + 1]

        t_i = frames[i]["tangent"]
        n_i = frames[i]["normal"]

        t_next = tangents[i + 1]

        # Reflection 1: Reflect frame at p_i to p_next
        v1 = _sub(p_next, p_i)
        c1 = _dot(v1, v1)

        if c1 > 1e-12:
            t_i_L = _sub(t_i, _scale(v1, 2.0 * _dot(v1, t_i) / c1))
            n_i_L = _sub(n_i, _scale(v1, 2.0 * _dot(v1, n_i) / c1))
        else:
            t_i_L = t_i
            n_i_L = n_i

        # Reflection 2: Reflect t_i_L to t_next
        v2 = _sub(t_next, t_i_L)
        c2 = _dot(v2, v2)

        if c2 > 1e-12:
            n_next = _sub(n_i_L, _scale(v2, 2.0 * _dot(v2, n_i_L) / c2))
        else:
            n_next = n_i_L

        # Ensure orthogonality: n_next = n_next - (n_next . t_next) * t_next
        n_next = _sub(n_next, _scale(t_next, _dot(n_next, t_next)))
        n_next = _normalize(n_next)
        b_next = _normalize(_cross(t_next, n_next))

        frames.append({
            "station": stations[i + 1],
            "position": p_next,
            "tangent": t_next,
            "normal": n_next,
            "binormal": b_next,
        })

    return frames


def create_road_camber_profile(
    width: float = 7.00,
    thickness: float = 0.20,
    camber_slope: float = 0.02,
) -> List[Tuple[float, float]]:
    """
    Generates a 2D crowned carriageway cross-section profile with camber slope (default 2%).
    Local u-axis is lateral width (-W/2 to +W/2), v-axis is vertical elevation offset.

    Returns a closed polygon of 2D (u, v) points in CCW order:
      1. Center top crown (0.0, 0.0)
      2. Right edge top (+W/2, -W/2 * camber)
      3. Right edge bottom (+W/2, -W/2 * camber - thickness)
      4. Center bottom (0.0, -thickness)
      5. Left edge bottom (-W/2, -W/2 * camber - thickness)
      6. Left edge top (-W/2, -W/2 * camber)
    """
    half_w = width / 2.0
    camber_drop = half_w * camber_slope

    return [
        (0.0, 0.0),
        (half_w, -camber_drop),
        (half_w, -camber_drop - thickness),
        (0.0, -thickness),
        (-half_w, -camber_drop - thickness),
        (-half_w, -camber_drop),
    ]


def sweep_cross_section_rmf(
    profile_points: List[Tuple[float, float]],
    frames: List[Dict[str, Any]],
    one_based: bool = False,
) -> Dict[str, Any]:
    """
    Sweeps a 2D cross-section profile along 3D RMF coordinate frames into a 3D solid mesh.

    Parameters:
      profile_points: List of (u, v) local 2D offsets
      frames: List of RMF frame dicts from compute_rmf_frames
      one_based: If True, returns 1-based face indices for IFC, else 0-based

    Returns dict with:
      'vertices': List[Tuple[float, float, float]]
      'faces': List[Tuple[int, int, int]]
    """
    if not profile_points or len(profile_points) < 3 or not frames:
        return {"vertices": [], "faces": []}

    n_verts_per_frame = len(profile_points)
    n_frames = len(frames)

    mesh_vertices: List[Tuple[float, float, float]] = []

    # 1. Generate 3D vertices across all frames
    for frame in frames:
        px, py, pz = frame["position"]
        Nx, Ny, Nz = frame["normal"]
        Bx, By, Bz = frame["binormal"]

        for u, v in profile_points:
            vx = px + u * Nx + v * Bx
            vy = py + u * Ny + v * By
            vz = pz + u * Nz + v * Bz
            mesh_vertices.append((round(vx, 6), round(vy, 6), round(vz, 6)))

    offset = 1 if one_based else 0
    face_indices: List[Tuple[int, int, int]] = []

    # 2. Generate side quad faces (split into 2 triangles) along frames
    for k in range(n_frames - 1):
        base_curr = k * n_verts_per_frame
        base_next = (k + 1) * n_verts_per_frame

        for i in range(n_verts_per_frame):
            i_next = (i + 1) % n_verts_per_frame

            v1 = base_curr + i + offset
            v2 = base_curr + i_next + offset
            v3 = base_next + i_next + offset
            v4 = base_next + i + offset

            # Triangle 1: (v1, v2, v3), Triangle 2: (v1, v3, v4)
            face_indices.append((v1, v2, v3))
            face_indices.append((v1, v3, v4))

    # 3. Start cap (frame 0) - reversed orientation
    start_base = offset
    for i in range(1, n_verts_per_frame - 1):
        face_indices.append((
            start_base,
            start_base + i + 1,
            start_base + i,
        ))

    # 4. End cap (frame N-1) - forward orientation
    end_base = (n_frames - 1) * n_verts_per_frame + offset
    for i in range(1, n_verts_per_frame - 1):
        face_indices.append((
            end_base,
            end_base + i,
            end_base + i + 1,
        ))

    return {
        "vertices": mesh_vertices,
        "faces": face_indices,
    }
