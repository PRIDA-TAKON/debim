"""
Core 2D Vertical Cut-Plane Slicing & Section Projection Engine for debim.
Slices 3D BIM models at vertical cutting planes (Section A-A, Section B-B)
and generates 2D cross-section primitives, CAD hatching tags, background projections,
storey level markers, and perpendicular grid lines.
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
    box,
)
from shapely.geometry.base import BaseGeometry

from debim.draw.projection import coords_from_geometry
from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedCovering,
    ResolvedCustomElement,
    ResolvedDoor,
    ResolvedFooting,
    ResolvedManifest,
    ResolvedPile,
    ResolvedRamp,
    ResolvedRoof,
    ResolvedSlab,
    ResolvedStair,
    ResolvedWall,
    ResolvedWindow,
    SpatialResolver,
)
from debim.schema import (
    BoxProfile,
    CircularProfile,
    ProjectManifest,
)


class SectionCutElement(BaseModel):
    """Represents an element sliced by a vertical section cut plane."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element_class: str
    category: Literal["heavy_cut", "medium_cut", "low_projection"]
    hatch_pattern: Literal["concrete", "wall", "solid", "steel"] = "concrete"
    geometry: Union[Polygon, MultiPolygon]
    polygon_coords: List[List[Tuple[float, float]]] = Field(default_factory=list)
    layer: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.polygon_coords and self.geometry is not None:
            self.polygon_coords = coords_from_geometry(self.geometry)


class SectionProjectionElement(BaseModel):
    """Represents a background element projected behind the section cut plane."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element_class: str
    category: Literal["projection", "low_projection"] = "projection"
    geometry: Union[Polygon, MultiPolygon, LineString, MultiLineString]
    polygon_coords: List[List[Tuple[float, float]]] = Field(default_factory=list)
    layer: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.polygon_coords and self.geometry is not None:
            self.polygon_coords = coords_from_geometry(self.geometry)


class StoreyLevelMarker(BaseModel):
    """Represents an elevation level marker line and label in section view."""
    id: str
    name: str
    elevation: float
    display_text: str  # e.g. "+0.00", "+3.20", "-1.50"


class SectionCutPlaneResult(BaseModel):
    """Result of vertical section plane slicing."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    section_id: str = "A-A"
    title: str = "Section A-A"
    plane_axis: Literal["X", "Y"] = "Y"
    position: float = 0.0
    grid_id: Optional[str] = None
    clip_distance: float = 12.0
    view_direction: float = 1.0  # +1.0 or -1.0
    cut_elements: List[SectionCutElement] = Field(default_factory=list)
    projection_elements: List[SectionProjectionElement] = Field(default_factory=list)
    grid_lines: List[Dict[str, Any]] = Field(default_factory=list)  # perpendicular grid markers
    level_markers: List[StoreyLevelMarker] = Field(default_factory=list)
    bounds: Tuple[float, float, float, float] = (0.0, 0.0, 10.0, 10.0)  # (min_u, min_z, max_u, max_z)

    @property
    def heavy_cut_elements(self) -> List[SectionCutElement]:
        return [e for e in self.cut_elements if e.category == "heavy_cut"]

    @property
    def medium_cut_elements(self) -> List[SectionCutElement]:
        return [e for e in self.cut_elements if e.category == "medium_cut"]


def _format_elevation(elev: float) -> str:
    """Format elevation string as +0.00, -1.50, or ±0.00."""
    if abs(elev) < 1e-4:
        return "±0.00"
    elif elev > 0:
        return f"+{elev:.2f}"
    else:
        return f"{elev:.2f}"


def slice_section(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
    section_id: str = "A-A",
    plane_axis: Literal["X", "Y"] = "Y",
    position: Optional[float] = None,
    grid_id: Optional[str] = None,
    clip_distance: float = 12.0,
    view_direction: float = 1.0,
    title: Optional[str] = None,
) -> SectionCutPlaneResult:
    """
    Slices the 3D building model at a vertical section cutting plane (parallel to X or Y axis)
    and generates 2D cross-section primitives, CAD hatching tags, background projected elements,
    storey level markers, and perpendicular grid lines.

    - plane_axis="Y": Cut plane equation Y = position. Section horizontal coordinate U = X, vertical = Z.
    - plane_axis="X": Cut plane equation X = position. Section horizontal coordinate U = Y, vertical = Z.
    """
    if isinstance(manifest_or_resolved, ProjectManifest):
        resolved = SpatialResolver(manifest_or_resolved).resolve()
        manifest = manifest_or_resolved
    else:
        resolved = manifest_or_resolved
        manifest = resolved.manifest

    # Resolve position from grid_id if specified
    if grid_id is not None:
        if plane_axis == "Y" and grid_id in manifest.grids.axes_y:
            position = manifest.grids.axes_y[grid_id]
        elif plane_axis == "X" and grid_id in manifest.grids.axes_x:
            position = manifest.grids.axes_x[grid_id]

    # Default position if None
    if position is None:
        if plane_axis == "Y":
            vals = list(manifest.grids.axes_y.values())
            position = (sum(vals) / len(vals)) if vals else 0.0
        else:
            vals = list(manifest.grids.axes_x.values())
            position = (sum(vals) / len(vals)) if vals else 0.0

    cut_pos = position
    sec_title = title or f"Section {section_id}"

    cut_elements: List[SectionCutElement] = []
    projection_elements: List[SectionProjectionElement] = []
    u_points: List[float] = []
    z_points: List[float] = []

    # 1. Process Slabs
    for slab in resolved.slabs:
        s_z = slab.center[2]
        s_thick = slab.thickness or 0.20
        z_bot = s_z - s_thick
        z_top = s_z
        z_points.extend([z_bot, z_top])

        if slab.polygon and len(slab.polygon) >= 3:
            poly_2d = Polygon([(p[0], p[1]) for p in slab.polygon])

            # Subtract voids if any
            for void_pts_3d in slab.voids:
                if len(void_pts_3d) >= 3:
                    v_poly = Polygon([(vp[0], vp[1]) for vp in void_pts_3d])
                    poly_2d = poly_2d.difference(v_poly)

            # Intersect with cut line
            if plane_axis == "Y":
                cut_line = LineString([(-1000.0, cut_pos), (1000.0, cut_pos)])
            else:
                cut_line = LineString([(cut_pos, -1000.0), (cut_pos, 1000.0)])

            inter = poly_2d.intersection(cut_line)
            if not inter.is_empty:
                lines = [inter] if isinstance(inter, LineString) else (inter.geoms if hasattr(inter, "geoms") else [])
                for line in lines:
                    if isinstance(line, LineString) and not line.is_empty:
                        coords = list(line.coords)
                        if plane_axis == "Y":
                            u1, u2 = min(coords[0][0], coords[1][0]), max(coords[0][0], coords[1][0])
                        else:
                            u1, u2 = min(coords[0][1], coords[1][1]), max(coords[0][1], coords[1][1])

                        if abs(u2 - u1) > 1e-4:
                            u_points.extend([u1, u2])
                            s_box = box(u1, z_bot, u2, z_top)
                            cut_elements.append(SectionCutElement(
                                tag=slab.tag,
                                element_class="IfcSlab",
                                category="heavy_cut",
                                hatch_pattern="concrete",
                                geometry=s_box,
                                layer=slab.layer,
                                properties={"material": slab.element.material, "thickness": s_thick},
                            ))

    # 2. Process Footings
    for footing in resolved.footings:
        fx, fy, fz = footing.position
        fw = footing.width
        fd = footing.depth
        ft = footing.thickness
        z_bot = fz - ft
        z_top = fz
        z_points.extend([z_bot, z_top])

        if plane_axis == "Y":
            is_cut = (fy - fd / 2.0) <= cut_pos <= (fy + fd / 2.0)
            u1, u2 = fx - fw / 2.0, fx + fw / 2.0
        else:
            is_cut = (fx - fw / 2.0) <= cut_pos <= (fx + fw / 2.0)
            u1, u2 = fy - fd / 2.0, fy + fd / 2.0

        if is_cut:
            u_points.extend([u1, u2])
            f_box = box(u1, z_bot, u2, z_top)
            cut_elements.append(SectionCutElement(
                tag=footing.tag,
                element_class="IfcFooting",
                category="heavy_cut",
                hatch_pattern="concrete",
                geometry=f_box,
                layer=footing.layer,
                properties={"thickness": ft, "width": fw, "depth": fd},
            ))

    # 3. Process Beams
    for beam in resolved.beams:
        bx1, by1, bz1 = beam.start_point
        bx2, by2, bz2 = beam.end_point
        b_depth = getattr(beam, "depth", None) or 0.40
        b_width = getattr(beam, "width", None) or 0.20
        z_top = max(bz1, bz2)
        z_bot = z_top - b_depth
        z_points.extend([z_bot, z_top])

        if plane_axis == "Y":
            min_y = min(by1, by2) - b_width / 2.0
            max_y = max(by1, by2) + b_width / 2.0
            is_cut = min_y <= cut_pos <= max_y
            u1 = min(bx1, bx2) - (b_width / 2.0 if abs(bx2 - bx1) < 1e-4 else 0.0)
            u2 = max(bx1, bx2) + (b_width / 2.0 if abs(bx2 - bx1) < 1e-4 else 0.0)
            in_background = (cut_pos < min_y <= cut_pos + clip_distance)
        else:
            min_x = min(bx1, bx2) - b_width / 2.0
            max_x = max(bx1, bx2) + b_width / 2.0
            is_cut = min_x <= cut_pos <= max_x
            u1 = min(by1, by2) - (b_width / 2.0 if abs(by2 - by1) < 1e-4 else 0.0)
            u2 = max(by1, by2) + (b_width / 2.0 if abs(by2 - by1) < 1e-4 else 0.0)
            in_background = (cut_pos < min_x <= cut_pos + clip_distance)

        if is_cut and abs(u2 - u1) > 1e-4:
            u_points.extend([u1, u2])
            b_box = box(u1, z_bot, u2, z_top)
            cut_elements.append(SectionCutElement(
                tag=beam.tag,
                element_class="IfcBeam",
                category="heavy_cut",
                hatch_pattern="concrete",
                geometry=b_box,
                layer=beam.layer,
                properties={"material": beam.element.material, "depth": b_depth, "width": b_width},
            ))
        elif in_background and abs(u2 - u1) > 1e-4:
            b_box = box(u1, z_bot, u2, z_top)
            projection_elements.append(SectionProjectionElement(
                tag=beam.tag,
                element_class="IfcBeam",
                category="projection",
                geometry=b_box,
                layer=beam.layer,
                properties={"material": beam.element.material},
            ))

    # 4. Process Walls
    for wall in resolved.walls:
        wx1, wy1, wz1 = wall.start_point
        wx2, wy2, _ = wall.end_point
        w_thick = wall.thickness
        w_height = wall.height
        z_bot = wz1
        z_top = wz1 + w_height
        z_points.extend([z_bot, z_top])

        w_len = math.hypot(wx2 - wx1, wy2 - wy1)
        if w_len <= 0:
            continue

        ux = (wx2 - wx1) / w_len
        uy = (wy2 - wy1) / w_len
        nx, ny = -uy, ux

        ht = w_thick / 2.0
        w_poly_2d = Polygon([
            (wx1 + ht * nx, wy1 + ht * ny),
            (wx2 + ht * nx, wy2 + ht * ny),
            (wx2 - ht * nx, wy2 - ht * ny),
            (wx1 - ht * nx, wy1 - ht * ny),
        ])

        if plane_axis == "Y":
            cut_line = LineString([(-1000.0, cut_pos), (1000.0, cut_pos)])
            in_bg = (cut_pos < min(wy1, wy2) <= cut_pos + clip_distance)
        else:
            cut_line = LineString([(cut_pos, -1000.0), (cut_pos, 1000.0)])
            in_bg = (cut_pos < min(wx1, wx2) <= cut_pos + clip_distance)

        inter = w_poly_2d.intersection(cut_line)
        if not inter.is_empty:
            lines = [inter] if isinstance(inter, LineString) else (inter.geoms if hasattr(inter, "geoms") else [])
            for line in lines:
                if isinstance(line, LineString) and not line.is_empty:
                    coords = list(line.coords)
                    if plane_axis == "Y":
                        u1, u2 = min(coords[0][0], coords[1][0]), max(coords[0][0], coords[1][0])
                    else:
                        u1, u2 = min(coords[0][1], coords[1][1]), max(coords[0][1], coords[1][1])

                    if abs(u2 - u1) > 1e-4:
                        u_points.extend([u1, u2])
                        w_box = box(u1, z_bot, u2, z_top)

                        # Subtract door/window openings
                        for child in wall.children:
                            c_z_bot = z_bot + child.sill_height
                            c_z_top = c_z_bot + child.height

                            d1 = child.offset_distance
                            d2 = d1 + child.width
                            o_p0 = (wx1 + d1 * ux, wy1 + d1 * uy)
                            o_p1 = (wx1 + d2 * ux, wy1 + d2 * uy)

                            if plane_axis == "Y":
                                cu1, cu2 = min(o_p0[0], o_p1[0]), max(o_p0[0], o_p1[0])
                            else:
                                cu1, cu2 = min(o_p0[1], o_p1[1]), max(o_p0[1], o_p1[1])

                            # Opening subtract box
                            o_box = box(cu1 - 0.01, c_z_bot, cu2 + 0.01, c_z_top)
                            w_box = w_box.difference(o_box)

                        is_bearing = (w_thick >= 0.12) or any(k in wall.tag.upper() for k in ["CORE", "BEARING", "SHEAR"])
                        is_glass = "GLASS" in wall.tag.upper() or "GLASS" in (wall.element.material or "").upper()

                        cat: Literal["heavy_cut", "medium_cut"] = "heavy_cut" if is_bearing else "medium_cut"
                        hatch: Literal["concrete", "wall", "solid", "steel"] = "concrete" if is_bearing else ("solid" if is_glass else "wall")

                        cut_elements.append(SectionCutElement(
                            tag=wall.tag,
                            element_class="IfcWall",
                            category=cat,
                            hatch_pattern=hatch,
                            geometry=w_box,
                            layer=wall.layer,
                            properties={"material": wall.element.material, "thickness": w_thick, "height": w_height},
                        ))
        elif in_bg:
            if plane_axis == "Y":
                u1, u2 = min(wx1, wx2), max(wx1, wx2)
            else:
                u1, u2 = min(wy1, wy2), max(wy1, wy2)

            if abs(u2 - u1) > 1e-4:
                w_box = box(u1, z_bot, u2, z_top)
                projection_elements.append(SectionProjectionElement(
                    tag=wall.tag,
                    element_class="IfcWall",
                    category="projection",
                    geometry=w_box,
                    layer=wall.layer,
                    properties={"material": wall.element.material},
                ))

    # 5. Process Columns (Cut or Background)
    for col in resolved.columns:
        cx1, cy1, cz1 = col.start_point
        cx2, cy2, cz2 = col.end_point
        z_bot = min(cz1, cz2)
        z_top = max(cz1, cz2)
        z_points.extend([z_bot, z_top])

        prof = col.element.profile
        w = getattr(prof, "width", 0.30) if isinstance(prof, BoxProfile) else 0.30
        d = getattr(prof, "depth", 0.30) if isinstance(prof, BoxProfile) else 0.30

        if plane_axis == "Y":
            is_cut = (cy1 - d / 2.0) <= cut_pos <= (cy1 + d / 2.0)
            in_bg = (cut_pos < cy1 <= cut_pos + clip_distance)
            u1, u2 = cx1 - w / 2.0, cx1 + w / 2.0
        else:
            is_cut = (cx1 - w / 2.0) <= cut_pos <= (cx1 + w / 2.0)
            in_bg = (cut_pos < cx1 <= cut_pos + clip_distance)
            u1, u2 = cy1 - d / 2.0, cy1 + d / 2.0

        if is_cut:
            u_points.extend([u1, u2])
            col_box = box(u1, z_bot, u2, z_top)
            cut_elements.append(SectionCutElement(
                tag=col.tag,
                element_class="IfcColumn",
                category="heavy_cut",
                hatch_pattern="concrete",
                geometry=col_box,
                layer=col.layer,
                properties={"material": col.element.material, "width": w, "depth": d},
            ))
        elif in_bg:
            col_box = box(u1, z_bot, u2, z_top)
            projection_elements.append(SectionProjectionElement(
                tag=col.tag,
                element_class="IfcColumn",
                category="projection",
                geometry=col_box,
                layer=col.layer,
                properties={"material": col.element.material},
            ))

    # 6. Process Background Doors and Windows
    for door in resolved.doors:
        dx, dy, dz = door.position
        dw, dh = door.width, door.height
        if plane_axis == "Y":
            in_bg = (cut_pos < dy <= cut_pos + clip_distance)
            u1, u2 = dx - dw / 2.0, dx + dw / 2.0
        else:
            in_bg = (cut_pos < dx <= cut_pos + clip_distance)
            u1, u2 = dy - dw / 2.0, dy + dw / 2.0

        if in_bg:
            d_box = box(u1, dz, u2, dz + dh)
            projection_elements.append(SectionProjectionElement(
                tag=door.tag,
                element_class="IfcDoor",
                category="projection",
                geometry=d_box,
                layer=door.layer,
                properties={"width": dw, "height": dh},
            ))

    for win in resolved.windows:
        wx, wy, wz = win.position
        ww, wh = win.width, win.height
        if plane_axis == "Y":
            in_bg = (cut_pos < wy <= cut_pos + clip_distance)
            u1, u2 = wx - ww / 2.0, wx + ww / 2.0
        else:
            in_bg = (cut_pos < dx <= cut_pos + clip_distance)
            u1, u2 = wy - ww / 2.0, wy + ww / 2.0

        if in_bg:
            w_box = box(u1, wz, u2, wz + wh)
            projection_elements.append(SectionProjectionElement(
                tag=win.tag,
                element_class="IfcWindow",
                category="projection",
                geometry=w_box,
                layer=win.layer,
                properties={"width": ww, "height": wh},
            ))

    # 7. Storey Level Markers
    level_markers: List[StoreyLevelMarker] = []
    if manifest.spatial_structure.storeys:
        for s in manifest.spatial_structure.storeys:
            elev = s.elevation
            z_points.append(elev)
            level_markers.append(StoreyLevelMarker(
                id=s.id,
                name=s.name,
                elevation=elev,
                display_text=f"{s.name}  {_format_elevation(elev)}",
            ))

    # 8. Perpendicular Grid Lines along U
    perpendicular_grids: List[Dict[str, Any]] = []
    if plane_axis == "Y":
        # Y-cut plane -> perpendicular grids are X-axes
        for g_id, x_pos in sorted(manifest.grids.axes_x.items(), key=lambda k: k[1]):
            if "-" not in g_id:
                perpendicular_grids.append({"id": g_id, "position": x_pos})
                u_points.append(x_pos)
    else:
        # X-cut plane -> perpendicular grids are Y-axes
        for g_id, y_pos in sorted(manifest.grids.axes_y.items(), key=lambda k: k[1]):
            if "-" not in g_id:
                perpendicular_grids.append({"id": g_id, "position": y_pos})
                u_points.append(y_pos)

    # Calculate Bounds
    min_u = min(u_points) - 2.0 if u_points else 0.0
    max_u = max(u_points) + 2.0 if u_points else 10.0
    min_z = min(z_points) - 1.5 if z_points else -1.5
    max_z = max(z_points) + 2.0 if z_points else 5.0

    return SectionCutPlaneResult(
        section_id=section_id,
        title=sec_title,
        plane_axis=plane_axis,
        position=cut_pos,
        grid_id=grid_id,
        clip_distance=clip_distance,
        view_direction=view_direction,
        cut_elements=cut_elements,
        projection_elements=projection_elements,
        grid_lines=perpendicular_grids,
        level_markers=level_markers,
        bounds=(round(min_u, 4), round(min_z, 4), round(max_u, 4), round(max_z, 4)),
    )


def project_2d_section(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest],
    section_id: str = "A-A",
    plane_axis: Literal["X", "Y"] = "Y",
    position: Optional[float] = None,
    grid_id: Optional[str] = None,
    clip_distance: float = 12.0,
) -> SectionCutPlaneResult:
    """Alias for slice_section."""
    return slice_section(
        manifest_or_resolved=manifest_or_resolved,
        section_id=section_id,
        plane_axis=plane_axis,
        position=position,
        grid_id=grid_id,
        clip_distance=clip_distance,
    )
