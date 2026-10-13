"""
Exemplar Manifest Generator for debim.
Generates minimal, syntactically valid .debim manifests and element dictionaries
for all supported IFC classes and universal proxy entities.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from debim.schema import ProjectManifest, load_manifest

# Standard material definitions for exemplar manifests
EXEMPLAR_MATERIALS = [
    {"id": "CONCRETE_C30", "name": "Concrete C30/35", "category": "Concrete", "unit_cost_ref": "MAT-CONC-C30"},
    {"id": "STEEL_SS400", "name": "Structural Steel SS400", "category": "Steel", "unit_cost_ref": "MAT-STEEL-SS400"},
    {"id": "BRICK_MASONRY", "name": "Clay Brick Masonry", "category": "Masonry", "unit_cost_ref": "MAT-BRICK"},
    {"id": "GLASS_TRANSPARENT", "name": "Clear Float Glass", "category": "Glass", "unit_cost_ref": "MAT-GLASS-CLEAR"},
    {"id": "GYPSUM_BOARD", "name": "Gypsum Board 9mm", "category": "Finish", "unit_cost_ref": "MAT-GYPSUM-9MM"},
    {"id": "PVC_PIPE", "name": "PVC Pipe Class 8.5", "category": "Plumbing", "unit_cost_ref": "MAT-PVC-PIPE"},
    {"id": "GALVANIZED_STEEL", "name": "Galvanized Steel Sheet", "category": "HVAC", "unit_cost_ref": "MAT-GI-SHEET"},
    {"id": "CERAMIC_TILE", "name": "Ceramic Tile", "category": "Finish", "unit_cost_ref": "MAT-CERAMIC-TILE"},
    {"id": "STAINLESS_STEEL", "name": "Stainless Steel Grade 304", "category": "Steel", "unit_cost_ref": "MAT-SS-304"},
    {"id": "ALUMINUM", "name": "Extruded Aluminum Frame", "category": "Aluminum", "unit_cost_ref": "MAT-ALUM-FRAME"},
    {"id": "PLASTIC_PVC", "name": "Electrical Grade PVC", "category": "Electrical", "unit_cost_ref": "MAT-ELEC-PVC"},
    {"id": "SOIL_COMPACTED", "name": "Compacted Earth Fill", "category": "Earthworks", "unit_cost_ref": "MAT-SOIL-FILL"},
    {"id": "ASPHALT_CONCRETE", "name": "Asphalt Concrete Wearing Course", "category": "Pavement", "unit_cost_ref": "MAT-ASPHALT"},
    {"id": "CAST_IRON", "name": "Cast Iron", "category": "Metal", "unit_cost_ref": "MAT-CAST-IRON"},
    {"id": "WOOD", "name": "Natural Wood Timber", "category": "Wood", "unit_cost_ref": "MAT-TIMBER"},
]

# Discover golden entity classes from fixtures if available
_GOLDEN_FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "golden_entities"
if not _GOLDEN_FIXTURES_DIR.exists():
    _GOLDEN_FIXTURES_DIR = Path("tests/fixtures/golden_entities")

_GOLDEN_CLASSES = []
if _GOLDEN_FIXTURES_DIR.exists():
    _GOLDEN_CLASSES = sorted([f.stem for f in _GOLDEN_FIXTURES_DIR.glob("*.yaml")])

_CIVIL_EXTRA_CLASSES = [
    "IfcAlignment", "IfcRoad", "IfcBridge", "IfcBridgePart", "IfcBearing", "IfcRailway", "IfcRailwayPart",
    "IfcTrackElement", "IfcEarthworksElement", "IfcEarthworksCut", "IfcEarthworksFill",
    "IfcGeotechnicalStratum", "IfcSoil", "IfcRetainingWall", "IfcMarineFacility", "IfcMarinePart",
    "IfcMooringDevice", "IfcNavigationElement", "IfcElectricAppliance", "IfcLamp", "IfcSwitchingDevice",
    "IfcPump", "IfcBoiler", "IfcChiller", "IfcSensor", "IfcFlowMeter", "IfcFan", "IfcTank"
]

SUPPORTED_CLASSES = sorted(list(set(_GOLDEN_CLASSES + _CIVIL_EXTRA_CLASSES)))


def generate_exemplar_element(class_name: str, tag_suffix: str = "01") -> Dict[str, Any]:
    """
    Generate minimal, syntactically valid dictionary for a given IFC class name.
    """
    norm_cls = class_name.strip()

    if norm_cls == "IfcColumn":
        prefix = "C" if tag_suffix == "A1" else "COL"
        return {
            "class": norm_cls,
            "tag": f"{prefix}-{tag_suffix}",
            "material": "CONCRETE_C30",
            "profile": {"shape": "BOX", "width": 0.30, "depth": 0.30},
            "placement": {
                "grid": ["1", "A"],
                "base_storey": "L1",
                "top_storey": "L2",
            },
        }

    elif norm_cls == "IfcBeam":
        prefix = "B" if tag_suffix == "A1" else "BM"
        return {
            "class": norm_cls,
            "tag": f"{prefix}-{tag_suffix}",
            "material": "CONCRETE_C30",
            "profile": {"shape": "BOX", "width": 0.20, "depth": 0.40},
            "placement": {
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
                "storey": "L1",
                "offset_z": 3.0,
            },
        }

    elif norm_cls == "IfcWall":
        prefix = "W" if tag_suffix == "A1" else "WALL"
        return {
            "class": norm_cls,
            "tag": f"{prefix}-{tag_suffix}",
            "material": "BRICK_MASONRY",
            "thickness": 0.10,
            "height": 3.0,
            "placement": {
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
                "storey": "L1",
            },
        }

    elif norm_cls == "IfcFooting":
        prefix = "F" if tag_suffix == "A1" else "FTG"
        return {
            "class": norm_cls,
            "tag": f"{prefix}-{tag_suffix}",
            "material": "CONCRETE_C30",
            "profile": {"shape": "BOX", "width": 1.20, "depth": 1.20, "thickness": 0.35},
            "placement": {
                "grid": ["1", "A"],
                "storey": "L1",
                "offset_z": -0.80,
            },
        }

    elif norm_cls == "IfcSlab":
        prefix = "S" if tag_suffix == "A1" else "SLAB"
        return {
            "class": norm_cls,
            "tag": f"{prefix}-{tag_suffix}",
            "material": "CONCRETE_C30",
            "thickness": 0.15,
            "placement": {
                "boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]],
                "storey": "L1",
                "offset_z": 3.0,
            },
        }

    elif norm_cls == "IfcCovering":
        return {
            "class": "IfcCovering",
            "tag": f"COV-{tag_suffix}",
            "covering_type": "CEILING",
            "material": "GYPSUM_BOARD",
            "thickness": 0.009,
            "placement": {
                "boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]],
                "storey": "L1",
                "offset_z": 2.80,
            },
        }

    elif norm_cls == "IfcStair":
        return {
            "class": "IfcStair",
            "tag": f"STR-{tag_suffix}",
            "material": "CONCRETE_C30",
            "stair_type": "DOG_LEG",
            "width": 1.20,
            "waist_thickness": 0.15,
            "placement": {
                "grid_anchor": ["1", "A"],
                "from_storey": "L1",
                "to_storey": "L2",
            },
        }

    elif norm_cls == "IfcStairFlight":
        return {
            "class": "IfcStairFlight",
            "tag": f"STFL-{tag_suffix}",
            "material": "CONCRETE_C30",
            "flight_width": 1.00,
            "waist_thickness": 0.12,
            "riser_height": 0.18,
            "tread_length": 0.25,
            "placement": {
                "grid_anchor": ["1", "A"],
                "from_storey": "L1",
                "to_storey": "L2",
            },
        }

    elif norm_cls == "IfcRamp":
        return {
            "class": "IfcRamp",
            "tag": f"RMP-{tag_suffix}",
            "material": "CONCRETE_C30",
            "ramp_width": 1.20,
            "slope_percentage": 8.33,
            "slab_thickness": 0.15,
            "placement": {
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
                "storey": "L1",
            },
        }

    elif norm_cls == "IfcRailing":
        return {
            "class": "IfcRailing",
            "tag": f"RLG-{tag_suffix}",
            "material": "STEEL_SS400",
            "predefined_type": "HANDRAIL",
            "height": 1.00,
            "placement": {
                "storey": "L1",
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
            },
        }

    elif norm_cls == "IfcRoof":
        return {
            "class": "IfcRoof",
            "tag": f"ROOF-{tag_suffix}",
            "material": "CERAMIC_TILE",
            "roof_type": "HIP",
            "placement": {
                "boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]],
                "storey": "L2",
                "offset_z": 3.0,
            },
        }

    elif norm_cls == "IfcCurtainWall":
        return {
            "class": "IfcCurtainWall",
            "tag": f"CW-{tag_suffix}",
            "material": "GLASS_TRANSPARENT",
            "predefined_type": "POST_AND_BEAM",
            "height": 3.00,
            "placement": {
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
                "storey": "L1",
            },
        }

    elif norm_cls == "IfcPlate":
        return {
            "class": "IfcPlate",
            "tag": f"PLT-{tag_suffix}",
            "material": "STEEL_SS400",
            "predefined_type": "SHEET",
            "thickness": 0.010,
            "width": 1.00,
            "depth": 1.00,
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcPipeSegment":
        return {
            "class": "IfcPipeSegment",
            "tag": f"PIPE-{tag_suffix}",
            "system_type": "COLD_WATER",
            "material": "PVC_PIPE",
            "nominal_diameter": 0.025,
            "placement": {
                "storey": "L1",
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
            },
        }

    elif norm_cls == "IfcCableCarrierSegment":
        return {
            "class": "IfcCableCarrierSegment",
            "tag": f"CONDUIT-{tag_suffix}",
            "system_type": "LIGHTING",
            "material": "PVC_PIPE",
            "nominal_diameter": 0.020,
            "placement": {
                "storey": "L1",
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
            },
        }

    elif norm_cls == "IfcDuctSegment":
        return {
            "class": "IfcDuctSegment",
            "tag": f"DUCT-{tag_suffix}",
            "system_type": "EXHAUST_AIR",
            "material": "GALVANIZED_STEEL",
            "width": 0.30,
            "height": 0.20,
            "placement": {
                "storey": "L1",
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
            },
        }

    elif norm_cls in ("IfcSanitaryTerminal", "IfcWasteTerminal"):
        return {
            "class": norm_cls,
            "tag": f"SAN-{tag_suffix}",
            "terminal_type": "WATER_CLOSET" if norm_cls == "IfcSanitaryTerminal" else "FLOOR_DRAIN",
            "material": "CERAMIC_TILE" if norm_cls == "IfcSanitaryTerminal" else "STAINLESS_STEEL",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls in ("IfcDistributionBoard", "IfcElectricDistributionBoard"):
        return {
            "class": norm_cls,
            "tag": f"DB-{tag_suffix}",
            "board_type": "CONSUMER_UNIT",
            "material": "STEEL_SS400",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcLightFixture":
        return {
            "class": "IfcLightFixture",
            "tag": f"LGT-{tag_suffix}",
            "fixture_type": "DOWNLIGHT",
            "material": "ALUMINUM",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcSwitchingDevice":
        return {
            "class": "IfcSwitchingDevice",
            "tag": f"SWT-{tag_suffix}",
            "switch_type": "ONE_WAY",
            "material": "PLASTIC_PVC",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcOutlet":
        return {
            "class": "IfcOutlet",
            "tag": f"OUT-{tag_suffix}",
            "outlet_type": "DUPLEX_GROUNDED",
            "material": "PLASTIC_PVC",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcAirTerminal":
        return {
            "class": "IfcAirTerminal",
            "tag": f"AIR-{tag_suffix}",
            "terminal_type": "DIFFUSER",
            "material": "ALUMINUM",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcEarthworksElement":
        return {
            "class": norm_cls,
            "tag": f"EW-{tag_suffix}",
            "predefined_type": "RETAINING_STRUCTURE",
            "material": "SOIL_COMPACTED",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls in ("IfcEarthworksCut", "IfcEarthworksFill"):
        return {
            "class": norm_cls,
            "tag": f"EW-{tag_suffix}",
            "predefined_type": "CUT" if norm_cls == "IfcEarthworksCut" else "EMBANKMENT",
            "material": "SOIL_COMPACTED",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls in ("IfcFurniture", "IfcFurnishingElement"):
        return {
            "class": norm_cls,
            "tag": f"FURN-{tag_suffix}",
            "name": f"Exemplar {norm_cls}",
            "material": "WOOD",
            "dimensions": {"width": 1.0, "depth": 0.8, "height": 0.75},
            "placement": {
                "storey": "L1",
                "position": [0.0, 0.0, 0.0],
            },
        }

    elif norm_cls in ("IfcAlignment", "IfcRoad", "IfcBridge", "IfcRailway", "IfcRailwayPart", "IfcTrackElement", "IfcRetainingWall"):
        return {
            "class": norm_cls,
            "tag": f"CIV-{tag_suffix}",
            "material": "CONCRETE_C30" if "Bridge" in norm_cls or "Retaining" in norm_cls else "ASPHALT_CONCRETE",
            "placement": {
                "storey": "L1",
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
            },
        }

    else:
        clean_tag_prefix = norm_cls.replace("Ifc", "").upper()[:4]
        return {
            "class": "IfcBuildingElementProxy",
            "ifc_class": norm_cls,
            "tag": f"{clean_tag_prefix}-{tag_suffix}",
            "material": "CAST_IRON" if any(k in norm_cls for k in ("Pump", "Boiler", "Chiller", "Tank", "Engine")) else "STEEL_SS400",
            "dimensions": {"width": 1.0, "depth": 1.0, "height": 1.0},
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }


def get_supported_exemplar_classes() -> List[str]:
    """Get list of supported exemplar IFC class names."""
    return sorted(SUPPORTED_CLASSES)


def generate_exemplar_manifest(
    class_name: Optional[str] = None,
    class_names: Optional[List[str]] = None,
    project_id: str = "EXEMPLAR-01",
    project_name: str = "debim Exemplar Project",
) -> ProjectManifest:
    """
    Generate a complete, syntactically valid ProjectManifest populated with exemplar elements.
    If class_name is None and class_names is None, generates exemplar elements for all supported classes.
    """
    target_classes: List[str] = []
    if class_names:
        target_classes = class_names
    elif class_name:
        if class_name.upper() == "ALL":
            target_classes = get_supported_exemplar_classes()
        else:
            target_classes = [class_name]
    else:
        target_classes = get_supported_exemplar_classes()

    elements_data = []
    for idx, cls_item in enumerate(target_classes, start=1):
        elem_dict = generate_exemplar_element(cls_item, tag_suffix=f"{idx:02d}")
        elements_data.append(elem_dict)

    raw_manifest = {
        "schema": "IFC4-Minimal",
        "project": {
            "id": project_id,
            "name": project_name,
            "units": {
                "length": "METER",
                "area": "SQUARE_METER",
                "volume": "CUBIC_METER",
            },
        },
        "spatial_structure": {
            "storeys": [
                {"id": "L1", "name": "Level 1 Ground", "elevation": 0.0, "height": 3.50},
                {"id": "L2", "name": "Level 2 Upper", "elevation": 3.50, "height": 3.50},
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 6.0, "3": 12.0},
            "axes_y": {"A": 0.0, "B": 6.0, "C": 12.0},
        },
        "materials": EXEMPLAR_MATERIALS,
        "elements": elements_data,
    }

    return ProjectManifest.model_validate(raw_manifest)
