"""
Automated Multi-Discipline Drawing Sheet Index Generator for debim.
Discovers, classifies, aggregates, and renders Drawing Sheet Indices across
General (G), Architectural (A), Structural (S), Electrical (EE), and Sanitation (SN) disciplines.
"""

from pathlib import Path
import re
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, Field

from debim.resolver import ResolvedManifest, resolve_manifest
from debim.schema import ProjectManifest, load_manifest

DisciplineCode = Literal["G", "A", "S", "EE", "SN", "OTHER"]

DISCIPLINE_TITLES_TH: Dict[str, str] = {
    "G": "หมวดงานทั่วไป (GENERAL / MASTER INDEX)",
    "A": "หมวดงานสถาปัตยกรรม (ARCHITECTURAL DRAWINGS)",
    "S": "หมวดงานวิศวกรรมโครงสร้าง (STRUCTURAL DRAWINGS)",
    "EE": "หมวดงานวิศวกรรมไฟฟ้า (ELECTRICAL DRAWINGS)",
    "SN": "หมวดงานวิศวกรรมสุขาภิบาล (SANITATION & PLUMBING DRAWINGS)",
    "OTHER": "หมวดงานอื่นๆ (OTHER DRAWINGS)",
}

DISCIPLINE_NAMES_TH: Dict[str, str] = {
    "G": "งานทั่วไป",
    "A": "งานสถาปัตยกรรม",
    "S": "งานวิศวกรรมโครงสร้าง",
    "EE": "งานวิศวกรรมไฟฟ้า",
    "SN": "งานวิศวกรรมสุขาภิบาล",
    "OTHER": "งานอื่นๆ",
}


class DrawingIndexItem(BaseModel):
    """Drawing index entry for tabular sheet list."""

    sheet_no: str
    title: str
    scale: str = "1:100"
    revision: str = "01"
    remarks: str = ""
    discipline: DisciplineCode = "A"


def infer_discipline(sheet_no: str, explicit_discipline: Optional[str] = None) -> DisciplineCode:
    """Infer discipline code (G, A, S, EE, SN, OTHER) from sheet number or explicit label."""
    if explicit_discipline:
        disc_up = explicit_discipline.upper().strip()
        if disc_up in ("G", "GENERAL", "MASTER"):
            return "G"
        if disc_up in ("A", "ARCH", "ARCHITECTURAL"):
            return "A"
        if disc_up in ("S", "STRUCT", "STRUCTURAL"):
            return "S"
        if disc_up in ("EE", "ELEC", "ELECTRICAL"):
            return "EE"
        if disc_up in ("SN", "SAN", "SANITATION", "PLUMBING"):
            return "SN"

    s_no = (sheet_no or "").upper().strip()
    if s_no.startswith("G-") or s_no.startswith("G0") or s_no == "G":
        return "G"
    if s_no.startswith("A-") or s_no.startswith("A0") or s_no.startswith("ARCH-"):
        return "A"
    if s_no.startswith("S-") or s_no.startswith("S0") or s_no.startswith("ST-"):
        return "S"
    if s_no.startswith("EE-") or s_no.startswith("E-") or s_no.startswith("EE0"):
        return "EE"
    if s_no.startswith("SN-") or s_no.startswith("SAN-") or s_no.startswith("P-"):
        return "SN"

    return "OTHER"


def _natural_sheet_sort_key(sheet_no: str) -> Tuple[int, int, str]:
    """Sort key for natural sheet ordering e.g. G-001, A-001, A-101, A-102, S-001..."""
    disc = infer_discipline(sheet_no)
    disc_order = {"G": 0, "A": 1, "S": 2, "EE": 3, "SN": 4, "OTHER": 5}[disc]

    # Extract trailing digits
    match = re.search(r"(\d+)", sheet_no)
    num = int(match.group(1)) if match else 9999
    return (disc_order, num, sheet_no)


def generate_default_project_sheets(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
) -> List[DrawingIndexItem]:
    """Generate default complete multi-discipline drawing sheet list from project manifest."""
    if isinstance(manifest_or_resolved, (str, Path)):
        manifest_obj = load_manifest(manifest_or_resolved)
        resolved = resolve_manifest(manifest_obj)
    elif isinstance(manifest_or_resolved, ProjectManifest):
        resolved = resolve_manifest(manifest_or_resolved)
    else:
        resolved = manifest_or_resolved

    storeys = resolved.manifest.spatial_structure.storeys or []

    items: List[DrawingIndexItem] = [
        DrawingIndexItem(
            sheet_no="G-001",
            title="สารบัญแบบรวมทั้งโครงการ (MASTER DRAWING SHEET INDEX)",
            scale="N.T.S.",
            revision="01",
            remarks="งานทั่วไป",
            discipline="G",
        ),
        DrawingIndexItem(
            sheet_no="A-001",
            title="สารบัญแบบและรายการประกอบแบบงานสถาปัตยกรรม (ARCHITECTURAL INDEX)",
            scale="N.T.S.",
            revision="01",
            remarks="งานสถาปัตยกรรม",
            discipline="A",
        ),
    ]

    # Architectural Storey Plans
    if storeys:
        for idx, st in enumerate(storeys, 1):
            items.append(
                DrawingIndexItem(
                    sheet_no=f"A-10{idx}",
                    title=f"แปลนพื้น {st.name} ({st.id} FLOOR PLAN)",
                    scale="1:100",
                    revision="01",
                    remarks="งานสถาปัตยกรรม",
                    discipline="A",
                )
            )
    else:
        items.append(
            DrawingIndexItem(
                sheet_no="A-101",
                title="แปลนพื้นชั้นล่าง (GROUND FLOOR PLAN)",
                scale="1:100",
                revision="01",
                remarks="งานสถาปัตยกรรม",
                discipline="A",
            )
        )

    # Architectural Elevations & Sections
    items.extend([
        DrawingIndexItem(
            sheet_no="A-201",
            title="รูปด้าน 1 - 2 (FRONT & REAR ELEVATIONS)",
            scale="1:100",
            revision="01",
            remarks="งานสถาปัตยกรรม",
            discipline="A",
        ),
        DrawingIndexItem(
            sheet_no="A-202",
            title="รูปด้าน 3 - 4 (LEFT & RIGHT ELEVATIONS)",
            scale="1:100",
            revision="01",
            remarks="งานสถาปัตยกรรม",
            discipline="A",
        ),
        DrawingIndexItem(
            sheet_no="A-301",
            title="รูปตัด A-A (CROSS SECTION A-A)",
            scale="1:100",
            revision="01",
            remarks="งานสถาปัตยกรรม",
            discipline="A",
        ),
        DrawingIndexItem(
            sheet_no="A-302",
            title="รูปตัด B-B (LONGITUDINAL SECTION B-B)",
            scale="1:100",
            revision="01",
            remarks="งานสถาปัตยกรรม",
            discipline="A",
        ),
        DrawingIndexItem(
            sheet_no="A-401",
            title="แบบขยายประตู-หน้าต่าง และรายการอุปกรณ์ (DOOR & WINDOW SCHEDULE)",
            scale="1:50",
            revision="01",
            remarks="งานสถาปัตยกรรม",
            discipline="A",
        ),
    ])

    # Structural Discipline
    items.extend([
        DrawingIndexItem(
            sheet_no="S-001",
            title="สารบัญแบบและรายการประกอบแบบงานวิศวกรรมโครงสร้าง (STRUCTURAL INDEX)",
            scale="N.T.S.",
            revision="01",
            remarks="งานวิศวกรรมโครงสร้าง",
            discipline="S",
        ),
        DrawingIndexItem(
            sheet_no="S-101",
            title="แปลนฐานราก เสาตลิ่ง และคานคอดิน (FOUNDATION & GROUND BEAM PLAN)",
            scale="1:100",
            revision="01",
            remarks="งานวิศวกรรมโครงสร้าง",
            discipline="S",
        ),
        DrawingIndexItem(
            sheet_no="S-102",
            title="แปลนโครงสร้างพื้นและคานชั้น 1 (FL.1 STRUCTURAL FRAMING PLAN)",
            scale="1:100",
            revision="01",
            remarks="งานวิศวกรรมโครงสร้าง",
            discipline="S",
        ),
        DrawingIndexItem(
            sheet_no="S-201",
            title="แบบขยายโครงสร้าง คสล. ฐานราก เสา คาน (RC STRUCTURAL DETAILS)",
            scale="1:25",
            revision="01",
            remarks="งานวิศวกรรมโครงสร้าง",
            discipline="S",
        ),
    ])

    # Electrical Discipline
    items.extend([
        DrawingIndexItem(
            sheet_no="EE-001",
            title="สารบัญแบบและรายการประกอบแบบงานวิศวกรรมไฟฟ้า (ELECTRICAL INDEX)",
            scale="N.T.S.",
            revision="01",
            remarks="งานวิศวกรรมไฟฟ้า",
            discipline="EE",
        ),
        DrawingIndexItem(
            sheet_no="EE-101",
            title="ไดอะแกรมเส้นเดียวไฟฟ้า และตารางโหลด (ELECTRICAL SINGLE LINE DIAGRAM)",
            scale="N.T.S.",
            revision="01",
            remarks="งานวิศวกรรมไฟฟ้า",
            discipline="EE",
        ),
    ])

    # Sanitation Discipline
    items.extend([
        DrawingIndexItem(
            sheet_no="SN-001",
            title="สารบัญแบบและรายการประกอบแบบงานวิศวกรรมสุขาภิบาล (SANITATION INDEX)",
            scale="N.T.S.",
            revision="01",
            remarks="งานวิศวกรรมสุขาภิบาล",
            discipline="SN",
        ),
        DrawingIndexItem(
            sheet_no="SN-101",
            title="ไดอะแกรมระบบสุขาภิบาลและประปา (SANITATION RISER DIAGRAM)",
            scale="N.T.S.",
            revision="01",
            remarks="งานวิศวกรรมสุขาภิบาล",
            discipline="SN",
        ),
    ])

    return items


def discover_and_aggregate_sheets(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    sheets_dir_or_configs: Optional[Union[Path, str, List[Any]]] = None,
) -> Tuple[List[DrawingIndexItem], int]:
    """
    Discover all generated/configured sheets across disciplines.
    Returns (aggregated_drawing_indices, total_sheet_count).
    """
    if sheets_dir_or_configs:
        from debim.draw.renderer import SheetConfig, load_sheet_config

        configs: List[SheetConfig] = []
        if isinstance(sheets_dir_or_configs, (str, Path)):
            p = Path(sheets_dir_or_configs)
            if p.is_dir():
                for yf in sorted(p.glob("*.yaml")) + sorted(p.glob("*.yml")):
                    configs.append(load_sheet_config(yf))
            elif p.is_file():
                configs.append(load_sheet_config(p))
        elif isinstance(sheets_dir_or_configs, list):
            for item in sheets_dir_or_configs:
                configs.append(load_sheet_config(item))

        if configs:
            items: List[DrawingIndexItem] = []
            for cfg in configs:
                disc = infer_discipline(cfg.id)
                remarks_str = cfg.title_block.fields[0].value if cfg.title_block.fields else DISCIPLINE_NAMES_TH.get(disc, "")
                items.append(
                    DrawingIndexItem(
                        sheet_no=cfg.id,
                        title=cfg.title,
                        scale=f"1:{cfg.scale}" if cfg.scale > 1 else "N.T.S.",
                        revision=cfg.revision,
                        remarks=remarks_str or DISCIPLINE_NAMES_TH.get(disc, ""),
                        discipline=disc,
                    )
                )

            # Sort items in natural discipline & sheet_no order
            items.sort(key=lambda x: _natural_sheet_sort_key(x.sheet_no))
            return items, len(items)

    # Fallback to auto-discovering from project manifest
    default_items = generate_default_project_sheets(manifest_or_resolved)
    default_items.sort(key=lambda x: _natural_sheet_sort_key(x.sheet_no))
    return default_items, len(default_items)


def render_sheet_index_svg(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    sheet_config: Optional[Any] = None,
    sheets_dir_or_configs: Optional[Union[Path, str, List[Any]]] = None,
) -> str:
    """
    Render complete Cover & Drawing Sheet Index drawing sheet (G-001, A-001, S-001, EE-001, SN-001).
    Displays total sheet count summary callout (e.g. 'รวมแบบทั้งชุด 48 แผ่น')
    and 5 tabular index columns: Sheet Number, Sheet Title, Scale, Revision, Remarks.
    """
    from debim.draw.renderer import SheetConfig, SheetRenderer

    if isinstance(manifest_or_resolved, (str, Path)):
        manifest_obj = load_manifest(manifest_or_resolved)
        resolved = resolve_manifest(manifest_obj)
    elif isinstance(manifest_or_resolved, ProjectManifest):
        resolved = resolve_manifest(manifest_or_resolved)
    else:
        resolved = manifest_or_resolved

    if sheet_config is None:
        cfg = SheetConfig(
            id="G-001",
            title="สารบัญแบบรวมทั้งโครงการ (MASTER DRAWING INDEX)",
            view_type="INDEX",
            paper_size="A3",
            scale=1,
        )
    elif isinstance(sheet_config, SheetConfig):
        cfg = sheet_config
    else:
        cfg = SheetConfig.model_validate(sheet_config)

    # Discover and aggregate all project drawing sheets
    all_index_items, total_count = discover_and_aggregate_sheets(resolved, sheets_dir_or_configs)

    # If sheet_config has explicit sheet_index items passed in, prioritize those
    if cfg.sheet_index:
        converted_items: List[DrawingIndexItem] = []
        for s_item in cfg.sheet_index:
            disc = infer_discipline(s_item.sheet_no)
            converted_items.append(
                DrawingIndexItem(
                    sheet_no=s_item.sheet_no,
                    title=s_item.title,
                    scale=s_item.scale,
                    revision=s_item.revision,
                    remarks=DISCIPLINE_NAMES_TH.get(disc, ""),
                    discipline=disc,
                )
            )
        if converted_items:
            all_index_items = converted_items
            total_count = len(converted_items)

    target_disc = infer_discipline(cfg.id)

    # Filter items if rendering discipline-specific cover index (e.g. A-001, S-001, EE-001, SN-001)
    if target_disc != "G" and cfg.id.endswith("001"):
        display_items = [it for it in all_index_items if it.discipline == target_disc or it.sheet_no == cfg.id]
    else:
        display_items = all_index_items

    paper_w, paper_h = cfg.get_paper_dimensions_mm()
    m_left, m_top, m_right, m_bottom = cfg.get_margins_mm()

    printable_x = m_left
    printable_y = m_top
    printable_w = paper_w - m_left - m_right
    printable_h = paper_h - m_top - m_bottom

    tb_width = cfg.title_block.width_mm if cfg.visibility.show_title_block else 0.0
    drawing_w = printable_w - tb_width - (5.0 if tb_width > 0 else 0.0)
    title_x = printable_x + printable_w - tb_width if tb_width > 0 else 0.0

    renderer = SheetRenderer(resolved, cfg)
    embedded_css = renderer._get_embedded_css() if hasattr(renderer, "_get_embedded_css") else ""

    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {paper_w:.1f} {paper_h:.1f}" width="{paper_w:.1f}mm" height="{paper_h:.1f}mm">',
        '  <defs>',
        '    <style type="text/css"><![CDATA[',
        f'{embedded_css}',
        '    ]]></style>',
        '  </defs>',
        '  <!-- Background -->',
        f'  <rect x="0" y="0" width="{paper_w:.1f}" height="{paper_h:.1f}" fill="#ffffff" />',
        '  <!-- Outer Sheet Border & Margin -->',
        f'  <rect x="{printable_x:.1f}" y="{printable_y:.1f}" width="{printable_w:.1f}" height="{printable_h:.1f}" class="sheet-border" fill="none" />',
        f'  <rect x="{printable_x + 2.0:.1f}" y="{printable_y + 2.0:.1f}" width="{printable_w - 4.0:.1f}" height="{printable_h - 4.0:.1f}" class="sheet-inner-border" fill="none" />',
        '  <!-- Drawing Viewport for Sheet Index -->',
        f'  <g id="index-viewport" transform="translate({printable_x:.1f}, {printable_y:.1f})">',
    ]

    # Header Title & Summary Banner
    main_title = f"สารบัญแบบ ({cfg.title.upper()})" if "สารบัญแบบ" not in cfg.title else cfg.title.upper()
    svg_lines.append(f'    <text x="5.0" y="10.0" font-family="Sarabun, sans-serif" font-size="5.5px" font-weight="bold" fill="#0f172a">{main_title}</text>')
    svg_lines.append(f'    <line x1="5.0" y1="12.5" x2="{drawing_w - 5.0:.1f}" y2="12.5" stroke="#0f172a" stroke-width="0.8" />')

    # Total Sheet Count Summary Callout Box (e.g. "รวมแบบทั้งชุด 48 แผ่น")
    summary_box_w = 110.0
    summary_box_x = drawing_w - summary_box_w - 5.0
    summary_text = f"รวมแบบทั้งชุด {total_count} แผ่น (TOTAL {total_count} SHEETS)"

    svg_lines.extend([
        f'    <rect x="{summary_box_x:.1f}" y="15.0" width="{summary_box_w:.1f}" height="9.0" fill="#f1f5f9" stroke="#0f172a" stroke-width="0.6" rx="1.0" />',
        f'    <text x="{summary_box_x + summary_box_w/2.0:.1f}" y="20.8" font-family="Sarabun, sans-serif" font-size="3.5px" font-weight="bold" text-anchor="middle" fill="#0f172a">{summary_text}</text>',
    ])

    # Table Geometry & Columns
    # 5 Tabular Columns:
    # 1. Sheet Number (เลขที่แบบ) - 30mm
    # 2. Sheet Title (ชื่อแบบ) - 130mm
    # 3. Scale (มาตราส่วน) - 30mm
    # 4. Revision (ครั้งที่แก้ไข) - 25mm
    # 5. Remarks (หมายเหตุ) - 50mm
    tbl_x = 5.0
    tbl_y = 28.0
    col_w_no = 32.0
    col_w_title = drawing_w - tbl_x - 32.0 - 28.0 - 22.0 - 45.0 - 5.0
    if col_w_title < 100.0:
        col_w_title = 120.0
    col_w_scale = 28.0
    col_w_rev = 22.0
    col_w_rem = 45.0

    c1_x = tbl_x
    c2_x = c1_x + col_w_no
    c3_x = c2_x + col_w_title
    c4_x = c3_x + col_w_scale
    c5_x = c4_x + col_w_rev
    tbl_total_w = col_w_no + col_w_title + col_w_scale + col_w_rev + col_w_rem

    # Table Header Row
    header_h = 7.5
    svg_lines.extend([
        f'    <rect x="{tbl_x:.1f}" y="{tbl_y:.1f}" width="{tbl_total_w:.1f}" height="{header_h:.1f}" fill="#1e293b" rx="0.5" />',
        f'    <text x="{c1_x + 3.0:.1f}" y="{tbl_y + 5.0:.1f}" font-family="Sarabun, sans-serif" font-size="3.2px" font-weight="bold" fill="#ffffff">เลขที่แบบ (SHEET NO.)</text>',
        f'    <text x="{c2_x + 4.0:.1f}" y="{tbl_y + 5.0:.1f}" font-family="Sarabun, sans-serif" font-size="3.2px" font-weight="bold" fill="#ffffff">ชื่อแบบ (SHEET TITLE)</text>',
        f'    <text x="{c3_x + col_w_scale/2.0:.1f}" y="{tbl_y + 5.0:.1f}" font-family="Sarabun, sans-serif" font-size="3.2px" font-weight="bold" text-anchor="middle" fill="#ffffff">มาตราส่วน (SCALE)</text>',
        f'    <text x="{c4_x + col_w_rev/2.0:.1f}" y="{tbl_y + 5.0:.1f}" font-family="Sarabun, sans-serif" font-size="3.2px" font-weight="bold" text-anchor="middle" fill="#ffffff">ครั้งที่แก้ไข (REV.)</text>',
        f'    <text x="{c5_x + 3.0:.1f}" y="{tbl_y + 5.0:.1f}" font-family="Sarabun, sans-serif" font-size="3.2px" font-weight="bold" fill="#ffffff">หมายเหตุ (REMARKS)</text>',
    ])

    curr_row_y = tbl_y + header_h
    row_h = 6.2

    # Group display items by discipline if Master Index G-001
    current_disc: Optional[str] = None

    for item in display_items:
        if curr_row_y + row_h > printable_h - 10.0:
            break

        # Render Discipline Header Divider Row if discipline changes in Master Index G-001
        if target_disc == "G" and item.discipline != current_disc:
            current_disc = item.discipline
            disc_title = DISCIPLINE_TITLES_TH.get(current_disc, f"หมวดงาน {current_disc}")
            svg_lines.extend([
                f'    <rect x="{tbl_x:.1f}" y="{curr_row_y:.1f}" width="{tbl_total_w:.1f}" height="{row_h:.1f}" fill="#cbd5e1" stroke="#94a3b8" stroke-width="0.3" />',
                f'    <text x="{tbl_x + 4.0:.1f}" y="{curr_row_y + 4.2:.1f}" font-family="Sarabun, sans-serif" font-size="2.8px" font-weight="bold" fill="#0f172a">{disc_title}</text>',
            ])
            curr_row_y += row_h
            if curr_row_y + row_h > printable_h - 10.0:
                break

        # Alternating Row Background
        bg_fill = "#f8fafc" if (len(svg_lines) % 2 == 0) else "#ffffff"
        svg_lines.append(f'    <rect x="{tbl_x:.1f}" y="{curr_row_y:.1f}" width="{tbl_total_w:.1f}" height="{row_h:.1f}" fill="{bg_fill}" stroke="#e2e8f0" stroke-width="0.3" />')

        # Cell Values
        title_disp = item.title[:65] + ("..." if len(item.title) > 65 else "")
        svg_lines.append(f'    <text x="{c1_x + 3.0:.1f}" y="{curr_row_y + 4.2:.1f}" font-family="Sarabun, sans-serif" font-size="2.8px" font-weight="bold" fill="#0f172a">{item.sheet_no}</text>')
        svg_lines.append(f'    <text x="{c2_x + 4.0:.1f}" y="{curr_row_y + 4.2:.1f}" font-family="Sarabun, sans-serif" font-size="2.8px" fill="#334155">{title_disp}</text>')
        svg_lines.append(f'    <text x="{c3_x + col_w_scale/2.0:.1f}" y="{curr_row_y + 4.2:.1f}" font-family="Sarabun, sans-serif" font-size="2.8px" text-anchor="middle" fill="#334155">{item.scale}</text>')
        svg_lines.append(f'    <text x="{c4_x + col_w_rev/2.0:.1f}" y="{curr_row_y + 4.2:.1f}" font-family="Sarabun, sans-serif" font-size="2.8px" text-anchor="middle" fill="#334155">{item.revision}</text>')
        svg_lines.append(f'    <text x="{c5_x + 3.0:.1f}" y="{curr_row_y + 4.2:.1f}" font-family="Sarabun, sans-serif" font-size="2.8px" fill="#64748b">{item.remarks}</text>')

        curr_row_y += row_h

    # Outer Table Boundary Line
    svg_lines.append(f'    <rect x="{tbl_x:.1f}" y="{tbl_y:.1f}" width="{tbl_total_w:.1f}" height="{curr_row_y - tbl_y:.1f}" fill="none" stroke="#0f172a" stroke-width="0.6" />')

    svg_lines.append('  </g> <!-- End index-viewport -->')

    # Standard Title Block
    if cfg.visibility.show_title_block:
        proj_name = cfg.project_name or resolved.manifest.project.name
        date_str = cfg.date or "2025-01-01"
        svg_lines.append(renderer._render_title_block_svg(title_x, printable_y, tb_width, printable_h, proj_name, date_str))

    svg_lines.append('</svg>')
    return "\n".join(svg_lines)
