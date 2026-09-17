"""
CLI interface for debim / bim
"""

from pathlib import Path
from typing import Optional
import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from debim.compiler import compile_to_ifc
from debim.cost import estimate_cost, load_price_catalog
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import ProjectManifest, load_manifest
from debim.viewer import generate_viewer_html, serve_viewer

app = typer.Typer(
    name="debim",
    help="Minimal Declarative BIM (Building-as-Code) engine",
    add_completion=False,
)
console = Console()


@app.command()
def init(
    name: str = typer.Argument(..., help="Name of the new project directory"),
):
    """Create a new project scaffold with template project.yaml and prices.json"""
    project_dir = Path(name)
    if project_dir.exists():
        console.print(f"[bold red]Error:[/bold red] Directory '{name}' already exists.")
        raise typer.Exit(code=1)

    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "assets").mkdir(exist_ok=True)
    (project_dir / "tests").mkdir(exist_ok=True)
    console.print(
        f"[bold green]Success:[/bold green] Initialized new debim project in [cyan]{name}[/cyan]"
    )


@app.command()
def validate(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest"
    ),
):
    """Validate project.yaml schema, grid alignment, and element placement links"""
    if not manifest.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest '{manifest}' not found.")
        raise typer.Exit(code=1)
    console.print(f"[bold green]Validating:[/bold green] {manifest}")
    try:
        load_manifest(manifest)
        console.print("[bold green]Validation passed successfully.[/bold green]")
    except (ValidationError, ValueError, Exception) as e:
        console.print(f"[bold red]Validation Error:[/bold red]\n{e}")
        raise typer.Exit(code=1)


@app.command()
def test(
    test_dir: Path = typer.Option(
        Path("tests"), "--tests", "-t", help="Directory containing compliance tests"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Display verbose pytest output"
    ),
):
    """Run building law & compliance test suite via pytest and report clean, descriptive rule checks"""
    import subprocess
    import sys

    console.print(
        Panel(
            f"[bold cyan]Automated Building Compliance Engine & Pytest Checker[/bold cyan]\n"
            f"[dim]Running compliance rule suite in:[/dim] [yellow]{test_dir}[/yellow]",
            title="[bold green]debim Compliance Engine[/bold green]",
        )
    )

    cmd = [sys.executable, "-m", "pytest", str(test_dir), "-rA"]
    if verbose:
        cmd.append("-v")

    res = subprocess.run(cmd, capture_output=True, text=True)

    if res.stdout:
        console.print(res.stdout)
    if res.stderr:
        console.print(f"[dim]{res.stderr}[/dim]")

    if res.returncode == 0:
        console.print(
            Panel(
                "[bold green]ALL COMPLIANCE RULES PASSED ACCORDING TO BUILDING CODES![/bold green]",
                style="green",
            )
        )
    else:
        console.print(
            Panel(
                "[bold red]COMPLIANCE CHECKS FAILED! PLEASE REVIEW REGULATORY VIOLATIONS ABOVE.[/bold red]",
                style="red",
            )
        )

    raise typer.Exit(code=res.returncode)


@app.command(name="summary")
@app.command(name="info", hidden=True)
def summary(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest"
    ),
    prices: Path = typer.Option(
        Path("prices.json"), "--prices", "-p", help="Path to price catalog"
    ),
):
    """Print high-level project summary table (Site bounds/area, footprint, storey elevations, element counts, cost)"""
    if not manifest.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest '{manifest}' not found.")
        raise typer.Exit(code=1)

    try:
        manifest_obj = load_manifest(manifest)
        resolved = resolve_manifest(manifest_obj)
        project_qto = calculate_qto(resolved)

        proj = manifest_obj.project
        console.print(
            Panel(
                f"[bold cyan]Project Name:[/bold cyan] {proj.name}\n"
                f"[bold cyan]Project ID:[/bold cyan] {proj.id}\n"
                f"[bold cyan]Units:[/bold cyan] length={proj.units.length}, area={proj.units.area}, volume={proj.units.volume}",
                title="[bold green]Project Overview[/bold green]",
            )
        )

        # Site & Grids
        axes_x = list(manifest_obj.grids.axes_x.values())
        axes_y = list(manifest_obj.grids.axes_y.values())
        min_x, max_x = (min(axes_x), max(axes_x)) if axes_x else (0.0, 0.0)
        min_y, max_y = (min(axes_y), max(axes_y)) if axes_y else (0.0, 0.0)
        span_x = max_x - min_x
        span_y = max_y - min_y
        bounding_area = span_x * span_y

        site_table = Table(title="Site Bounds & Spatial Structure", show_header=True, header_style="bold cyan")
        site_table.add_column("Property", style="bold yellow")
        site_table.add_column("Value", style="white")

        site_table.add_row("X Range", f"{min_x:.2f} m to {max_x:.2f} m (Span: {span_x:.2f} m)")
        site_table.add_row("Y Range", f"{min_y:.2f} m to {max_y:.2f} m (Span: {span_y:.2f} m)")
        site_table.add_row("Bounding Area", f"{bounding_area:.2f} m2")

        storeys_str = ", ".join([f"{s.name} (+{s.elevation:.2f}m)" for s in manifest_obj.spatial_structure.storeys])
        site_table.add_row("Storeys", storeys_str)

        console.print(site_table)

        # Element Statistics Table
        class_counts = {}
        for elem in manifest_obj.elements:
            cls = elem.class_
            class_counts[cls] = class_counts.get(cls, 0) + 1

        # Also count doors & windows if present in walls
        door_count = len(resolved.doors)
        window_count = len(resolved.windows)
        if door_count > 0:
            class_counts["IfcDoor"] = door_count
        if window_count > 0:
            class_counts["IfcWindow"] = window_count

        elem_table = Table(title="Element Statistics Breakdown", show_header=True, header_style="bold cyan")
        elem_table.add_column("IFC Class", style="bold green")
        elem_table.add_column("Count", justify="right", style="bold yellow")

        for cls, count in sorted(class_counts.items()):
            elem_table.add_row(cls, str(count))

        console.print(elem_table)

        # QTO & Cost Snapshot
        cost_str = "N/A (prices.json not found)"
        if prices.exists():
            try:
                price_catalog = load_price_catalog(prices)
                estimate = estimate_cost(project_qto, price_catalog, manifest_obj)
                cost_str = f"{estimate.grand_total:,.2f} {estimate.currency}"
            except Exception:
                pass

        qto_summary = (
            f"[bold cyan]Total Concrete Volume:[/bold cyan] {project_qto.total_concrete_volume:.3f} m3\n"
            f"[bold cyan]Total Formwork Area:[/bold cyan] {project_qto.total_formwork_area:.3f} m2\n"
            f"[bold cyan]Total Rebar Weight:[/bold cyan] {project_qto.total_rebar_weight:.3f} kg\n"
            f"[bold green]Estimated Budget:[/bold green] {cost_str}"
        )
        console.print(Panel(qto_summary, title="[bold green]QTO & Cost Snapshot[/bold green]"))

    except Exception as e:
        console.print(f"[bold red]Summary Error:[/bold red]\n{e}")
        raise typer.Exit(code=1)


@app.command()
def qto(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest"
    ),
):
    """Calculate Quantitative Take-Off (concrete volume, formwork, rebar schedule)"""
    if not manifest.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest '{manifest}' not found.")
        raise typer.Exit(code=1)

    console.print(f"[bold blue]Calculating QTO for:[/bold blue] {manifest}")
    try:
        manifest_obj = load_manifest(manifest)
        project_qto = calculate_qto(manifest_obj)

        table = Table(
            title="Quantitative Take-Off (QTO) Summary",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Tag", style="bold yellow")
        table.add_column("Class", style="green")
        table.add_column("Material", style="magenta")
        table.add_column("Concrete Vol (m3)", justify="right")
        table.add_column("Formwork Area (m2)", justify="right")
        table.add_column("Rebar Weight (kg)", justify="right")

        for eqto in project_qto.elements:
            table.add_row(
                eqto.tag,
                eqto.element_class,
                eqto.material or "-",
                f"{eqto.concrete_volume:.3f}",
                f"{eqto.formwork_area:.3f}",
                f"{eqto.total_rebar_weight:.3f}",
            )

        console.print(table)

        summary_text = (
            f"[bold cyan]Total Concrete Volume:[/bold cyan] {project_qto.total_concrete_volume:.3f} m3\n"
            f"[bold cyan]Total Formwork Area:[/bold cyan] {project_qto.total_formwork_area:.3f} m2\n"
            f"[bold cyan]Total Rebar Weight:[/bold cyan] {project_qto.total_rebar_weight:.3f} kg"
        )
        console.print(Panel(summary_text, title="[bold green]QTO Totals[/bold green]"))

    except Exception as e:
        console.print(f"[bold red]QTO Error:[/bold red]\n{e}")
        raise typer.Exit(code=1)


@app.command()
def cost(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest"
    ),
    prices: Path = typer.Option(
        Path("prices.json"), "--prices", "-p", help="Path to price catalog"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Path to export BOQ CSV (e.g. dist/boq.csv)"
    ),
):
    """Calculate cost estimate by matching QTO with price catalog"""
    if not manifest.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest '{manifest}' not found.")
        raise typer.Exit(code=1)
    if not prices.exists():
        console.print(f"[bold red]Error:[/bold red] Price catalog '{prices}' not found.")
        raise typer.Exit(code=1)

    console.print(
        f"[bold blue]Calculating project cost for:[/bold blue] {manifest} [blue]using[/blue] {prices}"
    )
    try:
        manifest_obj = load_manifest(manifest)
        project_qto = calculate_qto(manifest_obj)
        price_catalog = load_price_catalog(prices)

        estimate = estimate_cost(project_qto, price_catalog, manifest_obj)

        table = Table(
            title=f"Cost Estimate Summary ({estimate.currency})",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Code", style="bold yellow")
        table.add_column("Description", style="white")
        table.add_column("Unit", justify="center")
        table.add_column("Quantity", justify="right")
        table.add_column("Unit Mat", justify="right")
        table.add_column("Unit Labor", justify="right")
        table.add_column("Total Mat", justify="right")
        table.add_column("Total Labor", justify="right")
        table.add_column("Total Amount", justify="right", style="bold green")

        for item in estimate.line_items:
            table.add_row(
                item.code,
                item.name,
                item.unit,
                f"{item.quantity:.3f}",
                f"{item.unit_material_cost:,.2f}",
                f"{item.unit_labor_cost:,.2f}",
                f"{item.total_material_cost:,.2f}",
                f"{item.total_labor_cost:,.2f}",
                f"{item.total_amount:,.2f}",
            )

        console.print(table)

        summary_text = (
            f"[bold cyan]Total Material Cost:[/bold cyan] {estimate.total_material_cost:,.2f} {estimate.currency}\n"
            f"[bold cyan]Total Labor Cost:[/bold cyan] {estimate.total_labor_cost:,.2f} {estimate.currency}\n"
            f"[bold green]Grand Total Cost:[/bold green] {estimate.grand_total:,.2f} {estimate.currency}"
        )
        console.print(
            Panel(summary_text, title="[bold green]Project Budget Summary[/bold green]")
        )

        if output:
            csv_path = estimate.export_csv(output)
            console.print(
                f"[bold green]Exported BOQ CSV to:[/bold green] [cyan]{csv_path}[/cyan]"
            )

    except Exception as e:
        console.print(f"[bold red]Cost Estimation Error:[/bold red]\n{e}")
        raise typer.Exit(code=1)


@app.command()
def compile(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest"
    ),
    output: Path = typer.Option(
        Path("dist/model.ifc"), "--output", "-o", help="Output IFC file path"
    ),
):
    """Compile project.yaml to standardized IFC4 format via IfcOpenShell or STEP serializer"""
    if not manifest.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest '{manifest}' not found.")
        raise typer.Exit(code=1)

    console.print(
        f"[bold green]Compiling[/bold green] {manifest} -> [cyan]{output}[/cyan]"
    )
    try:
        out_path = compile_to_ifc(manifest, output)
        file_size = out_path.stat().st_size
        console.print(
            Panel(
                f"[bold green]IFC4 Compilation Successful![/bold green]\n"
                f"[bold cyan]Output Path:[/bold cyan] {out_path}\n"
                f"[bold cyan]File Size:[/bold cyan] {file_size} bytes",
                title="[bold green]debim Compiler[/bold green]",
            )
        )
    except Exception as e:
        console.print(f"[bold red]Compilation Error:[/bold red]\n{e}")
        raise typer.Exit(code=1)


@app.command()
def view(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest"
    ),
    port: int = typer.Option(8000, "--port", "-p", help="Port to serve 3D viewer"),
    no_browser: bool = typer.Option(
        False, "--no-browser", help="Do not open web browser automatically"
    ),
    export: Optional[Path] = typer.Option(
        None, "--export", "-e", help="Export standalone 3D/2D HTML viewer file without running HTTP server"
    ),
):
    """Launch lightweight local 3D preview server in browser or export HTML viewer"""
    if not manifest.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest '{manifest}' not found.")
        raise typer.Exit(code=1)

    try:
        html_content = generate_viewer_html(manifest)
        if export:
            export.parent.mkdir(parents=True, exist_ok=True)
            export.write_text(html_content, encoding="utf-8")
            file_size = export.stat().st_size
            console.print(
                Panel(
                    f"[bold green]Viewer HTML Exported Successfully![/bold green]\n"
                    f"[bold cyan]Export Path:[/bold cyan] {export}\n"
                    f"[bold cyan]File Size:[/bold cyan] {file_size} bytes",
                    title="[bold blue]debim 3D Viewer Export[/bold blue]",
                )
            )
            return

        url = f"http://localhost:{port}"
        console.print(
            Panel(
                f"[bold green]Serving 3D Web Preview at:[/bold green] [cyan bold]{url}[/cyan bold]\n"
                f"[dim]Press Ctrl+C in terminal to stop server.[/dim]",
                title="[bold blue]debim 3D Viewer[/bold blue]",
            )
        )
        serve_viewer(html_content, port=port, open_browser=not no_browser)
    except Exception as e:
        console.print(f"[bold red]Viewer Error:[/bold red]\n{e}")
        raise typer.Exit(code=1)


@app.command(name="import")
def import_ifc(
    ifc_path: Path = typer.Argument(..., help="Path to input IFC file (.ifc)"),
    output: Path = typer.Option(
        Path("project.yaml"), "--output", "-o", help="Output project manifest path"
    ),
):
    """Import an IFC4/IFC2X3 file and convert to declarative project.yaml for QTO & Cost estimation"""
    if not ifc_path.exists():
        console.print(f"[bold red]Error:[/bold red] IFC file '{ifc_path}' not found.")
        raise typer.Exit(code=1)

    console.print(f"[bold green]Importing IFC:[/bold green] {ifc_path} -> [cyan]{output}[/cyan]")
    try:
        from debim.importer import import_ifc_to_manifest
        manifest = import_ifc_to_manifest(ifc_path)

        import json
        data = json.loads(manifest.model_dump_json(by_alias=True, exclude_none=True))
        with open(output, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

        console.print(
            Panel(
                f"[bold green]IFC Successfully Imported to Declarative BIM![/bold green]\n"
                f"[cyan]Output YAML:[/cyan] {output}\n"
                f"[yellow]Elements Extracted:[/yellow] {len(manifest.elements)} elements\n"
                f"[dim]Run 'bim qto -m {output}' to calculate quantities & cost.[/dim]",
                title="[bold green]debim IFC Importer[/bold green]",
            )
        )
    except Exception as e:
        console.print(f"[bold red]Import Error:[/bold red]\n{e}")
        raise typer.Exit(code=1)


def _resolve_target_manifest(target_str: str) -> ProjectManifest:
    path = Path(target_str)
    if path.exists() and path.is_file():
        return load_manifest(path)

    import subprocess
    if ":" in target_str:
        rev, rel_path = target_str.split(":", 1)
    else:
        rev = target_str
        rel_path = "project.yaml"

    try:
        res = subprocess.run(
            ["git", "show", f"{rev}:{rel_path}"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = yaml.safe_load(res.stdout)
        return ProjectManifest.model_validate(data)
    except Exception as e:
        raise ValueError(f"Could not load manifest from '{target_str}': {e}")


@app.command()
def diff(
    target_a: str = typer.Argument(..., help="First target (file path or git rev e.g. HEAD~1)"),
    target_b: str = typer.Argument(..., help="Second target (file path or git rev e.g. HEAD)"),
    prices: Path = typer.Option(
        Path("prices.json"), "--prices", "-p", help="Path to price catalog"
    ),
):
    """Git-aware manifest comparison engine reporting element deltas, QTO deltas, and Cost variance"""
    try:
        manifest_a = _resolve_target_manifest(target_a)
    except Exception as e:
        console.print(f"[bold red]Error loading target A ({target_a}):[/bold red]\n{e}")
        raise typer.Exit(code=1)

    try:
        manifest_b = _resolve_target_manifest(target_b)
    except Exception as e:
        console.print(f"[bold red]Error loading target B ({target_b}):[/bold red]\n{e}")
        raise typer.Exit(code=1)

    console.print(f"[bold cyan]Comparing BIM Revisions:[/bold cyan] [yellow]{target_a}[/yellow] ➔ [green]{target_b}[/green]\n")

    # QTO calculations
    qto_a = calculate_qto(manifest_a)
    qto_b = calculate_qto(manifest_b)

    # Cost calculations
    cost_a = None
    cost_b = None
    if prices.exists():
        try:
            catalog = load_price_catalog(prices)
            cost_a = estimate_cost(qto_a, catalog, manifest_a)
            cost_b = estimate_cost(qto_b, catalog, manifest_b)
        except Exception:
            pass

    # Element comparison
    elems_a = {e.tag: e for e in manifest_a.elements}
    elems_b = {e.tag: e for e in manifest_b.elements}

    all_tags = sorted(list(set(elems_a.keys()) | set(elems_b.keys())))

    elem_table = Table(
        title="Element Changes Breakdown",
        show_header=True,
        header_style="bold cyan",
    )
    elem_table.add_column("Tag", style="bold yellow")
    elem_table.add_column("Class", style="white")
    elem_table.add_column("Change", justify="center")
    elem_table.add_column("Details", style="dim")

    added_count = 0
    removed_count = 0
    modified_count = 0

    for tag in all_tags:
        if tag in elems_b and tag not in elems_a:
            elem = elems_b[tag]
            elem_table.add_row(tag, elem.class_, "[bold green]+ Added[/bold green]", "New element introduced")
            added_count += 1
        elif tag in elems_a and tag not in elems_b:
            elem = elems_a[tag]
            elem_table.add_row(tag, elem.class_, "[bold red]- Removed[/bold red]", "Element deleted")
            removed_count += 1
        else:
            elem_a = elems_a[tag]
            elem_b = elems_b[tag]
            if elem_a.model_dump() != elem_b.model_dump():
                elem_table.add_row(tag, elem_b.class_, "[bold yellow]~ Modified[/bold yellow]", "Properties/geometry updated")
                modified_count += 1

    console.print(elem_table)

    # Helper for delta formatting
    def fmt_delta(val: float, unit: str = "", currency: str = "") -> str:
        prefix = f"{currency} " if currency else ""
        suffix = f" {unit}" if unit else ""
        if val > 1e-6:
            return f"[bold green]+{prefix}{val:,.3f}{suffix}[/bold green]"
        elif val < -1e-6:
            return f"[bold red]{prefix}{val:,.3f}{suffix}[/bold red]"
        else:
            return f"[dim]0.000{suffix}[/dim]"

    def fmt_cost_delta(val: float, currency: str = "THB") -> str:
        if val > 1e-2:
            return f"[bold green]+{val:,.2f} {currency}[/bold green]"
        elif val < -1e-2:
            return f"[bold red]{val:,.2f} {currency}[/bold red]"
        else:
            return f"[dim]0.00 {currency}[/dim]"

    # QTO Deltas
    d_conc = qto_b.total_concrete_volume - qto_a.total_concrete_volume
    d_form = qto_b.total_formwork_area - qto_a.total_formwork_area
    d_rebar = qto_b.total_rebar_weight - qto_a.total_rebar_weight

    qto_delta_table = Table(title="Quantity Take-Off (QTO) Deltas", show_header=True, header_style="bold cyan")
    qto_delta_table.add_column("Metric", style="bold yellow")
    qto_delta_table.add_column("Revision A", justify="right")
    qto_delta_table.add_column("Revision B", justify="right")
    qto_delta_table.add_column("Delta (Δ)", justify="right")

    qto_delta_table.add_row("Concrete Volume (m3)", f"{qto_a.total_concrete_volume:.3f}", f"{qto_b.total_concrete_volume:.3f}", fmt_delta(d_conc, "m3"))
    qto_delta_table.add_row("Formwork Area (m2)", f"{qto_a.total_formwork_area:.3f}", f"{qto_b.total_formwork_area:.3f}", fmt_delta(d_form, "m2"))
    qto_delta_table.add_row("Rebar Weight (kg)", f"{qto_a.total_rebar_weight:.3f}", f"{qto_b.total_rebar_weight:.3f}", fmt_delta(d_rebar, "kg"))

    console.print(qto_delta_table)

    # Cost Variance Breakdown
    if cost_a and cost_b:
        d_mat = cost_b.total_material_cost - cost_a.total_material_cost
        d_lab = cost_b.total_labor_cost - cost_a.total_labor_cost
        d_tot = cost_b.grand_total - cost_a.grand_total
        curr = cost_b.currency

        cost_delta_table = Table(title=f"Cost Variance Breakdown ({curr})", show_header=True, header_style="bold cyan")
        cost_delta_table.add_column("Cost Component", style="bold yellow")
        cost_delta_table.add_column("Revision A", justify="right")
        cost_delta_table.add_column("Revision B", justify="right")
        cost_delta_table.add_column("Variance (Δ)", justify="right")

        cost_delta_table.add_row("Material Cost", f"{cost_a.total_material_cost:,.2f}", f"{cost_b.total_material_cost:,.2f}", fmt_cost_delta(d_mat, curr))
        cost_delta_table.add_row("Labor Cost", f"{cost_a.total_labor_cost:,.2f}", f"{cost_b.total_labor_cost:,.2f}", fmt_cost_delta(d_lab, curr))
        cost_delta_table.add_row("Total Amount", f"{cost_a.grand_total:,.2f}", f"{cost_b.grand_total:,.2f}", fmt_cost_delta(d_tot, curr))

        console.print(cost_delta_table)

    summary_msg = (
        f"[bold yellow]Elements Changed:[/bold yellow] [green]+{added_count} Added[/green] | "
        f"[red]-{removed_count} Removed[/red] | [yellow]~{modified_count} Modified[/yellow]\n"
        f"[bold cyan]Net QTO Deltas:[/bold cyan] Δ Concrete: {d_conc:+.3f} m3, Δ Formwork: {d_form:+.3f} m2, Δ Rebar: {d_rebar:+.3f} kg"
    )
    if cost_a and cost_b:
        summary_msg += f"\n[bold green]Net Budget Variance:[/bold green] {cost_b.grand_total - cost_a.grand_total:+,.2f} {cost_b.currency}"

    console.print(Panel(summary_msg, title="[bold green]Diff Summary[/bold green]"))


if __name__ == "__main__":
    app()

