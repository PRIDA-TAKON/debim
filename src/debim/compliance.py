"""
Automated Building Code Compliance and Feasibility Rule Engine for debim.
"""

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedCustomElement,
    ResolvedDoor,
    ResolvedElement,
    ResolvedFooting,
    ResolvedManifest,
    ResolvedMember,
    ResolvedRoof,
    ResolvedSlab,
    ResolvedStair,
    ResolvedStairFlight,
    ResolvedWall,
    ResolvedWindow,
    resolve_manifest,
)
from debim.schema import ComplianceRule, IfcBeam, IfcWall, ProjectManifest, load_manifest


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
    if hasattr(elem, "bounding_box") and isinstance(elem.bounding_box, dict) and "min_x" in elem.bounding_box:
        b = elem.bounding_box
        return (b["min_x"], b["min_y"], b["min_z"], b["max_x"], b["max_y"], b["max_z"])

    elif isinstance(elem, ResolvedColumn):
        x, y = elem.start_point[0], elem.start_point[1]
        w = getattr(elem, "width", getattr(elem.element.profile, "width", 0.3))
        d = getattr(elem, "depth", getattr(elem.element.profile, "depth", 0.3))
        z1, z2 = elem.start_point[2], elem.end_point[2]
        return (x - w / 2, y - d / 2, min(z1, z2), x + w / 2, y + d / 2, max(z1, z2))

    elif isinstance(elem, (ResolvedBeam, ResolvedMember)):
        x1, y1, z1 = elem.start_point
        x2, y2, z2 = elem.end_point
        w = getattr(elem, "width", getattr(elem.element.profile, "width", 0.2))
        d = getattr(elem, "depth", getattr(elem.element.profile, "depth", 0.4))
        min_x = min(x1, x2) - w / 2
        max_x = max(x1, x2) + w / 2
        min_y = min(y1, y2) - w / 2
        max_y = max(y1, y2) + w / 2
        min_z = min(z1, z2) - d
        max_z = max(z1, z2)
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
        if elem.dimensions:
            w, d, h = elem.dimensions.width, elem.dimensions.depth or elem.dimensions.width, elem.dimensions.height
            return (x - w / 2, y - d / 2, z, x + w / 2, y + d / 2, z + h)
        return (x - 0.5, y - 0.5, z, x + 0.5, y + 0.5, z + 2.0)

    elif isinstance(elem, (ResolvedDoor, ResolvedWindow)):
        x, y, z = elem.position
        w = elem.width
        h = elem.height
        return (x - w / 2, y - w / 2, z, x + w / 2, y + w / 2, z + h)

    elif isinstance(elem, ResolvedSlab):
        xs = [pt[0] for pt in elem.polygon]
        ys = [pt[1] for pt in elem.polygon]
        zs = [pt[2] for pt in elem.polygon]
        t = elem.thickness
        min_z = min(zs) - t
        max_z = max(zs)
        return (min(xs), min(ys), min_z, max(xs), max(ys), max_z)

    elif isinstance(elem, ResolvedFooting):
        x, y, z = elem.position
        w = elem.width
        d = elem.depth
        t = elem.thickness
        return (x - w / 2, y - d / 2, z - t, x + w / 2, y + d / 2, z)

    elif isinstance(elem, (ResolvedDuctSegment, ResolvedPipeSegment, ResolvedCableCarrierSegment)):
        wpts = elem.waypoints if elem.waypoints else [elem.start_point, elem.end_point]
        xs = [p[0] for p in wpts]
        ys = [p[1] for p in wpts]
        zs = [p[2] for p in wpts]
        r = max(getattr(elem, "width", 0.0), getattr(elem, "height", 0.0), getattr(elem, "nominal_diameter", 0.1)) / 2.0
        r = max(r, 0.05)
        return (min(xs) - r, min(ys) - r, min(zs) - r, max(xs) + r, max(ys) + r, max(zs) + r)

    elif hasattr(elem, "dimensions") and hasattr(elem, "position"):
        x, y, z = elem.position
        dims = elem.dimensions
        if isinstance(dims, (tuple, list)) and len(dims) >= 3:
            w, d, h = dims[0], dims[1], dims[2]
        else:
            w = getattr(dims, "width", 0.5)
            d = getattr(dims, "depth", w)
            h = getattr(dims, "height", 0.5)
        return (x - w / 2, y - d / 2, z, x + w / 2, y + d / 2, z + h)

    elif isinstance(elem, ResolvedStair):
        xs, ys, zs = [], [], []
        if elem.landing_polygon:
            xs.extend(p[0] for p in elem.landing_polygon)
            ys.extend(p[1] for p in elem.landing_polygon)
            zs.extend(p[2] for p in elem.landing_polygon)
        for st in elem.steps:
            if hasattr(st, "polygon") and st.polygon:
                xs.extend(p[0] for p in st.polygon)
                ys.extend(p[1] for p in st.polygon)
                zs.extend(p[2] for p in st.polygon)
            elif hasattr(st, "position"):
                xs.append(st.position[0])
                ys.append(st.position[1])
                zs.append(st.position[2])
        if not xs:
            for fl in elem.flights:
                xs.extend([fl.start_point[0], fl.end_point[0]])
                ys.extend([fl.start_point[1], fl.end_point[1]])
                zs.extend([fl.start_point[2], fl.end_point[2]])
        w = getattr(elem.element, "width", 1.0)
        return (min(xs) - w / 2, min(ys) - w / 2, min(zs), max(xs) + w / 2, max(ys) + w / 2, max(zs) + 1.0)

    elif isinstance(elem, ResolvedStairFlight):
        xs = [elem.start_point[0], elem.end_point[0]]
        ys = [elem.start_point[1], elem.end_point[1]]
        zs = [elem.start_point[2], elem.end_point[2]]
        w = elem.width
        return (min(xs) - w / 2, min(ys) - w / 2, min(zs), max(xs) + w / 2, max(ys) + w / 2, max(zs) + 1.0)

    elif isinstance(elem, ResolvedRoof):
        xs = [pt[0] for pt in elem.footprint_polygon]
        ys = [pt[1] for pt in elem.footprint_polygon]
        min_z = min(elem.eaves_elevation, elem.ridge_elevation)
        max_z = max(elem.eaves_elevation, elem.ridge_elevation)
        return (min(xs), min(ys), min_z, max(xs), max(ys), max_z)

    elif hasattr(elem, "position"):
        x, y, z = elem.position
        return (x - 0.5, y - 0.5, z - 0.5, x + 0.5, y + 0.5, z + 0.5)

    elif hasattr(elem, "start_point") and hasattr(elem, "end_point"):
        x1, y1, z1 = elem.start_point
        x2, y2, z2 = elem.end_point
        return (min(x1, x2) - 0.2, min(y1, y2) - 0.2, min(z1, z2) - 0.2, max(x1, x2) + 0.2, max(y1, y2) + 0.2, max(z1, z2) + 0.2)

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
    if isinstance(elem1, (ResolvedDoor, ResolvedWindow)) or isinstance(elem2, (ResolvedDoor, ResolvedWindow)):
        return True

    # Stair connections (stair rests on slab, ground, column, beam, wall)
    if isinstance(elem1, (ResolvedStair, ResolvedStairFlight)) or isinstance(elem2, (ResolvedStair, ResolvedStairFlight)):
        other = elem2 if isinstance(elem1, (ResolvedStair, ResolvedStairFlight)) else elem1
        if isinstance(other, (ResolvedBeam, ResolvedColumn, ResolvedWall, ResolvedSlab)):
            return True

    # Roof connections (roof supported by column, beam, wall, slab or adjacent roof wing)
    if isinstance(elem1, ResolvedRoof) or isinstance(elem2, ResolvedRoof):
        other = elem2 if isinstance(elem1, ResolvedRoof) else elem1
        if isinstance(other, (ResolvedBeam, ResolvedColumn, ResolvedWall, ResolvedSlab, ResolvedRoof)):
            return True

    # Column and Beam/Wall joint connection (endpoint or embedded along segment)
    if isinstance(elem1, ResolvedColumn) and isinstance(elem2, (ResolvedBeam, ResolvedWall)):
        col_x, col_y = elem1.start_point[0], elem1.start_point[1]
        x1, y1 = elem2.start_point[0], elem2.start_point[1]
        x2, y2 = elem2.end_point[0], elem2.end_point[1]
        dist = point_to_segment_distance(col_x, col_y, x1, y1, x2, y2)
        if dist < 1e-2:
            return True

    if isinstance(elem2, ResolvedColumn) and isinstance(elem1, (ResolvedBeam, ResolvedWall)):
        col_x, col_y = elem2.start_point[0], elem2.start_point[1]
        x1, y1 = elem1.start_point[0], elem1.start_point[1]
        x2, y2 = elem1.end_point[0], elem1.end_point[1]
        dist = point_to_segment_distance(col_x, col_y, x1, y1, x2, y2)
        if dist < 1e-2:
            return True

    # Beam and Wall stacking/alignment (walls sitting on beams or walls under beams)
    if (isinstance(elem1, ResolvedBeam) and isinstance(elem2, ResolvedWall)) or (
        isinstance(elem2, ResolvedBeam) and isinstance(elem1, ResolvedWall)
    ):
        beam = elem1 if isinstance(elem1, ResolvedBeam) else elem2
        wall = elem2 if isinstance(elem1, ResolvedBeam) else elem1
        wall_top_z = wall.start_point[2] + wall.height
        wall_base_z = wall.start_point[2]
        beam_top_z = beam.start_point[2]
        beam_soffit_z = beam.start_point[2] - beam.element.profile.depth
        if abs(wall_top_z - beam_soffit_z) < 1e-2 or wall_top_z <= beam_top_z:
            return True
        if abs(wall_base_z - beam_top_z) < 2e-2 or wall_base_z >= beam_soffit_z - 1e-2:
            return True

    # Beam-to-beam framing joints
    if isinstance(elem1, ResolvedBeam) and isinstance(elem2, ResolvedBeam):
        p1 = (elem1.start_point[0], elem1.start_point[1])
        p2 = (elem1.end_point[0], elem1.end_point[1])
        q1 = (elem2.start_point[0], elem2.start_point[1])
        q2 = (elem2.end_point[0], elem2.end_point[1])
        if any(math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-2 for a in (p1, p2) for b in (q1, q2)):
            return True

    # Wall-to-wall corner joints
    if isinstance(elem1, ResolvedWall) and isinstance(elem2, ResolvedWall):
        p1 = (elem1.start_point[0], elem1.start_point[1])
        p2 = (elem1.end_point[0], elem1.end_point[1])
        q1 = (elem2.start_point[0], elem2.start_point[1])
        q2 = (elem2.end_point[0], elem2.end_point[1])
        if any(math.hypot(a[0] - b[0], a[1] - b[1]) < 1e-2 for a in (p1, p2) for b in (q1, q2)):
            return True

    # Slab resting on beams, columns, or walls
    if isinstance(elem1, ResolvedSlab) or isinstance(elem2, ResolvedSlab):
        slab = elem1 if isinstance(elem1, ResolvedSlab) else elem2
        other = elem2 if isinstance(elem1, ResolvedSlab) else elem1
        if isinstance(other, (ResolvedBeam, ResolvedColumn, ResolvedWall)):
            return True

    # Footing and Column connection
    if (isinstance(elem1, ResolvedFooting) and isinstance(elem2, ResolvedColumn)) or (
        isinstance(elem2, ResolvedFooting) and isinstance(elem1, ResolvedColumn)
    ):
        footing = elem1 if isinstance(elem1, ResolvedFooting) else elem2
        col = elem2 if isinstance(elem1, ResolvedFooting) else elem1
        fx, fy, _ = footing.position
        cx, cy = col.start_point[0], col.start_point[1]
        if math.hypot(fx - cx, fy - cy) < 1e-2:
            return True

    return False


class ComplianceCheckResult(BaseModel):
    rule: str
    passed: bool
    message: str
    standard: Optional[str] = "TH-MINISTERIAL-REG-55"
    details: Dict[str, Any] = Field(default_factory=dict)


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

    def evaluate_manifest_compliances(
        self, site_boundary: Optional[Any] = None
    ) -> List[ComplianceCheckResult]:
        """Evaluate declarative compliance rules configured on the manifest."""
        results: List[ComplianceCheckResult] = []
        rules = self.manifest.compliances
        if not rules:
            return results

        effective_boundary = site_boundary
        if effective_boundary is None and self.manifest.site:
            effective_boundary = (
                self.manifest.site.bounding_box or self.manifest.site.boundary
            )

        for rule_cfg in rules:
            if not rule_cfg.enabled:
                continue

            r_code = rule_cfg.rule.upper()

            if "CEILING_HEIGHT" in r_code or "CLEAR_HEIGHT" in r_code:
                min_h = rule_cfg.threshold or 2.40
                passed = True
                failed_storeys = []
                for st in self.manifest.spatial_structure.storeys:
                    s_id_lower = st.id.lower()
                    s_name_lower = (st.name or "").lower()
                    # Skip non-habitable roof/foundation levels in ceiling height check
                    if any(k in s_id_lower or k in s_name_lower for k in ["roof", "parapet", "หลังคา", "footing", "foundation"]):
                        continue
                    ch = self.calculate_clear_height(st.id)
                    if ch < min_h:
                        passed = False
                        failed_storeys.append(f"{st.name} ({ch:.2f}m < {min_h:.2f}m)")
                msg = (
                    f"Passed minimum clear ceiling height ({min_h:.2f}m)"
                    if passed
                    else f"Clear height violation on: {', '.join(failed_storeys)}"
                )
                results.append(
                    ComplianceCheckResult(
                        rule=rule_cfg.rule,
                        passed=passed,
                        message=msg,
                        standard=rule_cfg.standard,
                        details={"threshold": min_h},
                    )
                )

            elif "SETBACK_OPENING" in r_code:
                min_sb = rule_cfg.threshold or 2.00
                passed = True
                failed_walls = []
                for wall in self.resolved.walls:
                    if wall.children:
                        dist = self.calculate_setback(wall, site_boundary=effective_boundary)
                        if dist < min_sb:
                            passed = False
                            failed_walls.append(f"{wall.tag} ({dist:.2f}m < {min_sb:.2f}m)")
                msg = (
                    f"Passed wall setback with openings (>={min_sb:.2f}m)"
                    if passed
                    else f"Wall with openings setback violation on: {', '.join(failed_walls)}"
                )
                results.append(
                    ComplianceCheckResult(
                        rule=rule_cfg.rule,
                        passed=passed,
                        message=msg,
                        standard=rule_cfg.standard,
                        details={"threshold": min_sb},
                    )
                )

            elif "SETBACK_BLIND" in r_code:
                min_sb = rule_cfg.threshold or 0.50
                passed = True
                failed_walls = []
                for wall in self.resolved.walls:
                    if not wall.children:
                        dist = self.calculate_setback(wall, site_boundary=effective_boundary)
                        if dist < min_sb:
                            passed = False
                            failed_walls.append(f"{wall.tag} ({dist:.2f}m < {min_sb:.2f}m)")
                msg = (
                    f"Passed blind wall setback (>={min_sb:.2f}m)"
                    if passed
                    else f"Blind wall setback violation on: {', '.join(failed_walls)}"
                )
                results.append(
                    ComplianceCheckResult(
                        rule=rule_cfg.rule,
                        passed=passed,
                        message=msg,
                        standard=rule_cfg.standard,
                        details={"threshold": min_sb},
                    )
                )

            elif "CLASH" in r_code:
                clashes = self.detect_clashes()
                passed = len(clashes) == 0
                msg = "No structural clashes detected" if passed else f"Detected {len(clashes)} clashes: {clashes}"
                results.append(
                    ComplianceCheckResult(
                        rule=rule_cfg.rule,
                        passed=passed,
                        message=msg,
                        standard=rule_cfg.standard,
                        details={"clashes": clashes},
                    )
                )

            elif "FLOOR_AREA" in r_code or "AREA_LIMIT" in r_code:
                max_a = rule_cfg.threshold or 10000.0
                tot_a = self.calculate_total_floor_area()
                passed = tot_a <= max_a
                msg = (
                    f"Passed total floor area limit ({tot_a:.2f}m2 <= {max_a:.2f}m2)"
                    if passed
                    else f"Total floor area {tot_a:.2f}m2 exceeds limit {max_a:.2f}m2"
                )
                results.append(
                    ComplianceCheckResult(
                        rule=rule_cfg.rule,
                        passed=passed,
                        message=msg,
                        standard=rule_cfg.standard,
                        details={"total_area": tot_a, "limit": max_a},
                    )
                )

        return results



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


def check_topological_continuity(
    target: Union[ProjectManifest, ResolvedManifest, Path, str]
) -> List[Dict[str, Any]]:
    """
    Perform topological structural continuity check.
    Identifies floating columns (unsupported bases), unsupported beams, or dangling cantilevers.
    """
    if isinstance(target, (str, Path)):
        manifest = load_manifest(target)
        resolved = resolve_manifest(manifest)
    elif isinstance(target, ProjectManifest):
        resolved = resolve_manifest(target)
    elif isinstance(target, ResolvedManifest):
        resolved = target
    else:
        raise TypeError(f"Unsupported target type for check_topological_continuity: {type(target)}")

    warnings: List[Dict[str, Any]] = []

    # 1. Check Columns
    for col in resolved.columns:
        cx, cy, cz = col.start_point
        # Check if grounded at or below elevation 0.0 or connected to footing
        is_grounded = cz <= 0.05
        has_support = False

        if is_grounded:
            has_support = True
        else:
            # Check footings
            for footing in resolved.footings:
                fx, fy, fz = footing.position
                if math.hypot(cx - fx, cy - fy) <= (footing.width / 2.0 + 0.2) and abs(cz - fz) <= 0.2:
                    has_support = True
                    break

            # Check beams supporting column base
            if not has_support:
                for beam in resolved.beams:
                    bx1, by1, bz = beam.start_point
                    bx2, by2, _ = beam.end_point
                    dist = point_to_segment_distance(cx, cy, bx1, by1, bx2, by2)
                    b_w = getattr(beam, "width", 0.2)
                    if dist <= (b_w / 2.0 + 0.2) and abs(cz - bz) <= 0.3:
                        has_support = True
                        break

            # Check walls supporting column base
            if not has_support:
                for wall in resolved.walls:
                    wx1, wy1, wz = wall.start_point
                    wx2, wy2, _ = wall.end_point
                    wall_top_z = wz + wall.height
                    dist = point_to_segment_distance(cx, cy, wx1, wy1, wx2, wy2)
                    if dist <= (wall.thickness / 2.0 + 0.2) and abs(cz - wall_top_z) <= 0.3:
                        has_support = True
                        break

            # Check slabs supporting column base
            if not has_support:
                for slab in resolved.slabs:
                    sz = slab.center[2]
                    if abs(cz - sz) <= 0.3:
                        # Check 2D point in slab polygon
                        pts_2d = [(p[0], p[1]) for p in slab.polygon]
                        from debim.geometry2d import point_in_polygon
                        if point_in_polygon((cx, cy), pts_2d):
                            has_support = True
                            break

            # Check other columns below
            if not has_support:
                for other_col in resolved.columns:
                    if other_col.tag == col.tag:
                        continue
                    ocx, ocy, ocz_top = other_col.end_point
                    if math.hypot(cx - ocx, cy - ocy) <= 0.2 and abs(cz - ocz_top) <= 0.2:
                        has_support = True
                        break

        if not has_support:
            warnings.append({
                "type": "FLOATING_COLUMN",
                "tag": col.tag,
                "class": "IfcColumn",
                "position": col.start_point,
                "message": f"Floating Column '{col.tag}' at position ({cx:.2f}, {cy:.2f}, {cz:.2f}) has no supporting footing, beam, wall, or slab underneath.",
            })

    # 2. Check Beams
    for beam in resolved.beams:
        sp1 = beam.start_point
        sp2 = beam.end_point

        def is_point_supported(pt: Tuple[float, float, float]) -> bool:
            px, py, pz = pt
            # Check column support
            for col in resolved.columns:
                cx, cy = col.start_point[0], col.start_point[1]
                c_w = getattr(col, "width", 0.3)
                col_bot_z = min(col.start_point[2], col.end_point[2])
                col_top_z = max(col.start_point[2], col.end_point[2])
                if math.hypot(px - cx, py - cy) <= (c_w / 2.0 + 0.3) and (col_bot_z - 0.2 <= pz <= col_top_z + 0.2):
                    return True

            # Check wall support
            for wall in resolved.walls:
                wx1, wy1, wz = wall.start_point
                wx2, wy2, _ = wall.end_point
                dist = point_to_segment_distance(px, py, wx1, wy1, wx2, wy2)
                if dist <= (wall.thickness / 2.0 + 0.3) and (wz - 0.2 <= pz <= wz + wall.height + 0.2):
                    return True

            # Check supporting other beam
            for other_beam in resolved.beams:
                if other_beam.tag == beam.tag:
                    continue
                obx1, oby1, obz = other_beam.start_point
                obx2, oby2, _ = other_beam.end_point
                dist = point_to_segment_distance(px, py, obx1, oby1, obx2, oby2)
                ob_w = getattr(other_beam, "width", 0.2)
                if dist <= (ob_w / 2.0 + 0.3) and abs(pz - obz) <= 0.3:
                    return True

            # Check column/footing/slab directly
            for slab in resolved.slabs:
                if abs(pz - slab.center[2]) <= 0.3:
                    pts_2d = [(p[0], p[1]) for p in slab.polygon]
                    from debim.geometry2d import point_in_polygon
                    if point_in_polygon((px, py), pts_2d):
                        return True

            return False

        s1_ok = is_point_supported(sp1)
        s2_ok = is_point_supported(sp2)

        if not s1_ok and not s2_ok:
            warnings.append({
                "type": "UNSUPPORTED_BEAM",
                "tag": beam.tag,
                "class": "IfcBeam",
                "position": sp1,
                "message": f"Unsupported Beam '{beam.tag}' span from ({sp1[0]:.2f}, {sp1[1]:.2f}, {sp1[2]:.2f}) to ({sp2[0]:.2f}, {sp2[1]:.2f}, {sp2[2]:.2f}) has no support at either endpoint.",
            })
        elif not s1_ok or not s2_ok:
            unsupported_pt = sp1 if not s1_ok else sp2
            warnings.append({
                "type": "DANGLING_CANTILEVER",
                "tag": beam.tag,
                "class": "IfcBeam",
                "position": unsupported_pt,
                "message": f"Beam '{beam.tag}' has dangling/unsupported endpoint at ({unsupported_pt[0]:.2f}, {unsupported_pt[1]:.2f}, {unsupported_pt[2]:.2f}).",
            })

    return warnings


def detect_mep_structural_clashes(
    target: Union[ProjectManifest, ResolvedManifest, Path, str]
) -> List[Dict[str, Any]]:
    """
    Detect bounding-box AABB clashes between MEP elements (ducts, pipes, conduits, equipment)
    and structural elements (beams, columns).
    """
    if isinstance(target, (str, Path)):
        manifest = load_manifest(target)
        resolved = resolve_manifest(manifest)
    elif isinstance(target, ProjectManifest):
        resolved = resolve_manifest(target)
    elif isinstance(target, ResolvedManifest):
        resolved = target
    else:
        raise TypeError(f"Unsupported target type for detect_mep_structural_clashes: {type(target)}")

    struct_elems: List[ResolvedElement] = []
    struct_elems.extend(resolved.beams)
    struct_elems.extend(resolved.columns)

    mep_elems: List[ResolvedElement] = []
    mep_elems.extend(resolved.ducts)
    mep_elems.extend(resolved.pipes)
    mep_elems.extend(resolved.conduits)
    mep_elems.extend(resolved.air_terminals)
    mep_elems.extend(resolved.dampers)
    mep_elems.extend(resolved.flow_controllers)
    mep_elems.extend(resolved.unitary_equipments)
    mep_elems.extend(resolved.distribution_flow_elements)
    mep_elems.extend(resolved.flow_moving_devices)
    mep_elems.extend(resolved.energy_conversion_devices)

    clashes: List[Dict[str, Any]] = []

    for mep in mep_elems:
        try:
            mep_aabb = get_element_aabb(mep)
        except Exception:
            continue

        mep_cls = getattr(mep, "ifc_class", mep.__class__.__name__.replace("Resolved", "Ifc"))

        for struct in struct_elems:
            try:
                struct_aabb = get_element_aabb(struct)
            except Exception:
                continue

            if aabb_overlap(mep_aabb, struct_aabb, tol=1e-3):
                struct_cls = getattr(struct, "ifc_class", struct.__class__.__name__.replace("Resolved", "Ifc"))
                clashes.append({
                    "mep_tag": mep.tag,
                    "mep_class": mep_cls,
                    "struct_tag": struct.tag,
                    "struct_class": struct_cls,
                    "mep_aabb": mep_aabb,
                    "struct_aabb": struct_aabb,
                    "message": f"AABB Clash: MEP {mep_cls} '{mep.tag}' intersects Structural {struct_cls} '{struct.tag}'",
                })

    return clashes
