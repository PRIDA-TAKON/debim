"""
Tests for debim.schedule data models, YAML parsing, and JSON serialization.
"""

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from debim.schedule.schema import (
    ActivityScheduleResult,
    CrashingActivity,
    CrashingManifest,
    Milestone,
    MilestoneResult,
    ProgressLogEntry,
    SCurveData,
    ScheduleResult,
    dump_schedule_json,
    load_schedule_yaml,
)


def test_progress_log_entry_validation():
    entry = ProgressLogEntry(date="2026-10-15", percent=45.5, notes="Footing poured")
    assert entry.date == "2026-10-15"
    assert entry.percent == 45.5
    assert entry.notes == "Footing poured"

    with pytest.raises(ValidationError):
        ProgressLogEntry(date="2026-10-15", percent=105.0)

    with pytest.raises(ValidationError):
        ProgressLogEntry(date="2026-10-15", percent=-5.0)


def test_milestone_validation():
    ms = Milestone(
        id="MS-01",
        name="งวดที่ 1: งานฐานรากและเสาเข็มแล้วเสร็จ",
        payment_percent=15.0,
        payment_amount=150000.0,
        required_activities=["ACT_FOOTING_1", "ACT_PILES_1"],
    )
    assert ms.id == "MS-01"
    assert ms.payment_percent == 15.0
    assert ms.required_activities == ["ACT_FOOTING_1", "ACT_PILES_1"]

    with pytest.raises(ValidationError):
        Milestone(id="MS-02", name="Invalid Payment", payment_percent=120.0)


def test_crashing_activity_bounds_and_defaults():
    # Valid crashing activity
    act = CrashingActivity(
        id="ACT_COL_L1",
        name="Column L1 Concrete",
        element_ids=["COL-L1-01", "COL-L1-02"],
        predecessors=["ACT_FOOTING_1"],
        normal_duration=10,
        crash_duration=6,
        normal_cost=50000.0,
        crash_cost=75000.0,
    )
    assert act.id == "ACT_COL_L1"
    assert act.crash_duration == 6
    assert act.normal_duration == 10
    # Default cost_weight equals normal_cost
    assert act.cost_weight == 50000.0
    assert act.status == "NOT_STARTED"
    assert act.progress_percent == 0.0

    # Explicit cost_weight provided
    act_weighted = CrashingActivity(
        id="ACT_COL_L2",
        name="Column L2",
        normal_duration=8,
        crash_duration=5,
        normal_cost=40000.0,
        cost_weight=30000.0,
    )
    assert act_weighted.cost_weight == 30000.0

    # Invalid: crash_duration > normal_duration
    with pytest.raises(ValidationError) as exc_info:
        CrashingActivity(
            id="ACT_BAD",
            name="Bad Activity",
            normal_duration=5,
            crash_duration=8,
        )
    assert "crash_duration" in str(exc_info.value)

    # Invalid: negative duration
    with pytest.raises(ValidationError):
        CrashingActivity(
            id="ACT_NEG",
            name="Negative Duration",
            normal_duration=-2,
            crash_duration=1,
        )

    # Invalid: progress_percent > 100
    with pytest.raises(ValidationError):
        CrashingActivity(
            id="ACT_OVER",
            name="Over Progress",
            normal_duration=5,
            crash_duration=3,
            progress_percent=150.0,
        )


def test_crashing_manifest_with_progress_log():
    manifest_dict = {
        "project_id": "PROJECT-4D-001",
        "as_of_date": "2026-11-01",
        "overhead_per_day": 2000.0,
        "max_budget": 500000.0,
        "milestones": [
            {
                "id": "MS-01",
                "name": "Substructure Complete",
                "payment_percent": 20.0,
                "required_activities": ["ACT_SUB_01"],
            }
        ],
        "activities": [
            {
                "id": "ACT_SUB_01",
                "name": "Substructure Concrete",
                "element_ids": ["F1", "F2", "C1"],
                "predecessors": [],
                "normal_duration": 14,
                "crash_duration": 10,
                "normal_cost": 100000.0,
                "crash_cost": 140000.0,
                "status": "IN_PROGRESS",
                "progress_percent": 60.0,
                "actual_start": "2026-10-15",
                "progress_log": [
                    {"date": "2026-10-15", "percent": 0.0, "notes": "Commenced excavation"},
                    {"date": "2026-10-22", "percent": 30.0, "notes": "Rebar completed"},
                    {"date": "2026-10-29", "percent": 60.0, "notes": "Concrete poured"},
                ],
            }
        ],
    }

    manifest = CrashingManifest.model_validate(manifest_dict)
    assert manifest.project_id == "PROJECT-4D-001"
    assert manifest.as_of_date == "2026-11-01"
    assert manifest.overhead_per_day == 2000.0
    assert len(manifest.milestones) == 1
    assert manifest.milestones[0].id == "MS-01"
    assert len(manifest.activities) == 1

    act = manifest.activities[0]
    assert act.status == "IN_PROGRESS"
    assert act.progress_percent == 60.0
    assert len(act.progress_log) == 3
    assert act.progress_log[1].percent == 30.0


def test_load_schedule_yaml(tmp_path: Path):
    yaml_content = """
project_id: PROJ-HOUSE-01
as_of_date: "2026-10-01"
overhead_per_day: 1500.0
milestones:
  - id: MS-01
    name: "งวดที่ 1: งานโครงสร้างชั้น 1"
    payment_percent: 25.0
    required_activities: [ACT_F1, ACT_C1]
activities:
  - id: ACT_F1
    name: "งานฐานราก"
    normal_duration: 7
    crash_duration: 5
    normal_cost: 30000.0
    crash_cost: 42000.0
  - id: ACT_C1
    name: "งานเสาชั้น 1"
    predecessors: [ACT_F1]
    normal_duration: 10
    crash_duration: 7
    normal_cost: 50000.0
    crash_cost: 70000.0
"""
    schedule_file = tmp_path / "schedule.yaml"
    schedule_file.write_text(yaml_content, encoding="utf-8")

    manifest = load_schedule_yaml(schedule_file)
    assert manifest.project_id == "PROJ-HOUSE-01"
    assert manifest.as_of_date == "2026-10-01"
    assert manifest.overhead_per_day == 1500.0
    assert len(manifest.milestones) == 1
    assert manifest.milestones[0].name == "งวดที่ 1: งานโครงสร้างชั้น 1"
    assert len(manifest.activities) == 2
    assert manifest.activities[1].predecessors == ["ACT_F1"]


def test_schedule_result_and_json_roundtrip(tmp_path: Path):
    act_res = ActivityScheduleResult(
        id="ACT_F1",
        start_day=0,
        finish_day=5,
        duration=5,
        crashed_days=2,
        added_cost=12000.0,
        is_critical=True,
        progress_percent=100.0,
        status="COMPLETED",
    )

    ms_res = MilestoneResult(
        id="MS-01",
        name="Foundations Completed",
        payment_percent=25.0,
        planned_completion_day=5,
        actual_completion_day=5,
        is_completed=True,
        billing_status="READY_FOR_BILLING",
    )

    s_curve = SCurveData(
        dates=["2026-10-01", "2026-10-05", "2026-10-10"],
        planned_early_percent=[0.0, 50.0, 100.0],
        planned_late_percent=[0.0, 30.0, 100.0],
        actual_percent=[0.0, 50.0, 100.0],
    )

    result = ScheduleResult(
        project_id="PROJ-HOUSE-01",
        status="OPTIMAL",
        total_duration=12,
        total_direct_cost=80000.0,
        total_indirect_cost=18000.0,
        total_cost=98000.0,
        overall_progress_percent=100.0,
        critical_path=["ACT_F1", "ACT_C1"],
        activities={"ACT_F1": act_res},
        milestones=[ms_res],
        s_curve=s_curve,
    )

    json_file = tmp_path / "schedule_result.json"
    written_path = dump_schedule_json(result, json_file)
    assert written_path == json_file
    assert json_file.exists()

    # Read back and parse into ScheduleResult
    json_str = json_file.read_text(encoding="utf-8")
    loaded_data = json.loads(json_str)
    deserialized = ScheduleResult.model_validate(loaded_data)

    assert deserialized.project_id == "PROJ-HOUSE-01"
    assert deserialized.status == "OPTIMAL"
    assert deserialized.total_duration == 12
    assert deserialized.total_cost == 98000.0
    assert deserialized.critical_path == ["ACT_F1", "ACT_C1"]
    assert "ACT_F1" in deserialized.activities
    assert deserialized.activities["ACT_F1"].crashed_days == 2
    assert deserialized.milestones[0].billing_status == "READY_FOR_BILLING"
    assert deserialized.s_curve.planned_early_percent == [0.0, 50.0, 100.0]
