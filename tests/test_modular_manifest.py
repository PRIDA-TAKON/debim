"""
Unit tests for multi-file modular manifest support ('includes' pattern) in debim.
"""

from pathlib import Path
import pytest
from pydantic import ValidationError

from debim.qto import calculate_qto
from debim.resolver import SpatialResolver, resolve_manifest
from debim.schema import ProjectManifest, load_manifest


def test_modular_manifest_basic_glob(tmp_path: Path):
    """Test root project.yaml with glob pattern includes: ['models/*.yaml']."""
    models_dir = tmp_path / "models"
    models_dir.mkdir()

    # 1. Site / Grids / Storeys in site.yaml
    site_file = models_dir / "00_site.yaml"
    site_file.write_text(
        """
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
  - id: CONC_300
    name: "Structural Concrete 300 ksc"
    category: concrete
    unit_cost_ref: MAT-CONC-01
""",
        encoding="utf-8",
    )

    # 2. Columns in columns.yaml (raw element list)
    cols_file = models_dir / "01_columns.yaml"
    cols_file.write_text(
        """
- class: IfcColumn
  tag: COL-C1
  material: CONC_300
  profile:
    shape: BOX
    width: 0.40
    depth: 0.40
  placement:
    grid: ["1", "A"]
    base_storey: L1
    top_storey: L2
- class: IfcColumn
  tag: COL-C2
  material: CONC_300
  profile:
    shape: BOX
    width: 0.40
    depth: 0.40
  placement:
    grid: ["2", "B"]
    base_storey: L1
    top_storey: L2
""",
        encoding="utf-8",
    )

    # 3. Beams in beams.yaml (dict format)
    beams_file = models_dir / "02_beams.yaml"
    beams_file.write_text(
        """
elements:
  - class: IfcBeam
    tag: BM-B1
    material: CONC_300
    profile:
      shape: BOX
      width: 0.25
      depth: 0.50
    placement:
      from_grid: ["1", "A"]
      to_grid: ["2", "A"]
      storey: L2
""",
        encoding="utf-8",
    )

    # Root project.yaml
    root_file = tmp_path / "project.yaml"
    root_file.write_text(
        """
schema: IFC4-Minimal
project:
  id: PRJ-MODULAR-01
  name: "Modular Multi-File Manifest Building"
  units:
    length: METER
    area: SQUARE_METER
    volume: CUBIC_METER
includes:
  - "models/*.yaml"
""",
        encoding="utf-8",
    )

    manifest = load_manifest(root_file)

    # Verify Pydantic validation
    assert isinstance(manifest, ProjectManifest)
    assert manifest.project.id == "PRJ-MODULAR-01"

    # Verify Storeys and Grids deep-merge
    assert len(manifest.spatial_structure.storeys) == 2
    assert {s.id for s in manifest.spatial_structure.storeys} == {"L1", "L2"}
    assert manifest.grids.axes_x == {"1": 0.0, "2": 6.0}
    assert manifest.grids.axes_y == {"A": 0.0, "B": 8.0}

    # Verify Materials and Elements aggregation
    assert len(manifest.materials) == 1
    assert manifest.materials[0].id == "CONC_300"
    assert len(manifest.elements) == 3
    tags = [elem.tag for elem in manifest.elements]
    assert tags == ["COL-C1", "COL-C2", "BM-B1"]

    # Verify SpatialResolver resolution
    resolved = resolve_manifest(manifest)
    assert len(resolved.columns) == 2
    assert len(resolved.beams) == 1
    assert resolved.columns[0].start_point == (0.0, 0.0, 0.0)
    assert resolved.columns[0].end_point == (0.0, 0.0, 3.5)
    assert resolved.beams[0].span_length == 6.0

    # Verify QTO calculation
    qto = calculate_qto(manifest)
    assert qto.total_concrete_volume > 0.0
    assert qto.total_formwork_area > 0.0


def test_modular_manifest_nested_includes(tmp_path: Path):
    """Test sub-manifests that recursively include further sub-manifests."""
    struct_dir = tmp_path / "models" / "structure"
    struct_dir.mkdir(parents=True)

    # Deepest level: foundations.yaml
    fnd_file = struct_dir / "foundations.yaml"
    fnd_file.write_text(
        """
elements:
  - class: IfcFooting
    tag: FT-F1
    material: MAT_CONC
    profile:
      shape: BOX
      width: 1.20
      depth: 1.20
      thickness: 0.40
    placement:
      grid: ["1", "A"]
      storey: L1
""",
        encoding="utf-8",
    )

    # Sub-manifest: structure_index.yaml (includes foundations.yaml)
    struct_index = struct_dir / "structure_index.yaml"
    struct_index.write_text(
        """
includes:
  - "foundations.yaml"
elements:
  - class: IfcColumn
    tag: COL-C1
    material: MAT_CONC
    profile:
      shape: BOX
      width: 0.30
      depth: 0.30
    placement:
      grid: ["1", "A"]
      base_storey: L1
      top_storey: L2
""",
        encoding="utf-8",
    )

    # Root project.yaml
    root_file = tmp_path / "project.yaml"
    root_file.write_text(
        """
schema: IFC4-Minimal
project:
  id: PRJ-NESTED
  name: "Nested Includes Test"
spatial_structure:
  storeys:
    - id: L1
      name: "Level 1"
      elevation: 0.00
      height: 3.00
    - id: L2
      name: "Level 2"
      elevation: 3.00
      height: 3.00
grids:
  axes_x: { "1": 0.0 }
  axes_y: { "A": 0.0 }
materials:
  - id: MAT_CONC
    name: "Concrete"
    category: concrete
    unit_cost_ref: REF-CONC
includes:
  - "models/structure/structure_index.yaml"
""",
        encoding="utf-8",
    )

    manifest = load_manifest(root_file)
    assert len(manifest.elements) == 2
    tags = {elem.tag for elem in manifest.elements}
    assert tags == {"FT-F1", "COL-C1"}


def test_missing_glob_pattern_raises_error(tmp_path: Path):
    """Test friendly FileNotFoundError when a glob pattern matches no files."""
    root_file = tmp_path / "project.yaml"
    root_file.write_text(
        """
schema: IFC4-Minimal
project:
  id: PRJ-MISSING-GLOB
  name: "Missing Glob Test"
spatial_structure:
  storeys:
    - id: L1
      name: "L1"
      elevation: 0.0
      height: 3.0
grids:
  axes_x: { "1": 0.0 }
  axes_y: { "A": 0.0 }
materials: []
includes:
  - "non_existent_folder/**/*.yaml"
""",
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError) as exc_info:
        load_manifest(root_file)
    assert "No files matched include pattern" in str(exc_info.value)


def test_missing_explicit_file_raises_error(tmp_path: Path):
    """Test FileNotFoundError when an explicit included file does not exist."""
    root_file = tmp_path / "project.yaml"
    root_file.write_text(
        """
schema: IFC4-Minimal
project:
  id: PRJ-MISSING-FILE
  name: "Missing File Test"
spatial_structure:
  storeys:
    - id: L1
      name: "L1"
      elevation: 0.0
      height: 3.0
grids:
  axes_x: { "1": 0.0 }
  axes_y: { "A": 0.0 }
materials: []
includes:
  - "models/columns.yaml"
""",
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError) as exc_info:
        load_manifest(root_file)
    assert "Included file not found" in str(exc_info.value)


def test_circular_include_prevention(tmp_path: Path):
    """Test ValueError when circular includes are detected."""
    f1 = tmp_path / "mod_a.yaml"
    f2 = tmp_path / "mod_b.yaml"

    f1.write_text(
        f"""
includes:
  - "{f2.name}"
""",
        encoding="utf-8",
    )
    f2.write_text(
        f"""
includes:
  - "{f1.name}"
""",
        encoding="utf-8",
    )

    root_file = tmp_path / "project.yaml"
    root_file.write_text(
        f"""
schema: IFC4-Minimal
project:
  id: PRJ-CIRCULAR
  name: "Circular Include Test"
spatial_structure:
  storeys:
    - id: L1
      name: "L1"
      elevation: 0.0
      height: 3.0
grids:
  axes_x: {{ "1": 0.0 }}
  axes_y: {{ "A": 0.0 }}
materials: []
includes:
  - "{f1.name}"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        load_manifest(root_file)
    assert "Circular include detected" in str(exc_info.value)


def test_empty_included_yaml_file(tmp_path: Path):
    """Test that empty included files do not crash manifest parsing."""
    empty_file = tmp_path / "empty.yaml"
    empty_file.write_text("", encoding="utf-8")

    root_file = tmp_path / "project.yaml"
    root_file.write_text(
        """
schema: IFC4-Minimal
project:
  id: PRJ-EMPTY
  name: "Empty Included File Test"
spatial_structure:
  storeys:
    - id: L1
      name: "L1"
      elevation: 0.0
      height: 3.0
grids:
  axes_x: { "1": 0.0 }
  axes_y: { "A": 0.0 }
materials: []
includes:
  - "empty.yaml"
""",
        encoding="utf-8",
    )

    manifest = load_manifest(root_file)
    assert isinstance(manifest, ProjectManifest)
    assert len(manifest.elements) == 0
