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
    ResolvedWindow,
    resolve_manifest,
)
from debim.schema import ProjectManifest, load_manifest


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
        elements_data.append({
            "tag": col.tag,
            "class": "IfcColumn",
            "material": col.element.material,
            "position": [
                col.start_point[0],
                col.start_point[1],
                col.start_point[2] + col.height / 2.0,
            ],
            "rotation": [0, 0, 0],
            "dimensions": {
                "width": col.element.profile.width,
                "depth": col.element.profile.depth,
                "height": col.height,
            },
            "color": "#808080",
            "layer": col.layer,
        })

    # Beams
    for beam in resolved.beams:
        cx = (beam.start_point[0] + beam.end_point[0]) / 2.0
        cy = (beam.start_point[1] + beam.end_point[1]) / 2.0
        cz = beam.start_point[2] - beam.element.profile.depth / 2.0
        elements_data.append({
            "tag": beam.tag,
            "class": "IfcBeam",
            "material": beam.element.material,
            "position": [cx, cy, cz],
            "rotation": [0, 0, beam.rotation_angle],
            "dimensions": {
                "length": beam.span_length,
                "width": beam.element.profile.width,
                "depth": beam.element.profile.depth,
            },
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
            },
            "color": "#A8B2C1",
            "transparent": True,
            "opacity": 0.85,
            "layer": slab.layer,
        })

    # Stairs Assembly
    for stair in resolved.stairs:
        for step in stair.steps:
            elements_data.append({
                "tag": f"{stair.tag}-Step-{step.step_index}",
                "class": "IfcStairStep",
                "material": stair.element.finishes.tread_finish if (stair.element.finishes and stair.element.finishes.tread_finish) else stair.element.material,
                "position": [step.position[0], step.position[1], step.position[2]],
                "rotation": [0, 0, 0],
                "dimensions": {
                    "width": step.width,
                    "depth": step.tread,
                    "height": step.riser,
                },
                "color": "#D4A373",
                "layer": f"{stair.layer}/steps",
            })

        for stringer in stair.stringers:
            elements_data.append({
                "tag": f"{stringer.tag}-Centerline",
                "class": "IfcStairStringer",
                "geometry_type": "line",
                "points": [stringer.start_point, stringer.end_point],
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
                "member_name": "กระเบื้องมุงหลังคา (Roof Covering)",
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
                "member_name": member.name_th,
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
                "member_name": f"แนวสันหลังคา ({ridge.ridge_type})",
                "dimensions": {
                    "length": ridge.length,
                },
            })

    # Custom Elements
    for custom in resolved.custom_elements:
        tag_upper = custom.tag.upper()
        if "F2" in tag_upper or "FOOTING" in tag_upper:
            w, d, h = 0.8, 1.5, 0.8
            pos = [custom.position[0], custom.position[1], custom.position[2] - h / 2.0]
            color = "#8A8A8E"
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
        else:
            w, d, h = 0.8, 0.8, 1.5
            pos = [custom.position[0], custom.position[1], custom.position[2] + 0.75]
            color = "#9370DB"

        elements_data.append({
            "tag": custom.tag,
            "class": "IfcCustomElement",
            "material": "Custom Asset",
            "position": pos,
            "rotation": [0, 0, 0],
            "dimensions": {
                "width": w,
                "depth": d,
                "height": h,
            },
            "color": color,
            "layer": custom.layer,
        })

    # Coverings
    for cov in resolved.coverings:
        c_type = cov.covering_type
        if c_type == "CEILING":
            c_th = "ฝ้าเพดาน (Ceiling)"
            color = "#EDE8F5" if "GYPSUM" in (cov.element.material or "") else ("#E2E8F0" if "TBAR" in (cov.element.material or "") else "#D1D5DB")
            opacity = 0.50
        elif c_type == "FLOORING":
            c_th = "งานปูพื้น / ผิวตกแต่ง (Flooring)"
            color = "#CBD5E1"
            opacity = 0.85
        elif c_type == "SKIRTING":
            c_th = "บัวเชิงผนัง (Skirting)"
            color = "#B45309"
            opacity = 1.0
        else:
            c_th = f"วัสดุตกแต่งผิว ({c_type})"
            color = "#E5E7EB"
            opacity = 0.70

        if c_type == "SKIRTING" and cov.polygon and len(cov.polygon) >= 3:
            elements_data.append({
                "tag": cov.tag,
                "class": "IfcCovering",
                "material": cov.element.material,
                "geometry_type": "line_loop",
                "points": cov.polygon,
                "color": color,
                "linewidth": 3,
                "layer": cov.layer,
                "covering_type": c_type,
                "member_name": f"{c_th} - {cov.element.material}",
                "dimensions": {
                    "length": cov.perimeter or cov.area,
                },
            })
        elif cov.polygon and len(cov.polygon) >= 3:
            elements_data.append({
                "tag": cov.tag,
                "class": "IfcCovering",
                "material": cov.element.material,
                "geometry_type": "polygon",
                "points": cov.polygon,
                "color": color,
                "layer": cov.layer,
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
                "layer": cov.layer,
                "covering_type": c_type,
                "member_name": f"{c_th} - {cov.element.material}",
                "transparent": True,
                "opacity": opacity,
            })

    # MEP Elements: Pipes
    for pipe in resolved.pipes:
        sys_th = {
            "COLD_WATER": "ท่อน้ำดี (Cold Water)",
            "HOT_WATER": "ท่อน้ำร้อน (Hot Water)",
            "SOIL": "ท่อโสโครก/ส้วม (Soil Pipe)",
            "WASTE": "ท่อน้ำทิ้ง (Waste Pipe)",
            "VENT": "ท่อระบายอากาศ (Vent Pipe)",
            "DRAINAGE": "ท่อระบายน้ำรอบอาคาร (Drainage)",
            "REFRIGERANT": "ท่อน้ำยาแอร์ (Refrigerant Pipe)",
            "CONDENSATE": "ท่อน้ำทิ้งแอร์ (AC Condensate Drain)",
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
            "POWER": "ท่อร้อยสายไฟกำลัง (Power Conduit)",
            "LIGHTING": "ท่อร้อยสายไฟแสงสว่าง (Lighting Conduit)",
            "MAIN_FEEDER": "ท่อร้อยสายเมน (Main Feeder)",
            "COMMUNICATION": "สายสื่อสาร/LAN",
            "SOLAR": "สายไฟฟ้าโซล่าร์เซลล์",
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
            "WATER_CLOSET": "โถส้วม / สุขภัณฑ์ (WC)",
            "LAVATORY": "อ่างล้างหน้า (Lavatory)",
            "SHOWER": "ฝักบัวอาบน้ำ (Shower)",
            "KITCHEN_SINK": "อ่างล้างจาน (Kitchen Sink)",
            "FLOOR_DRAIN": "ตะแกรงดักกลิ่นที่พื้น (Floor Drain)",
            "GREASE_TRAP": "บ่อดักไขมัน (Grease Trap)",
            "SEPTIC_TANK": "ถังบำบัดน้ำเสีย (Septic Tank)",
            "WATER_TANK": "ถังเก็บน้ำบนดิน (Water Tank)",
            "WATER_PUMP": "ปั๊มน้ำอัตโนมัติ (Water Pump)",
        }.get(term.terminal_type, term.terminal_type)

        elements_data.append({
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
            "fixture_name_th": type_th,
        })

    # MEP Elements: Distribution Boards
    for board in resolved.distribution_boards:
        b_th = "ตู้ควบคุมไฟฟ้าหลัก (Consumer Unit / MDB)"
        elements_data.append({
            "tag": board.tag,
            "class": "IfcDistributionBoard",
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
            "fixture_name_th": b_th,
        })

    # MEP Elements: Lighting Fixtures
    for light in resolved.light_fixtures:
        l_th = {
            "DOWNLIGHT": "โคมไฟดาวน์ไลท์ (Downlight)",
            "LED_TUBE": "โคมไฟรางนีออน/LED (LED Tube)",
            "PENDANT": "โคมไฟแขวน (Pendant Lamp)",
            "WALL_LAMP": "โคมไฟกิ่งติดผนัง (Wall Lamp)",
            "FLOODLIGHT": "โคมไฟฟลัดไลท์ (Floodlight)",
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
            "wattage": light.wattage,
            "fixture_name_th": l_th,
        })

    # MEP Elements: Switches
    for sw in resolved.switches:
        s_th = f"สวิตช์ไฟ {sw.gangs} ช่อง ({sw.switch_type})"
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
        o_th = f"เต้ารับไฟฟ้า ({out.outlet_type})"
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
            "fixture_name_th": o_th,
        })

    # MEP Elements: Ducts
    for duct in resolved.ducts:
        sys_th = {
            "SUPPLY_AIR": "ท่อลมจ่าย (Supply Air Duct)",
            "RETURN_AIR": "ท่อลมกลับ (Return Air Duct)",
            "EXHAUST_AIR": "ท่อระบายอากาศ/ดูดควัน (Exhaust Air Duct)",
            "FRESH_AIR": "ท่อเติมอากาศบริสุทธิ์ (Fresh Air Duct)",
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
            "EXHAUST_FAN_CEILING": "พัดลมดูดอากาศติดเพดาน (Ceiling Exhaust Fan)",
            "EXHAUST_FAN_WALL": "พัดลมดูดอากาศติดผนัง (Wall Exhaust Fan)",
            "KITCHEN_HOOD": "ฮูดดูดควันห้องครัว (Kitchen Range Hood)",
            "SUPPLY_DIFFUSER": "หน้ากากหัวจ่ายลม (Supply Diffuser)",
            "RETURN_GRILLE": "หน้ากากลมกลับ (Return Grille)",
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
            "AC_INDOOR_WALL": "เครื่องปรับอากาศแบบติดผนัง (Wall Mounted AC)",
            "AC_INDOOR_CASSETTE": "เครื่องปรับอากาศแบบฝังฝ้า 4 ทิศทาง (Cassette AC)",
            "AC_INDOOR_CONCEALED": "เครื่องปรับอากาศแบบซ่อนในฝ้า (Concealed Duct AC)",
            "AC_OUTDOOR_CONDENSER": "คอนเดนซิ่งยูนิตภายนอก (Outdoor Condensing Unit)",
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
    }, indent=2)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>debim 3D Viewer - {proj.name}</title>
    <!-- CDN-hosted Three.js and OrbitControls -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
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
            top: 16px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            gap: 8px;
            background: rgba(20, 24, 33, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            padding: 6px 12px;
            border-radius: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            z-index: 100;
        }}
        .view-btn {{
            background: #2a3a4e;
            color: #e0e0e0;
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .view-btn:hover {{
            background: #3b82f6;
            color: #ffffff;
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
        <button class="view-btn" onclick="setView('top')">📐 ผังพื้น (Top View)</button>
        <button class="view-btn" onclick="setView('iso')">🏢 3D Isometric</button>
        <button class="view-btn" onclick="setView('front')">↔️ ด้านหน้า (Front)</button>
        <button class="view-btn" onclick="setView('side')">↕️ ด้านข้าง (Side)</button>
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
        <div><span style="color:#ff4d4d; font-weight:bold;">🔴 แกน X:</span> แนวนอน</div>
        <div><span style="color:#4dff4d; font-weight:bold;">🟢 แกน Y:</span> แนวตั้ง</div>
        <div><span style="color:#4da6ff; font-weight:bold;">🔵 แกน Z:</span> Elevation</div>
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
        container.appendChild(renderer.domElement);

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
            ctx.fillStyle = 'rgba(25, 30, 42, 0.88)';
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
            sprite.scale.set(4, 4, 1);
            return sprite;
        }}

        // Render Grid Lines & Ground
        const allX = Object.values(sceneData.grids.axes_x);
        const allY = Object.values(sceneData.grids.axes_y);
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

        // X Grids
        Object.entries(sceneData.grids.axes_x).forEach(([name, xVal]) => {{
            const pts = [
                new THREE.Vector3(xVal, minGridY - 6, 0),
                new THREE.Vector3(xVal, maxGridY + 6, 0)
            ];
            const geom = new THREE.BufferGeometry().setFromPoints(pts);
            const line = new THREE.Line(geom, gridLineMat);
            line.computeLineDistances();
            gridGroup.add(line);

            const topBubble = makeGridSprite(name, '#38bdf8');
            topBubble.position.set(xVal, maxGridY + 8, 0.1);
            gridGroup.add(topBubble);
            const botBubble = makeGridSprite(name, '#38bdf8');
            botBubble.position.set(xVal, minGridY - 8, 0.1);
            gridGroup.add(botBubble);
        }});

        // Y Grids
        Object.entries(sceneData.grids.axes_y).forEach(([name, yVal]) => {{
            const pts = [
                new THREE.Vector3(minGridX - 6, yVal, 0),
                new THREE.Vector3(maxGridX + 6, yVal, 0)
            ];
            const geom = new THREE.BufferGeometry().setFromPoints(pts);
            const line = new THREE.Line(geom, gridLineMat);
            line.computeLineDistances();
            gridGroup.add(line);

            const leftBubble = makeGridSprite(name, '#4ade80');
            leftBubble.position.set(minGridX - 8, yVal, 0.1);
            gridGroup.add(leftBubble);
            const rightBubble = makeGridSprite(name, '#4ade80');
            rightBubble.position.set(maxGridX + 8, yVal, 0.1);
            gridGroup.add(rightBubble);
        }});

        const axesHelper = new THREE.AxesHelper(15);
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

        sceneData.elements.forEach(data => {{
            let object3D;
            const dim = data.dimensions;

            if (data.geometry_type === "line" || data.geometry_type === "line_loop") {{
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
                let geometry;
                if (data.class === "IfcColumn") {{
                    geometry = new THREE.BoxGeometry(dim.width, dim.depth, dim.height);
                }} else if (data.class === "IfcBeam") {{
                    geometry = new THREE.BoxGeometry(dim.length, dim.width, dim.depth);
                }} else if (data.class === "IfcWall") {{
                    geometry = new THREE.BoxGeometry(dim.length, dim.thickness, dim.height);
                }} else if (data.class === "IfcDoor" || data.class === "IfcWindow") {{
                    geometry = new THREE.BoxGeometry(dim.width, dim.thickness, dim.height);
                }} else {{
                    geometry = new THREE.BoxGeometry(dim.width, dim.depth, dim.height);
                }}

                const matOptions = {{
                    color: new THREE.Color(data.color),
                    roughness: 0.5,
                    metalness: 0.1
                }};
                if (data.transparent) {{
                    matOptions.transparent = true;
                    matOptions.opacity = data.opacity || 0.6;
                }}

                const material = new THREE.MeshStandardMaterial(matOptions);
                const mesh = new THREE.Mesh(geometry, material);

                mesh.position.set(...data.position);
                mesh.rotation.set(...data.rotation);

                const edges = new THREE.EdgesGeometry(geometry);
                const line = new THREE.LineSegments(
                    edges,
                    new THREE.LineBasicMaterial({{ color: 0x000000, linewidth: 1 }})
                );
                mesh.add(line);
                object3D = mesh;
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

        // Camera position setup
        camera.position.set(centerX, centerY, 160);
        camera.up.set(0, 1, 0);
        controls.target.set(centerX, centerY, 0);
        controls.minPolarAngle = 0;
        controls.maxPolarAngle = 0;
        controls.update();

        window.setView = function(mode) {{
            if (mode === 'top') {{
                camera.position.set(centerX, centerY, 160);
                camera.up.set(0, 1, 0);
                controls.target.set(centerX, centerY, 0);
                controls.minPolarAngle = 0;
                controls.maxPolarAngle = 0;
            }} else if (mode === 'iso') {{
                camera.position.set(centerX + 60, centerY - 80, 60);
                camera.up.set(0, 0, 1);
                controls.target.set(centerX, centerY, 0);
                controls.minPolarAngle = 0;
                controls.maxPolarAngle = Math.PI;
            }} else if (mode === 'front') {{
                camera.position.set(centerX, minGridY - 90, 15);
                camera.up.set(0, 0, 1);
                controls.target.set(centerX, centerY, 0);
                controls.minPolarAngle = 0;
                controls.maxPolarAngle = Math.PI;
            }} else if (mode === 'side') {{
                camera.position.set(maxGridX + 70, centerY, 15);
                camera.up.set(0, 0, 1);
                controls.target.set(centerX, centerY, 0);
                controls.minPolarAngle = 0;
                controls.maxPolarAngle = Math.PI;
            }}
            controls.update();
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
            const intersects = raycaster.intersectObjects(pickableObjects);

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
                if (data.dimensions.area !== undefined) {{
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
                memberRow = `<div class="data-row"><span class="data-label">ชิ้นส่วน (Member)</span><span class="data-value">${{colorDot}}${{data.member_name}}</span></div>`;
            }}

            let profileRow = '';
            if (data.profile) {{
                profileRow = `<div class="data-row"><span class="data-label">หน้าตัด (Profile)</span><span class="data-value">${{data.profile}}</span></div>`;
            }}

            let mepRow = '';
            if (data.system_name_th) {{
                const colorDot = data.color ? `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${{data.color}};margin-right:6px;"></span>` : '';
                mepRow += `<div class="data-row"><span class="data-label">ระบบ (System)</span><span class="data-value">${{colorDot}}${{data.system_name_th}}</span></div>`;
            }}
            if (data.fixture_name_th) {{
                const colorDot = data.color ? `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${{data.color}};margin-right:6px;"></span>` : '';
                mepRow += `<div class="data-row"><span class="data-label">อุปกรณ์ (Fixture)</span><span class="data-value">${{colorDot}}${{data.fixture_name_th}}</span></div>`;
            }}
            if (data.dimensions && data.dimensions.diameter !== undefined) {{
                const dia_mm = (data.dimensions.diameter * 1000).toFixed(0);
                mepRow += `<div class="data-row"><span class="data-label">ขนาดท่อ (Dia)</span><span class="data-value">Ø ${{dia_mm}} mm (${{data.dimensions.diameter}}m)</span></div>`;
            }}
            if (data.dimensions && data.dimensions.slope) {{
                const slope_pct = (data.dimensions.slope * 100).toFixed(1);
                mepRow += `<div class="data-row"><span class="data-label">ความลาดชัน (Slope)</span><span class="data-value">${{slope_pct}}% (1:${{Math.round(1/data.dimensions.slope)}})</span></div>`;
            }}
            if (data.wattage) {{
                mepRow += `<div class="data-row"><span class="data-label">กำลังไฟฟ้า (Power)</span><span class="data-value">${{data.wattage}} W</span></div>`;
            }}
            if (data.circuits_count) {{
                mepRow += `<div class="data-row"><span class="data-label">จำนวนวงจร (Circuits)</span><span class="data-value">${{data.circuits_count}} วงจรย่อย</span></div>`;
            }}
            if (data.cooling_capacity_btu) {{
                mepRow += `<div class="data-row"><span class="data-label">ขนาดทำความเย็น (Cooling)</span><span class="data-value">${{data.cooling_capacity_btu.toLocaleString()}} BTU/hr</span></div>`;
            }}
            if (data.flow_rate_cfm) {{
                mepRow += `<div class="data-row"><span class="data-label">อัตราลมระบาย (Air Flow)</span><span class="data-value">${{data.flow_rate_cfm}} CFM</span></div>`;
            }}
            if (data.covering_type) {{
                const colorDot = data.color ? `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background-color:${{data.color}};margin-right:6px;"></span>` : '';
                mepRow += `<div class="data-row"><span class="data-label">ประเภทงานตกแต่ง</span><span class="data-value">${{colorDot}}${{data.covering_type}}</span></div>`;
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
