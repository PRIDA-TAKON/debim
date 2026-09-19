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
    ResolvedTerminal,
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
                if st_id in storey_elements:
                    storey_elements[st_id].append(p_ref)

        # 6. MEP Terminals
        for term in resolved.terminals:
            st_id = term.element.placement.storey or (
                term.hosting_wall.element.placement.storey if term.hosting_wall else None
            )
            ifc_cls = term.element.class_
            elem_ref = self.create_entity(
                ifc_cls,
                generate_ifc_guid(),
                None,
                term.tag,
                None,
                None,
                None,
                None,
                None,
            )
            if st_id and st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

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
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        # 4. Stairs
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

        # 6. Roofs
        for roof in resolved.roofs:
            st_id = roof.element.placement.storey
            elem_ref = self.create_entity(
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
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

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
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for board in resolved.distribution_boards:
            st_id = board.element.placement.storey
            elem_ref = self.create_entity(
                "IfcDistributionBoard",
                generate_ifc_guid(),
                None,
                board.tag,
                None,
                None,
                None,
                None,
                None,
            )
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for light in resolved.light_fixtures:
            st_id = light.element.placement.storey
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
            )
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for sw in resolved.switches:
            st_id = sw.element.placement.storey
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
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for out in resolved.outlets:
            st_id = out.element.placement.storey
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
            )
            if st_id in storey_elements:
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
            if st_id in storey_elements:
                storey_elements[st_id].append(elem_ref)

        for air in resolved.air_terminals:
            st_id = air.element.placement.storey
            elem_ref = self.create_entity(
                "IfcAirTerminal",
                generate_ifc_guid(),
                None,
                air.tag,
                None,
                None,
                None,
                None,
                None,
            )
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

    # 0. Footings & Piles
    for footing in resolved.footings:
        footing_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcFooting", name=footing.tag
        )
        st_id = footing.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(footing_obj)

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

    # 2. Beams
    for beam in resolved.beams:
        beam_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcBeam", name=beam.tag
        )
        st_id = beam.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(beam_obj)

    # 3. Slabs
    for slab in resolved.slabs:
        slab_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcSlab", name=slab.tag
        )
        st_id = slab.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(slab_obj)

    # 4. Stairs
    for stair in resolved.stairs:
        stair_obj = ifcopenshell.api.run(
            "root.create_entity", model, ifc_class="IfcStair", name=stair.tag
        )
        st_id = stair.element.placement.from_storey
        if st_id in storey_products:
            storey_products[st_id].append(stair_obj)

    # 5. Walls & Children
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

    # 6. Roofs
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
        )
        st_id = term.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(term_obj)

    for board in resolved.distribution_boards:
        board_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcDistributionBoard",
            name=board.tag,
        )
        st_id = board.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(board_obj)

    for light in resolved.light_fixtures:
        light_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcLightFixture",
            name=light.tag,
        )
        st_id = light.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(light_obj)

    for sw in resolved.switches:
        sw_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcSwitchingDevice",
            name=sw.tag,
        )
        st_id = sw.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(sw_obj)

    for out in resolved.outlets:
        out_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcOutlet",
            name=out.tag,
        )
        st_id = out.element.placement.storey
        if st_id in storey_products:
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
        air_obj = ifcopenshell.api.run(
            "root.create_entity",
            model,
            ifc_class="IfcAirTerminal",
            name=air.tag,
        )
        st_id = air.element.placement.storey
        if st_id in storey_products:
            storey_products[st_id].append(air_obj)

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
