"""
Unit tests for zero-dependency standalone .debim loader and path resolver.
"""

from pathlib import Path
import sys
import pytest

from debim.loader import parse_debim, load_debim_file, resolve_default_manifest_path, _pure_yaml_parse
from debim.schema import load_manifest, ProjectManifest
from cli_runner import CliRunner


def test_parse_debim_basic():
    yaml_text = """
    schema: "IFC4-Minimal"
    project:
      id: "PRJ-01"
      name: "Test Project"
      units:
        length: "METER"
    site:
      bounding_box: [-3.0, -3.0, 15.0, 15.0]
      front_road_width: 6.0
      enabled: true
      notes: null
    elements:
      - class: IfcColumn
        tag: "C1"
        profile: { shape: BOX, width: 0.25, depth: 0.25 }
    """
    data = parse_debim(yaml_text)
    assert data["schema"] == "IFC4-Minimal"
    assert data["project"]["id"] == "PRJ-01"
    assert data["site"]["bounding_box"] == [-3.0, -3.0, 15.0, 15.0]
    assert data["site"]["enabled"] is True
    assert data["site"]["notes"] is None
    assert data["elements"][0]["tag"] == "C1"


def test_parse_debim_zero_dependency_fallback(monkeypatch):
    yaml_text = """
    # Zero dependency comment
    schema: "IFC4-Minimal"
    project:
      id: "PRJ-ZERO-01"
      name: "Pure Python Parser"
      elevation: 0.00
      height: 3.50
    grids:
      axes_x:
        "1": 0.00
        "2": 4.00
      axes_y:
        "A": 0.00
        "B": 4.00
    elements:
      - class: IfcColumn
        tag: "C1"
        profile: { shape: BOX, width: 0.25, depth: 0.25 }
      - class: IfcWall
        tag: "W1"
        height: 3.00
        layers:
          - name: "Finish"
            thickness: 0.015
          - name: "Structure"
            thickness: 0.075
    """
    # Force _HAS_PYYAML to False in loader
    import debim.loader
    monkeypatch.setattr(debim.loader, "_HAS_PYYAML", False)

    data = parse_debim(yaml_text)
    assert data["schema"] == "IFC4-Minimal"
    assert data["project"]["id"] == "PRJ-ZERO-01"
    assert data["project"]["elevation"] == 0.00
    assert data["grids"]["axes_x"]["1"] == 0.00
    assert len(data["elements"]) == 2
    assert data["elements"][0]["class"] == "IfcColumn"
    assert data["elements"][0]["tag"] == "C1"
    assert data["elements"][1]["layers"][0]["thickness"] == 0.015


def test_load_debim_file_house():
    house_path = Path("house.debim")
    assert house_path.exists()

    data = load_debim_file(house_path)
    assert data["schema"] == "IFC4-Minimal"
    assert data["project"]["id"] == "PRJ-HOUSE-01"
    assert len(data["elements"]) == 4

    manifest = load_manifest(house_path)
    assert isinstance(manifest, ProjectManifest)
    assert manifest.project.id == "PRJ-HOUSE-01"


def test_load_debim_file_modular_includes(tmp_path):
    root_file = tmp_path / "main.debim"
    models_dir = tmp_path / "models"
    models_dir.mkdir()

    sub1 = models_dir / "m1.debim"
    sub1.write_text("""
    materials:
      - id: "MAT1"
        name: "Concrete 1"
        category: "concrete"
        unit_cost_ref: "C1"
    elements:
      - class: IfcColumn
        tag: "C1"
        material: "MAT1"
        profile: { shape: BOX, width: 0.2, depth: 0.2 }
        placement: { grid: ["1", "A"], base_storey: "L1", top_storey: "L1" }
    """, encoding="utf-8")

    sub2 = models_dir / "m2.debim"
    sub2.write_text("""
    elements:
      - class: IfcWall
        tag: "W1"
        material: "MAT1"
        thickness: 0.10
        height: 3.00
        placement: { from_grid: ["1", "A"], to_grid: ["2", "A"], storey: "L1" }
    """, encoding="utf-8")

    root_file.write_text("""
    schema: "IFC4-Minimal"
    project:
      id: "PRJ-MODULAR"
      name: "Modular Test"
    spatial_structure:
      storeys:
        - id: "L1"
          name: "Level 1"
          elevation: 0.00
          height: 3.50
    grids:
      axes_x: { "1": 0.00, "2": 4.00 }
      axes_y: { "A": 0.00, "B": 4.00 }
    materials: []
    includes:
      - "models/*.debim"
    """, encoding="utf-8")

    data = load_debim_file(root_file)
    assert len(data["materials"]) == 1
    assert data["materials"][0]["id"] == "MAT1"
    assert len(data["elements"]) == 2

    manifest = load_manifest(root_file)
    assert manifest.project.id == "PRJ-MODULAR"
    assert len(manifest.elements) == 2


def test_resolve_default_manifest_path_candidates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    # 1. No files -> returns default project.debim
    res = resolve_default_manifest_path()
    assert res.name == "project.debim"

    # 2. project.yaml created
    p_yaml = tmp_path / "project.yaml"
    p_yaml.write_text("schema: IFC4", encoding="utf-8")
    assert resolve_default_manifest_path().name == "project.yaml"

    # 3. house.debim created (higher priority candidate)
    h_debim = tmp_path / "house.debim"
    h_debim.write_text("schema: IFC4", encoding="utf-8")
    assert resolve_default_manifest_path().name == "house.debim"

    # 4. project.debim created (highest priority)
    p_debim = tmp_path / "project.debim"
    p_debim.write_text("schema: IFC4", encoding="utf-8")
    assert resolve_default_manifest_path().name == "project.debim"

    # 5. Explicit non-existent path
    explicit_missing = resolve_default_manifest_path("custom.debim")
    assert explicit_missing == Path("custom.debim")


def test_cli_debim_native_commands():
    from debim.cli import app
    runner = CliRunner()

    res_validate = runner.invoke(app, ["validate", "-m", "house.debim"])
    assert res_validate.exit_code == 0
    assert "Validating" in res_validate.output

    res_qto = runner.invoke(app, ["qto", "-m", "house.debim"])
    assert res_qto.exit_code == 0
    assert "Quantitative Take-Off" in res_qto.output

    res_summary = runner.invoke(app, ["summary", "-m", "house.debim"])
    assert res_summary.exit_code == 0
    assert "PRJ-HOUSE-01" in res_summary.output
