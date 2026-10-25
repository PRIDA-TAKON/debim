"""
Schedule package for 4D BIM scheduling, Time-Cost Trade-off (Project Crashing),
Payment Milestones, and S-Curve Progress Tracking.
"""

from debim.schedule.builder import extract_activities_from_manifest
from debim.schedule.scurve import compute_s_curves, evaluate_milestones
from debim.schedule.solver import solve_schedule
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
    load_schedule_json,
    load_schedule_yaml,
)
from debim.schedule.reporter import (
    get_scurve_variance,
    render_milestone_table,
    render_schedule_table,
    render_scurve_summary,
)

__all__ = [
    "ActivityScheduleResult",
    "CrashingActivity",
    "CrashingManifest",
    "Milestone",
    "MilestoneResult",
    "ProgressLogEntry",
    "SCurveData",
    "ScheduleResult",
    "compute_s_curves",
    "dump_schedule_json",
    "evaluate_milestones",
    "extract_activities_from_manifest",
    "get_scurve_variance",
    "load_schedule_json",
    "load_schedule_yaml",
    "render_milestone_table",
    "render_schedule_table",
    "render_scurve_summary",
    "solve_schedule",
]
