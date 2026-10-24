"""
debim Terrain Engine
AI Survey Ingestion, Delaunay TIN Mesh Generation, Boundary Clipping & Contour Extraction
"""

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from scipy.spatial import Delaunay
from shapely.geometry import Polygon, MultiPolygon, Point, LineString, MultiLineString
from shapely.ops import polygonize, unary_union


class SurveyPoint:
    def __init__(self, x: float, y: float, z: float):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def __repr__(self) -> str:
        return f"SurveyPoint(x={self.x:.3f}, y={self.y:.3f}, z={self.z:.3f})"


class ContourLine:
    def __init__(self, elevation: float, points: List[Tuple[float, float, float]]):
        self.elevation = float(elevation)
        self.points = points  # List of (x, y, z)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "elevation": self.elevation,
            "points": self.points,
        }


class SurveyData:
    def __init__(
        self,
        points: List[SurveyPoint],
        boundary: Optional[List[Tuple[float, float]]] = None,
    ):
        self.points = points
        self.boundary = boundary

    @classmethod
    def from_json(cls, json_path_or_str: Union[str, Path, dict]) -> "SurveyData":
        if isinstance(json_path_or_str, dict):
            data = json_path_or_str
        else:
            p = Path(json_path_or_str)
            if p.is_file():
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = json.loads(str(json_path_or_str))

        pts: List[SurveyPoint] = []
        raw_pts = data.get("points", [])
        for pt in raw_pts:
            if isinstance(pt, dict):
                x = pt.get("x", pt.get("X", pt.get("easting", 0.0)))
                y = pt.get("y", pt.get("Y", pt.get("northing", 0.0)))
                z = pt.get("z", pt.get("Z", pt.get("elevation", 0.0)))
                pts.append(SurveyPoint(x, y, z))
            elif isinstance(pt, (list, tuple)) and len(pt) >= 3:
                pts.append(SurveyPoint(pt[0], pt[1], pt[2]))

        boundary_poly = None
        raw_bnd = data.get("boundary")
        if raw_bnd and isinstance(raw_bnd, (list, tuple)):
            boundary_poly = [(float(p[0]), float(p[1])) for p in raw_bnd if len(p) >= 2]

        return cls(points=pts, boundary=boundary_poly)

    @classmethod
    def from_csv(cls, csv_path: Union[str, Path]) -> "SurveyData":
        p = Path(csv_path)
        pts: List[SurveyPoint] = []
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = None
            for row in reader:
                if not row or not any(row):
                    continue
                # Try to parse header
                if header is None:
                    lowered = [c.strip().lower() for c in row]
                    if any(k in lowered for k in ["x", "y", "z", "easting", "northing"]):
                        header = lowered
                        continue
                    else:
                        header = ["x", "y", "z"]

                # Extract coords based on header or position
                try:
                    vals = [float(v.strip()) for v in row if v.strip()]
                    if len(vals) >= 3:
                        pts.append(SurveyPoint(vals[0], vals[1], vals[2]))
                except ValueError:
                    continue

        return cls(points=pts)


class TerrainMesh:
    def __init__(
        self,
        vertices: List[Tuple[float, float, float]],
        faces: List[Tuple[int, int, int]],
        boundary: Optional[Polygon] = None,
        contours: Optional[List[ContourLine]] = None,
    ):
        self.vertices = vertices
        self.faces = faces
        self.boundary = boundary
        self.contours = contours or []

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def face_count(self) -> int:
        return len(self.faces)

    @property
    def bounds(self) -> Tuple[float, float, float, float, float, float]:
        """(min_x, min_y, min_z, max_x, max_y, max_z)"""
        if not self.vertices:
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        xs = [v[0] for v in self.vertices]
        ys = [v[1] for v in self.vertices]
        zs = [v[2] for v in self.vertices]
        return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))

    def get_elevation_at(self, x: float, y: float, default: float = 0.0) -> float:
        """Barycentric interpolation of elevation Z at (x, y)."""
        pt = Point(x, y)
        for (i0, i1, i2) in self.faces:
            v0 = self.vertices[i0]
            v1 = self.vertices[i1]
            v2 = self.vertices[i2]

            tri = Polygon([(v0[0], v0[1]), (v1[0], v1[1]), (v2[0], v2[1])])
            if tri.distance(pt) < 1e-5 or tri.contains(pt):
                # Barycentric coordinates
                det = (v1[1] - v2[1]) * (v0[0] - v2[0]) + (v2[0] - v1[0]) * (v0[1] - v2[1])
                if abs(det) < 1e-9:
                    continue
                w0 = ((v1[1] - v2[1]) * (x - v2[0]) + (v2[0] - v1[0]) * (y - v2[1])) / det
                w1 = ((v2[1] - v0[1]) * (x - v2[0]) + (v0[0] - v2[0]) * (y - v2[1])) / det
                w2 = 1.0 - w0 - w1
                return float(w0 * v0[2] + w1 * v1[2] + w2 * v2[2])
        return default

    def to_ifc_triangulated_face_set(self, one_based: bool = True) -> Tuple[List[List[float]], List[List[int]]]:
        """Returns (coordinates, coord_indices) for IFC4 IfcTriangulatedFaceSet."""
        coords = [[float(c) for c in v] for v in self.vertices]
        offset = 1 if one_based else 0
        indices = [[int(i + offset) for i in f] for f in self.faces]
        return coords, indices


def _barycentric_z(p0: Tuple[float, float, float], p1: Tuple[float, float, float], p2: Tuple[float, float, float], x: float, y: float) -> float:
    det = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
    if abs(det) < 1e-9:
        return (p0[2] + p1[2] + p2[2]) / 3.0
    w0 = ((p1[1] - p2[1]) * (x - p2[0]) + (p2[0] - p1[0]) * (y - p2[1])) / det
    w1 = ((p2[1] - p0[1]) * (x - p2[0]) + (p0[0] - p2[0]) * (y - p2[1])) / det
    w2 = 1.0 - w0 - w1
    return float(w0 * p0[2] + w1 * p1[2] + w2 * p2[2])


def extract_contours(
    vertices: List[Tuple[float, float, float]],
    faces: List[Tuple[int, int, int]],
    interval: float = 0.50,
) -> List[ContourLine]:
    """
    Extract non-intersecting contour lines from a 3D TIN mesh at specified height intervals.
    """
    if not vertices or not faces or interval <= 0:
        return []

    zs = [v[2] for v in vertices]
    min_z = min(zs)
    max_z = max(zs)

    # Calculate target elevation levels
    start_level = math.ceil(min_z / interval) * interval
    levels = []
    curr = start_level
    while curr < max_z:
        levels.append(round(curr, 4))
        curr += interval

    contours: List[ContourLine] = []

    for z_lvl in levels:
        segments: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []

        for (i0, i1, i2) in faces:
            v0 = vertices[i0]
            v1 = vertices[i1]
            v2 = vertices[i2]

            tri_zs = [v0[2], v1[2], v2[2]]
            if min(tri_zs) <= z_lvl <= max(tri_zs):
                cuts = []
                # Check 3 edges
                edges = [(v0, v1), (v1, v2), (v2, v0)]
                for (pA, pB) in edges:
                    zA, zB = pA[2], pB[2]
                    if (zA <= z_lvl <= zB or zB <= z_lvl <= zA) and abs(zA - zB) > 1e-7:
                        t = (z_lvl - zA) / (zB - zA)
                        cx = pA[0] + t * (pB[0] - pA[0])
                        cy = pA[1] + t * (pB[1] - pA[1])
                        cuts.append((round(cx, 4), round(cy, 4), z_lvl))

                # Keep unique cuts
                unique_cuts = []
                for c in cuts:
                    if not any(math.isclose(c[0], uc[0], abs_tol=1e-4) and math.isclose(c[1], uc[1], abs_tol=1e-4) for uc in unique_cuts):
                        unique_cuts.append(c)

                if len(unique_cuts) == 2:
                    segments.append((unique_cuts[0], unique_cuts[1]))

        # Stitch segments into polylines
        if segments:
            lines = [LineString([(s[0][0], s[0][1]), (s[1][0], s[1][1])]) for s in segments]
            merged = unary_union(lines)
            if isinstance(merged, LineString):
                coords = [(float(c[0]), float(c[1]), z_lvl) for c in merged.coords]
                contours.append(ContourLine(elevation=z_lvl, points=coords))
            elif isinstance(merged, MultiLineString):
                for geom in merged.geoms:
                    coords = [(float(c[0]), float(c[1]), z_lvl) for c in geom.coords]
                    contours.append(ContourLine(elevation=z_lvl, points=coords))

    return contours


def generate_terrain_mesh(
    survey: SurveyData,
    boundary: Optional[Union[List[Tuple[float, float]], Polygon]] = None,
    contour_interval: float = 0.50,
    clip_to_boundary: bool = True,
) -> TerrainMesh:
    """
    Generate a 3D TIN terrain mesh from survey points, optionally clipped to a property boundary.
    """
    pts = survey.points
    if len(pts) < 3:
        raise ValueError("At least 3 survey points are required to generate a terrain mesh.")

    # Determine boundary
    bound_poly = None
    if boundary is not None:
        if isinstance(boundary, Polygon):
            bound_poly = boundary
        elif isinstance(boundary, (list, tuple)) and len(boundary) >= 3:
            bound_poly = Polygon(boundary)
    elif survey.boundary is not None and len(survey.boundary) >= 3:
        bound_poly = Polygon(survey.boundary)

    # 2D Coordinates for Delaunay Triangulation
    coords_2d = np.array([[p.x, p.y] for p in pts], dtype=np.float64)
    tri = Delaunay(coords_2d)

    raw_vertices = [(p.x, p.y, p.z) for p in pts]
    raw_faces = [tuple(int(idx) for idx in simplex) for simplex in tri.simplices]

    if not clip_to_boundary or bound_poly is None:
        contours = extract_contours(raw_vertices, raw_faces, interval=contour_interval)
        return TerrainMesh(vertices=raw_vertices, faces=raw_faces, boundary=bound_poly, contours=contours)

    # Boundary Clipping: Clip each 3D triangle against the 2D boundary polygon
    final_vertices: List[Tuple[float, float, float]] = []
    final_faces: List[Tuple[int, int, int]] = []
    v_cache: Dict[Tuple[float, float, float], int] = {}

    def add_v(vx: float, vy: float, vz: float) -> int:
        key = (round(vx, 5), round(vy, 5), round(vz, 5))
        if key in v_cache:
            return v_cache[key]
        idx = len(final_vertices)
        final_vertices.append((vx, vy, vz))
        v_cache[key] = idx
        return idx

    for (i0, i1, i2) in raw_faces:
        p0 = raw_vertices[i0]
        p1 = raw_vertices[i1]
        p2 = raw_vertices[i2]

        tri_poly = Polygon([(p0[0], p0[1]), (p1[0], p1[1]), (p2[0], p2[1])])
        if not tri_poly.is_valid or tri_poly.area < 1e-7:
            continue

        if not bound_poly.intersects(tri_poly):
            continue

        clipped = bound_poly.intersection(tri_poly)
        if clipped.is_empty:
            continue

        polys_to_tessellate = []
        if isinstance(clipped, Polygon):
            polys_to_tessellate.append(clipped)
        elif isinstance(clipped, MultiPolygon):
            polys_to_tessellate.extend(clipped.geoms)

        for poly in polys_to_tessellate:
            ext = list(poly.exterior.coords)[:-1]  # drop duplicate closing pt
            if len(ext) == 3:
                # Direct triangle
                z0 = _barycentric_z(p0, p1, p2, ext[0][0], ext[0][1])
                z1 = _barycentric_z(p0, p1, p2, ext[1][0], ext[1][1])
                z2 = _barycentric_z(p0, p1, p2, ext[2][0], ext[2][1])
                idx0 = add_v(ext[0][0], ext[0][1], z0)
                idx1 = add_v(ext[1][0], ext[1][1], z1)
                idx2 = add_v(ext[2][0], ext[2][1], z2)
                if idx0 != idx1 and idx1 != idx2 and idx0 != idx2:
                    final_faces.append((idx0, idx1, idx2))
            elif len(ext) > 3:
                # Fan triangulation from centroid or first vertex
                pts_with_z = [(c[0], c[1], _barycentric_z(p0, p1, p2, c[0], c[1])) for c in ext]
                root_idx = add_v(pts_with_z[0][0], pts_with_z[0][1], pts_with_z[0][2])
                for k in range(1, len(pts_with_z) - 1):
                    iA = add_v(pts_with_z[k][0], pts_with_z[k][1], pts_with_z[k][2])
                    iB = add_v(pts_with_z[k + 1][0], pts_with_z[k + 1][1], pts_with_z[k + 1][2])
                    if root_idx != iA and iA != iB and root_idx != iB:
                        final_faces.append((root_idx, iA, iB))

    contours = extract_contours(final_vertices, final_faces, interval=contour_interval)
    return TerrainMesh(vertices=final_vertices, faces=final_faces, boundary=bound_poly, contours=contours)
