"""
Unit tests for Complete 5-Layer Audit Matrix, Auto-Fix Remediations, and Flight Recorder Telemetry.
"""

import json
import pytest
from pathlib import Path
from debim.schema import (
    ProjectManifest,
    ProjectInfo,
    SpatialStructure,
    Storey,
    Grids,
    Material,
    IfcColumn,
    ColumnPlacement,
    BoxProfile,
    IfcBeam,
    BeamPlacement,
    IfcWall,
    WallPlacement,
    IfcSlab,
    SlabPlacement,
    IfcPipeSegment,
    PipePlacement,
    IfcDuctSegment,
    IfcSpace,
    SpacePlacement,
    SpaceDesignSpec,
)
from debim.audit import AuditMatrixEvaluator, run_5_layer_audit
from debim.flight_recorder import AuditFlightRecorder, record_audit_telemetry
import sys
from pathlib import Path
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from cli_runner import CliRunner
from debim.cli import app


@pytest.fixture
def complex_manifest():
    return ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="PROJ-AUDIT", name="Audit Matrix Full Test House"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="FL1", name="Floor 1", elevation=0.0, height=3.0),
                Storey(id="FL2", name="Floor 2", elevation=3.0, height=3.0),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 5.0, "3": 10.0},
            axes_y={"A": 0.0, "B": 6.0, "C": 12.0},
        ),
        materials=[
            Material(id="CONCRETE", name="Structural Concrete", category="concrete", unit_cost_ref="MAT-CONC"),
            Material(id="PVC", name="PVC Pipe", category="pvc", unit_cost_ref="MAT-PVC"),
        ],
        elements=[
            IfcColumn(
                tag="C1",
                material="CONCRETE",
                profile=BoxProfile(width=0.3, depth=0.3),
                placement=ColumnPlacement(grid=("1", "A"), base_storey="FL1", top_storey="FL2"),
            ),
            IfcBeam(
                tag="B1",
                material="CONCRETE",
                profile=BoxProfile(width=0.2, depth=0.4),
                placement=BeamPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="FL1"),
            ),
            IfcPipeSegment(
                tag="PIPE-DRAIN-1",
                system_type="SOIL",
                material="PVC",
                nominal_diameter=0.10,
                placement=PipePlacement(
                    storey="FL1",
                    from_grid=("1", "A"),
                    to_grid=("2", "A"),
                    slope=0.005,  # Too flat (< 0.01) -> Layer 4 violation
                ),
            ),
        ],
    )


def test_5_layer_audit_execution(complex_manifest):
    report = run_5_layer_audit(complex_manifest, apply_fixes=False)
    assert report.project_id == "PROJ-AUDIT"
    assert len(report.layers) == 5

    # Layer 4 should detect flat pipe slope 0.005
    l4_res = report.layers[4]
    assert l4_res.passed is False
    v4 = [item for item in l4_res.items if item.rule_code == "LAYER4_SANITARY_DRAIN_SLOPE"][0]
    assert v4.remediation.fix_action == "INCREASE_PIPE_SLOPE"


def test_auto_remediation_fixes(complex_manifest):
    # Add wet space with bad drop_elevation
    complex_manifest.elements.append(
        IfcSpace(
            tag="SPACE-BATH",
            name="Bath WC",
            drop_elevation=0.0,  # Layer 2 violation
            placement=SpacePlacement(storey="FL1", boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")]),
        )
    )

    evaluator = AuditMatrixEvaluator(complex_manifest)
    report_before = evaluator.run_full_audit(apply_fixes=True)

    assert report_before.remediations_applied > 0

    # Verify Pipe slope was auto-fixed to 0.01 and Space drop to -0.10
    pipe_elem = next(e for e in complex_manifest.elements if getattr(e, "tag", None) == "PIPE-DRAIN-1")
    space_elem = next(e for e in complex_manifest.elements if getattr(e, "tag", None) == "SPACE-BATH")

    assert pipe_elem.placement.slope == 0.01
    assert space_elem.drop_elevation == -0.10


def test_flight_recorder_telemetry_export(complex_manifest, tmp_path):
    report = run_5_layer_audit(complex_manifest)
    json_path, md_path = record_audit_telemetry(report, log_dir=tmp_path)

    assert json_path.exists()
    assert md_path.exists()

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["project_id"] == "PROJ-AUDIT"
        assert len(data["layers"]) == 5

    md_text = md_path.read_text(encoding="utf-8")
    assert "# debim 5-Layer Audit Matrix Flight Recorder Report" in md_text
    assert "PROJ-AUDIT" in md_text


def test_cli_debim_audit(tmp_path):
    runner = CliRunner()
    res = runner.invoke(app, ["audit", "-m", "house.debim", "--log-dir", str(tmp_path)])
    assert res.exit_code == 0
    assert "debim 5-Layer Architectural & Engineering Audit Matrix" in res.output
    assert (tmp_path / "audit_log.json").exists()
    assert (tmp_path / "audit_report.md").exists()
