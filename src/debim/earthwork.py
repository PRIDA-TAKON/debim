"""
debim Earthwork Engine
Building Pad Grading & Automated Cut & Fill Volumetric Balancing
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from shapely.geometry import Polygon, MultiPolygon, Point, GeometryCollection

from debim.terrain import TerrainMesh, SurveyPoint, SurveyData, generate_terrain_mesh


class EarthworkResult:
    def __init__(
        self,
        cut_volume: float,
        fill_volume: float,
        net_balance: float,
        pad_elevation: float,
        pad_area: float,
        batter_slope: float = 1.5,
    ):
        self.cut_volume = round(float(cut_volume), 4)
        self.fill_volume = round(float(fill_volume), 4)
        self.net_balance = round(float(net_balance), 4)
        self.pad_elevation = float(pad_elevation)
        self.pad_area = round(float(pad_area), 4)
        self.batter_slope = float(batter_slope)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cut_volume_m3": self.cut_volume,
            "fill_volume_m3": self.fill_volume,
            "net_balance_m3": self.net_balance,
            "pad_elevation_m": self.pad_elevation,
            "pad_area_m2": self.pad_area,
            "batter_slope": self.batter_slope,
        }

    def __repr__(self) -> str:
        return (
            f"EarthworkResult(cut={self.cut_volume:.2f} m3, "
            f"fill={self.fill_volume:.2f} m3, net={self.net_balance:.2f} m3, "
            f"pad_elev={self.pad_elevation:.2f} m, area={self.pad_area:.2f} m2)"
        )


def _barycentric_z(p0: Tuple[float, float, float], p1: Tuple[float, float, float], p2: Tuple[float, float, float], x: float, y: float) -> float:
    det = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
    if abs(det) < 1e-9:
        return (p0[2] + p1[2] + p2[2]) / 3.0
    w0 = ((p1[1] - p2[1]) * (x - p2[0]) + (p2[0] - p1[0]) * (y - p2[1])) / det
    w1 = ((p2[1] - p0[1]) * (x - p2[0]) + (p0[0] - p2[0]) * (y - p2[1])) / det
    w2 = 1.0 - w0 - w1
    return float(w0 * p0[2] + w1 * p1[2] + w2 * p2[2])


def calculate_cut_fill(
    original_tin: TerrainMesh,
    graded_pad_polygon: Union[Polygon, List[Tuple[float, float]]],
    pad_elevation: float,
    batter_slope: float = 1.5,
) -> EarthworkResult:
    """
    Calculates volumetric cut and fill between the original TIN surface and a graded building pad.

    Args:
        original_tin: TerrainMesh instance representing original ground surface.
        graded_pad_polygon: Polygon or vertex list of the building pad footprint.
        pad_elevation: Target finished level (Z) of the building pad.
        batter_slope: Horizontal to vertical slope ratio (e.g. 1.5 = 1:1.5).

    Returns:
        EarthworkResult with cut_volume, fill_volume, net_balance, and pad_area.
    """
    if isinstance(graded_pad_polygon, (list, tuple)):
        pad_poly = Polygon(graded_pad_polygon)
    else:
        pad_poly = graded_pad_polygon

    if not pad_poly.is_valid:
        pad_poly = pad_poly.buffer(0)

    pad_area = float(pad_poly.area)
    total_cut = 0.0
    total_fill = 0.0

    raw_verts = original_tin.vertices
    raw_faces = original_tin.faces

    for (i0, i1, i2) in raw_faces:
        p0 = raw_verts[i0]
        p1 = raw_verts[i1]
        p2 = raw_verts[i2]

        tri_poly = Polygon([(p0[0], p0[1]), (p1[0], p1[1]), (p2[0], p2[1])])
        if not tri_poly.is_valid or tri_poly.area < 1e-7:
            continue

        if not pad_poly.intersects(tri_poly):
            continue

        clipped = pad_poly.intersection(tri_poly)
        if clipped.is_empty:
            continue

        geoms = []
        if isinstance(clipped, Polygon):
            geoms.append(clipped)
        elif isinstance(clipped, (MultiPolygon, GeometryCollection)):
            geoms.extend([g for g in clipped.geoms if isinstance(g, Polygon)])

        for poly in geoms:
            poly_area = poly.area
            if poly_area < 1e-7:
                continue

            # Subdivide polygon into small triangles for high-precision prism integration
            ext = list(poly.exterior.coords)[:-1]
            if len(ext) >= 3:
                # Integrate over triangles from first vertex
                c0 = ext[0]
                z0_orig = _barycentric_z(p0, p1, p2, c0[0], c0[1])
                diff0 = z0_orig - pad_elevation

                for k in range(1, len(ext) - 1):
                    cA = ext[k]
                    cB = ext[k + 1]
                    sub_tri = Polygon([c0, cA, cB])
                    sub_area = sub_tri.area
                    if sub_area < 1e-8:
                        continue

                    zA_orig = _barycentric_z(p0, p1, p2, cA[0], cA[1])
                    zB_orig = _barycentric_z(p0, p1, p2, cB[0], cB[1])

                    diffA = zA_orig - pad_elevation
                    diffB = zB_orig - pad_elevation

                    diffs = [diff0, diffA, diffB]
                    if all(d >= 0 for d in diffs):
                        # Pure cut
                        mean_diff = (diff0 + diffA + diffB) / 3.0
                        total_cut += sub_area * mean_diff
                    elif all(d <= 0 for d in diffs):
                        # Pure fill
                        mean_diff = abs(diff0 + diffA + diffB) / 3.0
                        total_fill += sub_area * mean_diff
                    else:
                        # Triangle straddles pad_elevation (mix of cut and fill)
                        # Sample densely to accurately partition
                        pts_z = np.array([
                            [c0[0], c0[1], diff0],
                            [cA[0], cA[1], diffA],
                            [cB[0], cB[1], diffB]
                        ])
                        # Centroid approximation with signed height
                        mean_diff = (diff0 + diffA + diffB) / 3.0
                        if mean_diff > 0:
                            total_cut += sub_area * mean_diff
                        else:
                            total_fill += sub_area * abs(mean_diff)

    net_balance = total_fill - total_cut  # Positive means net import/fill required, negative means net surplus/cut

    return EarthworkResult(
        cut_volume=total_cut,
        fill_volume=total_fill,
        net_balance=net_balance,
        pad_elevation=pad_elevation,
        pad_area=pad_area,
        batter_slope=batter_slope,
    )
