"""
Unit tests for Human Scale furniture & equipment variable library schema,
clearance envelopes, built-in standard presets, and manifest loader.
"""

from pathlib import Path
import tempfile
import pytest
from debim.schema import (
    ClearanceEnvelope,
    Dimensions,
    FurnitureVariable,
    VariableDefinition,
    STANDARD_FURNITURE_VARIABLES,
    ProjectManifest,
    export_json_schema,
)
from debim.loader import (
    get_variable,
    get_variable_dimensions,
    get_variable_footprint,
    get_variable_envelope_footprint,
    load_debim_file,
)


def test_clearance_envelope_defaults():
    ce = ClearanceEnvelope()
    assert ce.front == 0.0
    assert ce.back == 0.0
    assert ce.left == 0.0
    assert ce.right == 0.0


def test_furniture_variable_and_footprint():
    var = FurnitureVariable(
        tag="DESK-01",
        name="Office Executive Desk",
        dimensions=Dimensions(width=1.60, depth=0.80, height=0.75),
        clearance=ClearanceEnvelope(front=0.80, back=0.20, left=0.30, right=0.30),
        category="office",
    )

    assert var.class_ == "Variable"
    assert var.dimensions.width == 1.60
    assert var.dimensions.depth == 0.80
    assert var.dimensions.height == 0.75

    # Physical area
    assert var.get_physical_area() == pytest.approx(1.60 * 0.80)

    # Total width = 1.60 + 0.30 (left) + 0.30 (right) = 2.20
    assert var.total_width == pytest.approx(2.20)

    # Total depth = 0.80 + 0.80 (front) + 0.20 (back) = 1.80
    assert var.total_depth == pytest.approx(1.80)

    # Total height = 0.75
    assert var.total_height == pytest.approx(0.75)

    # Total envelope area = 2.20 * 1.80 = 3.96
    assert var.get_total_area() == pytest.approx(3.96)

    fp = var.get_envelope_footprint()
    assert fp["physical_width"] == 1.60
    assert fp["physical_depth"] == 0.80
    assert fp["total_width"] == pytest.approx(2.20)
    assert fp["total_depth"] == pytest.approx(1.80)
    assert fp["total_area"] == pytest.approx(3.96)


def test_standard_furniture_presets():
    expected_keys = [
        "BED_KING_6FT",
        "BED_QUEEN_5FT",
        "WARDROBE_2M",
        "WORKING_DESK",
        "TOILET_STANDARD",
        "SHOWER_ENCLOSURE",
        "DINING_TABLE_6SEAT",
        "CAR_SEDAN",
    ]

    for key in expected_keys:
        assert key in STANDARD_FURNITURE_VARIABLES
        preset = STANDARD_FURNITURE_VARIABLES[key]
        assert isinstance(preset, FurnitureVariable)
        assert preset.dimensions.width > 0
        assert preset.dimensions.height > 0
        assert preset.clearance is not None
        assert preset.get_total_area() >= preset.get_physical_area()


def test_manifest_variables_validation():
    manifest_yaml = """
schema: IFC4-Minimal
project:
  id: PROJ-VARS
  name: Variable Test Project
spatial_structure:
  storeys:
    - id: FL1
      name: Floor 1
      elevation: 0.0
      height: 3.5
grids:
  axes_x:
    "1": 0.0
    "2": 5.0
  axes_y:
    A: 0.0
    B: 5.0
materials:
  - id: CONCRETE
    name: Concrete C25/30
    category: Concrete
    unit_cost_ref: MAT-CONC
variables:
  CUSTOM_DESK:
    class: Variable
    name: Custom Desk 1.5m
    dimensions:
      width: 1.50
      depth: 0.75
      height: 0.75
    clearance:
      front: 0.80
      left: 0.20
      right: 0.20
      back: 0.10
    category: office
"""
    manifest = ProjectManifest.model_validate_json(
        ProjectManifest.model_validate(
            __import__("yaml").safe_load(manifest_yaml)
        ).model_dump_json()
    )

    assert manifest.variables is not None
    assert "CUSTOM_DESK" in manifest.variables

    custom_var = manifest.get_variable("CUSTOM_DESK")
    assert custom_var is not None
    assert custom_var.name == "Custom Desk 1.5m"
    assert custom_var.dimensions.width == 1.50
    assert custom_var.total_width == pytest.approx(1.90)

    # Built-in preset fallback check via get_variable
    king_bed = manifest.get_variable("BED_KING_6FT")
    assert king_bed is not None
    assert king_bed.category == "bedroom"


def test_loader_helper_methods():
    manifest_data = {
        "variables": {
            "MY_TABLE": {
                "name": "My Meeting Table",
                "dimensions": {"width": 2.40, "depth": 1.20, "height": 0.75},
                "clearance": {"front": 1.0, "back": 1.0, "left": 1.0, "right": 1.0},
                "category": "office",
            }
        }
    }

    var = get_variable(manifest_data, "MY_TABLE")
    assert var is not None
    assert var.name == "My Meeting Table"

    dims = get_variable_dimensions(manifest_data, "MY_TABLE")
    assert dims.width == 2.40
    assert dims.depth == 1.20

    fp = get_variable_footprint(manifest_data, "MY_TABLE")
    assert fp["total_width"] == pytest.approx(4.40)
    assert fp["total_depth"] == pytest.approx(3.20)
    assert fp["total_area"] == pytest.approx(4.40 * 3.20)

    # Standard fallback test
    car = get_variable(manifest_data, "CAR_SEDAN")
    assert car is not None
    assert car.category == "parking"


def test_modular_include_variables():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        sub_file = tmp_path / "vars.debim"
        sub_file.write_text(
            """
variables:
  SUB_SOFA:
    name: 3-Seater Sofa
    dimensions:
      width: 2.10
      depth: 0.90
      height: 0.85
    clearance:
      front: 0.80
    category: living
""",
            encoding="utf-8",
        )

        main_file = tmp_path / "project.debim"
        main_file.write_text(
            """
schema: IFC4-Minimal
includes:
  - vars.debim
project:
  id: PROJ-INC
  name: Include Project
spatial_structure:
  storeys:
    - id: FL1
      name: Floor 1
      elevation: 0.0
      height: 3.0
grids:
  axes_x:
    "1": 0.0
  axes_y:
    A: 0.0
materials: []
variables:
  MAIN_LAMP:
    name: Floor Lamp
    dimensions:
      width: 0.40
      depth: 0.40
      height: 1.60
""",
            encoding="utf-8",
        )

        loaded_data = load_debim_file(main_file)
        assert "variables" in loaded_data
        vars_dict = loaded_data["variables"]
        assert "MAIN_LAMP" in vars_dict
        assert "SUB_SOFA" in vars_dict


def test_json_schema_export():
    schema = export_json_schema()
    assert "variables" in schema["properties"]
    defs = schema["$defs"]
    assert "FurnitureVariable" in defs
    assert "ClearanceEnvelope" in defs
