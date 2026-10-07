"""
Specification Book Compiler for debim.
Compiles architectural material specifications into formatted Markdown and PDF-ready HTML.
"""

from datetime import datetime
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field

from debim.schema import ProjectManifest, load_manifest
from debim.spec.audit import extract_project_materials
from debim.spec.schema import MaterialSpec, SpecificationManifest, load_spec_manifest


MASTERFORMAT_DIVISIONS: Dict[str, str] = {
    "00": "Procurement and Contracting Requirements",
    "01": "General Requirements",
    "02": "Existing Conditions",
    "03": "Concrete",
    "04": "Masonry",
    "05": "Metals",
    "06": "Wood, Plastics, and Composites",
    "07": "Thermal and Moisture Protection",
    "08": "Openings",
    "09": "Finishes",
    "10": "Specialties",
    "11": "Equipment",
    "12": "Furnishings",
    "13": "Special Construction",
    "14": "Conveying Equipment",
    "21": "Fire Suppression",
    "22": "Plumbing",
    "23": "Heating, Ventilating, and Air Conditioning (HVAC)",
    "25": "Integrated Automation",
    "26": "Electrical",
    "27": "Communications",
    "28": "Electronic Safety and Security",
    "31": "Earthwork",
    "32": "Exterior Improvements",
    "33": "Utilities",
    "34": "Transportation",
    "35": "Waterway and Marine Construction",
    "40": "Process Interconnections",
    "41": "Material Processing and Handling Equipment",
    "42": "Process Heating, Cooling, and Drying Equipment",
    "43": "Process Gas and Liquid Handling, Purification and Storage Equipment",
    "44": "Pollution and Waste Control Equipment",
    "45": "Industry-Specific Manufacturing Equipment",
    "48": "Electrical Power Generation",
}


def get_masterformat_division(masterformat: Optional[str]) -> Tuple[str, str]:
    """
    Parse MasterFormat string to extract division code and division title.
    Returns tuple of (division_code, division_title).
    """
    if not masterformat or not str(masterformat).strip():
        return ("99", "General / Unassigned Specifications")

    s = str(masterformat).strip()

    # Match 2 digits at start or after 'Division'
    match = re.search(r"(?:Division\s*)?(\d{2})", s, re.IGNORECASE)
    if match:
        div_code = match.group(1)
        div_title = MASTERFORMAT_DIVISIONS.get(div_code, f"Division {div_code}")
        return (div_code, f"Division {div_code} - {div_title}")

    return ("99", "General / Unassigned Specifications")


def _discover_all_specs(
    spec_manifest: Optional[Union[SpecificationManifest, str, Path, List[Any], dict]] = None,
    project_path: Optional[Path] = None,
) -> SpecificationManifest:
    """Discover and aggregate all available material specifications from paths, dirs, or manifests."""
    specs_list: List[MaterialSpec] = []

    if spec_manifest is not None:
        if isinstance(spec_manifest, (str, Path)):
            p = Path(spec_manifest)
            if p.exists() and p.is_dir():
                for ext in ("*.yaml", "*.yml", "*.json"):
                    for filepath in p.rglob(ext):
                        try:
                            sub_manifest = load_spec_manifest(filepath)
                            specs_list.extend(sub_manifest.specifications)
                        except Exception:
                            pass
            elif p.exists():
                sub_manifest = load_spec_manifest(p)
                specs_list.extend(sub_manifest.specifications)
        else:
            sub_manifest = load_spec_manifest(spec_manifest)
            specs_list.extend(sub_manifest.specifications)

    if project_path is not None and project_path.exists():
        parent_dir = project_path.parent if project_path.is_file() else project_path
        candidate_dirs = [
            parent_dir / "specs",
            parent_dir / "specifications",
        ]
        for cdir in candidate_dirs:
            if cdir.exists() and cdir.is_dir():
                for ext in ("*.yaml", "*.yml", "*.json"):
                    for filepath in cdir.rglob(ext):
                        try:
                            sub_manifest = load_spec_manifest(filepath)
                            specs_list.extend(sub_manifest.specifications)
                        except Exception:
                            pass

        candidate_files = [
            parent_dir / "specs.yaml",
            parent_dir / "specs.yml",
            parent_dir / "specifications.yaml",
            parent_dir / "specifications.yml",
        ]
        for cfile in candidate_files:
            if cfile.exists() and cfile.is_file():
                try:
                    sub_manifest = load_spec_manifest(cfile)
                    specs_list.extend(sub_manifest.specifications)
                except Exception:
                    pass

    # Deduplicate by spec.id
    seen_ids: Set[str] = set()
    unique_specs: List[MaterialSpec] = []
    for spec in specs_list:
        if spec.id not in seen_ids:
            seen_ids.add(spec.id)
            unique_specs.append(spec)

    return SpecificationManifest(specifications=unique_specs)


def _format_clause_content(val: Any) -> str:
    """Helper to convert structured clause value into Markdown string."""
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, (list, tuple)):
        lines = []
        for item in val:
            if isinstance(item, str):
                lines.append(f"- {item.strip()}")
            elif isinstance(item, dict):
                for k, v in item.items():
                    lines.append(f"- **{k}**: {v}")
            else:
                lines.append(f"- {item}")
        return "\n".join(lines)
    if isinstance(val, dict):
        lines = []
        for k, v in val.items():
            lines.append(f"- **{k.replace('_', ' ').title()}**: {v}")
        return "\n".join(lines)
    return str(val)


class SpecificationBook(BaseModel):
    """Compiled Specification Book output container."""
    title: str = "ARCHITECTURAL MATERIAL SPECIFICATIONS BOOK"
    project_id: str
    project_name: str
    generated_at: str
    referenced_materials: List[str]
    included_specs: List[MaterialSpec]
    divisions: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    element_material_map: Dict[str, List[str]] = Field(default_factory=dict)
    markdown_content: str = ""
    html_content: str = ""

    def save(self, output_path: Union[str, Path], format: Optional[str] = None) -> Path:
        """Save compiled specification book to disk in Markdown or HTML format."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        fmt = format.lower() if format else out_p.suffix.lstrip(".").lower()
        if fmt in ("html", "htm"):
            out_p.write_text(self.html_content, encoding="utf-8")
        else:
            out_p.write_text(self.markdown_content, encoding="utf-8")

        return out_p


def build_specification_book(
    project_manifest: Union[ProjectManifest, str, Path, dict],
    spec_manifest: Optional[Union[SpecificationManifest, str, Path, List[Any], dict]] = None,
    title: str = "ARCHITECTURAL MATERIAL SPECIFICATIONS BOOK",
) -> SpecificationBook:
    """
    Compile an architectural specification book for materials actively used in project.yaml.

    1. Scans project manifest for all referenced materials across elements.
    2. Filters specs to include ONLY active materials (zero spec bloat).
    3. Groups and sorts specs by MasterFormat division.
    4. Generates Cover Page, Project Information, TOC with section numbering, and Spec Sections.
    """
    manifest_obj: ProjectManifest
    manifest_path: Optional[Path] = None

    if isinstance(project_manifest, ProjectManifest):
        manifest_obj = project_manifest
    elif isinstance(project_manifest, (str, Path)):
        manifest_path = Path(project_manifest)
        manifest_obj = load_manifest(manifest_path)
    elif isinstance(project_manifest, dict):
        manifest_obj = ProjectManifest.model_validate(project_manifest)
    else:
        raise ValueError(f"Invalid project manifest type: {type(project_manifest)}")

    # Extract referenced materials and element mapping from project
    referenced_mats, mat_elem_map = extract_project_materials(manifest_obj)

    # Discover all candidate specs
    candidate_specs_manifest = _discover_all_specs(spec_manifest, manifest_path)

    # Filter specs: ONLY include specs whose ID is in referenced_mats
    included_specs: List[MaterialSpec] = []
    spec_by_id: Dict[str, MaterialSpec] = {}
    for spec in candidate_specs_manifest.specifications:
        if spec.id in referenced_mats and spec.id not in spec_by_id:
            included_specs.append(spec)
            spec_by_id[spec.id] = spec

    # If any referenced material does not have an explicit MaterialSpec package found,
    # create a stub MaterialSpec so no active building material is omitted.
    for mat_id in sorted(referenced_mats):
        if mat_id not in spec_by_id:
            # Check if material is declared in manifest.materials with name
            mat_name = mat_id
            if hasattr(manifest_obj, "materials") and manifest_obj.materials:
                for m in manifest_obj.materials:
                    if m.id == mat_id and m.name:
                        mat_name = m.name
                        break
            stub_spec = MaterialSpec(
                id=mat_id,
                name=mat_name,
                masterformat="99 00 00",
            )
            included_specs.append(stub_spec)
            spec_by_id[mat_id] = stub_spec

    # Group included specs by MasterFormat division
    # Structure: division_code -> {"title": div_title, "specs": [MaterialSpec, ...]}
    division_groups: Dict[str, Dict[str, Any]] = {}

    for spec in included_specs:
        div_code, div_title = get_masterformat_division(spec.masterformat)
        if div_code not in division_groups:
            division_groups[div_code] = {
                "code": div_code,
                "title": div_title,
                "specs": [],
            }
        division_groups[div_code]["specs"].append(spec)

    # Sort divisions numerically by division code
    def _div_sort_key(code: str) -> Tuple[int, str]:
        if code.isdigit():
            return (0, f"{int(code):02d}")
        return (1, code)

    sorted_div_codes = sorted(division_groups.keys(), key=_div_sort_key)

    # Sort specs within each division by masterformat code then spec.id
    for div_code in sorted_div_codes:
        specs_in_div = division_groups[div_code]["specs"]
        specs_in_div.sort(key=lambda s: (s.masterformat or "", s.id))

    proj_info = manifest_obj.project
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Generate Markdown Output
    md_lines: List[str] = []

    # 1. Cover Page
    md_lines.append(f"# {title}")
    md_lines.append("")
    md_lines.append(f"**Project Name:** {proj_info.name}")
    md_lines.append(f"**Project ID:** {proj_info.id}")
    md_lines.append(f"**Date Generated:** {gen_time}")
    md_lines.append(f"**Engine:** debim Specification Compiler v1.0")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

    # 2. Project Information Block
    md_lines.append("## Project Information")
    md_lines.append("")
    md_lines.append(f"- **Building Name:** {proj_info.name} (`{proj_info.id}`)")
    if hasattr(manifest_obj, "spatial_structure") and manifest_obj.spatial_structure.storeys:
        storey_names = [s.name for s in manifest_obj.spatial_structure.storeys]
        md_lines.append(f"- **Storeys/Levels:** {', '.join(storey_names)}")
    md_lines.append(f"- **Active Specification Packages:** {len(included_specs)}")
    md_lines.append(f"- **Referenced Materials Count:** {len(referenced_mats)}")
    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

    # 3. Table of Contents (TOC) with Section Numbering
    md_lines.append("## Table of Contents")
    md_lines.append("")

    div_idx = 1
    for div_code in sorted_div_codes:
        div_data = division_groups[div_code]
        md_lines.append(f"{div_idx}. **{div_data['title']}**")
        spec_idx = 1
        for spec in div_data["specs"]:
            md_lines.append(f"   - {div_idx}.{spec_idx} [{spec.id} - {spec.name}](#section-{div_idx}-{spec_idx})")
            spec_idx += 1
        div_idx += 1

    md_lines.append("")
    md_lines.append("---")
    md_lines.append("")

    # 4. Specification Sections
    md_lines.append("## Detailed Material Specifications")
    md_lines.append("")

    div_idx = 1
    for div_code in sorted_div_codes:
        div_data = division_groups[div_code]
        md_lines.append(f"### Division {div_code}: {div_data['title']}")
        md_lines.append("")

        spec_idx = 1
        for spec in div_data["specs"]:
            anchor_id = f"section-{div_idx}-{spec_idx}"
            md_lines.append(f"#### <a id='{anchor_id}'></a>{div_idx}.{spec_idx} {spec.id} - {spec.name}")
            md_lines.append("")
            md_lines.append(f"- **Specification ID:** `{spec.id}`")
            md_lines.append(f"- **Material Name:** {spec.name}")
            if spec.masterformat:
                md_lines.append(f"- **MasterFormat Code:** `{spec.masterformat}`")
            if spec.manufacturer:
                md_lines.append(f"- **Manufacturer:** {spec.manufacturer}")
            if spec.warranty_years is not None:
                md_lines.append(f"- **Warranty Period:** {spec.warranty_years} Years")

            elem_tags = mat_elem_map.get(spec.id, [])
            if elem_tags:
                tags_str = ", ".join([f"`{t}`" for t in elem_tags])
                md_lines.append(f"- **Installed Elements:** {tags_str}")

            # Standards
            stds = spec.standards
            has_stds = any([stds.jis, stds.astm, stds.din, stds.iso])
            if has_stds:
                md_lines.append("")
                md_lines.append("**Industry Standards & Compliance:**")
                if stds.jis:
                    md_lines.append(f"  - **JIS:** {stds.jis}")
                if stds.astm:
                    md_lines.append(f"  - **ASTM:** {stds.astm}")
                if stds.din:
                    md_lines.append(f"  - **DIN:** {stds.din}")
                if stds.iso:
                    md_lines.append(f"  - **ISO:** {stds.iso}")

            # Clauses
            clauses = spec.clauses
            gen_prop = _format_clause_content(clauses.general_properties)
            surf_prep = _format_clause_content(clauses.surface_preparation)
            app_sys = _format_clause_content(clauses.application_system)

            if gen_prop or surf_prep or app_sys:
                md_lines.append("")
                md_lines.append("**Execution & Specification Clauses:**")
                if gen_prop:
                    md_lines.append("##### General Properties")
                    md_lines.append(gen_prop)
                if surf_prep:
                    md_lines.append("##### Surface Preparation")
                    md_lines.append(surf_prep)
                if app_sys:
                    md_lines.append("##### Application System")
                    md_lines.append(app_sys)

            md_lines.append("")
            md_lines.append("---")
            md_lines.append("")

            spec_idx += 1
        div_idx += 1

    markdown_content = "\n".join(md_lines)

    # Generate HTML / PDF-ready Output
    html_content = _generate_specification_html(
        title=title,
        proj_info=proj_info,
        gen_time=gen_time,
        included_specs=included_specs,
        referenced_mats=referenced_mats,
        division_groups=division_groups,
        sorted_div_codes=sorted_div_codes,
        mat_elem_map=mat_elem_map,
    )

    return SpecificationBook(
        title=title,
        project_id=proj_info.id,
        project_name=proj_info.name,
        generated_at=gen_time,
        referenced_materials=sorted(list(referenced_mats)),
        included_specs=included_specs,
        divisions=division_groups,
        element_material_map=mat_elem_map,
        markdown_content=markdown_content,
        html_content=html_content,
    )


def _generate_specification_html(
    title: str,
    proj_info: Any,
    gen_time: str,
    included_specs: List[MaterialSpec],
    referenced_mats: Set[str],
    division_groups: Dict[str, Dict[str, Any]],
    sorted_div_codes: List[str],
    mat_elem_map: Dict[str, List[str]],
) -> str:
    """Generate PDF-ready standalone HTML document with CSS print styles."""
    html_lines = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='UTF-8'>",
        "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        f"  <title>{title} - {proj_info.name}</title>",
        "  <style>",
        "    @page { size: A4; margin: 20mm; }",
        "    body { font-family: 'Segoe UI', Arial, sans-serif; color: #1e293b; line-height: 1.6; margin: 0; padding: 20px; }",
        "    .cover-page { text-align: center; padding: 80px 20px; page-break-after: always; border: 2px solid #0284c7; border-radius: 8px; margin-bottom: 40px; }",
        "    .cover-title { font-size: 28px; font-weight: bold; color: #0f172a; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 1px; }",
        "    .cover-subtitle { font-size: 18px; color: #0284c7; margin-bottom: 40px; }",
        "    .info-table { width: 100%; border-collapse: collapse; margin-bottom: 30px; }",
        "    .info-table th, .info-table td { border: 1px solid #cbd5e1; padding: 10px 14px; text-align: left; }",
        "    .info-table th { background-color: #f1f5f9; color: #334155; font-weight: 600; width: 30%; }",
        "    .toc { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 24px; margin-bottom: 40px; }",
        "    .toc h2 { color: #0f172a; margin-top: 0; border-bottom: 2px solid #0284c7; padding-bottom: 8px; }",
        "    .toc-div { font-weight: bold; color: #0369a1; margin-top: 14px; }",
        "    .toc-item { margin-left: 20px; font-size: 14px; margin-top: 4px; }",
        "    .toc-item a { color: #334155; text-decoration: none; }",
        "    .toc-item a:hover { text-decoration: underline; color: #0284c7; }",
        "    .section-div { font-size: 20px; color: #0f172a; background: #e0f2fe; padding: 10px 16px; border-left: 5px solid #0284c7; margin-top: 30px; margin-bottom: 20px; }",
        "    .spec-card { border: 1px solid #cbd5e1; border-radius: 6px; padding: 20px; margin-bottom: 24px; page-break-inside: avoid; background: #ffffff; }",
        "    .spec-header { font-size: 18px; font-weight: bold; color: #0f172a; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 14px; }",
        "    .badge { display: inline-block; background: #e2e8f0; color: #1e293b; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-family: monospace; }",
        "    .badge-primary { background: #0284c7; color: #ffffff; }",
        "    .clause-block { background: #f8fafc; padding: 12px; border-radius: 4px; margin-top: 10px; border-left: 3px solid #94a3b8; }",
        "    .clause-title { font-weight: bold; color: #334155; margin-bottom: 4px; font-size: 14px; }",
        "    @media print { body { padding: 0; } .spec-card { page-break-inside: avoid; } }",
        "  </style>",
        "</head>",
        "<body>",
        "  <div class='cover-page'>",
        f"    <div class='cover-title'>{title}</div>",
        f"    <div class='cover-subtitle'>Project Specification Manual</div>",
        "    <table class='info-table' style='max-width: 600px; margin: 0 auto;'>",
        f"      <tr><th>Project Name</th><td>{proj_info.name}</td></tr>",
        f"      <tr><th>Project ID</th><td>{proj_info.id}</td></tr>",
        f"      <tr><th>Date Generated</th><td>{gen_time}</td></tr>",
        f"      <tr><th>Specifications Count</th><td>{len(included_specs)}</td></tr>",
        "    </table>",
        "  </div>",
        "  <div class='toc'>",
        "    <h2>Table of Contents</h2>",
    ]

    div_idx = 1
    for div_code in sorted_div_codes:
        div_data = division_groups[div_code]
        html_lines.append(f"    <div class='toc-div'>{div_idx}. {div_data['title']}</div>")
        spec_idx = 1
        for spec in div_data["specs"]:
            anchor = f"spec-{div_idx}-{spec_idx}"
            html_lines.append(f"    <div class='toc-item'><a href='#{anchor}'>{div_idx}.{spec_idx} {spec.id} - {spec.name}</a></div>")
            spec_idx += 1
        div_idx += 1

    html_lines.extend([
        "  </div>",
        "  <div class='specifications-body'>",
    ])

    div_idx = 1
    for div_code in sorted_div_codes:
        div_data = division_groups[div_code]
        html_lines.append(f"    <div class='section-div'>Division {div_code}: {div_data['title']}</div>")

        spec_idx = 1
        for spec in div_data["specs"]:
            anchor = f"spec-{div_idx}-{spec_idx}"
            html_lines.append(f"    <div class='spec-card' id='{anchor}'>")
            html_lines.append(f"      <div class='spec-header'>{div_idx}.{spec_idx} {spec.id} - {spec.name}</div>")

            html_lines.append("      <table class='info-table'>")
            html_lines.append(f"        <tr><th>Specification ID</th><td><span class='badge badge-primary'>{spec.id}</span></td></tr>")
            html_lines.append(f"        <tr><th>Material Name</th><td>{spec.name}</td></tr>")
            if spec.masterformat:
                html_lines.append(f"        <tr><th>MasterFormat Code</th><td><span class='badge'>{spec.masterformat}</span></td></tr>")
            if spec.manufacturer:
                html_lines.append(f"        <tr><th>Manufacturer</th><td>{spec.manufacturer}</td></tr>")
            if spec.warranty_years is not None:
                html_lines.append(f"        <tr><th>Warranty Period</th><td>{spec.warranty_years} Years</td></tr>")

            elem_tags = mat_elem_map.get(spec.id, [])
            if elem_tags:
                tags_html = " ".join([f"<span class='badge'>{t}</span>" for t in elem_tags])
                html_lines.append(f"        <tr><th>Installed Elements</th><td>{tags_html}</td></tr>")

            # Standards
            stds = spec.standards
            has_stds = any([stds.jis, stds.astm, stds.din, stds.iso])
            if has_stds:
                stds_str = []
                if stds.jis: stds_str.append(f"JIS: {stds.jis}")
                if stds.astm: stds_str.append(f"ASTM: {stds.astm}")
                if stds.din: stds_str.append(f"DIN: {stds.din}")
                if stds.iso: stds_str.append(f"ISO: {stds.iso}")
                html_lines.append(f"        <tr><th>Standards & Compliance</th><td>{', '.join(stds_str)}</td></tr>")

            html_lines.append("      </table>")

            # Clauses
            clauses = spec.clauses
            gen_prop = _format_clause_content(clauses.general_properties)
            surf_prep = _format_clause_content(clauses.surface_preparation)
            app_sys = _format_clause_content(clauses.application_system)

            if gen_prop:
                gen_prop_html = gen_prop.replace("\n", "<br>")
                html_lines.append("      <div class='clause-block'>")
                html_lines.append("        <div class='clause-title'>General Properties</div>")
                html_lines.append(f"        <div>{gen_prop_html}</div>")
                html_lines.append("      </div>")
            if surf_prep:
                surf_prep_html = surf_prep.replace("\n", "<br>")
                html_lines.append("      <div class='clause-block'>")
                html_lines.append("        <div class='clause-title'>Surface Preparation</div>")
                html_lines.append(f"        <div>{surf_prep_html}</div>")
                html_lines.append("      </div>")
            if app_sys:
                app_sys_html = app_sys.replace("\n", "<br>")
                html_lines.append("      <div class='clause-block'>")
                html_lines.append("        <div class='clause-title'>Application System</div>")
                html_lines.append(f"        <div>{app_sys_html}</div>")
                html_lines.append("      </div>")

            html_lines.append("    </div>")
            spec_idx += 1
        div_idx += 1

    html_lines.extend([
        "  </div>",
        "</body>",
        "</html>",
    ])

    return "\n".join(html_lines)
