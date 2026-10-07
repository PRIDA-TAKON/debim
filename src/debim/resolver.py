"""
3D Spatial Coordinate Resolver for debim.
Converts relative grid and storey references into absolute 3D world coordinates
and geometric dimensions.
"""

import math
from typing import Any, Dict, List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ConfigDict, Field

from debim.schema import (
    Dimensions,
    IfcAirTerminal,
    IfcBeam,
    IfcBuildingElementProxy,
    IfcCableCarrierSegment,
    IfcColumn,
    IfcCovering,
    IfcCurtainWall,
    IfcCustomElement,
    IfcDamper,
    IfcDistributionBoard,
    IfcElectricDistributionBoard,
    IfcDoor,
    IfcDuctSegment,
    IfcFlowController,
    IfcFooting,
    IfcLightFixture,
    IfcOutlet,
    IfcPipeSegment,
    IfcPlate,
    IfcRailing,
    IfcRamp,
    IfcRoof,
    IfcSanitaryTerminal,
    IfcWasteTerminal,
    IfcSlab,
    IfcStair,
    IfcStairFlight,
    IfcSwitchingDevice,
    IfcUnitaryEquipment,
    IfcWall,
    IfcWindow,
    Profile,
    ProjectManifest,
    RevolvedAreaSolid,
    Storey,
    SweptDiskSolid,
    derive_default_layer,
)

TerminalElement = Union[
    IfcSanitaryTerminal,
    IfcWasteTerminal,
    IfcDistributionBoard,
    IfcElectricDistributionBoard,
    IfcLightFixture,
    IfcSwitchingDevice,
    IfcOutlet,
    IfcUnitaryEquipment,
    IfcAirTerminal,
    IfcDamper,
    IfcFlowController,
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
    height: float  # True 3D Euclidean spatial length L = sqrt(dx^2 + dy^2 + dz^2)
    direction_vector_3d: Tuple[float, float, float] = (0.0, 0.0, 1.0)
    pitch_angle: float = 0.0
    yaw_angle: float = 0.0
    layer: str = "structure/framing/columns"


class ResolvedBeam(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcBeam
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    span_length: float  # True 3D Euclidean spatial length L
    direction_vector: Tuple[float, float] = (1.0, 0.0)
    direction_vector_3d: Tuple[float, float, float] = (1.0, 0.0, 0.0)
    rotation_angle: float = 0.0
    pitch_angle: float = 0.0
    yaw_angle: float = 0.0
    waypoints: List[Tuple[float, float, float]] = []
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
    frame_thickness: float = 0.05
    frame_width: float = 0.05
    panel_recess: float = 0.015
    panel_thickness: float = 0.035
    operation_type: Optional[str] = None
    flipped: bool = False
    layer: str = "architecture/openings/doors"

    @property
    def frame_box(self) -> Dict[str, float]:
        return {
            "width": self.width,
            "depth": self.frame_thickness,
            "height": self.height,
        }

    @property
    def panel_box(self) -> Dict[str, float]:
        return {
            "width": max(0.01, self.width - 2 * self.frame_width),
            "depth": self.panel_thickness,
            "height": max(0.01, self.height - self.frame_width),
            "offset_y": self.panel_recess,
        }

    @property
    def sub_meshes(self) -> Dict[str, Dict[str, float]]:
        return {
            "frame": self.frame_box,
            "panel": self.panel_box,
        }


class ResolvedWindow(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcWindow
    position: Tuple[float, float, float]
    width: float
    height: float
    offset_distance: float
    sill_height: float
    frame_thickness: float = 0.05
    frame_width: float = 0.05
    panel_recess: float = 0.015
    panel_thickness: float = 0.015
    operation_type: Optional[str] = None
    flipped: bool = False
    layer: str = "architecture/openings/windows"

    @property
    def frame_box(self) -> Dict[str, float]:
        return {
            "width": self.width,
            "depth": self.frame_thickness,
            "height": self.height,
        }

    @property
    def panel_box(self) -> Dict[str, float]:
        return {
            "width": max(0.01, self.width - 2 * self.frame_width),
            "depth": self.panel_thickness,
            "height": max(0.01, self.height - 2 * self.frame_width),
            "offset_y": self.panel_recess,
        }

    @property
    def sub_meshes(self) -> Dict[str, Dict[str, float]]:
        return {
            "frame": self.frame_box,
            "panel": self.panel_box,
        }


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


class ResolvedSweptDisk(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    directrix: List[Tuple[float, float, float]]
    radius: float
    inner_radius: Optional[float] = None
    length: float
    centroid: Tuple[float, float, float]
    bounding_box: Dict[str, float]


class ResolvedRevolvedArea(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    profile: Profile
    axis_point: Tuple[float, float, float]
    axis_direction: Tuple[float, float, float]
    revolution_angle: float
    centroid: Tuple[float, float, float]
    bounding_box: Dict[str, float]
    distance_to_axis: float
    profile_area: float
    profile_perimeter: float


class ResolvedCustomElement(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcCustomElement
    position: Tuple[float, float, float]
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    dimensions: Optional[Dimensions] = None
    resolved_solid: Optional[Union[ResolvedSweptDisk, ResolvedRevolvedArea]] = None
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
    voids: List[List[Tuple[float, float, float]]] = Field(default_factory=list)


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
    layer: str = "architecture/finishes"


class ResolvedStairStep(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    step_index: int
    flight_tag: str
    position: Tuple[float, float, float]  # Center of step box (cx, cy, cz)
    width: float   # Width across flight
    tread: float   # Length along run (ลูกนอน)
    riser: float   # Height (ลูกตั้ง)
    rotation: float = 0.0  # Rotation around Z (radians)
    polygon: Optional[List[Tuple[float, float, float]]] = None


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
    curve_points: List[Tuple[float, float, float]] = []           # Discretized 3D points along helical curve


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
    element: Optional[IfcStairFlight] = None
    layer: str = "architecture/stairs/flights"


class ResolvedRamp(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcRamp
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    width: float
    slab_thickness: float
    run_length: float       # Horizontal length (m)
    rise_height: float      # Vertical rise (m)
    slope_length: float     # True 3D sloped length (m)
    slope_percentage: float # Slope in % (e.g. 8.33)
    direction_vector_3d: Tuple[float, float, float] = (1.0, 0.0, 0.0)
    pitch_angle: float = 0.0
    yaw_angle: float = 0.0
    waypoints: List[Tuple[float, float, float]] = []
    landing_length: Optional[float] = None
    concrete_volume: float = 0.0
    formwork_area: float = 0.0
    layer: str = "architecture/ramps"


class ResolvedRailing(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcRailing
    predefined_type: str = "HANDRAIL"
    height: float = 1.00
    post_spacing: float = 1.50
    waypoints: List[Tuple[float, float, float]] = []
    posts: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []
    rails: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []
    total_length: float = 0.0
    post_count: int = 0
    layer: str = "architecture/railings"


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
    total_steel_weight: float = 0.0
    inner_helical_length: float = 0.0
    outer_helical_length: float = 0.0
    treads_steel_weight: float = 0.0
    stringers_steel_weight: float = 0.0
    base_plates_steel_weight: float = 0.0
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


class ResolvedCurtainWall(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcCurtainWall
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    length: float
    height: float
    gross_facade_area: float  # m2
    net_glass_area: float     # m2
    mullion_length: float     # linear meters of mullions / transoms
    glass_panels_count: int
    mullion_grid_lines: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = Field(default_factory=list)
    layer: str = "architecture/facades/curtain_walls"


class ResolvedPlate(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcPlate
    position: Tuple[float, float, float]
    width: float
    depth: float
    thickness: float
    area: float      # m2
    volume: float    # m3
    weight: float    # kg
    polygon: List[Tuple[float, float, float]] = Field(default_factory=list)
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    layer: str = "architecture/cladding"


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
    "WATERCLOSET": (0.40, 0.70, 0.75),
    "LAVATORY": (0.50, 0.45, 0.80),
    "WASHHANDBASIN": (0.50, 0.45, 0.80),
    "URINAL": (0.35, 0.35, 0.75),
    "SHOWER": (0.20, 0.20, 0.90),
    "BATH": (0.75, 1.70, 0.55),
    "BIDET": (0.40, 0.60, 0.40),
    "KITCHEN_SINK": (0.60, 1.00, 0.85),
    "SINK": (0.60, 1.00, 0.85),
    "FLOOR_DRAIN": (0.15, 0.15, 0.05),
    "FLOORDRAIN": (0.15, 0.15, 0.05),
    "FLOORTRAP": (0.20, 0.20, 0.15),
    "GULLYSUMP": (0.30, 0.30, 0.30),
    "GREASE_TRAP": (0.40, 0.50, 0.40),
    "GREASEINTERCEPTOR": (0.40, 0.50, 0.40),
    "ROOFDRAIN": (0.20, 0.20, 0.10),
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
    "DIFFUSER": (0.60, 0.60, 0.10),
    "GRILLE": (0.60, 0.60, 0.05),
    "REGISTER": (0.40, 0.20, 0.05),
    "LOUVRE": (0.80, 0.60, 0.10),
    "SUPPLY_DIFFUSER": (0.60, 0.60, 0.10),
    "RETURN_GRILLE": (0.60, 0.60, 0.05),
    "AC_INDOOR_WALL": (0.85, 0.22, 0.30),
    "AC_INDOOR_CASSETTE": (0.84, 0.84, 0.28),
    "AC_INDOOR_CONCEALED": (0.90, 0.60, 0.30),
    "AC_OUTDOOR_CONDENSER": (0.85, 0.35, 0.65),
    # Dampers & Flow Controllers
    "FIRE_DAMPER": (0.40, 0.40, 0.30),
    "FIREDAMPER": (0.40, 0.40, 0.30),
    "SMOKE_DAMPER": (0.40, 0.40, 0.35),
    "SMOKEDAMPER": (0.40, 0.40, 0.35),
    "VOLUME_CONTROL_DAMPER": (0.30, 0.30, 0.25),
    "CONTROLDAMPER": (0.30, 0.30, 0.25),
    "GRAVITY_DAMPER": (0.30, 0.30, 0.20),
    "AIR_CONTROLLER": (0.80, 0.50, 0.40),
    "PRESSURE_CONTROLLER": (0.60, 0.40, 0.35),
}

DEFAULT_TERMINAL_COLORS: Dict[str, str] = {
    "WATER_CLOSET": "#F8FAFC",
    "WATERCLOSET": "#F8FAFC",
    "LAVATORY": "#F1F5F9",
    "WASHHANDBASIN": "#F1F5F9",
    "URINAL": "#F8FAFC",
    "SHOWER": "#CBD5E1",
    "BATH": "#FFFFFF",
    "BIDET": "#F8FAFC",
    "KITCHEN_SINK": "#94A3B8",
    "SINK": "#94A3B8",
    "FLOOR_DRAIN": "#64748B",
    "FLOORDRAIN": "#64748B",
    "FLOORTRAP": "#475569",
    "GULLYSUMP": "#334155",
    "GREASE_TRAP": "#0D9488",  # Teal
    "GREASEINTERCEPTOR": "#0D9488",
    "ROOFDRAIN": "#64748B",
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
    "EXHAUST_FAN_CEILING": "#D946EF",
    "EXHAUST_FAN_WALL": "#E11D48",
    "KITCHEN_HOOD": "#94A3B8",
    "DIFFUSER": "#0284C7",
    "GRILLE": "#E11D48",
    "REGISTER": "#38BDF8",
    "LOUVRE": "#64748B",
    "SUPPLY_DIFFUSER": "#0284C7",
    "RETURN_GRILLE": "#E11D48",
    "AC_INDOOR_WALL": "#FFFFFF",
    "AC_INDOOR_CASSETTE": "#F8FAFC",
    "AC_INDOOR_CONCEALED": "#64748B",
    "AC_OUTDOOR_CONDENSER": "#CBD5E1",
    # Dampers & Flow Controllers
    "FIRE_DAMPER": "#EF4444",
    "FIREDAMPER": "#EF4444",
    "SMOKE_DAMPER": "#F97316",
    "SMOKEDAMPER": "#F97316",
    "VOLUME_CONTROL_DAMPER": "#64748B",
    "CONTROLDAMPER": "#64748B",
    "GRAVITY_DAMPER": "#94A3B8",
    "AIR_CONTROLLER": "#475569",
    "PRESSURE_CONTROLLER": "#334155",
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
    predefined_type: str = "USERDEFINED"
    position: Tuple[float, float, float]
    rotation: float = 0.0
    rotation_angle: float = 0.0
    dimensions: Tuple[float, float, float]  # width, depth, height
    color: str
    layer: str = "mep/plumbing/fixtures"


class ResolvedWasteTerminal(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcWasteTerminal
    terminal_type: str
    predefined_type: str = "USERDEFINED"
    position: Tuple[float, float, float]
    rotation: float = 0.0
    rotation_angle: float = 0.0
    dimensions: Tuple[float, float, float]  # width, depth, height
    color: str
    layer: str = "mep/plumbing/drainage"


class ResolvedDistributionBoard(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: Union[IfcDistributionBoard, IfcElectricDistributionBoard]
    board_type: str
    position: Tuple[float, float, float]
    rotation: float = 0.0
    rotation_angle: float = 0.0
    dimensions: Tuple[float, float, float]
    color: str
    circuits_count: int
    voltage: Optional[float] = None
    phases: Optional[Union[int, str]] = None
    main_breaker_rating_amperes: Optional[float] = None
    poles_count: Optional[int] = None
    predefined_type: str = "CONSUMERUNIT"
    layer: str = "mep/electrical/panels"


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
    power_watts: float = 12.0
    luminous_flux_lumens: Optional[float] = None
    color_temperature_kelvin: Optional[float] = None
    predefined_type: str = "POINTSOURCE"
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
    layer: str = "mep/electrical/power"


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
    predefined_type: str = "POWEROUTLET"
    layer: str = "mep/electrical/power"


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
    predefined_type: str = "DIFFUSER"
    position: Tuple[float, float, float]
    rotation: float = 0.0
    rotation_angle: float = 0.0
    dimensions: Tuple[float, float, float]
    color: str
    flow_rate_cfm: Optional[float] = None
    air_flow_rate_m3h: Optional[float] = None
    face_area_m2: Optional[float] = None
    neck_width: Optional[float] = None
    neck_depth: Optional[float] = None
    neck_diameter: Optional[float] = None
    throw_distance_m: Optional[float] = None
    layer: str = "mep/hvac/terminals"


class ResolvedDamper(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcDamper
    damper_type: str
    predefined_type: str = "FIREDAMPER"
    position: Tuple[float, float, float]
    rotation: float = 0.0
    rotation_angle: float = 0.0
    dimensions: Tuple[float, float, float]
    color: str
    duct_width: Optional[float] = None
    duct_depth: Optional[float] = None
    duct_diameter: Optional[float] = None
    actuator_type: str = "MANUAL"
    layer: str = "mep/hvac/dampers"


class ResolvedFlowController(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcFlowController
    controller_type: str
    predefined_type: str = "AIR_CONTROLLER"
    position: Tuple[float, float, float]
    rotation: float = 0.0
    rotation_angle: float = 0.0
    dimensions: Tuple[float, float, float]
    color: str
    air_flow_rate_m3h: Optional[float] = None
    duct_width: Optional[float] = None
    duct_depth: Optional[float] = None
    duct_diameter: Optional[float] = None
    layer: str = "mep/hvac/equipment"


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


class ResolvedProxy(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    tag: str
    element: IfcBuildingElementProxy
    ifc_class: str
    predefined_type: Optional[str] = None
    position: Tuple[float, float, float]
    rotation: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    dimensions: Tuple[float, float, float]
    bounding_box: Dict[str, float]
    properties: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    color: str = "#8B5CF6"
    layer: str = "equipment/proxy"


ResolvedElement = Union[
    ResolvedColumn,
    ResolvedBeam,
    ResolvedWall,
    ResolvedFooting,
    ResolvedSlab,
    ResolvedCovering,
    ResolvedStair,
    ResolvedStairFlight,
    ResolvedRamp,
    ResolvedRailing,
    ResolvedRoof,
    ResolvedCurtainWall,
    ResolvedPlate,
    ResolvedPipeSegment,
    ResolvedCableCarrierSegment,
    ResolvedDuctSegment,
    ResolvedSanitaryTerminal,
    ResolvedWasteTerminal,
    ResolvedDistributionBoard,
    ResolvedLightFixture,
    ResolvedSwitchingDevice,
    ResolvedOutlet,
    ResolvedAirTerminal,
    ResolvedDamper,
    ResolvedFlowController,
    ResolvedUnitaryEquipment,
    ResolvedCustomElement,
    ResolvedTerminal,
    ResolvedDoor,
    ResolvedWindow,
    ResolvedProxy,
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
    stair_flights: List[ResolvedStairFlight] = []
    ramps: List[ResolvedRamp] = []
    railings: List[ResolvedRailing] = []
    roofs: List[ResolvedRoof] = []
    curtain_walls: List[ResolvedCurtainWall] = []
    plates: List[ResolvedPlate] = []
    doors: List[ResolvedDoor] = []
    windows: List[ResolvedWindow] = []
    pipes: List[ResolvedPipeSegment] = []
    conduits: List[ResolvedCableCarrierSegment] = []
    ducts: List[ResolvedDuctSegment] = []
    sanitary_terminals: List[ResolvedSanitaryTerminal] = []
    waste_terminals: List[ResolvedWasteTerminal] = []
    distribution_boards: List[ResolvedDistributionBoard] = []
    light_fixtures: List[ResolvedLightFixture] = []
    switches: List[ResolvedSwitchingDevice] = []
    outlets: List[ResolvedOutlet] = []
    air_terminals: List[ResolvedAirTerminal] = []
    dampers: List[ResolvedDamper] = []
    flow_controllers: List[ResolvedFlowController] = []
    unitary_equipments: List[ResolvedUnitaryEquipment] = []
    custom_elements: List[ResolvedCustomElement] = []
    terminals: List[ResolvedTerminal] = []
    proxies: List[ResolvedProxy] = []
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
        gx1, gy1 = self.get_grid_xy(col.placement.grid)
        base_s = self.get_storey(col.placement.base_storey)
        top_s = self.get_storey(col.placement.top_storey)

        ob = col.placement.offset_base
        ot = col.placement.offset_top

        x1 = gx1 + ob[0]
        y1 = gy1 + ob[1]
        z1 = base_s.elevation + ob[2]

        if col.placement.top_grid:
            gx2, gy2 = self.get_grid_xy(col.placement.top_grid)
            x2 = gx2 + ot[0]
            y2 = gy2 + ot[1]
        else:
            x2 = gx1 + ot[0]
            y2 = gy1 + ot[1]

        z2 = top_s.elevation + ot[2]

        dx = x2 - x1
        dy = y2 - y1
        dz = z2 - z1

        euclidean_length = math.sqrt(dx * dx + dy * dy + dz * dz)

        if euclidean_length > 0:
            dir_3d = (dx / euclidean_length, dy / euclidean_length, dz / euclidean_length)
            pitch_angle = math.asin(dz / euclidean_length)
            yaw_angle = math.atan2(dy, dx)
        else:
            dir_3d = (0.0, 0.0, 1.0)
            pitch_angle = math.pi / 2.0
            yaw_angle = 0.0

        start_point = (x1, y1, z1)
        end_point = (x2, y2, z2)

        return ResolvedColumn(
            tag=col.tag,
            element=col,
            start_point=start_point,
            end_point=end_point,
            height=euclidean_length,
            direction_vector_3d=dir_3d,
            pitch_angle=pitch_angle,
            yaw_angle=yaw_angle,
            layer=derive_default_layer(col),
        )

    def resolve_beam(self, beam: IfcBeam) -> ResolvedBeam:
        x1, y1 = self.get_grid_xy(beam.placement.from_grid)
        x2, y2 = self.get_grid_xy(beam.placement.to_grid)
        from_st = self.get_storey(beam.placement.storey)

        z1 = from_st.elevation + beam.placement.offset_z

        if beam.placement.to_storey:
            to_st = self.get_storey(beam.placement.to_storey)
        else:
            to_st = from_st

        to_off_z = (
            beam.placement.to_offset_z
            if beam.placement.to_offset_z is not None
            else beam.placement.offset_z
        )
        z2 = to_st.elevation + to_off_z

        start_point = (x1, y1, z1)
        end_point = (x2, y2, z2)

        waypoints_3d: List[Tuple[float, float, float]] = []

        if beam.placement.waypoints and len(beam.placement.waypoints) >= 2:
            for wpt in beam.placement.waypoints:
                if wpt.x is not None and wpt.y is not None:
                    wx = float(wpt.x)
                    wy = float(wpt.y)
                    wz = float(wpt.z) if wpt.z is not None else (from_st.elevation + wpt.offset_z)
                elif wpt.grid:
                    wgx, wgy = wpt.grid
                    wx = self.axes_x[wgx] + wpt.offset_x
                    wy = self.axes_y[wgy] + wpt.offset_y
                    wz = from_st.elevation + wpt.offset_z
                else:
                    wx, wy, wz = (0.0, 0.0, from_st.elevation + wpt.offset_z)
                waypoints_3d.append((wx, wy, wz))
        elif beam.placement.curve:
            curve = beam.placement.curve
            c_height = float(curve.get("arch_height", curve.get("height", curve.get("apex_offset_z", 1.0))))
            n_segs = int(curve.get("segments", 16))

            waypoints_3d = []
            for i in range(n_segs + 1):
                t = i / float(n_segs)
                px = x1 + t * (x2 - x1)
                py = y1 + t * (y2 - y1)
                pz = z1 + t * (z2 - z1) + 4.0 * c_height * t * (1.0 - t)
                waypoints_3d.append((px, py, pz))
        else:
            waypoints_3d = [start_point, end_point]

        total_length = sum(
            math.dist(waypoints_3d[i], waypoints_3d[i + 1])
            for i in range(len(waypoints_3d) - 1)
        )

        dx = x2 - x1
        dy = y2 - y1
        dz = z2 - z1
        euclidean_dist = math.sqrt(dx * dx + dy * dy + dz * dz)

        if euclidean_dist > 0:
            dir_3d = (dx / euclidean_dist, dy / euclidean_dist, dz / euclidean_dist)
            pitch_angle = math.asin(dz / euclidean_dist)
            yaw_angle = math.atan2(dy, dx)
        else:
            dir_3d = (1.0, 0.0, 0.0)
            pitch_angle = 0.0
            yaw_angle = 0.0

        span_2d = math.hypot(dx, dy)
        if span_2d > 0:
            dir_2d = (dx / span_2d, dy / span_2d)
        else:
            dir_2d = (1.0, 0.0)

        rotation_angle = yaw_angle

        return ResolvedBeam(
            tag=beam.tag,
            element=beam,
            start_point=start_point,
            end_point=end_point,
            span_length=total_length,
            direction_vector=dir_2d,
            direction_vector_3d=dir_3d,
            rotation_angle=rotation_angle,
            pitch_angle=pitch_angle,
            yaw_angle=yaw_angle,
            waypoints=waypoints_3d,
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
                f_thick = child.frame_thickness if child.frame_thickness is not None else 0.05
                r_door = ResolvedDoor(
                    tag=child.tag,
                    element=child,
                    position=child_pos,
                    width=child.dimensions.width,
                    height=child.dimensions.height,
                    offset_distance=child.offset_distance,
                    sill_height=child.sill_height,
                    frame_thickness=f_thick,
                    frame_width=0.05,
                    panel_recess=0.015,
                    panel_thickness=0.035,
                    operation_type=child.operation_type,
                    flipped=child.flipped,
                    layer=derive_default_layer(child),
                )
                resolved_children.append(r_door)
                resolved_doors.append(r_door)
            elif isinstance(child, IfcWindow):
                f_thick = child.frame_thickness if child.frame_thickness is not None else 0.05
                r_win = ResolvedWindow(
                    tag=child.tag,
                    element=child,
                    position=child_pos,
                    width=child.dimensions.width,
                    height=child.dimensions.height,
                    offset_distance=child.offset_distance,
                    sill_height=child.sill_height,
                    frame_thickness=f_thick,
                    frame_width=0.05,
                    panel_recess=0.015,
                    panel_thickness=0.015,
                    operation_type=child.operation_type,
                    flipped=child.flipped,
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

        resolved_solid = None
        if custom.solid:
            if isinstance(custom.solid, SweptDiskSolid):
                world_pts: List[Tuple[float, float, float]] = []
                for pt in custom.solid.directrix:
                    world_pts.append((
                        world_pos[0] + pt[0],
                        world_pos[1] + pt[1],
                        world_pos[2] + pt[2],
                    ))
                tot_length = sum(
                    math.dist(world_pts[i], world_pts[i + 1])
                    for i in range(len(world_pts) - 1)
                )
                xs = [p[0] for p in world_pts]
                ys = [p[1] for p in world_pts]
                zs = [p[2] for p in world_pts]
                r = custom.solid.radius
                min_x, max_x = min(xs) - r, max(xs) + r
                min_y, max_y = min(ys) - r, max(ys) + r
                min_z, max_z = min(zs) - r, max(zs) + r

                c_x = sum(p[0] for p in world_pts) / len(world_pts)
                c_y = sum(p[1] for p in world_pts) / len(world_pts)
                c_z = sum(p[2] for p in world_pts) / len(world_pts)

                bbox = {
                    "min_x": min_x, "max_x": max_x,
                    "min_y": min_y, "max_y": max_y,
                    "min_z": min_z, "max_z": max_z,
                    "width": max_x - min_x,
                    "depth": max_y - min_y,
                    "height": max_z - min_z,
                }

                resolved_solid = ResolvedSweptDisk(
                    tag=custom.tag,
                    directrix=world_pts,
                    radius=custom.solid.radius,
                    inner_radius=custom.solid.inner_radius,
                    length=tot_length,
                    centroid=(c_x, c_y, c_z),
                    bounding_box=bbox,
                )

            elif isinstance(custom.solid, RevolvedAreaSolid):
                ax_pt = (
                    world_pos[0] + custom.solid.axis_point[0],
                    world_pos[1] + custom.solid.axis_point[1],
                    world_pos[2] + custom.solid.axis_point[2],
                )
                axis_dir = custom.solid.axis_direction
                dir_len = math.sqrt(sum(x * x for x in axis_dir))
                u_dir = (axis_dir[0] / dir_len, axis_dir[1] / dir_len, axis_dir[2] / dir_len)

                from debim.qto import compute_profile_geometry
                prof_area, prof_perim, p_width, p_depth = compute_profile_geometry(custom.solid.profile)

                v = (world_pos[0] - ax_pt[0], world_pos[1] - ax_pt[1], world_pos[2] - ax_pt[2])
                cross_x = v[1] * u_dir[2] - v[2] * u_dir[1]
                cross_y = v[2] * u_dir[0] - v[0] * u_dir[2]
                cross_z = v[0] * u_dir[1] - v[1] * u_dir[0]
                dist_to_axis = math.sqrt(cross_x**2 + cross_y**2 + cross_z**2)

                if dist_to_axis < 1e-9 and custom.solid.axis_point != (0.0, 0.0, 0.0):
                    v_ax = (-custom.solid.axis_point[0], -custom.solid.axis_point[1], -custom.solid.axis_point[2])
                    cx = v_ax[1] * u_dir[2] - v_ax[2] * u_dir[1]
                    cy = v_ax[2] * u_dir[0] - v_ax[0] * u_dir[2]
                    cz = v_ax[0] * u_dir[1] - v_ax[1] * u_dir[0]
                    dist_to_axis = math.sqrt(cx**2 + cy**2 + cz**2)

                sweep_r = dist_to_axis + max(p_width, p_depth) / 2.0
                bbox = {
                    "min_x": world_pos[0] - sweep_r,
                    "max_x": world_pos[0] + sweep_r,
                    "min_y": world_pos[1] - sweep_r,
                    "max_y": world_pos[1] + sweep_r,
                    "min_z": world_pos[2] - p_depth / 2.0,
                    "max_z": world_pos[2] + p_depth / 2.0,
                    "width": 2.0 * sweep_r,
                    "depth": 2.0 * sweep_r,
                    "height": max(p_width, p_depth),
                }

                resolved_solid = ResolvedRevolvedArea(
                    tag=custom.tag,
                    profile=custom.solid.profile,
                    axis_point=ax_pt,
                    axis_direction=u_dir,
                    revolution_angle=custom.solid.revolution_angle,
                    centroid=world_pos,
                    bounding_box=bbox,
                    distance_to_axis=dist_to_axis,
                    profile_area=prof_area,
                    profile_perimeter=prof_perim,
                )

        dims = custom.dimensions
        if dims is None and resolved_solid is not None:
            dims = Dimensions(
                width=resolved_solid.bounding_box["width"],
                depth=resolved_solid.bounding_box["depth"],
                height=resolved_solid.bounding_box["height"],
            )

        return ResolvedCustomElement(
            tag=custom.tag,
            element=custom,
            position=world_pos,
            rotation=rot,
            dimensions=dims,
            resolved_solid=resolved_solid,
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

        # Resolve voids if present
        resolved_voids_3d: List[List[Tuple[float, float, float]]] = []
        voids_area_total = 0.0
        if getattr(slab.placement, "voids", None):
            for vloop in slab.placement.voids:
                vpts_2d: List[Tuple[float, float]] = []
                vpts_3d: List[Tuple[float, float, float]] = []
                for grid_pt in vloop:
                    vx, vy = self.get_grid_xy(grid_pt)
                    vpts_2d.append((vx, vy))
                    vpts_3d.append((vx, vy, z))
                nv = len(vpts_2d)
                if nv >= 3:
                    va = 0.0
                    for i in range(nv):
                        j = (i + 1) % nv
                        va += vpts_2d[i][0] * vpts_2d[j][1]
                        va -= vpts_2d[j][0] * vpts_2d[i][1]
                    voids_area_total += abs(va) / 2.0
                    resolved_voids_3d.append(vpts_3d)

        net_area = max(0.0, area - voids_area_total)

        return ResolvedSlab(
            tag=slab.tag,
            element=slab,
            polygon=poly_3d,
            thickness=slab.thickness,
            area=net_area,
            center=(cx, cy, z),
            layer=derive_default_layer(slab),
            voids=resolved_voids_3d,
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
                signed_area = 0.0
                for i in range(n):
                    j = (i + 1) % n
                    signed_area += pts_2d[i][0] * pts_2d[j][1]
                    signed_area -= pts_2d[j][0] * pts_2d[i][1]
                    dx = pts_2d[j][0] - pts_2d[i][0]
                    dy = pts_2d[j][1] - pts_2d[i][1]
                    calc_perimeter += math.sqrt(dx * dx + dy * dy)
                signed_area = signed_area / 2.0
                calc_area = abs(signed_area)

                if covering.covering_type == "CEILING" and signed_area > 0:
                    pts_2d.reverse()
                    poly_3d.reverse()
            
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

    def resolve_stair_flight(self, flight: IfcStairFlight) -> ResolvedStairFlight:
        from_st = self.get_storey(flight.placement.from_storey)
        to_st = self.get_storey(flight.placement.to_storey)

        z_bottom = from_st.elevation + flight.placement.offset_z
        z_top = to_st.elevation
        rise_height = z_top - z_bottom

        gx, gy = self.get_grid_xy(flight.placement.grid_anchor)
        base_x = gx + flight.placement.offset_x
        base_y = gy + flight.placement.offset_y

        w = flight.flight_width
        waist_t = flight.waist_thickness

        riser = flight.riser_height
        tread = flight.tread_length

        n_risers = flight.number_of_risers or max(1, int(round(rise_height / riser)))
        run_length = (n_risers - 1) * tread if flight.number_of_treads is None else flight.number_of_treads * tread
        if run_length == 0:
            run_length = n_risers * tread

        actual_riser = rise_height / n_risers
        slope_length = math.hypot(run_length, rise_height)

        orient = flight.placement.orientation
        if orient == "+Y":
            p_start = (base_x, base_y, z_bottom)
            p_end = (base_x, base_y + run_length, z_top)
        elif orient == "-Y":
            p_start = (base_x, base_y, z_bottom)
            p_end = (base_x, base_y - run_length, z_top)
        elif orient == "-X":
            p_start = (base_x, base_y, z_bottom)
            p_end = (base_x - run_length, base_y, z_top)
        else:  # +X
            p_start = (base_x, base_y, z_bottom)
            p_end = (base_x + run_length, base_y, z_top)

        f_steps: List[ResolvedStairStep] = []
        for i in range(n_risers):
            if orient == "+Y":
                scx = base_x + w / 2.0
                scy = base_y + i * tread + tread / 2.0
            elif orient == "-Y":
                scx = base_x + w / 2.0
                scy = base_y - (i * tread + tread / 2.0)
            elif orient == "-X":
                scx = base_x - (i * tread + tread / 2.0)
                scy = base_y + w / 2.0
            else:  # +X
                scx = base_x + i * tread + tread / 2.0
                scy = base_y + w / 2.0
            scz = z_bottom + i * actual_riser + actual_riser / 2.0

            step = ResolvedStairStep(
                step_index=i + 1,
                flight_tag=flight.tag,
                position=(scx, scy, scz),
                width=w,
                tread=tread,
                riser=actual_riser,
            )
            f_steps.append(step)

        return ResolvedStairFlight(
            tag=flight.tag,
            start_point=p_start,
            end_point=p_end,
            width=w,
            waist_thickness=waist_t,
            run_length=run_length,
            rise_height=rise_height,
            slope_length=slope_length,
            n_risers=n_risers,
            tread=tread,
            riser=actual_riser,
            steps=f_steps,
            element=flight,
            layer=derive_default_layer(flight),
        )

    def resolve_ramp(self, ramp: IfcRamp) -> ResolvedRamp:
        x1, y1 = self.get_grid_xy(ramp.placement.from_grid)
        x2, y2 = self.get_grid_xy(ramp.placement.to_grid)
        from_st = self.get_storey(ramp.placement.storey)
        to_st = self.get_storey(ramp.placement.to_storey) if ramp.placement.to_storey else from_st

        z1 = from_st.elevation + ramp.placement.offset_z
        to_off_z = ramp.placement.to_offset_z if ramp.placement.to_offset_z is not None else ramp.placement.offset_z
        z2 = to_st.elevation + to_off_z

        dx = x2 - x1
        dy = y2 - y1
        dz = z2 - z1
        run_length_calc = math.hypot(dx, dy)

        if abs(dz) < 1e-4 and ramp.slope_percentage > 0 and run_length_calc > 0:
            dz = run_length_calc * (ramp.slope_percentage / 100.0)
            z2 = z1 + dz

        start_point = (x1, y1, z1)
        end_point = (x2, y2, z2)

        rise_height = dz
        run_length = ramp.ramp_length if ramp.ramp_length is not None else run_length_calc
        slope_length = math.sqrt(run_length_calc * run_length_calc + rise_height * rise_height)
        slope_pct = (abs(rise_height) / run_length_calc * 100.0) if run_length_calc > 0 else ramp.slope_percentage

        if slope_length > 0:
            dir_3d = (dx / slope_length, dy / slope_length, dz / slope_length)
            pitch_angle = math.asin(dz / slope_length)
            yaw_angle = math.atan2(dy, dx)
        else:
            dir_3d = (1.0, 0.0, 0.0)
            pitch_angle = 0.0
            yaw_angle = 0.0

        w = ramp.ramp_width
        t = ramp.slab_thickness
        conc_vol = w * slope_length * t
        formwork = (w * slope_length) + (2.0 * slope_length * t)

        waypoints = [start_point, end_point]

        return ResolvedRamp(
            tag=ramp.tag,
            element=ramp,
            start_point=start_point,
            end_point=end_point,
            width=w,
            slab_thickness=t,
            run_length=run_length_calc,
            rise_height=rise_height,
            slope_length=slope_length,
            slope_percentage=slope_pct,
            direction_vector_3d=dir_3d,
            pitch_angle=pitch_angle,
            yaw_angle=yaw_angle,
            waypoints=waypoints,
            landing_length=ramp.landing_length,
            concrete_volume=conc_vol,
            formwork_area=formwork,
            layer=derive_default_layer(ramp),
        )

    def resolve_railing(self, railing: IfcRailing) -> ResolvedRailing:
        z_base = self.get_storey(railing.placement.storey).elevation

        waypoints: List[Tuple[float, float, float]] = []

        if railing.placement.path and len(railing.placement.path) >= 2:
            for pt in railing.placement.path:
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
            gx1, gy1 = railing.placement.from_grid or ("1", "A")
            gx2, gy2 = railing.placement.to_grid or ("1", "A")
            fo = railing.placement.from_offset
            to = railing.placement.to_offset
            p1 = (self.axes_x[gx1] + fo[0], self.axes_y[gy1] + fo[1], z_base + fo[2])
            p2 = (self.axes_x[gx2] + to[0], self.axes_y[gy2] + to[1], z_base + to[2])
            waypoints = [p1, p2]

        rh = railing.height
        post_sp = railing.post_spacing if railing.post_spacing > 0 else 1.50

        posts: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []
        rails: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []

        total_path_len = 0.0
        for i in range(len(waypoints) - 1):
            wp1 = waypoints[i]
            wp2 = waypoints[i + 1]
            seg_len = math.dist(wp1, wp2)
            total_path_len += seg_len

            r_start = (wp1[0], wp1[1], wp1[2] + rh)
            r_end = (wp2[0], wp2[1], wp2[2] + rh)
            rails.append((r_start, r_end))

            n_posts = max(1, int(round(seg_len / post_sp)))
            for k in range(n_posts if i < len(waypoints) - 2 else n_posts + 1):
                t_val = k / float(n_posts) if n_posts > 0 else 0.0
                px = wp1[0] + t_val * (wp2[0] - wp1[0])
                py = wp1[1] + t_val * (wp2[1] - wp1[1])
                pz = wp1[2] + t_val * (wp2[2] - wp1[2])
                p_base = (px, py, pz)
                p_top = (px, py, pz + rh)
                posts.append((p_base, p_top))

        return ResolvedRailing(
            tag=railing.tag,
            element=railing,
            predefined_type=railing.predefined_type,
            height=rh,
            post_spacing=post_sp,
            waypoints=waypoints,
            posts=posts,
            rails=rails,
            total_length=total_path_len,
            post_count=len(posts),
            layer=derive_default_layer(railing),
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

        elif stair.stair_type == "SPIRAL":
            landing_edge_beams = []
            landing_poly = None
            landing_area = 0.0
            landing_t = 0.0

            r_in = stair.inner_radius if stair.inner_radius is not None else 0.50
            r_out = r_in + w
            r_mid = (r_in + r_out) / 2.0

            n_risers = (
                stair.steps.n_risers
                if (stair.steps and stair.steps.n_risers)
                else max(1, int(round(total_height / riser)))
            )
            actual_riser = total_height / n_risers

            # Calculate angular span
            if stair.total_angle is not None:
                tot_angle_deg = stair.total_angle
            else:
                # Based on standard tread at centerline
                tot_angle_deg = math.degrees((n_risers * tread) / r_mid)

            tot_angle_rad = math.radians(tot_angle_deg)
            d_theta = tot_angle_rad / n_risers
            is_ccw = (stair.direction != "CW")
            dir_sign = 1.0 if is_ccw else -1.0

            # Initial angle from orientation
            orientation_map = {
                "+X": 0.0,
                "+Y": math.pi / 2.0,
                "-X": math.pi,
                "-Y": 3.0 * math.pi / 2.0,
            }
            theta_0 = orientation_map.get(stair.placement.orientation, 0.0)

            f1_steps = []
            for i in range(n_risers):
                th_start = theta_0 + dir_sign * i * d_theta
                th_end = th_start + dir_sign * d_theta
                th_mid = (th_start + th_end) / 2.0
                step_z = z_bottom + i * actual_riser

                scx = base_x + r_mid * math.cos(th_mid)
                scy = base_y + r_mid * math.sin(th_mid)
                scz = step_z + actual_riser / 2.0

                # 4 boundary corners of wedge tread at upper surface
                p1 = (base_x + r_in * math.cos(th_start), base_y + r_in * math.sin(th_start), step_z + actual_riser)
                p2 = (base_x + r_out * math.cos(th_start), base_y + r_out * math.sin(th_start), step_z + actual_riser)
                p3 = (base_x + r_out * math.cos(th_end), base_y + r_out * math.sin(th_end), step_z + actual_riser)
                p4 = (base_x + r_in * math.cos(th_end), base_y + r_in * math.sin(th_end), step_z + actual_riser)

                # Tread at center line
                step_tread = r_mid * d_theta
                # Radial orientation pointing outward from spiral center
                step_rot = th_mid

                step = ResolvedStairStep(
                    step_index=i + 1,
                    flight_tag=f"{stair.tag}-F1",
                    position=(scx, scy, scz),
                    width=w,
                    tread=step_tread,
                    riser=actual_riser,
                    rotation=step_rot,
                    polygon=[p1, p2, p3, p4],
                )
                f1_steps.append(step)
                all_steps.append(step)

            # Helical stringers calculations
            arc_in_horiz = r_in * tot_angle_rad
            arc_out_horiz = r_out * tot_angle_rad
            len_in_true = math.hypot(arc_in_horiz, total_height)
            len_out_true = math.hypot(arc_out_horiz, total_height)

            p_start = (base_x + r_mid * math.cos(theta_0), base_y + r_mid * math.sin(theta_0), z_bottom)
            th_final = theta_0 + dir_sign * tot_angle_rad
            p_end = (base_x + r_mid * math.cos(th_final), base_y + r_mid * math.sin(th_final), z_top)

            f = ResolvedStairFlight(
                tag=f"{stair.tag}-F1",
                start_point=p_start,
                end_point=p_end,
                width=w,
                waist_thickness=waist_t,
                run_length=r_mid * tot_angle_rad,
                rise_height=total_height,
                slope_length=math.hypot(r_mid * tot_angle_rad, total_height),
                n_risers=n_risers,
                tread=r_mid * d_theta,
                riser=actual_riser,
                steps=f1_steps,
            )
            flights.append(f)

            # Stringers definition
            st_mat = (stair.stringer.material if stair.stringer else None) or stair.material
            st_w = stair.stringer.width if stair.stringer else 0.016
            st_d = stair.stringer.depth if stair.stringer else (waist_t if waist_t > 0.3 else 1.40)
            st_thick = stair.stringer.thickness if (stair.stringer and stair.stringer.thickness) else st_w

            # Sample 3D helical curve points for visualization & true path
            s_in_curve = []
            s_out_curve = []
            n_samples = max(20, n_risers * 2)
            for k in range(n_samples + 1):
                tk = k / float(n_samples)
                th_k = theta_0 + dir_sign * tk * tot_angle_rad
                zk = z_bottom + tk * total_height
                s_in_curve.append((base_x + r_in * math.cos(th_k), base_y + r_in * math.sin(th_k), zk))
                s_out_curve.append((base_x + r_out * math.cos(th_k), base_y + r_out * math.sin(th_k), zk))

            # Inner stringer
            s_in_start = s_in_curve[0]
            s_in_end = s_in_curve[-1]
            stringers.append(ResolvedStairStringer(
                tag=f"{stair.tag}-Stringer-Inner",
                start_point=s_in_start,
                end_point=s_in_end,
                width=st_thick,
                depth=st_d,
                length=len_in_true,
                material=st_mat,
                curve_points=s_in_curve,
            ))

            # Outer stringer
            s_out_start = s_out_curve[0]
            s_out_end = s_out_curve[-1]
            stringers.append(ResolvedStairStringer(
                tag=f"{stair.tag}-Stringer-Outer",
                start_point=s_out_start,
                end_point=s_out_end,
                width=st_thick,
                depth=st_d,
                length=len_out_true,
                material=st_mat,
                curve_points=s_out_curve,
            ))

            # Railing for spiral
            if stair.railing:
                rh = stair.railing.height
                r_rad = r_out - 0.05 if stair.railing.side in ("OUTER", "BOTH") else r_in + 0.05
                r_posts = []
                r_rails = []
                post_indices = [0] + list(range(3, n_risers - 1, 3)) + [n_risers - 1]
                prev_top = None
                for idx in post_indices:
                    th_p = theta_0 + dir_sign * (idx + 0.5) * d_theta
                    pz = z_bottom + idx * actual_riser + actual_riser
                    p_base = (base_x + r_rad * math.cos(th_p), base_y + r_rad * math.sin(th_p), pz)
                    p_top = (p_base[0], p_base[1], pz + rh)
                    r_posts.append((p_base, p_top))
                    if prev_top:
                        r_rails.append((prev_top, p_top))
                    prev_top = p_top
                r_segs = r_posts + r_rails
                r_len = sum(math.dist(s[0], s[1]) for s in r_segs)
                resolved_railing = ResolvedStairRailing(
                    tag=f"{stair.tag}-Railing",
                    posts=r_posts,
                    rails=r_rails,
                    segments=r_segs,
                    total_length=r_len,
                    height=rh,
                    railing_type=stair.railing.type,
                    layout=stair.railing.layout,
                )

            # Material & QTO calculations
            is_steel = any(kw in (st_mat or "").upper() for kw in ["STEEL", "SS400", "SM400", "A36", "METAL"]) or any(kw in stair.material.upper() for kw in ["STEEL", "SS400", "SM400", "A36", "METAL"])

            total_tread_area_val = n_risers * 0.5 * d_theta * (r_out**2 - r_in**2)
            tot_stringer_wt = 0.0
            tot_treads_wt = 0.0
            tot_base_plates_wt = 0.0
            tot_steel_wt = 0.0

            if is_steel:
                # Stringer steel plates (Inner + Outer)
                vol_stringers = (len_in_true * st_d * st_thick) + (len_out_true * st_d * st_thick)
                tot_stringer_wt = vol_stringers * 7850.0

                # Treads steel (checkered plate)
                tread_plate_t = (
                    stair.steps.plate_thickness
                    if (stair.steps and stair.steps.plate_thickness)
                    else 0.0032
                )
                tot_treads_wt = total_tread_area_val * tread_plate_t * 7850.0

                # Base plates
                if stair.stringer and stair.stringer.base_plate_thickness:
                    bp_t = stair.stringer.base_plate_thickness
                    bp_w = stair.stringer.base_plate_width or 0.30
                    bp_l = stair.stringer.base_plate_length or 2.50
                    bp_cnt = stair.stringer.base_plate_count or 2
                    tot_base_plates_wt = bp_l * bp_w * bp_t * 7850.0 * bp_cnt

                tot_steel_wt = tot_stringer_wt + tot_treads_wt + tot_base_plates_wt
                tot_conc_vol = 0.0
                tot_formwork = 0.0
            else:
                # Reinforced concrete spiral stair
                vol_waist = total_tread_area_val * waist_t
                vol_steps = n_risers * 0.5 * (d_theta * r_mid * w) * actual_riser
                tot_conc_vol = vol_waist + vol_steps
                tot_formwork = total_tread_area_val + (n_risers * actual_riser * w) + (len_in_true + len_out_true) * waist_t

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
        if stair.railing and stair.stair_type != "SPIRAL":
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
            total_tread_finish_area=total_tread_area_val if stair.stair_type == "SPIRAL" else tot_tread_area,
            total_riser_finish_area=tot_riser_area,
            total_concrete_volume=tot_conc_vol,
            total_formwork_area=tot_formwork,
            total_steel_weight=tot_steel_wt if stair.stair_type == "SPIRAL" else 0.0,
            inner_helical_length=len_in_true if stair.stair_type == "SPIRAL" else 0.0,
            outer_helical_length=len_out_true if stair.stair_type == "SPIRAL" else 0.0,
            treads_steel_weight=tot_treads_wt if stair.stair_type == "SPIRAL" else 0.0,
            stringers_steel_weight=tot_stringer_wt if stair.stair_type == "SPIRAL" else 0.0,
            base_plates_steel_weight=tot_base_plates_wt if stair.stair_type == "SPIRAL" else 0.0,
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
                f_thick = child.frame_thickness if child.frame_thickness is not None else 0.05
                r_door = ResolvedDoor(
                    tag=child.tag,
                    element=child,
                    position=pos,
                    width=child.dimensions.width,
                    height=child.dimensions.height,
                    offset_distance=child.offset_distance,
                    sill_height=child.sill_height,
                    frame_thickness=f_thick,
                    frame_width=0.05,
                    panel_recess=0.015,
                    panel_thickness=0.035,
                    layer=derive_default_layer(child),
                )
                resolved_children.append(r_door)
            elif isinstance(child, IfcWindow):
                f_thick = child.frame_thickness if child.frame_thickness is not None else 0.05
                r_win = ResolvedWindow(
                    tag=child.tag,
                    element=child,
                    position=pos,
                    width=child.dimensions.width,
                    height=child.dimensions.height,
                    offset_distance=child.offset_distance,
                    sill_height=child.sill_height,
                    frame_thickness=f_thick,
                    frame_width=0.05,
                    panel_recess=0.015,
                    panel_thickness=0.015,
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

    def resolve_curtain_wall(self, cw: IfcCurtainWall) -> ResolvedCurtainWall:
        x1, y1 = self.get_grid_xy(cw.placement.from_grid)
        x2, y2 = self.get_grid_xy(cw.placement.to_grid)
        storey = self.get_storey(cw.placement.storey)

        z = storey.elevation + cw.placement.offset_z
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        height = cw.height

        start_point = (x1, y1, z)
        end_point = (x2, y2, z)

        gross_area = length * height

        # Mullion grid resolution
        sp_h = cw.mullion_spacing_h if cw.mullion_spacing_h > 0 else 1.20
        sp_v = cw.mullion_spacing_v if cw.mullion_spacing_v > 0 else 1.50
        mw = cw.mullion_width

        n_bays_h = max(1, int(round(length / sp_h))) if length > 0 else 1
        n_bays_v = max(1, int(round(height / sp_v))) if height > 0 else 1

        ux = dx / length if length > 0 else 1.0
        uy = dy / length if length > 0 else 0.0

        grid_lines: List[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = []
        mullion_len = 0.0

        # Vertical mullions (along length)
        for i in range(n_bays_h + 1):
            dist = i * (length / n_bays_h) if n_bays_h > 0 else 0.0
            mx = x1 + ux * dist
            my = y1 + uy * dist
            p_bot = (mx, my, z)
            p_top = (mx, my, z + height)
            grid_lines.append((p_bot, p_top))
            mullion_len += height

        # Horizontal transoms
        for j in range(n_bays_v + 1):
            hz = z + j * (height / n_bays_v) if n_bays_v > 0 else z
            p_s = (x1, y1, hz)
            p_e = (x2, y2, hz)
            grid_lines.append((p_s, p_e))
            mullion_len += length

        panel_count = n_bays_h * n_bays_v
        # Net glass area deducting mullion widths
        effective_w = max(0.01, (length / n_bays_h) - mw)
        effective_h = max(0.01, (height / n_bays_v) - mw)
        net_glass = panel_count * (effective_w * effective_h)

        return ResolvedCurtainWall(
            tag=cw.tag,
            element=cw,
            start_point=start_point,
            end_point=end_point,
            length=length,
            height=height,
            gross_facade_area=gross_area,
            net_glass_area=net_glass,
            mullion_length=mullion_len,
            glass_panels_count=panel_count,
            mullion_grid_lines=grid_lines,
            layer=derive_default_layer(cw),
        )

    def resolve_plate(self, plate: IfcPlate) -> ResolvedPlate:
        storey = self.get_storey(plate.placement.storey)
        z_base = storey.elevation + plate.placement.offset_z

        poly_3d: List[Tuple[float, float, float]] = []
        area = 0.0
        width = plate.width or 1.0
        depth = plate.depth or 1.0
        thick = plate.thickness

        if plate.placement.boundary:
            pts_2d: List[Tuple[float, float]] = []
            for grid_pt in plate.placement.boundary:
                x, y = self.get_grid_xy(grid_pt)
                pts_2d.append((x, y))
                poly_3d.append((x, y, z_base))

            n = len(pts_2d)
            if n >= 3:
                for i in range(n):
                    j = (i + 1) % n
                    area += pts_2d[i][0] * pts_2d[j][1]
                    area -= pts_2d[j][0] * pts_2d[i][1]
                area = abs(area) / 2.0
                xs = [p[0] for p in pts_2d]
                ys = [p[1] for p in pts_2d]
                width = max(xs) - min(xs)
                depth = max(ys) - min(ys)
                cx = sum(xs) / n
                cy = sum(ys) / n
                cz = z_base
            else:
                cx, cy, cz = 0.0, 0.0, z_base
        elif plate.placement.boundary_points:
            bpts = plate.placement.boundary_points
            gx, gy = (0.0, 0.0)
            if plate.placement.grid:
                gx, gy = self.get_grid_xy(plate.placement.grid)
            gx += plate.placement.offset_x
            gy += plate.placement.offset_y

            for lx, ly in bpts:
                poly_3d.append((gx + lx, gy + ly, z_base))

            n = len(bpts)
            if n >= 3:
                for i in range(n):
                    j = (i + 1) % n
                    area += bpts[i][0] * bpts[j][1]
                    area -= bpts[j][0] * bpts[i][1]
                area = abs(area) / 2.0
                xs = [p[0] for p in bpts]
                ys = [p[1] for p in bpts]
                width = max(xs) - min(xs)
                depth = max(ys) - min(ys)
                cx = gx + sum(xs) / n
                cy = gy + sum(ys) / n
                cz = z_base
            else:
                cx, cy, cz = gx, gy, z_base
        else:
            gx, gy = (0.0, 0.0)
            if plate.placement.grid:
                gx, gy = self.get_grid_xy(plate.placement.grid)
            cx = gx + plate.placement.offset_x
            cy = gy + plate.placement.offset_y
            cz = z_base
            area = width * depth

        volume = area * thick
        density = plate.density_kg_m3
        if density is None:
            # Default material density if omitted
            mat_low = (plate.material or "").lower()
            if any(k in mat_low for k in ["steel", "ss400", "metal", "iron"]):
                density = 7850.0
            elif "aluminum" in mat_low or "aluminium" in mat_low:
                density = 2700.0
            elif "glass" in mat_low:
                density = 2500.0
            else:
                density = 7850.0 if plate.predefined_type in ("FLANGE_PLATE", "BASE_PLATE") else 2500.0

        weight = volume * density
        rot = plate.placement.rotation if plate.placement.rotation else (0.0, 0.0, 0.0)

        return ResolvedPlate(
            tag=plate.tag,
            element=plate,
            position=(cx, cy, cz),
            width=width,
            depth=depth,
            thickness=thick,
            area=area,
            volume=volume,
            weight=weight,
            polygon=poly_3d,
            rotation=rot,
            layer=derive_default_layer(plate),
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
            predefined_type=term.predefined_type or "USERDEFINED",
            position=r_term.position,
            rotation=r_term.rotation_angle,
            rotation_angle=r_term.rotation_angle,
            dimensions=dims,
            color=color,
            layer=derive_default_layer(term),
        )

    def resolve_waste_terminal(self, term: IfcWasteTerminal) -> ResolvedWasteTerminal:
        r_term = self.resolve_terminal(term)
        dims = (
            (term.dimensions.width, term.dimensions.depth, term.dimensions.height)
            if term.dimensions
            else (term.width, term.depth, term.height)
            if (term.width or term.depth or term.height)
            else DEFAULT_TERMINAL_DIMENSIONS.get(term.terminal_type, (0.20, 0.20, 0.10))
        )
        color = DEFAULT_TERMINAL_COLORS.get(term.terminal_type, "#64748B")
        return ResolvedWasteTerminal(
            tag=term.tag,
            element=term,
            terminal_type=term.terminal_type,
            predefined_type=term.predefined_type or "USERDEFINED",
            position=r_term.position,
            rotation=r_term.rotation_angle,
            rotation_angle=r_term.rotation_angle,
            dimensions=dims,
            color=color,
            layer=derive_default_layer(term),
        )

    def resolve_distribution_board(
        self, board: Union[IfcDistributionBoard, IfcElectricDistributionBoard]
    ) -> ResolvedDistributionBoard:
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
            voltage=board.voltage,
            phases=board.phases,
            main_breaker_rating_amperes=board.main_breaker_rating_amperes,
            poles_count=board.poles_count or board.circuits_count,
            predefined_type=board.predefined_type or "CONSUMERUNIT",
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
        watt_val = fixture.power_watts or fixture.wattage or 12.0
        return ResolvedLightFixture(
            tag=fixture.tag,
            element=fixture,
            fixture_type=fixture.fixture_type,
            position=r_term.position,
            rotation=r_term.rotation_angle,
            rotation_angle=r_term.rotation_angle,
            dimensions=dims,
            color=color,
            wattage=watt_val,
            power_watts=watt_val,
            luminous_flux_lumens=fixture.luminous_flux_lumens,
            color_temperature_kelvin=fixture.color_temperature_kelvin,
            predefined_type=fixture.predefined_type or "POINTSOURCE",
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
            predefined_type=out.predefined_type or "POWEROUTLET",
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
            else DEFAULT_TERMINAL_DIMENSIONS.get(term.terminal_type, (0.60, 0.60, 0.10))
        )
        color = DEFAULT_TERMINAL_COLORS.get(term.terminal_type, "#0284C7")
        return ResolvedAirTerminal(
            tag=term.tag,
            element=term,
            terminal_type=term.terminal_type,
            predefined_type=term.predefined_type or "DIFFUSER",
            position=r_term.position,
            rotation=r_term.rotation_angle,
            rotation_angle=r_term.rotation_angle,
            dimensions=dims,
            color=color,
            flow_rate_cfm=term.flow_rate_cfm,
            air_flow_rate_m3h=term.air_flow_rate_m3h,
            face_area_m2=term.face_area_m2 or (dims[0] * dims[1]),
            neck_width=term.neck_width,
            neck_depth=term.neck_depth,
            neck_diameter=term.neck_diameter,
            throw_distance_m=term.throw_distance_m,
            layer=derive_default_layer(term),
        )

    def resolve_damper(self, damper: IfcDamper) -> ResolvedDamper:
        r_term = self.resolve_terminal(damper)
        dims = (
            (damper.dimensions.width, damper.dimensions.depth, damper.dimensions.height)
            if damper.dimensions
            else (damper.width, damper.depth, damper.height)
            if (damper.width or damper.depth or damper.height)
            else DEFAULT_TERMINAL_DIMENSIONS.get(damper.damper_type, (0.40, 0.40, 0.25))
        )
        color = DEFAULT_TERMINAL_COLORS.get(damper.damper_type, "#64748B")
        return ResolvedDamper(
            tag=damper.tag,
            element=damper,
            damper_type=damper.damper_type,
            predefined_type=damper.predefined_type or "FIREDAMPER",
            position=r_term.position,
            rotation=r_term.rotation_angle,
            rotation_angle=r_term.rotation_angle,
            dimensions=dims,
            color=color,
            duct_width=damper.duct_width or dims[0],
            duct_depth=damper.duct_depth or dims[1],
            duct_diameter=damper.duct_diameter,
            actuator_type=damper.actuator_type,
            layer=derive_default_layer(damper),
        )

    def resolve_flow_controller(self, controller: IfcFlowController) -> ResolvedFlowController:
        r_term = self.resolve_terminal(controller)
        dims = (
            (controller.dimensions.width, controller.dimensions.depth, controller.dimensions.height)
            if controller.dimensions
            else (controller.width, controller.depth, controller.height)
            if (controller.width or controller.depth or controller.height)
            else DEFAULT_TERMINAL_DIMENSIONS.get(controller.controller_type, (0.80, 0.50, 0.40))
        )
        color = DEFAULT_TERMINAL_COLORS.get(controller.controller_type, "#475569")
        return ResolvedFlowController(
            tag=controller.tag,
            element=controller,
            controller_type=controller.controller_type,
            predefined_type=controller.predefined_type or "AIR_CONTROLLER",
            position=r_term.position,
            rotation=r_term.rotation_angle,
            rotation_angle=r_term.rotation_angle,
            dimensions=dims,
            color=color,
            air_flow_rate_m3h=controller.air_flow_rate_m3h,
            duct_width=controller.duct_width or dims[0],
            duct_depth=controller.duct_depth or dims[1],
            duct_diameter=controller.duct_diameter,
            layer=derive_default_layer(controller),
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
            elif isinstance(elem, IfcStairFlight):
                r_flight = self.resolve_stair_flight(elem)
                resolved_manifest.stair_flights.append(r_flight)
                resolved_manifest.elements.append(r_flight)
            elif isinstance(elem, IfcRamp):
                r_ramp = self.resolve_ramp(elem)
                resolved_manifest.ramps.append(r_ramp)
                resolved_manifest.elements.append(r_ramp)
            elif isinstance(elem, IfcRailing):
                r_railing = self.resolve_railing(elem)
                resolved_manifest.railings.append(r_railing)
                resolved_manifest.elements.append(r_railing)
            elif isinstance(elem, IfcRoof):
                r_roof = self.resolve_roof(elem)
                resolved_manifest.roofs.append(r_roof)
                for child in r_roof.children:
                    if isinstance(child, ResolvedDoor):
                        resolved_manifest.doors.append(child)
                        resolved_manifest.elements.append(child)
                    elif isinstance(child, ResolvedWindow):
                        resolved_manifest.windows.append(child)
                        resolved_manifest.elements.append(child)
                resolved_manifest.elements.append(r_roof)
            elif isinstance(elem, IfcCurtainWall):
                r_cw = self.resolve_curtain_wall(elem)
                resolved_manifest.curtain_walls.append(r_cw)
                resolved_manifest.elements.append(r_cw)
            elif isinstance(elem, IfcPlate):
                r_plate = self.resolve_plate(elem)
                resolved_manifest.plates.append(r_plate)
                resolved_manifest.elements.append(r_plate)
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
                resolved_manifest.elements.extend(doors)
                resolved_manifest.elements.extend(windows)
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
            elif isinstance(elem, IfcWasteTerminal):
                r_term = self.resolve_waste_terminal(elem)
                resolved_manifest.waste_terminals.append(r_term)
                resolved_manifest.elements.append(r_term)
                resolved_manifest.terminals.append(self.resolve_terminal(elem))
            elif isinstance(elem, (IfcDistributionBoard, IfcElectricDistributionBoard)):
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
            elif isinstance(elem, IfcDamper):
                r_damper = self.resolve_damper(elem)
                resolved_manifest.dampers.append(r_damper)
                resolved_manifest.elements.append(r_damper)
                resolved_manifest.terminals.append(self.resolve_terminal(elem))
            elif isinstance(elem, IfcFlowController):
                r_fc = self.resolve_flow_controller(elem)
                resolved_manifest.flow_controllers.append(r_fc)
                resolved_manifest.elements.append(r_fc)
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
            elif isinstance(elem, IfcBuildingElementProxy):
                r_proxy = self.resolve_proxy(elem)
                resolved_manifest.proxies.append(r_proxy)
                resolved_manifest.elements.append(r_proxy)

        for proxy_elem in self.manifest.proxies:
            r_proxy = self.resolve_proxy(proxy_elem)
            resolved_manifest.proxies.append(r_proxy)
            resolved_manifest.elements.append(r_proxy)

        return resolved_manifest

    def resolve_proxy(self, proxy: IfcBuildingElementProxy) -> ResolvedProxy:
        storey_id = proxy.placement.storey
        storey = None
        if storey_id and storey_id in self.storeys:
            storey = self.storeys[storey_id]
        elif self.storeys:
            storey = next(iter(self.storeys.values()))

        st_elev = storey.elevation if storey else 0.0

        px, py, pz = 0.0, 0.0, 0.0
        if proxy.placement.position:
            px, py, pz = proxy.placement.position
        elif proxy.placement.grid:
            gx, gy = self.get_grid_xy(proxy.placement.grid)
            off_x = proxy.placement.offset_x + (proxy.placement.offset[0] if proxy.placement.offset else 0.0)
            off_y = proxy.placement.offset_y + (proxy.placement.offset[1] if proxy.placement.offset else 0.0)
            off_z = proxy.placement.offset_z + (proxy.placement.offset[2] if proxy.placement.offset else 0.0)
            px = gx + off_x
            py = gy + off_y
            pz = off_z
        elif proxy.placement.offset:
            px, py, pz = proxy.placement.offset

        world_pos = (px, py, st_elev + pz)

        dims_obj = proxy.get_resolved_dimensions()
        w = dims_obj.width
        d = dims_obj.depth if dims_obj.depth is not None else w
        h = dims_obj.height
        vol = w * d * h
        footprint = w * d

        bbox = {
            "min_x": world_pos[0] - w / 2.0, "max_x": world_pos[0] + w / 2.0,
            "min_y": world_pos[1] - d / 2.0, "max_y": world_pos[1] + d / 2.0,
            "min_z": world_pos[2], "max_z": world_pos[2] + h,
            "width": w, "depth": d, "height": h,
            "volume": vol, "footprint_area": footprint,
        }

        rot = proxy.placement.rotation if proxy.placement.rotation else (0.0, 0.0, 0.0)
        ifc_cls = proxy.ifc_class or proxy.class_ or "IfcBuildingElementProxy"

        return ResolvedProxy(
            tag=proxy.tag,
            element=proxy,
            ifc_class=ifc_cls,
            predefined_type=proxy.predefined_type,
            position=world_pos,
            rotation=rot,
            dimensions=(w, d, h),
            bounding_box=bbox,
            properties=proxy.properties or {},
            color="#8B5CF6",
            layer=derive_default_layer(proxy),
        )


def resolve_manifest(manifest: ProjectManifest) -> ResolvedManifest:
    """Resolve a ProjectManifest into 3D world coordinates and geometric dimensions."""
    resolver = SpatialResolver(manifest)
    return resolver.resolve()
