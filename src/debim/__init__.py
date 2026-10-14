"""
debim: Minimal Declarative BIM (Building-as-Code)
"""

from debim.version import __version__
from debim.modular import bundle_manifest, split_manifest
from debim.loader import parse_debim, load_debim_file, resolve_default_manifest_path

__all__ = [
    "__version__",
    "bundle_manifest",
    "split_manifest",
    "parse_debim",
    "load_debim_file",
    "resolve_default_manifest_path",
]
