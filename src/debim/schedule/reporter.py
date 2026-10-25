"""
Rich terminal reporting engine for 4D BIM schedules, payment milestones, and S-curve progress tracking.
"""

from typing import Tuple
from debim.cli import Panel, Table
from debim.schedule.schema import ScheduleResult


def get_scurve_variance(result: ScheduleResult) -> Tuple[float, str]:
    """
    Calculate S-Curve progress variance between Actual % and Planned Early %.

    Returns a tuple of (variance_float, variance_str_summary), e.g. (+3.5, "Ahead by +3.5%") or (-5.0, "Delayed by -5.0%").
    """
    sc = result.s_curve
    if not sc or not sc.planned_early_percent or not sc.actual_percent:
        return 0.0, "On Schedule (0.0%)"

    # Find the latest index where actual progress is evaluated or available
    # Look for last non-zero actual or last index
    idx = len(sc.actual_percent) - 1
    # Find last index with actual progress recorded, if any
    for i in range(len(sc.actual_percent) - 1, -1, -1):
        if sc.actual_percent[i] > 0.0 or i == 0:
            idx = i
            break

    planned_p = sc.planned_early_percent[idx] if idx < len(sc.planned_early_percent) else 0.0
    actual_p = sc.actual_percent[idx]

    variance = round(actual_p - planned_p, 2)

    if variance > 0.0:
        summary_str = f"Ahead by +{variance:.1f}%"
    elif variance < 0.0:
        summary_str = f"Delayed by {variance:.1f}%"
    else:
        summary_str = "On Schedule (0.0%)"

    return variance, summary_str


def render_schedule_table(result: ScheduleResult) -> Panel:
    """
    Renders a Rich terminal panel detailing activities, progress badges, costs, and critical path.
    """
    table = Table(
        title=f"4D BIM Construction Schedule ({result.project_id}) - Status: {result.status}",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Activity ID", style="bold yellow")
    table.add_column("Start Day", justify="right")
    table.add_column("Finish Day", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Crashed", justify="right")
    table.add_column("Added Cost", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Progress", justify="right")
    table.add_column("Critical Path", justify="center")

    for act_id, act in result.activities.items():
        # Status badge formatting
        if act.status == "COMPLETED" or act.progress_percent >= 100.0:
            status_badge = "[bold green]COMPLETED[/bold green]"
        elif act.status == "IN_PROGRESS" or act.progress_percent > 0.0:
            status_badge = "[bold yellow]IN_PROGRESS[/bold yellow]"
        else:
            status_badge = "[dim]NOT_STARTED[/dim]"

        # Critical path badge formatting
        if act.is_critical:
            cp_badge = "[bold red]⚡ CRITICAL[/bold red]"
        else:
            cp_badge = "[dim]Normal[/dim]"

        added_cost_str = f"{act.added_cost:,.2f}" if act.added_cost > 0 else "-"
        crashed_str = f"{act.crashed_days} d" if act.crashed_days > 0 else "-"

        table.add_row(
            act.id,
            f"Day {act.start_day}",
            f"Day {act.finish_day}",
            f"{act.duration} d",
            crashed_str,
            added_cost_str,
            status_badge,
            f"{act.progress_percent:.1f}%",
            cp_badge,
        )

    cp_chain = " ➔ ".join([f"[bold red]{cid}[/bold red]" for cid in result.critical_path]) or "[dim]None[/dim]"

    content = (
        f"{table}\n\n"
        f"[bold cyan]Project Schedule Summary:[/bold cyan]\n"
        f" • [bold]Total Duration:[/bold] {result.total_duration} days\n"
        f" • [bold]Direct Cost:[/bold] {result.total_direct_cost:,.2f} THB\n"
        f" • [bold]Indirect Overhead Cost:[/bold] {result.total_indirect_cost:,.2f} THB\n"
        f" • [bold green]Grand Total Cost:[/bold green] {result.total_cost:,.2f} THB\n"
        f" • [bold cyan]Overall Progress:[/bold cyan] {result.overall_progress_percent:.1f}%\n"
        f" • [bold red]Critical Path:[/bold red] {cp_chain}"
    )

    return Panel(
        content,
        title="[bold green]debim 4D Schedule Analysis[/bold green]",
        style="green",
    )


def render_milestone_table(result: ScheduleResult) -> Panel:
    """
    Renders a Rich terminal panel showing milestones, required activities, completion dates, and billing readiness status.
    """
    table = Table(
        title=f"Payment Milestones & Billing Readiness ({result.project_id})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Milestone ID", style="bold yellow")
    table.add_column("Name", style="white")
    table.add_column("Payment %", justify="right", style="cyan")
    table.add_column("Planned Day", justify="right")
    table.add_column("Actual Day", justify="right")
    table.add_column("Required Activities", style="dim")
    table.add_column("Billing Status", justify="center")

    total_payment_pct = 0.0
    ready_payment_pct = 0.0

    for ms in result.milestones:
        total_payment_pct += ms.payment_percent

        if ms.billing_status == "READY_FOR_BILLING":
            status_badge = "[bold green]READY_FOR_BILLING[/bold green]"
            ready_payment_pct += ms.payment_percent
        elif ms.billing_status == "PAID":
            status_badge = "[bold cyan]PAID[/bold cyan]"
            ready_payment_pct += ms.payment_percent
        else:
            status_badge = "[bold yellow]PENDING[/bold yellow]"

        planned_str = f"Day {ms.planned_completion_day}"
        actual_str = f"Day {ms.actual_completion_day}" if ms.actual_completion_day is not None else "-"
        req_acts_str = ", ".join(ms.required_activities) if ms.required_activities else "(none)"

        table.add_row(
            ms.id,
            ms.name,
            f"{ms.payment_percent:.1f}%",
            planned_str,
            actual_str,
            req_acts_str,
            status_badge,
        )

    content = (
        f"{table}\n\n"
        f"[bold cyan]Milestone Billing Summary:[/bold cyan]\n"
        f" • [bold]Total Milestones:[/bold] {len(result.milestones)}\n"
        f" • [bold green]Ready / Paid Payment Volume:[/bold green] {ready_payment_pct:.1f}% / {total_payment_pct:.1f}%"
    )

    return Panel(
        content,
        title="[bold green]debim Payment Milestones Report[/bold green]",
        style="green",
    )


def render_scurve_summary(result: ScheduleResult) -> Panel:
    """
    Renders a Rich terminal panel summarizing S-Curve progress, planned early/late curves, actual progress, and variance.
    """
    variance, var_str = get_scurve_variance(result)

    if variance > 0.0:
        var_badge = f"[bold green]{var_str}[/bold green]"
    elif variance < 0.0:
        var_badge = f"[bold red]{var_str}[/bold red]"
    else:
        var_badge = f"[bold yellow]{var_str}[/bold yellow]"

    sc = result.s_curve
    last_idx = len(sc.actual_percent) - 1 if sc and sc.actual_percent else 0
    date_label = sc.dates[last_idx] if sc and sc.dates and last_idx < len(sc.dates) else f"Day {last_idx}"
    pe_val = sc.planned_early_percent[last_idx] if sc and sc.planned_early_percent and last_idx < len(sc.planned_early_percent) else 0.0
    pl_val = sc.planned_late_percent[last_idx] if sc and sc.planned_late_percent and last_idx < len(sc.planned_late_percent) else 0.0
    act_val = sc.actual_percent[last_idx] if sc and sc.actual_percent and last_idx < len(sc.actual_percent) else 0.0

    content = (
        f"[bold cyan]S-Curve Progress Variance Analysis:[/bold cyan]\n"
        f" • [bold]As-Of Timepoint:[/bold] {date_label}\n"
        f" • [bold]Planned Early Progress:[/bold] {pe_val:.1f}%\n"
        f" • [bold]Planned Late Progress:[/bold] {pl_val:.1f}%\n"
        f" • [bold]Actual Progress Logged:[/bold] {act_val:.1f}%\n"
        f" • [bold]Progress Variance Status:[/bold] {var_badge}"
    )

    return Panel(
        content,
        title="[bold green]debim S-Curve Progress Summary[/bold green]",
        style="green",
    )
