"""
Unit tests for Architectural & Regulatory Compliance (Layers 1 & 2) in debim audit.
"""

import pytest
from pathlib import Path
from debim.schema import (
    ProjectManifest,
    ProjectInfo,
    SpatialStructure,
    Storey,
    Grids,
    Material,
    IfcSpace,
    SpacePlacement,
    SpaceDesignSpec,
    IfcWall,
    WallPlacement,
    IfcWindow,
    Dimensions,
    IfcStair,
    StairPlacement,
)
from debim.audit import AuditMatrixEvaluator, run_5_layer_audit


@pytest.fixture
def minimal_manifest():
    return ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="PROJ-ARCH", name="Architectural Test House"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="FL1", name="Floor 1", elevation=0.0, height=3.0),
                Storey(id="FL2", name="Floor 2", elevation=3.0, height=3.0),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 5.0, "3": 10.0},
            axes_y={"A": 0.0, "B": 6.0, "C": 12.0},
        ),
        materials=[
            Material(id="CONCRETE", name="Structural Concrete", category="concrete", unit_cost_ref="MAT-CONC"),
            Material(id="BRICK", name="Masonry Brick", category="masonry", unit_cost_ref="MAT-BRICK"),
            Material(id="GLASS", name="Clear Glass", category="glass", unit_cost_ref="MAT-GLASS"),
        ],
        elements=[
            IfcSpace(
                tag="SPACE-LIVING",
                name="Living Room",
                height=2.80,
                placement=SpacePlacement(storey="FL1", boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")]),
                design_spec=SpaceDesignSpec(min_area=20.0),
            ),
            IfcSpace(
                tag="SPACE-WC",
                name="Bathroom",
                room_number="102",
                drop_elevation=-0.10,
                placement=SpacePlacement(storey="FL1", boundary=[("2", "A"), ("3", "A"), ("3", "B"), ("2", "B")]),
                design_spec=SpaceDesignSpec(min_area=5.0),
            ),
            IfcWall(
                tag="WALL-1",
                material="BRICK",
                thickness=0.15,
                height=2.80,
                placement=WallPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="FL1"),
            ),
            IfcWall(
                tag="WALL-2",
                material="BRICK",
                thickness=0.15,
                height=2.80,
                placement=WallPlacement(from_grid=("2", "A"), to_grid=("3", "A"), storey="FL1"),
            ),
            IfcWindow(
                tag="WIN-1",
                material="GLASS",
                dimensions=Dimensions(width=2.0, height=1.5),
                offset_distance=1.0,
                host_wall="WALL-1",
            ),
            IfcWindow(
                tag="WIN-2",
                material="GLASS",
                dimensions=Dimensions(width=2.0, height=1.5),
                offset_distance=1.0,
                host_wall="WALL-2",
            ),
        ],
    )


def test_layer1_spatial_and_functional_pass(minimal_manifest):
    evaluator = AuditMatrixEvaluator(minimal_manifest)
    res1 = evaluator.evaluate_layer_1()
    assert res1.layer == 1
    assert res1.passed is True
    assert res1.violations_count == 0


def test_layer1_undersized_space_violation(minimal_manifest):
    # Set min_area to 50.0m² for space area 30.0m²
    minimal_manifest.elements[0].design_spec.min_area = 50.0
    evaluator = AuditMatrixEvaluator(minimal_manifest)
    res1 = evaluator.evaluate_layer_1()
    assert res1.passed is False
    assert res1.violations_count > 0
    v = res1.items[0]
    assert v.rule_code == "LAYER1_NET_AREA"
    assert v.remediation.fix_action == "EXPAND_SPACE"


def test_layer2_natural_ventilation_and_wet_drop(minimal_manifest):
    evaluator = AuditMatrixEvaluator(minimal_manifest)
    res2 = evaluator.evaluate_layer_2()
    # Bathroom drop is -0.10m, Living has 3.0m² window for 30m² space (10% vent)
    assert res2.layer == 2
    assert res2.passed is True

    # Violate wet room drop elevation
    minimal_manifest.elements[1].drop_elevation = 0.0
    evaluator2 = AuditMatrixEvaluator(minimal_manifest)
    res2_fail = evaluator2.evaluate_layer_2()
    assert res2_fail.passed is False
    v = [item for item in res2_fail.items if item.rule_code == "LAYER2_BATHROOM_SLAB_DROP"][0]
    assert v.remediation.fix_action == "LOWER_SLAB_DROP"


def test_layer2_stair_geometry_limits(minimal_manifest):
    # Add stair with steep riser (0.22m > 0.20m)
    minimal_manifest.elements.append(
        IfcStair(
            tag="STAIR-1",
            material="CONCRETE",
            stair_type="DOG_LEG",
            width=1.0,
            riser_height=0.22,
            tread_depth=0.20,
            placement=StairPlacement(grid_anchor=("1", "A"), from_storey="FL1", to_storey="FL2"),
        )
    )
    evaluator = AuditMatrixEvaluator(minimal_manifest)
    res2 = evaluator.evaluate_layer_2()
    assert res2.passed is False
    v = [item for item in res2.items if item.rule_code == "LAYER2_STAIR_GEOMETRY"][0]
    assert v.remediation.fix_action == "ADJUST_STAIR"
