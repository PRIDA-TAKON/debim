"""
Quantitative Take-Off (QTO) Engine for debim.
Calculates concrete volume, formwork area, and reinforcement (rebar) schedules/weights.
"""

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from debim.resolver import (
    ResolvedAirTerminal,
    ResolvedAlignment,
    ResolvedBeam,
    ResolvedBearing,
    ResolvedBridge,
    ResolvedBridgePart,
    ResolvedCableCarrierSegment,
    ResolvedColumn,
    ResolvedCovering,
    ResolvedCurtainWall,
    ResolvedCustomElement,
    ResolvedDamper,
    ResolvedDistributionBoard,
    ResolvedDoor,
    ResolvedDuctSegment,
    ResolvedEarthworksElement,
    ResolvedEarthworksCut,
    ResolvedEarthworksFill,
    ResolvedElement,
    ResolvedGeotechnicalStratum,
    ResolvedSoil,
    ResolvedMarinePart,
    ResolvedFlowController,
    ResolvedFooting,
    ResolvedLightFixture,
    ResolvedManifest,
    ResolvedOutlet,
    ResolvedPipeSegment,
    ResolvedPlate,
    ResolvedProxy,
    ResolvedRailing,
    ResolvedRailway,
    ResolvedRailwayPart,
    ResolvedRamp,
    ResolvedRetainingWall,
    ResolvedRevolvedArea,
    ResolvedRoad,
    ResolvedRoof,
    ResolvedSanitaryTerminal,
    ResolvedSlab,
    ResolvedStair,
    ResolvedStairFlight,
    ResolvedSweptDisk,
    ResolvedSwitchingDevice,
    ResolvedTerminal,
    ResolvedTrackElement,
    ResolvedUnitaryEquipment,
    ResolvedWall,
    ResolvedWasteTerminal,
    ResolvedWindow,
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
    stirrups_str: Optional[str], element_length: float, width: float = 0.0, depth: float = 0.0, perimeter: Optional[float] = None
) -> Tuple[Dict[str, float], float]:
    """
    Parse stirrups specification (e.g. 'RB6 @ 0.15m' or 'RB9 @ 0.15m').
    Perimeter = 2 * (width + depth) if perimeter is None else perimeter
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

    p = perimeter if perimeter is not None else 2.0 * (width + depth)
    num_stirrups = int(element_length / spacing) + 1
    unit_weight = get_bar_unit_weight(bar_type)
    weight = num_stirrups * p * unit_weight

    return {bar_type: weight}, weight


def parse_footing_mesh(
    mesh_str: Optional[str], bar_length: float, distribution_length: float
) -> Tuple[Dict[str, float], float]:
    """
    Parse footing rebar mesh spec across footing dimensions (e.g. 'DB12 @ 0.15m' or '4-DB16').
    For '@ spacing' syntax:
        num_bars = int(distribution_length / spacing) + 1
        total_length = num_bars * bar_length
        weight = total_length * unit_weight
    For main bar count syntax (e.g. '4-DB16'):
        weight = count * bar_length * unit_weight
    Returns (dict_by_bar_type, total_weight).
    """
    if not mesh_str:
        return {}, 0.0

    match_spacing = re.search(r"([A-Za-z0-9]+)\s*@\s*([0-9.]+)", mesh_str)
    if match_spacing:
        bar_type = match_spacing.group(1).upper()
        spacing = float(match_spacing.group(2))
        if spacing <= 0:
            return {}, 0.0
        num_bars = int(distribution_length / spacing) + 1
        unit_weight = get_bar_unit_weight(bar_type)
        weight = num_bars * bar_length * unit_weight
        return {bar_type: weight}, weight

    return parse_main_bars(mesh_str, bar_length)


# Standard linear masses (kg/m) for common structural steel profiles (TIS / JIS / ISO)
STEEL_PROFILE_MASSES: Dict[str, float] = {
    # H-Beam (TIS 1227 / JIS G3192)
    "H500X300X11X18": 128.0,
    "H500X200X10X16": 89.6,
    "H450X200X9X14": 76.0,
    "H400X200X8X13": 66.0,
    "H350X175X7X11": 49.6,
    "H300X150X6.5X9": 36.7,
    "H250X125X6X9": 29.6,
    "H200X100X5.5X8": 21.3,
    "H150X75X5X7": 14.0,
    "H175X90X5X8": 18.1,
    "H100X100X6X8": 17.2,
    "H125X125X6.5X9": 23.8,
    "H150X150X7X10": 31.5,
    "H175X175X7.5X11": 40.2,
    "H200X200X8X12": 49.9,
    "H250X250X9X14": 72.4,
    "H300X300X10X15": 94.0,
    "H350X350X12X19": 137.0,
    "H400X400X13X21": 172.0,
    # Channel C (TIS 1227 / JIS G3192)
    "C150X75X9X12.5": 24.0,
    "C150X75X6.5X10": 18.6,
    "C75X40X5X7": 6.92,
    "C100X50X5X7.5": 9.36,
    "C125X65X6X8": 13.4,
    "C180X75X7X10.5": 21.4,
    "C200X80X7.5X11": 24.6,
    "C200X90X8X13.5": 30.3,
    "C250X90X9X13": 34.6,
    "C300X90X9X13": 38.1,
    # Light-Gauge C-Lip Channel (TIS 1228 / JIS G3350)
    "C75X45X15X2.3": 3.25,
    "C100X50X20X3.2": 5.50,
    "C125X50X20X3.2": 6.13,
    "C150X50X20X3.2": 6.76,
    # Angle L (Equal Angle TIS 1227 / JIS G3192)
    "L65X65X5": 4.91,
    "L65X65X6": 5.86,
    "L65X65X8": 7.66,
    "L50X50X4": 3.06,
    "L50X50X5": 3.77,
    "L50X50X6": 4.43,
    "L40X40X3": 1.83,
    "L40X40X4": 2.39,
    "L40X40X5": 2.95,
    "L75X75X6": 6.85,
    "L75X75X9": 9.96,
    "L90X90X7": 9.63,
    "L100X100X7": 10.7,
    "L100X100X10": 14.9,
}


def parse_steel_linear_mass(text: str) -> Optional[float]:
    """
    Parse linear mass (kg/m) from steel section designation.
    Supports:
    1. Explicit weight annotation: e.g. '@128', '@ 89.6 kg/m', '128 kg/m'
    2. Standard lookup table: e.g. 'H-500x300x11x18' -> 128.0 kg/m, 'C-150x75x9x12.5' -> 24.0 kg/m
    3. American single-X designation: e.g. 'W310X60' -> 60.0 kg/m, 'UB203X30' -> 30.0 kg/m
    """
    if not text:
        return None
    raw = text.strip()

    # 1. Explicit @weight or weight kg/m
    m_weight = re.search(r"@\s*([0-9]+(?:\.[0-9]+)?)|([0-9]+(?:\.[0-9]+)?)\s*kg/m", raw, re.IGNORECASE)
    if m_weight:
        val = m_weight.group(1) or m_weight.group(2)
        try:
            return float(val)
        except ValueError:
            pass

    # 2. Lookup standard profile (normalize: map '[' to 'C', uppercase, strip -, spaces)
    normalized = re.sub(r"[\s\-\[\],]", "", raw.upper().replace("[", "C"))
    multiplier = 1.0
    if normalized.startswith("2C"):
        multiplier = 2.0
        normalized_lookup = normalized[1:]
    else:
        normalized_lookup = normalized

    for prof, mass in STEEL_PROFILE_MASSES.items():
        if prof in normalized_lookup:
            return mass * multiplier

    # 3. American single-X designation (e.g., 'W310X60' -> 60.0)
    # Ensure there is only 1 'X' so multi-dimensional specs (e.g. 500x300x11x18) don't match erroneously
    if raw.upper().count("X") == 1:
        match = re.search(r"[A-Za-z0-9]+\s*[Xx]\s*([0-9]+(?:\.[0-9]+)?)$", raw)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass
    return None


def is_steel_element(
    elem_class: str,
    tag: str,
    material_id: Optional[str],
    material_category: Optional[str],
    material_name: Optional[str],
    profile_shape: Optional[str] = None,
) -> bool:
    """Check if element is structural steel/metal based on category, material, section tag, or profile shape."""
    if material_category in ("concrete", "masonry", "timber", "wood"):
        return False

    if material_category in ("steel", "metal"):
        return True

    if profile_shape and str(profile_shape).upper() in (
        "ISHAPE", "I", "H",
        "LSHAPE", "L",
        "USHAPE", "U", "CSHAPE", "C",
        "TSHAPE", "T",
        "RHS", "RECTANGLE_HOLLOW", "BOX_HOLLOW",
        "CHS", "CIRCLE_HOLLOW", "PIPE_HOLLOW",
    ):
        return True

    combined = f"{tag} {material_id or ''} {material_name or ''}".upper()
    keywords = [
        "STEEL", "METAL", "SS400", "SM490", "WIDE-FLANGE", "WIDE_FLANGE",
        "H-BEAM", "I-BEAM", "STRUCTURAL STEEL"
    ]
    if any(k in combined for k in keywords):
        return True

    # Search for standard steel profile designations like W310X60, H200, UB200, UC200, 2L50x5, C-150, L-65, [-150
    if re.search(r"\b(W|H|2L|UB|UC)\d", combined) or re.search(r"\b(C|L)\s*[-xX]\s*\d+", combined) or "[-" in combined:
        return True

    return False


def is_timber_element(
    elem_class: str,
    tag: str,
    material_id: Optional[str],
    material_category: Optional[str],
    material_name: Optional[str],
) -> bool:
    """Check if element is timber/wood based on category, material, or section tag."""
    if material_category in ("timber", "wood"):
        return True

    combined = f"{tag} {material_id or ''} {material_name or ''}".upper()
    keywords = ["TIMBER", "WOOD", "LUMBER", "PLYWOOD", "GLULAM", "TEAK", "OAK", "PINE"]
    if any(k in combined for k in keywords):
        return True

    return False


class SubstructureQTO(BaseModel):
    lean_concrete_volume: float = 0.0  # m³
    sand_bedding_volume: float = 0.0   # m³
    excavation_volume: float = 0.0     # m³
    pile_count: int = 0                # count
    pile_total_length: float = 0.0     # m
    pile_chipping_count: int = 0       # count of pile heads chipped/trimmed
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
    inner_helical_length: float = 0.0  # m
    outer_helical_length: float = 0.0  # m
    steel_weight: float = 0.0          # kg
    stringers_steel_weight: float = 0.0
    treads_steel_weight: float = 0.0
    base_plates_steel_weight: float = 0.0


class WallLayerQTO(BaseModel):
    name: Optional[str] = None
    material: str
    thickness: float = 0.0              # m
    area: float = 0.0                   # m²
    volume: float = 0.0                 # m³
    function: Optional[str] = "structure"
    unit_cost_ref: Optional[str] = None


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
    purlin_length: float = 0.0           # Purlin/batten linear meters (m)
    rafter_length: float = 0.0           # Rafter/truss linear meters (m)
    purlin_weight: float = 0.0           # Steel purlin weight (kg)
    rafter_weight: float = 0.0           # Steel rafter/truss weight (kg)
    structural_steel_weight: float = 0.0 # SS400 structural steel weight (kg)
    timber_volume: float = 0.0           # Timber framing volume (m³)
    insulation_area: float = 0.0         # Under-tile insulation area (m²)


class CurtainWallQTO(BaseModel):
    facade_area: float = 0.0             # Gross facade area (m2)
    net_glass_area: float = 0.0          # Net glass panel area (m2)
    mullion_length: float = 0.0          # Linear meters of mullions / transoms (m)
    mullion_weight: float = 0.0          # Frame / mullion steel/aluminum weight (kg)
    glass_panels_count: int = 0          # Number of glass panel infills


class PlateQTO(BaseModel):
    area: float = 0.0                    # Plate surface area (m2)
    thickness: float = 0.0               # Thickness (m)
    volume: float = 0.0                  # Volume (m3)
    weight: float = 0.0                  # Weight (kg)


class EarthworksQTO(BaseModel):
    type: str = "CUT"                    # CUT or FILL
    volume: float = 0.0                  # Baseline volume (m3)
    compacted_volume: float = 0.0        # Compacted volume for fill (m3)
    footprint_area: float = 0.0          # Bottom footprint area for cut (m2)
    surface_area: float = 0.0            # Top surface area for fill (m2)
    depth: float = 0.0                   # Average depth/height (m)
    compaction_ratio: float = 0.95
    gabion_stone_fill_volume: float = 0.0  # Gabion rock stone fill volume (m3)
    wire_mesh_cage_area: float = 0.0       # Wire mesh cage surface area (m2)
    geotextile_area: float = 0.0           # Geotextile filter fabric area (m2)


class RetainingWallQTO(BaseModel):
    length: float = 0.0                  # Wall length (m)
    concrete_volume: float = 0.0         # Concrete volume (m3)
    formwork_area: float = 0.0           # Formwork area (m2)
    stem_height: float = 0.0             # Stem height (m)
    footing_width: float = 0.0           # Footing base width (m)


class AlignmentQTO(BaseModel):
    total_length: float = 0.0            # Total alignment curve length (m)
    start_chainage: float = 0.0          # Stationing start (m)
    end_chainage: float = 0.0            # Stationing end (m)


class RoadQTO(BaseModel):
    corridor_length: float = 0.0         # Corridor length (m)
    road_width: float = 0.0              # Roadway width (m)
    surface_area: float = 0.0            # Pavement surface area (m2)
    asphalt_volume: float = 0.0          # Asphalt wearing course volume (m3)
    base_volume: float = 0.0             # Aggregate base course volume (m3)
    subbase_volume: float = 0.0          # Compacted subbase volume (m3)
    lanes_count: int = 2


class BridgeQTO(BaseModel):
    span_length: float = 0.0             # Total span length (m)
    deck_width: float = 0.0              # Bridge deck width (m)
    deck_concrete_volume: float = 0.0    # Deck concrete volume (m3)
    piers_concrete_volume: float = 0.0   # Piers concrete volume (m3)
    total_concrete_volume: float = 0.0   # Total bridge concrete volume (m3)
    formwork_area: float = 0.0           # Bridge deck and pier formwork area (m2)
    pier_count: int = 2


class MarineQTO(BaseModel):
    length: float = 0.0                  # Berth/Wharf length (m)
    width: float = 0.0                   # Berth/Wharf width (m)
    deck_concrete_volume: float = 0.0    # Deck slab concrete volume (m3)
    formwork_area: float = 0.0           # Deck formwork area (m2)
    pile_count: int = 0                  # Number of foundation piles
    pile_total_length: float = 0.0       # Total pile linear meters (m)
    depth: float = 0.0                   # Water depth / berth depth (m)


class RailwayQTO(BaseModel):
    track_length: float = 0.0            # Track corridor length (m)
    total_rail_length: float = 0.0       # Total parallel steel rails length (m)
    total_rail_weight_kg: float = 0.0    # Steel rails weight (kg)
    sleepers_count: int = 0              # Number of sleepers / ties
    ballast_volume: float = 0.0          # Ballast prism subgrade volume (m3)
    turnout_count: int = 0               # Turnouts / switches / derailers count


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
    power_watts: Optional[float] = None
    voltage: Optional[float] = None
    phases: Optional[Union[int, str]] = None
    main_breaker_rating_amperes: Optional[float] = None
    predefined_type: Optional[str] = None


class ElementQTO(BaseModel):
    tag: str
    element_class: str
    material: Optional[str] = None
    length: float = 0.0
    concrete_volume: float = 0.0  # m³
    formwork_area: float = 0.0  # m²
    rebar_weights: Dict[str, float] = Field(default_factory=dict)  # kg by bar type
    total_rebar_weight: float = 0.0  # kg
    structural_steel_weight: float = 0.0
    painting_area: float = 0.0
    weld_touchup_area: float = 0.0
    timber_volume: float = 0.0
    substructure: Optional[SubstructureQTO] = None
    stair_assembly: Optional[StairQTO] = None
    wall_finishes: Optional[WallFinishesQTO] = None
    wall_layers: Optional[List[WallLayerQTO]] = None
    roof: Optional[RoofQTO] = None
    curtain_wall: Optional[CurtainWallQTO] = None
    plate: Optional[PlateQTO] = None
    covering: Optional[CoveringQTO] = None
    slab_finishes: Optional[SlabFinishesQTO] = None
    earthworks: Optional[EarthworksQTO] = None
    retaining_wall: Optional[RetainingWallQTO] = None
    alignment: Optional[AlignmentQTO] = None
    road: Optional[RoadQTO] = None
    bridge: Optional[BridgeQTO] = None
    marine: Optional[MarineQTO] = None
    railway: Optional[RailwayQTO] = None
    mep: Optional[MepQTO] = None


class ProjectQTO(BaseModel):
    elements: List[ElementQTO] = Field(default_factory=list)
    total_concrete_volume: float = 0.0
    total_formwork_area: float = 0.0
    total_rebar_weight: float = 0.0
    total_rebar_by_type: Dict[str, float] = Field(default_factory=dict)
    total_structural_steel_weight: float = 0.0
    total_painting_area: float = 0.0
    total_weld_touchup_area: float = 0.0
    total_timber_volume: float = 0.0
    total_excavation_volume: float = 0.0
    total_lean_concrete_volume: float = 0.0
    total_sand_bedding_volume: float = 0.0
    total_pile_count: int = 0
    total_pile_length: float = 0.0
    total_pile_chipping_count: int = 0
    total_nosing_length: float = 0.0
    total_railing_length: float = 0.0
    total_wall_masonry_area: float = 0.0
    total_wall_plaster_area: float = 0.0
    total_wall_paint_interior_area: float = 0.0
    total_wall_paint_exterior_area: float = 0.0
    total_wall_tile_area: float = 0.0
    total_roof_covering_area: float = 0.0
    total_roof_steel_weight: float = 0.0
    total_roof_purlin_length: float = 0.0
    total_roof_rafter_length: float = 0.0
    total_roof_ridge_length: float = 0.0
    total_roof_hip_length: float = 0.0
    total_roof_eaves_length: float = 0.0
    total_roof_insulation_area: float = 0.0
    # Curtain Wall & Plate Totals
    total_curtain_wall_facade_area: float = 0.0
    total_curtain_wall_mullion_length: float = 0.0
    total_curtain_wall_glass_panels_count: int = 0
    total_plate_area: float = 0.0
    total_plate_weight: float = 0.0
    # Earthworks & Retaining Wall Totals
    total_cut_volume: float = 0.0
    total_fill_volume: float = 0.0
    total_compacted_fill_volume: float = 0.0
    total_gabion_stone_fill_volume: float = 0.0
    total_wire_mesh_cage_area: float = 0.0
    total_geotextile_area: float = 0.0
    total_retaining_wall_concrete_volume: float = 0.0
    total_retaining_wall_formwork_area: float = 0.0
    # Civil Infrastructure Totals (IFC4.3)
    total_alignment_length: float = 0.0
    total_road_surface_area: float = 0.0
    total_road_asphalt_volume: float = 0.0
    total_road_base_volume: float = 0.0
    total_road_subbase_volume: float = 0.0
    total_bridge_concrete_volume: float = 0.0
    total_bridge_formwork_area: float = 0.0
    total_railway_track_length: float = 0.0
    total_railway_rail_length: float = 0.0
    total_railway_rail_weight_kg: float = 0.0
    total_railway_sleepers_count: int = 0
    total_railway_ballast_volume: float = 0.0
    total_railway_turnouts_count: int = 0
    # Ceilings & Floor Finishes Totals
    total_ceiling_gypsum_area: float = 0.0
    total_ceiling_tbar_area: float = 0.0
    total_ceiling_eaves_area: float = 0.0
    total_floor_tile_area: float = 0.0
    total_floor_polish_area: float = 0.0
    total_skirting_length: float = 0.0
    # Openings Totals
    total_doors_count: int = 0
    total_windows_count: int = 0
    total_openings_area: float = 0.0
    # Topology & Network Graph Totals
    total_ports_count: int = 0
    total_connected_ports_count: int = 0
    total_dead_end_ports_count: int = 0
    total_network_connections_count: int = 0
    total_connected_path_length: float = 0.0
    # Universal Proxies Totals
    total_proxies_count: int = 0
    total_proxies_volume: float = 0.0
    total_proxies_footprint_area: float = 0.0
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
    total_waste_terminals_count: int = 0
    total_distribution_boards_count: int = 0
    total_lighting_fixtures_count: int = 0
    total_switches_count: int = 0
    total_outlets_count: int = 0
    total_air_terminals_count: int = 0
    total_dampers_count: int = 0
    total_flow_controllers_count: int = 0
    total_unitary_equipment_count: int = 0


    def get_element(self, tag: str) -> Optional[ElementQTO]:
        for elem in self.elements:
            if elem.tag == tag:
                return elem
        return None


def compute_profile_geometry(profile: Any) -> Tuple[float, float, float, float]:
    """
    Compute (cross_section_area, surface_perimeter, bounding_width, bounding_depth)
    for any supported profile (Box, Circular, Ellipse, I, L, U, T, RHS, CHS).
    """
    shape = getattr(profile, "shape", "BOX")

    if shape == "CIRCULAR":
        r = profile.radius
        d = profile.diameter
        area = math.pi * (r ** 2)
        perimeter = math.pi * d
        return area, perimeter, d, d

    elif shape == "ELLIPSE":
        a = profile.semi_major_axis
        b = profile.semi_minor_axis
        area = math.pi * a * b
        perimeter = math.pi * (3.0 * (a + b) - math.sqrt((3.0 * a + b) * (a + 3.0 * b)))
        return area, perimeter, 2.0 * a, 2.0 * b

    elif shape in ("ISHAPE", "I", "H"):
        h = profile.overall_depth
        b = profile.overall_width
        tw = profile.web_thickness
        tf = profile.flange_thickness
        area = 2.0 * b * tf + (h - 2.0 * tf) * tw
        perimeter = 4.0 * b + 2.0 * h - 2.0 * tw
        return area, perimeter, b, h

    elif shape in ("LSHAPE", "L"):
        d = profile.depth
        w = profile.width
        t = profile.thickness
        area = (d + w - t) * t
        perimeter = 2.0 * (d + w)
        return area, perimeter, w, d

    elif shape in ("USHAPE", "U", "CSHAPE", "C"):
        d = profile.depth
        bf = profile.flange_width
        tw = profile.web_thickness
        tf = profile.flange_thickness
        area = 2.0 * bf * tf + (d - 2.0 * tf) * tw
        perimeter = 2.0 * d + 4.0 * bf - 2.0 * tw
        return area, perimeter, bf, d

    elif shape in ("TSHAPE", "T"):
        d = profile.depth
        bf = profile.flange_width
        tw = profile.web_thickness
        tf = profile.flange_thickness
        area = bf * tf + (d - tf) * tw
        perimeter = 2.0 * bf + 2.0 * d
        return area, perimeter, bf, d

    elif shape in ("RHS", "RECTANGLE_HOLLOW", "BOX_HOLLOW"):
        w = profile.width
        d = profile.depth
        t = profile.wall_thickness
        area = w * d - max(0.0, w - 2.0 * t) * max(0.0, d - 2.0 * t)
        perimeter = 2.0 * (w + d)
        return area, perimeter, w, d

    elif shape in ("CHS", "CIRCLE_HOLLOW", "PIPE_HOLLOW"):
        r = profile.radius
        d = profile.diameter
        t = profile.wall_thickness
        area = math.pi * (r ** 2 - max(0.0, r - t) ** 2)
        perimeter = math.pi * d
        return area, perimeter, d, d

    elif shape in ("ARBITRARY", "ARBITRARY_CLOSED", "POLYGON", "ARBITRARY_WITH_VOIDS"):
        pts = getattr(profile, "outer_curve", None) or getattr(profile, "points", None) or []
        if not pts or len(pts) < 3:
            return 0.0, 0.0, getattr(profile, "width", 0.0), getattr(profile, "depth", 0.0)

        def _poly_area(p_list):
            n = len(p_list)
            if n < 3:
                return 0.0
            a = 0.0
            for i in range(n):
                j = (i + 1) % n
                a += p_list[i][0] * p_list[j][1] - p_list[j][0] * p_list[i][1]
            return abs(a) / 2.0

        def _poly_perimeter(p_list):
            n = len(p_list)
            if n < 2:
                return 0.0
            perim = 0.0
            for i in range(n):
                j = (i + 1) % n
                dx = p_list[j][0] - p_list[i][0]
                dy = p_list[j][1] - p_list[i][1]
                perim += math.hypot(dx, dy)
            return perim

        outer_area = _poly_area(pts)
        outer_perimeter = _poly_perimeter(pts)

        voids = getattr(profile, "inner_curves", None) or getattr(profile, "voids", None) or []
        voids_area = 0.0
        voids_perimeter = 0.0
        for v in voids:
            if v and len(v) >= 3:
                voids_area += _poly_area(v)
                voids_perimeter += _poly_perimeter(v)

        net_area = max(0.0, outer_area - voids_area)
        total_perimeter = outer_perimeter + voids_perimeter
        w = profile.width
        d = profile.depth
        return net_area, total_perimeter, w, d

    else:  # Default BOX
        w = profile.width
        d = profile.depth
        area = w * d
        perimeter = 2.0 * (w + d)
        return area, perimeter, w, d


def calculate_element_qto(
    resolved: ResolvedElement,
    manifest: Optional[ProjectManifest] = None,
) -> ElementQTO:
    """Calculate QTO for a resolved element."""
    tag = resolved.tag
    rebar_dict: Dict[str, float] = {}
    total_rebar = 0.0

    # Look up material details from manifest if provided
    mat_cat = None
    mat_name = None
    if manifest and hasattr(resolved, "element") and getattr(resolved.element, "material", None):
        mat_id = resolved.element.material
        for m in manifest.materials:
            if m.id == mat_id:
                mat_cat = m.category.lower() if m.category else None
                mat_name = m.name
                break

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
            # mesh_x bars run along X axis (length = w), distributed along Y axis (distribution length = d)
            mx_dict, mx_wt = parse_footing_mesh(elem.reinforcement.mesh_x, bar_length=w, distribution_length=d)
            # mesh_y bars run along Y axis (length = d), distributed along X axis (distribution length = w)
            my_dict, my_wt = parse_footing_mesh(elem.reinforcement.mesh_y, bar_length=d, distribution_length=w)

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
                pile_chipping_count=pile_cnt,
                pile_type=pile_type_str,
            )

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=getattr(elem, "material", None),
            concrete_volume=vol,
            formwork_area=formwork,
            rebar_weights=rebar_dict,
            total_rebar_weight=total_rebar,
            substructure=substructure,
        )

    elif isinstance(resolved, ResolvedColumn):
        elem = resolved.element
        profile = elem.profile
        h = resolved.height

        area, perimeter, w, depth_val = compute_profile_geometry(profile)
        vol = area * h
        formwork = perimeter * h

        is_steel = is_steel_element(elem.class_, tag, elem.material, mat_cat, mat_name, profile_shape=profile.shape)
        is_timber = is_timber_element(elem.class_, tag, elem.material, mat_cat, mat_name)

        if is_steel:
            linear_mass = (
                getattr(profile, "linear_mass", None)
                or parse_steel_linear_mass(getattr(profile, "section", None) or "")
                or parse_steel_linear_mass(tag)
                or parse_steel_linear_mass(mat_name or "")
                or parse_steel_linear_mass(elem.material or "")
            )
            if linear_mass is not None:
                steel_wt = linear_mass * h
            else:
                steel_wt = area * 7850.0 * h

            paint_area = perimeter * h
            weld_area = paint_area * 0.10

            return ElementQTO(
                tag=tag,
                element_class=elem.class_,
                material=elem.material,
                length=h,
                concrete_volume=0.0,
                formwork_area=0.0,
                rebar_weights={},
                total_rebar_weight=0.0,
                structural_steel_weight=steel_wt,
                painting_area=paint_area,
                weld_touchup_area=weld_area,
            )

        elif is_timber:
            timber_vol = vol
            paint_area = perimeter * h

            return ElementQTO(
                tag=tag,
                element_class=elem.class_,
                material=elem.material,
                length=h,
                concrete_volume=0.0,
                formwork_area=0.0,
                rebar_weights={},
                total_rebar_weight=0.0,
                timber_volume=timber_vol,
                painting_area=paint_area,
            )

        else:
            if elem.reinforcement:
                m_dict, m_wt = parse_main_bars(elem.reinforcement.main, h)
                s_dict, s_wt = parse_stirrups(elem.reinforcement.stirrups, h, w, depth_val, perimeter=perimeter)

                for btype, wt in m_dict.items():
                    rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
                for btype, wt in s_dict.items():
                    rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
                total_rebar = m_wt + s_wt

            return ElementQTO(
                tag=tag,
                element_class=elem.class_,
                material=elem.material,
                length=h,
                concrete_volume=vol,
                formwork_area=formwork,
                rebar_weights=rebar_dict,
                total_rebar_weight=total_rebar,
            )

    elif isinstance(resolved, ResolvedBeam):
        elem = resolved.element
        profile = elem.profile
        length = resolved.span_length

        area, perimeter, w, depth_val = compute_profile_geometry(profile)
        vol = area * length
        if profile.shape in ("CIRCULAR", "ELLIPSE"):
            formwork = perimeter * length
        else:
            formwork = (2.0 * depth_val + w) * length

        is_steel = is_steel_element(elem.class_, tag, elem.material, mat_cat, mat_name, profile_shape=profile.shape)
        is_timber = is_timber_element(elem.class_, tag, elem.material, mat_cat, mat_name)

        if is_steel:
            linear_mass = (
                getattr(profile, "linear_mass", None)
                or parse_steel_linear_mass(getattr(profile, "section", None) or "")
                or parse_steel_linear_mass(tag)
                or parse_steel_linear_mass(mat_name or "")
                or parse_steel_linear_mass(elem.material or "")
            )
            if linear_mass is not None:
                steel_wt = linear_mass * length
            else:
                steel_wt = area * 7850.0 * length

            paint_area = perimeter * length
            weld_area = paint_area * 0.10

            return ElementQTO(
                tag=tag,
                element_class=elem.class_,
                material=elem.material,
                length=length,
                concrete_volume=0.0,
                formwork_area=0.0,
                rebar_weights={},
                total_rebar_weight=0.0,
                structural_steel_weight=steel_wt,
                painting_area=paint_area,
                weld_touchup_area=weld_area,
            )

        elif is_timber:
            timber_vol = vol
            paint_area = perimeter * length

            return ElementQTO(
                tag=tag,
                element_class=elem.class_,
                material=elem.material,
                length=length,
                concrete_volume=0.0,
                formwork_area=0.0,
                rebar_weights={},
                total_rebar_weight=0.0,
                timber_volume=timber_vol,
                painting_area=paint_area,
            )

        else:
            if elem.reinforcement:
                m_top_dict, m_top_wt = parse_main_bars(elem.reinforcement.main_top, length)
                m_bot_dict, m_bot_wt = parse_main_bars(
                    elem.reinforcement.main_bottom, length
                )
                s_dict, s_wt = parse_stirrups(
                    elem.reinforcement.stirrups, length, w, depth_val, perimeter=perimeter
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
                length=length,
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

        wall_layer_qtos = None
        if elem.layers:
            wall_layer_qtos = []
            for lyr in elem.layers:
                l_vol = net_one_side * lyr.thickness
                wall_layer_qtos.append(
                    WallLayerQTO(
                        name=lyr.name,
                        material=lyr.material,
                        thickness=lyr.thickness,
                        area=net_one_side,
                        volume=l_vol,
                        function=lyr.function,
                        unit_cost_ref=lyr.unit_cost_ref,
                    )
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
            wall_layers=wall_layer_qtos,
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
            material=getattr(elem, "material", None),
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

        steel_paint_area = 0.0
        if resolved.total_steel_weight > 0:
            st_d = elem.stringer.depth if elem.stringer else 1.40
            stringers_surface = (resolved.inner_helical_length + resolved.outer_helical_length) * st_d * 2.0
            treads_surface = resolved.total_tread_finish_area * 2.0
            steel_paint_area = stringers_surface + treads_surface

        stair_qto = StairQTO(
            total_steps=len(resolved.steps),
            tread_finish_area=resolved.total_tread_finish_area,
            riser_finish_area=resolved.total_riser_finish_area,
            nosing_length=resolved.nosing_length,
            railing_length=resolved.railing.total_length if resolved.railing else 0.0,
            railing_type=resolved.railing.railing_type if resolved.railing else None,
            inner_helical_length=resolved.inner_helical_length,
            outer_helical_length=resolved.outer_helical_length,
            steel_weight=resolved.total_steel_weight,
            stringers_steel_weight=resolved.stringers_steel_weight,
            treads_steel_weight=resolved.treads_steel_weight,
            base_plates_steel_weight=resolved.base_plates_steel_weight,
        )

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=getattr(elem, "material", None),
            concrete_volume=vol,
            formwork_area=formwork,
            rebar_weights=rebar_dict,
            total_rebar_weight=total_rebar,
            structural_steel_weight=resolved.total_steel_weight,
            painting_area=steel_paint_area,
            stair_assembly=stair_qto,
        )

    elif isinstance(resolved, ResolvedStairFlight):
        elem = resolved.element or IfcStairFlight(
            tag=resolved.tag,
            material="MAT_CONC",
            flight_width=resolved.width,
            waist_thickness=resolved.waist_thickness,
            riser_height=resolved.riser,
            tread_length=resolved.tread,
            placement=None,  # Not accessed directly for qto
        )
        vol = (resolved.slope_length * resolved.width * resolved.waist_thickness) + (
            resolved.n_risers * 0.5 * resolved.tread * resolved.riser * resolved.width
        )
        formwork = (resolved.slope_length * resolved.width) + (
            resolved.n_risers * resolved.riser * resolved.width
        ) + (resolved.slope_length * resolved.waist_thickness * 2.0)

        tread_finish = resolved.n_risers * resolved.width * resolved.tread
        riser_finish = resolved.n_risers * resolved.width * resolved.riser
        nosing_len = resolved.n_risers * resolved.width if (elem and elem.finishes and elem.finishes.nosing) else 0.0

        stair_qto = StairQTO(
            total_steps=resolved.n_risers,
            tread_finish_area=tread_finish,
            riser_finish_area=riser_finish,
            nosing_length=nosing_len,
        )

        return ElementQTO(
            tag=tag,
            element_class="IfcStairFlight",
            material=elem.material if elem else None,
            length=resolved.slope_length,
            concrete_volume=vol,
            formwork_area=formwork,
            stair_assembly=stair_qto,
        )

    elif isinstance(resolved, ResolvedRamp):
        elem = resolved.element
        vol = resolved.concrete_volume
        formwork = resolved.formwork_area

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            length=resolved.slope_length,
            concrete_volume=vol,
            formwork_area=formwork,
        )

    elif isinstance(resolved, ResolvedRailing):
        elem = resolved.element
        linear_m = resolved.total_length

        # Estimate steel/handrail weight based on profile or standard rate (~8.5 kg/m)
        steel_wt = 0.0
        if elem.handrail_profile:
            area, perimeter, w, d = compute_profile_geometry(elem.handrail_profile)
            steel_wt = area * 7850.0 * linear_m
        else:
            steel_wt = linear_m * 8.50

        paint_area = linear_m * math.pi * 0.05 * 2.0

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            length=linear_m,
            structural_steel_weight=steel_wt,
            painting_area=paint_area,
        )

    elif isinstance(resolved, ResolvedCustomElement):
        elem = resolved.element
        vol = 0.0
        formwork = 0.0
        rebar_dict: Dict[str, float] = {}
        total_rebar = 0.0
        substructure = None

        if resolved.resolved_solid:
            s = resolved.resolved_solid
            if isinstance(s, ResolvedSweptDisk):
                r = s.radius
                r_in = s.inner_radius or 0.0
                vol = math.pi * (r**2 - r_in**2) * s.length
                formwork = 2.0 * math.pi * (r + r_in) * s.length
            elif isinstance(s, ResolvedRevolvedArea):
                angle_ratio = s.revolution_angle / 360.0
                vol = s.profile_area * (2.0 * math.pi * s.distance_to_axis) * angle_ratio
                formwork = s.profile_perimeter * (2.0 * math.pi * s.distance_to_axis) * angle_ratio
        else:
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
                    pile_chipping_count=2,
                    pile_type="I-180",
                )
            else:
                # Try loading trimesh volume if source exists
                source_path = Path(elem.source) if elem.source else None
                if source_path and source_path.exists():
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
            material=getattr(elem, "material", None),
            concrete_volume=vol,
            formwork_area=formwork,
            rebar_weights=rebar_dict,
            total_rebar_weight=total_rebar,
            substructure=substructure,
        )

    elif isinstance(resolved, ResolvedRoof):
        elem = resolved.element
        has_insul = bool(elem.covering and elem.covering.insulation)

        is_timber = (
            (elem.framing and "TIMBER" in (elem.framing.truss_type or "").upper())
            or is_timber_element(
                elem.class_,
                tag,
                elem.framing.material if elem.framing else None,
                mat_cat,
                mat_name,
            )
        )

        purlin_len = 0.0
        rafter_len = 0.0
        purlin_wt = 0.0
        rafter_wt = 0.0

        for member in resolved.framing_members:
            m_len = member.length
            m_type = member.member_type
            if m_type == "PURLIN":
                purlin_len += m_len
                if not is_timber:
                    mass = parse_steel_linear_mass(member.profile or "") or parse_steel_linear_mass(member.tag) or 3.25
                    purlin_wt += m_len * mass
            else:
                rafter_len += m_len
                if not is_timber:
                    mass = parse_steel_linear_mass(member.profile or "") or parse_steel_linear_mass(member.tag) or 6.76
                    rafter_wt += m_len * mass

        if is_timber:
            purlin_timber_vol = purlin_len * 0.001444
            rafter_timber_vol = rafter_len * 0.005
            timber_vol = purlin_timber_vol + rafter_timber_vol
            steel_wt = 0.0
        else:
            timber_vol = 0.0
            steel_wt = resolved.total_steel_weight if resolved.total_steel_weight > 0 else (purlin_wt + rafter_wt)

        roof_qto = RoofQTO(
            footprint_area=resolved.total_footprint_area,
            sloped_area=resolved.total_sloped_area,
            ridge_cap_length=resolved.total_ridge_length,
            hip_cap_length=resolved.total_hip_length,
            eaves_length=resolved.total_eaves_length,
            purlin_length=purlin_len,
            rafter_length=rafter_len,
            purlin_weight=purlin_wt,
            rafter_weight=rafter_wt,
            structural_steel_weight=steel_wt,
            timber_volume=timber_vol,
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
            structural_steel_weight=steel_wt,
            timber_volume=timber_vol,
            roof=roof_qto,
        )

    elif isinstance(resolved, ResolvedCurtainWall):
        elem = resolved.element
        mw = elem.mullion_width
        md = elem.mullion_depth
        m_cross_area = mw * md
        mullion_vol = resolved.mullion_length * m_cross_area
        # Estimate aluminum/steel mullion weight (2700 kg/m3 for aluminum)
        mullion_wt = mullion_vol * 2700.0

        cw_qto = CurtainWallQTO(
            facade_area=resolved.gross_facade_area,
            net_glass_area=resolved.net_glass_area,
            mullion_length=resolved.mullion_length,
            mullion_weight=mullion_wt,
            glass_panels_count=resolved.glass_panels_count,
        )

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            structural_steel_weight=mullion_wt,
            curtain_wall=cw_qto,
        )

    elif isinstance(resolved, ResolvedPlate):
        elem = resolved.element
        pl_qto = PlateQTO(
            area=resolved.area,
            thickness=resolved.thickness,
            volume=resolved.volume,
            weight=resolved.weight,
        )

        is_steel = is_steel_element(
            elem.class_, tag, elem.material, mat_cat, mat_name
        ) or elem.predefined_type in ("FLANGE_PLATE", "BASE_PLATE")

        steel_wt = resolved.weight if is_steel else 0.0

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            structural_steel_weight=steel_wt,
            plate=pl_qto,
        )

    elif isinstance(resolved, ResolvedEarthworksElement):
        elem = resolved.element
        ew_qto = EarthworksQTO(
            type="FILL" if resolved.predefined_type in ("GABION", "CRIB_WALL", "REINFORCED_SOIL", "BERM", "TERRACE") else ("CUT" if "CUT" in str(resolved.predefined_type).upper() else "FILL"),
            volume=resolved.volume,
            surface_area=resolved.surface_area,
            depth=resolved.depth,
            gabion_stone_fill_volume=resolved.gabion_stone_fill_volume,
            wire_mesh_cage_area=resolved.wire_mesh_cage_area,
            geotextile_area=resolved.geotextile_area,
        )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            earthworks=ew_qto,
        )

    elif isinstance(resolved, ResolvedEarthworksCut):
        elem = resolved.element
        ew_qto = EarthworksQTO(
            type="CUT",
            volume=resolved.cut_volume,
            footprint_area=resolved.footprint_area,
            depth=resolved.depth,
        )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            earthworks=ew_qto,
        )

    elif isinstance(resolved, ResolvedGeotechnicalStratum):
        elem = resolved.element
        ew_qto = EarthworksQTO(
            type="FILL" if resolved.predefined_type in ("SOLID", "SOIL", "ROCK") else "CUT",
            volume=resolved.volume,
            surface_area=resolved.area,
            depth=resolved.thickness,
        )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            earthworks=ew_qto,
        )

    elif isinstance(resolved, ResolvedSoil):
        elem = resolved.element
        ew_qto = EarthworksQTO(
            type="FILL",
            volume=resolved.volume,
            surface_area=resolved.area,
            depth=resolved.thickness,
        )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            earthworks=ew_qto,
        )

    elif isinstance(resolved, ResolvedEarthworksFill):
        elem = resolved.element
        ew_qto = EarthworksQTO(
            type="FILL",
            volume=resolved.fill_volume,
            compacted_volume=resolved.compacted_volume,
            surface_area=resolved.surface_area,
            depth=resolved.depth,
            compaction_ratio=resolved.compaction_ratio,
        )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            earthworks=ew_qto,
        )

    elif isinstance(resolved, ResolvedRetainingWall):
        elem = resolved.element
        vol = resolved.concrete_volume
        formwork = resolved.formwork_area

        rebar_dict: Dict[str, float] = {}
        total_rebar = 0.0

        if elem.reinforcement:
            if elem.reinforcement.stem_main:
                m_dict, m_wt = parse_stirrups(elem.reinforcement.stem_main, resolved.length, resolved.stem_thickness, resolved.stem_height)
                for btype, wt in m_dict.items():
                    rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
                total_rebar += m_wt

            if elem.reinforcement.stem_distribution:
                d_dict, d_wt = parse_stirrups(elem.reinforcement.stem_distribution, resolved.stem_height, resolved.length, resolved.stem_thickness)
                for btype, wt in d_dict.items():
                    rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
                total_rebar += d_wt

            if elem.reinforcement.footing_mesh:
                f_dict, f_wt = parse_footing_mesh(elem.reinforcement.footing_mesh, bar_length=resolved.footing_base_width, distribution_length=resolved.length)
                for btype, wt in f_dict.items():
                    rebar_dict[btype] = rebar_dict.get(btype, 0.0) + wt
                total_rebar += f_wt

        rw_qto = RetainingWallQTO(
            length=resolved.length,
            concrete_volume=vol,
            formwork_area=formwork,
            stem_height=resolved.stem_height,
            footing_width=resolved.footing_base_width,
        )

        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            length=resolved.length,
            concrete_volume=vol,
            formwork_area=formwork,
            rebar_weights=rebar_dict,
            total_rebar_weight=total_rebar,
            retaining_wall=rw_qto,
        )

    elif isinstance(resolved, ResolvedAlignment):
        elem = resolved.element
        align_qto = AlignmentQTO(
            total_length=resolved.total_length,
            start_chainage=resolved.start_chainage,
            end_chainage=resolved.end_chainage,
        )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            length=resolved.total_length,
            alignment=align_qto,
        )

    elif isinstance(resolved, ResolvedRoad):
        elem = resolved.element
        road_qto = RoadQTO(
            corridor_length=resolved.corridor_length,
            road_width=resolved.road_width,
            surface_area=resolved.surface_area,
            asphalt_volume=resolved.asphalt_volume,
            base_volume=resolved.base_volume,
            subbase_volume=resolved.subbase_volume,
            lanes_count=resolved.lanes_count,
        )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            length=resolved.corridor_length,
            road=road_qto,
        )

    elif isinstance(resolved, ResolvedBridge):
        elem = resolved.element
        vol = resolved.total_concrete_volume
        formwork = resolved.formwork_area

        bridge_qto = BridgeQTO(
            span_length=resolved.span_length,
            deck_width=resolved.deck_width,
            deck_concrete_volume=resolved.deck_concrete_volume,
            piers_concrete_volume=resolved.piers_concrete_volume,
            total_concrete_volume=vol,
            formwork_area=formwork,
            pier_count=resolved.pier_count,
        )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            length=resolved.span_length,
            concrete_volume=vol,
            formwork_area=formwork,
            bridge=bridge_qto,
        )

    elif isinstance(resolved, ResolvedMarinePart):
        elem = resolved.element
        vol = resolved.concrete_volume
        formwork = resolved.formwork_area
        pile_cnt = resolved.pile_count
        pile_len = resolved.pile_total_length

        marine_qto = MarineQTO(
            length=resolved.length,
            width=resolved.width,
            deck_concrete_volume=vol,
            formwork_area=formwork,
            pile_count=pile_cnt,
            pile_total_length=pile_len,
            depth=resolved.depth,
        )
        sub_qto = None
        if pile_cnt > 0:
            sub_qto = SubstructureQTO(
                pile_count=pile_cnt,
                pile_total_length=pile_len,
                pile_chipping_count=pile_cnt,
            )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            length=resolved.length,
            concrete_volume=vol,
            formwork_area=formwork,
            marine=marine_qto,
            substructure=sub_qto,
        )

    elif isinstance(resolved, ResolvedRailway):
        elem = resolved.element
        rw_qto = RailwayQTO(
            track_length=resolved.total_length,
        )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            length=resolved.total_length,
            railway=rw_qto,
        )

    elif isinstance(resolved, ResolvedRailwayPart):
        elem = resolved.element
        rw_qto = RailwayQTO(
            track_length=resolved.total_length,
        )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            length=resolved.total_length,
            railway=rw_qto,
        )

    elif isinstance(resolved, ResolvedTrackElement):
        elem = resolved.element
        is_turnout = resolved.predefined_type.upper() in ("TURNOUT", "SWITCH", "DERAILER")
        rw_qto = RailwayQTO(
            track_length=resolved.track_length,
            total_rail_length=resolved.total_rail_length,
            total_rail_weight_kg=resolved.total_rail_weight_kg,
            sleepers_count=resolved.sleepers_count,
            ballast_volume=resolved.ballast_volume,
            turnout_count=1 if is_turnout else 0,
        )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            length=resolved.track_length,
            structural_steel_weight=resolved.total_rail_weight_kg,
            railway=rw_qto,
        )

    elif isinstance(resolved, ResolvedBridgePart):
        elem = resolved.element
        vol = resolved.concrete_volume
        formwork = resolved.formwork_area

        bridge_qto = BridgeQTO(
            span_length=resolved.span_length,
            deck_width=resolved.width,
            deck_concrete_volume=vol,
            total_concrete_volume=vol,
            formwork_area=formwork,
        )
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            length=resolved.span_length,
            concrete_volume=vol,
            formwork_area=formwork,
            bridge=bridge_qto,
        )

    elif isinstance(resolved, ResolvedBearing):
        elem = resolved.element
        vol = resolved.width * resolved.depth * resolved.height
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=elem.material,
            mep=MepQTO(
                system_type="BEARING",
                fixture_type=resolved.predefined_type,
                count=1,
                width=resolved.width,
                height=resolved.height,
            ),
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

    elif isinstance(resolved, ResolvedWasteTerminal):
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
                system_type="DRAINAGE",
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
                voltage=resolved.voltage,
                phases=resolved.phases,
                main_breaker_rating_amperes=resolved.main_breaker_rating_amperes,
                predefined_type=resolved.predefined_type,
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
                power_watts=resolved.power_watts or resolved.wattage,
                predefined_type=resolved.predefined_type,
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
                predefined_type=resolved.predefined_type,
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
                capacity=resolved.flow_rate_cfm or resolved.air_flow_rate_m3h,
                predefined_type=resolved.predefined_type,
            ),
        )

    elif isinstance(resolved, ResolvedDamper):
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
                fixture_type=resolved.damper_type,
                count=1,
                dimensions=resolved.dimensions,
                width=resolved.duct_width or resolved.dimensions[0],
                height=resolved.duct_depth or resolved.dimensions[1],
                nominal_diameter=resolved.duct_diameter or 0.0,
                predefined_type=resolved.predefined_type,
            ),
        )

    elif isinstance(resolved, ResolvedFlowController):
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
                fixture_type=resolved.controller_type,
                count=1,
                dimensions=resolved.dimensions,
                capacity=resolved.air_flow_rate_m3h,
                width=resolved.duct_width or resolved.dimensions[0],
                height=resolved.duct_depth or resolved.dimensions[1],
                nominal_diameter=resolved.duct_diameter or 0.0,
                predefined_type=resolved.predefined_type,
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

    elif isinstance(resolved, ResolvedDoor):
        elem = resolved.element
        mat = getattr(elem, "material", None)
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=mat,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type="DOOR",
                fixture_type=elem.class_,
                count=1,
                width=resolved.width,
                height=resolved.height,
            ),
        )

    elif isinstance(resolved, ResolvedWindow):
        elem = resolved.element
        mat = getattr(elem, "material", None)
        return ElementQTO(
            tag=tag,
            element_class=elem.class_,
            material=mat,
            concrete_volume=0.0,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type="WINDOW",
                fixture_type=elem.class_,
                count=1,
                width=resolved.width,
                height=resolved.height,
            ),
        )

    elif isinstance(resolved, ResolvedProxy):
        elem = resolved.element
        vol = resolved.bounding_box["volume"]
        w, d, h = resolved.dimensions
        return ElementQTO(
            tag=tag,
            element_class=resolved.ifc_class,
            material=elem.material or resolved.ifc_class,
            concrete_volume=vol,
            formwork_area=0.0,
            rebar_weights={},
            total_rebar_weight=0.0,
            mep=MepQTO(
                system_type=resolved.ifc_class,
                fixture_type=resolved.ifc_class,
                count=1,
                width=w,
                height=h,
                predefined_type=resolved.predefined_type,
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
    total_struct_steel_wt = 0.0
    total_paint_area = 0.0
    total_weld_touchup = 0.0
    total_timber_vol = 0.0
    total_lean_vol = 0.0
    total_sand_vol = 0.0
    total_excav_vol = 0.0
    total_piles_count = 0
    total_piles_len = 0.0
    total_piles_chip = 0
    total_nosing_len = 0.0
    total_railing_len = 0.0
    total_wall_masonry = 0.0
    total_wall_plaster = 0.0
    total_wall_paint_int = 0.0
    total_wall_paint_ext = 0.0
    total_wall_tile = 0.0
    total_roof_covering = 0.0
    total_roof_steel = 0.0
    total_roof_purlin_len = 0.0
    total_roof_rafter_len = 0.0
    total_roof_ridge = 0.0
    total_roof_hip = 0.0
    total_roof_eaves = 0.0
    total_roof_insul = 0.0

    # Curtain Wall & Plate Totals
    total_cw_facade_area = 0.0
    total_cw_mullion_len = 0.0
    total_cw_glass_panels = 0
    total_plate_area_val = 0.0
    total_plate_weight_val = 0.0

    # Earthworks & Retaining Wall Totals
    total_cut_vol = 0.0
    total_fill_vol = 0.0
    total_compacted_fill_vol = 0.0
    total_gabion_stone_vol = 0.0
    total_wire_mesh_area = 0.0
    total_geotextile_area_val = 0.0
    total_rw_conc_vol = 0.0
    total_rw_formwork = 0.0

    # Civil Infrastructure Totals (IFC4.3)
    total_alignment_len = 0.0
    total_road_surf_area = 0.0
    total_road_asphalt_vol = 0.0
    total_road_base_vol = 0.0
    total_road_subbase_vol = 0.0
    total_bridge_conc_vol = 0.0
    total_bridge_formwork = 0.0
    total_railway_track_length = 0.0
    total_railway_rail_length = 0.0
    total_railway_rail_weight_kg = 0.0
    total_railway_sleepers_count = 0
    total_railway_ballast_volume = 0.0
    total_railway_turnouts_count = 0

    total_ceil_gypsum = 0.0
    total_ceil_tbar = 0.0
    total_ceil_eaves = 0.0
    total_floor_tile = 0.0
    total_floor_polish = 0.0
    total_skirting = 0.0

    # Openings Totals
    total_doors = 0
    total_windows = 0
    total_openings_area = 0.0

    # Topology Graph Analytics
    total_ports = 0
    total_connected_ports = 0
    total_dead_ends = 0
    total_net_conns = 0
    total_path_len = 0.0

    if getattr(resolved, "topology_graph", None):
        tg = resolved.topology_graph
        total_ports = len(tg.ports)
        total_dead_ends = len(tg.dead_ends)
        total_connected_ports = total_ports - total_dead_ends
        total_net_conns = len(tg.connected_edges)

        for p1_id, p2_id in tg.connected_edges:
            if p1_id in tg.ports and p2_id in tg.ports:
                pos1 = tg.ports[p1_id].world_position
                pos2 = tg.ports[p2_id].world_position
                total_path_len += math.dist(pos1, pos2)

    # Proxies Totals
    total_proxies_cnt = 0
    total_proxies_vol = 0.0
    total_proxies_footprint = 0.0

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
    total_waste_terms = 0
    total_dist_boards = 0
    total_lights = 0
    total_switches = 0
    total_outlets = 0
    total_air_terms = 0
    total_dampers = 0
    total_flow_controllers = 0
    total_unitary_eqs = 0

    # Build material category lookup
    material_categories = {
        m.id: m.category.lower() for m in resolved.manifest.materials
    }

    manifest_obj = resolved.manifest if hasattr(resolved, "manifest") else None

    all_elements: List[ResolvedElement] = list(resolved.elements)
    existing_tags = {e.tag for e in all_elements}
    for door in resolved.doors:
        if door.tag not in existing_tags:
            all_elements.append(door)
            existing_tags.add(door.tag)
    for window in resolved.windows:
        if window.tag not in existing_tags:
            all_elements.append(window)
            existing_tags.add(window.tag)

    for elem in all_elements:
        eqto = calculate_element_qto(elem, manifest=manifest_obj)
        qto_elements.append(eqto)

        # Include volume in concrete volume total if element's material category is concrete
        mat_cat = material_categories.get(eqto.material, "") if eqto.material else ""
        if mat_cat == "concrete" or (eqto.element_class in ("IfcColumn", "IfcBeam", "IfcSlab", "IfcStair") and mat_cat not in ("steel", "metal", "timber", "wood")):
            total_conc_vol += eqto.concrete_volume
        elif "footing" in eqto.element_class.lower() or "f2" in eqto.tag.lower() or "footing" in eqto.tag.lower():
            total_conc_vol += eqto.concrete_volume

        total_formwork += eqto.formwork_area
        total_rebar_wt += eqto.total_rebar_weight
        total_struct_steel_wt += eqto.structural_steel_weight
        total_paint_area += eqto.painting_area
        total_weld_touchup += eqto.weld_touchup_area
        total_timber_vol += eqto.timber_volume

        for btype, wt in eqto.rebar_weights.items():
            rebar_by_type[btype] = rebar_by_type.get(btype, 0.0) + wt

        if eqto.substructure:
            total_lean_vol += eqto.substructure.lean_concrete_volume
            total_sand_vol += eqto.substructure.sand_bedding_volume
            total_excav_vol += eqto.substructure.excavation_volume
            total_piles_count += eqto.substructure.pile_count
            total_piles_len += eqto.substructure.pile_total_length
            total_piles_chip += eqto.substructure.pile_chipping_count

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

        if eqto.element_class == "IfcRailing":
            total_railing_len += eqto.length

        if eqto.roof:
            total_roof_covering += eqto.roof.sloped_area
            total_roof_steel += eqto.roof.structural_steel_weight
            total_roof_purlin_len += eqto.roof.purlin_length
            total_roof_rafter_len += eqto.roof.rafter_length
            total_roof_ridge += eqto.roof.ridge_cap_length
            total_roof_hip += eqto.roof.hip_cap_length
            total_roof_eaves += eqto.roof.eaves_length
            total_roof_insul += eqto.roof.insulation_area

        if eqto.curtain_wall:
            total_cw_facade_area += eqto.curtain_wall.facade_area
            total_cw_mullion_len += eqto.curtain_wall.mullion_length
            total_cw_glass_panels += eqto.curtain_wall.glass_panels_count

        if eqto.plate:
            total_plate_area_val += eqto.plate.area
            total_plate_weight_val += eqto.plate.weight

        if eqto.earthworks:
            if eqto.earthworks.type == "CUT":
                total_cut_vol += eqto.earthworks.volume
            elif eqto.earthworks.type == "FILL":
                total_fill_vol += eqto.earthworks.volume
                total_compacted_fill_vol += eqto.earthworks.compacted_volume
            total_gabion_stone_vol += eqto.earthworks.gabion_stone_fill_volume
            total_wire_mesh_area += eqto.earthworks.wire_mesh_cage_area
            total_geotextile_area_val += eqto.earthworks.geotextile_area

        if eqto.retaining_wall:
            total_rw_conc_vol += eqto.retaining_wall.concrete_volume
            total_rw_formwork += eqto.retaining_wall.formwork_area

        if eqto.alignment:
            total_alignment_len += eqto.alignment.total_length

        if eqto.road:
            total_road_surf_area += eqto.road.surface_area
            total_road_asphalt_vol += eqto.road.asphalt_volume
            total_road_base_vol += eqto.road.base_volume
            total_road_subbase_vol += eqto.road.subbase_volume

        if eqto.bridge:
            total_bridge_conc_vol += eqto.bridge.total_concrete_volume
            total_bridge_formwork += eqto.bridge.formwork_area

        if eqto.railway:
            total_railway_track_length += eqto.railway.track_length
            total_railway_rail_length += eqto.railway.total_rail_length
            total_railway_rail_weight_kg += eqto.railway.total_rail_weight_kg
            total_railway_sleepers_count += eqto.railway.sleepers_count
            total_railway_ballast_volume += eqto.railway.ballast_volume
            total_railway_turnouts_count += eqto.railway.turnout_count

        if eqto.element_class == "IfcWall":
            if hasattr(elem, "thickness") and elem.thickness > 0:
                total_wall_masonry += eqto.concrete_volume / elem.thickness
            if eqto.wall_finishes:
                total_wall_plaster += eqto.wall_finishes.plaster_area
                total_wall_paint_int += eqto.wall_finishes.paint_interior_area
                total_wall_paint_ext += eqto.wall_finishes.paint_exterior_area
                total_wall_tile += eqto.wall_finishes.tile_area

        if isinstance(elem, ResolvedDoor) or eqto.element_class == "IfcDoor":
            total_doors += 1
            total_openings_area += elem.width * elem.height
        elif isinstance(elem, ResolvedWindow) or eqto.element_class == "IfcWindow":
            total_windows += 1
            total_openings_area += elem.width * elem.height
        elif isinstance(elem, ResolvedProxy):
            total_proxies_cnt += 1
            total_proxies_vol += eqto.concrete_volume
            total_proxies_footprint += elem.bounding_box["footprint_area"]

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
            elif eqto.element_class == "IfcWasteTerminal":
                total_waste_terms += eqto.mep.count
            elif eqto.element_class in ("IfcDistributionBoard", "IfcElectricDistributionBoard"):
                total_dist_boards += eqto.mep.count
            elif eqto.element_class == "IfcLightFixture":
                total_lights += eqto.mep.count
            elif eqto.element_class == "IfcSwitchingDevice":
                total_switches += eqto.mep.count
            elif eqto.element_class == "IfcOutlet":
                total_outlets += eqto.mep.count
            elif eqto.element_class == "IfcAirTerminal":
                total_air_terms += eqto.mep.count
            elif eqto.element_class == "IfcDamper":
                total_dampers += eqto.mep.count
            elif eqto.element_class == "IfcFlowController":
                total_flow_controllers += eqto.mep.count
            elif eqto.element_class == "IfcUnitaryEquipment":
                total_unitary_eqs += eqto.mep.count

    return ProjectQTO(
        elements=qto_elements,
        total_concrete_volume=total_conc_vol,
        total_formwork_area=total_formwork,
        total_rebar_weight=total_rebar_wt,
        total_rebar_by_type=rebar_by_type,
        total_structural_steel_weight=total_struct_steel_wt,
        total_painting_area=total_paint_area,
        total_weld_touchup_area=total_weld_touchup,
        total_timber_volume=total_timber_vol,
        total_lean_concrete_volume=total_lean_vol,
        total_sand_bedding_volume=total_sand_vol,
        total_excavation_volume=total_excav_vol,
        total_pile_count=total_piles_count,
        total_pile_length=total_piles_len,
        total_pile_chipping_count=total_piles_chip,
        total_nosing_length=total_nosing_len,
        total_railing_length=total_railing_len,
        total_wall_masonry_area=total_wall_masonry,
        total_wall_plaster_area=total_wall_plaster,
        total_wall_paint_interior_area=total_wall_paint_int,
        total_wall_paint_exterior_area=total_wall_paint_ext,
        total_wall_tile_area=total_wall_tile,
        total_roof_covering_area=total_roof_covering,
        total_roof_steel_weight=total_roof_steel,
        total_roof_purlin_length=total_roof_purlin_len,
        total_roof_rafter_length=total_roof_rafter_len,
        total_roof_ridge_length=total_roof_ridge,
        total_roof_hip_length=total_roof_hip,
        total_roof_eaves_length=total_roof_eaves,
        total_roof_insulation_area=total_roof_insul,
        total_curtain_wall_facade_area=total_cw_facade_area,
        total_curtain_wall_mullion_length=total_cw_mullion_len,
        total_curtain_wall_glass_panels_count=total_cw_glass_panels,
        total_plate_area=total_plate_area_val,
        total_plate_weight=total_plate_weight_val,
        total_cut_volume=total_cut_vol,
        total_fill_volume=total_fill_vol,
        total_compacted_fill_volume=total_compacted_fill_vol,
        total_gabion_stone_fill_volume=total_gabion_stone_vol,
        total_wire_mesh_cage_area=total_wire_mesh_area,
        total_geotextile_area=total_geotextile_area_val,
        total_retaining_wall_concrete_volume=total_rw_conc_vol,
        total_retaining_wall_formwork_area=total_rw_formwork,
        total_alignment_length=total_alignment_len,
        total_road_surface_area=total_road_surf_area,
        total_road_asphalt_volume=total_road_asphalt_vol,
        total_road_base_volume=total_road_base_vol,
        total_road_subbase_volume=total_road_subbase_vol,
        total_bridge_concrete_volume=total_bridge_conc_vol,
        total_bridge_formwork_area=total_bridge_formwork,
        total_railway_track_length=total_railway_track_length,
        total_railway_rail_length=total_railway_rail_length,
        total_railway_rail_weight_kg=total_railway_rail_weight_kg,
        total_railway_sleepers_count=total_railway_sleepers_count,
        total_railway_ballast_volume=total_railway_ballast_volume,
        total_railway_turnouts_count=total_railway_turnouts_count,
        total_ceiling_gypsum_area=total_ceil_gypsum,
        total_ceiling_tbar_area=total_ceil_tbar,
        total_ceiling_eaves_area=total_ceil_eaves,
        total_floor_tile_area=total_floor_tile,
        total_floor_polish_area=total_floor_polish,
        total_skirting_length=total_skirting,
        total_proxies_count=total_proxies_cnt,
        total_proxies_volume=total_proxies_vol,
        total_proxies_footprint_area=total_proxies_footprint,
        total_doors_count=total_doors,
        total_windows_count=total_windows,
        total_openings_area=total_openings_area,
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
        total_waste_terminals_count=total_waste_terms,
        total_distribution_boards_count=total_dist_boards,
        total_lighting_fixtures_count=total_lights,
        total_switches_count=total_switches,
        total_outlets_count=total_outlets,
        total_air_terminals_count=total_air_terms,
        total_dampers_count=total_dampers,
        total_flow_controllers_count=total_flow_controllers,
        total_unitary_equipment_count=total_unitary_eqs,
        total_ports_count=total_ports,
        total_connected_ports_count=total_connected_ports,
        total_dead_end_ports_count=total_dead_ends,
        total_network_connections_count=total_net_conns,
        total_connected_path_length=total_path_len,

    )
