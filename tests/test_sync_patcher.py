"""
tests/test_sync_patcher.py

Unit tests for as-built change detection and surgical AST patcher module.
Verifies discrepancy detection, comment and structure preservation, and CLI subcommands.
"""

import json
from pathlib import Path
import pytest
import yaml

from debim.cli import app
from debim.resolver import resolve_manifest
from debim.schema import (
    load_manifest,
    ProjectManifest,
    ProjectInfo,
    Units,
    SpatialStructure,
    Storey,
    Grids,
    IfcColumn,
    ColumnPlacement,
    Material,
    BoxProfile,
)
from debim.sync.detector import (
    ChangeProposal,
    DeviationResult,
    ElementDeviation,
    detect_asbuilt_discrepancies,
)
from debim.sync.patcher import apply_asbuilt_patch


def test_detect_asbuilt_discrepancies():
    """Test detect_asbuilt_discrepancies threshold filtering and proposal creation."""
    col1 = IfcColumn(
        tag="C1",
        profile=BoxProfile(shape="BOX", width=0.3, depth=0.3),
        material="CONCRETE",
        placement=ColumnPlacement(grid=("1", "A"), offset_x=0.0, offset_y=0.0, storey="STOREY-1"),
    )
    col2 = IfcColumn(
        tag="C2",
        profile=BoxProfile(shape="BOX", width=0.3, depth=0.3),
        material="CONCRETE",
        placement=ColumnPlacement(grid=("2", "A"), offset_x=0.0, offset_y=0.0, storey="STOREY-1"),
    )

    m = ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="PRJ-1", name="Test", units=Units()),
        spatial_structure=SpatialStructure(storeys=[Storey(id="STOREY-1", name="FL1", elevation=0.0, height=3.0)]),
        grids=Grids(axes_x={"1": 0.0, "2": 4.0}, axes_y={"A": 0.0}),
        materials=[Material(id="CONCRETE", name="Reinforced Concrete", category="CONCRETE", unit_cost_ref="MAT-CONCRETE")],
        elements=[col1, col2],
    )
    resolved = resolve_manifest(m)

    # 1. Deviation below threshold (20mm shift) -> no proposals
    dev_small = DeviationResult(
        deviations=[ElementDeviation(tag="C1", delta_x=0.02, delta_y=0.0)]
    )
    props = detect_asbuilt_discrepancies(resolved.elements, dev_small, threshold_mm=30.0)
    assert len(props) == 0

    # 2. Deviation above threshold (50mm shift) -> proposal generated
    dev_large = DeviationResult(
        deviations=[
            ElementDeviation(tag="C1", delta_x=0.05, delta_y=-0.04),
            ElementDeviation(tag="C2", delta_x=0.01, delta_y=0.0), # 10mm below threshold
        ]
    )
    props = detect_asbuilt_discrepancies(resolved.elements, dev_large, threshold_mm=30.0)
    assert len(props) == 2
    tags_fields = [(p.tag, p.field_name, p.proposed_value) for p in props]
    assert ("C1", "offset_x", 0.05) in tags_fields
    assert ("C1", "offset_y", -0.04) in tags_fields


def test_apply_asbuilt_patch_comment_preservation(tmp_path: Path):
    """Test surgical AST patcher preserving all comments, indentation, and structure."""
    sample_debim = """# Project Header Comment
project:
  id: PRJ-ASBUILT-01
  name: Asbuilt Test Building # Important Project
  units:
    length: METER

spatial_structure:
  storeys:
    - id: STOREY-1
      name: Storey 1
      elevation: 0.0
      height: 3.0

materials:
  - id: CONCRETE
    name: Reinforced Concrete
    category: CONCRETE
    unit_cost_ref: MAT-CONCRETE

# Grid Axes Section
grids:
  axes_x:
    '1': 0.0
    '2': 4.0
  axes_y:
    A: 0.0

elements:
  # Structural Column 1
  - tag: C1
    class: IfcColumn
    profile:
      shape: BOX
      width: 0.3
      depth: 0.3
    material: CONCRETE
    # Local grid offsets
    placement:
      grid: ['1', 'A']
      offset_x: 0.0 # Initial zero offset
      offset_y: 0.0

  # Structural Column 2
  - tag: C2
    class: IfcColumn
    profile:
      shape: BOX
      width: 0.3
      depth: 0.3
    material: CONCRETE
    placement:
      grid: ['2', 'A']
"""
    debim_file = tmp_path / "project.debim"
    debim_file.write_text(sample_debim, encoding="utf-8")

    proposals = [
        ChangeProposal(
            tag="C1",
            element_class="IfcColumn",
            field_name="offset_x",
            current_value=0.0,
            proposed_value=0.045,
            deviation_mm=45.0,
        ),
        ChangeProposal(
            tag="C1",
            element_class="IfcColumn",
            field_name="offset_y",
            current_value=0.0,
            proposed_value=-0.035,
            deviation_mm=35.0,
        ),
    ]

    out_file = tmp_path / "updated.debim"
    updated_str = apply_asbuilt_patch(debim_file, proposals, output_path=out_file)

    # Acceptance Criteria Verification:
    # 1. All existing comments must be preserved
    assert "# Project Header Comment" in updated_str
    assert "# Important Project" in updated_str
    assert "# Grid Axes Section" in updated_str
    assert "# Structural Column 1" in updated_str
    assert "# Local grid offsets" in updated_str
    assert "# Structural Column 2" in updated_str

    # 2. Values updated correctly
    assert "offset_x: 0.045" in updated_str
    assert "offset_y: -0.035" in updated_str

    # 3. Must parse back as valid debim manifest
    updated_manifest = load_manifest(out_file)
    assert len(updated_manifest.elements) == 2
    c1 = [e for e in updated_manifest.elements if e.tag == "C1"][0]
    assert c1.placement.offset_x == 0.045
    assert c1.placement.offset_y == -0.035


def test_cli_sync_propose_and_apply(tmp_path: Path):
    """Test full CLI workflow: debim sync propose followed by debim sync apply."""
    debim_content = """project:
  id: PRJ-CLI-SYNC
  name: CLI Sync Test

spatial_structure:
  storeys:
    - id: STOREY-1
      name: Storey 1
      elevation: 0.0
      height: 3.0

materials:
  - id: CONCRETE
    name: Reinforced Concrete
    category: CONCRETE
    unit_cost_ref: MAT-CONCRETE

grids:
  axes_x:
    '1': 0.0
    '2': 5.0
  axes_y:
    A: 0.0

elements:
  - tag: C1
    class: IfcColumn
    profile:
      shape: BOX
      width: 0.3
      depth: 0.3
    material: CONCRETE
    placement:
      grid: ['1', 'A']
      offset_x: 0.0
      offset_y: 0.0
"""
    model_file = tmp_path / "model.debim"
    model_file.write_text(debim_content, encoding="utf-8")

    scan_data = {
        "deviations": [
            {
                "tag": "C1",
                "delta_x": 0.05,
                "delta_y": -0.04,
            }
        ]
    }
    scan_file = tmp_path / "scan.json"
    scan_file.write_text(json.dumps(scan_data), encoding="utf-8")

    patch_file = tmp_path / "patch.json"

    # 1. Run debim sync propose
    app(["sync", "propose", "-m", str(model_file), "-s", str(scan_file), "-o", str(patch_file), "-t", "30.0"])

    assert patch_file.exists()
    with open(patch_file, "r", encoding="utf-8") as f:
        proposals_raw = json.load(f)
    assert len(proposals_raw) == 2

    # 2. Run debim sync apply
    updated_model_file = tmp_path / "updated_model.debim"
    app(["sync", "apply", "-m", str(model_file), "-p", str(patch_file), "-o", str(updated_model_file)])

    assert updated_model_file.exists()
    updated_str = updated_model_file.read_text(encoding="utf-8")
    assert "offset_x: 0.05" in updated_str
    assert "offset_y: -0.04" in updated_str

    # Ensure valid manifest
    updated_m = load_manifest(updated_model_file)
    c1 = updated_m.elements[0]
    assert c1.placement.offset_x == 0.05
    assert c1.placement.offset_y == -0.04
