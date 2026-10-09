"""
Documentation, exemplar generators, execution pipeline, spec library, and Class Directory engine for debim.
"""

from debim.docs.exemplar import (
    generate_exemplar_element,
    generate_exemplar_manifest,
    get_supported_exemplar_classes,
)
from debim.docs.generator import (
    DEFAULT_CLASS_DIRECTORY_DATA,
    export_class_directory,
    generate_class_directory_html,
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
    "DEFAULT_CLASS_DIRECTORY_DATA",
    "export_class_directory",
    "generate_class_directory_html",
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
