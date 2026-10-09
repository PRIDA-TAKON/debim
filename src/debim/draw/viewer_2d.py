"""
2D HTML Blueprint Viewer Exporter Engine for debim.
Generates standalone lightweight 2D HTML blueprint viewer decoupled from 3D WebGL runtime.
Provides collapsible sheet navigator drawer, pan & pinch-to-zoom, digital measurement ruler,
layer visibility toggles, and one-click native print styling.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from debim.draw.renderer import (
    SheetConfig,
    load_sheet_config,
    render_sheet_set,
)
from debim.resolver import ResolvedManifest, resolve_manifest
from debim.schema import ProjectManifest, load_manifest


def _load_template_html() -> str:
    """Load template HTML from src/debim/draw/templates/viewer_2d.html."""
    tmpl_path = Path(__file__).parent / "templates" / "viewer_2d.html"
    if tmpl_path.exists():
        return tmpl_path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"2D Viewer HTML template not found at {tmpl_path}")


def generate_2d_viewer_html(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    sheets_dir_or_configs: Optional[Union[Path, str, List[Union[SheetConfig, dict, Path]]]] = None,
) -> str:
    """
    Generate a self-contained, standalone 2D web viewer HTML string
    embedding compiled SVG architectural sheets with zero 3D runtime dependencies.
    """
    if isinstance(manifest_or_resolved, (str, Path)):
        manifest_path = Path(manifest_or_resolved)
        manifest_obj = load_manifest(manifest_path)
        resolved = resolve_manifest(manifest_obj)
        manifest_dir = manifest_path.parent if manifest_path.is_file() else manifest_path
    elif isinstance(manifest_or_resolved, ProjectManifest):
        manifest_obj = manifest_or_resolved
        resolved = resolve_manifest(manifest_obj)
        manifest_dir = Path(".")
    elif isinstance(manifest_or_resolved, ResolvedManifest):
        resolved = manifest_or_resolved
        manifest_obj = resolved.manifest
        manifest_dir = Path(".")
    else:
        raise TypeError(f"Unsupported manifest type: {type(manifest_or_resolved)}")

    # Determine sheets directory or configurations
    if sheets_dir_or_configs is None:
        local_sheets_dir = manifest_dir / "sheets"
        if local_sheets_dir.exists() and local_sheets_dir.is_dir():
            sheets_dir_or_configs = local_sheets_dir
        elif Path("sheets").exists() and Path("sheets").is_dir():
            sheets_dir_or_configs = Path("sheets")

    if sheets_dir_or_configs is None:
        # Fallback: auto-generate sheet configs for floor plans & default elevation views
        configs = []
        storeys = manifest_obj.spatial_structure.storeys or []
        if storeys:
            for idx, storey in enumerate(storeys):
                sheet_id = f"A-10{idx + 1}"
                configs.append(
                    SheetConfig(
                        id=sheet_id,
                        title=f"{storey.name} Plan",
                        storey_id=storey.id,
                        scale=100,
                        paper_size="A3",
                        orientation="landscape",
                    )
                )
        else:
            configs.append(SheetConfig(id="A-101", title="Floor Plan"))

        # Add default elevation sheets (A-201..A-204)
        elevation_specs = [
            ("A-201", "รูปด้าน 1 (Front Elevation)", "FRONT"),
            ("A-202", "รูปด้าน 2 (Rear Elevation)", "REAR"),
            ("A-203", "รูปด้าน 3 (Right Elevation)", "RIGHT"),
            ("A-204", "รูปด้าน 4 (Left Elevation)", "LEFT"),
        ]
        for elev_id, elev_title, elev_dir in elevation_specs:
            configs.append(
                SheetConfig(
                    id=elev_id,
                    title=elev_title,
                    view_type="ELEVATION",
                    elevation_direction=elev_dir,
                    scale=100,
                    paper_size="A3",
                    orientation="landscape",
                )
            )

        rendered_sheets = render_sheet_set(resolved, configs)
    else:
        rendered_sheets = render_sheet_set(resolved, sheets_dir_or_configs)

    sheets_data: List[Dict[str, Any]] = []
    for cfg, svg_str in rendered_sheets:
        paper_w, paper_h = cfg.get_paper_dimensions_mm()
        sheets_data.append(
            {
                "id": cfg.id,
                "title": cfg.title,
                "paper_size": cfg.paper_size,
                "orientation": cfg.orientation,
                "scale": cfg.scale,
                "paper_width_mm": paper_w,
                "paper_height_mm": paper_h,
                "svg_content": svg_str,
            }
        )

    template_html = _load_template_html()
    json_payload = json.dumps(sheets_data, ensure_ascii=False)

    html_content = template_html.replace("__PROJECT_NAME__", manifest_obj.project.name)
    html_content = html_content.replace("__PROJECT_ID__", manifest_obj.project.id)
    html_content = html_content.replace("__SHEETS_DATA_JSON__", json_payload)

    return html_content


def export_2d_viewer(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    output_path: Union[Path, str] = "dist/viewer_2d.html",
    sheets_dir_or_configs: Optional[Union[Path, str, List[Union[SheetConfig, dict, Path]]]] = None,
) -> Path:
    """
    Export 2D interactive HTML viewer to output file path.
    """
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    html_content = generate_2d_viewer_html(manifest_or_resolved, sheets_dir_or_configs)
    out_p.write_text(html_content, encoding="utf-8")
    return out_p
