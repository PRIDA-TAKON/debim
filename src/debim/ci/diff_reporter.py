"""
Core Diff Reporter Module for Building-as-Code projects.
Computes QTO & cost deltas, evaluates compliance audits, and generates GitHub PR Markdown reports.
"""

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from debim.audit import run_5_layer_audit
from debim.compat import BaseModel, Field
from debim.cost import estimate_cost, generate_cost_template, load_price_catalog
from debim.qto import calculate_qto
from debim.schema import ProjectManifest, load_manifest


class CostDiffResult(BaseModel):
    base_concrete_m3: float = 0.0
    head_concrete_m3: float = 0.0
    delta_concrete_m3: float = 0.0
    pct_concrete: float = 0.0

    base_rebar_kg: float = 0.0
    head_rebar_kg: float = 0.0
    delta_rebar_kg: float = 0.0
    pct_rebar: float = 0.0

    base_formwork_m2: float = 0.0
    head_formwork_m2: float = 0.0
    delta_formwork_m2: float = 0.0
    pct_formwork: float = 0.0

    base_cost: float = 0.0
    head_cost: float = 0.0
    delta_cost: float = 0.0
    pct_cost: float = 0.0

    currency: str = "THB"
    rules: str = "cg-v480"
    detailed_items_diff: List[Dict[str, Any]] = Field(default_factory=list)


class ComplianceSummary(BaseModel):
    status: str = "PASS"  # 'PASS' | 'WARNING' | 'FAIL'
    total_checks: int = 0
    total_violations: int = 0
    errors_count: int = 0
    warnings_count: int = 0
    jurisdiction: str = "th"
    layer_results: Dict[int, Dict[str, Any]] = Field(default_factory=dict)
    violations: List[Dict[str, Any]] = Field(default_factory=list)


def compare_manifest_costs(
    base_manifest_path: Union[str, Path],
    head_manifest_path: Union[str, Path],
    rules: str = "cg-v480",
    price_catalog_path: Optional[Union[str, Path]] = None,
) -> CostDiffResult:
    """
    Compares concrete volume (m3), rebar weight (kg), formwork area (m2), and total estimated cost
    between Base branch manifest and PR Head branch manifest.
    """
    base_m = load_manifest(base_manifest_path) if isinstance(base_manifest_path, (str, Path)) else base_manifest_path
    head_m = load_manifest(head_manifest_path) if isinstance(head_manifest_path, (str, Path)) else head_manifest_path

    base_qto = calculate_qto(base_m)
    head_qto = calculate_qto(head_m)

    # Price catalog loading or automatic benchmark template generation
    if price_catalog_path and Path(price_catalog_path).exists():
        catalog = load_price_catalog(price_catalog_path)
    else:
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as tmp:
            tmp_p = Path(tmp.name)
        generate_cost_template(head_m, output_path=tmp_p)
        catalog = load_price_catalog(tmp_p)
        try:
            tmp_p.unlink()
        except Exception:
            pass
        # Set baseline benchmark values if generated template was zeroed
        for item in catalog.items.values():
            if item.unit.lower() == "m3":
                item.material_cost = item.material_cost or 2400.0
                item.labor_cost = item.labor_cost or 450.0
            elif item.unit.lower() == "m2":
                item.material_cost = item.material_cost or 350.0
                item.labor_cost = item.labor_cost or 120.0
            elif item.unit.lower() == "kg":
                item.material_cost = item.material_cost or 32.0
                item.labor_cost = item.labor_cost or 5.0
            elif item.unit.lower() == "m":
                item.material_cost = item.material_cost or 180.0
                item.labor_cost = item.labor_cost or 60.0

    base_estimate = estimate_cost(base_qto, catalog, base_m)
    head_estimate = estimate_cost(head_qto, catalog, head_m)

    # Compute QTO deltas
    base_conc = base_qto.total_concrete_volume
    head_conc = head_qto.total_concrete_volume
    d_conc = head_conc - base_conc
    pct_conc = (d_conc / base_conc * 100.0) if base_conc > 0 else (100.0 if head_conc > 0 else 0.0)

    base_rebar = base_qto.total_rebar_weight
    head_rebar = head_qto.total_rebar_weight
    d_rebar = head_rebar - base_rebar
    pct_rebar = (d_rebar / base_rebar * 100.0) if base_rebar > 0 else (100.0 if head_rebar > 0 else 0.0)

    base_form = base_qto.total_formwork_area
    head_form = head_qto.total_formwork_area
    d_form = head_form - base_form
    pct_form = (d_form / base_form * 100.0) if base_form > 0 else (100.0 if head_form > 0 else 0.0)

    # Compute Cost deltas
    base_c = base_estimate.grand_total
    head_c = head_estimate.grand_total
    d_c = head_c - base_c
    pct_c = (d_c / base_c * 100.0) if base_c > 0 else (100.0 if head_c > 0 else 0.0)

    # Compute item-level diffs
    base_items_map = {item.code: item for item in base_estimate.line_items}
    head_items_map = {item.code: item for item in head_estimate.line_items}
    all_codes = sorted(list(set(base_items_map.keys()) | set(head_items_map.keys())))

    detailed_diffs = []
    for code in all_codes:
        b_item = base_items_map.get(code)
        h_item = head_items_map.get(code)

        name = (h_item.name if h_item else b_item.name) if (h_item or b_item) else code
        unit = (h_item.unit if h_item else b_item.unit) if (h_item or b_item) else ""

        b_qty = b_item.quantity if b_item else 0.0
        h_qty = h_item.quantity if h_item else 0.0
        d_qty = h_qty - b_qty

        b_amt = b_item.total_amount if b_item else 0.0
        h_amt = h_item.total_amount if h_item else 0.0
        d_amt = h_amt - b_amt

        if abs(d_qty) > 1e-4 or abs(d_amt) > 1e-2:
            detailed_diffs.append({
                "code": code,
                "name": name,
                "unit": unit,
                "base_qty": b_qty,
                "head_qty": h_qty,
                "delta_qty": d_qty,
                "base_amount": b_amt,
                "head_amount": h_amt,
                "delta_amount": d_amt,
            })

    return CostDiffResult(
        base_concrete_m3=base_conc,
        head_concrete_m3=head_conc,
        delta_concrete_m3=d_conc,
        pct_concrete=pct_conc,
        base_rebar_kg=base_rebar,
        head_rebar_kg=head_rebar,
        delta_rebar_kg=d_rebar,
        pct_rebar=pct_rebar,
        base_formwork_m2=base_form,
        head_formwork_m2=head_form,
        delta_formwork_m2=d_form,
        pct_formwork=pct_form,
        base_cost=base_c,
        head_cost=head_c,
        delta_cost=d_c,
        pct_cost=pct_c,
        currency=catalog.currency,
        rules=rules,
        detailed_items_diff=detailed_diffs,
    )


def run_pr_compliance_check(
    head_manifest_path: Union[str, Path],
    jurisdiction: str = "th",
) -> ComplianceSummary:
    """
    Runs debim 5-layer audit matrix (MR 55 setback rules, structural spans, clearances)
    and returns PASS / WARNING / FAIL compliance summary status.
    """
    report = run_5_layer_audit(head_manifest_path, apply_fixes=False, jurisdiction=jurisdiction)

    errors_cnt = 0
    warnings_cnt = 0
    violations_list = []

    layer_results_dict = {}
    for l_num, l_res in report.layers.items():
        layer_results_dict[l_num] = {
            "name": l_res.layer_name,
            "passed": l_res.passed,
            "checks_count": l_res.checks_count,
            "violations_count": l_res.violations_count,
        }
        for item in l_res.items:
            sev = item.severity.upper()
            if sev == "ERROR":
                errors_cnt += 1
            elif sev == "WARNING":
                warnings_cnt += 1

            violations_list.append({
                "layer": l_num,
                "layer_name": l_res.layer_name,
                "rule_code": item.rule_code,
                "severity": item.severity,
                "element_tag": item.element_tag,
                "element_class": item.element_class,
                "message": item.message,
                "remediation": item.remediation.model_dump() if item.remediation else None,
            })

    if errors_cnt > 0:
        overall_status = "FAIL"
    elif warnings_cnt > 0:
        overall_status = "WARNING"
    else:
        overall_status = "PASS"

    return ComplianceSummary(
        status=overall_status,
        total_checks=report.total_checks,
        total_violations=report.total_violations,
        errors_count=errors_cnt,
        warnings_count=warnings_cnt,
        jurisdiction=jurisdiction,
        layer_results=layer_results_dict,
        violations=violations_list,
    )


def _fmt_pct(pct: float) -> str:
    if pct > 1e-4:
        return f"+{pct:.1f}%"
    elif pct < -1e-4:
        return f"{pct:.1f}%"
    else:
        return "0.0%"


def _fmt_delta_val(val: float, unit: str = "") -> str:
    u = f" {unit}" if unit else ""
    if val > 1e-4:
        return f"+{val:,.2f}{u}"
    elif val < -1e-4:
        return f"{val:,.2f}{u}"
    else:
        return f"0.00{u}"


def generate_pr_markdown_report(cost_diff: CostDiffResult, compliance: ComplianceSummary) -> str:
    """
    Generates a beautifully formatted GitHub PR comment in Markdown with status badges,
    summary tables, and collapsible detailed quantity breakdowns.
    """
    # Badges
    if compliance.status == "PASS":
        comp_badge = "![Compliance](https://img.shields.io/badge/Building_Compliance-PASS-brightgreen)"
    elif compliance.status == "WARNING":
        comp_badge = "![Compliance](https://img.shields.io/badge/Building_Compliance-WARNING-yellow)"
    else:
        comp_badge = "![Compliance](https://img.shields.io/badge/Building_Compliance-FAIL-red)"

    d_cost_str = f"{cost_diff.delta_cost:+,.0f} {cost_diff.currency}" if abs(cost_diff.delta_cost) > 1e-2 else f"0 {cost_diff.currency}"

    if cost_diff.delta_cost > 1e-2:
        cost_badge = f"![Cost Delta](https://img.shields.io/badge/Cost_Delta-{d_cost_str.replace(' ', '_')}-red)"
    elif cost_diff.delta_cost < -1e-2:
        cost_badge = f"![Cost Delta](https://img.shields.io/badge/Cost_Delta-{d_cost_str.replace(' ', '_')}-brightgreen)"
    else:
        cost_badge = f"![Cost Delta](https://img.shields.io/badge/Cost_Delta-{d_cost_str.replace(' ', '_')}-blue)"

    md_lines = [
        "## 🏢 Building-as-Code CI Audit & Cost Diff Report",
        "",
        f"{comp_badge} {cost_badge}",
        "",
        "### 📊 Material Quantities & Estimated Cost Variance",
        "",
        "| Material / Cost Metric | Base Branch | PR Branch | Net Change (Δ) | Variance (%) |",
        "| :--- | :---: | :---: | :---: | :---: |",
        f"| **Concrete Volume** | {cost_diff.base_concrete_m3:,.2f} m³ | {cost_diff.head_concrete_m3:,.2f} m³ | `{_fmt_delta_val(cost_diff.delta_concrete_m3, 'm³')}` | `{_fmt_pct(cost_diff.pct_concrete)}` |",
        f"| **Steel Reinforcement** | {cost_diff.base_rebar_kg:,.2f} kg | {cost_diff.head_rebar_kg:,.2f} kg | `{_fmt_delta_val(cost_diff.delta_rebar_kg, 'kg')}` | `{_fmt_pct(cost_diff.pct_rebar)}` |",
        f"| **Formwork Area** | {cost_diff.base_formwork_m2:,.2f} m² | {cost_diff.head_formwork_m2:,.2f} m² | `{_fmt_delta_val(cost_diff.delta_formwork_m2, 'm²')}` | `{_fmt_pct(cost_diff.pct_formwork)}` |",
        f"| **Total Estimated Cost** | {cost_diff.base_cost:,.2f} {cost_diff.currency} | {cost_diff.head_cost:,.2f} {cost_diff.currency} | `{_fmt_delta_val(cost_diff.delta_cost, cost_diff.currency)}` | `{_fmt_pct(cost_diff.pct_cost)}` |",
        "",
        "### 🛡️ 5-Layer Architectural & Engineering Compliance Summary",
        "",
        f"- **Overall Audit Status**: `{compliance.status}`",
        f"- **Total Rules Checked**: `{compliance.total_checks}`",
        f"- **Violations Found**: `{compliance.total_violations}` (`{compliance.errors_count}` Errors, `{compliance.warnings_count}` Warnings)",
        "",
        "| Layer | Layer Name | Status | Checks | Violations |",
        "| :---: | :--- | :---: | :---: | :---: |",
    ]

    for l_num, l_data in sorted(compliance.layer_results.items()):
        l_status = "✅ PASS" if l_data.get("passed") else "❌ FAIL"
        md_lines.append(
            f"| L{l_num} | {l_data.get('name', f'Layer {l_num}')} | {l_status} | {l_data.get('checks_count', 0)} | {l_data.get('violations_count', 0)} |"
        )

    if compliance.violations:
        md_lines.extend([
            "",
            "#### ⚠️ Detected Non-Compliance Violations",
            "",
            "| Rule Code | Layer | Class / Tag | Message | Recommended Remediation |",
            "| :--- | :---: | :--- | :--- | :--- |",
        ])
        for v in compliance.violations:
            rem_str = "-"
            if v.get("remediation"):
                rem_str = f"`{v['remediation'].get('fix_action')}`: {v['remediation'].get('description')}"
            md_lines.append(
                f"| `{v['rule_code']}` | L{v['layer']} | {v.get('element_class') or ''} ({v.get('element_tag') or '-'}) | {v['message']} | {rem_str} |"
            )

    # Collapsible Detailed Items Breakdown
    if cost_diff.detailed_items_diff:
        md_lines.extend([
            "",
            "<details>",
            "<summary>🔍 Detailed Itemized Quantity & Cost Delta Breakdown</summary>",
            "",
            "| Item Code | Description | Unit | Base Qty | PR Qty | Δ Qty | Base Cost | PR Cost | Δ Cost |",
            "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
        ])
        for item in cost_diff.detailed_items_diff:
            md_lines.append(
                f"| `{item['code']}` | {item['name']} | {item['unit']} | {item['base_qty']:,.2f} | {item['head_qty']:,.2f} | `{item['delta_qty']:+,.2f}` | {item['base_amount']:,.2f} | {item['head_amount']:,.2f} | `{item['delta_amount']:+,.2f}` |"
            )
        md_lines.extend([
            "",
            "</details>",
        ])

    md_lines.extend([
        "",
        "---",
        "🌐 *Generated automatically by [debim](https://github.com/PRIDA-TAKON/debim) Building-as-Code CI Engine*",
    ])

    return "\n".join(md_lines)
