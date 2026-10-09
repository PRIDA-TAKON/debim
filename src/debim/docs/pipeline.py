"""
Multi-View Single-Element Execution Pipeline (IFC, QTO, 3D Mesh, 2D SVG)
"""

import os
import pathlib
import tempfile
import time
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field
import yaml

import ifcopenshell
import ifcopenshell.geom

from debim.compiler import StepSerializer, compile_to_ifc
from debim.cost import CostEstimate, PriceCatalog, estimate_cost
from debim.draw.renderer import SheetConfig, render_sheet
from debim.qto import ProjectQTO, calculate_qto
from debim.resolver import ResolvedManifest, resolve_manifest
from debim.schema import ProjectManifest, load_manifest


class Mesh3DPayload(BaseModel):
    vertices: List[float] = Field(
        default_factory=list,
        description="Flat list of 3D vertex coordinates [x0, y0, z0, x1, y1, z1, ...]",
    )
    normals: List[float] = Field(
        default_factory=list,
        description="Flat list of 3D surface normal vectors [nx0, ny0, nz0, ...]",
    )
    indices: List[int] = Field(
        default_factory=list,
        description="Flat list of triangle vertex indices [i0, i1, i2, ...]",
    )
    buffer_geometry: Dict[str, Any] = Field(
        default_factory=dict,
        description="Three.js BufferGeometry compatible JSON object",
    )


class ClassDocumentationEntry(BaseModel):
    class_name: str = Field(description="IFC entity class name, e.g. IfcColumn")
    element_tag: str = Field(description="Unique tag of the element in the manifest, e.g. C-01")
    manifest_yaml: str = Field(
        description="Dimension 1: Declarative YAML manifest source representation"
    )
    ifc_step: str = Field(
        description="Dimension 2: Joined exact ISO 10303-21 STEP lines representing the entity"
    )
    ifc_step_lines: List[str] = Field(
        default_factory=list,
        description="Dimension 2: List of exact ISO 10303-21 STEP lines representing the entity",
    )
    qto: ProjectQTO = Field(
        description="Dimension 3: Computed Quantitative Take-Off results (volume, formwork, rebar, etc.)"
    )
    cost: CostEstimate = Field(description="Dimension 3: Computed itemized cost estimate breakdown")
    mesh_3d: Mesh3DPayload = Field(
        description="Dimension 4: 3D mesh vertices, normals, indices, and Three.js BufferGeometry"
    )
    plan_svg: str = Field(
        description="Dimension 5: 2D plan cut SVG snippet generated via debim draw"
    )
    section_svg: str = Field(
        description="Dimension 6: 2D section cut SVG snippet generated via debim draw"
    )
    execution_time_ms: float = Field(
        description="Headless pipeline execution time in milliseconds (<50ms target)"
    )


def extract_entity_step_lines(ifc_file: Any, target_entity: Any) -> List[str]:
    """
    Recursively extracts the exact ISO 10303-21 STEP lines representing an IFC entity
    and all its sub-tree dependencies (placement, profile, representation, solid, etc.).
    """
    if target_entity is None:
        return []

    visited = set()
    stack = [target_entity]
    step_lines = []

    while stack:
        curr = stack.pop(0)
        if curr is None or not hasattr(curr, "id"):
            continue
        curr_id = curr.id()
        if curr_id == 0 or curr_id in visited:
            continue
        visited.add(curr_id)
        step_lines.append(str(curr))

        for i in range(len(curr)):
            val = curr[i]
            if isinstance(val, ifcopenshell.entity_instance):
                if val.id() not in visited:
                    stack.append(val)
            elif isinstance(val, (list, tuple)):
                for item in val:
                    if isinstance(item, ifcopenshell.entity_instance):
                        if item.id() not in visited:
                            stack.append(item)

    def _parse_step_id(s: str) -> int:
        if "=" in s and s.startswith("#"):
            try:
                return int(s.split("=")[0].replace("#", ""))
            except ValueError:
                return 0
        return 0

    step_lines.sort(key=_parse_step_id)
    return step_lines


def get_exemplar_manifest(element_class: str) -> ProjectManifest:
    """
    Generates a canonical single-element exemplar ProjectManifest for standard IFC classes.
    """
    cls_clean = element_class.strip()
    if not cls_clean.startswith("Ifc") and not cls_clean.startswith("ifc"):
        cls_clean = f"Ifc{cls_clean.capitalize()}"

    cls_key = cls_clean.lower().replace("ifc", "")

    base_dict = {
        "schema": "IFC4-Minimal",
        "project": {
            "id": f"EXEMPLAR-{cls_clean.upper()}",
            "name": f"Exemplar {cls_clean} Manifest",
        },
        "spatial_structure": {
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.5},
                {"id": "L2", "name": "Level 2", "elevation": 3.5, "height": 3.2},
            ]
        },
        "grids": {
            "axes_x": {"A": 0.0, "B": 4.0},
            "axes_y": {"1": 0.0, "2": 5.0},
        },
        "materials": [
            {
                "id": "CONC_240",
                "name": "Concrete 240 ksc",
                "category": "concrete",
                "unit_cost_ref": "MAT-CONC-01",
            }
        ],
    }

    if cls_key == "column":
        elem = {
            "class": "IfcColumn",
            "tag": "C-A1",
            "material": "CONC_240",
            "profile": {"shape": "BOX", "width": 0.3, "depth": 0.3},
            "placement": {
                "grid": ["A", "1"],
                "base_storey": "L1",
                "top_storey": "L2",
            },
            "reinforcement": {"main": "4-DB16", "stirrups": "RB6 @ 0.15m"},
        }
    elif cls_key == "wall":
        elem = {
            "class": "IfcWall",
            "tag": "W-A1",
            "material": "CONC_240",
            "thickness": 0.15,
            "height": 3.0,
            "placement": {
                "from_grid": ["A", "1"],
                "to_grid": ["B", "1"],
                "storey": "L1",
            },
        }
    elif cls_key == "beam":
        elem = {
            "class": "IfcBeam",
            "tag": "B-A1",
            "material": "CONC_240",
            "profile": {"shape": "BOX", "width": 0.2, "depth": 0.4},
            "placement": {
                "from_grid": ["A", "1"],
                "to_grid": ["B", "1"],
                "storey": "L1",
            },
        }
    elif cls_key == "slab":
        elem = {
            "class": "IfcSlab",
            "tag": "S-A1",
            "material": "CONC_240",
            "thickness": 0.15,
            "placement": {
                "storey": "L1",
                "boundary": [["A", "1"], ["B", "1"], ["B", "2"], ["A", "2"]],
            },
        }
    elif cls_key == "footing":
        elem = {
            "class": "IfcFooting",
            "tag": "F-A1",
            "material": "CONC_240",
            "profile": {"shape": "BOX", "width": 1.2, "depth": 1.2, "thickness": 0.4},
            "placement": {"grid": ["A", "1"], "storey": "L1"},
        }
    else:
        # Default fallback custom proxy element
        elem = {
            "class": cls_clean,
            "tag": f"E-{cls_clean.upper()[:3]}",
            "name": f"Exemplar {cls_clean}",
            "placement": {"position": [0.0, 0.0, 0.0], "storey": "L1"},
            "dimensions": {"width": 1.0, "depth": 1.0, "height": 1.0},
        }

    base_dict["elements"] = [elem]
    return ProjectManifest.model_validate(base_dict)


def execute_single_element_pipeline(
    manifest: Union[ProjectManifest, dict, str, pathlib.Path],
    element_tag: Optional[str] = None,
    price_catalog: Optional[PriceCatalog] = None,
    sheet_config_plan: Optional[SheetConfig] = None,
    sheet_config_section: Optional[SheetConfig] = None,
) -> ClassDocumentationEntry:
    """
    Executes a single-element manifest through debim core engines (Resolver, Compiler,
    QTO, Cost, 3D Mesh generator, and debim draw 2D Blueprint renderer) and collects
    all 6 dimensions into a ClassDocumentationEntry payload.
    """
    t0 = time.perf_counter()

    # 1. Parse manifest & extract YAML source (Dimension 1)
    if isinstance(manifest, (str, pathlib.Path)):
        p_str = str(manifest)
        if p_str.strip().startswith("{") or "schema:" in p_str or "project:" in p_str:
            data = yaml.safe_load(p_str)
            manifest_obj = ProjectManifest.model_validate(data)
            manifest_yaml = p_str
        else:
            manifest_obj = load_manifest(p_str)
            manifest_yaml = pathlib.Path(p_str).read_text(encoding="utf-8")
    elif isinstance(manifest, dict):
        manifest_obj = ProjectManifest.model_validate(manifest)
        manifest_yaml = yaml.dump(
            manifest_obj.model_dump(by_alias=True, exclude_none=True), sort_keys=False
        )
    elif isinstance(manifest, ProjectManifest):
        manifest_obj = manifest
        manifest_yaml = yaml.dump(
            manifest_obj.model_dump(by_alias=True, exclude_none=True), sort_keys=False
        )
    else:
        raise TypeError(f"Unsupported manifest input type: {type(manifest)}")

    # 2. Resolve Spatial Model
    resolved = resolve_manifest(manifest_obj)

    # Determine target element
    resolved_elements = resolved.elements
    if not resolved_elements:
        raise ValueError("Manifest contains no resolved elements")

    target_elem = None
    if element_tag:
        for elem in resolved_elements:
            if getattr(elem, "tag", None) == element_tag:
                target_elem = elem
                break
    if not target_elem:
        target_elem = resolved_elements[0]

    cls_name = getattr(target_elem, "class_", target_elem.__class__.__name__)
    if cls_name.startswith("Resolved"):
        cls_name = f"Ifc{cls_name.replace('Resolved', '')}"
    tag_val = getattr(target_elem, "tag", "E-01")

    # 3. Compile IFC STEP & extract entity STEP lines (Dimension 2)
    tmp_file = tempfile.NamedTemporaryFile(suffix=".ifc", delete=False)
    tmp_path = pathlib.Path(tmp_file.name)
    tmp_file.close()

    try:
        compile_to_ifc(resolved, output_path=tmp_path)
        ifc_file = ifcopenshell.open(tmp_path)

        # Locate target product entity
        products = ifc_file.by_type(cls_name)
        target_product = None
        for p in products:
            p_tag = getattr(p, "Tag", None) or getattr(p, "Name", None) or ""
            if p_tag == tag_val or tag_val in p_tag:
                target_product = p
                break
        if not target_product and products:
            target_product = products[0]

        step_lines = extract_entity_step_lines(ifc_file, target_product)
        ifc_step_str = "\n".join(step_lines) if step_lines else tmp_path.read_text(encoding="utf-8")

        # 4. QTO & Cost Data (Dimension 3)
        qto_res = calculate_qto(resolved)
        catalog = price_catalog or PriceCatalog()
        cost_res = estimate_cost(qto_res, catalog, manifest_obj)

        # 5. 3D Mesh Payload (Dimension 4)
        verts: List[float] = []
        normals: List[float] = []
        indices: List[int] = []

        if target_product:
            try:
                settings = ifcopenshell.geom.settings()
                settings.set(settings.USE_WORLD_COORDS, True)
                shape = ifcopenshell.geom.create_shape(settings, target_product)
                verts = [round(float(v), 4) for v in shape.geometry.verts]
                normals = [round(float(n), 4) for n in shape.geometry.normals]
                indices = [int(f) for f in shape.geometry.faces]
            except Exception:
                # Fallback empty or default mesh if create_shape fails
                pass

        buffer_geo = {
            "metadata": {"version": 4.5, "type": "BufferGeometry"},
            "attributes": {
                "position": {"itemSize": 3, "type": "Float32Array", "array": verts},
                "normal": {"itemSize": 3, "type": "Float32Array", "array": normals},
            },
            "index": {"type": "Uint16Array", "array": indices},
        }

        mesh_payload = Mesh3DPayload(
            vertices=verts,
            normals=normals,
            indices=indices,
            buffer_geometry=buffer_geo,
        )

        # 6. 2D Blueprint SVGs (Dimensions 5 & 6)
        storey_id = getattr(target_elem, "storey", None)
        if not storey_id and manifest_obj.spatial_structure.storeys:
            storey_id = manifest_obj.spatial_structure.storeys[0].id

        cfg_plan = sheet_config_plan or SheetConfig(
            sheet_number="A-101", title="Plan Cut", storey_id=storey_id or "L1"
        )
        plan_svg = render_sheet(resolved, cfg_plan)

        cfg_sec = sheet_config_section or SheetConfig(
            sheet_number="A-301", title="Section Cut", view_type="ELEVATION"
        )
        section_svg = render_sheet(resolved, cfg_sec)

    finally:
        if tmp_path.exists():
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    t1 = time.perf_counter()
    dur_ms = round((t1 - t0) * 1000, 2)

    return ClassDocumentationEntry(
        class_name=cls_name,
        element_tag=tag_val,
        manifest_yaml=manifest_yaml,
        ifc_step=ifc_step_str,
        ifc_step_lines=step_lines,
        qto=qto_res,
        cost=cost_res,
        mesh_3d=mesh_payload,
        plan_svg=plan_svg,
        section_svg=section_svg,
        execution_time_ms=dur_ms,
    )


def generate_exemplar_entry(element_class: str) -> ClassDocumentationEntry:
    """
    Convenience function to generate a canonical ClassDocumentationEntry for an IFC class name.
    """
    manifest = get_exemplar_manifest(element_class)
    return execute_single_element_pipeline(manifest)
