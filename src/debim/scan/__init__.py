"""
debim.scan

Point cloud scan processing, calibration, slicing, and extraction.
"""

from debim.scan.calibrator import (
    CalibrationResult,
    load_ply,
    save_ply,
    estimate_floor_plane,
    rodrigues_rotation_matrix,
    detect_door_height,
    calibrate_point_cloud,
)
from debim.scan.slicer import (
    StoreyHeightResult,
    SliceResult,
    detect_storey_height,
    extract_eye_level_slice,
    slice_point_cloud,
)
from debim.scan.wall_extractor import (
    ExtractedWall,
    WallExtractionResult,
    fit_lines_2d_ransac,
    rectify_manhattan,
    snap_corners_and_close_loops,
    extract_walls,
)
from debim.scan.opening_detector import (
    DetectedOpening,
    OpeningDetectionResult,
    detect_openings_along_wall,
    detect_openings,
)

__all__ = [
    "CalibrationResult",
    "load_ply",
    "save_ply",
    "estimate_floor_plane",
    "rodrigues_rotation_matrix",
    "detect_door_height",
    "calibrate_point_cloud",
    "StoreyHeightResult",
    "SliceResult",
    "detect_storey_height",
    "extract_eye_level_slice",
    "slice_point_cloud",
    "ExtractedWall",
    "WallExtractionResult",
    "fit_lines_2d_ransac",
    "rectify_manhattan",
    "snap_corners_and_close_loops",
    "extract_walls",
    "DetectedOpening",
    "OpeningDetectionResult",
    "detect_openings_along_wall",
    "detect_openings",
]
