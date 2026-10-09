"""
Procedural 3D Curve Sweeper and Frenet-Serret Frame Engine for IFC4.3 Alignments.
Supports linear tangents, circular arcs, clothoid spirals, vertical parabolic curves,
cant superelevations, and arbitrary cross-section corridor sweeping.
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union

from debim.schema import (
    AlignmentCantSegment,
    AlignmentHorizontalSegment,
    AlignmentPoint,
    AlignmentVerticalSegment,
    CorridorCrossSection,
    IfcAlignment,
)


def numerical_integration_clothoid(
    x0: float,
    y0: float,
    theta0: float,
    kappa0: float,
    kappa1: float,
    length: float,
    s_eval: float,
    n_steps: int = 20,
) -> Tuple[float, float, float]:
    """
    Numerically integrates position (x, y) and heading theta along a clothoid spiral segment.
    kappa(s) = kappa0 + (kappa1 - kappa0) * (s / length)
    theta(s) = theta0 + kappa0 * s + (kappa1 - kappa0) * s^2 / (2 * length)
    """
    if s_eval <= 0.0:
        return x0, y0, theta0

    # Simpson's 3/8 rule or trapezoidal integration over n_steps
    ds = s_eval / float(n_steps)
    curr_x = x0
    curr_y = y0

    def heading(s_val: float) -> float:
        if length > 1e-9:
            return theta0 + kappa0 * s_val + (kappa1 - kappa0) * (s_val ** 2) / (2.0 * length)
        return theta0 + kappa0 * s_val

    for i in range(n_steps):
        s_mid = (i + 0.5) * ds
        th_mid = heading(s_mid)
        curr_x += math.cos(th_mid) * ds
        curr_y += math.sin(th_mid) * ds

    th_final = heading(s_eval)
    return curr_x, curr_y, th_final


class AlignmentSweeper:
    def __init__(self, alignment: IfcAlignment):
        self.alignment = alignment
        self.horizontal_segments: List[AlignmentHorizontalSegment] = []
        self.vertical_segments: List[AlignmentVerticalSegment] = []
        self.cant_segments: List[AlignmentCantSegment] = []
        self.cross_sections: List[CorridorCrossSection] = []

        self._build_alignment_definition()

    def _build_alignment_definition(self):
        """Constructs explicit horizontal, vertical, cant, and cross section components."""
        # 1. Horizontal definition
        if self.alignment.horizontal and self.alignment.horizontal.segments:
            self.horizontal_segments = list(self.alignment.horizontal.segments)
        else:
            # Construct from placement points
            pts = self.alignment.placement.points if self.alignment.placement else []
            if len(pts) >= 2:
                self.horizontal_segments = self._pts_to_horizontal_segments(pts)
            else:
                # Default 100m straight alignment
                self.horizontal_segments = [
                    AlignmentHorizontalSegment(
                        segment_type="LINE",
                        start_point=(0.0, 0.0),
                        start_direction=0.0,
                        segment_length=100.0,
                    )
                ]

        # 2. Vertical definition
        if self.alignment.vertical and self.alignment.vertical.segments:
            self.vertical_segments = list(self.alignment.vertical.segments)
        else:
            # Build vertical definition from points or horizontal length
            pts = self.alignment.placement.points if self.alignment.placement else []
            tot_h_len = sum(s.segment_length for s in self.horizontal_segments)
            if len(pts) >= 2:
                self.vertical_segments = self._pts_to_vertical_segments(pts, tot_h_len)
            else:
                self.vertical_segments = [
                    AlignmentVerticalSegment(
                        segment_type="LINE",
                        start_dist_along=0.0,
                        horizontal_length=tot_h_len,
                        start_height=0.0,
                        start_gradient=0.0,
                    )
                ]

        # 3. Cant definition
        if self.alignment.cant and self.alignment.cant.segments:
            self.cant_segments = list(self.alignment.cant.segments)
        else:
            tot_h_len = sum(s.segment_length for s in self.horizontal_segments)
            self.cant_segments = [
                AlignmentCantSegment(
                    segment_type="CONSTANTCANT",
                    start_dist_along=0.0,
                    horizontal_length=tot_h_len,
                    start_cant=0.0,
                )
            ]

        # 4. Cross Sections definition
        if self.alignment.cross_sections:
            self.cross_sections = list(self.alignment.cross_sections)
        else:
            # Default carriageway cross-section
            self.cross_sections = [
                CorridorCrossSection(
                    name="carriageway",
                    points=[(-3.5, 0.0), (3.5, 0.0), (3.5, -0.30), (-3.5, -0.30)],
                    material=getattr(self.alignment, "material", None),
                )
            ]

    def _pts_to_horizontal_segments(
        self, pts: List[AlignmentPoint]
    ) -> List[AlignmentHorizontalSegment]:
        segments = []
        curr_x, curr_y = pts[0].x, pts[0].y
        for i in range(len(pts) - 1):
            p1 = pts[i]
            p2 = pts[i + 1]
            dx = p2.x - curr_x
            dy = p2.y - curr_y
            seg_len = math.hypot(dx, dy)
            if seg_len < 1e-6:
                continue

            heading = math.atan2(dy, dx)
            st_type = p2.segment_type.upper() if p2.segment_type else "LINE"

            if st_type == "ARC":
                # Estimate radius of circular arc
                r_val = seg_len / 2.0
                segments.append(
                    AlignmentHorizontalSegment(
                        segment_type="CIRCULARARC",
                        start_point=(curr_x, curr_y),
                        start_direction=heading,
                        start_radius_of_curvature=r_val,
                        end_radius_of_curvature=r_val,
                        segment_length=seg_len,
                    )
                )
            elif st_type == "CLOTHOID":
                # Clothoid spiral segment from infinity (r=0) to finite radius
                segments.append(
                    AlignmentHorizontalSegment(
                        segment_type="CLOTHOID",
                        start_point=(curr_x, curr_y),
                        start_direction=heading,
                        start_radius_of_curvature=0.0,
                        end_radius_of_curvature=seg_len * 2.0,
                        segment_length=seg_len,
                        clothoid_constant=math.sqrt(seg_len * seg_len * 2.0),
                    )
                )
            else:
                # LINE
                segments.append(
                    AlignmentHorizontalSegment(
                        segment_type="LINE",
                        start_point=(curr_x, curr_y),
                        start_direction=heading,
                        segment_length=seg_len,
                    )
                )
            curr_x, curr_y = p2.x, p2.y
        return segments

    def _pts_to_vertical_segments(
        self, pts: List[AlignmentPoint], total_h_len: float
    ) -> List[AlignmentVerticalSegment]:
        v_segs = []
        n = len(pts)
        cum_dist = 0.0
        for i in range(n - 1):
            p1 = pts[i]
            p2 = pts[i + 1]
            dx = p2.x - p1.x
            dy = p2.y - p1.y
            h_len = math.hypot(dx, dy)
            dz = p2.z - p1.z
            grad = dz / h_len if h_len > 1e-6 else 0.0
            st_type = p2.segment_type.upper() if p2.segment_type else "LINE"

            if st_type == "PARABOLA":
                v_segs.append(
                    AlignmentVerticalSegment(
                        segment_type="PARABOLA",
                        start_dist_along=cum_dist,
                        horizontal_length=h_len,
                        start_height=p1.z,
                        start_gradient=grad,
                        end_gradient=grad * 0.5,
                    )
                )
            else:
                v_segs.append(
                    AlignmentVerticalSegment(
                        segment_type="LINE",
                        start_dist_along=cum_dist,
                        horizontal_length=h_len,
                        start_height=p1.z,
                        start_gradient=grad,
                    )
                )
            cum_dist += h_len
        return v_segs

    def evaluate_horizontal(self, station: float) -> Tuple[float, float, float]:
        """Evaluates 2D horizontal position (x, y) and heading angle (radians) at station."""
        cum_len = 0.0
        for seg in self.horizontal_segments:
            seg_len = seg.segment_length
            if station <= cum_len + seg_len or seg == self.horizontal_segments[-1]:
                s_local = max(0.0, min(seg_len, station - cum_len))
                st_x, st_y = seg.start_point
                th0 = seg.start_direction

                if seg.segment_type == "LINE":
                    x = st_x + s_local * math.cos(th0)
                    y = st_y + s_local * math.sin(th0)
                    heading = th0
                    return x, y, heading

                elif seg.segment_type == "CIRCULARARC":
                    r = seg.start_radius_of_curvature
                    if abs(r) < 1e-6:
                        x = st_x + s_local * math.cos(th0)
                        y = st_y + s_local * math.sin(th0)
                        heading = th0
                    else:
                        kappa = 1.0 / r
                        heading = th0 + kappa * s_local
                        x = st_x + (math.sin(th0 + kappa * s_local) - math.sin(th0)) / kappa
                        y = st_y + (-math.cos(th0 + kappa * s_local) + math.cos(th0)) / kappa
                    return x, y, heading

                elif seg.segment_type == "CLOTHOID":
                    r0 = seg.start_radius_of_curvature
                    r1 = seg.end_radius_of_curvature
                    k0 = 1.0 / r0 if abs(r0) > 1e-6 else 0.0
                    k1 = 1.0 / r1 if abs(r1) > 1e-6 else 0.0
                    return numerical_integration_clothoid(
                        st_x, st_y, th0, k0, k1, seg_len, s_local
                    )

            cum_len += seg_len

        # Fallback end point
        last_seg = self.horizontal_segments[-1]
        st_x, st_y = last_seg.start_point
        th0 = last_seg.start_direction
        s_local = last_seg.segment_length
        return st_x + s_local * math.cos(th0), st_y + s_local * math.sin(th0), th0

    def evaluate_vertical(self, station: float) -> Tuple[float, float]:
        """Evaluates vertical elevation z and dz/ds gradient at station."""
        for seg in self.vertical_segments:
            s_start = seg.start_dist_along
            h_len = seg.horizontal_length
            if station <= s_start + h_len or seg == self.vertical_segments[-1]:
                s_local = max(0.0, min(h_len, station - s_start))
                g1 = seg.start_gradient
                z0 = seg.start_height

                if seg.segment_type == "LINE":
                    z = z0 + g1 * s_local
                    grad = g1
                    return z, grad

                elif seg.segment_type == "PARABOLA":
                    g2 = seg.end_gradient if seg.end_gradient is not None else g1
                    if h_len > 1e-6:
                        grad = g1 + (g2 - g1) * (s_local / h_len)
                        z = z0 + g1 * s_local + (g2 - g1) * (s_local ** 2) / (2.0 * h_len)
                    else:
                        grad = g1
                        z = z0 + g1 * s_local
                    return z, grad

                elif seg.segment_type == "CIRCULARARC":
                    r_v = seg.radius_of_curvature or 1000.0
                    grad = g1 + (s_local / r_v)
                    z = z0 + g1 * s_local + (s_local ** 2) / (2.0 * r_v)
                    return z, grad

        last_v = self.vertical_segments[-1]
        return last_v.start_height + last_v.start_gradient * last_v.horizontal_length, last_v.start_gradient

    def evaluate_cant(self, station: float) -> float:
        """Evaluates cant / superelevation roll angle (radians) at station."""
        for seg in self.cant_segments:
            s_start = seg.start_dist_along
            h_len = seg.horizontal_length
            if station <= s_start + h_len or seg == self.cant_segments[-1]:
                s_local = max(0.0, min(h_len, station - s_start))
                c1 = seg.start_cant
                if seg.segment_type == "CONSTANTCANT":
                    return c1
                elif seg.segment_type == "LINEARTRANSITION":
                    c2 = seg.end_cant if seg.end_cant is not None else c1
                    if h_len > 1e-6:
                        cant_val = c1 + (c2 - c1) * (s_local / h_len)
                    else:
                        cant_val = c1
                    return cant_val
        return 0.0

    def evaluate_frame(self, station: float) -> Dict[str, Any]:
        """
        Computes sequential 3D Frenet-Serret coordinate frame at station.
        Returns dict with position P, tangent T, normal N, binormal B, cant angle.
        """
        x, y, heading = self.evaluate_horizontal(station)
        z, gradient = self.evaluate_vertical(station)
        cant_val = self.evaluate_cant(station)

        # Pitch angle from gradient
        pitch = math.atan(gradient)

        # Unrotated 3D tangent vector
        tx = math.cos(heading) * math.cos(pitch)
        ty = math.sin(heading) * math.cos(pitch)
        tz = math.sin(pitch)
        t_len = math.sqrt(tx * tx + ty * ty + tz * tz)
        T = (tx / t_len, ty / t_len, tz / t_len) if t_len > 1e-9 else (1.0, 0.0, 0.0)

        # Base horizontal normal vector (lateral left offset)
        N_base = (-math.sin(heading), math.cos(heading), 0.0)

        # Base binormal vector (upward perpendicular to tangent and normal)
        # B_base = T x N_base
        bx = T[1] * N_base[2] - T[2] * N_base[1]
        by = T[2] * N_base[0] - T[0] * N_base[2]
        bz = T[0] * N_base[1] - T[1] * N_base[0]
        b_len = math.sqrt(bx * bx + by * by + bz * bz)
        B_base = (bx / b_len, by / b_len, bz / b_len) if b_len > 1e-9 else (0.0, 0.0, 1.0)

        # Apply roll/cant angle rotation around Tangent T
        # cant_val can be in meters (e.g. 0.10m elevation difference across 1.435m track or 7m road)
        # Convert cant value (meters over ~1.435m track or 7.0m road) to roll angle in radians
        track_width = 1.435 if "RAIL" in (self.alignment.predefined_type or "") else 7.0
        roll_angle = math.atan2(cant_val, track_width) if abs(cant_val) < 1.0 else cant_val

        cos_r = math.cos(roll_angle)
        sin_r = math.sin(roll_angle)

        Nx = cos_r * N_base[0] + sin_r * B_base[0]
        Ny = cos_r * N_base[1] + sin_r * B_base[1]
        Nz = cos_r * N_base[2] + sin_r * B_base[2]
        N = (Nx, Ny, Nz)

        Bx = -sin_r * N_base[0] + cos_r * B_base[0]
        By = -sin_r * N_base[1] + cos_r * B_base[1]
        Bz = -sin_r * N_base[2] + cos_r * B_base[2]
        B = (Bx, By, Bz)

        return {
            "station": station,
            "position": (x, y, z),
            "tangent": T,
            "normal": N,
            "binormal": B,
            "cant_angle": roll_angle,
        }

    def discretize_frames(self, step_size: float = 5.0) -> List[Dict[str, Any]]:
        """Discretizes alignment into sequential Frenet-Serret frames at step_size chainages."""
        total_len = sum(s.segment_length for s in self.horizontal_segments)
        if total_len <= 0.0:
            total_len = 100.0

        n_steps = max(2, int(math.ceil(total_len / step_size)) + 1)
        actual_step = total_len / float(n_steps - 1)

        frames = []
        for i in range(n_steps):
            s_val = min(total_len, i * actual_step)
            frames.append(self.evaluate_frame(s_val))
        return frames

    def sweep_corridor_solids(
        self, frames: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Sweeps cross-sections along sequential 3D coordinate frames.
        Returns list of solid dictionaries containing 3D mesh vertices and triangle face indices.
        """
        if frames is None:
            frames = self.discretize_frames()

        swept_solids = []

        for cs in self.cross_sections:
            cs_pts = cs.points
            if len(cs_pts) < 3:
                continue

            n_verts_per_frame = len(cs_pts)
            n_frames = len(frames)

            # Build 3D mesh vertices
            mesh_vertices: List[Tuple[float, float, float]] = []
            for frame in frames:
                px, py, pz = frame["position"]
                Nx, Ny, Nz = frame["normal"]
                Bx, By, Bz = frame["binormal"]

                for u, v in cs_pts:
                    vx = px + u * Nx + v * Bx
                    vy = py + u * Ny + v * By
                    vz = pz + u * Nz + v * Bz
                    mesh_vertices.append((round(vx, 6), round(vy, 6), round(vz, 6)))

            # Build 1-based triangle face indices for IfcTriangulatedFaceSet
            face_indices: List[Tuple[int, int, int]] = []

            # Longitudinal quad faces between frame k and frame k+1
            for k in range(n_frames - 1):
                base_curr = k * n_verts_per_frame
                base_next = (k + 1) * n_verts_per_frame

                for i in range(n_verts_per_frame):
                    i_next = (i + 1) % n_verts_per_frame

                    # 4 vertices of quad in 1-based indexing
                    v1 = base_curr + i + 1
                    v2 = base_curr + i_next + 1
                    v3 = base_next + i_next + 1
                    v4 = base_next + i + 1

                    # Split quad into 2 triangles
                    face_indices.append((v1, v2, v3))
                    face_indices.append((v1, v3, v4))

            # Start cap (frame 0) - triangulate polygon in reverse order
            for i in range(1, n_verts_per_frame - 1):
                face_indices.append((1, i + 2, i + 1))

            # End cap (frame n_frames - 1)
            end_base = (n_frames - 1) * n_verts_per_frame
            for i in range(1, n_verts_per_frame - 1):
                face_indices.append((end_base + 1, end_base + i + 1, end_base + i + 2))

            swept_solids.append(
                {
                    "name": cs.name,
                    "material": cs.material or getattr(self.alignment, "material", None),
                    "vertices": mesh_vertices,
                    "faces": face_indices,
                }
            )

        return swept_solids
