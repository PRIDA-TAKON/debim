"""
Unit tests for Automated GLB Asset Baker and Section Plane Cut Tool
"""

from pathlib import Path
import tempfile
import numpy as np
import pytest
import trimesh
from typer.testing import CliRunner

from debim.cli import app
from debim.importer import _bake_element_to_glb, import_ifc_to_manifest
from debim.viewer import generate_viewer_html
from debim.schema import ProjectManifest, load_manifest

runner = CliRunner()


def test_trimesh_glb_export():
    """Verify trimesh exports valid binary .glb data."""
    verts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float64)
    faces = np.array([[0, 1, 2], [0, 2, 3], [0, 3, 1], [1, 3, 2]], dtype=np.int32)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces)

    with tempfile.TemporaryDirectory() as tmpdir:
        glb_path = Path(tmpdir) / "test_asset.glb"
        glb_bytes = trimesh.exchange.gltf.export_glb(mesh)
        glb_path.write_bytes(glb_bytes)

        assert glb_path.exists()
        content = glb_path.read_bytes()
        assert content.startswith(b"glTF")
        assert len(content) > 0


def test_bake_element_to_glb_helper():
    """Test _bake_element_to_glb helper with mock geometry."""
    class MockGeometry:
        def __init__(self):
            self.verts = (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
            self.faces = (0, 1, 2, 0, 2, 3, 0, 3, 1, 1, 3, 2)

    class MockShape:
        def __init__(self):
            self.geometry = MockGeometry()

    class MockElem:
        pass

    import ifcopenshell.geom
    orig_cs = ifcopenshell.geom.create_shape

    with tempfile.TemporaryDirectory() as tmpdir:
        assets_dir = Path(tmpdir) / "assets"
        mock_settings = object()

        ifcopenshell.geom.create_shape = lambda settings, elem: MockShape()

        try:
            rel_path = _bake_element_to_glb(MockElem(), "chair_test", assets_dir, mock_settings)
            assert rel_path == "assets/furniture/chair_test.glb"

            baked_file = assets_dir / "furniture" / "chair_test.glb"
            assert baked_file.exists()
            data = baked_file.read_bytes()
            assert data.startswith(b"glTF")

            # Re-use existing asset check
            rel_path_2 = _bake_element_to_glb(MockElem(), "chair_test", assets_dir, mock_settings)
            assert rel_path_2 == "assets/furniture/chair_test.glb"
        finally:
            ifcopenshell.geom.create_shape = orig_cs


def test_import_cli_bake_assets_flag(tmp_path):
    """Test bim import CLI command with --bake-assets flag."""
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "Duplex_A_20110907.ifc"
    out_yaml = tmp_path / "project.yaml"

    result = runner.invoke(app, ["import", str(fixture_path), "-o", str(out_yaml), "--bake-assets"])

    assert result.exit_code == 0
    assert "IFC Successfully Imported" in result.output
    assert out_yaml.exists()

    manifest = load_manifest(out_yaml)
    furniture_elems = [e for e in manifest.elements if e.class_ == "IfcCustomElement" and e.layer == "interior/furniture"]
    assert len(furniture_elems) == 61
    assert furniture_elems[0].source.startswith("assets/furniture/")

    # Check that at least one .glb asset file was created in tmp_path/assets/furniture/
    baked_assets = list((tmp_path / "assets" / "furniture").glob("*.glb"))
    assert len(baked_assets) > 0
    assert baked_assets[0].read_bytes().startswith(b"glTF")


def test_viewer_html_section_plane_and_gltfloader():
    """Verify generated viewer HTML includes GLTFLoader and section plane controls."""
    html = generate_viewer_html("examples/townhouse/project.yaml")

    assert "GLTFLoader.js" in html
    assert "section-plane-panel" in html
    assert "cut-height-slider" in html
    assert "renderer.localClippingEnabled = true;" in html
    assert "clipPlane.distanceToPoint" in html
