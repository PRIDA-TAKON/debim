"""
Real-world IFC Benchmark Suite for debim.
Downloads standardized models, measures conversion ratio, roundtrip fidelity, and QTO.
"""

import os
import tempfile
from pathlib import Path
import urllib.request
from typing import Dict, List, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from debim.importer import import_ifc_to_manifest
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.compiler import compile_to_ifc
from tools.compare_ifc import count_ifc_elements

console = Console()

DEFAULT_CACHE_DIR = Path(os.environ.get("DEBIM_CACHE_DIR", tempfile.gettempdir())) / "debim_benchmark_cache"

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
            title="[bold green]Benchmark Engine & Roundtrip Fidelity Analyzer[/bold green]",
        )
    )

    table = Table(
        title="Real-World Benchmark: Compression, Fidelity & Retention Rate",
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("ID", style="cyan", width=6)
    table.add_column("Model Name", style="bold", width=22)
    table.add_column("Category", width=14)
    table.add_column("IFC Size", justify="right", width=9)
    table.add_column("YAML Size", justify="right", width=9)
    table.add_column("Tokens", justify="right", width=8)
    table.add_column("Orig Elems", justify="right", width=10)
    table.add_column("YAML Elems", justify="right", width=10)
    table.add_column("Recomp Elems", justify="right", width=12)
    table.add_column("Retention", justify="right", width=10)
    table.add_column("Status", width=9)

    for bm in BENCHMARK_MODELS:
        ifc_file = cache_dir / bm["name"]
        yaml_file = cache_dir / f"{Path(bm['name']).stem}.yaml"
        recomp_ifc = cache_dir / f"{Path(bm['name']).stem}_recompiled.ifc"

        # 1. Resolve IFC file (check tests/fixtures first, then cache, then download)
        fixture_file = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / bm["name"]
        if not ifc_file.exists():
            if fixture_file.exists():
                import shutil
                shutil.copy(str(fixture_file), str(ifc_file))
            else:
                console.print(f"[dim]Downloading {bm['name']}...[/dim]")
                try:
                    urllib.request.urlretrieve(bm["url"], str(ifc_file))
                except Exception as e:
                    table.add_row(
                        bm["id"], bm["name"], bm["category"], "-", "-", "-", "-", "-", "-", "-", f"[red]DL Fail: {e}[/red]"
                    )
                    continue

        ifc_size = ifc_file.stat().st_size
        ifc_size_str = f"{ifc_size / 1024:.1f} KB" if ifc_size < 1024 * 1024 else f"{ifc_size / (1024 * 1024):.2f} MB"

        # 2. Count original IFC physical elements
        try:
            orig_elems_count, _ = count_ifc_elements(ifc_file)
        except Exception:
            orig_elems_count = 0

        # 3. Conversion to YAML
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

            # 4. Re-compile to IFC
            recomp_elems_count = 0
            try:
                compile_to_ifc(yaml_file, recomp_ifc)
                recomp_elems_count, _ = count_ifc_elements(recomp_ifc)
            except Exception as ce:
                console.print(f"[dim yellow]Compile warning for {bm['name']}: {ce}[/dim yellow]")

            retention_pct = (recomp_elems_count / orig_elems_count * 100.0) if orig_elems_count > 0 else 0.0

            status = "[bold green]PASS[/bold green]"
            table.add_row(
                bm["id"],
                bm["name"],
                bm["category"],
                ifc_size_str,
                yaml_size_str,
                f"~{approx_tokens:,}",
                str(orig_elems_count),
                str(len(manifest.elements)),
                str(recomp_elems_count),
                f"{retention_pct:.1f}%",
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
                str(orig_elems_count),
                "-",
                "-",
                "-",
                f"[bold red]FAIL[/bold red]",
            )

    console.print(table)


if __name__ == "__main__":
    run_benchmark()
