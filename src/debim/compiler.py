import re
"""
IFC4 Compiler & STEP Physical File Exporter for debim.
Compiles ProjectManifest or ResolvedManifest into standard buildingSMART IFC4 file format.
"""

import os
import math
import uuid
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from debim.bsdd import BSDD_STANDARD_PSETS
from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedCurtainWall,
    ResolvedCustomElement,
    ResolvedDoor,
    ResolvedManifest,
    ResolvedPlate,
    ResolvedProxy,
    ResolvedRevolvedArea,
    ResolvedSweptDisk,
    ResolvedTerminal,
    ResolvedWall,
    ResolvedWindow,
    resolve_manifest,
)
from debim.schema import (
    IFC4_DISTRIBUTION_8_ATTR_CLASSES,
    IFC4_DISTRIBUTION_9_ATTR_CLASSES,
    ProjectManifest,
    RevolvedAreaSolid,
    SweptDiskSolid,
    load_manifest,
)
from debim.schema_registry import SchemaEntityRegistry

_SCHEMA_REGISTRY: Optional[SchemaEntityRegistry] = None


def get_schema_registry() -> SchemaEntityRegistry:
    """Get or lazily initialize the singleton SchemaEntityRegistry."""
    global _SCHEMA_REGISTRY
    if _SCHEMA_REGISTRY is None:
        _SCHEMA_REGISTRY = SchemaEntityRegistry("IFC4")
    return _SCHEMA_REGISTRY


def generate_fallback_solid_ifcopenshell(
    model: Any,
    product_obj: Any,
    body_context: Any,
    dimensions: Tuple[float, float, float] = (0.5, 0.5, 0.5),
    shared_profile: Any = None,
    shared_pos3d: Any = None,
    shared_ext_dir: Any = None,
) -> Any:
    """Generate an oriented 3D bounding box solid representation using IfcExtrudedAreaSolid for any long-tail entity."""
    w, d, h = float(dimensions[0]), float(dimensions[1]), float(dimensions[2])
    w = max(w, 0.05)
    d = max(d, 0.05)
    h = max(h, 0.05)

    if shared_profile is None:
        pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
        profile = model.createIfcRectangleProfileDef("AREA", None, pos2d, w, d)
    else:
        profile = shared_profile

    if shared_pos3d is None:
        pos3d = model.createIfcAxis2Placement3D(
            model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
            model.createIfcDirection((0.0, 0.0, 1.0)),
            model.createIfcDirection((1.0, 0.0, 0.0)),
        )
    else:
        pos3d = shared_pos3d

    ext_dir = shared_ext_dir if shared_ext_dir is not None else model.createIfcDirection((0.0, 0.0, 1.0))

    solid = model.createIfcExtrudedAreaSolid(
        profile, pos3d, ext_dir, h
    )
    rep = model.createIfcShapeRepresentation(
        body_context, "Body", "SweptSolid", [solid]
    )
    if hasattr(product_obj, "Representation"):
        prod_shape = model.createIfcProductDefinitionShape(Representations=[rep])
        product_obj.Representation = prod_shape
    return rep


def bind_default_psets_ifcopenshell(
    model: Any,
    product_obj: Any,
    entity_class: str,
    custom_properties: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[Any]:
    """Automatically bind default Pset_*Common property sets via bSDD definitions."""
    reg = get_schema_registry()
    default_psets = reg.get_default_psets(entity_class)
    bound_psets = []

    all_psets: Dict[str, Dict[str, Any]] = {}

    for pset_name in default_psets:
        schema_props = BSDD_STANDARD_PSETS.get(pset_name, {})
        default_props = {}
        for prop_name, prop_spec in schema_props.items():
            prop_type = prop_spec.get("type")
            if prop_name == "Reference":
                default_props[prop_name] = getattr(product_obj, "Name", None) or "DEFAULT"
            elif prop_name == "Status":
                default_props[prop_name] = "NEW"
            elif prop_type == "Boolean":
                default_props[prop_name] = False
            elif prop_type in ("Float", "Real"):
                default_props[prop_name] = 0.0
            elif prop_type == "Integer":
                default_props[prop_name] = 0
            else:
                default_props[prop_name] = "UNSPECIFIED"
        all_psets[pset_name] = default_props

    if custom_properties:
        for pset_name, props in custom_properties.items():
            if pset_name in all_psets:
                all_psets[pset_name].update(props)
            else:
                all_psets[pset_name] = dict(props)

    for pset_name, props in all_psets.items():
        try:
            prop_objs = []
            for p_key, p_val in props.items():
                if isinstance(p_val, bool):
                    v_obj = model.createIfcBoolean(p_val)
                elif isinstance(p_val, int):
                    v_obj = model.createIfcInteger(p_val)
                elif isinstance(p_val, float):
                    v_obj = model.createIfcReal(float(p_val))
                else:
                    v_obj = model.createIfcLabel(str(p_val))
                psv = model.createIfcPropertySingleValue(p_key, None, v_obj, None)
                prop_objs.append(psv)

            pset_obj = model.createIfcPropertySet(
                generate_ifc_guid(),
                None,
                pset_name,
                None,
                prop_objs,
            )
            model.createIfcRelDefinesByProperties(
                generate_ifc_guid(),
                None,
                None,
                None,
                [product_obj],
                pset_obj,
            )
            bound_psets.append(pset_obj)
        except Exception:
            pass

    return bound_psets


def generate_fallback_solid_step(
    serializer: "StepSerializer",
    body_context_ref: str,
    dimensions: Tuple[float, float, float] = (0.5, 0.5, 0.5),
) -> str:
    """Generate an oriented 3D bounding box solid representation in STEP for long-tail entities."""
    w = max(float(dimensions[0]), 0.05)
    d = max(float(dimensions[1]), 0.05)
    h = max(float(dimensions[2]), 0.05)

    pos2d = serializer.create_entity("IfcCartesianPoint", (0.0, 0.0))
    axis2d = serializer.create_entity("IfcAxis2Placement2D", pos2d, None)
    rec_prof = serializer.create_entity("IfcRectangleProfileDef", ".AREA.", None, axis2d, w, d)

    pos3d = serializer.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
    axis3d = serializer.create_entity("IfcAxis2Placement3D", pos3d, None, None)
    ext_dir = serializer.create_entity("IfcDirection", (0.0, 0.0, 1.0))
    solid = serializer.create_entity("IfcExtrudedAreaSolid", rec_prof, axis3d, ext_dir, h)

    shape_rep = serializer.create_entity(
        "IfcShapeRepresentation",
        body_context_ref,
        "Body",
        "SweptSolid",
        [solid],
    )
    return serializer.create_entity(
        "IfcProductDefinitionShape", None, None, [shape_rep]
    )


def bind_default_psets_step(
    serializer: "StepSerializer",
    product_ref: str,
    entity_class: str,
    custom_properties: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[str]:
    """Automatically bind default Pset_*Common property sets via bSDD definitions in STEP serializer."""
    reg = get_schema_registry()
    default_psets = reg.get_default_psets(entity_class)
    bound_psets = []

    all_psets: Dict[str, Dict[str, Any]] = {}

    for pset_name in default_psets:
        schema_props = BSDD_STANDARD_PSETS.get(pset_name, {})
        default_props = {}
        for prop_name, prop_spec in schema_props.items():
            prop_type = prop_spec.get("type")
            if prop_name == "Reference":
                default_props[prop_name] = "DEFAULT"
            elif prop_name == "Status":
                default_props[prop_name] = "NEW"
            elif prop_type == "Boolean":
                default_props[prop_name] = False
            elif prop_type in ("Float", "Real"):
                default_props[prop_name] = 0.0
            elif prop_type == "Integer":
                default_props[prop_name] = 0
            else:
                default_props[prop_name] = "UNSPECIFIED"
        all_psets[pset_name] = default_props

    if custom_properties:
        for pset_name, props in custom_properties.items():
            if pset_name in all_psets:
                all_psets[pset_name].update(props)
            else:
                all_psets[pset_name] = dict(props)

    for pset_name, props in all_psets.items():
        prop_refs = []
        for p_key, p_val in props.items():
            if isinstance(p_val, bool):
                v_ref = serializer.create_entity("IfcBoolean", p_val)
            elif isinstance(p_val, int):
                v_ref = serializer.create_entity("IfcInteger", p_val)
            elif isinstance(p_val, float):
                v_ref = serializer.create_entity("IfcReal", float(p_val))
            else:
                v_ref = serializer.create_entity("IfcLabel", str(p_val))
            psv = serializer.create_entity("IfcPropertySingleValue", p_key, None, v_ref, None)
            prop_refs.append(psv)

        pset_ref = serializer.create_entity(
            "IfcPropertySet",
            generate_ifc_guid(),
            None,
            pset_name,
            None,
            prop_refs,
        )
        serializer.create_entity(
            "IfcRelDefinesByProperties",
            generate_ifc_guid(),
            None,
            None,
            None,
            [product_ref],
            pset_ref,
        )
        bound_psets.append(pset_ref)

    return bound_psets


def _build_transform_matrix(
    position: Tuple[float, float, float],
    rotation: Optional[Tuple[float, float, float]] = None,
):
    """Build a 4x4 affine transformation matrix for 3D position and Euler rotations (rx, ry, rz in degrees)."""
    import math
    import numpy as np

    x, y, z = position
    rx, ry, rz = rotation if rotation else (0.0, 0.0, 0.0)

    rx_r = math.radians(float(rx))
    ry_r = math.radians(float(ry))
    rz_r = math.radians(float(rz))

    cx, sx = math.cos(rx_r), math.sin(rx_r)
    cy, sy = math.cos(ry_r), math.sin(ry_r)
    cz, sz = math.cos(rz_r), math.sin(rz_r)

    R = np.array(
        [
            [cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
            [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
            [-sy, cy * sx, cy * cx],
        ]
    )

    mat = np.eye(4)
    mat[:3, :3] = R
    mat[0, 3] = float(x)
    mat[1, 3] = float(y)
    mat[2, 3] = float(z)
    return mat


def derive_custom_ifc_class(layer: Optional[str]) -> str:
    """Derive appropriate target IFC entity class for a custom element based on its layer."""
    if not layer:
        return "IfcBuildingElementProxy"
    l = layer.lower()
    if "furn" in l:
        return "IfcFurnishingElement"
    if "railing" in l:
        return "IfcRailing"
    if "member" in l:
        return "IfcMember"
    if "plate" in l:
        return "IfcPlate"
    if "part" in l or "buildingelementpart" in l:
        return "IfcBuildingElementPart"
    if "covering" in l:
        return "IfcCovering"
    if "stairflight" in l or "stair_flight" in l or "stair flight" in l or "stairflights" in l:
        return "IfcStairFlight"
    if "stair" in l:
        return "IfcStair"
    if "footing" in l:
        return "IfcFooting"
    if "proxy" in l:
        return "IfcBuildingElementProxy"
    if "bridgepart" in l or "bridge_part" in l:
        return "IfcBridgePart"
    if "bearing" in l:
        return "IfcBearing"
    if "marine" in l or "berth" in l or "quay" in l or "jetty" in l:
        return "IfcMarinePart"
    if "chimney" in l:
        return "IfcChimney"
    if "accessory" in l or "accessories" in l or "accessor" in l:
        return "IfcDiscreteAccessory"
    if "duct" in l:
        return "IfcDuctSegment"
    if "pipe" in l:
        return "IfcPipeSegment"
    if "waste" in l or "drainage" in l:
        return "IfcWasteTerminal"
    if "sanitary" in l:
        return "IfcSanitaryTerminal"
    if "pump" in l:
        return "IfcPump"
    if "chiller" in l:
        return "IfcChiller"
    if "boiler" in l:
        return "IfcBoiler"
    if "tank" in l:
        return "IfcTank"
    if "fan" in l:
        return "IfcFan"
    if "coil" in l:
        return "IfcCoil"
    if "transformer" in l:
        return "IfcTransformer"
    if "actuator" in l:
        return "IfcActuator"
    if "sensor" in l:
        return "IfcSensor"
    if "alarm" in l:
        return "IfcAlarm"
    if "interceptor" in l:
        return "IfcInterceptor"
    if "filter" in l:
        return "IfcFilter"
    if "heater" in l:
        return "IfcSpaceHeater"
    if "lamp" in l or "light" in l:
        return "IfcLightFixture"
    if "terminal" in l or "air_terminal" in l:
        return "IfcAirTerminal"
    if "fitting" in l:
        return "IfcFlowFitting"
    if "valve" in l:
        return "IfcValve"
    if "damper" in l:
        return "IfcDamper"
    if "flow_controller" in l or "flowcontroller" in l or "flow_control" in l or "flow_controllers" in l:
        return "IfcFlowController"
    if "controller" in l:
        return "IfcController"
    if "control" in l:
        return "IfcDistributionControlElement"
    return "IfcBuildingElementProxy"


def generate_ifc_guid() -> str:
    """Generate a valid 22-character IFC base64 encoded GUID."""
    # Standard 64-char alphabet for IFC GUIDs
    base64_chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"
    u = uuid.uuid4().bytes
    # Convert 16 bytes to 22 IFC base64 characters
    res = []

    # 16 bytes = 128 bits
    # Convert bytes into integer
    val = int.from_bytes(u, byteorder="big")
    for _ in range(22):
        res.append(base64_chars[val % 64])
        val //= 64
    return "".join(reversed(res))


class StepSerializer:
    """
    Lightweight, stand-alone IFC4 STEP physical file serializer.
    Used when ifcopenshell is not installed or as a fallback.
    """

    def __init__(self, project_name: str = "debim Project"):
        self.project_name = project_name
        self.lines: List[str] = []
        self.entity_counter = 0

    def create_entity(self, type_name: str, *args) -> str:
        self.entity_counter += 1
        ref = f"#{self.entity_counter}"

        formatted_args = []
        for arg in args:
            formatted_args.append(self._format_arg(arg))

        args_str = ",".join(formatted_args)
        line = f"{ref}={type_name.upper()}({args_str});"
        self.lines.append(line)
        return ref

    def _format_arg(self, arg) -> str:
        if arg is None:
            return "$"
        elif isinstance(arg, bool):
            return ".T." if arg else ".F."
        elif isinstance(arg, str):
            if arg.startswith("#"):
                return arg
            elif arg.startswith(".") and arg.endswith("."):
                return arg
            else:
                escaped = arg.replace("'", "''")
                return f"'{escaped}'"
        elif isinstance(arg, (int, float)):
            if isinstance(arg, float):
                # Ensure float representation ends with dot or includes decimals
                s = f"{arg:.6f}".rstrip("0")
                if s.endswith("."):
                    s += "0"
                return s
            return str(arg)
        elif isinstance(arg, (list, tuple)):
            inner = ",".join(self._format_arg(item) for item in arg)
            return f"({inner})"
        return str(arg)

    def create_cartesian_point_2d(self, x: float, y: float) -> str:
        return self.create_entity("IfcCartesianPoint", (float(x), float(y)))

    def create_polyline_2d(self, points: List[Any]) -> str:
        pt_refs = []
        for p in points:
            pt_refs.append(self.create_cartesian_point_2d(float(p[0]), float(p[1])))
        if points and (points[0][0] != points[-1][0] or points[0][1] != points[-1][1]):
            pt_refs.append(pt_refs[0])
        return self.create_entity("IfcPolyline", pt_refs)

    def create_ifc_profile_def(self, prof: Any, tag: str, axis2d: str) -> str:
        shape = getattr(prof, "shape", "BOX")
        prof_name = f"{tag}_Profile"
        if shape == "CIRCULAR":
            return self.create_entity("IfcCircleProfileDef", ".AREA.", prof_name, axis2d, float(prof.radius))
        elif shape == "ELLIPSE":
            return self.create_entity("IfcEllipseProfileDef", ".AREA.", prof_name, axis2d, float(prof.semi_major_axis), float(prof.semi_minor_axis))
        elif shape in ("ISHAPE", "I", "H"):
            fillet = float(prof.fillet_radius) if getattr(prof, "fillet_radius", None) is not None else None
            return self.create_entity("IfcIShapeProfileDef", ".AREA.", prof_name, axis2d, float(prof.overall_width), float(prof.overall_depth), float(prof.web_thickness), float(prof.flange_thickness), fillet)
        elif shape in ("LSHAPE", "L"):
            return self.create_entity("IfcLShapeProfileDef", ".AREA.", prof_name, axis2d, float(prof.depth), float(prof.width), float(prof.thickness))
        elif shape in ("USHAPE", "U", "CSHAPE", "C"):
            return self.create_entity("IfcUShapeProfileDef", ".AREA.", prof_name, axis2d, float(prof.depth), float(prof.flange_width), float(prof.web_thickness), float(prof.flange_thickness))
        elif shape in ("TSHAPE", "T"):
            return self.create_entity("IfcTShapeProfileDef", ".AREA.", prof_name, axis2d, float(prof.depth), float(prof.flange_width), float(prof.web_thickness), float(prof.flange_thickness))
        elif shape in ("RHS", "RECTANGLE_HOLLOW", "BOX_HOLLOW"):
            return self.create_entity("IfcRectangleHollowProfileDef", ".AREA.", prof_name, axis2d, float(prof.width), float(prof.depth), float(prof.wall_thickness))
        elif shape in ("CHS", "CIRCLE_HOLLOW", "PIPE_HOLLOW"):
            return self.create_entity("IfcCircleHollowProfileDef", ".AREA.", prof_name, axis2d, float(prof.radius), float(prof.wall_thickness))
        elif shape in ("ARBITRARY", "ARBITRARY_CLOSED", "POLYGON", "ARBITRARY_WITH_VOIDS"):
            pts = getattr(prof, "outer_curve", None) or getattr(prof, "points", None) or []
            outer_poly = self.create_polyline_2d(pts)
            voids = getattr(prof, "inner_curves", None) or getattr(prof, "voids", None) or []
            if voids:
                inner_polys = [self.create_polyline_2d(v) for v in voids if v]
                return self.create_entity("IfcArbitraryProfileDefWithVoids", ".AREA.", prof_name, outer_poly, inner_polys)
            else:
                return self.create_entity("IfcArbitraryClosedProfileDef", ".AREA.", prof_name, outer_poly)
        else:
            return self.create_entity("IfcRectangleProfileDef", ".AREA.", prof_name, axis2d, float(prof.width), float(prof.depth))

    def _create_mep_terminal_shape(
        self, px: float, py: float, pz: float, rot_z: float, st_pl_ref: Optional[str], st_elev: float, w: float, d: float, h: float, body_context_ref: str
    ) -> Tuple[str, str]:
        rel_z = float(pz - st_elev)
        elem_pt = self.create_entity("IfcCartesianPoint", (float(px), float(py), rel_z))
        if abs(rot_z) > 1e-4:
            rz_r = math.radians(float(rot_z))
            ref_dir = self.create_entity("IfcDirection", (round(math.cos(rz_r), 6), round(math.sin(rz_r), 6), 0.0))
            axis_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
            elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, axis_dir, ref_dir)
        else:
            elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, None, None)
        elem_pl = self.create_entity("IfcLocalPlacement", st_pl_ref, elem_axis)

        w_val = float(w) if w and float(w) > 0 else 0.30
        d_val = float(d) if d and float(d) > 0 else 0.30
        h_val = float(h) if h and float(h) > 0 else 0.30

        pos2d = self.create_entity("IfcCartesianPoint", (0.0, 0.0))
        axis2d = self.create_entity("IfcAxis2Placement2D", pos2d, None)
        rec_prof = self.create_entity("IfcRectangleProfileDef", ".AREA.", None, axis2d, w_val, d_val)

        pos3d = self.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
        axis3d = self.create_entity("IfcAxis2Placement3D", pos3d, None, None)
        ext_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
        solid = self.create_entity("IfcExtrudedAreaSolid", rec_prof, axis3d, ext_dir, h_val)

        shape_rep = self.create_entity("IfcShapeRepresentation", body_context_ref, "Body", "SweptSolid", [solid])
        prod_shape_ref = self.create_entity("IfcProductDefinitionShape", None, None, [shape_rep])
        return elem_pl, prod_shape_ref

    def _create_mep_flow_segment_shape(
        self, waypoints: List[Tuple[float, float, float]], radius: float, st_pl_ref: Optional[str], st_elev: float, body_context_ref: str
    ) -> Tuple[str, str]:
        if not waypoints:
            waypoints = [(0.0, 0.0, st_elev), (1.0, 0.0, st_elev)]
        start_pt = waypoints[0]
        rel_z = float(start_pt[2] - st_elev)
        elem_pt = self.create_entity("IfcCartesianPoint", (float(start_pt[0]), float(start_pt[1]), rel_z))
        elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, None, None)
        elem_pl = self.create_entity("IfcLocalPlacement", st_pl_ref, elem_axis)

        pt_refs = [
            self.create_entity("IfcCartesianPoint", (float(p[0]), float(p[1]), float(p[2] - st_elev)))
            for p in waypoints
        ]
        polyline_ref = self.create_entity("IfcPolyline", pt_refs)

        r = float(radius) if radius and float(radius) > 0 else 0.05
        solid_ref = self.create_entity("IfcSweptDiskSolid", polyline_ref, r, None, None, None)
        shape_rep = self.create_entity("IfcShapeRepresentation", body_context_ref, "Body", "SweptSolid", [solid_ref])
        prod_shape_ref = self.create_entity("IfcProductDefinitionShape", None, None, [shape_rep])
        return elem_pl, prod_shape_ref

    def serialize(
        self,
        resolved: ResolvedManifest,
    ) -> str:
        manifest = resolved.manifest
        project_info = manifest.project

        # STEP Header
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        header = [
            "ISO-10303-21;",
            "HEADER;",
            "FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');",
            f"FILE_NAME('','{timestamp}',(''),(''),'debim IFC4 Compiler','debim','');",
            "FILE_SCHEMA(('IFC4'));",
            "ENDSEC;",
            "DATA;",
        ]

        # Standard Units
        u_length = self.create_entity("IfcSIUnit", "*", ".LENGTHUNIT.", None, ".METRE.")
        u_area = self.create_entity("IfcSIUnit", "*", ".AREAUNIT.", None, ".SQUARE_METRE.")
        u_vol = self.create_entity("IfcSIUnit", "*", ".VOLUMEUNIT.", None, ".CUBIC_METRE.")
        unit_assignment = self.create_entity("IfcUnitAssignment", [u_length, u_area, u_vol])

        # IfcProject
        project_ref = self.create_entity(
            "IfcProject",
            generate_ifc_guid(),
            None,
            project_info.name,
            None,
            None,
            None,
            None,
            None,
            unit_assignment,
        )

        # Geometric Contexts
        axis_3d_zero = self.create_entity(
            "IfcAxis2Placement3D",
            self.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0)),
            None,
            None,
        )
        context_ref = self.create_entity(
            "IfcGeometricRepresentationContext",
            None,
            "Model",
            3,
            1.0e-5,
            axis_3d_zero,
            None,
        )
        body_context_ref = self.create_entity(
            "IfcGeometricRepresentationSubContext",
            "Body",
            "Model",
            "*",
            "*",
            "*",
            "*",
            context_ref,
            None,
            ".MODEL_VIEW.",
            None,
        )

        # IfcSite & IfcBuilding
        site_pl_ref = self.create_entity("IfcLocalPlacement", None, axis_3d_zero)
        site_ref = self.create_entity(
            "IfcSite",
            generate_ifc_guid(),
            None,
            "Default Site",
            None,
            None,
            site_pl_ref,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
        bldg_pl_ref = self.create_entity("IfcLocalPlacement", site_pl_ref, axis_3d_zero)
        bldg_ref = self.create_entity(
            "IfcBuilding",
            generate_ifc_guid(),
            None,
            project_info.name,
            None,
            None,
            bldg_pl_ref,
            None,
            None,
            None,
            None,
            None,
        )

        self.create_entity(
            "IfcRelAggregates",
            generate_ifc_guid(),
            None,
            None,
            None,
            project_ref,
            [site_ref],
        )
        self.create_entity(
            "IfcRelAggregates",
            generate_ifc_guid(),
            None,
            None,
            None,
            site_ref,
            [bldg_ref],
        )

        # Storeys mapping
        storey_refs: Dict[str, str] = {}
        storey_pl_refs: Dict[str, str] = {}
        storey_elevations: Dict[str, float] = {}
        for storey in manifest.spatial_structure.storeys:
            st_pt = self.create_entity("IfcCartesianPoint", (0.0, 0.0, float(storey.elevation)))
            st_axis = self.create_entity("IfcAxis2Placement3D", st_pt, None, None)
            st_pl = self.create_entity("IfcLocalPlacement", bldg_pl_ref, st_axis)
            st_ref = self.create_entity(
                "IfcBuildingStorey",
                generate_ifc_guid(),
                None,
                storey.name,
                None,
                None,
                st_pl,
                None,
                None,
                None,
                float(storey.elevation),
            )
            storey_refs[storey.id] = st_ref
            storey_pl_refs[storey.id] = st_pl
            storey_elevations[storey.id] = float(storey.elevation)

        # Aggregate storeys under building
        if storey_refs:
            self.create_entity(
                "IfcRelAggregates",
                generate_ifc_guid(),
                None,
                None,
                None,
                bldg_ref,
                list(storey_refs.values()),
            )

        # Elements containment buckets
        storey_elements: Dict[str, List[str]] = {s_id: [] for s_id in storey_refs}
        element_tag_refs: Dict[str, str] = {}

        # 0. Footings & Piles
        for footing in resolved.footings:
            st_id = footing.element.placement.storey
            elem_ref = self.create_entity(
                "IfcFooting",
                generate_ifc_guid(),
                None,
                footing.tag,
                None,
                None,
                None,
                None,
                None,
            )
            element_tag_refs[footing.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

            for pile in footing.piles:
                p_ref = self.create_entity(
                    "IfcPile",
                    generate_ifc_guid(),
                    None,
                    pile.tag,
                    None,
                    None,
                    None,
                    None,
                    None,
                )
                element_tag_refs[pile.tag] = p_ref
                if st_id in storey_elements:
                    storey_elements[st_id].append(p_ref)

        # 5.3 Civil Earthworks & Retaining Walls & Civil Infrastructure (IFC4.3)
        for ew in resolved.earthworks_elements:
            st_id = ew.element.placement.storey
            elem_ref = self.create_entity(
                "IfcGeographicElement",
                generate_ifc_guid(),
                None,
                ew.tag,
                None,
                f"IfcEarthworksElement.{ew.predefined_type}",
                None,
                None,
                ".USERDEFINED.",
            )
            element_tag_refs[ew.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for cut in resolved.earthworks_cuts:
            st_id = cut.element.placement.storey
            elem_ref = self.create_entity(
                "IfcGeographicElement",
                generate_ifc_guid(),
                None,
                cut.tag,
                None,
                f"IfcEarthworksCut.{cut.predefined_type}",
                None,
                None,
                ".USERDEFINED.",
            )
            element_tag_refs[cut.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for strat in resolved.geotechnical_strata:
            st_id = strat.element.placement.storey
            elem_ref = self.create_entity(
                "IfcGeographicElement",
                generate_ifc_guid(),
                None,
                strat.tag,
                None,
                f"IfcGeotechnicalStratum.{strat.predefined_type}",
                None,
                None,
                ".USERDEFINED.",
            )
            element_tag_refs[strat.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for soil in resolved.soils:
            st_id = soil.element.placement.storey
            elem_ref = self.create_entity(
                "IfcGeographicElement",
                generate_ifc_guid(),
                None,
                soil.tag,
                None,
                f"IfcSoil.{soil.soil_type}",
                None,
                None,
                ".USERDEFINED.",
            )
            element_tag_refs[soil.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for align in resolved.alignments:
            st_id = align.element.placement.storey
            elem_ref = self.create_entity(
                "IfcAlignment",
                generate_ifc_guid(),
                None,
                align.tag,
                None,
                f"IfcAlignment.{align.predefined_type}",
                None,
                None,
                ".USERDEFINED.",
            )
            element_tag_refs[align.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for road in resolved.roads:
            st_id = road.element.placement.storey
            elem_ref = self.create_entity(
                "IfcRoad",
                generate_ifc_guid(),
                None,
                road.tag,
                None,
                f"IfcRoad.{road.predefined_type}",
                None,
                None,
                f".{road.predefined_type.upper()}.",
            )
            element_tag_refs[road.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for bridge in resolved.bridges:
            st_id = bridge.element.placement.storey
            elem_ref = self.create_entity(
                "IfcBridge",
                generate_ifc_guid(),
                None,
                bridge.tag,
                None,
                f"IfcBridge.{bridge.predefined_type}",
                None,
                None,
                f".{bridge.predefined_type.upper()}.",
            )
            element_tag_refs[bridge.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for mf in getattr(resolved, "marine_facilities", []) or []:
            ptype = f".{mf.predefined_type.upper()}." if mf.predefined_type else ".PORT."
            mf_pl_ref = self.create_entity("IfcLocalPlacement", site_pl_ref, axis_3d_zero)
            elem_ref = self.create_entity(
                "IfcMarineFacility",
                generate_ifc_guid(),
                None,
                mf.name or mf.tag,
                None,
                f"IfcMarineFacility.{mf.predefined_type}",
                mf_pl_ref,
                None,
                ptype,
            )
            element_tag_refs[mf.tag] = elem_ref
            self.create_entity(
                "IfcRelAggregates",
                generate_ifc_guid(),
                None,
                None,
                None,
                site_ref,
                [elem_ref],
            )

        for rw in resolved.railways:
            st_id = rw.element.placement.storey
            elem_ref = self.create_entity(
                "IfcRailway",
                generate_ifc_guid(),
                None,
                rw.tag,
                None,
                f"IfcRailway.{rw.predefined_type}",
                None,
                None,
                f".{rw.predefined_type.upper()}.",
            )
            element_tag_refs[rw.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for rwp in resolved.railway_parts:
            st_id = rwp.element.placement.storey
            elem_ref = self.create_entity(
                "IfcRailwayPart",
                generate_ifc_guid(),
                None,
                rwp.tag,
                None,
                f"IfcRailwayPart.{rwp.predefined_type}",
                None,
                None,
                f".{rwp.predefined_type.upper()}.",
            )
            element_tag_refs[rwp.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for te in resolved.track_elements:
            st_id = te.element.placement.storey
            elem_ref = self.create_entity(
                "IfcTrackElement",
                generate_ifc_guid(),
                None,
                te.tag,
                None,
                f"IfcTrackElement.{te.predefined_type}",
                None,
                None,
                f".{te.predefined_type.upper()}.",
            )
            element_tag_refs[te.tag] = elem_ref
        for bp in getattr(resolved, "bridge_parts", []) or []:
            st_id = bp.element.placement.storey
            st_pl_ref = storey_pl_refs.get(st_id) if st_id else None
            st_elev = storey_elevations.get(st_id, 0.0) if st_id else 0.0

            px, py, pz = bp.position
            rel_z = float(pz - st_elev)

            pos2d = self.create_entity("IfcCartesianPoint", (0.0, 0.0))
            axis2d = self.create_entity("IfcAxis2Placement2D", pos2d, None)
            rec_prof = self.create_entity("IfcRectangleProfileDef", ".AREA.", None, axis2d, float(bp.span_length), float(bp.width))

            pos3d = self.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
            axis3d = self.create_entity("IfcAxis2Placement3D", pos3d, None, None)
            ext_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
            solid = self.create_entity("IfcExtrudedAreaSolid", rec_prof, axis3d, ext_dir, float(bp.thickness))

            shape_rep = self.create_entity("IfcShapeRepresentation", body_context_ref, "Body", "SweptSolid", [solid])
            prod_shape_ref = self.create_entity("IfcProductDefinitionShape", None, None, [shape_rep])

            elem_pt = self.create_entity("IfcCartesianPoint", (float(px), float(py), rel_z))
            elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, None, None)
            elem_pl = self.create_entity("IfcLocalPlacement", st_pl_ref or site_pl_ref, elem_axis)

            ptype = f".{bp.predefined_type.upper()}." if bp.predefined_type else ".SUPERSTRUCTURE."
            elem_ref = self.create_entity(
                "IfcBridgePart",
                generate_ifc_guid(),
                None,
                bp.tag,
                None,
                f"IfcBridgePart.{bp.predefined_type}",
                elem_pl,
                prod_shape_ref,
                ptype,
            )
            element_tag_refs[bp.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for mp in getattr(resolved, "marine_parts", []) or []:
            st_id = mp.element.placement.storey
            st_pl_ref = storey_pl_refs.get(st_id) if st_id else None
            st_elev = storey_elevations.get(st_id, 0.0) if st_id else 0.0

            px, py, pz = mp.position
            ptype_str = mp.predefined_type.upper() if mp.predefined_type else "BERTH"

            if ptype_str in ("BREAKWATER", "REVETMENT"):
                rel_z = float(pz - st_elev)
                H = float(mp.depth + mp.crest_elevation) if (mp.depth + mp.crest_elevation) > 0 else float(mp.depth)
                top_w = float(mp.crest_width)
                bot_w = float(mp.base_width)

                # Trapezoid cross-section profile in 2D (Y is height/depth, X is width across profile)
                # Extrusion direction along local +Z or local +X
                p1 = self.create_entity("IfcCartesianPoint", (-bot_w / 2.0, 0.0))
                p2 = self.create_entity("IfcCartesianPoint", (bot_w / 2.0, 0.0))
                p3 = self.create_entity("IfcCartesianPoint", (top_w / 2.0, H))
                p4 = self.create_entity("IfcCartesianPoint", (-top_w / 2.0, H))
                polyline = self.create_entity("IfcPolyline", [p1, p2, p3, p4, p1])
                prof_ref = self.create_entity("IfcArbitraryClosedProfileDef", ".AREA.", None, polyline)
                ext_height = float(mp.length)
            elif mp.predefined_type in ("SEAWALL", "GROYNE") and mp.wall_profile_points:
                rel_z = float(pz + mp.deck_elevation - st_elev)
                pts_refs = [self.create_cartesian_point_2d(float(p[0]), float(p[1])) for p in mp.wall_profile_points]
                if mp.wall_profile_points[0] != mp.wall_profile_points[-1]:
                    pts_refs.append(pts_refs[0])
                poly_ref = self.create_entity("IfcPolyline", pts_refs)
                prof_ref = self.create_entity("IfcArbitraryClosedProfileDef", ".AREA.", None, poly_ref)
                ext_height = float(mp.length)
            else:
                rel_z = float(pz + mp.deck_elevation - st_elev)
                pos2d = self.create_entity("IfcCartesianPoint", (0.0, 0.0))
                axis2d = self.create_entity("IfcAxis2Placement2D", pos2d, None)
                prof_ref = self.create_entity("IfcRectangleProfileDef", ".AREA.", None, axis2d, float(mp.length), float(mp.width))
                ext_height = float(mp.deck_thickness if mp.deck_thickness > 0 else 1.0)

            pos3d = self.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
            axis3d = self.create_entity("IfcAxis2Placement3D", pos3d, None, None)
            ext_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
            solid = self.create_entity("IfcExtrudedAreaSolid", prof_ref, axis3d, ext_dir, ext_height)

            shape_rep = self.create_entity("IfcShapeRepresentation", body_context_ref, "Body", "SweptSolid", [solid])
            prod_shape_ref = self.create_entity("IfcProductDefinitionShape", None, None, [shape_rep])

            elem_pt = self.create_entity("IfcCartesianPoint", (float(px), float(py), rel_z))
            elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, None, None)
            elem_pl = self.create_entity("IfcLocalPlacement", st_pl_ref or site_pl_ref, elem_axis)

            ptype = f".{mp.predefined_type.upper()}." if mp.predefined_type else ".BERTH."
            elem_ref = self.create_entity(
                "IfcMarinePart",
                generate_ifc_guid(),
                None,
                mp.tag,
                None,
                f"IfcMarinePart.{mp.predefined_type}",
                elem_pl,
                prod_shape_ref,
                ptype,
            )
            element_tag_refs[mp.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

            for pile in mp.piles:
                p_px, p_py, p_pz = pile.position
                p_rel_z = float(p_pz - pile.length - st_elev)
                p_pos2d = self.create_entity("IfcCartesianPoint", (0.0, 0.0))
                p_axis2d = self.create_entity("IfcAxis2Placement2D", p_pos2d, None)
                if pile.shape == "CIRCULAR":
                    p_prof = self.create_entity("IfcCircleProfileDef", ".AREA.", None, p_axis2d, float(pile.dimension / 2.0))
                else:
                    p_prof = self.create_entity("IfcRectangleProfileDef", ".AREA.", None, p_axis2d, float(pile.dimension), float(pile.dimension))
                p_pos3d = self.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
                p_axis3d = self.create_entity("IfcAxis2Placement3D", p_pos3d, None, None)
                p_ext_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
                p_solid = self.create_entity("IfcExtrudedAreaSolid", p_prof, p_axis3d, p_ext_dir, float(pile.length))
                p_shape_rep = self.create_entity("IfcShapeRepresentation", body_context_ref, "Body", "SweptSolid", [p_solid])
                p_prod_shape = self.create_entity("IfcProductDefinitionShape", None, None, [p_shape_rep])

                p_pt = self.create_entity("IfcCartesianPoint", (float(p_px), float(p_py), p_rel_z))
                p_axis = self.create_entity("IfcAxis2Placement3D", p_pt, None, None)
                p_pl = self.create_entity("IfcLocalPlacement", st_pl_ref or site_pl_ref, p_axis)

                p_ref = self.create_entity(
                    "IfcPile",
                    generate_ifc_guid(),
                    None,
                    pile.tag,
                    None,
                    None,
                    p_pl,
                    p_prod_shape,
                    ".BORED.",
                )
                element_tag_refs[pile.tag] = p_ref
                if st_id and st_id in storey_elements:
                    storey_elements[st_id].append(p_ref)

        for br in getattr(resolved, "bearings", []) or []:
            st_id = br.element.placement.storey
            st_pl_ref = storey_pl_refs.get(st_id) if st_id else None
            st_elev = storey_elevations.get(st_id, 0.0) if st_id else 0.0

            px, py, pz = br.position
            rel_z = float(pz - st_elev)

            pos2d = self.create_entity("IfcCartesianPoint", (0.0, 0.0))
            axis2d = self.create_entity("IfcAxis2Placement2D", pos2d, None)
            rec_prof = self.create_entity("IfcRectangleProfileDef", ".AREA.", None, axis2d, float(br.width), float(br.depth))

            pos3d = self.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
            axis3d = self.create_entity("IfcAxis2Placement3D", pos3d, None, None)
            ext_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
            solid = self.create_entity("IfcExtrudedAreaSolid", rec_prof, axis3d, ext_dir, float(br.height))

            shape_rep = self.create_entity("IfcShapeRepresentation", body_context_ref, "Body", "SweptSolid", [solid])
            prod_shape_ref = self.create_entity("IfcProductDefinitionShape", None, None, [shape_rep])

            elem_pt = self.create_entity("IfcCartesianPoint", (float(px), float(py), rel_z))
            elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, None, None)
            elem_pl = self.create_entity("IfcLocalPlacement", st_pl_ref or site_pl_ref, elem_axis)

            ptype = f".{br.predefined_type.upper()}." if br.predefined_type else ".BRIDGEBEARING."
            elem_ref = self.create_entity(
                "IfcBearing",
                generate_ifc_guid(),
                None,
                br.tag,
                None,
                f"IfcBearing.{br.predefined_type}",
                elem_pl,
                prod_shape_ref,
                ptype,
            )
            element_tag_refs[br.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for fill in resolved.earthworks_fills:
            st_id = fill.element.placement.storey
            elem_ref = self.create_entity(
                "IfcGeographicElement",
                generate_ifc_guid(),
                None,
                fill.tag,
                None,
                f"IfcEarthworksFill.{fill.predefined_type}",
                None,
                None,
                ".USERDEFINED.",
            )
            element_tag_refs[fill.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for rw in resolved.retaining_walls:
            st_id = rw.element.placement.storey
            elem_ref = self.create_entity(
                "IfcWall",
                generate_ifc_guid(),
                None,
                rw.tag,
                None,
                None,
                None,
                None,
                ".RETAINING.",
            )
            element_tag_refs[rw.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        # 1. Columns
        for col in resolved.columns:
            st_id = col.element.placement.base_storey

            prof = col.element.profile
            pos2d = self.create_entity("IfcCartesianPoint", (0.0, 0.0))
            axis2d = self.create_entity("IfcAxis2Placement2D", pos2d, None)
            ifc_prof = self.create_ifc_profile_def(prof, col.tag, axis2d)

            pos3d = self.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
            axis3d = self.create_entity("IfcAxis2Placement3D", pos3d, None, None)
            ext_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
            solid = self.create_entity("IfcExtrudedAreaSolid", ifc_prof, axis3d, ext_dir, float(col.height))

            shape_rep = self.create_entity(
                "IfcShapeRepresentation",
                body_context_ref,
                "Body",
                "SweptSolid",
                [solid],
            )
            prod_shape_ref = self.create_entity(
                "IfcProductDefinitionShape", None, None, [shape_rep]
            )

            st_pl_ref = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)

            px, py, pz = col.start_point
            rel_z = float(pz - st_elev)

            elem_pt = self.create_entity("IfcCartesianPoint", (float(px), float(py), rel_z))
            dx, dy, dz = col.direction_vector_3d
            axis_dir = self.create_entity("IfcDirection", (round(dx, 6), round(dy, 6), round(dz, 6)))
            elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, axis_dir, None)
            elem_pl = self.create_entity("IfcLocalPlacement", st_pl_ref, elem_axis)

            elem_ref = self.create_entity(
                "IfcColumn",
                generate_ifc_guid(),
                None,
                col.tag,
                None,
                None,
                elem_pl,
                prod_shape_ref,
                None,
            )
            element_tag_refs[col.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        # 2. Beams
        for beam in resolved.beams:
            st_id = beam.element.placement.storey

            prof = beam.element.profile
            pos2d = self.create_entity("IfcCartesianPoint", (0.0, 0.0))
            axis2d = self.create_entity("IfcAxis2Placement2D", pos2d, None)
            ifc_prof = self.create_ifc_profile_def(prof, beam.tag, axis2d)

            pos3d = self.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
            axis3d = self.create_entity("IfcAxis2Placement3D", pos3d, None, None)
            ext_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
            solid = self.create_entity("IfcExtrudedAreaSolid", ifc_prof, axis3d, ext_dir, float(beam.span_length))

            shape_rep = self.create_entity(
                "IfcShapeRepresentation",
                body_context_ref,
                "Body",
                "SweptSolid",
                [solid],
            )
            prod_shape_ref = self.create_entity(
                "IfcProductDefinitionShape", None, None, [shape_rep]
            )

            st_pl_ref = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)

            px, py, pz = beam.start_point
            dx, dy, dz = beam.direction_vector_3d

            # z_axis along beam span direction
            z_len = math.sqrt(dx * dx + dy * dy + dz * dz)
            if z_len > 1e-6:
                zx, zy, zz = dx / z_len, dy / z_len, dz / z_len
            else:
                zx, zy, zz = 1.0, 0.0, 0.0

            # y_axis along perpendicular up/depth direction
            dot_up = zz  # dot((zx, zy, zz), (0, 0, 1))
            if abs(dot_up) < 0.99:
                yrx, yry, yrz = -zx * zz, -zy * zz, 1.0 - zz * zz
            else:
                yrx, yry, yrz = -zx * zy, 1.0 - zy * zy, -zz * zy
            y_len = math.sqrt(yrx * yrx + yry * yry + yrz * yrz)
            if y_len > 1e-6:
                yx, yy, yz = yrx / y_len, yry / y_len, yrz / y_len
            else:
                yx, yy, yz = 0.0, 1.0, 0.0

            # x_axis = y_axis x z_axis
            xx = yy * zz - yz * zy
            xy = yz * zx - yx * zz
            xz = yx * zy - yy * zx
            x_len = math.sqrt(xx * xx + xy * xy + xz * xz)
            if x_len > 1e-6:
                xx, xy, xz = xx / x_len, xy / x_len, xz / x_len

            b_depth = getattr(prof, "depth", getattr(prof, "overall_depth", 0.3))
            ox = px - yx * (b_depth / 2.0)
            oy = py - yy * (b_depth / 2.0)
            oz = pz - yz * (b_depth / 2.0)
            rel_z = float(oz - st_elev)

            elem_pt = self.create_entity("IfcCartesianPoint", (float(ox), float(oy), rel_z))
            axis_dir = self.create_entity("IfcDirection", (round(zx, 6), round(zy, 6), round(zz, 6)))
            ref_dir = self.create_entity("IfcDirection", (round(xx, 6), round(xy, 6), round(xz, 6)))
            elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, axis_dir, ref_dir)
            elem_pl = self.create_entity("IfcLocalPlacement", st_pl_ref, elem_axis)

            elem_ref = self.create_entity(
                "IfcBeam",
                generate_ifc_guid(),
                None,
                beam.tag,
                None,
                None,
                elem_pl,
                prod_shape_ref,
                None,
            )
            element_tag_refs[beam.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        # 3. Slabs
        for slab in resolved.slabs:
            st_id = slab.element.placement.storey
            elem_ref = self.create_entity(
                "IfcSlab",
                generate_ifc_guid(),
                None,
                slab.tag,
                None,
                None,
                None,
                None,
                None,
            )
            element_tag_refs[slab.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        # 3.1 Coverings
        for cov in resolved.coverings:
            st_id = cov.element.placement.storey
            ptype = cov.covering_type.upper() if cov.covering_type else "CEILING"

            st_pl_ref = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)

            cx, cy, cz = cov.center
            rel_z = float(cz - st_elev)

            prod_shape_ref = None
            if cov.polygon and len(cov.polygon) >= 3:
                thick = float(cov.thickness)
                # Extruded polygon shape (relative to centroid cx, cy)
                pts_2d = [(float(p[0] - cx), float(p[1] - cy)) for p in cov.polygon]
                poly_ref = self.create_polyline_2d(pts_2d)
                prof_ref = self.create_entity("IfcArbitraryClosedProfileDef", ".AREA.", None, poly_ref)

                pos3d = self.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
                axis3d = self.create_entity("IfcAxis2Placement3D", pos3d, None, None)
                ext_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
                solid = self.create_entity("IfcExtrudedAreaSolid", prof_ref, axis3d, ext_dir, thick)

                shape_rep = self.create_entity(
                    "IfcShapeRepresentation",
                    body_context_ref,
                    "Body",
                    "SweptSolid",
                    [solid],
                )
                prod_shape_ref = self.create_entity(
                    "IfcProductDefinitionShape", None, None, [shape_rep]
                )

            elem_pt = self.create_entity("IfcCartesianPoint", (float(cx), float(cy), rel_z))
            elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, None, None)
            elem_pl = self.create_entity("IfcLocalPlacement", st_pl_ref, elem_axis)

            elem_ref = self.create_entity(
                "IfcCovering",
                generate_ifc_guid(),
                None,
                cov.tag,
                None,
                None,
                elem_pl,
                prod_shape_ref,
                None,
                f".{ptype}.",
            )
            element_tag_refs[cov.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        # 4. Stairs, Stair Flights, Ramps, Railings
        for stair in resolved.stairs:
            st_id = stair.element.placement.from_storey
            elem_ref = self.create_entity(
                "IfcStair",
                generate_ifc_guid(),
                None,
                stair.tag,
                None,
                None,
                None,
                None,
                None,
            )
            element_tag_refs[stair.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for flight in resolved.stair_flights:
            st_id = flight.element.placement.from_storey if flight.element else None
            elem_ref = self.create_entity(
                "IfcStairFlight",
                generate_ifc_guid(),
                None,
                flight.tag,
                None,
                None,
                None,
                None,
                None,
                flight.n_risers,
                int(flight.n_risers - 1) if flight.n_risers > 1 else 1,
                float(flight.riser),
                float(flight.tread),
            )
            element_tag_refs[flight.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for ramp in resolved.ramps:
            st_id = ramp.element.placement.storey
            elem_ref = self.create_entity(
                "IfcRamp",
                generate_ifc_guid(),
                None,
                ramp.tag,
                None,
                None,
                None,
                None,
                None,
            )
            element_tag_refs[ramp.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for railing in resolved.railings:
            st_id = railing.element.placement.storey
            ptype = railing.predefined_type if railing.predefined_type in ("HANDRAIL", "GUARDRAIL", "BALUSTRADE", "USERDEFINED") else "HANDRAIL"
            elem_ref = self.create_entity(
                "IfcRailing",
                generate_ifc_guid(),
                None,
                railing.tag,
                None,
                None,
                None,
                None,
                f".{ptype}.",
            )
            element_tag_refs[railing.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        # 5. Walls & Child Openings / Doors / Windows
        for wall in resolved.walls:
            st_id = wall.element.placement.storey
            wall_ref = self.create_entity(
                "IfcWall",
                generate_ifc_guid(),
                None,
                wall.tag,
                None,
                None,
                None,
                None,
                None,
            )
            element_tag_refs[wall.tag] = wall_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(wall_ref)

            # Process children (Doors / Windows)
            for child in wall.children:
                if isinstance(child, ResolvedDoor):
                    door_ref = self.create_entity(
                        "IfcDoor",
                        generate_ifc_guid(),
                        None,
                        child.tag,
                        None,
                        None,
                        None,
                        None,
                        None,
                        float(child.height),
                        float(child.width),
                    )
                    element_tag_refs[child.tag] = door_ref
                    opening_ref = self.create_entity(
                        "IfcOpeningElement",
                        generate_ifc_guid(),
                        None,
                        f"{child.tag}_Opening",
                        None,
                        None,
                        None,
                        None,
                        None,
                    )
                    # Void relationship (Wall -> Opening)
                    self.create_entity(
                        "IfcRelVoidsElement",
                        generate_ifc_guid(),
                        None,
                        None,
                        None,
                        wall_ref,
                        opening_ref,
                    )
                    # Filling relationship (Opening -> Door)
                    self.create_entity(
                        "IfcRelFillsElement",
                        generate_ifc_guid(),
                        None,
                        None,
                        None,
                        opening_ref,
                        door_ref,
                    )
                    if st_id in storey_elements:
                        storey_elements[st_id].append(door_ref)

                elif isinstance(child, ResolvedWindow):
                    win_ref = self.create_entity(
                        "IfcWindow",
                        generate_ifc_guid(),
                        None,
                        child.tag,
                        None,
                        None,
                        None,
                        None,
                        None,
                        float(child.height),
                        float(child.width),
                    )
                    element_tag_refs[child.tag] = win_ref
                    opening_ref = self.create_entity(
                        "IfcOpeningElement",
                        generate_ifc_guid(),
                        None,
                        f"{child.tag}_Opening",
                        None,
                        None,
                        None,
                        None,
                        None,
                    )
                    self.create_entity(
                        "IfcRelVoidsElement",
                        generate_ifc_guid(),
                        None,
                        None,
                        None,
                        wall_ref,
                        opening_ref,
                    )
                    self.create_entity(
                        "IfcRelFillsElement",
                        generate_ifc_guid(),
                        None,
                        None,
                        None,
                        opening_ref,
                        win_ref,
                    )
                    if st_id in storey_elements:
                        storey_elements[st_id].append(win_ref)

        # 4. Custom Elements
        for custom in resolved.custom_elements:
            st_id = custom.element.placement.storey
            ifc_cls = derive_custom_ifc_class(custom.layer)

            # Local placement relative to storey
            st_pl_ref = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)

            px, py, pz = custom.position
            rel_z = float(pz - st_elev)

            elem_pt = self.create_entity("IfcCartesianPoint", (float(px), float(py), rel_z))
            rx, ry, rz = custom.rotation if custom.rotation else (0.0, 0.0, 0.0)
            if abs(rz) > 1e-4 or abs(rx) > 1e-4 or abs(ry) > 1e-4:
                rz_r = math.radians(float(rz))
                ref_dir = self.create_entity("IfcDirection", (round(math.cos(rz_r), 6), round(math.sin(rz_r), 6), 0.0))
                axis_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
                elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, axis_dir, ref_dir)
            else:
                elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, None, None)
            elem_pl = self.create_entity("IfcLocalPlacement", st_pl_ref, elem_axis)

            # Shape representation
            prod_shape_ref = None
            solid_ref = None

            if custom.element.solid or custom.resolved_solid:
                c_solid = custom.element.solid or custom.resolved_solid
                if isinstance(c_solid, (SweptDiskSolid, ResolvedSweptDisk)):
                    directrix_pts = c_solid.directrix
                    pt_refs = [self.create_entity("IfcCartesianPoint", (float(p[0]), float(p[1]), float(p[2]))) for p in directrix_pts]
                    polyline_ref = self.create_entity("IfcPolyline", pt_refs)
                    r = float(c_solid.radius)
                    inner_r = float(c_solid.inner_radius) if c_solid.inner_radius is not None else None
                    solid_ref = self.create_entity("IfcSweptDiskSolid", polyline_ref, r, inner_r, None, None)
                elif isinstance(c_solid, (RevolvedAreaSolid, ResolvedRevolvedArea)):
                    pos2d = self.create_entity("IfcCartesianPoint", (0.0, 0.0))
                    axis2d = self.create_entity("IfcAxis2Placement2D", pos2d, None)
                    prof_ref = self.create_ifc_profile_def(c_solid.profile, custom.tag, axis2d)
                    ax_pt_ref = self.create_entity("IfcCartesianPoint", (float(x) for x in c_solid.axis_point))
                    ax_dir_ref = self.create_entity("IfcDirection", (float(x) for x in c_solid.axis_direction))
                    axis1_ref = self.create_entity("IfcAxis1Placement", ax_pt_ref, ax_dir_ref)
                    angle_rad = float(c_solid.revolution_angle) * math.pi / 180.0
                    solid_ref = self.create_entity("IfcRevolvedAreaSolid", prof_ref, None, axis1_ref, angle_rad)

            if solid_ref:
                shape_rep = self.create_entity(
                    "IfcShapeRepresentation",
                    body_context_ref,
                    "Body",
                    "SweptSolid",
                    [solid_ref],
                )
                prod_shape_ref = self.create_entity(
                    "IfcProductDefinitionShape", None, None, [shape_rep]
                )
            else:
                dims = custom.dimensions or custom.element.dimensions
                if dims:
                    w = float(dims.width)
                    d = float(dims.depth if dims.depth is not None else dims.width)
                    h = float(dims.height)

                    pos2d = self.create_entity("IfcCartesianPoint", (0.0, 0.0))
                    axis2d = self.create_entity("IfcAxis2Placement2D", pos2d, None)
                    rec_prof = self.create_entity("IfcRectangleProfileDef", ".AREA.", None, axis2d, w, d)

                    pos3d = self.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
                    axis3d = self.create_entity("IfcAxis2Placement3D", pos3d, None, None)
                    ext_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
                    solid = self.create_entity("IfcExtrudedAreaSolid", rec_prof, axis3d, ext_dir, h)

                    shape_rep = self.create_entity(
                        "IfcShapeRepresentation",
                        body_context_ref,
                        "Body",
                        "SweptSolid",
                        [solid],
                    )
                    prod_shape_ref = self.create_entity(
                        "IfcProductDefinitionShape", None, None, [shape_rep]
                    )

            elem_ref = self.create_entity(
                ifc_cls,
                generate_ifc_guid(),
                None,
                custom.tag,
                None,
                None,
                elem_pl,
                prod_shape_ref,
                None,
            )
            element_tag_refs[custom.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        # 5.1 Curtain Walls
        for cw in resolved.curtain_walls:
            st_id = cw.element.placement.storey
            raw_pred_type = cw.element.predefined_type
            pred_type = f".{raw_pred_type.upper()}." if raw_pred_type else None

            st_pl_ref = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)

            x1, y1, z1 = cw.start_point
            x2, y2, z2 = cw.end_point
            dx, dy = x2 - x1, y2 - y1
            l_2d = math.hypot(dx, dy)
            ux, uy = (dx / l_2d, dy / l_2d) if l_2d > 1e-6 else (1.0, 0.0)

            rel_z = float(z1 - st_elev)
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0

            elem_pt = self.create_entity("IfcCartesianPoint", (float(cx), float(cy), rel_z))
            ref_dir = self.create_entity("IfcDirection", (round(ux, 6), round(uy, 6), 0.0))
            elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, None, ref_dir)
            elem_pl = self.create_entity("IfcLocalPlacement", st_pl_ref, elem_axis)

            pos2d = self.create_entity("IfcCartesianPoint", (0.0, 0.0))
            axis2d = self.create_entity("IfcAxis2Placement2D", pos2d, None)
            rec_prof = self.create_entity("IfcRectangleProfileDef", ".AREA.", None, axis2d, float(cw.length), float(cw.element.glass_thickness or 0.01))

            pos3d = self.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
            axis3d = self.create_entity("IfcAxis2Placement3D", pos3d, None, None)
            ext_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
            solid = self.create_entity("IfcExtrudedAreaSolid", rec_prof, axis3d, ext_dir, float(cw.height))

            shape_rep = self.create_entity(
                "IfcShapeRepresentation",
                body_context_ref,
                "Body",
                "SweptSolid",
                [solid],
            )
            prod_shape_ref = self.create_entity(
                "IfcProductDefinitionShape", None, None, [shape_rep]
            )

            elem_ref = self.create_entity(
                "IfcCurtainWall",
                generate_ifc_guid(),
                None,
                cw.tag,
                None,
                None,
                elem_pl,
                prod_shape_ref,
                None,
                pred_type,
            )
            element_tag_refs[cw.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        # 5.2 Plates
        for plate in resolved.plates:
            st_id = plate.element.placement.storey
            raw_pred_type = plate.element.predefined_type
            pred_type = f".{raw_pred_type.upper()}." if raw_pred_type else None

            st_pl_ref = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)

            px, py, pz = plate.position
            rel_z = float(pz - st_elev)

            elem_pt = self.create_entity("IfcCartesianPoint", (float(px), float(py), rel_z))
            elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, None, None)
            elem_pl = self.create_entity("IfcLocalPlacement", st_pl_ref, elem_axis)

            if plate.polygon and len(plate.polygon) >= 3:
                pts_2d = [(float(p[0] - px), float(p[1] - py)) for p in plate.polygon]
                poly_ref = self.create_polyline_2d(pts_2d)
                prof_ref = self.create_entity("IfcArbitraryClosedProfileDef", ".AREA.", None, poly_ref)
            else:
                pos2d = self.create_entity("IfcCartesianPoint", (0.0, 0.0))
                axis2d = self.create_entity("IfcAxis2Placement2D", pos2d, None)
                prof_ref = self.create_entity("IfcRectangleProfileDef", ".AREA.", None, axis2d, float(plate.width), float(plate.depth))

            pos3d = self.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
            axis3d = self.create_entity("IfcAxis2Placement3D", pos3d, None, None)
            ext_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
            solid = self.create_entity("IfcExtrudedAreaSolid", prof_ref, axis3d, ext_dir, float(plate.thickness))

            shape_rep = self.create_entity(
                "IfcShapeRepresentation",
                body_context_ref,
                "Body",
                "SweptSolid",
                [solid],
            )
            prod_shape_ref = self.create_entity(
                "IfcProductDefinitionShape", None, None, [shape_rep]
            )

            elem_ref = self.create_entity(
                "IfcPlate",
                generate_ifc_guid(),
                None,
                plate.tag,
                None,
                None,
                elem_pl,
                prod_shape_ref,
                None,
                pred_type,
            )
            element_tag_refs[plate.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        # 6. Roofs & Roof Openings / Skylights
        for roof in resolved.roofs:
            st_id = roof.element.placement.storey
            roof_ref = self.create_entity(
                "IfcRoof",
                generate_ifc_guid(),
                None,
                roof.tag,
                None,
                None,
                None,
                None,
                None,
            )
            element_tag_refs[roof.tag] = roof_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(roof_ref)

            for child in roof.children:
                if isinstance(child, ResolvedDoor):
                    door_ref = self.create_entity(
                        "IfcDoor",
                        generate_ifc_guid(),
                        None,
                        child.tag,
                        None,
                        None,
                        None,
                        None,
                        None,
                        float(child.height),
                        float(child.width),
                    )
                    element_tag_refs[child.tag] = door_ref
                    opening_ref = self.create_entity(
                        "IfcOpeningElement",
                        generate_ifc_guid(),
                        None,
                        f"{child.tag}_Opening",
                        None,
                        None,
                        None,
                        None,
                        None,
                    )
                    self.create_entity(
                        "IfcRelVoidsElement",
                        generate_ifc_guid(),
                        None,
                        None,
                        None,
                        roof_ref,
                        opening_ref,
                    )
                    self.create_entity(
                        "IfcRelFillsElement",
                        generate_ifc_guid(),
                        None,
                        None,
                        None,
                        opening_ref,
                        door_ref,
                    )
                    if st_id in storey_elements:
                        storey_elements[st_id].append(door_ref)

                elif isinstance(child, ResolvedWindow):
                    win_ref = self.create_entity(
                        "IfcWindow",
                        generate_ifc_guid(),
                        None,
                        child.tag,
                        None,
                        None,
                        None,
                        None,
                        None,
                        float(child.height),
                        float(child.width),
                    )
                    element_tag_refs[child.tag] = win_ref
                    opening_ref = self.create_entity(
                        "IfcOpeningElement",
                        generate_ifc_guid(),
                        None,
                        f"{child.tag}_Opening",
                        None,
                        None,
                        None,
                        None,
                        None,
                    )
                    self.create_entity(
                        "IfcRelVoidsElement",
                        generate_ifc_guid(),
                        None,
                        None,
                        None,
                        roof_ref,
                        opening_ref,
                    )
                    self.create_entity(
                        "IfcRelFillsElement",
                        generate_ifc_guid(),
                        None,
                        None,
                        None,
                        opening_ref,
                        win_ref,
                    )
                    if st_id in storey_elements:
                        storey_elements[st_id].append(win_ref)

        # 7. MEP Elements (Pipes, Conduits, Terminals, Electrical, HVAC)
        for pipe in resolved.pipes:
            st_id = pipe.element.placement.storey
            st_pl = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)
            wpts = pipe.waypoints or [pipe.start_point, pipe.end_point]
            rad = (pipe.nominal_diameter or 0.05) / 2.0
            elem_pl, prod_shape = self._create_mep_flow_segment_shape(wpts, rad, st_pl, st_elev, body_context_ref)
            elem_ref = self.create_entity(
                "IfcPipeSegment", generate_ifc_guid(), None, pipe.tag, None, None, elem_pl, prod_shape, None
            )
            element_tag_refs[pipe.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for conduit in resolved.conduits:
            st_id = conduit.element.placement.storey
            st_pl = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)
            wpts = conduit.waypoints or [conduit.start_point, conduit.end_point]
            rad = (conduit.nominal_diameter or 0.05) / 2.0
            elem_pl, prod_shape = self._create_mep_flow_segment_shape(wpts, rad, st_pl, st_elev, body_context_ref)
            elem_ref = self.create_entity(
                "IfcCableCarrierSegment", generate_ifc_guid(), None, conduit.tag, None, None, elem_pl, prod_shape, None
            )
            element_tag_refs[conduit.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for duct in resolved.ducts:
            st_id = duct.element.placement.storey
            st_pl = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)
            wpts = getattr(duct, "waypoints", None) or [getattr(duct, "start_point", (0.0, 0.0, 0.0)), getattr(duct, "end_point", (1.0, 0.0, 0.0))]
            rad = getattr(duct, "width", 0.25) / 2.0
            elem_pl, prod_shape = self._create_mep_flow_segment_shape(wpts, rad, st_pl, st_elev, body_context_ref)
            elem_ref = self.create_entity(
                "IfcDuctSegment", generate_ifc_guid(), None, duct.tag, None, None, elem_pl, prod_shape, None
            )
            element_tag_refs[duct.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for term in resolved.sanitary_terminals:
            st_id = term.element.placement.storey
            st_pl = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)
            elem_pl, prod_shape = self._create_mep_terminal_shape(
                term.position[0], term.position[1], term.position[2],
                getattr(term, "rotation_angle", 0.0), st_pl, st_elev,
                getattr(term, "width", 0.5), getattr(term, "depth", 0.5), getattr(term, "height", 0.8),
                body_context_ref
            )
            ptype = f".{term.predefined_type}." if term.predefined_type else ".USERDEFINED."
            elem_ref = self.create_entity(
                "IfcSanitaryTerminal", generate_ifc_guid(), None, term.tag, None, None, elem_pl, prod_shape, None, ptype
            )
            element_tag_refs[term.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for term in getattr(resolved, "waste_terminals", []):
            st_id = term.element.placement.storey
            st_pl = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)
            elem_pl, prod_shape = self._create_mep_terminal_shape(
                term.position[0], term.position[1], term.position[2],
                getattr(term, "rotation_angle", 0.0), st_pl, st_elev,
                getattr(term, "width", 0.4), getattr(term, "depth", 0.4), getattr(term, "height", 0.4),
                body_context_ref
            )
            ptype = f".{term.predefined_type}." if term.predefined_type else ".FLOORDRAIN."
            elem_ref = self.create_entity(
                "IfcWasteTerminal", generate_ifc_guid(), None, term.tag, None, None, elem_pl, prod_shape, None, ptype
            )
            element_tag_refs[term.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for board in resolved.distribution_boards:
            st_id = board.element.placement.storey
            if not st_id and getattr(board.element.placement, "wall", None):
                for w in resolved.walls:
                    if w.tag == board.element.placement.wall:
                        st_id = w.element.placement.storey
                        break
            st_pl = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)
            elem_pl, prod_shape = self._create_mep_terminal_shape(
                board.position[0], board.position[1], board.position[2],
                getattr(board, "rotation_angle", 0.0), st_pl, st_elev,
                getattr(board, "width", 0.4), getattr(board, "depth", 0.2), getattr(board, "height", 0.6),
                body_context_ref
            )
            ifc_cls = "IfcElectricDistributionBoard" if getattr(board.element, "class_", "") == "IfcElectricDistributionBoard" else "IfcDistributionBoard"
            ptype = f".{board.predefined_type}." if board.predefined_type else ".CONSUMERUNIT."
            elem_ref = self.create_entity(
                ifc_cls, generate_ifc_guid(), None, board.tag, None, None, elem_pl, prod_shape, None, ptype
            )
            element_tag_refs[board.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for light in resolved.light_fixtures:
            st_id = light.element.placement.storey
            if not st_id and getattr(light.element.placement, "wall", None):
                for w in resolved.walls:
                    if w.tag == light.element.placement.wall:
                        st_id = w.element.placement.storey
                        break
            st_pl = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)
            elem_pl, prod_shape = self._create_mep_terminal_shape(
                light.position[0], light.position[1], light.position[2],
                getattr(light, "rotation_angle", 0.0), st_pl, st_elev,
                getattr(light, "width", 0.3), getattr(light, "depth", 0.3), getattr(light, "height", 0.1),
                body_context_ref
            )
            ptype = f".{light.predefined_type}." if light.predefined_type else ".POINTSOURCE."
            elem_ref = self.create_entity(
                "IfcLightFixture", generate_ifc_guid(), None, light.tag, None, None, elem_pl, prod_shape, None, ptype
            )
            element_tag_refs[light.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for sw in resolved.switches:
            st_id = sw.element.placement.storey
            if not st_id and getattr(sw.element.placement, "wall", None):
                for w in resolved.walls:
                    if w.tag == sw.element.placement.wall:
                        st_id = w.element.placement.storey
                        break
            st_pl = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)
            elem_pl, prod_shape = self._create_mep_terminal_shape(
                sw.position[0], sw.position[1], sw.position[2],
                getattr(sw, "rotation_angle", 0.0), st_pl, st_elev,
                getattr(sw, "width", 0.1), getattr(sw, "depth", 0.05), getattr(sw, "height", 0.1),
                body_context_ref
            )
            elem_ref = self.create_entity(
                "IfcSwitchingDevice", generate_ifc_guid(), None, sw.tag, None, None, elem_pl, prod_shape, None
            )
            element_tag_refs[sw.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for out in resolved.outlets:
            st_id = out.element.placement.storey
            if not st_id and getattr(out.element.placement, "wall", None):
                for w in resolved.walls:
                    if w.tag == out.element.placement.wall:
                        st_id = w.element.placement.storey
                        break
            st_pl = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)
            elem_pl, prod_shape = self._create_mep_terminal_shape(
                out.position[0], out.position[1], out.position[2],
                getattr(out, "rotation_angle", 0.0), st_pl, st_elev,
                getattr(out, "width", 0.1), getattr(out, "depth", 0.05), getattr(out, "height", 0.1),
                body_context_ref
            )
            ptype = f".{out.predefined_type}." if out.predefined_type else ".POWEROUTLET."
            elem_ref = self.create_entity(
                "IfcOutlet", generate_ifc_guid(), None, out.tag, None, None, elem_pl, prod_shape, None, ptype
            )
            element_tag_refs[out.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for air in resolved.air_terminals:
            st_id = air.element.placement.storey
            st_pl = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)
            elem_pl, prod_shape = self._create_mep_terminal_shape(
                air.position[0], air.position[1], air.position[2],
                getattr(air, "rotation_angle", 0.0), st_pl, st_elev,
                getattr(air, "width", 0.4), getattr(air, "depth", 0.4), getattr(air, "height", 0.2),
                body_context_ref
            )
            ptype = f".{air.predefined_type}." if air.predefined_type else ".DIFFUSER."
            elem_ref = self.create_entity(
                "IfcAirTerminal", generate_ifc_guid(), None, air.tag, None, None, elem_pl, prod_shape, None, ptype
            )
            element_tag_refs[air.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for damper in resolved.dampers:
            st_id = damper.element.placement.storey
            st_pl = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)
            elem_pl, prod_shape = self._create_mep_terminal_shape(
                damper.position[0], damper.position[1], damper.position[2],
                getattr(damper, "rotation_angle", 0.0), st_pl, st_elev,
                getattr(damper, "duct_width", getattr(damper, "width", 0.3)),
                getattr(damper, "duct_depth", getattr(damper, "depth", 0.3)),
                getattr(damper, "height", 0.3),
                body_context_ref
            )
            ptype = f".{damper.predefined_type}." if damper.predefined_type else ".FIREDAMPER."
            elem_ref = self.create_entity(
                "IfcDamper", generate_ifc_guid(), None, damper.tag, None, None, elem_pl, prod_shape, None, ptype
            )
            element_tag_refs[damper.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for controller in resolved.flow_controllers:
            st_id = controller.element.placement.storey
            st_pl = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)
            elem_pl, prod_shape = self._create_mep_terminal_shape(
                controller.position[0], controller.position[1], controller.position[2],
                getattr(controller, "rotation_angle", 0.0), st_pl, st_elev,
                getattr(controller, "duct_width", getattr(controller, "width", 0.4)),
                getattr(controller, "duct_depth", getattr(controller, "depth", 0.3)),
                getattr(controller, "height", 0.3),
                body_context_ref
            )
            obj_type = controller.predefined_type or "AIR_CONTROLLER"
            elem_ref = self.create_entity(
                "IfcFlowController", generate_ifc_guid(), None, controller.tag, None, obj_type, elem_pl, prod_shape, None
            )
            element_tag_refs[controller.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for eq in resolved.unitary_equipments:
            st_id = eq.element.placement.storey
            st_pl = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)
            elem_pl, prod_shape = self._create_mep_terminal_shape(
                eq.position[0], eq.position[1], eq.position[2],
                getattr(eq, "rotation_angle", 0.0), st_pl, st_elev,
                getattr(eq, "width", 0.8), getattr(eq, "depth", 0.4), getattr(eq, "height", 0.6),
                body_context_ref
            )
            elem_ref = self.create_entity(
                "IfcUnitaryEquipment", generate_ifc_guid(), None, eq.tag, None, None, elem_pl, prod_shape, None
            )
            element_tag_refs[eq.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        # 8. Universal Proxies
        for proxy in resolved.proxies:
            st_id = proxy.element.placement.storey
            ifc_cls = proxy.ifc_class or "IfcBuildingElementProxy"

            st_pl_ref = storey_pl_refs.get(st_id)
            st_elev = storey_elevations.get(st_id, 0.0)

            px, py, pz = proxy.position
            rel_z = float(pz - st_elev)

            elem_pt = self.create_entity("IfcCartesianPoint", (float(px), float(py), rel_z))
            rx, ry, rz = proxy.rotation
            if abs(rz) > 1e-4 or abs(rx) > 1e-4 or abs(ry) > 1e-4:
                rz_r = math.radians(float(rz))
                ref_dir = self.create_entity("IfcDirection", (round(math.cos(rz_r), 6), round(math.sin(rz_r), 6), 0.0))
                axis_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
                elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, axis_dir, ref_dir)
            else:
                elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, None, None)
            elem_pl = self.create_entity("IfcLocalPlacement", st_pl_ref, elem_axis)

            w, d, h = proxy.dimensions
            pos2d = self.create_entity("IfcCartesianPoint", (0.0, 0.0))
            axis2d = self.create_entity("IfcAxis2Placement2D", pos2d, None)
            rec_prof = self.create_entity("IfcRectangleProfileDef", ".AREA.", None, axis2d, float(w), float(d))

            pos3d = self.create_entity("IfcCartesianPoint", (0.0, 0.0, 0.0))
            axis3d = self.create_entity("IfcAxis2Placement3D", pos3d, None, None)
            ext_dir = self.create_entity("IfcDirection", (0.0, 0.0, 1.0))
            solid = self.create_entity("IfcExtrudedAreaSolid", rec_prof, axis3d, ext_dir, float(h))

            shape_rep = self.create_entity(
                "IfcShapeRepresentation",
                body_context_ref,
                "Body",
                "SweptSolid",
                [solid],
            )
            prod_shape_ref = self.create_entity(
                "IfcProductDefinitionShape", None, None, [shape_rep]
            )

            cls_upper = ifc_cls.upper()
            if cls_upper in IFC4_DISTRIBUTION_9_ATTR_CLASSES or cls_upper in ("IFCBUILDINGELEMENTPROXY", "IFCUNITARYEQUIPMENT"):
                target_entity = ifc_cls
                obj_type = ifc_cls if target_entity.upper() == "IFCBUILDINGELEMENTPROXY" else None
                pred_type = f".{proxy.predefined_type.upper()}." if proxy.predefined_type else ".USERDEFINED."
                proxy_ref = self.create_entity(
                    target_entity,
                    generate_ifc_guid(),
                    None,
                    proxy.tag,
                    None,
                    obj_type,
                    elem_pl,
                    prod_shape_ref,
                    None,
                    pred_type,
                )
            elif cls_upper in IFC4_DISTRIBUTION_8_ATTR_CLASSES:
                target_entity = ifc_cls
                obj_type = ifc_cls if target_entity.upper() == "IFCBUILDINGELEMENTPROXY" else None
                proxy_ref = self.create_entity(
                    target_entity,
                    generate_ifc_guid(),
                    None,
                    proxy.tag,
                    None,
                    obj_type,
                    elem_pl,
                    prod_shape_ref,
                    None,
                )
            else:
                target_entity = "IfcBuildingElementProxy"
                obj_type = ifc_cls
                pred_type = f".{proxy.predefined_type.upper()}." if proxy.predefined_type else None
                if pred_type:
                    proxy_ref = self.create_entity(
                        target_entity,
                        generate_ifc_guid(),
                        None,
                        proxy.tag,
                        None,
                        obj_type,
                        elem_pl,
                        prod_shape_ref,
                        None,
                        pred_type,
                    )
                else:
                    proxy_ref = self.create_entity(
                        target_entity,
                        generate_ifc_guid(),
                        None,
                        proxy.tag,
                        None,
                        obj_type,
                        elem_pl,
                        prod_shape_ref,
                        None,
                    )

            element_tag_refs[proxy.tag] = proxy_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(proxy_ref)

            # Automatically bind default bSDD Psets + custom properties
            bind_default_psets_step(self, proxy_ref, target_entity, proxy.properties)

        # Spatial containment (IfcRelContainedInSpatialStructure)
        for st_id, elem_refs in storey_elements.items():
            if elem_refs and st_id in storey_refs:
                self.create_entity(
                    "IfcRelContainedInSpatialStructure",
                    generate_ifc_guid(),
                    None,
                    None,
                    None,
                    elem_refs,
                    storey_refs[st_id],
                )


        # 8. Topological Ports & Connections (IfcDistributionPort, IfcRelConnectsPortToElement, IfcRelConnectsPorts)
        port_entity_refs: Dict[str, str] = {}

        for port in getattr(resolved, "resolved_ports", []) or []:
            f_dir = f".{port.flow_direction.upper()}." if port.flow_direction else ".SOURCEANDSINK."
            port_ref = self.create_entity(
                "IfcDistributionPort",
                generate_ifc_guid(),
                None,
                port.port_id,
                None,
                None,
                None,
                None,
                f_dir,
                None,
                None,
            )
            port_entity_refs[port.global_port_id] = port_ref

            host_ref = element_tag_refs.get(port.host_tag)
            if host_ref:
                self.create_entity(
                    "IfcRelConnectsPortToElement",
                    generate_ifc_guid(),
                    None,
                    None,
                    None,
                    port_ref,
                    host_ref,
                )

        if getattr(resolved, "topology_graph", None):
            for p1_id, p2_id in resolved.topology_graph.connected_edges:
                p1_ref = port_entity_refs.get(p1_id)
                p2_ref = port_entity_refs.get(p2_id)
                if p1_ref and p2_ref:
                    self.create_entity(
                        "IfcRelConnectsPorts",
                        generate_ifc_guid(),
                        None,
                        None,
                        None,
                        p1_ref,
                        p2_ref,
                        None,
                    )

        # 9. Systems Containment (IfcDistributionSystem & IfcRelAssignsToGroup)
        systems_to_compile = []
        if hasattr(manifest, "systems") and manifest.systems:
            for sys in manifest.systems:
                systems_to_compile.append((sys.name, sys.system_type or sys.predefined_type, sys.elements))
        else:
            # Auto-group elements by system_type/system
            system_groups: Dict[str, List[str]] = {}
            for elem in getattr(resolved, "elements", []):
                stype = getattr(elem, "system_type", None) or getattr(getattr(elem, "element", None), "system_type", None)
                if stype:
                    system_groups.setdefault(str(stype), []).append(elem.tag)
            for s_name, tags in system_groups.items():
                systems_to_compile.append((s_name, s_name, tags))

        for sys_name, sys_type, elem_tags in systems_to_compile:
            ptype = f".{str(sys_type).upper()}." if sys_type else None
            sys_ref = self.create_entity(
                "IfcDistributionSystem",
                generate_ifc_guid(),
                None,
                sys_name,
                None,
                sys_name,
                None,
                ptype,
            )
            elem_refs = [element_tag_refs[t] for t in elem_tags if t in element_tag_refs]
            if elem_refs:
                self.create_entity(
                    "IfcRelAssignsToGroup",
                    generate_ifc_guid(),
                    None,
                    sys_name,
                    None,
                    elem_refs,
                    None,
                    sys_ref,
                )

        footer = ["ENDSEC;", "END-ISO-10303-21;"]
        return "\n".join(header + self.lines + footer) + "\n"


def _create_ifcopenshell_profile(model: Any, prof: Any, tag: str, pos2d: Any) -> Any:
    shape = getattr(prof, "shape", "BOX")
    prof_name = f"{tag}_Profile"
    try:
        if shape == "CIRCULAR":
            return model.createIfcCircleProfileDef("AREA", prof_name, pos2d, float(prof.radius))
        elif shape == "ELLIPSE":
            return model.createIfcEllipseProfileDef("AREA", prof_name, pos2d, float(prof.semi_major_axis), float(prof.semi_minor_axis))
        elif shape in ("ISHAPE", "I", "H"):
            return model.createIfcIShapeProfileDef("AREA", prof_name, pos2d, float(prof.overall_width), float(prof.overall_depth), float(prof.web_thickness), float(prof.flange_thickness))
        elif shape in ("LSHAPE", "L"):
            return model.createIfcLShapeProfileDef("AREA", prof_name, pos2d, float(prof.depth), float(prof.width), float(prof.thickness))
        elif shape in ("USHAPE", "U", "CSHAPE", "C"):
            return model.createIfcUShapeProfileDef("AREA", prof_name, pos2d, float(prof.depth), float(prof.flange_width), float(prof.web_thickness), float(prof.flange_thickness))
        elif shape in ("TSHAPE", "T"):
            return model.createIfcTShapeProfileDef("AREA", prof_name, pos2d, float(prof.depth), float(prof.flange_width), float(prof.web_thickness), float(prof.flange_thickness))
        elif shape in ("RHS", "RECTANGLE_HOLLOW", "BOX_HOLLOW"):
            return model.createIfcRectangleHollowProfileDef("AREA", prof_name, pos2d, float(prof.width), float(prof.depth), float(prof.wall_thickness))
        elif shape in ("CHS", "CIRCLE_HOLLOW", "PIPE_HOLLOW"):
            return model.createIfcCircleHollowProfileDef("AREA", prof_name, pos2d, float(prof.radius), float(prof.wall_thickness))
        elif shape in ("ARBITRARY", "ARBITRARY_CLOSED", "POLYGON", "ARBITRARY_WITH_VOIDS"):
            pts = getattr(prof, "outer_curve", None) or getattr(prof, "points", None) or []
            if pts:
                pt_objs = [model.createIfcCartesianPoint((float(p[0]), float(p[1]))) for p in pts]
                if pts[0][0] != pts[-1][0] or pts[0][1] != pts[-1][1]:
                    pt_objs.append(pt_objs[0])
                outer_poly = model.createIfcPolyline(pt_objs)
                voids = getattr(prof, "inner_curves", None) or getattr(prof, "voids", None) or []
                if voids:
                    inner_polys = []
                    for v in voids:
                        if v and len(v) >= 3:
                            v_objs = [model.createIfcCartesianPoint((float(p[0]), float(p[1]))) for p in v]
                            if v[0][0] != v[-1][0] or v[0][1] != v[-1][1]:
                                v_objs.append(v_objs[0])
                            inner_polys.append(model.createIfcPolyline(v_objs))
                    if inner_polys:
                        return model.createIfcArbitraryProfileDefWithVoids("AREA", prof_name, outer_poly, inner_polys)
                return model.createIfcArbitraryClosedProfileDef("AREA", prof_name, outer_poly)
    except Exception:
        pass
    return model.createIfcRectangleProfileDef("AREA", prof_name, pos2d, float(getattr(prof, "width", 0.3)), float(getattr(prof, "depth", 0.3)))


def _compile_with_ifcopenshell(resolved: ResolvedManifest, output_path: Path) -> Path:
    """Compile model using ifcopenshell library."""
    import ifcopenshell
    import ifcopenshell.api
    import numpy as np

    manifest = resolved.manifest
    project_info = manifest.project

    schema_ver = str(getattr(manifest, "schema_version", "") or getattr(manifest, "schema", "") or "")
    is_ifc43 = (
        "4.3" in schema_ver
        or "4X3" in schema_ver.upper()
        or bool(
            resolved.alignments
            or resolved.roads
            or resolved.bridges
            or getattr(resolved, "bridge_parts", [])
            or getattr(resolved, "bearings", [])
            or getattr(resolved, "marine_facilities", [])
            or getattr(resolved, "marine_parts", [])
            or getattr(resolved, "railways", [])
            or getattr(resolved, "railway_parts", [])
            or getattr(resolved, "track_elements", [])
        )
    )
    ifc_schema = "IFC4X3" if is_ifc43 else "IFC4"
    try:
        model = ifcopenshell.file(schema=ifc_schema)
    except Exception:
        model = ifcopenshell.file(schema="IFC4")

    # IfcProject
    project = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcProject", name=project_info.name
    )

    # Units
    u_length = ifcopenshell.api.run("unit.add_si_unit", model, unit_type="LENGTHUNIT")
    u_area = ifcopenshell.api.run("unit.add_si_unit", model, unit_type="AREAUNIT")
    u_vol = ifcopenshell.api.run("unit.add_si_unit", model, unit_type="VOLUMEUNIT")
    ifcopenshell.api.run("unit.assign_unit", model, units=[u_length, u_area, u_vol])

    # Geometric Contexts
    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body_context = ifcopenshell.api.run(
        "context.add_context",
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )

    # Site & Building
    site = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcSite", name="Default Site"
    )
    building = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcBuilding", name=project_info.name
    )

    ifcopenshell.api.run("aggregate.assign_object", model, products=[site], relating_object=project)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[building], relating_object=site)

    ifcopenshell.api.run("geometry.edit_object_placement", model, product=site, matrix=np.eye(4))
    ifcopenshell.api.run("geometry.edit_object_placement", model, product=building, matrix=np.eye(4))

    # Building Storeys
    storey_objs: Dict[str, ifcopenshell.entity_instance] = {}
    for storey in manifest.spatial_structure.storeys:
        st_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcBuildingStorey", name=storey.name
        )
        st_obj.Elevation = float(storey.elevation)
        m_st = np.eye(4)
        m_st[2][3] = float(storey.elevation)
        ifcopenshell.api.run("geometry.edit_object_placement", model, product=st_obj, matrix=m_st)
        storey_objs[storey.id] = st_obj

    if storey_objs:
        ifcopenshell.api.run(
            "aggregate.assign_object",
            model,
            products=list(storey_objs.values()),
            relating_object=building,
        )

    # Track elements per storey for spatial containment
    storey_products: Dict[str, List[ifcopenshell.entity_instance]] = {
        s_id: [] for s_id in storey_objs
    }
    ifcopenshell_elem_objs: Dict[str, Any] = {}

    # 0. Footings & Piles
    for footing in resolved.footings:
        footing_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcFooting", name=footing.tag
        )
        st_id = footing.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(footing_obj)

        fx, fy, fz = footing.position
        f_thick = float(footing.thickness)
        mat = np.eye(4)
        mat[0, 3] = float(fx)
        mat[1, 3] = float(fy)
        mat[2, 3] = float(fz)
        ifcopenshell.api.run(
            "geometry.edit_object_placement",
            model,
            product=footing_obj,
            matrix=mat,
        )

        pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
        rect_prof = model.createIfcRectangleProfileDef(
            "AREA", None, pos2d, float(footing.width), float(footing.depth)
        )
        pos3d = model.createIfcAxis2Placement3D(
            model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
            model.createIfcDirection((0.0, 0.0, 1.0)),
            model.createIfcDirection((1.0, 0.0, 0.0)),
        )
        solid = model.createIfcExtrudedAreaSolid(
            rect_prof, pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), f_thick
        )
        rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run("geometry.assign_representation", model, product=footing_obj, representation=rep)

        for pile in footing.piles:
            pile_obj = ifcopenshell.api.run(
                "root.create_entity", model, ifc_class="IfcPile", name=pile.tag
            )
            if st_id in storey_products:
                storey_products[st_id].append(pile_obj)

    # 1. Columns
    for col in resolved.columns:
        col_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcColumn", name=col.tag
        )
        st_id = col.element.placement.base_storey
        if st_id in storey_products:
            storey_products[st_id].append(col_obj)

        px, py, pz = col.start_point
        dx, dy, dz = col.direction_vector_3d
        z_axis = np.array([dx, dy, dz], dtype=float)
        z_norm = np.linalg.norm(z_axis)
        if z_norm > 1e-6:
            z_axis /= z_norm
        else:
            z_axis = np.array([0, 0, 1], dtype=float)

        if abs(z_axis[2]) < 0.9:
            x_axis = np.cross(np.array([0, 0, 1]), z_axis)
        else:
            x_axis = np.cross(np.array([0, 1, 0]), z_axis)
        x_norm = np.linalg.norm(x_axis)
        if x_norm > 1e-6:
            x_axis /= x_norm
        else:
            x_axis = np.array([1, 0, 0], dtype=float)
        y_axis = np.cross(z_axis, x_axis)

        mat = np.eye(4)
        mat[:3, 0] = x_axis
        mat[:3, 1] = y_axis
        mat[:3, 2] = z_axis
        mat[0, 3] = px
        mat[1, 3] = py
        mat[2, 3] = pz

        ifcopenshell.api.run(
            "geometry.edit_object_placement",
            model,
            product=col_obj,
            matrix=mat,
        )

        prof = col.element.profile
        pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
        ifc_prof = _create_ifcopenshell_profile(model, prof, col.tag, pos2d)

        solid = model.createIfcExtrudedAreaSolid(
            ifc_prof,
            model.createIfcAxis2Placement3D(
                model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                model.createIfcDirection((0.0, 0.0, 1.0)),
                model.createIfcDirection((1.0, 0.0, 0.0)),
            ),
            model.createIfcDirection((0.0, 0.0, 1.0)),
            float(col.height),
        )
        rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run("geometry.assign_representation", model, product=col_obj, representation=rep)

    # 2. Beams
    for beam in resolved.beams:
        beam_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcBeam", name=beam.tag
        )
        st_id = beam.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(beam_obj)

        px, py, pz = beam.start_point
        dx, dy, dz = beam.direction_vector_3d
        z_axis = np.array([dx, dy, dz], dtype=float)
        z_norm = np.linalg.norm(z_axis)
        if z_norm > 1e-6:
            z_axis /= z_norm
        else:
            z_axis = np.array([1, 0, 0], dtype=float)

        up = np.array([0.0, 0.0, 1.0], dtype=float)
        if abs(np.dot(z_axis, up)) < 0.99:
            y_raw = up - np.dot(up, z_axis) * z_axis
            y_axis = y_raw / np.linalg.norm(y_raw)
        else:
            y_raw = np.array([0.0, 1.0, 0.0], dtype=float) - np.dot(np.array([0.0, 1.0, 0.0]), z_axis) * z_axis
            y_axis = y_raw / np.linalg.norm(y_raw)

        x_axis = np.cross(y_axis, z_axis)
        x_norm = np.linalg.norm(x_axis)
        if x_norm > 1e-6:
            x_axis /= x_norm

        prof = beam.element.profile
        b_depth = float(getattr(prof, "depth", getattr(prof, "overall_depth", 0.3)))
        origin = np.array([px, py, pz], dtype=float) - y_axis * (b_depth / 2.0)

        mat = np.eye(4)
        mat[:3, 0] = x_axis
        mat[:3, 1] = y_axis
        mat[:3, 2] = z_axis
        mat[0, 3] = float(origin[0])
        mat[1, 3] = float(origin[1])
        mat[2, 3] = float(origin[2])

        ifcopenshell.api.run(
            "geometry.edit_object_placement",
            model,
            product=beam_obj,
            matrix=mat,
        )

        pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
        ifc_prof = _create_ifcopenshell_profile(model, prof, beam.tag, pos2d)

        solid = model.createIfcExtrudedAreaSolid(
            ifc_prof,
            model.createIfcAxis2Placement3D(
                model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                model.createIfcDirection((0.0, 0.0, 1.0)),
                model.createIfcDirection((1.0, 0.0, 0.0)),
            ),
            model.createIfcDirection((0.0, 0.0, 1.0)),
            float(beam.span_length),
        )
        rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run("geometry.assign_representation", model, product=beam_obj, representation=rep)

    # 3. Slabs
    for slab in resolved.slabs:
        slab_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcSlab", name=slab.tag
        )
        st_id = slab.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(slab_obj)

        if slab.polygon and len(slab.polygon) >= 3:
            h = float(slab.thickness)
            cz = float(slab.center[2])
            mat = np.eye(4)
            mat[2, 3] = cz - h
            ifcopenshell.api.run(
                "geometry.edit_object_placement",
                model,
                product=slab_obj,
                matrix=mat,
            )

            pts_objs = [model.createIfcCartesianPoint((float(p[0]), float(p[1]))) for p in slab.polygon]
            pts_objs.append(pts_objs[0])
            poly_curve = model.createIfcPolyline(pts_objs)
            prof = model.createIfcArbitraryClosedProfileDef("AREA", None, poly_curve)
            pos3d = model.createIfcAxis2Placement3D(
                model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                model.createIfcDirection((0.0, 0.0, 1.0)),
                model.createIfcDirection((1.0, 0.0, 0.0)),
            )
            solid = model.createIfcExtrudedAreaSolid(
                prof, pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), h
            )
            rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
            ifcopenshell.api.run("geometry.assign_representation", model, product=slab_obj, representation=rep)

    # 3.1 Coverings
    for cov in resolved.coverings:
        ptype = cov.covering_type.upper() if cov.covering_type else "CEILING"
        cov_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcCovering", predefined_type=ptype, name=cov.tag
        )
        st_id = cov.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(cov_obj)

        if cov.polygon and len(cov.polygon) >= 3:
            thick = float(cov.thickness)
            cz = float(cov.center[2])
            mat = np.eye(4)
            mat[2, 3] = cz
            ifcopenshell.api.run(
                "geometry.edit_object_placement",
                model,
                product=cov_obj,
                matrix=mat,
            )

            pts_objs = [model.createIfcCartesianPoint((float(p[0]), float(p[1]))) for p in cov.polygon]
            pts_objs.append(pts_objs[0])
            poly_curve = model.createIfcPolyline(pts_objs)
            prof = model.createIfcArbitraryClosedProfileDef("AREA", None, poly_curve)
            pos3d = model.createIfcAxis2Placement3D(
                model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                model.createIfcDirection((0.0, 0.0, 1.0)),
                model.createIfcDirection((1.0, 0.0, 0.0)),
            )
            solid = model.createIfcExtrudedAreaSolid(
                prof, pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), thick
            )
            rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
            ifcopenshell.api.run("geometry.assign_representation", model, product=cov_obj, representation=rep)

    # 4. Stairs, Stair Flights, Ramps, Railings
    for stair in resolved.stairs:
        stair_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcStair", name=stair.tag
        )
        st_id = stair.element.placement.from_storey
        if st_id in storey_products:
            storey_products[st_id].append(stair_obj)

        if stair.landing_polygon and len(stair.landing_polygon) >= 3:
            lz = min(p[2] for p in stair.landing_polygon)
            l_thick = float(stair.landing_thickness)
            mat = np.eye(4)
            mat[2, 3] = float(lz)
            ifcopenshell.api.run(
                "geometry.edit_object_placement",
                model,
                product=stair_obj,
                matrix=mat,
            )

            pts_objs = [model.createIfcCartesianPoint((float(p[0]), float(p[1]))) for p in stair.landing_polygon]
            pts_objs.append(pts_objs[0])
            poly_curve = model.createIfcPolyline(pts_objs)
            prof = model.createIfcArbitraryClosedProfileDef("AREA", None, poly_curve)
            pos3d = model.createIfcAxis2Placement3D(
                model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                model.createIfcDirection((0.0, 0.0, 1.0)),
                model.createIfcDirection((1.0, 0.0, 0.0)),
            )
            solid = model.createIfcExtrudedAreaSolid(
                prof, pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), l_thick
            )
            rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
            ifcopenshell.api.run("geometry.assign_representation", model, product=stair_obj, representation=rep)

        for s_idx, step in enumerate(stair.steps):
            step_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBuildingElementPart",
                name=f"{stair.tag}_Step_{step.step_index}",
                predefined_type="USERDEFINED",
            )
            if st_id in storey_products:
                storey_products[st_id].append(step_obj)

            scx, scy, scz = step.position
            s_rot = step.rotation or 0.0
            s_cos = math.cos(s_rot)
            s_sin = math.sin(s_rot)
            s_mat = np.eye(4)
            s_mat[0, 0] = s_cos
            s_mat[0, 1] = -s_sin
            s_mat[1, 0] = s_sin
            s_mat[1, 1] = s_cos
            s_mat[0, 3] = float(scx)
            s_mat[1, 3] = float(scy)
            s_mat[2, 3] = float(scz - step.riser / 2.0)
            ifcopenshell.api.run("geometry.edit_object_placement", model, product=step_obj, matrix=s_mat)

            s_pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
            s_prof = model.createIfcRectangleProfileDef("AREA", None, s_pos2d, float(step.width), float(step.tread))
            s_pos3d = model.createIfcAxis2Placement3D(
                model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                model.createIfcDirection((0.0, 0.0, 1.0)),
                model.createIfcDirection((1.0, 0.0, 0.0)),
            )
            s_solid = model.createIfcExtrudedAreaSolid(
                s_prof, s_pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(step.riser)
            )
            s_rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [s_solid])
            ifcopenshell.api.run("geometry.assign_representation", model, product=step_obj, representation=s_rep)

    for flight in resolved.stair_flights:
        flight_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcStairFlight", name=flight.tag
        )
        st_id = flight.element.placement.from_storey if flight.element else None
        if st_id and st_id in storey_products:
            storey_products[st_id].append(flight_obj)

    for ramp in resolved.ramps:
        ramp_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcRamp", name=ramp.tag
        )
        st_id = ramp.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(ramp_obj)

    for railing in resolved.railings:
        ptype = railing.predefined_type if railing.predefined_type in ("HANDRAIL", "GUARDRAIL", "BALUSTRADE", "USERDEFINED") else "HANDRAIL"
        railing_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcRailing", name=railing.tag, predefined_type=ptype
        )
        st_id = railing.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(railing_obj)

    # 5. Walls & Children
    for wall in resolved.walls:
        wall_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcWall", name=wall.tag
        )
        st_id = wall.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(wall_obj)

        x1, y1, z1 = wall.start_point
        x2, y2, z2 = wall.end_point
        dx = x2 - x1
        dy = y2 - y1
        l_2d = math.hypot(dx, dy)
        if l_2d > 1e-6:
            ux, uy = dx / l_2d, dy / l_2d
        else:
            ux, uy = 1.0, 0.0

        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        cz = z1

        mat = np.eye(4)
        mat[0, 0] = ux
        mat[0, 1] = -uy
        mat[1, 0] = uy
        mat[1, 1] = ux
        mat[0, 3] = cx
        mat[1, 3] = cy
        mat[2, 3] = cz
        ifcopenshell.api.run(
            "geometry.edit_object_placement",
            model,
            product=wall_obj,
            matrix=mat,
        )

        pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
        rect_prof = model.createIfcRectangleProfileDef(
            "AREA", None, pos2d, float(wall.length), float(wall.thickness)
        )
        pos3d = model.createIfcAxis2Placement3D(
            model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
            model.createIfcDirection((0.0, 0.0, 1.0)),
            model.createIfcDirection((1.0, 0.0, 0.0)),
        )
        solid = model.createIfcExtrudedAreaSolid(
            rect_prof, pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(wall.height)
        )
        rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run("geometry.assign_representation", model, product=wall_obj, representation=rep)

        for child in wall.children:
            if isinstance(child, ResolvedDoor):
                door_obj = ifcopenshell.api.run(
                    "root.create_entity", model, ifc_class="IfcDoor", name=child.tag
                )
                door_obj.OverallHeight = float(child.height)
                door_obj.OverallWidth = float(child.width)

                dcx, dcy, dcz = child.position
                dmat = np.eye(4)
                dmat[0, 0] = ux
                dmat[0, 1] = -uy
                dmat[1, 0] = uy
                dmat[1, 1] = ux
                dmat[0, 3] = float(dcx)
                dmat[1, 3] = float(dcy)
                dmat[2, 3] = float(dcz)
                ifcopenshell.api.run(
                    "geometry.edit_object_placement",
                    model,
                    product=door_obj,
                    matrix=dmat,
                )

                d_pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
                d_prof = model.createIfcRectangleProfileDef(
                    "AREA", None, d_pos2d, float(child.width), float(child.frame_thickness)
                )
                d_pos3d = model.createIfcAxis2Placement3D(
                    model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                    model.createIfcDirection((0.0, 0.0, 1.0)),
                    model.createIfcDirection((1.0, 0.0, 0.0)),
                )
                d_solid = model.createIfcExtrudedAreaSolid(
                    d_prof, d_pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(child.height)
                )
                d_rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [d_solid])
                ifcopenshell.api.run("geometry.assign_representation", model, product=door_obj, representation=d_rep)

                opening_obj = ifcopenshell.api.run(
                    "root.create_entity",
                    model,
                    ifc_class="IfcOpeningElement",
                    name=f"{child.tag}_Opening",
                )
                ifcopenshell.api.run("geometry.edit_object_placement", model, product=opening_obj, matrix=dmat)
                op_d_prof = model.createIfcRectangleProfileDef(
                    "AREA", None, d_pos2d, float(child.width), float(wall.thickness) * 1.2
                )
                op_d_solid = model.createIfcExtrudedAreaSolid(
                    op_d_prof, d_pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(child.height)
                )
                op_d_rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [op_d_solid])
                ifcopenshell.api.run("geometry.assign_representation", model, product=opening_obj, representation=op_d_rep)

                ifcopenshell.api.run("feature.add_feature", model, feature=opening_obj, element=wall_obj)
                ifcopenshell.api.run("feature.add_filling", model, opening=opening_obj, element=door_obj)

                if st_id in storey_products:
                    storey_products[st_id].append(door_obj)

            elif isinstance(child, ResolvedWindow):
                win_obj = ifcopenshell.api.run(
                    "root.create_entity", model, ifc_class="IfcWindow", name=child.tag
                )
                win_obj.OverallHeight = float(child.height)
                win_obj.OverallWidth = float(child.width)

                wcx, wcy, wcz = child.position
                wmat = np.eye(4)
                wmat[0, 0] = ux
                wmat[0, 1] = -uy
                wmat[1, 0] = uy
                wmat[1, 1] = ux
                wmat[0, 3] = float(wcx)
                wmat[1, 3] = float(wcy)
                wmat[2, 3] = float(wcz)
                ifcopenshell.api.run(
                    "geometry.edit_object_placement",
                    model,
                    product=win_obj,
                    matrix=wmat,
                )

                w_pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
                w_prof = model.createIfcRectangleProfileDef(
                    "AREA", None, w_pos2d, float(child.width), float(child.frame_thickness)
                )
                w_pos3d = model.createIfcAxis2Placement3D(
                    model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                    model.createIfcDirection((0.0, 0.0, 1.0)),
                    model.createIfcDirection((1.0, 0.0, 0.0)),
                )
                w_solid = model.createIfcExtrudedAreaSolid(
                    w_prof, w_pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(child.height)
                )
                w_rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [w_solid])
                ifcopenshell.api.run("geometry.assign_representation", model, product=win_obj, representation=w_rep)

                opening_obj = ifcopenshell.api.run(
                    "root.create_entity",
                    model,
                    ifc_class="IfcOpeningElement",
                    name=f"{child.tag}_Opening",
                )
                ifcopenshell.api.run("geometry.edit_object_placement", model, product=opening_obj, matrix=wmat)
                op_w_prof = model.createIfcRectangleProfileDef(
                    "AREA", None, w_pos2d, float(child.width), float(wall.thickness) * 1.2
                )
                op_w_solid = model.createIfcExtrudedAreaSolid(
                    op_w_prof, w_pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(child.height)
                )
                op_w_rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [op_w_solid])
                ifcopenshell.api.run("geometry.assign_representation", model, product=opening_obj, representation=op_w_rep)

                ifcopenshell.api.run("feature.add_feature", model, feature=opening_obj, element=wall_obj)
                ifcopenshell.api.run("feature.add_filling", model, opening=opening_obj, element=win_obj)

                if st_id in storey_products:
                    storey_products[st_id].append(win_obj)

    # 4. Custom Elements
    for custom in resolved.custom_elements:
        ifc_cls = derive_custom_ifc_class(custom.layer)
        custom_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class=ifc_cls,
            name=custom.tag,
        )
        st_id = custom.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(custom_obj)

        if st_id in storey_objs:
            ifcopenshell.api.run(
                "spatial.assign_container",
                model,
                products=[custom_obj],
                relating_structure=storey_objs[st_id],
            )

        px, py, pz = custom.position
        rx, ry, rz = custom.rotation if custom.rotation else (0.0, 0.0, 0.0)
        mat = _build_transform_matrix((px, py, pz), (rx, ry, rz))
        ifcopenshell.api.run(
            "geometry.edit_object_placement",
            model,
            product=custom_obj,
            matrix=mat,
        )

        solid_entity = None
        if custom.element.solid or custom.resolved_solid:
            c_solid = custom.element.solid or custom.resolved_solid
            if isinstance(c_solid, (SweptDiskSolid, ResolvedSweptDisk)):
                directrix_pts = c_solid.directrix
                pt_objs = [model.createIfcCartesianPoint((float(p[0]), float(p[1]), float(p[2]))) for p in directrix_pts]
                directrix_curve = model.createIfcPolyline(pt_objs)
                r = float(c_solid.radius)
                inner_r = float(c_solid.inner_radius) if c_solid.inner_radius is not None else None
                solid_entity = model.createIfcSweptDiskSolid(directrix_curve, r, inner_r, None, None)
            elif isinstance(c_solid, (RevolvedAreaSolid, ResolvedRevolvedArea)):
                pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
                prof_def = _create_ifcopenshell_profile(model, c_solid.profile, custom.tag, pos2d)
                axis_pt = model.createIfcCartesianPoint((float(x) for x in c_solid.axis_point))
                axis_dir = model.createIfcDirection((float(x) for x in c_solid.axis_direction))
                axis1 = model.createIfcAxis1Placement(axis_pt, axis_dir)
                angle_rad = float(c_solid.revolution_angle) * math.pi / 180.0
                solid_entity = model.createIfcRevolvedAreaSolid(prof_def, None, axis1, angle_rad)

        if solid_entity:
            rep = model.createIfcShapeRepresentation(
                body_context, "Body", "SweptSolid", [solid_entity]
            )
            ifcopenshell.api.run(
                "geometry.assign_representation",
                model,
                product=custom_obj,
                representation=rep,
            )
        else:
            dims = custom.dimensions or custom.element.dimensions
            if dims:
                w = float(dims.width)
                d = float(dims.depth if dims.depth is not None else dims.width)
                h = float(dims.height)

                profile = model.createIfcRectangleProfileDef(
                    "AREA",
                    None,
                    model.createIfcAxis2Placement2D(
                        model.createIfcCartesianPoint((0.0, 0.0))
                    ),
                    w,
                    d,
                )
                solid = model.createIfcExtrudedAreaSolid(
                    profile,
                    model.createIfcAxis2Placement3D(
                        model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                        model.createIfcDirection((0.0, 0.0, 1.0)),
                        model.createIfcDirection((1.0, 0.0, 0.0)),
                    ),
                    model.createIfcDirection((0.0, 0.0, 1.0)),
                    h,
                )
                rep = model.createIfcShapeRepresentation(
                    body_context, "Body", "SweptSolid", [solid]
                )
                ifcopenshell.api.run(
                    "geometry.assign_representation",
                    model,
                    product=custom_obj,
                    representation=rep,
                )

    # 5.1 Curtain Walls
    for cw in resolved.curtain_walls:
        pred_type = cw.element.predefined_type if cw.element.predefined_type in ("POST_AND_BEAM", "UNITIZED", "USERDEFINED") else "NOTDEFINED"
        cw_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcCurtainWall",
            name=cw.tag,
            predefined_type=pred_type,
        )
        st_id = cw.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(cw_obj)

        x1, y1, z1 = cw.start_point
        x2, y2, z2 = cw.end_point
        dx, dy = x2 - x1, y2 - y1
        l_2d = math.hypot(dx, dy)
        ux, uy = (dx / l_2d, dy / l_2d) if l_2d > 1e-6 else (1.0, 0.0)

        mat = np.eye(4)
        mat[0, 0] = ux
        mat[0, 1] = -uy
        mat[1, 0] = uy
        mat[1, 1] = ux
        mat[0, 3] = (x1 + x2) / 2.0
        mat[1, 3] = (y1 + y2) / 2.0
        mat[2, 3] = z1
        ifcopenshell.api.run(
            "geometry.edit_object_placement",
            model,
            product=cw_obj,
            matrix=mat,
        )

        pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
        rect_prof = model.createIfcRectangleProfileDef("AREA", None, pos2d, float(cw.length), float(cw.element.glass_thickness or 0.01))
        pos3d = model.createIfcAxis2Placement3D(
            model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
            model.createIfcDirection((0.0, 0.0, 1.0)),
            model.createIfcDirection((1.0, 0.0, 0.0)),
        )
        solid = model.createIfcExtrudedAreaSolid(
            rect_prof, pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(cw.height)
        )
        rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run("geometry.assign_representation", model, product=cw_obj, representation=rep)

    # 5.2 Plates
    for plate in resolved.plates:
        pred_type = plate.element.predefined_type if plate.element.predefined_type in ("CURTAIN_PANEL", "SHEET", "FLANGE_PLATE", "BASE_PLATE", "USERDEFINED") else "NOTDEFINED"
        plate_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcPlate",
            name=plate.tag,
            predefined_type=pred_type,
        )
        st_id = plate.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(plate_obj)

        px, py, pz = plate.position
        rx, ry, rz = plate.rotation
        mat = _build_transform_matrix((px, py, pz), (rx, ry, rz))
        ifcopenshell.api.run(
            "geometry.edit_object_placement",
            model,
            product=plate_obj,
            matrix=mat,
        )

        if plate.polygon and len(plate.polygon) >= 3:
            pts_objs = [model.createIfcCartesianPoint((float(p[0]), float(p[1]))) for p in plate.polygon]
            pts_objs.append(pts_objs[0])
            poly_curve = model.createIfcPolyline(pts_objs)
            prof = model.createIfcArbitraryClosedProfileDef("AREA", None, poly_curve)
        else:
            pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
            prof = model.createIfcRectangleProfileDef("AREA", None, pos2d, float(plate.width), float(plate.depth))

        pos3d = model.createIfcAxis2Placement3D(
            model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
            model.createIfcDirection((0.0, 0.0, 1.0)),
            model.createIfcDirection((1.0, 0.0, 0.0)),
        )
        solid = model.createIfcExtrudedAreaSolid(
            prof, pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(plate.thickness)
        )
        rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run("geometry.assign_representation", model, product=plate_obj, representation=rep)

    # 5.3 Civil Earthworks & Retaining Walls & Civil Infrastructure (IFC4.3)
    for ew in resolved.earthworks_elements:
        ew_cls = "IfcEarthworksElement" if hasattr(model, "schema") and model.schema in ("IFC4X3", "IFC4X3_ADD2") else "IfcGeographicElement"
        try:
            ew_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class=ew_cls,
                name=ew.tag,
            )
        except Exception:
            ew_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcGeographicElement",
                name=ew.tag,
                predefined_type="USERDEFINED",
            )
        ew_obj.ObjectType = f"IfcEarthworksElement.{ew.predefined_type}"
        st_id = ew.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(ew_obj)

    for cut in resolved.earthworks_cuts:
        cut_cls = "IfcEarthworksCut" if hasattr(model, "schema") and model.schema in ("IFC4X3", "IFC4X3_ADD2") else "IfcGeographicElement"
        try:
            cut_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class=cut_cls,
                name=cut.tag,
            )
        except Exception:
            cut_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcGeographicElement",
                name=cut.tag,
                predefined_type="USERDEFINED",
            )
        cut_obj.ObjectType = f"IfcEarthworksCut.{cut.predefined_type}"
        st_id = cut.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(cut_obj)

    for fill in resolved.earthworks_fills:
        fill_cls = "IfcEarthworksFill" if hasattr(model, "schema") and model.schema in ("IFC4X3", "IFC4X3_ADD2") else "IfcGeographicElement"
        try:
            fill_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class=fill_cls,
                name=fill.tag,
            )
        except Exception:
            fill_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcGeographicElement",
                name=fill.tag,
                predefined_type="USERDEFINED",
            )
        fill_obj.ObjectType = f"IfcEarthworksFill.{fill.predefined_type}"
        st_id = fill.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(fill_obj)

    for strat in resolved.geotechnical_strata:
        strat_cls = "IfcGeotechnicalStratum" if hasattr(model, "schema") and model.schema in ("IFC4X3", "IFC4X3_ADD2") else "IfcGeographicElement"
        try:
            strat_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class=strat_cls,
                name=strat.tag,
            )
        except Exception:
            strat_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcGeographicElement",
                name=strat.tag,
                predefined_type="USERDEFINED",
            )
        strat_obj.ObjectType = f"IfcGeotechnicalStratum.{strat.predefined_type}"
        st_id = strat.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(strat_obj)

    for soil in resolved.soils:
        soil_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcGeographicElement",
            name=soil.tag,
            predefined_type="USERDEFINED",
        )
        soil_obj.ObjectType = f"IfcSoil.{soil.soil_type}"
        st_id = soil.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(soil_obj)

    for rw in resolved.retaining_walls:
        rw_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcWall",
            name=rw.tag,
            predefined_type="RETAINING",
        )
        st_id = rw.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(rw_obj)

    for align in resolved.alignments:
        try:
            align_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcAlignment",
                name=align.tag,
            )
        except Exception:
            align_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBuildingElementProxy",
                name=align.tag,
            )
            align_obj.ObjectType = f"IfcAlignment.{align.predefined_type}"

        if align.swept_solids:
            rep_items = []
            for solid in align.swept_solids:
                verts = solid["vertices"]
                faces = solid["faces"]
                if verts and faces:
                    pts = model.createIfcCartesianPointList3D([list(v) for v in verts])
                    tfs = model.createIfcTriangulatedFaceSet(Coordinates=pts, CoordIndex=[list(f) for f in faces])
                    rep_items.append(tfs)
            if rep_items:
                rep = model.createIfcShapeRepresentation(
                    ContextOfItems=body_context,
                    RepresentationIdentifier="Body",
                    RepresentationType="Tessellation",
                    Items=rep_items,
                )
                ifcopenshell.api.run("geometry.assign_representation", model, product=align_obj, representation=rep)

        st_id = align.element.placement.storey
        if st_id and st_id in storey_products:
            storey_products[st_id].append(align_obj)

    for road in resolved.roads:
        try:
            road_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcRoad",
                name=road.tag,
            )
            try:
                ifcopenshell.api.run("aggregate.assign_object", model, products=[road_obj], relating_object=site)
            except Exception:
                pass
        except Exception:
            road_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBuildingElementProxy",
                name=road.tag,
            )
            road_obj.ObjectType = f"IfcRoad.{road.predefined_type}"
            st_id = road.element.placement.storey
            if st_id and st_id in storey_products:
                storey_products[st_id].append(road_obj)

    bridge_objs: Dict[str, Any] = {}
    for bridge in resolved.bridges:
        try:
            bridge_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBridge",
                name=bridge.tag,
            )
            try:
                ifcopenshell.api.run("aggregate.assign_object", model, products=[bridge_obj], relating_object=site)
            except Exception:
                pass
        except Exception:
            bridge_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBuildingElementProxy",
                name=bridge.tag,
            )
            bridge_obj.ObjectType = f"IfcBridge.{bridge.predefined_type}"
            st_id = bridge.element.placement.storey
            if st_id and st_id in storey_products:
                storey_products[st_id].append(bridge_obj)

        ifcopenshell.api.run("geometry.edit_object_placement", model, product=bridge_obj, matrix=np.eye(4))
        bridge_objs[bridge.tag] = bridge_obj

    for mp in getattr(resolved, "marine_parts", []) or []:
        ptype = mp.predefined_type.upper()
        if ptype in ("BERTH", "JETTY", "QUAY", "PIER", "USERDEFINED", "NOTDEFINED"):
            try:
                mp_obj = ifcopenshell.api.run(
                    "root.create_entity",
                    model,
                    ifc_class="IfcMarinePart",
                    name=mp.tag,
                    predefined_type=ptype,
                )
            except Exception:
                mp_obj = ifcopenshell.api.run(
                    "root.create_entity",
                    model,
                    ifc_class="IfcBuildingElementProxy",
                    name=mp.tag,
                )
                mp_obj.ObjectType = f"IfcMarinePart.{ptype}"
        else:
            try:
                mp_obj = ifcopenshell.api.run(
                    "root.create_entity",
                    model,
                    ifc_class="IfcMarinePart",
                    name=mp.tag,
                    predefined_type="USERDEFINED",
                )
                mp_obj.ObjectType = ptype
            except Exception:
                mp_obj = ifcopenshell.api.run(
                    "root.create_entity",
                    model,
                    ifc_class="IfcBuildingElementProxy",
                    name=mp.tag,
                )
                mp_obj.ObjectType = f"IfcMarinePart.{ptype}"

        st_id = mp.element.placement.storey if mp.element and mp.element.placement else None
        if st_id and st_id in storey_products:
            storey_products[st_id].append(mp_obj)

        px, py, pz = mp.position
        ptype_str = mp.predefined_type.upper() if mp.predefined_type else "BERTH"

        if ptype_str in ("BREAKWATER", "REVETMENT"):
            mat = _build_transform_matrix((px, py, pz), (0.0, 0.0, mp.rotation_angle))
            ifcopenshell.api.run("geometry.edit_object_placement", model, product=mp_obj, matrix=mat)

            H = float(mp.depth + mp.crest_elevation) if (mp.depth + mp.crest_elevation) > 0 else float(mp.depth)
            top_w = float(mp.crest_width)
            bot_w = float(mp.base_width)

            p1 = model.createIfcCartesianPoint((-bot_w / 2.0, 0.0))
            p2 = model.createIfcCartesianPoint((bot_w / 2.0, 0.0))
            p3 = model.createIfcCartesianPoint((top_w / 2.0, H))
            p4 = model.createIfcCartesianPoint((-top_w / 2.0, H))
            polyline = model.createIfcPolyline([p1, p2, p3, p4, p1])
            prof = model.createIfcArbitraryClosedProfileDef("AREA", None, polyline)

            pos3d = model.createIfcAxis2Placement3D(
                model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                model.createIfcDirection((0.0, 0.0, 1.0)),
                model.createIfcDirection((1.0, 0.0, 0.0)),
            )
            solid = model.createIfcExtrudedAreaSolid(
                prof, pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(mp.length)
            )
        elif mp.predefined_type in ("SEAWALL", "GROYNE") and mp.wall_profile_points:
            pz += mp.deck_elevation
            mat = _build_transform_matrix((px, py, pz), (0.0, 0.0, mp.rotation_angle))
            ifcopenshell.api.run("geometry.edit_object_placement", model, product=mp_obj, matrix=mat)

            pt_objs = [model.createIfcCartesianPoint((float(p[0]), float(p[1]))) for p in mp.wall_profile_points]
            if mp.wall_profile_points[0] != mp.wall_profile_points[-1]:
                pt_objs.append(pt_objs[0])
            poly = model.createIfcPolyline(pt_objs)
            prof = model.createIfcArbitraryClosedProfileDef("AREA", None, poly)
            pos3d = model.createIfcAxis2Placement3D(
                model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                model.createIfcDirection((0.0, 0.0, 1.0)),
                model.createIfcDirection((1.0, 0.0, 0.0)),
            )
            solid = model.createIfcExtrudedAreaSolid(
                prof, pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(mp.length)
            )
        else:
            pz += mp.deck_elevation
            mat = _build_transform_matrix((px, py, pz), (0.0, 0.0, mp.rotation_angle))
            ifcopenshell.api.run("geometry.edit_object_placement", model, product=mp_obj, matrix=mat)

            pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
            prof = model.createIfcRectangleProfileDef("AREA", None, pos2d, float(mp.length), float(mp.width))
            pos3d = model.createIfcAxis2Placement3D(
                model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                model.createIfcDirection((0.0, 0.0, 1.0)),
                model.createIfcDirection((1.0, 0.0, 0.0)),
            )
            solid = model.createIfcExtrudedAreaSolid(
                prof, pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(mp.deck_thickness if mp.deck_thickness > 0 else 1.0)
            )
        rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run("geometry.assign_representation", model, product=mp_obj, representation=rep)

        for pile in mp.piles:
            try:
                pile_obj = ifcopenshell.api.run(
                    "root.create_entity", model, ifc_class="IfcPile", name=pile.tag
                )
            except Exception:
                pile_obj = ifcopenshell.api.run(
                    "root.create_entity", model, ifc_class="IfcBuildingElementProxy", name=pile.tag
                )
                pile_obj.ObjectType = "IfcPile"

            p_px, p_py, p_pz = pile.position
            p_mat = _build_transform_matrix((p_px, p_py, p_pz - pile.length), (0.0, 0.0, 0.0))
            ifcopenshell.api.run("geometry.edit_object_placement", model, product=pile_obj, matrix=p_mat)

            p_pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
            if pile.shape == "CIRCULAR":
                p_prof = model.createIfcCircleProfileDef("AREA", None, p_pos2d, float(pile.dimension / 2.0))
            else:
                p_prof = model.createIfcRectangleProfileDef("AREA", None, p_pos2d, float(pile.dimension), float(pile.dimension))
            p_pos3d = model.createIfcAxis2Placement3D(
                model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                model.createIfcDirection((0.0, 0.0, 1.0)),
                model.createIfcDirection((1.0, 0.0, 0.0)),
            )
            p_solid = model.createIfcExtrudedAreaSolid(
                p_prof, p_pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(pile.length)
            )
            p_rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [p_solid])
            ifcopenshell.api.run("geometry.assign_representation", model, product=pile_obj, representation=p_rep)

            if st_id and st_id in storey_products:
                storey_products[st_id].append(pile_obj)
            elif default_storey_obj:
                ifcopenshell.api.run("spatial.assign_container", model, products=[pile_obj], relating_structure=default_storey_obj)

    bridge_part_objs: Dict[str, Any] = {}
    for bp in getattr(resolved, "bridge_parts", []) or []:
        try:
            bp_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBridgePart",
                name=bp.tag,
                predefined_type=bp.predefined_type.upper(),
            )
        except Exception:
            bp_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBuildingElementProxy",
                name=bp.tag,
            )
            bp_obj.ObjectType = f"IfcBridgePart.{bp.predefined_type}"

        bridge_part_objs[bp.tag] = bp_obj

        parent_bridge = None
        if bp.bridge_tag and bp.bridge_tag in bridge_objs:
            parent_bridge = bridge_objs[bp.bridge_tag]
        elif bridge_objs:
            parent_bridge = next(iter(bridge_objs.values()))

        if parent_bridge:
            try:
                ifcopenshell.api.run("aggregate.assign_object", model, products=[bp_obj], relating_object=parent_bridge)
            except Exception:
                pass

        px, py, pz = bp.position
        mat = _build_transform_matrix((px, py, pz), (0.0, 0.0, 0.0))
        ifcopenshell.api.run("geometry.edit_object_placement", model, product=bp_obj, matrix=mat)

        pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
        prof = model.createIfcRectangleProfileDef("AREA", None, pos2d, float(bp.span_length), float(bp.width))
        pos3d = model.createIfcAxis2Placement3D(
            model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
            model.createIfcDirection((0.0, 0.0, 1.0)),
            model.createIfcDirection((1.0, 0.0, 0.0)),
        )
        solid = model.createIfcExtrudedAreaSolid(
            prof, pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(bp.thickness)
        )
        rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run("geometry.assign_representation", model, product=bp_obj, representation=rep)

    for br in getattr(resolved, "bearings", []) or []:
        try:
            br_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBearing",
                name=br.tag,
                predefined_type=br.predefined_type.upper(),
            )
        except Exception:
            br_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBuildingElementProxy",
                name=br.tag,
            )
            br_obj.ObjectType = f"IfcBearing.{br.predefined_type}"

        parent_part = None
        if br.bridge_part_tag and br.bridge_part_tag in bridge_part_objs:
            parent_part = bridge_part_objs[br.bridge_part_tag]
        elif bridge_part_objs:
            parent_part = next(iter(bridge_part_objs.values()))

        if parent_part:
            try:
                ifcopenshell.api.run("spatial.assign_container", model, products=[br_obj], relating_structure=parent_part)
            except Exception:
                pass
        else:
            st_id = br.element.placement.storey
            if st_id and st_id in storey_products:
                storey_products[st_id].append(br_obj)

        px, py, pz = br.position
        mat = _build_transform_matrix((px, py, pz), (0.0, 0.0, 0.0))
        ifcopenshell.api.run("geometry.edit_object_placement", model, product=br_obj, matrix=mat)

        pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
        prof = model.createIfcRectangleProfileDef("AREA", None, pos2d, float(br.width), float(br.depth))
        pos3d = model.createIfcAxis2Placement3D(
            model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
            model.createIfcDirection((0.0, 0.0, 1.0)),
            model.createIfcDirection((1.0, 0.0, 0.0)),
        )
        solid = model.createIfcExtrudedAreaSolid(
            prof, pos3d, model.createIfcDirection((0.0, 0.0, 1.0)), float(br.height)
        )
        rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run("geometry.assign_representation", model, product=br_obj, representation=rep)

    for mf in getattr(resolved, "marine_facilities", []) or []:
        ptype = mf.predefined_type.upper() if mf.predefined_type else "PORT"
        try:
            mf_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcMarineFacility",
                name=mf.name or mf.tag,
                predefined_type=ptype,
            )
        except Exception:
            mf_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBuildingElementProxy",
                name=mf.name or mf.tag,
            )
            mf_obj.ObjectType = f"IfcMarineFacility.{ptype}"

        try:
            ifcopenshell.api.run("aggregate.assign_object", model, products=[mf_obj], relating_object=site)
        except Exception:
            pass

        ifcopenshell.api.run("geometry.edit_object_placement", model, product=mf_obj, matrix=np.eye(4))
        ifcopenshell_elem_objs[mf.tag] = mf_obj

    for rw in resolved.railways:
        try:
            rw_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcRailway",
                name=rw.tag,
            )
        except Exception:
            rw_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBuildingElementProxy",
                name=rw.tag,
            )
            rw_obj.ObjectType = f"IfcRailway.{rw.predefined_type}"
        st_id = rw.element.placement.storey
        if st_id and st_id in storey_products:
            storey_products[st_id].append(rw_obj)

    for rwp in resolved.railway_parts:
        try:
            rwp_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcRailwayPart",
                name=rwp.tag,
            )
        except Exception:
            rwp_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBuildingElementProxy",
                name=rwp.tag,
            )
            rwp_obj.ObjectType = f"IfcRailwayPart.{rwp.predefined_type}"
        st_id = rwp.element.placement.storey
        if st_id and st_id in storey_products:
            storey_products[st_id].append(rwp_obj)

    for te in resolved.track_elements:
        try:
            te_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcTrackElement",
                name=te.tag,
            )
        except Exception:
            te_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBuildingElementProxy",
                name=te.tag,
            )
            te_obj.ObjectType = f"IfcTrackElement.{te.predefined_type}"
        st_id = te.element.placement.storey
        if st_id and st_id in storey_products:
            storey_products[st_id].append(te_obj)

    # 6. Roofs & Roof Openings / Skylights
    for roof in resolved.roofs:
        pred_type = roof.element.roof_type if roof.element.roof_type in ("GABLE_ROOF", "HIP_ROOF", "SHED_ROOF", "FLAT_ROOF") else "NOTDEFINED"
        roof_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcRoof",
            name=roof.tag,
            predefined_type=pred_type,
        )
        st_id = roof.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(roof_obj)

        all_pts = []
        coord_indices = []
        if roof.planes:
            for plane in roof.planes:
                if plane.polygon and len(plane.polygon) >= 3:
                    base_idx = len(all_pts) + 1
                    for pt in plane.polygon:
                        all_pts.append((float(pt[0]), float(pt[1]), float(pt[2])))
                    for i in range(1, len(plane.polygon) - 1):
                        coord_indices.append([base_idx, base_idx + i, base_idx + i + 1])
        elif roof.footprint_polygon and len(roof.footprint_polygon) >= 3:
            base_idx = len(all_pts) + 1
            for pt in roof.footprint_polygon:
                all_pts.append((float(pt[0]), float(pt[1]), float(pt[2])))
            for i in range(1, len(roof.footprint_polygon) - 1):
                coord_indices.append([base_idx, base_idx + i, base_idx + i + 1])

        if all_pts and coord_indices:
            ifcopenshell.api.run(
                "geometry.edit_object_placement",
                model,
                product=roof_obj,
                matrix=np.eye(4),
            )
            pt_list = model.createIfcCartesianPointList3D(all_pts)
            face_set = model.createIfcTriangulatedFaceSet(pt_list, None, False, coord_indices)
            rep = model.createIfcShapeRepresentation(body_context, "Body", "Tessellation", [face_set])
            ifcopenshell.api.run("geometry.assign_representation", model, product=roof_obj, representation=rep)

        for child in roof.children:
            if isinstance(child, ResolvedDoor):
                door_obj = ifcopenshell.api.run(
                    "root.create_entity", model, ifc_class="IfcDoor", name=child.tag
                )
                door_obj.OverallHeight = float(child.height)
                door_obj.OverallWidth = float(child.width)

                opening_obj = ifcopenshell.api.run(
                    "root.create_entity",
                    model,
                    ifc_class="IfcOpeningElement",
                    name=f"{child.tag}_Opening",
                )
                ifcopenshell.api.run("feature.add_feature", model, feature=opening_obj, element=roof_obj)
                ifcopenshell.api.run("feature.add_filling", model, opening=opening_obj, element=door_obj)

                if st_id in storey_products:
                    storey_products[st_id].append(door_obj)

            elif isinstance(child, ResolvedWindow):
                win_obj = ifcopenshell.api.run(
                    "root.create_entity", model, ifc_class="IfcWindow", name=child.tag
                )
                win_obj.OverallHeight = float(child.height)
                win_obj.OverallWidth = float(child.width)

                opening_obj = ifcopenshell.api.run(
                    "root.create_entity",
                    model,
                    ifc_class="IfcOpeningElement",
                    name=f"{child.tag}_Opening",
                )
                ifcopenshell.api.run("feature.add_feature", model, feature=opening_obj, element=roof_obj)
                ifcopenshell.api.run("feature.add_filling", model, opening=opening_obj, element=win_obj)

                if st_id in storey_products:
                    storey_products[st_id].append(win_obj)

    def _add_ifcopenshell_terminal_geometry(product_obj: Any, position: Tuple[float, float, float], rotation: float, dimensions: Tuple[float, float, float]):
        px, py, pz = position
        rz = float(rotation) if rotation else 0.0
        mat = _build_transform_matrix((px, py, pz), (0.0, 0.0, rz))
        ifcopenshell.api.run("geometry.edit_object_placement", model, product=product_obj, matrix=mat)

        w, d, h = dimensions
        w_val = float(w) if w and float(w) > 0 else 0.30
        d_val = float(d) if d and float(d) > 0 else 0.30
        h_val = float(h) if h and float(h) > 0 else 0.30

        profile = model.createIfcRectangleProfileDef(
            "AREA", None, model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0))), w_val, d_val
        )
        solid = model.createIfcExtrudedAreaSolid(
            profile,
            model.createIfcAxis2Placement3D(
                model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                model.createIfcDirection((0.0, 0.0, 1.0)),
                model.createIfcDirection((1.0, 0.0, 0.0)),
            ),
            model.createIfcDirection((0.0, 0.0, 1.0)),
            h_val,
        )
        rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run("geometry.assign_representation", model, product=product_obj, representation=rep)

    def _add_ifcopenshell_flow_segment_geometry(product_obj: Any, waypoints: List[Tuple[float, float, float]], radius: float):
        if not waypoints:
            waypoints = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        start_pt = waypoints[0]
        mat = _build_transform_matrix(start_pt, (0.0, 0.0, 0.0))
        ifcopenshell.api.run("geometry.edit_object_placement", model, product=product_obj, matrix=mat)

        pt_objs = [model.createIfcCartesianPoint((float(p[0]), float(p[1]), float(p[2]))) for p in waypoints]
        polyline = model.createIfcPolyline(pt_objs)
        r = float(radius) if radius and float(radius) > 0 else 0.05
        solid = model.createIfcSweptDiskSolid(polyline, r, None, None, None)
        rep = model.createIfcShapeRepresentation(body_context, "Body", "SweptSolid", [solid])
        ifcopenshell.api.run("geometry.assign_representation", model, product=product_obj, representation=rep)

    # 7. MEP Elements (Pipes, Conduits, Terminals, Electrical, HVAC)
    for pipe in resolved.pipes:
        pipe_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcPipeSegment",
            name=pipe.tag,
        )
        ifcopenshell_elem_objs[pipe.tag] = pipe_obj
        wpts = pipe.waypoints or [pipe.start_point, pipe.end_point]
        rad = (pipe.nominal_diameter or 0.05) / 2.0
        _add_ifcopenshell_flow_segment_geometry(pipe_obj, wpts, rad)
        st_id = pipe.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(pipe_obj)

    for conduit in resolved.conduits:
        conduit_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcCableCarrierSegment",
            name=conduit.tag,
        )
        ifcopenshell_elem_objs[conduit.tag] = conduit_obj
        wpts = conduit.waypoints or [conduit.start_point, conduit.end_point]
        rad = (conduit.nominal_diameter or 0.05) / 2.0
        _add_ifcopenshell_flow_segment_geometry(conduit_obj, wpts, rad)
        st_id = conduit.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(conduit_obj)

    for duct in resolved.ducts:
        duct_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcDuctSegment",
            name=duct.tag,
        )
        ifcopenshell_elem_objs[duct.tag] = duct_obj
        wpts = getattr(duct, "waypoints", None) or [getattr(duct, "start_point", (0.0, 0.0, 0.0)), getattr(duct, "end_point", (1.0, 0.0, 0.0))]
        rad = getattr(duct, "width", 0.25) / 2.0
        _add_ifcopenshell_flow_segment_geometry(duct_obj, wpts, rad)
        st_id = duct.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(duct_obj)

    for term in resolved.sanitary_terminals:
        term_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcSanitaryTerminal",
            name=term.tag,
            predefined_type=term.predefined_type or "USERDEFINED",
        )
        ifcopenshell_elem_objs[term.tag] = term_obj
        _add_ifcopenshell_terminal_geometry(
            term_obj, term.position, getattr(term, "rotation_angle", 0.0),
            (getattr(term, "width", 0.5), getattr(term, "depth", 0.5), getattr(term, "height", 0.8))
        )
        st_id = term.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(term_obj)

    for term in getattr(resolved, "waste_terminals", []):
        term_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcWasteTerminal",
            name=term.tag,
            predefined_type=term.predefined_type or "USERDEFINED",
        )
        ifcopenshell_elem_objs[term.tag] = term_obj
        _add_ifcopenshell_terminal_geometry(
            term_obj, term.position, getattr(term, "rotation_angle", 0.0),
            (getattr(term, "width", 0.4), getattr(term, "depth", 0.4), getattr(term, "height", 0.4))
        )
        st_id = term.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(term_obj)

    for board in resolved.distribution_boards:
        board_cls = "IfcElectricDistributionBoard" if getattr(board.element, "class_", "") == "IfcElectricDistributionBoard" else "IfcDistributionBoard"
        ptype = getattr(board, "predefined_type", "CONSUMERUNIT")
        board_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class=board_cls,
            name=board.tag,
            predefined_type=ptype,
        )
        ifcopenshell_elem_objs[board.tag] = board_obj
        _add_ifcopenshell_terminal_geometry(
            board_obj, board.position, getattr(board, "rotation_angle", 0.0),
            (getattr(board, "width", 0.4), getattr(board, "depth", 0.2), getattr(board, "height", 0.6))
        )
        st_id = board.element.placement.storey
        if not st_id and getattr(board.element.placement, "wall", None):
            for w in resolved.walls:
                if w.tag == board.element.placement.wall:
                    st_id = w.element.placement.storey
                    break
        if st_id and st_id in storey_products:
            storey_products[st_id].append(board_obj)

    for light in resolved.light_fixtures:
        ptype = getattr(light, "predefined_type", "POINTSOURCE")
        light_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcLightFixture",
            name=light.tag,
            predefined_type=ptype,
        )
        ifcopenshell_elem_objs[light.tag] = light_obj
        _add_ifcopenshell_terminal_geometry(
            light_obj, light.position, getattr(light, "rotation_angle", 0.0),
            (getattr(light, "width", 0.3), getattr(light, "depth", 0.3), getattr(light, "height", 0.1))
        )
        st_id = light.element.placement.storey
        if not st_id and getattr(light.element.placement, "wall", None):
            for w in resolved.walls:
                if w.tag == light.element.placement.wall:
                    st_id = w.element.placement.storey
                    break
        if st_id and st_id in storey_products:
            storey_products[st_id].append(light_obj)

    for sw in resolved.switches:
        sw_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcSwitchingDevice",
            name=sw.tag,
        )
        ifcopenshell_elem_objs[sw.tag] = sw_obj
        _add_ifcopenshell_terminal_geometry(
            sw_obj, sw.position, getattr(sw, "rotation_angle", 0.0),
            (getattr(sw, "width", 0.1), getattr(sw, "depth", 0.05), getattr(sw, "height", 0.1))
        )
        st_id = sw.element.placement.storey
        if not st_id and getattr(sw.element.placement, "wall", None):
            for w in resolved.walls:
                if w.tag == sw.element.placement.wall:
                    st_id = w.element.placement.storey
                    break
        if st_id and st_id in storey_products:
            storey_products[st_id].append(sw_obj)

    for out in resolved.outlets:
        ptype = getattr(out, "predefined_type", "POWEROUTLET")
        out_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcOutlet",
            name=out.tag,
            predefined_type=ptype,
        )
        ifcopenshell_elem_objs[out.tag] = out_obj
        _add_ifcopenshell_terminal_geometry(
            out_obj, out.position, getattr(out, "rotation_angle", 0.0),
            (getattr(out, "width", 0.1), getattr(out, "depth", 0.05), getattr(out, "height", 0.1))
        )
        st_id = out.element.placement.storey
        if not st_id and getattr(out.element.placement, "wall", None):
            for w in resolved.walls:
                if w.tag == out.element.placement.wall:
                    st_id = w.element.placement.storey
                    break
        if st_id and st_id in storey_products:
            storey_products[st_id].append(out_obj)

    for air in resolved.air_terminals:
        ptype = getattr(air, "predefined_type", "DIFFUSER")
        air_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcAirTerminal",
            name=air.tag,
            predefined_type=ptype,
        )
        ifcopenshell_elem_objs[air.tag] = air_obj
        _add_ifcopenshell_terminal_geometry(
            air_obj, air.position, getattr(air, "rotation_angle", 0.0),
            (getattr(air, "width", 0.4), getattr(air, "depth", 0.4), getattr(air, "height", 0.2))
        )
        st_id = air.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(air_obj)

    for damper in resolved.dampers:
        ptype = getattr(damper, "predefined_type", "FIREDAMPER")
        damper_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcDamper",
            name=damper.tag,
            predefined_type=ptype,
        )
        ifcopenshell_elem_objs[damper.tag] = damper_obj
        _add_ifcopenshell_terminal_geometry(
            damper_obj, damper.position, getattr(damper, "rotation_angle", 0.0),
            (
                getattr(damper, "duct_width", getattr(damper, "width", 0.3)),
                getattr(damper, "duct_depth", getattr(damper, "depth", 0.3)),
                getattr(damper, "height", 0.3)
            )
        )
        st_id = damper.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(damper_obj)

    for controller in resolved.flow_controllers:
        controller_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcFlowController",
            name=controller.tag,
        )
        ifcopenshell_elem_objs[controller.tag] = controller_obj
        if controller.predefined_type:
            controller_obj.ObjectType = controller.predefined_type
        _add_ifcopenshell_terminal_geometry(
            controller_obj, controller.position, getattr(controller, "rotation_angle", 0.0),
            (
                getattr(controller, "duct_width", getattr(controller, "width", 0.4)),
                getattr(controller, "duct_depth", getattr(controller, "depth", 0.3)),
                getattr(controller, "height", 0.3)
            )
        )
        st_id = controller.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(controller_obj)

    for eq in resolved.unitary_equipments:
        eq_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcUnitaryEquipment",
            name=eq.tag,
        )
        ifcopenshell_elem_objs[eq.tag] = eq_obj
        _add_ifcopenshell_terminal_geometry(
            eq_obj, eq.position, getattr(eq, "rotation_angle", 0.0),
            (getattr(eq, "width", 0.8), getattr(eq, "depth", 0.4), getattr(eq, "height", 0.6))
        )
        st_id = eq.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(eq_obj)

    # Universal Proxies in ifcopenshell
    for proxy in resolved.proxies:
        ifc_cls = proxy.ifc_class or "IfcBuildingElementProxy"
        try:
            proxy_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class=ifc_cls,
                name=proxy.tag,
            )
        except Exception:
            proxy_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBuildingElementProxy",
                name=proxy.tag,
            )
            proxy_obj.ObjectType = ifc_cls

        if proxy.predefined_type:
            try:
                proxy_obj.PredefinedType = proxy.predefined_type.upper()
            except Exception:
                proxy_obj.ObjectType = proxy.predefined_type

        ifcopenshell_elem_objs[proxy.tag] = proxy_obj
        st_id = proxy.element.placement.storey
        if st_id and st_id in storey_products:
            storey_products[st_id].append(proxy_obj)

        if st_id and st_id in storey_objs:
            ifcopenshell.api.run(
                "spatial.assign_container",
                model,
                products=[proxy_obj],
                relating_structure=storey_objs[st_id],
            )

        px, py, pz = proxy.position
        rx, ry, rz = proxy.rotation
        mat = _build_transform_matrix((px, py, pz), (rx, ry, rz))
        ifcopenshell.api.run(
            "geometry.edit_object_placement",
            model,
            product=proxy_obj,
            matrix=mat,
        )

        w, d, h = proxy.dimensions
        profile = model.createIfcRectangleProfileDef(
            "AREA",
            None,
            model.createIfcAxis2Placement2D(
                model.createIfcCartesianPoint((0.0, 0.0))
            ),
            float(w),
            float(d),
        )
        solid = model.createIfcExtrudedAreaSolid(
            profile,
            model.createIfcAxis2Placement3D(
                model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                model.createIfcDirection((0.0, 0.0, 1.0)),
                model.createIfcDirection((1.0, 0.0, 0.0)),
            ),
            model.createIfcDirection((0.0, 0.0, 1.0)),
            float(h),
        )
        rep = model.createIfcShapeRepresentation(
            body_context, "Body", "SweptSolid", [solid]
        )
        ifcopenshell.api.run(
            "geometry.assign_representation",
            model,
            product=proxy_obj,
            representation=rep,
        )

        # Automatically bind default bSDD Psets + custom properties
        bind_default_psets_ifcopenshell(model, proxy_obj, ifc_cls, proxy.properties)

    # Assign containment
    for st_id, products in storey_products.items():
        if products and st_id in storey_objs:
            spatial_prods = []
            aggregate_prods = []
            for p in products:
                if p.is_a("IfcFacility") or p.is_a("IfcFacilityPart"):
                    aggregate_prods.append(p)
                else:
                    spatial_prods.append(p)

            if spatial_prods:
                ifcopenshell.api.run(
                    "spatial.assign_container",
                    model,
                    products=spatial_prods,
                    relating_structure=storey_objs[st_id],
                )
            if aggregate_prods:
                ifcopenshell.api.run(
                    "aggregate.assign_object",
                    model,
                    products=aggregate_prods,
                    relating_object=storey_objs[st_id],
                )


    # 8. Topological Ports & Connections
    ifcopenshell_port_objs: Dict[str, ifcopenshell.entity_instance] = {}
    ifcopenshell_elem_objs: Dict[str, ifcopenshell.entity_instance] = {}

    for st_prods in storey_products.values():
        for prod in st_prods:
            if hasattr(prod, "Name") and prod.Name:
                ifcopenshell_elem_objs[prod.Name] = prod

    for port in getattr(resolved, "resolved_ports", []) or []:
        f_dir = port.flow_direction.upper() if port.flow_direction else "SOURCEANDSINK"
        port_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcDistributionPort",
            name=port.port_id,
        )
        port_obj.FlowDirection = f_dir
        ifcopenshell_port_objs[port.global_port_id] = port_obj

        host_obj = ifcopenshell_elem_objs.get(port.host_tag)
        if host_obj:
            model.create_entity(
                "IfcRelConnectsPortToElement",
                GlobalId=generate_ifc_guid(),
                RelatingPort=port_obj,
                RelatedElement=host_obj,
            )

    if getattr(resolved, "topology_graph", None):
        for p1_id, p2_id in resolved.topology_graph.connected_edges:
            p1_obj = ifcopenshell_port_objs.get(p1_id)
            p2_obj = ifcopenshell_port_objs.get(p2_id)
            if p1_obj and p2_obj:
                model.create_entity(
                    "IfcRelConnectsPorts",
                    GlobalId=generate_ifc_guid(),
                    RelatingPort=p1_obj,
                    RelatedPort=p2_obj,
                )

    # 9. Systems Containment (IfcDistributionSystem & IfcRelAssignsToGroup)
    systems_to_compile = []
    if hasattr(manifest, "systems") and manifest.systems:
        for sys in manifest.systems:
            systems_to_compile.append((sys.name, sys.system_type or sys.predefined_type, sys.elements))
    else:
        system_groups: Dict[str, List[str]] = {}
        for elem in getattr(resolved, "elements", []):
            stype = getattr(elem, "system_type", None) or getattr(getattr(elem, "element", None), "system_type", None)
            if stype:
                system_groups.setdefault(str(stype), []).append(elem.tag)
        for s_name, tags in system_groups.items():
            systems_to_compile.append((s_name, s_name, tags))

    for sys_name, sys_type, elem_tags in systems_to_compile:
        try:
            sys_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcDistributionSystem",
                name=sys_name,
            )
            if sys_type:
                try:
                    sys_obj.PredefinedType = str(sys_type).upper()
                except Exception:
                    sys_obj.ObjectType = str(sys_type)

            rel_objs = [ifcopenshell_elem_objs[t] for t in elem_tags if t in ifcopenshell_elem_objs]
            if rel_objs:
                ifcopenshell.api.run(
                    "group.assign_group",
                    model,
                    products=rel_objs,
                    group=sys_obj,
                )
        except Exception as e:
            logger.warning(f"Failed to create IfcDistributionSystem {sys_name}: {e}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    model.write(str(output_path))
    return output_path


def compile_to_ifc(
    manifest: Union[ProjectManifest, ResolvedManifest, Path, str],
    output_path: Union[Path, str] = "dist/model.ifc",
    force_fallback: bool = False,
) -> Path:
    """
    Compiles a ProjectManifest or ResolvedManifest into an IFC4 STEP physical file.
    Uses ifcopenshell if installed and force_fallback is False, otherwise falls back
    to StepSerializer.
    """
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    # Load / resolve manifest
    if isinstance(manifest, (str, Path)):
        manifest_obj = load_manifest(manifest)
        resolved = resolve_manifest(manifest_obj)
    elif isinstance(manifest, ProjectManifest):
        resolved = resolve_manifest(manifest)
    elif isinstance(manifest, ResolvedManifest):
        resolved = manifest
    else:
        raise TypeError(f"Invalid manifest type: {type(manifest)}")

    if not force_fallback:
        try:
            return _compile_with_ifcopenshell(resolved, out_p)
        except Exception:
            # Fall back if ifcopenshell compilation fails
            pass

    serializer = StepSerializer()
    step_content = serializer.serialize(resolved)
    with open(out_p, "w", encoding="utf-8") as f:
        f.write(step_content)

    return out_p
