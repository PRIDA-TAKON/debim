"""Declarative Specifications, Auditor, and Package Registry for debim."""

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
from debim.spec.builder import (
    SpecificationBook,
    build_specification_book,
    get_masterformat_division,
)
from debim.spec.registry import (
    MaterialSpecPackage,
    SpecRegistryClient,
    resolve_package_urls,
    parse_spec_content,
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
    "SpecificationBook",
    "build_specification_book",
    "get_masterformat_division",
    "MaterialSpecPackage",
    "SpecRegistryClient",
    "resolve_package_urls",
    "parse_spec_content",
]
