"""
IFC Quantity Take-Off (QTO) Extractor & Comparator for debim.
Extracts volumetric, surface area, and length quantities from Original IFC files
and benchmarks them against debim's declarative YAML QTO engine and Re-compiled IFCs.
"""

from collections import defaultdict
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

import ifcopenshell
import ifcopenshell.util.element
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from debim.schema import load_manifest
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto

console = Console()


def extract_ifc_element_quantities(elem) -> Dict[str, Optional[float]]:
    """
    Extract volume, area, and length from an IFC element via
    IfcElementQuantity (Qto_*) or property sets (e.g. PSet_Revit_Dimensions).
    """
    ps = ifcopenshell.util.element.get_psets(elem)
    vol = None
    area = None
    length = None

    for pset_name, props in ps.items():
        if not isinstance(props, dict):
            continue
        p_lower = {k.lower(): v for k, v in props.items()}
        for k, v in p_lower.items():
            if isinstance(v, (int, float)):
                val = float(v)
                # Volume detection (handle mm3 if unusually huge)
                if ("volume" in k or k == "netvolume" or k == "grossvolume") and vol is None:
                    vol = val / 1e9 if val > 1e6 else val
                # Area detection
                elif ("area" in k or k in ("netsidearea", "grosssidearea", "netarea", "grossarea")) and area is None:
                    area = val / 1e6 if val > 1e4 else val
                # Length detection
                elif ("length" in k or k == "netlength") and length is None:
                    length = val / 1000.0 if val > 100 else val

    return {
        "volume": vol,
        "area": area,
        "length": length,
    }


def extract_original_ifc_qto(ifc_path: Path) -> Dict[str, Dict[str, float]]:
    """
    Extract and aggregate quantities for all physical elements in an IFC file.
    Returns a dict keyed by element class (e.g. IfcWall, IfcSlab) with totals.
    """
    if not ifc_path.exists():
        raise FileNotFoundError(f"IFC file not found: {ifc_path}")

    ifc_file = ifcopenshell.open(str(ifc_path))
    elements = [
        e for e in ifc_file.by_type("IfcElement")
        if not e.is_a("IfcOpeningElement")
    ]

    totals_by_class: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"count": 0, "volume": 0.0, "area": 0.0, "length": 0.0}
    )

    for elem in elements:
        cls_name = elem.is_a()
        if cls_name == "IfcWallStandardCase":
            cls_name = "IfcWall"

        q = extract_ifc_element_quantities(elem)
        totals_by_class[cls_name]["count"] += 1
        if q["volume"] is not None:
            totals_by_class[cls_name]["volume"] += q["volume"]
        if q["area"] is not None:
            totals_by_class[cls_name]["area"] += q["area"]
        if q["length"] is not None:
            totals_by_class[cls_name]["length"] += q["length"]

    return dict(totals_by_class)


def extract_debim_yaml_qto(yaml_path: Path) -> Dict[str, Dict[str, float]]:
    """
    Calculate quantities from debim YAML project manifest.
    Returns totals grouped by element class.
    """
    manifest = load_manifest(yaml_path)
    resolved = resolve_manifest(manifest)
    project_qto = calculate_qto(resolved)

    totals_by_class: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"count": 0, "volume": 0.0, "area": 0.0, "rebar_kg": 0.0}
    )

    for eq in project_qto.elements:
        totals_by_class[eq.element_class]["count"] += 1
        totals_by_class[eq.element_class]["volume"] += eq.concrete_volume
        totals_by_class[eq.element_class]["area"] += eq.formwork_area
        totals_by_class[eq.element_class]["rebar_kg"] += eq.total_rebar_weight

    return dict(totals_by_class)


def compare_qto(
    ifc_path: Path,
    yaml_path: Path,
    recompiled_ifc: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Compare original IFC quantities vs debim YAML QTO calculations.
    """
    orig_qto = extract_original_ifc_qto(ifc_path)
    debim_qto = extract_debim_yaml_qto(yaml_path)

    console.print(
        Panel(
            f"[bold cyan]Original IFC Model:[/bold cyan] {ifc_path.name}\n"
            f"[bold cyan]debim Declarative YAML:[/bold cyan] {yaml_path.name}\n"
            f"[dim]Comparing element volumetric & dimensional quantities[/dim]",
            title="[bold green]debim QTO Cross-Validation & Benchmark[/bold green]",
        )
    )

    table = Table(
        title="Element Quantities Comparison (Original IFC vs debim YAML)",
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("Element Class", style="bold", width=18)
    table.add_column("Orig Count", justify="right", width=11)
    table.add_column("debim Count", justify="right", width=12)
    table.add_column("Orig Vol (m3)", justify="right", width=14)
    table.add_column("debim Vol (m3)", justify="right", width=15)
    table.add_column("Vol Variance", justify="right", width=13)
    table.add_column("Status", width=14)

    all_classes = sorted(set(orig_qto.keys()) | set(debim_qto.keys()))

    total_orig_vol = 0.0
    total_debim_vol = 0.0

    for cls in all_classes:
        orig = orig_qto.get(cls, {"count": 0, "volume": 0.0, "area": 0.0})
        deb = debim_qto.get(cls, {"count": 0, "volume": 0.0, "area": 0.0})

        o_vol = orig["volume"]
        d_vol = deb["volume"]
        total_orig_vol += o_vol
        total_debim_vol += d_vol

        if o_vol > 0.0:
            diff_pct = ((d_vol - o_vol) / o_vol) * 100.0
            diff_str = f"{diff_pct:+.1f}%"
            if abs(diff_pct) <= 15.0:
                status = "[bold green]Close Match[/bold green]"
            elif abs(diff_pct) <= 30.0:
                status = "[yellow]Acceptable[/yellow]"
            else:
                status = "[red]Variance[/red]"
        elif d_vol > 0.0:
            diff_str = "N/A (New)"
            status = "[cyan]Derived[/cyan]"
        else:
            diff_str = "-"
            status = "[dim]No Vol Data[/dim]"

        table.add_row(
            cls,
            str(orig["count"]),
            str(deb["count"]),
            f"{o_vol:.2f}" if o_vol > 0 else "-",
            f"{d_vol:.2f}" if d_vol > 0 else "-",
            diff_str,
            status,
        )

    table.add_section()
    overall_diff = (
        ((total_debim_vol - total_orig_vol) / total_orig_vol * 100.0)
        if total_orig_vol > 0
        else 0.0
    )
    table.add_row(
        "[bold]TOTAL VOLUME[/bold]",
        f"[bold]{sum(o['count'] for o in orig_qto.values())}[/bold]",
        f"[bold]{sum(d['count'] for d in debim_qto.values())}[/bold]",
        f"[bold]{total_orig_vol:.2f} m3[/bold]",
        f"[bold]{total_debim_vol:.2f} m3[/bold]",
        f"[bold]{overall_diff:+.1f}%[/bold]",
        "[bold green]Audited[/bold green]",
    )

    console.print(table)
    return {
        "original_totals": orig_qto,
        "debim_totals": debim_qto,
        "total_original_volume": total_orig_vol,
        "total_debim_volume": total_debim_vol,
        "variance_percentage": overall_diff,
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        console.print("[red]Usage: python tools/compare_qto.py <original.ifc> <debim_project.yaml> [recompiled.ifc][/red]")
        sys.exit(1)

    ifc_p = Path(sys.argv[1])
    yaml_p = Path(sys.argv[2])
    recomp_p = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    compare_qto(ifc_p, yaml_p, recomp_p)
