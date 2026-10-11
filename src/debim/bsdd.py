"""
buildingSMART bSDD (Building Data Dictionary) Property Set (Pset_*) Validation Module for debim.

Provides built-in schema definitions for core standard IFC4 Property Sets (Pset_*Common)
and validation engines to inspect element properties against official buildingSMART specifications.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from pydantic import BaseModel, Field


class PsetValidationStatus(str, Enum):
    VALID = "VALID"
    WARNING = "WARNING"
    NON_STANDARD = "NON_STANDARD"
    ERROR = "ERROR"


class PsetValidationResult(BaseModel):
    element_tag: str
    element_class: str
    pset_name: str
    property_name: str
    status: PsetValidationStatus
    message: str
    expected_type: Optional[str] = None
    actual_value: Any = None


# Core standard IFC4 Property Sets definition map
STANDARD_IFC4_PSETS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "Pset_WallCommon": {
        "Reference": {"type": "Label", "description": "Reference ID for wall type"},
        "AcousticRating": {"type": "Label", "description": "Acoustic sound transmission rating"},
        "FireRating": {"type": "Label", "description": "Fire resistance rating"},
        "Combustible": {"type": "Boolean", "description": "Indicates whether material is combustible"},
        "SurfaceSpreadOfFlame": {"type": "Label", "description": "Flame spread classification"},
        "ThermalTransmittance": {"type": "Real", "description": "U-value thermal transmittance"},
        "IsExternal": {"type": "Boolean", "description": "Indicates whether element is external"},
        "LoadBearing": {"type": "Boolean", "description": "Indicates whether wall carries structural load"},
        "ExtendToStructure": {"type": "Boolean", "description": "Indicates whether wall extends to structure above"},
        "Compartmentation": {"type": "Boolean", "description": "Indicates whether wall acts as fire compartment"},
    },
    "Pset_DoorCommon": {
        "Reference": {"type": "Label", "description": "Reference ID for door type"},
        "AcousticRating": {"type": "Label", "description": "Acoustic rating"},
        "FireRating": {"type": "Label", "description": "Fire resistance rating"},
        "IsExternal": {"type": "Boolean", "description": "External or internal door"},
        "Infiltration": {"type": "Real", "description": "Infiltration rate"},
        "ThermalTransmittance": {"type": "Real", "description": "Thermal transmittance U-value"},
        "GlazingAreaFraction": {"type": "Real", "description": "Fraction of door area that is glazed"},
        "Handing": {
            "type": "Label",
            "enum_values": ["LEFT", "RIGHT", "BOTH", "NOTDEFINED"],
            "description": "Door swing handing direction",
        },
        "SecurityRating": {"type": "Label", "description": "Security classification"},
    },
    "Pset_WindowCommon": {
        "Reference": {"type": "Label", "description": "Reference ID for window type"},
        "AcousticRating": {"type": "Label", "description": "Acoustic rating"},
        "FireRating": {"type": "Label", "description": "Fire resistance rating"},
        "IsExternal": {"type": "Boolean", "description": "External or internal window"},
        "ThermalTransmittance": {"type": "Real", "description": "Thermal transmittance U-value"},
        "GlazingAreaFraction": {"type": "Real", "description": "Glazed fraction"},
        "SecurityRating": {"type": "Label", "description": "Security rating"},
        "SolarHeatGainTransmittance": {"type": "Real", "description": "SHGC value"},
    },
    "Pset_BeamCommon": {
        "Reference": {"type": "Label", "description": "Reference ID"},
        "AcousticRating": {"type": "Label", "description": "Acoustic rating"},
        "FireRating": {"type": "Label", "description": "Fire rating"},
        "LoadBearing": {"type": "Boolean", "description": "Structural load bearing"},
        "IsExternal": {"type": "Boolean", "description": "External beam"},
        "Slope": {"type": "Real", "description": "Beam slope angle"},
    },
    "Pset_ColumnCommon": {
        "Reference": {"type": "Label", "description": "Reference ID"},
        "AcousticRating": {"type": "Label", "description": "Acoustic rating"},
        "FireRating": {"type": "Label", "description": "Fire rating"},
        "LoadBearing": {"type": "Boolean", "description": "Structural load bearing"},
        "IsExternal": {"type": "Boolean", "description": "External column"},
        "Slope": {"type": "Real", "description": "Column slope angle"},
    },
    "Pset_SlabCommon": {
        "Reference": {"type": "Label", "description": "Reference ID"},
        "AcousticRating": {"type": "Label", "description": "Acoustic rating"},
        "FireRating": {"type": "Label", "description": "Fire rating"},
        "LoadBearing": {"type": "Boolean", "description": "Load bearing"},
        "IsExternal": {"type": "Boolean", "description": "External slab"},
        "Compartmentation": {"type": "Boolean", "description": "Fire compartmentation"},
        "ThermalTransmittance": {"type": "Real", "description": "Thermal transmittance U-value"},
        "PitchAngle": {"type": "Real", "description": "Slab pitch angle"},
    },
    "Pset_RoofCommon": {
        "Reference": {"type": "Label", "description": "Reference ID"},
        "AcousticRating": {"type": "Label", "description": "Acoustic rating"},
        "FireRating": {"type": "Label", "description": "Fire rating"},
        "IsExternal": {"type": "Boolean", "description": "External roof"},
        "ThermalTransmittance": {"type": "Real", "description": "Thermal transmittance U-value"},
        "ProjectedArea": {"type": "Real", "description": "Projected plan area"},
    },
    "Pset_SanitaryTerminalTypeCommon": {
        "Reference": {"type": "Label", "description": "Reference ID"},
        "Status": {"type": "Label", "description": "Operational status"},
    },
    "Pset_AirTerminalTypeCommon": {
        "Reference": {"type": "Label", "description": "Reference ID"},
        "AirFlowType": {"type": "Label", "description": "Air flow distribution pattern"},
        "AirFlowRateMax": {"type": "Real", "description": "Maximum air flow rate"},
        "AirFlowRateMin": {"type": "Real", "description": "Minimum air flow rate"},
    },
    "Pset_LightFixtureTypeCommon": {
        "Reference": {"type": "Label", "description": "Reference ID"},
        "MaintenanceFactor": {"type": "Real", "description": "Maintenance factor fraction"},
    },
    "Pset_ChillerTypeCommon": {
        "Reference": {"type": "Label", "description": "Reference ID"},
        "NominalCapacity": {"type": "Real", "description": "Nominal cooling capacity"},
        "RefrigerantClass": {"type": "Label", "description": "Refrigerant fluid classification"},
    },
    "Pset_CoveringCommon": {
        "Reference": {"type": "Label", "description": "Reference ID"},
        "FireRating": {"type": "Label", "description": "Fire rating"},
        "AcousticRating": {"type": "Label", "description": "Acoustic rating"},
    },
    "Pset_RailingCommon": {
        "Reference": {"type": "Label", "description": "Reference ID"},
        "Height": {"type": "Real", "description": "Railing height"},
    },
    "Pset_StairCommon": {
        "Reference": {"type": "Label", "description": "Reference ID"},
        "NumberOfRisers": {"type": "Integer", "description": "Number of risers"},
        "NumberOfTreads": {"type": "Integer", "description": "Number of treads"},
        "RiserHeight": {"type": "Real", "description": "Height of risers"},
        "TreadLength": {"type": "Real", "description": "Length of treads"},
    },
    "Pset_PlateCommon": {
        "Reference": {"type": "Label", "description": "Reference ID"},
        "AcousticRating": {"type": "Label", "description": "Acoustic rating"},
        "FireRating": {"type": "Label", "description": "Fire rating"},
        "LoadBearing": {"type": "Boolean", "description": "Load bearing"},
        "IsExternal": {"type": "Boolean", "description": "External plate"},
    },
    "Pset_CurtainWallCommon": {
        "Reference": {"type": "Label", "description": "Reference ID"},
        "AcousticRating": {"type": "Label", "description": "Acoustic rating"},
        "FireRating": {"type": "Label", "description": "Fire rating"},
        "IsExternal": {"type": "Boolean", "description": "External curtain wall"},
    },
}


def get_property_expected_type(pset_name: str, property_name: str) -> Optional[str]:
    """Return the expected buildingSMART type for a property within a standard Pset."""
    pset_def = STANDARD_IFC4_PSETS.get(pset_name)
    if pset_def and property_name in pset_def:
        return pset_def[property_name].get("type")
    return None


def coerce_pset_properties(pset_name: str, properties: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coerce raw input dictionary property values into strictly typed Python primitives
    matching the buildingSMART bSDD expected types where possible.
    """
    coerced: Dict[str, Any] = {}
    for p_name, p_val in properties.items():
        exp_type = get_property_expected_type(pset_name, p_name)
        if exp_type == "Boolean":
            if isinstance(p_val, bool):
                coerced[p_name] = p_val
            elif isinstance(p_val, str):
                coerced[p_name] = p_val.strip().lower() in ("true", "1", "yes", "t")
            else:
                coerced[p_name] = bool(p_val)
        elif exp_type == "Integer":
            try:
                coerced[p_name] = int(p_val)
            except (ValueError, TypeError):
                coerced[p_name] = p_val
        elif exp_type in ("Real", "Float"):
            try:
                coerced[p_name] = float(p_val)
            except (ValueError, TypeError):
                coerced[p_name] = p_val
        elif exp_type in ("Label", "String"):
            coerced[p_name] = str(p_val) if p_val is not None else ""
        else:
            coerced[p_name] = p_val
    return coerced


def get_element_properties(element: Any) -> Dict[str, Dict[str, Any]]:
    """Extract property sets map from any element instance or dict representation."""
    if hasattr(element, "properties") and getattr(element, "properties"):
        return getattr(element, "properties")
    if hasattr(element, "psets") and getattr(element, "psets"):
        return getattr(element, "psets")
    if isinstance(element, dict):
        if "properties" in element and element["properties"]:
            return element["properties"]
        if "psets" in element and element["psets"]:
            return element["psets"]
    return {}


def validate_element_psets(element: Any) -> List[PsetValidationResult]:
    """
    Validate all Property Sets attached to an element against buildingSMART specifications.
    Returns a list of PsetValidationResult entries.
    """
    results: List[PsetValidationResult] = []

    tag = getattr(element, "tag", None) or (element.get("tag") if isinstance(element, dict) else "UNKNOWN")
    elem_cls = getattr(element, "ifc_class", None) or getattr(element, "class_", None)
    if not elem_cls:
        elem_cls = element.__class__.__name__ if hasattr(element, "__class__") else "Unknown"

    psets_map = get_element_properties(element)
    if not psets_map:
        return results

    for pset_name, pset_props in psets_map.items():
        if not isinstance(pset_props, dict):
            results.append(
                PsetValidationResult(
                    element_tag=tag,
                    element_class=elem_cls,
                    pset_name=pset_name,
                    property_name="*",
                    status=PsetValidationStatus.ERROR,
                    message=f"Property Set '{pset_name}' content must be a dictionary, got {type(pset_props).__name__}",
                    actual_value=pset_props,
                )
            )
            continue

        is_standard_pset_name = pset_name in STANDARD_IFC4_PSETS
        starts_with_pset = pset_name.startswith("Pset_")

        if starts_with_pset and not is_standard_pset_name:
            results.append(
                PsetValidationResult(
                    element_tag=tag,
                    element_class=elem_cls,
                    pset_name=pset_name,
                    property_name="*",
                    status=PsetValidationStatus.NON_STANDARD,
                    message=f"Property Set '{pset_name}' starts with 'Pset_' but is not in standard IFC4 bSDD dictionary",
                )
            )

        if not starts_with_pset:
            # Custom user defined Property Set
            for p_name, p_val in pset_props.items():
                results.append(
                    PsetValidationResult(
                        element_tag=tag,
                        element_class=elem_cls,
                        pset_name=pset_name,
                        property_name=p_name,
                        status=PsetValidationStatus.NON_STANDARD,
                        message="User-defined custom property set",
                        actual_value=p_val,
                    )
                )
            continue

        # Standard Pset processing
        if is_standard_pset_name:
            schema_props = STANDARD_IFC4_PSETS[pset_name]
            for p_name, p_val in pset_props.items():
                if p_name not in schema_props:
                    results.append(
                        PsetValidationResult(
                            element_tag=tag,
                            element_class=elem_cls,
                            pset_name=pset_name,
                            property_name=p_name,
                            status=PsetValidationStatus.NON_STANDARD,
                            message=f"Property '{p_name}' is non-standard for '{pset_name}'",
                            actual_value=p_val,
                        )
                    )
                    continue

                prop_def = schema_props[p_name]
                exp_type = prop_def["type"]
                enum_vals = prop_def.get("enum_values")

                # Validate data types
                if exp_type == "Boolean":
                    if isinstance(p_val, bool):
                        results.append(
                            PsetValidationResult(
                                element_tag=tag,
                                element_class=elem_cls,
                                pset_name=pset_name,
                                property_name=p_name,
                                status=PsetValidationStatus.VALID,
                                message="Valid Boolean property",
                                expected_type=exp_type,
                                actual_value=p_val,
                            )
                        )
                    else:
                        results.append(
                            PsetValidationResult(
                                element_tag=tag,
                                element_class=elem_cls,
                                pset_name=pset_name,
                                property_name=p_name,
                                status=PsetValidationStatus.ERROR,
                                message=f"Data type mismatch: expected Boolean, got '{p_val}' ({type(p_val).__name__})",
                                expected_type=exp_type,
                                actual_value=p_val,
                            )
                        )

                elif exp_type == "Integer":
                    if isinstance(p_val, int) and not isinstance(p_val, bool):
                        results.append(
                            PsetValidationResult(
                                element_tag=tag,
                                element_class=elem_cls,
                                pset_name=pset_name,
                                property_name=p_name,
                                status=PsetValidationStatus.VALID,
                                message="Valid Integer property",
                                expected_type=exp_type,
                                actual_value=p_val,
                            )
                        )
                    else:
                        results.append(
                            PsetValidationResult(
                                element_tag=tag,
                                element_class=elem_cls,
                                pset_name=pset_name,
                                property_name=p_name,
                                status=PsetValidationStatus.ERROR,
                                message=f"Data type mismatch: expected Integer, got '{p_val}' ({type(p_val).__name__})",
                                expected_type=exp_type,
                                actual_value=p_val,
                            )
                        )

                elif exp_type in ("Real", "Float"):
                    if isinstance(p_val, (float, int)) and not isinstance(p_val, bool):
                        results.append(
                            PsetValidationResult(
                                element_tag=tag,
                                element_class=elem_cls,
                                pset_name=pset_name,
                                property_name=p_name,
                                status=PsetValidationStatus.VALID,
                                message="Valid Real/Float property",
                                expected_type=exp_type,
                                actual_value=p_val,
                            )
                        )
                    else:
                        results.append(
                            PsetValidationResult(
                                element_tag=tag,
                                element_class=elem_cls,
                                pset_name=pset_name,
                                property_name=p_name,
                                status=PsetValidationStatus.ERROR,
                                message=f"Data type mismatch: expected Real/Float, got '{p_val}' ({type(p_val).__name__})",
                                expected_type=exp_type,
                                actual_value=p_val,
                            )
                        )

                elif exp_type in ("Label", "String"):
                    if enum_vals and p_val not in enum_vals:
                        results.append(
                            PsetValidationResult(
                                element_tag=tag,
                                element_class=elem_cls,
                                pset_name=pset_name,
                                property_name=p_name,
                                status=PsetValidationStatus.ERROR,
                                message=f"Value '{p_val}' not in allowed enumerated choices: {enum_vals}",
                                expected_type=exp_type,
                                actual_value=p_val,
                            )
                        )
                    elif isinstance(p_val, str):
                        results.append(
                            PsetValidationResult(
                                element_tag=tag,
                                element_class=elem_cls,
                                pset_name=pset_name,
                                property_name=p_name,
                                status=PsetValidationStatus.VALID,
                                message="Valid Label/String property",
                                expected_type=exp_type,
                                actual_value=p_val,
                            )
                        )
                    else:
                        results.append(
                            PsetValidationResult(
                                element_tag=tag,
                                element_class=elem_cls,
                                pset_name=pset_name,
                                property_name=p_name,
                                status=PsetValidationStatus.WARNING,
                                message=f"Expected string/label, got type {type(p_val).__name__}",
                                expected_type=exp_type,
                                actual_value=p_val,
                            )
                        )

    return results


def validate_manifest_psets(manifest: Any) -> List[PsetValidationResult]:
    """Validate Property Sets across all elements declared in a ProjectManifest."""
    all_results: List[PsetValidationResult] = []

    elements = getattr(manifest, "elements", []) or []
    proxies = getattr(manifest, "proxies", []) or []

    for elem in list(elements) + list(proxies):
        res = validate_element_psets(elem)
        all_results.extend(res)

    return all_results
