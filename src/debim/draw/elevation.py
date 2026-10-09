"""
Architectural Elevations Projection Engine (รูปด้าน 4 ทิศ) for debim.
Projects 3D elements from ResolvedManifest onto 2D vertical projection planes
across 4 cardinal orientations (Front, Rear, Right, Left).
"""

import math
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field
from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.geometry.base import BaseGeometry

from debim.draw.projection import coords_from_geometry
from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedCovering,
    ResolvedCurtainWall,
    ResolvedCustomElement,
    ResolvedDoor,
    ResolvedFooting,
    ResolvedManifest,
    ResolvedPlate,
    ResolvedRailing,
    ResolvedRamp,
    ResolvedRoof,
    ResolvedSlab,
    ResolvedStair,
    ResolvedStairFlight,
    ResolvedWall,
    ResolvedWindow,
    SpatialResolver,
)
from debim.schema import ProjectManifest

ElevationDirection = Literal["FRONT", "REAR", "RIGHT", "LEFT"]


class ElevationElement(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element_class: str
    category: Literal["outline", "detail", "roof", "opening", "ground", "structure"]
    geometry: Union[Polygon, MultiPolygon, LineString, MultiLineString]
    polygon_coords: List[List[Tuple[float, float]]] = Field(default_factory=list)
    depth: float = 0.0  # Distance along view axis for depth sorting
    layer: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.polygon_coords and self.geometry is not None:
            self.polygon_coords = coords_from_geometry(self.geometry)


class LevelMarker2D(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    label: str  # e.g., "ระดับดินเดิม ±0.00", "ระดับพื้นชั้น 1 +0.80"
    elevation: float  # Z elevation in meters
    display_text: str  # e.g., "+0.80" or "±0.00"
    start_u: float
    end_u: float


class ElevationGridLine2D(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    position_u: float
    start_v: float
    end_v: float
    line: LineString


class ElevationResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    direction: ElevationDirection
    title_th: str
    title_en: str
    elements: List[ElevationElement] = Field(default_factory=list)
    level_markers: List[LevelMarker2D] = Field(default_factory=list)
    grid_lines: List[ElevationGridLine2D] = Field(default_factory=list)
    bounds: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)  # min_u, min_v, max_u, max_v
    max_height: float = 0.0


def normalize_direction(direction_input: str) -> ElevationDirection:
    """Normalize elevation direction string to standard enum."""
    d = direction_input.strip().upper()
    if d in ("FRONT", "SOUTH", "1", "SOUTH_ELEVATION", "FRONT_ELEVATION"):
        return "FRONT"
    if d in ("REAR", "NORTH", "2", "NORTH_ELEVATION", "REAR_ELEVATION", "BACK"):
        return "REAR"
    if d in ("RIGHT", "EAST", "3", "EAST_ELEVATION", "RIGHT_ELEVATION"):
        return "RIGHT"
    if d in ("LEFT", "WEST", "4", "WEST_ELEVATION", "LEFT_ELEVATION"):
        return "LEFT"
    return "FRONT"


def _get_direction_titles(direction: ElevationDirection) -> Tuple[str, str]:
    if direction == "FRONT":
        return ("รูปด้าน 1 (ทิศใต้)", "Front Elevation (South)")
    elif direction == "REAR":
        return ("รูปด้าน 2 (ทิศเหนือ)", "Rear Elevation (North)")
    elif direction == "RIGHT":
        return ("รูปด้าน 3 (ทิศตะวันออก)", "Right Elevation (East)")
    else:
        return ("รูปด้าน 4 (ทิศตะวันตก)", "Left Elevation (West)")


def map_3d_point_to_uv(
    x: float, y: float, z: float, direction: ElevationDirection, bounds_3d: Tuple[float, float, float, float, float, float]
) -> Tuple[float, float, float]:
    """
    Map a 3D coordinate (x, y, z) to 2D elevation coordinate (u, v) and depth value.
    u: Horizontal distance across elevation face.
    v: Height (z).
    depth: Distance along line of sight (smaller depth = closer to viewer).
    """
    min_x, min_y, min_z, max_x, max_y, max_z = bounds_3d

    if direction == "FRONT":
        # Looking towards +Y (from South to North)
        u = x
        v = z
        depth = y - min_y
    elif direction == "REAR":
        # Looking towards -Y (from North to South), reversed X
        u = max_x - (x - min_x)
        v = z
        depth = max_y - y
    elif direction == "RIGHT":
        # Looking towards -X (from East to West)
        u = y
        v = z
        depth = max_x - x
    else:  # LEFT
        # Looking towards +X (from West to East), reversed Y
        u = max_y - (y - min_y)
        v = z
        depth = x - min_x

    return (round(u, 4), round(v, 4), round(depth, 4))


def project_2d_elevation(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
    direction: Union[ElevationDirection, str] = "FRONT",
) -> ElevationResult:
    """
    Project 3D elements from ResolvedManifest onto 2D vertical projection planes
    for the specified cardinal direction (FRONT, REAR, RIGHT, LEFT).
    """
    if isinstance(manifest_or_resolved, ProjectManifest):
        resolved = SpatialResolver(manifest_or_resolved).resolve()
        manifest = manifest_or_resolved
    else:
        resolved = manifest_or_resolved
        manifest = resolved.manifest

    norm_dir = normalize_direction(str(direction))
    title_th, title_en = _get_direction_titles(norm_dir)

    # 1. Calculate overall 3D model bounding box
    all_xs: List[float] = []
    all_ys: List[float] = []
    all_zs: List[float] = [0.0]

    for wall in resolved.walls:
        all_xs.extend([wall.start_point[0], wall.end_point[0]])
        all_ys.extend([wall.start_point[1], wall.end_point[1]])
        all_zs.extend([wall.start_point[2], wall.start_point[2] + wall.height])

    for col in resolved.columns:
        all_xs.extend([col.start_point[0], col.end_point[0]])
        all_ys.extend([col.start_point[1], col.end_point[1]])
        all_zs.extend([col.start_point[2], col.end_point[2]])

    for slab in resolved.slabs:
        for p in slab.polygon:
            all_xs.append(p[0])
            all_ys.append(p[1])
            all_zs.append(p[2])

    for roof in resolved.roofs:
        for p in roof.footprint_polygon:
            all_xs.append(p[0])
            all_ys.append(p[1])
            all_zs.append(p[2])
        all_zs.append(roof.ridge_elevation)

    grid_x_vals = list(manifest.grids.axes_x.values())
    grid_y_vals = list(manifest.grids.axes_y.values())
    if grid_x_vals:
        all_xs.extend(grid_x_vals)
    if grid_y_vals:
        all_ys.extend(grid_y_vals)

    min_x = min(all_xs) if all_xs else 0.0
    max_x = max(all_xs) if all_xs else 10.0
    min_y = min(all_ys) if all_ys else 0.0
    max_y = max(all_ys) if all_ys else 10.0
    min_z = min(all_zs) if all_zs else 0.0
    max_z = max(all_zs) if all_zs else 6.0

    bounds_3d = (min_x, min_y, min_z, max_x, max_y, max_z)

    elements: List[ElevationElement] = []

    # 2. Project Exterior Walls
    for wall in resolved.walls:
        x1, y1, z1 = wall.start_point
        x2, y2, _ = wall.end_point
        h = wall.height
        t = wall.thickness

        u1, v1, d1 = map_3d_point_to_uv(x1, y1, z1, norm_dir, bounds_3d)
        u2, v2, d2 = map_3d_point_to_uv(x2, y2, z1, norm_dir, bounds_3d)

        min_u = min(u1, u2)
        max_u = max(u1, u2)
        avg_depth = (d1 + d2) / 2.0

        # Create wall vertical face polygon
        if abs(max_u - min_u) > 1e-4:
            wall_poly = Polygon([
                (min_u, v1),
                (max_u, v1),
                (max_u, v1 + h),
                (min_u, v1 + h),
            ])

            elements.append(ElevationElement(
                tag=wall.tag,
                element_class="IfcWall",
                category="outline",
                geometry=wall_poly,
                depth=avg_depth,
                layer=wall.layer,
                properties={"material": wall.element.material, "thickness": t, "height": h},
            ))

        # Project Wall Openings (Doors & Windows)
        for child in wall.children:
            d_offset = child.offset_distance
            c_w = child.width
            c_h = child.height
            c_sill = child.sill_height

            # Ratio along wall centerline
            wall_len = wall.length if wall.length > 0 else 1.0
            t1 = d_offset / wall_len
            t2 = (d_offset + c_w) / wall_len

            cx1 = x1 + t1 * (x2 - x1)
            cy1 = y1 + t1 * (y2 - y1)
            cx2 = x1 + t2 * (x2 - x1)
            cy2 = y1 + t2 * (y2 - y1)

            cu1, cv1, cd1 = map_3d_point_to_uv(cx1, cy1, z1 + c_sill, norm_dir, bounds_3d)
            cu2, cv2, cd2 = map_3d_point_to_uv(cx2, cy2, z1 + c_sill, norm_dir, bounds_3d)

            c_min_u = min(cu1, cu2)
            c_max_u = max(cu1, cu2)

            if abs(c_max_u - c_min_u) > 1e-4:
                opening_poly = Polygon([
                    (c_min_u, cv1),
                    (c_max_u, cv1),
                    (c_max_u, cv1 + c_h),
                    (c_min_u, cv1 + c_h),
                ])

                elem_cls = "IfcDoor" if isinstance(child, ResolvedDoor) else "IfcWindow"
                elements.append(ElevationElement(
                    tag=child.tag,
                    element_class=elem_cls,
                    category="opening",
                    geometry=opening_poly,
                    depth=(cd1 + cd2) / 2.0 - 0.01,
                    layer=child.layer,
                    properties={"width": c_w, "height": c_h, "sill_height": c_sill},
                ))

    # 3. Project Columns
    for col in resolved.columns:
        x1, y1, z1 = col.start_point
        x2, y2, z2 = col.end_point

        u1, v1, d1 = map_3d_point_to_uv(x1, y1, min(z1, z2), norm_dir, bounds_3d)
        u2, v2, d2 = map_3d_point_to_uv(x2, y2, max(z1, z2), norm_dir, bounds_3d)

        prof = col.element.profile
        w = getattr(prof, "width", 0.30) or 0.30

        col_poly = Polygon([
            (u1 - w / 2.0, v1),
            (u1 + w / 2.0, v1),
            (u1 + w / 2.0, v2),
            (u1 - w / 2.0, v2),
        ])

        elements.append(ElevationElement(
            tag=col.tag,
            element_class="IfcColumn",
            category="structure",
            geometry=col_poly,
            depth=d1,
            layer=col.layer,
            properties={"height": col.height},
        ))

    # 4. Project Floor Slabs & Plinth / Base Slabs
    for slab in resolved.slabs:
        s_z = slab.center[2]
        s_thick = slab.thickness

        u_coords: List[float] = []
        d_coords: List[float] = []
        for pt in slab.polygon:
            u, _, d = map_3d_point_to_uv(pt[0], pt[1], pt[2], norm_dir, bounds_3d)
            u_coords.append(u)
            d_coords.append(d)

        if u_coords:
            s_min_u = min(u_coords)
            s_max_u = max(u_coords)
            if abs(s_max_u - s_min_u) > 1e-4:
                slab_poly = Polygon([
                    (s_min_u, s_z - s_thick),
                    (s_max_u, s_z - s_thick),
                    (s_max_u, s_z),
                    (s_min_u, s_z),
                ])

                elements.append(ElevationElement(
                    tag=slab.tag,
                    element_class="IfcSlab",
                    category="structure",
                    geometry=slab_poly,
                    depth=min(d_coords) if d_coords else 0.0,
                    layer=slab.layer,
                    properties={"thickness": s_thick, "elevation": s_z},
                ))

    # 5. Project Roofs (Slopes, Fascia, Ridge)
    for roof in resolved.roofs:
        # Roof Slope Planes
        for plane in roof.planes:
            p_uv: List[Tuple[float, float]] = []
            p_depths: List[float] = []
            for pt in plane.polygon:
                u, v, d = map_3d_point_to_uv(pt[0], pt[1], pt[2], norm_dir, bounds_3d)
                p_uv.append((u, v))
                p_depths.append(d)

            if len(p_uv) >= 3:
                try:
                    roof_poly = Polygon(p_uv)
                    if not roof_poly.is_valid:
                        roof_poly = roof_poly.buffer(0)
                    elements.append(ElevationElement(
                        tag=plane.tag,
                        element_class="IfcRoof",
                        category="roof",
                        geometry=roof_poly,
                        depth=min(p_depths) if p_depths else 0.0,
                        layer=roof.layer,
                        properties={"slope": plane.slope_degrees},
                    ))
                except Exception:
                    pass

        # Fascia Boards / Eaves lines (เชิงชาย)
        for ridge in roof.ridges:
            r_u1, r_v1, r_d1 = map_3d_point_to_uv(ridge.start_point[0], ridge.start_point[1], ridge.start_point[2], norm_dir, bounds_3d)
            r_u2, r_v2, r_d2 = map_3d_point_to_uv(ridge.end_point[0], ridge.end_point[1], ridge.end_point[2], norm_dir, bounds_3d)

            line = LineString([(r_u1, r_v1), (r_u2, r_v2)])
            elements.append(ElevationElement(
                tag=ridge.tag,
                element_class="IfcRoof",
                category="detail",
                geometry=line,
                depth=min(r_d1, r_d2),
                layer=roof.layer,
                properties={"ridge_type": ridge.ridge_type, "length": ridge.length},
            ))

    # 6. Project Stairs, Railings, and Ramps
    for stair in resolved.stairs:
        for flight in stair.flights:
            for step in flight.steps:
                scx, scy, scz = step.position
                su, sv, sd = map_3d_point_to_uv(scx, scy, scz, norm_dir, bounds_3d)
                w = step.width
                t = step.tread
                r = step.riser

                step_poly = Polygon([
                    (su - t / 2.0, sv - r / 2.0),
                    (su + t / 2.0, sv - r / 2.0),
                    (su + t / 2.0, sv + r / 2.0),
                    (su - t / 2.0, sv + r / 2.0),
                ])

                elements.append(ElevationElement(
                    tag=f"{stair.tag}-Step-{step.step_index}",
                    element_class="IfcStair",
                    category="detail",
                    geometry=step_poly,
                    depth=sd,
                    layer=stair.layer,
                ))

    for railing in resolved.railings:
        for r_start, r_end in railing.rails:
            u1, v1, d1 = map_3d_point_to_uv(r_start[0], r_start[1], r_start[2], norm_dir, bounds_3d)
            u2, v2, d2 = map_3d_point_to_uv(r_end[0], r_end[1], r_end[2], norm_dir, bounds_3d)
            line = LineString([(u1, v1), (u2, v2)])
            elements.append(ElevationElement(
                tag=f"{railing.tag}-Rail",
                element_class="IfcRailing",
                category="detail",
                geometry=line,
                depth=min(d1, d2),
                layer=railing.layer,
            ))

    for ramp in resolved.ramps:
        u1, v1, d1 = map_3d_point_to_uv(ramp.start_point[0], ramp.start_point[1], ramp.start_point[2], norm_dir, bounds_3d)
        u2, v2, d2 = map_3d_point_to_uv(ramp.end_point[0], ramp.end_point[1], ramp.end_point[2], norm_dir, bounds_3d)
        line = LineString([(u1, v1), (u2, v2)])
        elements.append(ElevationElement(
            tag=ramp.tag,
            element_class="IfcRamp",
            category="structure",
            geometry=line,
            depth=min(d1, d2),
            layer=ramp.layer,
        ))

    # Sort elements by depth (furthest to nearest)
    elements.sort(key=lambda e: e.depth, reverse=True)

    # 7. Calculate Horizontal U Extents for Grid and Level Lines
    all_u_points: List[float] = []
    for elem in elements:
        for ring in elem.polygon_coords:
            for pt in ring:
                all_u_points.append(pt[0])

    if all_u_points:
        min_u_val = min(all_u_points)
        max_u_val = max(all_u_points)
    else:
        min_u_val = min_x if norm_dir in ("FRONT", "REAR") else min_y
        max_u_val = max_x if norm_dir in ("FRONT", "REAR") else max_y

    margin_u = 2.0
    u_start = min_u_val - margin_u
    u_end = max_u_val + margin_u

    # 8. Generate Level Markers (สัญลักษณ์บอกระดับ)
    level_markers: List[LevelMarker2D] = []

    # Natural Ground Level ±0.00
    level_markers.append(LevelMarker2D(
        id="level-ground",
        label="ระดับดินเดิม ±0.00",
        elevation=0.00,
        display_text="±0.00",
        start_u=u_start,
        end_u=u_end,
    ))

    # Add Ground Line Element (เส้นระดับดินเดิม)
    ground_line = LineString([(u_start - 1.0, 0.0), (u_end + 1.0, 0.0)])
    elements.append(ElevationElement(
        tag="GroundLine",
        element_class="IfcSite",
        category="ground",
        geometry=ground_line,
        depth=100.0,
        layer="site/ground",
    ))

    # Storey Level Markers
    for storey in sorted(manifest.spatial_structure.storeys, key=lambda s: s.elevation):
        s_elev = storey.elevation
        s_text = f"+{s_elev:.2f}" if s_elev > 0 else f"{s_elev:.2f}"
        s_label = f"ระดับ{storey.name} {s_text}"

        level_markers.append(LevelMarker2D(
            id=f"level-{storey.id}",
            label=s_label,
            elevation=s_elev,
            display_text=s_text,
            start_u=u_start,
            end_u=u_end,
        ))

    # Roof Level Markers (Eaves & Ridge)
    highest_v = max_z
    if resolved.roofs:
        r0 = resolved.roofs[0]
        if r0.eaves_elevation > 0:
            e_text = f"+{r0.eaves_elevation:.2f}"
            level_markers.append(LevelMarker2D(
                id="level-eaves",
                label=f"ระดับอะเส {e_text}",
                elevation=r0.eaves_elevation,
                display_text=e_text,
                start_u=u_start,
                end_u=u_end,
            ))
        if r0.ridge_elevation > r0.eaves_elevation:
            rg_text = f"+{r0.ridge_elevation:.2f}"
            level_markers.append(LevelMarker2D(
                id="level-ridge",
                label=f"ระดับอกไก่ {rg_text}",
                elevation=r0.ridge_elevation,
                display_text=rg_text,
                start_u=u_start,
                end_u=u_end,
            ))
            highest_v = max(highest_v, r0.ridge_elevation)

    # 9. Generate Vertical Grid Lines
    grid_lines: List[ElevationGridLine2D] = []
    v_top = highest_v + 1.5

    if norm_dir in ("FRONT", "REAR"):
        # Grid X axes
        grid_axes = sorted(manifest.grids.axes_x.items(), key=lambda kv: kv[1])
        if norm_dir == "REAR":
            grid_axes.reverse()

        for g_id, x_pos in grid_axes:
            u_pos, _, _ = map_3d_point_to_uv(x_pos, min_y, 0.0, norm_dir, bounds_3d)
            line = LineString([(u_pos, 0.0), (u_pos, v_top)])
            grid_lines.append(ElevationGridLine2D(
                id=g_id,
                position_u=u_pos,
                start_v=0.0,
                end_v=v_top,
                line=line,
            ))
    else:
        # Grid Y axes
        grid_axes = sorted(manifest.grids.axes_y.items(), key=lambda kv: kv[1])
        if norm_dir == "LEFT":
            grid_axes.reverse()

        for g_id, y_pos in grid_axes:
            u_pos, _, _ = map_3d_point_to_uv(min_x, y_pos, 0.0, norm_dir, bounds_3d)
            line = LineString([(u_pos, 0.0), (u_pos, v_top)])
            grid_lines.append(ElevationGridLine2D(
                id=g_id,
                position_u=u_pos,
                start_v=0.0,
                end_v=v_top,
                line=line,
            ))

    bounds = (
        round(u_start - 1.0, 4),
        round(-0.5, 4),
        round(u_end + 1.0, 4),
        round(v_top + 1.0, 4),
    )

    return ElevationResult(
        direction=norm_dir,
        title_th=title_th,
        title_en=title_en,
        elements=elements,
        level_markers=level_markers,
        grid_lines=grid_lines,
        bounds=bounds,
        max_height=highest_v,
    )
