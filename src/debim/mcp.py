"""
Model Context Protocol (MCP) server for debim.
Allows AI coding agents (Claude, Cursor, Antigravity, Devin, Windsurf) to natively invoke
debim's validation, QTO, cost estimation, and IFC compilation tools.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from mcp.server.fastmcp import FastMCP

from debim.compiler import compile_to_ifc
from debim.cost import (
    PriceCatalog,
    estimate_cost,
    generate_cost_template,
    load_price_catalog,
)
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import ProjectManifest
from debim.viewer import generate_viewer_html

mcp = FastMCP("debim")


def _parse_manifest_from_yaml_string(yaml_str: str) -> ProjectManifest:
    """Parse YAML string into ProjectManifest model."""
    data = yaml.safe_load(yaml_str)
    if not isinstance(data, dict):
        raise ValueError("Provided manifest YAML must be a dictionary.")
    return ProjectManifest.model_validate(data)


@mcp.tool()
def debim_validate(manifest_yaml: str) -> Dict[str, Any]:
    """
    Validate a declarative BIM manifest YAML string.
    Checks schema syntax, grid consistency, storey heights, and material references.
    """
    try:
        manifest = _parse_manifest_from_yaml_string(manifest_yaml)
        resolved = resolve_manifest(manifest)
        return {
            "valid": True,
            "project_id": manifest.project.id,
            "project_name": manifest.project.name,
            "storeys_count": len(manifest.spatial_structure.storeys),
            "elements_count": len(manifest.elements),
            "resolved_columns": len(resolved.columns),
            "resolved_beams": len(resolved.beams),
            "resolved_slabs": len(resolved.slabs),
            "resolved_walls": len(resolved.walls),
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


@mcp.tool()
def debim_qto(manifest_yaml: str) -> Dict[str, Any]:
    """
    Calculate Quantitative Take-Off (QTO) material quantities deterministically.
    Returns exact concrete volume (m3), formwork area (m2), rebar weight (kg),
    structural steel (kg), timber volume (m3), masonry area (m2), and excavation (m3).
    """
    try:
        manifest = _parse_manifest_from_yaml_string(manifest_yaml)
        qto = calculate_qto(manifest)

        return {
            "success": True,
            "project_id": manifest.project.id,
            "summary": {
                "concrete_volume_m3": round(qto.total_concrete_volume, 3),
                "formwork_area_m2": round(qto.total_formwork_area, 2),
                "rebar_weight_kg": round(qto.total_rebar_weight, 2),
                "structural_steel_kg": round(qto.total_structural_steel_weight, 2),
                "structural_timber_m3": round(qto.total_timber_volume, 3),
                "masonry_wall_area_m2": round(qto.total_wall_masonry_area, 2),
                "excavation_m3": round(qto.total_excavation_volume, 3),
                "lean_concrete_m3": round(qto.total_lean_concrete_volume, 3),
            },
            "rebar_breakdown_by_type": {
                k: round(v, 2) for k, v in qto.total_rebar_by_type.items()
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def debim_cost_template(manifest_yaml: str) -> Dict[str, Any]:
    """
    Generate a minimal project-scoped price catalog YAML template
    based only on the materials and items actively used by the building model.
    """
    try:
        manifest = _parse_manifest_from_yaml_string(manifest_yaml)
        # Create a temporary template and read back text
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tf:
            tmp_path = Path(tf.name)
        try:
            generate_cost_template(manifest, output_path=tmp_path, format="yaml")
            template_str = tmp_path.read_text(encoding="utf-8")
        finally:
            tmp_path.unlink(missing_ok=True)

        return {"success": True, "prices_template_yaml": template_str}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def debim_cost(
    manifest_yaml: str,
    prices_yaml: Optional[str] = None,
    export_csv_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate full Bill of Quantities (BOQ) and cost estimation.
    Matches QTO quantities against unit material and labor prices.
    If prices_yaml is omitted, auto-generates a benchmark template.
    Optionally exports the complete BOQ to a CSV file.
    """
    try:
        manifest = _parse_manifest_from_yaml_string(manifest_yaml)
        qto = calculate_qto(manifest)

        if prices_yaml and prices_yaml.strip():
            price_data = yaml.safe_load(prices_yaml)
            catalog = PriceCatalog.model_validate(price_data)
        else:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tf:
                tmp_path = Path(tf.name)
            try:
                generate_cost_template(manifest, output_path=tmp_path, format="yaml")
                price_data = yaml.safe_load(tmp_path.read_text(encoding="utf-8"))
                catalog = PriceCatalog.model_validate(price_data)
            finally:
                tmp_path.unlink(missing_ok=True)

        cost_est = estimate_cost(qto, catalog, manifest=manifest)

        items_breakdown = [
            {
                "code": item.code,
                "name": item.name,
                "unit": item.unit,
                "quantity": round(item.quantity, 3),
                "unit_material_cost": round(item.unit_material_cost, 2),
                "unit_labor_cost": round(item.unit_labor_cost, 2),
                "total_material_cost": round(item.total_material_cost, 2),
                "total_labor_cost": round(item.total_labor_cost, 2),
                "total_amount": round(item.total_amount, 2),
            }
            for item in cost_est.line_items
        ]

        csv_result_path = None
        if export_csv_path:
            csv_result_path = str(cost_est.export_csv(Path(export_csv_path)))

        return {
            "success": True,
            "currency": cost_est.currency,
            "total_material_cost": round(cost_est.total_material_cost, 2),
            "total_labor_cost": round(cost_est.total_labor_cost, 2),
            "grand_total": round(cost_est.grand_total, 2),
            "line_items_count": len(items_breakdown),
            "line_items": items_breakdown,
            "exported_csv_path": csv_result_path,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def debim_compile_ifc(manifest_yaml: str, output_ifc_path: str) -> Dict[str, Any]:
    """
    Compile a declarative BIM YAML manifest into a standard IFC4 building model.
    """
    try:
        manifest = _parse_manifest_from_yaml_string(manifest_yaml)
        out_path = Path(output_ifc_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        compile_to_ifc(manifest, out_path)
        file_size_kb = round(out_path.stat().st_size / 1024, 2)
        return {
            "success": True,
            "output_ifc_path": str(out_path),
            "file_size_kb": file_size_kb,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def debim_generate_viewer(
    manifest_yaml: str, output_html_path: str
) -> Dict[str, Any]:
    """
    Generate a standalone, zero-dependency interactive 3D HTML web viewer
    with OrbitControls, X-Ray, Section Cut, and Layer Explorer.
    """
    try:
        manifest = _parse_manifest_from_yaml_string(manifest_yaml)
        out_path = Path(output_html_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        html_content = generate_viewer_html(manifest)
        out_path.write_text(html_content, encoding="utf-8")

        return {
            "success": True,
            "output_html_path": str(out_path),
            "file_size_kb": round(out_path.stat().st_size / 1024, 2),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_mcp_server():
    """CLI entrypoint to run the debim MCP server via stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_mcp_server()
