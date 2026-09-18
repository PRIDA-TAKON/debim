"""
Quantitative Take-Off (QTO) Engine for debim.
Calculates concrete volume, formwork area, and reinforcement (rebar) schedules/weights.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedCustomElement,
    ResolvedElement,
    ResolvedFooting,
    ResolvedManifest,
    ResolvedSlab,
    ResolvedStair,
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
    pile_count: int = 0                # count
    pile_total_length: float = 0.0     # m
    pile_type: Optional[str] = None


class StairQTO(BaseModel):
    total_steps: int = 0
    tread_finish_area: float = 0.0     # m²
    riser_finish_area: float = 0.0     # m²
    nosing_length: float = 0.0         # m
    railing_length: float = 0.0        # m
    railing_type: Optional[str] = None


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


class ProjectQTO(BaseModel):
    elements: List[ElementQTO] = Field(default_factory=list)
    total_concrete_volume: float = 0.0
    total_formwork_area: float = 0.0
    total_rebar_weight: float = 0.0
    total_rebar_by_type: Dict[str, float] = Field(default_factory=dict)
    total_lean_concrete_volume: float = 0.0
    total_sand_bedding_volume: float = 0.0
    total_pile_count: int = 0
    total_pile_length: float = 0.0
    total_nosing_length: float = 0.0
    total_railing_length: float = 0.0


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

        substructure = None
        if elem.piles and elem.piles.count > 0:
            pile_cnt = elem.piles.count
            total_len = pile_cnt * elem.piles.length
            pile_shape = elem.piles.profile.shape if elem.piles.profile else "HEXAGONAL"
            pile_dim = elem.piles.profile.dimension if elem.piles.profile else 0.15
            substructure = SubstructureQTO(
                lean_concrete_volume=w * d * 0.10,
                sand_bedding_volume=w * d * 0.05,
                pile_count=pile_cnt,
                pile_total_length=total_len,
                pile_type=f"{pile_shape}-{pile_dim}",
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

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=vol,
            formwork_area=formwork,
            rebar_weights={},
            total_rebar_weight=0.0,
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

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=vol,
            formwork_area=formwork,
            rebar_weights=rebar_dict,
            total_rebar_weight=total_rebar,
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
    total_piles_count = 0
    total_piles_len = 0.0
    total_nosing_len = 0.0
    total_railing_len = 0.0


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
            total_piles_count += eqto.substructure.pile_count
            total_piles_len += eqto.substructure.pile_total_length

        if eqto.stair_assembly:
            total_nosing_len += eqto.stair_assembly.nosing_length
            total_railing_len += eqto.stair_assembly.railing_length

    return ProjectQTO(
        elements=qto_elements,
        total_concrete_volume=total_conc_vol,
        total_formwork_area=total_formwork,
        total_rebar_weight=total_rebar_wt,
        total_rebar_by_type=rebar_by_type,
        total_lean_concrete_volume=total_lean_vol,
        total_sand_bedding_volume=total_sand_vol,
        total_pile_count=total_piles_count,
        total_pile_length=total_piles_len,
        total_nosing_length=total_nosing_len,
        total_railing_length=total_railing_len,
    )
