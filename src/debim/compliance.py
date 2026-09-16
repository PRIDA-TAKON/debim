"""
Automated Building Code Compliance and Feasibility Rule Engine for debim.
"""

import math
from pathlib import Path
from typing import List, Optional, Tuple, Union

from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedCustomElement,
    ResolvedElement,
    ResolvedManifest,
    ResolvedWall,
    resolve_manifest,
)
from debim.schema import IfcBeam, IfcWall, ProjectManifest, load_manifest


def point_to_segment_distance(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> float:
    """Calculate distance from point (px, py) to line segment (ax, ay)-(bx, by)."""
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = ax + t * dx
    proj_y = ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _segment_distance(
    seg1: Tuple[Tuple[float, float], Tuple[float, float]],
    seg2: Tuple[Tuple[float, float], Tuple[float, float]],
) -> float:
    """Calculate minimum distance between two 2D line segments."""
    (x1, y1), (x2, y2) = seg1
    (x3, y3), (x4, y4) = seg2

    d1 = point_to_segment_distance(x1, y1, x3, y3, x4, y4)
    d2 = point_to_segment_distance(x2, y2, x3, y3, x4, y4)
    d3 = point_to_segment_distance(x3, y3, x1, y1, x2, y2)
    d4 = point_to_segment_distance(x4, y4, x1, y1, x2, y2)

    return min(d1, d2, d3, d4)


def get_element_aabb(elem: ResolvedElement) -> Tuple[float, float, float, float, float, float]:
    """Return 3D Axis-Aligned Bounding Box (min_x, min_y, min_z, max_x, max_y, max_z) for a resolved element."""
    if isinstance(elem, ResolvedColumn):
        x, y = elem.start_point[0], elem.start_point[1]
        w, d = elem.element.profile.width, elem.element.profile.depth
        z1, z2 = elem.start_point[2], elem.end_point[2]
        return (x - w / 2, y - d / 2, min(z1, z2), x + w / 2, y + d / 2, max(z1, z2))

    elif isinstance(elem, ResolvedBeam):
        x1, y1, z = elem.start_point
        x2, y2, _ = elem.end_point
        w, d = elem.element.profile.width, elem.element.profile.depth
        min_x = min(x1, x2) - w / 2
        max_x = max(x1, x2) + w / 2
        min_y = min(y1, y2) - w / 2
        max_y = max(y1, y2) + w / 2
        min_z = z - d
        max_z = z
        return (min_x, min_y, min_z, max_x, max_y, max_z)

    elif isinstance(elem, ResolvedWall):
        x1, y1, z = elem.start_point
        x2, y2, _ = elem.end_point
        t = elem.thickness
        h = elem.height
        min_x = min(x1, x2) - t / 2
        max_x = max(x1, x2) + t / 2
        min_y = min(y1, y2) - t / 2
        max_y = max(y1, y2) + t / 2
        min_z = z
        max_z = z + h
        return (min_x, min_y, min_z, max_x, max_y, max_z)

    elif isinstance(elem, ResolvedCustomElement):
        x, y, z = elem.position
        return (x - 0.5, y - 0.5, z, x + 0.5, y + 0.5, z + 2.0)

    raise TypeError(f"Unsupported resolved element type: {type(elem)}")


def aabb_overlap(
    b1: Tuple[float, float, float, float, float, float],
    b2: Tuple[float, float, float, float, float, float],
    tol: float = 1e-3,
) -> bool:
    """Check if two 3D bounding boxes overlap by more than tolerance."""
    return (
        (b1[0] < b2[3] - tol and b1[3] > b2[0] + tol)
        and (b1[1] < b2[4] - tol and b1[4] > b2[1] + tol)
        and (b1[2] < b2[5] - tol and b1[5] > b2[2] + tol)
    )


def is_valid_connection(elem1: ResolvedElement, elem2: ResolvedElement) -> bool:
    """Determine if overlap between two elements is an expected structural joint connection."""
    # Column and Beam/Wall joint connection
    if isinstance(elem1, ResolvedColumn) and isinstance(elem2, (ResolvedBeam, ResolvedWall)):
        col_x, col_y = elem1.start_point[0], elem1.start_point[1]
        p1 = (elem2.start_point[0], elem2.start_point[1])
        p2 = (elem2.end_point[0], elem2.end_point[1])
        if math.hypot(p1[0] - col_x, p1[1] - col_y) < 1e-2 or math.hypot(p2[0] - col_x, p2[1] - col_y) < 1e-2:
            return True

    if isinstance(elem2, ResolvedColumn) and isinstance(elem1, (ResolvedBeam, ResolvedWall)):
        col_x, col_y = elem2.start_point[0], elem2.start_point[1]
        p1 = (elem1.start_point[0], elem1.start_point[1])
        p2 = (elem1.end_point[0], elem1.end_point[1])
        if math.hypot(p1[0] - col_x, p1[1] - col_y) < 1e-2 or math.hypot(p2[0] - col_x, p2[1] - col_y) < 1e-2:
            return True

    # Beam and Wall stacking/alignment
    if (isinstance(elem1, ResolvedBeam) and isinstance(elem2, ResolvedWall)) or (
        isinstance(elem2, ResolvedBeam) and isinstance(elem1, ResolvedWall)
    ):
        beam = elem1 if isinstance(elem1, ResolvedBeam) else elem2
        wall = elem2 if isinstance(elem1, ResolvedBeam) else elem1
        # Check if wall top sits under beam soffit
        wall_top_z = wall.start_point[2] + wall.height
        beam_soffit_z = beam.start_point[2] - beam.element.profile.depth
        if abs(wall_top_z - beam_soffit_z) < 1e-2:
            return True

    return False


class ComplianceChecker:
    def __init__(self, target: Union[ProjectManifest, ResolvedManifest, Path, str]):
        if isinstance(target, (str, Path)):
            self.manifest = load_manifest(target)
            self.resolved = resolve_manifest(self.manifest)
        elif isinstance(target, ProjectManifest):
            self.manifest = target
            self.resolved = resolve_manifest(target)
        elif isinstance(target, ResolvedManifest):
            self.resolved = target
            self.manifest = target.manifest
        else:
            raise TypeError(f"Unsupported target type for ComplianceChecker: {type(target)}")

    def calculate_clear_height(self, storey_id: str) -> float:
        """
        Calculate clear vertical ceiling height for a storey:
        clear_height = storey.height - max_beam_depth_in_storey
        """
        storey = None
        for s in self.manifest.spatial_structure.storeys:
            if s.id == storey_id:
                storey = s
                break
        if not storey:
            raise ValueError(f"Storey '{storey_id}' not found in spatial structure.")

        max_beam_depth = 0.0
        storey_top_z = storey.elevation + storey.height

        for beam in self.resolved.beams:
            b_storey = beam.element.placement.storey
            b_z = beam.start_point[2]

            # Beam is in storey if assigned to storey_id or located at top/bottom elevation of storey
            if (
                b_storey == storey_id
                or abs(b_z - storey_top_z) < 1e-3
                or abs(b_z - storey.elevation) < 1e-3
            ):
                depth = beam.element.profile.depth
                if depth > max_beam_depth:
                    max_beam_depth = depth

        return storey.height - max_beam_depth

    def calculate_total_floor_area(self) -> float:
        """Calculate total floor area of the building based on grid extent and storeys."""
        axes_x = list(self.manifest.grids.axes_x.values())
        axes_y = list(self.manifest.grids.axes_y.values())

        if not axes_x or not axes_y:
            return 0.0

        min_x, max_x = min(axes_x), max(axes_x)
        min_y, max_y = min(axes_y), max(axes_y)

        footprint_area = (max_x - min_x) * (max_y - min_y)
        num_storeys = len(self.manifest.spatial_structure.storeys)

        return footprint_area * num_storeys

    def calculate_setback(
        self,
        wall: Union[IfcWall, ResolvedWall, str],
        site_boundary: Optional[
            Union[Tuple[float, float, float, float], List[Tuple[float, float]]]
        ] = None,
    ) -> float:
        """
        Calculate distance from wall to site boundary line.
        If site_boundary is None, defaults to grid extent bounding box expanded by a default setback (2.0m).
        """
        r_wall: Optional[ResolvedWall] = None
        if isinstance(wall, str):
            elem = self.resolved.get_element_by_tag(wall)
            if isinstance(elem, ResolvedWall):
                r_wall = elem
        elif isinstance(wall, ResolvedWall):
            r_wall = wall
        elif isinstance(wall, IfcWall):
            for w in self.resolved.walls:
                if w.tag == wall.tag:
                    r_wall = w
                    break

        if not r_wall:
            raise ValueError(f"Wall '{wall}' not found in resolved manifest.")

        if site_boundary is None:
            axes_x = list(self.manifest.grids.axes_x.values())
            axes_y = list(self.manifest.grids.axes_y.values())
            min_x, max_x = min(axes_x), max(axes_x)
            min_y, max_y = min(axes_y), max(axes_y)
            offset = 2.0
            boundary_box = (
                min_x - offset,
                min_y - offset,
                max_x + offset,
                max_y + offset,
            )
            boundary_segments = [
                ((boundary_box[0], boundary_box[1]), (boundary_box[2], boundary_box[1])),
                ((boundary_box[2], boundary_box[1]), (boundary_box[2], boundary_box[3])),
                ((boundary_box[2], boundary_box[3]), (boundary_box[0], boundary_box[3])),
                ((boundary_box[0], boundary_box[3]), (boundary_box[0], boundary_box[1])),
            ]
        elif isinstance(site_boundary, tuple) and len(site_boundary) == 4:
            b_min_x, b_min_y, b_max_x, b_max_y = site_boundary
            boundary_segments = [
                ((b_min_x, b_min_y), (b_max_x, b_min_y)),
                ((b_max_x, b_min_y), (b_max_x, b_max_y)),
                ((b_max_x, b_max_y), (b_min_x, b_max_y)),
                ((b_min_x, b_max_y), (b_min_x, b_min_y)),
            ]
        elif isinstance(site_boundary, list):
            boundary_segments = []
            n = len(site_boundary)
            for i in range(n):
                p1 = site_boundary[i]
                p2 = site_boundary[(i + 1) % n]
                boundary_segments.append((p1, p2))
        else:
            raise ValueError(f"Invalid site_boundary format: {site_boundary}")

        wx1, wy1 = r_wall.start_point[0], r_wall.start_point[1]
        wx2, wy2 = r_wall.end_point[0], r_wall.end_point[1]
        wall_seg = ((wx1, wy1), (wx2, wy2))

        min_dist = float("inf")
        for b_seg in boundary_segments:
            d = _segment_distance(wall_seg, b_seg)
            if d < min_dist:
                min_dist = d

        return min_dist

    def detect_clashes(self) -> List[Tuple[str, str]]:
        """
        Check for unintended 3D bounding box overlaps between structural elements.
        Returns list of clashing element tag pairs.
        """
        clashes: List[Tuple[str, str]] = []
        resolved_elems = self.resolved.elements
        n = len(resolved_elems)

        aabbs = [get_element_aabb(elem) for elem in resolved_elems]

        for i in range(n):
            for j in range(i + 1, n):
                elem1, aabb1 = resolved_elems[i], aabbs[i]
                elem2, aabb2 = resolved_elems[j], aabbs[j]

                if is_valid_connection(elem1, elem2):
                    continue

                if aabb_overlap(aabb1, aabb2):
                    clashes.append((elem1.tag, elem2.tag))

        return clashes


def calculate_clear_height(
    target: Union[ProjectManifest, ResolvedManifest, Path, str], storey_id: str
) -> float:
    """Calculate clear vertical height for a given storey."""
    checker = ComplianceChecker(target)
    return checker.calculate_clear_height(storey_id)


def calculate_total_floor_area(
    target: Union[ProjectManifest, ResolvedManifest, Path, str]
) -> float:
    """Calculate total floor area for the project."""
    checker = ComplianceChecker(target)
    return checker.calculate_total_floor_area()


def calculate_setback(
    target: Union[ProjectManifest, ResolvedManifest, Path, str],
    wall: Union[IfcWall, ResolvedWall, str],
    site_boundary: Optional[
        Union[Tuple[float, float, float, float], List[Tuple[float, float]]]
    ] = None,
) -> float:
    """Calculate setback distance from a wall to site boundary."""
    checker = ComplianceChecker(target)
    return checker.calculate_setback(wall, site_boundary)


def detect_clashes(
    target: Union[ProjectManifest, ResolvedManifest, Path, str]
) -> List[Tuple[str, str]]:
    """Detect critical spatial 3D clashes between structural elements."""
    checker = ComplianceChecker(target)
    return checker.detect_clashes()
