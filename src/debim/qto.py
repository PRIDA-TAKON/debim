"""
Quantitative Take-Off (QTO) Engine for debim.
Calculates concrete volume, formwork area, and reinforcement (rebar) schedules/weights.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from debim.resolver import (
    ResolvedAirTerminal,
    ResolvedBeam,
    ResolvedCableCarrierSegment,
    ResolvedColumn,
    ResolvedCovering,
    ResolvedCustomElement,
    ResolvedDistributionBoard,
    ResolvedDuctSegment,
    ResolvedElement,
    ResolvedFooting,
    ResolvedLightFixture,
    ResolvedManifest,
    ResolvedOutlet,
    ResolvedPipeSegment,
    ResolvedRoof,
    ResolvedSanitaryTerminal,
    ResolvedSlab,
    ResolvedStair,
    ResolvedSwitchingDevice,
    ResolvedUnitaryEquipment,
    ResolvedTerminal,
    ResolvedWall,
    resolve_manifest,
)
from debim.schema import ProjectManifest, load_manifest

# Standard unit weights (kg/m) for reinforcement bars
UNIT_WEIGHTS: Dict[str, float] = {
    "RB6": 0.222,
    "RB9": 0.499,
    "DB12": 0.888,
    "DB16": 1.578,
    "DB20": 2.466,
    "DB25": 3.853,
}


def get_bar_unit_weight(bar_type: str) -> float:
    """Look up standard unit weight or calculate via generic formula (diameter_mm^2 / 162.0)."""
    clean_type = bar_type.strip().upper()
    if clean_type in UNIT_WEIGHTS:
        return UNIT_WEIGHTS[clean_type]

    match = re.search(r"(\d+)", clean_type)
    if match:
        diameter_mm = float(match.group(1))
        return (diameter_mm ** 2) / 162.0

    return 0.0


def parse_main_bars(
    main_str: Optional[str], element_length: float
) -> Tuple[Dict[str, float], float]:
    """
    Parse main bar specification (e.g. '4-DB16' or '2-DB16 + 3-DB20' or '2-DB16, 3-DB20').
    Returns (dict_by_bar_type, total_weight).
    """
    if not main_str:
        return {}, 0.0

    weights: Dict[str, float] = {}
    total_weight = 0.0

    # Split by + or comma
    terms = re.split(r"[+,]", main_str)
    for term in terms:
        term = term.strip()
        if not term:
            continue
        match = re.search(r"(\d+)\s*-\s*([A-Za-z0-9]+)", term)
        if match:
            count = int(match.group(1))
            bar_type = match.group(2).upper()
            unit_weight = get_bar_unit_weight(bar_type)
            weight = count * element_length * unit_weight
            weights[bar_type] = weights.get(bar_type, 0.0) + weight
            total_weight += weight

    return weights, total_weight


def parse_stirrups(
    stirrups_str: Optional[str], element_length: float, width: float, depth: float
) -> Tuple[Dict[str, float], float]:
    """
    Parse stirrups specification (e.g. 'RB6 @ 0.15m' or 'RB9 @ 0.15m').
    Perimeter = 2 * (width + depth)
    Number = int(element_length / spacing) + 1
    Total weight = number * perimeter * unit_weight
    Returns (dict_by_bar_type, total_weight).
    """
    if not stirrups_str:
        return {}, 0.0

    match = re.search(r"([A-Za-z0-9]+)\s*@\s*([0-9.]+)", stirrups_str)
    if not match:
        return {}, 0.0

    bar_type = match.group(1).upper()
    spacing = float(match.group(2))

    if spacing <= 0:
        return {}, 0.0

    perimeter = 2.0 * (width + depth)
    num_stirrups = int(element_length / spacing) + 1
    unit_weight = get_bar_unit_weight(bar_type)
    weight = num_stirrups * perimeter * unit_weight

    return {bar_type: weight}, weight


class SubstructureQTO(BaseModel):
    lean_concrete_volume: float = 0.0  # m³
    sand_bedding_volume: float = 0.0   # m³
    excavation_volume: float = 0.0     # m³
    pile_count: int = 0                # count
    pile_total_length: float = 0.0     # m
    pile_type: Optional[str] = None


class CoveringQTO(BaseModel):
    covering_type: str = "CEILING"
    area: float = 0.0                  # m²
    length: float = 0.0                # m
    thickness: float = 0.0             # m


class SlabFinishesQTO(BaseModel):
    floor_finish: Optional[str] = None
    tile_area: float = 0.0             # m²
    polished_concrete_area: float = 0.0 # m²
    skirting_length: float = 0.0       # m
    sand_bedding_volume: float = 0.0   # m³


class StairQTO(BaseModel):
    total_steps: int = 0
    tread_finish_area: float = 0.0     # m²
    riser_finish_area: float = 0.0     # m²
    nosing_length: float = 0.0         # m
    railing_length: float = 0.0        # m
    railing_type: Optional[str] = None


class WallFinishesQTO(BaseModel):
    net_area_one_side: float = 0.0      # m²
    plaster_area: float = 0.0           # m²
    paint_interior_area: float = 0.0    # m²
    paint_exterior_area: float = 0.0    # m²
    tile_area: float = 0.0              # m²


class RoofQTO(BaseModel):
    footprint_area: float = 0.0          # Projected horizontal area (m²)
    sloped_area: float = 0.0             # Sloped roof covering tile area (m²)
    ridge_cap_length: float = 0.0        # Ridge cap length (m)
    hip_cap_length: float = 0.0          # Hip cap length (m)
    eaves_length: float = 0.0            # Eaves/fascia board length (m)
    structural_steel_weight: float = 0.0 # SS400 structural steel weight (kg)
    insulation_area: float = 0.0         # Under-tile insulation area (m²)


class MepQTO(BaseModel):
    system_type: str = ""
    length: float = 0.0                    # ท่อ / สายไฟ / ท่อลม (linear meters)
    nominal_diameter: float = 0.0          # m (สำหรับท่อกลม)
    width: float = 0.0                     # m (สำหรับท่อลมสี่เหลี่ยม)
    height: float = 0.0                    # m (สำหรับท่อลมสี่เหลี่ยม)
    fittings_count: int = 0                # จำนวน fittings / ข้อต่อ
    fixture_type: str = ""                 # ประเภทสุขภัณฑ์หรืออุปกรณ์
    count: int = 1                         # จำนวนชิ้น / ชุด
    dimensions: Optional[Tuple[float, float, float]] = None
    capacity: Optional[float] = None       # CFM หรือ BTU


class ElementQTO(BaseModel):
    tag: str
    element_class: str
    material: Optional[str] = None
    concrete_volume: float = 0.0  # m³
    formwork_area: float = 0.0  # m²
    rebar_weights: Dict[str, float] = Field(default_factory=dict)  # kg by bar type
    total_rebar_weight: float = 0.0  # kg
    substructure: Optional[SubstructureQTO] = None
    stair_assembly: Optional[StairQTO] = None
    wall_finishes: Optional[WallFinishesQTO] = None
    roof: Optional[RoofQTO] = None
    covering: Optional[CoveringQTO] = None
    slab_finishes: Optional[SlabFinishesQTO] = None
    mep: Optional[MepQTO] = None


class ProjectQTO(BaseModel):
    elements: List[ElementQTO] = Field(default_factory=list)
    total_concrete_volume: float = 0.0
    total_formwork_area: float = 0.0
    total_rebar_weight: float = 0.0
    total_rebar_by_type: Dict[str, float] = Field(default_factory=dict)
    total_excavation_volume: float = 0.0
    total_lean_concrete_volume: float = 0.0
    total_sand_bedding_volume: float = 0.0
    total_pile_count: int = 0
    total_pile_length: float = 0.0
    total_nosing_length: float = 0.0
    total_railing_length: float = 0.0
    total_wall_masonry_area: float = 0.0
    total_wall_plaster_area: float = 0.0
    total_wall_paint_interior_area: float = 0.0
    total_wall_paint_exterior_area: float = 0.0
    total_wall_tile_area: float = 0.0
    total_roof_covering_area: float = 0.0
    total_roof_steel_weight: float = 0.0
    total_roof_ridge_length: float = 0.0
    total_roof_hip_length: float = 0.0
    total_roof_eaves_length: float = 0.0
    total_roof_insulation_area: float = 0.0
    # Ceilings & Floor Finishes Totals
    total_ceiling_gypsum_area: float = 0.0
    total_ceiling_tbar_area: float = 0.0
    total_ceiling_eaves_area: float = 0.0
    total_floor_tile_area: float = 0.0
    total_floor_polish_area: float = 0.0
    total_skirting_length: float = 0.0
    # MEP Totals
    total_cold_water_pipe_length: float = 0.0
    total_soil_pipe_length: float = 0.0
    total_waste_pipe_length: float = 0.0
    total_vent_pipe_length: float = 0.0
    total_drainage_pipe_length: float = 0.0
    total_refrigerant_pipe_length: float = 0.0
    total_condensate_pipe_length: float = 0.0
    total_pipe_fittings_count: int = 0
    total_conduit_length: float = 0.0
    total_conduit_fittings_count: int = 0
    total_duct_length: float = 0.0
    total_duct_fittings_count: int = 0
    total_sanitary_terminals_count: int = 0
    total_distribution_boards_count: int = 0
    total_lighting_fixtures_count: int = 0
    total_switches_count: int = 0
    total_outlets_count: int = 0
    total_air_terminals_count: int = 0
    total_unitary_equipment_count: int = 0


    def get_element(self, tag: str) -> Optional[ElementQTO]:
        for elem in self.elements:
            if elem.tag == tag:
                return elem
        return None


def calculate_element_qto(resolved: ResolvedElement) -> ElementQTO:
    """Calculate QTO for a resolved element."""
    tag = resolved.tag
    rebar_dict: Dict[str, float] = {}
    total_rebar = 0.0

    if isinstance(resolved, ResolvedFooting):
        elem = resolved.element
        w = resolved.width
        d = resolved.depth
        t = resolved.thickness
        vol = w * d * t
        formwork = 2.0 * (w + d) * t

        rebar_dict: Dict[str, float] = {}
        total_rebar = 0.0

        if elem.reinforcement:
            mx_dict, mx_wt = parse_main_bars(elem.reinforcement.mesh_x, w)
            my_dict, my_wt = parse_main_bars(elem.reinforcement.mesh_y, d)

            for btype, wt in mx_dict.items():
                rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
            for btype, wt in my_dict.items():
                rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
            total_rebar = mx_wt + my_wt

        cfg = getattr(elem, "substructure", None)
        has_substructure = cfg is not None or (elem.piles and elem.piles.count > 0)

        substructure = None
        if has_substructure:
            if elem.piles and elem.piles.count > 0:
                default_lean = 0.10
                default_sand = 0.05
            else:
                default_lean = 0.05
                default_sand = 0.10

            lean_thick = cfg.lean_thickness if (cfg and "lean_thickness" in cfg.model_fields_set) else default_lean
            sand_thick = cfg.sand_thickness if (cfg and "sand_thickness" in cfg.model_fields_set) else default_sand
            ws = cfg.excavation_working_space if cfg else 0.20
            depth = cfg.excavation_depth if (cfg and cfg.excavation_depth) else abs(elem.placement.offset_z if elem.placement.offset_z != 0 else 1.50)

            lean_vol = (w * d * lean_thick) if (not cfg or cfg.lean_concrete) else 0.0
            sand_vol = (w * d * sand_thick) if (not cfg or cfg.sand_bedding) else 0.0
            excav_vol = ((w + 2.0 * ws) * (d + 2.0 * ws) * depth) if (not cfg or cfg.excavation) else 0.0

            pile_cnt = 0
            total_len = 0.0
            pile_type_str = None
            if elem.piles and elem.piles.count > 0:
                pile_cnt = elem.piles.count
                total_len = pile_cnt * elem.piles.length
                pile_shape = elem.piles.profile.shape if elem.piles.profile else "HEXAGONAL"
                pile_dim = elem.piles.profile.dimension if elem.piles.profile else 0.15
                pile_type_str = f"{pile_shape}-{pile_dim}"

            substructure = SubstructureQTO(
                lean_concrete_volume=lean_vol,
                sand_bedding_volume=sand_vol,
                excavation_volume=excav_vol,
                pile_count=pile_cnt,
                pile_total_length=total_len,
                pile_type=pile_type_str,
            )

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=vol,
            formwork_area=formwork,
            rebar_weights=rebar_dict,
            total_rebar_weight=total_rebar,
            substructure=substructure,
        )

    elif isinstance(resolved, ResolvedColumn):
        elem = resolved.element
        w = elem.profile.width
        d = elem.profile.depth
        h = resolved.height

        vol = w * d * h
        formwork = 2.0 * (w + d) * h

        if elem.reinforcement:
            m_dict, m_wt = parse_main_bars(elem.reinforcement.main, h)
            s_dict, s_wt = parse_stirrups(elem.reinforcement.stirrups, h, w, d)

            for btype, wt in m_dict.items():
                rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
            for btype, wt in s_dict.items():
                rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
            total_rebar = m_wt + s_wt

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=vol,
            formwork_area=formwork,
            rebar_weights=rebar_dict,
            total_rebar_weight=total_rebar,
        )

    elif isinstance(resolved, ResolvedBeam):
        elem = resolved.element
        w = elem.profile.width
        d = elem.profile.depth
        length = resolved.span_length

        vol = w * d * length
        formwork = (2.0 * d + w) * length

        if elem.reinforcement:
            m_top_dict, m_top_wt = parse_main_bars(elem.reinforcement.main_top, length)
            m_bot_dict, m_bot_wt = parse_main_bars(
                elem.reinforcement.main_bottom, length
            )
            s_dict, s_wt = parse_stirrups(
                elem.reinforcement.stirrups, length, w, d
            )

            for btype, wt in m_top_dict.items():
                rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
            for btype, wt in m_bot_dict.items():
                rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
            for btype, wt in s_dict.items():
                rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
            total_rebar = m_top_wt + m_bot_wt + s_wt

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=vol,
            formwork_area=formwork,
            rebar_weights=rebar_dict,
            total_rebar_weight=total_rebar,
        )

    elif isinstance(resolved, ResolvedWall):
        elem = resolved.element
        t = resolved.thickness
        h = resolved.height
        length = resolved.length

        opening_area = sum(child.width * child.height for child in resolved.children)
        opening_volume = opening_area * t

        vol = (t * h * length) - opening_volume
        formwork = 2.0 * (h * length) - 2.0 * opening_area
        net_one_side = max(0.0, (h * length) - opening_area)

        finishes_qto = None
        if elem.finishes:
            fin_cfg = elem.finishes
            # 1. Plaster area
            if fin_cfg.plaster == "BOTH":
                plaster_area = 2.0 * net_one_side
            elif fin_cfg.plaster in ("INTERIOR", "EXTERIOR"):
                plaster_area = net_one_side
            else:
                plaster_area = 0.0

            # 2. Side finishes (Tiles vs Paint)
            def calc_side_finish(ftype: str) -> Tuple[float, float]:
                """Returns (tile_area, paint_area)."""
                if ftype == "TILES":
                    if fin_cfg.tile_height is not None and h > 0:
                        ratio = min(1.0, max(0.0, fin_cfg.tile_height / h))
                        t_area = net_one_side * ratio
                        p_area = net_one_side - t_area
                        return t_area, p_area
                    return net_one_side, 0.0
                elif ftype == "PAINT":
                    return 0.0, net_one_side
                else:
                    return 0.0, 0.0

            int_tile, int_paint = calc_side_finish(fin_cfg.interior_finish)
            ext_tile, ext_paint = calc_side_finish(fin_cfg.exterior_finish)

            finishes_qto = WallFinishesQTO(
                net_area_one_side=net_one_side,
                plaster_area=plaster_area,
                paint_interior_area=int_paint,
                paint_exterior_area=ext_paint,
                tile_area=int_tile + ext_tile,
            )

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=vol,
            formwork_area=formwork,
            rebar_weights={},
            total_rebar_weight=0.0,
            wall_finishes=finishes_qto,
        )

    elif isinstance(resolved, ResolvedSlab):
        elem = resolved.element
        area = resolved.area
        t = resolved.thickness
        vol = area * t

        # Formwork area: bottom soffit + side edges
        # For PRECAST_PLANK or GROUND_SLAB, soffit formwork is typically 0
        if elem.slab_type in ("PRECAST_PLANK", "GROUND_SLAB"):
            formwork = 0.0
        else:
            formwork = area  # Bottom soffit formwork

        rebar_dict: Dict[str, float] = {}
        total_rebar = 0.0

        if elem.reinforcement:
            # Check for mesh, e.g., wire mesh or RB9 @ 0.20m
            if elem.reinforcement.mesh:
                m_str = elem.reinforcement.mesh
                m_dict, m_wt = parse_stirrups(m_str, area, 1.0, 1.0)
                if m_wt > 0:
                    for btype, wt in m_dict.items():
                        rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
                    total_rebar += m_wt
                else:
                    # Fallback estimate: 2.5 kg/m2 for wire mesh if string contains wire mesh
                    if "wire" in m_str.lower() or "mesh" in m_str.lower():
                        wire_wt = area * 1.50
                        rebar_dict["WIRE_MESH"] = wire_wt
                        total_rebar += wire_wt

            if elem.reinforcement.main_bottom:
                mb_dict, mb_wt = parse_main_bars(elem.reinforcement.main_bottom, math.sqrt(area))
                for btype, wt in mb_dict.items():
                    rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
                total_rebar += mb_wt

            if elem.reinforcement.main_top:
                mt_dict, mt_wt = parse_main_bars(elem.reinforcement.main_top, math.sqrt(area))
                for btype, wt in mt_dict.items():
                    rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
                total_rebar += mt_wt

        slab_finishes_qto = None
        substructure = None

        if getattr(elem, "finishes", None):
            fin = elem.finishes
            tile_a = area if fin.floor_finish == "TILES" else 0.0
            polish_a = area if fin.floor_finish == "POLISHED_CONCRETE" else 0.0
            skirt_l = 0.0
            if fin.skirting:
                if resolved.polygon and len(resolved.polygon) >= 3:
                    pts = resolved.polygon
                    skirt_l = sum(
                        math.sqrt((pts[(i+1)%len(pts)][0] - pts[i][0])**2 + (pts[(i+1)%len(pts)][1] - pts[i][1])**2)
                        for i in range(len(pts))
                    )
                else:
                    skirt_l = 4.0 * math.sqrt(area)
            sand_v = area * fin.sand_thickness if fin.sand_bedding else 0.0
            if fin.sand_bedding or elem.slab_type == "GROUND_SLAB":
                sand_v = max(sand_v, area * 0.10)
                substructure = SubstructureQTO(sand_bedding_volume=sand_v)

            slab_finishes_qto = SlabFinishesQTO(
                floor_finish=fin.floor_finish,
                tile_area=tile_a,
                polished_concrete_area=polish_a,
                skirting_length=skirt_l,
                sand_bedding_volume=sand_v,
            )
        elif elem.slab_type == "GROUND_SLAB":
            substructure = SubstructureQTO(sand_bedding_volume=area * 0.10)

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=vol,
            formwork_area=formwork,
            rebar_weights=rebar_dict,
            total_rebar_weight=total_rebar,
            substructure=substructure,
            slab_finishes=slab_finishes_qto,
        )

    elif isinstance(resolved, ResolvedCovering):
        elem = resolved.element
        cov_qto = CoveringQTO(
            covering_type=resolved.covering_type,
            area=resolved.area,
            length=resolved.perimeter,
            thickness=resolved.thickness,
        )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            covering=cov_qto,
        )

    elif isinstance(resolved, ResolvedStair):
        elem = resolved.element
        vol = resolved.total_concrete_volume
        formwork = resolved.total_formwork_area

        rebar_dict: Dict[str, float] = {}
        total_rebar = 0.0

        if elem.reinforcement:
            # Estimate main rebar along stair slope
            tot_slope = sum(f.slope_length for f in resolved.flights)
            if elem.reinforcement.main:
                m_dict, m_wt = parse_stirrups(elem.reinforcement.main, tot_slope, elem.width, 1.0)
                for btype, wt in m_dict.items():
                    rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
                total_rebar += m_wt

            if elem.reinforcement.temperature:
                t_dict, t_wt = parse_stirrups(elem.reinforcement.temperature, elem.width, tot_slope, 1.0)
                for btype, wt in t_dict.items():
                    rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
                total_rebar += t_wt

        stair_qto = StairQTO(
            total_steps=len(resolved.steps),
            tread_finish_area=resolved.total_tread_finish_area,
            riser_finish_area=resolved.total_riser_finish_area,
            nosing_length=resolved.nosing_length,
            railing_length=resolved.railing.total_length if resolved.railing else 0.0,
            railing_type=resolved.railing.railing_type if resolved.railing else None,
        )

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=vol,
            formwork_area=formwork,
            rebar_weights=rebar_dict,
            total_rebar_weight=total_rebar,
            stair_assembly=stair_qto,
        )

    elif isinstance(resolved, ResolvedCustomElement):
        elem = resolved.element
        vol = 0.0
        formwork = 0.0
        rebar_dict: Dict[str, float] = {}
        total_rebar = 0.0
        substructure = None

        tag_upper = tag.upper()
        if "F2" in tag_upper or "FOOTING" in tag_upper:
            # Footing dimensions (LOD 350 standard: 0.8m width x 1.5m length x 0.8m thickness)
            w, l, d = 0.8, 1.5, 0.8
            vol = w * l * d
            formwork = 2.0 * (w + l) * d
            # Reinforcement mesh: 8-DB16 in Y (1.4m active length), 5-DB16 in X (0.7m active length)
            unit_db16 = get_bar_unit_weight("DB16")
            rebar_wt = (8 * 1.4 + 5 * 0.7) * unit_db16
            rebar_dict["DB16"] = rebar_wt
            total_rebar = rebar_wt
            # Substructure items: Lean concrete (10cm), Sand bedding (5cm), Piles (2 x I-180 @ 12m)
            substructure = SubstructureQTO(
                lean_concrete_volume=w * l * 0.10,
                sand_bedding_volume=w * l * 0.05,
                pile_count=2,
                pile_total_length=2 * 12.0,
                pile_type="I-180",
            )
        else:
            # Try loading trimesh volume if source exists
            source_path = Path(elem.source)
            if source_path.exists():
                try:
                    import trimesh

                    mesh = trimesh.load(str(source_path))
                    if hasattr(mesh, "volume") and mesh.is_watertight:
                        vol = float(mesh.volume)
                except Exception:
                    vol = 0.0

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=None,
            concrete_volume=vol,
            formwork_area=formwork,
            rebar_weights=rebar_dict,
            total_rebar_weight=total_rebar,
            substructure=substructure,
        )

    elif isinstance(resolved, ResolvedRoof):
        elem = resolved.element
        steel_wt = resolved.total_steel_weight
        has_insul = bool(elem.covering and elem.covering.insulation)
        roof_qto = RoofQTO(
            footprint_area=resolved.total_footprint_area,
            sloped_area=resolved.total_sloped_area,
            ridge_cap_length=resolved.total_ridge_length,
            hip_cap_length=resolved.total_hip_length,
            eaves_length=resolved.total_eaves_length,
            structural_steel_weight=steel_wt,
            insulation_area=resolved.total_sloped_area if has_insul else 0.0,
        )

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            roof=roof_qto,
        )

    elif isinstance(resolved, ResolvedTerminal):
        elem = resolved.element
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type=getattr(elem, "terminal_type", getattr(elem, "equipment_type", getattr(elem, "board_type", getattr(elem, "switch_type", getattr(elem, "outlet_type", getattr(elem, "fixture_type", "TERMINAL")))))),
                count=1,
            ),
        )

    elif isinstance(resolved, ResolvedPipeSegment):
        elem = resolved.element
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type=resolved.system_type,
                length=resolved.length,
                nominal_diameter=resolved.nominal_diameter,
                fittings_count=resolved.fittings_count,
                count=1,
            ),
        )

    elif isinstance(resolved, ResolvedCableCarrierSegment):
        elem = resolved.element
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type=resolved.system_type,
                length=resolved.length,
                nominal_diameter=resolved.nominal_diameter,
                fittings_count=resolved.fittings_count,
                count=1,
            ),
        )

    elif isinstance(resolved, ResolvedSanitaryTerminal):
        elem = resolved.element
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type="SANITARY",
                fixture_type=resolved.terminal_type,
                count=1,
                dimensions=resolved.dimensions,
            ),
        )

    elif isinstance(resolved, ResolvedDistributionBoard):
        elem = resolved.element
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type="ELECTRICAL",
                fixture_type=resolved.board_type,
                count=1,
                dimensions=resolved.dimensions,
            ),
        )

    elif isinstance(resolved, ResolvedLightFixture):
        elem = resolved.element
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type="ELECTRICAL",
                fixture_type=resolved.fixture_type,
                count=1,
                dimensions=resolved.dimensions,
            ),
        )

    elif isinstance(resolved, ResolvedSwitchingDevice):
        elem = resolved.element
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type="ELECTRICAL",
                fixture_type=resolved.switch_type,
                count=1,
                dimensions=resolved.dimensions,
            ),
        )

    elif isinstance(resolved, ResolvedOutlet):
        elem = resolved.element
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type="ELECTRICAL",
                fixture_type=resolved.outlet_type,
                count=1,
                dimensions=resolved.dimensions,
            ),
        )

    elif isinstance(resolved, ResolvedDuctSegment):
        elem = resolved.element
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type=resolved.system_type,
                length=resolved.length,
                width=resolved.width,
                height=resolved.height,
                fittings_count=resolved.fittings_count,
                count=1,
            ),
        )

    elif isinstance(resolved, ResolvedAirTerminal):
        elem = resolved.element
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type="HVAC",
                fixture_type=resolved.terminal_type,
                count=1,
                dimensions=resolved.dimensions,
                capacity=resolved.flow_rate_cfm,
            ),
        )

    elif isinstance(resolved, ResolvedUnitaryEquipment):
        elem = resolved.element
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type="HVAC",
                fixture_type=resolved.equipment_type,
                count=1,
                dimensions=resolved.dimensions,
                capacity=resolved.cooling_capacity_btu,
            ),
        )

    raise TypeError(f"Unsupported resolved element type: {type(resolved)}")


def calculate_qto(
    target: Union[ProjectManifest, ResolvedManifest, Path, str]
) -> ProjectQTO:
    """Calculate project QTO from a manifest or resolved manifest."""
    if isinstance(target, (str, Path)):
        manifest = load_manifest(target)
        resolved = resolve_manifest(manifest)
    elif isinstance(target, ProjectManifest):
        resolved = resolve_manifest(target)
    elif isinstance(target, ResolvedManifest):
        resolved = target
    else:
        raise TypeError(f"Unsupported target type for calculate_qto: {type(target)}")

    qto_elements: List[ElementQTO] = []
    total_conc_vol = 0.0
    total_formwork = 0.0
    total_rebar_wt = 0.0
    rebar_by_type: Dict[str, float] = {}
    total_lean_vol = 0.0
    total_sand_vol = 0.0
    total_excav_vol = 0.0
    total_piles_count = 0
    total_piles_len = 0.0
    total_nosing_len = 0.0
    total_railing_len = 0.0
    total_wall_masonry = 0.0
    total_wall_plaster = 0.0
    total_wall_paint_int = 0.0
    total_wall_paint_ext = 0.0
    total_wall_tile = 0.0
    total_roof_covering = 0.0
    total_roof_steel = 0.0
    total_roof_ridge = 0.0
    total_roof_hip = 0.0
    total_roof_eaves = 0.0
    total_roof_insul = 0.0
    total_ceil_gypsum = 0.0
    total_ceil_tbar = 0.0
    total_ceil_eaves = 0.0
    total_floor_tile = 0.0
    total_floor_polish = 0.0
    total_skirting = 0.0

    # MEP Totals
    total_cold_water_len = 0.0
    total_soil_len = 0.0
    total_waste_len = 0.0
    total_vent_len = 0.0
    total_drainage_len = 0.0
    total_refrigerant_len = 0.0
    total_condensate_len = 0.0
    total_pipe_fittings = 0
    total_conduit_len = 0.0
    total_conduit_fittings = 0
    total_duct_len = 0.0
    total_duct_fittings = 0
    total_sanitary_terms = 0
    total_dist_boards = 0
    total_lights = 0
    total_switches = 0
    total_outlets = 0
    total_air_terms = 0
    total_unitary_eqs = 0

    # Build material category lookup
    material_categories = {
        m.id: m.category.lower() for m in resolved.manifest.materials
    }

    for elem in resolved.elements:
        eqto = calculate_element_qto(elem)
        qto_elements.append(eqto)

        # Include volume in concrete volume total if element's material category is concrete
        mat_cat = material_categories.get(eqto.material, "") if eqto.material else ""
        if mat_cat == "concrete" or eqto.element_class in ("IfcColumn", "IfcBeam", "IfcSlab", "IfcStair"):
            total_conc_vol += eqto.concrete_volume
        elif "footing" in eqto.element_class.lower() or "f2" in eqto.tag.lower() or "footing" in eqto.tag.lower():
            total_conc_vol += eqto.concrete_volume

        total_formwork += eqto.formwork_area
        total_rebar_wt += eqto.total_rebar_weight

        for btype, wt in eqto.rebar_weights.items():
            rebar_by_type[btype] = rebar_by_type.get(btype, 0.0) + wt

        if eqto.substructure:
            total_lean_vol += eqto.substructure.lean_concrete_volume
            total_sand_vol += eqto.substructure.sand_bedding_volume
            total_excav_vol += eqto.substructure.excavation_volume
            total_piles_count += eqto.substructure.pile_count
            total_piles_len += eqto.substructure.pile_total_length

        if eqto.covering:
            ctype = eqto.covering.covering_type.upper()
            tag_low = eqto.tag.lower()
            mat_low = (eqto.material or "").lower()
            if ctype == "CEILING":
                if any(k in tag_low or k in mat_low for k in ["tbar", "t-bar", "ทีบาร์"]):
                    total_ceil_tbar += eqto.covering.area
                elif any(k in tag_low or k in mat_low for k in ["eaves", "ชายคา", "ระบาย"]):
                    total_ceil_eaves += eqto.covering.area
                else:
                    total_ceil_gypsum += eqto.covering.area
            elif ctype == "FLOORING":
                if any(k in tag_low or k in mat_low for k in ["tile", "กระเบื้อง"]):
                    total_floor_tile += eqto.covering.area
                elif any(k in tag_low or k in mat_low for k in ["polish", "ขัดเรียบ", "ขัดมัน"]):
                    total_floor_polish += eqto.covering.area
                else:
                    total_floor_tile += eqto.covering.area
            elif ctype == "SKIRTING":
                total_skirting += eqto.covering.length or eqto.covering.area

        if eqto.slab_finishes:
            total_floor_tile += eqto.slab_finishes.tile_area
            total_floor_polish += eqto.slab_finishes.polished_concrete_area
            total_skirting += eqto.slab_finishes.skirting_length
            total_sand_vol += eqto.slab_finishes.sand_bedding_volume

        if eqto.stair_assembly:
            total_nosing_len += eqto.stair_assembly.nosing_length
            total_railing_len += eqto.stair_assembly.railing_length

        if eqto.roof:
            total_roof_covering += eqto.roof.sloped_area
            total_roof_steel += eqto.roof.structural_steel_weight
            total_roof_ridge += eqto.roof.ridge_cap_length
            total_roof_hip += eqto.roof.hip_cap_length
            total_roof_eaves += eqto.roof.eaves_length
            total_roof_insul += eqto.roof.insulation_area

        if eqto.element_class == "IfcWall":
            if hasattr(elem, "thickness") and elem.thickness > 0:
                total_wall_masonry += eqto.concrete_volume / elem.thickness
            if eqto.wall_finishes:
                total_wall_plaster += eqto.wall_finishes.plaster_area
                total_wall_paint_int += eqto.wall_finishes.paint_interior_area
                total_wall_paint_ext += eqto.wall_finishes.paint_exterior_area
                total_wall_tile += eqto.wall_finishes.tile_area

        if eqto.mep:
            if eqto.element_class == "IfcPipeSegment":
                st = eqto.mep.system_type
                if st == "COLD_WATER":
                    total_cold_water_len += eqto.mep.length
                elif st == "SOIL":
                    total_soil_len += eqto.mep.length
                elif st == "WASTE":
                    total_waste_len += eqto.mep.length
                elif st == "VENT":
                    total_vent_len += eqto.mep.length
                elif st == "DRAINAGE":
                    total_drainage_len += eqto.mep.length
                elif st == "REFRIGERANT":
                    total_refrigerant_len += eqto.mep.length
                elif st == "CONDENSATE":
                    total_condensate_len += eqto.mep.length
                total_pipe_fittings += eqto.mep.fittings_count
            elif eqto.element_class == "IfcCableCarrierSegment":
                total_conduit_len += eqto.mep.length
                total_conduit_fittings += eqto.mep.fittings_count
            elif eqto.element_class == "IfcDuctSegment":
                total_duct_len += eqto.mep.length
                total_duct_fittings += eqto.mep.fittings_count
            elif eqto.element_class == "IfcSanitaryTerminal":
                total_sanitary_terms += eqto.mep.count
            elif eqto.element_class == "IfcDistributionBoard":
                total_dist_boards += eqto.mep.count
            elif eqto.element_class == "IfcLightFixture":
                total_lights += eqto.mep.count
            elif eqto.element_class == "IfcSwitchingDevice":
                total_switches += eqto.mep.count
            elif eqto.element_class == "IfcOutlet":
                total_outlets += eqto.mep.count
            elif eqto.element_class == "IfcAirTerminal":
                total_air_terms += eqto.mep.count
            elif eqto.element_class == "IfcUnitaryEquipment":
                total_unitary_eqs += eqto.mep.count

    return ProjectQTO(
        elements=qto_elements,
        total_concrete_volume=total_conc_vol,
        total_formwork_area=total_formwork,
        total_rebar_weight=total_rebar_wt,
        total_rebar_by_type=rebar_by_type,
        total_lean_concrete_volume=total_lean_vol,
        total_sand_bedding_volume=total_sand_vol,
        total_excavation_volume=total_excav_vol,
        total_pile_count=total_piles_count,
        total_pile_length=total_piles_len,
        total_nosing_length=total_nosing_len,
        total_railing_length=total_railing_len,
        total_wall_masonry_area=total_wall_masonry,
        total_wall_plaster_area=total_wall_plaster,
        total_wall_paint_interior_area=total_wall_paint_int,
        total_wall_paint_exterior_area=total_wall_paint_ext,
        total_wall_tile_area=total_wall_tile,
        total_roof_covering_area=total_roof_covering,
        total_roof_steel_weight=total_roof_steel,
        total_roof_ridge_length=total_roof_ridge,
        total_roof_hip_length=total_roof_hip,
        total_roof_eaves_length=total_roof_eaves,
        total_roof_insulation_area=total_roof_insul,
        total_ceiling_gypsum_area=total_ceil_gypsum,
        total_ceiling_tbar_area=total_ceil_tbar,
        total_ceiling_eaves_area=total_ceil_eaves,
        total_floor_tile_area=total_floor_tile,
        total_floor_polish_area=total_floor_polish,
        total_skirting_length=total_skirting,
        total_cold_water_pipe_length=total_cold_water_len,
        total_soil_pipe_length=total_soil_len,
        total_waste_pipe_length=total_waste_len,
        total_vent_pipe_length=total_vent_len,
        total_drainage_pipe_length=total_drainage_len,
        total_refrigerant_pipe_length=total_refrigerant_len,
        total_condensate_pipe_length=total_condensate_len,
        total_pipe_fittings_count=total_pipe_fittings,
        total_conduit_length=total_conduit_len,
        total_conduit_fittings_count=total_conduit_fittings,
        total_duct_length=total_duct_len,
        total_duct_fittings_count=total_duct_fittings,
        total_sanitary_terminals_count=total_sanitary_terms,
        total_distribution_boards_count=total_dist_boards,
        total_lighting_fixtures_count=total_lights,
        total_switches_count=total_switches,
        total_outlets_count=total_outlets,
        total_air_terminals_count=total_air_terms,
        total_unitary_equipment_count=total_unitary_eqs,
    )
