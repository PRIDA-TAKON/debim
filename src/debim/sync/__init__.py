"""
debim.sync

Automated As-built Synchronization engine for debim.
Detects spatial discrepancies between scanned as-built point clouds and model elements,
and performs surgical comment-preserving round-trip YAML updates on .debim files.
"""

from debim.sync.detector import (
    ChangeProposal,
    DeviationResult,
    ElementDeviation,
    detect_asbuilt_discrepancies,
)
from debim.sync.patcher import (
    apply_asbuilt_patch,
)

__all__ = [
    "ChangeProposal",
    "DeviationResult",
    "ElementDeviation",
    "detect_asbuilt_discrepancies",
    "apply_asbuilt_patch",
]
