"""
3D Spatial Coordinate Resolver for debim.
Converts relative grid and storey references into absolute 3D world coordinates
and geometric dimensions.
"""

import math
from typing import Dict, List, Tuple, Union
from pydantic import BaseModel, ConfigDict

from debim.schema import (
    IfcBeam,
    IfcColumn,
    IfcCustomElement,
    IfcDoor,
    IfcFooting,
    IfcWall,
    IfcWindow,
    ProjectManifest,
    Storey,
)


class ResolvedColumn(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcColumn
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    height: float


class ResolvedBeam(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcBeam
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    span_length: float
    direction_vector: Tuple[float, float]
    rotation_angle: float


class ResolvedDoor(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcDoor
    position: Tuple[float, float, float]
    width: float
    height: float
    offset_distance: float
    sill_height: float


class ResolvedWindow(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcWindow
    position: Tuple[float, float, float]
    width: float
    height: float
    offset_distance: float
    sill_height: float


ResolvedWallChild = Union[ResolvedDoor, ResolvedWindow]


class ResolvedWall(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcWall
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    length: float
    thickness: float
    height: float
    children: List[ResolvedWallChild] = []


class ResolvedCustomElement(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcCustomElement
    position: Tuple[float, float, float]


class ResolvedFooting(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcFooting
    position: Tuple[float, float, float]
    width: float
    depth: float
    thickness: float


ResolvedElement = Union[
    ResolvedColumn,
    ResolvedBeam,
    ResolvedWall,
    ResolvedFooting,
    ResolvedCustomElement,
]


class ResolvedManifest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    manifest: ProjectManifest
    footings: List[ResolvedFooting] = []
    columns: List[ResolvedColumn] = []
    beams: List[ResolvedBeam] = []
    walls: List[ResolvedWall] = []
    doors: List[ResolvedDoor] = []
    windows: List[ResolvedWindow] = []
    custom_elements: List[ResolvedCustomElement] = []
    elements: List[ResolvedElement] = []

    def get_element_by_tag(self, tag: str) -> Union[ResolvedElement, None]:
        for elem in self.elements:
            if elem.tag == tag:
                return elem
        return None


class SpatialResolver:
    def __init__(self, manifest: ProjectManifest):
        self.manifest = manifest
        self.storeys: Dict[str, Storey] = {
            s.id: s for s in manifest.spatial_structure.storeys
        }
        self.axes_x: Dict[str, float] = manifest.grids.axes_x
        self.axes_y: Dict[str, float] = manifest.grids.axes_y

    def get_grid_xy(self, grid_ref: Tuple[str, str]) -> Tuple[float, float]:
        gx, gy = grid_ref
        if gx not in self.axes_x:
            raise ValueError(f"Grid X axis '{gx}' not found in manifest grids.")
        if gy not in self.axes_y:
            raise ValueError(f"Grid Y axis '{gy}' not found in manifest grids.")
        return (float(self.axes_x[gx]), float(self.axes_y[gy]))

    def get_storey(self, storey_id: str) -> Storey:
        if storey_id not in self.storeys:
            raise ValueError(f"Storey '{storey_id}' not found in spatial structure.")
        return self.storeys[storey_id]

    def resolve_column(self, col: IfcColumn) -> ResolvedColumn:
        gx, gy = self.get_grid_xy(col.placement.grid)
        base_s = self.get_storey(col.placement.base_storey)
        top_s = self.get_storey(col.placement.top_storey)

        z_start = base_s.elevation
        z_end = top_s.elevation
        height = z_end - z_start

        start_point = (gx, gy, z_start)
        end_point = (gx, gy, z_end)

        return ResolvedColumn(
            tag=col.tag,
            element=col,
            start_point=start_point,
            end_point=end_point,
            height=height,
        )

    def resolve_beam(self, beam: IfcBeam) -> ResolvedBeam:
        x1, y1 = self.get_grid_xy(beam.placement.from_grid)
        x2, y2 = self.get_grid_xy(beam.placement.to_grid)
        storey = self.get_storey(beam.placement.storey)

        z = storey.elevation + beam.placement.offset_z
        dx = x2 - x1
        dy = y2 - y1
        span_length = math.hypot(dx, dy)

        if span_length > 0:
            direction_vector = (dx / span_length, dy / span_length)
        else:
            direction_vector = (0.0, 0.0)

        rotation_angle = math.atan2(dy, dx)

        start_point = (x1, y1, z)
        end_point = (x2, y2, z)

        return ResolvedBeam(
            tag=beam.tag,
            element=beam,
            start_point=start_point,
            end_point=end_point,
            span_length=span_length,
            direction_vector=direction_vector,
            rotation_angle=rotation_angle,
        )

    def resolve_wall(
        self, wall: IfcWall
    ) -> Tuple[ResolvedWall, List[ResolvedDoor], List[ResolvedWindow]]:
        x1, y1 = self.get_grid_xy(wall.placement.from_grid)
        x2, y2 = self.get_grid_xy(wall.placement.to_grid)
        storey = self.get_storey(wall.placement.storey)

        z = storey.elevation
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)

        start_point = (x1, y1, z)
        end_point = (x2, y2, z)

        if length > 0:
            ux = dx / length
            uy = dy / length
        else:
            ux = 0.0
            uy = 0.0

        resolved_children: List[ResolvedWallChild] = []
        resolved_doors: List[ResolvedDoor] = []
        resolved_windows: List[ResolvedWindow] = []

        for child in wall.children:
            child_x = x1 + ux * child.offset_distance
            child_y = y1 + uy * child.offset_distance
            child_z = storey.elevation + child.sill_height
            child_pos = (child_x, child_y, child_z)

            if isinstance(child, IfcDoor):
                r_door = ResolvedDoor(
                    tag=child.tag,
                    element=child,
                    position=child_pos,
                    width=child.dimensions.width,
                    height=child.dimensions.height,
                    offset_distance=child.offset_distance,
                    sill_height=child.sill_height,
                )
                resolved_children.append(r_door)
                resolved_doors.append(r_door)
            elif isinstance(child, IfcWindow):
                r_win = ResolvedWindow(
                    tag=child.tag,
                    element=child,
                    position=child_pos,
                    width=child.dimensions.width,
                    height=child.dimensions.height,
                    offset_distance=child.offset_distance,
                    sill_height=child.sill_height,
                )
                resolved_children.append(r_win)
                resolved_windows.append(r_win)

        r_wall = ResolvedWall(
            tag=wall.tag,
            element=wall,
            start_point=start_point,
            end_point=end_point,
            length=length,
            thickness=wall.thickness,
            height=wall.height,
            children=resolved_children,
        )

        return r_wall, resolved_doors, resolved_windows

    def resolve_custom_element(
        self, custom: IfcCustomElement
    ) -> ResolvedCustomElement:
        storey = self.get_storey(custom.placement.storey)
        pos_x, pos_y, pos_z = custom.placement.position
        world_pos = (pos_x, pos_y, storey.elevation + pos_z)

        return ResolvedCustomElement(
            tag=custom.tag,
            element=custom,
            position=world_pos,
        )

    def resolve_footing(self, footing: IfcFooting) -> ResolvedFooting:
        gx, gy = self.get_grid_xy(footing.placement.grid)
        storey = self.get_storey(footing.placement.storey)
        z = storey.elevation + footing.placement.offset_z

        return ResolvedFooting(
            tag=footing.tag,
            element=footing,
            position=(gx, gy, z),
            width=footing.profile.width,
            depth=footing.profile.depth,
            thickness=footing.profile.thickness,
        )

    def resolve(self) -> ResolvedManifest:
        resolved_manifest = ResolvedManifest(manifest=self.manifest)

        for elem in self.manifest.elements:
            if isinstance(elem, IfcFooting):
                r_footing = self.resolve_footing(elem)
                resolved_manifest.footings.append(r_footing)
                resolved_manifest.elements.append(r_footing)
            elif isinstance(elem, IfcColumn):
                r_col = self.resolve_column(elem)
                resolved_manifest.columns.append(r_col)
                resolved_manifest.elements.append(r_col)
            elif isinstance(elem, IfcBeam):
                r_beam = self.resolve_beam(elem)
                resolved_manifest.beams.append(r_beam)
                resolved_manifest.elements.append(r_beam)
            elif isinstance(elem, IfcWall):
                r_wall, doors, windows = self.resolve_wall(elem)
                resolved_manifest.walls.append(r_wall)
                resolved_manifest.doors.extend(doors)
                resolved_manifest.windows.extend(windows)
                resolved_manifest.elements.append(r_wall)
            elif isinstance(elem, IfcCustomElement):
                r_custom = self.resolve_custom_element(elem)
                resolved_manifest.custom_elements.append(r_custom)
                resolved_manifest.elements.append(r_custom)

        return resolved_manifest


def resolve_manifest(manifest: ProjectManifest) -> ResolvedManifest:
    """Resolve a ProjectManifest into 3D world coordinates and geometric dimensions."""
    resolver = SpatialResolver(manifest)
    return resolver.resolve()
