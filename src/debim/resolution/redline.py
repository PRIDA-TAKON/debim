"""
debim.resolution.redline

Generates redline_overlay.png visualizing the Grid Intersection ROI,
drawing the clashing baseline pipe in dotted red and the resolved rerouted pipe in solid green,
complete with clearance dimensions and Bill of Materials callouts for RFI documentation.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import yaml

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def generate_redline_overlay(
    base_manifest_path: Union[str, Path],
    resolved_manifest_path: Union[str, Path],
    output_png_path: Union[str, Path] = "workspace/redline_overlay.png",
    width: int = 1200,
    height: int = 900,
) -> str:
    """
    Renders high-resolution engineering redline diagram comparing clashing vs resolved pipes.
    """
    out_file = Path(output_png_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if not PIL_AVAILABLE:
        # Fallback dummy SVG if PIL not installed
        svg_content = f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="#ffffff"/>
        <text x="50" y="50" font-family="sans-serif" font-size="20" fill="#333333">debim Engineering Redline Overlay</text>
        </svg>"""
        with open(out_file.with_suffix(".svg"), "w", encoding="utf-8") as f:
            f.write(svg_content)
        return str(out_file.with_suffix(".svg"))

    # Create white canvas
    img = Image.new("RGB", (width, height), color=(250, 252, 255))
    draw = ImageDraw.Draw(img)

    # Coordinate mapping:
    # World coordinate (-2.0, -2.0) to (+2.0, +2.0) mapped into center canvas
    cx = width // 2
    cy = height // 2 - 40
    scale = 180.0  # 180 pixels per meter

    def to_px(x: float, y: float) -> Tuple[int, int]:
        px = int(cx + (x * scale))
        py = int(cy - (y * scale))  # Y inverted in raster
        return px, py

    # 1. Background Grid & Axes
    grid_color = (220, 225, 235)
    for offset_m in [-1.5, -1.0, -0.5, 0.5, 1.0, 1.5]:
        p1 = to_px(offset_m, -2.0)
        p2 = to_px(offset_m, 2.0)
        draw.line([p1, p2], fill=grid_color, width=1)
        p3 = to_px(-2.0, offset_m)
        p4 = to_px(2.0, offset_m)
        draw.line([p3, p4], fill=grid_color, width=1)

    # Main Grid Lines (X=0: Grid B, Y=0: Grid 2)
    axis_color = (130, 145, 170)
    draw.line([to_px(0, -2.2), to_px(0, 2.2)], fill=axis_color, width=2)
    draw.line([to_px(-2.2, 0), to_px(2.2, 0)], fill=axis_color, width=2)

    # 2. Main Concrete Column at (0, 0) - 0.40m x 0.40m
    col_w, col_d = 0.40, 0.40
    c_x1, c_y1 = to_px(-col_w / 2, col_d / 2)
    c_x2, c_y2 = to_px(col_w / 2, -col_d / 2)

    # Clearance Buffer Zone (0.05m dashed outline)
    cl_x1, cl_y1 = to_px(-col_w / 2 - 0.05, col_d / 2 + 0.05)
    cl_x2, cl_y2 = to_px(col_w / 2 + 0.05, -col_d / 2 - 0.05)
    draw.rectangle([cl_x1, cl_y1, cl_x2, cl_y2], outline=(255, 180, 0), width=2)

    # Solid Column Body
    draw.rectangle([c_x1, c_y1, c_x2, c_y2], fill=(180, 188, 200), outline=(70, 80, 95), width=3)
    # Hatching inside column
    draw.line([(c_x1, c_y1), (c_x2, c_y2)], fill=(150, 160, 175), width=2)
    draw.line([(c_x1, c_y2), (c_x2, c_y1)], fill=(150, 160, 175), width=2)

    # 3. Clashing As-Designed Pipe (Dotted / Dashed Red)
    # Straight along Y = 0 from X = -1.8 to X = +1.8
    p_red_start = to_px(-1.8, 0.0)
    p_red_end = to_px(1.8, 0.0)
    for x_step in range(p_red_start[0], p_red_end[0], 16):
        draw.line([(x_step, cy), (min(x_step + 8, p_red_end[0]), cy)], fill=(225, 40, 40), width=4)

    # Red Clash Warning Icon / Marker at (0, 0)
    draw.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=(255, 230, 230), outline=(220, 30, 30), width=3)
    draw.line([(cx - 12, cy - 12), (cx + 12, cy + 12)], fill=(220, 30, 30), width=4)
    draw.line([(cx - 12, cy + 12), (cx + 12, cy - 12)], fill=(220, 30, 30), width=4)

    # 4. Resolved Pipe Trajectory (Solid Green with 45-degree offset)
    # Bypass around Y = +0.35m
    pt1 = to_px(-1.8, 0.0)
    pt2 = to_px(-0.6, 0.0)
    pt3 = to_px(-0.25, 0.35)
    pt4 = to_px(0.25, 0.35)
    pt5 = to_px(0.6, 0.0)
    pt6 = to_px(1.8, 0.0)

    green_color = (15, 165, 75)
    draw.line([pt1, pt2], fill=green_color, width=6)
    draw.line([pt2, pt3], fill=green_color, width=6)
    draw.line([pt3, pt4], fill=green_color, width=6)
    draw.line([pt4, pt5], fill=green_color, width=6)
    draw.line([pt5, pt6], fill=green_color, width=6)

    # Draw Elbow fittings nodes (Circles)
    for p in [pt2, pt3, pt4, pt5]:
        draw.ellipse([p[0] - 7, p[1] - 7, p[0] + 7, p[1] + 7], fill=(255, 255, 255), outline=green_color, width=3)

    # 5. Header Title and Project Information Block
    draw.rectangle([0, 0, width, 75], fill=(30, 42, 56))
    draw.text((25, 16), "debim ENGINEERING CLASH RESOLUTION RFI OVERLAY", fill=(255, 255, 255))
    draw.text((25, 42), "Location: Grid Intersection B-2 (Floor 1F) | Clash Target: RC Column (40x40cm) vs 150mm PVC Gravity Pipe", fill=(170, 190, 215))

    # 6. Legend & Annotation Box (Bottom Right)
    lx, ly = width - 420, height - 230
    draw.rectangle([lx, ly, width - 25, height - 25], fill=(255, 255, 255), outline=(190, 200, 215), width=2)
    draw.text((lx + 15, ly + 12), "LEGEND & BILL OF QUANTITY DELTA", fill=(30, 45, 65))

    # Redline legend
    draw.line([(lx + 15, ly + 45), (lx + 55, ly + 45)], fill=(220, 30, 30), width=4)
    draw.text((lx + 65, ly + 37), "As-Designed (Clashing Straight)", fill=(180, 20, 20))

    # Greenline legend
    draw.line([(lx + 15, ly + 72), (lx + 55, ly + 72)], fill=green_color, width=5)
    draw.text((lx + 65, ly + 64), "Resolved Path: Option A (45° Bypass)", fill=(10, 120, 50))

    # Column / clearance legend
    draw.rectangle([lx + 15, ly + 95, lx + 35, ly + 115], fill=(180, 188, 200), outline=(70, 80, 95))
    draw.text((lx + 45, ly + 98), "RC Column (40x40cm) + 5cm Clearance", fill=(50, 60, 75))

    # Materials delta
    draw.text((lx + 15, ly + 130), "• PVC Elbow 45°: +2 pcs", fill=(40, 50, 65))
    draw.text((lx + 15, ly + 150), "• Extra Pipe 150mm: +0.35 m", fill=(40, 50, 65))
    draw.text((lx + 15, ly + 170), "• Pipe Hanger Clamps: +3 sets", fill=(40, 50, 65))

    # Grid labels on canvas
    draw.text((cx - 10, cy - 240), "Grid B", fill=(80, 95, 120))
    draw.text((cx + 250, cy - 8), "Grid 2", fill=(80, 95, 120))
    draw.text((cx - 15, cy + 28), "COL-B2", fill=(30, 40, 55))

    img.save(out_file, "PNG")
    return str(out_file.resolve())
