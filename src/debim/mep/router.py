"""
Level 2 Constraint-Aware MEP Auto-Routing Engine.
Implements 3D Constrained A* pathfinding on corridor grid with wall-hugging preference,
under-slab suspension, obstacle avoidance (columns/beams), and monotonic drainage slopes.
"""

from typing import List, Tuple, Dict, Any, Optional, Union, Set
import math
import heapq
from debim.compat import BaseModel, Field, ConfigDict


class PipeConnectSpec(BaseModel):
    """Specification for auto-routing connection between two MEP elements."""
    model_config = ConfigDict(extra="ignore")

    from_tag: str = Field(alias="from")
    to_tag: str = Field(alias="to")
    wall_hugging: bool = True
    slope: Optional[float] = None


class MEPRouter:
    """
    3D Constraint-Aware A* Auto-Router for MEP Systems.
    """

    def __init__(self, manifest: Any, resolver: Optional[Any] = None):
        self.manifest = manifest
        self.resolver = resolver

    def _get_element_by_tag(self, tag: str) -> Optional[Any]:
        if self.resolver and hasattr(self.resolver, "get_element_by_tag"):
            elem = self.resolver.get_element_by_tag(tag)
            if elem is not None:
                return elem
        if hasattr(self.manifest, "elements"):
            for e in self.manifest.elements:
                if getattr(e, "tag", None) == tag:
                    return e
        return None

    def _get_element_3d_position(self, elem: Any, is_source: bool = True) -> Tuple[float, float, float]:
        """Extract 3D world position for an element or its connection port."""
        if hasattr(elem, "position") and isinstance(elem.position, (tuple, list)):
            x, y, z = elem.position
        elif hasattr(elem, "start_point") and isinstance(elem.start_point, (tuple, list)):
            x, y, z = elem.start_point if is_source else getattr(elem, "end_point", elem.start_point)
        else:
            pos = None
            if self.resolver is not None:
                if hasattr(self.resolver, "get_element_by_tag"):
                    r_elem = self.resolver.get_element_by_tag(getattr(elem, "tag", str(elem)))
                    if r_elem:
                        if hasattr(r_elem, "position"):
                            pos = r_elem.position
                        elif hasattr(r_elem, "start_point"):
                            pos = r_elem.start_point if is_source else getattr(r_elem, "end_point", r_elem.start_point)

                if pos is None and hasattr(self.resolver, "resolve_terminal") and hasattr(elem, "placement"):
                    try:
                        r_term = self.resolver.resolve_terminal(elem)
                        pos = r_term.position
                    except Exception:
                        pass

            if pos is not None:
                x, y, z = pos
            else:
                pl = getattr(elem, "placement", None)
                st_name = getattr(pl, "storey", "L1") if pl else "L1"
                st_elev = 0.0
                if hasattr(self.manifest, "spatial_structure") and self.manifest.spatial_structure:
                    for st in self.manifest.spatial_structure.storeys:
                        if st.id == st_name:
                            st_elev = st.elevation
                            break

                axes_x = getattr(self.manifest.grids, "axes_x", {}) if hasattr(self.manifest, "grids") else {}
                axes_y = getattr(self.manifest.grids, "axes_y", {}) if hasattr(self.manifest, "grids") else {}

                if pl and getattr(pl, "from_grid", None):
                    gx, gy = pl.from_grid
                    fo = getattr(pl, "from_offset", (0.0, 0.0, 0.0))
                    to = getattr(pl, "to_offset", (0.0, 0.0, 0.0))
                    x = axes_x.get(gx, 0.0) + fo[0]
                    y = axes_y.get(gy, 0.0) + fo[1]
                    if not is_source and "Pipe" in str(getattr(elem, "class_", "")):
                        z = st_elev + min(fo[2], to[2])
                    else:
                        cur_o = fo if is_source else to
                        z = st_elev + cur_o[2]
                elif pl and getattr(pl, "grid", None):
                    gx, gy = pl.grid
                    x = axes_x.get(gx, 0.0) + getattr(pl, "offset_x", 0.0)
                    y = axes_y.get(gy, 0.0) + getattr(pl, "offset_y", 0.0)
                    z = st_elev + getattr(pl, "offset_z", 0.0)
                else:
                    x, y, z = (0.0, 0.0, st_elev)

        # Port adjustments if ports are declared
        ports = getattr(elem, "ports", None) or []
        if ports:
            target_direction = "SOURCE" if is_source else "SINK"
            for p in ports:
                p_dir = getattr(p, "flow_direction", "")
                p_offset = getattr(p, "offset", (0.0, 0.0, 0.0))
                if p_dir == target_direction or not target_direction:
                    return (x + p_offset[0], y + p_offset[1], z + p_offset[2])

        # If sanitary terminal (e.g. WC-01), adjust waste outlet height/offset
        elem_cls = getattr(elem, "class_", getattr(elem, "__class__", "").__name__)
        if "SanitaryTerminal" in str(elem_cls) or "WC" in getattr(elem, "tag", ""):
            return (x, y, z + 0.10)

        return (x, y, z)

    def route(
        self,
        from_tag: str,
        to_tag: str,
        system_type: str = "SOIL",
        slope: float = 0.0,
        wall_hugging: bool = True,
        nominal_diameter: float = 0.10,
    ) -> List[Tuple[float, float, float]]:
        """
        Execute 3D Constrained A* routing from from_tag to to_tag.
        """
        elem_from = self._get_element_by_tag(from_tag)
        elem_to = self._get_element_by_tag(to_tag)

        if not elem_from:
            raise ValueError(f"Source element '{from_tag}' not found in project manifest")
        if not elem_to:
            raise ValueError(f"Target element '{to_tag}' not found in project manifest")

        start_pt = self._get_element_3d_position(elem_from, is_source=True)
        end_pt = self._get_element_3d_position(elem_to, is_source=False)

        # If target element is a vertical stack pipe (e.g. PIPE-STACK-01), align end_pt X, Y
        elem_to_cls = str(getattr(elem_to, "class_", getattr(elem_to, "__class__", "")))
        if "Pipe" in elem_to_cls or "STACK" in to_tag.upper():
            if hasattr(elem_to, "start_point") and hasattr(elem_to, "end_point"):
                sp = getattr(elem_to, "start_point")
                ep = getattr(elem_to, "end_point")
                if abs(sp[0] - ep[0]) < 0.1 and abs(sp[1] - ep[1]) < 0.1:
                    end_pt = (sp[0], sp[1], min(sp[2], ep[2]))
            elif hasattr(elem_to, "placement") and getattr(elem_to.placement, "from_grid", None):
                pl = elem_to.placement
                fo = getattr(pl, "from_offset", (0.0, 0.0, 0.0))
                to = getattr(pl, "to_offset", (0.0, 0.0, 0.0))
                st_name = getattr(pl, "storey", "L1") or "L1"
                st_elev = 0.0
                if hasattr(self.manifest, "spatial_structure") and self.manifest.spatial_structure:
                    for st in self.manifest.spatial_structure.storeys:
                        if st.id == st_name:
                            st_elev = st.elevation
                            break
                axes_x = getattr(self.manifest.grids, "axes_x", {}) if hasattr(self.manifest, "grids") else {}
                axes_y = getattr(self.manifest.grids, "axes_y", {}) if hasattr(self.manifest, "grids") else {}
                gx, gy = pl.from_grid
                x_stack = axes_x.get(gx, 0.0) + fo[0]
                y_stack = axes_y.get(gy, 0.0) + fo[1]
                min_z = st_elev + min(fo[2], to[2])
                end_pt = (x_stack, y_stack, min_z)

        is_gravity_drain = system_type in ("SOIL", "WASTE", "DRAINAGE", "SANITARY") or slope > 0.0
        if is_gravity_drain and slope == 0.0:
            slope = 0.02  # Default 1:50 (2%) for gravity sanitary drains

        if is_gravity_drain and start_pt[2] >= end_pt[2]:
            route_start_z = start_pt[2] - 0.20
        else:
            route_start_z = start_pt[2]

        p_start_routed = (start_pt[0], start_pt[1], route_start_z)

        # Gather structural obstacles (Columns & Beams)
        column_boxes: List[Tuple[float, float, float, float, float, float]] = []
        beam_boxes: List[Tuple[float, float, float, float, float, float]] = []

        if self.resolver and hasattr(self.resolver, "columns"):
            for col in self.resolver.columns:
                cx, cy, cz = col.position
                w, d, h = col.dimensions
                margin = nominal_diameter / 2.0 + 0.02
                column_boxes.append((cx - w/2 - margin, cx + w/2 + margin, cy - d/2 - margin, cy + d/2 + margin, cz, cz + h))

        if self.resolver and hasattr(self.resolver, "beams"):
            for bm in self.resolver.beams:
                sx, sy, sz = bm.start_point
                ex, ey, ez = bm.end_point
                w, d = bm.width, bm.depth
                margin = nominal_diameter / 2.0 + 0.02
                xmin, xmax = min(sx, ex) - w/2 - margin, max(sx, ex) + w/2 + margin
                ymin, ymax = min(sy, ey) - w/2 - margin, max(sy, ey) + w/2 + margin
                zmin, zmax = min(sz, ez) - d - margin, max(sz, ez) + margin
                beam_boxes.append((xmin, xmax, ymin, ymax, zmin, zmax))

        # Gather wall baselines for wall-hugging preference
        wall_segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        if self.resolver and hasattr(self.resolver, "walls"):
            for w in self.resolver.walls:
                p1 = (w.start_point[0], w.start_point[1])
                p2 = (w.end_point[0], w.end_point[1])
                wall_segments.append((p1, p2))

        # Run 3D Constrained A*
        grid_step = 0.10
        raw_grid_path = self._astar_search(
            start=p_start_routed,
            end=end_pt,
            column_boxes=column_boxes,
            beam_boxes=beam_boxes,
            wall_segments=wall_segments,
            grid_step=grid_step,
            wall_hugging=wall_hugging,
        )

        if not raw_grid_path:
            from debim.resolver import _generate_orthogonal_waypoints
            raw_grid_path = _generate_orthogonal_waypoints(p_start_routed, end_pt)

        full_path: List[Tuple[float, float, float]] = []
        if abs(start_pt[2] - p_start_routed[2]) > 1e-3:
            full_path.append(start_pt)

        simplified = self._simplify_waypoints(raw_grid_path)
        full_path.extend(simplified)

        if is_gravity_drain and slope > 0.0:
            full_path = self._apply_monotonic_slope(full_path, slope)

        return full_path

    def _is_obstacle(
        self,
        pt: Tuple[float, float, float],
        column_boxes: List[Tuple[float, float, float, float, float, float]],
        beam_boxes: List[Tuple[float, float, float, float, float, float]],
    ) -> bool:
        x, y, z = pt
        for xmin, xmax, ymin, ymax, zmin, zmax in column_boxes:
            if xmin <= x <= xmax and ymin <= y <= ymax and zmin <= z <= zmax:
                return True
        for xmin, xmax, ymin, ymax, zmin, zmax in beam_boxes:
            if xmin <= x <= xmax and ymin <= y <= ymax and zmin <= z <= zmax:
                return True
        return False

    def _min_dist_to_walls(
        self,
        pt: Tuple[float, float],
        wall_segments: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    ) -> float:
        if not wall_segments:
            return 999.0
        px, py = pt
        min_d = 999.0
        for (x1, y1), (x2, y2) in wall_segments:
            dx = x2 - x1
            dy = y2 - y1
            if dx == 0 and dy == 0:
                d = math.hypot(px - x1, py - y1)
            else:
                t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
                proj_x = x1 + t * dx
                proj_y = y1 + t * dy
                d = math.hypot(px - proj_x, py - proj_y)
            if d < min_d:
                min_d = d
        return min_d

    def _astar_search(
        self,
        start: Tuple[float, float, float],
        end: Tuple[float, float, float],
        column_boxes: List[Tuple[float, float, float, float, float, float]],
        beam_boxes: List[Tuple[float, float, float, float, float, float]],
        wall_segments: List[Tuple[Tuple[float, float], Tuple[float, float]]],
        grid_step: float = 0.10,
        wall_hugging: bool = True,
    ) -> List[Tuple[float, float, float]]:
        """3D Constrained A* search on corridor grid."""
        def to_grid(p: Tuple[float, float, float]) -> Tuple[int, int, int]:
            return (round(p[0] / grid_step), round(p[1] / grid_step), round(p[2] / grid_step))

        def to_world(g: Tuple[int, int, int]) -> Tuple[float, float, float]:
            return (g[0] * grid_step, g[1] * grid_step, g[2] * grid_step)

        g_start = to_grid(start)
        g_end = to_grid(end)

        dirs = [
            (1, 0, 0), (-1, 0, 0),
            (0, 1, 0), (0, -1, 0),
            (0, 0, 1), (0, 0, -1),
        ]

        open_set: List[Tuple[float, float, Tuple[int, int, int], Tuple[int, int, int]]] = []
        heapq.heappush(open_set, (0.0, 0.0, g_start, (0, 0, 0)))

        came_from: Dict[Tuple[int, int, int], Tuple[int, int, int]] = {}
        g_scores: Dict[Tuple[int, int, int], float] = {g_start: 0.0}

        def heuristic(g: Tuple[int, int, int]) -> float:
            return abs(g[0] - g_end[0]) + abs(g[1] - g_end[1]) + abs(g[2] - g_end[2])

        max_iterations = 20000
        iterations = 0

        while open_set and iterations < max_iterations:
            iterations += 1
            _, current_g_score, current, last_dir = heapq.heappop(open_set)

            if current == g_end:
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return [to_world(g) for g in path]

            for d in dirs:
                neighbor = (current[0] + d[0], current[1] + d[1], current[2] + d[2])
                world_pt = to_world(neighbor)

                if self._is_obstacle(world_pt, column_boxes, beam_boxes):
                    continue

                step_cost = 1.0
                if wall_hugging and wall_segments and (d[0] != 0 or d[1] != 0):
                    dist_wall = self._min_dist_to_walls((world_pt[0], world_pt[1]), wall_segments)
                    if 0.05 <= dist_wall <= 0.50:
                        step_cost *= 0.6
                    elif dist_wall > 1.0:
                        step_cost *= 1.4

                if last_dir != (0, 0, 0) and last_dir != d:
                    step_cost += 2.0

                tentative_g = current_g_score + step_cost

                if neighbor not in g_scores or tentative_g < g_scores[neighbor]:
                    g_scores[neighbor] = tentative_g
                    f_score = tentative_g + heuristic(neighbor)
                    came_from[neighbor] = current
                    heapq.heappush(open_set, (f_score, tentative_g, neighbor, d))

        return [start, end]

    def _simplify_waypoints(
        self, waypoints: List[Tuple[float, float, float]]
    ) -> List[Tuple[float, float, float]]:
        """Compress collinear grid steps into clean segment endpoints."""
        if len(waypoints) <= 2:
            return waypoints

        simplified = [waypoints[0]]
        for i in range(1, len(waypoints) - 1):
            prev = simplified[-1]
            curr = waypoints[i]
            nxt = waypoints[i + 1]

            dx1, dy1, dz1 = curr[0] - prev[0], curr[1] - prev[1], curr[2] - prev[2]
            dx2, dy2, dz2 = nxt[0] - curr[0], nxt[1] - curr[1], nxt[2] - curr[2]

            cx = dy1 * dz2 - dz1 * dy2
            cy = dz1 * dx2 - dx1 * dz2
            cz = dx1 * dy2 - dy1 * dx2

            if abs(cx) > 1e-4 or abs(cy) > 1e-4 or abs(cz) > 1e-4:
                simplified.append(curr)

        simplified.append(waypoints[-1])
        return simplified

    def _apply_monotonic_slope(
        self, waypoints: List[Tuple[float, float, float]], slope: float
    ) -> List[Tuple[float, float, float]]:
        """Adjust Z coordinates along waypoints to enforce monotonic drainage slope."""
        if len(waypoints) <= 1:
            return waypoints

        sloped_path = [waypoints[0]]
        start_idx = 0
        if len(waypoints) >= 2 and abs(waypoints[0][0] - waypoints[1][0]) < 1e-3 and abs(waypoints[0][1] - waypoints[1][1]) < 1e-3:
            sloped_path.append(waypoints[1])
            start_idx = 1

        start_z = waypoints[start_idx][2]
        cum_dist = 0.0

        for i in range(start_idx + 1, len(waypoints)):
            px, py, _ = waypoints[i - 1]
            cx, cy, cz = waypoints[i]
            d2d = math.hypot(cx - px, cy - py)
            cum_dist += d2d
            target_z = start_z - cum_dist * slope
            sloped_path.append((cx, cy, target_z))

        return sloped_path


def route_connection(
    manifest: Any,
    from_tag: str,
    to_tag: str,
    system_type: str = "SOIL",
    slope: float = 0.0,
    wall_hugging: bool = True,
) -> List[Tuple[float, float, float]]:
    """Helper function to auto-route a pipe connection given a project manifest."""
    router = MEPRouter(manifest)
    return router.route(
        from_tag=from_tag,
        to_tag=to_tag,
        system_type=system_type,
        slope=slope,
        wall_hugging=wall_hugging,
    )
