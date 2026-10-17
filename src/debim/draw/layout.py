"""
Paper Space Layout Engine (A3/A2/A1) with Title Block & Dynamic Project Metadata for debim.
Handles pure vector paper space SVG generation and DXF paper space layout setup.
"""

from pathlib import Path
from typing import List, Optional, Tuple, Union

from debim.draw.dxf import export_2d_dxf
from debim.draw.renderer import (
    SheetConfig,
    SheetRenderer,
    render_sheet,
    render_sheet_set,
)
from debim.resolver import ResolvedManifest, resolve_manifest
from debim.schema import ProjectManifest, load_manifest


def export_paper_space_layout_svg(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    sheet_config: Optional[Union[SheetConfig, dict, Path, str]] = None,
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """
    Generate paper space layout vector SVG for a sheet configuration.
    If output_path is provided, writes to file.
    """
    svg_str = render_sheet(manifest_or_resolved, sheet_config)
    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(svg_str, encoding="utf-8")
    return svg_str


def export_paper_space_layout_set(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    sheets_dir_or_configs: Union[Path, str, List[Union[SheetConfig, dict, Path]]],
    output_dir: Optional[Union[str, Path]] = None,
) -> List[Tuple[SheetConfig, str]]:
    """
    Generate set of paper space layout vector SVGs with dynamic metadata and sheet numbering.
    """
    results = render_sheet_set(manifest_or_resolved, sheets_dir_or_configs)
    if output_dir:
        out_d = Path(output_dir)
        out_d.mkdir(parents=True, exist_ok=True)
        for cfg, svg_content in results:
            file_name = f"{cfg.id}_{cfg.title.replace(' ', '_')}.svg"
            (out_d / file_name).write_text(svg_content, encoding="utf-8")
    return results


def export_paper_space_layout_dxf(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    output_path: Union[str, Path],
    sheet_config: Optional[Union[SheetConfig, dict, Path, str]] = None,
) -> Path:
    """
    Export paper space layout to DXF with paper space viewport and paper boundary.
    """
    cfg = SheetConfig() if sheet_config is None else (
        sheet_config if isinstance(sheet_config, SheetConfig) else SheetConfig.model_validate(sheet_config)
    )
    return export_2d_dxf(
        manifest_or_resolved,
        output_path=output_path,
        storey_id=cfg.storey_id,
        cut_offset_z=cfg.cut_offset_z,
        units="mm",
    )
