"""
Unit tests for debim.schema parsing and manifest validation.
"""

from pathlib import Path
import pytest
from pydantic import ValidationError
import yaml

from debim.schema import (
    IfcBeam,
    IfcColumn,
    IfcCustomElement,
    IfcWall,
    ProjectManifest,
    load_manifest,
)


def test_load_townhouse_manifest():
    manifest_path = Path("examples/townhouse/project.yaml")
    manifest = load_manifest(manifest_path)
    assert isinstance(manifest, ProjectManifest)
    assert manifest.project.id == "PRJ-2026-001"
    assert manifest.project.name == "Townhouse-Feasibility"
    assert len(manifest.spatial_structure.storeys) == 2
    assert len(manifest.materials) == 2
    assert len(manifest.elements) == 4

    # Verify element instances
    classes = [elem.class_ for elem in manifest.elements]
    assert classes == ["IfcColumn", "IfcBeam", "IfcWall", "IfcCustomElement"]

    column = manifest.elements[0]
    assert isinstance(column, IfcColumn)
    assert column.tag == "C-A1"

    beam = manifest.elements[1]
    assert isinstance(beam, IfcBeam)
    assert beam.tag == "B-A1_B1"

    wall = manifest.elements[2]
    assert isinstance(wall, IfcWall)
    assert wall.tag == "W-A1_A2"
    assert len(wall.children) == 1
    assert wall.children[0].class_ == "IfcDoor"

    custom = manifest.elements[3]
    assert isinstance(custom, IfcCustomElement)
    assert custom.tag == "ST-01"


def test_invalid_storey_reference():
    with open("examples/townhouse/project.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Change column base_storey to non-existent storey L99
    data["elements"][0]["placement"]["base_storey"] = "L99"

    with pytest.raises(ValidationError) as exc_info:
        ProjectManifest.model_validate(data)
    assert "references unknown base_storey 'L99'" in str(exc_info.value)


def test_invalid_grid_reference():
    with open("examples/townhouse/project.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Change beam from_grid X axis to unknown axis Z
    data["elements"][1]["placement"]["from_grid"] = ["Z", "1"]

    with pytest.raises(ValidationError) as exc_info:
        ProjectManifest.model_validate(data)
    assert "references unknown X grid 'Z'" in str(exc_info.value)


def test_invalid_material_reference():
    with open("examples/townhouse/project.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Change wall material to unknown material MAT_999
    data["elements"][2]["material"] = "MAT_999"

    with pytest.raises(ValidationError) as exc_info:
        ProjectManifest.model_validate(data)
    assert "references unknown material 'MAT_999'" in str(exc_info.value)


def test_missing_file_raises_error():
    with pytest.raises(FileNotFoundError):
        load_manifest("non_existent_file.yaml")


def test_piled_footing_schema():
    from debim.schema import IfcFooting, FootingProfile, FootingPlacement, FootingPiles, PileProfile

    footing = IfcFooting(
        **{
            "class": "IfcFooting",
            "tag": "F4-01",
            "material": "CONC_240",
            "profile": FootingProfile(width=1.20, depth=1.20, thickness=0.40),
            "placement": FootingPlacement(grid=("1", "A"), storey="L1"),
            "piles": FootingPiles(
                count=4,
                profile=PileProfile(shape="HEXAGONAL", dimension=0.15),
                length=6.00,
                spacing=0.50,
            ),
        }
    )
    assert footing.tag == "F4-01"
    assert footing.piles is not None
    assert footing.piles.count == 4
    assert footing.piles.profile.shape == "HEXAGONAL"
    assert footing.piles.length == 6.00


def test_slab_schema():
    from debim.schema import IfcSlab, SlabPlacement, SlabReinforcement

    slab = IfcSlab(
        **{
            "class": "IfcSlab",
            "tag": "S-L2-01",
            "material": "CONC_240",
            "thickness": 0.10,
            "slab_type": "PRECAST_PLANK",
            "placement": SlabPlacement(
                boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")],
                storey="L1",
            ),
            "reinforcement": SlabReinforcement(mesh="Wire Mesh Ø 4mm @ 0.20m"),
        }
    )
    assert slab.tag == "S-L2-01"
    assert slab.thickness == 0.10
    assert slab.slab_type == "PRECAST_PLANK"
    assert len(slab.placement.boundary) == 4


def test_ifcstair_schema():
    from debim.schema import IfcStair, StairPlacement, StairLanding, StairStepConfig, StairReinforcement

    stair = IfcStair(
        **{
            "class": "IfcStair",
            "tag": "ST-01",
            "material": "CONC_210",
            "stair_type": "DOG_LEG",
            "width": 1.00,
            "waist_thickness": 0.12,
            "placement": StairPlacement(
                grid_anchor=("2", "C"),
                from_storey="L1",
                to_storey="L2",
                offset_x=0.0,
                offset_y=0.0,
                offset_z=0.0,
                orientation="+Y",
            ),
            "landing": StairLanding(
                elevation=1.875,
                depth=1.00,
                thickness=0.12,
            ),
            "steps": StairStepConfig(
                tread=0.25,
                riser=0.1875,
            ),
            "reinforcement": StairReinforcement(
                main="DB12 @ 0.15m",
                temperature="RB9 @ 0.20m",
            ),
        }
    )
    assert stair.tag == "ST-01"
    assert stair.stair_type == "DOG_LEG"
    assert stair.width == 1.00
    assert stair.steps.riser == 0.1875
    assert stair.steps.tread == 0.25
    assert stair.landing.depth == 1.00


def test_includes_directive_list_and_dict_format(tmp_path):
    modules_dir = tmp_path / "modules"
    modules_dir.mkdir()

    # Create module with raw list of elements
    cols_file = modules_dir / "columns.yaml"
    cols_content = """
- class: IfcColumn
  tag: C-01
  material: CONC_210
  profile: { shape: BOX, width: 0.20, depth: 0.20 }
  placement: { grid: ["1", "A"], base_storey: L1, top_storey: L2 }
"""
    cols_file.write_text(cols_content, encoding="utf-8")

    # Create module with dict format (materials and elements)
    extra_file = modules_dir / "extra.yaml"
    extra_content = """
materials:
  - id: CONC_210
    name: "Concrete 210"
    category: concrete
    unit_cost_ref: "REF-01"
  - id: EXTRA_MAT
    name: "Extra Material"
    category: misc
    unit_cost_ref: "REF-02"
elements:
  - class: IfcBeam
    tag: B-01
    material: CONC_210
    profile: { shape: BOX, width: 0.20, depth: 0.40 }
    placement: { from_grid: ["1", "A"], to_grid: ["2", "A"], storey: L1 }
"""
    extra_file.write_text(extra_content, encoding="utf-8")

    root_file = tmp_path / "project.yaml"
    root_content = """
schema: IFC4-Minimal
project:
  id: PRJ-TEST-MODULAR
  name: "Modular Project Test"
  units: { length: METER, area: SQUARE_METER, volume: CUBIC_METER }
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
  axes_x: { "1": 0.0, "2": 4.0 }
  axes_y: { "A": 0.0, "B": 5.0 }
materials:
  - id: CONC_210
    name: "Concrete 210"
    category: concrete
    unit_cost_ref: "REF-01"
includes:
  - "modules/columns.yaml"
  - "modules/extra.yaml"
"""
    root_file.write_text(root_content, encoding="utf-8")

    manifest = load_manifest(root_file)
    assert len(manifest.materials) == 2
    assert {m.id for m in manifest.materials} == {"CONC_210", "EXTRA_MAT"}
    assert len(manifest.elements) == 2
    assert manifest.elements[0].tag == "C-01"
    assert manifest.elements[1].tag == "B-01"


def test_includes_missing_file_error(tmp_path):
    root_file = tmp_path / "project.yaml"
    root_content = """
schema: IFC4-Minimal
project:
  id: PRJ-TEST-MISSING
  name: "Missing Include Test"
spatial_structure:
  storeys:
    - id: L1
      name: "Level 1"
      elevation: 0.00
      height: 3.50
grids:
  axes_x: { "1": 0.0 }
  axes_y: { "A": 0.0 }
materials: []
includes:
  - "modules/non_existent.yaml"
"""
    root_file.write_text(root_content, encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        load_manifest(root_file)


def test_includes_circular_reference_prevention(tmp_path):
    file_a = tmp_path / "a.yaml"
    file_b = tmp_path / "b.yaml"

    content_a = f"""
schema: IFC4-Minimal
project:
  id: PRJ-CIRCULAR
  name: "Circular Include Test"
spatial_structure:
  storeys:
    - id: L1
      name: "Level 1"
      elevation: 0.00
      height: 3.50
grids:
  axes_x: {{ "1": 0.0 }}
  axes_y: {{ "A": 0.0 }}
materials: []
includes:
  - "{file_b.name}"
"""
    content_b = f"""
includes:
  - "{file_a.name}"
elements: []
"""
    file_a.write_text(content_a, encoding="utf-8")
    file_b.write_text(content_b, encoding="utf-8")

    with pytest.raises(ValueError) as exc_info:
        load_manifest(file_a)
    assert "Circular include detected" in str(exc_info.value)
