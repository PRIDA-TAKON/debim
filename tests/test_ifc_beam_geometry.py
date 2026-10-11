"""
Unit and visual regression tests for IfcBeam 3D & 2D geometry resolution.
"""

from pathlib import Path
import pytest
from debim.importer import import_ifc_to_manifest
from debim.resolver import resolve_manifest
from debim.draw.projection import slice_storey
from debim.viewer import generate_viewer_html


def test_resolved_beam_properties_and_precision():
    ifc_path = Path("tests/fixtures/Duplex_A_20110907.ifc")
    assert ifc_path.exists()

    manifest = import_ifc_to_manifest(ifc_path)
    resolved = resolve_manifest(manifest)

    assert len(resolved.beams) > 0

    for beam in resolved.beams:
        assert beam.width > 0.1
        assert beam.depth > 0.2
        assert beam.span_length > 1.0
        assert len(beam.start_point) == 3
        assert len(beam.end_point) == 3
        assert len(beam.direction_vector_3d) == 3

    # Check specific beam
    w310_beam = next((b for b in resolved.beams if "207325" in b.tag), None)
    assert w310_beam is not None
    assert abs(w310_beam.width - 0.203) < 1e-3
    assert abs(w310_beam.depth - 0.303) < 1e-3
    assert abs(w310_beam.span_length - 7.52) < 0.1


def test_beam_2d_cut_plane_projection():
    ifc_path = Path("tests/fixtures/Duplex_A_20110907.ifc")
    manifest = import_ifc_to_manifest(ifc_path)
    resolved = resolve_manifest(manifest)

    storey_id = manifest.spatial_structure.storeys[0].id
    cut_res = slice_storey(resolved, storey_id=storey_id, cut_offset_z=0.20)

    beam_elems = [e for e in cut_res.cut_elements + cut_res.projection_elements if e.element_class == "IfcBeam"]
    assert len(beam_elems) >= 4

    for b in beam_elems:
        assert b.geometry is not None
        assert b.geometry.area > 0.1
        assert "width" in b.properties
        assert "depth" in b.properties


def test_beam_viewer_3d_html_generation():
    ifc_path = Path("tests/fixtures/Duplex_A_20110907.ifc")
    manifest = import_ifc_to_manifest(ifc_path)
    resolved = resolve_manifest(manifest)

    html = generate_viewer_html(resolved)
    assert "IfcBeam" in html
    assert "BOX" in html or "RECTANGLE" in html or "ISHAPE" in html
