"""
Unit and CLI integration tests for 4D BIM schedule reporting and CLI subcommands:
  - debim schedule init
  - debim schedule solve
  - debim schedule report
"""

import json
from pathlib import Path
import pytest
import yaml

from debim.cli import main, app
from debim.schedule.schema import (
    ActivityScheduleResult,
    CrashingActivity,
    CrashingManifest,
    Milestone,
    MilestoneResult,
    ProgressLogEntry,
    SCurveData,
    ScheduleResult,
    load_schedule_json,
    load_schedule_yaml,
)
from debim.schedule.reporter import (
    get_scurve_variance,
    render_milestone_table,
    render_schedule_table,
    render_scurve_summary,
)


@pytest.fixture
def sample_manifest_path() -> Path:
    """Path to valid sample project manifest fixture."""
    p = Path("tests/fixtures/townhouse/project.yaml")
    if not p.exists():
        p = Path("examples/farnsworth_house/project.debim")
    return p


@pytest.fixture
def sample_schedule_result() -> ScheduleResult:
    """Fixture providing a mock ScheduleResult with activities, milestones, and S-Curve data."""
    return ScheduleResult(
        project_id="PROJ-SCHED-TEST",
        status="OPTIMAL",
        total_duration=25,
        total_direct_cost=150000.0,
        total_indirect_cost=50000.0,
        total_cost=200000.0,
        overall_progress_percent=60.0,
        critical_path=["ACT_SUBSTRUCTURE", "ACT_COL_GROUND", "ACT_STRUCT_GROUND"],
        activities={
            "ACT_SUBSTRUCTURE": ActivityScheduleResult(
                id="ACT_SUBSTRUCTURE",
                start_day=0,
                finish_day=7,
                duration=7,
                crashed_days=2,
                added_cost=10000.0,
                is_critical=True,
                progress_percent=100.0,
                status="COMPLETED",
            ),
            "ACT_COL_GROUND": ActivityScheduleResult(
                id="ACT_COL_GROUND",
                start_day=7,
                finish_day=14,
                duration=7,
                crashed_days=0,
                added_cost=0.0,
                is_critical=True,
                progress_percent=80.0,
                status="IN_PROGRESS",
            ),
            "ACT_STRUCT_GROUND": ActivityScheduleResult(
                id="ACT_STRUCT_GROUND",
                start_day=14,
                finish_day=25,
                duration=11,
                crashed_days=0,
                added_cost=0.0,
                is_critical=True,
                progress_percent=0.0,
                status="NOT_STARTED",
            ),
        },
        milestones=[
            MilestoneResult(
                id="MS-01",
                name="Milestone 1: Substructure",
                payment_percent=30.0,
                planned_completion_day=7,
                actual_completion_day=7,
                is_completed=True,
                billing_status="READY_FOR_BILLING",
                required_activities=["ACT_SUBSTRUCTURE"],
            ),
            MilestoneResult(
                id="MS-02",
                name="Milestone 2: Superstructure",
                payment_percent=70.0,
                planned_completion_day=25,
                actual_completion_day=None,
                is_completed=False,
                billing_status="PENDING",
                required_activities=["ACT_COL_GROUND", "ACT_STRUCT_GROUND"],
            ),
        ],
        s_curve=SCurveData(
            dates=["Day 0", "Day 7", "Day 14", "Day 25"],
            planned_early_percent=[0.0, 30.0, 60.0, 100.0],
            planned_late_percent=[0.0, 20.0, 45.0, 100.0],
            actual_percent=[0.0, 33.5, 65.0, 0.0],
        ),
    )


# --- Unit Tests for Reporter ---

def test_reporter_render_schedule_table(sample_schedule_result):
    panel = render_schedule_table(sample_schedule_result)
    output = str(panel)

    assert "4D BIM Construction Schedule (PROJ-SCHED-TEST)" in output
    assert "ACT_SUBSTRUCTURE" in output
    assert "ACT_COL_GROUND" in output
    assert "COMPLETED" in output
    assert "IN_PROGRESS" in output
    assert "CRITICAL" in output
    assert "200,000.00 THB" in output
    assert "Total Duration:" in output


def test_reporter_render_milestone_table(sample_schedule_result):
    panel = render_milestone_table(sample_schedule_result)
    output = str(panel)

    assert "Payment Milestones & Billing Readiness" in output
    assert "MS-01" in output
    assert "MS-02" in output
    assert "READY_FOR_BILLING" in output
    assert "PENDING" in output
    assert "30.0%" in output
    assert "ACT_SUBSTRUCTURE" in output


def test_reporter_get_scurve_variance(sample_schedule_result):
    variance, var_str = get_scurve_variance(sample_schedule_result)

    assert variance == 5.0
    assert var_str == "Ahead by +5.0%"

    # Test delayed variance
    sample_schedule_result.s_curve.actual_percent = [0.0, 25.0, 0.0, 0.0]
    variance_del, var_str_del = get_scurve_variance(sample_schedule_result)
    assert variance_del == -5.0
    assert var_str_del == "Delayed by -5.0%"


def test_reporter_render_scurve_summary(sample_schedule_result):
    panel = render_scurve_summary(sample_schedule_result)
    output = str(panel)

    assert "S-Curve Progress Variance Analysis" in output
    assert "Ahead by +5.0%" in output
    assert "Planned Early Progress:" in output


# --- CLI Integration Tests ---

def test_cli_schedule_init(sample_manifest_path, tmp_path, capsys):
    out_yaml = tmp_path / "test_schedule.yaml"

    main(["schedule", "init", str(sample_manifest_path), "-o", str(out_yaml)])

    captured = capsys.readouterr()
    assert "4D Schedule Manifest Scaffolding Complete!" in captured.out
    assert out_yaml.exists()

    # Load and verify schedule.yaml
    manifest = load_schedule_yaml(out_yaml)
    assert len(manifest.activities) > 0
    assert len(manifest.milestones) > 0
    assert manifest.overhead_per_day > 0


def test_cli_schedule_solve(sample_manifest_path, tmp_path, capsys):
    out_yaml = tmp_path / "schedule.yaml"
    out_json = tmp_path / "schedule.json"

    # Step 1: init
    main(["schedule", "init", str(sample_manifest_path), "-o", str(out_yaml)])

    # Step 2: solve
    main(["schedule", "solve", str(out_yaml), "-o", str(out_json)])

    captured = capsys.readouterr()
    assert "CPM Schedule Solution & Optimization Complete!" in captured.out
    assert out_json.exists()

    # Load and verify schedule.json
    res = load_schedule_json(out_json)
    assert res.status == "OPTIMAL"
    assert res.total_duration > 0
    assert res.total_cost > 0.0
    assert len(res.activities) > 0


def test_cli_schedule_report(sample_schedule_result, tmp_path, capsys):
    json_path = tmp_path / "schedule.json"
    from debim.schedule import dump_schedule_json
    dump_schedule_json(sample_schedule_result, json_path)

    main(["schedule", "report", str(json_path)])

    captured = capsys.readouterr()
    assert "4D Schedule Analysis" in captured.out
    assert "Payment Milestones Report" in captured.out
    assert "S-Curve Progress Summary" in captured.out
    assert "PROJ-SCHED-TEST" in captured.out
    assert "READY_FOR_BILLING" in captured.out


def test_cli_schedule_missing_files(tmp_path, capsys):
    non_existent = tmp_path / "does_not_exist.yaml"

    with pytest.raises(SystemExit) as exc_info:
        main(["schedule", "init", str(non_existent)])
    assert exc_info.value.code == 1

    with pytest.raises(SystemExit) as exc_info:
        main(["schedule", "solve", str(non_existent)])
    assert exc_info.value.code == 1

    with pytest.raises(SystemExit) as exc_info:
        main(["schedule", "report", str(non_existent)])
    assert exc_info.value.code == 1
