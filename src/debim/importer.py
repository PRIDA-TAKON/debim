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
    IfcBeam,
    IfcColumn,
    IfcCustomElement,
    CustomElementPlacement,
    IfcWall,
    WallPlacement,
    IfcSlab,
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

            if mat_name:
                clean_id = re.sub(r"[^A-Za-z0-9_]", "_", mat_name.strip()).upper()[:24]
                if clean_id not in materials_dict:
                    cat = "concrete" if "conc" in clean_id.lower() else ("steel" if "steel" in clean_id.lower() else "masonry")
                    materials_dict[clean_id] = Material(
                        id=clean_id,
                        name=mat_name,
                        category=cat,
                        unit_cost_ref="MAT-CONC-01" if cat == "concrete" else "MAT-STEEL-DB16",
                    )
                return clean_id
        except Exception:
            pass
        return default_id

    # 5. Elements extraction
    elements: List[Any] = []

    # 5.1 Extract Columns
    for col in ifc_file.by_type("IfcColumn"):
        tag = col.Name or f"COL-{col.GlobalId[:8]}"
        w, d = 0.3, 0.3

        ps = ifcopenshell.util.element.get_psets(col)
        dims = ps.get("Dimensions", {}) or ps.get("PSet_Revit_Dimensions", {})
        if "Width" in dims and dims["Width"]:
            w = float(dims["Width"])
            if w > 10:
                w /= 1000.0
        if "Depth" in dims and dims["Depth"]:
            d = float(dims["Depth"])
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
                    "reinforcement": ColumnReinforcement(
                        main="4-DB16",
                        stirrups="RB6 @ 0.15m",
                    ),
                }
            )
        )

    # 5.2 Extract Beams
    for idx, beam in enumerate(ifc_file.by_type("IfcBeam")):
        tag = beam.Name or f"BEAM-{beam.GlobalId[:8]}"
        w, d = 0.2, 0.4
        ps = ifcopenshell.util.element.get_psets(beam)
        dims = ps.get("Dimensions", {}) or ps.get("PSet_Revit_Dimensions", {})
        length = float(dims.get("Length", 4.0)) if dims.get("Length") else 4.0

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
                    "reinforcement": BeamReinforcement(
                        main_top="2-DB16",
                        main_bottom="2-DB16",
                        stirrups="RB6 @ 0.15m",
                    ),
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
