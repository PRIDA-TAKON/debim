"""
2D SVG Architectural Sheet Builder Engine for debim.
Converts 2D projection primitives (Floor Plans and Architectural Sections) into production-ready SVG
and print-ready sheets using CSS Paged Media, CAD Hatching, Thai Google Fonts,
Annotative Scaling, Level Dimensions, Section Callouts, and Title Blocks.
"""

from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
import yaml

from pydantic import BaseModel, ConfigDict, Field, field_validator

from debim.draw.elevation import (
    ElevationDirection,
    ElevationResult,
    project_2d_elevation,
)
from debim.draw.projection import (
    CutElement,
    CutPlaneResult,
    GridLine2D,
    ProjectionElement,
    slice_storey,
)
from debim.draw.section import (
    SectionCutElement,
    SectionCutPlaneResult,
    SectionProjectionElement,
    StoreyLevelMarker,
    slice_section,
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
    show_level_markers: bool = True
    show_section_callouts: bool = True


class SheetIndexItem(BaseModel):
    """Entry for automated Sheet Index table."""
    sheet_no: str
    title: str
    scale: str = "1:100"
    revision: str = "01"


class SignatureBoxConfig(BaseModel):
    """Signature / Stamp box area configuration."""
    enabled: bool = True
    title: str = "PROFESSIONAL STAMP & SIGNATURE"
    subtext: str = "Digital Signature & Seal Area"
    height_mm: float = 22.0


class TitleBlockField(BaseModel):
    """Custom professional or metadata field for Title Block."""
    label: str
    value: str
    subtext: Optional[str] = None


class TitleBlockConfig(BaseModel):
    """Declarative Title Block configuration."""
    enabled: bool = True
    layout: Literal["vertical_right", "horizontal_bottom", "corner_bottom_right"] = "vertical_right"
    width_mm: float = 75.0
    height_mm: float = 38.0
    fields: List[TitleBlockField] = Field(default_factory=list)
    show_sheet_index: bool = True
    show_notes: bool = True
    show_signature_box: bool = True
    signature_box: SignatureBoxConfig = Field(default_factory=SignatureBoxConfig)


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
    view_type: str = "FLOOR_PLAN"
    paper_size: Literal["A4", "A3", "A2", "A1", "A0"] = "A3"
    orientation: Literal["landscape", "portrait"] = "landscape"
    scale: int = 100  # Scale ratio 1:S e.g. 100 for 1:100, 50 for 1:50
    elevation_direction: Union[ElevationDirection, str] = "FRONT"
    storey_id: Optional[str] = None
    cut_offset_z: float = 1.20
    # Section specific parameters
    section_id: Optional[str] = "A-A"
    section_axis: Optional[Literal["X", "Y"]] = "Y"
    section_position: Optional[float] = None
    section_grid_id: Optional[str] = None
    crop: Optional[Union[CropBox, Dict[str, float], Tuple[float, float, float, float], List[float]]] = None
    visibility: VisibilityFilter = Field(default_factory=VisibilityFilter)
    margin_mm: float = 10.0
    margin_left_mm: Optional[float] = None
    margin_top_mm: Optional[float] = None
    margin_right_mm: Optional[float] = None
    margin_bottom_mm: Optional[float] = None
    binding_margin_enabled: bool = True
    binding_margin_mm: float = 20.0
    project_name: Optional[str] = None
    client_name: str = "N/A"
    architect_name: str = "debim Engine"
    date: Optional[str] = None
    revision: str = "01"
    total_sheets: Optional[int] = None
    title_block: TitleBlockConfig = Field(default_factory=TitleBlockConfig)
    sheet_index: List[SheetIndexItem] = Field(default_factory=list)

    @field_validator("title_block", mode="before")
    @classmethod
    def parse_title_block(cls, v: Any) -> Any:
        if isinstance(v, dict):
            return TitleBlockConfig.model_validate(v)
        if isinstance(v, TitleBlockConfig):
            return v
        return TitleBlockConfig()

    @field_validator("view_type", mode="before")
    @classmethod
    def normalize_view_type(cls, v: Any) -> str:
        if isinstance(v, str):
            v_upper = v.upper()
            if v_upper in ("PLAN", "FLOOR_PLAN"):
                return "FLOOR_PLAN"
            if v_upper in ("SECTION",):
                return "SECTION"
            if v_upper in ("ELEVATION",):
                return "ELEVATION"
            if v_upper in ("SCHEDULE", "DOOR_WINDOW_SCHEDULE", "DOOR_SCHEDULE", "WINDOW_SCHEDULE"):
                return "SCHEDULE"
            if v_upper in ("STRUCTURAL_DETAILS", "STRUCTURAL_SCHEDULE", "STRUCTURAL_DETAIL"):
                return "STRUCTURAL_DETAILS"
            if v_upper in ("ELECTRICAL_DIAGRAM", "SINGLE_LINE_DIAGRAM", "EE_DIAGRAM", "EE-101"):
                return "ELECTRICAL_DIAGRAM"
            if v_upper in ("SANITATION_DIAGRAM", "RISER_DIAGRAM", "PLUMBING_DIAGRAM", "SN_DIAGRAM", "SN-101"):
                return "SANITATION_DIAGRAM"
            if v_upper in ("MEP_DIAGRAM", "MEP_SCHEMATIC"):
                return "ELECTRICAL_DIAGRAM"
        return str(v).upper() if v else "FLOOR_PLAN"

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

    def get_margins_mm(self) -> Tuple[float, float, float, float]:
        """Get (left, top, right, bottom) margins in millimeters."""
        left = self.margin_left_mm
        if left is None:
            left = self.binding_margin_mm if self.binding_margin_enabled else self.margin_mm
        top = self.margin_top_mm if self.margin_top_mm is not None else self.margin_mm
        right = self.margin_right_mm if self.margin_right_mm is not None else self.margin_mm
        bottom = self.margin_bottom_mm if self.margin_bottom_mm is not None else self.margin_mm
        return (left, top, right, bottom)


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


STANDARD_ARCHITECTURAL_SCALES: List[int] = [50, 75, 100]


def select_architectural_scale(
    model_width_m: float,
    model_height_m: float,
    viewport_width_mm: float,
    viewport_height_mm: float,
    annotation_margin_mm: float = 60.0,
    allowed_scales: Optional[List[int]] = None,
) -> int:
    """
    Select the optimal standard architectural scale (1:50, 1:75, 1:100, etc.)
    that fits the building bounds plus annotation margins within the printable viewport.
    """
    scales = allowed_scales or STANDARD_ARCHITECTURAL_SCALES
    avail_w_mm = max(10.0, viewport_width_mm - annotation_margin_mm)
    avail_h_mm = max(10.0, viewport_height_mm - annotation_margin_mm)

    for s in sorted(scales):
        needed_w_mm = model_width_m * (1000.0 / float(s))
        needed_h_mm = model_height_m * (1000.0 / float(s))
        if needed_w_mm <= avail_w_mm and needed_h_mm <= avail_h_mm:
            return s

    return max(scales)


class ViewportTransform(BaseModel):
    """Result of floating viewport transformation calculation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    scale: int
    transformer: 'CoordinateTransformer'
    model_bounds: Tuple[float, float, float, float]  # min_x, min_y, max_x, max_y
    model_center: Tuple[float, float]
    viewport_center: Tuple[float, float]
    viewport_dimensions_mm: Tuple[float, float]


def calculate_viewport_transform(
    model_bounds: Tuple[float, float, float, float],
    drawing_center_mm: Tuple[float, float],
    drawing_size_mm: Tuple[float, float],
    scale: Optional[int] = None,
    annotation_margin_mm: float = 60.0,
) -> ViewportTransform:
    """
    Calculate model-to-paper viewport transformation centered on building bounds,
    using exact standard architectural scale (1:50, 1:75, 1:100).
    """
    min_x, min_y, max_x, max_y = model_bounds
    model_w_m = max_x - min_x
    model_h_m = max_y - min_y
    model_cx = (min_x + max_x) / 2.0
    model_cy = (min_y + max_y) / 2.0

    dw_mm, dh_mm = drawing_size_mm
    dcx_mm, dcy_mm = drawing_center_mm

    if scale is None or scale <= 0:
        chosen_scale = select_architectural_scale(
            model_w_m, model_h_m, dw_mm, dh_mm, annotation_margin_mm=annotation_margin_mm
        )
    else:
        chosen_scale = scale

    transformer = CoordinateTransformer(
        model_center=(model_cx, model_cy),
        viewport_center=(dcx_mm, dcy_mm),
        scale=chosen_scale,
    )

    return ViewportTransform(
        scale=chosen_scale,
        transformer=transformer,
        model_bounds=model_bounds,
        model_center=(model_cx, model_cy),
        viewport_center=(dcx_mm, dcy_mm),
        viewport_dimensions_mm=drawing_size_mm,
    )


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

    def mm_to_model(self, mm: float) -> float:
        """Convert paper millimeters to model meters based on drawing scale."""
        return (mm * float(self.scale)) / 1000.0

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


class SheetRenderer:
    """
    2D Architectural Sheet Rendering Engine.
    Converts 2D projection primitives (Plans & Sections) into production-ready SVG and PDF-ready sheets.
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

        # Determine if this is a section view, schedule view, or MEP diagram view
        is_schedule_sheet = (cfg.view_type == "SCHEDULE") or cfg.id.startswith("A-4")
        is_structural_schedule = (cfg.view_type == "STRUCTURAL_DETAILS") or cfg.id.startswith("S-2") or cfg.id.startswith("S-201")
        is_electrical_sheet = (cfg.view_type == "ELECTRICAL_DIAGRAM") or cfg.id.startswith("EE-") or cfg.id == "EE-101"
        is_sanitation_sheet = (cfg.view_type == "SANITATION_DIAGRAM") or cfg.id.startswith("SN-") or cfg.id == "SN-101"
        is_section_sheet = (cfg.view_type == "section") or cfg.id.startswith("A-3")

        v_type = str(cfg.view_type).upper()
        if v_type == "SCHEDULE" or is_schedule_sheet:
            from debim.draw.schedule import render_opening_schedule_svg
            return render_opening_schedule_svg(self.resolved, cfg)
        elif v_type == "STRUCTURAL_DETAILS" or is_structural_schedule:
            from debim.draw.structural_details import render_structural_details_schedule_svg
            return render_structural_details_schedule_svg(self.resolved, cfg)
        elif v_type == "ELECTRICAL_DIAGRAM" or is_electrical_sheet:
            from debim.draw.mep_diagrams import render_electrical_sheet_svg
            return render_electrical_sheet_svg(self.resolved, cfg)
        elif v_type == "SANITATION_DIAGRAM" or is_sanitation_sheet:
            from debim.draw.mep_diagrams import render_sanitation_sheet_svg
            return render_sanitation_sheet_svg(self.resolved, cfg)
        elif v_type == "ELEVATION":
            return self._render_elevation_svg()
        elif is_section_sheet:
            return self._render_section_svg()
        else:
            return self._render_plan_svg()

    def _render_plan_svg(self) -> str:
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
        m_left, m_top, m_right, m_bottom = cfg.get_margins_mm()

        # Layout Areas:
        printable_x = m_left
        printable_y = m_top
        printable_w = paper_w - m_left - m_right
        printable_h = paper_h - m_top - m_bottom

        # Title Block & Drawing Area Calculations
        tb_enabled = cfg.visibility.show_title_block and cfg.title_block.enabled
        tb_layout = cfg.title_block.layout

        if tb_enabled:
            if tb_layout == "horizontal_bottom":
                title_w = printable_w
                title_h = cfg.title_block.height_mm
                title_x = printable_x
                title_y = printable_y + printable_h - title_h

                drawing_w = printable_w
                drawing_h = printable_h - title_h - 2.0
                drawing_cx = printable_x + drawing_w / 2.0
                drawing_cy = printable_y + drawing_h / 2.0
            elif tb_layout == "corner_bottom_right":
                title_w = cfg.title_block.width_mm
                title_h = cfg.title_block.height_mm
                title_x = printable_x + printable_w - title_w
                title_y = printable_y + printable_h - title_h

                drawing_w = printable_w
                drawing_h = printable_h
                drawing_cx = printable_x + drawing_w / 2.0
                drawing_cy = printable_y + drawing_h / 2.0
            else:  # vertical_right (default)
                title_w = cfg.title_block.width_mm if cfg.title_block.width_mm != 75.0 or printable_w < 300.0 else 75.0
                if printable_w < 300.0 and cfg.title_block.width_mm == 75.0:
                    title_w = 55.0
                title_h = printable_h
                title_x = printable_x + printable_w - title_w
                title_y = printable_y

                drawing_w = printable_w - title_w - 5.0
                drawing_h = printable_h
                drawing_cx = printable_x + drawing_w / 2.0
                drawing_cy = printable_y + drawing_h / 2.0
        else:
            title_w = 0.0
            title_h = 0.0
            title_x = 0.0
            title_y = 0.0
            drawing_w = printable_w
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
        arch_name = cfg.architect_name if cfg.architect_name != "debim Engine" else (proj.architect_name or "debim Engine")
        eng_name = proj.engineer_name or ""
        eng_lic = proj.engineer_license or ""
        eng_role = proj.engineer_role or "วิศวกรโครงสร้าง"

        # 5. Build SVG Elements
        embedded_css = _get_embedded_css()

        svg_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {paper_w:.1f} {paper_h:.1f}" width="{paper_w:.1f}mm" height="{paper_h:.1f}mm">',
            '  <defs>',
            '    <style type="text/css"><![CDATA[',
            f'{embedded_css}',
            '    ]]></style>',
            '  </defs>',
            '  <!-- Background -->',
            f'  <rect x="0" y="0" width="{paper_w:.1f}" height="{paper_h:.1f}" fill="#ffffff" />',
            '  <!-- Outer Sheet Border & Margin -->',
            f'  <rect x="{printable_x:.1f}" y="{printable_y:.1f}" width="{printable_w:.1f}" height="{printable_h:.1f}" class="sheet-border" fill="none" />',
        ]

        # Inner Margin Line
        inner_m = 2.0
        svg_lines.append(
            f'  <rect x="{printable_x + inner_m:.1f}" y="{printable_y + inner_m:.1f}" width="{printable_w - 2*inner_m:.1f}" height="{printable_h - 2*inner_m:.1f}" class="sheet-inner-border" fill="none" />'
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
        x_grids = [g for g in cut_result.grid_lines if g.axis == "X" and "-" not in g.id]
        y_grids = [g for g in cut_result.grid_lines if g.axis == "Y" and "-" not in g.id]

        all_model_x = [g.position for g in x_grids] or [min_x, max_x]
        all_model_y = [g.position for g in y_grids] or [min_y, max_y]

        min_gx, max_gx = min(all_model_x), max(all_model_x)
        min_gy, max_gy = min(all_model_y), max(all_model_y)

        # Annotative Paper Offsets for 3-Tier Dimensions & Grid Bubbles
        dim1_offset_mm = 8.0    # Tier 1 (Inner): Openings & Wall Offsets
        dim2_offset_mm = 16.0   # Tier 2 (Middle): Grid-to-Grid Bay Distances
        dim3_offset_mm = 24.0   # Tier 3 (Outer): Overall Building Dimensions
        bubble_offset_mm = 32.0 # Automated Grid Bubbles
        ext_other_mm = 8.0      # Offset for opposite sides
        bubble_r_mm = 3.6       # Grid bubble radius

        if cfg.visibility.show_grid:
            svg_lines.append('    <!-- Grid Lines & Automated Bubbles -->')

            y_top_m = max_gy + transformer.mm_to_model(bubble_offset_mm)
            y_bot_m = min_gy - transformer.mm_to_model(ext_other_mm)
            x_left_m = min_gx - transformer.mm_to_model(bubble_offset_mm)
            x_right_m = max_gx + transformer.mm_to_model(ext_other_mm)

            # Draw X Grids (Vertical lines & Bubbles)
            for g in x_grids:
                p_top = transformer.to_paper(g.position, y_top_m)
                p_bot = transformer.to_paper(g.position, y_bot_m)

                svg_lines.append(
                    f'    <line x1="{p_bot[0]}" y1="{p_bot[1]}" x2="{p_top[0]}" y2="{p_top[1]}" class="grid-line" />'
                )

                svg_lines.append(
                    f'    <circle cx="{p_top[0]}" cy="{p_top[1]}" r="{bubble_r_mm}" class="grid-bubble" />'
                )
                svg_lines.append(
                    f'    <text x="{p_top[0]}" y="{p_top[1]}" class="grid-text">{g.id}</text>'
                )

                svg_lines.append(
                    f'    <circle cx="{p_bot[0]}" cy="{p_bot[1]}" r="{bubble_r_mm}" class="grid-bubble" />'
                )
                svg_lines.append(
                    f'    <text x="{p_bot[0]}" y="{p_bot[1]}" class="grid-text">{g.id}</text>'
                )

            # Draw Y Grids (Horizontal lines & Bubbles)
            for g in y_grids:
                p_left = transformer.to_paper(x_left_m, g.position)
                p_right = transformer.to_paper(x_right_m, g.position)

                svg_lines.append(
                    f'    <line x1="{p_left[0]}" y1="{p_left[1]}" x2="{p_right[0]}" y2="{p_right[1]}" class="grid-line" />'
                )

                svg_lines.append(
                    f'    <circle cx="{p_left[0]}" cy="{p_left[1]}" r="{bubble_r_mm}" class="grid-bubble" />'
                )
                svg_lines.append(
                    f'    <text x="{p_left[0]}" y="{p_left[1]}" class="grid-text">{g.id}</text>'
                )

                svg_lines.append(
                    f'    <circle cx="{p_right[0]}" cy="{p_right[1]}" r="{bubble_r_mm}" class="grid-bubble" />'
                )
                svg_lines.append(
                    f'    <text x="{p_right[0]}" y="{p_right[1]}" class="grid-text">{g.id}</text>'
                )

        # 10. Render Automated 3-Tier Dimensions (.dimension-line, .dimension-text, .text-mask)
        if cfg.visibility.show_dimensions and cfg.visibility.show_grid:
            svg_lines.append('    <!-- Automated 3-Tier Dimensions -->')

            x_grids_sorted = sorted([g for g in cut_result.grid_lines if g.axis == "X" and "-" not in g.id], key=lambda g: g.position)
            y_grids_sorted = sorted([g for g in cut_result.grid_lines if g.axis == "Y" and "-" not in g.id], key=lambda g: g.position)

            tick_len_mm = 1.8

            # Extract Tier 1 (Inner) break points along X axis (openings & wall offsets)
            x_tier1_set = set(g.position for g in x_grids_sorted)
            for ce in cut_result.cut_elements:
                if ce.geometry is not None:
                    gx0, gy0, gx1, gy1 = ce.geometry.bounds
                    if min_gx - 0.5 <= gx0 <= max_gx + 0.5:
                        x_tier1_set.add(round(gx0, 4))
                    if min_gx - 0.5 <= gx1 <= max_gx + 0.5:
                        x_tier1_set.add(round(gx1, 4))

            sorted_t1_x = sorted(list(x_tier1_set))
            merged_t1_x = []
            for x_val in sorted_t1_x:
                if not merged_t1_x or abs(x_val - merged_t1_x[-1]) >= 0.05:
                    merged_t1_x.append(x_val)

            # X-Axis Tier 1 (Inner): Openings & Wall offsets
            if len(merged_t1_x) >= 2:
                dim_t1_y_m = max_gy + transformer.mm_to_model(dim1_offset_mm)
                dim_t1_y_p = transformer.to_paper(0, dim_t1_y_m)[1]

                for i in range(len(merged_t1_x) - 1):
                    x1_m, x2_m = merged_t1_x[i], merged_t1_x[i + 1]
                    p1 = transformer.to_paper(x1_m, dim_t1_y_m)
                    p2 = transformer.to_paper(x2_m, dim_t1_y_m)
                    dist_m = abs(x2_m - x1_m)

                    svg_lines.append(
                        f'    <line x1="{p1[0]}" y1="{dim_t1_y_p}" x2="{p2[0]}" y2="{dim_t1_y_p}" class="dimension-line" data-tier="1" />'
                    )
                    svg_lines.append(
                        f'    <line x1="{p1[0] - tick_len_mm/2}" y1="{dim_t1_y_p + tick_len_mm/2}" x2="{p1[0] + tick_len_mm/2}" y2="{dim_t1_y_p - tick_len_mm/2}" class="dimension-tick" />'
                    )
                    svg_lines.append(
                        f'    <line x1="{p2[0] - tick_len_mm/2}" y1="{dim_t1_y_p + tick_len_mm/2}" x2="{p2[0] + tick_len_mm/2}" y2="{dim_t1_y_p - tick_len_mm/2}" class="dimension-tick" />'
                    )

                    mid_x = (p1[0] + p2[0]) / 2.0
                    val_str = f"{dist_m:.2f}"
                    text_w_mm = len(val_str) * 1.5 + 2.0
                    text_h_mm = 2.4

                    svg_lines.append(
                        f'    <rect x="{mid_x - text_w_mm/2:.2f}" y="{dim_t1_y_p - text_h_mm/2:.2f}" width="{text_w_mm:.2f}" height="{text_h_mm:.2f}" class="text-mask" />'
                    )
                    svg_lines.append(
                        f'    <text x="{mid_x:.2f}" y="{dim_t1_y_p:.2f}" class="dimension-text" data-tier="1">{val_str}</text>'
                    )

            # X-Axis Tier 2 (Middle): Grid-to-Grid column distances
            if len(x_grids_sorted) >= 2:
                dim_t2_y_m = max_gy + transformer.mm_to_model(dim2_offset_mm)
                dim_t2_y_p = transformer.to_paper(0, dim_t2_y_m)[1]

                for i in range(len(x_grids_sorted) - 1):
                    g1, g2 = x_grids_sorted[i], x_grids_sorted[i + 1]
                    p1 = transformer.to_paper(g1.position, dim_t2_y_m)
                    p2 = transformer.to_paper(g2.position, dim_t2_y_m)
                    dist_m = abs(g2.position - g1.position)

                    svg_lines.append(
                        f'    <line x1="{p1[0]}" y1="{dim_t2_y_p}" x2="{p2[0]}" y2="{dim_t2_y_p}" class="dimension-line" data-tier="2" />'
                    )
                    svg_lines.append(
                        f'    <line x1="{p1[0] - tick_len_mm/2}" y1="{dim_t2_y_p + tick_len_mm/2}" x2="{p1[0] + tick_len_mm/2}" y2="{dim_t2_y_p - tick_len_mm/2}" class="dimension-tick" />'
                    )
                    svg_lines.append(
                        f'    <line x1="{p2[0] - tick_len_mm/2}" y1="{dim_t2_y_p + tick_len_mm/2}" x2="{p2[0] + tick_len_mm/2}" y2="{dim_t2_y_p - tick_len_mm/2}" class="dimension-tick" />'
                    )

                    mid_x = (p1[0] + p2[0]) / 2.0
                    val_str = f"{dist_m:.2f}"
                    text_w_mm = len(val_str) * 1.5 + 2.0
                    text_h_mm = 2.4

                    svg_lines.append(
                        f'    <rect x="{mid_x - text_w_mm/2:.2f}" y="{dim_t2_y_p - text_h_mm/2:.2f}" width="{text_w_mm:.2f}" height="{text_h_mm:.2f}" class="text-mask" />'
                    )
                    svg_lines.append(
                        f'    <text x="{mid_x:.2f}" y="{dim_t2_y_p:.2f}" class="dimension-text" data-tier="2">{val_str}</text>'
                    )

                # X-Axis Tier 3 (Outer): Total building width
                dim_t3_y_m = max_gy + transformer.mm_to_model(dim3_offset_mm)
                dim_t3_y_p = transformer.to_paper(0, dim_t3_y_m)[1]

                p_start = transformer.to_paper(x_grids_sorted[0].position, dim_t3_y_m)
                p_end = transformer.to_paper(x_grids_sorted[-1].position, dim_t3_y_m)
                total_dist_m = abs(x_grids_sorted[-1].position - x_grids_sorted[0].position)

                svg_lines.append(
                    f'    <line x1="{p_start[0]}" y1="{dim_t3_y_p}" x2="{p_end[0]}" y2="{dim_t3_y_p}" class="dimension-line" data-tier="3" />'
                )
                svg_lines.append(
                    f'    <line x1="{p_start[0] - tick_len_mm/2}" y1="{dim_t3_y_p + tick_len_mm/2}" x2="{p_start[0] + tick_len_mm/2}" y2="{dim_t3_y_p - tick_len_mm/2}" class="dimension-tick" />'
                )
                svg_lines.append(
                    f'    <line x1="{p_end[0] - tick_len_mm/2}" y1="{dim_t3_y_p + tick_len_mm/2}" x2="{p_end[0] + tick_len_mm/2}" y2="{dim_t3_y_p - tick_len_mm/2}" class="dimension-tick" />'
                )

                mid_x_overall = (p_start[0] + p_end[0]) / 2.0
                val_overall_str = f"{total_dist_m:.2f}"
                text_w_overall = len(val_overall_str) * 1.5 + 2.0

                svg_lines.append(
                    f'    <rect x="{mid_x_overall - text_w_overall/2:.2f}" y="{dim_t3_y_p - text_h_mm/2:.2f}" width="{text_w_overall:.2f}" height="{text_h_mm:.2f}" class="text-mask" />'
                )
                svg_lines.append(
                    f'    <text x="{mid_x_overall:.2f}" y="{dim_t3_y_p:.2f}" class="dimension-text" data-tier="3">{val_overall_str}</text>'
                )

            # Extract Tier 1 (Inner) break points along Y axis (openings & wall offsets)
            y_tier1_set = set(g.position for g in y_grids_sorted)
            for ce in cut_result.cut_elements:
                if ce.geometry is not None:
                    gx0, gy0, gx1, gy1 = ce.geometry.bounds
                    if min_gy - 0.5 <= gy0 <= max_gy + 0.5:
                        y_tier1_set.add(round(gy0, 4))
                    if min_gy - 0.5 <= gy1 <= max_gy + 0.5:
                        y_tier1_set.add(round(gy1, 4))

            sorted_t1_y = sorted(list(y_tier1_set))
            merged_t1_y = []
            for y_val in sorted_t1_y:
                if not merged_t1_y or abs(y_val - merged_t1_y[-1]) >= 0.05:
                    merged_t1_y.append(y_val)

            # Y-Axis Tier 1 (Inner): Openings & Wall offsets
            if len(merged_t1_y) >= 2:
                dim_t1_x_m = min_gx - transformer.mm_to_model(dim1_offset_mm)
                dim_t1_x_p = transformer.to_paper(dim_t1_x_m, 0)[0]

                for i in range(len(merged_t1_y) - 1):
                    y1_m, y2_m = merged_t1_y[i], merged_t1_y[i + 1]
                    p1 = transformer.to_paper(dim_t1_x_m, y1_m)
                    p2 = transformer.to_paper(dim_t1_x_m, y2_m)
                    dist_m = abs(y2_m - y1_m)

                    svg_lines.append(
                        f'    <line x1="{dim_t1_x_p}" y1="{p1[1]}" x2="{dim_t1_x_p}" y2="{p2[1]}" class="dimension-line" data-tier="1" />'
                    )
                    svg_lines.append(
                        f'    <line x1="{dim_t1_x_p - tick_len_mm/2}" y1="{p1[1] + tick_len_mm/2}" x2="{dim_t1_x_p + tick_len_mm/2}" y2="{p1[1] - tick_len_mm/2}" class="dimension-tick" />'
                    )
                    svg_lines.append(
                        f'    <line x1="{dim_t1_x_p - tick_len_mm/2}" y1="{p2[1] + tick_len_mm/2}" x2="{dim_t1_x_p + tick_len_mm/2}" y2="{p2[1] - tick_len_mm/2}" class="dimension-tick" />'
                    )

                    mid_y = (p1[1] + p2[1]) / 2.0
                    val_str = f"{dist_m:.2f}"
                    text_w_mm = len(val_str) * 1.5 + 2.0
                    text_h_mm = 2.4

                    svg_lines.append(
                        f'    <rect x="{dim_t1_x_p - text_w_mm/2:.2f}" y="{mid_y - text_h_mm/2:.2f}" width="{text_w_mm:.2f}" height="{text_h_mm:.2f}" class="text-mask" transform="rotate(-90, {dim_t1_x_p:.2f}, {mid_y:.2f})" />'
                    )
                    svg_lines.append(
                        f'    <text x="{dim_t1_x_p:.2f}" y="{mid_y:.2f}" class="dimension-text" data-tier="1" transform="rotate(-90, {dim_t1_x_p:.2f}, {mid_y:.2f})">{val_str}</text>'
                    )

            # Y-Axis Tier 2 (Middle): Grid-to-Grid column distances
            if len(y_grids_sorted) >= 2:
                dim_t2_x_m = min_gx - transformer.mm_to_model(dim2_offset_mm)
                dim_t2_x_p = transformer.to_paper(dim_t2_x_m, 0)[0]

                for i in range(len(y_grids_sorted) - 1):
                    g1, g2 = y_grids_sorted[i], y_grids_sorted[i + 1]
                    p1 = transformer.to_paper(dim_t2_x_m, g1.position)
                    p2 = transformer.to_paper(dim_t2_x_m, g2.position)
                    dist_m = abs(g2.position - g1.position)

                    svg_lines.append(
                        f'    <line x1="{dim_t2_x_p}" y1="{p1[1]}" x2="{dim_t2_x_p}" y2="{p2[1]}" class="dimension-line" data-tier="2" />'
                    )
                    svg_lines.append(
                        f'    <line x1="{dim_t2_x_p - tick_len_mm/2}" y1="{p1[1] + tick_len_mm/2}" x2="{dim_t2_x_p + tick_len_mm/2}" y2="{p1[1] - tick_len_mm/2}" class="dimension-tick" />'
                    )
                    svg_lines.append(
                        f'    <line x1="{dim_t2_x_p - tick_len_mm/2}" y1="{p2[1] + tick_len_mm/2}" x2="{dim_t2_x_p + tick_len_mm/2}" y2="{p2[1] - tick_len_mm/2}" class="dimension-tick" />'
                    )

                    mid_y = (p1[1] + p2[1]) / 2.0
                    val_str = f"{dist_m:.2f}"
                    text_w_mm = len(val_str) * 1.5 + 2.0
                    text_h_mm = 2.4

                    svg_lines.append(
                        f'    <rect x="{dim_t2_x_p - text_w_mm/2:.2f}" y="{mid_y - text_h_mm/2:.2f}" width="{text_w_mm:.2f}" height="{text_h_mm:.2f}" class="text-mask" transform="rotate(-90, {dim_t2_x_p:.2f}, {mid_y:.2f})" />'
                    )
                    svg_lines.append(
                        f'    <text x="{dim_t2_x_p:.2f}" y="{mid_y:.2f}" class="dimension-text" data-tier="2" transform="rotate(-90, {dim_t2_x_p:.2f}, {mid_y:.2f})">{val_str}</text>'
                    )

                # Y-Axis Tier 3 (Outer): Total building length
                dim_t3_x_m = min_gx - transformer.mm_to_model(dim3_offset_mm)
                dim_t3_x_p = transformer.to_paper(dim_t3_x_m, 0)[0]

                p_start_y = transformer.to_paper(dim_t3_x_m, y_grids_sorted[0].position)
                p_end_y = transformer.to_paper(dim_t3_x_m, y_grids_sorted[-1].position)
                total_y_dist = abs(y_grids_sorted[-1].position - y_grids_sorted[0].position)

                svg_lines.append(
                    f'    <line x1="{dim_t3_x_p}" y1="{p_start_y[1]}" x2="{dim_t3_x_p}" y2="{p_end_y[1]}" class="dimension-line" data-tier="3" />'
                )
                svg_lines.append(
                    f'    <line x1="{dim_t3_x_p - tick_len_mm/2}" y1="{p_start_y[1] + tick_len_mm/2}" x2="{dim_t3_x_p + tick_len_mm/2}" y2="{p_start_y[1] - tick_len_mm/2}" class="dimension-tick" />'
                )
                svg_lines.append(
                    f'    <line x1="{dim_t3_x_p - tick_len_mm/2}" y1="{p_end_y[1] + tick_len_mm/2}" x2="{dim_t3_x_p + tick_len_mm/2}" y2="{p_end_y[1] - tick_len_mm/2}" class="dimension-tick" />'
                )

                mid_y_overall = (p_start_y[1] + p_end_y[1]) / 2.0
                val_y_overall_str = f"{total_y_dist:.2f}"
                text_w_y_overall = len(val_y_overall_str) * 1.5 + 2.0

                svg_lines.append(
                    f'    <rect x="{dim_t3_x_p - text_w_y_overall/2:.2f}" y="{mid_y_overall - text_h_mm/2:.2f}" width="{text_w_y_overall:.2f}" height="{text_h_mm:.2f}" class="text-mask" transform="rotate(-90, {dim_t3_x_p:.2f}, {mid_y_overall:.2f})" />'
                )
                svg_lines.append(
                    f'    <text x="{dim_t3_x_p:.2f}" y="{mid_y_overall:.2f}" class="dimension-text" data-tier="3" transform="rotate(-90, {dim_t3_x_p:.2f}, {mid_y_overall:.2f})">{val_y_overall_str}</text>'
                )

        # 11. Section Callouts on Floor Plan
        if cfg.visibility.show_section_callouts:
            svg_lines.append('    <!-- Section Callout Symbols (A-A / B-B) -->')

            mid_x = (min_x + max_x) / 2.0
            mid_y = (min_y + max_y) / 2.0

            sec_a_p1 = transformer.to_paper(min_x - 1.5, mid_y)
            sec_a_p2 = transformer.to_paper(max_x + 1.5, mid_y)

            svg_lines.append(f'    <line x1="{sec_a_p1[0]}" y1="{sec_a_p1[1]}" x2="{sec_a_p2[0]}" y2="{sec_a_p2[1]}" class="section-callout-line" />')
            svg_lines.append(f'    <circle cx="{sec_a_p1[0]}" cy="{sec_a_p1[1]}" r="4.0" class="section-callout-bubble" />')
            svg_lines.append(f'    <line x1="{sec_a_p1[0] - 4.0}" y1="{sec_a_p1[1]}" x2="{sec_a_p1[0] + 4.0}" y2="{sec_a_p1[1]}" class="section-callout-line" />')
            svg_lines.append(f'    <text x="{sec_a_p1[0]}" y="{sec_a_p1[1] - 1.8}" class="section-callout-text">A</text>')
            svg_lines.append(f'    <text x="{sec_a_p1[0]}" y="{sec_a_p1[1] + 2.2}" class="section-callout-text" style="font-size: 1.6px;">A-301</text>')
            svg_lines.append(f'    <polygon points="{sec_a_p1[0]},{sec_a_p1[1] - 4.2} {sec_a_p1[0] - 2.0},{sec_a_p1[1] - 7.0} {sec_a_p1[0] + 2.0},{sec_a_p1[1] - 7.0}" class="section-callout-arrow" />')

            svg_lines.append(f'    <circle cx="{sec_a_p2[0]}" cy="{sec_a_p2[1]}" r="4.0" class="section-callout-bubble" />')
            svg_lines.append(f'    <line x1="{sec_a_p2[0] - 4.0}" y1="{sec_a_p2[1]}" x2="{sec_a_p2[0] + 4.0}" y2="{sec_a_p2[1]}" class="section-callout-line" />')
            svg_lines.append(f'    <text x="{sec_a_p2[0]}" y="{sec_a_p2[1] - 1.8}" class="section-callout-text">A</text>')
            svg_lines.append(f'    <text x="{sec_a_p2[0]}" y="{sec_a_p2[1] + 2.2}" class="section-callout-text" style="font-size: 1.6px;">A-301</text>')
            svg_lines.append(f'    <polygon points="{sec_a_p2[0]},{sec_a_p2[1] - 4.2} {sec_a_p2[0] - 2.0},{sec_a_p2[1] - 7.0} {sec_a_p2[0] + 2.0},{sec_a_p2[1] - 7.0}" class="section-callout-arrow" />')

            sec_b_p1 = transformer.to_paper(mid_x, min_y - 1.5)
            sec_b_p2 = transformer.to_paper(mid_x, max_y + 1.5)

            svg_lines.append(f'    <line x1="{sec_b_p1[0]}" y1="{sec_b_p1[1]}" x2="{sec_b_p2[0]}" y2="{sec_b_p2[1]}" class="section-callout-line" />')
            svg_lines.append(f'    <circle cx="{sec_b_p1[0]}" cy="{sec_b_p1[1]}" r="4.0" class="section-callout-bubble" />')
            svg_lines.append(f'    <line x1="{sec_b_p1[0] - 4.0}" y1="{sec_b_p1[1]}" x2="{sec_b_p1[0] + 4.0}" y2="{sec_b_p1[1]}" class="section-callout-line" />')
            svg_lines.append(f'    <text x="{sec_b_p1[0]}" y="{sec_b_p1[1] - 1.8}" class="section-callout-text">B</text>')
            svg_lines.append(f'    <text x="{sec_b_p1[0]}" y="{sec_b_p1[1] + 2.2}" class="section-callout-text" style="font-size: 1.6px;">A-302</text>')
            svg_lines.append(f'    <polygon points="{sec_b_p1[0] + 4.2},{sec_b_p1[1]} {sec_b_p1[0] + 7.0},{sec_b_p1[1] - 2.0} {sec_b_p1[0] + 7.0},{sec_b_p1[1] + 2.0}" class="section-callout-arrow" />')

            svg_lines.append(f'    <circle cx="{sec_b_p2[0]}" cy="{sec_b_p2[1]}" r="4.0" class="section-callout-bubble" />')
            svg_lines.append(f'    <line x1="{sec_b_p2[0] - 4.0}" y1="{sec_b_p2[1]}" x2="{sec_b_p2[0] + 4.0}" y2="{sec_b_p2[1]}" class="section-callout-line" />')
            svg_lines.append(f'    <text x="{sec_b_p2[0]}" y="{sec_b_p2[1] - 1.8}" class="section-callout-text">B</text>')
            svg_lines.append(f'    <text x="{sec_b_p2[0]}" y="{sec_b_p2[1] + 2.2}" class="section-callout-text" style="font-size: 1.6px;">A-302</text>')
            svg_lines.append(f'    <polygon points="{sec_b_p2[0] + 4.2},{sec_b_p2[1]} {sec_b_p2[0] + 7.0},{sec_b_p2[1] - 2.0} {sec_b_p2[0] + 7.0},{sec_b_p2[1] + 2.0}" class="section-callout-arrow" />')

        # 12. Render Room Centroid Level Tags (e.g. FL.1 +0.00)
        if cfg.visibility.show_room_tags:
            svg_lines.append('    <!-- Room Centroid Level Tags -->')

            import re
            m_s = re.search(r"\d+", cut_result.storey_id or "") or re.search(r"\d+", cut_result.storey_name or "")
            s_num = m_s.group(0) if m_s else "1"
            elev_val = cut_result.storey_elevation
            elev_str = f"+{elev_val:.2f}" if elev_val >= 0.0 else f"{elev_val:.2f}"
            level_tag_str = f"FL.{s_num} {elev_str}"

            storey_spaces = [
                sp for sp in getattr(self.resolved, "spaces", [])
                if sp.element and getattr(sp.element.placement, "storey", None) == cut_result.storey_id
            ]
            if not storey_spaces:
                storey_spaces = getattr(self.resolved, "spaces", [])

            if storey_spaces:
                for sp in storey_spaces:
                    cx, cy = sp.center[0], sp.center[1]
                    p_center = transformer.to_paper(cx, cy)
                    r_name = (sp.name or sp.tag).upper()

                    w_mm = max(len(r_name), len(level_tag_str)) * 1.8 + 4.0
                    h_mm = 7.0
                    svg_lines.append(
                        f'    <rect x="{p_center[0] - w_mm/2:.2f}" y="{p_center[1] - h_mm/2:.2f}" width="{w_mm:.2f}" height="{h_mm:.2f}" class="text-mask" />'
                    )
                    svg_lines.append(
                        f'    <text x="{p_center[0]:.2f}" y="{p_center[1] - 1.2:.2f}" class="room-tag">{r_name}</text>'
                    )
                    svg_lines.append(
                        f'    <text x="{p_center[0]:.2f}" y="{p_center[1] + 2.2:.2f}" class="dimension-text">{level_tag_str}</text>'
                    )
            else:
                tag_p = transformer.to_paper(model_cx, model_cy)
                r_name = (cut_result.storey_name or cut_result.storey_id).upper()
                w_mm = max(len(r_name), len(level_tag_str)) * 1.8 + 4.0
                h_mm = 7.0

                svg_lines.append(
                    f'    <rect x="{tag_p[0] - w_mm/2:.2f}" y="{tag_p[1] - h_mm/2:.2f}" width="{w_mm:.2f}" height="{h_mm:.2f}" class="text-mask" />'
                )
                svg_lines.append(
                    f'    <text x="{tag_p[0]:.2f}" y="{tag_p[1] - 1.2:.2f}" class="room-tag">{r_name}</text>'
                )
                svg_lines.append(
                    f'    <text x="{tag_p[0]:.2f}" y="{tag_p[1] + 2.2:.2f}" class="dimension-text">{level_tag_str}</text>'
                )

        svg_lines.append('  </g> <!-- End drawing-viewport -->')

        # 12. Title Block & Sheet Index Table
        if tb_enabled:
            svg_lines.append('  <!-- Standard Architectural Title Block -->')
            svg_lines.append(
                f'  <g id="title-block" transform="translate({title_x:.1f}, {title_y:.1f})">'
            )
            svg_lines.append(
                f'    <rect x="0" y="0" width="{title_w:.1f}" height="{title_h:.1f}" class="title-block-container" />'
            )

            if tb_layout == "horizontal_bottom":
                # Divide strip into 4 modular horizontal grid cells
                w1 = round(title_w * 0.22, 1)
                w2 = round(title_w * 0.22, 1)
                w3 = round(title_w * 0.38, 1)
                w4 = title_w - w1 - w2 - w3

                x1 = 0.0
                x2 = x1 + w1
                x3 = x2 + w2
                x4 = x3 + w3

                # Vertical Dividers between cells
                svg_lines.append(f'    <line x1="{x2:.1f}" y1="0" x2="{x2:.1f}" y2="{title_h:.1f}" class="title-block-divider" />')
                svg_lines.append(f'    <line x1="{x3:.1f}" y1="0" x2="{x3:.1f}" y2="{title_h:.1f}" class="title-block-divider" />')
                svg_lines.append(f'    <line x1="{x4:.1f}" y1="0" x2="{x4:.1f}" y2="{title_h:.1f}" class="title-block-divider" />')

                # Cell 1: Project Info & Organization
                curr_y = 4.0
                svg_lines.append(f'    <text x="{x1 + 3.0:.1f}" y="{curr_y:.1f}" class="title-block-label">PROJECT / โครงการ</text>')
                curr_y += 3.5
                display_proj = (proj_name[:24] + "...") if len(proj_name) > 26 else proj_name
                svg_lines.append(f'    <text x="{x1 + 3.0:.1f}" y="{curr_y:.1f}" class="sheet-title">{display_proj}</text>')
                curr_y += 6.5
                svg_lines.append(f'    <line x1="{x1}" y1="{curr_y:.1f}" x2="{x2:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />')
                curr_y += 3.0
                svg_lines.append(f'    <text x="{x1 + 3.0:.1f}" y="{curr_y:.1f}" class="title-block-label">CLIENT / เจ้าของโครงการ</text>')
                curr_y += 3.5
                svg_lines.append(f'    <text x="{x1 + 3.0:.1f}" y="{curr_y:.1f}" class="title-block-text">{cfg.client_name}</text>')

                # Cell 2: Sheet Title & Drawing Type
                curr_y = 4.0
                svg_lines.append(f'    <text x="{x2 + 3.0:.1f}" y="{curr_y:.1f}" class="title-block-label">DRAWING TITLE / ชื่อแบบ</text>')
                curr_y += 3.5
                svg_lines.append(f'    <text x="{x2 + 3.0:.1f}" y="{curr_y:.1f}" class="sheet-title">{cfg.title}</text>')
                curr_y += 6.5
                svg_lines.append(f'    <line x1="{x2}" y1="{curr_y:.1f}" x2="{x3:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />')
                curr_y += 3.0
                svg_lines.append(f'    <text x="{x2 + 3.0:.1f}" y="{curr_y:.1f}" class="title-block-label">ARCHITECT / สถาปนิก</text>')
                curr_y += 3.5
                svg_lines.append(f'    <text x="{x2 + 3.0:.1f}" y="{curr_y:.1f}" class="title-block-text">{cfg.architect_name}</text>')

                # Cell 3: Multi-Signatory Professional Certification Grid
                svg_lines.append(f'    <text x="{x3 + 3.0:.1f}" y="4.0" class="title-block-label">PROFESSIONAL CERTIFICATION / คณะผู้จัดทำ &amp; วิศวกร</text>')
                fields = cfg.title_block.fields
                if fields:
                    num_cols = min(len(fields), 2)
                    col_w = w3 / max(num_cols, 1)
                    for i, field in enumerate(fields):
                        col_idx = i % 2 if len(fields) > 1 else 0
                        row_idx = i // 2 if len(fields) > 1 else i
                        fx = x3 + 3.0 + col_idx * col_w
                        fy = 8.5 + row_idx * 13.5
                        if fy < title_h - 2.0:
                            svg_lines.append(f'    <text x="{fx:.1f}" y="{fy:.1f}" class="title-block-label">{field.label}</text>')
                            svg_lines.append(f'    <text x="{fx:.1f}" y="{fy + 3.2:.1f}" class="title-block-text">{field.value}</text>')
                            if field.subtext:
                                svg_lines.append(f'    <text x="{fx:.1f}" y="{fy + 6.5:.1f}" class="title-block-subtext">{field.subtext}</text>')
                else:
                    svg_lines.append(f'    <text x="{x3 + 3.0:.1f}" y="9.0" class="title-block-text">สถาปนิกโครงการ / วิศวกรโครงสร้าง / งานระบบ</text>')

                # Cell 4: Sheet No, Scale, Revision, Date
                c4_y = 3.5
                details_c4 = [
                    ("SHEET NO.", cfg.id),
                    ("SCALE", f"1:{cfg.scale}"),
                    ("DATE", date_str),
                    ("REVISION", cfg.revision),
                ]
                for lbl, val in details_c4:
                    svg_lines.append(f'    <text x="{x4 + 3.0:.1f}" y="{c4_y:.1f}" class="title-block-label">{lbl}</text>')
                    svg_lines.append(f'    <text x="{x4 + 22.0:.1f}" y="{c4_y:.1f}" class="title-block-text">{val}</text>')
                    c4_y += 5.5
                    if c4_y < title_h - 2.0:
                        svg_lines.append(f'    <line x1="{x4}" y1="{c4_y - 1.5:.1f}" x2="{title_w:.1f}" y2="{c4_y - 1.5:.1f}" class="title-block-divider" />')

            elif tb_layout == "corner_bottom_right":
                curr_y = 4.0
                svg_lines.append(f'    <text x="4.0" y="{curr_y:.1f}" class="title-block-label">PROJECT / โครงการ: {proj_name[:20]}</text>')
                curr_y += 4.5
                svg_lines.append(f'    <text x="4.0" y="{curr_y:.1f}" class="sheet-title">{cfg.title}</text>')
                curr_y += 6.0
                svg_lines.append(f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_w:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />')
                curr_y += 2.5

                svg_lines.append(f'    <text x="4.0" y="{curr_y:.1f}" class="title-block-label">SHEET NO: <tspan class="title-block-text">{cfg.id}</tspan>  SCALE: <tspan class="title-block-text">1:{cfg.scale}</tspan></text>')
                curr_y += 4.5
                svg_lines.append(f'    <text x="4.0" y="{curr_y:.1f}" class="title-block-label">DATE: <tspan class="title-block-text">{date_str}</tspan>  REV: <tspan class="title-block-text">{cfg.revision}</tspan></text>')
                curr_y += 5.0

                if cfg.title_block.fields:
                    svg_lines.append(f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_w:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />')
                    curr_y += 2.5
                    for field in cfg.title_block.fields:
                        if curr_y > title_h - 4.0:
                            break
                        svg_lines.append(f'    <text x="4.0" y="{curr_y:.1f}" class="title-block-label">{field.label}: <tspan class="title-block-text">{field.value}</tspan></text>')
                        curr_y += 4.0

            else:  # vertical_right
                curr_y = 6.0

                # Project Title Header Box
                svg_lines.append(
                    f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">PROJECT / โครงการ</text>'
                )
                curr_y += 3.5
                display_proj = (proj_name[:26] + "...") if len(proj_name) > 28 else proj_name
                svg_lines.append(
                    f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-title">{display_proj}</text>'
                )
                curr_y += 6.5
                svg_lines.append(
                    f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_w:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
                )
                curr_y += 3.0

                # Sheet Title Box
                svg_lines.append(
                    f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">DRAWING TITLE / ชื่อแบบ</text>'
                )
                curr_y += 3.5
                svg_lines.append(
                    f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-title">{cfg.title}</text>'
                )
                curr_y += 6.5
                svg_lines.append(
                    f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_w:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
                )
                curr_y += 3.0

                # Format sheet label with total sheets if available
                sheet_label = cfg.id
                if cfg.total_sheets and cfg.total_sheets > 0:
                    current_idx = 1
                    if cfg.sheet_index:
                        for idx, s in enumerate(cfg.sheet_index, 1):
                            if s.sheet_no == cfg.id:
                                current_idx = idx
                                break
                    sheet_label = f"{cfg.id} ({current_idx}/{cfg.total_sheets})"

                # Details Grid: Sheet No, Scale, Date, Rev, Client, Architect
                details = [
                    ("SHEET NO. / เลขที่แบบ", sheet_label),
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
                    curr_y += 3.2
                    svg_lines.append(
                        f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-text">{val}</text>'
                    )
                    curr_y += 4.5
                    svg_lines.append(
                        f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_w:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
                    )
                    curr_y += 2.5

                # Auto-populate title block fields from manifest project if not overridden
                effective_fields = list(cfg.title_block.fields)
                if not effective_fields:
                    if eng_name:
                        val_str = f"{eng_name} ({eng_lic})" if eng_lic else eng_name
                        effective_fields.append(TitleBlockField(label=eng_role, value=val_str))
                    if proj.architect_name and proj.architect_license:
                        effective_fields.append(TitleBlockField(label="สถาปนิกโครงการ", value=f"{proj.architect_name} ({proj.architect_license})"))

                # Professional Certification / Custom Fields
                if effective_fields:
                    svg_lines.append(
                        f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">PROFESSIONAL CERTIFICATION / คณะผู้จัดทำ</text>'
                    )
                    curr_y += 3.5
                    for field in effective_fields:
                        if curr_y > title_h - 45.0:
                            break
                        svg_lines.append(
                            f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">{field.label}</text>'
                        )
                        curr_y += 3.2
                        svg_lines.append(
                            f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-text">{field.value}</text>'
                        )
                        curr_y += 4.0
                        if field.subtext:
                            svg_lines.append(
                                f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-subtext">{field.subtext}</text>'
                            )
                            curr_y += 3.5
                        svg_lines.append(
                            f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_w:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
                        )
                        curr_y += 2.5

                # Sheet Index Table (if enabled & provided)
                if cfg.visibility.show_sheet_index and cfg.title_block.show_sheet_index and cfg.sheet_index:
                    curr_y += 1.0
                    svg_lines.append(
                        f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-title">SHEET INDEX /สารบัญแบบ</text>'
                    )
                    curr_y += 4.5

                    # Table Header
                    svg_lines.append(
                        f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-header">NO.</text>'
                    )
                    svg_lines.append(
                        f'    <text x="18.0" y="{curr_y:.1f}" class="sheet-index-header">TITLE</text>'
                    )
                    svg_lines.append(
                        f'    <text x="{title_w - 15.0:.1f}" y="{curr_y:.1f}" class="sheet-index-header">SCALE</text>'
                    )
                    curr_y += 3.2
                    svg_lines.append(
                        f'    <line x1="5.0" y1="{curr_y:.1f}" x2="{title_w - 5.0:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
                    )
                    curr_y += 2.5

                    for idx_item in cfg.sheet_index:
                        if curr_y > title_h - 45.0:
                            break
                        svg_lines.append(
                            f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-cell">{idx_item.sheet_no}</text>'
                        )
                        svg_lines.append(
                            f'    <text x="18.0" y="{curr_y:.1f}" class="sheet-index-cell">{idx_item.title[:20]}</text>'
                        )
                        svg_lines.append(
                            f'    <text x="{title_w - 15.0:.1f}" y="{curr_y:.1f}" class="sheet-index-cell">{idx_item.scale}</text>'
                        )
                        curr_y += 4.0

                # General Notes & Professional Stamp Box
                if cfg.title_block.show_notes and curr_y < title_h - 40.0:
                    curr_y += 3.0
                    svg_lines.append(
                        f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_w:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
                    )
                    curr_y += 3.0
                    svg_lines.append(
                        f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">GENERAL NOTES / ข้อกำหนดทั่วไป</text>'
                    )
                    curr_y += 3.5
                    svg_lines.append(
                        f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-cell">1. DO NOT SCALE DRAWINGS / ห้ามวัดขนาดจากแบบ</text>'
                    )
                    curr_y += 3.5
                    svg_lines.append(
                        f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-cell">2. ALL DIMENSIONS IN METERS / หน่วยวัดเป็นเมตร</text>'
                    )
                    curr_y += 3.5
                    svg_lines.append(
                        f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-cell">3. VERIFY ALL DIMS ON SITE / ตรวจขนาดจริงหน้างาน</text>'
                    )
                    curr_y += 4.5

                # Clean Signature & Stamp Box Area for PdfCraft digital signing
                if cfg.title_block.show_signature_box and cfg.title_block.signature_box.enabled and curr_y < title_h - 25.0:
                    sig_box = cfg.title_block.signature_box
                    svg_lines.append(
                        f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_w:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
                    )
                    curr_y += 3.0
                    svg_lines.append(
                        f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">{sig_box.title}</text>'
                    )
                    curr_y += 3.0
                    box_h = sig_box.height_mm
                    svg_lines.append(
                        f'    <rect x="5.0" y="{curr_y:.1f}" width="{title_w - 10.0:.1f}" height="{box_h:.1f}" fill="none" stroke="#94a3b8" stroke-dasharray="2 2" stroke-width="0.3" class="signature-box" />'
                    )
                    svg_lines.append(
                        f'    <text x="{title_w / 2.0:.1f}" y="{curr_y + box_h / 2.0 + 1.0:.1f}" text-anchor="middle" class="title-block-subtext" fill="#94a3b8">{sig_box.subtext}</text>'
                    )
                    curr_y += box_h + 3.0

                # Footer debim Engine Tag
                svg_lines.append(
                    f'    <text x="5.0" y="{title_h - 4.0:.1f}" class="title-block-label">GENERATED BY debim ARCHITECTURAL ENGINE</text>'
                )

            svg_lines.append('  </g> <!-- End title-block -->')

        svg_lines.append('</svg>')
        return "\n".join(svg_lines)

    def _render_elevation_svg(self) -> str:
        """Render Elevation view as SVG sheet."""
        cfg = self.config
        manifest = self.resolved.manifest
        proj = manifest.project

        # Project 2D Elevation
        elevation_res: ElevationResult = project_2d_elevation(
            self.resolved, direction=cfg.elevation_direction
        )

        paper_w, paper_h = cfg.get_paper_dimensions_mm()
        m_left, m_top, m_right, m_bottom = cfg.get_margins_mm()

        printable_x = m_left
        printable_y = m_top
        printable_w = paper_w - m_left - m_right
        printable_h = paper_h - m_top - m_bottom

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

        if cfg.crop:
            if isinstance(cfg.crop, CropBox):
                cb = cfg.crop
            else:
                cb = CropBox.model_validate(cfg.crop)
            min_u, min_v, max_u, max_v = cb.min_x, cb.min_y, cb.max_x, cb.max_y
        else:
            min_u, min_v, max_u, max_v = elevation_res.bounds

        model_cu = (min_u + max_u) / 2.0
        model_cv = (min_v + max_v) / 2.0

        transformer = CoordinateTransformer(
            model_center=(model_cu, model_cv),
            viewport_center=(drawing_cx, drawing_cy),
            scale=cfg.scale,
        )

        proj_name = cfg.project_name or proj.name
        date_str = cfg.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        embedded_css = _get_embedded_css()

        svg_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {paper_w:.1f} {paper_h:.1f}" width="{paper_w:.1f}mm" height="{paper_h:.1f}mm">',
            '  <defs>',
            '    <style type="text/css"><![CDATA[',
            f'{embedded_css}',
            '    ]]></style>',
            '  </defs>',
            '  <!-- Background -->',
            f'  <rect x="0" y="0" width="{paper_w:.1f}" height="{paper_h:.1f}" fill="#ffffff" />',
            '  <!-- Outer Sheet Border & Margin -->',
            f'  <rect x="{printable_x:.1f}" y="{printable_y:.1f}" width="{printable_w:.1f}" height="{printable_h:.1f}" class="sheet-border" fill="none" />',
        ]

        inner_m = 2.0
        svg_lines.append(
            f'  <rect x="{printable_x + inner_m:.1f}" y="{printable_y + inner_m:.1f}" width="{printable_w - 2*inner_m:.1f}" height="{printable_h - 2*inner_m:.1f}" class="sheet-inner-border" fill="none" />'
        )

        svg_lines.append('  <g id="drawing-viewport">')

        # 1. Render Elevation Projected Elements
        svg_lines.append('    <!-- Elevation Architectural Elements -->')
        for elem in elevation_res.elements:
            d_str = transformer.polygon_to_paper_path(elem.polygon_coords)
            css_cls = "cut-heavy" if elem.category in ("outline", "structure") else "cut-medium" if elem.category in ("opening", "roof") else "projection"
            if elem.category == "ground":
                css_cls = "ground-line"

            if d_str:
                svg_lines.append(
                    f'    <path d="{d_str}" class="{css_cls}" fill-rule="evenodd" data-tag="{elem.tag}" data-class="{elem.element_class}" />'
                )

        # 2. Render Level Markers (สัญลักษณ์บอกระดับชั้น)
        if cfg.visibility.show_dimensions:
            svg_lines.append('    <!-- Level Markers -->')
            for lm in elevation_res.level_markers:
                p_start = transformer.to_paper(lm.start_u, lm.elevation)
                p_end = transformer.to_paper(lm.end_u, lm.elevation)

                # Dashed level line
                svg_lines.append(
                    f'    <line x1="{p_start[0]}" y1="{p_start[1]}" x2="{p_end[0]}" y2="{p_end[1]}" class="level-line" />'
                )

                # Inverted triangle level symbol at right end
                sym_x = p_end[0] + 2.0
                sym_y = p_end[1]
                tri_pts = f"{sym_x},{sym_y} {sym_x + 3.0},{sym_y - 2.5} {sym_x + 3.0},{sym_y}"
                svg_lines.append(
                    f'    <polygon points="{tri_pts}" class="level-symbol" />'
                )
                svg_lines.append(
                    f'    <text x="{sym_x + 4.5:.1f}" y="{sym_y:.1f}" class="level-text">{lm.label}</text>'
                )

        # 3. Render Vertical Grid Lines & Bubbles
        if cfg.visibility.show_grid:
            svg_lines.append('    <!-- Grid Lines & Bubbles -->')
            bubble_r_mm = 3.6
            v_bubble_top_m = elevation_res.max_height + transformer.mm_to_model(18.0)

            for g in elevation_res.grid_lines:
                p_bot = transformer.to_paper(g.position_u, 0.0)
                p_top = transformer.to_paper(g.position_u, v_bubble_top_m)

                svg_lines.append(
                    f'    <line x1="{p_bot[0]}" y1="{p_bot[1]}" x2="{p_top[0]}" y2="{p_top[1]}" class="grid-line" />'
                )
                svg_lines.append(
                    f'    <circle cx="{p_top[0]}" cy="{p_top[1]}" r="{bubble_r_mm}" class="grid-bubble" />'
                )
                svg_lines.append(
                    f'    <text x="{p_top[0]}" y="{p_top[1]}" class="grid-text">{g.id}</text>'
                )

        # 4. Render Drawing Title Label below elevation
        if cfg.visibility.show_room_tags:
            svg_lines.append('    <!-- Elevation Title Tag -->')
            title_p = transformer.to_paper(model_cu, -1.2)
            title_text = f"{elevation_res.title_th} ({elevation_res.title_en})"
            svg_lines.append(
                f'    <text x="{title_p[0]:.2f}" y="{title_p[1]:.2f}" class="room-tag">{title_text}</text>'
            )

        svg_lines.append('  </g> <!-- End drawing-viewport -->')

        # Title Block
        if cfg.visibility.show_title_block:
            svg_lines.append('  <!-- Title Block -->')
            svg_lines.append(
                f'  <g id="title-block" transform="translate({title_x:.1f}, {title_y:.1f})">'
            )
            svg_lines.append(
                f'    <rect x="0" y="0" width="{title_block_width:.1f}" height="{title_h:.1f}" class="title-block-container" />'
            )

            curr_y = 6.0
            svg_lines.append(
                f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">PROJECT / โครงการ</text>'
            )
            curr_y += 3.5
            display_proj = (proj_name[:26] + "...") if len(proj_name) > 28 else proj_name
            svg_lines.append(
                f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-title">{display_proj}</text>'
            )
            curr_y += 6.5
            svg_lines.append(
                f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_block_width:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
            )
            curr_y += 3.0

            svg_lines.append(
                f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">DRAWING TITLE / ชื่อแบบ</text>'
            )
            curr_y += 3.5
            svg_lines.append(
                f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-title">{cfg.title}</text>'
            )
            curr_y += 6.5
            svg_lines.append(
                f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_block_width:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
            )
            curr_y += 3.0

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
                curr_y += 3.2
                svg_lines.append(
                    f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-text">{val}</text>'
                )
                curr_y += 4.5
                svg_lines.append(
                    f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_block_width:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
                )
                curr_y += 2.5

            if cfg.visibility.show_sheet_index and cfg.sheet_index:
                curr_y += 1.0
                svg_lines.append(
                    f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-title">SHEET INDEX /สารบัญแบบ</text>'
                )
                curr_y += 4.5
                svg_lines.append(
                    f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-header">NO.</text>'
                )
                svg_lines.append(
                    f'    <text x="18.0" y="{curr_y:.1f}" class="sheet-index-header">TITLE</text>'
                )
                svg_lines.append(
                    f'    <text x="{title_block_width - 15.0:.1f}" y="{curr_y:.1f}" class="sheet-index-header">SCALE</text>'
                )
                curr_y += 3.2
                svg_lines.append(
                    f'    <line x1="5.0" y1="{curr_y:.1f}" x2="{title_block_width - 5.0:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />'
                )
                curr_y += 2.5

                for idx_item in cfg.sheet_index:
                    if curr_y > title_h - 45.0:
                        break
                    svg_lines.append(
                        f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-cell">{idx_item.sheet_no}</text>'
                    )
                    svg_lines.append(
                        f'    <text x="18.0" y="{curr_y:.1f}" class="sheet-index-cell">{idx_item.title[:20]}</text>'
                    )
                    svg_lines.append(
                        f'    <text x="{title_block_width - 15.0:.1f}" y="{curr_y:.1f}" class="sheet-index-cell">{idx_item.scale}</text>'
                    )
                    curr_y += 4.0

            svg_lines.append(
                f'    <text x="5.0" y="{title_h - 4.0:.1f}" class="title-block-label">GENERATED BY debim ARCHITECTURAL ENGINE</text>'
            )
            svg_lines.append('  </g> <!-- End title-block -->')

        svg_lines.append('</svg>')
        return "\n".join(svg_lines)


    def _render_section_svg(self) -> str:
        """Render 2D Architectural Section sheet (รูปตัด A-A, B-B)."""
        cfg = self.config
        manifest = self.resolved.manifest
        proj = manifest.project

        sec_id = cfg.section_id or ("B-B" if cfg.id == "A-302" else "A-A")
        sec_axis = cfg.section_axis or ("X" if sec_id == "B-B" else "Y")

        sec_result: SectionCutPlaneResult = slice_section(
            self.resolved,
            section_id=sec_id,
            plane_axis=sec_axis,
            position=cfg.section_position,
            grid_id=cfg.section_grid_id,
            title=cfg.title,
        )

        paper_w, paper_h = cfg.get_paper_dimensions_mm()
        m_left, m_top, m_right, m_bottom = cfg.get_margins_mm()

        printable_x = m_left
        printable_y = m_top
        printable_w = paper_w - m_left - m_right
        printable_h = paper_h - m_top - m_bottom

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

        min_u, min_z, max_u, max_z = sec_result.bounds
        model_cx = (min_u + max_u) / 2.0
        model_cy = (min_z + max_z) / 2.0

        transformer = CoordinateTransformer(
            model_center=(model_cx, model_cy),
            viewport_center=(drawing_cx, drawing_cy),
            scale=cfg.scale,
        )

        proj_name = cfg.project_name or proj.name
        date_str = cfg.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        embedded_css = _get_embedded_css()

        svg_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {paper_w:.1f} {paper_h:.1f}" width="{paper_w:.1f}mm" height="{paper_h:.1f}mm">',
            '  <defs>',
            '    <style type="text/css"><![CDATA[',
            f'{embedded_css}',
            '    ]]></style>',
            '    <!-- CAD Hatch Patterns -->',
            '    <pattern id="hatch-concrete" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">',
            '      <line x1="0" y1="0" x2="0" y2="6" stroke="#0f172a" stroke-width="0.6" />',
            '      <circle cx="3" cy="3" r="0.6" fill="#0f172a" />',
            '    </pattern>',
            '    <pattern id="hatch-wall" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">',
            '      <line x1="0" y1="0" x2="0" y2="8" stroke="#334155" stroke-width="0.4" />',
            '      <line x1="3" y1="0" x2="3" y2="8" stroke="#334155" stroke-width="0.4" />',
            '    </pattern>',
            '  </defs>',
            '  <!-- Background -->',
            f'  <rect x="0" y="0" width="{paper_w:.1f}" height="{paper_h:.1f}" fill="#ffffff" />',
            f'  <rect x="{printable_x:.1f}" y="{printable_y:.1f}" width="{printable_w:.1f}" height="{printable_h:.1f}" class="sheet-border" fill="none" />',
        ]

        inner_m = 2.0
        svg_lines.append(f'  <rect x="{printable_x + inner_m:.1f}" y="{printable_y + inner_m:.1f}" width="{printable_w - 2*inner_m:.1f}" height="{printable_h - 2*inner_m:.1f}" class="sheet-inner-border" fill="none" />')

        svg_lines.append('  <g id="drawing-viewport">')

        # Background Projection Elements
        if cfg.visibility.show_projection:
            svg_lines.append('    <!-- Background Projection Elements -->')
            for pe in sec_result.projection_elements:
                d_str = transformer.polygon_to_paper_path(pe.polygon_coords)
                if d_str:
                    svg_lines.append(f'    <path d="{d_str}" class="projection" fill-rule="evenodd" data-tag="{pe.tag}" data-class="{pe.element_class}" />')

        # Cut Elements with CAD Hatching
        if cfg.visibility.show_cut_heavy or cfg.visibility.show_cut_medium:
            svg_lines.append('    <!-- Cut Cross-Section Elements with CAD Hatching -->')
            for ce in sec_result.cut_elements:
                d_str = transformer.polygon_to_paper_path(ce.polygon_coords)
                if d_str:
                    hatch_cls = "cut-concrete" if ce.hatch_pattern == "concrete" else ("cut-wall" if ce.hatch_pattern == "wall" else "cut-heavy")
                    svg_lines.append(f'    <path d="{d_str}" class="{hatch_cls}" fill-rule="evenodd" data-tag="{ce.tag}" data-class="{ce.element_class}" data-hatch="{ce.hatch_pattern}" />')

        # Storey Level Markers (Elevation markers)
        if cfg.visibility.show_level_markers:
            svg_lines.append('    <!-- Storey Level Markers & Elevations -->')
            for lm in sec_result.level_markers:
                p_left = transformer.to_paper(min_u, lm.elevation)
                p_right = transformer.to_paper(max_u, lm.elevation)

                # Dashed Level Line
                svg_lines.append(f'    <line x1="{p_left[0]}" y1="{p_left[1]}" x2="{p_right[0] + 15.0}" y2="{p_right[1]}" class="level-line" />')
                # Inverted Target Triangle Symbol (∇)
                sym_x = p_right[0] + 2.0
                sym_y = p_right[1]
                svg_lines.append(f'    <polygon points="{sym_x},{sym_y} {sym_x + 3.0},{sym_y - 3.0} {sym_x - 3.0},{sym_y - 3.0}" class="level-symbol" />')
                # Level Text Annotation
                svg_lines.append(f'    <text x="{sym_x + 4.5}" y="{sym_y}" class="level-marker-text">{lm.display_text}</text>')

        # Perpendicular Grid Lines along Section Horizontal Axis U
        if cfg.visibility.show_grid:
            svg_lines.append('    <!-- Perpendicular Section Grid Lines -->')
            for g in sec_result.grid_lines:
                gx = g["position"]
                gid = g["id"]
                p_bot = transformer.to_paper(gx, min_z)
                p_top = transformer.to_paper(gx, max_z + 1.0)

                svg_lines.append(f'    <line x1="{p_bot[0]}" y1="{p_bot[1]}" x2="{p_top[0]}" y2="{p_top[1]}" class="grid-line" />')
                svg_lines.append(f'    <circle cx="{p_top[0]}" cy="{p_top[1]}" r="3.6" class="grid-bubble" />')
                svg_lines.append(f'    <text x="{p_top[0]}" y="{p_top[1]}" class="grid-text">{gid}</text>')
                svg_lines.append(f'    <circle cx="{p_bot[0]}" cy="{p_bot[1]}" r="3.6" class="grid-bubble" />')
                svg_lines.append(f'    <text x="{p_bot[0]}" y="{p_bot[1]}" class="grid-text">{gid}</text>')

        svg_lines.append('  </g> <!-- End drawing-viewport -->')

        # Title Block
        if cfg.visibility.show_title_block:
            svg_lines.append(self._render_title_block_svg(title_x, title_y, title_block_width, title_h, proj_name, date_str))

        svg_lines.append('</svg>')
        return "\n".join(svg_lines)

    def _render_title_block_svg(
        self, title_x: float, title_y: float, title_block_width: float, title_h: float, proj_name: str, date_str: str
    ) -> str:
        """Render Standard Architectural Title Block."""
        cfg = self.config
        lines = [
            '  <!-- Standard Architectural Title Block -->',
            f'  <g id="title-block" transform="translate({title_x:.1f}, {title_y:.1f})">',
            f'    <rect x="0" y="0" width="{title_block_width:.1f}" height="{title_h:.1f}" class="title-block-container" />',
        ]

        curr_y = 6.0
        lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">PROJECT / โครงการ</text>')
        curr_y += 3.5
        display_proj = (proj_name[:26] + "...") if len(proj_name) > 28 else proj_name
        lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-title">{display_proj}</text>')
        curr_y += 6.5
        lines.append(f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_block_width:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />')
        curr_y += 3.0

        lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">DRAWING TITLE / ชื่อแบบ</text>')
        curr_y += 3.5
        lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-title">{cfg.title}</text>')
        curr_y += 6.5
        lines.append(f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_block_width:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />')
        curr_y += 3.0

        details = [
            ("SHEET NO. / เลขที่แบบ", cfg.id),
            ("SCALE / มาตราส่วน", f"1:{cfg.scale}"),
            ("DATE / วันที่", date_str),
            ("REVISION / แก้ไขครั้งที่", cfg.revision),
            ("CLIENT / เจ้าของโครงการ", cfg.client_name),
            ("ARCHITECT / สถาปนิก", cfg.architect_name),
        ]

        for lbl, val in details:
            lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">{lbl}</text>')
            curr_y += 3.2
            lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-text">{val}</text>')
            curr_y += 4.5
            lines.append(f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_block_width:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />')
            curr_y += 2.5

        if cfg.visibility.show_sheet_index and cfg.sheet_index:
            curr_y += 1.0
            lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-title">SHEET INDEX /สารบัญแบบ</text>')
            curr_y += 4.5

            lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-header">NO.</text>')
            lines.append(f'    <text x="18.0" y="{curr_y:.1f}" class="sheet-index-header">TITLE</text>')
            lines.append(f'    <text x="{title_block_width - 15.0:.1f}" y="{curr_y:.1f}" class="sheet-index-header">SCALE</text>')
            curr_y += 3.2
            lines.append(f'    <line x1="5.0" y1="{curr_y:.1f}" x2="{title_block_width - 5.0:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />')
            curr_y += 2.5

            for idx_item in cfg.sheet_index:
                if curr_y > title_h - 45.0:
                    break
                lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-cell">{idx_item.sheet_no}</text>')
                lines.append(f'    <text x="18.0" y="{curr_y:.1f}" class="sheet-index-cell">{idx_item.title[:20]}</text>')
                lines.append(f'    <text x="{title_block_width - 15.0:.1f}" y="{curr_y:.1f}" class="sheet-index-cell">{idx_item.scale}</text>')
                curr_y += 4.0

        if curr_y < title_h - 40.0:
            curr_y += 3.0
            lines.append(f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_block_width:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />')
            curr_y += 3.0
            lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">GENERAL NOTES / ข้อกำหนดทั่วไป</text>')
            curr_y += 3.5
            lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-cell">1. DO NOT SCALE DRAWINGS / ห้ามวัดขนาดจากแบบ</text>')
            curr_y += 3.5
            lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-cell">2. ALL DIMENSIONS IN METERS / หน่วยวัดเป็นเมตร</text>')
            curr_y += 3.5
            lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="sheet-index-cell">3. VERIFY ALL DIMS ON SITE / ตรวจขนาดจริงหน้างาน</text>')
            curr_y += 4.5
            lines.append(f'    <line x1="0" y1="{curr_y:.1f}" x2="{title_block_width:.1f}" y2="{curr_y:.1f}" class="title-block-divider" />')
            curr_y += 3.0
            lines.append(f'    <text x="5.0" y="{curr_y:.1f}" class="title-block-label">PROFESSIONAL STAMP & SIGNATURE</text>')

        lines.append(f'    <text x="5.0" y="{title_h - 4.0:.1f}" class="title-block-label">GENERATED BY debim ARCHITECTURAL ENGINE</text>')
        lines.append('  </g> <!-- End title-block -->')
        return "\n".join(lines)

    def save_svg(self, output_path: Union[str, Path]) -> Path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        svg_content = self.render_svg()
        out_p.write_text(svg_content, encoding="utf-8")
        return out_p


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

    sheet_index_items = [
        SheetIndexItem(
            sheet_no=cfg.id,
            title=cfg.title,
            scale=f"1:{cfg.scale}",
            revision=cfg.revision,
        )
        for cfg in configs
    ]

    total_count = len(configs)
    results = []
    for cfg in configs:
        if not cfg.sheet_index:
            cfg.sheet_index = sheet_index_items
        if cfg.total_sheets is None:
            cfg.total_sheets = total_count
        renderer = SheetRenderer(resolved, cfg)
        svg_str = renderer.render_svg()
        results.append((cfg, svg_str))

    return results
