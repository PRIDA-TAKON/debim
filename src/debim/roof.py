"""L-shaped composite hip roof geometry and framing solver module for debim.

Provides 3D polygon ridge solver for non-convex L-shaped boundary polygons,
intersecting hips (สันตะเข้) and valleys (ตะเข้ราง) solver, multi-level eaves,
dual ridge heights, and structural rafter/purlin take-off synthesis.
"""

import math
from typing import Dict, List, Optional, Tuple, Any

from debim.schema import IfcRoof


def _calc_polygon_3d(pts: List[Tuple[float, float, float]]) -> Tuple[float, Tuple[float, float, float]]:
    """Calculates 3D surface area and normal vector for a planar polygon in 3D."""
    n = len(pts)
    if n < 3:
        return 0.0, (0.0, 0.0, 1.0)
    nx = 0.0
    ny = 0.0
    nz = 0.0
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        nx += (p1[1] * p2[2] - p1[2] * p2[1])
        ny += (p1[2] * p2[0] - p1[0] * p2[2])
        nz += (p1[0] * p2[1] - p1[1] * p2[0])
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    area = 0.5 * length
    if length > 1e-9:
        normal = (nx / length, ny / length, nz / length)
    else:
        normal = (0.0, 0.0, 1.0)
    return area, normal


def _offset_l_shape_2d(poly: List[Tuple[float, float]], offset: float) -> List[Tuple[float, float]]:
    """Offsets a 2D simple polygon (such as an L-shape) outwards by offset meters.

    Preserves vertex order and handles convex vs. re-entrant (concave) corners correctly.
    """
    n = len(poly)
    if n < 3 or abs(offset) < 1e-6:
        return list(poly)

    # Determine winding order (positive area = CCW)
    signed_area = 0.0
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        signed_area += (p1[0] * p2[1] - p2[0] * p1[1])
    is_ccw = signed_area > 0

    offset_lines = []
    for i in range(n):
        p1 = poly[i]
        p2 = poly[(i + 1) % n]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length < 1e-9:
            nx, ny = 0.0, 0.0
        else:
            if is_ccw:
                # Normal pointing right/outward for CCW
                nx, ny = dy / length, -dx / length
            else:
                # Normal pointing left/outward for CW
                nx, ny = -dy / length, dx / length

        line_p1 = (p1[0] + nx * offset, p1[1] + ny * offset)
        line_p2 = (p2[0] + nx * offset, p2[1] + ny * offset)
        offset_lines.append((line_p1, line_p2))

    # Intersect adjacent offset lines to find new vertices
    new_poly = []
    for i in range(n):
        l1 = offset_lines[(i - 1) % n]
        l2 = offset_lines[i]

        (x1, y1), (x2, y2) = l1
        (x3, y3), (x4, y4) = l2

        denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(denom) < 1e-9:
            new_poly.append(l2[0])
        else:
            ix = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
            iy = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
            new_poly.append((ix, iy))

    return new_poly


def solve_l_shape_roof(
    roof: IfcRoof,
    axes_x: Dict[str, float],
    axes_y: Dict[str, float],
    storey_elevation: float,
) -> Dict[str, Any]:
    """Solves geometry, 3D hip/valley intersections, sloped planes, and framing take-off

    for non-convex L-shaped composite roofs.
    """
    from debim.resolver import ResolvedRoofPlane, ResolvedRoofRidge, ResolvedRoofFramingMember

    # 1. Base coordinates & parameters
    boundary_pts = []
    for gx, gy in roof.placement.boundary:
        boundary_pts.append((axes_x[str(gx)], axes_y[str(gy)]))

    z0 = storey_elevation + roof.placement.offset_z
    pitch = roof.pitch_deg if roof.pitch_deg is not None else (roof.covering.pitch if roof.covering else 30.0)
    pitch_rad = math.radians(pitch)
    oh = roof.placement.overhang

    # Outward eave overhang offset
    eave_poly_2d = _offset_l_shape_2d(boundary_pts, oh)

    # Eaves levels mapping or single porch eave level
    porch_eave_dz = roof.placement.porch_eaves_level or 0.0
    eaves_levels = roof.placement.eaves_levels or {}

    # Assign 3D elevations to footprint polygon
    footprint_polygon_3d: List[Tuple[float, float, float]] = []
    for idx, (x, y) in enumerate(eave_poly_2d):
        key = f"P{idx+1}"
        e_z = z0 + eaves_levels.get(key, eaves_levels.get(str(idx), 0.0))
        footprint_polygon_3d.append((x, y, e_z))

    # 2. Decompose L-shape into Main Wing and Porch Wing
    xs = [p[0] for p in boundary_pts]
    ys = [p[1] for p in boundary_pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    # Find internal re-entrant (concave) corner
    n_pts = len(boundary_pts)
    reentrant_idx = -1
    for i in range(n_pts):
        p_prev = boundary_pts[(i - 1) % n_pts]
        p_curr = boundary_pts[i]
        p_next = boundary_pts[(i + 1) % n_pts]

        v1 = (p_curr[0] - p_prev[0], p_curr[1] - p_prev[1])
        v2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])
        cross = v1[0] * v2[1] - v1[1] * v2[0]

        # In CCW winding, re-entrant corner has negative cross product (right turn)
        # Check signed area to know CCW vs CW
        signed_area = sum(boundary_pts[k][0] * boundary_pts[(k+1)%n_pts][1] - boundary_pts[(k+1)%n_pts][0] * boundary_pts[k][1] for k in range(n_pts))
        if (signed_area > 0 and cross < -1e-4) or (signed_area < 0 and cross > 1e-4):
            reentrant_idx = i
            break

    if reentrant_idx == -1:
        # Fallback to simple bounding box if not 6-pt L-shape
        reentrant_idx = 0

    re_corner_2d = boundary_pts[reentrant_idx]
    re_eave_2d = eave_poly_2d[reentrant_idx]

    # Decompose into Main Wing (larger rectangle) and Porch Wing
    # For standard L-shape, re-entrant corner splits X and Y ranges
    rx, ry = re_corner_2d

    # Main Wing vs Porch Wing bounding boxes
    # Determine orientation of wings
    dx_range = max_x - min_x
    dy_range = max_y - min_y

    # Main rectangle bounding box
    if rx in (min_x, max_x):
        # Porch extends along Y
        main_x0, main_x1 = min_x, max_x
        if ry > (min_y + max_y) / 2.0:
            main_y0, main_y1 = min_y, ry
            porch_y0, porch_y1 = ry, max_y
        else:
            main_y0, main_y1 = ry, max_y
            porch_y0, porch_y1 = min_y, ry

        # Porch X span
        porch_x0 = min_x if abs(rx - max_x) < 1e-3 else rx
        porch_x1 = rx if abs(rx - max_x) < 1e-3 else max_x
    else:
        # Porch extends along X
        main_y0, main_y1 = min_y, max_y
        if rx > (min_x + max_x) / 2.0:
            main_x0, main_x1 = min_x, rx
            porch_x0, porch_x1 = rx, max_x
        else:
            main_x0, main_x1 = rx, max_x
            porch_x0, porch_x1 = min_x, rx

        porch_y0 = min_y if abs(ry - max_y) < 1e-3 else ry
        porch_y1 = ry if abs(ry - max_y) < 1e-3 else max_y

    # Overhang extended wing bounding boxes
    m_x0, m_x1 = main_x0 - oh, main_x1 + oh
    m_y0, m_y1 = main_y0 - oh, main_y1 + oh
    p_x0, p_x1 = porch_x0 - oh, porch_x1 + oh
    p_y0, p_y1 = porch_y0 - oh, porch_y1 + oh

    # 3. Ridge Heights & Elevations
    m_width = m_x1 - m_x0 if (main_x1 - main_x0) < (main_y1 - main_y0) else (main_y1 - m_y0)
    p_width = (porch_x1 - porch_x0) if (porch_x1 - porch_x0) < (porch_y1 - porch_y0) else (porch_y1 - porch_y0)

    z_eave_main = z0
    z_eave_porch = z0 + porch_eave_dz

    if roof.placement.main_ridge_height is not None:
        zr_main = z0 + roof.placement.main_ridge_height
    else:
        zr_main = z_eave_main + (m_width / 2.0) * math.tan(pitch_rad)

    if roof.placement.porch_ridge_height is not None:
        zr_porch = z0 + roof.placement.porch_ridge_height
    else:
        zr_porch = z_eave_porch + (p_width / 2.0) * math.tan(pitch_rad)

    eaves_elevation = min(z_eave_main, z_eave_porch)
    ridge_elevation = max(zr_main, zr_porch)

    planes: List[ResolvedRoofPlane] = []
    ridges: List[ResolvedRoofRidge] = []
    framing_members: List[ResolvedRoofFramingMember] = []

    # 4. Construct 3D Ridge, Valley, and Hip Lines
    # Determine main ridge endpoints
    if (main_x1 - main_x0) >= (main_y1 - main_y0):
        # Main ridge along X
        y_m_mid = (m_y0 + m_y1) / 2.0
        mr_start = (m_x0 + m_width / 2.0, y_m_mid, zr_main)
        mr_end = (m_x1 - m_width / 2.0, y_m_mid, zr_main)
    else:
        # Main ridge along Y
        x_m_mid = (m_x0 + m_x1) / 2.0
        mr_start = (x_m_mid, m_y0 + m_width / 2.0, zr_main)
        mr_end = (x_m_mid, m_y1 - m_width / 2.0, zr_main)

    m_ridge_len = math.dist(mr_start, mr_end)
    if m_ridge_len > 0.01:
        ridges.append(ResolvedRoofRidge(
            tag=f"{roof.tag}-MainRidge",
            start_point=mr_start,
            end_point=mr_end,
            length=m_ridge_len,
            ridge_type="RIDGE",
        ))

    # Porch ridge line & Valley intersection point
    # Re-entrant eave corner in 3D
    ex, ey = re_eave_2d
    re_eave_3d = (ex, ey, z_eave_main)

    # Valley top intersection (where porch roof meets main roof)
    # Direction of valley from re-entrant corner towards main ridge
    vx_dir = 1.0 if ex < (m_x0 + m_x1) / 2.0 else -1.0
    vy_dir = 1.0 if ey < (m_y0 + m_y1) / 2.0 else -1.0

    # Valley top point at porch ridge or main slope intersection
    v_top_x = ex + vx_dir * (p_width / 2.0)
    v_top_y = ey + vy_dir * (p_width / 2.0)
    v_top_z = zr_porch
    v_top_3d = (v_top_x, v_top_y, v_top_z)

    # Valley line (ตะเข้ราง)
    v_len = math.dist(re_eave_3d, v_top_3d)
    ridges.append(ResolvedRoofRidge(
        tag=f"{roof.tag}-Valley-1",
        start_point=re_eave_3d,
        end_point=v_top_3d,
        length=v_len,
        ridge_type="VALLEY",
    ))

    # Porch ridge line extending from porch end up to valley top or main ridge
    if (porch_x1 - porch_x0) > (porch_y1 - porch_y0):
        # Porch along X
        pr_start = (p_x0 + p_width / 2.0 if p_x0 < ex else p_x1 - p_width / 2.0, (p_y0 + p_y1) / 2.0, zr_porch)
        pr_end = v_top_3d
    else:
        # Porch along Y
        pr_start = ((p_x0 + p_x1) / 2.0, p_y0 + p_width / 2.0 if p_y0 < ey else p_y1 - p_width / 2.0, zr_porch)
        pr_end = v_top_3d

    p_ridge_len = math.dist(pr_start, pr_end)
    if p_ridge_len > 0.01:
        ridges.append(ResolvedRoofRidge(
            tag=f"{roof.tag}-PorchRidge",
            start_point=pr_start,
            end_point=pr_end,
            length=p_ridge_len,
            ridge_type="RIDGE",
        ))

    # Secondary valley if porch ridge height is lower than main ridge height
    if zr_porch < zr_main - 0.01:
        # Extension valley from v_top_3d up to main ridge
        v2_end = (v_top_x + vx_dir * (zr_main - zr_porch) / math.tan(pitch_rad),
                  v_top_y + vy_dir * (zr_main - zr_porch) / math.tan(pitch_rad),
                  zr_main)
        v2_len = math.dist(v_top_3d, v2_end)
        ridges.append(ResolvedRoofRidge(
            tag=f"{roof.tag}-Valley-2",
            start_point=v_top_3d,
            end_point=v2_end,
            length=v2_len,
            ridge_type="VALLEY",
        ))

    # Hips (สันตะเข้) from the 5 convex corners of the L-shape
    convex_hips = []
    for idx, pt3d in enumerate(footprint_polygon_3d):
        if idx == reentrant_idx:
            continue  # Re-entrant corner has valley, not hip

        # Connect to closest ridge endpoint
        candidate_ridge_pts = [mr_start, mr_end, pr_start]
        best_r = min(candidate_ridge_pts, key=lambda rp: math.dist(pt3d, rp))

        h_tag = f"Hip-C{idx+1}"
        h_len = math.dist(pt3d, best_r)
        ridges.append(ResolvedRoofRidge(
            tag=f"{roof.tag}-{h_tag}",
            start_point=pt3d,
            end_point=best_r,
            length=h_len,
            ridge_type="HIP",
        ))

    # Eaves perimeter ridges
    n_fp = len(footprint_polygon_3d)
    for i in range(n_fp):
        e_s = footprint_polygon_3d[i]
        e_e = footprint_polygon_3d[(i + 1) % n_fp]
        ridges.append(ResolvedRoofRidge(
            tag=f"{roof.tag}-Eave-{i+1}",
            start_point=e_s,
            end_point=e_e,
            length=math.dist(e_s, e_e),
            ridge_type="EAVE",
        ))

    # 5. Roof Planes (Sloped Facets)
    # Create sloped planes for Main Wing and Porch Wing
    # Main Wing Slopes
    m_p1 = [footprint_polygon_3d[0], footprint_polygon_3d[1], mr_start]
    m_p2 = [footprint_polygon_3d[1], footprint_polygon_3d[2], mr_end, mr_start] if m_ridge_len > 0.01 else [footprint_polygon_3d[1], footprint_polygon_3d[2], mr_start]
    m_p3 = [footprint_polygon_3d[2], footprint_polygon_3d[3], mr_end]
    m_p4 = [footprint_polygon_3d[3], footprint_polygon_3d[4], mr_start, mr_end] if m_ridge_len > 0.01 else [footprint_polygon_3d[3], footprint_polygon_3d[4], mr_start]

    for p_idx, poly in enumerate([m_p1, m_p2, m_p3, m_p4]):
        area, normal = _calc_polygon_3d(poly)
        planes.append(ResolvedRoofPlane(
            tag=f"{roof.tag}-MainSlope-{p_idx+1}",
            polygon=poly,
            area=area,
            slope_degrees=pitch,
            normal=normal,
        ))

    # Porch Wing Slopes
    p_p1 = [re_eave_3d, v_top_3d, pr_start]
    p_p2 = [footprint_polygon_3d[(reentrant_idx + 1) % n_fp], footprint_polygon_3d[(reentrant_idx + 2) % n_fp], pr_start, v_top_3d]

    for p_idx, poly in enumerate([p_p1, p_p2]):
        area, normal = _calc_polygon_3d(poly)
        planes.append(ResolvedRoofPlane(
            tag=f"{roof.tag}-PorchSlope-{p_idx+1}",
            polygon=poly,
            area=area,
            slope_degrees=pitch,
            normal=normal,
        ))

    # 6. Roof Framing Synthesis
    f_mat = roof.framing.material if roof.framing else "STEEL_SS400"
    profiles_dict = roof.framing.profiles if (roof.framing and roof.framing.profiles and isinstance(roof.framing.profiles, dict)) else {}
    raf_prof = profiles_dict.get("rafter", "C100x50x20x3.2")
    pur_prof = profiles_dict.get("purlin", "C75x45x15x2.3")
    ridge_prof = profiles_dict.get("ridge", "2C150x50x20x3.2")
    hip_prof = profiles_dict.get("hip", "2C150x50x20x3.2")
    valley_prof = profiles_dict.get("valley", "2C150x50x20x3.2")
    wp_prof = profiles_dict.get("wall_plate", "C150x50x20x3.2")

    # Wall Plates (อะเส)
    for i in range(n_fp):
        e_s = footprint_polygon_3d[i]
        e_e = footprint_polygon_3d[(i + 1) % n_fp]
        framing_members.append(ResolvedRoofFramingMember(
            tag=f"{roof.tag}-WallPlate-{i+1}",
            member_type="WALL_PLATE",
            name_th="อะเส (Wall Plate)",
            start_point=e_s,
            end_point=e_e,
            length=math.dist(e_s, e_e),
            color="#3B82F6",
            material=f_mat,
            profile=wp_prof,
        ))

    # Ridge Beams, Hip Rafters, Valley Rafters, King Posts, Tie Beams
    for r in ridges:
        if r.ridge_type == "RIDGE":
            framing_members.append(ResolvedRoofFramingMember(
                tag=f"{r.tag}-Beam",
                member_type="RIDGE_BEAM",
                name_th="อกไก่ (Ridge Beam)",
                start_point=r.start_point,
                end_point=r.end_point,
                length=r.length,
                color="#EF4444",
                material=f_mat,
                profile=ridge_prof,
            ))
            # King Post at start point
            framing_members.append(ResolvedRoofFramingMember(
                tag=f"{r.tag}-KingPost-1",
                member_type="KING_POST",
                name_th="เสาดั้ง (King Post)",
                start_point=(r.start_point[0], r.start_point[1], z0),
                end_point=r.start_point,
                length=max(0.1, r.start_point[2] - z0),
                color="#A855F7",
                material=f_mat,
                profile="2C100x50x20x3.2",
            ))
            if r.length > 0.01:
                framing_members.append(ResolvedRoofFramingMember(
                    tag=f"{r.tag}-KingPost-2",
                    member_type="KING_POST",
                    name_th="เสาดั้ง (King Post)",
                    start_point=(r.end_point[0], r.end_point[1], z0),
                    end_point=r.end_point,
                    length=max(0.1, r.end_point[2] - z0),
                    color="#A855F7",
                    material=f_mat,
                    profile="2C100x50x20x3.2",
                ))
                framing_members.append(ResolvedRoofFramingMember(
                    tag=f"{r.tag}-TieBeam",
                    member_type="TIE_BEAM",
                    name_th="ขื่อ (Tie Beam)",
                    start_point=(r.start_point[0], r.start_point[1], z0),
                    end_point=(r.end_point[0], r.end_point[1], z0),
                    length=r.length,
                    color="#6366F1",
                    material=f_mat,
                    profile="2C125x50x20x3.2",
                ))
        elif r.ridge_type == "HIP":
            framing_members.append(ResolvedRoofFramingMember(
                tag=r.tag.replace("Roof", "HipRafter"),
                member_type="HIP_RAFTER",
                name_th="ตะเข้สัน (Hip Rafter)",
                start_point=r.start_point,
                end_point=r.end_point,
                length=r.length,
                color="#F59E0B",
                material=f_mat,
                profile=hip_prof,
            ))
        elif r.ridge_type == "VALLEY":
            framing_members.append(ResolvedRoofFramingMember(
                tag=r.tag.replace("Roof", "ValleyRafter"),
                member_type="VALLEY_RAFTER",
                name_th="ตะเข้ราง (Valley Rafter)",
                start_point=r.start_point,
                end_point=r.end_point,
                length=r.length,
                color="#10B981",
                material=f_mat,
                profile=valley_prof,
            ))

    # Common & Jack Rafters along sloped planes
    r_spacing = roof.framing.rafter_spacing if (roof.framing and roof.framing.rafter_spacing) else (roof.framing.spacing if roof.framing else 1.0)
    raf_idx = 1
    for plane in planes:
        poly = plane.polygon
        poly_xs = [p[0] for p in poly]
        poly_ys = [p[1] for p in poly]
        min_px, max_px = min(poly_xs), max(poly_xs)
        min_py, max_py = min(poly_ys), max(poly_ys)

        nx, ny, nz = plane.normal
        if abs(nx) > abs(ny):
            y_curr = min_py + r_spacing
            while y_curr < max_py - 0.2:
                x_pts = []
                n_p = len(poly)
                for i in range(n_p):
                    p_a = poly[i]
                    p_b = poly[(i + 1) % n_p]
                    if (p_a[1] <= y_curr <= p_b[1]) or (p_b[1] <= y_curr <= p_a[1]):
                        if abs(p_b[1] - p_a[1]) > 1e-4:
                            t = (y_curr - p_a[1]) / (p_b[1] - p_a[1])
                            ix = p_a[0] + t * (p_b[0] - p_a[0])
                            iz = p_a[2] + t * (p_b[2] - p_a[2])
                            x_pts.append((ix, y_curr, iz))
                if len(x_pts) >= 2:
                    x_pts.sort(key=lambda p: p[0])
                    p_start = x_pts[0]
                    p_end = x_pts[-1]
                    l_raf = math.dist(p_start, p_end)
                    if l_raf > 0.3:
                        framing_members.append(ResolvedRoofFramingMember(
                            tag=f"{roof.tag}-Rafter-{raf_idx}",
                            member_type="COMMON_RAFTER" if l_raf > (m_width / 2.0 / math.cos(pitch_rad) - 0.5) else "JACK_RAFTER",
                            name_th="จันทัน (Rafter)",
                            start_point=p_start,
                            end_point=p_end,
                            length=l_raf,
                            color="#10B981",
                            material=f_mat,
                            profile=raf_prof,
                        ))
                        raf_idx += 1
                y_curr += r_spacing
        else:
            x_curr = min_px + r_spacing
            while x_curr < max_px - 0.2:
                y_pts = []
                n_p = len(poly)
                for i in range(n_p):
                    p_a = poly[i]
                    p_b = poly[(i + 1) % n_p]
                    if (p_a[0] <= x_curr <= p_b[0]) or (p_b[0] <= x_curr <= p_a[0]):
                        if abs(p_b[0] - p_a[0]) > 1e-4:
                            t = (x_curr - p_a[0]) / (p_b[0] - p_a[0])
                            iy = p_a[1] + t * (p_b[1] - p_a[1])
                            iz = p_a[2] + t * (p_b[2] - p_a[2])
                            y_pts.append((x_curr, iy, iz))
                if len(y_pts) >= 2:
                    y_pts.sort(key=lambda p: p[1])
                    p_start = y_pts[0]
                    p_end = y_pts[-1]
                    l_raf = math.dist(p_start, p_end)
                    if l_raf > 0.3:
                        framing_members.append(ResolvedRoofFramingMember(
                            tag=f"{roof.tag}-Rafter-{raf_idx}",
                            member_type="COMMON_RAFTER" if l_raf > (m_width / 2.0 / math.cos(pitch_rad) - 0.5) else "JACK_RAFTER",
                            name_th="จันทัน (Rafter)",
                            start_point=p_start,
                            end_point=p_end,
                            length=l_raf,
                            color="#10B981",
                            material=f_mat,
                            profile=raf_prof,
                        ))
                        raf_idx += 1
                x_curr += r_spacing

    # Purlins (แป)
    p_spacing = roof.framing.purlin_spacing if (roof.framing and roof.framing.purlin_spacing) else 0.32
    pur_idx = 1
    for plane in planes:
        poly = plane.polygon
        poly_zs = [p[2] for p in poly]
        min_pz, max_pz = min(poly_zs), max(poly_zs)
        z_curr = min_pz + p_spacing * math.sin(pitch_rad)
        while z_curr < max_pz - 0.05:
            pur_pts = []
            n_p = len(poly)
            for i in range(n_p):
                p_a = poly[i]
                p_b = poly[(i + 1) % n_p]
                if (p_a[2] <= z_curr <= p_b[2]) or (p_b[2] <= z_curr <= p_a[2]):
                    if abs(p_b[2] - p_a[2]) > 1e-4:
                        t = (z_curr - p_a[2]) / (p_b[2] - p_a[2])
                        ix = p_a[0] + t * (p_b[0] - p_a[0])
                        iy = p_a[1] + t * (p_b[1] - p_a[1])
                        pur_pts.append((ix, iy, z_curr))
            if len(pur_pts) >= 2:
                pur_pts.sort(key=lambda p: (p[0], p[1]))
                p_s = pur_pts[0]
                p_e = pur_pts[-1]
                l_pur = math.dist(p_s, p_e)
                if l_pur > 0.3:
                    framing_members.append(ResolvedRoofFramingMember(
                        tag=f"{roof.tag}-Purlin-{pur_idx}",
                        member_type="PURLIN",
                        name_th="แป (Purlin)",
                        start_point=p_s,
                        end_point=p_e,
                        length=l_pur,
                        color="#EAB308",
                        material=f_mat,
                        profile=pur_prof,
                    ))
                    pur_idx += 1
            z_curr += p_spacing * math.sin(pitch_rad)

    # Calculate L-shape footprint area via Shoelace formula
    fp_area = 0.5 * abs(sum(eave_poly_2d[i][0] * eave_poly_2d[(i+1)%n_fp][1] - eave_poly_2d[(i+1)%n_fp][0] * eave_poly_2d[i][1] for i in range(n_fp)))
    tot_sloped_area = sum(p.area for p in planes)
    tot_ridge_len = sum(r.length for r in ridges if r.ridge_type == "RIDGE")
    tot_hip_len = sum(r.length for r in ridges if r.ridge_type == "HIP")
    tot_valley_len = sum(r.length for r in ridges if r.ridge_type == "VALLEY")
    tot_eaves_len = sum(r.length for r in ridges if r.ridge_type == "EAVE")

    steel_rate = roof.framing.steel_weight_per_sqm if roof.framing else 18.0
    tot_steel = fp_area * steel_rate

    return {
        "roof_type": roof.roof_type if roof.roof_type in ("L_SHAPE", "L_SHAPE_HIP") else "L_SHAPE_HIP",
        "pitch": pitch,
        "eaves_elevation": eaves_elevation,
        "ridge_elevation": ridge_elevation,
        "footprint_polygon": footprint_polygon_3d,
        "planes": planes,
        "ridges": ridges,
        "framing_members": framing_members,
        "total_footprint_area": fp_area,
        "total_sloped_area": tot_sloped_area,
        "total_ridge_length": tot_ridge_len,
        "total_hip_length": tot_hip_len,
        "total_valley_length": tot_valley_len,
        "total_eaves_length": tot_eaves_len,
        "total_steel_weight": tot_steel,
    }
