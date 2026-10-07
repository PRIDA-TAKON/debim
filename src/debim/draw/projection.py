"""
Core 2D Cut-Plane & Geometry Projection Engine for debim.
Slices 3D BIM models at horizontal cut-planes and generates 2D projection primitives
(Cut Polygons, Projection Polygons, Centerlines, and Grid Lines).
"""

import math
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field
from shapely.affinity import rotate
from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.geometry.base import BaseGeometry

from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedCovering,
    ResolvedCurtainWall,
    ResolvedCustomElement,
    ResolvedDoor,
    ResolvedManifest,
    ResolvedPipeSegment,
    ResolvedPlate,
    ResolvedRailing,
    ResolvedRamp,
    ResolvedSanitaryTerminal,
    ResolvedSlab,
    ResolvedStair,
    ResolvedStairFlight,
    ResolvedStairStep,
    ResolvedTerminal,
    ResolvedWall,
    ResolvedWasteTerminal,
    ResolvedWindow,
    SpatialResolver,
)
from debim.schema import (
    BoxProfile,
    CircularProfile,
    EllipseProfile,
    ProjectManifest,
)


def coords_from_geometry(geom: BaseGeometry) -> List[List[Tuple[float, float]]]:
    """Extract coordinate rings/loops from a Shapely geometry object."""
    coords_list: List[List[Tuple[float, float]]] = []
    if geom.is_empty:
        return coords_list

    if isinstance(geom, Polygon):
        ext = [(round(float(x), 4), round(float(y), 4)) for x, y in geom.exterior.coords]
        coords_list.append(ext)
        for interior in geom.interiors:
            hole = [(round(float(x), 4), round(float(y), 4)) for x, y in interior.coords]
            coords_list.append(hole)
    elif isinstance(geom, MultiPolygon):
        for poly in geom.geoms:
            coords_list.extend(coords_from_geometry(poly))
    elif isinstance(geom, (LineString, MultiLineString)):
        if isinstance(geom, LineString):
            pts = [(round(float(x), 4), round(float(y), 4)) for x, y in geom.coords]
            coords_list.append(pts)
        else:
            for line in geom.geoms:
                pts = [(round(float(x), 4), round(float(y), 4)) for x, y in line.coords]
                coords_list.append(pts)
    return coords_list


class CutElement(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element_class: str
    category: Literal["heavy_cut", "medium_cut", "low_projection"]
    geometry: Union[Polygon, MultiPolygon]
    polygon_coords: List[List[Tuple[float, float]]] = Field(default_factory=list)
    centerline: Optional[Union[LineString, Point]] = None
    layer: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.polygon_coords and self.geometry is not None:
            self.polygon_coords = coords_from_geometry(self.geometry)


class ProjectionElement(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element_class: str
    category: Literal["low_projection", "medium_cut", "heavy_cut"]
    geometry: Union[Polygon, MultiPolygon, LineString, MultiLineString]
    polygon_coords: List[List[Tuple[float, float]]] = Field(default_factory=list)
    layer: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.polygon_coords and self.geometry is not None:
            self.polygon_coords = coords_from_geometry(self.geometry)


class GridLine2D(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    axis: Literal["X", "Y"]
    position: float
    start: Tuple[float, float]
    end: Tuple[float, float]
    line: LineString


class CutPlaneResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    storey_id: str
    storey_name: str
    storey_elevation: float
    cut_offset_z: float
    cut_elevation: float
    cut_elements: List[CutElement] = Field(default_factory=list)
    projection_elements: List[ProjectionElement] = Field(default_factory=list)
    grid_lines: List[GridLine2D] = Field(default_factory=list)
    bounds: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # min_x, min_y, max_x, max_y

    @property
    def heavy_cut_elements(self) -> List[CutElement]:
        return [e for e in self.cut_elements if e.category == "heavy_cut"]

    @property
    def medium_cut_elements(self) -> List[CutElement]:
        return [e for e in self.cut_elements if e.category == "medium_cut"]

    @property
    def low_projection_elements(self) -> List[ProjectionElement]:
        return [e for e in self.projection_elements if e.category == "low_projection"]


def _is_load_bearing_wall(wall: ResolvedWall) -> bool:
    """Determine if a wall is structural / load-bearing (Heavy Cut)."""
    tag_upper = wall.tag.upper()
    mat_upper = (wall.element.material or "").upper()
    layer_lower = (wall.layer or "").lower()

    # Structural indicators in tag
    if any(k in tag_upper for k in ["CORE", "LOAD", "BEARING", "SHEAR", "COL"]):
        return True

    # Glass / partition indicators
    if "GLASS" in tag_upper or "GLASS" in mat_upper or "PARTITION" in tag_upper:
        return False

    # Thickness and material threshold: walls with thickness >= 0.12m and masonry/concrete
    if wall.thickness >= 0.12:
        return True

    return False


def _create_rotated_box(
    cx: float, cy: float, width: float, depth: float, angle_degrees: float
) -> Polygon:
    """Create a 2D box polygon centered at (cx, cy) with rotation."""
    hw = width / 2.0
    hd = depth / 2.0
    box_poly = Polygon([
        (cx - hw, cy - hd),
        (cx + hw, cy - hd),
        (cx + hw, cy + hd),
        (cx - hw, cy + hd),
    ])
    if abs(angle_degrees) > 1e-4:
        box_poly = rotate(box_poly, angle_degrees, origin=(cx, cy))
    return box_poly


def slice_storey(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
    storey_id: str,
    cut_offset_z: float = 1.20,
) -> CutPlaneResult:
    """
    Slice the 3D building model at a horizontal cut-plane (Z = Storey_Elevation + cut_offset_z)
    and return structured 2D geometry primitives (Cut Polygons, Projection Polygons, Grid Lines).
    """
    if isinstance(manifest_or_resolved, ProjectManifest):
        resolved = SpatialResolver(manifest_or_resolved).resolve()
        manifest = manifest_or_resolved
    else:
        resolved = manifest_or_resolved
        manifest = resolved.manifest

    storey = None
    for s in manifest.spatial_structure.storeys:
        if s.id == storey_id:
            storey = s
            break
    if storey is None:
        raise ValueError(f"Storey ID '{storey_id}' not found in spatial structure.")

    storey_elev = storey.elevation
    cut_elev = storey_elev + cut_offset_z

    cut_elements: List[CutElement] = []
    projection_elements: List[ProjectionElement] = []

    # Track all 2D points to calculate bounding box
    all_2d_points: List[Tuple[float, float]] = []

    # 1. Process Walls
    for wall in resolved.walls:
        w_base_z = wall.start_point[2]
        w_top_z = w_base_z + wall.height

        # Check if storey matches or cut-plane intersects wall vertical span
        if not (w_base_z <= cut_elev <= w_top_z):
            continue

        x1, y1 = wall.start_point[0], wall.start_point[1]
        x2, y2 = wall.end_point[0], wall.end_point[1]
        all_2d_points.extend([(x1, y1), (x2, y2)])

        length = wall.length
        thickness = wall.thickness

        if length <= 0:
            continue

        ux = (x2 - x1) / length
        uy = (y2 - y1) / length
        nx, ny = -uy, ux  # Normal vector

        ht = thickness / 2.0
        p0 = (x1 + ht * nx, y1 + ht * ny)
        p1 = (x2 + ht * nx, y2 + ht * ny)
        p2 = (x2 - ht * nx, y2 - ht * ny)
        p3 = (x1 - ht * nx, y1 - ht * ny)

        wall_poly = Polygon([p0, p1, p2, p3])
        all_2d_points.extend([p0, p1, p2, p3])

        # Subtract door/window openings that cut through Z_cut
        for child in wall.children:
            c_base_z = w_base_z + child.sill_height
            c_top_z = c_base_z + child.height

            # Is the opening cut at cut_elev?
            if c_base_z <= cut_elev <= c_top_z:
                d1 = child.offset_distance
                w_child = child.width
                d2 = d1 + w_child

                # Opening subtract polygon
                o0 = (x1 + d1 * ux + (ht + 0.02) * nx, y1 + d1 * uy + (ht + 0.02) * ny)
                o1 = (x1 + d2 * ux + (ht + 0.02) * nx, y1 + d2 * uy + (ht + 0.02) * ny)
                o2 = (x1 + d2 * ux - (ht + 0.02) * nx, y1 + d2 * uy - (ht + 0.02) * ny)
                o3 = (x1 + d1 * ux - (ht + 0.02) * nx, y1 + d1 * uy - (ht + 0.02) * ny)
                opening_poly = Polygon([o0, o1, o2, o3])

                wall_poly = wall_poly.difference(opening_poly)

                # Add cut primitive for Door or Window
                c_center_x = x1 + (d1 + w_child / 2.0) * ux
                c_center_y = y1 + (d1 + w_child / 2.0) * uy
                wall_angle_deg = math.degrees(math.atan2(uy, ux))

                f_thick = getattr(child, "frame_thickness", 0.05) or 0.05
                frame_poly = _create_rotated_box(c_center_x, c_center_y, w_child, f_thick, wall_angle_deg)

                elem_cls = "IfcDoor" if isinstance(child, ResolvedDoor) else "IfcWindow"
                cut_elements.append(CutElement(
                    tag=child.tag,
                    element_class=elem_cls,
                    category="medium_cut",
                    geometry=frame_poly,
                    layer=child.layer,
                    properties={
                        "host_wall": wall.tag,
                        "width": child.width,
                        "height": child.height,
                        "sill_height": child.sill_height,
                    },
                ))

        category: Literal["heavy_cut", "medium_cut"] = (
            "heavy_cut" if _is_load_bearing_wall(wall) else "medium_cut"
        )

        cut_elements.append(CutElement(
            tag=wall.tag,
            element_class="IfcWall",
            category=category,
            geometry=wall_poly,
            centerline=LineString([(x1, y1), (x2, y2)]),
            layer=wall.layer,
            properties={
                "material": wall.element.material,
                "thickness": wall.thickness,
                "height": wall.height,
            },
        ))

    # 2. Process Columns
    for col in resolved.columns:
        z1 = min(col.start_point[2], col.end_point[2])
        z2 = max(col.start_point[2], col.end_point[2])

        if not (z1 <= cut_elev <= z2):
            continue

        # Position at cut_elev
        if abs(z2 - z1) > 1e-4:
            t_val = (cut_elev - col.start_point[2]) / (col.end_point[2] - col.start_point[2])
            cx = col.start_point[0] + t_val * (col.end_point[0] - col.start_point[0])
            cy = col.start_point[1] + t_val * (col.end_point[1] - col.start_point[1])
        else:
            cx, cy = col.start_point[0], col.start_point[1]

        all_2d_points.append((cx, cy))

        prof = col.element.profile
        if isinstance(prof, BoxProfile) or getattr(prof, "shape", "BOX") == "BOX":
            w = prof.width
            d = prof.depth
            poly = Polygon([
                (cx - w / 2.0, cy - d / 2.0),
                (cx + w / 2.0, cy - d / 2.0),
                (cx + w / 2.0, cy + d / 2.0),
                (cx - w / 2.0, cy + d / 2.0),
            ])
        elif isinstance(prof, CircularProfile) or getattr(prof, "shape", "") == "CIRCULAR":
            r = prof.radius or 0.15
            poly = Point(cx, cy).buffer(r)
        elif isinstance(prof, EllipseProfile) or getattr(prof, "shape", "") == "ELLIPSE":
            a = prof.semi_major_axis or 0.15
            b = prof.semi_minor_axis or 0.10
            # Approximate ellipse
            poly = Point(cx, cy).buffer(a)
        else:
            w = getattr(prof, "width", 0.30)
            d = getattr(prof, "depth", 0.30)
            poly = Polygon([
                (cx - w / 2.0, cy - d / 2.0),
                (cx + w / 2.0, cy - d / 2.0),
                (cx + w / 2.0, cy + d / 2.0),
                (cx - w / 2.0, cy + d / 2.0),
            ])

        cut_elements.append(CutElement(
            tag=col.tag,
            element_class="IfcColumn",
            category="heavy_cut",
            geometry=poly,
            centerline=Point(cx, cy),
            layer=col.layer,
            properties={
                "material": col.element.material,
                "height": col.height,
            },
        ))

    # 3. Process Floor Slabs (Low Projection)
    for slab in resolved.slabs:
        s_z = slab.center[2]
        # Slab below cut_elev
        if s_z <= cut_elev:
            pts_2d = [(p[0], p[1]) for p in slab.polygon]
            all_2d_points.extend(pts_2d)

            if len(pts_2d) >= 3:
                s_poly = Polygon(pts_2d)

                # Subtract voids if present
                for void_pts_3d in slab.voids:
                    v_pts_2d = [(vp[0], vp[1]) for vp in void_pts_3d]
                    if len(v_pts_2d) >= 3:
                        v_poly = Polygon(v_pts_2d)
                        s_poly = s_poly.difference(v_poly)

                projection_elements.append(ProjectionElement(
                    tag=slab.tag,
                    element_class="IfcSlab",
                    category="low_projection",
                    geometry=s_poly,
                    layer=slab.layer,
                    properties={
                        "material": slab.element.material,
                        "thickness": slab.thickness,
                        "area": slab.area,
                    },
                ))

    # 4. Process Stairs (Low Projection / Cut)
    for stair in resolved.stairs:
        for step in stair.steps:
            if step.position[2] <= cut_elev:
                if step.polygon and len(step.polygon) >= 3:
                    st_pts_2d = [(p[0], p[1]) for p in step.polygon]
                    st_poly = Polygon(st_pts_2d)
                else:
                    scx, scy, _ = step.position
                    st_poly = _create_rotated_box(scx, scy, step.width, step.tread, math.degrees(step.rotation))

                projection_elements.append(ProjectionElement(
                    tag=f"{stair.tag}-Step-{step.step_index}",
                    element_class="IfcStairStep",
                    category="low_projection",
                    geometry=st_poly,
                    layer=stair.layer,
                    properties={
                        "flight": step.flight_tag,
                        "riser": step.riser,
                        "tread": step.tread,
                    },
                ))

    # 5. Process Sanitary & MEP Terminals (Low Projection)
    for term in resolved.sanitary_terminals:
        if term.position[2] <= cut_elev:
            tx, ty, _ = term.position
            all_2d_points.append((tx, ty))
            w, d, _ = term.dimensions
            term_poly = _create_rotated_box(tx, ty, w, d, term.rotation)

            projection_elements.append(ProjectionElement(
                tag=term.tag,
                element_class="IfcSanitaryTerminal",
                category="low_projection",
                geometry=term_poly,
                layer=term.layer,
                properties={
                    "terminal_type": term.terminal_type,
                    "dimensions": term.dimensions,
                },
            ))

    for term in resolved.waste_terminals:
        if term.position[2] <= cut_elev:
            tx, ty, _ = term.position
            all_2d_points.append((tx, ty))
            w, d, _ = term.dimensions
            term_poly = _create_rotated_box(tx, ty, w, d, term.rotation)

            projection_elements.append(ProjectionElement(
                tag=term.tag,
                element_class="IfcWasteTerminal",
                category="low_projection",
                geometry=term_poly,
                layer=term.layer,
                properties={
                    "terminal_type": term.terminal_type,
                    "dimensions": term.dimensions,
                },
            ))

    # 6. Calculate Bounding Box
    if all_2d_points:
        xs = [p[0] for p in all_2d_points]
        ys = [p[1] for p in all_2d_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
    else:
        grid_x_vals = list(manifest.grids.axes_x.values())
        grid_y_vals = list(manifest.grids.axes_y.values())
        min_x = min(grid_x_vals) if grid_x_vals else 0.0
        max_x = max(grid_x_vals) if grid_x_vals else 10.0
        min_y = min(grid_y_vals) if grid_y_vals else 0.0
        max_y = max(grid_y_vals) if grid_y_vals else 10.0

    margin = 2.0
    bbox_min_x = min_x - margin
    bbox_max_x = max_x + margin
    bbox_min_y = min_y - margin
    bbox_max_y = max_y + margin

    # 7. Generate Grid Lines (GridLine2D)
    grid_lines_2d: List[GridLine2D] = []

    # X-Axes (Vertical grid lines along X)
    for g_id, x_pos in manifest.grids.axes_x.items():
        line = LineString([(x_pos, bbox_min_y), (x_pos, bbox_max_y)])
        grid_lines_2d.append(GridLine2D(
            id=g_id,
            axis="X",
            position=x_pos,
            start=(x_pos, bbox_min_y),
            end=(x_pos, bbox_max_y),
            line=line,
        ))

    # Y-Axes (Horizontal grid lines along Y)
    for g_id, y_pos in manifest.grids.axes_y.items():
        line = LineString([(bbox_min_x, y_pos), (bbox_max_x, y_pos)])
        grid_lines_2d.append(GridLine2D(
            id=g_id,
            axis="Y",
            position=y_pos,
            start=(bbox_min_x, y_pos),
            end=(bbox_max_x, y_pos),
            line=line,
        ))

    return CutPlaneResult(
        storey_id=storey.id,
        storey_name=storey.name,
        storey_elevation=storey.elevation,
        cut_offset_z=cut_offset_z,
        cut_elevation=cut_elev,
        cut_elements=cut_elements,
        projection_elements=projection_elements,
        grid_lines=grid_lines_2d,
        bounds=(round(bbox_min_x, 4), round(bbox_min_y, 4), round(bbox_max_x, 4), round(bbox_max_y, 4)),
    )


def project_2d_floor_plan(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
    storey_id: str,
    cut_offset_z: float = 1.20,
) -> CutPlaneResult:
    """Alias for slice_storey."""
    return slice_storey(manifest_or_resolved, storey_id, cut_offset_z)
