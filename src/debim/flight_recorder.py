"""
Audit Flight Recorder for debim continuous engine telemetry and reporting.

Exports timestamped machine-readable JSON logs (audit_log.json) and
human-readable Markdown audit reports (audit_report.md).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple, Union

from debim.audit import AuditMatrixReport


class AuditFlightRecorder:
    """
    Flight recorder engine for recording debim 5-layer audit matrix telemetry,
    diagnostics, and remediation outcomes.
    """

    def __init__(self, log_dir: Optional[Union[Path, str]] = None):
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = Path("dist/audit")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def record_audit(self, report: AuditMatrixReport) -> Tuple[Path, Path]:
        """
        Exports audit_log.json and audit_report.md to the configured log directory.
        Returns tuple of (json_path, markdown_path).
        """
        json_path = self.log_dir / "audit_log.json"
        md_path = self.log_dir / "audit_report.md"

        # 1. Write audit_log.json
        dict_data = report.model_dump(by_alias=True, exclude_none=False)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(dict_data, f, indent=2, ensure_ascii=False)
            f.write("\n")

        # 2. Write audit_report.md
        md_content = self.generate_markdown_report(report)
        md_path.write_text(md_content, encoding="utf-8")

        return json_path, md_path

    def generate_markdown_report(self, report: AuditMatrixReport) -> str:
        """
        Generates human-readable Markdown summary report from AuditMatrixReport.
        """
        status_badge = "🟢 PASSED" if report.passed else "🔴 VIOLATIONS DETECTED"

        lines = [
            f"# debim 5-Layer Audit Matrix Flight Recorder Report",
            f"",
            f"**Project Name:** `{report.project_name}` (`{report.project_id}`)",
            f"**Timestamp:** `{report.timestamp}`",
            f"**Status:** **{status_badge}**",
            f"**Total Checks Executed:** `{report.total_checks}`",
            f"**Total Violations:** `{report.total_violations}`",
            f"**Auto-Fix Remediations Applied:** `{report.remediations_applied}`",
            f"**Execution Time:** `{report.execution_time_sec:.4f}s`",
            f"",
            f"---",
            f"",
            f"## 📊 Layer Breakdown Summary",
            f"",
            f"| Layer | Layer Name | Status | Checks | Violations |",
            f"|:---:|:---|:---:|:---:|:---:|",
        ]

        for l_num, l_res in sorted(report.layers.items()):
            l_status = "✅ PASS" if l_res.passed else "❌ FAIL"
            lines.append(f"| {l_num} | {l_res.layer_name} | {l_status} | {l_res.checks_count} | {l_res.violations_count} |")

        lines.extend([
            f"",
            f"---",
            f"",
            f"## 🚨 Diagnostic Violations & Structured Remediations",
            f"",
        ])

        if report.total_violations == 0:
            lines.append("🎉 *Zero violations detected across all 5 audit layers! Building model meets all architectural, regulatory, structural, MEP, and constructability standards.*")
        else:
            for l_num, l_res in sorted(report.layers.items()):
                if l_res.violations_count > 0:
                    lines.append(f"### Layer {l_num}: {l_res.layer_name}")
                    lines.append("")
                    for item in l_res.items:
                        sev_icon = "🔴" if item.severity == "ERROR" else "⚠️"
                        lines.append(f"- **{sev_icon} [{item.rule_code}]** `{item.element_class}` (`{item.element_tag or 'GLOBAL'}`) — {item.message}")
                        if item.remediation:
                            rem = item.remediation
                            app_str = "✅ APPLIED" if rem.applied else "⏳ PROPOSED"
                            lines.append(f"  - **Auto-Fix Proposal [{rem.fix_action}]:** {rem.description} (`{app_str}`)")
                    lines.append("")

        lines.extend([
            f"",
            f"---",
            f"",
            f"*Generated automatically by debim Audit Engine v0.9.0 (@PRIDA-TAKON)*",
            f"",
        ])

        return "\n".join(lines)


def record_audit_telemetry(
    report: AuditMatrixReport, log_dir: Optional[Union[Path, str]] = None
) -> Tuple[Path, Path]:
    """
    Convenience function to record audit telemetry flight logs.
    """
    recorder = AuditFlightRecorder(log_dir=log_dir)
    return recorder.record_audit(report)
