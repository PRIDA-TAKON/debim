"""
Exemplar Manifest Generator for debim.
Generates minimal, syntactically valid .debim manifests and element dictionaries
for all supported IFC classes and universal proxy entities.
"""

from typing import Any, Dict, List, Optional
import yaml
from debim.schema import EXPLICIT_TYPED_ELEMENT_CLASSES, ProjectManifest, load_manifest

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
]

SUPPORTED_CLASSES = list(EXPLICIT_TYPED_ELEMENT_CLASSES) + [
    "IfcPump", "IfcBoiler", "IfcChiller", "IfcSensor", "IfcFlowMeter", "IfcFan", "IfcTank"
]


def generate_exemplar_element(class_name: str, tag_suffix: str = "01") -> Dict[str, Any]:
    """
    Generate minimal, syntactically valid dictionary for a given IFC class name.
    """
    norm_cls = class_name.strip()

    if norm_cls == "IfcColumn":
        return {
            "class": "IfcColumn",
            "tag": f"COL-{tag_suffix}",
            "material": "CONCRETE_C30",
            "profile": {"shape": "BOX", "width": 0.30, "depth": 0.30},
            "placement": {
                "grid": ["1", "A"],
                "base_storey": "L1",
                "top_storey": "L2",
            },
        }

    elif norm_cls == "IfcBeam":
        return {
            "class": "IfcBeam",
            "tag": f"BM-{tag_suffix}",
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
        return {
            "class": "IfcWall",
            "tag": f"WALL-{tag_suffix}",
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
        return {
            "class": "IfcFooting",
            "tag": f"FTG-{tag_suffix}",
            "material": "CONCRETE_C30",
            "profile": {"shape": "BOX", "width": 1.20, "depth": 1.20, "thickness": 0.35},
            "placement": {
                "grid": ["1", "A"],
                "storey": "L1",
                "offset_z": -0.80,
            },
        }

    elif norm_cls == "IfcSlab":
        return {
            "class": "IfcSlab",
            "tag": f"SLAB-{tag_suffix}",
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

    elif norm_cls == "IfcSanitaryTerminal":
        return {
            "class": "IfcSanitaryTerminal",
            "tag": f"SAN-{tag_suffix}",
            "terminal_type": "WATER_CLOSET",
            "material": "CERAMIC_TILE",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcWasteTerminal":
        return {
            "class": "IfcWasteTerminal",
            "tag": f"WST-{tag_suffix}",
            "terminal_type": "FLOOR_DRAIN",
            "material": "STAINLESS_STEEL",
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

    elif norm_cls == "IfcDamper":
        return {
            "class": "IfcDamper",
            "tag": f"DMP-{tag_suffix}",
            "damper_type": "VOLUME_CONTROL_DAMPER",
            "material": "GALVANIZED_STEEL",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcFlowController":
        return {
            "class": "IfcFlowController",
            "tag": f"FLC-{tag_suffix}",
            "controller_type": "AIR_CONTROLLER",
            "material": "GALVANIZED_STEEL",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcUnitaryEquipment":
        return {
            "class": "IfcUnitaryEquipment",
            "tag": f"AC-{tag_suffix}",
            "equipment_type": "AC_INDOOR_WALL",
            "material": "PLASTIC_PVC",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcEarthworksElement":
        return {
            "class": "IfcEarthworksElement",
            "tag": f"EW-{tag_suffix}",
            "predefined_type": "RETAINING_STRUCTURE",
            "material": "CONCRETE_C30",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcEarthworksCut":
        return {
            "class": "IfcEarthworksCut",
            "tag": f"CUT-{tag_suffix}",
            "predefined_type": "CUT",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcEarthworksFill":
        return {
            "class": "IfcEarthworksFill",
            "tag": f"FILL-{tag_suffix}",
            "predefined_type": "EMBANKMENT",
            "material": "SOIL_COMPACTED",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcGeotechnicalStratum":
        return {
            "class": "IfcGeotechnicalStratum",
            "tag": f"STRATUM-{tag_suffix}",
            "predefined_type": "SOLID",
            "soil_type": "clay",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcSoil":
        return {
            "class": "IfcSoil",
            "tag": f"SOIL-{tag_suffix}",
            "soil_type": "topsoil",
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
            },
        }

    elif norm_cls == "IfcRetainingWall":
        return {
            "class": "IfcRetainingWall",
            "tag": f"RET-{tag_suffix}",
            "material": "CONCRETE_C30",
            "placement": {
                "storey": "L1",
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
            },
        }

    elif norm_cls == "IfcAlignment":
        return {
            "class": "IfcAlignment",
            "tag": f"ALIGN-{tag_suffix}",
            "placement": {
                "storey": "L1",
                "points": [
                    {"x": 0.0, "y": 0.0, "z": 0.0},
                    {"x": 10.0, "y": 0.0, "z": 0.0},
                ],
            },
        }

    elif norm_cls == "IfcRoad":
        return {
            "class": "IfcRoad",
            "tag": f"ROAD-{tag_suffix}",
            "material": "ASPHALT_CONCRETE",
            "placement": {
                "storey": "L1",
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
            },
        }

    elif norm_cls == "IfcBridge":
        return {
            "class": "IfcBridge",
            "tag": f"BRG-{tag_suffix}",
            "material": "CONCRETE_C30",
            "placement": {
                "storey": "L1",
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
            },
        }

    elif norm_cls == "IfcRailway":
        return {
            "class": "IfcRailway",
            "tag": f"RLW-{tag_suffix}",
            "placement": {
                "storey": "L1",
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
            },
        }

    elif norm_cls == "IfcRailwayPart":
        return {
            "class": "IfcRailwayPart",
            "tag": f"RLWP-{tag_suffix}",
            "predefined_type": "TRACK",
            "placement": {
                "storey": "L1",
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
            },
        }

    elif norm_cls == "IfcTrackElement":
        return {
            "class": "IfcTrackElement",
            "tag": f"TRK-{tag_suffix}",
            "predefined_type": "RAIL",
            "material": "STEEL_SS400",
            "placement": {
                "storey": "L1",
                "from_grid": ["1", "A"],
                "to_grid": ["2", "A"],
            },
        }

    elif norm_cls == "IfcCustomElement":
        return {
            "class": "IfcCustomElement",
            "tag": f"CUST-{tag_suffix}",
            "name": "Custom Procedural Component",
            "placement": {
                "storey": "L1",
                "position": [0.0, 0.0, 0.0],
            },
        }

    else:
        # Universal Proxy fallback (e.g. IfcBuildingElementProxy or dynamic classes like IfcPump)
        clean_tag_prefix = norm_cls.replace("Ifc", "").upper()[:4]
        return {
            "class": "IfcBuildingElementProxy",
            "ifc_class": norm_cls,
            "tag": f"{clean_tag_prefix}-{tag_suffix}",
            "material": "CAST_IRON" if "Pump" in norm_cls or "Boiler" in norm_cls or "Chiller" in norm_cls else "STEEL_SS400",
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
