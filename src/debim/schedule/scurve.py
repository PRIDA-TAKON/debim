"""
S-Curve Progress Engine and Payment Milestone Evaluator for 4D BIM Scheduling.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np

from debim.schedule.schema import (
    ActivityScheduleResult,
    CrashingActivity,
    CrashingManifest,
    Milestone,
    MilestoneResult,
    SCurveData,
    ScheduleResult,
)


def _parse_date_to_day(date_str: str, start_date_str: Optional[str]) -> Optional[int]:
    """Helper to convert date strings (e.g. '2026-10-15' or 'Day 5' or '5') to integer day index."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    if date_str.isdigit():
        return int(date_str)
    if date_str.lower().startswith("day "):
        try:
            return int(date_str.split()[1])
        except (IndexError, ValueError):
            pass
    if start_date_str:
        try:
            d_fmt = "%Y-%m-%d"
            d1 = datetime.strptime(date_str[:10], d_fmt)
            d0 = datetime.strptime(start_date_str[:10], d_fmt)
            return (d1 - d0).days
        except Exception:
            pass
    return None


def compute_s_curves(
    manifest: CrashingManifest, schedule_res: ScheduleResult
) -> SCurveData:
    """
    Computes Planned Early, Planned Late, and Actual S-Curve cumulative percentage series
    over time points t = 0..T (where T is total project duration).

    Weighting is based on activity cost_weight (or normal_cost).
    """
    total_dur = schedule_res.total_duration
    activities = manifest.activities
    n_act = len(activities)

    if total_dur <= 0 or n_act == 0:
        return SCurveData(
            dates=["Day 0"],
            planned_early_percent=[100.0],
            planned_late_percent=[100.0],
            actual_percent=[100.0],
        )

    # Activity weight dictionary
    weights: Dict[str, float] = {}
    for a in activities:
        w = a.cost_weight if a.cost_weight is not None else a.normal_cost
        weights[a.id] = float(w)

    total_weight = sum(weights.values())
    if total_weight <= 0:
        total_weight = float(n_act)
        for a in activities:
            weights[a.id] = 1.0

    # Build CPM graphs for Late Start / Late Finish calculation
    act_map = {a.id: a for a in activities}
    preds_graph = {a.id: [p for p in a.predecessors if p in act_map] for a in activities}
    succs_graph: Dict[str, List[str]] = {a.id: [] for a in activities}
    for a in activities:
        for p in preds_graph[a.id]:
            succs_graph[p].append(a.id)

    act_durations = {}
    es = {}
    ef = {}
    for a in activities:
        res_a = schedule_res.activities.get(a.id)
        if res_a:
            es[a.id] = res_a.start_day
            ef[a.id] = res_a.finish_day
            act_durations[a.id] = res_a.duration
        else:
            es[a.id] = 0
            ef[a.id] = a.normal_duration
            act_durations[a.id] = a.normal_duration

    # Backward pass for Late Start (LS) and Late Finish (LF)
    lf: Dict[str, int] = {a.id: total_dur for a in activities}
    ls: Dict[str, int] = {a.id: total_dur - act_durations[a.id] for a in activities}

    changed = True
    while changed:
        changed = False
        for a in activities:
            s_list = succs_graph[a.id]
            if s_list:
                min_s_ls = min(ls[s] for s in s_list)
                if min_s_ls != lf[a.id]:
                    lf[a.id] = min_s_ls
                    ls[a.id] = min_s_ls - act_durations[a.id]
                    changed = True

    # Date labels
    start_date_str = manifest.as_of_date
    dates_list: List[str] = []
    has_calendar = False
    start_dt = None
    if start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str[:10], "%Y-%m-%d")
            has_calendar = True
        except Exception:
            has_calendar = False

    for d in range(total_dur + 1):
        if has_calendar and start_dt:
            curr_dt = start_dt + timedelta(days=d)
            dates_list.append(curr_dt.strftime("%Y-%m-%d"))
        else:
            dates_list.append(f"Day {d}")

    planned_early_pct: List[float] = []
    planned_late_pct: List[float] = []
    actual_pct: List[float] = []

    # Map progress logs per activity
    # Build a lookup for each activity's progress at day d
    # If progress_log exists, map log entries to day indices
    act_progress_timeline: Dict[str, Dict[int, float]] = {a.id: {} for a in activities}

    for a in activities:
        if a.progress_log:
            for entry in a.progress_log:
                day_idx = _parse_date_to_day(entry.date, start_date_str)
                if day_idx is not None:
                    act_progress_timeline[a.id][day_idx] = entry.percent

    for d in range(total_dur + 1):
        # 1. Planned Early
        early_cum_weight = 0.0
        for a in activities:
            w = weights[a.id]
            st = es[a.id]
            fn = ef[a.id]
            dur = act_durations[a.id]
            if d <= st:
                pass
            elif d >= fn:
                early_cum_weight += w
            else:
                if dur > 0:
                    early_cum_weight += w * ((d - st) / float(dur))
                else:
                    early_cum_weight += w

        pe_val = round(min(100.0, max(0.0, (early_cum_weight / total_weight) * 100.0)), 2)
        planned_early_pct.append(pe_val)

        # 2. Planned Late
        late_cum_weight = 0.0
        for a in activities:
            w = weights[a.id]
            lst = ls[a.id]
            lfn = lf[a.id]
            dur = act_durations[a.id]
            if d <= lst:
                pass
            elif d >= lfn:
                late_cum_weight += w
            else:
                if dur > 0:
                    late_cum_weight += w * ((d - lst) / float(dur))
                else:
                    late_cum_weight += w

        pl_val = round(min(100.0, max(0.0, (late_cum_weight / total_weight) * 100.0)), 2)
        planned_late_pct.append(pl_val)

        # 3. Actual Progress
        actual_cum_weight = 0.0
        for a in activities:
            w = weights[a.id]
            timeline = act_progress_timeline[a.id]
            if timeline:
                # Find latest logged progress at or before day d
                past_days = [p_day for p_day in timeline.keys() if p_day <= d]
                if past_days:
                    latest_day = max(past_days)
                    act_pct = timeline[latest_day]
                else:
                    act_pct = 0.0
            else:
                # Fallback to activity.progress_percent and status
                st = es[a.id]
                fn = ef[a.id]
                dur = act_durations[a.id]
                target_pct = a.progress_percent
                if a.status == "COMPLETED":
                    target_pct = 100.0

                if d <= st:
                    act_pct = 0.0
                elif target_pct > 0:
                    # If currently logged progress exists
                    if d >= fn:
                        act_pct = target_pct
                    else:
                        if dur > 0:
                            act_pct = target_pct * min(1.0, (d - st) / float(dur))
                        else:
                            act_pct = target_pct
                else:
                    act_pct = 0.0

            actual_cum_weight += w * (act_pct / 100.0)

        act_val = round(min(100.0, max(0.0, (actual_cum_weight / total_weight) * 100.0)), 2)
        actual_pct.append(act_val)

    return SCurveData(
        dates=dates_list,
        planned_early_percent=planned_early_pct,
        planned_late_percent=planned_late_pct,
        actual_percent=actual_pct,
    )


def evaluate_milestones(
    manifest: CrashingManifest, schedule_res: ScheduleResult
) -> List[MilestoneResult]:
    """
    Evaluates payment milestone planned/actual completion days and billing status.

    - Planned completion day = max(finish_day of required_activities).
    - Checks current completion status across required activities.
    - Sets billing_status = READY_FOR_BILLING when all required activities are 100% completed.
    """
    results: List[MilestoneResult] = []
    act_map = schedule_res.activities

    for ms in manifest.milestones:
        req_ids = ms.required_activities
        payment_pct = ms.payment_percent if ms.payment_percent is not None else 0.0

        if not req_ids:
            planned_day = 0
            is_comp = True
        else:
            finish_days = [
                act_map[aid].finish_day for aid in req_ids if aid in act_map
            ]
            planned_day = max(finish_days) if finish_days else 0

            # Check if all required activities are 100% completed
            completed_flags = []
            for aid in req_ids:
                if aid in act_map:
                    act_res = act_map[aid]
                    is_done = (
                        act_res.progress_percent >= 100.0 or act_res.status == "COMPLETED"
                    )
                    completed_flags.append(is_done)
                else:
                    completed_flags.append(False)

            is_comp = all(completed_flags) if completed_flags else False

        actual_day = planned_day if is_comp else None
        billing_status = "READY_FOR_BILLING" if is_comp else "PENDING"

        results.append(
            MilestoneResult(
                id=ms.id,
                name=ms.name,
                payment_percent=payment_pct,
                planned_completion_day=planned_day,
                actual_completion_day=actual_day,
                is_completed=is_comp,
                billing_status=billing_status,
            )
        )

    return results
