#!/usr/bin/env python3
"""
create_schedule_step1_issue.py

Creates the initial Step 1 GitHub Issue for Jules AI to begin implementing
the 4D BIM Scheduling, Milestone Allocation, S-Curve & One-Shot MILP Engine.
"""

import subprocess
import sys

REPO = "PRIDA-TAKON/debim"
TITLE = "feat(schedule): Step 1 - Pydantic Schema for schedule.yaml (Milestones, S-Curve ProgressLog, Crashing) & schedule.json"
LABELS = "jules,enhancement,schedule"

BODY = """### Overview
Implement Pydantic v2 data models and serialization helpers for 4D BIM construction scheduling, Time-Cost Trade-off (Project Crashing), Payment Milestones allocation, and Periodic (Daily/Weekly) Progress Logging for S-Curve analysis.

### Key Deliverables
1. `src/debim/schedule/__init__.py`
2. `src/debim/schedule/schema.py`:
   - `ProgressLogEntry`:
     - `date: str` (e.g. '2026-10-15')
     - `percent: float` (0.0 to 100.0)
     - `notes: str | None = None`
   - `Milestone`:
     - `id: str` (e.g. 'MS-01')
     - `name: str` (e.g. 'งวดที่ 1: งานฐานรากและเสาเข็มแล้วเสร็จ')
     - `payment_percent: float | None = None` (e.g. 15.0)
     - `payment_amount: float | None = None`
     - `required_activities: list[str] = []` (list of activity IDs that must be finished to bill this milestone)
   - `CrashingActivity`:
     - Plan / Crashing fields:
       - `id: str` (e.g. 'ACT_COL_L1')
       - `name: str`
       - `element_ids: list[str] = []` (mapped to debim 3D element IDs)
       - `predecessors: list[str] = []`
       - `normal_duration: int`
       - `crash_duration: int`
       - `normal_cost: float = 0.0`
       - `crash_cost: float = 0.0`
       - `cost_weight: float | None = None` (weight for S-Curve calculation, defaults to normal_cost)
     - As-Built / Actual Progress fields:
       - `status: Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETED"] = "NOT_STARTED"`
       - `progress_percent: float = 0.0` (0.0 to 100.0)
       - `actual_start: str | None = None`
       - `actual_finish: str | None = None`
       - `progress_log: list[ProgressLogEntry] = []` (daily or weekly progress entries)
       - `notes: str | None = None`
     - Validator: `crash_duration <= normal_duration` and non-negative values.
   - `CrashingManifest`:
     - `project_id: str`
     - `as_of_date: str | None = None` (Data Date for progress cutoff)
     - `overhead_per_day: float = 0.0`
     - `max_budget: float | None = None`
     - `milestones: list[Milestone] = []`
     - `activities: list[CrashingActivity]`
   - `MilestoneResult`:
     - `id: str`
     - `name: str`
     - `payment_percent: float`
     - `planned_completion_day: int`
     - `actual_completion_day: int | None = None`
     - `is_completed: bool = False`
     - `billing_status: Literal["PENDING", "READY_FOR_BILLING", "PAID"] = "PENDING"`
   - `SCurveData`:
     - `dates: list[str] = []`
     - `planned_early_percent: list[float] = []`
     - `planned_late_percent: list[float] = []`
     - `actual_percent: list[float] = []`
   - `ActivityScheduleResult`:
     - `id: str`, `start_day: int`, `finish_day: int`, `duration: int`, `crashed_days: int`, `added_cost: float`, `is_critical: bool`, `progress_percent: float = 0.0`, `status: str = "NOT_STARTED"`
   - `ScheduleResult`:
     - `project_id: str`, `status: str`, `total_duration: int`, `total_direct_cost: float`, `total_indirect_cost: float`, `total_cost: float`, `overall_progress_percent: float = 0.0`, `critical_path: list[str]`, `activities: dict[str, ActivityScheduleResult]`, `milestones: list[MilestoneResult] = []`, `s_curve: SCurveData = Field(default_factory=SCurveData)`
   - Helper functions:
     - `load_schedule_yaml(path: Path | str) -> CrashingManifest`
     - `dump_schedule_json(result: ScheduleResult, path: Path | str) -> Path`
3. Tests (`tests/test_schedule_schema.py`):
   - Test YAML deserialization with milestones, periodic progress logs, and valid/invalid crash bounds.
   - Test JSON round-trip serialization of `ScheduleResult`.

### Acceptance Criteria
- Full test coverage for schema validation, milestones, and S-curve progress log data structures.
- `pytest tests/test_schedule_schema.py` passes 100%.
"""

def main():
    print(f"Creating Step 1 Issue on {REPO}...")
    cmd = [
        "gh", "issue", "create",
        "-R", REPO,
        "--title", TITLE,
        "--body", BODY,
        "--label", LABELS,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode == 0:
        url = res.stdout.strip()
        print(f"\n[+] Successfully created Step 1 issue:\n    {url}")
        print("\nNext: Start jules_watchdog to monitor Jules PRs and auto-trigger subsequent steps:")
        print("  python -u C:\\Users\\takon\\.gemini\\config\\skills\\jules_watchdog\\scripts\\watchdog_orchestrator.py `")
        print(f"    --repo \"{REPO}\" `")
        print("    --branch main `")
        print("    --interval 300 `")
        print("    --config tools\\roadmap_schedule_jules.json `")
        print("    --test-cmd \"pytest\"")
    else:
        print(f"[!] Failed to create issue:\n{res.stderr.strip()}")
        sys.exit(1)

if __name__ == "__main__":
    main()
