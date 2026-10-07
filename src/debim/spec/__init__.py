"""
Declarative Specifications & Discrepancy Auditor package for debim.
"""

from debim.spec.schema import (
    IndustryStandards,
    MaterialSpec,
    SpecificationManifest,
    StructuredClauses,
    load_spec_manifest,
)
from debim.spec.audit import (
    SpecAuditResult,
    audit_project_specs,
    extract_project_materials,
)

__all__ = [
    "IndustryStandards",
    "MaterialSpec",
    "SpecificationManifest",
    "StructuredClauses",
    "load_spec_manifest",
    "SpecAuditResult",
    "audit_project_specs",
    "extract_project_materials",
]
