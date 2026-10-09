"""
2D Architectural Blueprint Projection, Section Slicing & Rendering Engine for debim.
"""

from debim.draw.dxf import export_2d_dxf
from debim.draw.elevation import (
    ElevationDirection,
    ElevationElement,
    ElevationGridLine2D,
    ElevationResult,
    LevelMarker2D,
    normalize_direction,
    project_2d_elevation,
)
from debim.draw.projection import (
    CutElement,
    CutPlaneResult,
    GridLine2D,
    ProjectionElement,
    project_2d_floor_plan,
    slice_storey,
)
from debim.draw.renderer import (
    CropBox,
    SheetConfig,
    SheetIndexItem,
    SheetRenderer,
    VisibilityFilter,
    load_sheet_config,
    render_sheet,
    render_sheet_set,
)
from debim.draw.section import (
    SectionCutElement,
    SectionCutPlaneResult,
    SectionProjectionElement,
    StoreyLevelMarker,
    project_2d_section,
    slice_section,
)
from debim.draw.viewer_2d import (
    export_2d_viewer,
    generate_2d_viewer_html,
)

__all__ = [
    "CutElement",
    "ProjectionElement",
    "GridLine2D",
    "CutPlaneResult",
    "ElevationDirection",
    "ElevationElement",
    "LevelMarker2D",
    "ElevationGridLine2D",
    "ElevationResult",
    "normalize_direction",
    "project_2d_elevation",
    "slice_storey",
    "project_2d_floor_plan",
    "SectionCutElement",
    "SectionProjectionElement",
    "StoreyLevelMarker",
    "SectionCutPlaneResult",
    "slice_section",
    "project_2d_section",
    "SheetConfig",
    "SheetRenderer",
    "VisibilityFilter",
    "SheetIndexItem",
    "CropBox",
    "load_sheet_config",
    "render_sheet",
    "render_sheet_set",
    "export_2d_dxf",
    "generate_2d_viewer_html",
    "export_2d_viewer",
]
