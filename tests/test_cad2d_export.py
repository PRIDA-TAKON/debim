"""
Unit tests for 2D Multi-Discipline CAD Exporter & Parametric Stairs Generator.
"""

from pathlib import Path
import ezdxf
import pytest

from debim.cad2d import PlanCutGenerator, export_cad_dxf, export_cad_svg
from debim.cli import build_parser, cmd_export, main
from debim.geometry.stairs import (
    calculate_stair_parameters,
    generate_parametric_stair,
    generate_stair_railings,
)
from debim.schema import (
    Grids,
    IfcPipeSegment,
    IfcSpace,
    IfcWall,
    Material,
    PipePlacement,
    ProjectInfo,
    ProjectManifest,
    SpacePlacement,
    SpatialStructure,
    Storey,
    Units,
    WallPlacement,
)


@pytest.fixture
def sample_manifest() -> ProjectManifest:
    """Create a minimal sample ProjectManifest with walls, space, pipe, and storey."""
    w1 = IfcWall(
        tag="W1",
        material="Masonry",
        thickness=0.15,
        height=3.20,
        placement=WallPlacement(
            from_grid=("A", "1"),
            to_grid=("B", "1"),
            storey="FL1",
        ),
    )
    w2 = IfcWall(
        tag="W2",
        material="Masonry",
        thickness=0.15,
        height=3.20,
        placement=WallPlacement(
            from_grid=("A", "1"),
            to_grid=("A", "2"),
            storey="FL1",
        ),
    )
    sp = IfcSpace(
        tag="SP-01",
        name="Living Room",
        placement=SpacePlacement(
            storey="FL1",
            boundary=[("A", "1"), ("B", "1"), ("B", "2"), ("A", "2")],
        ),
    )
    pipe = IfcPipeSegment(
        tag="PIPE-01",
        system_type="SOIL",
        material="PVC",
        nominal_diameter=0.100,
        placement=PipePlacement(
            from_grid=("A", "1"),
            to_grid=("B", "1"),
            storey="FL1",
            from_offset=(0.5, 0.5, 0.5),
            to_offset=(5.5, 0.5, 0.4),
        ),
    )

    return ProjectManifest(
        project=ProjectInfo(id="TEST-PROJ", name="Test CAD Project", units=Units()),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="FL1", name="Floor 1", elevation=0.00, height=3.20),
                Storey(id="FL2", name="Floor 2", elevation=3.20, height=3.20),
            ]
        ),
        grids=Grids(
            axes_x={"A": 0.0, "B": 6.0},
            axes_y={"1": 0.0, "2": 8.0},
        ),
        materials=[
            Material(id="Masonry", name="Masonry", category="masonry", unit_cost_ref="cost_masonry"),
            Material(id="PVC", name="PVC", category="plastic", unit_cost_ref="cost_pvc"),
        ],
        elements=[w1, w2, sp, pipe],
    )


def test_calculate_stair_parameters():
    """Test parametric stair geometry parameter calculations."""
    params = calculate_stair_parameters(total_height=3.20, max_riser=0.20, min_tread=0.25)

    assert params["num_risers"] == 16
    assert params["riser_height"] <= 0.20
    assert params["tread_depth"] >= 0.25
    assert params["total_height"] == 3.20

    # Dog-leg stair split into 2 flights
    dogleg_params = calculate_stair_parameters(total_height=3.20, stair_type="DOG_LEG")
    assert dogleg_params["stair_type"] == "DOG_LEG"
    assert len(dogleg_params["flight_steps"]) == 2
    assert dogleg_params["landing_elevation"] is not None


def test_generate_parametric_stair_and_railings():
    """Test automated IfcStair and IfcRailing generation."""
    stair, railings = generate_parametric_stair(
        tag="ST-01",
        total_height=3.20,
        grid_anchor=("A", "1"),
        from_storey="FL1",
        to_storey="FL2",
        width=1.20,
        railing_height=0.90,
    )

    assert stair.tag == "ST-01"
    assert stair.riser_height <= 0.20
    assert stair.tread_depth >= 0.25
    assert stair.width == 1.20
    assert len(railings) == 2

    for r in railings:
        assert r.height == 0.90
        assert r.layer == "circulation/railings"


def test_plan_cut_generator(sample_manifest):
    """Test PlanCutGenerator horizontal slicing at 1.20m."""
    cut_gen = PlanCutGenerator(sample_manifest, cut_offset_z=1.20)
    res = cut_gen.slice_storey_plan("FL1")

    assert res.storey_id == "FL1"
    assert res.cut_offset_z == 1.20
    assert res.cut_elevation == 1.20
    assert len(res.cut_elements) >= 2
    assert len(res.grid_lines) == 4


def test_export_cad_dxf(sample_manifest, tmp_path: Path):
    """Test 2D CAD DXF export with layers, wall hatches, room area labels, and MEP pipe tags."""
    output_dxf = tmp_path / "test_drawing.dxf"

    res_path = export_cad_dxf(
        manifest_or_resolved=sample_manifest,
        output_path=output_dxf,
        storey_id="FL1",
        cut_offset_z=1.20,
        units="mm",
    )

    assert res_path.exists()
    assert res_path.stat().st_size > 0

    # Read exported DXF with ezdxf and verify layers and entities
    doc = ezdxf.readfile(res_path)
    msp = doc.modelspace()
    layer_names = {layer.dxf.name for layer in doc.layers}

    expected_layers = {"A-WALL", "A-WALL-HATCH", "A-ROOM-LABEL", "DIM-ANNO", "GRID-ANNO", "M-PIPE", "M-ANNO"}
    assert expected_layers.issubset(layer_names)

    # Check for text entities (Room label area and pipe annotation tags)
    texts = [e.dxf.text for e in msp if e.dxftype() == "TEXT"]
    assert any("LIVING ROOM" in t for t in texts)
    assert any("m²" in t for t in texts)
    assert any("PVC" in t or "Ø100" in t for t in texts)


def test_export_cad_svg(sample_manifest, tmp_path: Path):
    """Test 2D CAD SVG export generation."""
    output_svg = tmp_path / "test_drawing.svg"

    res_path = export_cad_svg(
        manifest_or_resolved=sample_manifest,
        output_path=output_svg,
        storey_id="FL1",
    )

    assert res_path.exists()
    content = res_path.read_text(encoding="utf-8")

    assert "<svg" in content
    assert 'class="wall"' in content
    assert 'class="room-label"' in content
    assert 'class="pipe"' in content
    assert "Living Room" in content or "LIVING ROOM" in content


def test_cli_export_command(tmp_path: Path):
    """Test CLI `debim export --format dxf` subcommand via ArgumentParser."""
    output_dxf = tmp_path / "cli_export.dxf"
    house_manifest = Path("house.debim")
    assert house_manifest.exists()

    parser = build_parser()
    args = parser.parse_args([
        "export",
        "-m", str(house_manifest),
        "-f", "dxf",
        "-o", str(output_dxf),
    ])

    cmd_export(args)
    assert output_dxf.exists()
    assert output_dxf.stat().st_size > 0
