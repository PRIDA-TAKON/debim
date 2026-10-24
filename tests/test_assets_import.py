"""
Unit tests for external asset reference import (OBJ/GLTF/GLB to IFC proxy face sets).
"""

import json
from pathlib import Path
import struct

import pytest

from debim.assets import parse_gltf_glb_file, parse_mesh_file, parse_obj_file
from debim.compiler import compile_to_ifc
from debim.resolver import resolve_manifest
from debim.schema import (
    AssetReference,
    IfcBuildingElementProxy,
    ProjectManifest,
    ProxyGeometry,
    ProxyPlacement,
    load_manifest,
)


def create_sample_obj(path: Path) -> Path:
    """Create a sample Wavefront .obj cube file."""
    obj_content = """# Sample Cube OBJ
v -0.5 -0.5 0.0
v  0.5 -0.5 0.0
v  0.5  0.5 0.0
v -0.5  0.5 0.0
v -0.5 -0.5 1.0
v  0.5 -0.5 1.0
v  0.5  0.5 1.0
v -0.5  0.5 1.0

# 6 quad faces -> 12 triangles
f 1 2 3
f 1 3 4
f 5 7 6
f 5 8 7
f 1 5 6
f 1 6 2
f 2 6 7
f 2 7 3
f 3 7 8
f 3 8 4
f 5 1 4
f 5 4 8
"""
    path.write_text(obj_content, encoding="utf-8")
    return path


def create_sample_gltf(path: Path) -> Path:
    """Create a sample glTF 2.0 embedded base64 triangle file."""
    import base64

    # 3 vertices float32: (0,0,0), (1,0,0), (0,1,0) -> 36 bytes
    verts = struct.pack("<9f", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    # 3 indices uint16: 0, 1, 2 -> 6 bytes + 2 padding -> 8 bytes
    indices = struct.pack("<3H", 0, 1, 2) + b"\x00\x00"

    buffer_data = verts + indices
    b64_buf = base64.b64encode(buffer_data).decode("ascii")

    gltf_data = {
        "asset": {"version": "2.0"},
        "buffers": [
            {
                "byteLength": len(buffer_data),
                "uri": f"data:application/octet-stream;base64,{b64_buf}",
            }
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 36, "target": 34962},
            {"buffer": 0, "byteOffset": 36, "byteLength": 6, "target": 34963},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "byteOffset": 0,
                "componentType": 5126,  # FLOAT
                "count": 3,
                "type": "VEC3",
                "max": [1.0, 1.0, 0.0],
                "min": [0.0, 0.0, 0.0],
            },
            {
                "bufferView": 1,
                "byteOffset": 0,
                "componentType": 5123,  # UNSIGNED_SHORT
                "count": 3,
                "type": "SCALAR",
            },
        ],
        "meshes": [
            {
                "name": "TriangleMesh",
                "primitives": [{"attributes": {"POSITION": 0}, "indices": 1}],
            }
        ],
        "nodes": [{"mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }

    path.write_text(json.dumps(gltf_data), encoding="utf-8")
    return path


def test_asset_reference_schema():
    asset = AssetReference(
        file="assets/lamp.obj",
        scale=(2.0, 2.0, 2.0),
        rotation_offset=(0.0, 0.0, 90.0),
        material_override="MAT-GOLD",
    )
    geom = ProxyGeometry(asset=asset)
    proxy = IfcBuildingElementProxy(
        tag="SCULPTURE-01",
        geometry=geom,
        placement=ProxyPlacement(storey="L1"),
    )

    assert proxy.geometry.asset.file == "assets/lamp.obj"
    assert proxy.geometry.asset.scale == (2.0, 2.0, 2.0)
    assert proxy.geometry.asset.rotation_offset == (0.0, 0.0, 90.0)
    assert proxy.geometry.asset.material_override == "MAT-GOLD"


def test_parse_obj_mesh(tmp_path: Path):
    obj_path = create_sample_obj(tmp_path / "cube.obj")
    verts, faces = parse_obj_file(obj_path)

    assert len(verts) == 8
    assert len(faces) == 12
    assert faces[0] == (1, 2, 3)

    # Test scaling & rotation via parse_mesh_file
    t_verts, t_faces = parse_mesh_file(obj_path, scale=(2.0, 2.0, 2.0))
    assert len(t_verts) == 8
    assert t_verts[0] == (-1.0, -1.0, 0.0)


def create_sample_glb(path: Path) -> Path:
    """Create a sample binary .glb file with a single triangle."""
    verts = struct.pack("<9f", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    indices = struct.pack("<3H", 0, 1, 2) + b"\x00\x00"
    bin_chunk_data = verts + indices

    gltf_json = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(bin_chunk_data)}],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 36, "target": 34962},
            {"buffer": 0, "byteOffset": 36, "byteLength": 6, "target": 34963},
        ],
        "accessors": [
            {
                "bufferView": 0,
                "byteOffset": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
            },
            {
                "bufferView": 1,
                "byteOffset": 0,
                "componentType": 5123,
                "count": 3,
                "type": "SCALAR",
            },
        ],
        "meshes": [
            {
                "name": "TriangleMesh",
                "primitives": [{"attributes": {"POSITION": 0}, "indices": 1}],
            }
        ],
        "nodes": [{"mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }

    json_bytes = json.dumps(gltf_json).encode("utf-8")
    # Pad json_bytes to 4-byte boundary with spaces
    json_pad = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b" " * json_pad

    # Pad bin_chunk_data to 4-byte boundary with nulls
    bin_pad = (4 - (len(bin_chunk_data) % 4)) % 4
    bin_chunk_data += b"\x00" * bin_pad

    json_header = struct.pack("<II", len(json_bytes), 0x4E4F534A)  # "JSON"
    bin_header = struct.pack("<II", len(bin_chunk_data), 0x004E4942)  # "BIN\0"

    total_len = 12 + len(json_header) + len(json_bytes) + len(bin_header) + len(bin_chunk_data)
    glb_header = struct.pack("<4sII", b"glTF", 2, total_len)

    with open(path, "wb") as f:
        f.write(glb_header)
        f.write(json_header)
        f.write(json_bytes)
        f.write(bin_header)
        f.write(bin_chunk_data)

    return path


def test_parse_gltf_mesh(tmp_path: Path):
    gltf_path = create_sample_gltf(tmp_path / "triangle.gltf")
    verts, faces = parse_gltf_glb_file(gltf_path)

    assert len(verts) == 3
    assert len(faces) == 1
    assert verts[0] == (0.0, 0.0, 0.0)
    assert verts[1] == (1.0, 0.0, 0.0)


def test_parse_glb_mesh(tmp_path: Path):
    glb_path = create_sample_glb(tmp_path / "triangle.glb")
    verts, faces = parse_gltf_glb_file(glb_path)

    assert len(verts) == 3
    assert len(faces) == 1
    assert verts[0] == (0.0, 0.0, 0.0)
    assert verts[1] == (1.0, 0.0, 0.0)


def test_compile_obj_asset_to_ifc(tmp_path: Path):
    obj_path = create_sample_obj(tmp_path / "statue.obj")

    manifest_yaml = f"""
schema: IFC4-Minimal
project:
  id: PROJ-ASSET-01
  name: Asset Import Project
spatial_structure:
  storeys:
    - id: L1
      name: Level 1
      elevation: 0.0
      height: 3.5
grids:
  axes_x:
    A: 0.0
  axes_y:
    "1": 0.0
materials:
  - id: MAT-BRONZE
    name: Bronze
    category: steel
    unit_cost_ref: MAT-BRONZE-01
proxies:
  - tag: STATUE-01
    class: IfcBuildingElementProxy
    material: MAT-BRONZE
    geometry:
      asset:
        file: "{obj_path.as_posix()}"
        scale: [1.5, 1.5, 1.5]
        rotation_offset: [0, 0, 45]
    placement:
      storey: L1
      grid: [A, "1"]
"""
    m_file = tmp_path / "project.yaml"
    out_ifc_step = tmp_path / "output_step.ifc"
    out_ifc_shell = tmp_path / "output_shell.ifc"

    m_file.write_text(manifest_yaml, encoding="utf-8")

    manifest = load_manifest(m_file)
    resolved = resolve_manifest(manifest)

    # 1. Test StepSerializer fallback
    compile_to_ifc(resolved, out_ifc_step, force_fallback=True)
    assert out_ifc_step.exists()
    step_content = out_ifc_step.read_text(encoding="utf-8")

    assert "STATUE-01" in step_content
    assert "IFCTRIANGULATEDFACESET" in step_content
    assert "IFCCARTESIANPOINTLIST3D" in step_content

    # 2. Test IfcOpenShell compilation
    compile_to_ifc(resolved, out_ifc_shell, force_fallback=False)
    assert out_ifc_shell.exists()
    shell_content = out_ifc_shell.read_text(encoding="utf-8")

    assert "STATUE-01" in shell_content
    assert "IFCTRIANGULATEDFACESET" in shell_content or "IfcTriangulatedFaceSet" in shell_content


def test_compile_gltf_asset_to_ifc(tmp_path: Path):
    gltf_path = create_sample_gltf(tmp_path / "fixture.gltf")

    manifest_yaml = f"""
schema: IFC4-Minimal
project:
  id: PROJ-ASSET-02
  name: GLTF Asset Import
spatial_structure:
  storeys:
    - id: L1
      name: Level 1
      elevation: 0.0
      height: 3.5
grids:
  axes_x:
    A: 0.0
  axes_y:
    "1": 0.0
materials:
  - id: MAT-STEEL
    name: Steel
    category: steel
    unit_cost_ref: MAT-STEEL
proxies:
  - tag: LIGHT-ASSET-01
    class: IfcLightFixture
    material: MAT-STEEL
    geometry:
      asset:
        file: "{gltf_path.as_posix()}"
        scale: [1.0, 1.0, 1.0]
    placement:
      storey: L1
      grid: [A, "1"]
"""
    m_file = tmp_path / "project.yaml"
    out_ifc = tmp_path / "output_gltf.ifc"

    m_file.write_text(manifest_yaml, encoding="utf-8")

    manifest = load_manifest(m_file)
    resolved = resolve_manifest(manifest)
    compile_to_ifc(resolved, out_ifc, force_fallback=True)

    assert out_ifc.exists()
    content = out_ifc.read_text(encoding="utf-8")

    assert "LIGHT-ASSET-01" in content
    assert "IFCTRIANGULATEDFACESET" in content
