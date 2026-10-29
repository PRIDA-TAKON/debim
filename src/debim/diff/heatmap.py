"""
debim.diff.heatmap

Deviation Tolerance Heatmap engine for colorizing point clouds based on signed geometric
deviations against debim BIM model elements.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Union
import numpy as np

from debim.scan.calibrator import save_ply


@dataclass
class HeatmapResult:
    """
    Data structure containing deviation tolerance heatmap calculations and statistical summary.
    """
    points: np.ndarray
    deviations: np.ndarray  # 1D array of signed deviations in mm
    colors: np.ndarray      # (N, 3) uint8 RGB array
    tolerance_mm: float
    pass_percentage: float
    within_tolerance_count: int
    out_of_tolerance_count: int
    rmse_mm: float
    max_deviation_mm: float
    min_deviation_mm: float
    mean_deviation_mm: float

    def export_ply(self, filepath: Union[str, Path], binary: bool = True) -> Path:
        """
        Export colorized deviation point cloud to a .ply file.
        """
        out_path = Path(filepath)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        save_ply(out_path, self.points, self.colors, binary=binary)
        return out_path


def generate_deviation_heatmap(
    points: np.ndarray,
    deviations: np.ndarray,
    tolerance_mm: float = 10.0,
) -> HeatmapResult:
    """
    Maps 3D point cloud deviations (mm) to RGB colors:
      - Green (0, 255, 0 / 34, 197, 94): Within tolerance (|dev| <= tolerance_mm)
      - Red (255, 0, 0 / 239, 68, 68): Protrusion / tilt (+dev > +tolerance_mm)
      - Blue (0, 0, 255 / 59, 130, 246): Missing / recessed (-dev < -tolerance_mm)

    Args:
        points: (N, 3) float array of 3D point cloud coordinates.
        deviations: (N,) float array of signed deviations (in mm).
        tolerance_mm: Tolerance threshold in millimeters (default: 10.0 mm).

    Returns:
        HeatmapResult containing colorized points, RGB array, pass percentage, and statistical summary.
    """
    pts = np.asarray(points, dtype=np.float64)
    devs = np.asarray(deviations, dtype=np.float64).reshape(-1)

    if pts.ndim == 1 and pts.shape[0] == 3:
        pts = pts.reshape(1, 3)

    num_pts = pts.shape[0] if pts.size > 0 else 0

    if num_pts == 0 or devs.size == 0:
        empty_pts = np.empty((0, 3), dtype=np.float64)
        empty_devs = np.empty((0,), dtype=np.float64)
        empty_cols = np.empty((0, 3), dtype=np.uint8)
        return HeatmapResult(
            points=empty_pts,
            deviations=empty_devs,
            colors=empty_cols,
            tolerance_mm=tolerance_mm,
            pass_percentage=100.0,
            within_tolerance_count=0,
            out_of_tolerance_count=0,
            rmse_mm=0.0,
            max_deviation_mm=0.0,
            min_deviation_mm=0.0,
            mean_deviation_mm=0.0,
        )

    if devs.shape[0] != num_pts:
        raise ValueError(f"Length of deviations ({devs.shape[0]}) does not match points ({num_pts}).")

    # RGB Colors assignment
    # Green: [34, 197, 94] (within tolerance)
    # Red: [239, 68, 68] (protrusion / +dev > tolerance_mm)
    # Blue: [59, 130, 246] (recessed / -dev < -tolerance_mm)
    colors = np.zeros((num_pts, 3), dtype=np.uint8)

    within_mask = np.abs(devs) <= tolerance_mm
    protrusion_mask = devs > tolerance_mm
    recessed_mask = devs < -tolerance_mm

    colors[within_mask] = [34, 197, 94]     # Green
    colors[protrusion_mask] = [239, 68, 68]  # Red
    colors[recessed_mask] = [59, 130, 246]   # Blue

    within_count = int(np.sum(within_mask))
    out_count = num_pts - within_count
    pass_pct = float((within_count / num_pts) * 100.0) if num_pts > 0 else 100.0

    rmse_val = float(np.sqrt(np.mean(devs ** 2)))
    max_dev = float(np.max(devs))
    min_dev = float(np.min(devs))
    mean_dev = float(np.mean(devs))

    return HeatmapResult(
        points=pts,
        deviations=devs,
        colors=colors,
        tolerance_mm=tolerance_mm,
        pass_percentage=round(pass_pct, 2),
        within_tolerance_count=within_count,
        out_of_tolerance_count=out_count,
        rmse_mm=round(rmse_val, 2),
        max_deviation_mm=round(max_dev, 2),
        min_deviation_mm=round(min_dev, 2),
        mean_deviation_mm=round(mean_dev, 2),
    )


def export_colorized_ply(filepath: Union[str, Path], result: HeatmapResult, binary: bool = True) -> Path:
    """
    Helper function to save HeatmapResult to a colorized PLY file (`colored_deviation.ply`).
    """
    return result.export_ply(filepath, binary=binary)
