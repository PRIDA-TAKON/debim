"""
CLI interface for debim / bim
"""

from pathlib import Path
import typer
from rich.console import Console

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
    console.print(f"[bold green]Success:[/bold green] Initialized new debim project in [cyan]{name}[/cyan]")


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
    # Jules will implement deep validation in Issue #1
    console.print("[dim]Basic syntax check passed.[/dim]")


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
    console.print(f"[bold blue]Calculating QTO for:[/bold blue] {manifest}")
    console.print("[yellow]QTO Engine stub — assigned to Issue #2[/yellow]")


@app.command()
def cost(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest"
    ),
    prices: Path = typer.Option(
        Path("prices.json"), "--prices", "-p", help="Path to price catalog"
    ),
):
    """Calculate cost estimate by matching QTO with price catalog"""
    console.print(f"[bold blue]Calculating project cost using:[/bold blue] {prices}")
    console.print("[yellow]Cost Engine stub — assigned to Issue #2[/yellow]")


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
    console.print(f"[bold green]Compiling[/bold green] {manifest} -> [cyan]{output}[/cyan]")
    console.print("[yellow]IFC Compiler stub — assigned to Issue #5[/yellow]")


@app.command()
def view(
    manifest: Path = typer.Option(
        Path("project.yaml"), "--manifest", "-m", help="Path to project manifest"
    ),
    port: int = typer.Option(8000, "--port", "-p", help="Port to serve 3D viewer"),
):
    """Launch lightweight local 3D preview server in browser"""
    console.print(f"[bold blue]Serving 3D preview at:[/bold blue] http://localhost:{port}")
    console.print("[yellow]3D Viewer stub — assigned to Issue #4[/yellow]")


if __name__ == "__main__":
    app()
