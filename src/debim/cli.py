"""
CLI interface for debim / bim
"""

from pathlib import Path
from typing import Optional
import typer
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from debim.cost import estimate_cost, load_price_catalog
from debim.qto import calculate_qto
from debim.schema import load_manifest

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
):
    """Run building law & compliance test suite via pytest"""
    import subprocess
    import sys

    console.print(f"[bold blue]Running Compliance Tests in:[/bold blue] {test_dir}")
    cmd = [sys.executable, "-m", "pytest", str(test_dir)]
    res = subprocess.run(cmd)
    raise typer.Exit(code=res.returncode)


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
    """Compile project.yaml to standardized IFC4 format via IfcOpenShell"""
    console.print(
        f"[bold green]Compiling[/bold green] {manifest} -> [cyan]{output}[/cyan]"
    )
    console.print("[yellow]IFC Compiler stub — assigned to Issue #5[/yellow]")


@app.command()
def view(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest"
    ),
    port: int = typer.Option(8000, "--port", "-p", help="Port to serve 3D viewer"),
):
    """Launch lightweight local 3D preview server in browser"""
    console.print(
        f"[bold blue]Serving 3D preview at:[/bold blue] http://localhost:{port}"
    )
    console.print("[yellow]3D Viewer stub — assigned to Issue #4[/yellow]")


if __name__ == "__main__":
    app()
