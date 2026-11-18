"""
debim.resolution
AI-Driven Construction Engineering & Clash Resolution Engine.
Simulates human engineer cognitive workflow for high-res drawing scans,
scoped declarative modeling, clash resolution, and multi-scenario trade-off audit.
"""

from debim.resolution.funnel import (
    VisualFunnelSearcher,
    DomainHypothesis,
    ingest_drawing_scans,
)
from debim.resolution.extractor import (
    ScopedExtractor,
    ClashDetector,
    extract_scoped_roi,
    detect_clashes,
)
from debim.resolution.variants import (
    VariantGenerator,
    generate_resolution_variants,
)
from debim.resolution.audit import (
    TradeoffAuditor,
    audit_resolution_options,
    commit_resolution_solution,
)
from debim.resolution.redline import (
    generate_redline_overlay,
)

__all__ = [
    "VisualFunnelSearcher",
    "DomainHypothesis",
    "ingest_drawing_scans",
    "ScopedExtractor",
    "ClashDetector",
    "extract_scoped_roi",
    "detect_clashes",
    "VariantGenerator",
    "generate_resolution_variants",
    "TradeoffAuditor",
    "audit_resolution_options",
    "commit_resolution_solution",
    "generate_redline_overlay",
]
