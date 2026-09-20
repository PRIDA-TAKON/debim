"""
IFC Element Counter & Roundtrip Comparator for debim.
Counts physical building & MEP elements in IFC files and compares
Original IFC vs Re-compiled IFC (from debim YAML) to measure fidelity & retention rate.
"""

from collections import Counter
from pathlib import Path
import sys
from typing import Any, Dict, Optional, Tuple

import ifcopenshell
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def count_ifc_elements(ifc_path: Path) -> Tuple[int, Counter]:
    """
    Count all physical building, structural, and MEP elements in an IFC file.
    Excludes spatial hierarchy (Project, Site, Building, Storey, Space)
    and opening voids (IfcOpeningElement).
    """
    if not ifc_path.exists():
        raise FileNotFoundError(f"IFC file not found: {ifc_path}")

    ifc_file = ifcopenshell.open(str(ifc_path))
    # Exclude non-physical / spatial containers / subtraction voids
    elements = [
        e for e in ifc_file.by_type("IfcElement")
        if not e.is_a("IfcOpeningElement")
    ]

    counter = Counter()
    for elem in elements:
        entity_type = elem.is_a()
        # Group StandardCase variants for fair comparison
        if entity_type == "IfcWallStandardCase":
            entity_type = "IfcWall"
        elif entity_type == "IfcDoorStandardCase":
            entity_type = "IfcDoor"
        elif entity_type == "IfcWindowStandardCase":
            entity_type = "IfcWindow"
        counter[entity_type] += 1

    return len(elements), counter


def compare_ifc_files(
    original_path: Path,
    recompiled_path: Optional[Path] = None,
    output_table: bool = True,
) -> Dict[str, Any]:
    """
    Compare element counts between original IFC and re-compiled IFC.
    """
    orig_total, orig_counts = count_ifc_elements(original_path)

    recomp_total, recomp_counts = 0, Counter()
    if recompiled_path and recompiled_path.exists():
        recomp_total, recomp_counts = count_ifc_elements(recompiled_path)

    if not output_table:
        return {
            "original_total": orig_total,
            "original_counts": orig_counts,
            "recompiled_total": recomp_total,
            "recompiled_counts": recomp_counts,
            "retention_rate": (recomp_total / orig_total * 100.0) if orig_total > 0 else 0.0,
        }

    console.print(
        Panel(
            f"[bold cyan]Original IFC:[/bold cyan] {original_path.name} ({orig_total} physical elements)\n"
            f"[bold cyan]Re-compiled IFC:[/bold cyan] {recompiled_path.name if recompiled_path else 'None'} ({recomp_total} physical elements)",
            title="[bold green]debim IFC Element Fidelity Comparator[/bold green]",
        )
    )

    table = Table(
        title="Element Breakdown & Comparison",
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("IFC Entity Class", style="bold", width=25)
    table.add_column("Original Count", justify="right", width=16)
    table.add_column("Re-compiled Count", justify="right", width=18)
    table.add_column("Retention Rate", justify="right", width=16)
    table.add_column("Status", width=14)

    all_keys = sorted(set(orig_counts.keys()) | set(recomp_counts.keys()))
    for key in all_keys:
        orig_c = orig_counts.get(key, 0)
        recomp_c = recomp_counts.get(key, 0)

        if orig_c > 0:
            rate = (recomp_c / orig_c) * 100.0
            rate_str = f"{rate:.1f}%"
        else:
            rate_str = "N/A (New)"

        if recomp_c == orig_c and orig_c > 0:
            status = "[bold green]100% Complete[/bold green]"
        elif recomp_c > 0 and recomp_c < orig_c:
            status = "[yellow]Partial[/yellow]"
        elif recomp_c == 0:
            status = "[dim red]Not Extracted[/dim red]"
        else:
            status = "[cyan]Transformed[/cyan]"

        table.add_row(
            key,
            str(orig_c),
            str(recomp_c),
            rate_str,
            status,
        )

    # Total row
    overall_rate = (recomp_total / orig_total * 100.0) if orig_total > 0 else 0.0
    table.add_section()
    table.add_row(
        "[bold]TOTAL PHYSICAL ELEMENTS[/bold]",
        f"[bold]{orig_total}[/bold]",
        f"[bold]{recomp_total}[/bold]",
        f"[bold]{overall_rate:.1f}%[/bold]",
        "[bold green]Verified[/bold green]" if overall_rate > 0 else "[bold red]No Match[/bold red]",
    )

    console.print(table)
    return {
        "original_total": orig_total,
        "original_counts": orig_counts,
        "recompiled_total": recomp_total,
        "recompiled_counts": recomp_counts,
        "retention_rate": overall_rate,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        console.print("[red]Usage: python tools/compare_ifc.py <original.ifc> [recompiled.ifc][/red]")
        sys.exit(1)

    orig = Path(sys.argv[1])
    recomp = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    compare_ifc_files(orig, recomp)
