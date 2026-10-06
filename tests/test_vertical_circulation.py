import math
import pytest
from debim.schema import (
    IfcStairFlight,
    IfcRamp,
    IfcRailing,
    StairPlacement,
    RampPlacement,
    RailingPlacement,
    RailingPoint,
    SpatialStructure,
    Storey,
    Grids,
    ProjectInfo,
    Units,
    Material,
    ProjectManifest,
    CircularProfile,
)
from debim.resolver import SpatialResolver
from debim.qto import calculate_element_qto, calculate_qto
from debim.compiler import compile_to_ifc
from debim.viewer import generate_viewer_html


@pytest.fixture
def vertical_circulation_manifest():
    return ProjectManifest(
        project=ProjectInfo(id="VERT-CIRC-PROJ", name="Vertical Circulation Test Project", units=Units()),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="FL1", name="Ground Floor", elevation=0.00, height=3.50),
                Storey(id="FL2", name="Second Floor", elevation=3.50, height=3.50),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 6.0, "3": 12.0},
            axes_y={"A": 0.0, "B": 6.0, "C": 12.0},
        ),
        materials=[
            Material(id="MAT_CONC", name="Reinforced Concrete", category="concrete", unit_cost_ref="cost_conc"),
            Material(id="STEEL_SS400", name="Structural Steel", category="steel", unit_cost_ref="cost_steel"),
        ],
        elements=[],
    )


def test_stair_flight_schema_and_resolver(vertical_circulation_manifest):
    flight = IfcStairFlight(
        **{
            "class": "IfcStairFlight",
            "tag": "ST-FLIGHT-01",
            "material": "MAT_CONC",
            "flight_width": 1.20,
            "waist_thickness": 0.15,
            "number_of_risers": 10,
            "riser_height": 0.175,
            "tread_length": 0.28,
            "placement": StairPlacement(
                grid_anchor=("1", "A"),
                from_storey="FL1",
                to_storey="FL2",
                offset_x=1.00,
                offset_y=1.00,
                orientation="+Y",
            ),
        }
    )
    assert flight.flight_width == 1.20
    assert flight.width == 1.20
    assert flight.waist_thickness == 0.15
    assert flight.number_of_risers == 10

    vertical_circulation_manifest.elements.append(flight)
    resolver = SpatialResolver(vertical_circulation_manifest)
    resolved = resolver.resolve()

    assert len(resolved.stair_flights) == 1
    res_flight = resolved.stair_flights[0]
    assert res_flight.tag == "ST-FLIGHT-01"
    assert res_flight.width == 1.20
    assert res_flight.n_risers == 10
    assert len(res_flight.steps) == 10
    assert res_flight.rise_height == 3.50
    assert math.isclose(res_flight.slope_length, math.hypot(res_flight.run_length, 3.50), rel_tol=1e-4)

    # QTO verification
    eqto = calculate_element_qto(res_flight, manifest=vertical_circulation_manifest)
    assert eqto.concrete_volume > 0.0
    assert eqto.formwork_area > 0.0
    assert eqto.stair_assembly is not None
    assert eqto.stair_assembly.total_steps == 10


def test_ramp_schema_and_resolver(vertical_circulation_manifest):
    ramp = IfcRamp(
        **{
            "class": "IfcRamp",
            "tag": "RAMP-01",
            "material": "MAT_CONC",
            "ramp_width": 1.50,
            "slope_percentage": 8.33,  # 1:12 accessible ramp slope
            "slab_thickness": 0.18,
            "landing_length": 1.50,
            "placement": RampPlacement(
                from_grid=("1", "A"),
                to_grid=("2", "A"),
                storey="FL1",
                offset_z=0.00,
                to_offset_z=0.50,
            ),
        }
    )
    assert ramp.ramp_width == 1.50
    assert ramp.width == 1.50
    assert ramp.slope_percentage == 8.33
    assert ramp.slab_thickness == 0.18

    vertical_circulation_manifest.elements.append(ramp)
    resolver = SpatialResolver(vertical_circulation_manifest)
    resolved = resolver.resolve()

    assert len(resolved.ramps) == 1
    res_ramp = resolved.ramps[0]
    assert res_ramp.tag == "RAMP-01"
    assert res_ramp.width == 1.50
    assert res_ramp.run_length == 6.00
    assert res_ramp.rise_height == 0.50
    assert math.isclose(res_ramp.slope_length, math.hypot(6.00, 0.50), rel_tol=1e-4)
    assert math.isclose(res_ramp.slope_percentage, (0.50 / 6.00) * 100.0, rel_tol=1e-2)

    # QTO verification
    eqto = calculate_element_qto(res_ramp, manifest=vertical_circulation_manifest)
    expected_vol = 1.50 * res_ramp.slope_length * 0.18
    assert math.isclose(eqto.concrete_volume, expected_vol, rel_tol=1e-4)
    assert eqto.formwork_area > 0.0


def test_railing_schema_and_resolver(vertical_circulation_manifest):
    railing = IfcRailing(
        **{
            "class": "IfcRailing",
            "tag": "RAILING-01",
            "material": "STEEL_SS400",
            "predefined_type": "GUARDRAIL",
            "height": 1.10,
            "post_spacing": 1.50,
            "handrail_profile": CircularProfile(diameter=0.05),
            "placement": RailingPlacement(
                storey="FL1",
                from_grid=("1", "B"),
                to_grid=("2", "B"),
                from_offset=(0.0, 0.0, 0.0),
                to_offset=(0.0, 0.0, 0.0),
                path=[
                    RailingPoint(grid=("1", "B"), offset_x=0.0, offset_y=0.0, offset_z=0.0),
                    RailingPoint(grid=("2", "B"), offset_x=0.0, offset_y=0.0, offset_z=0.0),
                    RailingPoint(grid=("2", "C"), offset_x=0.0, offset_y=0.0, offset_z=0.0),
                ],
            ),
        }
    )
    assert railing.predefined_type == "GUARDRAIL"
    assert railing.height == 1.10
    assert railing.post_spacing == 1.50

    vertical_circulation_manifest.elements.append(railing)
    resolver = SpatialResolver(vertical_circulation_manifest)
    resolved = resolver.resolve()

    assert len(resolved.railings) == 1
    res_rail = resolved.railings[0]
    assert res_rail.tag == "RAILING-01"
    assert res_rail.height == 1.10
    assert res_rail.total_length == 12.00  # 6m + 6m L-shaped path
    assert res_rail.post_count > 0
    assert len(res_rail.posts) == res_rail.post_count
    assert len(res_rail.rails) == 2

    # QTO verification
    eqto = calculate_element_qto(res_rail, manifest=vertical_circulation_manifest)
    assert eqto.length == 12.00
    assert eqto.structural_steel_weight > 0.0


def test_vertical_circulation_compiler_and_viewer(vertical_circulation_manifest, tmp_path):
    flight = IfcStairFlight(
        tag="ST1-FLIGHT",
        material="MAT_CONC",
        flight_width=1.20,
        waist_thickness=0.15,
        number_of_risers=10,
        riser_height=0.18,
        tread_length=0.25,
        placement=StairPlacement(grid_anchor=("1", "A"), from_storey="FL1", to_storey="FL2"),
    )
    ramp = IfcRamp(
        tag="RAMP1",
        material="MAT_CONC",
        ramp_width=1.50,
        slope_percentage=8.33,
        slab_thickness=0.15,
        placement=RampPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="FL1", to_offset_z=0.50),
    )
    railing = IfcRailing(
        tag="RAIL1",
        material="STEEL_SS400",
        predefined_type="HANDRAIL",
        height=0.90,
        placement=RailingPlacement(storey="FL1", from_grid=("1", "A"), to_grid=("1", "B")),
    )
    vertical_circulation_manifest.elements.extend([flight, ramp, railing])

    resolver = SpatialResolver(vertical_circulation_manifest)
    resolved = resolver.resolve()

    # Verify project QTO aggregation
    pqto = calculate_qto(resolved)
    assert pqto.total_concrete_volume > 0.0
    assert pqto.total_railing_length >= 6.00

    # Test IFC Step Export
    output_ifc = tmp_path / "model_vert_circ.ifc"
    compiled_path = compile_to_ifc(resolved, output_path=output_ifc, force_fallback=True)
    assert compiled_path.exists()
    content = compiled_path.read_text(encoding="utf-8")
    assert "IFCSTAIRFLIGHT" in content
    assert "IFCRAMP" in content
    assert "IFCRAILING" in content

    # Test 3D Viewer HTML generation
    html_str = generate_viewer_html(resolved)
    assert "IfcStairFlight" in html_str or "IfcStairStep" in html_str
    assert "IfcRamp" in html_str
    assert "IfcRailing" in html_str
