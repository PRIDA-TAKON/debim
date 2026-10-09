"""
Unit tests for IFC4.3 Alignment 3D Curve Sweeping and Corridor Modeler.
Verifies linear tangents, circular arcs, clothoid spirals, vertical parabolic curves,
cant transitions, Frenet-Serret frames, cross-section sweeping, and valid 3D mesh creation.
"""

import math
from pathlib import Path
import tempfile
import ifcopenshell
import ifcopenshell.geom
import pytest

from debim.civil.alignment_sweeper import AlignmentSweeper, numerical_integration_clothoid
from debim.compiler import compile_to_ifc
from debim.resolver import resolve_manifest
from debim.schema import (
    AlignmentCantSegment,
    AlignmentHorizontalSegment,
    AlignmentVerticalSegment,
    CorridorCrossSection,
    Grids,
    IfcAlignment,
    IfcAlignmentCant,
    IfcAlignmentHorizontal,
    IfcAlignmentVertical,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)


def test_clothoid_numerical_integration():
    """Test clothoid spiral numerical integration accuracy."""
    x0, y0, th0 = 0.0, 0.0, 0.0
    k0, k1 = 0.0, 1.0 / 100.0  # Spiral from straight (R=inf) to R=100m
    length = 50.0

    x, y, heading = numerical_integration_clothoid(x0, y0, th0, k0, k1, length, s_eval=length)

    # Heading at end should be theta0 + (k0+k1)*L/2 = 0.5 * 0.01 * 50 = 0.25 rad
    expected_heading = 0.25
    assert abs(heading - expected_heading) < 1e-4
    assert x > 40.0  # X moves along tangent
    assert y > 0.0   # Y curves upward into spiral


def test_alignment_curve_interpolation_and_frames():
    """Test discretization of horizontal line, circular arc, and clothoid spiral segments."""
    align = IfcAlignment(
        tag="ALIGN-COMPLEX-01",
        name="Complex Alignment",
        start_chainage=0.0,
        horizontal=IfcAlignmentHorizontal(
            segments=[
                AlignmentHorizontalSegment(
                    segment_type="LINE",
                    start_point=(0.0, 0.0),
                    start_direction=0.0,
                    segment_length=100.0,
                ),
                AlignmentHorizontalSegment(
                    segment_type="CLOTHOID",
                    start_point=(100.0, 0.0),
                    start_direction=0.0,
                    start_radius_of_curvature=0.0,
                    end_radius_of_curvature=200.0,
                    segment_length=50.0,
                ),
                AlignmentHorizontalSegment(
                    segment_type="CIRCULARARC",
                    start_point=(150.0, 5.0),
                    start_direction=0.125,
                    start_radius_of_curvature=200.0,
                    end_radius_of_curvature=200.0,
                    segment_length=100.0,
                ),
            ]
        ),
        vertical=IfcAlignmentVertical(
            segments=[
                AlignmentVerticalSegment(
                    segment_type="LINE",
                    start_dist_along=0.0,
                    horizontal_length=100.0,
                    start_height=10.0,
                    start_gradient=0.02,
                ),
                AlignmentVerticalSegment(
                    segment_type="PARABOLA",
                    start_dist_along=100.0,
                    horizontal_length=150.0,
                    start_height=12.0,
                    start_gradient=0.02,
                    end_gradient=-0.01,
                ),
            ]
        ),
        cant=IfcAlignmentCant(
            segments=[
                AlignmentCantSegment(
                    segment_type="CONSTANTCANT",
                    start_dist_along=0.0,
                    horizontal_length=100.0,
                    start_cant=0.0,
                ),
                AlignmentCantSegment(
                    segment_type="LINEARTRANSITION",
                    start_dist_along=100.0,
                    horizontal_length=150.0,
                    start_cant=0.0,
                    end_cant=0.12,  # 120mm cant
                ),
            ]
        ),
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )

    sweeper = AlignmentSweeper(align)
    frames = sweeper.discretize_frames(step_size=10.0)
    assert len(frames) >= 20

    # Verify smooth normal vectors and frame orthonormality (T . N = 0, T . B = 0, N . B = 0)
    for frame in frames:
        P = frame["position"]
        T = frame["tangent"]
        N = frame["normal"]
        B = frame["binormal"]

        # Unit lengths
        assert abs(math.sqrt(sum(x * x for x in T)) - 1.0) < 1e-4
        assert abs(math.sqrt(sum(x * x for x in N)) - 1.0) < 1e-4
        assert abs(math.sqrt(sum(x * x for x in B)) - 1.0) < 1e-4

        # Orthogonality
        dot_TN = sum(T[i] * N[i] for i in range(3))
        dot_TB = sum(T[i] * B[i] for i in range(3))
        dot_NB = sum(N[i] * B[i] for i in range(3))
        assert abs(dot_TN) < 1e-4
        assert abs(dot_TB) < 1e-4
        assert abs(dot_NB) < 1e-4


def test_corridor_cross_sections_sweeping():
    """Test sweeping arbitrary cross sections (carriageway, curb, median, rail)."""
    align = IfcAlignment(
        tag="ALIGN-CORRIDOR-01",
        cross_sections=[
            CorridorCrossSection(
                name="carriageway_left",
                points=[(-7.0, 0.0), (-0.5, 0.0), (-0.5, -0.3), (-7.0, -0.3)],
            ),
            CorridorCrossSection(
                name="median",
                points=[(-0.5, 0.0), (0.5, 0.0), (0.5, 0.25), (-0.5, 0.25)],
            ),
            CorridorCrossSection(
                name="carriageway_right",
                points=[(0.5, 0.0), (7.0, 0.0), (7.0, -0.3), (0.5, -0.3)],
            ),
            CorridorCrossSection(
                name="curb",
                points=[(7.0, 0.0), (7.5, 0.0), (7.5, 0.15), (7.0, 0.15)],
            ),
            CorridorCrossSection(
                name="rail_track",
                points=[(-0.7175, 0.0), (0.7175, 0.0), (0.7175, 0.15), (-0.7175, 0.15)],
            ),
        ],
        placement={"points": [[0, 0, 0], [100, 0, 0], [200, 50, 5]]},
    )

    sweeper = AlignmentSweeper(align)
    frames = sweeper.discretize_frames(step_size=20.0)
    solids = sweeper.sweep_corridor_solids(frames)

    assert len(solids) == 5
    solid_names = [s["name"] for s in solids]
    assert "carriageway_left" in solid_names
    assert "median" in solid_names
    assert "carriageway_right" in solid_names
    assert "curb" in solid_names
    assert "rail_track" in solid_names

    for solid in solids:
        assert len(solid["vertices"]) > 0
        assert len(solid["faces"]) > 0


def test_corridor_3d_ifcopenshell_mesh_generation(tmp_path: Path):
    """Test full 3D IFC compilation and mesh generation via ifcopenshell.geom.create_shape."""
    align = IfcAlignment(
        tag="ALIGN-HW-SWEEP",
        name="Highway Corridor Swept Solid",
        start_chainage=1000.0,
        horizontal=IfcAlignmentHorizontal(
            segments=[
                AlignmentHorizontalSegment(
                    segment_type="LINE",
                    start_point=(0.0, 0.0),
                    start_direction=0.0,
                    segment_length=50.0,
                ),
                AlignmentHorizontalSegment(
                    segment_type="CLOTHOID",
                    start_point=(50.0, 0.0),
                    start_direction=0.0,
                    start_radius_of_curvature=0.0,
                    end_radius_of_curvature=150.0,
                    segment_length=30.0,
                ),
                AlignmentHorizontalSegment(
                    segment_type="CIRCULARARC",
                    start_point=(80.0, 3.0),
                    start_direction=0.10,
                    start_radius_of_curvature=150.0,
                    end_radius_of_curvature=150.0,
                    segment_length=60.0,
                ),
            ]
        ),
        vertical=IfcAlignmentVertical(
            segments=[
                AlignmentVerticalSegment(
                    segment_type="PARABOLA",
                    start_dist_along=0.0,
                    horizontal_length=140.0,
                    start_height=5.0,
                    start_gradient=0.03,
                    end_gradient=-0.02,
                )
            ]
        ),
        cant=IfcAlignmentCant(
            segments=[
                AlignmentCantSegment(
                    segment_type="LINEARTRANSITION",
                    start_dist_along=0.0,
                    horizontal_length=140.0,
                    start_cant=0.0,
                    end_cant=0.15,
                )
            ]
        ),
        cross_sections=[
            CorridorCrossSection(
                name="carriageway",
                points=[(-3.5, 0.0), (3.5, 0.0), (3.5, -0.35), (-3.5, -0.35)],
            ),
            CorridorCrossSection(
                name="curb",
                points=[(3.5, 0.0), (3.8, 0.0), (3.8, 0.20), (3.5, 0.20)],
            ),
        ],
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )

    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-SWEEP-01", name="Corridor Sweeper Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0}, axes_y={"A": 0.0}),
        materials=[],
        elements=[align],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.alignments) == 1
    r_align = resolved.alignments[0]
    assert len(r_align.frames_3d) > 0
    assert len(r_align.swept_solids) == 2

    # Compile to IFC file
    ifc_path = tmp_path / "corridor_model.ifc"
    compile_to_ifc(manifest, output_path=ifc_path)
    assert ifc_path.exists()

    # Open IFC model and verify create_shape generates valid 3D mesh
    model = ifcopenshell.open(ifc_path)
    products = model.by_type("IfcProduct")
    assert len(products) > 0

    settings = ifcopenshell.geom.settings()
    mesh_found = False
    for prod in products:
        if prod.Name == "ALIGN-HW-SWEEP":
            shape = ifcopenshell.geom.create_shape(settings, prod)
            assert shape is not None
            assert len(shape.geometry.verts) > 0
            assert len(shape.geometry.faces) > 0
            mesh_found = True

    assert mesh_found, "Valid 3D solid mesh was not generated for ALIGN-HW-SWEEP"
