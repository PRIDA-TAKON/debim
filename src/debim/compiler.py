"""
IFC4 Compiler & STEP Physical File Exporter for debim.
Compiles ProjectManifest or ResolvedManifest into standard buildingSMART IFC4 file format.
"""

import os
import uuid
import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

from debim.resolver import (
    ResolvedBeam,
    ResolvedColumn,
    ResolvedCustomElement,
    ResolvedDoor,
    ResolvedManifest,
    ResolvedWall,
    ResolvedWindow,
    resolve_manifest,
)
from debim.schema import ProjectManifest, load_manifest


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

        # IfcSite & IfcBuilding
        site_ref = self.create_entity(
            "IfcSite",
            generate_ifc_guid(),
            None,
            "Default Site",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
        bldg_ref = self.create_entity(
            "IfcBuilding",
            generate_ifc_guid(),
            None,
            project_info.name,
            None,
            None,
            None,
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
        for storey in manifest.spatial_structure.storeys:
            st_ref = self.create_entity(
                "IfcBuildingStorey",
                generate_ifc_guid(),
                None,
                storey.name,
                None,
                None,
                None,
                None,
                None,
                None,
                float(storey.elevation),
            )
            storey_refs[storey.id] = st_ref

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

        # 1. Columns
        for col in resolved.columns:
            st_id = col.element.placement.base_storey
            elem_ref = self.create_entity(
                "IfcColumn",
                generate_ifc_guid(),
                None,
                col.tag,
                None,
                None,
                None,
                None,
                None,
            )
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        # 2. Beams
        for beam in resolved.beams:
            st_id = beam.element.placement.storey
            elem_ref = self.create_entity(
                "IfcBeam",
                generate_ifc_guid(),
                None,
                beam.tag,
                None,
                None,
                None,
                None,
                None,
            )
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        # 3. Walls & Child Openings / Doors / Windows
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
                        float(child.height),
                        float(child.width),
                    )
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
                        float(child.height),
                        float(child.width),
                    )
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
            elem_ref = self.create_entity(
                "IfcBuildingElementProxy",
                generate_ifc_guid(),
                None,
                custom.tag,
                None,
                None,
                None,
                None,
                None,
            )
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

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

        footer = ["ENDSEC;", "END-ISO-10303-21;"]
        return "\n".join(header + self.lines + footer) + "\n"


def _compile_with_ifcopenshell(resolved: ResolvedManifest, output_path: Path) -> Path:
    """Compile model using ifcopenshell library."""
    import ifcopenshell
    import ifcopenshell.api

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

    # Site & Building
    site = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcSite", name="Default Site"
    )
    building = ifcopenshell.api.run(
        "root.create_entity", model, ifc_class="IfcBuilding", name=project_info.name
    )

    ifcopenshell.api.run("aggregate.assign_object", model, products=[site], relating_object=project)
    ifcopenshell.api.run("aggregate.assign_object", model, products=[building], relating_object=site)

    # Building Storeys
    storey_objs: Dict[str, ifcopenshell.entity_instance] = {}
    for storey in manifest.spatial_structure.storeys:
        st_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcBuildingStorey", name=storey.name
        )
        st_obj.Elevation = float(storey.elevation)
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

    # 1. Columns
    for col in resolved.columns:
        col_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcColumn", name=col.tag
        )
        st_id = col.element.placement.base_storey
        if st_id in storey_products:
            storey_products[st_id].append(col_obj)

    # 2. Beams
    for beam in resolved.beams:
        beam_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcBeam", name=beam.tag
        )
        st_id = beam.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(beam_obj)

    # 3. Walls & Children
    for wall in resolved.walls:
        wall_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcWall", name=wall.tag
        )
        st_id = wall.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(wall_obj)

        for child in wall.children:
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

                opening_obj = ifcopenshell.api.run(
                    "root.create_entity",
                    model,
                    ifc_class="IfcOpeningElement",
                    name=f"{child.tag}_Opening",
                )
                ifcopenshell.api.run("feature.add_feature", model, feature=opening_obj, element=wall_obj)
                ifcopenshell.api.run("feature.add_filling", model, opening=opening_obj, element=win_obj)

                if st_id in storey_products:
                    storey_products[st_id].append(win_obj)

    # 4. Custom Elements
    for custom in resolved.custom_elements:
        custom_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcBuildingElementProxy",
            name=custom.tag,
        )
        st_id = custom.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(custom_obj)

    # Assign containment
    for st_id, products in storey_products.items():
        if products and st_id in storey_objs:
            ifcopenshell.api.run(
                "spatial.assign_container",
                model,
                products=products,
                relating_structure=storey_objs[st_id],
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
