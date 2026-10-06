"""
Lightweight 3D Web Viewer generator and local HTTP preview server for debim.
"""

import json
import math
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Union
import webbrowser

from debim.resolver import (
    ResolvedDoor,
    ResolvedManifest,
    ResolvedRevolvedArea,
    ResolvedSweptDisk,
    ResolvedWindow,
    resolve_manifest,
)
from debim.schema import ProjectManifest, load_manifest


def extract_profile_viewer_dim(prof: Any, length_or_height: float, is_column: bool = True) -> Dict[str, Any]:
    shape = getattr(prof, "shape", "BOX")
    len_key = "height" if is_column else "length"
    dim: Dict[str, Any] = {
        "shape": shape,
        len_key: length_or_height,
        "width": getattr(prof, "width", 0.3),
        "depth": getattr(prof, "depth", 0.3),
    }
    if shape == "CIRCULAR":
        dim["radius"] = prof.radius
        dim["diameter"] = prof.diameter
    elif shape == "ELLIPSE":
        dim["semi_major_axis"] = prof.semi_major_axis
        dim["semi_minor_axis"] = prof.semi_minor_axis
    elif shape in ("ISHAPE", "I", "H"):
        dim["overall_width"] = prof.overall_width
        dim["overall_depth"] = prof.overall_depth
        dim["web_thickness"] = prof.web_thickness
        dim["flange_thickness"] = prof.flange_thickness
        dim["width"] = prof.overall_width
        dim["depth"] = prof.overall_depth
    elif shape in ("LSHAPE", "L"):
        dim["width"] = prof.width
        dim["depth"] = prof.depth
        dim["thickness"] = prof.thickness
    elif shape in ("USHAPE", "U", "CSHAPE", "C"):
        dim["flange_width"] = prof.flange_width
        dim["depth"] = prof.depth
        dim["web_thickness"] = prof.web_thickness
        dim["flange_thickness"] = prof.flange_thickness
        dim["width"] = prof.flange_width
    elif shape in ("TSHAPE", "T"):
        dim["flange_width"] = prof.flange_width
        dim["depth"] = prof.depth
        dim["web_thickness"] = prof.web_thickness
        dim["flange_thickness"] = prof.flange_thickness
        dim["width"] = prof.flange_width
    elif shape in ("RHS", "RECTANGLE_HOLLOW", "BOX_HOLLOW"):
        dim["width"] = prof.width
        dim["depth"] = prof.depth
        dim["wall_thickness"] = prof.wall_thickness
    elif shape in ("CHS", "CIRCLE_HOLLOW", "PIPE_HOLLOW"):
        dim["radius"] = prof.radius
        dim["diameter"] = prof.diameter
        dim["wall_thickness"] = prof.wall_thickness
        dim["width"] = prof.diameter
        dim["depth"] = prof.diameter
    elif shape in ("ARBITRARY", "ARBITRARY_CLOSED", "POLYGON", "ARBITRARY_WITH_VOIDS"):
        dim["points"] = getattr(prof, "outer_curve", None) or getattr(prof, "points", None) or []
        dim["voids"] = getattr(prof, "inner_curves", None) or getattr(prof, "voids", None) or []
        dim["width"] = getattr(prof, "width", 0.3)
        dim["depth"] = getattr(prof, "depth", 0.3)
    return dim


def generate_viewer_html(
    manifest: Union[ProjectManifest, ResolvedManifest, Path, str]
) -> str:
    """
    Generate a self-contained, standalone 3D web viewer HTML string
    using CDN-hosted Three.js and OrbitControls with a Hierarchical Layer Explorer.
    """
    if isinstance(manifest, (str, Path)):
        manifest_obj = load_manifest(manifest)
        resolved = resolve_manifest(manifest_obj)
    elif isinstance(manifest, ProjectManifest):
        resolved = resolve_manifest(manifest)
    elif isinstance(manifest, ResolvedManifest):
        resolved = manifest
    else:
        raise TypeError(f"Unsupported manifest type: {type(manifest)}")

    proj = resolved.manifest.project
    storeys_data = [s.model_dump() for s in resolved.manifest.spatial_structure.storeys]
    grids_data = {
        "axes_x": resolved.manifest.grids.axes_x,
        "axes_y": resolved.manifest.grids.axes_y,
    }

    elements_data: List[Dict[str, Any]] = []

    # Footings & Piles
    for footing in resolved.footings:
        elements_data.append({
            "tag": footing.tag,
            "class": "IfcFooting",
            "material": footing.element.material,
            "position": [
                footing.position[0],
                footing.position[1],
                footing.position[2] + footing.thickness / 2.0,
            ],
            "rotation": [0, 0, 0],
            "dimensions": {
                "width": footing.width,
                "depth": footing.depth,
                "height": footing.thickness,
            },
            "color": "#6A6A6A",
            "layer": footing.layer,
        })

        for pile in footing.piles:
            elements_data.append({
                "tag": pile.tag,
                "class": "IfcPile",
                "material": pile.material or footing.element.material,
                "position": [
                    pile.position[0],
                    pile.position[1],
                    pile.position[2] - pile.length / 2.0,
                ],
                "rotation": [0, 0, 0],
                "dimensions": {
                    "width": pile.dimension,
                    "depth": pile.dimension,
                    "height": pile.length,
                },
                "color": "#4F4F4F",
                "layer": pile.layer,
            })

    # Columns
    for col in resolved.columns:
        prof = col.element.profile
        dim = extract_profile_viewer_dim(prof, col.height, is_column=True)

        cx = (col.start_point[0] + col.end_point[0]) / 2.0
        cy = (col.start_point[1] + col.end_point[1]) / 2.0
        cz = (col.start_point[2] + col.end_point[2]) / 2.0
        elements_data.append({
            "tag": col.tag,
            "class": "IfcColumn",
            "material": col.element.material,
            "position": [cx, cy, cz],
            "direction_vector_3d": col.direction_vector_3d,
            "dimensions": dim,
            "color": "#808080",
            "layer": col.layer,
        })

    # Beams
    for beam in resolved.beams:
        prof = beam.element.profile
        dim = extract_profile_viewer_dim(prof, beam.span_length, is_column=False)

        if beam.waypoints and len(beam.waypoints) > 2:
            elements_data.append({
                "tag": beam.tag,
                "class": "IfcBeam",
                "geometry_type": "line",
                "points": beam.waypoints,
                "color": "#9A9A9A",
                "linewidth": 4,
                "layer": beam.layer,
                "material": beam.element.material,
                "dimensions": dim,
            })
        else:
            cx = (beam.start_point[0] + beam.end_point[0]) / 2.0
            cy = (beam.start_point[1] + beam.end_point[1]) / 2.0
            cz = (beam.start_point[2] + beam.end_point[2]) / 2.0
            elements_data.append({
                "tag": beam.tag,
                "class": "IfcBeam",
                "material": beam.element.material,
                "position": [cx, cy, cz],
                "direction_vector_3d": beam.direction_vector_3d,
                "rotation": [0, 0, beam.rotation_angle],
                "dimensions": dim,
                "color": "#9A9A9A",
                "layer": beam.layer,
            })

    # Slabs
    for slab in resolved.slabs:
        xs = [pt[0] for pt in slab.polygon]
        ys = [pt[1] for pt in slab.polygon]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        w = max_x - min_x
        d = max_y - min_y
        h = slab.thickness
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        cz = slab.center[2] - h / 2.0

        elements_data.append({
            "tag": slab.tag,
            "class": "IfcSlab",
            "material": slab.element.material,
            "position": [cx, cy, cz],
            "rotation": [0, 0, 0],
            "dimensions": {
                "width": w,
                "depth": d,
                "height": h,
                "polygon": [[pt[0], pt[1]] for pt in slab.polygon],
                "voids": [[[pt[0], pt[1]] for pt in vloop] for vloop in getattr(slab, "voids", [])],
                "area": slab.area,
            },
            "color": "#A8B2C1",
            "transparent": True,
            "opacity": 0.85,
            "layer": slab.layer,
        })

    # Stairs Assembly
    for stair in resolved.stairs:
        for step in stair.steps:
            if getattr(step, "polygon", None) and len(step.polygon) >= 3:
                elements_data.append({
                    "tag": f"{stair.tag}-Step-{step.step_index}",
                    "class": "IfcStairStep",
                    "material": stair.element.finishes.tread_finish if (stair.element.finishes and stair.element.finishes.tread_finish) else stair.element.material,
                    "geometry_type": "polygon",
                    "points": step.polygon,
                    "color": "#D4A373",
                    "layer": f"{stair.layer}/steps",
                })
            else:
                elements_data.append({
                    "tag": f"{stair.tag}-Step-{step.step_index}",
                    "class": "IfcStairStep",
                    "material": stair.element.finishes.tread_finish if (stair.element.finishes and stair.element.finishes.tread_finish) else stair.element.material,
                    "position": [step.position[0], step.position[1], step.position[2]],
                    "rotation": [0, 0, getattr(step, "rotation", 0.0)],
                    "dimensions": {
                        "width": step.width,
                        "depth": step.tread,
                        "height": step.riser,
                    },
                    "color": "#D4A373",
                    "layer": f"{stair.layer}/steps",
                })

        for stringer in stair.stringers:
            st_points = stringer.curve_points if (getattr(stringer, "curve_points", None) and len(stringer.curve_points) >= 2) else [stringer.start_point, stringer.end_point]
            elements_data.append({
                "tag": f"{stringer.tag}-Centerline",
                "class": "IfcStairStringer",
                "geometry_type": "line",
                "points": st_points,
                "color": "#3B82F6",
                "linewidth": 3,
                "layer": f"{stair.layer}/stringers",
            })

            if stringer.start_profile_corners and len(stringer.start_profile_corners) == 4:
                sc = stringer.start_profile_corners
                elements_data.append({
                    "tag": f"{stringer.tag}-ProfileStart",
                    "class": "IfcStairStringer",
                    "geometry_type": "line_loop",
                    "points": [sc[0], sc[1], sc[2], sc[3], sc[0]],
                    "color": "#2563EB",
                    "linewidth": 2,
                    "layer": f"{stair.layer}/stringers",
                })

            if stringer.end_profile_corners and len(stringer.end_profile_corners) == 4:
                ec = stringer.end_profile_corners
                elements_data.append({
                    "tag": f"{stringer.tag}-ProfileEnd",
                    "class": "IfcStairStringer",
                    "geometry_type": "line_loop",
                    "points": [ec[0], ec[1], ec[2], ec[3], ec[0]],
                    "color": "#2563EB",
                    "linewidth": 2,
                    "layer": f"{stair.layer}/stringers",
                })

        if stair.landing_polygon and len(stair.landing_polygon) >= 4:
            l_xs = [p[0] for p in stair.landing_polygon]
            l_ys = [p[1] for p in stair.landing_polygon]
            l_z = stair.landing_polygon[0][2]
            l_min_x, l_max_x = min(l_xs), max(l_xs)
            l_min_y, l_max_y = min(l_ys), max(l_ys)
            elements_data.append({
                "tag": f"{stair.tag}-Landing",
                "class": "IfcStairLanding",
                "material": stair.element.landing.material if (stair.element.landing and stair.element.landing.material) else stair.element.material,
                "position": [
                    (l_min_x + l_max_x) / 2.0,
                    (l_min_y + l_max_y) / 2.0,
                    l_z - stair.landing_thickness / 2.0,
                ],
                "rotation": [0, 0, 0],
                "dimensions": {
                    "width": l_max_x - l_min_x,
                    "depth": l_max_y - l_min_y,
                    "height": stair.landing_thickness,
                },
                "color": "#BC6C25",
                "layer": f"{stair.layer}/landing",
            })

            for eb in stair.landing_edge_beams:
                elements_data.append({
                    "tag": f"{eb.tag}-Centerline",
                    "class": "IfcStairLanding",
                    "geometry_type": "line",
                    "points": [eb.start_point, eb.end_point],
                    "color": "#1D4ED8",
                    "linewidth": 3,
                    "layer": f"{stair.layer}/landing",
                })
                if eb.start_profile_corners and len(eb.start_profile_corners) == 4:
                    c = eb.start_profile_corners
                    elements_data.append({
                        "tag": f"{eb.tag}-ProfileStart",
                        "class": "IfcStairLanding",
                        "geometry_type": "line_loop",
                        "points": [c[0], c[1], c[2], c[3], c[0]],
                        "color": "#1E40AF",
                        "linewidth": 2,
                        "layer": f"{stair.layer}/landing",
                    })
                if eb.end_profile_corners and len(eb.end_profile_corners) == 4:
                    c = eb.end_profile_corners
                    elements_data.append({
                        "tag": f"{eb.tag}-ProfileEnd",
                        "class": "IfcStairLanding",
                        "geometry_type": "line_loop",
                        "points": [c[0], c[1], c[2], c[3], c[0]],
                        "color": "#1E40AF",
                        "linewidth": 2,
                        "layer": f"{stair.layer}/landing",
                    })

        if stair.railing:
            for p_idx, (p_base, p_top) in enumerate(stair.railing.posts):
                elements_data.append({
                    "tag": f"{stair.tag}-Railing-Post-{p_idx+1}",
                    "class": "IfcRailing",
                    "geometry_type": "line",
                    "points": [p_base, p_top],
                    "color": "#0F172A",
                    "linewidth": 3,
                    "layer": f"{stair.layer}/railing",
                })
            for r_idx, (r_start, r_end) in enumerate(stair.railing.rails):
                elements_data.append({
                    "tag": f"{stair.tag}-Railing-Rail-{r_idx+1}",
                    "class": "IfcRailing",
                    "geometry_type": "line",
                    "points": [r_start, r_end],
                    "color": "#E11D48",
                    "linewidth": 4,
                    "layer": f"{stair.layer}/railing",
                })

    # Standalone Stair Flights
    for flight in resolved.stair_flights:
        for step in flight.steps:
            elements_data.append({
                "tag": f"{flight.tag}-Step-{step.step_index}",
                "class": "IfcStairStep",
                "material": flight.element.material if flight.element else "MAT_CONC",
                "position": [step.position[0], step.position[1], step.position[2]],
                "rotation": [0, 0, getattr(step, "rotation", 0.0)],
                "dimensions": {
                    "width": step.width,
                    "depth": step.tread,
                    "height": step.riser,
                },
                "color": "#D4A373",
                "layer": f"{flight.layer}/steps",
            })

    # Ramps
    for ramp in resolved.ramps:
        cx = (ramp.start_point[0] + ramp.end_point[0]) / 2.0
        cy = (ramp.start_point[1] + ramp.end_point[1]) / 2.0
        cz = (ramp.start_point[2] + ramp.end_point[2]) / 2.0
        elements_data.append({
            "tag": ramp.tag,
            "class": "IfcRamp",
            "material": ramp.element.material,
            "position": [cx, cy, cz],
            "direction_vector_3d": ramp.direction_vector_3d,
            "dimensions": {
                "length": ramp.slope_length,
                "width": ramp.width,
                "height": ramp.slab_thickness,
                "slope_percentage": ramp.slope_percentage,
            },
            "color": "#78716C",
            "layer": ramp.layer,
        })

    # Railings
    for railing in resolved.railings:
        for p_idx, (p_base, p_top) in enumerate(railing.posts):
            elements_data.append({
                "tag": f"{railing.tag}-Post-{p_idx+1}",
                "class": "IfcRailing",
                "geometry_type": "line",
                "points": [p_base, p_top],
                "color": "#0F172A",
                "linewidth": 3,
                "layer": f"{railing.layer}/posts",
            })
        for r_idx, (r_start, r_end) in enumerate(railing.rails):
            elements_data.append({
                "tag": f"{railing.tag}-Rail-{r_idx+1}",
                "class": "IfcRailing",
                "geometry_type": "line",
                "points": [r_start, r_end],
                "color": "#E11D48",
                "linewidth": 4,
                "layer": f"{railing.layer}/rails",
            })

    # Walls & Children
    for wall in resolved.walls:
        dx = wall.end_point[0] - wall.start_point[0]
        dy = wall.end_point[1] - wall.start_point[1]
        angle = math.atan2(dy, dx)
        cx = (wall.start_point[0] + wall.end_point[0]) / 2.0
        cy = (wall.start_point[1] + wall.end_point[1]) / 2.0
        cz = wall.start_point[2] + wall.height / 2.0

        elements_data.append({
            "tag": wall.tag,
            "class": "IfcWall",
            "material": wall.element.material,
            "position": [cx, cy, cz],
            "rotation": [0, 0, angle],
            "dimensions": {
                "length": wall.length,
                "thickness": wall.thickness,
                "height": wall.height,
            },
            "color": "#D3D3D3",
            "layer": wall.layer,
        })

        for child in wall.children:
            if isinstance(child, ResolvedDoor):
                elements_data.append({
                    "tag": child.tag,
                    "class": "IfcDoor",
                    "material": "Wood",
                    "position": [
                        child.position[0],
                        child.position[1],
                        child.position[2] + child.height / 2.0,
                    ],
                    "rotation": [0, 0, angle],
                    "dimensions": {
                        "width": child.width,
                        "thickness": wall.thickness * 1.08,
                        "height": child.height,
                    },
                    "color": "#8B4513",
                    "layer": child.layer,
                })
            elif isinstance(child, ResolvedWindow):
                elements_data.append({
                    "tag": child.tag,
                    "class": "IfcWindow",
                    "material": "Glass",
                    "position": [
                        child.position[0],
                        child.position[1],
                        child.position[2] + child.height / 2.0,
                    ],
                    "rotation": [0, 0, angle],
                    "dimensions": {
                        "width": child.width,
                        "thickness": wall.thickness * 1.08,
                        "height": child.height,
                    },
                    "color": "#00FFFF",
                    "transparent": True,
                    "opacity": 0.6,
                    "layer": child.layer,
                })

    # Roofs
    for roof in resolved.roofs:
        for plane in roof.planes:
            elements_data.append({
                "tag": plane.tag,
                "class": "IfcRoofCovering",
                "geometry_type": "polygon",
                "points": plane.polygon,
                "material": roof.element.covering.tile_type if roof.element.covering else "Roof Tiles",
                "color": "#9E4734",
                "layer": f"{roof.layer}/covering",
                "member_name": "Roof Covering",
                "dimensions": {
                    "area": plane.area,
                    "slope_degrees": plane.slope_degrees,
                },
            })

        for member in roof.framing_members:
            elements_data.append({
                "tag": member.tag,
                "class": "IfcRoofFraming",
                "geometry_type": "line",
                "points": [member.start_point, member.end_point],
                "color": member.color,
                "linewidth": 3 if member.member_type in ("RIDGE_BEAM", "HIP_RAFTER", "KING_POST", "WALL_PLATE") else 2,
                "layer": f"{roof.layer}/framing",
                "member_type": member.member_type,
                "member_name": member.member_type.replace("_", " ").title(),
                "material": member.material or "STEEL_SS400",
                "profile": member.profile,
                "dimensions": {
                    "length": member.length,
                },
            })

        for ridge in roof.ridges:
            color = "#DC2626" if ridge.ridge_type == "RIDGE" else ("#F59E0B" if ridge.ridge_type == "HIP" else "#64748B")
            elements_data.append({
                "tag": ridge.tag,
                "class": "IfcRoofRidge",
                "geometry_type": "line",
                "points": [ridge.start_point, ridge.end_point],
                "color": color,
                "linewidth": 3 if ridge.ridge_type in ("RIDGE", "HIP") else 2,
                "layer": f"{roof.layer}/covering",
                "member_name": f"Roof Ridge ({ridge.ridge_type.title()})",
                "dimensions": {
                    "length": ridge.length,
                },
            })

    # Custom Elements
    for custom in resolved.custom_elements:
        tag_upper = custom.tag.upper()
        tag_lower = custom.tag.lower()
        layer_lower = (custom.layer or "").lower()
        rot = list(custom.rotation) if custom.rotation else [0.0, 0.0, 0.0]

        if custom.resolved_solid:
            s = custom.resolved_solid
            if isinstance(s, ResolvedSweptDisk):
                elem_dict = {
                    "tag": custom.tag,
                    "class": "IfcCustomElement",
                    "geometry_type": "swept_disk",
                    "material": "Swept Disk Asset",
                    "position": list(s.centroid),
                    "points": list(s.directrix),
                    "radius": s.radius,
                    "inner_radius": s.inner_radius,
                    "color": "#38BDF8",
                    "layer": custom.layer,
                    "dimensions": s.bounding_box,
                }
                elements_data.append(elem_dict)
                continue
            elif isinstance(s, ResolvedRevolvedArea):
                prof_dim = extract_profile_viewer_dim(s.profile, 1.0, is_column=True)
                elem_dict = {
                    "tag": custom.tag,
                    "class": "IfcCustomElement",
                    "geometry_type": "revolved_area",
                    "material": "Revolved Asset",
                    "position": list(custom.position),
                    "profile": prof_dim,
                    "axis_point": list(s.axis_point),
                    "axis_direction": list(s.axis_direction),
                    "revolution_angle": s.revolution_angle,
                    "color": "#A855F7",
                    "layer": custom.layer,
                    "dimensions": s.bounding_box,
                }
                elements_data.append(elem_dict)
                continue

        if custom.dimensions:
            w = custom.dimensions.width
            d = custom.dimensions.depth if custom.dimensions.depth is not None else 0.8
            h = custom.dimensions.height
            pos = [custom.position[0], custom.position[1], custom.position[2] + h / 2.0]
            if "glass" in tag_lower or "glass" in layer_lower or "railing" in tag_lower or "railing" in layer_lower:
                color = "#90CAF9"
            elif "furniture" in layer_lower or any(kw in tag_lower for kw in ["chair", "desk", "table", "bed", "sofa", "cabinet"]):
                color = "#D4A373" if any(kw in tag_lower for kw in ["desk", "table"]) else ("#C5A880" if "bed" in tag_lower else "#B58A63")
            elif any(kw in tag_lower for kw in ["water closet", "wc", "lavatory", "sink", "bath tub", "bathtub", "shower"]) or "sanitary" in layer_lower:
                color = "#FFFFFF"
            elif any(kw in layer_lower for kw in ["duct", "hvac"]):
                color = "#CBD5E1"
            elif any(kw in layer_lower for kw in ["electrical", "elec"]):
                color = "#FDE047" if "light" in tag_lower else "#F97316"
            elif any(kw in layer_lower for kw in ["pipe", "plumbing"]):
                color = "#0284C7" if "cold" in tag_lower else ("#EF4444" if "hot" in tag_lower else "#64748B")
            else:
                color = "#9370DB" if "furniture" in layer_lower else "#808080"
        elif "F2" in tag_upper or "FOOTING" in tag_upper:
            w, d, h = 0.9, 0.9, 0.35
            pos = [custom.position[0], custom.position[1], custom.position[2] - h / 2.0]
            color = "#64748B"
        elif "PIN" in tag_upper:
            w, d, h = 0.35, 0.35, 0.8
            pos = [custom.position[0], custom.position[1], custom.position[2] + h / 2.0]
            color = "#E63946"
        elif "TRUSS" in tag_upper:
            w, d, h = 5.5, 0.8, 3.8
            pos = [custom.position[0] - w / 2.0, custom.position[1], custom.position[2] + h / 2.0]
            color = "#2A6F97"
        elif "LINE" in tag_upper or "BOUNDARY" in tag_upper:
            w, d, h = 134.0, 40.0, 0.05
            pos = [67.0, 20.0, 0.025]
            color = "#FFB703"
        elif "furniture" in layer_lower or any(kw in tag_lower for kw in ["chair", "desk", "table", "bed", "sofa", "cabinet", "shelf", "credenza", "counter"]):
            if "bed" in tag_lower:
                w, d, h = 2.0, 1.6, 0.55
                color = "#C5A880"
            elif any(kw in tag_lower for kw in ["desk", "table"]):
                w, d, h = 1.4, 0.75, 0.75
                color = "#D4A373"
            elif "chair" in tag_lower:
                w, d, h = 0.5, 0.5, 0.85
                color = "#8D99AE"
            elif any(kw in tag_lower for kw in ["sofa", "couch"]):
                w, d, h = 1.8, 0.85, 0.75
                color = "#6C757D"
            elif any(kw in tag_lower for kw in ["cabinet", "credenza", "shelf"]):
                h_val = 1.9 if "tall" in tag_lower else 0.9
                w, d, h = 0.8, 0.55, h_val
                color = "#8C6D53"
            elif "counter" in tag_lower:
                w, d, h = 1.2, 0.6, 0.85
                color = "#A3B18A"
            else:
                w, d, h = 0.6, 0.6, 0.75
                color = "#B58A63"
            pos = [custom.position[0], custom.position[1], custom.position[2] + h / 2.0]
        elif any(kw in tag_lower for kw in ["water closet", "wc", "lavatory", "sink", "bath tub", "bathtub", "shower"]) or "sanitary" in layer_lower:
            if any(kw in tag_lower for kw in ["water closet", "wc"]):
                w, d, h = 0.45, 0.70, 0.75
                color = "#FFFFFF"
            elif any(kw in tag_lower for kw in ["lavatory", "sink"]):
                w, d, h = 0.60, 0.50, 0.82
                color = "#F8FAFC"
            elif any(kw in tag_lower for kw in ["bath tub", "bathtub"]):
                w, d, h = 1.52, 0.76, 0.52
                color = "#FFFFFF"
            elif "shower" in tag_lower:
                w, d, h = 0.90, 0.90, 2.00
                color = "#E2E8F0"
            else:
                w, d, h = 0.5, 0.5, 0.6
                color = "#FFFFFF"
            pos = [custom.position[0], custom.position[1], custom.position[2] + h / 2.0]
        elif any(kw in layer_lower for kw in ["electrical", "elec"]) or any(kw in tag_lower for kw in ["light", "sconce", "pendant", "panelboard", "receptacle", "conduit", "emt"]):
            if any(kw in tag_lower for kw in ["light", "sconce", "pendant"]):
                w, d, h = 0.25, 0.25, 0.25
                color = "#FDE047"
            elif "panelboard" in tag_lower:
                w, d, h = 0.45, 0.15, 0.65
                color = "#475569"
            elif any(kw in tag_lower for kw in ["receptacle", "switch"]):
                w, d, h = 0.08, 0.05, 0.12
                color = "#F1F5F9"
            elif any(kw in tag_lower for kw in ["conduit", "emt"]):
                w, d, h = 0.05, 0.05, 0.05
                color = "#F97316"
            else:
                w, d, h = 0.2, 0.2, 0.2
                color = "#F59E0B"
            pos = [custom.position[0], custom.position[1], custom.position[2] + h / 2.0]
        elif any(kw in layer_lower for kw in ["duct", "hvac"]) or any(kw in tag_lower for kw in ["duct", "mechanical pipe"]):
            if "duct" in tag_lower:
                w, d, h = 0.35, 0.35, 0.25
                color = "#CBD5E1"
            elif "mechanical pipe" in tag_lower:
                w, d, h = 0.08, 0.08, 0.08
                color = "#10B981"
            else:
                w, d, h = 0.25, 0.25, 0.20
                color = "#94A3B8"
            pos = [custom.position[0], custom.position[1], custom.position[2] + h / 2.0]
        elif any(kw in layer_lower for kw in ["pipe", "plumbing"]) or any(kw in tag_lower for kw in ["cold water", "hot water", "waste", "soil", "pvc"]):
            if "cold water" in tag_lower:
                w, d, h = 0.06, 0.06, 0.06
                color = "#0284C7"
            elif "hot water" in tag_lower:
                w, d, h = 0.06, 0.06, 0.06
                color = "#EF4444"
            elif any(kw in tag_lower for kw in ["waste", "soil"]):
                w, d, h = 0.10, 0.10, 0.10
                color = "#64748B"
            elif "pvc" in tag_lower:
                w, d, h = 0.08, 0.08, 0.08
                color = "#0EA5E9"
            else:
                w, d, h = 0.06, 0.06, 0.06
                color = "#38BDF8"
            pos = [custom.position[0], custom.position[1], custom.position[2] + h / 2.0]
        elif "fitting" in layer_lower or any(kw in tag_lower for kw in ["elbow", "tee", "transition", "bend"]):
            w, d, h = 0.08, 0.08, 0.08
            pos = [custom.position[0], custom.position[1], custom.position[2] + h / 2.0]
            color = "#475569"
        elif any(kw in layer_lower for kw in ["stair", "railing"]):
            if "railing" in tag_lower or "railing" in layer_lower:
                w, d, h = 0.08, 1.20, 0.90
                color = "#334155"
            else:
                w, d, h = 1.00, 2.50, 1.50
                color = "#A0522D"
            pos = [custom.position[0], custom.position[1], custom.position[2] + h / 2.0]
        else:
            w, d, h = 0.3, 0.3, 0.3
            pos = [custom.position[0], custom.position[1], custom.position[2] + h / 2.0]
            color = "#A855F7"

        elem_dict = {
            "tag": custom.tag,
            "class": "IfcCustomElement",
            "source": custom.element.source if custom.element and hasattr(custom.element, "source") else None,
            "material": "Custom Asset",
            "position": pos,
            "rotation": rot,
            "dimensions": {
                "width": w,
                "depth": d,
                "height": h,
            },
            "color": color,
            "layer": custom.layer,
        }
        if "glass" in tag_lower or "glass" in layer_lower:
            elem_dict["transparent"] = True
            elem_dict["opacity"] = 0.45
        elements_data.append(elem_dict)

    # Coverings
    for cov in resolved.coverings:
        c_type = cov.covering_type
        cov_layer = cov.layer or ""
        if cov_layer.startswith("architecture/coverings/"):
            cov_layer = cov_layer.replace("architecture/coverings/", "architecture/finishes/")
        elif not cov_layer or cov_layer in ("architecture/coverings", "architecture/finishes"):
            cov_layer = f"architecture/finishes/{c_type.lower()}"

        if c_type == "CEILING":
            c_th = "Ceiling"
            color = "#EDE8F5" if "GYPSUM" in (cov.element.material or "") else ("#E2E8F0" if "TBAR" in (cov.element.material or "") else "#D1D5DB")
            opacity = 0.50
        elif c_type == "FLOORING":
            c_th = "Flooring"
            color = "#CBD5E1"
            opacity = 0.85
        elif c_type == "SKIRTING":
            c_th = "Skirting"
            color = "#B45309"
            opacity = 1.0
        elif c_type == "CLADDING":
            c_th = "Cladding"
            color = "#D97706"
            opacity = 1.0
        else:
            c_th = f"Finish ({c_type})"
            color = "#E5E7EB"
            opacity = 0.70

        if c_type == "SKIRTING":
            sk_height = 0.10
            sk_depth = cov.thickness if cov.thickness > 0 else 0.015
            pts = cov.polygon or []
            n_pts = len(pts)
            if n_pts >= 2:
                n_segs = n_pts if n_pts >= 3 else 1
                for i in range(n_segs):
                    p1 = pts[i]
                    p2 = pts[(i + 1) % n_pts] if n_pts >= 3 else pts[1]
                    dx = p2[0] - p1[0]
                    dy = p2[1] - p1[1]
                    seg_len = math.hypot(dx, dy)
                    if seg_len <= 1e-4:
                        continue
                    angle = math.atan2(dy, dx)
                    cx = (p1[0] + p2[0]) / 2.0
                    cy = (p1[1] + p2[1]) / 2.0
                    cz = (p1[2] + p2[2]) / 2.0 + sk_height / 2.0

                    tag_val = f"{cov.tag}-Seg-{i+1}" if n_segs > 1 else cov.tag
                    elements_data.append({
                        "tag": tag_val,
                        "class": "IfcCovering",
                        "material": cov.element.material,
                        "position": [cx, cy, cz],
                        "rotation": [0, 0, angle],
                        "dimensions": {
                            "length": seg_len,
                            "thickness": sk_depth,
                            "height": sk_height,
                        },
                        "color": color,
                        "layer": cov_layer,
                        "covering_type": c_type,
                        "member_name": f"{c_th} - {cov.element.material}",
                    })
            else:
                w = math.sqrt(cov.area) if cov.area > 0 else (cov.perimeter or 2.0)
                elements_data.append({
                    "tag": cov.tag,
                    "class": "IfcCovering",
                    "material": cov.element.material,
                    "position": [cov.center[0], cov.center[1], cov.center[2] + sk_height / 2.0],
                    "rotation": [0, 0, 0],
                    "dimensions": {
                        "length": w,
                        "thickness": sk_depth,
                        "height": sk_height,
                        "area": cov.area,
                        "length_total": cov.perimeter if cov.perimeter > 0 else None,
                    },
                    "color": color,
                    "layer": cov_layer,
                    "covering_type": c_type,
                    "member_name": f"{c_th} - {cov.element.material}",
                })

        elif c_type == "CLADDING":
            cl_depth = cov.thickness if cov.thickness > 0 else 0.015
            pts = cov.polygon or []
            n_pts = len(pts)

            z_vals = [p[2] for p in pts] if pts else []
            is_vertical_poly = bool(z_vals and (max(z_vals) - min(z_vals) > 0.1))

            if n_pts >= 3 and is_vertical_poly:
                elements_data.append({
                    "tag": cov.tag,
                    "class": "IfcCovering",
                    "material": cov.element.material,
                    "geometry_type": "polygon",
                    "points": cov.polygon,
                    "color": color,
                    "layer": cov_layer,
                    "covering_type": c_type,
                    "member_name": f"{c_th} - {cov.element.material}",
                    "dimensions": {
                        "area": cov.area,
                        "thickness": cov.thickness,
                    },
                })
            elif n_pts >= 2:
                cl_height = 2.70
                if cov.area > 0 and cov.perimeter > 0:
                    calc_h = cov.area / cov.perimeter
                    if 0.5 <= calc_h <= 6.0:
                        cl_height = calc_h

                n_segs = n_pts if n_pts >= 3 else 1
                for i in range(n_segs):
                    p1 = pts[i]
                    p2 = pts[(i + 1) % n_pts] if n_pts >= 3 else pts[1]
                    dx = p2[0] - p1[0]
                    dy = p2[1] - p1[1]
                    seg_len = math.hypot(dx, dy)
                    if seg_len <= 1e-4:
                        continue
                    angle = math.atan2(dy, dx)
                    cx = (p1[0] + p2[0]) / 2.0
                    cy = (p1[1] + p2[1]) / 2.0
                    cz = (p1[2] + p2[2]) / 2.0 + cl_height / 2.0

                    tag_val = f"{cov.tag}-Seg-{i+1}" if n_segs > 1 else cov.tag
                    elements_data.append({
                        "tag": tag_val,
                        "class": "IfcCovering",
                        "material": cov.element.material,
                        "position": [cx, cy, cz],
                        "rotation": [0, 0, angle],
                        "dimensions": {
                            "length": seg_len,
                            "thickness": cl_depth,
                            "height": cl_height,
                        },
                        "color": color,
                        "layer": cov_layer,
                        "covering_type": c_type,
                        "member_name": f"{c_th} - {cov.element.material}",
                    })
            else:
                w = math.sqrt(cov.area) if cov.area > 0 else 2.0
                cl_height = 2.70
                elements_data.append({
                    "tag": cov.tag,
                    "class": "IfcCovering",
                    "material": cov.element.material,
                    "position": [cov.center[0], cov.center[1], cov.center[2] + cl_height / 2.0],
                    "rotation": [0, 0, 0],
                    "dimensions": {
                        "width": w,
                        "depth": w,
                        "height": cl_height,
                        "area": cov.area,
                    },
                    "color": color,
                    "layer": cov_layer,
                    "covering_type": c_type,
                    "member_name": f"{c_th} - {cov.element.material}",
                })

        else:
            if cov.polygon and len(cov.polygon) >= 3:
                elements_data.append({
                    "tag": cov.tag,
                    "class": "IfcCovering",
                    "material": cov.element.material,
                    "geometry_type": "polygon",
                    "points": cov.polygon,
                    "color": color,
                    "layer": cov_layer,
                    "covering_type": c_type,
                    "member_name": f"{c_th} - {cov.element.material}",
                    "dimensions": {
                        "area": cov.area,
                        "thickness": cov.thickness,
                    },
                    "transparent": True,
                    "opacity": opacity,
                })
            else:
                w = math.sqrt(cov.area) if cov.area > 0 else 2.0
                elements_data.append({
                    "tag": cov.tag,
                    "class": "IfcCovering",
                    "material": cov.element.material,
                    "position": [cov.center[0], cov.center[1], cov.center[2]],
                    "rotation": [0, 0, 0],
                    "dimensions": {
                        "width": w,
                        "depth": w,
                        "height": cov.thickness,
                        "area": cov.area,
                        "length": cov.perimeter if cov.perimeter > 0 else None,
                    },
                    "color": color,
                    "layer": cov_layer,
                    "covering_type": c_type,
                    "member_name": f"{c_th} - {cov.element.material}",
                    "transparent": True,
                    "opacity": opacity,
                })

    # MEP Elements: Pipes
    for pipe in resolved.pipes:
        sys_th = {
            "COLD_WATER": "Cold Water",
            "HOT_WATER": "Hot Water",
            "SOIL": "Soil Pipe",
            "WASTE": "Waste Pipe",
            "VENT": "Vent Pipe",
            "DRAINAGE": "Drainage",
            "REFRIGERANT": "Refrigerant Pipe",
            "CONDENSATE": "AC Condensate Drain",
        }.get(pipe.system_type, pipe.system_type)

        elements_data.append({
            "tag": pipe.tag,
            "class": "IfcPipeSegment",
            "geometry_type": "line",
            "points": pipe.waypoints,
            "color": pipe.color,
            "linewidth": 4,
            "layer": pipe.layer,
            "system_type": pipe.system_type,
            "system_name_th": sys_th,
            "material": pipe.element.material or ("PPR" if pipe.system_type == "COLD_WATER" else "PVC"),
            "dimensions": {
                "length": pipe.length,
                "diameter": pipe.nominal_diameter,
                "slope": pipe.slope,
            },
            "fittings_count": pipe.fittings_count,
        })

    # MEP Elements: Conduits
    for conduit in resolved.conduits:
        sys_th = {
            "POWER": "Power Conduit",
            "LIGHTING": "Lighting Conduit",
            "MAIN_FEEDER": "Main Feeder",
            "COMMUNICATION": "Telecom / LAN",
            "SOLAR": "Solar PV Conduit",
        }.get(conduit.system_type, conduit.system_type)

        elements_data.append({
            "tag": conduit.tag,
            "class": "IfcCableCarrierSegment",
            "geometry_type": "line",
            "points": conduit.waypoints,
            "color": conduit.color,
            "linewidth": 3,
            "layer": conduit.layer,
            "system_type": conduit.system_type,
            "system_name_th": sys_th,
            "material": conduit.element.material or "EMT / PVC",
            "dimensions": {
                "length": conduit.length,
                "diameter": conduit.nominal_diameter,
            },
            "fittings_count": conduit.fittings_count,
        })

    # MEP Elements: Sanitary Terminals
    for term in resolved.sanitary_terminals:
        type_th = {
            "WATER_CLOSET": "Water Closet (WC)",
            "WATERCLOSET": "Water Closet (WC)",
            "LAVATORY": "Lavatory / Basin",
            "WASHHANDBASIN": "Wash Hand Basin",
            "URINAL": "Urinal",
            "SHOWER": "Shower",
            "BATH": "Bathtub",
            "BIDET": "Bidet",
            "KITCHEN_SINK": "Kitchen Sink",
            "SINK": "Sink",
            "FLOOR_DRAIN": "Floor Drain",
            "GREASE_TRAP": "Grease Trap",
            "SEPTIC_TANK": "Septic Tank",
            "WATER_TANK": "Water Storage Tank",
            "WATER_PUMP": "Water Booster Pump",
        }.get(term.terminal_type, term.terminal_type)

        elem_dict = {
            "tag": term.tag,
            "class": "IfcSanitaryTerminal",
            "material": term.element.material or "Sanitary Ware",
            "position": [
                term.position[0],
                term.position[1],
                term.position[2] + term.dimensions[2] / 2.0,
            ],
            "rotation": [0, 0, math.radians(term.rotation)],
            "dimensions": {
                "width": term.dimensions[0],
                "depth": term.dimensions[1],
                "height": term.dimensions[2],
            },
            "color": term.color,
            "layer": term.layer,
            "fixture_type": term.terminal_type,
            "predefined_type": term.predefined_type,
            "fixture_name_th": type_th,
        }
        if term.element.cold_water_inlet_diameter or term.element.hot_water_inlet_diameter or term.element.waste_outlet_diameter:
            elem_dict["ports"] = {
                "cold_water_in": term.element.cold_water_inlet_diameter,
                "hot_water_in": term.element.hot_water_inlet_diameter,
                "waste_out": term.element.waste_outlet_diameter,
            }
        elements_data.append(elem_dict)

    # MEP Elements: Waste Terminals
    for term in resolved.waste_terminals:
        type_th = {
            "FLOORDRAIN": "Floor Drain",
            "FLOOR_DRAIN": "Floor Drain",
            "FLOORTRAP": "Floor Trap",
            "GULLYSUMP": "Gully Sump",
            "GREASEINTERCEPTOR": "Grease Interceptor / Trap",
            "GREASE_TRAP": "Grease Trap",
            "ROOFDRAIN": "Roof Drain",
        }.get(term.terminal_type, term.terminal_type)

        elem_dict = {
            "tag": term.tag,
            "class": "IfcWasteTerminal",
            "material": term.element.material or "Drainage Fixture",
            "position": [
                term.position[0],
                term.position[1],
                term.position[2] + term.dimensions[2] / 2.0,
            ],
            "rotation": [0, 0, math.radians(term.rotation)],
            "dimensions": {
                "width": term.dimensions[0],
                "depth": term.dimensions[1],
                "height": term.dimensions[2],
            },
            "color": term.color,
            "layer": term.layer,
            "fixture_type": term.terminal_type,
            "predefined_type": term.predefined_type,
            "fixture_name_th": type_th,
        }
        if term.element.waste_outlet_diameter:
            elem_dict["ports"] = {
                "waste_out": term.element.waste_outlet_diameter,
            }
        elements_data.append(elem_dict)

    # MEP Elements: Distribution Boards
    for board in resolved.distribution_boards:
        b_th = f"Distribution Panel ({board.board_type})"
        ifc_cls = getattr(board.element, "class_", "IfcDistributionBoard")
        elements_data.append({
            "tag": board.tag,
            "class": ifc_cls,
            "material": board.element.material or "Enclosure Box",
            "position": [
                board.position[0],
                board.position[1],
                board.position[2] + board.dimensions[2] / 2.0,
            ],
            "rotation": [0, 0, math.radians(board.rotation)],
            "dimensions": {
                "width": board.dimensions[0],
                "depth": board.dimensions[1],
                "height": board.dimensions[2],
            },
            "color": board.color,
            "layer": board.layer,
            "board_type": board.board_type,
            "circuits_count": board.circuits_count,
            "voltage": board.voltage,
            "phases": board.phases,
            "main_breaker_rating_amperes": board.main_breaker_rating_amperes,
            "poles_count": board.poles_count or board.circuits_count,
            "predefined_type": board.predefined_type,
            "fixture_name_th": b_th,
        })

    # MEP Elements: Lighting Fixtures
    for light in resolved.light_fixtures:
        l_th = {
            "DOWNLIGHT": "Downlight",
            "LED_TUBE": "LED Tube / Batten",
            "PENDANT": "Pendant Lamp",
            "WALL_LAMP": "Wall Lamp",
            "FLOODLIGHT": "Floodlight",
            "POINTSOURCE": "Point Source Light",
            "DIRECTIONSOURCE": "Directional Light",
            "SECURITYLIGHTING": "Emergency / Security Light",
        }.get(light.fixture_type, light.fixture_type)

        elements_data.append({
            "tag": light.tag,
            "class": "IfcLightFixture",
            "material": light.element.material or "Lighting Fixture",
            "position": [
                light.position[0],
                light.position[1],
                light.position[2] - light.dimensions[2] / 2.0,
            ],
            "rotation": [0, 0, 0],
            "dimensions": {
                "width": light.dimensions[0],
                "depth": light.dimensions[1],
                "height": light.dimensions[2],
            },
            "color": light.color,
            "layer": light.layer,
            "fixture_type": light.fixture_type,
            "wattage": light.power_watts or light.wattage,
            "power_watts": light.power_watts or light.wattage,
            "luminous_flux_lumens": light.luminous_flux_lumens,
            "color_temperature_kelvin": light.color_temperature_kelvin,
            "predefined_type": light.predefined_type,
            "fixture_name_th": l_th,
        })

    # MEP Elements: Switches
    for sw in resolved.switches:
        s_th = f"Switch {sw.gangs}-Gang ({sw.switch_type})"
        elements_data.append({
            "tag": sw.tag,
            "class": "IfcSwitchingDevice",
            "material": sw.element.material or "Polycarbonate",
            "position": [
                sw.position[0],
                sw.position[1],
                sw.position[2] + sw.dimensions[2] / 2.0,
            ],
            "rotation": [0, 0, 0],
            "dimensions": {
                "width": sw.dimensions[0],
                "depth": sw.dimensions[1],
                "height": sw.dimensions[2],
            },
            "color": sw.color,
            "layer": sw.layer,
            "switch_type": sw.switch_type,
            "gangs": sw.gangs,
            "fixture_name_th": s_th,
        })

    # MEP Elements: Outlets
    for out in resolved.outlets:
        o_th = f"Power Outlet ({out.outlet_type})"
        elements_data.append({
            "tag": out.tag,
            "class": "IfcOutlet",
            "material": out.element.material or "Polycarbonate",
            "position": [
                out.position[0],
                out.position[1],
                out.position[2] + out.dimensions[2] / 2.0,
            ],
            "rotation": [0, 0, 0],
            "dimensions": {
                "width": out.dimensions[0],
                "depth": out.dimensions[1],
                "height": out.dimensions[2],
            },
            "color": out.color,
            "layer": out.layer,
            "outlet_type": out.outlet_type,
            "predefined_type": out.predefined_type,
            "fixture_name_th": o_th,
        })

    # MEP Elements: Ducts
    for duct in resolved.ducts:
        sys_th = {
            "SUPPLY_AIR": "Supply Air Duct",
            "RETURN_AIR": "Return Air Duct",
            "EXHAUST_AIR": "Exhaust Air Duct",
            "FRESH_AIR": "Fresh Air Duct",
        }.get(duct.system_type, duct.system_type)

        elements_data.append({
            "tag": duct.tag,
            "class": "IfcDuctSegment",
            "geometry_type": "line",
            "points": duct.waypoints,
            "color": duct.color,
            "linewidth": 4,
            "layer": duct.layer,
            "system_type": duct.system_type,
            "system_name_th": sys_th,
            "material": duct.element.material or "Galvanized Steel / Aluminum",
            "dimensions": {
                "length": duct.length,
                "width": duct.width,
                "height": duct.height,
            },
            "fittings_count": duct.fittings_count,
        })

    # MEP Elements: Air Terminals
    for air in resolved.air_terminals:
        type_th = {
            "EXHAUST_FAN_CEILING": "Ceiling Exhaust Fan",
            "EXHAUST_FAN_WALL": "Wall Exhaust Fan",
            "KITCHEN_HOOD": "Kitchen Range Hood",
            "SUPPLY_DIFFUSER": "Supply Diffuser",
            "RETURN_GRILLE": "Return Grille",
        }.get(air.terminal_type, air.terminal_type)

        elements_data.append({
            "tag": air.tag,
            "class": "IfcAirTerminal",
            "material": air.element.material or "Ventilation Terminal",
            "position": [
                air.position[0],
                air.position[1],
                air.position[2] + air.dimensions[2] / 2.0,
            ],
            "rotation": [0, 0, math.radians(air.rotation)],
            "dimensions": {
                "width": air.dimensions[0],
                "depth": air.dimensions[1],
                "height": air.dimensions[2],
            },
            "color": air.color,
            "layer": air.layer,
            "terminal_type": air.terminal_type,
            "flow_rate_cfm": air.flow_rate_cfm,
            "fixture_name_th": type_th,
        })

    # MEP Elements: Unitary Equipment
    for eq in resolved.unitary_equipments:
        eq_th = {
            "AC_INDOOR_WALL": "Wall Mounted AC",
            "AC_INDOOR_CASSETTE": "4-Way Cassette AC",
            "AC_INDOOR_CONCEALED": "Concealed Duct AC",
            "AC_OUTDOOR_CONDENSER": "Outdoor Condensing Unit",
        }.get(eq.equipment_type, eq.equipment_type)

        elements_data.append({
            "tag": eq.tag,
            "class": "IfcUnitaryEquipment",
            "material": eq.element.material or "Air Conditioner",
            "position": [
                eq.position[0],
                eq.position[1],
                eq.position[2] + eq.dimensions[2] / 2.0,
            ],
            "rotation": [0, 0, math.radians(eq.rotation)],
            "dimensions": {
                "width": eq.dimensions[0],
                "depth": eq.dimensions[1],
                "height": eq.dimensions[2],
            },
            "color": eq.color,
            "layer": eq.layer,
            "equipment_type": eq.equipment_type,
            "cooling_capacity_btu": eq.cooling_capacity_btu,
            "fixture_name_th": eq_th,
        })

    scene_json = json.dumps({
        "project": {
            "id": proj.id,
            "name": proj.name,
            "units": proj.units.model_dump(),
        },
        "storeys": storeys_data,
        "grids": grids_data,
        "elements": elements_data,
    }, indent=2, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>debim 3D Viewer - {proj.name}</title>
    <!-- CDN-hosted Three.js and OrbitControls -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/GLTFLoader.js"></script>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            width: 100vw;
            height: 100vh;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #1a1a1e;
            color: #e0e0e0;
        }}
        #canvas-container {{
            width: 100%;
            height: 100%;
            display: block;
        }}
        .ui-panel {{
            position: absolute;
            background: rgba(25, 27, 31, 0.88);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            pointer-events: auto;
            z-index: 10;
        }}
        #layer-explorer-panel {{
            top: 16px;
            left: 16px;
            width: 310px;
            max-height: calc(100vh - 120px);
            display: flex;
            flex-direction: column;
        }}
        #layer-tree-container {{
            overflow-y: auto;
            max-height: calc(100vh - 280px);
            margin-top: 8px;
            padding-right: 4px;
        }}
        .search-box {{
            width: 100%;
            padding: 6px 10px;
            background: rgba(15, 23, 42, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 6px;
            color: #ffffff;
            font-size: 0.8rem;
            margin-bottom: 8px;
        }}
        .search-box:focus {{
            outline: none;
            border-color: #3b82f6;
        }}
        .batch-controls {{
            display: flex;
            gap: 4px;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }}
        .batch-btn {{
            background: #1e293b;
            color: #94a3b8;
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            cursor: pointer;
            transition: all 0.15s;
        }}
        .batch-btn:hover {{
            background: #3b82f6;
            color: #ffffff;
        }}
        .tree-node {{
            user-select: none;
            font-size: 0.8rem;
            line-height: 1.5;
        }}
        .tree-node-content {{
            display: flex;
            align-items: center;
            padding: 2px 4px;
            border-radius: 4px;
        }}
        .tree-node-content:hover {{
            background: rgba(255, 255, 255, 0.05);
        }}
        .tree-expander {{
            cursor: pointer;
            width: 16px;
            text-align: center;
            margin-right: 4px;
            font-size: 0.8rem;
            color: #94a3b8;
        }}
        .tree-checkbox {{
            margin-right: 6px;
            cursor: pointer;
        }}
        .tree-label {{
            cursor: pointer;
            flex-grow: 1;
            color: #e2e8f0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .tree-count {{
            font-size: 0.7rem;
            color: #64748b;
            margin-left: 6px;
        }}
        .tree-children {{
            margin-left: 16px;
            display: block;
        }}
        .tree-children.collapsed {{
            display: none;
        }}
        #info-panel {{
            bottom: 16px;
            left: 16px;
            width: 310px;
            max-height: 200px;
            overflow-y: auto;
        }}
        #inspector-panel {{
            top: 16px;
            right: 16px;
            width: 320px;
        }}
        h1 {{
            font-size: 1.1rem;
            color: #ffffff;
            margin-bottom: 4px;
        }}
        .subtitle {{
            font-size: 0.8rem;
            color: #8888aa;
            margin-bottom: 12px;
        }}
        .section-title {{
            font-size: 0.85rem;
            font-weight: 600;
            color: #4da6ff;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 12px;
            margin-bottom: 6px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding-bottom: 4px;
        }}
        .data-row {{
            display: flex;
            justify-content: space-between;
            font-size: 0.82rem;
            margin-bottom: 4px;
        }}
        .data-label {{
            color: #aaaaaa;
        }}
        .data-value {{
            font-weight: 500;
            color: #ffffff;
            text-align: right;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            background: #2a3a4e;
            color: #66b2ff;
        }}
        #view-toolbar {{
            position: absolute;
            top: 12px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            align-items: center;
            gap: 4px;
            background: rgba(15, 23, 42, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.12);
            backdrop-filter: blur(10px);
            padding: 3px 6px;
            border-radius: 6px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
            z-index: 100;
            white-space: nowrap;
            max-width: calc(100vw - 32px);
            overflow-x: auto;
        }}
        .view-btn {{
            background: #1e293b;
            color: #cbd5e1;
            border: 1px solid rgba(255, 255, 255, 0.08);
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.72rem;
            font-weight: 500;
            line-height: 1.3;
            cursor: pointer;
            transition: all 0.15s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            white-space: nowrap;
        }}
        .view-btn:hover {{
            background: #334155;
            color: #ffffff;
            border-color: rgba(255, 255, 255, 0.2);
        }}
        .view-btn.active {{
            background: #334155;
            color: #38bdf8;
            border-color: #38bdf8;
        }}
        #axes-legend {{
            position: absolute;
            bottom: 16px;
            right: 16px;
            background: rgba(20, 24, 33, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.75rem;
            color: #ddd;
            z-index: 10;
            pointer-events: none;
        }}
        #instructions {{
            position: absolute;
            bottom: 16px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.6);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.8rem;
            color: #cccccc;
            pointer-events: none;
        }}
    </style>
</head>
<body>
    <div id="canvas-container"></div>

    <div id="view-toolbar">
        <button class="view-btn" onclick="setView('top')">Top</button>
        <button class="view-btn" onclick="setView('iso')">Isometric</button>
        <button class="view-btn" onclick="setView('front')">Front</button>
        <button class="view-btn" onclick="setView('side')">Side</button>
        <button id="xray-btn" class="view-btn" onclick="toggleXRay()">X-Ray</button>
        <button id="section-btn" class="view-btn" onclick="toggleSectionPlaneUI()">Section</button>
        <button id="measure-btn" class="view-btn" onclick="toggleMeasureTool()">Measure</button>
        <button id="clear-measure-btn" class="view-btn" onclick="clearMeasurements()" style="display:none;">Clear</button>
    </div>

    <div id="section-plane-panel" class="ui-panel" style="display: none; top: 60px; left: 50%; transform: translateX(-50%); width: 380px; z-index: 1000;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h1 style="font-size: 0.95rem; color: #a78bfa;">✂️ 3D Section Plane / Floor Slicer</h1>
            <button class="batch-btn" onclick="toggleSectionPlaneUI()">✕</button>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
            <span class="data-label">Enable Section Cut:</span>
            <input type="checkbox" id="section-enable-toggle" onchange="setSectionCutEnabled(this.checked)">
        </div>
        <div id="section-controls" style="opacity: 0.5; pointer-events: none; transition: opacity 0.2s;">
            <div class="data-row" style="margin-bottom: 4px;">
                <span class="data-label">Cut Elevation (Z):</span>
                <span class="data-value" id="cut-z-display">0.00 m</span>
            </div>
            <input type="range" id="cut-height-slider" min="0" max="10" step="0.1" value="10" style="width: 100%; margin-bottom: 8px;" oninput="onSectionSliderChange(this.value)">
            <div style="display: flex; gap: 6px; margin-bottom: 8px;">
                <button class="batch-btn" style="flex: 1;" onclick="flipSectionDirection()">🔄 Flip Cut Dir (<span id="dir-label">Clip Above</span>)</button>
                <button class="batch-btn" style="flex: 1;" onclick="resetSectionPlane()">↺ Reset View</button>
            </div>
            <div style="font-size: 0.75rem; color: #94a3b8; margin-bottom: 4px;">Quick Storey Slices:</div>
            <div id="storey-quick-btns" style="display: flex; gap: 4px; flex-wrap: wrap;"></div>
        </div>
    </div>

    <div id="layer-explorer-panel" class="ui-panel">
        <h1>Hierarchical Layer Explorer</h1>
        <div class="subtitle">Filter and toggle layers dynamically</div>
        <input type="text" id="layer-search-input" class="search-box" placeholder="🔍 Search layers..." oninput="filterLayerTree(this.value)">
        <div class="batch-controls">
            <button class="batch-btn" onclick="setAllLayers(true)">Show All</button>
            <button class="batch-btn" onclick="setAllLayers(false)">Hide All</button>
            <button class="batch-btn" onclick="toggleExpandAll(true)">Expand All</button>
            <button class="batch-btn" onclick="toggleExpandAll(false)">Collapse All</button>
        </div>
        <div id="layer-tree-container"></div>
    </div>

    <div id="axes-legend">
        <div><span style="color:#ff4d4d; font-weight:bold;">🔴 Axis X:</span> Width (E-W)</div>
        <div><span style="color:#4dff4d; font-weight:bold;">🟢 Axis Y:</span> Depth (N-S)</div>
        <div><span style="color:#4da6ff; font-weight:bold;">🔵 Axis Z:</span> Elevation</div>
    </div>

    <div id="info-panel" class="ui-panel">
        <h1>{proj.name}</h1>
        <div class="subtitle">Project ID: <span id="project-id">{proj.id}</span></div>

        <div class="section-title">Storeys</div>
        <div id="storeys-list"></div>
    </div>

    <div id="inspector-panel" class="ui-panel">
        <h1>Element Inspector</h1>
        <div class="subtitle">Click on any 3D element to inspect</div>

        <div id="inspector-content">
            <p style="color: #888; font-size: 0.85rem; font-style: italic;">No element selected</p>
        </div>
    </div>

    <div id="instructions">
        Rotate: Left Click + Drag | Pan: Right Click + Drag | Zoom: Scroll
    </div>

    <script>
        const sceneData = {scene_json};

        // Initialize Three.js Scene
        const container = document.getElementById('canvas-container');
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x1a1a1e);

        if (THREE.Object3D.DefaultUp) {{
            THREE.Object3D.DefaultUp.set(0, 0, 1);
        }}

        const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.up.set(0, 0, 1);

        const renderer = new THREE.WebGLRenderer({{ antialias: true }});
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.shadowMap.enabled = true;
        renderer.localClippingEnabled = true;
        container.appendChild(renderer.domElement);

        const gltfLoader = new THREE.GLTFLoader();

        // Section Plane Slicer Engine
        let isSectionCutEnabled = false;
        let sectionCutDir = -1; // -1: clip above, +1: clip below
        let currentCutZ = 10.0;
        let clipPlane = new THREE.Plane(new THREE.Vector3(0, 0, -1), currentCutZ);

        window.toggleSectionPlaneUI = function() {{
            const panel = document.getElementById('section-plane-panel');
            const btn = document.getElementById('section-btn');
            const isVisible = panel.style.display !== 'none';
            panel.style.display = isVisible ? 'none' : 'block';
            if (btn) {{
                if (!isVisible) btn.classList.add('active');
                else btn.classList.remove('active');
            }}
        }};

        window.setSectionCutEnabled = function(enabled) {{
            isSectionCutEnabled = enabled;
            const controls = document.getElementById('section-controls');
            controls.style.opacity = enabled ? '1' : '0.5';
            controls.style.pointerEvents = enabled ? 'auto' : 'none';
            updateSectionPlane();
        }};

        window.onSectionSliderChange = function(val) {{
            currentCutZ = parseFloat(val);
            document.getElementById('cut-z-display').textContent = currentCutZ.toFixed(2) + ' m';
            updateSectionPlane();
        }};

        window.flipSectionDirection = function() {{
            sectionCutDir *= -1;
            document.getElementById('dir-label').textContent = sectionCutDir === -1 ? 'Clip Above' : 'Clip Below';
            updateSectionPlane();
        }};

        const storeyElevations = sceneData.storeys.map(s => s.elevation);
        const minCutZ = storeyElevations.length > 0 ? Math.min(...storeyElevations) - 1.0 : -2.0;
        const maxCutZ = storeyElevations.length > 0 ? Math.max(...storeyElevations) + 4.0 : 15.0;

        window.resetSectionPlane = function() {{
            const toggle = document.getElementById('section-enable-toggle');
            toggle.checked = false;
            setSectionCutEnabled(false);
            currentCutZ = maxCutZ;
            document.getElementById('cut-height-slider').value = currentCutZ;
            document.getElementById('cut-z-display').textContent = currentCutZ.toFixed(2) + ' m';
        }};

        function updateSectionPlane() {{
            if (isSectionCutEnabled) {{
                const nz = sectionCutDir;
                clipPlane.normal.set(0, 0, nz);
                clipPlane.constant = sectionCutDir === -1 ? currentCutZ : -currentCutZ;
                renderer.clippingPlanes = [clipPlane];
            }} else {{
                renderer.clippingPlanes = [];
            }}
        }}

        // Setup Section Plane slider & quick buttons
        setTimeout(() => {{
            const slider = document.getElementById('cut-height-slider');
            if (slider) {{
                slider.min = minCutZ.toFixed(2);
                slider.max = maxCutZ.toFixed(2);
                slider.value = maxCutZ.toFixed(2);
                currentCutZ = maxCutZ;
                document.getElementById('cut-z-display').textContent = currentCutZ.toFixed(2) + ' m';
            }}
            const quickBtnsContainer = document.getElementById('storey-quick-btns');
            if (quickBtnsContainer) {{
                sceneData.storeys.forEach(s => {{
                    const btn = document.createElement('button');
                    btn.className = 'batch-btn';
                    btn.textContent = `${{s.name}} (+${{s.elevation.toFixed(1)}}m)`;
                    btn.onclick = () => {{
                        document.getElementById('section-enable-toggle').checked = true;
                        setSectionCutEnabled(true);
                        const targetZ = s.elevation + 1.2;
                        slider.value = targetZ.toFixed(2);
                        onSectionSliderChange(targetZ);
                    }};
                    quickBtnsContainer.appendChild(btn);
                }});
            }}
        }}, 100);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
        scene.add(ambientLight);

        const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444455, 0.6);
        hemiLight.position.set(0, 0, 50);
        scene.add(hemiLight);

        const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight1.position.set(70, -20, 100);
        scene.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0xaaccff, 0.4);
        dirLight2.position.set(70, 60, 80);
        scene.add(dirLight2);

        // Build UI - Storeys list
        const storeysListEl = document.getElementById('storeys-list');
        sceneData.storeys.forEach(s => {{
            const row = document.createElement('div');
            row.className = 'data-row';
            row.innerHTML = `<span class="data-label">${{s.name}} (${{s.id}})</span><span class="data-value">+${{s.elevation.toFixed(2)}}m (h: ${{s.height.toFixed(2)}}m)</span>`;
            storeysListEl.appendChild(row);
        }});

        // Helper to create circular grid bubble sprites
        function makeGridSprite(name, color) {{
            const canvas = document.createElement('canvas');
            canvas.width = 128;
            canvas.height = 128;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = 'rgba(25, 30, 42, 0.90)';
            ctx.beginPath();
            ctx.arc(64, 64, 52, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = color || '#38bdf8';
            ctx.lineWidth = 6;
            ctx.stroke();
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 44px -apple-system, BlinkMacSystemFont, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(name, 64, 64);
            const texture = new THREE.CanvasTexture(canvas);
            const spriteMat = new THREE.SpriteMaterial({{ map: texture, depthTest: false }});
            const sprite = new THREE.Sprite(spriteMat);
            sprite.scale.set(0.8, 0.8, 1);
            return sprite;
        }}

        // Render Grid Lines & Ground
        const mainX = Object.entries(sceneData.grids.axes_x).filter(([n]) => !n.includes('-')).map(([_, v]) => v);
        const mainY = Object.entries(sceneData.grids.axes_y).filter(([n]) => !n.includes('-')).map(([_, v]) => v);
        const allX = mainX.length > 0 ? mainX : Object.values(sceneData.grids.axes_x);
        const allY = mainY.length > 0 ? mainY : Object.values(sceneData.grids.axes_y);
        const minGridX = Math.min(...allX);
        const maxGridX = Math.max(...allX);
        const minGridY = Math.min(...allY);
        const maxGridY = Math.max(...allY);
        const centerX = (minGridX + maxGridX) / 2;
        const centerY = (minGridY + maxGridY) / 2;
        const gridSize = Math.max(maxGridX - minGridX, maxGridY - minGridY) * 1.4;

        // Actual Project Grid Lines & Grids Group
        const gridGroup = new THREE.Group();
        scene.add(gridGroup);

        const gridLineMat = new THREE.LineDashedMaterial({{
            color: 0x475569,
            dashSize: 1,
            gapSize: 0.5,
            linewidth: 1
        }});

        const bubbleOffset = 1.8;
        const lineExtend = 1.2;

        // X Grids (display primary grids, skip secondary '-')
        Object.entries(sceneData.grids.axes_x).forEach(([name, xVal]) => {{
            if (name.includes('-')) return;
            const pts = [
                new THREE.Vector3(xVal, minGridY - lineExtend, 0),
                new THREE.Vector3(xVal, maxGridY + lineExtend, 0)
            ];
            const geom = new THREE.BufferGeometry().setFromPoints(pts);
            const line = new THREE.Line(geom, gridLineMat);
            line.computeLineDistances();
            gridGroup.add(line);

            const topBubble = makeGridSprite(name, '#38bdf8');
            topBubble.position.set(xVal, maxGridY + bubbleOffset, 0.1);
            gridGroup.add(topBubble);
            const botBubble = makeGridSprite(name, '#38bdf8');
            botBubble.position.set(xVal, minGridY - bubbleOffset, 0.1);
            gridGroup.add(botBubble);
        }});

        // Y Grids (display primary grids, skip secondary '-')
        Object.entries(sceneData.grids.axes_y).forEach(([name, yVal]) => {{
            if (name.includes('-')) return;
            const pts = [
                new THREE.Vector3(minGridX - lineExtend, yVal, 0),
                new THREE.Vector3(maxGridX + lineExtend, yVal, 0)
            ];
            const geom = new THREE.BufferGeometry().setFromPoints(pts);
            const line = new THREE.Line(geom, gridLineMat);
            line.computeLineDistances();
            gridGroup.add(line);

            const leftBubble = makeGridSprite(name, '#4ade80');
            leftBubble.position.set(minGridX - bubbleOffset, yVal, 0.1);
            gridGroup.add(leftBubble);
            const rightBubble = makeGridSprite(name, '#4ade80');
            rightBubble.position.set(maxGridX + bubbleOffset, yVal, 0.1);
            gridGroup.add(rightBubble);
        }});

        const axesHelper = new THREE.AxesHelper(2.5);
        axesHelper.position.set(0, 0, 0.05);
        gridGroup.add(axesHelper);

        const gridHelper = new THREE.GridHelper(gridSize, 20, 0x223046, 0x15202e);
        gridHelper.rotation.x = Math.PI / 2;
        gridHelper.position.set(centerX, centerY, -0.05);
        gridGroup.add(gridHelper);

        sceneData.storeys.forEach(s => {{
            if (s.elevation > 0) {{
                const storeyGrid = new THREE.GridHelper(gridSize, 10, 0x334466, 0x112233);
                storeyGrid.rotation.x = Math.PI / 2;
                storeyGrid.position.set(centerX, centerY, s.elevation);
                gridGroup.add(storeyGrid);
            }}
        }});

        // Render Elements
        const pickableObjects = [];

        function renderProceduralBox(data) {{
            let geometry;
            const dim = data.dimensions || {{ width: 1, depth: 1, height: 1 }};
            if (data.class === "IfcColumn") {{
                if (dim.shape === "CIRCULAR" || dim.shape === "CHS") {{
                    geometry = new THREE.CylinderGeometry(dim.radius, dim.radius, dim.height, 32);
                    geometry.rotateX(Math.PI / 2);
                }} else if (dim.shape === "ELLIPSE") {{
                    geometry = new THREE.CylinderGeometry(1, 1, dim.height, 32);
                    geometry.rotateX(Math.PI / 2);
                    geometry.scale(dim.semi_major_axis, dim.semi_minor_axis, 1);
                }} else if (dim.shape === "ISHAPE" || dim.shape === "I" || dim.shape === "H") {{
                    const w = dim.overall_width || dim.width || 0.2;
                    const d = dim.overall_depth || dim.depth || 0.2;
                    const tw = dim.web_thickness || 0.008;
                    const tf = dim.flange_thickness || 0.012;
                    const s = new THREE.Shape();
                    const x1 = -w/2, x2 = -tw/2, x3 = tw/2, x4 = w/2;
                    const y1 = -d/2, y2 = -d/2 + tf, y3 = d/2 - tf, y4 = d/2;
                    s.moveTo(x1, y1); s.lineTo(x4, y1); s.lineTo(x4, y2); s.lineTo(x3, y2);
                    s.lineTo(x3, y3); s.lineTo(x4, y3); s.lineTo(x4, y4); s.lineTo(x1, y4);
                    s.lineTo(x1, y3); s.lineTo(x2, y3); s.lineTo(x2, y2); s.lineTo(x1, y2);
                    s.closePath();
                    geometry = new THREE.ExtrudeGeometry(s, {{ depth: dim.height, bevelEnabled: false }});
                    geometry.center();
                }} else if (dim.shape === "LSHAPE" || dim.shape === "L") {{
                    const d = dim.depth || 0.05, w = dim.width || 0.05, t = dim.thickness || 0.005;
                    const s = new THREE.Shape();
                    s.moveTo(-w/2, -d/2); s.lineTo(w/2, -d/2); s.lineTo(w/2, -d/2 + t);
                    s.lineTo(-w/2 + t, -d/2 + t); s.lineTo(-w/2 + t, d/2); s.lineTo(-w/2, d/2);
                    s.closePath();
                    geometry = new THREE.ExtrudeGeometry(s, {{ depth: dim.height, bevelEnabled: false }});
                    geometry.center();
                }} else if (dim.shape === "USHAPE" || dim.shape === "U" || dim.shape === "CSHAPE" || dim.shape === "C") {{
                    const d = dim.depth || 0.15, bf = dim.flange_width || dim.width || 0.075;
                    const tw = dim.web_thickness || 0.0065, tf = dim.flange_thickness || 0.01;
                    const s = new THREE.Shape();
                    s.moveTo(-bf/2, -d/2); s.lineTo(bf/2, -d/2); s.lineTo(bf/2, -d/2 + tf);
                    s.lineTo(-bf/2 + tw, -d/2 + tf); s.lineTo(-bf/2 + tw, d/2 - tf); s.lineTo(bf/2, d/2 - tf);
                    s.lineTo(bf/2, d/2); s.lineTo(-bf/2, d/2);
                    s.closePath();
                    geometry = new THREE.ExtrudeGeometry(s, {{ depth: dim.height, bevelEnabled: false }});
                    geometry.center();
                }} else if (dim.shape === "TSHAPE" || dim.shape === "T") {{
                    const d = dim.depth || 0.15, bf = dim.flange_width || dim.width || 0.15;
                    const tw = dim.web_thickness || 0.006, tf = dim.flange_thickness || 0.009;
                    const s = new THREE.Shape();
                    s.moveTo(-bf/2, d/2); s.lineTo(bf/2, d/2); s.lineTo(bf/2, d/2 - tf);
                    s.lineTo(tw/2, d/2 - tf); s.lineTo(tw/2, -d/2); s.lineTo(-tw/2, -d/2);
                    s.lineTo(-tw/2, d/2 - tf); s.lineTo(-bf/2, d/2 - tf);
                    s.closePath();
                    geometry = new THREE.ExtrudeGeometry(s, {{ depth: dim.height, bevelEnabled: false }});
                    geometry.center();
                }} else if (dim.shape === "ARBITRARY" || dim.shape === "ARBITRARY_CLOSED" || dim.shape === "POLYGON" || dim.shape === "ARBITRARY_WITH_VOIDS") {{
                    const pts = dim.points || [];
                    if (pts.length >= 3) {{
                        const s = new THREE.Shape();
                        s.moveTo(pts[0][0], pts[0][1]);
                        for (let i = 1; i < pts.length; i++) {{
                            s.lineTo(pts[i][0], pts[i][1]);
                        }}
                        s.closePath();
                        const voids = dim.voids || [];
                        for (let v = 0; v < voids.length; v++) {{
                            const vpts = voids[v];
                            if (vpts && vpts.length >= 3) {{
                                const hole = new THREE.Path();
                                hole.moveTo(vpts[0][0], vpts[0][1]);
                                for (let j = 1; j < vpts.length; j++) {{
                                    hole.lineTo(vpts[j][0], vpts[j][1]);
                                }}
                                hole.closePath();
                                s.holes.push(hole);
                            }}
                        }}
                        geometry = new THREE.ExtrudeGeometry(s, {{ depth: dim.height, bevelEnabled: false }});
                        geometry.center();
                    }} else {{
                        geometry = new THREE.BoxGeometry(dim.width, dim.depth, dim.height);
                    }}
                }} else {{
                    geometry = new THREE.BoxGeometry(dim.width, dim.depth, dim.height);
                }}
            }} else if (data.class === "IfcBeam") {{
                if (dim.shape === "CIRCULAR" || dim.shape === "CHS") {{
                    geometry = new THREE.CylinderGeometry(dim.radius, dim.radius, dim.length, 32);
                    geometry.rotateZ(-Math.PI / 2);
                }} else if (dim.shape === "ELLIPSE") {{
                    geometry = new THREE.CylinderGeometry(1, 1, dim.length, 32);
                    geometry.rotateZ(-Math.PI / 2);
                    geometry.scale(1, dim.semi_major_axis, dim.semi_minor_axis);
                }} else if (dim.shape === "ISHAPE" || dim.shape === "I" || dim.shape === "H") {{
                    const w = dim.overall_width || dim.width || 0.2;
                    const d = dim.overall_depth || dim.depth || 0.2;
                    const tw = dim.web_thickness || 0.008;
                    const tf = dim.flange_thickness || 0.012;
                    const s = new THREE.Shape();
                    const x1 = -w/2, x2 = -tw/2, x3 = tw/2, x4 = w/2;
                    const y1 = -d/2, y2 = -d/2 + tf, y3 = d/2 - tf, y4 = d/2;
                    s.moveTo(x1, y1); s.lineTo(x4, y1); s.lineTo(x4, y2); s.lineTo(x3, y2);
                    s.lineTo(x3, y3); s.lineTo(x4, y3); s.lineTo(x4, y4); s.lineTo(x1, y4);
                    s.lineTo(x1, y3); s.lineTo(x2, y3); s.lineTo(x2, y2); s.lineTo(x1, y2);
                    s.closePath();
                    geometry = new THREE.ExtrudeGeometry(s, {{ depth: dim.length, bevelEnabled: false }});
                    geometry.center();
                    geometry.rotateY(Math.PI / 2);
                }} else if (dim.shape === "LSHAPE" || dim.shape === "L") {{
                    const d = dim.depth || 0.05, w = dim.width || 0.05, t = dim.thickness || 0.005;
                    const s = new THREE.Shape();
                    s.moveTo(-w/2, -d/2); s.lineTo(w/2, -d/2); s.lineTo(w/2, -d/2 + t);
                    s.lineTo(-w/2 + t, -d/2 + t); s.lineTo(-w/2 + t, d/2); s.lineTo(-w/2, d/2);
                    s.closePath();
                    geometry = new THREE.ExtrudeGeometry(s, {{ depth: dim.length, bevelEnabled: false }});
                    geometry.center();
                    geometry.rotateY(Math.PI / 2);
                }} else if (dim.shape === "USHAPE" || dim.shape === "U" || dim.shape === "CSHAPE" || dim.shape === "C") {{
                    const d = dim.depth || 0.15, bf = dim.flange_width || dim.width || 0.075;
                    const tw = dim.web_thickness || 0.0065, tf = dim.flange_thickness || 0.01;
                    const s = new THREE.Shape();
                    s.moveTo(-bf/2, -d/2); s.lineTo(bf/2, -d/2); s.lineTo(bf/2, -d/2 + tf);
                    s.lineTo(-bf/2 + tw, -d/2 + tf); s.lineTo(-bf/2 + tw, d/2 - tf); s.lineTo(bf/2, d/2 - tf);
                    s.lineTo(bf/2, d/2); s.lineTo(-bf/2, d/2);
                    s.closePath();
                    geometry = new THREE.ExtrudeGeometry(s, {{ depth: dim.length, bevelEnabled: false }});
                    geometry.center();
                    geometry.rotateY(Math.PI / 2);
                }} else if (dim.shape === "TSHAPE" || dim.shape === "T") {{
                    const d = dim.depth || 0.15, bf = dim.flange_width || dim.width || 0.15;
                    const tw = dim.web_thickness || 0.006, tf = dim.flange_thickness || 0.009;
                    const s = new THREE.Shape();
                    s.moveTo(-bf/2, d/2); s.lineTo(bf/2, d/2); s.lineTo(bf/2, d/2 - tf);
                    s.lineTo(tw/2, d/2 - tf); s.lineTo(tw/2, -d/2); s.lineTo(-tw/2, -d/2);
                    s.lineTo(-tw/2, d/2 - tf); s.lineTo(-bf/2, d/2 - tf);
                    s.closePath();
                    geometry = new THREE.ExtrudeGeometry(s, {{ depth: dim.length, bevelEnabled: false }});
                    geometry.center();
                    geometry.rotateY(Math.PI / 2);
                }} else if (dim.shape === "ARBITRARY" || dim.shape === "ARBITRARY_CLOSED" || dim.shape === "POLYGON" || dim.shape === "ARBITRARY_WITH_VOIDS") {{
                    const pts = dim.points || [];
                    if (pts.length >= 3) {{
                        const s = new THREE.Shape();
                        s.moveTo(pts[0][0], pts[0][1]);
                        for (let i = 1; i < pts.length; i++) {{
                            s.lineTo(pts[i][0], pts[i][1]);
                        }}
                        s.closePath();
                        const voids = dim.voids || [];
                        for (let v = 0; v < voids.length; v++) {{
                            const vpts = voids[v];
                            if (vpts && vpts.length >= 3) {{
                                const hole = new THREE.Path();
                                hole.moveTo(vpts[0][0], vpts[0][1]);
                                for (let j = 1; j < vpts.length; j++) {{
                                    hole.lineTo(vpts[j][0], vpts[j][1]);
                                }}
                                hole.closePath();
                                s.holes.push(hole);
                            }}
                        }}
                        geometry = new THREE.ExtrudeGeometry(s, {{ depth: dim.length, bevelEnabled: false }});
                        geometry.center();
                        geometry.rotateY(Math.PI / 2);
                    }} else {{
                        geometry = new THREE.BoxGeometry(dim.length, dim.width, dim.depth);
                    }}
                }} else {{
                    geometry = new THREE.BoxGeometry(dim.length, dim.width, dim.depth);
                }}
            }} else if (data.class === "IfcSlab") {{
                if (dim.polygon && dim.polygon.length >= 3) {{
                    const s = new THREE.Shape();
                    s.moveTo(dim.polygon[0][0] - data.position[0], dim.polygon[0][1] - data.position[1]);
                    for (let i = 1; i < dim.polygon.length; i++) {{
                        s.lineTo(dim.polygon[i][0] - data.position[0], dim.polygon[i][1] - data.position[1]);
                    }}
                    s.closePath();
                    if (dim.voids && dim.voids.length > 0) {{
                        for (let v = 0; v < dim.voids.length; v++) {{
                            const vpts = dim.voids[v];
                            if (vpts && vpts.length >= 3) {{
                                const hole = new THREE.Path();
                                hole.moveTo(vpts[0][0] - data.position[0], vpts[0][1] - data.position[1]);
                                for (let j = 1; j < vpts.length; j++) {{
                                    hole.lineTo(vpts[j][0] - data.position[0], vpts[j][1] - data.position[1]);
                                }}
                                hole.closePath();
                                s.holes.push(hole);
                            }}
                        }}
                    }}
                    geometry = new THREE.ExtrudeGeometry(s, {{ depth: dim.height, bevelEnabled: false }});
                    geometry.center();
                }} else {{
                    geometry = new THREE.BoxGeometry(dim.width, dim.depth, dim.height);
                }}
            }} else if (data.class === "IfcWall") {{
                geometry = new THREE.BoxGeometry(dim.length, dim.thickness, dim.height);
            }} else if (data.class === "IfcDoor" || data.class === "IfcWindow") {{
                geometry = new THREE.BoxGeometry(dim.width, dim.thickness, dim.height);
            }} else {{
                geometry = new THREE.BoxGeometry(dim.width || 1, dim.depth || 1, dim.height || 1);
            }}

            const matOptions = {{
                color: new THREE.Color(data.color || "#808080"),
                roughness: 0.5,
                metalness: 0.1
            }};
            if (data.transparent) {{
                matOptions.transparent = true;
                matOptions.opacity = data.opacity || 0.6;
            }}

            const material = new THREE.MeshStandardMaterial(matOptions);
            const mesh = new THREE.Mesh(geometry, material);

            if (data.position) mesh.position.set(...data.position);
            if (data.direction_vector_3d) {{
                const d = data.direction_vector_3d;
                const dir = new THREE.Vector3(d[0], d[1], d[2]).normalize();
                if (data.class === "IfcColumn") {{
                    const defaultDir = new THREE.Vector3(0, 0, 1);
                    const q = new THREE.Quaternion().setFromUnitVectors(defaultDir, dir);
                    mesh.quaternion.copy(q);
                }} else if (data.class === "IfcBeam") {{
                    const defaultDir = new THREE.Vector3(1, 0, 0);
                    const q = new THREE.Quaternion().setFromUnitVectors(defaultDir, dir);
                    mesh.quaternion.copy(q);
                }}
            }} else if (data.rotation) {{
                mesh.rotation.set(data.rotation[0], data.rotation[1], data.rotation[2]);
            }}

            const edges = new THREE.EdgesGeometry(geometry);
            const line = new THREE.LineSegments(
                edges,
                new THREE.LineBasicMaterial({{ color: 0x000000, linewidth: 1 }})
            );
            mesh.add(line);
            mesh.userData = data;

            let layerPath = data.layer || "general/other";
            if (!layerPath.includes("/")) {{
                layerPath = "general/" + layerPath;
            }}
            mesh.userData.layer = layerPath;

            scene.add(mesh);
            pickableObjects.push(mesh);
        }}

        sceneData.elements.forEach(data => {{
            let object3D;

            if (data.source && (data.source.endsWith(".glb") || data.source.endsWith(".gltf"))) {{
                gltfLoader.load(
                    data.source,
                    function (gltf) {{
                        const model = gltf.scene;
                        if (data.position) model.position.set(...data.position);
                        if (data.rotation) model.rotation.set(...data.rotation);
                        model.userData = data;
                        let layerPath = data.layer || "general/other";
                        if (!layerPath.includes("/")) layerPath = "general/" + layerPath;
                        model.userData.layer = layerPath;

                        model.traverse((child) => {{
                            if (child.isMesh) {{
                                child.userData = data;
                                child.userData.layer = layerPath;
                            }}
                        }});

                        scene.add(model);
                        pickableObjects.push(model);
                    }},
                    undefined,
                    function (error) {{
                        renderProceduralBox(data);
                    }}
                );
                return;
            }}

            if (data.geometry_type === "swept_disk") {{
                const points = data.points.map(p => new THREE.Vector3(...p));
                const curve = new THREE.CatmullRomCurve3(points);
                const tubeGeom = new THREE.TubeGeometry(curve, 64, data.radius, 16, false);
                const mat = new THREE.MeshStandardMaterial({{
                    color: new THREE.Color(data.color || "#38bdf8"),
                    roughness: 0.4,
                    metalness: 0.2
                }});
                object3D = new THREE.Mesh(tubeGeom, mat);
            }} else if (data.geometry_type === "revolved_area") {{
                const prof = data.profile || {{}};
                const w = prof.width || 0.4;
                const d = prof.depth || 0.4;
                const shape = new THREE.Shape();
                shape.moveTo(-w/2, -d/2);
                shape.lineTo(w/2, -d/2);
                shape.lineTo(w/2, d/2);
                shape.lineTo(-w/2, d/2);
                shape.closePath();
                const pts2d = shape.getPoints(12);
                const points = pts2d.map(p => new THREE.Vector2(p.x, p.y));
                const segments = Math.max(12, Math.round((data.revolution_angle / 360) * 32));
                const phiLength = (data.revolution_angle / 360) * Math.PI * 2;
                const latheGeom = new THREE.LatheGeometry(points, segments, 0, phiLength);
                const mat = new THREE.MeshStandardMaterial({{
                    color: new THREE.Color(data.color || "#a855f7"),
                    roughness: 0.5,
                    metalness: 0.1,
                    side: THREE.DoubleSide
                }});
                object3D = new THREE.Mesh(latheGeom, mat);
                if (data.position) object3D.position.set(...data.position);
            }} else if (data.geometry_type === "line" || data.geometry_type === "line_loop") {{
                const points = data.points.map(p => new THREE.Vector3(...p));
                const lineGeom = new THREE.BufferGeometry().setFromPoints(points);
                const lineMat = new THREE.LineBasicMaterial({{
                    color: new THREE.Color(data.color),
                    linewidth: data.linewidth || 2,
                }});
                object3D = (data.geometry_type === "line_loop")
                    ? new THREE.LineLoop(lineGeom, lineMat)
                    : new THREE.Line(lineGeom, lineMat);
            }} else if (data.geometry_type === "polygon") {{
                const geom = new THREE.BufferGeometry();
                const vertices = [];
                const pts = data.points;
                if (pts.length === 3) {{
                    vertices.push(...pts[0], ...pts[1], ...pts[2]);
                }} else if (pts.length >= 4) {{
                    for (let i = 1; i < pts.length - 1; i++) {{
                        vertices.push(...pts[0], ...pts[i], ...pts[i + 1]);
                    }}
                }}
                geom.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
                geom.computeVertexNormals();

                const matOptions = {{
                    color: new THREE.Color(data.color),
                    roughness: 0.6,
                    metalness: 0.1,
                    side: THREE.DoubleSide,
                }};
                const mat = new THREE.MeshStandardMaterial(matOptions);
                const mesh = new THREE.Mesh(geom, mat);

                const edges = new THREE.EdgesGeometry(geom);
                const line = new THREE.LineSegments(
                    edges,
                    new THREE.LineBasicMaterial({{ color: 0x111111, linewidth: 1 }})
                );
                mesh.add(line);
                object3D = mesh;
            }} else {{
                renderProceduralBox(data);
                return;
            }}

            object3D.userData = data;

            let layerPath = data.layer || "general/other";
            if (!layerPath.includes("/")) {{
                layerPath = "general/" + layerPath;
            }}
            object3D.userData.layer = layerPath;

            scene.add(object3D);
            pickableObjects.push(object3D);
        }});

        // Automatic Model Bounding Box & Target Framing
        const modelBox = new THREE.Box3();
        pickableObjects.forEach(obj => modelBox.expandByObject(obj));
        const bCenter = new THREE.Vector3();
        const bSize = new THREE.Vector3();
        modelBox.getCenter(bCenter);
        modelBox.getSize(bSize);

        const targetX = (isFinite(bCenter.x) && bSize.x > 0.1) ? bCenter.x : centerX;
        const targetY = (isFinite(bCenter.y) && bSize.y > 0.1) ? bCenter.y : centerY;
        const targetZ = (isFinite(bCenter.z) && bSize.z > 0.1) ? bCenter.z : 2.5;
        const maxSpan = Math.max(bSize.x, bSize.y, bSize.z, 15);

        // Camera position setup (Default: ISO View framed to model)
        camera.position.set(targetX + maxSpan * 0.9, targetY - maxSpan * 1.2, targetZ + maxSpan * 0.8);
        camera.up.set(0, 0, 1);
        controls.target.set(targetX, targetY, targetZ);
        controls.minPolarAngle = 0;
        controls.maxPolarAngle = Math.PI;
        controls.update();

        window.setView = function(mode) {{
            if (mode === 'top') {{
                camera.position.set(targetX, targetY, targetZ + maxSpan * 1.6);
                camera.up.set(0, 1, 0);
                controls.target.set(targetX, targetY, targetZ);
                controls.minPolarAngle = 0;
                controls.maxPolarAngle = 0;
            }} else if (mode === 'iso') {{
                camera.position.set(targetX + maxSpan * 0.9, targetY - maxSpan * 1.2, targetZ + maxSpan * 0.8);
                camera.up.set(0, 0, 1);
                controls.target.set(targetX, targetY, targetZ);
                controls.minPolarAngle = 0;
                controls.maxPolarAngle = Math.PI;
            }} else if (mode === 'front') {{
                camera.position.set(targetX, targetY - maxSpan * 1.5, targetZ);
                camera.up.set(0, 0, 1);
                controls.target.set(targetX, targetY, targetZ);
                controls.minPolarAngle = 0;
                controls.maxPolarAngle = Math.PI;
            }} else if (mode === 'side') {{
                camera.position.set(targetX + maxSpan * 1.5, targetY, targetZ);
                camera.up.set(0, 0, 1);
                controls.target.set(targetX, targetY, targetZ);
                controls.minPolarAngle = 0;
                controls.maxPolarAngle = Math.PI;
            }}
            controls.update();
        }};

        // X-Ray and Quick Discipline Filters
        let isXRay = false;
        window.toggleXRay = function() {{
            isXRay = !isXRay;
            const btn = document.getElementById('xray-btn');
            if (btn) {{
                if (isXRay) {{
                    btn.classList.add('active');
                    btn.textContent = 'X-Ray (On)';
                }} else {{
                    btn.classList.remove('active');
                    btn.textContent = 'X-Ray';
                }}
            }}
            pickableObjects.forEach(obj => {{
                if (obj.userData && (obj.userData.class === "IfcWall" || obj.userData.class === "IfcRoofCovering" || (obj.userData.layer && obj.userData.layer.includes("walls")))) {{
                    if (obj.material) {{
                        if (isXRay) {{
                            obj.material.transparent = true;
                            obj.material.opacity = 0.20;
                            obj.material.needsUpdate = true;
                        }} else {{
                            obj.material.transparent = Boolean(obj.userData.transparent);
                            obj.material.opacity = obj.userData.opacity || 1.0;
                            obj.material.needsUpdate = true;
                        }}
                    }}
                }}
            }});
        }};

        window.filterDiscipline = function(discipline) {{
            if (!layerTreeRoot || !layerTreeRoot.children) return;
            if (discipline === 'all') {{
                setAllLayers(true);
                return;
            }}
            setAllLayers(false);
            if (discipline === 'mep') {{
                if (layerTreeRoot.children['mep']) setNodeChecked(layerTreeRoot.children['mep'], true);
                if (layerTreeRoot.children['architecture'] && layerTreeRoot.children['architecture'].children['walls']) {{
                    layerTreeRoot.children['architecture'].children['walls'].checked = true;
                }}
                if (!isXRay) toggleXRay();
            }} else if (discipline === 'interior') {{
                if (layerTreeRoot.children['interior']) setNodeChecked(layerTreeRoot.children['interior'], true);
                if (layerTreeRoot.children['structure'] && layerTreeRoot.children['structure'].children['slabs']) {{
                    layerTreeRoot.children['structure'].children['slabs'].checked = true;
                }}
                if (!isXRay) toggleXRay();
            }} else if (discipline === 'structure') {{
                if (layerTreeRoot.children['structure']) setNodeChecked(layerTreeRoot.children['structure'], true);
            }}
            update3DVisibility();
            renderLayerTree(layerTreeRoot, document.getElementById("layer-tree-container"));
        }};

        // Hierarchical Tree Layer Explorer Engine
        const layerTreeRoot = {{ children: {{}}, count: 0, path: "" }};

        function buildLayerTree() {{
            pickableObjects.forEach(obj => {{
                let layerPath = obj.userData.layer || "general/other";
                if (!layerPath.includes("/")) {{
                    layerPath = "general/" + layerPath;
                }}
                const parts = layerPath.split("/");
                let curr = layerTreeRoot;
                curr.count++;
                let pathSoFar = "";

                parts.forEach((part, idx) => {{
                    pathSoFar = pathSoFar ? (pathSoFar + "/" + part) : part;
                    if (!curr.children[part]) {{
                        curr.children[part] = {{
                            name: part,
                            path: pathSoFar,
                            children: {{}},
                            count: 0,
                            checked: true,
                            expanded: true,
                            objects: []
                        }};
                    }}
                    curr = curr.children[part];
                    curr.count++;
                    if (idx === parts.length - 1) {{
                        curr.objects.push(obj);
                    }}
                }});
            }});

            layerTreeRoot.children["general"] = layerTreeRoot.children["general"] || {{
                name: "general",
                path: "general",
                children: {{}},
                count: 0,
                checked: true,
                expanded: true,
                objects: []
            }};
            layerTreeRoot.children["general"].children["grids"] = {{
                name: "grids",
                path: "general/grids",
                children: {{}},
                count: 1,
                checked: true,
                expanded: true,
                objects: []
            }};
            layerTreeRoot.children["general"].count++;
        }}

        function renderLayerTree(node, containerEl) {{
            containerEl.innerHTML = "";
            const keys = Object.keys(node.children).sort();

            keys.forEach(key => {{
                const childNode = node.children[key];
                const nodeEl = document.createElement("div");
                nodeEl.className = "tree-node";
                nodeEl.dataset.path = childNode.path;

                const hasChildren = Object.keys(childNode.children).length > 0;
                const folderIcon = hasChildren ? (childNode.expanded ? "📂" : "📁") : "📄";
                const expanderSymbol = hasChildren ? (childNode.expanded ? "▼" : "▶") : "";

                const contentEl = document.createElement("div");
                contentEl.className = "tree-node-content";

                const expanderEl = document.createElement("span");
                expanderEl.className = "tree-expander";
                expanderEl.textContent = expanderSymbol;
                expanderEl.onclick = (e) => {{
                    e.stopPropagation();
                    childNode.expanded = !childNode.expanded;
                    renderLayerTree(layerTreeRoot, document.getElementById("layer-tree-container"));
                }};

                const checkboxEl = document.createElement("input");
                checkboxEl.type = "checkbox";
                checkboxEl.className = "tree-checkbox";
                checkboxEl.checked = childNode.checked;
                checkboxEl.onclick = (e) => {{
                    e.stopPropagation();
                    setNodeChecked(childNode, checkboxEl.checked);
                    update3DVisibility();
                    renderLayerTree(layerTreeRoot, document.getElementById("layer-tree-container"));
                }};

                const labelEl = document.createElement("span");
                labelEl.className = "tree-label";
                labelEl.innerHTML = `${{folderIcon}} ${{childNode.name}}`;
                labelEl.onclick = () => {{
                    if (hasChildren) {{
                        childNode.expanded = !childNode.expanded;
                        renderLayerTree(layerTreeRoot, document.getElementById("layer-tree-container"));
                    }}
                }};

                const countEl = document.createElement("span");
                countEl.className = "tree-count";
                countEl.textContent = `(${{childNode.count}})`;

                contentEl.appendChild(expanderEl);
                contentEl.appendChild(checkboxEl);
                contentEl.appendChild(labelEl);
                contentEl.appendChild(countEl);
                nodeEl.appendChild(contentEl);

                if (hasChildren) {{
                    const childrenContainer = document.createElement("div");
                    childrenContainer.className = "tree-children" + (childNode.expanded ? "" : " collapsed");
                    renderLayerTree(childNode, childrenContainer);
                    nodeEl.appendChild(childrenContainer);
                }}

                containerEl.appendChild(nodeEl);
            }});
        }}

        function setNodeChecked(node, isChecked) {{
            node.checked = isChecked;
            Object.values(node.children).forEach(child => setNodeChecked(child, isChecked));
        }}

        function update3DVisibility() {{
            function checkObjectVisible(obj) {{
                let layerPath = obj.userData.layer || "general/other";
                if (!layerPath.includes("/")) layerPath = "general/" + layerPath;
                const parts = layerPath.split("/");
                let curr = layerTreeRoot;
                for (let part of parts) {{
                    if (!curr.children[part]) return true;
                    curr = curr.children[part];
                    if (!curr.checked) return false;
                }}
                return true;
            }}

            pickableObjects.forEach(obj => {{
                obj.visible = checkObjectVisible(obj);
            }});

            if (layerTreeRoot.children["general"] && layerTreeRoot.children["general"].children["grids"]) {{
                gridGroup.visible = layerTreeRoot.children["general"].children["grids"].checked && layerTreeRoot.children["general"].checked;
            }}
        }}

        window.setAllLayers = function(visible) {{
            setNodeChecked(layerTreeRoot, visible);
            update3DVisibility();
            renderLayerTree(layerTreeRoot, document.getElementById("layer-tree-container"));
        }};

        window.toggleExpandAll = function(expanded) {{
            function setExpanded(node) {{
                node.expanded = expanded;
                Object.values(node.children).forEach(child => setExpanded(child));
            }}
            setExpanded(layerTreeRoot);
            renderLayerTree(layerTreeRoot, document.getElementById("layer-tree-container"));
        }};

        window.filterLayerTree = function(keyword) {{
            const query = keyword.trim().toLowerCase();
            const nodes = document.querySelectorAll("#layer-tree-container .tree-node");
            nodes.forEach(n => {{
                const path = (n.dataset.path || "").toLowerCase();
                if (!query || path.includes(query)) {{
                    n.style.display = "";
                }} else {{
                    n.style.display = "none";
                }}
            }});
        }};

        buildLayerTree();
        renderLayerTree(layerTreeRoot, document.getElementById("layer-tree-container"));

        // Select first element by default if available
        if (sceneData.elements.length > 0) {{
            showInspector(sceneData.elements[0]);
        }}

        // 3D Measurement Tool Engine
        let isMeasureActive = false;
        let measurePointA = null;
        const measureGroup = new THREE.Group();
        scene.add(measureGroup);
        const measureHistory = [];

        const previewSphereGeom = new THREE.SphereGeometry(0.12, 16, 16);
        const snapMarker = new THREE.Mesh(
            previewSphereGeom,
            new THREE.MeshBasicMaterial({{ color: 0xf59e0b, depthTest: false, transparent: true, opacity: 0.85 }})
        );
        snapMarker.visible = false;
        measureGroup.add(snapMarker);

        let livePreviewLine = null;
        let startMarkerA = null;

        function getSnappedPoint(hit) {{
            let pt = hit.point.clone();
            const obj = hit.object;
            if (obj && obj.geometry && obj.geometry.attributes && obj.geometry.attributes.position) {{
                const posAttr = obj.geometry.attributes.position;
                const localHit = obj.worldToLocal(pt.clone());
                let closestDistSq = Infinity;
                let closestVertex = null;
                const v = new THREE.Vector3();
                const count = Math.min(posAttr.count, 200);
                for (let i = 0; i < count; i++) {{
                    v.fromBufferAttribute(posAttr, i);
                    const dSq = v.distanceToSquared(localHit);
                    if (dSq < closestDistSq) {{
                        closestDistSq = dSq;
                        closestVertex = v.clone();
                    }}
                }}
                if (closestVertex) {{
                    const worldV = obj.localToWorld(closestVertex);
                    if (worldV.distanceTo(hit.point) <= 0.40) {{
                        return {{ point: worldV, snapped: true }};
                    }}
                }}
            }}
            return {{ point: pt, snapped: false }};
        }}

        function makeDimensionSprite(dist, dx, dy, dz) {{
            const canvas = document.createElement('canvas');
            canvas.width = 380;
            canvas.height = 140;
            const ctx = canvas.getContext('2d');

            ctx.fillStyle = 'rgba(15, 23, 42, 0.90)';
            ctx.strokeStyle = '#2dd4bf';
            ctx.lineWidth = 4;
            const r = 16;
            ctx.beginPath();
            if (ctx.roundRect) {{
                ctx.roundRect(8, 8, 364, 124, r);
            }} else {{
                ctx.rect(8, 8, 364, 124);
            }}
            ctx.fill();
            ctx.stroke();

            ctx.fillStyle = '#f8fafc';
            ctx.font = 'bold 44px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(dist.toFixed(2) + ' m', 190, 48);

            ctx.fillStyle = '#94a3b8';
            ctx.font = '22px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
            ctx.fillText('ΔX: ' + dx.toFixed(2) + '  ΔY: ' + dy.toFixed(2) + '  ΔZ: ' + dz.toFixed(2), 190, 94);

            const texture = new THREE.CanvasTexture(canvas);
            const spriteMat = new THREE.SpriteMaterial({{ map: texture, depthTest: false }});
            const sprite = new THREE.Sprite(spriteMat);
            sprite.scale.set(2.4, 0.88, 1);
            return sprite;
        }}

        window.toggleMeasureTool = function() {{
            isMeasureActive = !isMeasureActive;
            const btn = document.getElementById('measure-btn');
            const clearBtn = document.getElementById('clear-measure-btn');
            const container = document.getElementById('canvas-container');

            if (isMeasureActive) {{
                btn.classList.add('active');
                btn.textContent = 'Measure (On)';
                container.style.cursor = 'crosshair';
                document.getElementById('instructions').textContent = 'Measure: Click element to set Point A | Esc to exit';
                if (measureHistory.length > 0) clearBtn.style.display = 'inline-block';
            }} else {{
                btn.classList.remove('active');
                btn.textContent = 'Measure';
                container.style.cursor = 'default';
                document.getElementById('instructions').textContent = 'Rotate: Left Click + Drag | Pan: Right Click + Drag | Zoom: Scroll';
                resetCurrentMeasure();
            }}
        }};

        function resetCurrentMeasure() {{
            measurePointA = null;
            snapMarker.visible = false;
            if (livePreviewLine) {{
                measureGroup.remove(livePreviewLine);
                livePreviewLine = null;
            }}
            if (startMarkerA) {{
                measureGroup.remove(startMarkerA);
                startMarkerA = null;
            }}
        }}

        window.clearMeasurements = function() {{
            measureHistory.forEach(obj => measureGroup.remove(obj));
            measureHistory.length = 0;
            resetCurrentMeasure();
            document.getElementById('clear-measure-btn').style.display = 'none';
        }};

        window.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape' && isMeasureActive) {{
                toggleMeasureTool();
            }}
        }});

        window.addEventListener('mousemove', (event) => {{
            if (!isMeasureActive) return;
            if (event.target.closest('.ui-panel')) {{
                snapMarker.visible = false;
                return;
            }}

            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
            raycaster.setFromCamera(mouse, camera);
            let intersects = raycaster.intersectObjects(pickableObjects);
            if (isSectionCutEnabled) {{
                intersects = intersects.filter(hit => clipPlane.distanceToPoint(hit.point) >= 0);
            }}

            if (intersects.length > 0) {{
                const snap = getSnappedPoint(intersects[0]);
                snapMarker.position.copy(snap.point);
                snapMarker.material.color.setHex(snap.snapped ? 0x22c55e : 0xf59e0b);
                snapMarker.visible = true;

                if (measurePointA) {{
                    if (livePreviewLine) measureGroup.remove(livePreviewLine);
                    const pts = [measurePointA, snap.point];
                    const geom = new THREE.BufferGeometry().setFromPoints(pts);
                    const mat = new THREE.LineDashedMaterial({{ color: 0x2dd4bf, dashSize: 0.3, gapSize: 0.15, linewidth: 2 }});
                    livePreviewLine = new THREE.Line(geom, mat);
                    livePreviewLine.computeLineDistances();
                    measureGroup.add(livePreviewLine);

                    const curDist = measurePointA.distanceTo(snap.point);
                    document.getElementById('instructions').textContent = 'Distance: ' + curDist.toFixed(2) + ' m | Click Point B to complete';
                }}
            }} else {{
                snapMarker.visible = false;
            }}
        }});

        // Element Selection / Raycasting
        const raycaster = new THREE.Raycaster();
        raycaster.params.Line = {{ threshold: 0.35 }};
        const mouse = new THREE.Vector2();
        let selectedMesh = null;
        let originalColor = null;

        window.addEventListener('click', (event) => {{
            if (event.target.closest('.ui-panel')) return;

            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);
            let intersects = raycaster.intersectObjects(pickableObjects);

            if (isSectionCutEnabled) {{
                intersects = intersects.filter(hit => clipPlane.distanceToPoint(hit.point) >= 0);
            }}

            // Measurement Mode Click Handler
            if (isMeasureActive) {{
                if (intersects.length === 0) return;
                const snap = getSnappedPoint(intersects[0]);

                if (!measurePointA) {{
                    measurePointA = snap.point.clone();
                    startMarkerA = new THREE.Mesh(
                        previewSphereGeom,
                        new THREE.MeshBasicMaterial({{ color: 0x38bdf8, depthTest: false }})
                    );
                    startMarkerA.position.copy(measurePointA);
                    measureGroup.add(startMarkerA);
                    document.getElementById('instructions').textContent = 'Point A set! Click Point B to measure distance';
                }} else {{
                    const measurePointB = snap.point.clone();
                    const dist = measurePointA.distanceTo(measurePointB);
                    const dx = Math.abs(measurePointB.x - measurePointA.x);
                    const dy = Math.abs(measurePointB.y - measurePointA.y);
                    const dz = Math.abs(measurePointB.z - measurePointA.z);

                    // Create permanent dimension line
                    const lineGeom = new THREE.BufferGeometry().setFromPoints([measurePointA, measurePointB]);
                    const lineMat = new THREE.LineBasicMaterial({{ color: 0x2dd4bf, linewidth: 3, depthTest: false }});
                    const dimLine = new THREE.Line(lineGeom, lineMat);

                    // Markers
                    const endMarker = new THREE.Mesh(
                        previewSphereGeom,
                        new THREE.MeshBasicMaterial({{ color: 0x2dd4bf, depthTest: false }})
                    );
                    endMarker.position.copy(measurePointB);

                    const persistentStart = new THREE.Mesh(
                        previewSphereGeom,
                        new THREE.MeshBasicMaterial({{ color: 0x38bdf8, depthTest: false }})
                    );
                    persistentStart.position.copy(measurePointA);

                    // Midpoint label
                    const midPt = new THREE.Vector3().addVectors(measurePointA, measurePointB).multiplyScalar(0.5);
                    midPt.z += 0.20;
                    const labelSprite = makeDimensionSprite(dist, dx, dy, dz);
                    labelSprite.position.copy(midPt);

                    const record = new THREE.Group();
                    record.add(dimLine);
                    record.add(persistentStart);
                    record.add(endMarker);
                    record.add(labelSprite);
                    measureGroup.add(record);
                    measureHistory.push(record);

                    document.getElementById('clear-measure-btn').style.display = 'inline-block';
                    document.getElementById('instructions').textContent = 'Measured: ' + dist.toFixed(2) + ' m (ΔX: ' + dx.toFixed(2) + ', ΔY: ' + dy.toFixed(2) + ', ΔZ: ' + dz.toFixed(2) + ') | Click element to start new measurement';

                    resetCurrentMeasure();
                }}
                return;
            }}

            if (selectedMesh && originalColor) {{
                selectedMesh.material.color.copy(originalColor);
                selectedMesh = null;
            }}

            if (intersects.length > 0) {{
                selectedMesh = intersects[0].object;
                originalColor = selectedMesh.material.color.clone();
                selectedMesh.material.color.setHex(0xffaa00);

                showInspector(selectedMesh.userData);
            }} else {{
                showInspector(null);
            }}
        }});

        function showInspector(data) {{
            const contentEl = document.getElementById('inspector-content');
            if (!data) {{
                contentEl.innerHTML = '<p style="color: #888; font-size: 0.85rem; font-style: italic;">No element selected</p>';
                return;
            }}

            let dimText = '-';
            if (data.dimensions) {{
                if (data.dimensions.shape === "CIRCULAR" || data.dimensions.shape === "CHS") {{
                    dimText = 'Ø ' + (data.dimensions.diameter || data.dimensions.radius * 2).toFixed(2) + 'm (Circular)';
                }} else if (data.dimensions.shape === "ELLIPSE") {{
                    dimText = (data.dimensions.semi_major_axis * 2).toFixed(2) + 'm × ' + (data.dimensions.semi_minor_axis * 2).toFixed(2) + 'm (Ellipse)';
                }} else if (data.dimensions.shape === "ISHAPE" || data.dimensions.shape === "I" || data.dimensions.shape === "H") {{
                    dimText = `${{((data.dimensions.overall_depth || data.dimensions.depth || 0) * 1000).toFixed(0)}}×${{((data.dimensions.overall_width || data.dimensions.width || 0) * 1000).toFixed(0)}}×${{((data.dimensions.web_thickness || 0) * 1000).toFixed(1)}}×${{((data.dimensions.flange_thickness || 0) * 1000).toFixed(1)}} mm (I-Shape)`;
                }} else if (data.dimensions.shape === "LSHAPE" || data.dimensions.shape === "L") {{
                    dimText = `L ${{((data.dimensions.depth || 0) * 1000).toFixed(0)}}×${{((data.dimensions.width || 0) * 1000).toFixed(0)}}×${{((data.dimensions.thickness || 0) * 1000).toFixed(1)}} mm (Angle)`;
                }} else if (data.dimensions.shape === "USHAPE" || data.dimensions.shape === "U" || data.dimensions.shape === "CSHAPE" || data.dimensions.shape === "C") {{
                    dimText = `[ ${{((data.dimensions.depth || 0) * 1000).toFixed(0)}}×${{((data.dimensions.flange_width || data.dimensions.width || 0) * 1000).toFixed(0)}}×${{((data.dimensions.web_thickness || 0) * 1000).toFixed(1)}}×${{((data.dimensions.flange_thickness || 0) * 1000).toFixed(1)}} mm (Channel)`;
                }} else if (data.dimensions.shape === "TSHAPE" || data.dimensions.shape === "T") {{
                    dimText = `T ${{((data.dimensions.depth || 0) * 1000).toFixed(0)}}×${{((data.dimensions.flange_width || data.dimensions.width || 0) * 1000).toFixed(0)}} mm (Tee)`;
                }} else if (data.dimensions.shape === "RHS" || data.dimensions.shape === "RECTANGLE_HOLLOW" || data.dimensions.shape === "BOX_HOLLOW") {{
                    dimText = `RHS ${{((data.dimensions.depth || 0) * 1000).toFixed(0)}}×${{((data.dimensions.width || 0) * 1000).toFixed(0)}}×${{((data.dimensions.wall_thickness || 0) * 1000).toFixed(1)}} mm (Hollow Box)`;
                }} else if (data.dimensions.shape === "ARBITRARY" || data.dimensions.shape === "ARBITRARY_CLOSED" || data.dimensions.shape === "POLYGON" || data.dimensions.shape === "ARBITRARY_WITH_VOIDS") {{
                    const ptsCount = data.dimensions.points ? data.dimensions.points.length : 0;
                    const voidsCount = data.dimensions.voids ? data.dimensions.voids.length : 0;
                    dimText = `Arbitrary (${{ptsCount}} pts, ${{voidsCount}} voids, ${{((data.dimensions.width || 0) * 1000).toFixed(0)}}×${{((data.dimensions.depth || 0) * 1000).toFixed(0)}} mm)`;
                }} else if (data.dimensions.area !== undefined) {{
                    dimText = `${{data.dimensions.area.toFixed(2)}} m² (Slope: ${{data.dimensions.slope_degrees || 0}}°)`;
                }} else if (data.dimensions.length !== undefined) {{
                    dimText = `${{data.dimensions.length.toFixed(2)}}m (L)`;
                    if (data.dimensions.width !== undefined) dimText += ` × ${{data.dimensions.width.toFixed(2)}}m (W)`;
                    if (data.dimensions.thickness !== undefined) dimText += ` × ${{data.dimensions.thickness.toFixed(2)}}m (Thk)`;
                    if (data.dimensions.height !== undefined) dimText += ` × ${{data.dimensions.height.toFixed(2)}}m (H)`;
                    if (data.dimensions.depth !== undefined) dimText += ` × ${{data.dimensions.depth.toFixed(2)}}m (D)`;
                }} else if (data.dimensions.width !== undefined) {{
                    dimText = `${{data.dimensions.width.toFixed(2)}}m (W) × ${{data.dimensions.depth.toFixed(2)}}m (D) × ${{data.dimensions.height.toFixed(2)}}m (H)`;
                }}
            }}

            const posText = data.position ? `(${{data.position[0].toFixed(2)}}, ${{data.position[1].toFixed(2)}}, ${{data.position[2].toFixed(2)}})` : '-';

            let memberRow = '';
            if (data.member_name) {{
                const colorDot = data.color ? `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${{data.color}};margin-right:6px;"></span>` : '';
                memberRow = `<div class="data-row"><span class="data-label">Member</span><span class="data-value">${{colorDot}}${{data.member_name}}</span></div>`;
            }}

            let profileRow = '';
            if (data.profile) {{
                profileRow = `<div class="data-row"><span class="data-label">Profile</span><span class="data-value">${{data.profile}}</span></div>`;
            }}

            let mepRow = '';
            if (data.system_name_th) {{
                const colorDot = data.color ? `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${{data.color}};margin-right:6px;"></span>` : '';
                mepRow += `<div class="data-row"><span class="data-label">System</span><span class="data-value">${{colorDot}}${{data.system_name_th}}</span></div>`;
            }}
            if (data.fixture_name_th) {{
                const colorDot = data.color ? `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${{data.color}};margin-right:6px;"></span>` : '';
                mepRow += `<div class="data-row"><span class="data-label">Fixture</span><span class="data-value">${{colorDot}}${{data.fixture_name_th}}</span></div>`;
            }}
            if (data.predefined_type) {{
                mepRow += `<div class="data-row"><span class="data-label">PredefinedType</span><span class="data-value">${{data.predefined_type}}</span></div>`;
            }}
            if (data.ports) {{
                if (data.ports.cold_water_in) {{
                    mepRow += `<div class="data-row"><span class="data-label">CW Inlet</span><span class="data-value">Ø ${{ (data.ports.cold_water_in * 1000).toFixed(0) }} mm</span></div>`;
                }}
                if (data.ports.hot_water_in) {{
                    mepRow += `<div class="data-row"><span class="data-label">HW Inlet</span><span class="data-value">Ø ${{ (data.ports.hot_water_in * 1000).toFixed(0) }} mm</span></div>`;
                }}
                if (data.ports.waste_out) {{
                    mepRow += `<div class="data-row"><span class="data-label">Waste Outlet</span><span class="data-value">Ø ${{ (data.ports.waste_out * 1000).toFixed(0) }} mm</span></div>`;
                }}
            }}
            if (data.dimensions && data.dimensions.diameter !== undefined) {{
                const dia_mm = (data.dimensions.diameter * 1000).toFixed(0);
                mepRow += `<div class="data-row"><span class="data-label">Pipe Dia</span><span class="data-value">Ø ${{dia_mm}} mm (${{data.dimensions.diameter}}m)</span></div>`;
            }}
            if (data.dimensions && data.dimensions.slope) {{
                const slope_pct = (data.dimensions.slope * 100).toFixed(1);
                mepRow += `<div class="data-row"><span class="data-label">Slope</span><span class="data-value">${{slope_pct}}% (1:${{Math.round(1/data.dimensions.slope)}})</span></div>`;
            }}
            if (data.predefined_type) {{
                mepRow += `<div class="data-row"><span class="data-label">Type</span><span class="data-value">${{data.predefined_type}}</span></div>`;
            }}
            if (data.wattage || data.power_watts) {{
                mepRow += `<div class="data-row"><span class="data-label">Power</span><span class="data-value">${{data.power_watts || data.wattage}} W</span></div>`;
            }}
            if (data.luminous_flux_lumens) {{
                mepRow += `<div class="data-row"><span class="data-label">Luminous Flux</span><span class="data-value">${{data.luminous_flux_lumens}} lm</span></div>`;
            }}
            if (data.color_temperature_kelvin) {{
                mepRow += `<div class="data-row"><span class="data-label">Color Temp</span><span class="data-value">${{data.color_temperature_kelvin}} K</span></div>`;
            }}
            if (data.voltage) {{
                mepRow += `<div class="data-row"><span class="data-label">Voltage</span><span class="data-value">${{data.voltage}} V</span></div>`;
            }}
            if (data.phases) {{
                mepRow += `<div class="data-row"><span class="data-label">Phases</span><span class="data-value">${{data.phases}}</span></div>`;
            }}
            if (data.main_breaker_rating_amperes) {{
                mepRow += `<div class="data-row"><span class="data-label">Main Breaker</span><span class="data-value">${{data.main_breaker_rating_amperes}} A</span></div>`;
            }}
            if (data.circuits_count || data.poles_count) {{
                mepRow += `<div class="data-row"><span class="data-label">Poles/Circuits</span><span class="data-value">${{data.poles_count || data.circuits_count}} poles</span></div>`;
            }}
            if (data.cooling_capacity_btu) {{
                mepRow += `<div class="data-row"><span class="data-label">Cooling</span><span class="data-value">${{data.cooling_capacity_btu.toLocaleString()}} BTU/hr</span></div>`;
            }}
            if (data.flow_rate_cfm) {{
                mepRow += `<div class="data-row"><span class="data-label">Air Flow</span><span class="data-value">${{data.flow_rate_cfm}} CFM</span></div>`;
            }}
            if (data.covering_type) {{
                const colorDot = data.color ? `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${{data.color}};margin-right:6px;"></span>` : '';
                mepRow += `<div class="data-row"><span class="data-label">Finish Type</span><span class="data-value">${{colorDot}}${{data.covering_type}}</span></div>`;
            }}


            contentEl.innerHTML = `
                <div style="margin-bottom: 8px;"><span class="badge">${{data.class}}</span></div>
                <div class="data-row"><span class="data-label">Tag</span><span class="data-value">${{data.tag}}</span></div>
                <div class="data-row"><span class="data-label">Layer</span><span class="data-value">${{data.layer || 'general/other'}}</span></div>
                ${{memberRow}}
                ${{profileRow}}
                ${{mepRow}}
                <div class="data-row"><span class="data-label">Material</span><span class="data-value">${{data.material || '-'}}</span></div>
                <div class="data-row"><span class="data-label">Dimensions</span><span class="data-value">${{dimText}}</span></div>
                <div class="data-row"><span class="data-label">Position</span><span class="data-value">${{posText}}</span></div>
            `;
        }}

        // Animation loop
        function animate() {{
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        }}
        animate();

        // Responsive resize
        window.addEventListener('resize', () => {{
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }});
    </script>
</body>
</html>
"""
    return html_content


class _ViewerHTTPRequestHandler(BaseHTTPRequestHandler):
    html_content: bytes = b""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(self.html_content)))
        self.end_headers()
        self.wfile.write(self.html_content)

    def log_message(self, format: str, *args: Any) -> None:
        pass


def serve_viewer(
    html_content: str, port: int = 8000, open_browser: bool = True
) -> None:
    """
    Serve the viewer HTML content on a local HTTP server and optionally open in browser.
    """
    handler = type(
        "ViewerHandler",
        (_ViewerHTTPRequestHandler,),
        {"html_content": html_content.encode("utf-8")},
    )
    server = HTTPServer(("0.0.0.0", port), handler)
    url = f"http://localhost:{port}"

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
