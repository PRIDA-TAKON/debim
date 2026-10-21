"""
Unit tests for IFC4.3 Civil Infrastructure features:
Sectioned Solid Horizontal export and station distance expression anchoring.
"""

from pathlib import Path
import ifcopenshell
import pytest

from debim.civil.alignment_sweeper import AlignmentSweeper, IfcDistanceExpression
from debim.compiler import compile_to_ifc
from debim.resolver import resolve_manifest
from debim.schema import (
    AlignmentHorizontalSegment,
    AlignmentVerticalSegment,
    CorridorCrossSection,
    Grids,
    IfcAlignment,
    IfcAlignmentHorizontal,
    IfcAlignmentVertical,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)


def test_ifc_distance_expression_anchoring():
    """Test IfcDistanceExpression instantiation and point creation in IFC4.3."""
    m = ifcopenshell.file(schema="IFC4X3")
    pts = [m.createIfcCartesianPoint((0.0, 0.0, 0.0)), m.createIfcCartesianPoint((100.0, 0.0, 0.0))]
    directrix = m.createIfcPolyline(pts)

    dist_expr = IfcDistanceExpression(
        distance_along=25.0,
        offset_lateral=1.5,
        offset_vertical=0.5,
        offset_longitudinal=0.0,
    )
    ifc_point = dist_expr.to_ifc(m, basis_curve=directrix)

    assert ifc_point.is_a("IfcPointByDistanceExpression")
    assert pytest.approx(float(ifc_point.DistanceAlong.wrappedValue), 1e-4) == 25.0
    assert pytest.approx(float(ifc_point.OffsetLateral), 1e-4) == 1.5
    assert pytest.approx(float(ifc_point.OffsetVertical), 1e-4) == 0.5
    assert ifc_point.BasisCurve == directrix


def test_sectioned_solid_horizontal(tmp_path: Path):
    """Test converting station cross-section profiles to IfcSectionedSolidHorizontal (IFC4.3)."""
    align = IfcAlignment(
        tag="ALIGN-SECTIONED-01",
        name="Sukhumvit Highway Corridor",
        start_chainage=100.0,
        horizontal=IfcAlignmentHorizontal(
            segments=[
                AlignmentHorizontalSegment(
                    segment_type="LINE",
                    start_point=(0.0, 0.0),
                    start_direction=0.0,
                    segment_length=100.0,
                )
            ]
        ),
        vertical=IfcAlignmentVertical(
            segments=[
                AlignmentVerticalSegment(
                    segment_type="LINE",
                    start_dist_along=0.0,
                    horizontal_length=100.0,
                    start_height=5.0,
                    start_gradient=0.01,
                )
            ]
        ),
        cross_sections=[
            CorridorCrossSection(
                name="carriageway_road",
                points=[(-3.5, 0.0), (3.5, 0.0), (3.5, -0.30), (-3.5, -0.30)],
            ),
            CorridorCrossSection(
                name="curb_stone",
                points=[(3.5, 0.0), (3.8, 0.0), (3.8, 0.15), (3.5, 0.15)],
            ),
        ],
        placement={"offset_x": 0, "offset_y": 0, "offset_z": 0},
    )

    sweeper = AlignmentSweeper(align)
    model = ifcopenshell.file(schema="IFC4X3")
    solids = sweeper.build_sectioned_solid_horizontal(model=model, step_size=20.0)

    assert len(solids) == 2
    for solid in solids:
        assert solid.is_a("IfcSectionedSolidHorizontal")
        assert len(solid.CrossSections) >= 2
        assert len(solid.CrossSectionPositions) == len(solid.CrossSections)
        assert solid.Directrix is not None

        for pos in solid.CrossSectionPositions:
            assert pos.is_a("IfcAxis2PlacementLinear")
            assert pos.Location.is_a("IfcPointByDistanceExpression")

    # Test full manifest compilation
    manifest = ProjectManifest(
        schema="IFC4.3",
        project=ProjectInfo(id="PROJ-SECTIONED-01", name="Sectioned Solid Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GROUND", name="Ground", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0}, axes_y={"A": 0.0}),
        materials=[],
        elements=[align],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.alignments) == 1

    ifc_file = tmp_path / "sectioned_corridor.ifc"
    compile_to_ifc(resolved, output_path=ifc_file)
    assert ifc_file.exists()

    ifc_model = ifcopenshell.open(str(ifc_file))
    sectioned_entities = ifc_model.by_type("IfcSectionedSolidHorizontal")
    assert len(sectioned_entities) == 2

    points_by_dist = ifc_model.by_type("IfcPointByDistanceExpression")
    assert len(points_by_dist) > 0

    placements_linear = ifc_model.by_type("IfcAxis2PlacementLinear")
    assert len(placements_linear) > 0
