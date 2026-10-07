"""
Unit tests for Cloud Ephemeral Runner and Temp Storage Lifecycle (debim.cloud.runner).
Verifies in-memory compilation, 2D blueprint SVG generation, 3D HTML viewer, IFC STEP output,
BOQ calculation, deterministic execution, and 100% scratch directory auto-purge cleanup.
"""

import glob
import os
from pathlib import Path
import tempfile
import pytest

from debim.cloud.runner import (
    CloudRunner,
    CompileResult,
    compile_ephemeral,
    ephemeral_scratch_dir,
    generate_2d_blueprint_svg,
)
from debim.schema import ProjectManifest, load_manifest

SAMPLE_MANIFEST_YAML = """
schema: IFC4-Minimal
project:
  id: "proj-cloud-test"
  name: "Cloud Ephemeral Test House"
  units:
    length: METER
    area: SQUARE_METER
    volume: CUBIC_METER

spatial_structure:
  storeys:
    - id: "L1"
      name: "Ground Floor"
      elevation: 0.00
      height: 3.50

grids:
  axes_x:
    "1": 0.00
    "2": 6.00
  axes_y:
    "A": 0.00
    "B": 6.00

materials:
  - id: "MAT_CONC"
    name: "Reinforced Concrete C30"
    category: "structure"
    unit_cost_ref: "MAT-CONC-C30"
  - id: "MAT_BRICK"
    name: "AAC Block Wall"
    category: "architecture"
    unit_cost_ref: "MAT-BRICK-AAC"

elements:
  - class: IfcColumn
    tag: "C1"
    material: "MAT_CONC"
    profile:
      shape: BOX
      width: 0.30
      depth: 0.30
    placement:
      grid: ["1", "A"]
      base_storey: "L1"
      top_storey: "L1"

  - class: IfcColumn
    tag: "C2"
    material: "MAT_CONC"
    profile:
      shape: BOX
      width: 0.30
      depth: 0.30
    placement:
      grid: ["2", "A"]
      base_storey: "L1"
      top_storey: "L1"

  - class: IfcBeam
    tag: "B1"
    material: "MAT_CONC"
    profile:
      shape: BOX
      width: 0.20
      depth: 0.40
    placement:
      from_grid: ["1", "A"]
      to_grid: ["2", "A"]
      storey: "L1"
      offset_z: 3.50

  - class: IfcWall
    tag: "W1"
    material: "MAT_BRICK"
    thickness: 0.15
    height: 3.50
    placement:
      from_grid: ["1", "A"]
      to_grid: ["2", "A"]
      storey: "L1"
    children:
      - class: IfcDoor
        tag: "D1"
        dimensions:
          width: 0.90
          height: 2.10
        offset_distance: 2.00
      - class: IfcWindow
        tag: "WIN1"
        dimensions:
          width: 1.20
          height: 1.20
        offset_distance: 4.00
        sill_height: 1.00

  - class: IfcSlab
    tag: "S1"
    material: "MAT_CONC"
    thickness: 0.15
    slab_type: SOLID
    placement:
      boundary: [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]]
      storey: "L1"
      offset_z: 3.50
"""

SAMPLE_PRICES_JSON = """{
  "currency": "THB",
  "items": {
    "MAT-CONC-C30": {
      "name": "Concrete C30/37",
      "unit": "m3",
      "material_cost": 2500.0,
      "labor_cost": 450.0
    },
    "MAT-BRICK-AAC": {
      "name": "AAC Masonry Wall",
      "unit": "m2",
      "material_cost": 320.0,
      "labor_cost": 180.0
    },
    "MAT-FORMWORK": {
      "name": "Formwork Timber",
      "unit": "m2",
      "material_cost": 250.0,
      "labor_cost": 150.0
    }
  }
}"""


def list_scratch_dirs() -> list:
    """Helper listing active /tmp/debim_scratch_* directories."""
    tmp_dir = "/tmp" if os.path.exists("/tmp") else tempfile.gettempdir()
    pattern = os.path.join(tmp_dir, "debim_scratch_*")
    return [d for d in glob.glob(pattern) if os.path.isdir(d)]


def test_ephemeral_compile_from_yaml_string():
    """Verify ephemeral execution pipeline accepting in-memory YAML payload."""
    result = compile_ephemeral(payload=SAMPLE_MANIFEST_YAML, price_catalog=SAMPLE_PRICES_JSON)

    assert result.success is True
    assert result.error is None
    assert result.manifest_id == "proj-cloud-test"
    assert result.manifest_name == "Cloud Ephemeral Test House"

    # Check 3D HTML Viewer Output
    assert len(result.viewer_html) > 0
    assert "<!DOCTYPE html>" in result.viewer_html
    assert "Cloud Ephemeral Test House" in result.viewer_html

    # Check 2D Vector Blueprint SVG Output
    assert len(result.blueprint_2d) > 0
    assert "<svg" in result.blueprint_2d
    assert "</svg>" in result.blueprint_2d
    assert "debim 2D Architectural Blueprint" in result.blueprint_2d

    # Check IFC STEP File
    assert len(result.ifc_content) > 0
    assert "ISO-10303-21;" in result.ifc_content
    assert "FILE_SCHEMA(('IFC4'));" in result.ifc_content
    assert "END-ISO-10303-21;" in result.ifc_content

    # Check BOQ Summary
    assert result.boq_summary["currency"] == "THB"
    assert result.boq_summary["grand_total"] > 0.0
    assert result.qto_summary["total_concrete_volume"] > 0.0

    # Check Artifacts payload
    assert "viewer.html" in result.artifacts
    assert "blueprint.svg" in result.artifacts
    assert "model.ifc" in result.artifacts
    assert "boq.csv" in result.artifacts
    assert "boq.json" in result.artifacts


def test_ephemeral_compile_from_checkout_dir(tmp_path):
    """Verify ephemeral compilation from temporary project directory."""
    proj_dir = tmp_path / "checkout_project"
    proj_dir.mkdir(parents=True, exist_ok=True)

    (proj_dir / "project.yaml").write_text(SAMPLE_MANIFEST_YAML, encoding="utf-8")
    (proj_dir / "prices.json").write_text(SAMPLE_PRICES_JSON, encoding="utf-8")

    result = compile_ephemeral(payload=proj_dir)

    assert result.success is True
    assert result.manifest_id == "proj-cloud-test"
    assert len(result.ifc_content) > 0
    assert len(result.viewer_html) > 0
    assert len(result.blueprint_2d) > 0


def test_scratch_directory_auto_purge_on_success():
    """Verify 100% scratch directory wipeout after successful compilation."""
    initial_scratches = set(list_scratch_dirs())

    result = compile_ephemeral(payload=SAMPLE_MANIFEST_YAML)
    assert result.success is True

    final_scratches = set(list_scratch_dirs())
    # Assert no new scratch directory was leaked on disk
    new_scratches = final_scratches - initial_scratches
    assert len(new_scratches) == 0, f"Leaked scratch directories: {new_scratches}"


def test_scratch_directory_auto_purge_on_failure():
    """Verify 100% scratch directory wipeout even upon exception/failure."""
    initial_scratches = set(list_scratch_dirs())

    invalid_yaml = "invalid_manifest_key: foo\nelements: [broken_element_data]"

    result = compile_ephemeral(payload=invalid_yaml)
    assert result.success is False
    assert result.error is not None

    final_scratches = set(list_scratch_dirs())
    new_scratches = final_scratches - initial_scratches
    assert len(new_scratches) == 0, f"Leaked scratch directories on failure: {new_scratches}"


def test_ephemeral_scratch_dir_context_manager():
    """Directly test ephemeral_scratch_dir context manager cleanup."""
    scratch_path = None
    with ephemeral_scratch_dir(prefix="debim_scratch_test_") as s_dir:
        scratch_path = s_dir
        assert scratch_path.exists()
        assert scratch_path.is_dir()
        # Write dummy file
        (scratch_path / "dummy.txt").write_text("hello", encoding="utf-8")

    # Outside context manager
    assert scratch_path is not None
    assert not scratch_path.exists(), "Scratch directory was not purged after exit"


def test_deterministic_execution():
    """Verify compilation pipeline determinism across multiple runs."""
    res1 = compile_ephemeral(payload=SAMPLE_MANIFEST_YAML, price_catalog=SAMPLE_PRICES_JSON)
    res2 = compile_ephemeral(payload=SAMPLE_MANIFEST_YAML, price_catalog=SAMPLE_PRICES_JSON)

    assert res1.success is True
    assert res2.success is True
    assert res1.qto_summary == res2.qto_summary
    assert res1.boq_summary == res2.boq_summary
    assert len(res1.ifc_content) == len(res2.ifc_content)


def test_cloud_runner_class_and_bytes_artifacts():
    """Verify CloudRunner class with return_bytes option."""
    runner = CloudRunner(prefix="debim_scratch_runner_")
    result = runner.compile(payload=SAMPLE_MANIFEST_YAML, return_bytes=True)

    assert result.success is True
    assert isinstance(result.artifacts["model.ifc"], bytes)
    assert isinstance(result.artifacts["viewer.html"], bytes)
    assert isinstance(result.artifacts["blueprint.svg"], bytes)
    assert b"ISO-10303-21;" in result.artifacts["model.ifc"]


def test_generate_2d_blueprint_svg_standalone():
    """Verify generate_2d_blueprint_svg with ProjectManifest object input."""
    import yaml
    data = yaml.safe_load(SAMPLE_MANIFEST_YAML)
    manifest_obj = ProjectManifest.model_validate(data)

    svg_str = generate_2d_blueprint_svg(manifest_obj)
    assert "<svg" in svg_str
    assert "</svg>" in svg_str
    assert 'class="wall-fill"' in svg_str
    assert 'class="column-fill"' in svg_str
    assert 'class="grid-line"' in svg_str
