"""
debim.diff.distance

Ultra-fast vectorized distance calculation engine between real-world 3D point clouds (.ply)
and compiled debim geometry/mesh (As-planned).
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy.spatial import cKDTree

from debim.compliance import get_element_aabb
from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedCustomElement,
    ResolvedDoor,
    ResolvedElement,
    ResolvedFooting,
    ResolvedMember,
    ResolvedRoof,
    ResolvedSlab,
    ResolvedStair,
    ResolvedStairFlight,
    ResolvedWall,
    ResolvedWindow,
)
from debim.sync.detector import DeviationResult, ElementDeviation


def compute_point_to_plane_distance(
    points: np.ndarray,
    plane_origin: np.ndarray,
    plane_normal: np.ndarray,
) -> np.ndarray:
    """
    Compute signed perpendicular distance from 3D points to a plane.

    Args:
        points: (N, 3) float array of 3D point coordinates.
        plane_origin: (3,) or (1, 3) float array representing a point on the plane.
        plane_normal: (3,) float array representing the normal vector of the plane.

    Returns:
        1D np.ndarray of shape (N,) containing signed distances.
        Positive distances indicate points on the side of the normal vector;
        negative distances indicate points on the opposite side.
    """
    pts = np.asarray(points, dtype=np.float64)
    if pts.size == 0 or pts.shape[0] == 0:
        return np.empty((0,), dtype=np.float64)

    if pts.ndim == 1 and pts.shape[0] == 3:
        pts = pts.reshape(1, 3)

    origin = np.asarray(plane_origin, dtype=np.float64).reshape(-1)
    normal = np.asarray(plane_normal, dtype=np.float64).reshape(-1)

    norm_val = np.linalg.norm(normal)
    if norm_val > 1e-12:
        unit_normal = normal / norm_val
    else:
        unit_normal = normal

    diff = pts - origin
    signed_dists = np.dot(diff, unit_normal)
    return signed_dists


def _point_triangle_distance_batch(
    pts: np.ndarray,
    tri_a: np.ndarray,
    tri_b: np.ndarray,
    tri_c: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Vectorized calculation of distance from points pts (M, 3) to corresponding triangles (M, 3).
    Returns (distances, closest_points).
    """
    u = tri_b - tri_a
    w = tri_c - tri_a
    n = np.cross(u, w)
    n_norm_sq = np.sum(n * n, axis=1)

    valid_mask = n_norm_sq > 1e-12

    pa = pts - tri_a
    dot_n = np.sum(pa * n, axis=1)

    # Projection onto triangle plane
    proj = pts - (dot_n / np.where(valid_mask, n_norm_sq, 1.0))[:, None] * n

    # Barycentric system
    uu = np.sum(u * u, axis=1)
    uv = np.sum(u * w, axis=1)
    vv = np.sum(w * w, axis=1)

    p_proj_a = proj - tri_a
    wu = np.sum(p_proj_a * u, axis=1)
    wv = np.sum(p_proj_a * w, axis=1)

    denom = uu * vv - uv * uv
    denom_valid = np.abs(denom) > 1e-12

    r = (vv * wu - uv * wv) / np.where(denom_valid, denom, 1.0)
    s = (uu * wv - uv * wu) / np.where(denom_valid, denom, 1.0)

    inside = valid_mask & denom_valid & (r >= 0.0) & (s >= 0.0) & (r + s <= 1.0)

    # Boundary segment projections
    def closest_on_seg(p, a, b):
        ab = b - a
        ab_sq = np.sum(ab * ab, axis=1)
        t = np.clip(
            np.sum((p - a) * ab, axis=1) / np.where(ab_sq > 1e-12, ab_sq, 1.0),
            0.0,
            1.0,
        )
        return a + t[:, None] * ab

    p_ab = closest_on_seg(pts, tri_a, tri_b)
    p_bc = closest_on_seg(pts, tri_b, tri_c)
    p_ca = closest_on_seg(pts, tri_c, tri_a)

    d_ab = np.linalg.norm(pts - p_ab, axis=1)
    d_bc = np.linalg.norm(pts - p_bc, axis=1)
    d_ca = np.linalg.norm(pts - p_ca, axis=1)

    closest_pts = np.where(d_ab[:, None] < d_bc[:, None], p_ab, p_bc)
    min_seg_d = np.minimum(d_ab, d_bc)

    closest_pts = np.where(d_ca[:, None] < min_seg_d[:, None], p_ca, closest_pts)

    final_closest = np.where(inside[:, None], proj, closest_pts)
    final_d = np.linalg.norm(pts - final_closest, axis=1)

    return final_d, final_closest


def compute_point_to_mesh_distance(
    points: np.ndarray,
    vertices: np.ndarray,
    faces: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute minimum distance from 3D points to a polygonal triangle mesh.

    Args:
        points: (N, 3) float array of 3D point coordinates.
        vertices: (V, 3) float array of mesh vertices.
        faces: (F, 3) int array of triangle face indices (0-based).

    Returns:
        Tuple[np.ndarray, np.ndarray]:
            - distances: 1D np.ndarray of shape (N,) containing unsigned distances to closest mesh face.
            - closest_points: 2D np.ndarray of shape (N, 3) containing 3D coordinates on mesh.
    """
    pts = np.asarray(points, dtype=np.float64)
    verts = np.asarray(vertices, dtype=np.float64)
    fcs = np.asarray(faces, dtype=np.int32)

    N = pts.shape[0] if pts.ndim == 2 else 0
    if N == 0 or verts.size == 0 or fcs.size == 0:
        return np.empty((0,), dtype=np.float64), np.empty((0, 3), dtype=np.float64)

    # Normalize face indices to 0-based if necessary
    if np.min(fcs) >= 1:
        fcs = fcs - 1

    F = fcs.shape[0]
    tri_a = verts[fcs[:, 0]]
    tri_b = verts[fcs[:, 1]]
    tri_c = verts[fcs[:, 2]]

    # Triangles centroids
    centroids = (tri_a + tri_b + tri_c) / 3.0

    if F <= 32:
        # Evaluate against all faces directly for small meshes
        min_dists = np.full(N, np.inf, dtype=np.float64)
        best_closest = np.zeros((N, 3), dtype=np.float64)

        for f_idx in range(F):
            a_idx = np.tile(tri_a[f_idx], (N, 1))
            b_idx = np.tile(tri_b[f_idx], (N, 1))
            c_idx = np.tile(tri_c[f_idx], (N, 1))

            d_f, cp_f = _point_triangle_distance_batch(pts, a_idx, b_idx, c_idx)
            closer = d_f < min_dists
            min_dists[closer] = d_f[closer]
            best_closest[closer] = cp_f[closer]

        return min_dists, best_closest

    # KDTree candidate filtering for larger meshes
    tree = cKDTree(centroids)
    k = min(F, 16)
    _, candidate_idxs = tree.query(pts, k=k)

    if k == 1:
        candidate_idxs = candidate_idxs[:, None]

    min_dists = np.full(N, np.inf, dtype=np.float64)
    best_closest = np.zeros((N, 3), dtype=np.float64)

    for i in range(k):
        f_idxs = candidate_idxs[:, i]
        a_idx = tri_a[f_idxs]
        b_idx = tri_b[f_idxs]
        c_idx = tri_c[f_idxs]

        d_i, cp_i = _point_triangle_distance_batch(pts, a_idx, b_idx, c_idx)
        closer = d_i < min_dists
        min_dists[closer] = d_i[closer]
        best_closest[closer] = cp_i[closer]

    return min_dists, best_closest


def _build_box_mesh(
    origin: Tuple[float, float, float],
    u_vec: Tuple[float, float, float],
    v_vec: Tuple[float, float, float],
    w_vec: Tuple[float, float, float],
    len_u: float,
    len_v: float,
    len_w: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Builds a 3D box mesh (8 vertices, 12 triangles) from origin and 3 orthogonal basis vectors."""
    u = np.array(u_vec, dtype=np.float64) / (np.linalg.norm(u_vec) or 1.0)
    v = np.array(v_vec, dtype=np.float64) / (np.linalg.norm(v_vec) or 1.0)
    w = np.array(w_vec, dtype=np.float64) / (np.linalg.norm(w_vec) or 1.0)
    o = np.array(origin, dtype=np.float64)

    verts = np.zeros((8, 3), dtype=np.float64)
    idx = 0
    for iu in [0.0, len_u]:
        for iv in [-len_v / 2.0, len_v / 2.0]:
            for iw in [0.0, len_w]:
                verts[idx] = o + iu * u + iv * v + iw * w
                idx += 1

    # Re-order vertices cleanly for standard 3D box faces
    # Standard 8 corners:
    # 0: (0, -v/2, 0), 1: (0, -v/2, w), 2: (0, +v/2, 0), 3: (0, +v/2, w)
    # 4: (u, -v/2, 0), 5: (u, -v/2, w), 6: (u, +v/2, 0), 7: (u, +v/2, w)
    c0 = o - (len_v / 2.0) * v
    c1 = o + (len_v / 2.0) * v
    verts = np.array([
        c0,
        c0 + len_w * w,
        c1,
        c1 + len_w * w,
        c0 + len_u * u,
        c0 + len_u * u + len_w * w,
        c1 + len_u * u,
        c1 + len_u * u + len_w * w,
    ], dtype=np.float64)

    faces = np.array([
        # Bottom (-Z)
        [0, 2, 6], [0, 6, 4],
        # Top (+Z)
        [1, 5, 7], [1, 7, 3],
        # Front (-Y)
        [0, 4, 5], [0, 5, 1],
        # Back (+Y)
        [2, 3, 7], [2, 7, 6],
        # Left (-X)
        [0, 1, 3], [0, 3, 2],
        # Right (+X)
        [4, 6, 7], [4, 7, 5],
    ], dtype=np.int32)

    return verts, faces


def get_element_mesh(elem: ResolvedElement) -> Tuple[np.ndarray, np.ndarray]:
    """
    Construct or extract 3D surface mesh (vertices, faces) for any resolved BIM element.
    """
    if hasattr(elem, "mesh") and isinstance(elem.mesh, dict) and "vertices" in elem.mesh and "faces" in elem.mesh:
        return np.asarray(elem.mesh["vertices"], dtype=np.float64), np.asarray(elem.mesh["faces"], dtype=np.int32)

    if hasattr(elem, "swept_mesh") and isinstance(elem.swept_mesh, dict) and "vertices" in elem.swept_mesh and "faces" in elem.swept_mesh:
        return np.asarray(elem.swept_mesh["vertices"], dtype=np.float64), np.asarray(elem.swept_mesh["faces"], dtype=np.int32)

    if isinstance(elem, ResolvedWall):
        x1, y1, z = elem.start_point
        x2, y2, _ = elem.end_point
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 1e-6:
            dx, dy, length = 1.0, 0.0, 1.0
        u = (dx / length, dy / length, 0.0)
        v = (-u[1], u[0], 0.0)
        w = (0.0, 0.0, 1.0)
        return _build_box_mesh((x1, y1, z), u, v, w, length, elem.thickness, elem.height)

    if isinstance(elem, ResolvedColumn):
        x, y, z1 = elem.start_point[0], elem.start_point[1], elem.start_point[2]
        z2 = elem.end_point[2]
        min_z, max_z = min(z1, z2), max(z1, z2)
        h = max_z - min_z or 3.0
        w_val = getattr(elem, "width", getattr(getattr(elem, "element", None), "profile", None) and getattr(elem.element.profile, "width", 0.3) or 0.3)
        d_val = getattr(elem, "depth", getattr(getattr(elem, "element", None), "profile", None) and getattr(elem.element.profile, "depth", 0.3) or 0.3)
        origin = (x - w_val / 2.0, y, min_z)
        return _build_box_mesh(origin, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), w_val, d_val, h)

    if isinstance(elem, (ResolvedBeam, ResolvedMember)):
        x1, y1, z1 = elem.start_point
        x2, y2, z2 = elem.end_point
        dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
        length = math.hypot(dx, dy, dz)
        if length < 1e-6:
            dx, dy, length = 1.0, 0.0, 1.0
        u = (dx / length, dy / length, dz / length)
        v = (-u[1], u[0], 0.0)
        norm_v = math.hypot(v[0], v[1])
        if norm_v < 1e-6:
            v = (0.0, 1.0, 0.0)
        else:
            v = (v[0] / norm_v, v[1] / norm_v, 0.0)
        w = (0.0, 0.0, 1.0)
        w_val = getattr(elem, "width", 0.2)
        d_val = getattr(elem, "depth", 0.4)
        origin = (x1, y1, z1 - d_val)
        return _build_box_mesh(origin, u, v, w, length, w_val, d_val)

    if isinstance(elem, ResolvedFooting):
        x, y, z = elem.position
        w_val = elem.width
        d_val = elem.depth
        t_val = elem.thickness
        origin = (x - w_val / 2.0, y, z - t_val)
        return _build_box_mesh(origin, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), w_val, d_val, t_val)

    if isinstance(elem, (ResolvedDoor, ResolvedWindow)):
        x, y, z = elem.position
        w_val = elem.width
        h_val = elem.height
        t_val = 0.10
        origin = (x - w_val / 2.0, y, z)
        return _build_box_mesh(origin, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), w_val, t_val, h_val)

    if isinstance(elem, ResolvedSlab):
        poly = elem.polygon
        if poly and len(poly) >= 3:
            zs = [p[2] for p in poly]
            base_z = min(zs)
            t_val = elem.thickness
            top_z = base_z
            bot_z = base_z - t_val

            n_pts = len(poly)
            verts = []
            for p in poly:
                verts.append([p[0], p[1], bot_z])
            for p in poly:
                verts.append([p[0], p[1], top_z])

            faces = []
            # Side faces
            for i in range(n_pts):
                nxt = (i + 1) % n_pts
                b1, b2 = i, nxt
                t1, t2 = i + n_pts, nxt + n_pts
                faces.append([b1, b2, t2])
                faces.append([b1, t2, t1])

            # Top & Bottom fan triangulation
            for i in range(1, n_pts - 1):
                faces.append([0, i + 1, i])
                faces.append([n_pts, n_pts + i, n_pts + i + 1])

            return np.array(verts, dtype=np.float64), np.array(faces, dtype=np.int32)

    # General AABB fallback box
    min_x, min_y, min_z, max_x, max_y, max_z = get_element_aabb(elem)
    len_x = max(max_x - min_x, 0.1)
    len_y = max(max_y - min_y, 0.1)
    len_z = max(max_z - min_z, 0.1)
    origin = (min_x, min_y + len_y / 2.0, min_z)
    return _build_box_mesh(origin, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), len_x, len_y, len_z)


def calculate_element_deviations(
    scan_points: np.ndarray,
    elements: List[ResolvedElement],
) -> DeviationResult:
    """
    Computes signed deviation (mm) and absolute error per architectural/structural element
    between real-world 3D scan point cloud and compiled model geometry.

    Args:
        scan_points: (N, 3) float array of 3D point cloud scan coordinates.
        elements: List of resolved BIM model elements.

    Returns:
        DeviationResult containing per-element ElementDeviation list and metadata summary.
    """
    pts = np.asarray(scan_points, dtype=np.float64)
    if pts.ndim == 1 and pts.shape[0] == 3:
        pts = pts.reshape(1, 3)

    num_scan_points = pts.shape[0] if pts.size > 0 else 0

    deviations: List[ElementDeviation] = []

    for elem in elements:
        tag = getattr(elem, "tag", None) or getattr(elem, "id", None) or "UNKNOWN"
        elem_cls = getattr(elem, "element_class", None) or type(elem).__name__.replace("Resolved", "Ifc")

        # Get element AABB bounding box expanded by tolerance margin
        min_x, min_y, min_z, max_x, max_y, max_z = get_element_aabb(elem)
        margin = 0.25  # 250mm bounding box expansion
        b_min = np.array([min_x - margin, min_y - margin, min_z - margin])
        b_max = np.array([max_x + margin, max_y + margin, max_z + margin])

        if num_scan_points > 0:
            mask = np.all((pts >= b_min) & (pts <= b_max), axis=1)
            pts_sub = pts[mask]
        else:
            pts_sub = np.empty((0, 3), dtype=np.float64)

        sub_count = pts_sub.shape[0]

        if sub_count == 0:
            # Element has no scan points nearby
            curr_pos = (
                getattr(elem, "start_point", None)
                or getattr(elem, "center", None)
                or getattr(elem, "position", None)
            )
            meas_pos = tuple(round(p, 4) for p in curr_pos) if curr_pos and len(curr_pos) >= 3 else None
            deviations.append(
                ElementDeviation(
                    tag=tag,
                    measured_position=meas_pos,
                    delta_x=0.0,
                    delta_y=0.0,
                    delta_z=0.0,
                    mean_deviation_mm=0.0,
                    signed_deviation_mm=0.0,
                    absolute_error_mm=0.0,
                    rms_error_mm=0.0,
                    max_error_mm=0.0,
                    point_count=0,
                )
            )
            continue

        # Build surface mesh for element
        verts, faces = get_element_mesh(elem)

        # Distance computation
        dists, closest_pts = compute_point_to_mesh_distance(pts_sub, verts, faces)

        # Signed distance calculation relative to element centroid / normal
        elem_center = (
            (min_x + max_x) / 2.0,
            (min_y + max_y) / 2.0,
            (min_z + max_z) / 2.0,
        )
        vec_out = closest_pts - elem_center
        norm_out = np.linalg.norm(vec_out, axis=1)
        safe_norm = np.where(norm_out[:, None] > 1e-6, norm_out[:, None], 1.0)
        unit_out = np.where(norm_out[:, None] > 1e-6, vec_out / safe_norm, 0.0)

        vec_diff = pts_sub - closest_pts
        dot_out = np.sum(vec_diff * unit_out, axis=1)
        signs = np.where(dot_out >= 0.0, 1.0, -1.0)
        signed_dists = dists * signs

        # Statistical metrics in mm
        mean_signed_mm = float(np.mean(signed_dists)) * 1000.0
        abs_err_mm = float(np.mean(dists)) * 1000.0
        rms_err_mm = float(np.sqrt(np.mean(dists ** 2))) * 1000.0
        max_err_mm = float(np.max(dists)) * 1000.0

        # Mean spatial shifts along X, Y, Z in meters
        dx_m = float(np.mean(pts_sub[:, 0] - closest_pts[:, 0]))
        dy_m = float(np.mean(pts_sub[:, 1] - closest_pts[:, 1]))
        dz_m = float(np.mean(pts_sub[:, 2] - closest_pts[:, 2]))

        curr_pos = (
            getattr(elem, "start_point", None)
            or getattr(elem, "center", None)
            or getattr(elem, "position", None)
        )
        if curr_pos and len(curr_pos) >= 3:
            meas_pos = (
                round(curr_pos[0] + dx_m, 4),
                round(curr_pos[1] + dy_m, 4),
                round(curr_pos[2] + dz_m, 4),
            )
        else:
            meas_pos = None

        deviations.append(
            ElementDeviation(
                tag=tag,
                measured_position=meas_pos,
                delta_x=round(dx_m, 4),
                delta_y=round(dy_m, 4),
                delta_z=round(dz_m, 4),
                mean_deviation_mm=round(mean_signed_mm, 2),
                signed_deviation_mm=round(mean_signed_mm, 2),
                absolute_error_mm=round(abs_err_mm, 2),
                rms_error_mm=round(rms_err_mm, 2),
                max_error_mm=round(max_err_mm, 2),
                point_count=sub_count,
            )
        )

    return DeviationResult(
        deviations=deviations,
        metadata={
            "total_scan_points": num_scan_points,
            "elements_evaluated": len(deviations),
        },
    )
