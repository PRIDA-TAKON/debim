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
from debim.schema import ProjectManifest, RevolvedAreaSolid, SweptDiskSolid, load_manifest


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
    if "terminal" in l or "air_terminal" in l:
        return "IfcAirTerminal"
    if "fitting" in l:
        return "IfcFlowFitting"
    if "valve" in l:
        return "IfcValve"
    if "damper" in l:
        return "IfcDamper"
    if "flow_controller" in l or "flowcontroller" in l or "flow_control" in l:
        return "IfcFlowController"
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

        # 6. MEP Terminals
        for term in resolved.terminals:
            st_id = term.element.placement.storey or (
                term.hosting_wall.element.placement.storey if term.hosting_wall else None
            )
            ifc_cls = term.element.class_
            raw_pred_type = getattr(term, "predefined_type", None) or getattr(term.element, "predefined_type", None)
            pred_type = f".{raw_pred_type.upper()}." if raw_pred_type else None
            elem_ref = self.create_entity(
                ifc_cls,
                generate_ifc_guid(),
                None,
                term.tag,
                None,
                None,
                None,
                None,
                pred_type,
            )
            element_tag_refs[term.tag] = elem_ref
            if st_id and st_id in storey_elements:
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
            ext_dir = self.create_entity("IfcDirection", (1.0, 0.0, 0.0))
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
            b_depth = getattr(prof, "depth", getattr(prof, "overall_depth", 0.3))
            rel_z = float(pz - st_elev - b_depth / 2.0)

            elem_pt = self.create_entity("IfcCartesianPoint", (float(px), float(py), rel_z))
            dx, dy, dz = beam.direction_vector_3d
            ref_dir = self.create_entity("IfcDirection", (round(dx, 6), round(dy, 6), round(dz, 6)))
            elem_axis = self.create_entity("IfcAxis2Placement3D", elem_pt, None, ref_dir)
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
            elem_ref = self.create_entity(
                "IfcCovering",
                generate_ifc_guid(),
                None,
                cov.tag,
                None,
                None,
                None,
                None,
                ptype,
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
            elem_ref = self.create_entity(
                "IfcCurtainWall",
                generate_ifc_guid(),
                None,
                cw.tag,
                None,
                None,
                None,
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
            elem_ref = self.create_entity(
                "IfcPlate",
                generate_ifc_guid(),
                None,
                plate.tag,
                None,
                None,
                None,
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

        # 7. MEP Elements (Pipes, Conduits, Terminals, Electrical)
        for pipe in resolved.pipes:
            st_id = pipe.element.placement.storey
            elem_ref = self.create_entity(
                "IfcPipeSegment",
                generate_ifc_guid(),
                None,
                pipe.tag,
                None,
                None,
                None,
                None,
                None,
            )
            element_tag_refs[pipe.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for conduit in resolved.conduits:
            st_id = conduit.element.placement.storey
            elem_ref = self.create_entity(
                "IfcCableCarrierSegment",
                generate_ifc_guid(),
                None,
                conduit.tag,
                None,
                None,
                None,
                None,
                None,
            )
            element_tag_refs[conduit.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for term in resolved.sanitary_terminals:
            st_id = term.element.placement.storey
            elem_ref = self.create_entity(
                "IfcSanitaryTerminal",
                generate_ifc_guid(),
                None,
                term.tag,
                None,
                None,
                None,
                None,
                None,
            )
            element_tag_refs[term.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for board in resolved.distribution_boards:
            st_id = board.element.placement.storey
            if not st_id and getattr(board.element.placement, "wall", None):
                for w in resolved.walls:
                    if w.tag == board.element.placement.wall:
                        st_id = w.element.placement.storey
                        break
            ifc_cls = "IfcElectricDistributionBoard" if getattr(board.element, "class_", "") == "IfcElectricDistributionBoard" else "IfcDistributionBoard"
            ptype = f".{board.predefined_type}." if board.predefined_type else ".CONSUMERUNIT."
            elem_ref = self.create_entity(
                ifc_cls,
                generate_ifc_guid(),
                None,
                board.tag,
                None,
                None,
                None,
                None,
                None,
                ptype,
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
            ptype = f".{light.predefined_type}." if light.predefined_type else ".POINTSOURCE."
            elem_ref = self.create_entity(
                "IfcLightFixture",
                generate_ifc_guid(),
                None,
                light.tag,
                None,
                None,
                None,
                None,
                None,
                ptype,
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
            elem_ref = self.create_entity(
                "IfcSwitchingDevice",
                generate_ifc_guid(),
                None,
                sw.tag,
                None,
                None,
                None,
                None,
                None,
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
            ptype = f".{out.predefined_type}." if out.predefined_type else ".POWEROUTLET."
            elem_ref = self.create_entity(
                "IfcOutlet",
                generate_ifc_guid(),
                None,
                out.tag,
                None,
                None,
                None,
                None,
                None,
                ptype,
            )
            element_tag_refs[out.tag] = elem_ref
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for duct in resolved.ducts:
            st_id = duct.element.placement.storey
            elem_ref = self.create_entity(
                "IfcDuctSegment",
                generate_ifc_guid(),
                None,
                duct.tag,
                None,
                None,
                None,
                None,
                None,
            )
            element_tag_refs[duct.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for air in resolved.air_terminals:
            st_id = air.element.placement.storey
            ptype = f".{air.predefined_type}." if air.predefined_type else ".DIFFUSER."
            elem_ref = self.create_entity(
                "IfcAirTerminal",
                generate_ifc_guid(),  # 1. GlobalId
                None,                 # 2. OwnerHistory
                air.tag,              # 3. Name
                None,                 # 4. Description
                None,                 # 5. ObjectType
                None,                 # 6. ObjectPlacement
                None,                 # 7. Representation
                None,                 # 8. Tag
                ptype,                # 9. PredefinedType
            )
            element_tag_refs[air.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for damper in resolved.dampers:
            st_id = damper.element.placement.storey
            ptype = f".{damper.predefined_type}." if damper.predefined_type else ".FIREDAMPER."
            elem_ref = self.create_entity(
                "IfcDamper",
                generate_ifc_guid(),  # 1. GlobalId
                None,                 # 2. OwnerHistory
                damper.tag,           # 3. Name
                None,                 # 4. Description
                None,                 # 5. ObjectType
                None,                 # 6. ObjectPlacement
                None,                 # 7. Representation
                None,                 # 8. Tag
                ptype,                # 9. PredefinedType
            )
            element_tag_refs[damper.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for controller in resolved.flow_controllers:
            st_id = controller.element.placement.storey
            obj_type = controller.predefined_type or "AIR_CONTROLLER"
            elem_ref = self.create_entity(
                "IfcFlowController",
                generate_ifc_guid(),
                None,
                controller.tag,
                None,
                obj_type,
                None,
                None,
                None,
            )
            element_tag_refs[controller.tag] = elem_ref
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for eq in resolved.unitary_equipments:
            st_id = eq.element.placement.storey
            elem_ref = self.create_entity(
                "IfcUnitaryEquipment",
                generate_ifc_guid(),
                None,
                eq.tag,
                None,
                None,
                None,
                None,
                None,
            )
            element_tag_refs[eq.tag] = elem_ref
            if st_id in storey_elements:
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

            std_classes = {
                "IFCBUILDINGELEMENTPROXY", "IFCCHILLER", "IFCBURNER", "IFCSOLARDEVICE",
                "IFCCOMPRESSOR", "IFCUNITARYEQUIPMENT", "IFCINTERCEPTOR", "IFCENERGYCONVERSIONDEVICE",
                "IFCENGINE", "IFCPUMP", "IFCFAN", "IFCTANK", "IFCBOILER"
            }
            target_entity = ifc_cls if ifc_cls.upper() in std_classes else "IfcBuildingElementProxy"
            obj_type = ifc_cls if target_entity == "IfcBuildingElementProxy" else None
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

            if proxy.properties:
                for pset_name, pset_props in proxy.properties.items():
                    prop_refs = []
                    for p_key, p_val in pset_props.items():
                        if isinstance(p_val, bool):
                            v_ref = self.create_entity("IfcBoolean", p_val)
                        elif isinstance(p_val, int):
                            v_ref = self.create_entity("IfcInteger", p_val)
                        elif isinstance(p_val, float):
                            v_ref = self.create_entity("IfcReal", float(p_val))
                        else:
                            v_ref = self.create_entity("IfcLabel", str(p_val))
                        psv = self.create_entity("IfcPropertySingleValue", p_key, None, v_ref, None)
                        prop_refs.append(psv)

                    pset_ref = self.create_entity(
                        "IfcPropertySet",
                        generate_ifc_guid(),
                        None,
                        pset_name,
                        None,
                        prop_refs,
                    )
                    self.create_entity(
                        "IfcRelDefinesByProperties",
                        generate_ifc_guid(),
                        None,
                        None,
                        None,
                        [proxy_ref],
                        pset_ref,
                    )

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
        x_axis = np.array([dx, dy, dz], dtype=float)
        x_norm = np.linalg.norm(x_axis)
        if x_norm > 1e-6:
            x_axis /= x_norm
        else:
            x_axis = np.array([1, 0, 0], dtype=float)

        if abs(x_axis[2]) < 0.9:
            z_axis = np.array([0, 0, 1], dtype=float)
            y_axis = np.cross(z_axis, x_axis)
            y_norm = np.linalg.norm(y_axis)
            if y_norm > 1e-6:
                y_axis /= y_norm
            else:
                y_axis = np.array([0, 1, 0], dtype=float)
            z_axis = np.cross(x_axis, y_axis)
        else:
            y_axis = np.array([0, 1, 0], dtype=float)
            z_axis = np.cross(x_axis, y_axis)
            z_norm = np.linalg.norm(z_axis)
            if z_norm > 1e-6:
                z_axis /= z_norm
            else:
                z_axis = np.array([0, 0, 1], dtype=float)
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
            product=beam_obj,
            matrix=mat,
        )

        prof = beam.element.profile
        pos2d = model.createIfcAxis2Placement2D(model.createIfcCartesianPoint((0.0, 0.0)))
        ifc_prof = _create_ifcopenshell_profile(model, prof, beam.tag, pos2d)

        solid = model.createIfcExtrudedAreaSolid(
            ifc_prof,
            model.createIfcAxis2Placement3D(
                model.createIfcCartesianPoint((0.0, 0.0, 0.0)),
                model.createIfcDirection((0.0, 0.0, 1.0)),
                model.createIfcDirection((1.0, 0.0, 0.0)),
            ),
            model.createIfcDirection((1.0, 0.0, 0.0)),
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

    # 5.3 Civil Earthworks & Retaining Walls & Civil Infrastructure (IFC4.3)
    for cut in resolved.earthworks_cuts:
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

    for bridge in resolved.bridges:
        try:
            bridge_obj = ifcopenshell.api.run(
                "root.create_entity",
                model,
                ifc_class="IfcBridge",
                name=bridge.tag,
            )
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

    # 7. MEP Elements (Pipes, Conduits, Terminals, Electrical)
    for pipe in resolved.pipes:
        pipe_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcPipeSegment",
            name=pipe.tag,
        )
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
        st_id = conduit.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(conduit_obj)

    for term in resolved.sanitary_terminals:
        term_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcSanitaryTerminal",
            name=term.tag,
            predefined_type=term.predefined_type or "USERDEFINED",
        )
        st_id = term.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(term_obj)

    for term in resolved.waste_terminals:
        term_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcWasteTerminal",
            name=term.tag,
            predefined_type=term.predefined_type or "USERDEFINED",
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
        st_id = out.element.placement.storey
        if not st_id and getattr(out.element.placement, "wall", None):
            for w in resolved.walls:
                if w.tag == out.element.placement.wall:
                    st_id = w.element.placement.storey
                    break
        if st_id and st_id in storey_products:
            storey_products[st_id].append(out_obj)

    for duct in resolved.ducts:
        duct_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcDuctSegment",
            name=duct.tag,
        )
        st_id = duct.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(duct_obj)

    for air in resolved.air_terminals:
        ptype = getattr(air, "predefined_type", "DIFFUSER")
        air_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcAirTerminal",
            name=air.tag,
            predefined_type=ptype,
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
        if controller.predefined_type:
            controller_obj.ObjectType = controller.predefined_type
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

        st_id = proxy.element.placement.storey
        if st_id and st_id in storey_products:
            storey_products[st_id].append(proxy_obj)

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

        # Property Sets
        if proxy.properties:
            for pset_name, pset_props in proxy.properties.items():
                try:
                    pset_obj = ifcopenshell.api.run(
                        "pset.add_pset",
                        model,
                        product=proxy_obj,
                        name=pset_name,
                    )
                    if pset_props:
                        ifcopenshell.api.run(
                            "pset.edit_pset",
                            model,
                            pset=pset_obj,
                            properties=pset_props,
                        )
                except Exception:
                    pass

    # Assign containment
    for st_id, products in storey_products.items():
        if products and st_id in storey_objs:
            ifcopenshell.api.run(
                "spatial.assign_container",
                model,
                products=products,
                relating_structure=storey_objs[st_id],
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
