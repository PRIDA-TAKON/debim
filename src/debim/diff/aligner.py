"""
debim.diff.aligner

Iterative Closest Point (ICP) fine coordinate alignment between real-world as-built point clouds
and as-planned debim surface geometry.
"""

from typing import Tuple
import numpy as np
from scipy.spatial import cKDTree


def icp_fine_align(
    scan_points: np.ndarray,
    model_surface_points: np.ndarray,
    max_iterations: int = 50,
    tolerance: float = 1e-4,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Computes optimal 4x4 rigid transformation matrix (R, t) to register
    as-built scan points to as-planned debim coordinate origin.

    Args:
        scan_points: (N, 3) float array of source scan point cloud coordinates.
        model_surface_points: (M, 3) float array of target model surface points.
        max_iterations: Maximum number of ICP iterations (default: 50).
        tolerance: Stopping threshold on RMSE change (default: 1e-4).

    Returns:
        Tuple[np.ndarray, np.ndarray, float]:
            - transformed_points: (N, 3) float array of aligned scan points.
            - transformation_matrix: 4x4 float array rigid transformation matrix T.
            - rmse: Root Mean Square Error distance (in meters) after alignment.
    """
    P = np.asarray(scan_points, dtype=np.float64)
    Q = np.asarray(model_surface_points, dtype=np.float64)

    if P.ndim == 1 and P.shape[0] == 3:
        P = P.reshape(1, 3)
    if Q.ndim == 1 and Q.shape[0] == 3:
        Q = Q.reshape(1, 3)

    num_p = P.shape[0] if P.size > 0 else 0
    num_q = Q.shape[0] if Q.size > 0 else 0

    if num_p == 0 or num_q == 0:
        return P, np.eye(4, dtype=np.float64), 0.0

    tree = cKDTree(Q)
    T_total = np.eye(4, dtype=np.float64)
    P_curr = P.copy()

    prev_rmse = float("inf")

    for iteration in range(max_iterations):
        dists, indices = tree.query(P_curr, k=1)
        Q_matched = Q[indices]

        curr_rmse = float(np.sqrt(np.mean(dists ** 2)))

        if abs(prev_rmse - curr_rmse) < tolerance:
            break
        prev_rmse = curr_rmse

        p_centroid = np.mean(P_curr, axis=0)
        q_centroid = np.mean(Q_matched, axis=0)

        p_centered = P_curr - p_centroid
        q_centered = Q_matched - q_centroid

        H = p_centered.T @ q_centered

        U, S, Vt = np.linalg.svd(H)
        R_step = Vt.T @ U.T

        # Reflection check
        if np.linalg.det(R_step) < 0:
            Vt_mod = Vt.copy()
            Vt_mod[2, :] *= -1
            R_step = Vt_mod.T @ U.T

        t_step = q_centroid - R_step @ p_centroid

        T_step = np.eye(4, dtype=np.float64)
        T_step[:3, :3] = R_step
        T_step[:3, 3] = t_step

        P_curr = (P_curr @ R_step.T) + t_step
        T_total = T_step @ T_total

    final_dists, _ = tree.query(P_curr, k=1)
    final_rmse = float(np.sqrt(np.mean(final_dists ** 2)))

    return P_curr, T_total, final_rmse
