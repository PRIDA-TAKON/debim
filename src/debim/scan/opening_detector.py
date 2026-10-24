"""
debim.scan.opening_detector

Vertical point density profile sampling along 2D wall centerlines for
opening gap detection, distinguishing doors (0.0m - 2.0m void) and
windows (0.8m - 2.0m void with apron wall below 0.8m).
"""

from dataclasses import dataclass, field
import math
from typing import Literal
import numpy as np

from debim.scan.wall_extractor import ExtractedWall, WallExtractionResult


@dataclass
class DetectedOpening:
    """
    Represents a detected door or window opening along an extracted wall line.
    """
    opening_type: Literal["Door", "Window"]
    tag: str  # e.g. "D1", "W1"
    sill_height: float
    head_height: float
    width: float
    start_point: tuple[float, float]
    end_point: tuple[float, float]
    center_point: tuple[float, float, float]
    wall_index: int = 0

    @property
    def height(self) -> float:
        return float(self.head_height - self.sill_height)


@dataclass
class OpeningDetectionResult:
    """
    Container for all detected openings across extracted wall lines.
    """
    openings: list[DetectedOpening]
    doors: list[DetectedOpening]
    windows: list[DetectedOpening]
    num_openings: int
    num_doors: int
    num_windows: int


def detect_openings_along_wall(
    wall: ExtractedWall,
    points_3d: np.ndarray,
    wall_index: int = 0,
    floor_z: float = 0.0,
    bin_size: float = 0.05,
    min_opening_width: float = 0.40,
    perpendicular_tolerance: float = 0.25,
    min_points_wall_cell: int = 3,
    door_sill_max: float = 0.20,
    window_sill_default: float = 0.80,
    head_default: float = 2.00,
) -> list[DetectedOpening]:
    """
    Samples vertical point density profiles along a wall line to detect door and window voids.

    Args:
        wall: ExtractedWall object containing start_point and end_point.
        points_3d: (N, 3) numpy array of 3D point cloud coordinates.
        wall_index: Index of the wall segment being analyzed.
        floor_z: Floor level Z coordinate reference.
        bin_size: Spatial bin size along the wall centerline in meters.
        min_opening_width: Minimum width in meters to classify as a valid opening gap.
        perpendicular_tolerance: Maximum distance from wall centerline to include points.
        min_points_wall_cell: Minimum 3D points required to consider a height zone solid.
        door_sill_max: Maximum sill height threshold to classify as a Door (0.0m - 2.0m void).
        window_sill_default: Default sill height for Windows (0.8m).
        head_default: Default opening head height (2.0m).

    Returns:
        List of DetectedOpening objects along the given wall segment.
    """
    if len(points_3d) == 0:
        return []

    x1, y1 = wall.start_point
    x2, y2 = wall.end_point
    dx = x2 - x1
    dy = y2 - y1
    wall_length = math.hypot(dx, dy)

    if wall_length < 1e-4:
        return []

    # Unit direction vector along wall line and normal vector perpendicular
    ux, uy = dx / wall_length, dy / wall_length
    nx, ny = -uy, ux

    # Project 3D points onto wall coordinate system (t along wall, d perpendicular)
    pts = np.asarray(points_3d, dtype=np.float64)
    px = pts[:, 0] - x1
    py = pts[:, 1] - y1
    pz = pts[:, 2] - floor_z

    t_proj = px * ux + py * uy
    d_proj = np.abs(px * nx + py * ny)

    # Filter points near the wall line
    near_mask = (t_proj >= 0.0) & (t_proj <= wall_length) & (d_proj <= perpendicular_tolerance) & (pz >= -0.10)
    if not np.any(near_mask):
        return []

    t_near = t_proj[near_mask]
    pz_near = pz[near_mask]

    n_bins = max(1, int(math.ceil(wall_length / bin_size)))
    bin_edges = np.linspace(0.0, wall_length, n_bins + 1)

    # Height zones:
    # Zone A (Low / Apron): Z in [0.05, 0.75]
    # Zone B (Mid / Opening): Z in [0.85, 1.95]
    # Zone C (High / Header): Z in [2.05, wall.height]
    zone_a_mask = (pz_near >= 0.05) & (pz_near <= 0.75)
    zone_b_mask = (pz_near >= 0.85) & (pz_near <= 1.95)

    bin_classifications: list[str] = []

    for i in range(n_bins):
        t_min_b, t_max_b = bin_edges[i], bin_edges[i + 1]
        bin_mask = (t_near >= t_min_b) & (t_near < t_max_b)

        count_zone_a = np.sum(bin_mask & zone_a_mask)
        count_zone_b = np.sum(bin_mask & zone_b_mask)

        if count_zone_b < min_points_wall_cell:
            if count_zone_a < min_points_wall_cell:
                bin_classifications.append("DOOR_VOID")
            else:
                bin_classifications.append("WINDOW_VOID")
        else:
            bin_classifications.append("SOLID")

    # Merge contiguous runs of void bins
    openings: list[DetectedOpening] = []
    i = 0
    while i < n_bins:
        cls = bin_classifications[i]
        if cls in ("DOOR_VOID", "WINDOW_VOID"):
            start_bin = i
            while i < n_bins and bin_classifications[i] == cls:
                i += 1
            end_bin = i

            t_start = float(bin_edges[start_bin])
            t_end = float(bin_edges[end_bin])
            width = t_end - t_start

            if width >= min_opening_width:
                t_mid = (t_start + t_end) / 2.0
                c_x = x1 + t_mid * ux
                c_y = y1 + t_mid * uy

                opening_mask = (t_near >= t_start) & (t_near <= t_end)
                pz_opening = pz_near[opening_mask]

                if cls == "DOOR_VOID":
                    opening_type = "Door"
                    sill_height = 0.0
                    head_height = head_default

                    # Check if header points exist above door opening
                    header_pts = pz_opening[pz_opening >= 1.80]
                    if len(header_pts) > 0:
                        min_head = float(np.min(header_pts))
                        if 1.70 <= min_head <= 2.50:
                            head_height = min_head
                else:
                    opening_type = "Window"
                    sill_height = window_sill_default
                    head_height = head_default

                    # Measure dynamic sill height from Zone A points if available
                    apron_pts = pz_opening[(pz_opening >= 0.05) & (pz_opening <= 1.20)]
                    if len(apron_pts) > 0:
                        max_apron = float(np.max(apron_pts))
                        if 0.50 <= max_apron <= 1.20:
                            sill_height = max_apron

                    header_pts = pz_opening[pz_opening >= 1.80]
                    if len(header_pts) > 0:
                        min_head = float(np.min(header_pts))
                        if 1.70 <= min_head <= 2.50:
                            head_height = min_head

                p_start = (float(x1 + t_start * ux), float(y1 + t_start * uy))
                p_end = (float(x1 + t_end * ux), float(y1 + t_end * uy))
                c_z = float(floor_z + (sill_height + head_height) / 2.0)
                center_point = (float(c_x), float(c_y), c_z)

                detected = DetectedOpening(
                    opening_type=opening_type,
                    tag="",  # Assigned in aggregate detect_openings
                    sill_height=round(sill_height, 2),
                    head_height=round(head_height, 2),
                    width=round(width, 3),
                    start_point=p_start,
                    end_point=p_end,
                    center_point=center_point,
                    wall_index=wall_index,
                )
                openings.append(detected)
        else:
            i += 1

    return openings


def detect_openings(
    walls_or_result: list[ExtractedWall] | WallExtractionResult,
    points_3d: np.ndarray | object,
    floor_z: float = 0.0,
    bin_size: float = 0.05,
    min_opening_width: float = 0.40,
    perpendicular_tolerance: float = 0.25,
) -> OpeningDetectionResult:
    """
    Detects door and window openings across extracted wall lines.

    Args:
        walls_or_result: List of ExtractedWall objects or WallExtractionResult.
        points_3d: (N, 3) numpy array or calibration object containing points.
        floor_z: Floor reference Z coordinate.
        bin_size: Spatial sampling bin size along wall lines.
        min_opening_width: Minimum void width to classify as opening.
        perpendicular_tolerance: Max distance from wall centerline to sample points.

    Returns:
        OpeningDetectionResult containing detected openings, doors, windows, and counts.
    """
    if hasattr(walls_or_result, "walls"):
        walls = getattr(walls_or_result, "walls")
    else:
        walls = list(walls_or_result)

    if hasattr(points_3d, "calibrated_points"):
        pts = getattr(points_3d, "calibrated_points")
    else:
        pts = np.asarray(points_3d, dtype=np.float64)

    all_openings: list[DetectedOpening] = []
    doors: list[DetectedOpening] = []
    windows: list[DetectedOpening] = []

    door_count = 1
    window_count = 1

    for idx, wall in enumerate(walls):
        wall_openings = detect_openings_along_wall(
            wall=wall,
            points_3d=pts,
            wall_index=idx,
            floor_z=floor_z,
            bin_size=bin_size,
            min_opening_width=min_opening_width,
            perpendicular_tolerance=perpendicular_tolerance,
        )

        for op in wall_openings:
            if op.opening_type == "Door":
                op.tag = f"D{door_count}"
                door_count += 1
                doors.append(op)
            else:
                op.tag = f"W{window_count}"
                window_count += 1
                windows.append(op)
            all_openings.append(op)

    return OpeningDetectionResult(
        openings=all_openings,
        doors=doors,
        windows=windows,
        num_openings=len(all_openings),
        num_doors=len(doors),
        num_windows=len(windows),
    )
