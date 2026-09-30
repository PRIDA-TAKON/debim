import math
import pytest
from debim.schema import (
    IfcStair,
    StairPlacement,
    StairStepConfig,
    StairStringerConfig,
    StairFinishesConfig,
    StairRailingConfig,
    SpatialStructure,
    Storey,
    Grids,
    ProjectInfo,
    Units,
    Material,
    ProjectManifest,
)
from debim.resolver import SpatialResolver
from debim.qto import calculate_element_qto, calculate_qto


@pytest.fixture
def sample_spiral_manifest():
    return ProjectManifest(
        project=ProjectInfo(id="SPIRAL-PROJ", name="Spiral Test Project", units=Units()),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="FL1", name="Floor 1", elevation=0.00, height=3.00),
                Storey(id="FL2", name="Floor 2", elevation=3.00, height=3.00),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 5.0},
            axes_y={"A": 0.0, "B": 5.0},
        ),
        materials=[
            Material(id="STEEL_SS400", name="Structural Steel", category="steel", unit_cost_ref="cost_steel"),
            Material(id="MAT_CONC", name="Concrete", category="concrete", unit_cost_ref="cost_conc"),
        ],
        elements=[],
    )


def test_spiral_stair_schema():
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-SPIRAL-01",
            "material": "STEEL_SS400",
            "stair_type": "SPIRAL",
            "width": 1.50,
            "waist_thickness": 0.16,
            "inner_radius": 0.50,
            "total_angle": 270.0,
            "direction": "CCW",
            "placement": StairPlacement(
                grid_anchor=("1", "A"),
                from_storey="FL1",
                to_storey="FL2",
                offset_x=2.50,
                offset_y=2.50,
                offset_z=0.00,
                orientation="+Y",
            ),
            "steps": StairStepConfig(
                tread=0.25,
                riser=0.1765,
                plate_thickness=0.0032,
            ),
            "stringer": StairStringerConfig(
                material="STEEL_SS400",
                width=0.016,
                depth=1.40,
                thickness=0.016,
                base_plate_thickness=0.020,
                base_plate_width=0.30,
                base_plate_length=2.50,
                base_plate_count=2,
            ),
        }
    )
    assert stair.stair_type == "SPIRAL"
    assert stair.inner_radius == 0.50
    assert stair.total_angle == 270.0
    assert stair.direction == "CCW"
    assert stair.steps.plate_thickness == 0.0032
    assert stair.stringer.thickness == 0.016
    assert stair.stringer.base_plate_thickness == 0.020


def test_spiral_stair_resolver_geometry(sample_spiral_manifest):
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST1",
            "material": "STEEL_SS400",
            "stair_type": "SPIRAL",
            "width": 1.50,
            "waist_thickness": 0.016,
            "inner_radius": 0.50,
            "total_angle": 270.0,
            "direction": "CCW",
            "placement": StairPlacement(
                grid_anchor=("1", "A"),
                from_storey="FL1",
                to_storey="FL2",
                offset_x=2.00,
                offset_y=2.00,
                offset_z=0.00,
                orientation="+X",
            ),
            "steps": StairStepConfig(
                riser=0.1765,
                plate_thickness=0.0032,
            ),
            "stringer": StairStringerConfig(
                material="STEEL_SS400",
                width=0.016,
                depth=1.40,
                thickness=0.016,
                base_plate_thickness=0.020,
                base_plate_width=0.30,
                base_plate_length=2.50,
                base_plate_count=2,
            ),
            "railing": StairRailingConfig(
                height=0.90,
                type="STEEL_HANDRAIL",
                side="OUTER",
            ),
        }
    )
    sample_spiral_manifest.elements.append(stair)
    resolver = SpatialResolver(sample_spiral_manifest)
    res = resolver.resolve_stair(stair)

    assert res.tag == "ST1"
    assert len(res.flights) == 1
    flight = res.flights[0]

    # Check risers and height
    total_height = 3.00
    assert len(res.steps) == flight.n_risers
    assert math.isclose(flight.rise_height, total_height, rel_tol=1e-4)

    # Check radii
    r_in = 0.50
    r_out = 0.50 + 1.50  # 2.00
    r_mid = (r_in + r_out) / 2.0  # 1.25

    # Check steps follow circular arc at r_mid
    center_x = 0.0 + 2.00
    center_y = 0.0 + 2.00
    for step in res.steps:
        dist_to_center = math.hypot(step.position[0] - center_x, step.position[1] - center_y)
        assert math.isclose(dist_to_center, r_mid, rel_tol=1e-3)
        assert step.rotation != 0.0
        assert step.polygon is not None
        assert len(step.polygon) == 4

    # Check helical lengths
    tot_angle_rad = math.radians(270.0)
    expected_in_true = math.hypot(r_in * tot_angle_rad, total_height)
    expected_out_true = math.hypot(r_out * tot_angle_rad, total_height)

    assert math.isclose(res.inner_helical_length, expected_in_true, rel_tol=1e-3)
    assert math.isclose(res.outer_helical_length, expected_out_true, rel_tol=1e-3)

    # Check stringers
    assert len(res.stringers) == 2
    inner_str = next(s for s in res.stringers if "Inner" in s.tag)
    outer_str = next(s for s in res.stringers if "Outer" in s.tag)
    assert math.isclose(inner_str.length, expected_in_true, rel_tol=1e-3)
    assert math.isclose(outer_str.length, expected_out_true, rel_tol=1e-3)


def test_spiral_stair_steel_qto(sample_spiral_manifest):
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST1",
            "material": "STEEL_SS400",
            "stair_type": "SPIRAL",
            "width": 1.50,
            "waist_thickness": 0.016,
            "inner_radius": 0.50,
            "total_angle": 270.0,
            "direction": "CCW",
            "placement": StairPlacement(
                grid_anchor=("1", "A"),
                from_storey="FL1",
                to_storey="FL2",
            ),
            "steps": StairStepConfig(
                riser=0.1765,
                plate_thickness=0.0032,
            ),
            "stringer": StairStringerConfig(
                material="STEEL_SS400",
                width=0.016,
                depth=1.40,
                thickness=0.016,
                base_plate_thickness=0.020,
                base_plate_width=0.30,
                base_plate_length=2.50,
                base_plate_count=2,
            ),
        }
    )
    sample_spiral_manifest.elements.append(stair)
    resolver = SpatialResolver(sample_spiral_manifest)
    res = resolver.resolve_stair(stair)

    # Steel quantities verification
    assert res.total_steel_weight > 0.0
    assert res.stringers_steel_weight > 0.0
    assert res.treads_steel_weight > 0.0
    assert res.base_plates_steel_weight > 0.0
    assert math.isclose(
        res.total_steel_weight,
        res.stringers_steel_weight + res.treads_steel_weight + res.base_plates_steel_weight,
        rel_tol=1e-4,
    )

    # Base plates weight: 2.50 * 0.30 * 0.020 * 7850 * 2 = 235.5 kg
    assert math.isclose(res.base_plates_steel_weight, 235.5, rel_tol=1e-2)

    # QTO Element calculation
    eqto = calculate_element_qto(res)
    assert eqto.structural_steel_weight == res.total_steel_weight
    assert eqto.painting_area > 0.0
    assert eqto.stair_assembly is not None
    assert eqto.stair_assembly.steel_weight == res.total_steel_weight

    # Project QTO aggregation
    resolved_manifest = resolver.resolve()
    pqto = calculate_qto(resolved_manifest)
    assert pqto.total_structural_steel_weight >= res.total_steel_weight


def test_spiral_stair_concrete_qto(sample_spiral_manifest):
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-CONC",
            "material": "MAT_CONC",
            "stair_type": "SPIRAL",
            "width": 1.20,
            "waist_thickness": 0.15,
            "inner_radius": 0.40,
            "total_angle": 360.0,
            "placement": StairPlacement(
                grid_anchor=("1", "A"),
                from_storey="FL1",
                to_storey="FL2",
            ),
            "steps": StairStepConfig(
                riser=0.1875,
                tread=0.25,
            ),
        }
    )
    sample_spiral_manifest.elements.append(stair)
    resolver = SpatialResolver(sample_spiral_manifest)
    res = resolver.resolve_stair(stair)

    assert res.total_steel_weight == 0.0
    assert res.total_concrete_volume > 0.0
    assert res.total_formwork_area > 0.0

    eqto = calculate_element_qto(res)
    assert eqto.concrete_volume == res.total_concrete_volume
    assert eqto.formwork_area == res.total_formwork_area
    assert eqto.structural_steel_weight == 0.0
