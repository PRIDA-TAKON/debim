"""
debim.scan.wall_extractor

Vectorized 2D RANSAC wall centerline extractor, Manhattan 90-degree
orthogonal rectifier, corner snapping, and topological loop closure.
"""

from dataclasses import dataclass, field
import math
import numpy as np


@dataclass
class ExtractedWall:
    """
    Extracted wall representation with centerline endpoints, thickness, height,
    angle, and 2D bounding polygon vertices.
    """
    start_point: tuple[float, float]
    end_point: tuple[float, float]
    thickness: float = 0.15
    height: float = 2.80
    polygon: list[tuple[float, float]] = field(default_factory=list)
    angle_deg: float = 0.0

    @property
    def length(self) -> float:
        dx = self.end_point[0] - self.start_point[0]
        dy = self.end_point[1] - self.start_point[1]
        return float(math.hypot(dx, dy))

    @property
    def centerline(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return (self.start_point, self.end_point)


@dataclass
class WallExtractionResult:
    """
    Container for extracted walls and topologically closed room loop polygons.
    """
    walls: list[ExtractedWall]
    closed_polygons: list[list[tuple[float, float]]]
    num_walls: int


def line_line_intersection_2d(
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    p4: tuple[float, float],
) -> tuple[float, float] | None:
    """
    Computes 2D infinite line intersection between line (p1, p2) and line (p3, p4).
    Returns None if lines are parallel or coincident.
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-7:
        return None  # Parallel or collinear

    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
    return (float(px), float(py))


def fit_lines_2d_ransac(
    points_2d: np.ndarray,
    distance_threshold: float = 0.05,
    min_inliers: int = 15,
    max_iterations: int = 1000,
    min_length: float = 0.30,
    max_lines: int = 50,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """
    Vectorized 2D RANSAC line fitting across 2D point cloud slice.

    Repeatedly fits 2D line segments through dense point clusters using RANSAC and SVD refinement,
    removing inliers after each line fit until remaining points are exhausted.

    Returns:
        List of line segments represented as ((x1, y1), (x2, y2)).
    """
    if len(points_2d) < 2:
        return []

    pts = points_2d.copy().astype(np.float64)
    line_segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    rng = np.random.default_rng(42)

    while len(pts) >= max(2, min_inliers) and len(line_segments) < max_lines:
        n_pts = len(pts)
        best_inliers = np.array([], dtype=int)

        # RANSAC sampling loop
        iters = min(max_iterations, max(100, n_pts * 5))
        for _ in range(iters):
            idx = rng.choice(n_pts, size=2, replace=False)
            p1, p2 = pts[idx[0]], pts[idx[1]]
            v = p2 - p1
            norm_v = np.linalg.norm(v)
            if norm_v < 1e-6:
                continue

            # Unit normal vector n = (-vy, vx) / norm
            n = np.array([-v[1], v[0]]) / norm_v
            d = -np.dot(n, p1)

            # Vectorized distance computation from all points to line
            dists = np.abs(np.dot(pts, n) + d)
            inliers = np.where(dists < distance_threshold)[0]

            if len(inliers) > len(best_inliers):
                best_inliers = inliers

        if len(best_inliers) < min_inliers:
            break

        # SVD / PCA refinement on inliers
        inlier_pts = pts[best_inliers]
        centroid = np.mean(inlier_pts, axis=0)
        centered = inlier_pts - centroid
        _, _, vh = np.linalg.svd(centered)
        dir_vector = vh[0, :]  # Principal component direction
        norm_dir = np.linalg.norm(dir_vector)
        if norm_dir > 1e-6:
            dir_vector = dir_vector / norm_dir

        # Project inliers onto direction vector
        projections = np.dot(centered, dir_vector)
        t_min, t_max = np.min(projections), np.max(projections)
        seg_length = t_max - t_min

        if seg_length >= min_length:
            p_start = centroid + t_min * dir_vector
            p_end = centroid + t_max * dir_vector
            p1_tuple = (float(p_start[0]), float(p_start[1]))
            p2_tuple = (float(p_end[0]), float(p_end[1]))
            line_segments.append((p1_tuple, p2_tuple))

        # Remove inliers from point cloud pool
        pts = np.delete(pts, best_inliers, axis=0)

    return line_segments


def rectify_manhattan(
    line_segments: list[tuple[tuple[float, float], tuple[float, float]]],
    dominant_angles: tuple[float, ...] = (0.0, 90.0, 45.0, 135.0),
    auto_grid_offset: bool = False,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """
    Aligns 2D line segments to dominant Manhattan orthogonal grid angles (0°, 90°, 45°, 135°).

    If auto_grid_offset is True, identifies dominant orientation grid offset theta_0 from segment angles.
    Otherwise, snaps each line segment directly to the closest angle in dominant_angles while preserving
    its centroid and length.
    """
    if not line_segments:
        return []

    rectified: list[tuple[tuple[float, float], tuple[float, float]]] = []

    if auto_grid_offset and len(line_segments) > 0:
        angles_rad = []
        lengths = []
        for p1, p2 in line_segments:
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            length = math.hypot(dx, dy)
            if length < 1e-6:
                continue
            angle = math.atan2(dy, dx) % math.pi
            angles_rad.append(angle)
            lengths.append(length)

        if angles_rad:
            angles_mod90 = [a % (math.pi / 2.0) for a in angles_rad]
            weights = np.array(lengths)
            counts, bin_edges = np.histogram(angles_mod90, bins=18, range=(0.0, math.pi / 2.0), weights=weights)
            best_bin = int(np.argmax(counts))
            theta_0 = float((bin_edges[best_bin] + bin_edges[best_bin + 1]) / 2.0)
            base_deg = np.array(dominant_angles) + math.degrees(theta_0)
        else:
            base_deg = np.array(dominant_angles)
    else:
        base_deg = np.array(dominant_angles)

    for p1, p2 in line_segments:
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length < 1e-6:
            rectified.append((p1, p2))
            continue

        mid_x = (p1[0] + p2[0]) / 2.0
        mid_y = (p1[1] + p2[1]) / 2.0

        current_angle_deg = math.degrees(math.atan2(dy, dx)) % 180.0

        # Find closest target angle in base_deg
        diffs = [abs((current_angle_deg - target) % 180.0) for target in base_deg]
        diffs = [min(d, 180.0 - d) for d in diffs]
        best_idx = int(np.argmin(diffs))

        target_angle_deg = base_deg[best_idx] % 180.0
        target_rad = math.radians(target_angle_deg)

        ux = math.cos(target_rad)
        uy = math.sin(target_rad)

        half_l = length / 2.0
        new_p1 = (float(mid_x - half_l * ux), float(mid_y - half_l * uy))
        new_p2 = (float(mid_x + half_l * ux), float(mid_y + half_l * uy))

        rectified.append((new_p1, new_p2))

    return rectified


def _extract_closed_polygons(
    walls: list[ExtractedWall],
    node_tol: float = 0.05,
) -> list[list[tuple[float, float]]]:
    """
    Extracts closed room perimeter loops from snapped wall segments.
    """
    if not walls:
        return []

    # Map unique node coordinates
    nodes: list[tuple[float, float]] = []

    def get_node_id(p: tuple[float, float]) -> int:
        for idx, node in enumerate(nodes):
            if math.hypot(node[0] - p[0], node[1] - p[1]) <= node_tol:
                return idx
        nodes.append(p)
        return len(nodes) - 1

    edges: list[tuple[int, int]] = []
    for w in walls:
        n1 = get_node_id(w.start_point)
        n2 = get_node_id(w.end_point)
        if n1 != n2:
            edges.append((n1, n2))

    if not edges or len(nodes) < 3:
        return []

    # Adjacency map
    adj: dict[int, set[int]] = {i: set() for i in range(len(nodes))}
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)

    visited_edges: set[tuple[int, int]] = set()
    closed_polys: list[list[tuple[float, float]]] = []

    # Simple cycle traversal starting at degree >= 2 nodes
    for start_node in range(len(nodes)):
        if len(adj[start_node]) < 2:
            continue

        path = [start_node]
        curr = start_node

        while True:
            next_node = None
            for neighbor in adj[curr]:
                edge_key = (min(curr, neighbor), max(curr, neighbor))
                if edge_key not in visited_edges:
                    next_node = neighbor
                    visited_edges.add(edge_key)
                    break

            if next_node is None:
                break

            if next_node == start_node and len(path) >= 3:
                # Loop closed!
                poly_pts = [nodes[i] for i in path]
                closed_polys.append(poly_pts)
                break
            elif next_node in path:
                # Sub-cycle detected
                idx = path.index(next_node)
                sub_path = path[idx:]
                if len(sub_path) >= 3:
                    closed_polys.append([nodes[i] for i in sub_path])
                break
            else:
                path.append(next_node)
                curr = next_node

    return closed_polys


def snap_corners_and_close_loops(
    line_segments: list[tuple[tuple[float, float], tuple[float, float]]],
    snap_threshold: float = 0.50,
    thickness: float = 0.15,
    height: float = 2.80,
) -> tuple[list[ExtractedWall], list[list[tuple[float, float]]]]:
    """
    Snaps intersecting wall segment endpoints to create closed topological wall loops.

    1. Computes line-line intersections for non-parallel segments whose endpoints are within `snap_threshold`.
    2. Snaps nearby endpoints together to ensure topological closure.
    3. Construct ExtractedWall objects with thickness, height, and bounding 2D polygons.
    4. Extracts closed room loop polygons.

    Returns:
        (extracted_walls, closed_polygons)
    """
    if not line_segments:
        return [], []

    segs = [[list(p1), list(p2)] for p1, p2 in line_segments]
    n_segs = len(segs)

    # 1. Line-line intersection snapping for adjacent non-parallel segments
    for i in range(n_segs):
        for j in range(i + 1, n_segs):
            s1_p1, s1_p2 = segs[i][0], segs[i][1]
            s2_p1, s2_p2 = segs[j][0], segs[j][1]

            endpoints1 = [(s1_p1, 0, i), (s1_p2, 1, i)]
            endpoints2 = [(s2_p1, 0, j), (s2_p2, 1, j)]

            for ep1, idx1, seg_i in endpoints1:
                for ep2, idx2, seg_j in endpoints2:
                    dist = math.hypot(ep1[0] - ep2[0], ep1[1] - ep2[1])
                    if dist <= snap_threshold:
                        isect = line_line_intersection_2d(
                            (s1_p1[0], s1_p1[1]), (s1_p2[0], s1_p2[1]),
                            (s2_p1[0], s2_p1[1]), (s2_p2[0], s2_p2[1]),
                        )
                        if isect is not None:
                            d1 = math.hypot(isect[0] - ep1[0], isect[1] - ep1[1])
                            d2 = math.hypot(isect[0] - ep2[0], isect[1] - ep2[1])
                            if d1 <= snap_threshold * 1.5 and d2 <= snap_threshold * 1.5:
                                segs[seg_i][idx1] = [isect[0], isect[1]]
                                segs[seg_j][idx2] = [isect[0], isect[1]]
                        else:
                            avg_p = [(ep1[0] + ep2[0]) / 2.0, (ep1[1] + ep2[1]) / 2.0]
                            segs[seg_i][idx1] = avg_p
                            segs[seg_j][idx2] = avg_p

    # 2. Secondary endpoint cluster snapping
    all_endpoints = []
    for i in range(n_segs):
        all_endpoints.append((segs[i][0], 0, i))
        all_endpoints.append((segs[i][1], 1, i))

    n_ep = len(all_endpoints)
    visited = [False] * n_ep

    for i in range(n_ep):
        if visited[i]:
            continue
        cluster = [i]
        visited[i] = True
        p_i = all_endpoints[i][0]

        for j in range(i + 1, n_ep):
            if visited[j]:
                continue
            p_j = all_endpoints[j][0]
            if math.hypot(p_i[0] - p_j[0], p_i[1] - p_j[1]) <= snap_threshold:
                cluster.append(j)
                visited[j] = True

        if len(cluster) > 1:
            mean_x = sum(all_endpoints[c][0][0] for c in cluster) / len(cluster)
            mean_y = sum(all_endpoints[c][0][1] for c in cluster) / len(cluster)
            for c in cluster:
                _, ep_idx, s_idx = all_endpoints[c]
                segs[s_idx][ep_idx] = [mean_x, mean_y]

    # 3. Create ExtractedWall objects with 4-vertex bounding polygons
    extracted_walls: list[ExtractedWall] = []
    for s1, s2 in segs:
        p1 = (float(s1[0]), float(s1[1]))
        p2 = (float(s2[0]), float(s2[1]))

        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length < 1e-4:
            continue

        angle_deg = math.degrees(math.atan2(dy, dx))
        if angle_deg < 0:
            angle_deg += 360.0
        angle_deg = angle_deg % 180.0

        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux

        half_w = thickness / 2.0
        c1 = (round(p1[0] + half_w * nx, 4), round(p1[1] + half_w * ny, 4))
        c2 = (round(p2[0] + half_w * nx, 4), round(p2[1] + half_w * ny, 4))
        c3 = (round(p2[0] - half_w * nx, 4), round(p2[1] - half_w * ny, 4))
        c4 = (round(p1[0] - half_w * nx, 4), round(p1[1] - half_w * ny, 4))
        poly = [c1, c2, c3, c4]

        wall = ExtractedWall(
            start_point=p1,
            end_point=p2,
            thickness=thickness,
            height=height,
            polygon=poly,
            angle_deg=round(angle_deg, 2),
        )
        extracted_walls.append(wall)

    # 4. Topology loop extraction
    closed_polygons = _extract_closed_polygons(extracted_walls)

    return extracted_walls, closed_polygons


def extract_walls(
    points_or_slice: np.ndarray | object,
    thickness: float = 0.15,
    height: float = 2.80,
    distance_threshold: float = 0.05,
    min_inliers: int = 15,
    max_iterations: int = 1000,
    min_length: float = 0.30,
    snap_threshold: float = 0.50,
    dominant_angles: tuple[float, ...] = (0.0, 90.0, 45.0, 135.0),
    auto_grid_offset: bool = False,
) -> WallExtractionResult:
    """
    Main entry point for 2D RANSAC wall centerline extraction and Manhattan rectification.

    Args:
        points_or_slice: (N, 2) or (N, 3) numpy array, or SliceResult object from slicer.
        thickness: Standard wall thickness in meters.
        height: Standard wall height in meters.
        distance_threshold: RANSAC line fitting distance threshold in meters.
        min_inliers: Minimum number of inlier points required per wall line.
        max_iterations: Maximum RANSAC iterations.
        min_length: Minimum line segment length in meters.
        snap_threshold: Maximum distance to snap adjacent endpoints together.
        dominant_angles: Target Manhattan angles in degrees.
        auto_grid_offset: If True, auto-detects principal orientation offset theta_0.

    Returns:
        WallExtractionResult containing extracted walls and closed room polygons.
    """
    if hasattr(points_or_slice, "slice_points_2d"):
        pts_2d = getattr(points_or_slice, "slice_points_2d")
    else:
        pts = np.asarray(points_or_slice, dtype=np.float64)
        if pts.ndim == 2 and pts.shape[1] >= 2:
            pts_2d = pts[:, :2]
        else:
            pts_2d = np.empty((0, 2), dtype=np.float64)

    if len(pts_2d) < 2:
        return WallExtractionResult(walls=[], closed_polygons=[], num_walls=0)

    # 1. 2D RANSAC line segment fitting
    raw_segments = fit_lines_2d_ransac(
        pts_2d,
        distance_threshold=distance_threshold,
        min_inliers=min_inliers,
        max_iterations=max_iterations,
        min_length=min_length,
    )

    # 2. Manhattan 90-degree orthogonal rectification
    rectified_segments = rectify_manhattan(
        raw_segments,
        dominant_angles=dominant_angles,
        auto_grid_offset=auto_grid_offset,
    )

    # 3. Corner snapping & topology loop closure
    walls, closed_polys = snap_corners_and_close_loops(
        rectified_segments,
        snap_threshold=snap_threshold,
        thickness=thickness,
        height=height,
    )

    return WallExtractionResult(
        walls=walls,
        closed_polygons=closed_polys,
        num_walls=len(walls),
    )
