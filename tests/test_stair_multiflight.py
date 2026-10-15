import math
import pytest

from debim.schema import (
    IfcStair,
    StairPlacement,
    SpatialStructure,
    Storey,
    Grids,
    ProjectInfo,
    Units,
    Material,
    ProjectManifest,
)
from debim.resolver import resolve_manifest
from debim.qto import calculate_element_qto, calculate_qto
from debim.compiler import compile_to_ifc
from debim.viewer import generate_viewer_html


@pytest.fixture
def multiflight_stair_manifest():
    return ProjectManifest(
        project=ProjectInfo(id="MULTIFLIGHT-PROJ", name="Multi-Flight Stair Test Project", units=Units()),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="FL1", name="Ground Floor", elevation=0.00, height=3.40),
                Storey(id="FL2", name="Second Floor", elevation=3.40, height=3.40),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 6.0},
            axes_y={"A": 0.0, "B": 6.0},
        ),
        materials=[
            Material(id="MAT_CONC", name="Reinforced Concrete", category="concrete", unit_cost_ref="cost_conc"),
        ],
        elements=[],
    )


def test_multiflight_stair_schema_sync():
    # Test top-level landing_elevation syncs to landing.elevation
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-MULTI-01",
            "stair_type": "DOG_LEG",
            "width": 1.20,
            "waist_thickness": 0.15,
            "landing_depth": 1.20,
            "landing_elevation": 2.20,
            "flight_steps": [11, 6],
            "material": "MAT_CONC",
            "placement": StairPlacement(
                grid_anchor=("1", "A"),
                from_storey="FL1",
                to_storey="FL2",
                orientation="+Y",
            ),
        }
    )
    assert stair.landing_elevation == 2.20
    assert stair.landing is not None
    assert stair.landing.elevation == 2.20
    assert stair.flight_steps == [11, 6]

    # Test nested landing.elevation syncs to top-level landing_elevation
    stair2 = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-MULTI-02",
            "stair_type": "DOG_LEG",
            "material": "MAT_CONC",
            "placement": StairPlacement(
                grid_anchor=("1", "A"),
                from_storey="FL1",
                to_storey="FL2",
            ),
            "landing": {"elevation": 2.10, "depth": 1.10},
        }
    )
    assert stair2.landing_elevation == 2.10
    assert stair2.landing.elevation == 2.10


def test_multiflight_stair_spatial_resolution_explicit_landing_elevation(multiflight_stair_manifest):
    # Total storey height = 3.40m
    # Flight 1: 11 steps rise to 2.20m landing_elevation -> riser 1 = 0.20m
    # Flight 2: 6 steps rise remaining 1.20m -> riser 2 = 0.20m
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-MULTI-01",
            "stair_type": "DOG_LEG",
            "width": 1.20,
            "waist_thickness": 0.15,
            "landing_depth": 1.20,
            "landing_elevation": 2.20,
            "flight_steps": [11, 6],
            "tread_depth": 0.28,
            "material": "MAT_CONC",
            "placement": StairPlacement(
                grid_anchor=("1", "A"),
                from_storey="FL1",
                to_storey="FL2",
                orientation="+Y",
            ),
        }
    )
    multiflight_stair_manifest.elements.append(stair)

    resolved = resolve_manifest(multiflight_stair_manifest)
    assert len(resolved.stairs) == 1
    res_stair = resolved.stairs[0]

    assert len(res_stair.flights) == 2
    f1, f2 = res_stair.flights

    assert f1.n_risers == 11
    assert f2.n_risers == 6
    assert len(res_stair.steps) == 17

    assert math.isclose(f1.rise_height, 2.20, rel_tol=1e-3)
    assert math.isclose(f1.riser, 0.20, rel_tol=1e-3)

    assert math.isclose(f2.rise_height, 1.20, rel_tol=1e-3)
    assert math.isclose(f2.riser, 0.20, rel_tol=1e-3)

    # Flight 1 start/end points
    assert f1.start_point == (0.0, 0.0, 0.0)
    assert math.isclose(f1.end_point[2], 2.20, rel_tol=1e-3)

    # Flight 2 start/end points
    assert math.isclose(f2.start_point[2], 2.20, rel_tol=1e-3)
    assert math.isclose(f2.end_point[2], 3.40, rel_tol=1e-3)

    # Landing elevation
    assert all(math.isclose(pt[2], 2.20, rel_tol=1e-3) for pt in res_stair.landing_polygon)


def test_multiflight_stair_spatial_resolution_ratio_landing_elevation(multiflight_stair_manifest):
    # Total storey height = 3.40m
    # Flight 1: 10 steps, Flight 2: 7 steps (no explicit landing_elevation)
    # Landing elevation ratio = 3.40 * (10 / 17) = 2.00m
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-MULTI-RATIO",
            "stair_type": "DOG_LEG",
            "width": 1.20,
            "flight_steps": [10, 7],
            "material": "MAT_CONC",
            "placement": StairPlacement(
                grid_anchor=("1", "A"),
                from_storey="FL1",
                to_storey="FL2",
                orientation="+Y",
            ),
        }
    )
    multiflight_stair_manifest.elements.append(stair)

    resolved = resolve_manifest(multiflight_stair_manifest)
    res_stair = resolved.stairs[0]

    f1, f2 = res_stair.flights
    assert f1.n_risers == 10
    assert f2.n_risers == 7

    assert math.isclose(f1.rise_height, 2.00, rel_tol=1e-3)
    assert math.isclose(f2.rise_height, 1.40, rel_tol=1e-3)
    assert math.isclose(f1.riser, 0.20, rel_tol=1e-3)
    assert math.isclose(f2.riser, 0.20, rel_tol=1e-3)


def test_multiflight_stair_qto(multiflight_stair_manifest):
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-MULTI-QTO",
            "stair_type": "DOG_LEG",
            "width": 1.20,
            "waist_thickness": 0.15,
            "landing_depth": 1.20,
            "landing_elevation": 2.20,
            "flight_steps": [11, 6],
            "material": "MAT_CONC",
            "placement": StairPlacement(
                grid_anchor=("1", "A"),
                from_storey="FL1",
                to_storey="FL2",
                orientation="+Y",
            ),
        }
    )
    multiflight_stair_manifest.elements.append(stair)
    resolved = resolve_manifest(multiflight_stair_manifest)
    res_stair = resolved.stairs[0]

    eqto = calculate_element_qto(res_stair, manifest=multiflight_stair_manifest)

    # Concrete volume and formwork area are non-zero and reasonable
    assert eqto.concrete_volume > 1.5 and eqto.concrete_volume < 4.0
    assert eqto.formwork_area > 0.0

    pqto = calculate_qto(resolved)
    assert pqto.total_concrete_volume == eqto.concrete_volume


def test_multiflight_stair_compiler_and_viewer(multiflight_stair_manifest, tmp_path):
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-MULTI-COMPILE",
            "stair_type": "DOG_LEG",
            "width": 1.20,
            "waist_thickness": 0.15,
            "landing_depth": 1.20,
            "landing_elevation": 2.20,
            "flight_steps": [11, 6],
            "material": "MAT_CONC",
            "placement": StairPlacement(
                grid_anchor=("1", "A"),
                from_storey="FL1",
                to_storey="FL2",
                orientation="+Y",
            ),
        }
    )
    multiflight_stair_manifest.elements.append(stair)
    resolved = resolve_manifest(multiflight_stair_manifest)

    # Compile to IFC
    output_ifc = tmp_path / "model_multiflight_stair.ifc"
    compiled_path = compile_to_ifc(resolved, output_path=output_ifc, force_fallback=True)
    assert compiled_path.exists()
    content = compiled_path.read_text(encoding="utf-8")
    assert "IFCSTAIR" in content

    # Render to WebGL HTML viewer
    html_str = generate_viewer_html(resolved)
    assert "ST-MULTI-COMPILE" in html_str
    assert "IfcStairStep" in html_str
