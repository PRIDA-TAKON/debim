"""
Round-Trip Cognitive Regression Benchmark Engine for debim.
Measures 2D architectural blueprint clarity and benchmarks AI Vision models
as autonomous architectural assistants.
"""

from debim.benchmark.cognitive import (
    CognitiveBenchmarkEngine,
    CognitiveBenchmarkResult,
    generate_json_report,
    generate_markdown_report,
    run_cognitive_benchmark,
)

__all__ = [
    "CognitiveBenchmarkEngine",
    "CognitiveBenchmarkResult",
    "generate_json_report",
    "generate_markdown_report",
    "run_cognitive_benchmark",
]
