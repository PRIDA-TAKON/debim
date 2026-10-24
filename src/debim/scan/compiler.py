"""
debim.scan.compiler

Assembles extracted architectural geometry (storeys, walls, doors, windows)
from 3D point cloud scans into standard declarative .debim (project.yaml) manifest models.
Exposes scan_ingest and compile_scan_to_manifest for CLI integration and programmatic compilation.
"""

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import yaml

from debim.scan.calibrator import calibrate_point_cloud, CalibrationResult
from debim.scan.slicer import slice_point_cloud, StoreyHeightResult, SliceResult
from debim.scan.wall_extractor import extract_walls, ExtractedWall, WallExtractionResult
from debim.scan.opening_detector import detect_openings, DetectedOpening, OpeningDetectionResult
from debim.schema import (
    Dimensions,
    Grids,
    IfcDoor,
    IfcWall,
    IfcWindow,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    Units,
    WallPlacement,
)


def _cluster_coordinates(coords: List[float], tolerance: float = 0.05) -> List[float]:
    """Cluster close 1D coordinates within tolerance and return sorted cluster averages."""
    if not coords:
        return []
    sorted_coords = sorted(coords)
    clusters: List[List[float]] = []

    for c in sorted_coords:
        if not clusters:
            clusters.append([c])
        else:
            if c - clusters[-1][-1] <= tolerance:
                clusters[-1].append(c)
            else:
                clusters.append([c])

    means = [float(round(sum(group) / len(group), 3)) for group in clusters]
    return sorted(list(set(means)))


def _find_nearest_grid(val: float, grid_map: Dict[str, float]) -> str:
    """Find grid label key in grid_map closest to coordinate value val."""
    if not grid_map:
        return "1"
    best_key = list(grid_map.keys())[0]
    best_dist = abs(val - grid_map[best_key])
    for k, v in grid_map.items():
        dist = abs(val - v)
        if dist < best_dist:
            best_dist = dist
            best_key = k
    return best_key


def compile_scan_to_manifest(
    pointcloud_or_file: Union[str, Path, np.ndarray],
    output_path: Optional[Union[str, Path]] = None,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    thickness: float = 0.15,
    target_door_height: float = 2.00,
) -> ProjectManifest:
    """
    Ingests raw or uncalibrated point cloud (.ply or XYZ array), performs:
    1. Metric scale and floor orientation calibration
    2. Storey floor & ceiling height detection
    3. Eye-level horizontal 2D slice extraction
    4. 2D RANSAC wall centerline extraction & corner snapping
    5. Vertical point density opening detection (doors & windows)
    6. Assembles storeys, grids, materials, walls, doors, windows into ProjectManifest
    7. Optionally serializes to project.yaml at output_path.

    Returns:
        Valid ProjectManifest object.
    """
    # 1. Calibrate point cloud
    calib_res = calibrate_point_cloud(
        pointcloud_or_file,
        target_door_height=target_door_height,
    )

    # 2 & 3. Storey height detection & eye-level slice extraction
    storey_res, slice_res = slice_point_cloud(calib_res.calibrated_points)

    # 4. 2D RANSAC wall centerline extraction & corner snapping
    wall_res = extract_walls(
        slice_res,
        thickness=thickness,
        height=storey_res.storey_height,
    )

    # 5. Door & window opening detection along wall lines
    opening_res = detect_openings(
        wall_res,
        calib_res.calibrated_points,
        floor_z=storey_res.floor_z,
    )

    # 6. Assemble grid axes from wall endpoints
    raw_xs: List[float] = []
    raw_ys: List[float] = []

    for w in wall_res.walls:
        raw_xs.append(w.start_point[0])
        raw_xs.append(w.end_point[0])
        raw_ys.append(w.start_point[1])
        raw_ys.append(w.end_point[1])

    clustered_xs = _cluster_coordinates(raw_xs, tolerance=0.05)
    clustered_ys = _cluster_coordinates(raw_ys, tolerance=0.05)

    axes_x: Dict[str, float] = {}
    axes_y: Dict[str, float] = {}

    if not clustered_xs:
        axes_x = {"X1": 0.00, "X2": 5.00}
    else:
        for idx, x_val in enumerate(clustered_xs, start=1):
            axes_x[f"X{idx}"] = x_val

    if not clustered_ys:
        axes_y = {"Y1": 0.00, "Y2": 5.00}
    else:
        for idx, y_val in enumerate(clustered_ys, start=1):
            axes_y[f"Y{idx}"] = y_val

    # Group openings by wall_index
    openings_by_wall: Dict[int, List[DetectedOpening]] = {}
    for op in opening_res.openings:
        openings_by_wall.setdefault(op.wall_index, []).append(op)

    # Assemble elements (IfcWall with child IfcDoor / IfcWindow)
    manifest_elements: List[Any] = []

    for idx, w in enumerate(wall_res.walls):
        w_tag = f"WALL-{idx + 1}"
        x1, y1 = w.start_point
        x2, y2 = w.end_point

        gx1 = _find_nearest_grid(x1, axes_x)
        gy1 = _find_nearest_grid(y1, axes_y)
        gx2 = _find_nearest_grid(x2, axes_x)
        gy2 = _find_nearest_grid(y2, axes_y)

        dx = x2 - x1
        dy = y2 - y1
        wall_len = math.hypot(dx, dy)
        if wall_len > 1e-6:
            ux, uy = dx / wall_len, dy / wall_len
        else:
            ux, uy = 1.0, 0.0

        children: List[Any] = []
        wall_ops = openings_by_wall.get(idx, [])

        for op in wall_ops:
            # Scalar offset distance along wall baseline
            t = (op.center_point[0] - x1) * ux + (op.center_point[1] - y1) * uy
            offset_dist = round(max(0.0, min(wall_len, t)), 3)
            w_dim = round(op.width, 3)
            h_dim = round(op.height, 3)
            sill_h = round(op.sill_height, 3)

            if op.opening_type == "Door":
                door = IfcDoor(
                    tag=op.tag,
                    dimensions=Dimensions(width=w_dim, height=h_dim),
                    offset_distance=offset_dist,
                    sill_height=sill_h,
                    material="TIMBER",
                )
                children.append(door)
            else:
                win = IfcWindow(
                    tag=op.tag,
                    dimensions=Dimensions(width=w_dim, height=h_dim),
                    offset_distance=offset_dist,
                    sill_height=sill_h,
                    material="GLASS",
                )
                children.append(win)

        ifc_wall = IfcWall(
            tag=w_tag,
            thickness=round(w.thickness, 3),
            height=round(w.height, 3),
            material="CONCRETE_MASONRY",
            placement=WallPlacement(
                from_grid=(gx1, gy1),
                to_grid=(gx2, gy2),
                storey="STOREY-1",
            ),
            children=children,
        )
        manifest_elements.append(ifc_wall)

    # Project metadata
    if isinstance(pointcloud_or_file, (str, Path)):
        stem_name = Path(pointcloud_or_file).stem.upper()
    else:
        stem_name = "ARRAY"

    prj_id = project_id or f"PRJ-SCAN-{stem_name}"
    prj_name = project_name or f"Scan Ingested Project ({stem_name})"

    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(
            id=prj_id,
            name=prj_name,
            units=Units(length="METER", area="SQUARE_METER", volume="CUBIC_METER"),
        ),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(
                    id="STOREY-1",
                    name="Storey 1",
                    elevation=round(storey_res.floor_z, 3),
                    height=round(storey_res.storey_height, 3),
                )
            ]
        ),
        grids=Grids(axes_x=axes_x, axes_y=axes_y),
        materials=[
            Material(
                id="CONCRETE_MASONRY",
                name="Concrete Masonry Wall",
                category="MASONRY",
                unit_cost_ref="MAT-WALL-MASONRY",
            ),
            Material(
                id="TIMBER",
                name="Timber Door",
                category="TIMBER",
                unit_cost_ref="MAT-DOOR-TIMBER",
            ),
            Material(
                id="GLASS",
                name="Clear Glass Window",
                category="GLASS",
                unit_cost_ref="MAT-WIN-GLASS",
            ),
        ],
        elements=manifest_elements,
    )

    # 7. Serialize to output_path if provided
    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        dict_data = manifest.model_dump(by_alias=True, exclude_none=True)
        yaml_str = yaml.safe_dump(dict_data, sort_keys=False, allow_unicode=True)

        header_comment = (
            f"# ==============================================================================\n"
            f"# Point Cloud Scan Ingested Manifest: {prj_id}\n"
            f"# Extracted Storey Height: {storey_res.storey_height:.2f}m | Walls: {len(wall_res.walls)} | Openings: {opening_res.num_openings}\n"
            f"# Generated by debim scan ingest compiler\n"
            f"# ==============================================================================\n\n"
        )
        out_p.write_text(header_comment + yaml_str, encoding="utf-8")

    return manifest


def scan_ingest(
    pointcloud_path: Union[str, Path],
    output_path: Union[str, Path] = "project.yaml",
) -> Path:
    """
    High-level entry point to ingest point cloud .ply file and emit project.yaml.
    Returns absolute Path to output_path.
    """
    out_p = Path(output_path)
    compile_scan_to_manifest(
        pointcloud_or_file=pointcloud_path,
        output_path=out_p,
    )
    return out_p.resolve()
