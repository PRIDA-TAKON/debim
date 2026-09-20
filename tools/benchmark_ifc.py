"""
Real-world IFC Benchmark Suite for debim.
Downloads standardized models, measures conversion ratio, checks validation & QTO.
"""

import os
from pathlib import Path
import urllib.request
from typing import Dict, List, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from debim.importer import import_ifc_to_manifest
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.schema import load_manifest

console = Console()

DEFAULT_CACHE_DIR = Path(r"C:\Users\takon\OneDrive\Desktop\งานปี2024")

BENCHMARK_MODELS = [
    {
        "id": "BM-01",
        "name": "Building-Structural.ifc",
        "schema": "IFC4",
        "category": "Structure",
        "url": "https://raw.githubusercontent.com/buildingSMART/Certification-datasets/main/IFC%204.0.2.1%20(IFC%204%20ADD2%20TC1)/Simple-Scene/Building-Structural.ifc",
    },
    {
        "id": "BM-02",
        "name": "Building-Architecture.ifc",
        "schema": "IFC4",
        "category": "Architecture",
        "url": "https://raw.githubusercontent.com/buildingSMART/Certification-datasets/main/IFC%204.0.2.1%20(IFC%204%20ADD2%20TC1)/Simple-Scene/Building-Architecture.ifc",
    },
    {
        "id": "BM-03",
        "name": "Duplex_A_20110907.ifc",
        "schema": "IFC2X3",
        "category": "Residential (Full)",
        "url": "https://raw.githubusercontent.com/andyward/XBimDemo/master/Xbim.TestApp/Duplex_A_20110907.ifc",
    },
    {
        "id": "BM-04",
        "name": "Building-Hvac.ifc",
        "schema": "IFC4",
        "category": "MEP / HVAC",
        "url": "https://raw.githubusercontent.com/buildingSMART/Certification-datasets/main/IFC%204.0.2.1%20(IFC%204%20ADD2%20TC1)/Simple-Scene/Building-Hvac.ifc",
    },
]


def run_benchmark(cache_dir: Path = DEFAULT_CACHE_DIR):
    cache_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        Panel(
            f"[bold cyan]debim Real-World IFC Benchmark Suite[/bold cyan]\n"
            f"[dim]Cache & Output Directory:[/dim] [yellow]{cache_dir}[/yellow]",
            title="[bold green]Benchmark Engine[/bold green]",
        )
    )

    table = Table(
        title="Benchmark Test Results",
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Model Name", style="bold", width=24)
    table.add_column("Category", width=16)
    table.add_column("IFC Size", justify="right", width=10)
    table.add_column("YAML Size", justify="right", width=10)
    table.add_column("Tokens", justify="right", width=9)
    table.add_column("Reduction", justify="right", width=10)
    table.add_column("Elements", justify="right", width=9)
    table.add_column("Concrete", justify="right", width=10)
    table.add_column("Status", width=10)

    for bm in BENCHMARK_MODELS:
        ifc_file = cache_dir / bm["name"]
        yaml_file = cache_dir / f"{Path(bm['name']).stem}.yaml"

        # 1. Download if missing
        if not ifc_file.exists():
            console.print(f"[dim]Downloading {bm['name']}...[/dim]")
            try:
                urllib.request.urlretrieve(bm["url"], str(ifc_file))
            except Exception as e:
                table.add_row(
                    bm["id"], bm["name"], bm["category"], "-", "-", "-", "-", "-", "-", f"[red]DL Fail: {e}[/red]"
                )
                continue

        ifc_size = ifc_file.stat().st_size
        ifc_size_str = f"{ifc_size / 1024:.1f} KB" if ifc_size < 1024 * 1024 else f"{ifc_size / (1024 * 1024):.2f} MB"

        # 2. Conversion
        try:
            manifest = import_ifc_to_manifest(ifc_file)

            import json
            import yaml
            data = json.loads(manifest.model_dump_json(by_alias=True, exclude_none=True))
            with open(yaml_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

            yaml_size = yaml_file.stat().st_size
            yaml_size_str = f"{yaml_size / 1024:.1f} KB"
            yaml_text = yaml_file.read_text(encoding="utf-8")
            approx_tokens = int(len(yaml_text) / 3.5)
            reduction_pct = (1.0 - (yaml_size / ifc_size)) * 100.0

            # 3. Validation & QTO
            resolved = resolve_manifest(manifest)
            qto = calculate_qto(resolved)
            concrete_str = f"{qto.total_concrete_volume:.2f} m3"

            status = "[bold green]PASS[/bold green]"
            table.add_row(
                bm["id"],
                bm["name"],
                bm["category"],
                ifc_size_str,
                yaml_size_str,
                f"~{approx_tokens:,}",
                f"{reduction_pct:.1f}%",
                str(len(manifest.elements)),
                concrete_str,
                status,
            )
        except Exception as e:
            table.add_row(
                bm["id"],
                bm["name"],
                bm["category"],
                ifc_size_str,
                "-",
                "-",
                "-",
                "-",
                "-",
                f"[bold red]FAIL: {e}[/bold red]",
            )

    console.print(table)


if __name__ == "__main__":
    run_benchmark()
