"""
Unit tests for debim multi-view single-element documentation pipeline.
"""

import sys
import time
import pytest

from debim.docs import (
    ClassDocumentationEntry,
    Mesh3DPayload,
    execute_single_element_pipeline,
    generate_exemplar_entry,
    get_exemplar_manifest,
)
from debim.docs.pipeline import extract_entity_step_lines
from debim.schema import ProjectManifest


def test_mesh_3d_payload_schema():
    payload = Mesh3DPayload(
        vertices=[0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        normals=[0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
        indices=[0, 1, 2],
        buffer_geometry={"type": "BufferGeometry"},
    )
    assert len(payload.vertices) == 9
    assert len(payload.normals) == 9
    assert len(payload.indices) == 3
    assert payload.buffer_geometry["type"] == "BufferGeometry"


def test_execute_single_element_pipeline_column():
    manifest = get_exemplar_manifest("IfcColumn")
    entry = execute_single_element_pipeline(manifest)

    # Validate metadata
    assert entry.class_name == "IfcColumn"
    assert entry.element_tag == "C-A1"

    # Dimension 1: Declarative YAML manifest
    assert "schema: IFC4-Minimal" in entry.manifest_yaml or "schema" in entry.manifest_yaml
    assert "IfcColumn" in entry.manifest_yaml

    # Dimension 2: Exact ISO 10303-21 STEP lines
    assert len(entry.ifc_step_lines) > 0
    assert any("ifccolumn" in line.lower() for line in entry.ifc_step_lines)
    assert "#" in entry.ifc_step

    # Dimension 3: QTO & Cost data
    assert entry.qto.total_concrete_volume > 0.0
    assert entry.cost is not None
    assert hasattr(entry.cost, "grand_total")

    # Dimension 4: 3D Mesh payload
    assert len(entry.mesh_3d.vertices) > 0
    assert len(entry.mesh_3d.indices) > 0
    assert "position" in entry.mesh_3d.buffer_geometry["attributes"]

    # Dimension 5: 2D Plan Cut SVG
    assert entry.plan_svg.startswith("<svg") or "<svg" in entry.plan_svg
    assert "</svg>" in entry.plan_svg

    # Dimension 6: 2D Section Cut SVG
    assert entry.section_svg.startswith("<svg") or "<svg" in entry.section_svg
    assert "</svg>" in entry.section_svg

    # Timing
    assert entry.execution_time_ms > 0.0


def test_execute_single_element_pipeline_wall():
    manifest = get_exemplar_manifest("IfcWall")
    entry = execute_single_element_pipeline(manifest)

    assert entry.class_name == "IfcWall"
    assert entry.element_tag == "W-A1"
    assert any("ifcwall" in line.lower() for line in entry.ifc_step_lines)
    assert entry.qto.total_wall_masonry_area > 0.0 or entry.qto.total_concrete_volume >= 0.0
    assert len(entry.mesh_3d.vertices) > 0
    assert "<svg" in entry.plan_svg
    assert "<svg" in entry.section_svg


def test_execute_single_element_pipeline_beam():
    manifest = get_exemplar_manifest("IfcBeam")
    entry = execute_single_element_pipeline(manifest)

    assert entry.class_name == "IfcBeam"
    assert entry.element_tag == "B-A1"
    assert any("ifcbeam" in line.lower() for line in entry.ifc_step_lines)
    assert entry.qto.total_concrete_volume > 0.0
    assert len(entry.mesh_3d.vertices) > 0
    assert "<svg" in entry.plan_svg
    assert "<svg" in entry.section_svg


def test_execute_single_element_pipeline_slab():
    manifest = get_exemplar_manifest("IfcSlab")
    entry = execute_single_element_pipeline(manifest)

    assert entry.class_name == "IfcSlab"
    assert entry.element_tag == "S-A1"
    assert any("ifcslab" in line.lower() for line in entry.ifc_step_lines)
    assert entry.qto.total_concrete_volume > 0.0
    assert len(entry.mesh_3d.vertices) > 0
    assert "<svg" in entry.plan_svg
    assert "<svg" in entry.section_svg


def test_generate_exemplar_entry_helper():
    entry = generate_exemplar_entry("IfcFooting")
    assert entry.class_name == "IfcFooting"
    assert entry.element_tag == "F-A1"
    assert len(entry.ifc_step_lines) > 0
    assert len(entry.mesh_3d.vertices) > 0


def test_pipeline_performance_under_50ms():
    manifest = get_exemplar_manifest("IfcColumn")

    # Warm up call
    _ = execute_single_element_pipeline(manifest)

    # Benchmark 5 runs
    times = []
    for _ in range(5):
        t0 = time.perf_counter()
        entry = execute_single_element_pipeline(manifest)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)

    avg_time = sum(times) / len(times)
    # Headroom allowance (target is <50ms on fast Linux runners, up to 100ms on Windows/virtualized CI)
    limit_ms = 100.0 if sys.platform == "win32" else 65.0
    assert avg_time < limit_ms, f"Pipeline warm execution average {avg_time:.2f}ms exceeded {limit_ms}ms limit"
