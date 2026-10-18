"""
Mathematical macro-geometry & multi-storey hyperbolic loft engine for debim.
Evaluates double-curved and asymmetric building enclosures using parametric mathematical functions.
"""

import math
from typing import List, Optional, Tuple
import numpy as np

from debim.schema import (
    BoxProfile,
    CircleHollowProfile,
    ColumnPlacement,
    GeometryRules,
    IfcColumn,
    IfcSlab,
    IfcWall,
    ProjectManifest,
    SlabPlacement,
    WallPlacement,
    parse_steel_section_spec,
)


def evaluate_loft_radii(
    rules: GeometryRules,
    z: float,
    total_height: float,
) -> Tuple[float, float]:
    """
    Evaluates cross-sectional semi-axes radii (a(z), b(z)) at height z for a given GeometryRules spec.

    total_height H > 0.
    Normalized height t = z / H in [0, 1].
    """
    H = max(total_height, 1e-6)
    t = max(0.0, min(1.0, z / H))

    a_base, b_base = float(rules.base_radii[0]), float(rules.base_radii[1])
    a_roof, b_roof = float(rules.roof_radii[0]), float(rules.roof_radii[1])

    if rules.type == "CYLINDRICAL_LOFT":
        return a_base, b_base

    elif rules.type == "CONICAL_LOFT":
        a_z = (1.0 - t) * a_base + t * a_roof
        b_z = (1.0 - t) * b_base + t * b_roof
        return a_z, b_z

    elif rules.type == "HYPERBOLIC_LOFT":
        if rules.waist_radii is not None:
            a_waist, b_waist = float(rules.waist_radii[0]), float(rules.waist_radii[1])
        else:
            # Default midpoint waist pinch (80% of average base and roof)
            a_waist = 0.8 * (a_base + a_roof) / 2.0
            b_waist = 0.8 * (b_base + b_roof) / 2.0

        # Lagrange quadratic polynomial interpolation through t=0 (base), t=0.5 (waist), t=1.0 (roof)
        # L0(t) = 2*(t-0.5)*(t-1.0)
        # L1(t) = -4*t*(t-1.0)
        # L2(t) = 2*t*(t-0.5)
        l0 = 2.0 * (t - 0.5) * (t - 1.0)
        l1 = -4.0 * t * (t - 1.0)
        l2 = 2.0 * t * (t - 0.5)

        a_z = l0 * a_base + l1 * a_waist + l2 * a_roof
        b_z = l0 * b_base + l1 * b_waist + l2 * b_roof
        return max(a_z, 0.01), max(b_z, 0.01)

    return a_base, b_base


def evaluate_loft_boundary(
    rules: GeometryRules,
    z: float,
    total_height: float,
    n_points: int = 64,
) -> np.ndarray:
    """
    Evaluates 2D cross-sectional boundary polygon points P(u, z) at height z.

    Formula:
      P(u, z) = C(z) + [a(z) * cos(u), b(z) * sin(u)]
    where C(z) is the cantilever center offset at height z.

    Returns Nx2 numpy array of [x, y] coordinates.
    """
    H = max(total_height, 1e-6)
    t = max(0.0, min(1.0, z / H))

    a_z, b_z = evaluate_loft_radii(rules, z, total_height)

    # Cantilever lean offset C(z)
    if rules.cantilever_offset is not None:
        cx_top, cy_top = float(rules.cantilever_offset[0]), float(rules.cantilever_offset[1])
        cx_z = t * cx_top
        cy_z = t * cy_top
    else:
        cx_z, cy_z = 0.0, 0.0

    u = np.linspace(0.0, 2.0 * np.pi, n_points, endpoint=False)
    x = cx_z + a_z * np.cos(u)
    y = cy_z + b_z * np.sin(u)

    return np.column_stack((x, y))


def generate_loft_storey_elements(
    manifest: ProjectManifest,
    n_points: int = 32,
    slab_material: str = "CONCRETE",
    slab_thickness: float = 0.20,
    wall_material: Optional[str] = None,
    wall_thickness: float = 0.15,
) -> Tuple[List[IfcSlab], List[IfcWall]]:
    """
    Auto-generates storey boundary slabs (IfcSlab) and exterior wall enclosures sliced
    at each storey height based on evaluated loft geometry rules.
    """
    if manifest.geometry_rules is None:
        return [], []

    rules = manifest.geometry_rules
    storeys = manifest.spatial_structure.storeys
    if not storeys:
        return [], []

    sorted_storeys = sorted(storeys, key=lambda s: s.elevation)
    top_storey = sorted_storeys[-1]
    total_height = top_storey.elevation + top_storey.height

    slabs: List[IfcSlab] = []
    walls: List[IfcWall] = []

    # Choose default material from manifest materials if available
    mat_id = slab_material
    if manifest.materials:
        mat_ids = [m.id for m in manifest.materials]
        if mat_id not in mat_ids:
            mat_id = mat_ids[0]

    for s_idx, storey in enumerate(sorted_storeys):
        z_elev = storey.elevation
        boundary_pts = evaluate_loft_boundary(rules, z_elev, total_height, n_points=n_points)

        # Convert 2D points to string grid expressions (x_str, y_str) for SlabPlacement
        boundary_tuples = [(f"{pt[0]:.4f}", f"{pt[1]:.4f}") for pt in boundary_pts]

        slab = IfcSlab(
            tag=f"SLAB-LOFT-{storey.id}",
            material=mat_id,
            thickness=slab_thickness,
            placement=SlabPlacement(
                boundary=boundary_tuples,
                storey=storey.id,
                offset_z=0.0,
            ),
        )
        slabs.append(slab)

        # Auto-generate exterior wall enclosure panels between boundary points for this storey
        for i in range(len(boundary_pts)):
            pt_a = boundary_pts[i]
            pt_b = boundary_pts[(i + 1) % len(boundary_pts)]

            w_tag = f"WALL-LOFT-{storey.id}-{i+1}"
            from_grid_str = (f"{pt_a[0]:.4f}", f"{pt_a[1]:.4f}")
            to_grid_str = (f"{pt_b[0]:.4f}", f"{pt_b[1]:.4f}")

            wall = IfcWall(
                tag=w_tag,
                material=mat_id,
                thickness=wall_thickness,
                height=storey.height,
                placement=WallPlacement(
                    from_grid=from_grid_str,
                    to_grid=to_grid_str,
                    storey=storey.id,
                ),
            )
            walls.append(wall)

    return slabs, walls


def generate_curved_spine_columns(
    manifest: ProjectManifest,
) -> List[IfcColumn]:
    """
    Generates 3D curved structural ribs/columns following 3D spline directrix
    trajectories (such as the 28 curved columns of Museo Soumaya) travelling along
    the outer hyperbolic loft boundary across storeys.
    """
    if manifest.geometry_rules is None or manifest.structures is None:
        return []
    if manifest.structures.column_generator is None:
        return []

    rules = manifest.geometry_rules
    gen = manifest.structures.column_generator
    storeys = manifest.spatial_structure.storeys
    if not storeys:
        return []

    sorted_storeys = sorted(storeys, key=lambda s: s.elevation)
    top_storey = sorted_storeys[-1]
    total_height = top_storey.elevation + top_storey.height

    count = gen.count
    if count <= 0:
        return []

    # Parse profile
    prof_raw = gen.profile
    if isinstance(prof_raw, str):
        parsed_sec = parse_steel_section_spec(prof_raw)
        if "diameter" in parsed_sec and "wall_thickness" in parsed_sec:
            prof_obj = CircleHollowProfile(
                shape="CIRCLE_HOLLOW",
                diameter=parsed_sec["diameter"],
                wall_thickness=parsed_sec["wall_thickness"],
            )
        elif "width" in parsed_sec and "depth" in parsed_sec:
            prof_obj = BoxProfile(
                shape="BOX",
                width=parsed_sec["width"],
                depth=parsed_sec["depth"],
            )
        else:
            prof_obj = CircleHollowProfile(
                shape="CIRCLE_HOLLOW",
                diameter=0.60,
                wall_thickness=0.02,
            )
    elif isinstance(prof_raw, dict):
        prof_obj = prof_raw
    else:
        prof_obj = prof_raw

    # Determine material (prefer steel if available)
    mat_id = gen.material or "STEEL"
    if manifest.materials:
        mat_ids = [m.id for m in manifest.materials]
        if mat_id not in mat_ids:
            steel_mats = [m.id for m in manifest.materials if (m.category or "").lower() in ("steel", "metal")]
            mat_id = steel_mats[0] if steel_mats else mat_ids[0]

    # Angles for each column
    u_angles = [2.0 * math.pi * k / count for k in range(count)]

    columns: List[IfcColumn] = []

    # For each column index k
    for k, u in enumerate(u_angles):
        # Generate continuous curved spine segments across each storey
        for s_idx, storey in enumerate(sorted_storeys):
            z1 = storey.elevation
            z2 = z1 + storey.height

            # Evaluate (x1, y1) at base of storey
            a_z1, b_z1 = evaluate_loft_radii(rules, z1, total_height)
            t1 = max(0.0, min(1.0, z1 / max(total_height, 1e-6)))
            cx1 = t1 * float(rules.cantilever_offset[0]) if rules.cantilever_offset else 0.0
            cy1 = t1 * float(rules.cantilever_offset[1]) if rules.cantilever_offset else 0.0
            x1 = cx1 + a_z1 * math.cos(u)
            y1 = cy1 + b_z1 * math.sin(u)

            # Evaluate (x2, y2) at top of storey
            a_z2, b_z2 = evaluate_loft_radii(rules, z2, total_height)
            t2 = max(0.0, min(1.0, z2 / max(total_height, 1e-6)))
            cx2 = t2 * float(rules.cantilever_offset[0]) if rules.cantilever_offset else 0.0
            cy2 = t2 * float(rules.cantilever_offset[1]) if rules.cantilever_offset else 0.0
            x2 = cx2 + a_z2 * math.cos(u)
            y2 = cy2 + b_z2 * math.sin(u)

            top_st_id = sorted_storeys[s_idx + 1].id if s_idx + 1 < len(sorted_storeys) else storey.id

            col = IfcColumn(
                tag=f"COL-CURVED-{k+1}-{storey.id}",
                material=mat_id,
                profile=prof_obj,
                placement=ColumnPlacement(
                    grid=(f"{x1:.4f}", f"{y1:.4f}"),
                    top_grid=(f"{x2:.4f}", f"{y2:.4f}"),
                    base_storey=storey.id,
                    top_storey=top_st_id,
                    base_elevation=z1,
                    top_elevation=z2,
                    height=storey.height,
                ),
                layer=gen.layer or "S-COLS",
            )
            columns.append(col)

    return columns
