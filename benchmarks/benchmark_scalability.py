"""
Scalability & AI Token Efficiency Benchmark Suite for debim.
Measures compilation throughput, peak RAM, and AI Context Window token savings
across large-scale synthetic models (1,000 to 10,000+ building elements).
"""

import math
import os
from pathlib import Path
import tempfile
import time
import tracemalloc
from typing import Any, Dict, List, Optional
import yaml

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from debim.compiler import compile_to_ifc
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import load_manifest

console = Console()

DEFAULT_SCALES = [100, 1000, 5000, 10000]


def generate_synthetic_project(num_elements: int, target_dir: Path) -> Dict[str, Path]:
    """
    Programmatically generates a synthetic BIM project with configurable scale.
    Creates both a modular project structure (project.yaml + includes) and a single monolithic.yaml.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    models_dir = target_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    # 1. Determine grid layout and storey count based on element scale
    # Aim for ~200-500 elements per storey file to model realistic modularity
    elems_per_storey = 250
    num_storeys = max(1, math.ceil(num_elements / elems_per_storey))

    grid_dim = max(4, math.ceil(math.sqrt(num_elements / num_storeys / 2)))

    storeys = []
    for i in range(1, num_storeys + 1):
        storeys.append({
            "id": f"L{i}",
            "name": f"Level {i}",
            "elevation": (i - 1) * 3.5,
            "height": 3.5,
        })

    axes_x = {str(k): float((k - 1) * 6.0) for k in range(1, grid_dim + 2)}
    axes_y = {chr(64 + k): float((k - 1) * 6.0) for k in range(1, grid_dim + 2)}

    materials = [
        {
            "id": "MAT_CONC",
            "name": "Structural Concrete 30MPa",
            "category": "concrete",
            "unit_cost_ref": "CONC-30MPA",
        },
        {
            "id": "MAT_STEEL",
            "name": "Structural Steel SS400",
            "category": "steel",
            "unit_cost_ref": "STEEL-SS400",
        },
        {
            "id": "MAT_PVC",
            "name": "PVC Pipe 8.5",
            "category": "plastic",
            "unit_cost_ref": "PVC-85",
        },
    ]

    # 2. Generate elements distributed across storeys and sub-files
    grid_x_keys = list(axes_x.keys())
    grid_y_keys = list(axes_y.keys())

    all_elements: List[Dict[str, Any]] = []
    modular_files: List[Path] = []

    element_types = [
        "IfcColumn",
        "IfcBeam",
        "IfcWall",
        "IfcSlab",
        "IfcPipeSegment",
        "IfcLightFixture",
        "IfcBuildingElementProxy",
    ]

    elem_idx = 0
    for s_idx, storey in enumerate(storeys):
        storey_id = storey["id"]
        next_storey_id = storeys[min(s_idx + 1, len(storeys) - 1)]["id"] if s_idx < len(storeys) - 1 else storey_id

        storey_elements: List[Dict[str, Any]] = []

        while len(all_elements) < num_elements and len(storey_elements) < elems_per_storey:
            elem_idx += 1
            e_type = element_types[elem_idx % len(element_types)]

            gx1 = grid_x_keys[(elem_idx) % len(grid_x_keys)]
            gy1 = grid_y_keys[(elem_idx // len(grid_x_keys)) % len(grid_y_keys)]
            gx2 = grid_x_keys[(elem_idx + 1) % len(grid_x_keys)]
            gy2 = grid_y_keys[((elem_idx + 1) // len(grid_x_keys)) % len(grid_y_keys)]

            if e_type == "IfcColumn":
                elem = {
                    "class": "IfcColumn",
                    "tag": f"COL-{storey_id}-{elem_idx}",
                    "material": "MAT_CONC",
                    "profile": {"shape": "BOX", "width": 0.4, "depth": 0.4},
                    "placement": {
                        "grid": [gx1, gy1],
                        "base_storey": storey_id,
                        "top_storey": next_storey_id if next_storey_id != storey_id else storey_id,
                        "offset_top": [0.0, 0.0, 3.5] if next_storey_id == storey_id else [0.0, 0.0, 0.0],
                    },
                }
            elif e_type == "IfcBeam":
                elem = {
                    "class": "IfcBeam",
                    "tag": f"BEAM-{storey_id}-{elem_idx}",
                    "material": "MAT_CONC",
                    "profile": {"shape": "BOX", "width": 0.25, "depth": 0.5},
                    "placement": {
                        "from_grid": [gx1, gy1],
                        "to_grid": [gx2, gy1],
                        "storey": storey_id,
                    },
                }
            elif e_type == "IfcWall":
                elem = {
                    "class": "IfcWall",
                    "tag": f"WALL-{storey_id}-{elem_idx}",
                    "material": "MAT_CONC",
                    "thickness": 0.2,
                    "height": 3.0,
                    "placement": {
                        "from_grid": [gx1, gy1],
                        "to_grid": [gx1, gy2],
                        "storey": storey_id,
                    },
                }
            elif e_type == "IfcSlab":
                elem = {
                    "class": "IfcSlab",
                    "tag": f"SLAB-{storey_id}-{elem_idx}",
                    "material": "MAT_CONC",
                    "thickness": 0.15,
                    "placement": {
                        "boundary": [[gx1, gy1], [gx2, gy1], [gx2, gy2], [gx1, gy2]],
                        "storey": storey_id,
                    },
                }
            elif e_type == "IfcPipeSegment":
                elem = {
                    "class": "IfcPipeSegment",
                    "tag": f"PIPE-{storey_id}-{elem_idx}",
                    "system_type": "COLD_WATER",
                    "material": "MAT_PVC",
                    "nominal_diameter": 0.05,
                    "placement": {
                        "from_grid": [gx1, gy1],
                        "to_grid": [gx2, gy1],
                        "storey": storey_id,
                        "from_offset": [0.0, 0.0, 2.8],
                        "to_offset": [0.0, 0.0, 2.8],
                    },
                }
            elif e_type == "IfcLightFixture":
                elem = {
                    "class": "IfcLightFixture",
                    "tag": f"LIGHT-{storey_id}-{elem_idx}",
                    "fixture_type": "DOWNLIGHT",
                    "wattage": 12.0,
                    "placement": {
                        "grid": [gx1, gy1],
                        "storey": storey_id,
                        "offset_z": 3.0,
                    },
                }
            else:
                elem = {
                    "class": "IfcBuildingElementProxy",
                    "ifc_class": "IfcEquipment",
                    "tag": f"PROXY-{storey_id}-{elem_idx}",
                    "material": "MAT_STEEL",
                    "geometry": {"box": [0.8, 0.8, 1.2]},
                    "placement": {
                        "grid": [gx1, gy1],
                        "storey": storey_id,
                        "offset_z": 0.0,
                    },
                }

            storey_elements.append(elem)
            all_elements.append(elem)

        # Save storey sub-file
        st_file = models_dir / f"storey_{s_idx + 1}.yaml"
        with open(st_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(storey_elements, f, sort_keys=False, allow_unicode=True)
        modular_files.append(st_file)

    # 3. Save main project.yaml (modular)
    project_manifest = {
        "schema": "IFC4-Minimal",
        "project": {
            "id": f"BENCH-{num_elements}",
            "name": f"Synthetic BIM Model ({num_elements:,} Elements)",
        },
        "spatial_structure": {"storeys": storeys},
        "grids": {"axes_x": axes_x, "axes_y": axes_y},
        "materials": materials,
        "includes": ["models/**/*.yaml"],
    }

    project_yaml_path = target_dir / "project.yaml"
    with open(project_yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(project_manifest, f, sort_keys=False, allow_unicode=True)

    # 4. Save monolithic.yaml
    monolithic_manifest = dict(project_manifest)
    del monolithic_manifest["includes"]
    monolithic_manifest["elements"] = all_elements

    monolithic_yaml_path = target_dir / "monolithic.yaml"
    with open(monolithic_yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(monolithic_manifest, f, sort_keys=False, allow_unicode=True)

    return {
        "project_yaml": project_yaml_path,
        "monolithic_yaml": monolithic_yaml_path,
        "first_storey_file": modular_files[0],
    }


def estimate_token_count(text: str) -> int:
    """Estimates LLM Context Window token count (1 token ~ 3.5 characters for YAML/code)."""
    return max(1, int(len(text) / 3.5))


def run_scalability_benchmark(
    scales: List[int] = DEFAULT_SCALES,
    cache_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Runs the scalability & token efficiency benchmark suite across configured element scales.
    Returns structured metrics list and displays a Rich table summary.
    """
    if cache_dir is None:
        temp_dir_obj = tempfile.TemporaryDirectory(prefix="debim_scalability_")
        work_dir = Path(temp_dir_obj.name)
    else:
        work_dir = cache_dir
        work_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        Panel(
            f"[bold cyan]debim Scalability & AI Token Efficiency Benchmark Suite[/bold cyan]\n"
            f"[dim]Work Directory:[/dim] [yellow]{work_dir}[/yellow]",
            title="[bold green]High-Performance Multi-Scale Compiler & Context Window Analyzer[/bold green]",
        )
    )

    results: List[Dict[str, Any]] = []

    table = Table(
        title="Scalability & AI Context Window Token Efficiency Benchmark Results",
        header_style="bold magenta",
        show_lines=True,
    )
    table.add_column("Elements", justify="right", style="cyan", width=10)
    table.add_column("Load/Parse", justify="right", width=11)
    table.add_column("Spatial Res", justify="right", width=11)
    table.add_column("QTO Calc", justify="right", width=11)
    table.add_column("IFC Compile", justify="right", width=11)
    table.add_column("Total Time", justify="right", style="bold green", width=11)
    table.add_column("Peak RAM", justify="right", style="yellow", width=10)
    table.add_column("Mono Tokens", justify="right", width=12)
    table.add_column("Edit Tokens", justify="right", width=11)
    table.add_column("Token Savings", justify="right", style="bold bright_green", width=14)

    for scale in scales:
        scale_dir = work_dir / f"scale_{scale}"
        paths = generate_synthetic_project(scale, scale_dir)

        project_yaml = paths["project_yaml"]
        monolithic_yaml = paths["monolithic_yaml"]
        single_subfile = paths["first_storey_file"]
        ifc_out = scale_dir / f"output_{scale}.ifc"

        # Token Metrics Calculation
        monolithic_text = monolithic_yaml.read_text(encoding="utf-8")
        monolithic_tokens = estimate_token_count(monolithic_text)

        single_file_text = single_subfile.read_text(encoding="utf-8")
        single_file_tokens = estimate_token_count(single_file_text)

        # Single element surgical edit token size estimate (~1 element snippet)
        first_elem_snippet = single_file_text.split("- class:")[1] if "- class:" in single_file_text else single_file_text[:200]
        surgical_edit_tokens = estimate_token_count(first_elem_snippet)

        token_savings_pct = (
            ((monolithic_tokens - surgical_edit_tokens) / monolithic_tokens) * 100.0
            if monolithic_tokens > 0
            else 0.0
        )

        # Performance & Memory Tracing
        tracemalloc.start()

        t0 = time.perf_counter()
        manifest = load_manifest(project_yaml)
        t_load = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        resolved = resolve_manifest(manifest)
        t_resolve = (time.perf_counter() - t1) * 1000.0

        t2 = time.perf_counter()
        qto = calculate_qto(resolved)
        t_qto = (time.perf_counter() - t2) * 1000.0

        t3 = time.perf_counter()
        compile_to_ifc(resolved, ifc_out, force_fallback=True)
        t_compile = (time.perf_counter() - t3) * 1000.0

        _, peak_mem_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mem_mb = peak_mem_bytes / (1024.0 * 1024.0)
        t_total = t_load + t_resolve + t_qto + t_compile

        metrics = {
            "scale": scale,
            "load_parse_ms": round(t_load, 2),
            "spatial_resolution_ms": round(t_resolve, 2),
            "qto_calc_ms": round(t_qto, 2),
            "ifc_compile_ms": round(t_compile, 2),
            "total_time_ms": round(t_total, 2),
            "peak_memory_mb": round(peak_mem_mb, 2),
            "monolithic_tokens": monolithic_tokens,
            "surgical_tokens": surgical_edit_tokens,
            "token_savings_pct": round(token_savings_pct, 2),
        }
        results.append(metrics)

        table.add_row(
            f"{scale:,}",
            f"{t_load:.1f} ms",
            f"{t_resolve:.1f} ms",
            f"{t_qto:.1f} ms",
            f"{t_compile:.1f} ms",
            f"{t_total:.1f} ms",
            f"{peak_mem_mb:.2f} MB",
            f"~{monolithic_tokens:,}",
            f"~{surgical_edit_tokens:,}",
            f"[bold green]{token_savings_pct:.2f}%[/bold green]",
        )

    console.print(table)
    return results


if __name__ == "__main__":
    run_scalability_benchmark()
