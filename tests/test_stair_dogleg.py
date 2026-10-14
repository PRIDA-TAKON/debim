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
from debim.resolver import SpatialResolver, resolve_manifest
from debim.qto import calculate_element_qto, calculate_qto
from debim.compiler import compile_to_ifc
from debim.viewer import generate_viewer_html


@pytest.fixture
def dogleg_stair_manifest():
    return ProjectManifest(
        project=ProjectInfo(id="DOGLEG-PROJ", name="Dog-Leg Stair Test Project", units=Units()),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="FL1", name="Ground Floor", elevation=0.00, height=3.50),
                Storey(id="FL2", name="Second Floor", elevation=3.50, height=3.50),
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


def test_dogleg_stair_schema_sync():
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-DOGLEG-01",
            "stair_type": "DOG_LEG",
            "width": 1.20,
            "waist_thickness": 0.15,
            "landing_depth": 1.20,
            "riser_height": 0.175,
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
    assert stair.stair_type == "DOG_LEG"
    assert stair.width == 1.20
    assert stair.waist_thickness == 0.15
    assert stair.landing_depth == 1.20
    assert stair.riser_height == 0.175
    assert stair.tread_depth == 0.28
    assert stair.landing is not None
    assert stair.landing.depth == 1.20
    assert stair.landing.thickness == 0.15
    assert stair.steps is not None
    assert stair.steps.riser == 0.175
    assert stair.steps.tread == 0.28


def test_dogleg_stair_spatial_resolution(dogleg_stair_manifest):
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-DOGLEG-01",
            "stair_type": "DOG_LEG",
            "width": 1.20,
            "waist_thickness": 0.15,
            "landing_depth": 1.20,
            "riser_height": 0.175,
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
    dogleg_stair_manifest.elements.append(stair)

    resolved = resolve_manifest(dogleg_stair_manifest)

    assert len(resolved.stairs) == 1
    res_stair = resolved.stairs[0]

    assert res_stair.tag == "ST-DOGLEG-01"
    assert len(res_stair.flights) == 2

    # Total storey delta height = 3.50m
    # Total risers = round(3.50 / 0.175) = 20 risers
    # Flight 1: 10 risers, Flight 2: 10 risers
    total_steps = len(res_stair.steps)
    assert total_steps == 20

    f1, f2 = res_stair.flights
    assert f1.n_risers == 10
    assert f2.n_risers == 10
    assert math.isclose(f1.rise_height, 1.75, rel_tol=1e-3)
    assert math.isclose(f2.rise_height, 1.75, rel_tol=1e-3)

    # Flight 1 connects (0, 0, 0) to landing at (0, run_1, 1.75)
    assert f1.start_point == (0.0, 0.0, 0.0)
    assert math.isclose(f1.end_point[2], 1.75, rel_tol=1e-3)

    # Flight 2 connects landing at (1.20, run_1, 1.75) to top at (1.20, run_1 - run_2, 3.50)
    assert math.isclose(f2.start_point[2], 1.75, rel_tol=1e-3)
    assert math.isclose(f2.end_point[2], 3.50, rel_tol=1e-3)

    # Landing polygon
    assert res_stair.landing_polygon is not None
    assert len(res_stair.landing_polygon) == 4
    # Landing elevation is at mid-height 1.75m
    assert all(math.isclose(pt[2], 1.75, rel_tol=1e-3) for pt in res_stair.landing_polygon)


def test_dogleg_stair_qto(dogleg_stair_manifest):
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-DOGLEG-01",
            "stair_type": "DOG_LEG",
            "width": 1.20,
            "waist_thickness": 0.15,
            "landing_depth": 1.20,
            "riser_height": 0.175,
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
    dogleg_stair_manifest.elements.append(stair)
    resolved = resolve_manifest(dogleg_stair_manifest)
    res_stair = resolved.stairs[0]

    eqto = calculate_element_qto(res_stair, manifest=dogleg_stair_manifest)

    # Concrete volume includes waist slab + step triangles + landing slab
    assert eqto.concrete_volume > 1.5 and eqto.concrete_volume < 3.5
    assert eqto.formwork_area > 0.0

    pqto = calculate_qto(resolved)
    assert pqto.total_concrete_volume == eqto.concrete_volume


def test_dogleg_stair_compiler_and_viewer(dogleg_stair_manifest, tmp_path):
    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-DOGLEG-01",
            "stair_type": "DOG_LEG",
            "width": 1.20,
            "waist_thickness": 0.15,
            "landing_depth": 1.20,
            "riser_height": 0.175,
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
    dogleg_stair_manifest.elements.append(stair)
    resolved = resolve_manifest(dogleg_stair_manifest)

    # Compile to IFC
    output_ifc = tmp_path / "model_dogleg_stair.ifc"
    compiled_path = compile_to_ifc(resolved, output_path=output_ifc, force_fallback=True)
    assert compiled_path.exists()
    content = compiled_path.read_text(encoding="utf-8")
    assert "IFCSTAIR" in content

    # Render to 3D WebGL HTML viewer
    html_str = generate_viewer_html(resolved)
    assert "ST-DOGLEG-01" in html_str
    assert "IfcStairStep" in html_str
