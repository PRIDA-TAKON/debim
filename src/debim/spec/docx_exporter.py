"""
Markdown to Microsoft Word (.docx) Exporter for debim Specification Books.
Supports Thai fonts, MasterFormat division headings, formatted clauses, tables, and lists.
"""

from pathlib import Path
import re
from typing import Any, List, Optional, Tuple, Union

try:
    import docx
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import nsdecls, qn
    from docx.shared import Inches, Pt, RGBColor
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


def _set_cell_background(cell, fill_hex: str):
    """Set background color of a docx table cell."""
    tcPr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)


def _set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set inner padding of a docx table cell in dxa (1/20 of a pt)."""
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)


def _set_run_thai_font(run, font_name: str = "TH Sarabun PSK", size_pt: float = 14):
    """Apply Thai-compatible font family and size to a run."""
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    rPr = run._r.get_or_add_rPr()
    rFonts = parse_xml(
        f'<w:rFonts {nsdecls("w")} w:ascii="{font_name}" w:hAnsi="{font_name}" w:cs="{font_name}"/>'
    )
    rPr.append(rFonts)


def _add_styled_inlines(paragraph, text: str, default_font: str = "TH Sarabun PSK", base_size: float = 14):
    """Parse inline markdown (bold, italic, inline code) and add styled runs to paragraph."""
    # Pattern for **bold**, *italic*, `code`
    token_pattern = re.compile(r"(\*\*.*?\*\*|\*.*?\*|`.*?`)")
    tokens = token_pattern.split(text)

    for token in tokens:
        if not token:
            continue
        if token.startswith("**") and token.endswith("**") and len(token) >= 4:
            clean = token[2:-2]
            run = paragraph.add_run(clean)
            run.bold = True
            _set_run_thai_font(run, default_font, base_size)
        elif token.startswith("*") and token.endswith("*") and len(token) >= 2:
            clean = token[1:-1]
            run = paragraph.add_run(clean)
            run.italic = True
            _set_run_thai_font(run, default_font, base_size)
        elif token.startswith("`") and token.endswith("`") and len(token) >= 2:
            clean = token[1:-1]
            run = paragraph.add_run(clean)
            run.font.color.rgb = RGBColor(180, 40, 40)
            _set_run_thai_font(run, "Consolas", base_size - 1)
        else:
            # Plain text, strip markdown link syntax if present [text](url) -> text
            clean = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", token)
            # Remove raw anchor tags <a id="..."></a>
            clean = re.sub(r"<a[^>]*>(.*?)</a>", r"\1", clean)
            clean = re.sub(r"<[^>]+>", "", clean)
            run = paragraph.add_run(clean)
            _set_run_thai_font(run, default_font, base_size)


def markdown_to_docx(
    md_content: str,
    output_path: Union[str, Path],
    title: Optional[str] = None,
    font_name: str = "TH Sarabun PSK",
) -> Path:
    """
    Convert Markdown content into a professionally styled Microsoft Word document (.docx).

    Supports:
    - Headers (H1-H4) with corporate architectural color palette
    - Tables with header shading and border formatting
    - Bullet points and numbered lists
    - Thai font rendering support (TH Sarabun PSK / Cordia New / Aptos)
    - Metadata and callout dividers
    """
    if not HAS_DOCX:
        raise ImportError(
            "The 'python-docx' package is required to export to MS Word (.docx). "
            "Please install it with: pip install python-docx"
        )

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    doc = Document()

    # Configure 1-inch margins
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Palette
    color_h1 = RGBColor(27, 54, 93)     # Navy #1B365D
    color_h2 = RGBColor(44, 82, 130)    # Slate Blue #2C5282
    color_h3 = RGBColor(49, 130, 206)   # Cobalt #3182CE
    color_h4 = RGBColor(74, 85, 104)    # Cool Gray #4A5568

    lines = md_content.splitlines()
    i = 0
    in_table = False
    table_lines: List[str] = []

    def flush_table():
        nonlocal table_lines
        if not table_lines:
            return
        # Parse table lines
        parsed_rows = []
        for tl in table_lines:
            # Skip separator row like |---|---|
            if re.match(r"^\|?[\s\-:|]+\|?$", tl):
                continue
            cols = [c.strip() for c in tl.strip().strip("|").split("|")]
            if cols:
                parsed_rows.append(cols)

        if parsed_rows:
            col_count = max(len(r) for r in parsed_rows)
            table = doc.add_table(rows=len(parsed_rows), cols=col_count)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER

            for row_idx, row_data in enumerate(parsed_rows):
                is_header = (row_idx == 0)
                table_row = table.rows[row_idx]
                for col_idx in range(col_count):
                    val = row_data[col_idx] if col_idx < len(row_data) else ""
                    cell = table_row.cells[col_idx]
                    p = cell.paragraphs[0]
                    p.paragraph_format.space_before = Pt(2)
                    p.paragraph_format.space_after = Pt(2)

                    _set_cell_margins(cell, top=120, bottom=120, left=150, right=150)

                    if is_header:
                        _set_cell_background(cell, "1B365D")
                        run = p.add_run(val)
                        run.bold = True
                        run.font.color.rgb = RGBColor(255, 255, 255)
                        _set_run_thai_font(run, font_name, 13)
                    else:
                        bg_hex = "F7FAFC" if row_idx % 2 == 1 else "FFFFFF"
                        _set_cell_background(cell, bg_hex)
                        _add_styled_inlines(p, val, default_font=font_name, base_size=13)

            p_after = doc.add_paragraph()
            p_after.paragraph_format.space_after = Pt(6)

        table_lines = []

    while i < len(lines):
        line = lines[i].strip()

        # Table detection
        if "|" in line and (line.startswith("|") or line.endswith("|")):
            table_lines.append(line)
            i += 1
            continue
        elif table_lines:
            flush_table()

        if not line:
            i += 1
            continue

        # Horizontal rule
        if line in ("---", "___", "***"):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(8)
            pBdr = parse_xml(
                f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="6" w:space="1" w:color="CBD5E0"/></w:pBdr>'
            )
            p._p.get_or_add_pPr().append(pBdr)
            i += 1
            continue

        # Headers
        if line.startswith("# "):
            header_text = line[2:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(18)
            p.paragraph_format.space_after = Pt(8)
            run = p.add_run(header_text)
            run.bold = True
            run.font.color.rgb = color_h1
            _set_run_thai_font(run, font_name, 22)
        elif line.startswith("## "):
            header_text = line[3:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(14)
            p.paragraph_format.space_after = Pt(6)
            run = p.add_run(header_text)
            run.bold = True
            run.font.color.rgb = color_h2
            _set_run_thai_font(run, font_name, 18)
        elif line.startswith("### "):
            header_text = line[4:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(12)
            p.paragraph_format.space_after = Pt(4)
            run = p.add_run(header_text)
            run.bold = True
            run.font.color.rgb = color_h3
            _set_run_thai_font(run, font_name, 16)
        elif line.startswith("#### "):
            header_text = line[5:].strip()
            # Clean anchor tag <a id='...'></a>
            header_text = re.sub(r"<a[^>]*>(.*?)</a>", r"\1", header_text)
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(10)
            p.paragraph_format.space_after = Pt(4)
            run = p.add_run(header_text)
            run.bold = True
            run.font.color.rgb = color_h4
            _set_run_thai_font(run, font_name, 15)
        # Bullet list
        elif line.startswith("- ") or line.startswith("* "):
            bullet_text = line[2:].strip()
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.left_indent = Inches(0.25)
            _add_styled_inlines(p, bullet_text, default_font=font_name, base_size=14)
        # Sub-bullet list
        elif line.startswith("   - ") or line.startswith("    - "):
            bullet_text = line.lstrip(" -").strip()
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(2)
            p.paragraph_format.left_indent = Inches(0.5)
            _add_styled_inlines(p, bullet_text, default_font=font_name, base_size=14)
        # Numbered list
        elif re.match(r"^\d+\.\s+", line):
            num_match = re.match(r"^(\d+\.)\s+(.*)$", line)
            if num_match:
                prefix = num_match.group(1)
                text_part = num_match.group(2)
                p = doc.add_paragraph()
                p.paragraph_format.space_before = Pt(1)
                p.paragraph_format.space_after = Pt(2)
                p.paragraph_format.left_indent = Inches(0.25)
                run_p = p.add_run(f"{prefix} ")
                run_p.bold = True
                _set_run_thai_font(run_p, font_name, 14)
                _add_styled_inlines(p, text_part, default_font=font_name, base_size=14)
        # Blockquote
        elif line.startswith("> "):
            quote_text = line[2:].strip()
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.left_indent = Inches(0.3)
            pBdr = parse_xml(
                f'<w:pBdr {nsdecls("w")}><w:left w:val="single" w:sz="18" w:space="10" w:color="3182CE"/></w:pBdr>'
            )
            p._p.get_or_add_pPr().append(pBdr)
            _add_styled_inlines(p, quote_text, default_font=font_name, base_size=13.5)
        # Normal paragraph
        else:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(4)
            _add_styled_inlines(p, line, default_font=font_name, base_size=14)

        i += 1

    if table_lines:
        flush_table()

    doc.save(str(out_file))
    return out_file


def export_spec_book_to_docx(book_or_md: Any, output_path: Union[str, Path]) -> Path:
    """Export a SpecificationBook object or Markdown string to .docx."""
    if hasattr(book_or_md, "markdown_content"):
        md_text = book_or_md.markdown_content
        title = getattr(book_or_md, "project_name", "Specification Book")
    else:
        md_text = str(book_or_md)
        title = "Specification Book"

    return markdown_to_docx(md_text, output_path, title=title)
