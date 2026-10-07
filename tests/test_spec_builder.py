"""
Unit tests for debim.spec.builder Specification Book Compiler and CLI command.
"""

from pathlib import Path
import tempfile
import pytest
import yaml
from typer.testing import CliRunner

from debim.cli import app
from debim.schema import (
    Grids,
    IfcWall,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    WallPlacement,
)
from debim.spec.builder import (
    build_specification_book,
    get_masterformat_division,
)
from debim.spec.schema import (
    IndustryStandards,
    MaterialSpec,
    SpecificationManifest,
    StructuredClauses,
)


def test_get_masterformat_division():
    assert get_masterformat_division("03 30 00")[0] == "03"
    assert "Concrete" in get_masterformat_division("03 30 00")[1]

    assert get_masterformat_division("Division 04 Masonry")[0] == "04"
    assert "Masonry" in get_masterformat_division("Division 04 Masonry")[1]

    assert get_masterformat_division("09 91 23")[0] == "09"
    assert "Finishes" in get_masterformat_division("09 91 23")[1]

    assert get_masterformat_division(None)[0] == "99"
    assert get_masterformat_division("")[0] == "99"


@pytest.fixture
def sample_building_manifest():
    return ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="BUILDING-101", name="Commercial Complex Alpha"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="FL1", name="Level 1", elevation=0.0, height=3.5),
                Storey(id="FL2", name="Level 2", elevation=3.5, height=3.5),
            ]
        ),
        grids=Grids(
            axes_x={"A": 0.0, "B": 8.0, "C": 16.0},
            axes_y={"1": 0.0, "2": 8.0},
        ),
        materials=[
            Material(id="CONCRETE_C30", name="Cast-in-Place Concrete C30/37", category="CONCRETE", unit_cost_ref="C30"),
            Material(id="BRICK_RED", name="Facing Clay Brickwork", category="MASONRY", unit_cost_ref="BRK"),
            Material(id="PAINT_INTERIOR", name="Low-VOC Acrylic Wall Paint", category="FINISHES", unit_cost_ref="PNT"),
        ],
        elements=[
            IfcWall(
                tag="WAL-101",
                placement=WallPlacement(storey="FL1", from_grid=("A", "1"), to_grid=("B", "1")),
                material="CONCRETE_C30",
                thickness=0.2,
                height=3.0,
            ),
            IfcWall(
                tag="WAL-102",
                placement=WallPlacement(storey="FL1", from_grid=("B", "1"), to_grid=("C", "1")),
                material="BRICK_RED",
                thickness=0.15,
                height=3.0,
            ),
            IfcWall(
                tag="WAL-201",
                placement=WallPlacement(storey="FL2", from_grid=("A", "1"), to_grid=("B", "1")),
                material="PAINT_INTERIOR",
                thickness=0.1,
                height=3.0,
            ),
        ],
    )


@pytest.fixture
def sample_specs_manifest():
    return SpecificationManifest(
        specifications=[
            MaterialSpec(
                id="CONCRETE_C30",
                name="Cast-in-Place Concrete C30/37 Specification",
                masterformat="03 30 00",
                manufacturer="Cemex Concrete",
                warranty_years=10,
                standards=IndustryStandards(astm="ASTM C94", jis="JIS A 5308"),
                clauses=StructuredClauses(
                    general_properties="Compressive strength >= 30 MPa at 28 days.",
                    application_system="Pour continuously and vibrate properly.",
                ),
            ),
            MaterialSpec(
                id="BRICK_RED",
                name="Facing Clay Masonry Units",
                masterformat="04 20 00",
                manufacturer="Siam Brick Co.",
                warranty_years=15,
            ),
            MaterialSpec(
                id="PAINT_INTERIOR",
                name="Interior Latex Acrylic Paint",
                masterformat="09 91 23",
                manufacturer="TOA Paint Ltd.",
                warranty_years=5,
            ),
            # Unreferenced / Bloat Specification
            MaterialSpec(
                id="UNUSED_FOAM_INSULATION",
                name="Extruded Polystyrene Thermal Board",
                masterformat="07 21 00",
                manufacturer="Dow Chemical",
            ),
        ]
    )


def test_build_specification_book_filtering_and_sorting(
    sample_building_manifest, sample_specs_manifest
):
    book = build_specification_book(
        project_manifest=sample_building_manifest,
        spec_manifest=sample_specs_manifest,
        title="COMMERCIAL ALPHA SPECIFICATIONS",
    )

    assert book.title == "COMMERCIAL ALPHA SPECIFICATIONS"
    assert book.project_id == "BUILDING-101"
    assert book.project_name == "Commercial Complex Alpha"

    # Verify zero unused spec bloat (UNUSED_FOAM_INSULATION filtered out)
    included_ids = [s.id for s in book.included_specs]
    assert "UNUSED_FOAM_INSULATION" not in included_ids
    assert sorted(included_ids) == ["BRICK_RED", "CONCRETE_C30", "PAINT_INTERIOR"]

    # Verify MasterFormat divisions grouping and ordering
    div_codes = list(book.divisions.keys())
    assert div_codes == ["03", "04", "09"]

    assert "Concrete" in book.divisions["03"]["title"]
    assert "Masonry" in book.divisions["04"]["title"]
    assert "Finishes" in book.divisions["09"]["title"]


def test_toc_and_section_numbering(sample_building_manifest, sample_specs_manifest):
    book = build_specification_book(
        project_manifest=sample_building_manifest,
        spec_manifest=sample_specs_manifest,
    )

    md = book.markdown_content
    html = book.html_content

    # Cover page and project info
    assert "ARCHITECTURAL MATERIAL SPECIFICATIONS BOOK" in md
    assert "Commercial Complex Alpha" in md
    assert "## Table of Contents" in md

    # Check section numbering in TOC
    assert "1. **Division 03 - Concrete**" in md
    assert "1.1 [CONCRETE_C30 - Cast-in-Place Concrete C30/37 Specification](#section-1-1)" in md
    assert "2. **Division 04 - Masonry**" in md
    assert "2.1 [BRICK_RED - Facing Clay Masonry Units](#section-2-1)" in md
    assert "3. **Division 09 - Finishes**" in md
    assert "3.1 [PAINT_INTERIOR - Interior Latex Acrylic Paint](#section-3-1)" in md

    # Check detailed specification sections
    assert "#### <a id='section-1-1'></a>1.1 CONCRETE_C30" in md
    assert "ASTM C94" in md
    assert "Compressive strength >= 30 MPa" in md

    # HTML verification
    assert "<title>ARCHITECTURAL MATERIAL SPECIFICATIONS BOOK - Commercial Complex Alpha</title>" in html
    assert "class='cover-page'" in html
    assert "class='toc'" in html
    assert "spec-card" in html


def test_save_specification_book(sample_building_manifest, sample_specs_manifest):
    book = build_specification_book(
        project_manifest=sample_building_manifest,
        spec_manifest=sample_specs_manifest,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Markdown save
        md_file = tmp_path / "specifications.md"
        saved_md = book.save(md_file)
        assert saved_md.exists()
        assert "Table of Contents" in saved_md.read_text(encoding="utf-8")

        # HTML save
        html_file = tmp_path / "specifications.html"
        saved_html = book.save(html_file, format="html")
        assert saved_html.exists()
        assert "<!DOCTYPE html>" in saved_html.read_text(encoding="utf-8")


def test_cli_spec_build_command(sample_building_manifest, sample_specs_manifest):
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        proj_file = tmp_path / "project.yaml"
        spec_file = tmp_path / "specs.yaml"
        out_file = tmp_path / "dist" / "specifications.md"

        # Dump project and spec manifests
        proj_file.write_text(
            yaml.dump(sample_building_manifest.model_dump(by_alias=True, mode="json")),
            encoding="utf-8",
        )
        spec_file.write_text(
            yaml.dump(sample_specs_manifest.model_dump(by_alias=True, mode="json")),
            encoding="utf-8",
        )

        res = runner.invoke(
            app,
            [
                "spec",
                "build",
                "-m",
                str(proj_file),
                "-s",
                str(spec_file),
                "-o",
                str(out_file),
                "-t",
                "PROJECT SPEC BOOK",
            ],
        )

        assert res.exit_code == 0
        assert "Compiling Specification Book for" in res.output
        assert "Specification Book Summary" in res.output
        assert "debim Spec Book Build Complete" in res.output

        assert out_file.exists()
        content = out_file.read_text(encoding="utf-8")
        assert "# PROJECT SPEC BOOK" in content
        assert "Division 03" in content
        assert "Division 04" in content
        assert "Division 09" in content
