"""
Unit tests for ColumnGrid and BeamBay framing array macros in debim.
Verifies batch generation of 20+ columns and beams from macro specifications,
exception point/beam filtering, storey level distributions, and end-to-end manifest parsing.
"""

from debim.modular import expand_macro_elements
from debim.schema import ProjectManifest, load_manifest, ColumnGrid, BeamBay


def test_column_grid_expansion_simple():
    macro_data = {
        "macro_elements": [
            {
                "type": "ColumnGrid",
                "grids_x": ["1", "2", "3", "4", "5"],
                "grids_y": ["A", "B", "C", "D"],
                "material": "CONCRETE_C30",
                "profile": {"shape": "BOX", "width": 0.30, "depth": 0.30},
                "base_storey": "L1",
                "top_storey": "L2",
                "tag_prefix": "C_",
            }
        ]
    }

    expanded = expand_macro_elements(macro_data)
    elements = expanded["elements"]

    # 5 x 4 = 20 columns
    assert len(elements) == 20
    assert all(e["class"] == "IfcColumn" for e in elements)
    assert elements[0]["tag"] == "C_1_A"
    assert elements[0]["placement"]["grid"] == ["1", "A"]
    assert elements[0]["placement"]["base_storey"] == "L1"
    assert elements[0]["placement"]["top_storey"] == "L2"
    assert elements[-1]["tag"] == "C_5_D"


def test_column_grid_multistorey_and_exceptions():
    macro_data = {
        "macro_elements": [
            {
                "type": "ColumnGrid",
                "grids_x": ["1", "2", "3", "4", "5"],
                "grids_y": ["A", "B", "C", "D", "E"],
                "material": "STEEL_SS400",
                "profile": {"shape": "BOX", "width": 0.40, "depth": 0.40},
                "storeys": ["L1", "L2", "L3"],
                "except_points": [("3", "C"), ("5", "E")],
                "tag_prefix": "COL_",
            }
        ]
    }

    expanded = expand_macro_elements(macro_data)
    elements = expanded["elements"]

    # 5 x 5 = 25 grid points - 2 exceptions = 23 columns per level
    # 2 storey pairs: (L1, L2), (L2, L3) => 23 x 2 = 46 columns total
    assert len(elements) == 46

    # Verify exception filtering
    tags = {e["tag"] for e in elements}
    assert "COL_3_C_L1" not in tags
    assert "COL_5_E_L1" not in tags
    assert "COL_3_C_L2" not in tags
    assert "COL_1_A_L1" in tags
    assert "COL_1_A_L2" in tags


def test_beam_bay_expansion_both_directions():
    macro_data = {
        "macro_elements": [
            {
                "type": "BeamBay",
                "grids_x": ["1", "2", "3", "4"],
                "grids_y": ["A", "B", "C", "D"],
                "material": "CONCRETE_C30",
                "profile": {"shape": "BOX", "width": 0.20, "depth": 0.50},
                "storey": "L2",
                "direction": "BOTH",
                "tag_prefix": "B_",
            }
        ]
    }

    expanded = expand_macro_elements(macro_data)
    elements = expanded["elements"]

    # X-direction beams: 4 Y-lines x 3 bays along X = 12 beams
    # Y-direction beams: 4 X-lines x 3 bays along Y = 12 beams
    # Total = 24 beams
    assert len(elements) == 24
    assert all(e["class"] == "IfcBeam" for e in elements)

    x_beams = [e for e in elements if e["placement"]["from_grid"][1] == e["placement"]["to_grid"][1]]
    y_beams = [e for e in elements if e["placement"]["from_grid"][0] == e["placement"]["to_grid"][0]]

    assert len(x_beams) == 12
    assert len(y_beams) == 12


def test_beam_bay_exceptions_and_multistorey():
    macro_data = {
        "macro_elements": [
            {
                "type": "BeamBay",
                "grids_x": ["1", "2", "3", "4", "5"],
                "grids_y": ["A", "B", "C"],
                "material": "CONCRETE_C30",
                "profile": {"shape": "BOX", "width": 0.25, "depth": 0.50},
                "storeys": ["L2", "L3"],
                "direction": "BOTH",
                "except_points": [("3", "B")],
                "except_beams": [
                    [("1", "A"), ("2", "A")],
                ],
                "tag_prefix": "BM_",
            }
        ]
    }

    expanded = expand_macro_elements(macro_data)
    elements = expanded["elements"]

    # Point ("3", "B") excludes:
    #   X-beams touching ("3", "B"): (2,B)-(3,B) and (3,B)-(4,B) [2 beams]
    #   Y-beams touching ("3", "B"): (3,A)-(3,B) and (3,B)-(3,C) [2 beams]
    # Beam exception excludes:
    #   (1,A)-(2,A) [1 beam]
    # Per storey:
    #   Baseline X: 3 Y-lines x 4 bays = 12 beams
    #   Baseline Y: 5 X-lines x 2 bays = 10 beams
    #   Total baseline per storey = 22 beams
    #   Excluded per storey: 2 (X touching 3,B) + 2 (Y touching 3,B) + 1 (1,A-2,A) = 5 beams
    #   Remaining per storey = 17 beams
    # 2 storeys => 34 beams total

    assert len(elements) == 34

    tags = {e["tag"] for e in elements}
    assert "BM_1_2_A_L2" not in tags
    assert "BM_2_3_B_L2" not in tags
    assert "BM_3_4_B_L2" not in tags
    assert "BM_3_A_B_L2" not in tags
    assert "BM_3_B_C_L2" not in tags


def test_end_to_end_manifest_validation(tmp_path):
    debim_yaml = """
schema: IFC4-Minimal
project:
  id: PROJ-MACRO-01
  name: Macro Framing Test
spatial_structure:
  storeys:
    - id: L1
      name: Level 1
      elevation: 0.0
      height: 3.5
    - id: L2
      name: Level 2
      elevation: 3.5
      height: 3.5
grids:
  axes_x:
    '1': 0.0
    '2': 4.0
    '3': 8.0
    '4': 12.0
    '5': 16.0
  axes_y:
    'A': 0.0
    'B': 5.0
    'C': 10.0
    'D': 15.0
materials:
  - id: CONCRETE_C30
    name: Concrete C30/37
    category: CONCRETE
    unit_cost_ref: MAT-CONC-01

macro_elements:
  - type: ColumnGrid
    grids_x: ['1', '2', '3', '4', '5']
    grids_y: ['A', 'B', 'C', 'D']
    material: CONCRETE_C30
    profile:
      shape: BOX
      width: 0.35
      depth: 0.35
    base_storey: L1
    top_storey: L2
    tag_prefix: C_

  - type: BeamBay
    grids_x: ['1', '2', '3', '4', '5']
    grids_y: ['A', 'B', 'C', 'D']
    material: CONCRETE_C30
    profile:
      shape: BOX
      width: 0.25
      depth: 0.50
    storey: L2
    direction: BOTH
    tag_prefix: B_
"""

    manifest_file = tmp_path / "project.debim"
    manifest_file.write_text(debim_yaml, encoding="utf-8")

    manifest = load_manifest(manifest_file)

    # 20 columns + 31 beams = 51 elements generated from 2 macro blocks
    cols = [e for e in manifest.elements if e.class_ == "IfcColumn"]
    beams = [e for e in manifest.elements if e.class_ == "IfcBeam"]

    assert len(cols) == 20
    assert len(beams) == 31  # (4 Y-lines x 4 bays X = 16) + (5 X-lines x 3 bays Y = 15) = 31
    assert len(manifest.elements) == 51
