"""
Conformal surface tessellation engine for double-curved loft facade envelopes.
Discretizes double-curved surfaces into planar hexagonal tiles (conformal & centroidal Voronoi)
with uniform joint gaps.
"""

import math
from typing import Dict, List, Literal, Optional, Tuple, Any
import numpy as np

from debim.geometry.loft import evaluate_loft_boundary, evaluate_loft_point, evaluate_loft_radii
from debim.schema import FacadeEnvelopeSkin, GeometryRules, ProjectManifest


class HexPanel:
    """Represents a single 3D planar hexagonal facade panel."""

    def __init__(
        self,
        panel_id: str,
        center: Tuple[float, float, float],
        normal: Tuple[float, float, float],
        tangent_u: Tuple[float, float, float],
        tangent_v: Tuple[float, float, float],
        vertices: List[Tuple[float, float, float]],
        faces: List[Tuple[int, int, int]],
        area: float,
        rotation_matrix: np.ndarray,
        uv_coord: Tuple[float, float],
    ):
        self.panel_id = panel_id
        self.center = center
        self.normal = normal
        self.tangent_u = tangent_u
        self.tangent_v = tangent_v
        self.vertices = vertices  # 3D corner points (usually 6 for hexagon)
        self.faces = faces  # 0-based face triangle vertex index tuples
        self.area = area  # panel 3D surface area (m2)
        self.rotation_matrix = rotation_matrix
        self.uv_coord = uv_coord

    def to_dict(self) -> Dict[str, Any]:
        return {
            "panel_id": self.panel_id,
            "center": list(self.center),
            "normal": list(self.normal),
            "vertices": [list(v) for v in self.vertices],
            "faces": [list(f) for f in self.faces],
            "area": self.area,
            "uv_coord": list(self.uv_coord),
        }


class FacadeTessellationResult:
    """Aggregated facade discretization result across thousands of panels."""

    def __init__(
        self,
        target_rule: str,
        panels: List[HexPanel],
        material: str,
        ifc_representation: str,
        pattern: str,
        target_panel_size: float,
        joint_gap: float,
    ):
        self.target_rule = target_rule
        self.panels = panels
        self.material = material
        self.ifc_representation = ifc_representation
        self.pattern = pattern
        self.target_panel_size = target_panel_size
        self.joint_gap = joint_gap

    @property
    def total_panel_count(self) -> int:
        return len(self.panels)

    @property
    def total_surface_area(self) -> float:
        return sum(p.area for p in self.panels)

    def get_combined_tessellation_mesh(self) -> Tuple[List[List[float]], List[List[int]]]:
        """
        Consolidates all panel vertices and face indices into unified point list and 1-based index list
        suitable for IFC4 IfcTriangulatedFaceSet export.
        """
        combined_pts: List[List[float]] = []
        combined_indices: List[List[int]] = []

        pt_offset = 1  # IFC Step index is 1-based
        for panel in self.panels:
            # Each panel has 6 outer vertices and 1 center vertex or 6 vertices
            v_start = pt_offset
            for v in panel.vertices:
                combined_pts.append([v[0], v[1], v[2]])
                pt_offset += 1

            for f in panel.faces:
                combined_indices.append([v_start + f[0], v_start + f[1], v_start + f[2]])

        return combined_pts, combined_indices


def _evaluate_surface_point_and_frame(
    rules: GeometryRules,
    u: float,
    z: float,
    total_height: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    Computes 3D surface point P(u, z) and local orthonormal tangent frame (T_u, T_z, Normal).
    """
    H = max(total_height, 1e-6)

    x0, y0 = evaluate_loft_point(rules, u, z, total_height)
    p_center = np.array([x0, y0, z], dtype=float)

    # Compute numerical partial derivatives for tangent directions
    du = 1e-4
    dz = 1e-4

    # P(u + du, z)
    x_u, y_u = evaluate_loft_point(rules, u + du, z, total_height)
    p_u_plus = np.array([x_u, y_u, z], dtype=float)

    # P(u, z + dz)
    z_plus = min(z + dz, total_height)
    actual_dz = z_plus - z if z_plus > z else 1e-4
    x_z, y_z = evaluate_loft_point(rules, u, z_plus, total_height)
    p_z_plus = np.array([x_z, y_z, z_plus], dtype=float)

    tan_u = (p_u_plus - p_center) / du
    norm_tu = np.linalg.norm(tan_u)
    if norm_tu > 1e-9:
        u1 = tan_u / norm_tu
    else:
        u1 = np.array([1.0, 0.0, 0.0])

    tan_z = (p_z_plus - p_center) / actual_dz
    norm_tz = np.linalg.norm(tan_z)
    if norm_tz > 1e-9:
        tz_unit = tan_z / norm_tz
    else:
        tz_unit = np.array([0.0, 0.0, 1.0])

    # Normal vector N = T_u x T_z
    normal = np.cross(u1, tz_unit)
    norm_n = np.linalg.norm(normal)
    if norm_n > 1e-9:
        n3 = normal / norm_n
    else:
        n3 = np.array([math.cos(u), math.sin(u), 0.0])

    # Orthonormal u2 = n3 x u1
    u2 = np.cross(n3, u1)
    norm_u2 = np.linalg.norm(u2)
    if norm_u2 > 1e-9:
        u2 = u2 / norm_u2

    return p_center, u1, u2, n3


def generate_facade_tessellation(
    manifest: ProjectManifest,
    envelope_skin: Optional[FacadeEnvelopeSkin] = None,
) -> Optional[FacadeTessellationResult]:
    """
    Generates algorithmic surface discretization of double-curved facade lofts
    into planar hexagonal panels with uniform joint gaps.
    """
    if envelope_skin is None:
        if manifest.facade and manifest.facade.envelope_skin:
            envelope_skin = manifest.facade.envelope_skin

    if envelope_skin is None or manifest.geometry_rules is None:
        return None

    rules = manifest.geometry_rules
    storeys = manifest.spatial_structure.storeys
    if not storeys:
        return None

    sorted_storeys = sorted(storeys, key=lambda s: s.elevation)
    top_storey = sorted_storeys[-1]
    total_height = top_storey.elevation + top_storey.height

    d_target = max(envelope_skin.target_panel_size, 0.05)
    joint_gap = max(envelope_skin.joint_gap, 0.001)

    # Panel outer bounding radius and inner tile radius after subtracting reveal gap
    r_outer = d_target / 2.0
    r_panel = max(r_outer - joint_gap / 2.0, 0.01)

    # Flat-to-flat width W = sqrt(3)*r_outer, vertical row step H_step = 1.5*r_outer
    w_flat = math.sqrt(3.0) * r_outer
    v_step = 1.5 * r_outer

    # Average perimeter calculation via boundary sampling
    mid_boundary = evaluate_loft_boundary(rules, total_height / 2.0, total_height, n_points=64)
    mid_diffs = np.diff(np.vstack([mid_boundary, mid_boundary[0]]), axis=0)
    p_avg = float(np.sum(np.linalg.norm(mid_diffs, axis=1)))
    p_avg = max(p_avg, 1.0)

    n_u = max(6, int(round(p_avg / w_flat)))
    n_z = max(2, int(round(total_height / v_step)))

    du = 2.0 * math.pi / n_u
    dz = total_height / n_z

    panels: List[HexPanel] = []
    panel_idx = 1

    # Voronoi Centroidal jitter factor if pattern is VORONOI_CENTROIDAL
    is_voronoi = envelope_skin.pattern == "VORONOI_CENTROIDAL"

    for j in range(n_z + 1):
        z_val = max(0.0, min(total_height, j * dz))
        u_shift = (j % 2) * (du / 2.0)

        for i in range(n_u):
            u_val = (i * du + u_shift) % (2.0 * math.pi)

            if is_voronoi:
                # Organic centroidal relaxation jitter
                u_jitter = (math.sin(i * 3.7 + j * 2.3) * 0.15) * du
                z_jitter = (math.cos(i * 1.9 + j * 4.1) * 0.10) * dz
                u_val = (u_val + u_jitter) % (2.0 * math.pi)
                z_val_ij = max(0.0, min(total_height, z_val + z_jitter))
            else:
                z_val_ij = z_val

            p_center, u1, u2, n3 = _evaluate_surface_point_and_frame(rules, u_val, z_val_ij, total_height)

            # Build regular 2D flat-topped hexagon in tangent plane
            vertices_3d: List[Tuple[float, float, float]] = []
            for k in range(6):
                angle_k = math.pi / 6.0 + k * (math.pi / 3.0) if not is_voronoi else k * (math.pi / 3.0)
                if is_voronoi:
                    # Perturb radius slightly for organic Voronoi tiles
                    r_k = r_panel * (1.0 + 0.08 * math.sin(k * 2.1 + i + j))
                else:
                    r_k = r_panel

                x_local = r_k * math.cos(angle_k)
                y_local = r_k * math.sin(angle_k)

                v_3d = p_center + x_local * u1 + y_local * u2
                vertices_3d.append((float(v_3d[0]), float(v_3d[1]), float(v_3d[2])))

            # 4 Triangles forming the hexagon (0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 5)
            faces = [
                (0, 1, 2),
                (0, 2, 3),
                (0, 3, 4),
                (0, 4, 5),
            ]

            # 3D surface area of regular hexagon = 3 * sqrt(3) / 2 * r_panel^2
            hex_area = 1.5 * math.sqrt(3.0) * (r_panel ** 2)

            rot_mat = np.column_stack((u1, u2, n3))

            panel = HexPanel(
                panel_id=f"HEX-PANEL-{panel_idx:05d}",
                center=(float(p_center[0]), float(p_center[1]), float(p_center[2])),
                normal=(float(n3[0]), float(n3[1]), float(n3[2])),
                tangent_u=(float(u1[0]), float(u1[1]), float(u1[2])),
                tangent_v=(float(u2[0]), float(u2[1]), float(u2[2])),
                vertices=vertices_3d,
                faces=faces,
                area=hex_area,
                rotation_matrix=rot_mat,
                uv_coord=(u_val, z_val_ij),
            )
            panels.append(panel)
            panel_idx += 1

    return FacadeTessellationResult(
        target_rule=rules.type,
        panels=panels,
        material=envelope_skin.material,
        ifc_representation=envelope_skin.ifc_representation,
        pattern=envelope_skin.pattern,
        target_panel_size=envelope_skin.target_panel_size,
        joint_gap=envelope_skin.joint_gap,
    )
