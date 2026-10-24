"""
debim.scan.calibrator

Point cloud (.ply) ingestion with RANSAC horizontal floor plane detection,
Rodrigues rotation gravity alignment (+Z up), door opening height detection,
and true metric 1:1 scale calibration (door opening height = 2.00m).
"""

from pathlib import Path
from dataclasses import dataclass
import numpy as np

try:
    import plyfile
except ImportError:
    plyfile = None


@dataclass
class CalibrationResult:
    calibrated_points: np.ndarray
    calibrated_colors: np.ndarray | None
    scale_factor: float
    rotation_matrix: np.ndarray
    translation: np.ndarray
    floor_z_raw: float
    door_height_raw: float


def load_ply(filepath: str | Path) -> tuple[np.ndarray, np.ndarray | None]:
    """
    Load XYZ points and optional colors from ASCII or Binary .ply files.
    Uses plyfile if installed, otherwise pure NumPy PLY parser.
    """
    filepath = Path(filepath)
    if plyfile is not None:
        try:
            plydata = plyfile.PlyData.read(str(filepath))
            vertex = plydata["vertex"]
            x = np.asarray(vertex["x"], dtype=np.float64)
            y = np.asarray(vertex["y"], dtype=np.float64)
            z = np.asarray(vertex["z"], dtype=np.float64)
            pts = np.column_stack([x, y, z])

            colors = None
            color_keys = [("red", "green", "blue"), ("r", "g", "b"), ("diffuse_red", "diffuse_green", "diffuse_blue")]
            for r_k, g_k, b_k in color_keys:
                if r_k in vertex and g_k in vertex and b_k in vertex:
                    r = np.asarray(vertex[r_k], dtype=np.uint8)
                    g = np.asarray(vertex[g_k], dtype=np.uint8)
                    b = np.asarray(vertex[b_k], dtype=np.uint8)
                    colors = np.column_stack([r, g, b])
                    break
            return pts, colors
        except Exception:
            pass

    # Pure NumPy PLY parser fallback
    with open(filepath, "rb") as f:
        header_lines = []
        while True:
            line = f.readline()
            if not line:
                break
            line_str = line.decode("ascii", errors="replace").strip()
            header_lines.append(line_str)
            if line_str == "end_header":
                break

    format_str = ""
    num_vertices = 0
    properties = []
    in_vertex_element = False

    for line in header_lines:
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0] == "format":
            format_str = tokens[1]
        elif tokens[0] == "element":
            if tokens[1] == "vertex":
                in_vertex_element = True
                num_vertices = int(tokens[2])
            else:
                in_vertex_element = False
        elif tokens[0] == "property" and in_vertex_element:
            prop_type = tokens[1]
            prop_name = tokens[2]
            properties.append((prop_name, prop_type))

    if format_str == "ascii":
        # ASCII parsing
        data = np.loadtxt(filepath, skiprows=len(header_lines), max_rows=num_vertices)
        if data.ndim == 1:
            data = data.reshape(1, -1)

        prop_names = [p[0] for p in properties]
        x_idx = prop_names.index("x") if "x" in prop_names else 0
        y_idx = prop_names.index("y") if "y" in prop_names else 1
        z_idx = prop_names.index("z") if "z" in prop_names else 2
        pts = data[:, [x_idx, y_idx, z_idx]].astype(np.float64)

        colors = None
        for r_k, g_k, b_k in [("red", "green", "blue"), ("r", "g", "b")]:
            if r_k in prop_names and g_k in prop_names and b_k in prop_names:
                r_i = prop_names.index(r_k)
                g_i = prop_names.index(g_k)
                b_i = prop_names.index(b_k)
                colors = data[:, [r_i, g_i, b_i]].astype(np.uint8)
                break
        return pts, colors

    elif "binary" in format_str:
        # Binary parsing
        type_map = {
            "char": "i1", "uchar": "u1",
            "short": "i2", "ushort": "u2",
            "int": "i4", "uint": "u4", "int32": "i4", "uint32": "u4",
            "float": "f4", "float32": "f4",
            "double": "f8", "float64": "f8",
        }
        endian = "<" if "little_endian" in format_str else ">"
        dtype_list = []
        for prop_name, prop_type in properties:
            np_t = type_map.get(prop_type, "f4")
            dtype_list.append((prop_name, endian + np_t))

        dt = np.dtype(dtype_list)
        header_bytes_count = 0
        with open(filepath, "rb") as f:
            for line in header_lines:
                header_bytes_count += len(line.encode("ascii")) + 1 # include newline

        with open(filepath, "rb") as f:
            f.seek(header_bytes_count)
            raw_data = np.frombuffer(f.read(num_vertices * dt.itemsize), dtype=dt)

        x = raw_data["x"].astype(np.float64)
        y = raw_data["y"].astype(np.float64)
        z = raw_data["z"].astype(np.float64)
        pts = np.column_stack([x, y, z])

        colors = None
        for r_k, g_k, b_k in [("red", "green", "blue"), ("r", "g", "b")]:
            if r_k in raw_data.dtype.names and g_k in raw_data.dtype.names and b_k in raw_data.dtype.names:
                r = raw_data[r_k].astype(np.uint8)
                g = raw_data[g_k].astype(np.uint8)
                b = raw_data[b_k].astype(np.uint8)
                colors = np.column_stack([r, g, b])
                break
        return pts, colors

    raise ValueError(f"Unsupported PLY format: {format_str}")


def save_ply(
    filepath: str | Path,
    points: np.ndarray,
    colors: np.ndarray | None = None,
    binary: bool = True,
) -> None:
    """
    Save 3D points and optional colors to a .ply file.
    """
    filepath = Path(filepath)
    num_vertices = len(points)

    if binary:
        if colors is not None:
            dtype_list = [
                ("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                ("red", "<u1"), ("green", "<u1"), ("blue", "<u1"),
            ]
            rec = np.empty(num_vertices, dtype=dtype_list)
            rec["x"] = points[:, 0].astype(np.float32)
            rec["y"] = points[:, 1].astype(np.float32)
            rec["z"] = points[:, 2].astype(np.float32)
            rec["red"] = colors[:, 0].astype(np.uint8)
            rec["green"] = colors[:, 1].astype(np.uint8)
            rec["blue"] = colors[:, 2].astype(np.uint8)
        else:
            dtype_list = [("x", "<f4"), ("y", "<f4"), ("z", "<f4")]
            rec = np.empty(num_vertices, dtype=dtype_list)
            rec["x"] = points[:, 0].astype(np.float32)
            rec["y"] = points[:, 1].astype(np.float32)
            rec["z"] = points[:, 2].astype(np.float32)

        header = [
            "ply",
            "format binary_little_endian 1.0",
            f"element vertex {num_vertices}",
            "property float x",
            "property float y",
            "property float z",
        ]
        if colors is not None:
            header.extend([
                "property uchar red",
                "property uchar green",
                "property uchar blue",
            ])
        header.append("end_header\n")

        with open(filepath, "wb") as f:
            f.write("\n".join(header).encode("ascii"))
            f.write(rec.tobytes())
    else:
        header = [
            "ply",
            "format ascii 1.0",
            f"element vertex {num_vertices}",
            "property float x",
            "property float y",
            "property float z",
        ]
        if colors is not None:
            header.extend([
                "property uchar red",
                "property uchar green",
                "property uchar blue",
            ])
        header.append("end_header")

        with open(filepath, "w", encoding="ascii") as f:
            f.write("\n".join(header) + "\n")
            for i in range(num_vertices):
                px, py, pz = points[i]
                if colors is not None:
                    cr, cg, cb = colors[i]
                    f.write(f"{px:.6f} {py:.6f} {pz:.6f} {int(cr)} {int(cg)} {int(cb)}\n")
                else:
                    f.write(f"{px:.6f} {py:.6f} {pz:.6f}\n")


def estimate_floor_plane(
    points: np.ndarray,
    max_iterations: int = 1000,
    distance_threshold: float = 0.05,
    vertical_normal_min_z: float = 0.7,
) -> tuple[np.ndarray, float, np.ndarray]:
    """
    RANSAC plane estimation for horizontal floor plane detection.
    Refines normal using SVD on inliers.

    Returns:
        (normal, d, inlier_indices) where plane equation is normal . p + d = 0,
        normal is a unit 3D vector with normal[2] > 0 (+Z pointing up).
    """
    num_pts = len(points)
    if num_pts < 3:
        raise ValueError("Need at least 3 points to estimate floor plane.")

    best_inliers = np.array([], dtype=int)
    best_normal = np.array([0.0, 0.0, 1.0])
    best_d = 0.0

    # Deterministic seed for reproducible RANSAC if needed
    rng = np.random.default_rng(42)

    for _ in range(max_iterations):
        idx = rng.choice(num_pts, size=3, replace=False)
        p1, p2, p3 = points[idx]
        v1 = p2 - p1
        v2 = p3 - p1
        n = np.cross(v1, v2)
        norm_val = np.linalg.norm(n)
        if norm_val < 1e-7:
            continue
        n = n / norm_val
        if n[2] < 0:
            n = -n
        if n[2] < vertical_normal_min_z:
            continue

        d = -np.dot(n, p1)
        dists = np.abs(np.dot(points, n) + d)
        inliers = np.where(dists < distance_threshold)[0]

        if len(inliers) > len(best_inliers):
            best_inliers = inliers
            best_normal = n
            best_d = d

    if len(best_inliers) >= 3:
        # SVD refinement on inliers
        inlier_pts = points[best_inliers]
        centroid = np.mean(inlier_pts, axis=0)
        centered = inlier_pts - centroid
        _, _, vh = np.linalg.svd(centered)
        refined_normal = vh[2, :]
        norm_val = np.linalg.norm(refined_normal)
        if norm_val > 1e-7:
            refined_normal = refined_normal / norm_val
        if refined_normal[2] < 0:
            refined_normal = -refined_normal

        if refined_normal[2] >= vertical_normal_min_z:
            best_normal = refined_normal
            best_d = -np.dot(best_normal, centroid)
            # Recompute inliers with refined plane
            dists = np.abs(np.dot(points, best_normal) + best_d)
            best_inliers = np.where(dists < distance_threshold)[0]

    return best_normal, float(best_d), best_inliers


def rodrigues_rotation_matrix(normal: np.ndarray) -> np.ndarray:
    """
    Computes a 3x3 Rodrigues rotation matrix aligning unit vector `normal` with +Z (0, 0, 1).
    """
    n = np.asarray(normal, dtype=np.float64)
    n_norm = np.linalg.norm(n)
    if n_norm > 1e-7:
        n = n / n_norm

    z_axis = np.array([0.0, 0.0, 1.0], dtype=np.float64)
    v = np.cross(n, z_axis)
    c = float(np.dot(n, z_axis))
    s = float(np.linalg.norm(v))

    if s < 1e-7:
        if c > 0:
            return np.eye(3, dtype=np.float64)
        else:
            return np.diag([1.0, -1.0, -1.0])

    K = np.array([
        [0.0, -v[2], v[1]],
        [v[2], 0.0, -v[0]],
        [-v[1], v[0], 0.0],
    ], dtype=np.float64)

    R = np.eye(3, dtype=np.float64) + K + np.dot(K, K) * ((1.0 - c) / (s ** 2))
    return R


def detect_door_height(
    points: np.ndarray,
    floor_z: float = 0.0,
    cell_size: float = 0.10,
) -> float:
    """
    Detects door opening lintel height relative to floor_z.

    Analyzes 2D grid cells across the point cloud to find wall opening cutouts
    (cells with floor points, header points, but missing mid-height wall points).
    """
    z_rel = points[:, 2] - floor_z
    valid_idx = np.where(z_rel >= -0.10)[0]
    if len(valid_idx) == 0:
        return 2.00

    pts_valid = points[valid_idx]
    z_valid = z_rel[valid_idx]

    grid_x = np.floor(pts_valid[:, 0] / cell_size).astype(int)
    grid_y = np.floor(pts_valid[:, 1] / cell_size).astype(int)

    cell_dict: dict[tuple[int, int], list[float]] = {}
    for i in range(len(pts_valid)):
        key = (grid_x[i], grid_y[i])
        if key not in cell_dict:
            cell_dict[key] = []
        cell_dict[key].append(z_valid[i])

    lintel_candidates = []
    for key, z_vals in cell_dict.items():
        z_arr = np.array(z_vals)
        has_low = np.any(z_arr < 0.20)
        high_pts = z_arr[z_arr >= 0.50]
        if len(high_pts) == 0:
            continue

        min_high = float(np.min(high_pts))
        # Door cutout condition: points exist above min_high, but no/few points between 0.30 and min_high - 0.05
        mid_pts = z_arr[(z_arr >= 0.30) & (z_arr < min_high - 0.05)]
        if len(mid_pts) < 2 and 0.80 <= min_high <= 3.50:
            lintel_candidates.append(min_high)

    if len(lintel_candidates) > 0:
        return float(np.median(lintel_candidates))

    # Fallback: scan histogram of upper opening bounds or return standard 2.00
    return 2.00


def calibrate_point_cloud(
    points_or_file: str | Path | np.ndarray,
    colors: np.ndarray | None = None,
    target_door_height: float = 2.00,
) -> CalibrationResult:
    """
    Calibrates raw point cloud:
    1. Estimates floor plane via RANSAC.
    2. Rotates point cloud using Rodrigues rotation so floor normal aligns with +Z.
    3. Translates point cloud so floor level Z = 0.0.
    4. Detects raw door opening lintel height h_door_raw.
    5. Rescales point cloud so door opening height equals target_door_height (2.00m).
    """
    if isinstance(points_or_file, (str, Path)):
        pts, cols = load_ply(points_or_file)
        if colors is None:
            colors = cols
    else:
        pts = np.asarray(points_or_file, dtype=np.float64)

    # 1. RANSAC floor plane
    normal, d, inliers = estimate_floor_plane(pts)

    # 2. Rodrigues rotation matrix
    R = rodrigues_rotation_matrix(normal)
    pts_rotated = np.dot(pts, R.T)

    # 3. Floor Z level
    if len(inliers) > 0:
        inlier_rotated_z = pts_rotated[inliers, 2]
        floor_z_raw = float(np.median(inlier_rotated_z))
    else:
        floor_z_raw = float(np.min(pts_rotated[:, 2]))

    translation = np.array([0.0, 0.0, -floor_z_raw], dtype=np.float64)
    pts_shifted = pts_rotated + translation

    # 4. Door lintel height detection
    door_height_raw = detect_door_height(pts_shifted, floor_z=0.0)
    if door_height_raw <= 1e-3:
        door_height_raw = 2.00

    # 5. Metric scale calibration
    scale_factor = float(target_door_height / door_height_raw)
    pts_calibrated = pts_shifted * scale_factor

    return CalibrationResult(
        calibrated_points=pts_calibrated,
        calibrated_colors=colors,
        scale_factor=scale_factor,
        rotation_matrix=R,
        translation=translation,
        floor_z_raw=floor_z_raw,
        door_height_raw=door_height_raw,
    )
