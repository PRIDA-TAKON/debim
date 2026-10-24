"""
debim.scan.slicer

Z-histogram peak analysis for floor and ceiling detection (storey height extraction)
and horizontal 2D slice extraction at eye level (+1.20m, thickness ±0.10m)
filtering low furniture for room perimeter reconstruction.
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class StoreyHeightResult:
    floor_z: float
    ceiling_z: float
    storey_height: float
    histogram_counts: np.ndarray
    bin_centers: np.ndarray


@dataclass
class SliceResult:
    slice_points_2d: np.ndarray  # Shape (M, 2)
    slice_points_3d: np.ndarray  # Shape (M, 3)
    slice_colors: np.ndarray | None
    z_level: float
    thickness: float
    num_points: int


def detect_storey_height(
    points: np.ndarray,
    bin_size: float = 0.05,
    min_height: float = 2.20,
    max_height: float = 5.0,
    floor_search_range: tuple[float, float] = (-0.5, 0.5),
) -> StoreyHeightResult:
    """
    Analyzes 1D Z-density histogram of a 3D point cloud to detect:
    1. Floor peak around Z = 0.0m (within floor_search_range)
    2. Ceiling peak at Z = floor_z + height H (between min_height and max_height)

    Returns:
        StoreyHeightResult containing floor_z, ceiling_z, storey_height, and histogram data.
    """
    if len(points) == 0:
        return StoreyHeightResult(
            floor_z=0.0,
            ceiling_z=2.80,
            storey_height=2.80,
            histogram_counts=np.array([]),
            bin_centers=np.array([]),
        )

    z_vals = points[:, 2]
    z_min = float(np.min(z_vals))
    z_max = float(np.max(z_vals))

    # Expand bounds slightly to cover bin edges properly
    bins = np.arange(z_min - bin_size, z_max + 2 * bin_size, bin_size)
    counts, bin_edges = np.histogram(z_vals, bins=bins)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

    # Floor peak detection: look within floor_search_range
    f_min, f_max = floor_search_range
    floor_mask = (bin_centers >= f_min) & (bin_centers <= f_max)

    if np.any(floor_mask) and np.sum(counts[floor_mask]) > 0:
        floor_sub_idx = np.argmax(counts[floor_mask])
        floor_idx = np.where(floor_mask)[0][floor_sub_idx]
        floor_z = float(bin_centers[floor_idx])
    else:
        # Fallback to overall minimum Z or 0.0
        floor_z = max(0.0, z_min)

    # Ceiling peak detection: look in Z range [floor_z + min_height, floor_z + max_height]
    c_min = floor_z + min_height
    c_max = floor_z + max_height
    ceiling_mask = (bin_centers >= c_min) & (bin_centers <= c_max)

    if np.any(ceiling_mask) and np.sum(counts[ceiling_mask]) > 0:
        ceiling_sub_idx = np.argmax(counts[ceiling_mask])
        ceiling_idx = np.where(ceiling_mask)[0][ceiling_sub_idx]
        ceiling_z = float(bin_centers[ceiling_idx])
    else:
        # Fallback to z_max or standard 2.80m above floor
        ceiling_z = max(floor_z + 2.80, z_max)

    storey_height = float(ceiling_z - floor_z)

    return StoreyHeightResult(
        floor_z=floor_z,
        ceiling_z=ceiling_z,
        storey_height=storey_height,
        histogram_counts=counts,
        bin_centers=bin_centers,
    )


def extract_eye_level_slice(
    points: np.ndarray,
    colors: np.ndarray | None = None,
    z_level: float = 1.20,
    thickness: float = 0.10,
    filter_low_furniture: bool = True,
    floor_z: float = 0.0,
) -> SliceResult:
    """
    Extracts horizontal 2D slice from 3D point cloud at Z = floor_z + z_level (thickness ±thickness).

    Default parameters target eye level (+1.20m, thickness ±0.10m, i.e., Z in [1.10, 1.30] relative to floor_z).
    This slice height naturally passes above low furniture (coffee tables < 0.50m, desks/chairs < 0.90m)
    and below door headers (> 2.00m) and ceiling (> 2.60m), providing clean 2D room perimeter points.

    Args:
        points: (N, 3) XYZ point cloud.
        colors: Optional (N, 3) RGB color array.
        z_level: Relative height above floor_z for eye-level slice (default 1.20m).
        thickness: Half-thickness allowance for slice (default 0.10m -> ±0.10m band).
        filter_low_furniture: If True, ensures low Z points (< z_level - thickness) are excluded.
        floor_z: Floor reference Z coordinate.

    Returns:
        SliceResult containing 2D/3D points, optional colors, z_level, thickness, and point count.
    """
    if len(points) == 0:
        return SliceResult(
            slice_points_2d=np.empty((0, 2), dtype=np.float64),
            slice_points_3d=np.empty((0, 3), dtype=np.float64),
            slice_colors=None if colors is None else np.empty((0, 3), dtype=colors.dtype),
            z_level=z_level,
            thickness=thickness,
            num_points=0,
        )

    abs_z = floor_z + z_level
    min_z = abs_z - thickness
    max_z = abs_z + thickness

    # Base mask for points inside the slice band
    z_vals = points[:, 2]
    slice_mask = (z_vals >= min_z) & (z_vals <= max_z)

    if filter_low_furniture:
        # Additional sanity filter: points below min_z are explicitly excluded from mask
        furniture_min_z = floor_z + 1.00 # Anything below 1.0m is filtered out
        slice_mask = slice_mask & (z_vals >= furniture_min_z)

    slice_3d = points[slice_mask]
    slice_2d = slice_3d[:, :2]

    slice_colors = None
    if colors is not None and len(colors) == len(points):
        slice_colors = colors[slice_mask]

    return SliceResult(
        slice_points_2d=slice_2d,
        slice_points_3d=slice_3d,
        slice_colors=slice_colors,
        z_level=z_level,
        thickness=thickness,
        num_points=len(slice_3d),
    )


def slice_point_cloud(
    points: np.ndarray,
    colors: np.ndarray | None = None,
    eye_level: float = 1.20,
    thickness: float = 0.10,
    bin_size: float = 0.05,
) -> tuple[StoreyHeightResult, SliceResult]:
    """
    Convenience function that detects storey floor and ceiling height using Z-density histogram analysis
    and then extracts an eye-level horizontal slice (+1.20m, thickness ±0.10m).

    Returns:
        (StoreyHeightResult, SliceResult)
    """
    storey_res = detect_storey_height(points, bin_size=bin_size)
    slice_res = extract_eye_level_slice(
        points,
        colors=colors,
        z_level=eye_level,
        thickness=thickness,
        floor_z=storey_res.floor_z,
    )
    return storey_res, slice_res
