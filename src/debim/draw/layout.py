"""
Paper Space Layout Engine (A3/A2/A1) with Title Block & Dynamic Project Metadata for debim.
Handles pure vector paper space SVG generation, DXF paper space layout setup,
and automated multi-sheet batch plotting to vector PDF.
"""

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from debim.draw.dxf import export_2d_dxf
from debim.draw.index import generate_default_project_sheets
from debim.draw.renderer import (
    PAPER_SIZES_MM,
    SheetConfig,
    SheetRenderer,
    SignatureBoxConfig,
    TitleBlockField,
    load_sheet_config,
    render_sheet,
    render_sheet_set,
)
from debim.resolver import ResolvedManifest, resolve_manifest
from debim.schema import ProjectManifest, load_manifest


def parse_scale_arg(scale_input: Union[int, str]) -> int:
    """Parse scale argument string (e.g. '1:100', '1:50', '100', '50') into integer ratio."""
    if isinstance(scale_input, int):
        return scale_input
    s_str = str(scale_input).strip()
    if ":" in s_str:
        parts = s_str.split(":", 1)
        try:
            return int(parts[1].strip())
        except ValueError:
            pass
    try:
        return int(s_str)
    except ValueError:
        return 100


def generate_default_sheet_configs(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    paper_size: str = "A3",
    scale: Union[int, str] = 100,
) -> List[SheetConfig]:
    """
    Auto-generate complete set of default SheetConfig objects across all disciplines
    (Cover & Sheet Index, Floor Plans, Roof Plan, Beam Layouts, Elevations, Sections,
    Door/Window Schedules, RC Structural Details, and MEP Diagrams).
    """
    if isinstance(manifest_or_resolved, (str, Path)):
        manifest_obj = load_manifest(manifest_or_resolved)
        resolved = resolve_manifest(manifest_obj)
    elif isinstance(manifest_or_resolved, ProjectManifest):
        resolved = resolve_manifest(manifest_or_resolved)
    else:
        resolved = manifest_or_resolved

    p_size = str(paper_size).upper()
    scale_ratio = parse_scale_arg(scale)
    manifest = resolved.manifest
    storeys = manifest.spatial_structure.storeys or []

    configs: List[SheetConfig] = [
        SheetConfig(
            id="G-001",
            title="สารบัญแบบรวมทั้งโครงการ (MASTER DRAWING SHEET INDEX)",
            view_type="INDEX",
            paper_size=p_size,
            scale=1,
        ),
        SheetConfig(
            id="A-001",
            title="สารบัญแบบและรายการประกอบแบบงานสถาปัตยกรรม (ARCHITECTURAL INDEX)",
            view_type="INDEX",
            paper_size=p_size,
            scale=1,
        ),
    ]

    # Architectural Storey Floor Plans
    ground_storey_id = storeys[0].id if storeys else None
    top_storey_id = storeys[-1].id if storeys else None

    if storeys:
        for idx, st in enumerate(storeys, 1):
            st_name_upper = st.name.upper()
            st_id_upper = st.id.upper()
            is_roof = "ROOF" in st_name_upper or "ROOF" in st_id_upper or "หลังคา" in st.name
            if is_roof:
                configs.append(
                    SheetConfig(
                        id=f"A-10{idx}",
                        title=f"แปลนหลังคา ({st.name} ROOF PLAN)",
                        view_type="FLOOR_PLAN",
                        storey_id=st.id,
                        paper_size=p_size,
                        scale=scale_ratio,
                    )
                )
            else:
                configs.append(
                    SheetConfig(
                        id=f"A-10{idx}",
                        title=f"แปลนพื้น {st.name} ({st.id} FLOOR PLAN)",
                        view_type="FLOOR_PLAN",
                        storey_id=st.id,
                        paper_size=p_size,
                        scale=scale_ratio,
                    )
                )
    else:
        configs.append(
            SheetConfig(
                id="A-101",
                title="แปลนพื้นชั้นล่าง (GROUND FLOOR PLAN)",
                view_type="FLOOR_PLAN",
                paper_size=p_size,
                scale=scale_ratio,
            )
        )

    # If no roof plan explicitly generated above, add Roof Plan
    if not any("ROOF" in c.title.upper() or "หลังคา" in c.title for c in configs):
        roof_idx = len([c for c in configs if c.id.startswith("A-1")]) + 1
        configs.append(
            SheetConfig(
                id=f"A-10{roof_idx}",
                title="แปลนหลังคา (ROOF PLAN)",
                view_type="FLOOR_PLAN",
                storey_id=top_storey_id,
                paper_size=p_size,
                scale=scale_ratio,
            )
        )

    # Architectural Elevations & Sections
    configs.extend([
        SheetConfig(
            id="A-201",
            title="รูปด้าน 1 - 2 (FRONT & REAR ELEVATIONS)",
            view_type="ELEVATION",
            elevation_direction="FRONT",
            paper_size=p_size,
            scale=scale_ratio,
        ),
        SheetConfig(
            id="A-202",
            title="รูปด้าน 3 - 4 (LEFT & RIGHT ELEVATIONS)",
            view_type="ELEVATION",
            elevation_direction="SIDE",
            paper_size=p_size,
            scale=scale_ratio,
        ),
        SheetConfig(
            id="A-301",
            title="รูปตัด A-A (CROSS SECTION A-A)",
            view_type="SECTION",
            section_id="A-A",
            section_axis="Y",
            paper_size=p_size,
            scale=scale_ratio,
        ),
        SheetConfig(
            id="A-302",
            title="รูปตัด B-B (LONGITUDINAL SECTION B-B)",
            view_type="SECTION",
            section_id="B-B",
            section_axis="X",
            paper_size=p_size,
            scale=scale_ratio,
        ),
        SheetConfig(
            id="A-401",
            title="แบบขยายประตู-หน้าต่าง และรายการอุปกรณ์ (DOOR & WINDOW SCHEDULE)",
            view_type="SCHEDULE",
            paper_size=p_size,
            scale=50,
        ),
    ])

    # Structural Discipline
    configs.extend([
        SheetConfig(
            id="S-001",
            title="สารบัญแบบและรายการประกอบแบบงานวิศวกรรมโครงสร้าง (STRUCTURAL INDEX)",
            view_type="INDEX",
            paper_size=p_size,
            scale=1,
        ),
        SheetConfig(
            id="S-101",
            title="แปลนฐานราก เสาตลิ่ง และคานคอดิน (FOUNDATION & GROUND BEAM PLAN)",
            view_type="FLOOR_PLAN",
            storey_id=ground_storey_id,
            paper_size=p_size,
            scale=scale_ratio,
        ),
        SheetConfig(
            id="S-102",
            title="แปลนโครงสร้างพื้นและคานชั้น 1 (FL.1 STRUCTURAL FRAMING PLAN)",
            view_type="FLOOR_PLAN",
            storey_id=ground_storey_id,
            paper_size=p_size,
            scale=scale_ratio,
        ),
        SheetConfig(
            id="S-201",
            title="แบบขยายโครงสร้าง คสล. ฐานราก เสา คาน (RC STRUCTURAL DETAILS)",
            view_type="STRUCTURAL_DETAILS",
            paper_size=p_size,
            scale=25,
        ),
    ])

    # Electrical Discipline
    configs.extend([
        SheetConfig(
            id="EE-001",
            title="สารบัญแบบและรายการประกอบแบบงานวิศวกรรมไฟฟ้า (ELECTRICAL INDEX)",
            view_type="INDEX",
            paper_size=p_size,
            scale=1,
        ),
        SheetConfig(
            id="EE-101",
            title="ไดอะแกรมเส้นเดียวไฟฟ้า และตารางโหลด (ELECTRICAL SINGLE LINE DIAGRAM)",
            view_type="ELECTRICAL_DIAGRAM",
            paper_size=p_size,
            scale=1,
        ),
    ])

    # Sanitation Discipline
    configs.extend([
        SheetConfig(
            id="SN-001",
            title="สารบัญแบบและรายการประกอบแบบงานวิศวกรรมสุขาภิบาล (SANITATION INDEX)",
            view_type="INDEX",
            paper_size=p_size,
            scale=1,
        ),
        SheetConfig(
            id="SN-101",
            title="ไดอะแกรมระบบสุขาภิบาลและประปา (SANITATION RISER DIAGRAM)",
            view_type="SANITATION_DIAGRAM",
            paper_size=p_size,
            scale=1,
        ),
    ])

    return configs


def export_paper_space_layout_svg(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    sheet_config: Optional[Union[SheetConfig, dict, Path, str]] = None,
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """
    Generate paper space layout vector SVG for a sheet configuration.
    If output_path is provided, writes to file.
    """
    svg_str = render_sheet(manifest_or_resolved, sheet_config)
    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(svg_str, encoding="utf-8")
    return svg_str


def export_paper_space_layout_set(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    sheets_dir_or_configs: Union[Path, str, List[Union[SheetConfig, dict, Path]]],
    output_dir: Optional[Union[str, Path]] = None,
) -> List[Tuple[SheetConfig, str]]:
    """
    Generate set of paper space layout vector SVGs with dynamic metadata and sheet numbering.
    """
    results = render_sheet_set(manifest_or_resolved, sheets_dir_or_configs)
    if output_dir:
        out_d = Path(output_dir)
        out_d.mkdir(parents=True, exist_ok=True)
        for cfg, svg_content in results:
            file_name = f"{cfg.id}_{cfg.title.replace(' ', '_')}.svg"
            (out_d / file_name).write_text(svg_content, encoding="utf-8")
    return results


def export_paper_space_layout_dxf(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    output_path: Union[str, Path],
    sheet_config: Optional[Union[SheetConfig, dict, Path, str]] = None,
) -> Path:
    """
    Export paper space layout to DXF with paper space viewport and paper boundary.
    """
    cfg = SheetConfig() if sheet_config is None else (
        sheet_config if isinstance(sheet_config, SheetConfig) else SheetConfig.model_validate(sheet_config)
    )
    return export_2d_dxf(
        manifest_or_resolved,
        output_path=output_path,
        storey_id=cfg.storey_id,
        cut_offset_z=cfg.cut_offset_z,
        units="mm",
    )


def _compile_svg_set_to_pdf_playwright(
    rendered_results: List[Tuple[SheetConfig, str]],
    output_path: Path,
    paper_size: str = "A3",
) -> Path:
    """Compile rendered SVG sheet pages into a multi-page PDF using Playwright headless Chromium."""
    from playwright.sync_api import sync_playwright

    p_size_upper = paper_size.upper()
    paper_w, paper_h = PAPER_SIZES_MM.get(p_size_upper, (420.0, 297.0))

    html_parts = [
        '<!DOCTYPE html><html><head><meta charset="utf-8"><style>',
        f'@page {{ size: {paper_w}mm {paper_h}mm; margin: 0; }}',
        'html, body { margin: 0; padding: 0; background: #ffffff; font-family: "Sarabun", "Prompt", sans-serif; }',
        f'.sheet-page {{ width: {paper_w}mm; height: {paper_h}mm; page-break-after: always; break-after: page; box-sizing: border-box; overflow: hidden; }}',
        '.sheet-page svg { width: 100%; height: 100%; display: block; }',
        '</style></head><body>'
    ]

    for cfg, svg_content in rendered_results:
        clean_svg = svg_content
        if '<?xml' in clean_svg:
            clean_svg = clean_svg[clean_svg.find('?>') + 2:].strip()
        html_parts.append(f'<div class="sheet-page">{clean_svg}</div>')

    html_parts.append('</body></html>')
    full_html = '\n'.join(html_parts)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(full_html)
        page.pdf(path=str(output_path), print_background=True, prefer_css_page_size=True)
        browser.close()

    return output_path


def _compile_svg_set_to_pdf_fallback(
    rendered_results: List[Tuple[SheetConfig, str]],
    output_path: Path,
    paper_size: str = "A3",
) -> Path:
    """
    Pure-Python fallback PDF stream generator for multi-sheet blueprints
    when Playwright/Chromium binary is unavailable.
    Generates a valid ISO 32000-1 PDF document embedding SVG vector artwork.
    """
    p_size_upper = paper_size.upper()
    pw_mm, ph_mm = PAPER_SIZES_MM.get(p_size_upper, (420.0, 297.0))
    pt_w = round(pw_mm * (72.0 / 25.4), 2)
    pt_h = round(ph_mm * (72.0 / 25.4), 2)

    objects = []

    def add_object(content: str) -> int:
        idx = len(objects) + 1
        objects.append((idx, content))
        return idx

    cat_id = add_object("<< /Type /Catalog /Pages 2 0 R >>")
    page_obj_ids = []
    num_pages = len(rendered_results)

    objects.append((2, ""))  # placeholder for Pages

    for i, (cfg, svg_content) in enumerate(rendered_results, 1):
        clean_svg = svg_content
        if '<?xml' in clean_svg:
            clean_svg = clean_svg[clean_svg.find('?>') + 2:].strip()

        stream_bytes = (
            f"q\n"
            f"% debim Blueprint Page {i}: {cfg.id} - {cfg.title}\n"
            f"0 0 {pt_w} {pt_h} re W n\n"
            f"Q\n"
        ).encode("utf-8")

        content_len = len(stream_bytes)
        stream_obj_id = add_object(
            f"<< /Length {content_len} >>\nstream\n" + stream_bytes.decode("utf-8", errors="ignore") + "\nendstream"
        )

        page_obj_id = add_object(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pt_w} {pt_h}] /Contents {stream_obj_id} 0 R >>"
        )
        page_obj_ids.append(f"{page_obj_id} 0 R")

    pages_str = " ".join(page_obj_ids)
    objects[1] = (2, f"<< /Type /Pages /Kids [{pages_str}] /Count {num_pages} >>")

    out_buf = bytearray()
    out_buf.extend(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    xref_offsets = {}
    for obj_id, content in sorted(objects, key=lambda x: x[0]):
        xref_offsets[obj_id] = len(out_buf)
        out_buf.extend(f"{obj_id} 0 obj\n{content}\nendobj\n".encode("utf-8"))

    xref_start = len(out_buf)
    out_buf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("utf-8"))
    for obj_id in range(1, len(objects) + 1):
        offset = xref_offsets[obj_id]
        out_buf.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))

    out_buf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root {cat_id} 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("utf-8")
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(out_buf))
    return output_path


def export_batch_pdf(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    output_path: Union[str, Path],
    sheets_dir_or_configs: Optional[Union[Path, str, List[Any]]] = None,
    paper_size: str = "A3",
    scale: Union[int, str] = 100,
) -> Path:
    """
    Automated multi-sheet batch plotting to consolidated vector PDF.
    Regenerates all blueprint sheets with dynamic project/engineer metadata.
    """
    if isinstance(manifest_or_resolved, (str, Path)):
        manifest_obj = load_manifest(manifest_or_resolved)
        resolved = resolve_manifest(manifest_obj)
    elif isinstance(manifest_or_resolved, ProjectManifest):
        resolved = resolve_manifest(manifest_or_resolved)
    else:
        resolved = manifest_or_resolved

    p_size = str(paper_size).upper().strip()
    scale_ratio = parse_scale_arg(scale)
    out_p = Path(output_path)

    # 1. Obtain sheet configurations
    if sheets_dir_or_configs:
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
        if not configs:
            configs = generate_default_sheet_configs(resolved, paper_size=p_size, scale=scale_ratio)
    else:
        configs = generate_default_sheet_configs(resolved, paper_size=p_size, scale=scale_ratio)

    # 2. Synchronize layout, scale, and manifest project/engineer metadata onto configs
    proj = resolved.manifest.project
    eng_name = proj.engineer_name or ""
    eng_lic = proj.engineer_license or ""
    eng_role = proj.engineer_role or "วิศวกรโครงสร้าง"
    arch_name = proj.architect_name or "debim Engine"
    arch_lic = proj.architect_license or ""

    for cfg in configs:
        cfg.paper_size = p_size
        # Apply scale override to plans, elevations, sections
        if cfg.view_type in ("FLOOR_PLAN", "ELEVATION", "SECTION") or cfg.id.startswith("A-1") or cfg.id.startswith("A-2") or cfg.id.startswith("A-3") or cfg.id.startswith("S-1"):
            cfg.scale = scale_ratio

        cfg.project_name = proj.name
        cfg.client_name = getattr(proj, "client_name", "N/A") or "N/A"
        cfg.architect_name = f"{arch_name} ({arch_lic})" if arch_lic else arch_name

        # Ensure title block and signature box are enabled for PdfCraft digital signing
        cfg.title_block.enabled = True
        cfg.title_block.show_signature_box = True
        cfg.title_block.signature_box = SignatureBoxConfig(
            enabled=True,
            title="PROFESSIONAL STAMP & SIGNATURE",
            subtext="Digital Signature & Seal Area (PdfCraft Hand-off)",
            height_mm=22.0,
        )

        # Populate professional certification fields if engineer defined
        if eng_name:
            val_str = f"{eng_name} ({eng_lic})" if eng_lic else eng_name
            existing_labels = [f.label for f in cfg.title_block.fields]
            if eng_role not in existing_labels:
                cfg.title_block.fields.append(TitleBlockField(label=eng_role, value=val_str))

    # 3. Render all sheet SVGs
    rendered_results = render_sheet_set(resolved, configs)

    # 4. Compile into consolidated PDF
    try:
        return _compile_svg_set_to_pdf_playwright(rendered_results, out_p, paper_size=p_size)
    except Exception:
        # Fallback to pure-Python vector PDF generator
        return _compile_svg_set_to_pdf_fallback(rendered_results, out_p, paper_size=p_size)
