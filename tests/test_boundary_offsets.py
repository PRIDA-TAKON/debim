"""
Unit tests for boundary coordinate arithmetic expressions and slab elevation_offset.
"""

import pytest
from debim.schema import (
    Grids,
    IfcSlab,
    Material,
    ProjectInfo,
    ProjectManifest,
    SlabPlacement,
    SpatialStructure,
    Storey,
)
from debim.resolver import SpatialResolver, resolve_manifest
from debim.qto import calculate_element_qto, calculate_qto


def test_parse_coordinate_expression():
    manifest = ProjectManifest(
        project=ProjectInfo(id="P1", name="Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="S1", name="L1", elevation=0.0, height=3.0)]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 4.0, "3": 8.0, "GX_1": 0.0},
            axes_y={"A": 0.0, "B": 5.0, "C": 10.0, "GY_2": 5.0},
        ),
        materials=[
            Material(id="CONCRETE_C25", name="Concrete C25", category="concrete", unit_cost_ref="REF1")
        ],
        elements=[],
    )
    resolver = SpatialResolver(manifest)

    # Simple grid name
    assert resolver.parse_coordinate_expression("1", is_x=True) == 0.0
    assert resolver.parse_coordinate_expression("B", is_x=False) == 5.0

    # Direct float
    assert resolver.parse_coordinate_expression("2.50", is_x=True) == 2.50
    assert resolver.parse_coordinate_expression("-1.20", is_x=False) == -1.20

    # Arithmetic subtraction
    assert resolver.parse_coordinate_expression("1 - 0.60", is_x=True) == pytest.approx(-0.60)
    assert resolver.parse_coordinate_expression("B - 0.50", is_x=False) == pytest.approx(4.50)

    # Arithmetic addition
    assert resolver.parse_coordinate_expression("2 + 1.20", is_x=True) == pytest.approx(5.20)
    assert resolver.parse_coordinate_expression("B + 1.20", is_x=False) == pytest.approx(6.20)

    # Combined get_grid_xy
    gx, gy = resolver.get_grid_xy(("1 - 0.60", "B + 1.20"))
    assert gx == pytest.approx(-0.60)
    assert gy == pytest.approx(6.20)


def test_recessed_bathroom_slab_takeoff():
    manifest = ProjectManifest(
        project=ProjectInfo(id="P1", name="Bathroom Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="S1", name="L1", elevation=3.50, height=3.0)]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 3.0},
            axes_y={"A": 0.0, "B": 2.0},
        ),
        materials=[
            Material(id="CONCRETE_C25", name="Concrete C25", category="concrete", unit_cost_ref="REF1")
        ],
        elements=[
            IfcSlab(
                class_="IfcSlab",
                tag="SLAB-BATHROOM",
                material="CONCRETE_C25",
                thickness=0.10,
                elevation_offset=-0.10,  # Recessed / sunken bathroom slab (10 cm drop)
                placement=SlabPlacement(
                    boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")],
                    storey="S1",
                ),
            )
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.slabs) == 1
    r_slab = resolved.slabs[0]

    # Verification of 3D elevation Z
    # Storey elevation is 3.50m, elevation_offset is -0.10m -> 3.40m
    expected_z = 3.50 - 0.10
    assert r_slab.center[2] == pytest.approx(expected_z)
    for vertex in r_slab.polygon:
        assert vertex[2] == pytest.approx(expected_z)

    # Area & QTO Takeoff Verification
    expected_area = 3.0 * 2.0  # 6.0 m2
    expected_vol = expected_area * 0.10  # 0.60 m3

    assert r_slab.area == pytest.approx(expected_area)

    qto = calculate_element_qto(r_slab)
    assert qto.concrete_volume == pytest.approx(expected_vol)
    assert qto.formwork_area == pytest.approx(expected_area)  # Soffit formwork


def test_cantilever_balcony_slab_takeoff():
    manifest = ProjectManifest(
        project=ProjectInfo(id="P1", name="Balcony Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="S1", name="L1", elevation=0.0, height=3.0)]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 4.0},
            axes_y={"A": 0.0, "B": 5.0},
        ),
        materials=[
            Material(id="CONCRETE_C25", name="Concrete C25", category="concrete", unit_cost_ref="REF1")
        ],
        elements=[
            IfcSlab(
                class_="IfcSlab",
                tag="SLAB-BALCONY",
                material="CONCRETE_C25",
                thickness=0.12,
                placement=SlabPlacement(
                    # Cantilever balcony extending 1.20m beyond Grid 1 in -X, between Grid A and B
                    boundary=[
                        ("1 - 1.20", "A"),
                        ("1", "A"),
                        ("1", "B"),
                        ("1 - 1.20", "B"),
                    ],
                    storey="S1",
                ),
            )
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.slabs) == 1
    r_slab = resolved.slabs[0]

    # Check Resolved polygon coordinates
    xs = [pt[0] for pt in r_slab.polygon]
    ys = [pt[1] for pt in r_slab.polygon]
    assert min(xs) == pytest.approx(-1.20)
    assert max(xs) == pytest.approx(0.0)
    assert min(ys) == pytest.approx(0.0)
    assert max(ys) == pytest.approx(5.0)

    # Area & QTO Takeoff Verification
    expected_area = 1.20 * 5.0  # 6.0 m2
    expected_vol = expected_area * 0.12  # 0.72 m3

    assert r_slab.area == pytest.approx(expected_area)

    qto = calculate_element_qto(r_slab)
    assert qto.concrete_volume == pytest.approx(expected_vol)
    assert qto.formwork_area == pytest.approx(expected_area)


def test_combined_boundary_offset_and_elevation_offset():
    manifest = ProjectManifest(
        project=ProjectInfo(id="P1", name="Combined Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="S1", name="L2", elevation=3.50, height=3.0)]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 6.0},
            axes_y={"A": 0.0, "B": 4.0},
        ),
        materials=[
            Material(id="CONCRETE_C25", name="Concrete C25", category="concrete", unit_cost_ref="REF1")
        ],
        elements=[
            IfcSlab(
                class_="IfcSlab",
                tag="SLAB-BALCONY-RECESSED",
                material="CONCRETE_C25",
                thickness=0.15,
                elevation_offset=-0.05,  # 5 cm recessed balcony step
                placement=SlabPlacement(
                    boundary=[
                        ("1", "B"),
                        ("2 + 1.50", "B"),
                        ("2 + 1.50", "B + 1.20"),
                        ("1", "B + 1.20"),
                    ],
                    storey="S1",
                ),
            )
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.slabs) == 1
    r_slab = resolved.slabs[0]

    # Verify Z coordinates
    assert r_slab.center[2] == pytest.approx(3.50 - 0.05)

    # Verify dimensions & QTO
    # Width = 6.0 + 1.50 = 7.50m, Depth = 1.20m
    expected_area = 7.50 * 1.20  # 9.0 m2
    expected_vol = 9.0 * 0.15   # 1.35 m3

    assert r_slab.area == pytest.approx(expected_area)

    project_qto = calculate_qto(manifest)
    assert project_qto.total_concrete_volume >= expected_vol
