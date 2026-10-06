"""
debim: Minimal Declarative BIM (Building-as-Code)
"""

from debim.version import __version__
from debim.modular import bundle_manifest, split_manifest

__all__ = ["__version__", "bundle_manifest", "split_manifest"]
