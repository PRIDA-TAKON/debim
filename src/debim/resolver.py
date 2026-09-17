"""
3D Spatial Coordinate Resolver for debim.
Converts relative grid and storey references into absolute 3D world coordinates
and geometric dimensions.
"""

import math
from typing import Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict

from debim.schema import (
    IfcBeam,
    IfcColumn,
    IfcCustomElement,
    IfcDoor,
    IfcFooting,
    IfcSlab,
    IfcStair,
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


class ResolvedPile(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    position: Tuple[float, float, float]  # Top of pile (under footing cap)
    length: float
    dimension: float
    shape: str = "HEXAGONAL"
    material: Optional[str] = None


class ResolvedFooting(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcFooting
    position: Tuple[float, float, float]
    width: float
    depth: float
    thickness: float
    piles: List[ResolvedPile] = []


class ResolvedSlab(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcSlab
    polygon: List[Tuple[float, float, float]]  # Vertices in 3D (x, y, z)
    thickness: float
    area: float  # Top surface area (m2)
    center: Tuple[float, float, float]  # Centroid (cx, cy, cz)


class ResolvedStairFlight(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    start_point: Tuple[float, float, float]  # (x, y, z) at bottom of flight
    end_point: Tuple[float, float, float]    # (x, y, z) at top of flight
    width: float
    waist_thickness: float
    run_length: float      # Horizontal run (m)
    rise_height: float     # Vertical rise (m)
    slope_length: float    # True sloped length (m)
    n_risers: int
    tread: float
    riser: float


class ResolvedStair(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcStair
    flights: List[ResolvedStairFlight] = []
    landing_polygon: Optional[List[Tuple[float, float, float]]] = None
    landing_thickness: float = 0.12
    landing_area: float = 0.0
    total_concrete_volume: float = 0.0
    total_formwork_area: float = 0.0


ResolvedElement = Union[
    ResolvedColumn,
    ResolvedBeam,
    ResolvedWall,
    ResolvedFooting,
    ResolvedSlab,
    ResolvedStair,
    ResolvedCustomElement,
]


class ResolvedManifest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    manifest: ProjectManifest
    footings: List[ResolvedFooting] = []
    columns: List[ResolvedColumn] = []
    beams: List[ResolvedBeam] = []
    walls: List[ResolvedWall] = []
    slabs: List[ResolvedSlab] = []
    stairs: List[ResolvedStair] = []
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

        resolved_piles: List[ResolvedPile] = []
        if footing.piles and footing.piles.count > 0:
            p_count = footing.piles.count
            p_len = footing.piles.length
            p_prof = footing.piles.profile
            p_dim = p_prof.dimension if p_prof else 0.15
            p_shape = p_prof.shape if p_prof else "HEXAGONAL"
            p_mat = footing.piles.material or footing.material

            # Determine pile positions relative to footing center
            # Spacing between piles (default: 3 * dimension or 0.6m if not specified)
            spacing = footing.piles.spacing if footing.piles.spacing else max(0.50, p_dim * 3.0)
            half_s = spacing / 2.0

            offsets: List[Tuple[float, float]] = []
            if p_count == 1:
                offsets = [(0.0, 0.0)]
            elif p_count == 2:
                offsets = [(0.0, -half_s), (0.0, half_s)]
            elif p_count == 3:
                # Triangular arrangement
                r = spacing / math.sqrt(3.0)
                offsets = [
                    (0.0, r),
                    (-spacing / 2.0, -r / 2.0),
                    (spacing / 2.0, -r / 2.0),
                ]
            elif p_count == 4:
                # 2x2 grid
                offsets = [
                    (-half_s, -half_s),
                    (half_s, -half_s),
                    (-half_s, half_s),
                    (half_s, half_s),
                ]
            elif p_count == 5:
                # 4 corners + 1 center
                offsets = [
                    (-half_s, -half_s),
                    (half_s, -half_s),
                    (-half_s, half_s),
                    (half_s, half_s),
                    (0.0, 0.0),
                ]
            elif p_count == 6:
                # 2 rows of 3
                offsets = [
                    (-half_s, -spacing),
                    (-half_s, 0.0),
                    (-half_s, spacing),
                    (half_s, -spacing),
                    (half_s, 0.0),
                    (half_s, spacing),
                ]
            else:
                # General circular / grid distribution fallback
                for i in range(p_count):
                    angle = 2.0 * math.pi * i / p_count
                    radius = spacing * 0.75
                    offsets.append((radius * math.cos(angle), radius * math.sin(angle)))

            # Piles start directly beneath the bottom face of the footing cap (z)
            for idx, (ox, oy) in enumerate(offsets):
                resolved_piles.append(
                    ResolvedPile(
                        tag=f"{footing.tag}-P{idx + 1}",
                        position=(gx + ox, gy + oy, z),
                        length=p_len,
                        dimension=p_dim,
                        shape=p_shape,
                        material=p_mat,
                    )
                )

        return ResolvedFooting(
            tag=footing.tag,
            element=footing,
            position=(gx, gy, z),
            width=footing.profile.width,
            depth=footing.profile.depth,
            thickness=footing.profile.thickness,
            piles=resolved_piles,
        )

    def resolve_slab(self, slab: IfcSlab) -> ResolvedSlab:
        storey = self.get_storey(slab.placement.storey)
        z = storey.elevation + slab.placement.offset_z

        # Resolve polygon vertices in 2D and 3D
        poly_3d: List[Tuple[float, float, float]] = []
        pts_2d: List[Tuple[float, float]] = []
        for grid_pt in slab.placement.boundary:
            x, y = self.get_grid_xy(grid_pt)
            pts_2d.append((x, y))
            poly_3d.append((x, y, z))

        # Calculate polygon area using Shoelace formula
        n = len(pts_2d)
        area = 0.0
        if n >= 3:
            for i in range(n):
                j = (i + 1) % n
                area += pts_2d[i][0] * pts_2d[j][1]
                area -= pts_2d[j][0] * pts_2d[i][1]
            area = abs(area) / 2.0

        # Calculate centroid center
        if n > 0:
            cx = sum(p[0] for p in pts_2d) / n
            cy = sum(p[1] for p in pts_2d) / n
        else:
            cx, cy = 0.0, 0.0

        return ResolvedSlab(
            tag=slab.tag,
            element=slab,
            polygon=poly_3d,
            thickness=slab.thickness,
            area=area,
            center=(cx, cy, z),
        )

    def resolve_stair(self, stair: IfcStair) -> ResolvedStair:
        from_st = self.get_storey(stair.placement.from_storey)
        to_st = self.get_storey(stair.placement.to_storey)

        z_bottom = from_st.elevation + stair.placement.offset_z
        z_top = to_st.elevation
        total_height = z_top - z_bottom

        gx, gy = self.get_grid_xy(stair.placement.grid_anchor)
        base_x = gx + stair.placement.offset_x
        base_y = gy + stair.placement.offset_y

        w = stair.width
        waist_t = stair.waist_thickness

        # Steps config
        riser = stair.steps.riser if stair.steps else 0.1875
        tread = stair.steps.tread if stair.steps else 0.25

        flights: List[ResolvedStairFlight] = []
        tot_conc_vol = 0.0
        tot_formwork = 0.0

        if stair.stair_type == "DOG_LEG":
            # Dog-leg U-shape stair with mid-landing
            landing_elev = (
                stair.landing.elevation
                if stair.landing
                else total_height / 2.0
            )
            landing_depth = stair.landing.depth if stair.landing else 1.00
            landing_t = stair.landing.thickness if stair.landing else 0.12

            z_mid = z_bottom + landing_elev
            rise_1 = landing_elev
            rise_2 = total_height - landing_elev

            n_risers_1 = max(1, int(round(rise_1 / riser)))
            n_risers_2 = max(1, int(round(rise_2 / riser)))
            run_1 = (n_risers_1 - 1) * tread
            run_2 = (n_risers_2 - 1) * tread

            slope_1 = math.hypot(run_1, rise_1)
            slope_2 = math.hypot(run_2, rise_2)

            # Flight 1: Bottom to Landing
            # Orientation determines flight vector (+Y: runs in +Y direction)
            if stair.placement.orientation == "+Y":
                p1_start = (base_x, base_y, z_bottom)
                p1_end = (base_x, base_y + run_1, z_mid)
                p2_start = (base_x + w, base_y + run_1, z_mid)
                p2_end = (base_x + w, base_y + run_1 - run_2, z_top)
                landing_poly = [
                    (base_x, base_y + run_1, z_mid),
                    (base_x + 2 * w, base_y + run_1, z_mid),
                    (base_x + 2 * w, base_y + run_1 + landing_depth, z_mid),
                    (base_x, base_y + run_1 + landing_depth, z_mid),
                ]
            else:
                p1_start = (base_x, base_y, z_bottom)
                p1_end = (base_x + run_1, base_y, z_mid)
                p2_start = (base_x + run_1, base_y + w, z_mid)
                p2_end = (base_x + run_1 - run_2, base_y + w, z_top)
                landing_poly = [
                    (base_x + run_1, base_y, z_mid),
                    (base_x + run_1, base_y + 2 * w, z_mid),
                    (base_x + run_1 + landing_depth, base_y + 2 * w, z_mid),
                    (base_x + run_1 + landing_depth, base_y, z_mid),
                ]

            f1 = ResolvedStairFlight(
                tag=f"{stair.tag}-F1",
                start_point=p1_start,
                end_point=p1_end,
                width=w,
                waist_thickness=waist_t,
                run_length=run_1,
                rise_height=rise_1,
                slope_length=slope_1,
                n_risers=n_risers_1,
                tread=tread,
                riser=rise_1 / n_risers_1,
            )
            f2 = ResolvedStairFlight(
                tag=f"{stair.tag}-F2",
                start_point=p2_start,
                end_point=p2_end,
                width=w,
                waist_thickness=waist_t,
                run_length=run_2,
                rise_height=rise_2,
                slope_length=slope_2,
                n_risers=n_risers_2,
                tread=tread,
                riser=rise_2 / n_risers_2,
            )
            flights.extend([f1, f2])

            landing_area = (2.0 * w) * landing_depth
            landing_vol = landing_area * landing_t

            # Concrete volume: waist + steps triangles + landing
            vol_f1 = (slope_1 * w * waist_t) + (n_risers_1 * 0.5 * tread * (rise_1 / n_risers_1) * w)
            vol_f2 = (slope_2 * w * waist_t) + (n_risers_2 * 0.5 * tread * (rise_2 / n_risers_2) * w)
            tot_conc_vol = vol_f1 + vol_f2 + landing_vol

            # Formwork: soffit + riser faces + side edge
            form_f1 = (slope_1 * w) + (n_risers_1 * (rise_1 / n_risers_1) * w) + (slope_1 * waist_t * 2)
            form_f2 = (slope_2 * w) + (n_risers_2 * (rise_2 / n_risers_2) * w) + (slope_2 * waist_t * 2)
            tot_formwork = form_f1 + form_f2 + landing_area

        else:
            # Straight flight
            n_risers = max(1, int(round(total_height / riser)))
            run = (n_risers - 1) * tread
            slope = math.hypot(run, total_height)
            p_start = (base_x, base_y, z_bottom)
            p_end = (base_x, base_y + run, z_top)

            f = ResolvedStairFlight(
                tag=f"{stair.tag}-F1",
                start_point=p_start,
                end_point=p_end,
                width=w,
                waist_thickness=waist_t,
                run_length=run,
                rise_height=total_height,
                slope_length=slope,
                n_risers=n_risers,
                tread=tread,
                riser=total_height / n_risers,
            )
            flights.append(f)
            landing_poly = None
            landing_area = 0.0
            landing_t = 0.0

            vol_f = (slope * w * waist_t) + (n_risers * 0.5 * tread * (total_height / n_risers) * w)
            tot_conc_vol = vol_f
            tot_formwork = (slope * w) + (n_risers * (total_height / n_risers) * w) + (slope * waist_t * 2)

        return ResolvedStair(
            tag=stair.tag,
            element=stair,
            flights=flights,
            landing_polygon=landing_poly,
            landing_thickness=landing_t,
            landing_area=landing_area,
            total_concrete_volume=tot_conc_vol,
            total_formwork_area=tot_formwork,
        )

    def resolve(self) -> ResolvedManifest:
        resolved_manifest = ResolvedManifest(manifest=self.manifest)

        for elem in self.manifest.elements:
            if isinstance(elem, IfcFooting):
                r_footing = self.resolve_footing(elem)
                resolved_manifest.footings.append(r_footing)
                resolved_manifest.elements.append(r_footing)
            elif isinstance(elem, IfcSlab):
                r_slab = self.resolve_slab(elem)
                resolved_manifest.slabs.append(r_slab)
                resolved_manifest.elements.append(r_slab)
            elif isinstance(elem, IfcStair):
                r_stair = self.resolve_stair(elem)
                resolved_manifest.stairs.append(r_stair)
                resolved_manifest.elements.append(r_stair)
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
