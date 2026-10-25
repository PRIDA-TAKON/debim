"""
Unit tests for One-Shot MILP Solver, S-Curve Progress Engine, and Payment Milestone Evaluator.
"""

import pytest
from debim.schedule.schema import (
    CrashingActivity,
    CrashingManifest,
    Milestone,
    ProgressLogEntry,
)
from debim.schedule.solver import solve_schedule


def test_milp_solver_no_crashing_needed():
    """When overhead_per_day is 0, solver shouldn't crash activities unless max_budget requires or not needed."""
    manifest = CrashingManifest(
        project_id="PROJ-001",
        overhead_per_day=0.0,
        activities=[
            CrashingActivity(
                id="ACT_A",
                name="Activity A",
                normal_duration=10,
                crash_duration=6,
                normal_cost=10000.0,
                crash_cost=18000.0,
            ),
            CrashingActivity(
                id="ACT_B",
                name="Activity B",
                predecessors=["ACT_A"],
                normal_duration=8,
                crash_duration=5,
                normal_cost=15000.0,
                crash_cost=24000.0,
            ),
        ],
    )

    result = solve_schedule(manifest)

    assert result.status == "OPTIMAL"
    assert result.total_duration == 18
    assert result.activities["ACT_A"].crashed_days == 0
    assert result.activities["ACT_B"].crashed_days == 0
    assert result.activities["ACT_A"].start_day == 0
    assert result.activities["ACT_A"].finish_day == 10
    assert result.activities["ACT_B"].start_day == 10
    assert result.activities["ACT_B"].finish_day == 18
    assert result.total_direct_cost == 25000.0
    assert result.total_indirect_cost == 0.0
    assert result.total_cost == 25000.0
    assert result.critical_path == ["ACT_A", "ACT_B"]


def test_milp_solver_high_overhead_triggers_crashing():
    """High daily overhead should incentivize crashing the critical path to minimize total cost."""
    manifest = CrashingManifest(
        project_id="PROJ-002",
        overhead_per_day=5000.0,  # High overhead (5000 THB/day) vs crash cost of 2000 THB/day
        activities=[
            CrashingActivity(
                id="ACT_A",
                name="Foundation",
                normal_duration=10,
                crash_duration=6,
                normal_cost=10000.0,
                crash_cost=18000.0,  # 8000 THB / 4 days = 2000 THB/day unit crash cost
            ),
            CrashingActivity(
                id="ACT_B",
                name="Superstructure",
                predecessors=["ACT_A"],
                normal_duration=10,
                crash_duration=7,
                normal_cost=20000.0,
                crash_cost=29000.0,  # 9000 THB / 3 days = 3000 THB/day unit crash cost
            ),
        ],
    )

    result = solve_schedule(manifest)

    assert result.status == "OPTIMAL"
    # Should crash both activities fully: A from 10 to 6 days, B from 10 to 7 days -> total duration 13
    assert result.activities["ACT_A"].crashed_days == 4
    assert result.activities["ACT_B"].crashed_days == 3
    assert result.total_duration == 13
    assert result.critical_path == ["ACT_A", "ACT_B"]


def test_critical_path_and_float_detection():
    """Test parallel activities where non-critical activity has float."""
    manifest = CrashingManifest(
        project_id="PROJ-FLOAT",
        overhead_per_day=0.0,
        activities=[
            CrashingActivity(
                id="ACT_START",
                name="Site Prep",
                normal_duration=5,
                crash_duration=5,
                normal_cost=5000.0,
            ),
            CrashingActivity(
                id="ACT_LONG",
                name="Long Path",
                predecessors=["ACT_START"],
                normal_duration=20,
                crash_duration=20,
                normal_cost=20000.0,
            ),
            CrashingActivity(
                id="ACT_SHORT",
                name="Short Path",
                predecessors=["ACT_START"],
                normal_duration=8,
                crash_duration=8,
                normal_cost=8000.0,
            ),
            CrashingActivity(
                id="ACT_END",
                name="Handover",
                predecessors=["ACT_LONG", "ACT_SHORT"],
                normal_duration=2,
                crash_duration=2,
                normal_cost=2000.0,
            ),
        ],
    )

    result = solve_schedule(manifest)

    assert result.status == "OPTIMAL"
    assert result.total_duration == 27  # 5 + 20 + 2
    assert "ACT_LONG" in result.critical_path
    assert "ACT_START" in result.critical_path
    assert "ACT_END" in result.critical_path
    assert "ACT_SHORT" not in result.critical_path
    assert not result.activities["ACT_SHORT"].is_critical


def test_s_curve_aggregation_and_actual_progress():
    """Test S-Curve generation for planned early, planned late, and actual progress."""
    manifest = CrashingManifest(
        project_id="PROJ-SCURVE",
        as_of_date="2026-10-01",
        overhead_per_day=1000.0,
        activities=[
            CrashingActivity(
                id="ACT_1",
                name="Excavation",
                normal_duration=5,
                crash_duration=5,
                normal_cost=50000.0,
                cost_weight=50000.0,
                status="COMPLETED",
                progress_percent=100.0,
                progress_log=[
                    ProgressLogEntry(date="2026-10-01", percent=0.0),
                    ProgressLogEntry(date="2026-10-03", percent=50.0),
                    ProgressLogEntry(date="2026-10-06", percent=100.0),
                ],
            ),
            CrashingActivity(
                id="ACT_2",
                name="Structure",
                predecessors=["ACT_1"],
                normal_duration=5,
                crash_duration=5,
                normal_cost=50000.0,
                cost_weight=50000.0,
                status="IN_PROGRESS",
                progress_percent=40.0,
                progress_log=[
                    ProgressLogEntry(date="2026-10-06", percent=0.0),
                    ProgressLogEntry(date="2026-10-08", percent=40.0),
                ],
            ),
        ],
    )

    result = solve_schedule(manifest)

    assert result.s_curve is not None
    s_curve = result.s_curve
    assert len(s_curve.dates) == 11  # total duration 10 (0..10 days -> 11 points)
    assert s_curve.dates[0] == "2026-10-01"
    assert s_curve.dates[10] == "2026-10-11"

    # Start: 0%, End: 100%
    assert s_curve.planned_early_percent[0] == 0.0
    assert s_curve.planned_early_percent[-1] == 100.0
    assert s_curve.planned_late_percent[0] == 0.0
    assert s_curve.planned_late_percent[-1] == 100.0

    # Check progress at Day 5 (2026-10-06): ACT_1 complete (50% total cost weight), ACT_2 0% -> 50%
    assert s_curve.actual_percent[5] == 50.0
    # Day 7 (2026-10-08): ACT_1 100% (50%), ACT_2 40% (20%) -> 70%
    assert s_curve.actual_percent[7] == 70.0


def test_milestone_evaluation_and_billing_status():
    """Test milestone planned completion day and READY_FOR_BILLING status update."""
    manifest = CrashingManifest(
        project_id="PROJ-MILESTONES",
        overhead_per_day=500.0,
        milestones=[
            Milestone(
                id="MS-01",
                name="Phase 1: Substructure",
                payment_percent=30.0,
                required_activities=["ACT_1"],
            ),
            Milestone(
                id="MS-02",
                name="Phase 2: Completion",
                payment_percent=70.0,
                required_activities=["ACT_1", "ACT_2"],
            ),
        ],
        activities=[
            CrashingActivity(
                id="ACT_1",
                name="Foundation",
                normal_duration=6,
                crash_duration=6,
                normal_cost=30000.0,
                status="COMPLETED",
                progress_percent=100.0,
            ),
            CrashingActivity(
                id="ACT_2",
                name="Superstructure",
                predecessors=["ACT_1"],
                normal_duration=8,
                crash_duration=8,
                normal_cost=70000.0,
                status="IN_PROGRESS",
                progress_percent=50.0,
            ),
        ],
    )

    result = solve_schedule(manifest)

    assert len(result.milestones) == 2
    ms1 = result.milestones[0]
    ms2 = result.milestones[1]

    # MS-01: ACT_1 finished at day 6, 100% completed -> READY_FOR_BILLING
    assert ms1.id == "MS-01"
    assert ms1.planned_completion_day == 6
    assert ms1.is_completed is True
    assert ms1.billing_status == "READY_FOR_BILLING"

    # MS-02: ACT_2 finishes at day 14, 50% completed -> PENDING
    assert ms2.id == "MS-02"
    assert ms2.planned_completion_day == 14
    assert ms2.is_completed is False
    assert ms2.billing_status == "PENDING"
