"""
Unit tests for IfcSpace functional scopes, variable reference consumption,
clearance envelope footprint aggregation, 30% circulation rule,
and design specification schemas.
"""

import pytest
import yaml
from debim.schema import (
    IfcSpace,
    ProjectManifest,
    SpaceAdjacencySpec,
    SpaceDesignSpec,
    VariableReference,
)
from debim.resolver import resolve_manifest


def test_space_schema_with_contains_and_design_spec():
    space_yaml = """
class: IfcSpace
tag: SPACE-BED-01
name: Master Bedroom
height: 3.0
placement:
  storey: FL1
  boundary:
    - ["1", "A"]
    - ["3", "A"]
    - ["3", "B"]
    - ["1", "B"]
contains:
  - BED_KING_6FT
  - WARDROBE_2M
design_spec:
  min_area: 18.0
  clear_height: 2.80
  natural_ventilation_ratio: 0.10
  adjacencies:
    must_connect: ["SPACE-BATH-01", "SPACE-HALLWAY"]
    forbidden_adjacent: ["SPACE-KITCHEN"]
"""
    space_data = yaml.safe_load(space_yaml)
    space = IfcSpace.model_validate(space_data)

    assert space.tag == "SPACE-BED-01"
    assert space.contains is not None
    assert len(space.contains) == 2
    assert space.contains[0].ref == "BED_KING_6FT"
    assert space.contains[0].count == 1
    assert space.contains[1].ref == "WARDROBE_2M"
    assert space.contains[1].count == 1

    assert space.design_spec is not None
    assert space.design_spec.min_area == 18.0
    assert space.design_spec.clear_height == 2.80
    assert space.design_spec.natural_ventilation_ratio == 0.10
    assert space.design_spec.adjacencies is not None
    assert space.design_spec.adjacencies.must_connect == ["SPACE-BATH-01", "SPACE-HALLWAY"]
    assert space.design_spec.adjacencies.forbidden_adjacent == ["SPACE-KITCHEN"]


def test_variable_reference_flexibility():
    # String reference
    vr1 = VariableReference.model_validate("WORKING_DESK")
    assert vr1.ref == "WORKING_DESK"
    assert vr1.count == 1

    # Dict reference with ref and count
    vr2 = VariableReference.model_validate({"ref": "WORKING_DESK", "count": 2})
    assert vr2.ref == "WORKING_DESK"
    assert vr2.count == 2

    # Compact single-key dict reference
    vr3 = VariableReference.model_validate({"TOILET_STANDARD": 3})
    assert vr3.ref == "TOILET_STANDARD"
    assert vr3.count == 3


def test_space_required_area_calculation_30_percent_rule():
    manifest_yaml = """
schema: IFC4-Minimal
project:
  id: PROJ-FUNCTIONAL-SCOPE
  name: Space Functional Scope Project
spatial_structure:
  storeys:
    - id: FL1
      name: Floor 1
      elevation: 0.0
      height: 3.2
grids:
  axes_x:
    "1": 0.0
    "2": 5.0
    "3": 10.0
  axes_y:
    A: 0.0
    B: 6.0
materials:
  - id: CONCRETE
    name: Concrete C25/30
    category: Concrete
    unit_cost_ref: MAT-CONC
variables:
  CUSTOM_DESK:
    name: Custom Desk
    dimensions:
      width: 1.50
      depth: 0.80
      height: 0.75
    clearance:
      front: 0.80
      back: 0.20
      left: 0.25
      right: 0.25
elements:
  - class: IfcSpace
    tag: SPACE-OFFICE-01
    name: Executive Office
    height: 3.0
    placement:
      storey: FL1
      boundary:
        - ["1", "A"]
        - ["3", "A"]
        - ["3", "B"]
        - ["1", "B"]
    contains:
      - BED_KING_6FT
      - WARDROBE_2M
      - ref: CUSTOM_DESK
        count: 2
    design_spec:
      min_area: 20.0
      clear_height: 2.80
"""
    manifest_data = yaml.safe_load(manifest_yaml)
    manifest = ProjectManifest.model_validate(manifest_data)
    resolved = resolve_manifest(manifest)

    r_space = resolved.spaces[0]
    assert r_space.tag == "SPACE-OFFICE-01"
    assert r_space.net_floor_area == pytest.approx(60.0)  # 10.0 * 6.0

    # Contained items check
    # 1. BED_KING_6FT:
    #    width=1.83, depth=1.98, clearance(front=0.60, left=0.60, right=0.60, back=0.00)
    #    total_width = 1.83 + 0.60 + 0.60 = 3.03
    #    total_depth = 1.98 + 0.60 + 0.00 = 2.58
    #    footprint = 3.03 * 2.58 = 7.8174 m2
    bed_area = (1.83 + 0.60 + 0.60) * (1.98 + 0.60 + 0.00)
    assert bed_area == pytest.approx(7.8174)

    # 2. WARDROBE_2M:
    #    width=2.00, depth=0.60, clearance(front=0.80, left=0.00, right=0.00, back=0.00)
    #    total_width = 2.00
    #    total_depth = 0.60 + 0.80 = 1.40
    #    footprint = 2.00 * 1.40 = 2.80 m2
    wardrobe_area = 2.00 * (0.60 + 0.80)
    assert wardrobe_area == pytest.approx(2.80)

    # 3. CUSTOM_DESK (count = 2):
    #    width=1.50, depth=0.80, clearance(front=0.80, back=0.20, left=0.25, right=0.25)
    #    total_width = 1.50 + 0.25 + 0.25 = 2.00
    #    total_depth = 0.80 + 0.80 + 0.20 = 1.80
    #    footprint_per_unit = 2.00 * 1.80 = 3.60 m2
    #    total_desk_area = 3.60 * 2 = 7.20 m2
    desk_area = (1.50 + 0.25 + 0.25) * (0.80 + 0.80 + 0.20) * 2
    assert desk_area == pytest.approx(7.20)

    total_footprint = bed_area + wardrobe_area + desk_area
    assert total_footprint == pytest.approx(7.8174 + 2.80 + 7.20)
    assert r_space.contained_items_footprint == pytest.approx(total_footprint)

    # Architectural formula: Required Area = (Sum of Contained Items Footprint) * 1.30
    expected_required_area = total_footprint * 1.30
    assert r_space.required_net_area == pytest.approx(expected_required_area)
    assert r_space.net_floor_area >= r_space.required_net_area


def test_invalid_variable_reference_raises_validation_error():
    manifest_yaml = """
schema: IFC4-Minimal
project:
  id: PROJ-ERR
  name: Invalid Var Project
spatial_structure:
  storeys:
    - id: FL1
      name: Floor 1
      elevation: 0.0
      height: 3.0
grids:
  axes_x:
    "1": 0.0
    "2": 5.0
  axes_y:
    A: 0.0
    B: 5.0
materials: []
elements:
  - class: IfcSpace
    tag: SPACE-01
    placement:
      storey: FL1
      boundary:
        - ["1", "A"]
        - ["2", "A"]
        - ["2", "B"]
        - ["1", "B"]
    contains:
      - NON_EXISTENT_VARIABLE
"""
    manifest_data = yaml.safe_load(manifest_yaml)
    with pytest.raises(ValueError, match="Space 'SPACE-01' references unknown variable 'NON_EXISTENT_VARIABLE'"):
        ProjectManifest.model_validate(manifest_data)
