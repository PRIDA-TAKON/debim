"""
Automated Penetration Sleeve Generation Module for MEP Systems.
Detects 3D pipe centerline intersections with IfcSlab, IfcWall, and IfcBeam elements,
and generates protective sleeves (IfcBuildingElementProxy) with 25mm clearance offsets and host cutouts.
"""

from typing import List, Tuple, Dict, Any, Optional
import math
from debim.compat import BaseModel, Field, ConfigDict
from debim.geometry2d import point_in_polygon


class PenetrationSleeve(BaseModel):
    """Data model representing an auto-generated MEP penetration sleeve."""
    model_config = ConfigDict(extra="ignore")

    id: str
    pipe_tag: str
    host_tag: str
    host_class: str  # "IfcSlab", "IfcWall", "IfcBeam"
    intersection_point: Tuple[float, float, float]
    pipe_diameter: float
    sleeve_diameter: float  # pipe_diameter + 0.050m (25mm clearance offset on both sides)
    sleeve_length: float
    opening_element: Dict[str, Any]
    proxy_element: Dict[str, Any]


def _segment_intersects_z_plane(
    p1: Tuple[float, float, float],
    p2: Tuple[float, float, float],
    z_plane: float,
) -> Optional[Tuple[float, float, float]]:
    """Check if 3D segment p1 -> p2 intersects a horizontal Z plane."""
    z1, z2 = p1[2], p2[2]
    if (z1 <= z_plane <= z2) or (z2 <= z_plane <= z1):
        if abs(z2 - z1) < 1e-6:
            return None  # Parallel to plane
        t = (z_plane - z1) / (z2 - z1)
        x = p1[0] + t * (p2[0] - p1[0])
        y = p1[1] + t * (p2[1] - p1[1])
        return (x, y, z_plane)
    return None


def detect_penetration_sleeves(
    manifest: Any,
    resolved: Optional[Any] = None,
    clearance_offset: float = 0.025,  # 25mm clearance
) -> List[PenetrationSleeve]:
    """
    Detect all 3D centerline intersections between resolved pipes and structural elements
    (IfcSlab, IfcWall, IfcBeam) and generate protective penetration sleeves.
    """
    if resolved is None:
        from debim.resolver import SpatialResolver
        resolver = SpatialResolver(manifest)
        resolved = resolver.resolve()

    sleeves: List[PenetrationSleeve] = []
    sleeve_idx = 1

    pipes = getattr(resolved, "pipes", []) or []
    slabs = getattr(resolved, "slabs", []) or []
    walls = getattr(resolved, "walls", []) or []
    beams = getattr(resolved, "beams", []) or []

    # Default storey fallback if pipe placement storey is omitted
    default_storey = "L1"
    if hasattr(manifest, "spatial_structure") and manifest.spatial_structure and manifest.spatial_structure.storeys:
        default_storey = manifest.spatial_structure.storeys[0].id

    for pipe in pipes:
        pipe_tag = pipe.tag
        d_pipe = getattr(pipe, "nominal_diameter", 0.100) or 0.100
        d_sleeve = d_pipe + 2 * clearance_offset  # e.g. 100mm pipe -> 150mm sleeve
        waypoints = getattr(pipe, "waypoints", []) or []

        pipe_storey = getattr(getattr(pipe, "element", None), "placement", None)
        pipe_storey = getattr(pipe_storey, "storey", None) or default_storey

        if len(waypoints) < 2:
            continue

        for i in range(len(waypoints) - 1):
            p1 = waypoints[i]
            p2 = waypoints[i + 1]

            # 1. Check Slab Intersections
            for slab in slabs:
                thickness = getattr(slab, "thickness", 0.15) or 0.15
                top_z = getattr(slab, "elevation", 0.0) or 0.0
                bot_z = top_z - thickness
                mid_z = (top_z + bot_z) / 2.0

                int_pt = _segment_intersects_z_plane(p1, p2, mid_z)
                if int_pt is not None:
                    # Verify intersection point lies inside slab 2D boundary polygon
                    poly_raw = getattr(slab, "polygon", []) or getattr(slab, "boundary_points", []) or []
                    poly_2d = [(pt[0], pt[1]) for pt in poly_raw]
                    if poly_2d and point_in_polygon((int_pt[0], int_pt[1]), poly_2d):
                        s_id = f"SLEEVE-{sleeve_idx:03d}"
                        sleeve_idx += 1

                        opening = {
                            "class": "IfcOpeningElement",
                            "tag": f"OPENING-{pipe_tag}-{slab.tag}",
                            "host": slab.tag,
                            "shape": "CIRCULAR",
                            "diameter": d_sleeve,
                            "depth": thickness,
                            "position": int_pt,
                        }

                        proxy = {
                            "class": "IfcBuildingElementProxy",
                            "ifc_class": "IfcBuildingElementProxy",
                            "tag": f"SLEEVE-{pipe_tag}-{slab.tag}",
                            "predefined_type": "PROT_SLEEVE",
                            "material": "MAT_STEEL_SLEEVE",
                            "geometry": {
                                "cylinder": [d_sleeve / 2.0, thickness]
                            },
                            "placement": {
                                "storey": pipe_storey,
                                "position": int_pt,
                            },
                        }

                        sleeves.append(
                            PenetrationSleeve(
                                id=s_id,
                                pipe_tag=pipe_tag,
                                host_tag=slab.tag,
                                host_class="IfcSlab",
                                intersection_point=int_pt,
                                pipe_diameter=d_pipe,
                                sleeve_diameter=d_sleeve,
                                sleeve_length=thickness,
                                opening_element=opening,
                                proxy_element=proxy,
                            )
                        )

            # 2. Check Wall Intersections
            for wall in walls:
                thickness = getattr(wall, "thickness", 0.15) or 0.15
                height = getattr(wall, "height", 3.0) or 3.0
                w_p1 = getattr(wall, "start_point", (0, 0, 0))
                w_p2 = getattr(wall, "end_point", (0, 0, 0))

                xmin, xmax = min(w_p1[0], w_p2[0]) - thickness, max(w_p1[0], w_p2[0]) + thickness
                ymin, ymax = min(w_p1[1], w_p2[1]) - thickness, max(w_p1[1], w_p2[1]) + thickness
                zmin, zmax = w_p1[2], w_p1[2] + height

                if (
                    min(p1[0], p2[0]) <= xmax and max(p1[0], p2[0]) >= xmin and
                    min(p1[1], p2[1]) <= ymax and max(p1[1], p2[1]) >= ymin and
                    min(p1[2], p2[2]) <= zmax and max(p1[2], p2[2]) >= zmin
                ):
                    int_x = max(xmin, min(xmax, (p1[0] + p2[0]) / 2.0))
                    int_y = max(ymin, min(ymax, (p1[1] + p2[1]) / 2.0))
                    int_z = max(zmin, min(zmax, (p1[2] + p2[2]) / 2.0))
                    int_pt = (int_x, int_y, int_z)

                    s_id = f"SLEEVE-{sleeve_idx:03d}"
                    sleeve_idx += 1

                    opening = {
                        "class": "IfcOpeningElement",
                        "tag": f"OPENING-{pipe_tag}-{wall.tag}",
                        "host": wall.tag,
                        "shape": "CIRCULAR",
                        "diameter": d_sleeve,
                        "depth": thickness,
                        "position": int_pt,
                    }

                    proxy = {
                        "class": "IfcBuildingElementProxy",
                        "ifc_class": "IfcBuildingElementProxy",
                        "tag": f"SLEEVE-{pipe_tag}-{wall.tag}",
                        "predefined_type": "PROT_SLEEVE",
                        "material": "MAT_STEEL_SLEEVE",
                        "geometry": {
                            "cylinder": [d_sleeve / 2.0, thickness]
                        },
                        "placement": {
                            "storey": pipe_storey,
                            "position": int_pt,
                        },
                    }

                    sleeves.append(
                        PenetrationSleeve(
                            id=s_id,
                            pipe_tag=pipe_tag,
                            host_tag=wall.tag,
                            host_class="IfcWall",
                            intersection_point=int_pt,
                            pipe_diameter=d_pipe,
                            sleeve_diameter=d_sleeve,
                            sleeve_length=thickness,
                            opening_element=opening,
                            proxy_element=proxy,
                        )
                    )

            # 3. Check Beam Intersections
            for beam in beams:
                width = getattr(beam, "width", 0.20) or 0.20
                depth = getattr(beam, "depth", 0.40) or 0.40
                b_p1 = getattr(beam, "start_point", (0, 0, 0))
                b_p2 = getattr(beam, "end_point", (0, 0, 0))

                xmin, xmax = min(b_p1[0], b_p2[0]) - width/2.0, max(b_p1[0], b_p2[0]) + width/2.0
                ymin, ymax = min(b_p1[1], b_p2[1]) - width/2.0, max(b_p1[1], b_p2[1]) + width/2.0
                zmin, zmax = b_p1[2] - depth, b_p1[2]

                if (
                    min(p1[0], p2[0]) <= xmax and max(p1[0], p2[0]) >= xmin and
                    min(p1[1], p2[1]) <= ymax and max(p1[1], p2[1]) >= ymin and
                    min(p1[2], p2[2]) <= zmax and max(p1[2], p2[2]) >= zmin
                ):
                    int_x = max(xmin, min(xmax, (p1[0] + p2[0]) / 2.0))
                    int_y = max(ymin, min(ymax, (p1[1] + p2[1]) / 2.0))
                    int_z = max(zmin, min(zmax, (p1[2] + p2[2]) / 2.0))
                    int_pt = (int_x, int_y, int_z)

                    s_id = f"SLEEVE-{sleeve_idx:03d}"
                    sleeve_idx += 1

                    opening = {
                        "class": "IfcOpeningElement",
                        "tag": f"OPENING-{pipe_tag}-{beam.tag}",
                        "host": beam.tag,
                        "shape": "CIRCULAR",
                        "diameter": d_sleeve,
                        "depth": width,
                        "position": int_pt,
                    }

                    proxy = {
                        "class": "IfcBuildingElementProxy",
                        "ifc_class": "IfcBuildingElementProxy",
                        "tag": f"SLEEVE-{pipe_tag}-{beam.tag}",
                        "predefined_type": "PROT_SLEEVE",
                        "material": "MAT_STEEL_SLEEVE",
                        "geometry": {
                            "cylinder": [d_sleeve / 2.0, width]
                        },
                        "placement": {
                            "storey": pipe_storey,
                            "position": int_pt,
                        },
                    }

                    sleeves.append(
                        PenetrationSleeve(
                            id=s_id,
                            pipe_tag=pipe_tag,
                            host_tag=beam.tag,
                            host_class="IfcBeam",
                            intersection_point=int_pt,
                            pipe_diameter=d_pipe,
                            sleeve_diameter=d_sleeve,
                            sleeve_length=width,
                            opening_element=opening,
                            proxy_element=proxy,
                        )
                    )

    return sleeves
