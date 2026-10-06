"""
Unit tests for debim split and debim bundle commands and modular manifest engine.
"""

from pathlib import Path
import pytest
import yaml
from typer.testing import CliRunner

from debim.cli import app
from debim.modular import bundle_manifest, split_manifest
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import ProjectManifest, load_manifest

runner = CliRunner()

SAMPLE_MONOLITHIC_YAML = """
schema: IFC4-Minimal
project:
  id: PRJ-SPLIT-TEST
  name: "Split & Bundle Test Building"
  units:
    length: METER
    area: SQUARE_METER
    volume: CUBIC_METER
spatial_structure:
  storeys:
    - id: L1
      name: "Level 1"
      elevation: 0.00
      height: 3.50
    - id: L2
      name: "Level 2"
      elevation: 3.50
      height: 3.50
grids:
  axes_x:
    "1": 0.0
    "2": 6.0
  axes_y:
    "A": 0.0
    "B": 8.0
materials:
  - id: MAT_CONC
    name: "Structural Concrete"
    category: concrete
    unit_cost_ref: REF-CONC
  - id: MAT_BRICK
    name: "Clay Brick"
    category: masonry
    unit_cost_ref: REF-BRICK
elements:
  - class: IfcFooting
    tag: FT-01
    material: MAT_CONC
    profile:
      shape: BOX
      width: 1.50
      depth: 1.50
      thickness: 0.50
    placement:
      grid: ["1", "A"]
      storey: L1
  - class: IfcColumn
    tag: COL-01
    material: MAT_CONC
    profile:
      shape: BOX
      width: 0.40
      depth: 0.40
    placement:
      grid: ["1", "A"]
      base_storey: L1
      top_storey: L2
  - class: IfcColumn
    tag: COL-02
    material: MAT_CONC
    profile:
      shape: BOX
      width: 0.40
      depth: 0.40
    placement:
      grid: ["2", "B"]
      base_storey: L1
      top_storey: L2
  - class: IfcBeam
    tag: BM-01
    material: MAT_CONC
    profile:
      shape: BOX
      width: 0.25
      depth: 0.50
    placement:
      from_grid: ["1", "A"]
      to_grid: ["2", "A"]
      storey: L2
  - class: IfcWall
    tag: WL-01
    material: MAT_BRICK
    thickness: 0.20
    height: 3.00
    placement:
      from_grid: ["1", "A"]
      to_grid: ["1", "B"]
      storey: L1
"""


def test_split_manifest_by_system(tmp_path: Path):
    """Test splitting a monolithic manifest into modular system modules."""
    project_file = tmp_path / "project.yaml"
    project_file.write_text(SAMPLE_MONOLITHIC_YAML, encoding="utf-8")

    orig_manifest = load_manifest(project_file)
    assert len(orig_manifest.elements) == 5

    res = split_manifest(project_file, output_dir=tmp_path, by="system", backup=False)
    assert res["total_elements"] == 5
    assert not res["dry_run"]

    # Verify expected modular structure
    assert (tmp_path / "models" / "structure" / "foundations.yaml").exists()
    assert (tmp_path / "models" / "structure" / "columns.yaml").exists()
    assert (tmp_path / "models" / "structure" / "beams.yaml").exists()
    assert (tmp_path / "models" / "architecture" / "walls.yaml").exists()

    # Verify root manifest now has includes
    with open(project_file, "r", encoding="utf-8") as f:
        root_data = yaml.safe_load(f)
    assert root_data["includes"] == ["models/**/*.yaml"]
    assert "elements" not in root_data or not root_data["elements"]

    # Verify reloading the split project resolves identically
    split_loaded = load_manifest(project_file)
    assert len(split_loaded.elements) == 5

    orig_qto = calculate_qto(orig_manifest)
    split_qto = calculate_qto(split_loaded)
    assert orig_qto.total_concrete_volume == pytest.approx(split_qto.total_concrete_volume)
    assert orig_qto.total_formwork_area == pytest.approx(split_qto.total_formwork_area)


def test_split_manifest_by_storey(tmp_path: Path):
    """Test splitting manifest grouped by storey/level."""
    project_file = tmp_path / "project.yaml"
    project_file.write_text(SAMPLE_MONOLITHIC_YAML, encoding="utf-8")

    res = split_manifest(project_file, output_dir=tmp_path, by="storey", backup=False)
    assert res["total_elements"] == 5

    # Should group into L1 and L2
    assert (tmp_path / "models" / "storeys" / "l1.yaml").exists()
    assert (tmp_path / "models" / "storeys" / "l2.yaml").exists()

    split_loaded = load_manifest(project_file)
    assert len(split_loaded.elements) == 5


def test_split_manifest_dry_run(tmp_path: Path):
    """Test dry-run mode does not touch disk."""
    project_file = tmp_path / "project.yaml"
    project_file.write_text(SAMPLE_MONOLITHIC_YAML, encoding="utf-8")

    res = split_manifest(project_file, output_dir=tmp_path, by="system", dry_run=True)
    assert res["dry_run"] is True
    assert res["total_elements"] == 5
    assert not (tmp_path / "models").exists()


def test_bundle_manifest(tmp_path: Path):
    """Test bundling a multi-file modular manifest into a standalone single-file manifest."""
    # First split into modular format
    src_file = tmp_path / "project.yaml"
    src_file.write_text(SAMPLE_MONOLITHIC_YAML, encoding="utf-8")
    split_manifest(src_file, output_dir=tmp_path, by="system", backup=False)

    # Now bundle back
    bundled_file = tmp_path / "project.bundled.yaml"
    bundled_data = bundle_manifest(src_file, output_path=bundled_file)

    assert bundled_file.exists()
    assert "includes" not in bundled_data
    assert len(bundled_data["elements"]) == 5

    # Verify bundled file can be validated and parsed cleanly
    bundled_manifest = load_manifest(bundled_file)
    assert isinstance(bundled_manifest, ProjectManifest)
    assert len(bundled_manifest.elements) == 5
    assert bundled_manifest.project.id == "PRJ-SPLIT-TEST"


def test_cli_split_and_bundle(tmp_path: Path):
    """Test CLI commands 'debim split' and 'debim bundle'."""
    project_file = tmp_path / "project.yaml"
    project_file.write_text(SAMPLE_MONOLITHIC_YAML, encoding="utf-8")

    # 1. CLI split preview (dry-run)
    res_dry = runner.invoke(app, ["split", "-m", str(project_file), "--dry-run"])
    assert res_dry.exit_code == 0
    assert "Dry-run preview" in res_dry.output
    assert not (tmp_path / "models").exists()

    # 2. CLI split execution
    res_split = runner.invoke(app, ["split", "-m", str(project_file)])
    assert res_split.exit_code == 0
    assert "Successfully decomposed" in res_split.output
    assert (tmp_path / "models").exists()

    # 3. CLI bundle to file
    bundled_file = tmp_path / "bundled.yaml"
    res_bundle = runner.invoke(app, ["bundle", "-m", str(project_file), "-o", str(bundled_file)])
    assert res_bundle.exit_code == 0
    assert "Successfully bundled modular manifest" in res_bundle.output
    assert bundled_file.exists()

    # 4. CLI bundle to stdout
    res_stdout = runner.invoke(app, ["bundle", "-m", str(project_file)])
    assert res_stdout.exit_code == 0
    assert "schema: IFC4-Minimal" in res_stdout.output
    assert "PRJ-SPLIT-TEST" in res_stdout.output


def test_split_bundle_farnsworth_roundtrip(tmp_path: Path):
    """Verify roundtrip decomposition and bundling of standard Farnsworth House example."""
    farnsworth_src = Path("examples/farnsworth_house/project.yaml")
    if not farnsworth_src.exists():
        pytest.skip("examples/farnsworth_house/project.yaml not found")

    orig_manifest = load_manifest(farnsworth_src)
    orig_qto = calculate_qto(orig_manifest)

    # Copy farnsworth into tmp_path and split
    temp_proj = tmp_path / "project.yaml"
    temp_proj.write_text(farnsworth_src.read_text(encoding="utf-8"), encoding="utf-8")

    split_res = split_manifest(temp_proj, output_dir=tmp_path, by="system", backup=False)
    assert split_res["total_elements"] == len(orig_manifest.elements)

    # Bundle back
    bundled_file = tmp_path / "farnsworth.bundled.yaml"
    bundle_manifest(temp_proj, output_path=bundled_file)

    bundled_manifest = load_manifest(bundled_file)
    assert len(bundled_manifest.elements) == len(orig_manifest.elements)

    bundled_qto = calculate_qto(bundled_manifest)
    assert bundled_qto.total_concrete_volume == pytest.approx(orig_qto.total_concrete_volume)
    assert bundled_qto.total_formwork_area == pytest.approx(orig_qto.total_formwork_area)
    assert bundled_qto.total_rebar_weight == pytest.approx(orig_qto.total_rebar_weight)
