"""
One-Shot Time-Cost Trade-Off (Project Crashing) MILP Solver and Critical Path Engine.
Uses scipy.optimize.milp to solve project crashing to global optimality.
"""

from typing import Dict, List, Set, Tuple
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from debim.schedule.schema import (
    ActivityScheduleResult,
    CrashingActivity,
    CrashingManifest,
    ScheduleResult,
)


def solve_schedule(manifest: CrashingManifest) -> ScheduleResult:
    """
    Solves time-cost trade-off (project crashing) using scipy.optimize.milp.

    Formulates a Mixed-Integer Linear Program (MILP) over decision variables:
      - S_i: start time of activity i (continuous >= 0)
      - c_i: crash days for activity i (integer, 0 <= c_i <= normal_duration - crash_duration)
      - T: total project duration (continuous >= 0)

    Objective:
      Minimize Direct Crash Costs + Indirect Overhead Costs
      = sum_i (u_i * c_i) + overhead_per_day * T

    Subject to:
      - S_i + (D_i - c_i) <= T  for all activities i
      - S_j >= S_i + (D_i - c_i)  for all i in predecessors(j)
      - Direct Cost + Indirect Cost <= max_budget  (if max_budget is specified)

    After solving MILP to global optimality, performs CPM forward/backward passes
    to extract exact Early Start, Early Finish, Late Start, Late Finish, Total Float,
    and Critical Path activities.
    """
    activities = manifest.activities
    n = len(activities)

    if n == 0:
        # Empty manifest edge case
        from debim.schedule.scurve import compute_s_curves, evaluate_milestones
        res = ScheduleResult(
            project_id=manifest.project_id,
            status="OPTIMAL",
            total_duration=0,
            total_direct_cost=0.0,
            total_indirect_cost=0.0,
            total_cost=0.0,
            overall_progress_percent=0.0,
            critical_path=[],
            activities={},
            milestones=[],
        )
        res.s_curve = compute_s_curves(manifest, res)
        res.milestones = evaluate_milestones(manifest, res)
        return res

    act_map: Dict[str, CrashingActivity] = {a.id: a for a in activities}
    act_idx: Dict[str, int] = {a.id: i for i, a in enumerate(activities)}

    # Calculate unit crash costs for each activity
    unit_crash_costs = np.zeros(n, dtype=float)
    max_crashes = np.zeros(n, dtype=float)
    normal_durations = np.zeros(n, dtype=float)
    normal_costs = np.zeros(n, dtype=float)

    for i, a in enumerate(activities):
        normal_durations[i] = float(a.normal_duration)
        normal_costs[i] = float(a.normal_cost)
        max_crash = a.normal_duration - a.crash_duration
        max_crashes[i] = float(max_crash)
        if max_crash > 0:
            unit_crash_costs[i] = (a.crash_cost - a.normal_cost) / float(max_crash)
        else:
            unit_crash_costs[i] = 0.0

    overhead = float(manifest.overhead_per_day)

    # Decision variables vector x = [S_0..S_{n-1}, c_0..c_{n-1}, T]
    # Total dimension = 2*n + 1
    dim = 2 * n + 1

    # Objective c_vec: minimize sum_i (unit_crash_costs[i] * c_i) + overhead * T
    c_vec = np.zeros(dim, dtype=float)
    for i in range(n):
        c_vec[n + i] = unit_crash_costs[i]
    c_vec[2 * n] = overhead

    # Integrality vector: 0 = continuous, 1 = integer
    # S_i: continuous (0), c_i: integer (1), T: continuous (0)
    integrality = np.zeros(dim, dtype=int)
    for i in range(n):
        integrality[n + i] = 1

    # Bounds
    lb = np.zeros(dim, dtype=float)
    ub = np.full(dim, np.inf, dtype=float)
    for i in range(n):
        ub[n + i] = max_crashes[i]

    bounds = Bounds(lb, ub)

    # Linear constraints:
    # 1. Project duration constraints: S_i + D_i - c_i <= T  =>  S_i - c_i - T <= -D_i
    # 2. Predecessor constraints: S_p + D_p - c_p <= S_j  =>  S_p - c_p - S_j <= -D_p
    # 3. Optional max_budget constraint: sum(unit_crash_costs[i] * c_i) + overhead * T <= max_budget - sum(normal_costs)

    rows: List[np.ndarray] = []
    rhs_lb: List[float] = []
    rhs_ub: List[float] = []

    # 1. Duration bounds
    for i, a in enumerate(activities):
        row = np.zeros(dim, dtype=float)
        row[i] = 1.0          # S_i
        row[n + i] = -1.0     # -c_i
        row[2 * n] = -1.0     # -T
        rows.append(row)
        rhs_lb.append(-np.inf)
        rhs_ub.append(-normal_durations[i])

    # 2. Predecessors
    for j, a in enumerate(activities):
        for p_id in a.predecessors:
            if p_id in act_idx:
                p_i = act_idx[p_id]
                row = np.zeros(dim, dtype=float)
                row[p_i] = 1.0        # S_p
                row[n + p_i] = -1.0   # -c_p
                row[j] = -1.0         # -S_j
                rows.append(row)
                rhs_lb.append(-np.inf)
                rhs_ub.append(-normal_durations[p_i])

    # 3. Max budget
    if manifest.max_budget is not None:
        total_normal_cost = sum(normal_costs)
        avail_budget = manifest.max_budget - total_normal_cost
        row = np.zeros(dim, dtype=float)
        for i in range(n):
            row[n + i] = unit_crash_costs[i]
        row[2 * n] = overhead
        rows.append(row)
        rhs_lb.append(-np.inf)
        rhs_ub.append(avail_budget)

    A = np.vstack(rows)
    constraints = LinearConstraint(A, rhs_lb, rhs_ub)

    res = milp(c=c_vec, integrality=integrality, bounds=bounds, constraints=constraints)

    if not res.success or res.x is None:
        # Fallback if infeasible (e.g., budget too small)
        status_str = "INFEASIBLE"
        crashed_days_arr = np.zeros(n, dtype=int)
    else:
        status_str = "OPTIMAL"
        crashed_days_arr = np.round(res.x[n : 2 * n]).astype(int)

    # Actual activity durations after crashing
    act_durations = {
        a.id: max(a.crash_duration, int(a.normal_duration - crashed_days_arr[i]))
        for i, a in enumerate(activities)
    }

    # CPM Passes for exact Early/Late timing and Critical Path identification
    # Build predecessor and successor graphs
    preds_graph: Dict[str, List[str]] = {a.id: [p for p in a.predecessors if p in act_map] for a in activities}
    succs_graph: Dict[str, List[str]] = {a.id: [] for a in activities}
    for a in activities:
        for p in preds_graph[a.id]:
            succs_graph[p].append(a.id)

    # Forward pass -> Early Start (ES), Early Finish (EF)
    es: Dict[str, int] = {}
    ef: Dict[str, int] = {}

    # Topological sort (or iteration until convergence)
    changed = True
    for a in activities:
        es[a.id] = 0
        ef[a.id] = act_durations[a.id]

    while changed:
        changed = False
        for a in activities:
            p_list = preds_graph[a.id]
            if p_list:
                max_p_ef = max(ef[p] for p in p_list)
                if max_p_ef != es[a.id]:
                    es[a.id] = max_p_ef
                    ef[a.id] = max_p_ef + act_durations[a.id]
                    changed = True

    total_duration = max(ef.values()) if ef else 0

    # Backward pass -> Late Finish (LF), Late Start (LS)
    ls: Dict[str, int] = {}
    lf: Dict[str, int] = {}

    for a in activities:
        lf[a.id] = total_duration
        ls[a.id] = total_duration - act_durations[a.id]

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

    # Compute Total Float and Critical Path
    critical_path: List[str] = []
    activity_results: Dict[str, ActivityScheduleResult] = {}
    total_direct_cost = 0.0

    for i, a in enumerate(activities):
        c_days = int(crashed_days_arr[i])
        add_cost = round(c_days * unit_crash_costs[i], 2)
        total_direct_cost += a.normal_cost + add_cost

        total_float = ls[a.id] - es[a.id]
        is_crit = (total_float == 0)
        if is_crit:
            critical_path.append(a.id)

        activity_results[a.id] = ActivityScheduleResult(
            id=a.id,
            start_day=es[a.id],
            finish_day=ef[a.id],
            duration=act_durations[a.id],
            crashed_days=c_days,
            added_cost=add_cost,
            is_critical=is_crit,
            progress_percent=a.progress_percent,
            status=a.status,
        )

    total_indirect_cost = round(total_duration * manifest.overhead_per_day, 2)
    total_direct_cost = round(total_direct_cost, 2)
    total_cost = round(total_direct_cost + total_indirect_cost, 2)

    # Compute overall progress percent across activities weighted by cost_weight
    total_weight = sum(a.cost_weight or a.normal_cost for a in activities)
    if total_weight > 0:
        overall_progress = sum(
            a.progress_percent * (a.cost_weight or a.normal_cost) for a in activities
        ) / total_weight
    else:
        overall_progress = sum(a.progress_percent for a in activities) / float(n)

    result = ScheduleResult(
        project_id=manifest.project_id,
        status=status_str,
        total_duration=total_duration,
        total_direct_cost=total_direct_cost,
        total_indirect_cost=total_indirect_cost,
        total_cost=total_cost,
        overall_progress_percent=round(overall_progress, 2),
        critical_path=critical_path,
        activities=activity_results,
        milestones=[],
    )

    # Import and call scurve module functions
    from debim.schedule.scurve import compute_s_curves, evaluate_milestones
    result.s_curve = compute_s_curves(manifest, result)
    result.milestones = evaluate_milestones(manifest, result)

    return result
