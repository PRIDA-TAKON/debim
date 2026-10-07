"""
2D SVG Architectural Sheet Builder Engine for debim.
Converts 2D projection primitives into production-ready SVG and print-ready sheets
using CSS Paged Media, Thai Google Fonts, Annotative Scaling, Dimensions, and Title Blocks.
"""

from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
import yaml

from pydantic import BaseModel, ConfigDict, Field, field_validator

from debim.draw.projection import (
    CutElement,
    CutPlaneResult,
    GridLine2D,
    ProjectionElement,
    slice_storey,
)
from debim.resolver import ResolvedManifest, resolve_manifest
from debim.schema import ProjectManifest, load_manifest

# Standard paper sizes in millimeters (Landscape: width, height)
PAPER_SIZES_MM: Dict[str, Tuple[float, float]] = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
}


class VisibilityFilter(BaseModel):
    """Visibility filters for sheet elements."""
    show_grid: bool = True
    show_dimensions: bool = True
    show_cut_heavy: bool = True
    show_cut_medium: bool = True
    show_projection: bool = True
    show_title_block: bool = True
    show_sheet_index: bool = True
    show_room_tags: bool = True


class SheetIndexItem(BaseModel):
    """Entry for automated Sheet Index table."""
    sheet_no: str
    title: str
    scale: str = "1:100"
    revision: str = "01"


class CropBox(BaseModel):
    """2D crop box bounds in model coordinates (meters)."""
    min_x: float
    min_y: float
    max_x: float
    max_y: float


class SheetConfig(BaseModel):
    """Sheet specification model."""
    id: str = "A-101"
    title: str = "Ground Floor Plan"
    paper_size: Literal["A4", "A3", "A2", "A1", "A0"] = "A3"
    orientation: Literal["landscape", "portrait"] = "landscape"
    scale: int = 100  # Scale ratio 1:S e.g. 100 for 1:100, 50 for 1:50
    storey_id: Optional[str] = None
    cut_offset_z: float = 1.20
    crop: Optional[Union[CropBox, Dict[str, float], Tuple[float, float, float, float], List[float]]] = None
    visibility: VisibilityFilter = Field(default_factory=VisibilityFilter)
    margin_mm: float = 10.0
    project_name: Optional[str] = None
    client_name: str = "N/A"
    architect_name: str = "debim Engine"
    date: Optional[str] = None
    revision: str = "01"
    sheet_index: List[SheetIndexItem] = Field(default_factory=list)

    @field_validator("crop", mode="before")
    @classmethod
    def parse_crop_box(cls, v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, (tuple, list)) and len(v) >= 4:
            return CropBox(min_x=float(v[0]), min_y=float(v[1]), max_x=float(v[2]), max_y=float(v[3]))
        if isinstance(v, dict):
            return CropBox(
                min_x=float(v.get("min_x", 0.0)),
                min_y=float(v.get("min_y", 0.0)),
                max_x=float(v.get("max_x", 10.0)),
                max_y=float(v.get("max_y", 10.0)),
            )
        return v

    @field_validator("visibility", mode="before")
    @classmethod
    def parse_visibility(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return VisibilityFilter(**v)
        if isinstance(v, VisibilityFilter):
            return v
        return VisibilityFilter()

    @field_validator("sheet_index", mode="before")
    @classmethod
    def parse_sheet_index(cls, v: Any) -> Any:
        if isinstance(v, list):
            res = []
            for item in v:
                if isinstance(item, dict):
                    res.append(SheetIndexItem(**item))
                elif isinstance(item, SheetIndexItem):
                    res.append(item)
            return res
        return []

    def get_paper_dimensions_mm(self) -> Tuple[float, float]:
        """Get (width, height) in millimeters for paper size and orientation."""
        base_w, base_h = PAPER_SIZES_MM.get(self.paper_size.upper(), (420.0, 297.0))
        if self.orientation.lower() == "portrait":
            return (min(base_w, base_h), max(base_w, base_h))
        else:
            return (max(base_w, base_h), min(base_w, base_h))


def load_sheet_config(path_or_data: Union[Path, str, dict, SheetConfig]) -> SheetConfig:
    """Load SheetConfig from a YAML file path, dict, or existing model."""
    if isinstance(path_or_data, SheetConfig):
        return path_or_data
    if isinstance(path_or_data, dict):
        return SheetConfig.model_validate(path_or_data)
    if isinstance(path_or_data, (str, Path)):
        p = Path(path_or_data)
        if p.exists() and p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return SheetConfig.model_validate(data)
        elif isinstance(path_or_data, str) and "\n" in path_or_data:
            data = yaml.safe_load(path_or_data) or {}
            return SheetConfig.model_validate(data)
    raise ValueError(f"Unable to parse SheetConfig from: {type(path_or_data)}")


def _get_embedded_css() -> str:
    """Load stylesheet from src/debim/draw/styles/sheet.css."""
    css_path = Path(__file__).parent / "styles" / "sheet.css"
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return "/* Fallback Sheet CSS */"


class SheetRenderer:
    """
    2D Architectural Sheet Rendering Engine.
    Converts 2D projection primitives into production-ready SVG and PDF-ready sheets.
    """

    def __init__(
        self,
        manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
        sheet_config: Optional[Union[SheetConfig, dict, Path, str]] = None,
    ):
        if isinstance(manifest_or_resolved, (str, Path)):
            manifest_path = Path(manifest_or_resolved)
            if manifest_path.exists():
                manifest_obj = load_manifest(manifest_path)
                self.resolved = resolve_manifest(manifest_obj)
            else:
                raise FileNotFoundError(f"Manifest path not found: {manifest_path}")
        elif isinstance(manifest_or_resolved, ProjectManifest):
            self.resolved = resolve_manifest(manifest_or_resolved)
        elif isinstance(manifest_or_resolved, ResolvedManifest):
            self.resolved = manifest_or_resolved
        else:
            raise TypeError(f"Invalid manifest type: {type(manifest_or_resolved)}")

        if sheet_config is None:
            self.config = SheetConfig()
        else:
            self.config = load_sheet_config(sheet_config)

    def render_svg(self) -> str:
        """Full SVG sheet DOM generator."""
        cfg = self.config
        manifest = self.resolved.manifest
        proj = manifest.project

        # 1. Determine Storey ID
        storey_id = cfg.storey_id
        if not storey_id:
            if manifest.spatial_structure.storeys:
                ground_storeys = [s for s in manifest.spatial_structure.storeys if s.elevation >= 0.0]
                if ground_storeys:
                    storey_id = ground_storeys[0].id
                else:
                    storey_id = manifest.spatial_structure.storeys[0].id
            else:
                raise ValueError("No storeys defined in project manifest.")

        # 2. Slice Storey Geometry via debim.draw.projection
        cut_result: CutPlaneResult = slice_storey(self.resolved, storey_id, cut_offset_z=cfg.cut_offset_z)

        # 3. Determine Paper Dimensions & Layout Geometry (mm)
        paper_w, paper_h = cfg.get_paper_dimensions_mm()
        margin = cfg.margin_mm

        # Layout Areas:
        printable_x = margin
        printable_y = margin
        printable_w = paper_w - 2 * margin
        printable_h = paper_h - 2 * margin

        # Right Title Block Width & Area (if enabled)
        title_block_width = 75.0 if printable_w >= 300.0 else 55.0
        if cfg.visibility.show_title_block:
            drawing_w = printable_w - title_block_width - 5.0
            title_x = printable_x + printable_w - title_block_width
            title_y = printable_y
            title_h = printable_h
        else:
            drawing_w = printable_w
            title_x = 0.0
            title_y = 0.0
            title_h = 0.0

        drawing_h = printable_h
        drawing_cx = printable_x + drawing_w / 2.0
        drawing_cy = printable_y + drawing_h / 2.0

        # 4. Model Bounds & Crop Box
        if cfg.crop:
            if isinstance(cfg.crop, CropBox):
                cb = cfg.crop
            else:
                cb = CropBox.model_validate(cfg.crop)
            min_x, min_y, max_x, max_y = cb.min_x, cb.min_y, cb.max_x, cb.max_y
        else:
            min_x, min_y, max_x, max_y = cut_result.bounds

        model_cx = (min_x + max_x) / 2.0
        model_cy = (min_y + max_y) / 2.0

        # Coordinate Transformer instance
        transformer = CoordinateTransformer(
            model_center=(model_cx, model_cy),
            viewport_center=(drawing_cx, drawing_cy),
            scale=cfg.scale,
        )

        # Project Name
        proj_name = cfg.project_name or proj.name
        date_str = cfg.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 5. Build SVG Elements
        embedded_css = _get_embedded_css()

        svg_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {paper_w:.1f} {paper_h:.1f}" width="{paper_w:.1f}mm" height="{paper_h:.1f}mm">',
            '  <defs>',
            '    <style type="text/css">',
            f'{embedded_css}',
            '    </style>',
            '  </defs>',
            '  <!-- Background -->',
            f'  <rect x="0" y="0" width="{paper_w:.1f}" height="{paper_h:.1f}" fill="#ffffff" />',
            '  <!-- Outer Sheet Border & Margin -->',
            f'  <rect x="{printable_x:.1f}" y="{printable_y:.1f}" width="{printable_w:.1f}" height="{printable_h:.1f}" class="sheet-border" />',
        ]

        # Inner Margin Line
        inner_m = 2.0
        svg_lines.append(
            f'  <rect x="{printable_x + inner_m:.1f}" y="{printable_y + inner_m:.1f}" width="{printable_w - 2*inner_m:.1f}" height="{printable_h - 2*inner_m:.1f}" class="sheet-inner-border" />'
        )

        # Group for Model Geometry
        svg_lines.append('  <g id="drawing-viewport">')

        # 6. Render Low Projection Elements (.projection)
        if cfg.visibility.show_projection:
            svg_lines.append('    <!-- Projection Elements -->')
            for pe in cut_result.projection_elements:
                d_str = transformer.polygon_to_paper_path(pe.polygon_coords)
                if d_str:
                    svg_lines.append(
                        f'    <path d="{d_str}" class="projection" fill-rule="evenodd" data-tag="{pe.tag}" data-class="{pe.element_class}" />'
                    )

        # 7. Render Cut Medium Elements (.cut-medium)
        if cfg.visibility.show_cut_medium:
            svg_lines.append('    <!-- Cut Medium Elements -->')
            for ce in cut_result.medium_cut_elements:
                d_str = transformer.polygon_to_paper_path(ce.polygon_coords)
                if d_str:
                    svg_lines.append(
                        f'    <path d="{d_str}" class="cut-medium" fill-rule="evenodd" data-tag="{ce.tag}" data-class="{ce.element_class}" />'
                    )

        # 8. Render Cut Heavy Elements (.cut-heavy)
        if cfg.visibility.show_cut_heavy:
            svg_lines.append('    <!-- Cut Heavy Elements -->')
            for ce in cut_result.heavy_cut_elements:
                d_str = transformer.polygon_to_paper_path(ce.polygon_coords)
                if d_str:
                    svg_lines.append(
                        f'    <path d="{d_str}" class="cut-heavy" fill-rule="evenodd" data-tag="{ce.tag}" data-class="{ce.element_class}" />'
                    )

        # 9. Render Grid Lines & Bubbles (.grid-line, .grid-bubble, .grid-text)
        if cfg.visibility.show_grid:
            svg_lines.append('    <!-- Grid Lines & Bubbles -->')

            bubble_r_mm = 4.0

            x_grids = [g for g in cut_result.grid_lines if g.axis == "X" and "-" not in g.id]
            y_grids = [g for g in cut_result.grid_lines if g.axis == "Y" and "-" not in g.id]

            all_model_x = [g.position for g in x_grids] or [min_x, max_x]
            all_model_y = [g.position for g in y_grids] or [min_y, max_y]

            min_gx, max_gx = min(all_model_x), max(all_model_x)
            min_gy, max_gy = min(all_model_y), max(all_model_y)

            ext_m = 1.5
            y_top_m = max_gy + ext_m
            y_bot_m = min_gy - ext_m
            x_left_m = min_gx - ext_m
            x_right_m = max_gx + ext_m

            # Draw X Grids (Vertical lines)
            for g in x_grids:
                p_top = transformer.to_paper(g.position, y_top_m)
                p_bot = transformer.to_paper(g.position, y_bot_m)

                svg_lines.append(
                    f'    <line x1="{p_bot[0]}" y1="{p_bot[1]}" x2="{p_top[0]}" y2="{p_top[1]}" class="grid-line" />'
                )

                b_top_cy = p_top[1] - bubble_r_mm
                svg_lines.append(
                    f'    <circle cx="{p_top[0]}" cy="{b_top_cy:.2f}" r="{bubble_r_mm}" class="grid-bubble" />'
                )
                svg_lines.append(
                    f'    <text x="{p_top[0]}" y="{b_top_cy:.2f}" class="grid-text">{g.id}</text>'
                )

                b_bot_cy = p_bot[1] + bubble_r_mm
                svg_lines.append(
                    f'    <circle cx="{p_bot[0]}" cy="{b_bot_cy:.2f}" r="{bubble_r_mm}" class="grid-bubble" />'
                )
                svg_lines.append(
                    f'    <text x="{p_bot[0]}" y="{b_bot_cy:.2f}" class="grid-text">{g.id}</text>'
                )

            # Draw Y Grids (Horizontal lines)
            for g in y_grids:
                p_left = transformer.to_paper(x_left_m, g.position)
                p_right = transformer.to_paper(x_right_m, g.position)

                svg_lines.append(
                    f'    <line x1="{p_left[0]}" y1="{p_left[1]}" x2="{p_right[0]}" y2="{p_right[1]}" class="grid-line" />'
                )

                b_left_cx = p_left[0] - bubble_r_mm
                svg_lines.append(
                    f'    <circle cx="{b_left_cx:.2f}" cy="{p_left[1]}" r="{bubble_r_mm}" class="grid-bubble" />'
                )
                svg_lines.append(
                    f'    <text x="{b_left_cx:.2f}" y="{p_left[1]}" class="grid-text">{g.id}</text>'
                )

                b_right_cx = p_right[0] + bubble_r_mm
                svg_lines.append(
                    f'    <circle cx="{b_right_cx:.2f}" cy="{p_right[1]}" r="{bubble_r_mm}" class="grid-bubble" />'
                )
                svg_lines.append(
                    f'    <text x="{b_right_cx:.2f}" y="{p_right[1]}" class="grid-text">{g.id}</text>'
                )

        # 10. Render Automatic Dimensions (.dimension-line, .dimension-text, .text-mask)
        if cfg.visibility.show_dimensions and cfg.visibility.show_grid:
            svg_lines.append('    <!-- Automatic Dimensions -->')

            x_grids_sorted = sorted([g for g in cut_result.grid_lines if g.axis == "X" and "-" not in g.id], key=lambda g: g.position)
            y_grids_sorted = sorted([g for g in cut_result.grid_lines if g.axis == "Y" and "-" not in g.id], key=lambda g: g.position)

            tick_len_mm = 2.0

            # X-Axis Dimension Strings (above top grid bubbles)
            if len(x_grids_sorted) >= 2:
                dim_y_m = max_gy + ext_m + 1.2
                dim_y_p = transformer.to_paper(0, dim_y_m)[1]

                for i in range(len(x_grids_sorted) - 1):
                    g1, g2 = x_grids_sorted[i], x_grids_sorted[i + 1]
                    p1 = transformer.to_paper(g1.position, dim_y_m)
                    p2 = transformer.to_paper(g2.position, dim_y_m)
                    dist_m = abs(g2.position - g1.position)

                    svg_lines.append(
                        f'    <line x1="{p1[0]}" y1="{dim_y_p}" x2="{p2[0]}" y2="{dim_y_p}" class="dimension-line" />'
                    )

                    svg_lines.append(
                        f'    <line x1="{p1[0] - tick_len_mm/2}" y1="{dim_y_p + tick_len_mm/2}" x2="{p1[0] + tick_len_mm/2}" y2="{dim_y_p - tick_len_mm/2}" class="dimension-tick" />'
                    )
                    svg_lines.append(
                        f'    <line x1="{p2[0] - tick_len_mm/2}" y1="{dim_y_p + tick_len_mm/2}" x2="{p2[0] + tick_len_mm/2}" y2="{dim_y_p - tick_len_mm/2}" class="dimension-tick" />'
                    )

                    mid_x = (p1[0] + p2[0]) / 2.0
                    val_str = f"{dist_m:.2f}"
                    text_w_mm = len(val_str) * 2.2 + 2.0
                    text_h_mm = 2.8

                    svg_lines.append(
                        f'    <rect x="{mid_x - text_w_mm/2:.2f}" y="{dim_y_p - text_h_mm/2:.2f}" width="{text_w_mm:.2f}" height="{text_h_mm:.2f}" class="text-mask" />'
                    )
                    svg_lines.append(
                        f'    <text x="{mid_x:.2f}" y="{dim_y_p:.2f}" class="dimension-text">{val_str}</text>'
                    )

                # Overall Envelope Dimension (further above)
                dim_overall_y_m = dim_y_m + 1.2
                dim_overall_y_p = transformer.to_paper(0, dim_overall_y_m)[1]

                p_start = transformer.to_paper(x_grids_sorted[0].position, dim_overall_y_m)
                p_end = transformer.to_paper(x_grids_sorted[-1].position, dim_overall_y_m)
                total_dist_m = abs(x_grids_sorted[-1].position - x_grids_sorted[0].position)

                svg_lines.append(
                    f'    <line x1="{p_start[0]}" y1="{dim_overall_y_p}" x2="{p_end[0]}" y2="{dim_overall_y_p}" class="dimension-line" />'
                )
                svg_lines.append(
                    f'    <line x1="{p_start[0] - tick_len_mm/2}" y1="{dim_overall_y_p + tick_len_mm/2}" x2="{p_start[0] + tick_len_mm/2}" y2="{dim_overall_y_p - tick_len_mm/2}" class="dimension-tick" />'
                )
                svg_lines.append(
                    f'    <line x1="{p_end[0] - tick_len_mm/2}" y1="{dim_overall_y_p + tick_len_mm/2}" x2="{p_end[0] + tick_len_mm/2}" y2="{dim_overall_y_p - tick_len_mm/2}" class="dimension-tick" />'
                )

                mid_x_overall = (p_start[0] + p_end[0]) / 2.0
                val_overall_str = f"{total_dist_m:.2f}"
                text_w_overall = len(val_overall_str) * 2.2 + 2.0

                svg_lines.append(
                    f'    <rect x="{mid_x_overall - text_w_overall/2:.2f}" y="{dim_overall_y_p - text_h_mm/2:.2f}" width="{text_w_overall:.2f}" height="{text_h_mm:.2f}" class="text-mask" />'
                )
                svg_lines.append(
                    f'    <text x="{mid_x_overall:.2f}" y="{dim_overall_y_p:.2f}" class="dimension-text">{val_overall_str}</text>'
                )

            # Y-Axis Dimension Strings (left of left grid bubbles)
            if len(y_grids_sorted) >= 2:
                dim_x_m = min_gx - ext_m - 1.2
                dim_x_p = transformer.to_paper(dim_x_m, 0)[0]

                for i in range(len(y_grids_sorted) - 1):
                    g1, g2 = y_grids_sorted[i], y_grids_sorted[i + 1]
                    p1 = transformer.to_paper(dim_x_m, g1.position)
                    p2 = transformer.to_paper(dim_x_m, g2.position)
                    dist_m = abs(g2.position - g1.position)

                    svg_lines.append(
                        f'    <line x1="{dim_x_p}" y1="{p1[1]}" x2="{dim_x_p}" y2="{p2[1]}" class="dimension-line" />'
                    )
                    svg_lines.append(
                        f'    <line x1="{dim_x_p - tick_len_mm/2}" y1="{p1[1] + tick_len_mm/2}" x2="{dim_x_p + tick_len_mm/2}" y2="{p1[1] - tick_len_mm/2}" class="dimension-tick" />'
                    )
                    svg_lines.append(
                        f'    <line x1="{dim_x_p - tick_len_mm/2}" y1="{p2[1] + tick_len_mm/2}" x2="{dim_x_p + tick_len_mm/2}" y2="{p2[1] - tick_len_mm/2}" class="dimension-tick" />'
                    )

                    mid_y = (p1[1] + p2[1]) / 2.0
                    val_str = f"{dist_m:.2f}"
                    text_w_mm = len(val_str) * 2.2 + 2.0
                    text_h_mm = 2.8

                    svg_lines.append(
                        f'    <rect x="{dim_x_p - text_w_mm/2:.2f}" y="{mid_y - text_h_mm/2:.2f}" width="{text_w_mm:.2f}" height="{text_h_mm:.2f}" class="text-mask" />'
                    )
                    svg_lines.append(
                        f'    <text x="{dim_x_p:.2f}" y="{mid_y:.2f}" class="dimension-text">{val_str}</text>'
                    )

                # Overall Y Envelope Dimension
                dim_overall_x_m = dim_x_m - 1.2
                dim_overall_x_p = transformer.to_paper(dim_overall_x_m, 0)[0]

                p_start_y = transformer.to_paper(dim_overall_x_m, y_grids_sorted[0].position)
                p_end_y = transformer.to_paper(dim_overall_x_m, y_grids_sorted[-1].position)
                total_y_dist = abs(y_grids_sorted[-1].position - y_grids_sorted[0].position)

                svg_lines.append(
                    f'    <line x1="{dim_overall_x_p}" y1="{p_start_y[1]}" x2="{dim_overall_x_p}" y2="{p_end_y[1]}" class="dimension-line" />'
                )
                svg_lines.append(
                    f'    <line x1="{dim_overall_x_p - tick_len_mm/2}" y1="{p_start_y[1] + tick_len_mm/2}" x2="{dim_overall_x_p + tick_len_mm/2}" y2="{p_start_y[1] - tick_len_mm/2}" class="dimension-tick" />'
                )
                svg_lines.append(
                    f'    <line x1="{dim_overall_x_p - tick_len_mm/2}" y1="{p_end_y[1] + tick_len_mm/2}" x2="{dim_overall_x_p + tick_len_mm/2}" y2="{p_end_y[1] - tick_len_mm/2}" class="dimension-tick" />'
                )

                mid_y_overall = (p_start_y[1] + p_end_y[1]) / 2.0
                val_y_overall_str = f"{total_y_dist:.2f}"
                text_w_y_overall = len(val_y_overall_str) * 2.2 + 2.0

                svg_lines.append(
                    f'    <rect x="{dim_overall_x_p - text_w_y_overall/2:.2f}" y="{mid_y_overall - text_h_mm/2:.2f}" width="{text_w_y_overall:.2f}" height="{text_h_mm:.2f}" class="text-mask" />'
                )
                svg_lines.append(
                    f'    <text x="{dim_overall_x_p:.2f}" y="{mid_y_overall:.2f}" class="dimension-text">{val_y_overall_str}</text>'
                )

        # 11. Render Room Tags / Labels (.room-tag, .text-mask)
        if cfg.visibility.show_room_tags:
            svg_lines.append('    <!-- Room Tags / Storey Label -->')
            tag_p = transformer.to_paper(model_cx, model_cy)
            room_label = cut_result.storey_name or cut_result.storey_id
            text_w = len(room_label) * 2.8 + 4.0
            text_h = 4.5

            svg_lines.append(
                f'    <rect x="{tag_p[0] - text_w/2:.2f}" y="{tag_p[1] - text_h/2:.2f}" width="{text_w:.2f}" height="{text_h:.2f}" class="text-mask" />'
            )
            svg_lines.append(
                f'    <text x="{tag_p[0]:.2f}" y="{tag_p[1]:.2f}" class="room-tag">{room_label}</text>'
            )

        svg_lines.append('  </g> <!-- End drawing-viewport -->')

        # 12. Title Block & Sheet Index Table
        if cfg.visibility.show_title_block:
            svg_lines.append('  <!-- Standard Architectural Title Block -->')
            svg_lines.append(
                f'  <g id="title-block" transform="translate({title_x:.1f}, {title_y:.1f})">'
            )
            svg_lines.append(
                f'    <rect x="0" y="0" width="{title_block_width:.1f}" height="{title_h:.1f}" class="title-block-container" />'
            )

            curr_y = 10.0

            # Project Title Header
            svg_lines.append(
                f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">PROJECT / โครงการ</text>'
            )
            curr_y += 5.0
            svg_lines.append(
                f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-title">{proj_name}</text>'
            )
            curr_y += 7.0
            svg_lines.append(
                f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_block_width:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
            )
            curr_y += 6.0

            # Sheet Title
            svg_lines.append(
                f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">DRAWING TITLE / ชื่อแบบ</text>'
            )
            curr_y += 5.0
            svg_lines.append(
                f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-title">{cfg.title}</text>'
            )
            curr_y += 7.0
            svg_lines.append(
                f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_block_width:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
            )
            curr_y += 6.0

            # Details Grid: Sheet No, Scale, Date, Rev, Client
            details = [
                ("SHEET NO. / เลขที่แบบ", cfg.id),
                ("SCALE / มาตราส่วน", f"1:{cfg.scale}"),
                ("DATE / วันที่", date_str),
                ("REVISION / แก้ไขครั้งที่", cfg.revision),
                ("CLIENT / เจ้าของโครงการ", cfg.client_name),
                ("ARCHITECT / สถาปนิก", cfg.architect_name),
            ]

            for lbl, val in details:
                svg_lines.append(
                    f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">{lbl}</text>'
                )
                curr_y += 4.0
                svg_lines.append(
                    f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-text">{val}</text>'
                )
                curr_y += 5.0
                svg_lines.append(
                    f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_block_width:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
                )
                curr_y += 5.0

            # Sheet Index Table (if enabled & provided)
            if cfg.visibility.show_sheet_index and cfg.sheet_index:
                curr_y += 2.0
                svg_lines.append(
                    f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-title">SHEET INDEX /สารบัญแบบ</text>'
                )
                curr_y += 5.0

                # Table Header
                svg_lines.append(
                    f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-header">NO.</text>'
                )
                svg_lines.append(
                    f'    <text x="22.0" y="{curr_y:.1f}" class="sheet-index-header">TITLE</text>'
                )
                svg_lines.append(
                    f'    <text x="{title_block_width - 12.0:.1f}" y="{curr_y:.1f}" class="sheet-index-header">SCALE</text>'
                )
                curr_y += 3.0
                svg_lines.append(
                    f'    <line x1="5.0" y1="{curr_y:.1f}" x2="{title_block_width - 5.0:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
                )
                curr_y += 4.0

                for idx_item in cfg.sheet_index:
                    if curr_y > title_h - 10.0:
                        break
                    svg_lines.append(
                        f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-cell">{idx_item.sheet_no}</text>'
                    )
                    svg_lines.append(
                        f'    <text x="22.0" y="{curr_y:.1f}" class="sheet-index-cell">{idx_item.title[:20]}</text>'
                    )
                    svg_lines.append(
                        f'    <text x="{title_block_width - 12.0:.1f}" y="{curr_y:.1f}" class="sheet-index-cell">{idx_item.scale}</text>'
                    )
                    curr_y += 4.5

            # Footer debim Engine Tag
            svg_lines.append(
                f'    <text x="5.0" y="{title_h - 4.0:.1f}" class="title-block-label">GENERATED BY debim ARCHITECTURAL ENGINE</text>'
            )

            svg_lines.append('  </g> <!-- End title-block -->')

        svg_lines.append('</svg>')
        return "\n".join(svg_lines)

    def save_svg(self, output_path: Union[str, Path]) -> Path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        svg_content = self.render_svg()
        out_p.write_text(svg_content, encoding="utf-8")
        return out_p


class CoordinateTransformer:
    """Maps 2D BIM model coordinates (meters) to paper coordinates (millimeters)."""

    def __init__(
        self,
        model_center: Tuple[float, float],
        viewport_center: Tuple[float, float],
        scale: int,
    ):
        self.model_cx, self.model_cy = model_center
        self.viewport_cx, self.viewport_cy = viewport_center
        self.scale = scale
        # k = mm per meter = 1000.0 / scale
        self.k = 1000.0 / float(scale)

    def to_paper(self, x_m: float, y_m: float) -> Tuple[float, float]:
        """Convert model (x, y) in meters to paper (x, y) in mm."""
        x_p = self.viewport_cx + (x_m - self.model_cx) * self.k
        y_p = self.viewport_cy - (y_m - self.model_cy) * self.k
        return (round(x_p, 3), round(y_p, 3))

    def polygon_to_paper_path(self, polygon_coords: List[List[Tuple[float, float]]]) -> str:
        """Convert polygon ring coordinates to an SVG path string with fill-rule='evenodd'."""
        if not polygon_coords:
            return ""
        path_parts = []
        for ring in polygon_coords:
            if not ring:
                continue
            p0 = self.to_paper(ring[0][0], ring[0][1])
            ring_parts = [f"M {p0[0]},{p0[1]}"]
            for pt in ring[1:]:
                pp = self.to_paper(pt[0], pt[1])
                ring_parts.append(f"L {pp[0]},{pp[1]}")
            ring_parts.append("Z")
            path_parts.append(" ".join(ring_parts))
        return " ".join(path_parts)


def render_sheet(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    sheet_config: Optional[Union[SheetConfig, dict, Path, str]] = None,
) -> str:
    """Convenience function to render a single architectural SVG sheet."""
    renderer = SheetRenderer(manifest_or_resolved, sheet_config)
    return renderer.render_svg()


def render_sheet_set(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    sheets_dir_or_configs: Union[Path, str, List[Union[SheetConfig, dict, Path]]],
) -> List[Tuple[SheetConfig, str]]:
    """
    Render a full set of architectural sheets from sheet configs or a directory of YAML sheets.
    Returns list of (SheetConfig, svg_string) tuples.
    """
    if isinstance(manifest_or_resolved, (str, Path)):
        manifest_obj = load_manifest(manifest_or_resolved)
        resolved = resolve_manifest(manifest_obj)
    elif isinstance(manifest_or_resolved, ProjectManifest):
        resolved = resolve_manifest(manifest_or_resolved)
    else:
        resolved = manifest_or_resolved

    configs: List[SheetConfig] = []

    if isinstance(sheets_dir_or_configs, (str, Path)):
        p = Path(sheets_dir_or_configs)
        if p.is_dir():
            for yaml_file in sorted(p.glob("*.yaml")):
                configs.append(load_sheet_config(yaml_file))
            for yml_file in sorted(p.glob("*.yml")):
                configs.append(load_sheet_config(yml_file))
        elif p.is_file():
            configs.append(load_sheet_config(p))
    elif isinstance(sheets_dir_or_configs, list):
        for item in sheets_dir_or_configs:
            configs.append(load_sheet_config(item))

    # Auto populate sheet_index across set if not explicitly set
    sheet_index_items = [
        SheetIndexItem(
            sheet_no=cfg.id,
            title=cfg.title,
            scale=f"1:{cfg.scale}",
            revision=cfg.revision,
        )
        for cfg in configs
    ]

    results = []
    for cfg in configs:
        if not cfg.sheet_index:
            cfg.sheet_index = sheet_index_items
        renderer = SheetRenderer(resolved, cfg)
        svg_str = renderer.render_svg()
        results.append((cfg, svg_str))

    return results
