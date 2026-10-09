"""
Documentation, exemplar generators, execution pipeline, and spec library tools for debim.
"""

from debim.docs.exemplar import (
    generate_exemplar_element,
    generate_exemplar_manifest,
    get_supported_exemplar_classes,
)
from debim.docs.pipeline import (
    ClassDocumentationEntry,
    Mesh3DPayload,
    execute_single_element_pipeline,
    generate_exemplar_entry,
    get_exemplar_manifest,
)
from debim.docs.thai_specs import get_thai_spec_clause, THAI_SPEC_LIBRARY

__all__ = [
    "generate_exemplar_element",
    "generate_exemplar_manifest",
    "get_supported_exemplar_classes",
    "ClassDocumentationEntry",
    "Mesh3DPayload",
    "execute_single_element_pipeline",
    "generate_exemplar_entry",
    "get_exemplar_manifest",
    "get_thai_spec_clause",
    "THAI_SPEC_LIBRARY",
]
