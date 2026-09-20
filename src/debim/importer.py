"""
IFC Importer for debim.
Parses buildingSMART IFC4 / IFC2X3 files via IfcOpenShell
and converts them into declarative ProjectManifest (project.yaml) for QTO & Cost estimation.
"""

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union
import yaml

from debim.schema import (
    BoxProfile,
    ColumnPlacement,
    ColumnReinforcement,
    BeamPlacement,
    BeamReinforcement,
    Dimensions,
    IfcBeam,
    IfcColumn,
    IfcCustomElement,
    CustomElementPlacement,
    IfcDoor,
    IfcSlab,
    IfcWall,
    IfcWindow,
    WallPlacement,
    SlabPlacement,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    Grids,
    Units,
)


def import_ifc_to_manifest(
    ifc_path: Union[str, Path],
    project_name: Optional[str] = None,
) -> ProjectManifest:
    """
    Import an IFC file and convert it into a declarative ProjectManifest object.
    Supports IFC2X3 and IFC4 with columns, beams, walls, slabs, and footings.
    """
    import ifcopenshell
    import ifcopenshell.util.element
    import ifcopenshell.util.placement

    ifc_file = ifcopenshell.open(str(ifc_path))

    # 1. Project Info
    proj_entities = ifc_file.by_type("IfcProject")
    p_name = project_name or (proj_entities[0].Name if proj_entities else "Imported IFC Project")
    p_id = proj_entities[0].GlobalId if proj_entities else "PRJ-IMPORTED"

    # 2. Storeys
    storey_entities = ifc_file.by_type("IfcBuildingStorey")
    storeys: List[Storey] = []
    storey_id_by_name: Dict[str, str] = {}
    if storey_entities:
        for idx, s in enumerate(storey_entities):
            s_name = s.Name or f"Storey_{idx + 1}"
            s_id = s.Name or f"S_{idx + 1}"
            elev = float(s.Elevation) if s.Elevation is not None else 0.0
            if elev > 500:  # mm to m
                elev /= 1000.0
            storeys.append(
                Storey(
                    id=s_id,
                    name=s_name,
                    elevation=round(elev, 3),
                    height=3.5,
                )
            )
            storey_id_by_name[s_name] = s_id
    else:
        storeys.append(Storey(id="GL", name="Ground Floor", elevation=0.0, height=3.5))
        storey_id_by_name["Ground Floor"] = "GL"

    def get_elem_storey(elem) -> str:
        try:
            container = ifcopenshell.util.element.get_container(elem)
            if container and container.Name and container.Name in storey_id_by_name:
                return storey_id_by_name[container.Name]
        except Exception:
            pass
        return storeys[0].id

    # 3. Grids mapping & clustering
    grid_x_vals: Dict[str, float] = {}
    grid_y_vals: Dict[str, float] = {}

    def get_or_create_grid_x(val: float) -> str:
        val = round(float(val), 2)
        for k, v in grid_x_vals.items():
            if abs(v - val) < 0.05:
                return k
        tag = f"GX_{len(grid_x_vals) + 1}"
        grid_x_vals[tag] = val
        return tag

    def get_or_create_grid_y(val: float) -> str:
        val = round(float(val), 2)
        for k, v in grid_y_vals.items():
            if abs(v - val) < 0.05:
                return k
        tag = f"GY_{len(grid_y_vals) + 1}"
        grid_y_vals[tag] = val
        return tag

    # 4. Material registry helper
    materials_dict: Dict[str, Material] = {
        "CONC_280": Material(
            id="CONC_280",
            name="Structural Concrete 280 ksc",
            category="concrete",
            unit_cost_ref="MAT-CONC-01",
        ),
        "STEEL_STRUCT": Material(
            id="STEEL_STRUCT",
            name="Structural Steel",
            category="steel",
            unit_cost_ref="MAT-STEEL-DB16",
        ),
    }

    def resolve_material(elem, default_id: str = "CONC_280") -> str:
        try:
            mat = ifcopenshell.util.element.get_material(elem)
            mat_name = None
            if mat:
                if hasattr(mat, "Name") and mat.Name:
                    mat_name = str(mat.Name)
                elif mat.is_a("IfcMaterialLayerSetUsage"):
                    layers = mat.ForLayerSet.MaterialLayers
                    if layers and layers[0].Material and layers[0].Material.Name:
                        mat_name = str(layers[0].Material.Name)
                elif mat.is_a("IfcMaterialLayerSet"):
                    layers = mat.MaterialLayers
                    if layers and layers[0].Material and layers[0].Material.Name:
                        mat_name = str(layers[0].Material.Name)

            tag_str = getattr(elem, "Name", "") or ""
            combined_str = f"{mat_name or ''} {tag_str}".upper()

            if mat_name or tag_str:
                clean_id = re.sub(r"[^A-Za-z0-9_]", "_", (mat_name or tag_str).strip()).upper()[:24]
                if clean_id not in materials_dict:
                    if any(k in combined_str for k in ["TIMBER", "WOOD", "LUMBER", "PLYWOOD"]):
                        cat = "timber"
                        cost_ref = "MAT-TIMBER-01"
                    elif any(k in combined_str for k in ["STEEL", "METAL", "SS400", "SM490", "WIDE", "W-"]) or re.search(r"\b(W|H|2L|UB|UC)\d", combined_str):
                        cat = "steel"
                        cost_ref = "MAT-STEEL-STRUCT"
                    elif "CONC" in combined_str:
                        cat = "concrete"
                        cost_ref = "MAT-CONC-01"
                    else:
                        cat = "masonry"
                        cost_ref = "MAT-BRICK-01"

                    materials_dict[clean_id] = Material(
                        id=clean_id,
                        name=mat_name or tag_str,
                        category=cat,
                        unit_cost_ref=cost_ref,
                    )
                return clean_id
        except Exception:
            pass
        return default_id

    # 5. Elements extraction
    elements: List[Any] = []

    # Build wall children map (IfcDoor and IfcWindow openings)
    wall_children_map: Dict[str, List[Union[IfcDoor, IfcWindow]]] = {}

    for door in ifc_file.by_type("IfcDoor"):
        parent_wall_id = None
        parent_wall_elem = None
        try:
            for rel in getattr(door, "FillsVoids", []):
                opening = rel.RelatingOpeningElement
                for vrel in getattr(opening, "VoidsElements", []):
                    parent_wall_elem = vrel.RelatingBuildingElement
                    parent_wall_id = parent_wall_elem.GlobalId
                    break
                if parent_wall_id:
                    break
        except Exception:
            pass

        w = 0.90
        if getattr(door, "OverallWidth", None):
            w = float(door.OverallWidth)
            if w > 10:
                w /= 1000.0
        else:
            ps = ifcopenshell.util.element.get_psets(door)
            dims = ps.get("PSet_Revit_Dimensions", {}) or ps.get("Dimensions", {})
            if dims.get("Width"):
                w = float(dims["Width"])
                if w > 10:
                    w /= 1000.0

        h = 2.00
        if getattr(door, "OverallHeight", None):
            h = float(door.OverallHeight)
            if h > 10:
                h /= 1000.0
        else:
            ps = ifcopenshell.util.element.get_psets(door)
            dims = ps.get("PSet_Revit_Dimensions", {}) or ps.get("Dimensions", {})
            if dims.get("Height"):
                h = float(dims["Height"])
                if h > 10:
                    h /= 1000.0

        offset = 1.0
        if parent_wall_elem:
            try:
                d_mat = ifcopenshell.util.placement.get_local_placement(door.ObjectPlacement)
                w_mat = ifcopenshell.util.placement.get_local_placement(parent_wall_elem.ObjectPlacement)
                dx = float(d_mat[0, 3] - w_mat[0, 3])
                dy = float(d_mat[1, 3] - w_mat[1, 3])
                w_dir = w_mat[:2, 0]
                offset = float(dx * w_dir[0] + dy * w_dir[1])
                if offset < 0:
                    offset = abs(offset)
            except Exception:
                offset = 1.0

        d_obj = IfcDoor(
            class_="IfcDoor",
            tag=door.Name or f"DOOR-{door.GlobalId[:8]}",
            dimensions=Dimensions(width=round(w, 3), height=round(h, 3)),
            offset_distance=round(offset, 2),
        )
        if parent_wall_id:
            wall_children_map.setdefault(parent_wall_id, []).append(d_obj)

    for window in ifc_file.by_type("IfcWindow"):
        parent_wall_id = None
        parent_wall_elem = None
        try:
            for rel in getattr(window, "FillsVoids", []):
                opening = rel.RelatingOpeningElement
                for vrel in getattr(opening, "VoidsElements", []):
                    parent_wall_elem = vrel.RelatingBuildingElement
                    parent_wall_id = parent_wall_elem.GlobalId
                    break
                if parent_wall_id:
                    break
        except Exception:
            pass

        w = 1.20
        if getattr(window, "OverallWidth", None):
            w = float(window.OverallWidth)
            if w > 10:
                w /= 1000.0
        else:
            ps = ifcopenshell.util.element.get_psets(window)
            dims = ps.get("PSet_Revit_Dimensions", {}) or ps.get("Dimensions", {})
            if dims.get("Width"):
                w = float(dims["Width"])
                if w > 10:
                    w /= 1000.0

        h = 1.50
        if getattr(window, "OverallHeight", None):
            h = float(window.OverallHeight)
            if h > 10:
                h /= 1000.0
        else:
            ps = ifcopenshell.util.element.get_psets(window)
            dims = ps.get("PSet_Revit_Dimensions", {}) or ps.get("Dimensions", {})
            if dims.get("Height"):
                h = float(dims["Height"])
                if h > 10:
                    h /= 1000.0

        offset = 1.0
        if parent_wall_elem:
            try:
                win_mat = ifcopenshell.util.placement.get_local_placement(window.ObjectPlacement)
                w_mat = ifcopenshell.util.placement.get_local_placement(parent_wall_elem.ObjectPlacement)
                dx = float(win_mat[0, 3] - w_mat[0, 3])
                dy = float(win_mat[1, 3] - w_mat[1, 3])
                w_dir = w_mat[:2, 0]
                offset = float(dx * w_dir[0] + dy * w_dir[1])
                if offset < 0:
                    offset = abs(offset)
            except Exception:
                offset = 1.0

        win_obj = IfcWindow(
            class_="IfcWindow",
            tag=window.Name or f"WIN-{window.GlobalId[:8]}",
            dimensions=Dimensions(width=round(w, 3), height=round(h, 3)),
            offset_distance=round(offset, 2),
            sill_height=0.80,
        )
        if parent_wall_id:
            wall_children_map.setdefault(parent_wall_id, []).append(win_obj)

    # 5.1 Extract Columns
    for col in ifc_file.by_type("IfcColumn"):
        tag = col.Name or f"COL-{col.GlobalId[:8]}"
        w, d = 0.3, 0.3

        ps = ifcopenshell.util.element.get_psets(col)
        dims = ps.get("Dimensions", {}) or ps.get("PSet_Revit_Dimensions", {}) or ps.get("Qto_ColumnBaseQuantities", {})
        if "Width" in dims and dims["Width"]:
            w = float(dims["Width"])
            if w > 10:
                w /= 1000.0
        elif "OverallWidth" in dims and dims["OverallWidth"]:
            w = float(dims["OverallWidth"])
            if w > 10:
                w /= 1000.0

        if "Depth" in dims and dims["Depth"]:
            d = float(dims["Depth"])
            if d > 10:
                d /= 1000.0
        elif "OverallDepth" in dims and dims["OverallDepth"]:
            d = float(dims["OverallDepth"])
            if d > 10:
                d /= 1000.0

        try:
            mat = ifcopenshell.util.placement.get_local_placement(col.ObjectPlacement)
            grid_tag_x = get_or_create_grid_x(mat[0, 3])
            grid_tag_y = get_or_create_grid_y(mat[1, 3])
        except Exception:
            grid_tag_x = get_or_create_grid_x(float(len(grid_x_vals) * 5.0))
            grid_tag_y = get_or_create_grid_y(float(len(grid_y_vals) * 5.0))

        st_id = get_elem_storey(col)
        mat_id = resolve_material(col, "CONC_280")
        mat_obj = materials_dict.get(mat_id)
        mat_cat = mat_obj.category if mat_obj else "concrete"

        rebar_cfg = (
            ColumnReinforcement(main="4-DB16", stirrups="RB6 @ 0.15m")
            if mat_cat == "concrete"
            else None
        )

        elements.append(
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": tag,
                    "material": mat_id,
                    "profile": BoxProfile(shape="BOX", width=round(w, 3), depth=round(d, 3)),
                    "placement": ColumnPlacement(
                        grid=(grid_tag_x, grid_tag_y),
                        base_storey=st_id,
                        top_storey=st_id,
                    ),
                    "reinforcement": rebar_cfg,
                }
            )
        )

    # 5.2 Extract Beams
    for idx, beam in enumerate(ifc_file.by_type("IfcBeam")):
        tag = beam.Name or f"BEAM-{beam.GlobalId[:8]}"
        w, d = 0.2, 0.4
        ps = ifcopenshell.util.element.get_psets(beam)
        dims = ps.get("Dimensions", {}) or ps.get("PSet_Revit_Dimensions", {}) or ps.get("Qto_BeamBaseQuantities", {})
        length = float(dims.get("Length", 4.0)) if dims.get("Length") else 4.0
        if length > 100:
            length /= 1000.0

        if "Width" in dims and dims["Width"]:
            w = float(dims["Width"])
            if w > 10:
                w /= 1000.0
        elif "OverallWidth" in dims and dims["OverallWidth"]:
            w = float(dims["OverallWidth"])
            if w > 10:
                w /= 1000.0

        if "Depth" in dims and dims["Depth"]:
            d = float(dims["Depth"])
            if d > 10:
                d /= 1000.0
        elif "OverallDepth" in dims and dims["OverallDepth"]:
            d = float(dims["OverallDepth"])
            if d > 10:
                d /= 1000.0

        try:
            mat = ifcopenshell.util.placement.get_local_placement(beam.ObjectPlacement)
            sx, sy = float(mat[0, 3]), float(mat[1, 3])
            dx, dy = float(mat[0, 0]), float(mat[1, 0])
            ex, ey = sx + dx * length, sy + dy * length
            from_g = (get_or_create_grid_x(sx), get_or_create_grid_y(sy))
            to_g = (get_or_create_grid_x(ex), get_or_create_grid_y(ey))
            if from_g == to_g:
                to_g = (get_or_create_grid_x(ex + 0.1), to_g[1])
        except Exception:
            gx_keys = list(grid_x_vals.keys()) or ["GX_1", "GX_2"]
            gy_keys = list(grid_y_vals.keys()) or ["GY_1", "GY_2"]
            from_g = (gx_keys[0], gy_keys[0])
            to_g = (gx_keys[-1], gy_keys[-1])

        st_id = get_elem_storey(beam)
        mat_id = resolve_material(beam, "CONC_280")
        mat_obj = materials_dict.get(mat_id)
        mat_cat = mat_obj.category if mat_obj else "concrete"

        rebar_cfg = (
            BeamReinforcement(
                main_top="2-DB16",
                main_bottom="2-DB16",
                stirrups="RB6 @ 0.15m",
            )
            if mat_cat == "concrete"
            else None
        )

        elements.append(
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": tag,
                    "material": mat_id,
                    "profile": BoxProfile(shape="BOX", width=round(w, 3), depth=round(d, 3)),
                    "placement": BeamPlacement(
                        from_grid=from_g,
                        to_grid=to_g,
                        storey=st_id,
                    ),
                    "reinforcement": rebar_cfg,
                }
            )
        )

    # 5.3 Extract Walls (IfcWall and IfcWallStandardCase)
    for idx, wall in enumerate(ifc_file.by_type("IfcWall")):
        tag = wall.Name or f"WALL-{wall.GlobalId[:8]}"
        th = 0.15
        h = 2.8

        ps = ifcopenshell.util.element.get_psets(wall)
        dims = ps.get("PSet_Revit_Dimensions", {}) or ps.get("Dimensions", {})
        length = float(dims.get("Length", 3.0)) if dims.get("Length") else 3.0
        if "Width" in dims and dims["Width"]:
            th = float(dims["Width"])
            if th > 10:
                th /= 1000.0
        elif ps.get("PSet_Revit_Type_Construction", {}).get("Width"):
            th = float(ps["PSet_Revit_Type_Construction"]["Width"])
            if th > 10:
                th /= 1000.0

        constraints = ps.get("PSet_Revit_Constraints", {})
        if constraints.get("Unconnected Height"):
            h = float(constraints["Unconnected Height"])
            if h > 50:
                h /= 1000.0
        elif "Height" in dims and dims["Height"]:
            h = float(dims["Height"])
            if h > 50:
                h /= 1000.0

        try:
            mat = ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement)
            sx, sy = float(mat[0, 3]), float(mat[1, 3])
            dx, dy = float(mat[0, 0]), float(mat[1, 0])
            ex, ey = sx + dx * length, sy + dy * length
        except Exception:
            sx, sy = 0.0, 0.0
            ex, ey = 3.0, 0.0

        gx1 = get_or_create_grid_x(sx)
        gy1 = get_or_create_grid_y(sy)
        gx2 = get_or_create_grid_x(ex)
        gy2 = get_or_create_grid_y(ey)

        if gx1 == gx2 and gy1 == gy2:
            gx2 = get_or_create_grid_x(ex + 0.1)

        st_id = get_elem_storey(wall)
        mat_id = resolve_material(wall, "CONC_280")
        elements.append(
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": tag,
                    "material": mat_id,
                    "thickness": round(th, 3),
                    "height": round(h, 3),
                    "placement": WallPlacement(
                        from_grid=(gx1, gy1),
                        to_grid=(gx2, gy2),
                        storey=st_id,
                    ),
                    "children": wall_children_map.get(wall.GlobalId, []),
                }
            )
        )

    # 5.4 Extract Slabs (IfcSlab)
    for idx, slab in enumerate(ifc_file.by_type("IfcSlab")):
        tag = slab.Name or f"SLAB-{slab.GlobalId[:8]}"
        th = 0.15
        ps = ifcopenshell.util.element.get_psets(slab)
        dims = ps.get("PSet_Revit_Dimensions", {}) or ps.get("Dimensions", {})
        if dims.get("Thickness"):
            th = float(dims["Thickness"])
            if th > 10:
                th /= 1000.0
        elif ps.get("PSet_Revit_Type_Construction", {}).get("Default Thickness"):
            th = float(ps["PSet_Revit_Type_Construction"]["Default Thickness"])
            if th > 10:
                th /= 1000.0

        area = float(dims.get("Area", 16.0)) if dims.get("Area") else 16.0
        side = max(1.0, float(area) ** 0.5)

        try:
            mat = ifcopenshell.util.placement.get_local_placement(slab.ObjectPlacement)
            sx, sy = float(mat[0, 3]), float(mat[1, 3])
        except Exception:
            sx, sy = float(idx * 5.0), 0.0

        gx1 = get_or_create_grid_x(sx)
        gy1 = get_or_create_grid_y(sy)
        gx2 = get_or_create_grid_x(sx + side)
        gy2 = get_or_create_grid_y(sy + side)

        st_id = get_elem_storey(slab)
        mat_id = resolve_material(slab, "CONC_280")
        elements.append(
            IfcSlab(
                **{
                    "class": "IfcSlab",
                    "tag": tag,
                    "material": mat_id,
                    "thickness": round(th, 3),
                    "placement": SlabPlacement(
                        boundary=[(gx1, gy1), (gx2, gy1), (gx2, gy2), (gx1, gy2)],
                        storey=st_id,
                    ),
                }
            )
        )

    # 5.5 Extract Footings
    for idx, footing in enumerate(ifc_file.by_type("IfcFooting")):
        tag = footing.Name or f"F2-{idx + 1:02d}"
        pos = (idx * 4.8, 0.0, 0.0)
        try:
            mat = ifcopenshell.util.placement.get_local_placement(footing.ObjectPlacement)
            pos = (float(mat[0, 3]), float(mat[1, 3]), float(mat[2, 3]))
        except Exception:
            pass

        st_id = get_elem_storey(footing)
        elements.append(
            IfcCustomElement(
                **{
                    "class": "IfcCustomElement",
                    "tag": tag,
                    "name": tag,
                    "source": "assets/footing_f2.glb",
                    "placement": CustomElementPlacement(
                        position=pos,
                        storey=st_id,
                    ),
                }
            )
        )

    # Fallback grids if none created
    if not grid_x_vals:
        grid_x_vals = {"GX_1": 0.0, "GX_2": 6.0}
    if not grid_y_vals:
        grid_y_vals = {"GY_1": 6.0, "GY_2": 0.0}

    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id=str(p_id), name=str(p_name), units=Units()),
        spatial_structure=SpatialStructure(storeys=storeys),
        grids=Grids(axes_x=grid_x_vals, axes_y=grid_y_vals),
        materials=list(materials_dict.values()),
        elements=elements,
    )
    return manifest
