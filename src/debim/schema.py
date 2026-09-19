"""
Pydantic v2 data models for project.yaml schema and manifest validation logic.
"""

from pathlib import Path
from typing import Annotated, Dict, List, Literal, Optional, Tuple, Union
import yaml
from pydantic import BaseModel, Field, RootModel, field_validator, model_validator


class Units(BaseModel):
    length: str = "METER"
    area: str = "SQUARE_METER"
    volume: str = "CUBIC_METER"


class ProjectInfo(BaseModel):
    id: str
    name: str
    units: Units = Field(default_factory=Units)


class Storey(BaseModel):
    id: str
    name: str
    elevation: float
    height: float


class SpatialStructure(BaseModel):
    storeys: List[Storey]


class Grids(BaseModel):
    axes_x: Dict[str, float]
    axes_y: Dict[str, float]

    @field_validator("axes_x", "axes_y", mode="before")
    @classmethod
    def convert_keys_to_string(cls, v):
        if isinstance(v, dict):
            return {str(k): float(val) for k, val in v.items()}
        return v


class BoxProfile(BaseModel):
    shape: Literal["BOX"]
    width: float
    depth: float


# Column placement & element
class ColumnPlacement(BaseModel):
    grid: Tuple[str, str]
    base_storey: str
    top_storey: str

    @field_validator("grid", mode="before")
    @classmethod
    def convert_grid_items_to_str(cls, v):
        if isinstance(v, (list, tuple)):
            return tuple(str(x) for x in v)
        return v


class ColumnReinforcement(BaseModel):
    main: Optional[str] = None
    stirrups: Optional[str] = None


class IfcColumn(BaseModel):
    class_: Literal["IfcColumn"] = Field(alias="class")
    tag: str
    material: str
    profile: BoxProfile
    placement: ColumnPlacement
    reinforcement: Optional[ColumnReinforcement] = None


class FootingProfile(BaseModel):
    shape: Literal["BOX"] = "BOX"
    width: float
    depth: float
    thickness: float


class FootingPlacement(BaseModel):
    grid: Tuple[str, str]
    storey: str
    offset_z: float = 0.00

    @field_validator("grid", mode="before")
    @classmethod
    def convert_grid_items_to_str(cls, v):
        if isinstance(v, (list, tuple)):
            return tuple(str(x) for x in v)
        return v


class FootingReinforcement(BaseModel):
    mesh_x: Optional[str] = None
    mesh_y: Optional[str] = None


class PileProfile(BaseModel):
    shape: Literal["HEXAGONAL", "I_SHAPE", "CIRCULAR", "SQUARE"] = "HEXAGONAL"
    dimension: float  # Diameter, width, or depth (m)


class FootingPiles(BaseModel):
    count: int
    profile: Optional[PileProfile] = None
    length: float  # Length per pile (m)
    material: Optional[str] = None
    spacing: Optional[float] = None  # Spacing between piles if applicable (m)


class IfcFooting(BaseModel):
    class_: Literal["IfcFooting"] = Field(alias="class")
    tag: str
    material: str
    profile: FootingProfile
    placement: FootingPlacement
    reinforcement: Optional[FootingReinforcement] = None
    piles: Optional[FootingPiles] = None


# Beam placement & element
class BeamPlacement(BaseModel):
    from_grid: Tuple[str, str]
    to_grid: Tuple[str, str]
    storey: str
    offset_z: float = 0.00

    @field_validator("from_grid", "to_grid", mode="before")
    @classmethod
    def convert_grid_items_to_str(cls, v):
        if isinstance(v, (list, tuple)):
            return tuple(str(x) for x in v)
        return v


class BeamReinforcement(BaseModel):
    main_top: Optional[str] = None
    main_bottom: Optional[str] = None
    stirrups: Optional[str] = None


class IfcBeam(BaseModel):
    class_: Literal["IfcBeam"] = Field(alias="class")
    tag: str
    material: str
    profile: BoxProfile
    placement: BeamPlacement
    reinforcement: Optional[BeamReinforcement] = None


# Wall children (Doors / Windows)
class Dimensions(BaseModel):
    width: float
    height: float


class IfcDoor(BaseModel):
    class_: Literal["IfcDoor"] = Field(alias="class")
    tag: str
    dimensions: Dimensions
    offset_distance: float
    sill_height: float = 0.00


class IfcWindow(BaseModel):
    class_: Literal["IfcWindow"] = Field(alias="class")
    tag: str
    dimensions: Dimensions
    offset_distance: float
    sill_height: float = 0.00


WallChild = Annotated[Union[IfcDoor, IfcWindow], Field(discriminator="class_")]


# Wall placement & element
class WallPlacement(BaseModel):
    from_grid: Tuple[str, str]
    to_grid: Tuple[str, str]
    storey: str

    @field_validator("from_grid", "to_grid", mode="before")
    @classmethod
    def convert_grid_items_to_str(cls, v):
        if isinstance(v, (list, tuple)):
            return tuple(str(x) for x in v)
        return v


PlasterType = Literal["BOTH", "INTERIOR", "EXTERIOR", "NONE"]
WallFinishType = Literal["PAINT", "TILES", "NONE"]


class WallFinishesConfig(BaseModel):
    plaster: PlasterType = "BOTH"
    interior_finish: WallFinishType = "PAINT"
    exterior_finish: WallFinishType = "PAINT"
    tile_height: Optional[float] = None


class IfcWall(BaseModel):
    class_: Literal["IfcWall"] = Field(alias="class")
    tag: str
    material: str
    thickness: float
    height: float
    placement: WallPlacement
    children: List[WallChild] = Field(default_factory=list)
    finishes: Optional[WallFinishesConfig] = None


# Slab placement & element
class SlabPlacement(BaseModel):
    boundary: List[Tuple[str, str]]  # List of grid intersections forming polygon, e.g. [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]]
    storey: str
    offset_z: float = 0.00

    @field_validator("boundary", mode="before")
    @classmethod
    def convert_boundary_to_str(cls, v):
        if isinstance(v, list):
            return [tuple(str(x) for x in pt) if isinstance(pt, (list, tuple)) else pt for pt in v]
        return v


class SlabReinforcement(BaseModel):
    mesh: Optional[str] = None  # e.g., "Wire Mesh Ø 4mm @ 0.20m" or "RB9 @ 0.20m"
    main_bottom: Optional[str] = None
    main_top: Optional[str] = None


class IfcSlab(BaseModel):
    class_: Literal["IfcSlab"] = Field(alias="class")
    tag: str
    material: str
    thickness: float  # Slab thickness in meters
    slab_type: Literal["SOLID", "PRECAST_PLANK", "TOPPING", "GROUND_SLAB"] = "SOLID"
    placement: SlabPlacement
    reinforcement: Optional[SlabReinforcement] = None


StairType = Literal["STRAIGHT", "DOG_LEG", "L_SHAPE", "SPIRAL", "LADDER"]


# Stair placement & element
class StairPlacement(BaseModel):
    grid_anchor: Tuple[str, str]  # Starting grid intersection, e.g. ["2", "B"]
    from_storey: str
    to_storey: str
    offset_x: float = 0.00
    offset_y: float = 0.00
    offset_z: float = 0.00
    orientation: Literal["+X", "-X", "+Y", "-Y"] = "+Y"

    @field_validator("grid_anchor", mode="before")
    @classmethod
    def convert_grid_anchor_to_str(cls, v):
        if isinstance(v, (list, tuple)):
            return tuple(str(x) for x in v)
        return v


class LandingEdgeBeamConfig(BaseModel):
    width: float = 0.20   # ความกว้างคานขอบชานพัก (m)
    depth: float = 0.35   # ความลึกคานขอบชานพักรวมความหนาชานพัก (m)
    material: Optional[str] = None
    edges: Literal["ALL", "FRONT_REAR", "SIDES"] = "ALL"  # แนวขอบที่เทคาน


class StairLanding(BaseModel):
    elevation: float  # Absolute height above from_storey elevation (m)
    depth: float = 1.00  # Landing depth (m)
    thickness: float = 0.12  # Landing slab thickness (m)
    material: Optional[str] = None
    edge_beam: Optional[LandingEdgeBeamConfig] = None



class StairStepConfig(BaseModel):
    tread: float = 0.25  # ลูกนอน (m)
    riser: float = 0.1875  # ลูกตั้ง (m)
    n_risers: Optional[int] = None  # Auto-calculated from floor-to-floor height if omitted


class StairStringerConfig(BaseModel):
    material: Optional[str] = None
    width: float = 0.20
    depth: float = 0.30
    stringer_type: Literal["WAIST_SLAB", "SIDE_BEAMS", "CENTRAL_BEAM"] = "WAIST_SLAB"


class StairFinishesConfig(BaseModel):
    tread_finish: Optional[str] = None  # e.g. "WOOD_PLANK", "GRANITO", "CONCRETE_POLISHED"
    riser_finish: Optional[str] = None
    nosing: bool = False  # จมูกบันไดกันลื่น (คิดความยาวตามจำนวนขั้น x ความกว้าง)
    nosing_type: Optional[str] = "ALUMINUM_STRIP"


class StairRailingConfig(BaseModel):
    height: float = 0.90  # ราวกันตกสูง (m)
    type: str = "STEEL_HANDRAIL"  # ประเภทราวบันได
    side: Literal["INNER", "OUTER", "BOTH"] = "INNER"
    layout: Literal["SINGLE", "DOUBLE"] = "SINGLE"  # ราวเดี่ยว (SINGLE) หรือราวคู่ (DOUBLE)



class StairReinforcement(BaseModel):
    main: Optional[str] = None  # e.g. "DB12 @ 0.15m"
    temperature: Optional[str] = None  # e.g. "RB9 @ 0.20m"


class IfcStair(BaseModel):
    class_: Literal["IfcStair"] = Field(alias="class")
    tag: str
    material: str
    stair_type: StairType = "DOG_LEG"
    width: float = 1.00  # Clear flight width (m)
    waist_thickness: float = 0.12  # Structural waist slab thickness (m)
    placement: StairPlacement
    landing: Optional[StairLanding] = None
    steps: Optional[StairStepConfig] = None
    stringer: Optional[StairStringerConfig] = None
    finishes: Optional[StairFinishesConfig] = None
    railing: Optional[StairRailingConfig] = None
    reinforcement: Optional[StairReinforcement] = None



# Custom element placement & element
class CustomElementPlacement(BaseModel):
    position: Tuple[float, float, float]
    storey: str


class IfcCustomElement(BaseModel):
    class_: Literal["IfcCustomElement"] = Field(alias="class")
    tag: str
    name: str
    source: str
    placement: CustomElementPlacement


# Roof element definitions
RoofType = Literal["GABLE", "HIP", "SHED", "FLAT", "MANSARD"]
RidgeOrientation = Literal["X", "Y", "ALONG_LENGTH", "ALONG_WIDTH"]


class RoofPlacement(BaseModel):
    boundary: List[Tuple[str, str]]  # List of grid intersections bounding the roof e.g. [["1", "B"], ["4", "B"], ["4", "E"], ["1", "E"]]
    storey: str
    offset_z: float = 0.00
    overhang: float = 1.00  # Eave overhang in meters (ระยะยื่นชายคา)
    ridge_orientation: RidgeOrientation = "X"

    @field_validator("boundary", mode="before")
    @classmethod
    def convert_boundary_to_str(cls, v):
        if isinstance(v, list):
            return [tuple(str(x) for x in pt) if isinstance(pt, (list, tuple)) else pt for pt in v]
        return v


class RoofCoveringConfig(BaseModel):
    tile_type: str = "CONCRETE_TILE"  # e.g. "CONCRETE_TILE", "CERAMIC_TILE", "CORRUGATED_FIBER", "METAL_SHEET"
    material: Optional[str] = None
    pitch: float = 30.0  # Slope pitch angle in degrees (ความลาดชันหลังคา องศา)
    insulation: bool = True  # Foil insulation under tiles (แผ่นสะท้อนความร้อน)
    fascia_board: bool = True  # Fascia board (ไม้เชิงชาย)
    ridge_cap: bool = True  # Ridge / Hip caps (ครอบสันหลังคา/ตะเข้สัน)


class RoofFramingConfig(BaseModel):
    truss_type: Literal["STEEL_TRUSS", "TIMBER_TRUSS", "STEEL_RAFTER"] = "STEEL_TRUSS"
    material: Optional[str] = None  # Reference to material id, e.g. "STEEL_SS400"
    spacing: float = 1.00  # Truss / rafter spacing (m)
    purlin_spacing: float = 0.32  # Purlin spacing (m) (ระยะแป e.g. 0.32m for concrete tile)
    steel_weight_per_sqm: float = 18.0  # kg/m2 of projected roof area for structural steel framing


class IfcRoof(BaseModel):
    class_: Literal["IfcRoof"] = Field(alias="class", default="IfcRoof")
    tag: str
    material: str
    roof_type: RoofType = "HIP"
    placement: RoofPlacement
    covering: Optional[RoofCoveringConfig] = Field(default_factory=RoofCoveringConfig)
    framing: Optional[RoofFramingConfig] = Field(default_factory=RoofFramingConfig)



# MEP (Mechanical, Electrical & Plumbing) Elements

PipeSystemType = Literal[
    "COLD_WATER", "HOT_WATER", "SOIL", "WASTE", "VENT", "DRAINAGE", "REFRIGERANT", "CONDENSATE"
]
ElectricalSystemType = Literal["POWER", "LIGHTING", "MAIN_FEEDER", "COMMUNICATION", "SOLAR"]
DuctSystemType = Literal["SUPPLY_AIR", "RETURN_AIR", "EXHAUST_AIR", "FRESH_AIR"]
AirTerminalType = Literal[
    "EXHAUST_FAN_CEILING", "EXHAUST_FAN_WALL", "KITCHEN_HOOD", "SUPPLY_DIFFUSER", "RETURN_GRILLE"
]
HvacEquipmentType = Literal[
    "AC_INDOOR_WALL", "AC_INDOOR_CASSETTE", "AC_INDOOR_CONCEALED", "AC_OUTDOOR_CONDENSER"
]
SanitaryTerminalType = Literal[
    "WATER_CLOSET", "LAVATORY", "SHOWER", "KITCHEN_SINK",
    "FLOOR_DRAIN", "GREASE_TRAP", "SEPTIC_TANK", "WATER_TANK", "WATER_PUMP"
]
BoardType = Literal["CONSUMER_UNIT", "MDB", "PANELBOARD"]
LightFixtureType = Literal["DOWNLIGHT", "LED_TUBE", "PENDANT", "WALL_LAMP", "FLOODLIGHT"]
SwitchType = Literal["ONE_WAY", "TWO_WAY", "DIMMER"]
OutletType = Literal["DUPLEX_GROUNDED", "WATERPROOF", "HIGH_POWER"]


RoutingStrategy = Literal["DIRECT", "ORTHOGONAL", "X_THEN_Y", "Y_THEN_X"]


class PipePoint(BaseModel):
    grid: Optional[Tuple[str, str]] = None
    offset_x: float = 0.0
    offset_y: float = 0.0
    offset_z: float = 0.0
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None

    @field_validator("grid", mode="before")
    @classmethod
    def convert_grid_items_to_str(cls, v):
        if isinstance(v, (list, tuple)):
            return tuple(str(x) for x in v)
        return v


class PipePlacement(BaseModel):
    storey: str
    from_grid: Optional[Tuple[str, str]] = None
    to_grid: Optional[Tuple[str, str]] = None
    from_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    to_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    path: Optional[List[PipePoint]] = None
    routing: RoutingStrategy = "DIRECT"
    slope: float = 0.0  # Slope ratio, e.g. 0.01 (1:100) or 0.02 (1:50)

    @field_validator("from_grid", "to_grid", mode="before")
    @classmethod
    def convert_grid_items_to_str(cls, v):
        if isinstance(v, (list, tuple)):
            return tuple(str(x) for x in v)
        return v

    @field_validator("from_offset", "to_offset", mode="before")
    @classmethod
    def convert_offset_tuple(cls, v):
        if isinstance(v, (list, tuple)):
            return tuple(float(x) for x in v)
        return v


class IfcPipeSegment(BaseModel):
    class_: Literal["IfcPipeSegment"] = Field(alias="class", default="IfcPipeSegment")
    tag: str
    system_type: PipeSystemType = "COLD_WATER"
    material: Optional[str] = None
    nominal_diameter: float = 0.020  # Nominal diameter in meters (e.g. 0.020 for 3/4", 0.100 for 4")
    placement: PipePlacement


class IfcCableCarrierSegment(BaseModel):
    class_: Literal["IfcCableCarrierSegment"] = Field(alias="class", default="IfcCableCarrierSegment")
    tag: str
    system_type: ElectricalSystemType = "LIGHTING"
    material: Optional[str] = None
    nominal_diameter: float = 0.020  # Conduit diameter in meters
    placement: PipePlacement


class TerminalDimensions(BaseModel):
    width: float = 0.50
    depth: float = 0.50
    height: float = 0.50


# MEP Terminal placement & elements
class TerminalPlacement(BaseModel):
    # Existing grid-based fields (Optional when wall is specified)
    grid: Optional[Tuple[str, str]] = None
    storey: Optional[str] = None  # Optional if wall is provided (inherits from wall's storey)
    offset_x: float = 0.0
    offset_y: float = 0.0
    offset_z: float = 0.0  # Mounting elevation above storey level
    rotation: Optional[float] = None  # Auto-calculated if None and wall-hosted

    # NEW: Wall-hosted placement fields
    wall: Optional[str] = None  # Tag of the hosting IfcWall, e.g. "WALL-L1-3_D-E"
    distance: float = 0.0  # Distance along wall baseline from start_point in meters
    side: Literal["INTERIOR", "EXTERIOR", "CENTER"] = "INTERIOR"
    standoff: float = 0.0  # Gap between back of fixture and wall surface (0.0 = flush)

    @field_validator("grid", mode="before")
    @classmethod
    def convert_grid_items_to_str(cls, v):
        if isinstance(v, (list, tuple)):
            return tuple(str(x) for x in v)
        return v

    @model_validator(mode="after")
    def check_grid_or_wall(self) -> "TerminalPlacement":
        if not self.grid and not self.wall:
            raise ValueError("Either grid or wall must be provided for TerminalPlacement.")
        return self


class IfcSanitaryTerminal(BaseModel):
    class_: Literal["IfcSanitaryTerminal"] = Field(alias="class", default="IfcSanitaryTerminal")
    tag: str
    terminal_type: SanitaryTerminalType = "WATER_CLOSET"
    material: Optional[str] = None
    width: float = 0.0
    depth: float = 0.0
    height: float = 0.0
    placement: TerminalPlacement
    dimensions: Optional[TerminalDimensions] = None


class IfcDistributionBoard(BaseModel):
    class_: Literal["IfcDistributionBoard"] = Field(alias="class", default="IfcDistributionBoard")
    tag: str
    board_type: BoardType = "CONSUMER_UNIT"
    material: Optional[str] = None
    width: float = 0.0
    depth: float = 0.0
    height: float = 0.0
    placement: TerminalPlacement
    dimensions: Optional[TerminalDimensions] = None
    circuits_count: int = 12


class IfcLightFixture(BaseModel):
    class_: Literal["IfcLightFixture"] = Field(alias="class", default="IfcLightFixture")
    tag: str
    fixture_type: LightFixtureType = "DOWNLIGHT"
    material: Optional[str] = None
    width: float = 0.0
    depth: float = 0.0
    height: float = 0.0
    placement: TerminalPlacement
    dimensions: Optional[TerminalDimensions] = None
    wattage: Optional[float] = 12.0


class IfcSwitchingDevice(BaseModel):
    class_: Literal["IfcSwitchingDevice"] = Field(alias="class", default="IfcSwitchingDevice")
    tag: str
    switch_type: SwitchType = "ONE_WAY"
    material: Optional[str] = None
    width: float = 0.0
    depth: float = 0.0
    height: float = 0.0
    placement: TerminalPlacement
    dimensions: Optional[TerminalDimensions] = None
    gangs: int = 1


class IfcOutlet(BaseModel):
    class_: Literal["IfcOutlet"] = Field(alias="class", default="IfcOutlet")
    tag: str
    outlet_type: OutletType = "DUPLEX_GROUNDED"
    material: Optional[str] = None
    width: float = 0.0
    depth: float = 0.0
    height: float = 0.0
    placement: TerminalPlacement
    dimensions: Optional[TerminalDimensions] = None


class IfcDuctSegment(BaseModel):
    class_: Literal["IfcDuctSegment"] = Field(alias="class", default="IfcDuctSegment")
    tag: str
    system_type: DuctSystemType = "EXHAUST_AIR"
    material: Optional[str] = None
    width: float = 0.25   # Duct width in meters (or diameter if circular)
    height: float = 0.20  # Duct height in meters
    placement: PipePlacement


class IfcAirTerminal(BaseModel):
    class_: Literal["IfcAirTerminal"] = Field(alias="class", default="IfcAirTerminal")
    tag: str
    terminal_type: AirTerminalType = "EXHAUST_FAN_CEILING"
    material: Optional[str] = None
    width: float = 0.0
    depth: float = 0.0
    height: float = 0.0
    placement: TerminalPlacement
    dimensions: Optional[TerminalDimensions] = None
    flow_rate_cfm: Optional[float] = None


class IfcUnitaryEquipment(BaseModel):
    class_: Literal["IfcUnitaryEquipment"] = Field(alias="class", default="IfcUnitaryEquipment")
    tag: str
    equipment_type: HvacEquipmentType = "AC_INDOOR_WALL"
    material: Optional[str] = None
    width: float = 0.0
    depth: float = 0.0
    height: float = 0.0
    placement: TerminalPlacement
    dimensions: Optional[TerminalDimensions] = None
    cooling_capacity_btu: Optional[float] = 12000.0


Element = Annotated[
    Union[
        IfcColumn,
        IfcBeam,
        IfcWall,
        IfcFooting,
        IfcSlab,
        IfcStair,
        IfcRoof,
        IfcPipeSegment,
        IfcCableCarrierSegment,
        IfcDuctSegment,
        IfcSanitaryTerminal,
        IfcDistributionBoard,
        IfcLightFixture,
        IfcSwitchingDevice,
        IfcOutlet,
        IfcAirTerminal,
        IfcUnitaryEquipment,
        IfcCustomElement,
    ],
    Field(discriminator="class_"),
]


class Material(BaseModel):
    id: str
    name: str
    category: str
    unit_cost_ref: str


class ProjectManifest(BaseModel):
    schema_version: str = Field(alias="schema", default="IFC4-Minimal")
    project: ProjectInfo
    spatial_structure: SpatialStructure
    grids: Grids
    materials: List[Material]
    elements: List[Element] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "ProjectManifest":
        storey_ids = {s.id for s in self.spatial_structure.storeys}
        grid_x_ids = set(self.grids.axes_x.keys())
        grid_y_ids = set(self.grids.axes_y.keys())
        material_ids = {m.id for m in self.materials}

        for elem in self.elements:
            # Verify material ID reference if applicable
            if hasattr(elem, "material") and elem.material:
                if elem.material not in material_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown material '{elem.material}'"
                    )

            # Verify storey and grid references per element type
            if isinstance(elem, IfcColumn):
                if elem.placement.base_storey not in storey_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown base_storey '{elem.placement.base_storey}'"
                    )
                if elem.placement.top_storey not in storey_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown top_storey '{elem.placement.top_storey}'"
                    )
                gx, gy = elem.placement.grid
                if gx not in grid_x_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown X grid '{gx}'"
                    )
                if gy not in grid_y_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown Y grid '{gy}'"
                    )

            elif isinstance(elem, IfcBeam):
                if elem.placement.storey not in storey_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown storey '{elem.placement.storey}'"
                    )
                fgx, fgy = elem.placement.from_grid
                tgx, tgy = elem.placement.to_grid
                if fgx not in grid_x_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' from_grid references unknown X grid '{fgx}'"
                    )
                if fgy not in grid_y_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' from_grid references unknown Y grid '{fgy}'"
                    )
                if tgx not in grid_x_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' to_grid references unknown X grid '{tgx}'"
                    )
                if tgy not in grid_y_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' to_grid references unknown Y grid '{tgy}'"
                    )

            elif isinstance(elem, IfcWall):
                if elem.placement.storey not in storey_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown storey '{elem.placement.storey}'"
                    )
                fgx, fgy = elem.placement.from_grid
                tgx, tgy = elem.placement.to_grid
                if fgx not in grid_x_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' from_grid references unknown X grid '{fgx}'"
                    )
                if fgy not in grid_y_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' from_grid references unknown Y grid '{fgy}'"
                    )
                if tgx not in grid_x_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' to_grid references unknown X grid '{tgx}'"
                    )
                if tgy not in grid_y_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' to_grid references unknown Y grid '{tgy}'"
                    )

            elif isinstance(elem, IfcFooting):
                if elem.placement.storey not in storey_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown storey '{elem.placement.storey}'"
                    )
                gx, gy = elem.placement.grid
                if gx not in grid_x_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown X grid '{gx}'"
                    )
                if gy not in grid_y_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown Y grid '{gy}'"
                    )
                if elem.piles and elem.piles.material and elem.piles.material not in material_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' piles references unknown material '{elem.piles.material}'"
                    )

            elif isinstance(elem, IfcSlab):
                if elem.placement.storey not in storey_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown storey '{elem.placement.storey}'"
                    )
                for pt in elem.placement.boundary:
                    gx, gy = pt
                    if gx not in grid_x_ids:
                        raise ValueError(
                            f"Element '{elem.tag}' boundary references unknown X grid '{gx}'"
                        )
                    if gy not in grid_y_ids:
                        raise ValueError(
                            f"Element '{elem.tag}' boundary references unknown Y grid '{gy}'"
                        )

            elif isinstance(elem, IfcStair):
                if elem.placement.from_storey not in storey_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown from_storey '{elem.placement.from_storey}'"
                    )
                if elem.placement.to_storey not in storey_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown to_storey '{elem.placement.to_storey}'"
                    )
                gx, gy = elem.placement.grid_anchor
                if gx not in grid_x_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' grid_anchor references unknown X grid '{gx}'"
                    )
                if gy not in grid_y_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' grid_anchor references unknown Y grid '{gy}'"
                    )

            elif isinstance(elem, IfcRoof):
                if elem.placement.storey not in storey_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown storey '{elem.placement.storey}'"
                    )
                for pt in elem.placement.boundary:
                    gx, gy = pt
                    if gx not in grid_x_ids:
                        raise ValueError(
                            f"Element '{elem.tag}' boundary references unknown X grid '{gx}'"
                        )
                    if gy not in grid_y_ids:
                        raise ValueError(
                            f"Element '{elem.tag}' boundary references unknown Y grid '{gy}'"
                        )
                if elem.framing and elem.framing.material and elem.framing.material not in material_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' framing references unknown material '{elem.framing.material}'"
                    )

            elif isinstance(elem, (IfcPipeSegment, IfcCableCarrierSegment, IfcDuctSegment)):
                if elem.placement.storey not in storey_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown storey '{elem.placement.storey}'"
                    )
                if elem.placement.from_grid:
                    gx, gy = elem.placement.from_grid
                    if gx not in grid_x_ids:
                        raise ValueError(f"Element '{elem.tag}' references unknown X grid '{gx}'")
                    if gy not in grid_y_ids:
                        raise ValueError(f"Element '{elem.tag}' references unknown Y grid '{gy}'")
                if elem.placement.to_grid:
                    gx, gy = elem.placement.to_grid
                    if gx not in grid_x_ids:
                        raise ValueError(f"Element '{elem.tag}' references unknown X grid '{gx}'")
                    if gy not in grid_y_ids:
                        raise ValueError(f"Element '{elem.tag}' references unknown Y grid '{gy}'")
                if elem.placement.path:
                    for pt in elem.placement.path:
                        if pt.grid:
                            gx, gy = pt.grid
                            if gx not in grid_x_ids:
                                raise ValueError(f"Element '{elem.tag}' path references unknown X grid '{gx}'")
                            if gy not in grid_y_ids:
                                raise ValueError(f"Element '{elem.tag}' path references unknown Y grid '{gy}'")

            elif isinstance(elem, (IfcSanitaryTerminal, IfcDistributionBoard, IfcLightFixture, IfcSwitchingDevice, IfcOutlet, IfcAirTerminal, IfcUnitaryEquipment)):
                if elem.placement.storey and elem.placement.storey not in storey_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown storey '{elem.placement.storey}'"
                    )
                if elem.placement.grid:
                    gx, gy = elem.placement.grid
                    if gx not in grid_x_ids:
                        raise ValueError(
                            f"Element '{elem.tag}' references unknown X grid '{gx}'"
                        )
                    if gy not in grid_y_ids:
                        raise ValueError(
                            f"Element '{elem.tag}' references unknown Y grid '{gy}'"
                        )

            elif isinstance(elem, IfcCustomElement):
                if elem.placement.storey not in storey_ids:
                    raise ValueError(
                        f"Element '{elem.tag}' references unknown storey '{elem.placement.storey}'"
                    )

        return self


def load_manifest(path: Path | str) -> ProjectManifest:
    """Load and validate project.yaml manifest file."""
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return ProjectManifest.model_validate(data)
