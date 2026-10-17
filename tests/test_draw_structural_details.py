"""
Unit tests for structural RC Beam, Column, and Footing Detail Schedules (แบบขยายโครงสร้าง คสล.),
2D cross-section vector graphics, rebar callouts, and S-201 drawing sheet rendering.
"""

from pathlib import Path
import pytest

from debim.draw import (
    BeamDetailItem,
    ColumnDetailItem,
    FootingDetailItem,
    SheetConfig,
    SheetRenderer,
    extract_structural_details,
    render_beam_section_svg,
    render_column_section_svg,
    render_footing_detail_svg,
    render_structural_detail_card_svg,
    render_structural_details_schedule_svg,
)
from debim.resolver import SpatialResolver
from debim.schema import ProjectManifest, load_manifest


@pytest.fixture
def sample_structural_manifest() -> ProjectManifest:
    """Load sample townhouse or contemporary house manifest with RC structural members."""
    manifest_path = Path(__file__).parent / "fixtures" / "contemporary_thai_house" / "project.yaml"
    if manifest_path.exists():
        return load_manifest(manifest_path)

    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {"id": "P1", "name": "Structural Detail Test House"},
        "spatial_structure": {
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0},
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0, "3": 8.0},
            "axes_y": {"A": 0.0, "B": 4.0, "C": 8.0},
        },
        "materials": [
            {"id": "CONC", "name": "Structural Concrete 240 ksc", "category": "CONCRETE", "unit_cost_ref": "C1"},
        ],
        "elements": [
            {
                "class": "IfcFooting",
                "tag": "F1-01",
                "material": "CONC",
                "profile": {"shape": "BOX", "width": 1.00, "depth": 1.00, "thickness": 0.30},
                "placement": {"grid": ["1", "A"], "storey": "L1"},
                "reinforcement": {"mesh_x": "DB12@0.15 m", "mesh_y": "DB12@0.15 m"},
            },
            {
                "class": "IfcFooting",
                "tag": "F1-02",
                "material": "CONC",
                "profile": {"shape": "BOX", "width": 1.00, "depth": 1.00, "thickness": 0.30},
                "placement": {"grid": ["2", "A"], "storey": "L1"},
                "reinforcement": {"mesh_x": "DB12@0.15 m", "mesh_y": "DB12@0.15 m"},
            },
            {
                "class": "IfcFooting",
                "tag": "F2-01",
                "material": "CONC",
                "profile": {"shape": "BOX", "width": 1.20, "depth": 1.20, "thickness": 0.35},
                "placement": {"grid": ["3", "A"], "storey": "L1"},
                "reinforcement": {"mesh_x": "DB12@0.15 m", "mesh_y": "DB12@0.15 m"},
                "piles": {"count": 2, "length": 6.0, "spacing": 0.60},
            },
            {
                "class": "IfcColumn",
                "tag": "C1-01",
                "material": "CONC",
                "profile": {"shape": "BOX", "width": 0.20, "depth": 0.20},
                "placement": {"grid": ["1", "A"], "base_storey": "L1", "height": 3.0},
                "reinforcement": {"main": "4-DB12", "stirrups": "RB6@0.15 m"},
            },
            {
                "class": "IfcColumn",
                "tag": "C1-02",
                "material": "CONC",
                "profile": {"shape": "BOX", "width": 0.20, "depth": 0.20},
                "placement": {"grid": ["2", "A"], "base_storey": "L1", "height": 3.0},
                "reinforcement": {"main": "4-DB12", "stirrups": "RB6@0.15 m"},
            },
            {
                "class": "IfcColumn",
                "tag": "C2-CIRCULAR",
                "material": "CONC",
                "profile": {"shape": "CIRCULAR", "diameter": 0.30},
                "placement": {"grid": ["3", "A"], "base_storey": "L1", "height": 3.0},
                "reinforcement": {"main": "6-DB16", "stirrups": "RB9@0.15 m"},
            },
            {
                "class": "IfcBeam",
                "tag": "B1-01",
                "material": "CONC",
                "profile": {"shape": "BOX", "width": 0.20, "depth": 0.40},
                "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "L1"},
                "reinforcement": {"main_top": "2-DB12", "main_bottom": "2-DB12", "stirrups": "RB9@0.15 m"},
            },
            {
                "class": "IfcBeam",
                "tag": "B1-02",
                "material": "CONC",
                "profile": {"shape": "BOX", "width": 0.20, "depth": 0.40},
                "placement": {"from_grid": ["2", "A"], "to_grid": ["3", "A"], "storey": "L1"},
                "reinforcement": {"main_top": "2-DB12", "main_bottom": "2-DB12", "stirrups": "RB9@0.15 m"},
            },
            {
                "class": "IfcBeam",
                "tag": "DB1-01",
                "material": "CONC",
                "profile": {"shape": "BOX", "width": 0.25, "depth": 0.50},
                "placement": {"from_grid": ["1", "B"], "to_grid": ["3", "B"], "storey": "L1"},
                "reinforcement": {"main_top": "3-DB16", "main_bottom": "3-DB16", "stirrups": "RB9@0.15 m"},
            },
        ],
    }
    return ProjectManifest.model_validate(manifest_data)


def test_extract_structural_details(sample_structural_manifest: ProjectManifest):
    """Test beam, column, and footing schedule extraction and quantity aggregation."""
    resolved = SpatialResolver(sample_structural_manifest).resolve()
    beams, columns, footings = extract_structural_details(resolved)

    assert len(beams) >= 2
    assert len(columns) >= 2
    assert len(footings) >= 2

    tot_beams = sum(b.quantity for b in beams)
    tot_cols = sum(c.quantity for c in columns)
    tot_footings = sum(f.quantity for f in footings)

    assert tot_beams >= 3
    assert tot_cols >= 3
    assert tot_footings >= 3

    # Check beam properties
    for i, b in enumerate(beams, 1):
        assert b.type_tag == f"B{i}"
        assert b.category == "BEAM"
        assert b.width > 0
        assert b.depth > 0
        assert b.main_top is not None
        assert b.main_bottom is not None
        assert b.stirrups is not None

    # Check column properties
    for j, c in enumerate(columns, 1):
        assert c.type_tag == f"C{j}"
        assert c.category == "COLUMN"
        assert c.section_shape in ("RECTANGULAR", "CIRCULAR")
        assert c.main_rebar is not None
        assert c.stirrups is not None

    # Check footing properties
    for k, f in enumerate(footings, 1):
        assert f.type_tag == f"F{k}"
        assert f.category == "FOOTING"
        assert f.footing_type in ("SPREAD", "PILE_CAP")
        assert f.rebar_mat_x is not None
        assert f.lean_thickness == 0.05
        assert f.sand_thickness == 0.10


def test_render_beam_section_svg():
    """Test 2D vector cross-section rendering for RC beams."""
    item = BeamDetailItem(
        type_tag="B1",
        width=0.20,
        depth=0.40,
        main_top="2-DB12",
        main_bottom="2-DB12",
        stirrups="RB9@0.15 m",
        covering=0.03,
        quantity=2,
    )

    svg_out = render_beam_section_svg(item)

    assert 'id="beam-section-B1"' in svg_out
    assert 'class="concrete-boundary"' in svg_out
    assert 'class="stirrup-tie"' in svg_out
    assert 'class="rebar-main"' in svg_out
    assert "2-DB12 (Top)" in svg_out
    assert "2-DB12 (Bot)" in svg_out
    assert "RB9@0.15 m" in svg_out
    assert "0.20 m." in svg_out
    assert "0.40 m." in svg_out


def test_render_column_section_svg():
    """Test 2D vector cross-section rendering for rectangular and circular columns."""
    rect_col = ColumnDetailItem(
        type_tag="C1",
        section_shape="RECTANGULAR",
        width=0.20,
        depth=0.20,
        main_rebar="4-DB12",
        stirrups="RB6@0.15 m",
    )
    rect_svg = render_column_section_svg(rect_col)

    assert 'id="column-section-C1"' in rect_svg
    assert 'class="concrete-boundary"' in rect_svg
    assert 'class="stirrup-tie"' in rect_svg
    assert "4-DB12" in rect_svg
    assert "0.20 x 0.20 m." in rect_svg

    circ_col = ColumnDetailItem(
        type_tag="C2",
        section_shape="CIRCULAR",
        width=0.30,
        depth=0.30,
        main_rebar="6-DB16",
        stirrups="RB9@0.15 m",
    )
    circ_svg = render_column_section_svg(circ_col)

    assert 'id="column-section-C2"' in circ_svg
    assert 'circle cx=' in circ_svg
    assert "6-DB16" in circ_svg
    assert "Ø 0.30 m." in circ_svg


def test_render_footing_detail_svg():
    """Test 2D vector detail rendering for spread footings and pile caps."""
    spread_f = FootingDetailItem(
        type_tag="F1",
        footing_type="SPREAD",
        width=1.00,
        depth=1.00,
        thickness=0.30,
        rebar_mat_x="DB12@0.15 m",
        rebar_mat_y="DB12@0.15 m",
    )
    f_svg = render_footing_detail_svg(spread_f)

    assert 'id="footing-detail-F1"' in f_svg
    assert "ระดับดินเดิม" in f_svg
    assert "ทรายหยาบอัดแน่น (10 cm)" in f_svg
    assert "คอนกรีตหยาบ 1:3:5 (5 cm)" in f_svg
    assert "DB12@0.15 m (2 ทาง)" in f_svg
    assert "1.00 x 1.00 m." in f_svg

    pile_f = FootingDetailItem(
        type_tag="F2",
        footing_type="PILE_CAP",
        width=1.20,
        depth=1.20,
        thickness=0.35,
        rebar_mat_x="DB12@0.15 m",
        rebar_mat_y="DB12@0.15 m",
        piles_count=2,
        pile_spec="Piles: 2 Pcs (6.0m)",
    )
    pf_svg = render_footing_detail_svg(pile_f)

    assert 'id="footing-detail-F2"' in pf_svg
    assert "polygon points=" in pf_svg  # pile tips


def test_render_structural_detail_card_svg():
    """Test structural detail card rendering with specification table."""
    item = BeamDetailItem(
        type_tag="B1",
        width=0.20,
        depth=0.40,
        main_top="2-DB12",
        main_bottom="2-DB12",
        stirrups="RB9@0.15 m",
        quantity=3,
        instances=["B1-01", "B1-02", "B1-03"],
    )

    card_svg = render_structural_detail_card_svg(item)

    assert 'id="card-struct-B1"' in card_svg
    assert "แบบขยายหน้าตัดคาน (BEAM DETAIL) (B1)" in card_svg
    assert "จำนวน 3 ชุด (QTY: 3)" in card_svg
    assert "0.20 x 0.40 m." in card_svg
    assert "บน: 2-DB12 | ล่าง: 2-DB12 | ปลอก: RB9@0.15 m" in card_svg
    assert "B1-01, B1-02, B1-03" in card_svg


def test_render_structural_details_schedule_svg_sheet(sample_structural_manifest: ProjectManifest):
    """Test complete S-201 structural drawing sheet rendering."""
    resolved = SpatialResolver(sample_structural_manifest).resolve()

    cfg = SheetConfig(
        id="S-201",
        title="Structural RC Beam Column Footing Details",
        view_type="STRUCTURAL_DETAILS",
        paper_size="A3",
    )

    svg_content = render_structural_details_schedule_svg(resolved, cfg)

    assert '<?xml version="1.0" encoding="UTF-8"?>' in svg_content
    assert '<svg' in svg_content
    assert 'id="structural-schedule-viewport"' in svg_content
    assert "แบบขยายโครงสร้าง คสล. คาน เสา และฐานราก" in svg_content
    assert 'id="title-block"' in svg_content
    assert "</svg>" in svg_content


def test_sheet_renderer_structural_integration(sample_structural_manifest: ProjectManifest):
    """Test integration into SheetRenderer and view_type normalization for S-201."""
    resolved = SpatialResolver(sample_structural_manifest).resolve()

    cfg = SheetConfig(
        id="S-201",
        title="Structural Details Sheet",
        view_type="STRUCTURAL_SCHEDULE",
        paper_size="A3",
    )

    assert cfg.view_type == "STRUCTURAL_DETAILS"

    renderer = SheetRenderer(resolved, cfg)
    svg_out = renderer.render_svg()

    assert 'id="structural-schedule-viewport"' in svg_out
    assert "STRUCTURAL RC BEAM, COLUMN &amp; FOOTING DETAILS" in svg_out
