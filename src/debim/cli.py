"""
CLI interface for debim
"""

import sys
from pathlib import Path
from typing import Optional
import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from debim.version import __version__, check_and_notify_updates
from debim.compiler import compile_to_ifc
from debim.bsdd import validate_manifest_psets, PropertyValidationStatus
from debim.scaffold import scaffold_element
from debim.cost import estimate_cost, generate_cost_template, load_price_catalog
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import ProjectManifest, load_manifest
from debim.viewer import generate_viewer_html, serve_viewer
from debim.modular import bundle_manifest, split_manifest
from debim.spec.registry import SpecRegistryClient

app = typer.Typer(
    name="debim",
    help="Minimal Declarative BIM (Building-as-Code) engine",
    add_completion=False,
)
console = Console(legacy_windows=False)

DEBIM_BANNER = (
    "\n"
    "[bold #00ffff]  > _    [/bold #00ffff]  [bold #00ffff]██████╗ [/bold #00ffff][bold #22d3ee]███████╗[/bold #22d3ee][bold #38bdf8]██████╗ [/bold #38bdf8][bold #60a5fa]██╗[/bold #60a5fa][bold #818cf8]███╗   ███╗[/bold #818cf8]\n"
    "[bold #00ffff]  \\ \\    [/bold #00ffff]  [bold #00ffff]██╔══██╗[/bold #00ffff][bold #22d3ee]██╔════╝[/bold #22d3ee][bold #38bdf8]██╔══██╗[/bold #38bdf8][bold #60a5fa]██║[/bold #60a5fa][bold #818cf8]████╗ ████║[/bold #818cf8]\n"
    "[bold #00ffff] > \\ \\   [/bold #00ffff]  [bold #00ffff]██║  ██║[/bold #00ffff][bold #22d3ee]█████╗  [/bold #22d3ee][bold #38bdf8]██████╔╝[/bold #38bdf8][bold #60a5fa]██║[/bold #60a5fa][bold #818cf8]██╔████╔██║[/bold #818cf8]\n"
    "[bold #00ffff]  \\ \\ \\  [/bold #00ffff]  [bold #00ffff]██║  ██║[/bold #00ffff][bold #22d3ee]██╔══╝  [/bold #22d3ee][bold #38bdf8]██╔══██╗[/bold #38bdf8][bold #60a5fa]██║[/bold #60a5fa][bold #818cf8]██║╚██╔╝██║[/bold #818cf8]\n"
    "[bold #00ffff]   \\_\\_\\ [/bold #00ffff]  [bold #00ffff]██████╔╝[/bold #00ffff][bold #22d3ee]███████╗[/bold #22d3ee][bold #38bdf8]██████╔╝[/bold #38bdf8][bold #60a5fa]██║[/bold #60a5fa][bold #818cf8]██║ ╚═╝ ██║[/bold #818cf8]\n"
    "[bold #ffd700]  ══════ [/bold #ffd700]  [bold #00ffff]╚═════╝ [/bold #00ffff][bold #22d3ee]╚══════╝[/bold #22d3ee][bold #38bdf8]╚═════╝ [/bold #38bdf8][bold #60a5fa]╚═╝[/bold #60a5fa][bold #818cf8]╚═╝     ╚═╝[/bold #818cf8]\n"
    "[dim #64748b]  -------------------------------------------------------------[/dim #64748b]\n"
    "[bold #94a3b8]   Declarative BIM Compiler  |  Building-as-Code for AI Agents [/bold #94a3b8]\n"
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show debim version"),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Suppress update check and non-essential output"
    ),
):
    """Minimal Declarative BIM (Building-as-Code) engine"""
    if version:
        console.print(DEBIM_BANNER)
        console.print(f"[bold cyan]debim[/bold cyan] version [bold green]{__version__}[/bold green]")
        check_and_notify_updates(console=console, quiet=quiet, ctx=ctx)
        raise typer.Exit()
    if ctx.invoked_subcommand is None and not ctx.resilient_parsing:
        console.print(DEBIM_BANNER)
        console.print(ctx.get_help())
        check_and_notify_updates(console=console, quiet=quiet, ctx=ctx)
        raise typer.Exit()

    check_and_notify_updates(console=console, quiet=quiet, ctx=ctx)



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
    bsdd: bool = typer.Option(
        True, "--bsdd/--no-bsdd", help="Perform buildingSMART bSDD Property Set (Pset_*) validation"
    ),
    strict_psets: bool = typer.Option(
        False, "--strict-psets", help="Fail validation if non-compliant Pset types or values are found"
    ),
):
    """Validate project.yaml schema, grid alignment, element placement links, and bSDD Psets"""
    if not manifest.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest '{manifest}' not found.")
        raise typer.Exit(code=1)
    console.print(f"[bold green]Validating:[/bold green] {manifest}")
    try:
        manifest_obj = load_manifest(manifest)
        console.print("[bold green]Schema & Topology Validation passed successfully.[/bold green]")

        if bsdd:
            pset_results = validate_manifest_psets(manifest_obj)
            if pset_results:
                table = Table(
                    title="buildingSMART bSDD Pset Validation Summary",
                    show_header=True,
                    header_style="bold cyan",
                )
                table.add_column("Tag", style="bold yellow")
                table.add_column("Property Set", style="magenta")
                table.add_column("Property", style="white")
                table.add_column("Expected Type", style="cyan")
                table.add_column("Status", justify="center")
                table.add_column("Details", style="dim")

                has_errors = False
                for r in pset_results:
                    if r.status in (PropertyValidationStatus.TYPE_MISMATCH, PropertyValidationStatus.VALUE_CONSTRAINT_VIOLATION):
                        has_errors = True
                        status_str = f"[bold red]{r.status.value}[/bold red]"
                    elif r.status in (PropertyValidationStatus.NON_STANDARD_PROPERTY, PropertyValidationStatus.NON_STANDARD_PSET):
                        status_str = f"[yellow]{r.status.value}[/yellow]"
                    else:
                        status_str = f"[green]{r.status.value}[/green]"

                    table.add_row(
                        r.element_tag,
                        r.pset_name,
                        r.property_name,
                        r.expected_type or "-",
                        status_str,
                        r.message,
                    )

                console.print(table)

                if strict_psets and (has_errors or any(r.status != PropertyValidationStatus.VALID for r in pset_results)):
                    console.print("[bold red]Strict Pset Validation Failed! Non-compliant Property Sets detected.[/bold red]")
                    raise typer.Exit(code=1)

    except (ValidationError, ValueError) as e:
        console.print(f"[bold red]Validation Error:[/bold red]\n{e}")
        raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Validation Error:[/bold red]\n{e}")
        raise typer.Exit(code=1)


@app.command()
def split(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest to split"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Target output directory (defaults to manifest directory)"
    ),
    by: str = typer.Option(
        "system", "--by", "-b", help="Decomposition strategy: 'system' (subsystem/category) or 'storey' (by level)"
    ),
    backup: bool = typer.Option(
        True, "--backup/--no-backup", help="Create backup of original manifest if overwriting (project.yaml.bak)"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview decomposition without writing files to disk"
    ),
):
    """Split a monolithic project.yaml manifest into modular files under models/"""
    if not manifest.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest '{manifest}' not found.")
        raise typer.Exit(code=1)

    try:
        summary_info = split_manifest(
            manifest_path=manifest,
            output_dir=output_dir,
            by=by,
            backup=backup,
            dry_run=dry_run,
        )
    except Exception as e:
        console.print(f"[bold red]Error during split:[/bold red] {e}")
        raise typer.Exit(code=1)

    title = "[bold cyan]debim Split (Preview / Dry Run)[/bold cyan]" if dry_run else "[bold green]debim Split Complete[/bold green]"
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Module File", style="yellow")
    table.add_column("Elements", justify="right", style="green")

    for rel_path, count in summary_info["modules"].items():
        table.add_row(rel_path, str(count))

    console.print(table)
    total_elements = summary_info["total_elements"]
    num_modules = len(summary_info["modules"])

    if dry_run:
        console.print(
            Panel(
                f"[bold yellow]Dry-run preview:[/bold yellow] {total_elements} elements across {num_modules} modules.\n"
                f"Strategy: [cyan]{by}[/cyan]\n"
                "Run without [cyan]--dry-run[/cyan] to write modular manifest files to disk.",
                style="yellow",
            )
        )
    else:
        console.print(
            Panel(
                f"[bold green]Successfully decomposed[/bold green] [cyan]{manifest}[/cyan] into [yellow]{num_modules}[/yellow] modular files!\n"
                f"Total Elements: [green]{total_elements}[/green] | Strategy: [cyan]{by}[/cyan]\n"
                f"Root Manifest Updated: [cyan]{summary_info['root_file']}[/cyan] (with includes: [\"models/**/*.yaml\"])",
                style="green",
            )
        )


@app.command()
def bundle(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to modular project manifest to bundle"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output path for bundled single-file manifest (default: stdout)"
    ),
):
    """Bundle a modular project manifest (with includes:) into a single self-contained project.yaml"""
    if not manifest.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest '{manifest}' not found.")
        raise typer.Exit(code=1)

    try:
        bundled = bundle_manifest(manifest_path=manifest, output_path=output)
    except Exception as e:
        console.print(f"[bold red]Error during bundle:[/bold red] {e}")
        raise typer.Exit(code=1)

    elem_count = len(bundled.get("elements", []))
    storey_count = len(bundled.get("spatial_structure", {}).get("storeys", []))
    mat_count = len(bundled.get("materials", []))

    if output is not None:
        console.print(
            Panel(
                f"[bold green]Successfully bundled modular manifest into:[/bold green] [cyan]{output}[/cyan]\n"
                f"Aggregated: [green]{elem_count}[/green] elements, [green]{storey_count}[/green] storeys, [green]{mat_count}[/green] materials.",
                title="[bold green]debim Bundle Complete[/bold green]",
                style="green",
            )
        )
    else:
        yaml_str = yaml.safe_dump(bundled, sort_keys=False, allow_unicode=True)
        print(yaml_str, end="")


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
        if project_qto.total_excavation_volume > 0 or project_qto.total_lean_concrete_volume > 0 or project_qto.total_sand_bedding_volume > 0:
            summary_text += (
                f"\n[bold magenta]--- Substructure & Earthwork ---[/bold magenta]\n"
                f"[bold cyan]Excavation (งานดินขุดฐานราก):[/bold cyan] {project_qto.total_excavation_volume:.2f} m3\n"
                f"[bold cyan]Lean Concrete (คอนกรีตหยาบ):[/bold cyan] {project_qto.total_lean_concrete_volume:.2f} m3\n"
                f"[bold cyan]Sand Bedding (ทรายหยาบรองฐานราก/พื้น):[/bold cyan] {project_qto.total_sand_bedding_volume:.2f} m3"
            )
        if project_qto.total_ceiling_gypsum_area > 0 or project_qto.total_ceiling_tbar_area > 0 or project_qto.total_ceiling_eaves_area > 0:
            summary_text += (
                f"\n[bold magenta]--- Ceilings (งานฝ้าเพดาน) ---[/bold magenta]\n"
                f"[bold cyan]Gypsum Ceiling (ฝ้ายิปซั่มฉาบเรียบ):[/bold cyan] {project_qto.total_ceiling_gypsum_area:.2f} m2\n"
                f"[bold cyan]T-Bar Ceiling (ฝ้าทีบาร์ทนชื้นห้องน้ำ):[/bold cyan] {project_qto.total_ceiling_tbar_area:.2f} m2\n"
                f"[bold cyan]Eaves Ceiling (ฝ้าชายคาระบายอากาศ):[/bold cyan] {project_qto.total_ceiling_eaves_area:.2f} m2"
            )
        if project_qto.total_floor_tile_area > 0 or project_qto.total_floor_polish_area > 0 or project_qto.total_skirting_length > 0:
            summary_text += (
                f"\n[bold magenta]--- Flooring & Finishes (งานปูพื้นและตกแต่งผิว) ---[/bold magenta]\n"
                f"[bold cyan]Ceramic Floor Tiles (ปูกระเบื้องเซรามิค):[/bold cyan] {project_qto.total_floor_tile_area:.2f} m2\n"
                f"[bold cyan]Polished Concrete (คอนกรีตขัดเรียบ/ขัดมัน):[/bold cyan] {project_qto.total_floor_polish_area:.2f} m2\n"
                f"[bold cyan]Skirting Board (บัวเชิงผนัง):[/bold cyan] {project_qto.total_skirting_length:.2f} m"
            )
        if project_qto.total_structural_steel_weight > 0 or project_qto.total_painting_area > 0 or project_qto.total_timber_volume > 0:
            summary_text += (
                f"\n[bold magenta]--- Structural Steel & Timber (งานโครงสร้างเหล็กและไม้) ---[/bold magenta]\n"
            )
            if project_qto.total_structural_steel_weight > 0:
                summary_text += f"[bold cyan]Structural Steel Weight (เหล็กรูปพรรณ):[/bold cyan] {project_qto.total_structural_steel_weight:.2f} kg ({project_qto.total_structural_steel_weight/1000.0:.3f} tons)\n"
            if project_qto.total_painting_area > 0:
                summary_text += f"[bold cyan]Painting Area (พื้นที่ทาสีจริง):[/bold cyan] {project_qto.total_painting_area:.2f} m2\n"
            if project_qto.total_weld_touchup_area > 0:
                summary_text += f"[bold cyan]Weld Touch-Up Area (พื้นที่สีกันสนิมรอยเชื่อม 10%):[/bold cyan] {project_qto.total_weld_touchup_area:.2f} m2\n"
            if project_qto.total_timber_volume > 0:
                summary_text += f"[bold cyan]Timber Volume (ปริมาตรไม้โครงสร้าง):[/bold cyan] {project_qto.total_timber_volume:.3f} m3\n"
        if project_qto.total_roof_covering_area > 0:
            summary_text += (
                f"\n[bold cyan]Roof Covering Tiles:[/bold cyan] {project_qto.total_roof_covering_area:.2f} m2\n"
                f"[bold cyan]Roof Structural Steel:[/bold cyan] {project_qto.total_roof_steel_weight:.2f} kg\n"
                f"[bold cyan]Roof Ridge/Hip Caps:[/bold cyan] {project_qto.total_roof_ridge_length + project_qto.total_roof_hip_length:.2f} m\n"
                f"[bold cyan]Roof Eaves Perimeter:[/bold cyan] {project_qto.total_roof_eaves_length:.2f} m"
            )
        total_pipe = (
            project_qto.total_cold_water_pipe_length
            + project_qto.total_soil_pipe_length
            + project_qto.total_waste_pipe_length
            + project_qto.total_vent_pipe_length
            + project_qto.total_drainage_pipe_length
            + project_qto.total_refrigerant_pipe_length
            + project_qto.total_condensate_pipe_length
        )
        if (
            total_pipe > 0
            or project_qto.total_sanitary_terminals_count > 0
            or project_qto.total_conduit_length > 0
            or project_qto.total_duct_length > 0
            or project_qto.total_air_terminals_count > 0
            or project_qto.total_unitary_equipment_count > 0
        ):
            summary_text += (
                f"\n[bold magenta]--- MEP System Totals ---[/bold magenta]\n"
                f"[bold cyan]Cold Water Pipe (ท่อน้ำดี):[/bold cyan] {project_qto.total_cold_water_pipe_length:.2f} m\n"
                f"[bold cyan]Soil & Waste Pipe (ท่อโสโครก/น้ำทิ้ง):[/bold cyan] {project_qto.total_soil_pipe_length + project_qto.total_waste_pipe_length:.2f} m\n"
                f"[bold cyan]Vent Pipe (ท่อระบายอากาศ):[/bold cyan] {project_qto.total_vent_pipe_length:.2f} m\n"
                f"[bold cyan]Pipe Fittings & Valves (ข้อต่อท่อ):[/bold cyan] {project_qto.total_pipe_fittings_count} items\n"
                f"[bold cyan]Sanitary Fixtures (สุขภัณฑ์/อุปกรณ์):[/bold cyan] {project_qto.total_sanitary_terminals_count} sets\n"
                f"[bold cyan]Electrical Conduits (ท่อร้อยสายไฟ):[/bold cyan] {project_qto.total_conduit_length:.2f} m\n"
                f"[bold cyan]Distribution Boards (ตู้ควบคุมไฟ):[/bold cyan] {project_qto.total_distribution_boards_count} sets\n"
                f"[bold cyan]Lighting Fixtures (ดวงโคม):[/bold cyan] {project_qto.total_lighting_fixtures_count} sets\n"
                f"[bold cyan]Switches & Outlets (สวิตช์/เต้ารับ):[/bold cyan] {project_qto.total_switches_count + project_qto.total_outlets_count} sets\n"
                f"[bold cyan]Refrigerant Pipe (ท่อน้ำยาแอร์):[/bold cyan] {project_qto.total_refrigerant_pipe_length:.2f} m\n"
                f"[bold cyan]HVAC Ducts (ท่อลมระบายอากาศ):[/bold cyan] {project_qto.total_duct_length:.2f} m\n"
                f"[bold cyan]Air Conditioners (เครื่องปรับอากาศ):[/bold cyan] {project_qto.total_unitary_equipment_count} sets\n"
                f"[bold cyan]Ventilation Fans & Hoods (พัดลมดูด/ฮูด):[/bold cyan] {project_qto.total_air_terminals_count} sets"
            )
        console.print(Panel(summary_text, title="[bold green]QTO Totals[/bold green]"))

    except Exception as e:
        console.print(f"[bold red]QTO Error:[/bold red]\n{e}")
        raise typer.Exit(code=1)


cost_app = typer.Typer(
    help="Calculate cost estimate or generate price catalog templates",
    add_completion=False,
    invoke_without_command=True,
)
app.add_typer(cost_app, name="cost")


@cost_app.callback(invoke_without_command=True)
def cost_main(
    ctx: typer.Context,
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest"
    ),
    prices: Path = typer.Option(
        Path("prices.json"), "--prices", "-p", help="Path or '-' to read price catalog"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Path to export BOQ CSV (e.g. dist/boq.csv)"
    ),
):
    """Calculate cost estimate by matching QTO with price catalog"""
    if ctx.invoked_subcommand is not None:
        return

    if not manifest.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest '{manifest}' not found.")
        raise typer.Exit(code=1)

    prices_str = str(prices)
    if prices_str != "-" and not prices.exists():
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


@cost_app.command(name="template")
def cost_template(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Path for generated template file"
    ),
    format: str = typer.Option(
        "yaml", "--format", help="Output format (yaml or json)"
    ),
    modular: bool = typer.Option(
        False, "--modular/--no-modular", help="Generate modular folder structure"
    ),
):
    """Automatically scan project manifest and generate minimal project-scoped price catalog template"""
    if not manifest.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest '{manifest}' not found.")
        raise typer.Exit(code=1)

    if output is None:
        if modular:
            output = Path("prices/catalog.yaml")
        else:
            ext = "json" if format.lower() == "json" else "yaml"
            output = Path(f"prices.template.{ext}")

    console.print(
        f"[bold green]Generating cost template from:[/bold green] {manifest} -> [cyan]{output}[/cyan]"
    )
    try:
        out_path = generate_cost_template(
            manifest=manifest,
            output_path=output,
            format=format,
            modular=modular,
        )
        console.print(
            Panel(
                f"[bold green]Cost Catalog Template Generated Successfully![/bold green]\n"
                f"[bold cyan]Output File:[/bold cyan] {out_path}\n"
                f"[bold cyan]Modular Mode:[/bold cyan] {modular}\n"
                f"[dim]Populate material_cost and labor_cost fields to complete the pricing catalog.[/dim]",
                title="[bold green]debim Cost Template Generator[/bold green]",
            )
        )
    except Exception as e:
        console.print(f"[bold red]Cost Template Error:[/bold red]\n{e}")
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
    bake_assets: bool = typer.Option(
        False,
        "--bake-assets/--no-bake-assets",
        help="Automated GLB asset baker using IfcOpenShell and trimesh to export complex 3D geometry into lightweight .glb assets",
    ),
):
    """Import an IFC4/IFC2X3 file and convert to declarative project.yaml for QTO & Cost estimation"""
    if not ifc_path.exists():
        console.print(f"[bold red]Error:[/bold red] IFC file '{ifc_path}' not found.")
        raise typer.Exit(code=1)

    console.print(f"[bold green]Importing IFC:[/bold green] {ifc_path} -> [cyan]{output}[/cyan]")
    try:
        from debim.importer import import_ifc_to_manifest
        assets_dir = output.parent / "assets" if output.parent != Path(".") else Path("assets")
        manifest = import_ifc_to_manifest(ifc_path, bake_assets=bake_assets, assets_dir=assets_dir)

        import json
        data = json.loads(manifest.model_dump_json(by_alias=True, exclude_none=True))
        with open(output, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

        console.print(
            Panel(
                f"[bold green]IFC Successfully Imported to Declarative BIM![/bold green]\n"
                f"[cyan]Output YAML:[/cyan] {output}\n"
                f"[yellow]Elements Extracted:[/yellow] {len(manifest.elements)} elements\n"
                f"[magenta]Asset Baking Enabled:[/magenta] {bake_assets}\n"
                f"[dim]Run 'debim qto -m {output}' to calculate quantities & cost.[/dim]",
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


scaffold_app = typer.Typer(
    help="Developer scaffolding commands to generate BIM boilerplate & test skeletons",
    add_completion=False,
)
app.add_typer(scaffold_app, name="scaffold")


@scaffold_app.command(name="element")
def scaffold_element_cmd(
    class_name: str = typer.Argument(..., help="BIM Element class name (e.g. IfcRailing, IfcCurtainWall)"),
    placement_type: str = typer.Option(
        "grid", "--placement-type", "-p", help="Placement geometry type (grid, span, boundary, path, point)"
    ),
    layer: Optional[str] = typer.Option(
        None, "--layer", "-l", help="Default hierarchical layer path (e.g., architecture/openings/doors)"
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--no-dry-run", help="Print generated code to stdout without writing files (default: true for safety)"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Optional directory path to emit generated code modules or test templates"
    ),
):
    """Generate Pydantic v2 data model, resolver logic, QTO formula, and pytest test skeletons for a new element class."""
    if not class_name.startswith("Ifc"):
        class_name = f"Ifc{class_name[0].upper()}{class_name[1:]}"

    console.print(
        Panel(
            f"[bold cyan]debim Element Scaffolder[/bold cyan]\n"
            f"[bold yellow]Element Class:[/bold yellow] {class_name}\n"
            f"[bold yellow]Placement Type:[/bold yellow] {placement_type}\n"
            f"[bold yellow]Default Layer:[/bold yellow] {layer or 'derived'}\n"
            f"[bold yellow]Dry Run Mode:[/bold yellow] {dry_run}",
            title="[bold green]scaffold element[/bold green]",
        )
    )

    artifacts = scaffold_element(
        class_name=class_name,
        placement_type=placement_type,
        layer=layer,
        dry_run=dry_run,
        output_dir=output_dir,
    )

    if dry_run:
        console.print("[bold magenta]=== 1. Generated Pydantic v2 Model (for schema.py) ===[/bold magenta]")
        console.print(artifacts["schema_code"])

        console.print("\n[bold magenta]=== 2. Generated Resolver Logic (for resolver.py) ===[/bold magenta]")
        console.print(artifacts["resolver_code"])

        console.print("\n[bold magenta]=== 3. Generated QTO Formula (for qto.py) ===[/bold magenta]")
        console.print(artifacts["qto_code"])

        console.print("\n[bold magenta]=== 4. Generated Pytest Skeleton ===[/bold magenta]")
        console.print(artifacts["test_code"])

        console.print(
            Panel(
                "[bold green]Dry-run complete![/bold green] Pass [cyan]--no-dry-run -o <output_dir>[/cyan] to write files to disk.",
                style="green",
            )
        )
    else:
        if output_dir:
            console.print(
                Panel(
                    f"[bold green]Scaffold artifacts successfully written to:[/bold green] [cyan]{output_dir}[/cyan]",
                    style="green",
                )
            )
        else:
            console.print("[bold red]Error:[/bold red] --no-dry-run requires --output-dir (-o) specified.")
            raise typer.Exit(code=1)


spec_app = typer.Typer(
    help="Declarative material specification management & discrepancy auditing commands",
    add_completion=False,
)
app.add_typer(spec_app, name="spec")


@spec_app.command(name="build")
def spec_build_cmd(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest (project.yaml)"
    ),
    specs: Optional[Path] = typer.Option(
        None, "--specs", "-s", help="Path to material specifications manifest file or directory"
    ),
    output: Path = typer.Option(
        Path("dist/specifications.md"), "--output", "-o", help="Output destination file path (.md or .html)"
    ),
    format: Optional[str] = typer.Option(
        None, "--format", "-f", help="Output format override ('markdown' or 'html')"
    ),
    title: str = typer.Option(
        "ARCHITECTURAL MATERIAL SPECIFICATIONS BOOK", "--title", "-t", help="Title of the Specification Book"
    ),
):
    """Scan active project materials, resolve installed specifications, and compile a Specification Book."""
    if not manifest.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest '{manifest}' not found.")
        raise typer.Exit(code=1)

    console.print(f"[bold blue]Compiling Specification Book for:[/bold blue] {manifest}")
    if specs:
        console.print(f"[bold blue]Using Specs Path:[/bold blue] {specs}")

    try:
        from debim.spec.builder import build_specification_book

        book = build_specification_book(
            project_manifest=manifest,
            spec_manifest=specs,
            title=title,
        )

        saved_path = book.save(output_path=output, format=format)
        file_size = saved_path.stat().st_size

        table = Table(
            title="Specification Book Summary",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("MasterFormat Division", style="bold yellow")
        table.add_column("Division Title", style="white")
        table.add_column("Specs Count", justify="right", style="green")

        for div_code, div_data in book.divisions.items():
            table.add_row(
                f"Division {div_code}",
                div_data["title"],
                str(len(div_data["specs"])),
            )

        console.print(table)

        summary_text = (
            f"[bold cyan]Project Name:[/bold cyan] {book.project_name} ({book.project_id})\n"
            f"[bold cyan]Active Specifications Included:[/bold cyan] {len(book.included_specs)} (zero unreferenced bloat)\n"
            f"[bold cyan]MasterFormat Divisions Covered:[/bold cyan] {len(book.divisions)}\n"
            f"[bold green]Output Specification Book:[/bold green] [cyan]{saved_path}[/cyan] ({file_size:,} bytes)"
        )
        console.print(
            Panel(
                summary_text,
                title="[bold green]debim Spec Book Build Complete[/bold green]",
                style="green",
            )
        )

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Specification Book Build Error:[/bold red]\n{e}")
        raise typer.Exit(code=1)


@spec_app.command(name="audit")
def spec_audit_cmd(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest (project.yaml)"
    ),
    specs: Optional[Path] = typer.Option(
        None, "--specs", "-s", help="Path to material specifications manifest file or directory"
    ),
    strict: bool = typer.Option(
        False, "--strict/--no-strict", help="Exit with code 1 if discrepancies exist"
    ),
):
    """Cross-reference project manifest elements with material specification packages to audit discrepancies."""
    if not manifest.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest '{manifest}' not found.")
        raise typer.Exit(code=1)

    console.print(f"[bold blue]Auditing Specifications for:[/bold blue] {manifest}")
    if specs:
        console.print(f"[bold blue]Using Specs Path:[/bold blue] {specs}")

    try:
        from debim.spec import audit_project_specs, load_spec_manifest

        specs_manifest_obj = load_spec_manifest(specs) if specs else None
        res = audit_project_specs(manifest, specs_manifest_obj)

        table = Table(
            title="Material Specification Discrepancy Audit",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Material / Spec ID", style="bold white")
        table.add_column("Status", justify="center")
        table.add_column("Referenced Element Tags", style="dim")

        # Process missing specs
        for mat_id in res.missing_specs:
            tags = ", ".join(res.element_material_map.get(mat_id, [])) or "(manifest declared)"
            table.add_row(
                mat_id,
                "[bold red]MISSING SPEC[/bold red]",
                tags,
            )

        # Process unused specs
        for spec_id in res.unused_specs:
            table.add_row(
                spec_id,
                "[bold yellow]UNUSED / REDUNDANT[/bold yellow]",
                "(none)",
            )

        # Process compliant specs
        compliant_specs = set(res.referenced_materials).intersection(set(res.spec_ids))
        for mat_id in sorted(compliant_specs):
            tags = ", ".join(res.element_material_map.get(mat_id, [])) or "(manifest declared)"
            table.add_row(
                mat_id,
                "[bold green]MATCHED / OK[/bold green]",
                tags,
            )

        console.print(table)

        summary_text = (
            f"[bold]Referenced Materials:[/bold] {len(res.referenced_materials)}\n"
            f"[bold]Specification Packages:[/bold] {len(res.spec_ids)}\n"
            f"[bold red]Missing Specs:[/bold red] {len(res.missing_specs)}\n"
            f"[bold yellow]Unused / Redundant Specs:[/bold yellow] {len(res.unused_specs)}\n"
            f"[bold green]Compliant Specs:[/bold green] {len(compliant_specs)}"
        )

        title_style = "bold green" if res.is_compliant else "bold red"
        status_label = "COMPLIANT PASS" if res.is_compliant else "DISCREPANCIES DETECTED"
        console.print(
            Panel(
                summary_text,
                title=f"[{title_style}]Audit Summary: {status_label}[/{title_style}]",
            )
        )

        if strict and not res.is_compliant:
            raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[bold red]Specification Audit Error:[/bold red]\n{e}")
        raise typer.Exit(code=1)


@app.command()
def mcp():
    """Start the Model Context Protocol (MCP) server for AI coding agents."""
    from debim.mcp import run_mcp_server
    run_mcp_server()


@spec_app.command(name="add")
def spec_add(
    pkg_name: str = typer.Argument(
        ..., help="Package identifier (e.g. @toa/supershield-exterior or org/repo)"
    ),
    specs_dir: Path = typer.Option(
        Path("specs"),
        "--specs-dir",
        "-s",
        help="Target project directory to install specification packages into",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Bypass local registry cache and force re-download from remote",
    ),
    cache_dir: Optional[Path] = typer.Option(
        None, "--cache-dir", help="Custom registry cache directory"
    ),
):
    """Install specification package into project local specs/ directory"""
    console.print(f"[bold cyan]Fetching specification package:[/bold cyan] [yellow]{pkg_name}[/yellow]...")
    try:
        client = SpecRegistryClient(cache_dir=cache_dir)
        installed_path = client.install_package(pkg_name, specs_dir=specs_dir, force=force)
        pkg = client.fetch_package(pkg_name, force=False)

        console.print(
            Panel(
                f"[bold green]Specification Package Installed Successfully![/bold green]\n"
                f"[bold cyan]Package Name:[/bold cyan] {pkg.name}\n"
                f"[bold cyan]Version:[/bold cyan] {pkg.version}\n"
                f"[bold cyan]Manufacturer:[/bold cyan] {pkg.manufacturer or 'N/A'}\n"
                f"[bold cyan]Installed Path:[/bold cyan] {installed_path}",
                title="[bold green]debim Spec Package Manager[/bold green]",
            )
        )
    except Exception as e:
        console.print(f"[bold red]Error installing specification package '{pkg_name}':[/bold red]\n{e}")
        raise typer.Exit(code=1)


@spec_app.command(name="list")
def spec_list(
    specs_dir: Path = typer.Option(
        Path("specs"),
        "--specs-dir",
        "-s",
        help="Directory containing installed specification packages",
    ),
):
    """List installed specification packages and versions in local specs/ directory"""
    client = SpecRegistryClient()
    installed = client.list_installed_packages(specs_dir=specs_dir)

    if not installed:
        console.print(
            f"[yellow]No specification packages installed in '[cyan]{specs_dir}[/cyan]'.[/yellow]"
        )
        console.print("[dim]Use 'debim spec add <pkg_name>' to install material specifications.[/dim]")
        return

    table = Table(
        title=f"Installed Material Specification Packages ({specs_dir})",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Package Name", style="bold yellow")
    table.add_column("Version", justify="center", style="green")
    table.add_column("Category", style="magenta")
    table.add_column("Manufacturer", style="white")
    table.add_column("Path", style="dim")

    for item in installed:
        table.add_row(
            item["name"],
            item["version"],
            item["category"],
            item["manufacturer"],
            item["path"],
        )

    console.print(table)


if __name__ == "__main__":
    app()
