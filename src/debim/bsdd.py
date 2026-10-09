"""
buildingSMART bSDD (Building Data Dictionary) Pset Validation Engine for debim.
Validates standard and custom Property Sets (Pset_*) against buildingSMART IFC4 specifications.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

from debim.schema import ProjectManifest, IfcCustomElement, IfcBuildingElementProxy


class PropertyValidationStatus(str, Enum):
    VALID = "VALID"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    NON_STANDARD_PROPERTY = "NON_STANDARD_PROPERTY"
    NON_STANDARD_PSET = "NON_STANDARD_PSET"
    VALUE_CONSTRAINT_VIOLATION = "VALUE_CONSTRAINT_VIOLATION"


class PsetValidationResult(BaseModel):
    element_tag: str
    pset_name: str
    property_name: str
    expected_type: Optional[str] = None
    actual_type: str
    actual_value: Any = None
    status: PropertyValidationStatus
    message: str


# Core standard IFC4 Property Sets (Pset_*Common) based on buildingSMART specification
BSDD_STANDARD_PSETS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "Pset_WallCommon": {
        "Reference": {"type": "String"},
        "IsExternal": {"type": "Boolean"},
        "LoadBearing": {"type": "Boolean"},
        "ExtendToStructure": {"type": "Boolean"},
        "ThermalTransmittance": {"type": "Float"},
        "AcousticRating": {"type": "String"},
        "FireRating": {"type": "String"},
        "Combustible": {"type": "Boolean"},
        "Compartmentation": {"type": "Boolean"},
    },
    "Pset_DoorCommon": {
        "Reference": {"type": "String"},
        "IsExternal": {"type": "Boolean"},
        "FireRating": {"type": "String"},
        "AcousticRating": {"type": "String"},
        "SecurityRating": {"type": "String"},
        "DurationOfRating": {"type": "Float"},
        "ThermalTransmittance": {"type": "Float"},
        "Infiltration": {"type": "Float"},
        "IsLanding": {"type": "Boolean"},
        "OperationType": {
            "type": "Enum",
            "choices": [
                "SINGLE_SWING_LEFT",
                "SINGLE_SWING_RIGHT",
                "DOUBLE_DOOR_SINGLE_ACTING",
                "DOUBLE_DOOR_DOUBLE_ACTING",
                "DOUBLE_SWING",
                "SLIDING",
                "FOLDING",
                "REVOLVING",
                "ROLLING",
                "USERDEFINED",
                "NOTDEFINED",
            ],
        },
    },
    "Pset_WindowCommon": {
        "Reference": {"type": "String"},
        "IsExternal": {"type": "Boolean"},
        "FireRating": {"type": "String"},
        "AcousticRating": {"type": "String"},
        "SecurityRating": {"type": "String"},
        "ThermalTransmittance": {"type": "Float"},
        "Infiltration": {"type": "Float"},
        "PartitioningType": {
            "type": "Enum",
            "choices": [
                "SINGLE_PANEL",
                "DOUBLE_PANEL_VERTICAL",
                "DOUBLE_PANEL_HORIZONTAL",
                "TRIPLE_PANEL_VERTICAL",
                "TRIPLE_PANEL_HORIZONTAL",
                "USERDEFINED",
                "NOTDEFINED",
            ],
        },
    },
    "Pset_BeamCommon": {
        "Reference": {"type": "String"},
        "IsExternal": {"type": "Boolean"},
        "LoadBearing": {"type": "Boolean"},
        "FireRating": {"type": "String"},
        "Slope": {"type": "Float"},
        "Span": {"type": "Float"},
    },
    "Pset_ColumnCommon": {
        "Reference": {"type": "String"},
        "IsExternal": {"type": "Boolean"},
        "LoadBearing": {"type": "Boolean"},
        "FireRating": {"type": "String"},
        "Slope": {"type": "Float"},
    },
    "Pset_SlabCommon": {
        "Reference": {"type": "String"},
        "IsExternal": {"type": "Boolean"},
        "LoadBearing": {"type": "Boolean"},
        "FireRating": {"type": "String"},
        "AcousticRating": {"type": "String"},
        "ThermalTransmittance": {"type": "Float"},
        "Compartmentation": {"type": "Boolean"},
    },
    "Pset_RoofCommon": {
        "Reference": {"type": "String"},
        "IsExternal": {"type": "Boolean"},
        "FireRating": {"type": "String"},
        "ThermalTransmittance": {"type": "Float"},
        "AcousticRating": {"type": "String"},
    },
    "Pset_SanitaryTerminalTypeCommon": {
        "Reference": {"type": "String"},
        "Status": {"type": "String"},
    },
    "Pset_AirTerminalTypeCommon": {
        "Reference": {"type": "String"},
        "Status": {"type": "String"},
        "AirFlowRate": {"type": "Float"},
    },
    "Pset_LightFixtureTypeCommon": {
        "Reference": {"type": "String"},
        "Status": {"type": "String"},
        "NumberOfSources": {"type": "Integer"},
    },
    "Pset_ChillerTypeCommon": {
        "Reference": {"type": "String"},
        "Status": {"type": "String"},
        "NominalCapacity": {"type": "Float"},
        "RefrigerantClass": {"type": "String"},
    },
    "Pset_PumpTypeCommon": {
        "Reference": {"type": "String"},
        "Status": {"type": "String"},
        "FlowRate": {"type": "Float"},
        "ImpellerDiameter": {"type": "Float"},
    },
    "Pset_BoilerTypeCommon": {
        "Reference": {"type": "String"},
        "Status": {"type": "String"},
        "NominalCapacity": {"type": "Float"},
        "EnergySource": {"type": "String"},
    },
    "Pset_FanTypeCommon": {
        "Reference": {"type": "String"},
        "Status": {"type": "String"},
        "NominalAirFlowRate": {"type": "Float"},
        "OperationMode": {"type": "String"},
    },
    "Pset_SpaceCommon": {
        "Reference": {"type": "String"},
        "IsExternal": {"type": "Boolean"},
        "Category": {"type": "String"},
        "FloorCovering": {"type": "String"},
        "WallCovering": {"type": "String"},
        "CeilingCovering": {"type": "String"},
    },
    "Pset_BuildingElementProxyCommon": {
        "Reference": {"type": "String"},
        "IsExternal": {"type": "Boolean"},
        "FireRating": {"type": "String"},
    },
}


def _check_type(val: Any, expected_type: str, choices: Optional[List[str]] = None) -> PropertyValidationStatus:
    if expected_type == "Boolean":
        if isinstance(val, bool):
            return PropertyValidationStatus.VALID
        return PropertyValidationStatus.TYPE_MISMATCH

    elif expected_type in ("Float", "Real"):
        if isinstance(val, bool):
            return PropertyValidationStatus.TYPE_MISMATCH
        if isinstance(val, (float, int)):
            return PropertyValidationStatus.VALID
        return PropertyValidationStatus.TYPE_MISMATCH

    elif expected_type == "Integer":
        if isinstance(val, bool):
            return PropertyValidationStatus.TYPE_MISMATCH
        if isinstance(val, int):
            return PropertyValidationStatus.VALID
        return PropertyValidationStatus.TYPE_MISMATCH

    elif expected_type in ("String", "Label"):
        if isinstance(val, str):
            return PropertyValidationStatus.VALID
        return PropertyValidationStatus.TYPE_MISMATCH

    elif expected_type == "Enum":
        if not isinstance(val, str):
            return PropertyValidationStatus.TYPE_MISMATCH
        if choices:
            upper_choices = [c.upper() for c in choices]
            if val.upper() not in upper_choices:
                return PropertyValidationStatus.VALUE_CONSTRAINT_VIOLATION
        return PropertyValidationStatus.VALID

    return PropertyValidationStatus.VALID


def validate_pset(pset_name: str, pset_data: Dict[str, Any], element_tag: str = "UNKNOWN") -> List[PsetValidationResult]:
    results: List[PsetValidationResult] = []

    if not isinstance(pset_data, dict):
        return results

    is_standard_pset = pset_name in BSDD_STANDARD_PSETS
    schema_pset = BSDD_STANDARD_PSETS.get(pset_name, {})

    if pset_name.startswith("Pset_") and not is_standard_pset:
        # Non-standard Pset starting with Pset_
        results.append(
            PsetValidationResult(
                element_tag=element_tag,
                pset_name=pset_name,
                property_name="*",
                expected_type=None,
                actual_type=type(pset_data).__name__,
                actual_value=None,
                status=PropertyValidationStatus.NON_STANDARD_PSET,
                message=f"Property set '{pset_name}' is not in buildingSMART standard IFC4 Pset dictionary.",
            )
        )

    for prop_name, prop_val in pset_data.items():
        actual_type_str = type(prop_val).__name__

        if is_standard_pset:
            if prop_name in schema_pset:
                prop_schema = schema_pset[prop_name]
                exp_type = prop_schema["type"]
                choices = prop_schema.get("choices")

                status = _check_type(prop_val, exp_type, choices)

                if status == PropertyValidationStatus.VALID:
                    msg = f"Property '{prop_name}' matches bSDD specification."
                elif status == PropertyValidationStatus.TYPE_MISMATCH:
                    msg = f"Property '{prop_name}' in '{pset_name}' expects type '{exp_type}', got '{actual_type_str}' ({repr(prop_val)})."
                elif status == PropertyValidationStatus.VALUE_CONSTRAINT_VIOLATION:
                    msg = f"Property '{prop_name}' value '{prop_val}' is not one of allowed enum choices: {choices}."
                else:
                    msg = f"Property '{prop_name}' validation status: {status}."

                results.append(
                    PsetValidationResult(
                        element_tag=element_tag,
                        pset_name=pset_name,
                        property_name=prop_name,
                        expected_type=exp_type,
                        actual_type=actual_type_str,
                        actual_value=prop_val,
                        status=status,
                        message=msg,
                    )
                )
            else:
                # Property not in standard schema for this Pset
                results.append(
                    PsetValidationResult(
                        element_tag=element_tag,
                        pset_name=pset_name,
                        property_name=prop_name,
                        expected_type=None,
                        actual_type=actual_type_str,
                        actual_value=prop_val,
                        status=PropertyValidationStatus.NON_STANDARD_PROPERTY,
                        message=f"Property '{prop_name}' is not a standard property in buildingSMART '{pset_name}'.",
                    )
                )
        else:
            # Custom Pset property
            results.append(
                PsetValidationResult(
                    element_tag=element_tag,
                    pset_name=pset_name,
                    property_name=prop_name,
                    expected_type=None,
                    actual_type=actual_type_str,
                    actual_value=prop_val,
                    status=PropertyValidationStatus.VALID if not pset_name.startswith("Pset_") else PropertyValidationStatus.NON_STANDARD_PSET,
                    message=f"Custom property '{prop_name}' in '{pset_name}'.",
                )
            )

    return results


def validate_element_psets(element: Any) -> List[PsetValidationResult]:
    results: List[PsetValidationResult] = []

    tag = getattr(element, "tag", None) or "ELEMENT"

    properties = getattr(element, "properties", None)
    if not properties and isinstance(element, dict):
        properties = element.get("properties")

    if isinstance(properties, dict):
        for pset_name, pset_data in properties.items():
            if isinstance(pset_data, dict):
                results.extend(validate_pset(pset_name, pset_data, element_tag=tag))

    return results


def validate_manifest_psets(manifest: ProjectManifest) -> List[PsetValidationResult]:
    results: List[PsetValidationResult] = []

    all_elements = list(manifest.elements)

    if hasattr(manifest, "proxies") and manifest.proxies:
        all_elements.extend(manifest.proxies)

    for elem in all_elements:
        results.extend(validate_element_psets(elem))

    return results
