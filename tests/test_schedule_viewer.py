"""
Unit tests for Standalone Interactive HTML Schedule & 4D Progress Viewer generator
and CLI subcommand 'debim schedule view'.
"""

from pathlib import Path
import pytest

from debim.cli import main, app
from debim.schedule import (
    CrashingActivity,
    CrashingManifest,
    Milestone,
    ScheduleResult,
    generate_schedule_html,
    solve_schedule,
)
from debim.schema import load_manifest


@pytest.fixture
def sample_schedule_result() -> ScheduleResult:
    manifest = CrashingManifest(
        project_id="PROJ-TEST-VIEWER",
        overhead_per_day=500.0,
        milestones=[
            Milestone(
                id="MS-01",
                name="Substructure",
                payment_percent=30.0,
                required_activities=["ACT-01"],
            ),
            Milestone(
                id="MS-02",
                name="Superstructure",
                payment_percent=70.0,
                required_activities=["ACT-02"],
            ),
        ],
        activities=[
            CrashingActivity(
                id="ACT-01",
                name="Earthwork & Footings",
                element_ids=["F1", "F2"],
                normal_duration=5,
                crash_duration=3,
                normal_cost=10000.0,
                crash_cost=14000.0,
            ),
            CrashingActivity(
                id="ACT-02",
                name="Concrete Columns & Beams",
                element_ids=["C1", "B1"],
                predecessors=["ACT-01"],
                normal_duration=10,
                crash_duration=7,
                normal_cost=25000.0,
                crash_cost=32000.0,
            ),
        ],
    )
    return solve_schedule(manifest)


@pytest.fixture
def sample_model_path() -> Path:
    p = Path("house.debim")
    if not p.exists():
        p = Path("examples/farnsworth_house/project.debim")
    return p


def test_generate_schedule_html_without_model(sample_schedule_result):
    html = generate_schedule_html(sample_schedule_result)
    assert isinstance(html, str)
    assert "<!DOCTYPE html>" in html
    assert "debim 4D Schedule & Progress Viewer" in html
    assert "PROJ-TEST-VIEWER" in html
    assert "time-slider" in html
    assert "scurve-svg" in html
    assert "gantt-table" in html
    assert "milestones-container" in html
    assert "bim3d-container" in html


def test_generate_schedule_html_with_model(sample_schedule_result, sample_model_path):
    manifest_obj = load_manifest(sample_model_path)
    html = generate_schedule_html(sample_schedule_result, manifest_obj=manifest_obj)
    assert isinstance(html, str)
    assert "<!DOCTYPE html>" in html
    assert "PROJ-TEST-VIEWER" in html
    assert "time-slider" in html


def test_cli_schedule_view(sample_schedule_result, sample_model_path, tmp_path, capsys):
    json_path = tmp_path / "schedule.json"
    html_path = tmp_path / "schedule.html"

    # Save schedule json
    from debim.schedule import dump_schedule_json
    dump_schedule_json(sample_schedule_result, json_path)

    # Run CLI: debim schedule view schedule.json --model house.debim -o schedule.html
    main(["schedule", "view", str(json_path), "--model", str(sample_model_path), "-o", str(html_path)])

    captured = capsys.readouterr()
    assert "4D Schedule HTML Viewer Generation Complete!" in captured.out

    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "PROJ-TEST-VIEWER" in content
    assert "time-slider" in content
