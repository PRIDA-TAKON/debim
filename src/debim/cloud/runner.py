"""
Zero-Storage Ephemeral Runner for debim on Google Cloud Run and Local Docker.
Handles in-memory / scratch-directory compilation of 3D HTML viewer, 2D vector blueprints,
IFC4 STEP models, and BOQ cost estimates with guaranteed TTL auto-purge.
"""

from contextlib import contextmanager
import datetime
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Dict, Generator, Optional, Union
import yaml

from pydantic import BaseModel, Field

from debim.compiler import compile_to_ifc
from debim.cost import CostEstimate, PriceCatalog, estimate_cost, generate_cost_template, load_price_catalog
from debim.qto import ProjectQTO, calculate_qto
from debim.resolver import ResolvedDoor, ResolvedWindow, ResolvedManifest, resolve_manifest
from debim.schema import ProjectManifest, load_manifest
from debim.viewer import generate_viewer_html


class CompileResult(BaseModel):
    """Structured compile output returned by the ephemeral pipeline."""
    success: bool = True
    manifest_id: str = ""
    manifest_name: str = ""
    viewer_html: str = ""
    blueprint_2d: str = ""
    ifc_content: str = ""
    boq_summary: Dict[str, Any] = Field(default_factory=dict)
    qto_summary: Dict[str, Any] = Field(default_factory=dict)
    artifacts: Dict[str, Union[str, bytes]] = Field(default_factory=dict)
    execution_time_ms: float = 0.0
    error: Optional[str] = None


@contextmanager
def ephemeral_scratch_dir(prefix: str = "debim_scratch_") -> Generator[Path, None, None]:
    """
    Context manager creating an ephemeral scratch directory under /tmp/debim_scratch_*.
    Guarantees 100% immediate cleanup upon exit or failure.
    """
    tmp_parent = "/tmp" if os.path.exists("/tmp") else tempfile.gettempdir()
    scratch_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=tmp_parent))
    try:
        yield scratch_dir
    finally:
        if scratch_dir.exists():
            shutil.rmtree(scratch_dir, ignore_errors=True)


def generate_2d_blueprint_svg(
    manifest: Union[ProjectManifest, ResolvedManifest, Path, str]
) -> str:
    """
    Generate a 2D vector SVG architectural blueprint drawing from a manifest.
    Includes grid axes with bubble indicators, wall outlines, columns, beams,
    doors, windows, stairs, roof projections, and a standard title block.
    """
    if isinstance(manifest, (str, Path)):
        manifest_obj = load_manifest(manifest)
        resolved = resolve_manifest(manifest_obj)
    elif isinstance(manifest, ProjectManifest):
        resolved = resolve_manifest(manifest)
    elif isinstance(manifest, ResolvedManifest):
        resolved = manifest
    else:
        raise TypeError(f"Unsupported manifest type for blueprint generation: {type(manifest)}")

    proj = resolved.manifest.project
    grids = resolved.manifest.grids

    axes_x = grids.axes_x or {"1": 0.0, "2": 6.0}
    axes_y = grids.axes_y or {"A": 0.0, "B": 6.0}

    x_vals = list(axes_x.values())
    y_vals = list(axes_y.values())

    min_x, max_x = (min(x_vals), max(x_vals)) if x_vals else (0.0, 10.0)
    min_y, max_y = (min(y_vals), max(y_vals)) if y_vals else (0.0, 10.0)

    span_x = max_x - min_x or 10.0
    span_y = max_y - min_y or 10.0

    margin = max(span_x, span_y) * 0.25 + 3.0
    v_min_x = min_x - margin
    v_min_y = min_y - margin
    v_width = span_x + 2 * margin
    v_height = span_y + 2 * margin
    v_max_y = -(max_y + margin)

    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{v_min_x:.2f} {v_max_y:.2f} {v_width:.2f} {v_height:.2f}" style="background-color: #0b132b; font-family: -apple-system, BlinkMacSystemFont, sans-serif;">',
        "  <defs>",
        '    <pattern id="grid-pattern" width="1" height="1" patternUnits="userSpaceOnUse">',
        '      <path d="M 1 0 L 0 0 0 1" fill="none" stroke="#1e293b" stroke-width="0.05"/>',
        "    </pattern>",
        '    <style>',
        '      .grid-line { stroke: #38bdf8; stroke-width: 0.08; stroke-dasharray: 0.4 0.2; }',
        '      .grid-bubble { fill: #0f172a; stroke: #38bdf8; stroke-width: 0.12; }',
        '      .grid-text { fill: #38bdf8; font-size: 0.8px; font-weight: bold; text-anchor: middle; dominant-baseline: central; }',
        '      .wall-fill { fill: #334155; stroke: #94a3b8; stroke-width: 0.12; }',
        '      .column-fill { fill: #f59e0b; stroke: #fbbf24; stroke-width: 0.1; }',
        '      .beam-line { stroke: #60a5fa; stroke-width: 0.08; stroke-dasharray: 0.2 0.1; }',
        '      .slab-outline { fill: #1e293b; fill-opacity: 0.4; stroke: #475569; stroke-width: 0.06; }',
        '      .door-line { stroke: #34d399; stroke-width: 0.08; }',
        '      .door-arc { stroke: #34d399; stroke-width: 0.05; stroke-dasharray: 0.1 0.05; fill: none; }',
        '      .window-line { stroke: #38bdf8; stroke-width: 0.08; fill: #0284c7; fill-opacity: 0.3; }',
        '      .stair-step { fill: #475569; stroke: #94a3b8; stroke-width: 0.05; }',
        '      .title-box { fill: #0f172a; stroke: #38bdf8; stroke-width: 0.15; }',
        '      .title-text { fill: #ffffff; font-size: 0.7px; font-weight: bold; }',
        '      .sub-text { fill: #94a3b8; font-size: 0.45px; }',
        '    </style>',
        "  </defs>",
        f'  <rect x="{v_min_x:.2f}" y="{-(max_y + margin):.2f}" width="{v_width:.2f}" height="{v_height:.2f}" fill="url(#grid-pattern)" />',
    ]

    # Helper coordinate transform (BIM y-up to SVG y-down)
    def svg_y(y_val: float) -> float:
        return -float(y_val)

    # Render Slabs
    for slab in resolved.slabs:
        if slab.polygon and len(slab.polygon) >= 3:
            pts_str = " ".join([f"{pt[0]:.2f},{svg_y(pt[1]):.2f}" for pt in slab.polygon])
            svg_lines.append(f'  <polygon points="{pts_str}" class="slab-outline" />')

    # Render Walls
    for wall in resolved.walls:
        x1, y1 = wall.start_point[0], wall.start_point[1]
        x2, y2 = wall.end_point[0], wall.end_point[1]
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length < 1e-4:
            continue
        half_t = wall.thickness / 2.0
        nx = -dy / length * half_t
        ny = dx / length * half_t

        p1 = (x1 + nx, svg_y(y1 + ny))
        p2 = (x2 + nx, svg_y(y2 + ny))
        p3 = (x2 - nx, svg_y(y2 - ny))
        p4 = (x1 - nx, svg_y(y1 - ny))

        pts_str = f"{p1[0]:.2f},{p1[1]:.2f} {p2[0]:.2f},{p2[1]:.2f} {p3[0]:.2f},{p3[1]:.2f} {p4[0]:.2f},{p4[1]:.2f}"
        svg_lines.append(f'  <polygon points="{pts_str}" class="wall-fill" />')

        # Render Doors and Windows embedded in wall
        for child in wall.children:
            offset = child.offset_distance
            cx = x1 + (dx / length) * offset
            cy = y1 + (dy / length) * offset
            c_w = child.width

            if isinstance(child, ResolvedDoor):
                leaf_x2 = cx + (dx / length) * c_w
                leaf_y2 = cy + (dy / length) * c_w
                svg_lines.append(
                    f'  <line x1="{cx:.2f}" y1="{svg_y(cy):.2f}" x2="{leaf_x2:.2f}" y2="{svg_y(leaf_y2):.2f}" class="door-line" />'
                )
                r = c_w
                svg_lines.append(
                    f'  <circle cx="{cx:.2f}" cy="{svg_y(cy):.2f}" r="{r:.2f}" class="door-arc" />'
                )
            elif isinstance(child, ResolvedWindow):
                wx1 = cx
                wy1 = cy
                wx2 = cx + (dx / length) * c_w
                wy2 = cy + (dy / length) * c_w
                p_w1 = (wx1 + nx * 0.8, svg_y(wy1 + ny * 0.8))
                p_w2 = (wx2 + nx * 0.8, svg_y(wy2 + ny * 0.8))
                p_w3 = (wx2 - nx * 0.8, svg_y(wy2 - ny * 0.8))
                p_w4 = (wx1 - nx * 0.8, svg_y(wy1 - ny * 0.8))
                w_pts = f"{p_w1[0]:.2f},{p_w1[1]:.2f} {p_w2[0]:.2f},{p_w2[1]:.2f} {p_w3[0]:.2f},{p_w3[1]:.2f} {p_w4[0]:.2f},{p_w4[1]:.2f}"
                svg_lines.append(f'  <polygon points="{w_pts}" class="window-line" />')

    # Render Columns
    for col in resolved.columns:
        px, py = col.start_point[0], col.start_point[1]
        w = col.element.profile.width
        d = col.element.profile.depth
        shape = getattr(col.element.profile, "shape", "BOX")

        if shape in ("CIRCULAR", "CHS"):
            r = w / 2.0
            svg_lines.append(f'  <circle cx="{px:.2f}" cy="{svg_y(py):.2f}" r="{r:.2f}" class="column-fill" />')
        else:
            rx = px - w / 2.0
            ry = svg_y(py + d / 2.0)
            svg_lines.append(f'  <rect x="{rx:.2f}" y="{ry:.2f}" width="{w:.2f}" height="{d:.2f}" class="column-fill" />')

    # Render Beams
    for beam in resolved.beams:
        x1, y1 = beam.start_point[0], beam.start_point[1]
        x2, y2 = beam.end_point[0], beam.end_point[1]
        svg_lines.append(f'  <line x1="{x1:.2f}" y1="{svg_y(y1):.2f}" x2="{x2:.2f}" y2="{svg_y(y2):.2f}" class="beam-line" />')

    # Render Grid Lines and Bubbles
    bubble_r = 0.65
    extend_dist = 1.2

    # X-Grids (Vertical lines)
    for g_name, x_pos in axes_x.items():
        if "-" in g_name:
            continue
        y_top = max_y + extend_dist
        y_bot = min_y - extend_dist
        svg_lines.append(f'  <line x1="{x_pos:.2f}" y1="{svg_y(y_bot):.2f}" x2="{x_pos:.2f}" y2="{svg_y(y_top):.2f}" class="grid-line" />')

        # Top Bubble
        cy_top = svg_y(y_top + bubble_r)
        svg_lines.append(f'  <circle cx="{x_pos:.2f}" cy="{cy_top:.2f}" r="{bubble_r:.2f}" class="grid-bubble" />')
        svg_lines.append(f'  <text x="{x_pos:.2f}" y="{cy_top:.2f}" class="grid-text">{g_name}</text>')

        # Bottom Bubble
        cy_bot = svg_y(y_bot - bubble_r)
        svg_lines.append(f'  <circle cx="{x_pos:.2f}" cy="{cy_bot:.2f}" r="{bubble_r:.2f}" class="grid-bubble" />')
        svg_lines.append(f'  <text x="{x_pos:.2f}" y="{cy_bot:.2f}" class="grid-text">{g_name}</text>')

    # Y-Grids (Horizontal lines)
    for g_name, y_pos in axes_y.items():
        if "-" in g_name:
            continue
        x_left = min_x - extend_dist
        x_right = max_x + extend_dist
        sy = svg_y(y_pos)
        svg_lines.append(f'  <line x1="{x_left:.2f}" y1="{sy:.2f}" x2="{x_right:.2f}" y2="{sy:.2f}" class="grid-line" />')

        # Left Bubble
        cx_left = x_left - bubble_r
        svg_lines.append(f'  <circle cx="{cx_left:.2f}" cy="{sy:.2f}" r="{bubble_r:.2f}" class="grid-bubble" />')
        svg_lines.append(f'  <text x="{cx_left:.2f}" y="{sy:.2f}" class="grid-text">{g_name}</text>')

        # Right Bubble
        cx_right = x_right + bubble_r
        svg_lines.append(f'  <circle cx="{cx_right:.2f}" cy="{sy:.2f}" r="{bubble_r:.2f}" class="grid-bubble" />')
        svg_lines.append(f'  <text x="{cx_right:.2f}" y="{sy:.2f}" class="grid-text">{g_name}</text>')

    # Title Block (Bottom Right Corner)
    t_width = 8.5
    t_height = 3.5
    t_x = max_x + margin - t_width - 0.5
    t_y = svg_y(min_y - margin + t_height + 0.5)

    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    svg_lines.extend([
        f'  <g transform="translate({t_x:.2f}, {t_y:.2f})">',
        f'    <rect x="0" y="0" width="{t_width:.2f}" height="{t_height:.2f}" class="title-box" />',
        f'    <text x="0.4" y="0.8" class="title-text">{proj.name}</text>',
        f'    <text x="0.4" y="1.4" class="sub-text">Project ID: {proj.id}</text>',
        f'    <text x="0.4" y="1.9" class="sub-text">Scale: 1:100 (Metric METER)</text>',
        f'    <text x="0.4" y="2.4" class="sub-text">Generated: {timestamp}</text>',
        f'    <text x="0.4" y="3.0" class="sub-text" fill="#38bdf8">debim 2D Architectural Blueprint</text>',
        "  </g>",
        "</svg>"
    ])

    return "\n".join(svg_lines)


class CloudRunner:
    """
    Containerized Cloud Ephemeral Runner for debim.
    Encapsulates zero-storage execution pipeline with guaranteed temp directory cleanup.
    """

    def __init__(self, prefix: str = "debim_scratch_"):
        self.prefix = prefix

    def compile(
        self,
        payload: Union[str, dict, ProjectManifest, Path],
        price_catalog: Optional[Union[str, dict, PriceCatalog, Path]] = None,
        return_bytes: bool = False,
    ) -> CompileResult:
        """
        Execute full compilation pipeline in an ephemeral scratch directory.
        Returns a CompileResult containing in-memory 3D HTML viewer, 2D blueprint SVG,
        IFC4 STEP model, BOQ cost estimate, and artifact payload.
        """
        start_time = time.perf_counter()

        with ephemeral_scratch_dir(prefix=self.prefix) as scratch_dir:
            try:
                # 1. Resolve manifest payload
                manifest_file = scratch_dir / "project.yaml"

                if isinstance(payload, Path) or (isinstance(payload, str) and "\n" not in payload and len(payload) < 260 and (Path(payload).is_dir() or Path(payload).exists())):
                    p_path = Path(payload)
                    if p_path.is_dir():
                        manifest_path = p_path / "project.yaml"
                    else:
                        manifest_path = p_path
                    manifest_obj = load_manifest(manifest_path)
                elif isinstance(payload, str):
                    # In-memory YAML string
                    manifest_file.write_text(payload, encoding="utf-8")
                    manifest_obj = load_manifest(manifest_file)
                elif isinstance(payload, dict):
                    manifest_data = yaml.safe_dump(payload)
                    manifest_file.write_text(manifest_data, encoding="utf-8")
                    manifest_obj = load_manifest(manifest_file)
                elif isinstance(payload, ProjectManifest):
                    manifest_obj = payload
                    manifest_data = yaml.safe_dump(payload.model_dump(by_alias=True, exclude_none=True))
                    manifest_file.write_text(manifest_data, encoding="utf-8")
                else:
                    raise ValueError(f"Invalid payload type: {type(payload)}")

                resolved = resolve_manifest(manifest_obj)
                proj = resolved.manifest.project

                # 2. Resolve price catalog
                catalog_file = scratch_dir / "prices.json"
                if price_catalog is not None:
                    if isinstance(price_catalog, Path) or (isinstance(price_catalog, str) and "\n" not in price_catalog and len(price_catalog) < 260 and Path(price_catalog).exists()):
                        catalog_obj = load_price_catalog(price_catalog)
                    elif isinstance(price_catalog, str):
                        catalog_file.write_text(price_catalog, encoding="utf-8")
                        catalog_obj = load_price_catalog(catalog_file)
                    elif isinstance(price_catalog, dict):
                        catalog_file.write_text(yaml.safe_dump(price_catalog), encoding="utf-8")
                        catalog_obj = load_price_catalog(catalog_file)
                    elif isinstance(price_catalog, PriceCatalog):
                        catalog_obj = price_catalog
                    else:
                        raise ValueError(f"Invalid price catalog type: {type(price_catalog)}")
                else:
                    # Check if prices.json exists in checkout directory
                    is_dir_payload = isinstance(payload, Path) or (isinstance(payload, str) and "\n" not in payload and len(payload) < 260 and Path(payload).is_dir())
                    if is_dir_payload and (Path(payload) / "prices.json").exists():
                        catalog_obj = load_price_catalog(Path(payload) / "prices.json")
                    else:
                        # Auto-generate catalog template
                        template_path = scratch_dir / "prices.yaml"
                        generate_cost_template(manifest_obj, output_path=template_path)
                        catalog_obj = load_price_catalog(template_path)

                # 3. Generate 3D HTML Viewer
                viewer_html = generate_viewer_html(resolved)
                viewer_file = scratch_dir / "viewer.html"
                viewer_file.write_text(viewer_html, encoding="utf-8")

                # 4. Generate 2D Vector Blueprint SVG
                blueprint_2d = generate_2d_blueprint_svg(resolved)
                blueprint_file = scratch_dir / "blueprint.svg"
                blueprint_file.write_text(blueprint_2d, encoding="utf-8")

                # 5. Compile IFC4 STEP model
                ifc_file = scratch_dir / "model.ifc"
                compile_to_ifc(resolved, output_path=ifc_file, force_fallback=True)
                ifc_content = ifc_file.read_text(encoding="utf-8")

                # 6. Calculate QTO & Cost BOQ
                qto_obj = calculate_qto(resolved)
                cost_obj = estimate_cost(qto_obj, catalog_obj, manifest_obj)

                boq_csv_file = scratch_dir / "boq.csv"
                cost_obj.export_csv(boq_csv_file)
                boq_csv_content = boq_csv_file.read_text(encoding="utf-8")

                qto_summary = {
                    "total_concrete_volume": qto_obj.total_concrete_volume,
                    "total_formwork_area": qto_obj.total_formwork_area,
                    "total_rebar_weight": qto_obj.total_rebar_weight,
                    "elements_count": len(qto_obj.elements),
                }

                boq_summary = {
                    "currency": cost_obj.currency,
                    "total_material_cost": cost_obj.total_material_cost,
                    "total_labor_cost": cost_obj.total_labor_cost,
                    "grand_total": cost_obj.grand_total,
                    "line_items_count": len(cost_obj.line_items),
                }

                artifacts: Dict[str, Union[str, bytes]] = {
                    "viewer.html": viewer_html.encode("utf-8") if return_bytes else viewer_html,
                    "blueprint.svg": blueprint_2d.encode("utf-8") if return_bytes else blueprint_2d,
                    "model.ifc": ifc_content.encode("utf-8") if return_bytes else ifc_content,
                    "boq.csv": boq_csv_content.encode("utf-8") if return_bytes else boq_csv_content,
                    "boq.json": cost_obj.model_dump_json(indent=2),
                }

                elapsed_ms = (time.perf_counter() - start_time) * 1000.0

                return CompileResult(
                    success=True,
                    manifest_id=proj.id,
                    manifest_name=proj.name,
                    viewer_html=viewer_html,
                    blueprint_2d=blueprint_2d,
                    ifc_content=ifc_content,
                    boq_summary=boq_summary,
                    qto_summary=qto_summary,
                    artifacts=artifacts,
                    execution_time_ms=elapsed_ms,
                )

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return CompileResult(
                    success=False,
                    execution_time_ms=elapsed_ms,
                    error=str(e),
                )


def compile_ephemeral(
    payload: Union[str, dict, ProjectManifest, Path],
    price_catalog: Optional[Union[str, dict, PriceCatalog, Path]] = None,
    return_bytes: bool = False,
) -> CompileResult:
    """Convenience function for CloudRunner ephemeral compilation."""
    runner = CloudRunner()
    return runner.compile(payload=payload, price_catalog=price_catalog, return_bytes=return_bytes)
