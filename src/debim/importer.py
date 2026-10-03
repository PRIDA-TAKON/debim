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
    CoveringPlacement,
    Dimensions,
    IfcBeam,
    IfcColumn,
    IfcCovering,
    IfcCustomElement,
    CustomElementPlacement,
    IfcDoor,
    IfcRoof,
    IfcSlab,
    IfcWall,
    IfcWindow,
    RoofCoveringConfig,
    RoofPlacement,
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


import math


def _extract_euler_angles(mat: Any) -> Optional[Tuple[float, float, float]]:
    """Extract Euler angles (rx, ry, rz) in radians from a 3x3 or 4x4 transformation matrix."""
    try:
        R = mat[:3, :3]
        sy = math.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
        singular = sy < 1e-6
        if not singular:
            rx = math.atan2(R[2, 1], R[2, 2])
            ry = math.atan2(-R[2, 0], sy)
            rz = math.atan2(R[1, 0], R[0, 0])
        else:
            rx = math.atan2(-R[1, 2], R[1, 1])
            ry = math.atan2(-R[2, 0], sy)
            rz = 0.0
        return (round(rx, 4), round(ry, 4), round(rz, 4))
    except Exception:
        return None


def _extract_extruded_solid_dimensions(elem: Any) -> Optional[Dimensions]:
    """Extract dimensions from IfcExtrudedAreaSolid representation if available."""
    try:
        if not hasattr(elem, "Representation") or not elem.Representation:
            return None
        for rep in getattr(elem.Representation, "Representations", []):
            for item in getattr(rep, "Items", []):
                if item.is_a("IfcExtrudedAreaSolid"):
                    depth = float(item.Depth)
                    profile = item.SweptArea
                    x_dim, y_dim = None, None
                    if profile.is_a("IfcRectangleProfileDef"):
                        x_dim = float(profile.XDim)
                        y_dim = float(profile.YDim)
                    elif profile.is_a("IfcArbitraryClosedProfileDef") or profile.is_a("IfcArbitraryProfileDefWithVoids"):
                        curve = getattr(profile, "OuterCurve", None)
                        if curve and curve.is_a("IfcPolyline"):
                            pts = [p.Coordinates for p in curve.Points]
                            pxs = [float(p[0]) for p in pts]
                            pys = [float(p[1]) for p in pts]
                            x_dim = max(pxs) - min(pxs)
                            y_dim = max(pys) - min(pys)

                    dir_r = getattr(item.ExtrudedDirection, "DirectionRatios", (0.0, 0.0, 1.0))
                    dx, dy, dz = (dir_r[0], dir_r[1], dir_r[2]) if len(dir_r) >= 3 else (0.0, 0.0, 1.0)

                    if x_dim is not None and y_dim is not None:
                        if abs(dz) > 0.9:
                            w, d, h = x_dim, y_dim, depth
                        elif abs(dx) > 0.9:
                            w, d, h = depth, x_dim, y_dim
                        elif abs(dy) > 0.9:
                            w, d, h = x_dim, depth, y_dim
                        else:
                            w, d, h = x_dim, y_dim, depth
                        return Dimensions(
                            width=round(float(w), 3),
                            depth=round(float(d), 3),
                            height=round(float(h), 3),
                        )
    except Exception:
        pass
    return None


def _extract_bounding_box(elem: Any, settings: Any = None) -> Optional[Dimensions]:
    """Extract exact 3D bounding box (width, depth, height) using ifcopenshell.geom.create_shape."""
    if settings is None:
        try:
            import ifcopenshell.geom
            settings = ifcopenshell.geom.settings()
        except Exception:
            return _extract_extruded_solid_dimensions(elem)
    try:
        import ifcopenshell.geom
        shape = ifcopenshell.geom.create_shape(settings, elem)
        verts = shape.geometry.verts
        xs = verts[0::3]
        ys = verts[1::3]
        zs = verts[2::3]
        w = round(float(max(xs) - min(xs)), 3)
        d = round(float(max(ys) - min(ys)), 3)
        h = round(float(max(zs) - min(zs)), 3)
        if w > 0 and d > 0 and h > 0:
            return Dimensions(width=w, depth=d, height=h)
    except Exception:
        pass
    return _extract_extruded_solid_dimensions(elem)


def _derive_furniture_slug(name: Optional[str]) -> str:
    """Derive clean slug from element family name."""
    if not name:
        return "furniture"
    family = name.split(":")[0]
    if family.startswith(("M_", "m_")):
        family = family[2:]
    family = re.sub(r"\([^)]*\)", "", family)
    parts = family.split("-")
    if len(parts) > 1:
        if any(kw in parts[1].lower() for kw in ["single", "double", "wall", "drawer", "sink"]):
            family = parts[0]
        else:
            family = "_".join(parts)
    else:
        family = parts[0]
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", family).strip("_").lower()
    return slug or "furniture"


def _get_host_wall_geometry(wall: Any) -> Tuple[float, Tuple[float, float, float], Any]:
    """
    Returns (wall_length, vector_D_wall, w_mat) for a host IfcWall.
    vector_D_wall = P_end - P_start in 3D world coordinates.
    """
    import ifcopenshell.util.element
    import ifcopenshell.util.placement
    import numpy as np

    w_mat = ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement)

    ps = ifcopenshell.util.element.get_psets(wall)
    dims = ps.get("PSet_Revit_Dimensions", {}) or ps.get("Dimensions", {}) or ps.get("Qto_WallBaseQuantities", {}) or ps.get("PSet_WallCommon", {})
    wall_length = float(dims.get("Length", 0.0)) if dims.get("Length") else 0.0
    if wall_length > 100:
        wall_length /= 1000.0

    p_start_world = None
    p_end_world = None

    if hasattr(wall, "Representation") and wall.Representation:
        for rep in getattr(wall.Representation, "Representations", []):
            rep_id = getattr(rep, "RepresentationIdentifier", None)
            if rep_id == "Axis" or not p_start_world:
                for item in getattr(rep, "Items", []):
                    pts = None
                    if item.is_a("IfcPolyline"):
                        pts = [p.Coordinates for p in item.Points]
                    elif item.is_a("IfcPolyLoop"):
                        pts = [p.Coordinates for p in item.Polygon]
                    elif item.is_a("IfcTrimmedCurve"):
                        bc = getattr(item, "BasisCurve", None)
                        if bc and bc.is_a("IfcPolyline"):
                            pts = [p.Coordinates for p in bc.Points]
                    elif item.is_a("IfcLine"):
                        p_loc = item.Pnt.Coordinates
                        dir_v = item.Dir.Orientation.DirectionRatios
                        l_val = wall_length or 3.0
                        pts = [p_loc, [p_loc[0] + dir_v[0] * l_val, p_loc[1] + dir_v[1] * l_val, p_loc[2] if len(p_loc) > 2 else 0.0]]

                    if pts and len(pts) >= 2:
                        p_s_loc = np.array([float(pts[0][0]), float(pts[0][1]), float(pts[0][2]) if len(pts[0]) > 2 else 0.0, 1.0])
                        p_e_loc = np.array([float(pts[-1][0]), float(pts[-1][1]), float(pts[-1][2]) if len(pts[-1]) > 2 else 0.0, 1.0])
                        p_start_world = (w_mat @ p_s_loc)[:3]
                        p_end_world = (w_mat @ p_e_loc)[:3]
                        if rep_id == "Axis":
                            break

    if p_start_world is not None and p_end_world is not None:
        vec_D = p_end_world - p_start_world
        calc_len = float(np.linalg.norm(vec_D))
        if wall_length <= 0.0 and calc_len > 0:
            wall_length = calc_len
        return wall_length, (float(vec_D[0]), float(vec_D[1]), float(vec_D[2])), w_mat

    if wall_length <= 0.0:
        wall_length = 3.0

    x_local = w_mat[:3, 0]
    vec_D = x_local * wall_length
    return wall_length, (float(vec_D[0]), float(vec_D[1]), float(vec_D[2])), w_mat


def _bake_element_to_glb(
    elem: Any,
    slug: str,
    assets_dir: Path,
    geom_settings: Any,
) -> Optional[str]:
    """
    Bake complex 3D element geometry from IFC into a compact binary .glb asset using trimesh.
    Centers the mesh origin at its local coordinate base (X/Y center, min Z).
    Re-uses existing .glb file if present.
    """
    glb_dir = assets_dir / "furniture"
    glb_path = glb_dir / f"{slug}.glb"
    rel_path = f"assets/furniture/{slug}.glb"

    if glb_path.exists():
        return rel_path

    if geom_settings is None:
        return None

    try:
        import ifcopenshell.geom
        import trimesh
        import numpy as np

        shape = ifcopenshell.geom.create_shape(geom_settings, elem)
        verts_flat = shape.geometry.verts
        faces_flat = shape.geometry.faces

        if not verts_flat or not faces_flat:
            return None

        verts = np.array(verts_flat, dtype=np.float64).reshape(-1, 3)
        faces = np.array(faces_flat, dtype=np.int32).reshape(-1, 3)

        mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
        if len(mesh.vertices) == 0:
            return None

        min_bounds, max_bounds = mesh.bounds
        center_x = (min_bounds[0] + max_bounds[0]) / 2.0
        center_y = (min_bounds[1] + max_bounds[1]) / 2.0
        min_z = min_bounds[2]

        mesh.vertices -= [center_x, center_y, min_z]

        glb_dir.mkdir(parents=True, exist_ok=True)
        glb_data = trimesh.exchange.gltf.export_glb(mesh)
        glb_path.write_bytes(glb_data)

        return rel_path
    except Exception:
        return None


def import_ifc_to_manifest(
    ifc_path: Union[str, Path],
    project_name: Optional[str] = None,
    bake_assets: bool = False,
    assets_dir: Union[str, Path] = "assets",
) -> ProjectManifest:
    """
    Import an IFC file and convert it into a declarative ProjectManifest object.
    Supports IFC2X3 and IFC4 with columns, beams, walls, slabs, and footings.
    """
    import ifcopenshell
    import ifcopenshell.util.element
    import ifcopenshell.util.placement

    # 0. Graceful Legacy Schema Handling
    unsupported_schemas = {"IFC20_LONGFORM", "IFC2X_FINAL", "IFC2X2_FINAL"}
    try:
        with open(str(ifc_path), "r", encoding="utf-8", errors="ignore") as f_head:
            header_sample = f_head.read(4096)
        match = re.search(r"FILE_SCHEMA\s*\(\s*\('([^']+)'\)", header_sample, re.IGNORECASE)
        if match:
            schema_name = match.group(1).upper()
            if schema_name in unsupported_schemas:
                raise ValueError(
                    f"Unsupported legacy IFC schema '{schema_name}'. debim supports IFC2X3, IFC4, and IFC4X3."
                )
    except ValueError:
        raise
    except Exception:
        pass

    try:
        ifc_file = ifcopenshell.open(str(ifc_path))
    except Exception as e:
        err_msg = str(e)
        for un_schema in unsupported_schemas:
            if un_schema in err_msg:
                raise ValueError(
                    f"Unsupported legacy IFC schema '{un_schema}'. debim supports IFC2X3, IFC4, and IFC4X3."
                ) from e
        raise e

    if hasattr(ifc_file, "schema") and ifc_file.schema in unsupported_schemas:
        raise ValueError(
            f"Unsupported legacy IFC schema '{ifc_file.schema}'. debim supports IFC2X3, IFC4, and IFC4X3."
        )

    # 1. Project Info
    proj_entities = ifc_file.by_type("IfcProject")
    p_name = project_name or (proj_entities[0].Name if proj_entities else "Imported IFC Project")
    p_id = proj_entities[0].GlobalId if proj_entities else "PRJ-IMPORTED"

    # Geometry settings initialization
    try:
        import ifcopenshell.geom
        geom_settings = ifcopenshell.geom.settings()
    except Exception:
        geom_settings = None

    # 2. Storeys
    storey_entities = ifc_file.by_type("IfcBuildingStorey")
    storeys: List[Storey] = []
    storey_id_by_name: Dict[str, str] = {}
    storey_elevation_by_id: Dict[str, float] = {}
    if storey_entities:
        for idx, s in enumerate(storey_entities):
            s_name = s.Name or f"Storey_{idx + 1}"
            s_id = s.Name or f"S_{idx + 1}"
            elev = float(s.Elevation) if s.Elevation is not None else 0.0
            if elev > 500:  # mm to m
                elev /= 1000.0
            round_elev = round(elev, 3)
            storeys.append(
                Storey(
                    id=s_id,
                    name=s_name,
                    elevation=round_elev,
                    height=3.5,
                )
            )
            storey_id_by_name[s_name] = s_id
            storey_elevation_by_id[s_id] = round_elev
    else:
        storeys.append(Storey(id="GL", name="Ground Floor", elevation=0.0, height=3.5))
        storey_id_by_name["Ground Floor"] = "GL"
        storey_elevation_by_id["GL"] = 0.0

    def get_elem_storey(elem) -> str:
        try:
            container = ifcopenshell.util.element.get_container(elem)
            if container and container.Name and container.Name in storey_id_by_name:
                return storey_id_by_name[container.Name]
        except Exception:
            pass
        return storeys[0].id

    def extract_custom_placement_and_dims(
        elem: Any,
        st_id: str,
    ) -> Tuple[CustomElementPlacement, Optional[Dimensions]]:
        st_elev = storey_elevation_by_id.get(st_id, 0.0)
        pos = (0.0, 0.0, 0.0)
        rot = None
        try:
            mat = ifcopenshell.util.placement.get_local_placement(elem.ObjectPlacement)
            pos = (
                round(float(mat[0, 3]), 3),
                round(float(mat[1, 3]), 3),
                round(float(mat[2, 3]) - st_elev, 3),
            )
            rot = _extract_euler_angles(mat)
        except Exception:
            pass

        dims = _extract_bounding_box(elem, geom_settings)
        if dims is None or dims.width <= 0 or (dims.depth is not None and dims.depth <= 0) or dims.height <= 0:
            dims = Dimensions(width=0.2, depth=0.2, height=0.2)

        placement = CustomElementPlacement(
            position=pos,
            storey=st_id,
            rotation=rot,
        )
        return placement, dims

    def _get_connected_ports(elem: Any) -> List[Any]:
        """Retrieve connected IfcDistributionPort entities for an element via IfcRelConnectsPortToElement."""
        ports = []
        if hasattr(elem, "HasPorts") and elem.HasPorts:
            for rel in elem.HasPorts:
                p = getattr(rel, "RelatingPort", None)
                if p and p.is_a("IfcDistributionPort"):
                    ports.append(p)
        if not ports and ifc_file is not None:
            try:
                for rel in ifc_file.by_type("IfcRelConnectsPortToElement"):
                    if getattr(rel, "RelatedElement", None) == elem:
                        p = getattr(rel, "RelatingPort", None)
                        if p and p.is_a("IfcDistributionPort"):
                            ports.append(p)
            except Exception:
                pass
        seen = set()
        unique_ports = []
        for p in ports:
            gid = getattr(p, "GlobalId", id(p))
            if gid not in seen:
                seen.add(gid)
                unique_ports.append(p)
        return unique_ports

    def _compute_fitting_junction(
        elem: Any,
        ports: List[Any],
        st_elev: float,
    ) -> Tuple[float, float, float]:
        """
        Compute port-aligned centerline junction for MEP fittings (IfcPipeFitting, IfcDuctFitting, IfcFlowFitting).
        If 2 or more ports exist, compute the intersection or midpoint of port axes.
        Fall back to element geometric centroid if ports are unlinked.
        """
        import ifcopenshell.util.placement
        import numpy as np

        if len(ports) >= 2:
            port_axes = []
            for p in ports:
                try:
                    m = ifcopenshell.util.placement.get_local_placement(p.ObjectPlacement)
                    P = np.array([float(m[0, 3]), float(m[1, 3]), float(m[2, 3])])
                    d = np.array([float(m[0, 2]), float(m[1, 2]), float(m[2, 2])])
                    norm = np.linalg.norm(d)
                    if norm < 1e-6:
                        d = np.array([float(m[0, 0]), float(m[1, 0]), float(m[2, 0])])
                        norm = np.linalg.norm(d)
                    if norm >= 1e-6:
                        d = d / norm
                        port_axes.append((P, d))
                except Exception:
                    pass

            if len(port_axes) >= 2:
                junctions = []
                n = len(port_axes)
                for i in range(n):
                    for j in range(i + 1, n):
                        p1, d1 = port_axes[i]
                        p2, d2 = port_axes[j]
                        cross = np.cross(d1, d2)
                        denom = np.dot(cross, cross)
                        if denom < 1e-4:
                            junctions.append((p1 + p2) / 2.0)
                        else:
                            dp = p2 - p1
                            t = np.dot(np.cross(dp, d2), cross) / denom
                            s = np.dot(np.cross(dp, d1), cross) / denom
                            pt1 = p1 + t * d1
                            pt2 = p2 + s * d2
                            junctions.append((pt1 + pt2) / 2.0)

                if junctions:
                    avg_j = np.mean(junctions, axis=0)
                    midpoint = np.mean([p[0] for p in port_axes], axis=0)
                    if np.linalg.norm(avg_j - midpoint) <= 2.0:
                        return (
                            round(float(avg_j[0]), 3),
                            round(float(avg_j[1]), 3),
                            round(float(avg_j[2] - st_elev), 3),
                        )
                    else:
                        return (
                            round(float(midpoint[0]), 3),
                            round(float(midpoint[1]), 3),
                            round(float(midpoint[2] - st_elev), 3),
                        )

        # Fallback to element geometric centroid if unlinked or < 2 ports
        raw_pos = (0.0, 0.0, 0.0)
        try:
            mat = ifcopenshell.util.placement.get_local_placement(elem.ObjectPlacement)
            raw_pos = (
                float(mat[0, 3]),
                float(mat[1, 3]),
                float(mat[2, 3]),
            )
            if geom_settings is not None:
                try:
                    import ifcopenshell.geom
                    shape = ifcopenshell.geom.create_shape(geom_settings, elem)
                    verts = shape.geometry.verts
                    if verts:
                        xs = verts[0::3]
                        ys = verts[1::3]
                        zs = verts[2::3]
                        c_local = np.array([
                            (min(xs) + max(xs)) / 2.0,
                            (min(ys) + max(ys)) / 2.0,
                            (min(zs) + max(zs)) / 2.0,
                        ])
                        c_world = mat[:3, :3] @ c_local + mat[:3, 3]
                        return (
                            round(float(c_world[0]), 3),
                            round(float(c_world[1]), 3),
                            round(float(c_world[2] - st_elev), 3),
                        )
                except Exception:
                    pass
            return (
                round(float(raw_pos[0]), 3),
                round(float(raw_pos[1]), 3),
                round(float(raw_pos[2] - st_elev), 3),
            )
        except Exception:
            return (0.0, 0.0, round(0.0 - st_elev, 3))

    def extract_fitting_placement_and_dims(
        elem: Any,
        st_id: str,
    ) -> Tuple[CustomElementPlacement, Optional[Dimensions]]:
        import ifcopenshell.util.placement
        import numpy as np

        st_elev = storey_elevation_by_id.get(st_id, 0.0)
        ports = _get_connected_ports(elem)
        pos = _compute_fitting_junction(elem, ports, st_elev)
        rot = None
        try:
            mat = ifcopenshell.util.placement.get_local_placement(elem.ObjectPlacement)
            rot = _extract_euler_angles(mat)
        except Exception:
            pass

        # Inspect port direction vectors to detect vertical drops (+Z / -Z)
        if ports:
            port_dirs = []
            for p in ports:
                try:
                    m = ifcopenshell.util.placement.get_local_placement(p.ObjectPlacement)
                    d = np.array([float(m[0, 2]), float(m[1, 2]), float(m[2, 2])])
                    norm = np.linalg.norm(d)
                    if norm < 1e-6:
                        d = np.array([float(m[0, 0]), float(m[1, 0]), float(m[2, 0])])
                        norm = np.linalg.norm(d)
                    if norm >= 1e-6:
                        d = d / norm
                        port_dirs.append(d)
                except Exception:
                    pass

            if port_dirs:
                has_vert = any(abs(d[2]) > 0.7 for d in port_dirs)
                if has_vert:
                    vert_d = next(d for d in port_dirs if abs(d[2]) > 0.7)
                    horiz_d = next((d for d in port_dirs if abs(d[2]) <= 0.7), None)

                    sign = -1.0 if vert_d[2] < 0 else 1.0
                    pitch_rad = sign * (math.pi / 2.0)

                    if horiz_d is not None:
                        norm_h = np.linalg.norm(horiz_d[:2])
                        if norm_h > 1e-4:
                            yaw_rad = math.atan2(horiz_d[1], horiz_d[0])
                        else:
                            yaw_rad = rot[2] if rot else 0.0
                    else:
                        yaw_rad = rot[2] if rot else 0.0

                    rot = (round(0.0, 4), round(pitch_rad, 4), round(yaw_rad, 4))

        dims = _extract_bounding_box(elem, geom_settings)
        if dims is None or dims.width <= 0 or (dims.depth is not None and dims.depth <= 0) or dims.height <= 0:
            dims = Dimensions(width=0.2, depth=0.2, height=0.2)

        placement = CustomElementPlacement(
            position=pos,
            storey=st_id,
            rotation=rot,
        )
        return placement, dims

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

    # Build wall and roof children maps (IfcDoor and IfcWindow openings)
    wall_children_map: Dict[str, List[Union[IfcDoor, IfcWindow]]] = {}
    roof_children_map: Dict[str, List[Union[IfcDoor, IfcWindow]]] = {}

    for door in ifc_file.by_type("IfcDoor"):
        parent_host_elem = None
        try:
            for rel in getattr(door, "FillsVoids", []):
                opening = rel.RelatingOpeningElement
                for vrel in getattr(opening, "VoidsElements", []):
                    parent_host_elem = vrel.RelatingBuildingElement
                    break
                if parent_host_elem:
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
        is_reversed = False
        flipped = False
        if parent_host_elem:
            try:
                import numpy as np
                d_mat = ifcopenshell.util.placement.get_local_placement(door.ObjectPlacement)
                w_len, vec_D_wall, w_mat = _get_host_wall_geometry(parent_host_elem)
                dx = float(d_mat[0, 3] - w_mat[0, 3])
                dy = float(d_mat[1, 3] - w_mat[1, 3])
                w_dir = w_mat[:2, 0]
                offset = float(dx * w_dir[0] + dy * w_dir[1])

                x_local_3d = w_mat[:3, 0]
                dot_prod = float(vec_D_wall[0] * x_local_3d[0] + vec_D_wall[1] * x_local_3d[1] + vec_D_wall[2] * x_local_3d[2])
                if dot_prod < -1e-5:
                    is_reversed = True
                    offset = w_len - offset - w
                    if offset < 0:
                        offset = abs(offset)
                elif offset < 0:
                    offset = abs(offset)

                rel_mat = np.linalg.inv(w_mat) @ d_mat
                placement_flipped = bool(rel_mat[0, 0] < -0.5 or rel_mat[1, 1] < -0.5)
                flipped = is_reversed ^ placement_flipped
            except Exception:
                offset = 1.0

        op_type_str = None
        op_type = getattr(door, "OperationType", None)
        if not op_type:
            try:
                ps = ifcopenshell.util.element.get_psets(door)
                op_type = ps.get("PSet_DoorCommon", {}).get("OperationType") or ps.get("DoorCommon", {}).get("OperationType")
            except Exception:
                pass
        if not op_type:
            try:
                door_type = ifcopenshell.util.element.get_type(door)
                if door_type:
                    op_type = getattr(door_type, "OperationType", None)
            except Exception:
                pass
        if op_type:
            op_type_str = str(op_type)

        d_obj = IfcDoor(
            class_="IfcDoor",
            tag=door.Name or f"DOOR-{door.GlobalId[:8]}",
            dimensions=Dimensions(width=round(w, 3), height=round(h, 3)),
            offset_distance=round(offset, 2),
            operation_type=op_type_str,
            flipped=flipped,
        )
        if parent_host_elem:
            if parent_host_elem.is_a("IfcRoof"):
                roof_children_map.setdefault(parent_host_elem.GlobalId, []).append(d_obj)
            else:
                wall_children_map.setdefault(parent_host_elem.GlobalId, []).append(d_obj)

    for window in ifc_file.by_type("IfcWindow"):
        parent_host_elem = None
        try:
            for rel in getattr(window, "FillsVoids", []):
                opening = rel.RelatingOpeningElement
                for vrel in getattr(opening, "VoidsElements", []):
                    parent_host_elem = vrel.RelatingBuildingElement
                    break
                if parent_host_elem:
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
        is_reversed = False
        flipped = False
        if parent_host_elem:
            try:
                import numpy as np
                win_mat = ifcopenshell.util.placement.get_local_placement(window.ObjectPlacement)
                w_len, vec_D_wall, w_mat = _get_host_wall_geometry(parent_host_elem)
                dx = float(win_mat[0, 3] - w_mat[0, 3])
                dy = float(win_mat[1, 3] - w_mat[1, 3])
                w_dir = w_mat[:2, 0]
                offset = float(dx * w_dir[0] + dy * w_dir[1])

                x_local_3d = w_mat[:3, 0]
                dot_prod = float(vec_D_wall[0] * x_local_3d[0] + vec_D_wall[1] * x_local_3d[1] + vec_D_wall[2] * x_local_3d[2])
                if dot_prod < -1e-5:
                    is_reversed = True
                    offset = w_len - offset - w
                    if offset < 0:
                        offset = abs(offset)
                elif offset < 0:
                    offset = abs(offset)

                rel_mat = np.linalg.inv(w_mat) @ win_mat
                placement_flipped = bool(rel_mat[0, 0] < -0.5 or rel_mat[1, 1] < -0.5)
                flipped = is_reversed ^ placement_flipped
            except Exception:
                offset = 1.0

        op_type_str = None
        op_type = getattr(window, "PartitioningType", None) or getattr(window, "OperationType", None)
        if not op_type:
            try:
                ps = ifcopenshell.util.element.get_psets(window)
                op_type = ps.get("PSet_WindowCommon", {}).get("PartitioningType") or ps.get("WindowCommon", {}).get("PartitioningType")
            except Exception:
                pass
        if op_type:
            op_type_str = str(op_type)

        win_obj = IfcWindow(
            class_="IfcWindow",
            tag=window.Name or f"WIN-{window.GlobalId[:8]}",
            dimensions=Dimensions(width=round(w, 3), height=round(h, 3)),
            offset_distance=round(offset, 2),
            sill_height=0.80,
            operation_type=op_type_str,
            flipped=flipped,
        )
        if parent_host_elem:
            if parent_host_elem.is_a("IfcRoof"):
                roof_children_map.setdefault(parent_host_elem.GlobalId, []).append(win_obj)
            else:
                wall_children_map.setdefault(parent_host_elem.GlobalId, []).append(win_obj)

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
        st_id = get_elem_storey(footing)
        placement, dims = extract_custom_placement_and_dims(footing, st_id)
        elements.append(
            IfcCustomElement(
                **{
                    "class": "IfcCustomElement",
                    "tag": tag,
                    "name": tag,
                    "source": "assets/footing_f2.glb",
                    "placement": placement,
                    "dimensions": dims,
                    "layer": "structure/footings",
                }
            )
        )

    # 5.6 Extract Roofs (IfcRoof)
    for idx, roof in enumerate(ifc_file.by_type("IfcRoof")):
        tag = roof.Name or f"ROOF-{roof.GlobalId[:8]}"
        st_id = get_elem_storey(roof)
        ps = ifcopenshell.util.element.get_psets(roof)

        pitch = 0.0
        if ps.get("PSet_Revit_Type_Construction", {}).get("Pitch"):
            pitch = float(ps["PSet_Revit_Type_Construction"]["Pitch"])
        elif "Flat Roof" in (roof.Name or ""):
            pitch = 0.0

        roof_type = "FLAT" if pitch == 0.0 else "HIP"

        gx_keys = list(grid_x_vals.keys()) or ["GX_1", "GX_2"]
        gy_keys = list(grid_y_vals.keys()) or ["GY_1", "GY_2"]
        boundary = [
            (gx_keys[0], gy_keys[0]),
            (gx_keys[-1], gy_keys[0]),
            (gx_keys[-1], gy_keys[-1]),
            (gx_keys[0], gy_keys[-1]),
        ]

        mat_id = resolve_material(roof, "CONC_280")
        roof_children = roof_children_map.get(roof.GlobalId, [])

        elements.append(
            IfcRoof(
                **{
                    "class": "IfcRoof",
                    "tag": tag,
                    "material": mat_id,
                    "roof_type": roof_type,
                    "placement": RoofPlacement(
                        boundary=boundary,
                        storey=st_id,
                    ),
                    "covering": RoofCoveringConfig(pitch=pitch),
                    "children": roof_children,
                }
            )
        )

    # 5.7 Extract Coverings (IfcCovering / Ceilings)
    for cov in ifc_file.by_type("IfcCovering"):
        tag = cov.Name or f"COV-{cov.GlobalId[:8]}"
        st_id = get_elem_storey(cov)
        st_elev = storey_elevation_by_id.get(st_id, 0.0)
        ps = ifcopenshell.util.element.get_psets(cov)
        dims = ps.get("PSet_Revit_Dimensions", {}) or ps.get("Dimensions", {}) or ps.get("Qto_CoveringBaseQuantities", {})
        area = float(dims.get("Area", 10.0)) if dims.get("Area") else 10.0
        th = 0.0
        if dims.get("Thickness"):
            th = float(dims["Thickness"])
        elif ps.get("PSet_Revit_Type_Construction", {}).get("Thickness"):
            th = float(ps["PSet_Revit_Type_Construction"]["Thickness"])
        if th > 10:
            th /= 1000.0
        if th <= 0.0:
            th = 0.02  # Default 20mm (0.02m) gypsum ceiling

        pred_type = "CEILING"
        if getattr(cov, "PredefinedType", None):
            pred_type = str(cov.PredefinedType)
        if pred_type not in ["CEILING", "FLOORING", "SKIRTING", "CLADDING", "ROOFING", "INSULATION", "MEMBRANE"]:
            pred_type = "CEILING"

        mat_z = 0.0
        try:
            mat = ifcopenshell.util.placement.get_local_placement(cov.ObjectPlacement)
            mat_z = float(mat[2, 3])
        except Exception:
            pass

        world_z = mat_z
        boundary = None
        if geom_settings is not None:
            try:
                shape = ifcopenshell.geom.create_shape(geom_settings, cov)
                verts = shape.geometry.verts
                if verts:
                    xs = verts[0::3]
                    ys = verts[1::3]
                    zs = verts[2::3]
                    min_z = min(zs)
                    world_z = mat_z + min_z

                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)
                    if abs(max_x - min_x) > 0.05 and abs(max_y - min_y) > 0.05:
                        gx1 = get_or_create_grid_x(min_x)
                        gy1 = get_or_create_grid_y(min_y)
                        gx2 = get_or_create_grid_x(max_x)
                        gy2 = get_or_create_grid_y(max_y)
                        if gx1 != gx2 and gy1 != gy2:
                            boundary = [(gx1, gy1), (gx2, gy1), (gx2, gy2), (gx1, gy2)]
            except Exception:
                pass

        offset_z = round(float(world_z - st_elev), 3)

        mat_id = resolve_material(cov, "CONC_280")
        elements.append(
            IfcCovering(
                **{
                    "class": "IfcCovering",
                    "tag": tag,
                    "covering_type": pred_type,
                    "material": mat_id,
                    "thickness": round(th, 3),
                    "placement": CoveringPlacement(
                        storey=st_id,
                        offset_z=offset_z,
                        area=round(area, 3),
                        boundary=boundary,
                    ),
                }
            )
        )

    # 5.8 Extract Stairs
    for stair in ifc_file.by_type("IfcStair"):
        tag = stair.Name or f"STAIR-{stair.GlobalId[:8]}"
        st_id = get_elem_storey(stair)
        placement, dims = extract_custom_placement_and_dims(stair, st_id)
        elements.append(
            IfcCustomElement(
                **{
                    "class": "IfcCustomElement",
                    "tag": tag,
                    "name": tag,
                    "source": f"ifc/stair/{tag}",
                    "placement": placement,
                    "dimensions": dims,
                    "layer": "circulation/stairs",
                }
            )
        )

    # 5.9 Extract Stair Flights
    for flight in ifc_file.by_type("IfcStairFlight"):
        tag = flight.Name or f"FLIGHT-{flight.GlobalId[:8]}"
        st_id = get_elem_storey(flight)
        placement, dims = extract_custom_placement_and_dims(flight, st_id)
        elements.append(
            IfcCustomElement(
                **{
                    "class": "IfcCustomElement",
                    "tag": tag,
                    "name": tag,
                    "source": f"ifc/stairflight/{tag}",
                    "placement": placement,
                    "dimensions": dims,
                    "layer": "circulation/stairflights",
                }
            )
        )

    # 5.10 Extract Railings
    for railing in ifc_file.by_type("IfcRailing"):
        tag = railing.Name or f"RAILING-{railing.GlobalId[:8]}"
        st_id = get_elem_storey(railing)
        placement, dims = extract_custom_placement_and_dims(railing, st_id)
        elements.append(
            IfcCustomElement(
                **{
                    "class": "IfcCustomElement",
                    "tag": tag,
                    "name": tag,
                    "source": f"ifc/railing/{tag}",
                    "placement": placement,
                    "dimensions": dims,
                    "layer": "circulation/railings",
                }
            )
        )

    def extract_member_placement_and_dims(
        elem: Any,
        st_id: str,
    ) -> Tuple[CustomElementPlacement, Optional[Dimensions]]:
        st_elev = storey_elevation_by_id.get(st_id, 0.0)
        if geom_settings is not None:
            try:
                import ifcopenshell.geom
                import numpy as np

                shape = ifcopenshell.geom.create_shape(geom_settings, elem)
                verts = np.array(shape.geometry.verts, dtype=np.float64).reshape(-1, 3)
                if len(verts) >= 4:
                    mean = np.mean(verts, axis=0)
                    cov = np.cov(verts - mean, rowvar=False)
                    evals, evecs = np.linalg.eigh(cov)
                    axis = evecs[:, -1]
                    projections = (verts - mean) @ axis
                    p1 = mean + np.min(projections) * axis
                    p2 = mean + np.max(projections) * axis
                    if p1[2] > p2[2]:
                        p1, p2 = p2, p1

                    dp = p2 - p1
                    L = float(np.linalg.norm(dp))
                    if L > 1e-4 and abs(dp[2]) > 1e-4:
                        phi = float(math.asin(max(-1.0, min(1.0, dp[2] / L))))
                        psi = float(math.atan2(dp[1], dp[0]))

                        c_phi, s_phi = math.cos(phi), math.sin(phi)
                        c_psi, s_psi = math.cos(psi), math.sin(psi)
                        Ry = np.array([[c_phi, 0, -s_phi], [0, 1, 0], [s_phi, 0, c_phi]])
                        Rz = np.array([[c_psi, -s_psi, 0], [s_psi, c_psi, 0], [0, 0, 1]])
                        R = Rz @ Ry

                        rot = _extract_euler_angles(R)

                        v_local = (verts - mean) @ R
                        w = round(L, 3)
                        d = round(float(np.max(v_local[:, 1]) - np.min(v_local[:, 1])), 3)
                        h = round(float(np.max(v_local[:, 2]) - np.min(v_local[:, 2])), 3)
                        if d <= 0.0:
                            d = 0.2
                        if h <= 0.0:
                            h = 0.2

                        center_pos = (
                            round(float(mean[0]), 3),
                            round(float(mean[1]), 3),
                            round(float(mean[2] - st_elev), 3),
                        )
                        placement = CustomElementPlacement(
                            position=center_pos,
                            storey=st_id,
                            rotation=rot,
                        )
                        dims = Dimensions(width=w, depth=d, height=h)
                        return placement, dims
            except Exception:
                pass

        return extract_custom_placement_and_dims(elem, st_id)

    # 5.11 Extract Members
    for member in ifc_file.by_type("IfcMember"):
        tag = member.Name or f"MEMBER-{member.GlobalId[:8]}"
        st_id = get_elem_storey(member)
        placement, dims = extract_member_placement_and_dims(member, st_id)
        elements.append(
            IfcCustomElement(
                **{
                    "class": "IfcCustomElement",
                    "tag": tag,
                    "name": tag,
                    "source": f"ifc/member/{tag}",
                    "placement": placement,
                    "dimensions": dims,
                    "layer": "structure/members",
                }
            )
        )

    def safe_by_type(type_name: str) -> List[Any]:
        try:
            return list(ifc_file.by_type(type_name))
        except Exception:
            return []

    assets_dir_path = Path(assets_dir)

    # 5.12 Extract Furnishing Elements & Furniture
    extracted_custom_ids = set()

    for furn in safe_by_type("IfcFurnishingElement") + safe_by_type("IfcFurniture"):
        if furn.GlobalId in extracted_custom_ids:
            continue
        extracted_custom_ids.add(furn.GlobalId)
        tag = furn.Name or f"FURN-{furn.GlobalId[:8]}"
        name = furn.Name or tag
        slug = _derive_furniture_slug(furn.Name)
        st_id = get_elem_storey(furn)
        placement, dims = extract_custom_placement_and_dims(furn, st_id)

        source_path = f"assets/furniture/{slug}.glb"
        if bake_assets:
            baked = _bake_element_to_glb(furn, slug, assets_dir_path, geom_settings)
            if baked:
                source_path = baked

        elements.append(
            IfcCustomElement(
                **{
                    "class": "IfcCustomElement",
                    "tag": tag,
                    "name": name,
                    "source": source_path,
                    "placement": placement,
                    "dimensions": dims,
                    "layer": "interior/furniture",
                }
            )
        )

    # 5.13 Extract MEP Flow Segments (IfcDuctSegment, IfcPipeSegment, IfcFlowSegment)
    for seg_cls in ["IfcDuctSegment", "IfcPipeSegment", "IfcFlowSegment"]:
        for seg in safe_by_type(seg_cls):
            if seg.GlobalId in extracted_custom_ids:
                continue
            extracted_custom_ids.add(seg.GlobalId)
            tag = seg.Name or f"SEG-{seg.GlobalId[:8]}"
            st_id = get_elem_storey(seg)
            layer = "mep/pipes" if seg.is_a("IfcPipeSegment") else "mep/ducts"
            placement, dims = extract_custom_placement_and_dims(seg, st_id)
            elements.append(
                IfcCustomElement(
                    **{
                        "class": "IfcCustomElement",
                        "tag": tag,
                        "name": tag,
                        "source": f"ifc/segment/{tag}",
                        "placement": placement,
                        "dimensions": dims,
                        "layer": layer,
                    }
                )
            )

    # 5.17 Extract MEP Valves, Dampers, Flow Controllers & Distribution Control Elements
    mep_ctrl_configs = [
        ("IfcValve", "mep/valves", "VALVE"),
        ("IfcDamper", "mep/dampers", "DAMPER"),
        ("IfcFlowController", "mep/flow_controllers", "FLOW_CTRL"),
        ("IfcDistributionControlElement", "mep/controls", "CTRL_ELEM"),
    ]
    for c_cls, c_layer, c_prefix in mep_ctrl_configs:
        for ctrl_elem in safe_by_type(c_cls):
            if ctrl_elem.GlobalId in extracted_custom_ids:
                continue
            extracted_custom_ids.add(ctrl_elem.GlobalId)
            tag = ctrl_elem.Name or f"{c_prefix}-{ctrl_elem.GlobalId[:8]}"
            st_id = get_elem_storey(ctrl_elem)
            placement, dims = extract_custom_placement_and_dims(ctrl_elem, st_id)
            if dims is None or dims.width <= 0 or (dims.depth is not None and dims.depth <= 0) or dims.height <= 0:
                dims = Dimensions(width=0.2, depth=0.2, height=0.2)
            elements.append(
                IfcCustomElement(
                    **{
                        "class": "IfcCustomElement",
                        "tag": tag,
                        "name": tag,
                        "source": f"ifc/{c_prefix.lower()}/{tag}",
                        "placement": placement,
                        "dimensions": dims,
                        "layer": c_layer,
                    }
                )
            )

    # 5.14 Extract MEP Terminals (IfcAirTerminal, IfcSanitaryTerminal, IfcFlowTerminal)
    for term_cls in ["IfcAirTerminal", "IfcSanitaryTerminal", "IfcFlowTerminal"]:
        for term in safe_by_type(term_cls):
            if term.GlobalId in extracted_custom_ids:
                continue
            extracted_custom_ids.add(term.GlobalId)
            tag = term.Name or f"TERM-{term.GlobalId[:8]}"
            st_id = get_elem_storey(term)
            placement, dims = extract_custom_placement_and_dims(term, st_id)

            source_path = f"ifc/terminal/{tag}"
            if term.is_a("IfcSanitaryTerminal"):
                slug = _derive_furniture_slug(term.Name or tag)
                source_path = f"assets/furniture/{slug}.glb"
                if bake_assets:
                    baked = _bake_element_to_glb(term, slug, assets_dir_path, geom_settings)
                    if baked:
                        source_path = baked

            elements.append(
                IfcCustomElement(
                    **{
                        "class": "IfcCustomElement",
                        "tag": tag,
                        "name": tag,
                        "source": source_path,
                        "placement": placement,
                        "dimensions": dims,
                        "layer": "mep/terminals",
                    }
                )
            )

    # 5.15 Extract MEP Fittings (IfcFlowFitting, IfcPipeFitting, IfcDuctFitting)
    for fit_cls in ["IfcFlowFitting", "IfcPipeFitting", "IfcDuctFitting"]:
        for fit in safe_by_type(fit_cls):
            if fit.GlobalId in extracted_custom_ids:
                continue
            extracted_custom_ids.add(fit.GlobalId)
            tag = fit.Name or f"FIT-{fit.GlobalId[:8]}"
            st_id = get_elem_storey(fit)
            placement, dims = extract_fitting_placement_and_dims(fit, st_id)
            elements.append(
                IfcCustomElement(
                    **{
                        "class": "IfcCustomElement",
                        "tag": tag,
                        "name": tag,
                        "source": f"ifc/fitting/{tag}",
                        "placement": placement,
                        "dimensions": dims,
                        "layer": "mep/fittings",
                    }
                )
            )

    # 5.16 Extract Generic Proxies & Accessories (IfcBuildingElementProxy, IfcChimney, IfcDiscreteAccessory)
    proxy_configs = [
        ("IfcBuildingElementProxy", "architecture/proxies", "PROXY"),
        ("IfcChimney", "architecture/chimneys", "CHIMNEY"),
        ("IfcDiscreteAccessory", "structure/accessories", "ACC"),
    ]
    for p_cls, p_layer, p_prefix in proxy_configs:
        for proxy in safe_by_type(p_cls):
            if proxy.GlobalId in extracted_custom_ids:
                continue
            extracted_custom_ids.add(proxy.GlobalId)
            tag = proxy.Name or f"{p_prefix}-{proxy.GlobalId[:8]}"
            st_id = get_elem_storey(proxy)
            placement, dims = extract_custom_placement_and_dims(proxy, st_id)
            elements.append(
                IfcCustomElement(
                    **{
                        "class": "IfcCustomElement",
                        "tag": tag,
                        "name": tag,
                        "source": f"ifc/proxy/{tag}",
                        "placement": placement,
                        "dimensions": dims,
                        "layer": p_layer,
                    }
                )
            )

    # 5.17 Extract Plates (IfcPlate) and Building Element Parts (IfcBuildingElementPart)
    plate_configs = [
        ("IfcPlate", "structure/plates", "PLATE"),
        ("IfcBuildingElementPart", "structure/parts", "PART"),
    ]
    for p_cls, p_layer, p_prefix in plate_configs:
        for elem in safe_by_type(p_cls):
            if elem.GlobalId in extracted_custom_ids:
                continue
            extracted_custom_ids.add(elem.GlobalId)
            tag = elem.Name or f"{p_prefix}-{elem.GlobalId[:8]}"
            st_id = get_elem_storey(elem)
            placement, dims = extract_custom_placement_and_dims(elem, st_id)
            elements.append(
                IfcCustomElement(
                    **{
                        "class": "IfcCustomElement",
                        "tag": tag,
                        "name": elem.Name or tag,
                        "source": f"ifc/{p_prefix.lower()}/{tag}",
                        "placement": placement,
                        "dimensions": dims,
                        "layer": p_layer,
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
