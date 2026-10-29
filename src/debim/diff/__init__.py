"""
debim.diff

Point-to-mesh and point-to-plane distance calculation engine, ICP fine alignment,
deviation tolerance heatmap generation, and diff comparison modules.
"""

from debim.diff.distance import (
    compute_point_to_plane_distance,
    compute_point_to_mesh_distance,
    calculate_element_deviations,
    get_element_mesh,
)
from debim.diff.aligner import icp_fine_align
from debim.diff.heatmap import generate_deviation_heatmap, HeatmapResult, export_colorized_ply
from debim.diff.viewer_html import generate_heatmap_html

__all__ = [
    "compute_point_to_plane_distance",
    "compute_point_to_mesh_distance",
    "calculate_element_deviations",
    "get_element_mesh",
    "icp_fine_align",
    "generate_deviation_heatmap",
    "HeatmapResult",
    "export_colorized_ply",
    "generate_heatmap_html",
]
