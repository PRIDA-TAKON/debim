"""
3D Spatial Coordinate Resolver for debim.
Converts relative grid and storey references into absolute 3D world coordinates
and geometric dimensions.
"""

import math
from typing import Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict

from debim.schema import (
    Dimensions,
    IfcAirTerminal,
    IfcBeam,
    IfcCableCarrierSegment,
    IfcColumn,
    IfcCovering,
    IfcCustomElement,
    IfcDistributionBoard,
    IfcDoor,
    IfcDuctSegment,
    IfcFooting,
    IfcLightFixture,
    IfcOutlet,
    IfcPipeSegment,
    IfcRoof,
    IfcSanitaryTerminal,
    IfcSlab,
    IfcStair,
    IfcSwitchingDevice,
    IfcUnitaryEquipment,
    IfcWall,
    IfcWindow,
    ProjectManifest,
    Storey,
    derive_default_layer,
)

TerminalElement = Union[
    IfcSanitaryTerminal,
    IfcDistributionBoard,
    IfcLightFixture,
    IfcSwitchingDevice,
    IfcOutlet,
    IfcUnitaryEquipment,
    IfcAirTerminal,
]


def _calc_polygon_3d(pts: List[Tuple[float, float, float]]) -> Tuple[float, Tuple[float, float, float]]:
    """Calculates 3D surface area and normal vector for a planar polygon in 3D."""
    n = len(pts)
    if n < 3:
        return 0.0, (0.0, 0.0, 1.0)
    nx = 0.0
    ny = 0.0
    nz = 0.0
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        nx += (p1[1] * p2[2] - p1[2] * p2[1])
        ny += (p1[2] * p2[0] - p1[0] * p2[2])
        nz += (p1[0] * p2[1] - p1[1] * p2[0])
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    area = 0.5 * length
    if length > 1e-9:
        normal = (nx / length, ny / length, nz / length)
    else:
        normal = (0.0, 0.0, 1.0)
    return area, normal


def _generate_orthogonal_waypoints(
    p1: Tuple[float, float, float],
    p2: Tuple[float, float, float],
    strategy: str = "ORTHOGONAL",
) -> List[Tuple[float, float, float]]:
    """
    Generates orthogonal (Manhattan / Right-angle) 3D waypoints between p1 and p2.
    Prevents diagonal cuts across rooms and calculates realistic pipe/conduit lengths.
    """
    x1, y1, z1 = p1
    x2, y2, z2 = p2

    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    dz = abs(z2 - z1)

    # If already aligned along axes or virtually identical
    if (dx < 1e-4 and dy < 1e-4) or (dx < 1e-4 and dz < 1e-4) or (dy < 1e-4 and dz < 1e-4):
        return [p1, p2]

    waypoints: List[Tuple[float, float, float]] = [p1]

    if strategy in ("ORTHOGONAL", "X_THEN_Y"):
        # Route along X first, then Y, then vertical Z
        if dx > 1e-4:
            waypoints.append((x2, y1, z1))
        if dy > 1e-4:
            waypoints.append((x2, y2, z1))
        if dz > 1e-4:
            waypoints.append((x2, y2, z2))
    elif strategy == "Y_THEN_X":
        # Route along Y first, then X, then vertical Z
        if dy > 1e-4:
            waypoints.append((x1, y2, z1))
        if dx > 1e-4:
            waypoints.append((x2, y2, z1))
        if dz > 1e-4:
            waypoints.append((x2, y2, z2))
    else:
        return [p1, p2]

    # Deduplicate consecutive identical waypoints
    cleaned: List[Tuple[float, float, float]] = [waypoints[0]]
    for pt in waypoints[1:]:
        if math.dist(cleaned[-1], pt) > 1e-4:
            cleaned.append(pt)
    return cleaned


class ResolvedColumn(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcColumn
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    height: float
    layer: str = "structure/framing/columns"


class ResolvedBeam(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcBeam
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    span_length: float
    direction_vector: Tuple[float, float]
    rotation_angle: float
    layer: str = "structure/framing/beams"


class ResolvedDoor(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcDoor
    position: Tuple[float, float, float]
    width: float
    height: float
    offset_distance: float
    sill_height: float
    layer: str = "architecture/openings/doors"


class ResolvedWindow(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcWindow
    position: Tuple[float, float, float]
    width: float
    height: float
    offset_distance: float
    sill_height: float
    layer: str = "architecture/openings/windows"


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
    layer: str = "architecture/walls"


class ResolvedCustomElement(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcCustomElement
    position: Tuple[float, float, float]
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    dimensions: Optional[Dimensions] = None
    layer: str = "general/custom"


class ResolvedTerminal(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: TerminalElement
    position: Tuple[float, float, float]
    rotation_angle: float
    hosting_wall: Optional[ResolvedWall] = None
    layer: str = "mep/terminals"


class ResolvedPile(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    position: Tuple[float, float, float]  # Top of pile (under footing cap)
    length: float
    dimension: float
    shape: str = "HEXAGONAL"
    material: Optional[str] = None
    layer: str = "structure/substructure/piles"


class ResolvedFooting(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcFooting
    position: Tuple[float, float, float]
    width: float
    depth: float
    thickness: float
    piles: List[ResolvedPile] = []
    layer: str = "structure/substructure/footings"


class ResolvedSlab(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcSlab
    polygon: List[Tuple[float, float, float]]  # Vertices in 3D (x, y, z)
    thickness: float
    area: float  # Top surface area (m2)
    center: Tuple[float, float, float]  # Centroid (cx, cy, cz)
    layer: str = "structure/slabs"


class ResolvedCovering(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcCovering
    covering_type: str
    polygon: List[Tuple[float, float, float]]  # Vertices in 3D (x, y, z)
    thickness: float
    area: float  # Surface area (m2)
    perimeter: float = 0.0  # Perimeter length (m)
    center: Tuple[float, float, float]  # Centroid (cx, cy, cz)
    layer: str = "architecture/coverings"


class ResolvedStairStep(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    step_index: int
    flight_tag: str
    position: Tuple[float, float, float]  # Center of step box (cx, cy, cz)
    width: float   # Width across flight
    tread: float   # Length along run (ลูกนอน)
    riser: float   # Height (ลูกตั้ง)


class ResolvedStairStringer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    start_point: Tuple[float, float, float]  # Center of start cross-section
    end_point: Tuple[float, float, float]    # Center of end cross-section
    width: float
    depth: float
    length: float
    material: Optional[str] = None
    start_profile_corners: List[Tuple[float, float, float]] = []  # 4 vertices of rectangular cross-section at start
    end_profile_corners: List[Tuple[float, float, float]] = []    # 4 vertices of rectangular cross-section at end


class ResolvedStairRailing(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    posts: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []  # List of vertical posts (base, top)
    rails: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []  # List of sloping/horizontal rails (start, end)
    segments: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []
    total_length: float = 0.0
    height: float = 0.90
    railing_type: str = "STEEL_HANDRAIL"
    layout: str = "SINGLE"



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
    steps: List[ResolvedStairStep] = []


class ResolvedLandingEdgeBeam(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    width: float
    depth: float
    length: float
    concrete_volume: float
    formwork_area: float
    start_profile_corners: List[Tuple[float, float, float]] = []
    end_profile_corners: List[Tuple[float, float, float]] = []


class ResolvedStair(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcStair
    flights: List[ResolvedStairFlight] = []
    steps: List[ResolvedStairStep] = []
    stringers: List[ResolvedStairStringer] = []
    landing_polygon: Optional[List[Tuple[float, float, float]]] = None
    landing_thickness: float = 0.12
    landing_area: float = 0.0
    landing_edge_beams: List[ResolvedLandingEdgeBeam] = []
    railing: Optional[ResolvedStairRailing] = None
    nosing_length: float = 0.0
    total_tread_finish_area: float = 0.0
    total_riser_finish_area: float = 0.0
    total_concrete_volume: float = 0.0
    total_formwork_area: float = 0.0
    layer: str = "architecture/stairs"




class ResolvedRoofPlane(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    polygon: List[Tuple[float, float, float]]  # Vertices in 3D (x, y, z)
    area: float  # Sloped surface area (m2)
    slope_degrees: float
    normal: Tuple[float, float, float]


class ResolvedRoofRidge(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    length: float
    ridge_type: Literal["RIDGE", "HIP", "VALLEY", "EAVE", "VERGE"]


class ResolvedRoofFramingMember(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    member_type: Literal[
        "RIDGE_BEAM",
        "HIP_RAFTER",
        "VALLEY_RAFTER",
        "COMMON_RAFTER",
        "JACK_RAFTER",
        "PURLIN",
        "KING_POST",
        "WALL_PLATE",
        "TIE_BEAM",
    ]
    name_th: str
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    length: float
    color: str
    material: Optional[str] = None
    profile: Optional[str] = None


class ResolvedRoof(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcRoof
    roof_type: str
    pitch: float
    eaves_elevation: float
    ridge_elevation: float
    footprint_polygon: List[Tuple[float, float, float]]  # Eaves boundary at eaves elevation
    planes: List[ResolvedRoofPlane] = []
    ridges: List[ResolvedRoofRidge] = []
    framing_members: List[ResolvedRoofFramingMember] = []
    children: List[ResolvedWallChild] = []

    total_footprint_area: float  # Projected horizontal area including overhang (m2)
    total_sloped_area: float     # Actual sloped roof covering area (m2)
    total_ridge_length: float    # Main ridge cap length (m)
    total_hip_length: float      # Hip ridge cap length (m)
    total_eaves_length: float    # Fascia / gutter perimeter length (m)
    total_steel_weight: float    # Structural steel framing weight (kg)
    layer: str = "architecture/roofs"


# MEP Colors & Defaults
MEP_PIPE_COLORS: Dict[str, str] = {
    "COLD_WATER": "#0284C7",  # Sky Blue (น้ำดี ท่อ PVC ฟ้า / PPR)
    "HOT_WATER": "#EA580C",   # Orange-Red (น้ำร้อน)
    "SOIL": "#78350F",        # Amber Brown (ส้วม/โสโครก ท่อ PVC 4")
    "WASTE": "#475569",       # Slate Grey (น้ำทิ้ง ท่อ PVC 2")
    "VENT": "#65A30D",        # Lime Green (ท่อระบายอากาศ)
    "DRAINAGE": "#7C3AED",    # Purple (ท่อระบายน้ำรอบอาคาร)
    "REFRIGERANT": "#06B6D4", # Cyan / Deep Turquoise (ท่อน้ำยาแอร์)
    "CONDENSATE": "#38BDF8",  # Light Sky Blue (ท่อน้ำทิ้งแอร์)
}

MEP_CONDUIT_COLORS: Dict[str, str] = {
    "POWER": "#F97316",         # Orange (ท่อร้อยสายไฟกำลัง/เต้ารับ)
    "LIGHTING": "#EAB308",      # Amber/Yellow (ระบบแสงสว่าง)
    "MAIN_FEEDER": "#DC2626",   # Red (สายเมนเข้าตู้ MDB)
    "COMMUNICATION": "#06B6D4", # Cyan (LAN / โทรศัพท์)
    "SOLAR": "#84CC16",         # Lime (โซล่าร์เซลล์)
}

MEP_DUCT_COLORS: Dict[str, str] = {
    "SUPPLY_AIR": "#0284C7",    # Blue (ท่อลมจ่าย)
    "RETURN_AIR": "#F59E0B",    # Amber (ท่อลมกลับ)
    "EXHAUST_AIR": "#64748B",   # Slate Grey (ท่อระบายอากาศ/ดูดควัน)
    "FRESH_AIR": "#10B981",     # Emerald Green (ท่อเติมอากาศบริสุทธิ์)
}

DEFAULT_TERMINAL_DIMENSIONS: Dict[str, Tuple[float, float, float]] = {
    "WATER_CLOSET": (0.40, 0.70, 0.75),
    "LAVATORY": (0.50, 0.45, 0.80),
    "SHOWER": (0.20, 0.20, 0.90),
    "KITCHEN_SINK": (0.60, 1.00, 0.85),
    "FLOOR_DRAIN": (0.15, 0.15, 0.05),
    "GREASE_TRAP": (0.40, 0.50, 0.40),
    "SEPTIC_TANK": (1.20, 1.20, 1.50),
    "WATER_TANK": (1.00, 1.00, 1.60),
    "WATER_PUMP": (0.35, 0.35, 0.35),
    "CONSUMER_UNIT": (0.35, 0.12, 0.45),
    "MDB": (0.60, 0.25, 0.80),
    "PANELBOARD": (0.45, 0.15, 0.60),
    "DOWNLIGHT": (0.15, 0.15, 0.05),
    "LED_TUBE": (0.10, 1.20, 0.08),
    "PENDANT": (0.30, 0.30, 0.40),
    "WALL_LAMP": (0.15, 0.15, 0.20),
    "FLOODLIGHT": (0.25, 0.20, 0.25),
    "ONE_WAY": (0.07, 0.04, 0.12),
    "TWO_WAY": (0.07, 0.04, 0.12),
    "DIMMER": (0.07, 0.04, 0.12),
    "DUPLEX_GROUNDED": (0.07, 0.04, 0.12),
    "WATERPROOF": (0.08, 0.06, 0.13),
    "HIGH_POWER": (0.10, 0.06, 0.12),
    # HVAC Terminals & Equipment
    "EXHAUST_FAN_CEILING": (0.30, 0.30, 0.20),
    "EXHAUST_FAN_WALL": (0.30, 0.20, 0.30),
    "KITCHEN_HOOD": (0.90, 0.55, 0.50),
    "SUPPLY_DIFFUSER": (0.60, 0.60, 0.10),
    "RETURN_GRILLE": (0.60, 0.60, 0.05),
    "AC_INDOOR_WALL": (0.85, 0.22, 0.30),
    "AC_INDOOR_CASSETTE": (0.84, 0.84, 0.28),
    "AC_INDOOR_CONCEALED": (0.90, 0.60, 0.30),
    "AC_OUTDOOR_CONDENSER": (0.85, 0.35, 0.65),
}

DEFAULT_TERMINAL_COLORS: Dict[str, str] = {
    "WATER_CLOSET": "#F8FAFC",
    "LAVATORY": "#F1F5F9",
    "SHOWER": "#CBD5E1",
    "KITCHEN_SINK": "#94A3B8",
    "FLOOR_DRAIN": "#64748B",
    "GREASE_TRAP": "#0D9488",  # Teal
    "SEPTIC_TANK": "#1E293B",  # Dark Slate
    "WATER_TANK": "#0284C7",   # Blue
    "WATER_PUMP": "#2563EB",   # Royal Blue
    "CONSUMER_UNIT": "#334155",
    "MDB": "#1E293B",
    "PANELBOARD": "#334155",
    "DOWNLIGHT": "#FEF08A",
    "LED_TUBE": "#FEF9C3",
    "PENDANT": "#FDE047",
    "WALL_LAMP": "#FEF08A",
    "FLOODLIGHT": "#FACC15",
    "ONE_WAY": "#E2E8F0",
    "TWO_WAY": "#E2E8F0",
    "DIMMER": "#E2E8F0",
    "DUPLEX_GROUNDED": "#E2E8F0",
    "WATERPROOF": "#CBD5E1",
    "HIGH_POWER": "#94A3B8",
    # HVAC Terminals & Equipment
    "EXHAUST_FAN_CEILING": "#F1F5F9",
    "EXHAUST_FAN_WALL": "#E2E8F0",
    "KITCHEN_HOOD": "#94A3B8",
    "SUPPLY_DIFFUSER": "#F8FAFC",
    "RETURN_GRILLE": "#E2E8F0",
    "AC_INDOOR_WALL": "#FFFFFF",
    "AC_INDOOR_CASSETTE": "#F8FAFC",
    "AC_INDOOR_CONCEALED": "#64748B",
    "AC_OUTDOOR_CONDENSER": "#CBD5E1",
}


class ResolvedPipeSegment(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcPipeSegment
    system_type: str
    nominal_diameter: float
    length: float
    slope: float
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    waypoints: List[Tuple[float, float, float]]
    color: str
    fittings_count: int = 0
    layer: str = "mep/plumbing/pipes"


class ResolvedCableCarrierSegment(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcCableCarrierSegment
    system_type: str
    nominal_diameter: float
    length: float
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    waypoints: List[Tuple[float, float, float]]
    color: str
    fittings_count: int = 0
    layer: str = "mep/electrical/conduits"


class ResolvedSanitaryTerminal(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcSanitaryTerminal
    terminal_type: str
    position: Tuple[float, float, float]
    rotation: float = 0.0
    rotation_angle: float = 0.0
    dimensions: Tuple[float, float, float]  # width, depth, height
    color: str
    layer: str = "mep/plumbing/fixtures"


class ResolvedDistributionBoard(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcDistributionBoard
    board_type: str
    position: Tuple[float, float, float]
    rotation: float = 0.0
    rotation_angle: float = 0.0
    dimensions: Tuple[float, float, float]
    color: str
    circuits_count: int
    layer: str = "mep/electrical/distribution"


class ResolvedLightFixture(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcLightFixture
    fixture_type: str
    position: Tuple[float, float, float]
    rotation: float = 0.0
    rotation_angle: float = 0.0
    dimensions: Tuple[float, float, float]
    color: str
    wattage: float
    layer: str = "mep/electrical/lighting"


class ResolvedSwitchingDevice(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcSwitchingDevice
    switch_type: str
    position: Tuple[float, float, float]
    rotation: float = 0.0
    rotation_angle: float = 0.0
    dimensions: Tuple[float, float, float]
    color: str
    gangs: int
    layer: str = "mep/electrical/switches"


class ResolvedOutlet(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcOutlet
    outlet_type: str
    position: Tuple[float, float, float]
    rotation: float = 0.0
    rotation_angle: float = 0.0
    dimensions: Tuple[float, float, float]
    color: str
    layer: str = "mep/electrical/outlets"


class ResolvedDuctSegment(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcDuctSegment
    system_type: str
    width: float
    height: float
    length: float
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    waypoints: List[Tuple[float, float, float]]
    color: str
    fittings_count: int = 0
    layer: str = "mep/hvac/ducts"


class ResolvedAirTerminal(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcAirTerminal
    terminal_type: str
    position: Tuple[float, float, float]
    rotation: float = 0.0
    rotation_angle: float = 0.0
    dimensions: Tuple[float, float, float]
    color: str
    flow_rate_cfm: Optional[float] = None
    layer: str = "mep/hvac/terminals"


class ResolvedUnitaryEquipment(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcUnitaryEquipment
    equipment_type: str
    position: Tuple[float, float, float]
    rotation: float = 0.0
    rotation_angle: float = 0.0
    dimensions: Tuple[float, float, float]
    color: str
    cooling_capacity_btu: Optional[float] = None
    layer: str = "mep/hvac/equipment"


ResolvedElement = Union[
    ResolvedColumn,
    ResolvedBeam,
    ResolvedWall,
    ResolvedFooting,
    ResolvedSlab,
    ResolvedCovering,
    ResolvedStair,
    ResolvedRoof,
    ResolvedPipeSegment,
    ResolvedCableCarrierSegment,
    ResolvedDuctSegment,
    ResolvedSanitaryTerminal,
    ResolvedDistributionBoard,
    ResolvedLightFixture,
    ResolvedSwitchingDevice,
    ResolvedOutlet,
    ResolvedAirTerminal,
    ResolvedUnitaryEquipment,
    ResolvedCustomElement,
    ResolvedTerminal,
]


class ResolvedManifest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    manifest: ProjectManifest
    footings: List[ResolvedFooting] = []
    columns: List[ResolvedColumn] = []
    beams: List[ResolvedBeam] = []
    walls: List[ResolvedWall] = []
    slabs: List[ResolvedSlab] = []
    coverings: List[ResolvedCovering] = []
    stairs: List[ResolvedStair] = []
    roofs: List[ResolvedRoof] = []
    doors: List[ResolvedDoor] = []
    windows: List[ResolvedWindow] = []
    pipes: List[ResolvedPipeSegment] = []
    conduits: List[ResolvedCableCarrierSegment] = []
    ducts: List[ResolvedDuctSegment] = []
    sanitary_terminals: List[ResolvedSanitaryTerminal] = []
    distribution_boards: List[ResolvedDistributionBoard] = []
    light_fixtures: List[ResolvedLightFixture] = []
    switches: List[ResolvedSwitchingDevice] = []
    outlets: List[ResolvedOutlet] = []
    air_terminals: List[ResolvedAirTerminal] = []
    unitary_equipments: List[ResolvedUnitaryEquipment] = []
    custom_elements: List[ResolvedCustomElement] = []
    terminals: List[ResolvedTerminal] = []
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
        self.walls_by_tag: Dict[str, ResolvedWall] = {}

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
            layer=derive_default_layer(col),
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
            layer=derive_default_layer(beam),
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
                    layer=derive_default_layer(child),
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
                    layer=derive_default_layer(child),
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
            layer=derive_default_layer(wall),
        )

        return r_wall, resolved_doors, resolved_windows

    def resolve_custom_element(
        self, custom: IfcCustomElement
    ) -> ResolvedCustomElement:
        storey = self.get_storey(custom.placement.storey)
        pos_x, pos_y, pos_z = custom.placement.position
        world_pos = (pos_x, pos_y, storey.elevation + pos_z)
        rot = custom.placement.rotation if custom.placement.rotation is not None else (0.0, 0.0, 0.0)

        return ResolvedCustomElement(
            tag=custom.tag,
            element=custom,
            position=world_pos,
            rotation=rot,
            dimensions=custom.dimensions,
            layer=derive_default_layer(custom),
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
            layer=derive_default_layer(footing),
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
            layer=derive_default_layer(slab),
        )

    def resolve_covering(self, covering: IfcCovering) -> ResolvedCovering:
        storey = self.get_storey(covering.placement.storey)
        z = storey.elevation + covering.placement.offset_z

        poly_3d: List[Tuple[float, float, float]] = []
        pts_2d: List[Tuple[float, float]] = []
        area = 0.0
        perimeter = 0.0

        if covering.placement.boundary:
            for grid_pt in covering.placement.boundary:
                x, y = self.get_grid_xy(grid_pt)
                pts_2d.append((x, y))
                poly_3d.append((x, y, z))

            n = len(pts_2d)
            calc_area = 0.0
            calc_perimeter = 0.0
            if n >= 3:
                for i in range(n):
                    j = (i + 1) % n
                    calc_area += pts_2d[i][0] * pts_2d[j][1]
                    calc_area -= pts_2d[j][0] * pts_2d[i][1]
                    dx = pts_2d[j][0] - pts_2d[i][0]
                    dy = pts_2d[j][1] - pts_2d[i][1]
                    calc_perimeter += math.sqrt(dx * dx + dy * dy)
                calc_area = abs(calc_area) / 2.0
            
            area = covering.placement.area if covering.placement.area is not None else calc_area
            perimeter = covering.placement.length if covering.placement.length is not None else calc_perimeter
        elif covering.placement.area is not None:
            area = covering.placement.area
            perimeter = covering.placement.length or (4.0 * math.sqrt(area) if area > 0 else 0.0)

        if covering.placement.length is not None:
            perimeter = covering.placement.length

        if pts_2d:
            cx = sum(p[0] for p in pts_2d) / len(pts_2d)
            cy = sum(p[1] for p in pts_2d) / len(pts_2d)
        else:
            all_x = list(self.axes_x.values())
            all_y = list(self.axes_y.values())
            cx = (min(all_x) + max(all_x)) / 2.0 if all_x else 0.0
            cy = (min(all_y) + max(all_y)) / 2.0 if all_y else 0.0

        return ResolvedCovering(
            tag=covering.tag,
            element=covering,
            covering_type=covering.covering_type,
            polygon=poly_3d,
            thickness=covering.thickness,
            area=area,
            perimeter=perimeter,
            center=(cx, cy, z),
            layer=derive_default_layer(covering),
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
        all_steps: List[ResolvedStairStep] = []
        stringers: List[ResolvedStairStringer] = []
        railing_segments: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []

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

            actual_riser_1 = rise_1 / n_risers_1
            actual_riser_2 = rise_2 / n_risers_2

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

                # Step boxes generation for Flight 1 (+Y direction)
                f1_steps: List[ResolvedStairStep] = []
                for i in range(n_risers_1):
                    scx = base_x + w / 2.0
                    scy = base_y + i * tread + tread / 2.0
                    scz = z_bottom + i * actual_riser_1 + actual_riser_1 / 2.0
                    step = ResolvedStairStep(
                        step_index=i + 1,
                        flight_tag=f"{stair.tag}-F1",
                        position=(scx, scy, scz),
                        width=w,
                        tread=tread,
                        riser=actual_riser_1,
                    )
                    f1_steps.append(step)
                    all_steps.append(step)

                # Step boxes generation for Flight 2 (-Y direction)
                f2_steps: List[ResolvedStairStep] = []
                for j in range(n_risers_2):
                    scx = (base_x + w) + w / 2.0
                    scy = (base_y + run_1) - j * tread - tread / 2.0
                    scz = z_mid + j * actual_riser_2 + actual_riser_2 / 2.0
                    step = ResolvedStairStep(
                        step_index=n_risers_1 + j + 1,
                        flight_tag=f"{stair.tag}-F2",
                        position=(scx, scy, scz),
                        width=w,
                        tread=tread,
                        riser=actual_riser_2,
                    )
                    f2_steps.append(step)
                    all_steps.append(step)

                # Railing path (Inner side: along inner edge between flights)
                rh = stair.railing.height if stair.railing else 0.90
                # F1 inner handrail: (base_x + w, y, z + rh)
                railing_segments.append((
                    (base_x + w, base_y, z_bottom + rh),
                    (base_x + w, base_y + run_1, z_mid + rh),
                ))
                # Landing handrail across inner void: (base_x + w, base_y + run_1, z_mid + rh)
                railing_segments.append((
                    (base_x + w, base_y + run_1, z_mid + rh),
                    (base_x + w, base_y + run_1, z_mid + rh),
                ))
                # F2 inner handrail:
                railing_segments.append((
                    (base_x + w, base_y + run_1, z_mid + rh),
                    (base_x + w, base_y + run_1 - run_2, z_top + rh),
                ))

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

                f1_steps = []
                for i in range(n_risers_1):
                    scx = base_x + i * tread + tread / 2.0
                    scy = base_y + w / 2.0
                    scz = z_bottom + i * actual_riser_1 + actual_riser_1 / 2.0
                    step = ResolvedStairStep(
                        step_index=i + 1,
                        flight_tag=f"{stair.tag}-F1",
                        position=(scx, scy, scz),
                        width=w,
                        tread=tread,
                        riser=actual_riser_1,
                    )
                    f1_steps.append(step)
                    all_steps.append(step)

                f2_steps = []
                for j in range(n_risers_2):
                    scx = (base_x + run_1) - j * tread - tread / 2.0
                    scy = (base_y + w) + w / 2.0
                    scz = z_mid + j * actual_riser_2 + actual_riser_2 / 2.0
                    step = ResolvedStairStep(
                        step_index=n_risers_1 + j + 1,
                        flight_tag=f"{stair.tag}-F2",
                        position=(scx, scy, scz),
                        width=w,
                        tread=tread,
                        riser=actual_riser_2,
                    )
                    f2_steps.append(step)
                    all_steps.append(step)

                rh = stair.railing.height if stair.railing else 0.90
                railing_segments.append((
                    (base_x, base_y + w, z_bottom + rh),
                    (base_x + run_1, base_y + w, z_mid + rh),
                ))
                railing_segments.append((
                    (base_x + run_1, base_y + w, z_mid + rh),
                    (base_x + run_1 - run_2, base_y + w, z_top + rh),
                ))

            # Stringers (แม่บันได) - Centerline and end-profile corners
            st_mat = (stair.stringer.material if stair.stringer else None) or stair.material
            st_w = stair.stringer.width if stair.stringer else w
            st_d = stair.stringer.depth if stair.stringer else waist_t

            # F1 Stringer: under Flight 1
            if stair.placement.orientation == "+Y":
                s1_start = (base_x + w / 2.0, base_y, z_bottom - st_d / 2.0)
                s1_end = (base_x + w / 2.0, base_y + run_1, z_mid - st_d / 2.0)
                s1_start_corners = [
                    (base_x + (w - st_w) / 2.0, base_y, z_bottom - st_d),
                    (base_x + (w + st_w) / 2.0, base_y, z_bottom - st_d),
                    (base_x + (w + st_w) / 2.0, base_y, z_bottom),
                    (base_x + (w - st_w) / 2.0, base_y, z_bottom),
                ]
                s1_end_corners = [
                    (base_x + (w - st_w) / 2.0, base_y + run_1, z_mid - st_d),
                    (base_x + (w + st_w) / 2.0, base_y + run_1, z_mid - st_d),
                    (base_x + (w + st_w) / 2.0, base_y + run_1, z_mid),
                    (base_x + (w - st_w) / 2.0, base_y + run_1, z_mid),
                ]
                # F2 Stringer: under Flight 2
                s2_start = (base_x + w + w / 2.0, base_y + run_1, z_mid - st_d / 2.0)
                s2_end = (base_x + w + w / 2.0, base_y + run_1 - run_2, z_top - st_d / 2.0)
                s2_start_corners = [
                    (base_x + w + (w - st_w) / 2.0, base_y + run_1, z_mid - st_d),
                    (base_x + w + (w + st_w) / 2.0, base_y + run_1, z_mid - st_d),
                    (base_x + w + (w + st_w) / 2.0, base_y + run_1, z_mid),
                    (base_x + w + (w - st_w) / 2.0, base_y + run_1, z_mid),
                ]
                s2_end_corners = [
                    (base_x + w + (w - st_w) / 2.0, base_y + run_1 - run_2, z_top - st_d),
                    (base_x + w + (w + st_w) / 2.0, base_y + run_1 - run_2, z_top - st_d),
                    (base_x + w + (w + st_w) / 2.0, base_y + run_1 - run_2, z_top),
                    (base_x + w + (w - st_w) / 2.0, base_y + run_1 - run_2, z_top),
                ]
            else:
                s1_start = (base_x, base_y + w / 2.0, z_bottom - st_d / 2.0)
                s1_end = (base_x + run_1, base_y + w / 2.0, z_mid - st_d / 2.0)
                s1_start_corners = [
                    (base_x, base_y + (w - st_w) / 2.0, z_bottom - st_d),
                    (base_x, base_y + (w + st_w) / 2.0, z_bottom - st_d),
                    (base_x, base_y + (w + st_w) / 2.0, z_bottom),
                    (base_x, base_y + (w - st_w) / 2.0, z_bottom),
                ]
                s1_end_corners = [
                    (base_x + run_1, base_y + (w - st_w) / 2.0, z_mid - st_d),
                    (base_x + run_1, base_y + (w + st_w) / 2.0, z_mid - st_d),
                    (base_x + run_1, base_y + (w + st_w) / 2.0, z_mid),
                    (base_x + run_1, base_y + (w - st_w) / 2.0, z_mid),
                ]
                s2_start = (base_x + run_1, base_y + w + w / 2.0, z_mid - st_d / 2.0)
                s2_end = (base_x + run_1 - run_2, base_y + w + w / 2.0, z_top - st_d / 2.0)
                s2_start_corners = [
                    (base_x + run_1, base_y + w + (w - st_w) / 2.0, z_mid - st_d),
                    (base_x + run_1, base_y + w + (w + st_w) / 2.0, z_mid - st_d),
                    (base_x + run_1, base_y + w + (w + st_w) / 2.0, z_mid),
                    (base_x + run_1, base_y + w + (w - st_w) / 2.0, z_mid),
                ]
                s2_end_corners = [
                    (base_x + run_1 - run_2, base_y + w + (w - st_w) / 2.0, z_top - st_d),
                    (base_x + run_1 - run_2, base_y + w + (w + st_w) / 2.0, z_top - st_d),
                    (base_x + run_1 - run_2, base_y + w + (w + st_w) / 2.0, z_top),
                    (base_x + run_1 - run_2, base_y + w + (w - st_w) / 2.0, z_top),
                ]

            stringers.append(ResolvedStairStringer(
                tag=f"{stair.tag}-Stringer-F1",
                start_point=s1_start,
                end_point=s1_end,
                width=st_w,
                depth=st_d,
                length=slope_1,
                material=st_mat,
                start_profile_corners=s1_start_corners,
                end_profile_corners=s1_end_corners,
            ))
            stringers.append(ResolvedStairStringer(
                tag=f"{stair.tag}-Stringer-F2",
                start_point=s2_start,
                end_point=s2_end,
                width=st_w,
                depth=st_d,
                length=slope_2,
                material=st_mat,
                start_profile_corners=s2_start_corners,
                end_profile_corners=s2_end_corners,
            ))

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
                riser=actual_riser_1,
                steps=f1_steps,
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
                riser=actual_riser_2,
                steps=f2_steps,
            )
            flights.extend([f1, f2])

            landing_area = (2.0 * w) * landing_depth
            landing_vol = landing_area * landing_t

            # Landing edge beams calculation (คานขอบชานพัก / เทหนาพิเศษ)
            landing_edge_beams: List[ResolvedLandingEdgeBeam] = []
            if stair.landing and stair.landing.edge_beam and landing_poly:
                eb_cfg = stair.landing.edge_beam
                eb_w = eb_cfg.width
                eb_d = eb_cfg.depth
                # Extra depth below landing slab
                drop_d = max(0.0, eb_d - landing_t)

                # Edges of the landing polygon (4 edges)
                poly_edges = [
                    ("Edge-1", landing_poly[0], landing_poly[1]),
                    ("Edge-2", landing_poly[1], landing_poly[2]),
                    ("Edge-3", landing_poly[2], landing_poly[3]),
                    ("Edge-4", landing_poly[3], landing_poly[0]),
                ]

                # Filter edges based on config: "ALL", "FRONT_REAR", "SIDES"
                active_edges = poly_edges
                if eb_cfg.edges == "FRONT_REAR":
                    active_edges = [poly_edges[0], poly_edges[2]]
                elif eb_cfg.edges == "SIDES":
                    active_edges = [poly_edges[1], poly_edges[3]]

                for e_tag, ep_start, ep_end in active_edges:
                    e_len = math.dist(ep_start, ep_end)
                    if e_len <= 0:
                        continue
                    # Extra concrete for this edge beam drop below landing slab
                    eb_conc_vol = e_len * eb_w * drop_d
                    # Formwork for soffit + 1 or 2 side faces
                    eb_formwork = (e_len * eb_w) + (e_len * drop_d * 2.0)

                    # Centerline of edge beam below landing
                    eb_start = (ep_start[0], ep_start[1], z_mid - landing_t - drop_d / 2.0)
                    eb_end = (ep_end[0], ep_end[1], z_mid - landing_t - drop_d / 2.0)

                    # Cross section rectangle at start and end
                    sdx = ep_end[0] - ep_start[0]
                    sdy = ep_end[1] - ep_start[1]
                    norm_len = math.hypot(sdx, sdy)
                    # Perpendicular unit vector (nx, ny)
                    nx = -sdy / norm_len if norm_len > 0 else 0
                    ny = sdx / norm_len if norm_len > 0 else 0

                    c_start = [
                        (ep_start[0] - nx * eb_w / 2.0, ep_start[1] - ny * eb_w / 2.0, z_mid - landing_t - drop_d),
                        (ep_start[0] + nx * eb_w / 2.0, ep_start[1] + ny * eb_w / 2.0, z_mid - landing_t - drop_d),
                        (ep_start[0] + nx * eb_w / 2.0, ep_start[1] + ny * eb_w / 2.0, z_mid - landing_t),
                        (ep_start[0] - nx * eb_w / 2.0, ep_start[1] - ny * eb_w / 2.0, z_mid - landing_t),
                    ]
                    c_end = [
                        (ep_end[0] - nx * eb_w / 2.0, ep_end[1] - ny * eb_w / 2.0, z_mid - landing_t - drop_d),
                        (ep_end[0] + nx * eb_w / 2.0, ep_end[1] + ny * eb_w / 2.0, z_mid - landing_t - drop_d),
                        (ep_end[0] + nx * eb_w / 2.0, ep_end[1] + ny * eb_w / 2.0, z_mid - landing_t),
                        (ep_end[0] - nx * eb_w / 2.0, ep_end[1] - ny * eb_w / 2.0, z_mid - landing_t),
                    ]

                    landing_edge_beams.append(ResolvedLandingEdgeBeam(
                        tag=f"{stair.tag}-LandingBeam-{e_tag}",
                        start_point=eb_start,
                        end_point=eb_end,
                        width=eb_w,
                        depth=eb_d,
                        length=e_len,
                        concrete_volume=eb_conc_vol,
                        formwork_area=eb_formwork,
                        start_profile_corners=c_start,
                        end_profile_corners=c_end,
                    ))

            # Concrete volume: waist + steps triangles + landing + landing edge beams
            vol_f1 = (slope_1 * w * waist_t) + (n_risers_1 * 0.5 * tread * actual_riser_1 * w)
            vol_f2 = (slope_2 * w * waist_t) + (n_risers_2 * 0.5 * tread * actual_riser_2 * w)
            eb_total_vol = sum(b.concrete_volume for b in landing_edge_beams)
            tot_conc_vol = vol_f1 + vol_f2 + landing_vol + eb_total_vol

            # Formwork: soffit + riser faces + side edge + landing edge beams
            form_f1 = (slope_1 * w) + (n_risers_1 * actual_riser_1 * w) + (slope_1 * waist_t * 2)
            form_f2 = (slope_2 * w) + (n_risers_2 * actual_riser_2 * w) + (slope_2 * waist_t * 2)
            eb_total_formwork = sum(b.formwork_area for b in landing_edge_beams)
            tot_formwork = form_f1 + form_f2 + landing_area + eb_total_formwork

        else:
            landing_edge_beams = []

            # Straight flight
            n_risers = max(1, int(round(total_height / riser)))
            run = (n_risers - 1) * tread
            actual_riser = total_height / n_risers
            slope = math.hypot(run, total_height)
            p_start = (base_x, base_y, z_bottom)
            p_end = (base_x, base_y + run, z_top)

            f1_steps = []
            for i in range(n_risers):
                scx = base_x + w / 2.0
                scy = base_y + i * tread + tread / 2.0
                scz = z_bottom + i * actual_riser + actual_riser / 2.0
                step = ResolvedStairStep(
                    step_index=i + 1,
                    flight_tag=f"{stair.tag}-F1",
                    position=(scx, scy, scz),
                    width=w,
                    tread=tread,
                    riser=actual_riser,
                )
                f1_steps.append(step)
                all_steps.append(step)

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
                riser=actual_riser,
                steps=f1_steps,
            )
            flights.append(f)
            landing_poly = None
            landing_area = 0.0
            landing_t = 0.0

            st_mat = (stair.stringer.material if stair.stringer else None) or stair.material
            st_w = stair.stringer.width if stair.stringer else w
            st_d = stair.stringer.depth if stair.stringer else waist_t
            s_start = (base_x + w / 2.0, base_y, z_bottom - st_d / 2.0)
            s_end = (base_x + w / 2.0, base_y + run, z_top - st_d / 2.0)
            s_start_corners = [
                (base_x + (w - st_w) / 2.0, base_y, z_bottom - st_d),
                (base_x + (w + st_w) / 2.0, base_y, z_bottom - st_d),
                (base_x + (w + st_w) / 2.0, base_y, z_bottom),
                (base_x + (w - st_w) / 2.0, base_y, z_bottom),
            ]
            s_end_corners = [
                (base_x + (w - st_w) / 2.0, base_y + run, z_top - st_d),
                (base_x + (w + st_w) / 2.0, base_y + run, z_top - st_d),
                (base_x + (w + st_w) / 2.0, base_y + run, z_top),
                (base_x + (w - st_w) / 2.0, base_y + run, z_top),
            ]
            stringers.append(ResolvedStairStringer(
                tag=f"{stair.tag}-Stringer-F1",
                start_point=s_start,
                end_point=s_end,
                width=st_w,
                depth=st_d,
                length=slope,
                material=st_mat,
                start_profile_corners=s_start_corners,
                end_profile_corners=s_end_corners,
            ))

            rh = stair.railing.height if stair.railing else 0.90
            railing_segments.append((
                (base_x + w, base_y, z_bottom + rh),
                (base_x + w, base_y + run, z_top + rh),
            ))

            vol_f = (slope * w * waist_t) + (n_risers * 0.5 * tread * actual_riser * w)
            tot_conc_vol = vol_f
            tot_formwork = (slope * w) + (n_risers * actual_riser * w) + (slope * waist_t * 2)

        # Architectural Finishes & Railing calculations
        tot_tread_area = sum(step.width * step.tread for step in all_steps)
        tot_riser_area = sum(step.width * step.riser for step in all_steps)
        nosing_len = len(all_steps) * w if (stair.finishes and stair.finishes.nosing) else 0.0

        resolved_railing = None
        if stair.railing:
            rh = stair.railing.height
            rlayout = stair.railing.layout  # "SINGLE" or "DOUBLE"
            railing_posts: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []
            railing_rails: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []

            for f in flights:
                if not f.steps:
                    continue
                first_step = f.steps[0]
                last_step = f.steps[-1]

                # Determine post X offsets across width
                x_offsets = []
                if rlayout == "DOUBLE":
                    x_offsets = [-first_step.width / 2.0 + 0.05, first_step.width / 2.0 - 0.05]
                elif stair.railing.side == "OUTER":
                    x_offsets = [-first_step.width / 2.0 + 0.05]
                else:  # "INNER" default
                    x_offsets = [first_step.width / 2.0 - 0.05]

                for x_off in x_offsets:
                    # First step post
                    p1_base = (first_step.position[0] + x_off, first_step.position[1], first_step.position[2] + first_step.riser / 2.0)
                    p1_top = (p1_base[0], p1_base[1], p1_base[2] + rh)
                    railing_posts.append((p1_base, p1_top))

                    # Last step post
                    p2_base = (last_step.position[0] + x_off, last_step.position[1], last_step.position[2] + last_step.riser / 2.0)
                    p2_top = (p2_base[0], p2_base[1], p2_base[2] + rh)
                    railing_posts.append((p2_base, p2_top))

                    # Sloping handrail between the two posts
                    railing_rails.append((p1_top, p2_top))

            # Railing segments include posts + rails for total length calculation
            all_r_segs = railing_posts + railing_rails
            r_tot_len = sum(math.dist(seg[0], seg[1]) for seg in all_r_segs)

            resolved_railing = ResolvedStairRailing(
                tag=f"{stair.tag}-Railing",
                posts=railing_posts,
                rails=railing_rails,
                segments=all_r_segs,
                total_length=r_tot_len,
                height=stair.railing.height,
                railing_type=stair.railing.type,
                layout=rlayout,
            )

        return ResolvedStair(
            tag=stair.tag,
            element=stair,
            flights=flights,
            steps=all_steps,
            stringers=stringers,
            landing_polygon=landing_poly,
            landing_thickness=landing_t,
            landing_area=landing_area,
            landing_edge_beams=landing_edge_beams,
            railing=resolved_railing,

            nosing_length=nosing_len,
            total_tread_finish_area=tot_tread_area,
            total_riser_finish_area=tot_riser_area,
            total_concrete_volume=tot_conc_vol,
            total_formwork_area=tot_formwork,
            layer=derive_default_layer(stair),
        )

    def resolve_terminal(self, terminal: TerminalElement) -> ResolvedTerminal:
        placement = terminal.placement

        if placement.wall:
            if placement.wall not in self.walls_by_tag:
                raise ValueError(f"Hosting wall '{placement.wall}' not found.")

            r_wall = self.walls_by_tag[placement.wall]
            wall_elem = r_wall.element

            # Inherit storey from wall if omitted
            storey_id = placement.storey or wall_elem.placement.storey
            storey = self.get_storey(storey_id)

            x1, y1, _ = r_wall.start_point
            x2, y2, _ = r_wall.end_point
            wall_len = r_wall.length
            thickness = r_wall.thickness

            if wall_len > 0:
                ux = (x2 - x1) / wall_len
                uy = (y2 - y1) / wall_len
            else:
                ux, uy = 1.0, 0.0

            # Normal vector perpendicular to wall: n = (-uy, ux)
            nx, ny = -uy, ux

            # Base point along wall
            p_base_x = x1 + placement.distance * ux
            p_base_y = y1 + placement.distance * uy

            fixture_depth = getattr(terminal, "depth", 0.0) or 0.0
            if fixture_depth == 0.0 and getattr(terminal, "dimensions", None):
                fixture_depth = terminal.dimensions.depth
            standoff = placement.standoff

            # Offset distance from wall centerline
            if placement.side == "CENTER":
                offset_dist = 0.0
            elif placement.side == "EXTERIOR":
                offset_dist = -(thickness / 2.0 + standoff + fixture_depth / 2.0)
            else:  # INTERIOR
                offset_dist = +(thickness / 2.0 + standoff + fixture_depth / 2.0)

            px = p_base_x + offset_dist * nx
            py = p_base_y + offset_dist * ny
            pz = storey.elevation + placement.offset_z

            if placement.rotation is not None:
                rot_angle = placement.rotation
            else:
                # Auto-calculate rotation angle so the fixture faces away from wall into room
                # For INTERIOR, outward direction is n = (-uy, ux) -> angle = math.atan2(ny, nx)
                # For EXTERIOR, outward direction is -n = (uy, -ux) -> angle = math.atan2(-ny, -nx)
                if placement.side == "EXTERIOR":
                    rot_angle = math.degrees(math.atan2(-ny, -nx))
                else:  # INTERIOR or CENTER default
                    rot_angle = math.degrees(math.atan2(ny, nx))

            return ResolvedTerminal(
                tag=terminal.tag,
                element=terminal,
                position=(px, py, pz),
                rotation_angle=rot_angle,
                hosting_wall=r_wall,
                layer=derive_default_layer(terminal),
            )

        elif placement.grid:
            if not placement.storey:
                raise ValueError(f"Terminal '{terminal.tag}' with grid placement must specify a storey.")

            gx, gy = self.get_grid_xy(placement.grid)
            storey = self.get_storey(placement.storey)

            px = gx + placement.offset_x
            py = gy + placement.offset_y
            pz = storey.elevation + placement.offset_z
            rot_angle = placement.rotation if placement.rotation is not None else 0.0

            return ResolvedTerminal(
                tag=terminal.tag,
                element=terminal,
                position=(px, py, pz),
                rotation_angle=rot_angle,
                hosting_wall=None,
                layer=derive_default_layer(terminal),
            )

        else:
            raise ValueError(f"Terminal '{terminal.tag}' placement must specify either wall or grid.")

    def resolve_roof(self, roof: IfcRoof) -> ResolvedRoof:
        xs = []
        ys = []
        for pt in roof.placement.boundary:
            gx, gy = pt
            xs.append(self.axes_x[gx])
            ys.append(self.axes_y[gy])

        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        oh = roof.placement.overhang
        x0 = min_x - oh
        x1 = max_x + oh
        y0 = min_y - oh
        y1 = max_y + oh

        width = x1 - x0
        length = y1 - y0
        half_span = min(width, length) / 2.0

        st = self.storeys[roof.placement.storey]
        z0 = st.elevation + roof.placement.offset_z
        pitch = roof.covering.pitch if roof.covering else 30.0
        pitch_rad = math.radians(pitch)

        # 4 Eaves corners at base eaves elevation
        c1 = (x0, y0, z0)  # SW
        c2 = (x1, y0, z0)  # SE
        c3 = (x1, y1, z0)  # NE
        c4 = (x0, y1, z0)  # NW

        footprint_poly = [c1, c2, c3, c4]
        footprint_area = width * length
        eaves_perimeter = 2.0 * (width + length)

        planes: List[ResolvedRoofPlane] = []
        ridges: List[ResolvedRoofRidge] = []

        roof_type = roof.roof_type.upper()
        orientation = roof.placement.ridge_orientation

        if roof_type == "GABLE":
            # Gable roof (อกไก่แนวขวางหรือแนวยาว + 2 ด้านลาดเอียง)
            if orientation == "Y" or (orientation == "ALONG_LENGTH" and length >= width):
                span = width
                half_span = span / 2.0
                rise_h = half_span * math.tan(pitch_rad)
                zr = z0 + rise_h
                x_mid = (x0 + x1) / 2.0
                r1 = (x_mid, y0, zr)
                r2 = (x_mid, y1, zr)

                ridges.append(ResolvedRoofRidge(
                    tag=f"{roof.tag}-Ridge",
                    start_point=r1,
                    end_point=r2,
                    length=length,
                    ridge_type="RIDGE",
                ))

                p_west = [c1, r1, r2, c4]
                p_east = [c2, c3, r2, r1]

                for p_tag, poly in [("WestSlope", p_west), ("EastSlope", p_east)]:
                    area, normal = _calc_polygon_3d(poly)
                    planes.append(ResolvedRoofPlane(
                        tag=f"{roof.tag}-{p_tag}",
                        polygon=poly,
                        area=area,
                        slope_degrees=pitch,
                        normal=normal,
                    ))

                v_segs = [(c1, r1), (c2, r1), (c4, r2), (c3, r2)]
                for v_idx, (v_start, v_end) in enumerate(v_segs):
                    ridges.append(ResolvedRoofRidge(
                        tag=f"{roof.tag}-Verge-{v_idx+1}",
                        start_point=v_start,
                        end_point=v_end,
                        length=math.dist(v_start, v_end),
                        ridge_type="VERGE",
                    ))
            else:
                # Ridge runs along X (default)
                span = length
                half_span = span / 2.0
                rise_h = half_span * math.tan(pitch_rad)
                zr = z0 + rise_h
                y_mid = (y0 + y1) / 2.0
                r1 = (x0, y_mid, zr)
                r2 = (x1, y_mid, zr)

                ridges.append(ResolvedRoofRidge(
                    tag=f"{roof.tag}-Ridge",
                    start_point=r1,
                    end_point=r2,
                    length=width,
                    ridge_type="RIDGE",
                ))

                p_south = [c1, c2, r2, r1]
                p_north = [c4, r1, r2, c3]

                for p_tag, poly in [("SouthSlope", p_south), ("NorthSlope", p_north)]:
                    area, normal = _calc_polygon_3d(poly)
                    planes.append(ResolvedRoofPlane(
                        tag=f"{roof.tag}-{p_tag}",
                        polygon=poly,
                        area=area,
                        slope_degrees=pitch,
                        normal=normal,
                    ))

                v_segs = [(c1, r1), (c4, r1), (c2, r2), (c3, r2)]
                for v_idx, (v_start, v_end) in enumerate(v_segs):
                    ridges.append(ResolvedRoofRidge(
                        tag=f"{roof.tag}-Verge-{v_idx+1}",
                        start_point=v_start,
                        end_point=v_end,
                        length=math.dist(v_start, v_end),
                        ridge_type="VERGE",
                    ))

        elif roof_type == "HIP":
            # Hip roof (หลังคาปั้นหยา 4 ด้าน)
            if orientation == "Y" or (orientation == "ALONG_LENGTH" and length > width):
                half_span = width / 2.0
                rise_h = half_span * math.tan(pitch_rad)
                zr = z0 + rise_h
                x_mid = (x0 + x1) / 2.0
                y_a = y0 + half_span
                y_b = y1 - half_span
                if y_b < y_a:
                    y_a = y_b = (y0 + y1) / 2.0

                r1 = (x_mid, y_a, zr)
                r2 = (x_mid, y_b, zr)
                ridge_len = y_b - y_a
                if ridge_len > 0.01:
                    ridges.append(ResolvedRoofRidge(
                        tag=f"{roof.tag}-Ridge",
                        start_point=r1,
                        end_point=r2,
                        length=ridge_len,
                        ridge_type="RIDGE",
                    ))

                hip_lines = [
                    ("Hip-SW", c1, r1),
                    ("Hip-SE", c2, r1),
                    ("Hip-NE", c3, r2),
                    ("Hip-NW", c4, r2),
                ]
                for h_tag, h_s, h_e in hip_lines:
                    ridges.append(ResolvedRoofRidge(
                        tag=f"{roof.tag}-{h_tag}",
                        start_point=h_s,
                        end_point=h_e,
                        length=math.dist(h_s, h_e),
                        ridge_type="HIP",
                    ))

                p_south = [c1, c2, r1]
                p_north = [c3, c4, r2]
                p_east = [c2, c3, r2, r1] if ridge_len > 0.01 else [c2, c3, r1]
                p_west = [c4, c1, r1, r2] if ridge_len > 0.01 else [c4, c1, r1]

                for p_tag, poly in [("SouthHip", p_south), ("NorthHip", p_north), ("EastSlope", p_east), ("WestSlope", p_west)]:
                    area, normal = _calc_polygon_3d(poly)
                    planes.append(ResolvedRoofPlane(
                        tag=f"{roof.tag}-{p_tag}",
                        polygon=poly,
                        area=area,
                        slope_degrees=pitch,
                        normal=normal,
                    ))

            else:
                # Ridge along X (default)
                half_span = length / 2.0
                rise_h = half_span * math.tan(pitch_rad)
                zr = z0 + rise_h
                y_mid = (y0 + y1) / 2.0
                x_a = x0 + half_span
                x_b = x1 - half_span
                if x_b < x_a:
                    x_a = x_b = (x0 + x1) / 2.0

                r1 = (x_a, y_mid, zr)
                r2 = (x_b, y_mid, zr)
                ridge_len = x_b - x_a
                if ridge_len > 0.01:
                    ridges.append(ResolvedRoofRidge(
                        tag=f"{roof.tag}-Ridge",
                        start_point=r1,
                        end_point=r2,
                        length=ridge_len,
                        ridge_type="RIDGE",
                    ))

                hip_lines = [
                    ("Hip-SW", c1, r1),
                    ("Hip-NW", c4, r1),
                    ("Hip-SE", c2, r2),
                    ("Hip-NE", c3, r2),
                ]
                for h_tag, h_s, h_e in hip_lines:
                    ridges.append(ResolvedRoofRidge(
                        tag=f"{roof.tag}-{h_tag}",
                        start_point=h_s,
                        end_point=h_e,
                        length=math.dist(h_s, h_e),
                        ridge_type="HIP",
                    ))

                p_west = [c1, r1, c4]
                p_east = [c2, c3, r2]
                p_south = [c1, c2, r2, r1] if ridge_len > 0.01 else [c1, c2, r1]
                p_north = [c4, r1, r2, c3] if ridge_len > 0.01 else [c4, r1, c3]

                for p_tag, poly in [("WestHip", p_west), ("EastHip", p_east), ("SouthSlope", p_south), ("NorthSlope", p_north)]:
                    area, normal = _calc_polygon_3d(poly)
                    planes.append(ResolvedRoofPlane(
                        tag=f"{roof.tag}-{p_tag}",
                        polygon=poly,
                        area=area,
                        slope_degrees=pitch,
                        normal=normal,
                    ))

        elif roof_type == "SHED":
            # Shed (เพิงหมาแหงน)
            span = length
            rise_h = span * math.tan(pitch_rad)
            zr = z0 + rise_h
            p1 = c1
            p2 = c2
            p3 = (x1, y1, zr)
            p4 = (x0, y1, zr)
            poly = [p1, p2, p3, p4]
            area, normal = _calc_polygon_3d(poly)
            planes.append(ResolvedRoofPlane(
                tag=f"{roof.tag}-ShedSlope",
                polygon=poly,
                area=area,
                slope_degrees=pitch,
                normal=normal,
            ))
            ridges.append(ResolvedRoofRidge(
                tag=f"{roof.tag}-TopEdge",
                start_point=p4,
                end_point=p3,
                length=width,
                ridge_type="RIDGE",
            ))

        else:  # FLAT or other
            zr = z0
            poly = [c1, c2, c3, c4]
            area, normal = _calc_polygon_3d(poly)
            planes.append(ResolvedRoofPlane(
                tag=f"{roof.tag}-FlatSurface",
                polygon=poly,
                area=area,
                slope_degrees=0.0,
                normal=(0.0, 0.0, 1.0),
            ))

        # Eaves perimeter segments
        eave_segs = [(c1, c2), (c2, c3), (c3, c4), (c4, c1)]
        for e_idx, (e_s, e_e) in enumerate(eave_segs):
            ridges.append(ResolvedRoofRidge(
                tag=f"{roof.tag}-Eave-{e_idx+1}",
                start_point=e_s,
                end_point=e_e,
                length=math.dist(e_s, e_e),
                ridge_type="EAVE",
            ))

        tot_sloped_area = sum(p.area for p in planes)
        tot_ridge_len = sum(r.length for r in ridges if r.ridge_type == "RIDGE")
        tot_hip_len = sum(r.length for r in ridges if r.ridge_type == "HIP")

        steel_rate = roof.framing.steel_weight_per_sqm if roof.framing else 18.0
        tot_steel = footprint_area * steel_rate

        # Roof Framing Members Synthesis (โครงสร้างหลังคาแยกชิ้นส่วน: อะเส, ขื่อ, อกไก่, ดั้ง, ตะเข้สัน, จันทัน, แป)
        framing_members: List[ResolvedRoofFramingMember] = []
        f_mat = roof.framing.material if roof.framing else "STEEL_SS400"

        # 1. อะเส (Wall Plates) รอบแนวอาคาร/ชายคา
        wall_plate_corners = [
            ("WP-South", c1, c2),
            ("WP-East", c2, c3),
            ("WP-North", c3, c4),
            ("WP-West", c4, c1),
        ]
        for wp_tag, p_s, p_e in wall_plate_corners:
            framing_members.append(ResolvedRoofFramingMember(
                tag=f"{roof.tag}-{wp_tag}",
                member_type="WALL_PLATE",
                name_th="อะเส (Wall Plate)",
                start_point=p_s,
                end_point=p_e,
                length=math.dist(p_s, p_e),
                color="#3B82F6",  # Blue
                material=f_mat,
                profile="C150x50x20x3.2",
            ))

        # 2. อกไก่ (Ridge Beam), ตะเข้สัน (Hip Rafters), เสาดั้ง (King Posts), ขื่อ (Tie Beams)
        for r in ridges:
            if r.ridge_type == "RIDGE":
                framing_members.append(ResolvedRoofFramingMember(
                    tag=f"{roof.tag}-RidgeBeam",
                    member_type="RIDGE_BEAM",
                    name_th="อกไก่ (Ridge Beam)",
                    start_point=r.start_point,
                    end_point=r.end_point,
                    length=r.length,
                    color="#EF4444",  # Red
                    material=f_mat,
                    profile="2C150x50x20x3.2",
                ))
                # เสาดั้ง (King Posts) ที่ปลายอกไก่ลงมาที่ระดับอะเส
                framing_members.append(ResolvedRoofFramingMember(
                    tag=f"{roof.tag}-KingPost-1",
                    member_type="KING_POST",
                    name_th="เสาดั้ง (King Post)",
                    start_point=(r.start_point[0], r.start_point[1], z0),
                    end_point=r.start_point,
                    length=r.start_point[2] - z0,
                    color="#A855F7",  # Purple
                    material=f_mat,
                    profile="2C100x50x20x3.2",
                ))
                if r.length > 0.01:
                    framing_members.append(ResolvedRoofFramingMember(
                        tag=f"{roof.tag}-KingPost-2",
                        member_type="KING_POST",
                        name_th="เสาดั้ง (King Post)",
                        start_point=(r.end_point[0], r.end_point[1], z0),
                        end_point=r.end_point,
                        length=r.end_point[2] - z0,
                        color="#A855F7",  # Purple
                        material=f_mat,
                        profile="2C100x50x20x3.2",
                    ))
                    # ขื่อ (Tie Beam) เชื่อมใต้ดั้งทั้งสอง
                    framing_members.append(ResolvedRoofFramingMember(
                        tag=f"{roof.tag}-TieBeam",
                        member_type="TIE_BEAM",
                        name_th="ขื่อ (Tie Beam)",
                        start_point=(r.start_point[0], r.start_point[1], z0),
                        end_point=(r.end_point[0], r.end_point[1], z0),
                        length=r.length,
                        color="#6366F1",  # Indigo
                        material=f_mat,
                        profile="2C125x50x20x3.2",
                    ))
            elif r.ridge_type == "HIP":
                framing_members.append(ResolvedRoofFramingMember(
                    tag=r.tag.replace("Roof", "HipRafter"),
                    member_type="HIP_RAFTER",
                    name_th="ตะเข้สัน (Hip Rafter)",
                    start_point=r.start_point,
                    end_point=r.end_point,
                    length=r.length,
                    color="#F59E0B",  # Amber
                    material=f_mat,
                    profile="2C150x50x20x3.2",
                ))

        # 3. จันทัน (Rafters - Common & Jack Rafters) ตามระยะสแปน
        r_spacing = roof.framing.spacing if roof.framing and roof.framing.spacing else 1.0
        # กระจายจันทันบนแต่ละผืนหลังคา (Planes)
        rafter_idx = 1
        for plane in planes:
            poly = plane.polygon
            poly_xs = [p[0] for p in poly]
            poly_ys = [p[1] for p in poly]
            min_px, max_px = min(poly_xs), max(poly_xs)
            min_py, max_py = min(poly_ys), max(poly_ys)

            # ตรวจสอบว่าลาดเอียงไปทางแกนไหน
            # ถ้าความกว้างใน X กว้างกว่า Y หรือความลาดเอียงหลัก
            nx, ny, nz = plane.normal
            if abs(nx) > abs(ny):
                # ลาดเอียงทาง X -> จันทันวางขนานแนว X, เรียงไปตามแนว Y
                y_curr = min_py + r_spacing
                while y_curr < max_py - 0.2:
                    # หาจุดตัดกับขอบของ poly ที่ y = y_curr
                    x_pts = []
                    n_pts = len(poly)
                    for i in range(n_pts):
                        p_a = poly[i]
                        p_b = poly[(i + 1) % n_pts]
                        if (p_a[1] <= y_curr <= p_b[1]) or (p_b[1] <= y_curr <= p_a[1]):
                            if abs(p_b[1] - p_a[1]) > 1e-4:
                                t = (y_curr - p_a[1]) / (p_b[1] - p_a[1])
                                ix = p_a[0] + t * (p_b[0] - p_a[0])
                                iz = p_a[2] + t * (p_b[2] - p_a[2])
                                x_pts.append((ix, y_curr, iz))
                    if len(x_pts) >= 2:
                        x_pts.sort(key=lambda p: p[0])
                        p_start = x_pts[0]
                        p_end = x_pts[-1]
                        l_raf = math.dist(p_start, p_end)
                        if l_raf > 0.3:
                            framing_members.append(ResolvedRoofFramingMember(
                                tag=f"{roof.tag}-Rafter-{rafter_idx}",
                                member_type="COMMON_RAFTER" if abs(l_raf - half_span / math.cos(pitch_rad)) < 0.5 else "JACK_RAFTER",
                                name_th="จันทัน (Rafter)",
                                start_point=p_start,
                                end_point=p_end,
                                length=l_raf,
                                color="#06B6D4",  # Cyan
                                material=f_mat,
                                profile="C100x50x20x3.2",
                            ))
                            rafter_idx += 1
                    y_curr += r_spacing
            else:
                # ลาดเอียงทาง Y -> จันทันวางขนานแนว Y, เรียงไปตามแนว X
                x_curr = min_px + r_spacing
                while x_curr < max_px - 0.2:
                    # หาจุดตัดกับขอบของ poly ที่ x = x_curr
                    y_pts = []
                    n_pts = len(poly)
                    for i in range(n_pts):
                        p_a = poly[i]
                        p_b = poly[(i + 1) % n_pts]
                        if (p_a[0] <= x_curr <= p_b[0]) or (p_b[0] <= x_curr <= p_a[0]):
                            if abs(p_b[0] - p_a[0]) > 1e-4:
                                t = (x_curr - p_a[0]) / (p_b[0] - p_a[0])
                                iy = p_a[1] + t * (p_b[1] - p_a[1])
                                iz = p_a[2] + t * (p_b[2] - p_a[2])
                                y_pts.append((x_curr, iy, iz))
                    if len(y_pts) >= 2:
                        y_pts.sort(key=lambda p: p[1])
                        p_start = y_pts[0]
                        p_end = y_pts[-1]
                        l_raf = math.dist(p_start, p_end)
                        if l_raf > 0.3:
                            framing_members.append(ResolvedRoofFramingMember(
                                tag=f"{roof.tag}-Rafter-{rafter_idx}",
                                member_type="COMMON_RAFTER" if abs(l_raf - half_span / math.cos(pitch_rad)) < 0.5 else "JACK_RAFTER",
                                name_th="จันทัน (Rafter)",
                                start_point=p_start,
                                end_point=p_end,
                                length=l_raf,
                                color="#06B6D4",  # Cyan
                                material=f_mat,
                                profile="C100x50x20x3.2",
                            ))
                            rafter_idx += 1
                    x_curr += r_spacing

        # 4. แป (Purlins) กระจายตามแนวระดับความสูง (Purlin Rings / Lines)
        purlin_idx = 1
        p_spacing = roof.framing.purlin_spacing if roof.framing and roof.framing.purlin_spacing else 0.50
        # ระยะห่างในแนวลาดเอียงแปลงเป็นความสูงในแนวดิ่ง delta_z
        dz_purlin = p_spacing * math.sin(pitch_rad)
        if dz_purlin > 0.05:
            z_curr = z0 + dz_purlin
            while z_curr < zr - 0.05:
                # ในแต่ละความสูง z_curr หาเส้นตัดแนวนอนบนแต่ละ plane
                for plane in planes:
                    poly = plane.polygon
                    pts_at_z = []
                    n_pts = len(poly)
                    for i in range(n_pts):
                        p_a = poly[i]
                        p_b = poly[(i + 1) % n_pts]
                        if (p_a[2] <= z_curr <= p_b[2]) or (p_b[2] <= z_curr <= p_a[2]):
                            if abs(p_b[2] - p_a[2]) > 1e-4:
                                t = (z_curr - p_a[2]) / (p_b[2] - p_a[2])
                                ix = p_a[0] + t * (p_b[0] - p_a[0])
                                iy = p_a[1] + t * (p_b[1] - p_a[1])
                                pts_at_z.append((ix, iy, z_curr))
                    if len(pts_at_z) >= 2:
                        p_start = pts_at_z[0]
                        p_end = pts_at_z[-1]
                        l_pur = math.dist(p_start, p_end)
                        if l_pur > 0.2:
                            framing_members.append(ResolvedRoofFramingMember(
                                tag=f"{roof.tag}-Purlin-{purlin_idx}",
                                member_type="PURLIN",
                                name_th="แป (Purlin)",
                                start_point=p_start,
                                end_point=p_end,
                                length=l_pur,
                                color="#10B981",  # Emerald Green
                                material=f_mat,
                                profile="C75x45x15x2.3",
                            ))
                            purlin_idx += 1
                z_curr += dz_purlin

        resolved_children: List[ResolvedWallChild] = []
        st = self.storeys[roof.placement.storey]
        for child in roof.children:
            pos = (0.0, 0.0, st.elevation + child.sill_height)
            if isinstance(child, IfcDoor):
                r_door = ResolvedDoor(
                    tag=child.tag,
                    element=child,
                    position=pos,
                    width=child.dimensions.width,
                    height=child.dimensions.height,
                    offset_distance=child.offset_distance,
                    sill_height=child.sill_height,
                    layer=derive_default_layer(child),
                )
                resolved_children.append(r_door)
            elif isinstance(child, IfcWindow):
                r_win = ResolvedWindow(
                    tag=child.tag,
                    element=child,
                    position=pos,
                    width=child.dimensions.width,
                    height=child.dimensions.height,
                    offset_distance=child.offset_distance,
                    sill_height=child.sill_height,
                    layer=derive_default_layer(child),
                )
                resolved_children.append(r_win)

        return ResolvedRoof(
            tag=roof.tag,
            element=roof,
            roof_type=roof_type,
            pitch=pitch,
            eaves_elevation=z0,
            ridge_elevation=zr,
            footprint_polygon=footprint_poly,
            planes=planes,
            ridges=ridges,
            framing_members=framing_members,
            children=resolved_children,
            total_footprint_area=footprint_area,
            total_sloped_area=tot_sloped_area,
            total_ridge_length=tot_ridge_len,
            total_hip_length=tot_hip_len,
            total_eaves_length=eaves_perimeter,
            total_steel_weight=tot_steel,
            layer=derive_default_layer(roof),
        )

    def resolve_pipe(self, pipe: IfcPipeSegment) -> ResolvedPipeSegment:
        z_base = self.storeys[pipe.placement.storey].elevation
        waypoints: List[Tuple[float, float, float]] = []

        if pipe.placement.path and len(pipe.placement.path) >= 2:
            for pt in pipe.placement.path:
                if pt.x is not None and pt.y is not None:
                    x = float(pt.x)
                    y = float(pt.y)
                    z = float(pt.z) if pt.z is not None else (z_base + pt.offset_z)
                elif pt.grid:
                    gx, gy = pt.grid
                    x = self.axes_x[gx] + pt.offset_x
                    y = self.axes_y[gy] + pt.offset_y
                    z = z_base + pt.offset_z
                else:
                    x, y, z = (0.0, 0.0, z_base + pt.offset_z)
                waypoints.append((x, y, z))
        else:
            gx1, gy1 = pipe.placement.from_grid or ("1", "A")
            gx2, gy2 = pipe.placement.to_grid or ("1", "A")
            fo = pipe.placement.from_offset
            to = pipe.placement.to_offset
            p1 = (self.axes_x[gx1] + fo[0], self.axes_y[gy1] + fo[1], z_base + fo[2])
            p2 = (self.axes_x[gx2] + to[0], self.axes_y[gy2] + to[1], z_base + to[2])
            if pipe.placement.slope != 0.0:
                dist_xy = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                p2 = (p2[0], p2[1], p2[2] - dist_xy * pipe.placement.slope)

            routing_strat = getattr(pipe.placement, "routing", "DIRECT")
            if routing_strat != "DIRECT":
                waypoints = _generate_orthogonal_waypoints(p1, p2, routing_strat)
            else:
                waypoints = [p1, p2]

        total_length = sum(
            math.dist(waypoints[i], waypoints[i + 1]) for i in range(len(waypoints) - 1)
        )
        fittings = max(1, len(waypoints) - 1)
        color = MEP_PIPE_COLORS.get(pipe.system_type, "#0284C7")

        return ResolvedPipeSegment(
            tag=pipe.tag,
            element=pipe,
            system_type=pipe.system_type,
            nominal_diameter=pipe.nominal_diameter,
            length=total_length,
            slope=pipe.placement.slope,
            start_point=waypoints[0],
            end_point=waypoints[-1],
            waypoints=waypoints,
            color=color,
            fittings_count=fittings,
            layer=derive_default_layer(pipe),
        )

    def resolve_conduit(self, conduit: IfcCableCarrierSegment) -> ResolvedCableCarrierSegment:
        z_base = self.storeys[conduit.placement.storey].elevation
        waypoints: List[Tuple[float, float, float]] = []

        if conduit.placement.path and len(conduit.placement.path) >= 2:
            for pt in conduit.placement.path:
                if pt.x is not None and pt.y is not None:
                    x = float(pt.x)
                    y = float(pt.y)
                    z = float(pt.z) if pt.z is not None else (z_base + pt.offset_z)
                elif pt.grid:
                    gx, gy = pt.grid
                    x = self.axes_x[gx] + pt.offset_x
                    y = self.axes_y[gy] + pt.offset_y
                    z = z_base + pt.offset_z
                else:
                    x, y, z = (0.0, 0.0, z_base + pt.offset_z)
                waypoints.append((x, y, z))
        else:
            gx1, gy1 = conduit.placement.from_grid or ("1", "A")
            gx2, gy2 = conduit.placement.to_grid or ("1", "A")
            fo = conduit.placement.from_offset
            to = conduit.placement.to_offset
            p1 = (self.axes_x[gx1] + fo[0], self.axes_y[gy1] + fo[1], z_base + fo[2])
            p2 = (self.axes_x[gx2] + to[0], self.axes_y[gy2] + to[1], z_base + to[2])

            routing_strat = getattr(conduit.placement, "routing", "DIRECT")
            if routing_strat != "DIRECT":
                waypoints = _generate_orthogonal_waypoints(p1, p2, routing_strat)
            else:
                waypoints = [p1, p2]

        total_length = sum(
            math.dist(waypoints[i], waypoints[i + 1]) for i in range(len(waypoints) - 1)
        )
        fittings = max(1, len(waypoints) - 1)
        color = MEP_CONDUIT_COLORS.get(conduit.system_type, "#F97316")

        return ResolvedCableCarrierSegment(
            tag=conduit.tag,
            element=conduit,
            system_type=conduit.system_type,
            nominal_diameter=conduit.nominal_diameter,
            length=total_length,
            start_point=waypoints[0],
            end_point=waypoints[-1],
            waypoints=waypoints,
            color=color,
            fittings_count=fittings,
            layer=derive_default_layer(conduit),
        )

    def resolve_sanitary_terminal(self, term: IfcSanitaryTerminal) -> ResolvedSanitaryTerminal:
        r_term = self.resolve_terminal(term)
        dims = (
            (term.dimensions.width, term.dimensions.depth, term.dimensions.height)
            if term.dimensions
            else (term.width, term.depth, term.height)
            if (term.width or term.depth or term.height)
            else DEFAULT_TERMINAL_DIMENSIONS.get(term.terminal_type, (0.50, 0.50, 0.50))
        )
        color = DEFAULT_TERMINAL_COLORS.get(term.terminal_type, "#F8FAFC")
        return ResolvedSanitaryTerminal(
            tag=term.tag,
            element=term,
            terminal_type=term.terminal_type,
            position=r_term.position,
            rotation=r_term.rotation_angle,
            rotation_angle=r_term.rotation_angle,
            dimensions=dims,
            color=color,
            layer=derive_default_layer(term),
        )

    def resolve_distribution_board(self, board: IfcDistributionBoard) -> ResolvedDistributionBoard:
        r_term = self.resolve_terminal(board)
        dims = (
            (board.dimensions.width, board.dimensions.depth, board.dimensions.height)
            if board.dimensions
            else (board.width, board.depth, board.height)
            if (board.width or board.depth or board.height)
            else DEFAULT_TERMINAL_DIMENSIONS.get(board.board_type, (0.35, 0.12, 0.45))
        )
        color = DEFAULT_TERMINAL_COLORS.get(board.board_type, "#334155")
        return ResolvedDistributionBoard(
            tag=board.tag,
            element=board,
            board_type=board.board_type,
            position=r_term.position,
            rotation=r_term.rotation_angle,
            rotation_angle=r_term.rotation_angle,
            dimensions=dims,
            color=color,
            circuits_count=board.circuits_count,
            layer=derive_default_layer(board),
        )

    def resolve_light_fixture(self, fixture: IfcLightFixture) -> ResolvedLightFixture:
        r_term = self.resolve_terminal(fixture)
        dims = (
            (fixture.dimensions.width, fixture.dimensions.depth, fixture.dimensions.height)
            if fixture.dimensions
            else (fixture.width, fixture.depth, fixture.height)
            if (fixture.width or fixture.depth or fixture.height)
            else DEFAULT_TERMINAL_DIMENSIONS.get(fixture.fixture_type, (0.15, 0.15, 0.05))
        )
        color = DEFAULT_TERMINAL_COLORS.get(fixture.fixture_type, "#FEF08A")
        return ResolvedLightFixture(
            tag=fixture.tag,
            element=fixture,
            fixture_type=fixture.fixture_type,
            position=r_term.position,
            rotation=r_term.rotation_angle,
            rotation_angle=r_term.rotation_angle,
            dimensions=dims,
            color=color,
            wattage=fixture.wattage or 12.0,
            layer=derive_default_layer(fixture),
        )

    def resolve_switch(self, sw: IfcSwitchingDevice) -> ResolvedSwitchingDevice:
        r_term = self.resolve_terminal(sw)
        dims = (
            (sw.dimensions.width, sw.dimensions.depth, sw.dimensions.height)
            if sw.dimensions
            else (sw.width, sw.depth, sw.height)
            if (sw.width or sw.depth or sw.height)
            else DEFAULT_TERMINAL_DIMENSIONS.get(sw.switch_type, (0.07, 0.04, 0.12))
        )
        color = DEFAULT_TERMINAL_COLORS.get(sw.switch_type, "#E2E8F0")
        return ResolvedSwitchingDevice(
            tag=sw.tag,
            element=sw,
            switch_type=sw.switch_type,
            position=r_term.position,
            rotation=r_term.rotation_angle,
            rotation_angle=r_term.rotation_angle,
            dimensions=dims,
            color=color,
            gangs=sw.gangs,
            layer=derive_default_layer(sw),
        )

    def resolve_outlet(self, out: IfcOutlet) -> ResolvedOutlet:
        r_term = self.resolve_terminal(out)
        dims = (
            (out.dimensions.width, out.dimensions.depth, out.dimensions.height)
            if out.dimensions
            else (out.width, out.depth, out.height)
            if (out.width or out.depth or out.height)
            else DEFAULT_TERMINAL_DIMENSIONS.get(out.outlet_type, (0.07, 0.04, 0.12))
        )
        color = DEFAULT_TERMINAL_COLORS.get(out.outlet_type, "#E2E8F0")
        return ResolvedOutlet(
            tag=out.tag,
            element=out,
            outlet_type=out.outlet_type,
            position=r_term.position,
            rotation=r_term.rotation_angle,
            rotation_angle=r_term.rotation_angle,
            dimensions=dims,
            color=color,
            layer=derive_default_layer(out),
        )

    def resolve_duct(self, duct: IfcDuctSegment) -> ResolvedDuctSegment:
        z_base = self.storeys[duct.placement.storey].elevation
        waypoints: List[Tuple[float, float, float]] = []

        if duct.placement.path and len(duct.placement.path) >= 2:
            for pt in duct.placement.path:
                if pt.x is not None and pt.y is not None:
                    x = float(pt.x)
                    y = float(pt.y)
                    z = float(pt.z) if pt.z is not None else (z_base + pt.offset_z)
                elif pt.grid:
                    gx, gy = pt.grid
                    x = self.axes_x[gx] + pt.offset_x
                    y = self.axes_y[gy] + pt.offset_y
                    z = z_base + pt.offset_z
                else:
                    x, y, z = (0.0, 0.0, z_base + pt.offset_z)
                waypoints.append((x, y, z))
        else:
            gx1, gy1 = duct.placement.from_grid or ("1", "A")
            gx2, gy2 = duct.placement.to_grid or ("1", "A")
            fo = duct.placement.from_offset
            to = duct.placement.to_offset
            p1 = (self.axes_x[gx1] + fo[0], self.axes_y[gy1] + fo[1], z_base + fo[2])
            p2 = (self.axes_x[gx2] + to[0], self.axes_y[gy2] + to[1], z_base + to[2])

            routing_strat = getattr(duct.placement, "routing", "DIRECT")
            if routing_strat != "DIRECT":
                waypoints = _generate_orthogonal_waypoints(p1, p2, routing_strat)
            else:
                waypoints = [p1, p2]

        total_length = sum(
            math.dist(waypoints[i], waypoints[i + 1]) for i in range(len(waypoints) - 1)
        )
        fittings = max(1, len(waypoints) - 1)
        color = MEP_DUCT_COLORS.get(duct.system_type, "#64748B")

        return ResolvedDuctSegment(
            tag=duct.tag,
            element=duct,
            system_type=duct.system_type,
            width=duct.width,
            height=duct.height,
            length=total_length,
            start_point=waypoints[0],
            end_point=waypoints[-1],
            waypoints=waypoints,
            color=color,
            fittings_count=fittings,
            layer=derive_default_layer(duct),
        )

    def resolve_air_terminal(self, term: IfcAirTerminal) -> ResolvedAirTerminal:
        r_term = self.resolve_terminal(term)
        dims = (
            (term.dimensions.width, term.dimensions.depth, term.dimensions.height)
            if term.dimensions
            else (term.width, term.depth, term.height)
            if (term.width or term.depth or term.height)
            else DEFAULT_TERMINAL_DIMENSIONS.get(term.terminal_type, (0.30, 0.30, 0.20))
        )
        color = DEFAULT_TERMINAL_COLORS.get(term.terminal_type, "#F1F5F9")
        return ResolvedAirTerminal(
            tag=term.tag,
            element=term,
            terminal_type=term.terminal_type,
            position=r_term.position,
            rotation=r_term.rotation_angle,
            rotation_angle=r_term.rotation_angle,
            dimensions=dims,
            color=color,
            flow_rate_cfm=term.flow_rate_cfm,
            layer=derive_default_layer(term),
        )

    def resolve_unitary_equipment(self, equip: IfcUnitaryEquipment) -> ResolvedUnitaryEquipment:
        r_term = self.resolve_terminal(equip)
        dims = (
            (equip.dimensions.width, equip.dimensions.depth, equip.dimensions.height)
            if equip.dimensions
            else (equip.width, equip.depth, equip.height)
            if (equip.width or equip.depth or equip.height)
            else DEFAULT_TERMINAL_DIMENSIONS.get(equip.equipment_type, (0.85, 0.22, 0.30))
        )
        color = DEFAULT_TERMINAL_COLORS.get(equip.equipment_type, "#FFFFFF")
        return ResolvedUnitaryEquipment(
            tag=equip.tag,
            element=equip,
            equipment_type=equip.equipment_type,
            position=r_term.position,
            rotation=r_term.rotation_angle,
            rotation_angle=r_term.rotation_angle,
            dimensions=dims,
            color=color,
            cooling_capacity_btu=equip.cooling_capacity_btu,
            layer=derive_default_layer(equip),
        )

    def resolve(self) -> ResolvedManifest:
        resolved_manifest = ResolvedManifest(manifest=self.manifest)

        # Pass 1: Resolve all walls first and store in lookup mapping
        for elem in self.manifest.elements:
            if isinstance(elem, IfcWall):
                r_wall, doors, windows = self.resolve_wall(elem)
                self.walls_by_tag[elem.tag] = r_wall

        # Pass 2: Resolve all elements in order
        for elem in self.manifest.elements:
            if isinstance(elem, IfcFooting):
                r_footing = self.resolve_footing(elem)
                resolved_manifest.footings.append(r_footing)
                resolved_manifest.elements.append(r_footing)
            elif isinstance(elem, IfcSlab):
                r_slab = self.resolve_slab(elem)
                resolved_manifest.slabs.append(r_slab)
                resolved_manifest.elements.append(r_slab)
            elif isinstance(elem, IfcCovering):
                r_cov = self.resolve_covering(elem)
                resolved_manifest.coverings.append(r_cov)
                resolved_manifest.elements.append(r_cov)
            elif isinstance(elem, IfcStair):
                r_stair = self.resolve_stair(elem)
                resolved_manifest.stairs.append(r_stair)
                resolved_manifest.elements.append(r_stair)
            elif isinstance(elem, IfcRoof):
                r_roof = self.resolve_roof(elem)
                resolved_manifest.roofs.append(r_roof)
                for child in r_roof.children:
                    if isinstance(child, ResolvedDoor):
                        resolved_manifest.doors.append(child)
                    elif isinstance(child, ResolvedWindow):
                        resolved_manifest.windows.append(child)
                resolved_manifest.elements.append(r_roof)
            elif isinstance(elem, IfcColumn):
                r_col = self.resolve_column(elem)
                resolved_manifest.columns.append(r_col)
                resolved_manifest.elements.append(r_col)
            elif isinstance(elem, IfcBeam):
                r_beam = self.resolve_beam(elem)
                resolved_manifest.beams.append(r_beam)
                resolved_manifest.elements.append(r_beam)
            elif isinstance(elem, IfcWall):
                r_wall = self.walls_by_tag[elem.tag]
                # Doors and windows were extracted during resolve_wall
                # We can re-extract or reuse doors/windows
                _, doors, windows = self.resolve_wall(elem)
                resolved_manifest.walls.append(r_wall)
                resolved_manifest.doors.extend(doors)
                resolved_manifest.windows.extend(windows)
                resolved_manifest.elements.append(r_wall)
            elif isinstance(elem, IfcPipeSegment):
                r_pipe = self.resolve_pipe(elem)
                resolved_manifest.pipes.append(r_pipe)
                resolved_manifest.elements.append(r_pipe)
            elif isinstance(elem, IfcCableCarrierSegment):
                r_conduit = self.resolve_conduit(elem)
                resolved_manifest.conduits.append(r_conduit)
                resolved_manifest.elements.append(r_conduit)
            elif isinstance(elem, IfcDuctSegment):
                r_duct = self.resolve_duct(elem)
                resolved_manifest.ducts.append(r_duct)
                resolved_manifest.elements.append(r_duct)
            elif isinstance(elem, IfcSanitaryTerminal):
                r_term = self.resolve_sanitary_terminal(elem)
                resolved_manifest.sanitary_terminals.append(r_term)
                resolved_manifest.elements.append(r_term)
                resolved_manifest.terminals.append(self.resolve_terminal(elem))
            elif isinstance(elem, IfcDistributionBoard):
                r_board = self.resolve_distribution_board(elem)
                resolved_manifest.distribution_boards.append(r_board)
                resolved_manifest.elements.append(r_board)
                resolved_manifest.terminals.append(self.resolve_terminal(elem))
            elif isinstance(elem, IfcLightFixture):
                r_light = self.resolve_light_fixture(elem)
                resolved_manifest.light_fixtures.append(r_light)
                resolved_manifest.elements.append(r_light)
                resolved_manifest.terminals.append(self.resolve_terminal(elem))
            elif isinstance(elem, IfcSwitchingDevice):
                r_sw = self.resolve_switch(elem)
                resolved_manifest.switches.append(r_sw)
                resolved_manifest.elements.append(r_sw)
                resolved_manifest.terminals.append(self.resolve_terminal(elem))
            elif isinstance(elem, IfcOutlet):
                r_out = self.resolve_outlet(elem)
                resolved_manifest.outlets.append(r_out)
                resolved_manifest.elements.append(r_out)
                resolved_manifest.terminals.append(self.resolve_terminal(elem))
            elif isinstance(elem, IfcAirTerminal):
                r_air = self.resolve_air_terminal(elem)
                resolved_manifest.air_terminals.append(r_air)
                resolved_manifest.elements.append(r_air)
                resolved_manifest.terminals.append(self.resolve_terminal(elem))
            elif isinstance(elem, IfcUnitaryEquipment):
                r_eq = self.resolve_unitary_equipment(elem)
                resolved_manifest.unitary_equipments.append(r_eq)
                resolved_manifest.elements.append(r_eq)
                resolved_manifest.terminals.append(self.resolve_terminal(elem))
            elif isinstance(elem, IfcCustomElement):
                r_custom = self.resolve_custom_element(elem)
                resolved_manifest.custom_elements.append(r_custom)
                resolved_manifest.elements.append(r_custom)

        return resolved_manifest


def resolve_manifest(manifest: ProjectManifest) -> ResolvedManifest:
    """Resolve a ProjectManifest into 3D world coordinates and geometric dimensions."""
    resolver = SpatialResolver(manifest)
    return resolver.resolve()
