"""
IFC Importer for debim.
Parses buildingSMART IFC4 / IFC2X3 files via IfcOpenShell
and converts them into declarative ProjectManifest (project.yaml) for QTO & Cost estimation.
"""

from pathlib import Path
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
    """
    import ifcopenshell
    import ifcopenshell.util.element

    ifc_file = ifcopenshell.open(str(ifc_path))

    # 1. Project Info
    proj_entities = ifc_file.by_type("IfcProject")
    p_name = project_name or (proj_entities[0].Name if proj_entities else "Imported IFC Project")
    p_id = proj_entities[0].GlobalId if proj_entities else "PRJ-IMPORTED"

    # 2. Storeys
    storey_entities = ifc_file.by_type("IfcBuildingStorey")
    storeys: List[Storey] = []
    if storey_entities:
        for idx, s in enumerate(storey_entities):
            s_name = s.Name or f"Storey_{idx + 1}"
            s_id = s.Name or f"S_{idx + 1}"
            # Elevation in IFC is usually in mm or m; check units or assume meters if < 500
            elev = float(s.Elevation) if s.Elevation is not None else 0.0
            if elev > 500:  # mm to m
                elev /= 1000.0
            storeys.append(
                Storey(
                    id=s_id,
                    name=s_name,
                    elevation=elev,
                    height=3.5,
                )
            )
    else:
        storeys.append(Storey(id="GL", name="Ground Floor", elevation=0.0, height=3.5))

    # 3. Materials
    materials = [
        Material(
            id="CONC_280",
            name="Structural Concrete 280 ksc",
            category="concrete",
            unit_cost_ref="MAT-CONC-01",
        ),
        Material(
            id="STEEL_STRUCT",
            name="Structural Steel",
            category="steel",
            unit_cost_ref="MAT-STEEL-DB16",
        ),
    ]

    # 4. Elements extraction
    elements: List[Any] = []
    grid_x_vals: Dict[str, float] = {}
    grid_y_vals: Dict[str, float] = {}

    # Extract Columns
    for col in ifc_file.by_type("IfcColumn"):
        tag = col.Name or f"COL-{col.GlobalId[:8]}"
        w, d, h = 0.3, 0.3, 3.5

        # Infer placement
        ps = ifcopenshell.util.element.get_psets(col)
        dims = ps.get("Dimensions", {})
        if "Width" in dims:
            w = float(dims["Width"])
            if w > 10:
                w /= 1000.0
        if "Depth" in dims:
            d = float(dims["Depth"])
            if d > 10:
                d /= 1000.0
        if "Height" in dims:
            h = float(dims["Height"])
            if h > 10:
                h /= 1000.0

        grid_tag_x = f"GX_{len(grid_x_vals) + 1}"
        grid_tag_y = f"GY_{len(grid_y_vals) + 1}"
        grid_x_vals[grid_tag_x] = float(len(grid_x_vals) * 5.0)
        grid_y_vals[grid_tag_y] = float(len(grid_y_vals) * 5.0)

        elements.append(
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": tag,
                    "material": "CONC_280",
                    "profile": BoxProfile(shape="BOX", width=w, depth=d),
                    "placement": ColumnPlacement(
                        grid=(grid_tag_x, grid_tag_y),
                        base_storey=storeys[0].id,
                        top_storey=storeys[0].id,
                    ),
                    "reinforcement": ColumnReinforcement(
                        main="4-DB16",
                        stirrups="RB6 @ 0.15m",
                    ),
                }
            )
        )

    # Extract Beams
    for idx, beam in enumerate(ifc_file.by_type("IfcBeam")):
        tag = beam.Name or f"BEAM-{beam.GlobalId[:8]}"
        w, d = 0.2, 0.4

        elements.append(
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": tag,
                    "material": "CONC_280",
                    "profile": BoxProfile(shape="BOX", width=w, depth=d),
                    "placement": BeamPlacement(
                        from_grid=(list(grid_x_vals.keys())[0], list(grid_y_vals.keys())[0]),
                        to_grid=(list(grid_x_vals.keys())[-1], list(grid_y_vals.keys())[-1]),
                        storey=storeys[0].id,
                    ),
                    "reinforcement": BeamReinforcement(
                        main_top="2-DB16",
                        main_bottom="2-DB16",
                        stirrups="RB6 @ 0.15m",
                    ),
                }
            )
        )

    # Extract Footings
    for idx, footing in enumerate(ifc_file.by_type("IfcFooting")):
        tag = footing.Name or f"F2-{idx + 1:02d}"
        elements.append(
            IfcCustomElement(
                **{
                    "class": "IfcCustomElement",
                    "tag": tag,
                    "name": tag,
                    "source": "assets/footing_f2.glb",
                    "placement": CustomElementPlacement(
                        position=(idx * 4.8, 0.0, 0.0),
                        storey=storeys[0].id,
                    ),
                }
            )
        )

    # Grids fallback if none created
    if not grid_x_vals:
        grid_x_vals = {"1": 0.0, "2": 6.0}
    if not grid_y_vals:
        grid_y_vals = {"A": 6.0, "B": 0.0}

    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id=str(p_id), name=str(p_name), units=Units()),
        spatial_structure=SpatialStructure(storeys=storeys),
        grids=Grids(axes_x=grid_x_vals, axes_y=grid_y_vals),
        materials=materials,
        elements=elements,
    )
    return manifest
