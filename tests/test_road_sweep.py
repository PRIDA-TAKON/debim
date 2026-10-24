"""
Unit tests for 3D Road Alignment Sweeper (RMF / Bishop Frame), Terrain Auto-Drape,
and IFC4.3 Compilation.
"""

import math
from pathlib import Path
import ifcopenshell
import pytest

from debim.compiler import compile_to_ifc
from debim.geometry.drape import drape_points_to_terrain, subdivide_polyline
from debim.geometry.sweep3d import (
    compute_rmf_frames,
    create_road_camber_profile,
    sweep_cross_section_rmf,
)
from debim.resolver import resolve_manifest
from debim.schema import (
    AlignmentPoint,
    CRSConfig,
    Grids,
    IfcAlignment,
    IfcRoad,
    ProjectInfo,
    ProjectManifest,
    RoadPlacement,
    SiteBoundary,
    SiteTerrain,
    SpatialStructure,
    Storey,
)
from debim.terrain import SurveyData, SurveyPoint, generate_terrain_mesh


def test_rmf_frame_normal_vector_consistency():
    """Test Rotation Minimizing Frame (RMF / Bishop Frame) normal vector continuity on steep 3D slopes."""
    # 3D curve with steep climbs, S-curves, and vertical undulations
    points = [
        (0.0, 0.0, 0.0),
        (10.0, 5.0, 2.0),
        (20.0, 15.0, 8.0),
        (30.0, 10.0, 15.0),
        (40.0, 0.0, 22.0),
        (50.0, -10.0, 25.0),
        (60.0, 0.0, 20.0),
    ]

    frames = compute_rmf_frames(points)
    assert len(frames) == len(points)

    for i, frame in enumerate(frames):
        T = frame["tangent"]
        N = frame["normal"]
        B = frame["binormal"]

        # 1. Check unit lengths
        assert math.isclose(math.sqrt(sum(x * x for x in T)), 1.0, abs_tol=1e-4)
        assert math.isclose(math.sqrt(sum(x * x for x in N)), 1.0, abs_tol=1e-4)
        assert math.isclose(math.sqrt(sum(x * x for x in B)), 1.0, abs_tol=1e-4)

        # 2. Check orthonormality (dot products == 0)
        dot_TN = sum(a * b for a, b in zip(T, N))
        dot_TB = sum(a * b for a, b in zip(T, B))
        dot_NB = sum(a * b for a, b in zip(N, B))

        assert abs(dot_TN) < 1e-4
        assert abs(dot_TB) < 1e-4
        assert abs(dot_NB) < 1e-4

        # 3. Check normal vector continuity across adjacent frames (no gimbal flips or 180-deg twists)
        if i > 0:
            prev_N = frames[i - 1]["normal"]
            dot_NN = sum(a * b for a, b in zip(prev_N, N))
            assert dot_NN > 0.70, f"Discontinuity or gimbal flip at frame {i}: dot(N_{i-1}, N_{i}) = {dot_NN}"


def test_terrain_auto_drape_precision():
    """Test projecting 2D horizontal waypoints onto TIN terrain mesh with offset_z elevation precision."""
    # Define a planar sloped terrain: z(x, y) = 0.1 * x + 0.2 * y + 10.0
    pts = [
        SurveyPoint(0.0, 0.0, 10.0),
        SurveyPoint(100.0, 0.0, 20.0),
        SurveyPoint(100.0, 100.0, 40.0),
        SurveyPoint(0.0, 100.0, 30.0),
        SurveyPoint(50.0, 50.0, 25.0),
    ]
    survey = SurveyData(points=pts)
    terrain = generate_terrain_mesh(survey, clip_to_boundary=False)

    road_waypoints = [
        (10.0, 10.0, 0.0),
        (50.0, 30.0, 0.0),
        (90.0, 80.0, 0.0),
    ]

    offset_z = 0.05
    draped = drape_points_to_terrain(road_waypoints, terrain, offset_z=offset_z, max_step_size=5.0)

    assert len(draped) >= len(road_waypoints)

    for px, py, pz in draped:
        expected_z_terrain = terrain.get_elevation_at(px, py)
        expected_z = expected_z_terrain + offset_z
        assert pytest.approx(pz, abs=1e-3) == expected_z


def test_road_camber_profile_and_sweep():
    """Test creating 2% camber crowned road cross-section and sweeping along RMF frames."""
    profile = create_road_camber_profile(width=7.0, thickness=0.20, camber_slope=0.02)
    assert len(profile) == 6

    # Crown center
    assert profile[0] == (0.0, 0.0)
    # Right edge top
    assert profile[1] == (3.5, -0.07)
    # Right edge bottom
    assert profile[2] == (3.5, -0.27)
    # Left edge top
    assert profile[5] == (-3.5, -0.07)

    waypoints = [
        (0.0, 0.0, 0.0),
        (20.0, 0.0, 1.0),
        (40.0, 10.0, 3.0),
        (60.0, 20.0, 2.0),
    ]
    frames = compute_rmf_frames(waypoints)
    mesh = sweep_cross_section_rmf(profile, frames, one_based=True)

    expected_verts = len(frames) * len(profile)
    assert len(mesh["vertices"]) == expected_verts
    assert len(mesh["faces"]) > 0


def test_road_manifest_resolution_and_ifc_compilation(tmp_path: Path):
    """Test full manifest resolution with terrain auto-drape and IFC4.3 road export."""
    # Write temporary terrain survey file
    survey_json = tmp_path / "terrain.json"
    survey_json.write_text("""{
        "points": [
            [0, 0, 5.0],
            [100, 0, 10.0],
            [100, 100, 20.0],
            [0, 100, 15.0],
            [50, 50, 12.5]
        ]
    }""", encoding="utf-8")

    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-ROAD-01", name="3D Road Sweep Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 100.0}, axes_y={"A": 0.0, "B": 100.0}),
        materials=[],
        site=SiteBoundary(
            terrain=SiteTerrain(source=str(survey_json), format="json")
        ),
        elements=[
            IfcRoad(
                tag="ROAD-MAIN-01",
                predefined_type="CARRIAGEWAY",
                road_width=7.00,
                pavement_surface_thickness=0.05,
                pavement_base_thickness=0.15,
                pavement_subbase_thickness=0.20,
                placement=RoadPlacement(
                    drape_to="terrain",
                    camber_slope=0.02,
                    offset_z=0.05,
                    points=[
                        AlignmentPoint(x=10.0, y=10.0, z=0.0),
                        AlignmentPoint(x=50.0, y=50.0, z=0.0),
                        AlignmentPoint(x=90.0, y=90.0, z=0.0),
                    ]
                )
            )
        ]
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.roads) == 1

    resolved_road = resolved.roads[0]
    assert resolved_road.swept_mesh is not None
    assert len(resolved_road.swept_mesh["vertices"]) > 0
    assert len(resolved_road.swept_mesh["faces"]) > 0

    # Assert centerline points are draped above terrain level (> 5.0m elevation)
    for p in resolved_road.centerline_points:
        assert p[2] > 5.0

    # Test IFC compilation
    ifc_out = tmp_path / "road_model.ifc"
    compile_to_ifc(resolved, output_path=ifc_out)
    assert ifc_out.exists()

    ifc_model = ifcopenshell.open(str(ifc_out))
    roads = ifc_model.by_type("IfcRoad")
    assert len(roads) == 1

    tess_sets = ifc_model.by_type("IfcTriangulatedFaceSet")
    assert len(tess_sets) >= 1
