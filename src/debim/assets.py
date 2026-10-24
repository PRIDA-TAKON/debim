"""
External 3D Mesh Asset Parser Module (.obj, .gltf, .glb) for debim.
Extracts 3D vertex coordinates and triangular face indices from external assets.
"""

import json
import math
import os
from pathlib import Path
import struct
from typing import Any, Dict, List, Optional, Tuple, Union

from debim.schema import Dimensions


def _rotate_vertex(
    pt: Tuple[float, float, float], rx_deg: float, ry_deg: float, rz_deg: float
) -> Tuple[float, float, float]:
    """Rotate a 3D vertex by Euler angles rx, ry, rz (in degrees)."""
    x, y, z = pt
    rx, ry, rz = math.radians(rx_deg), math.radians(ry_deg), math.radians(rz_deg)

    # Rotate X
    if abs(rx) > 1e-6:
        cx, sx = math.cos(rx), math.sin(rx)
        y, z = y * cx - z * sx, y * sx + z * cx

    # Rotate Y
    if abs(ry) > 1e-6:
        cy, sy = math.cos(ry), math.sin(ry)
        x, z = x * cy + z * sy, -x * sy + z * cy

    # Rotate Z
    if abs(rz) > 1e-6:
        cz, sz = math.cos(rz), math.sin(rz)
        x, y = x * cz - y * sz, x * sz + y * cz

    return (x, y, z)


def _transform_vertices(
    vertices: List[Tuple[float, float, float]],
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    rotation_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> List[Tuple[float, float, float]]:
    """Apply 3D scaling and rotation offset to a list of vertex coordinates."""
    sx, sy, sz = float(scale[0]), float(scale[1]), float(scale[2])
    rx, ry, rz = float(rotation_offset[0]), float(rotation_offset[1]), float(rotation_offset[2])

    transformed = []
    for x, y, z in vertices:
        # 1. Apply scale
        vx, vy, vz = x * sx, y * sy, z * sz
        # 2. Apply rotation offset
        if abs(rx) > 1e-6 or abs(ry) > 1e-6 or abs(rz) > 1e-6:
            vx, vy, vz = _rotate_vertex((vx, vy, vz), rx, ry, rz)
        transformed.append((round(vx, 6), round(vy, 6), round(vz, 6)))

    return transformed


def parse_obj_file(filepath: Union[str, Path]) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]:
    """
    Lightweight pure-Python parser for Wavefront .obj files.
    Returns (vertices, faces_1based).
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"OBJ file not found: {path}")

    vertices: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, int, int]] = []

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            if not parts:
                continue

            cmd = parts[0].lower()
            if cmd == "v" and len(parts) >= 4:
                try:
                    vx, vy, vz = float(parts[1]), float(parts[2]), float(parts[3])
                    vertices.append((vx, vy, vz))
                except ValueError:
                    continue

            elif cmd == "f" and len(parts) >= 4:
                # Face indices in OBJ are 1-based (can be v, v/vt, v/vt/vn, or v//vn)
                face_verts = []
                for p in parts[1:]:
                    v_idx_str = p.split("/")[0]
                    try:
                        v_idx = int(v_idx_str)
                        if v_idx < 0:
                            v_idx = len(vertices) + 1 + v_idx
                        face_verts.append(v_idx)
                    except ValueError:
                        continue

                if len(face_verts) >= 3:
                    # Triangulate fan: (0, 1, 2), (0, 2, 3), ...
                    for i in range(1, len(face_verts) - 1):
                        faces.append((face_verts[0], face_verts[i], face_verts[i + 1]))

    return vertices, faces


def parse_gltf_glb_file(
    filepath: Union[str, Path]
) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]:
    """
    Lightweight pure-Python parser for glTF 2.0 (.gltf and .glb) files.
    Extracts POSITION accessor vertices and INDICES accessor faces.
    Returns (vertices, faces_1based).
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"glTF/GLB file not found: {path}")

    is_glb = path.suffix.lower() == ".glb" or path.name.lower().endswith(".glb")

    gltf_json: Dict[str, Any] = {}
    binary_buffers: List[bytes] = []

    if is_glb:
        with open(path, "rb") as f:
            data = f.read()

        if len(data) < 12:
            raise ValueError(f"Invalid GLB file (too short): {path}")

        magic, version, length = struct.unpack("<4sII", data[:12])
        if magic != b"glTF":
            raise ValueError(f"Invalid GLB magic header in {path}")

        offset = 12
        while offset + 8 <= len(data):
            chunk_len, chunk_type = struct.unpack("<II", data[offset : offset + 8])
            chunk_data = data[offset + 8 : offset + 8 + chunk_len]
            offset += 8 + chunk_len

            if chunk_type == 0x4E4F534A:  # "JSON"
                gltf_json = json.loads(chunk_data.decode("utf-8"))
            elif chunk_type == 0x004E4942 or chunk_type == 0x204E4942:  # "BIN\0" or "BIN"
                binary_buffers.append(chunk_data)
    else:
        with open(path, "r", encoding="utf-8") as f:
            gltf_json = json.load(f)

        # Load external buffer files if present
        buffers_info = gltf_json.get("buffers", [])
        for b_info in buffers_info:
            uri = b_info.get("uri")
            if uri:
                if uri.startswith("data:application/octet-stream;base64,"):
                    import base64

                    b64_str = uri.split(",", 1)[1]
                    binary_buffers.append(base64.b64decode(b64_str))
                else:
                    buf_path = path.parent / uri
                    if buf_path.exists():
                        binary_buffers.append(buf_path.read_bytes())
                    else:
                        binary_buffers.append(b"")
            else:
                binary_buffers.append(b"")

    buffer_views = gltf_json.get("bufferViews", [])
    accessors = gltf_json.get("accessors", [])

    def get_buffer_data(bv_index: int) -> bytes:
        if bv_index >= len(buffer_views):
            return b""
        bv = buffer_views[bv_index]
        buf_idx = bv.get("buffer", 0)
        byte_offset = bv.get("byteOffset", 0)
        byte_length = bv.get("byteLength", 0)

        if buf_idx < len(binary_buffers):
            buf_bytes = binary_buffers[buf_idx]
            return buf_bytes[byte_offset : byte_offset + byte_length]
        return b""

    all_vertices: List[Tuple[float, float, float]] = []
    all_faces: List[Tuple[int, int, int]] = []

    meshes = gltf_json.get("meshes", [])
    for mesh in meshes:
        for prim in mesh.get("primitives", []):
            attrs = prim.get("attributes", {})
            pos_acc_idx = attrs.get("POSITION")
            if pos_acc_idx is None or pos_acc_idx >= len(accessors):
                continue

            pos_acc = accessors[pos_acc_idx]
            pos_bv_idx = pos_acc.get("bufferView")
            if pos_bv_idx is None:
                continue

            pos_data = get_buffer_data(pos_bv_idx)
            pos_offset = pos_acc.get("byteOffset", 0)
            count = pos_acc.get("count", 0)

            vertex_offset_base = len(all_vertices)

            # Unpack float32 (x, y, z)
            for i in range(count):
                idx_off = pos_offset + i * 12
                if idx_off + 12 <= len(pos_data):
                    vx, vy, vz = struct.unpack_from("<fff", pos_data, idx_off)
                    all_vertices.append((vx, vy, vz))

            # Unpack indices if present
            indices_acc_idx = prim.get("indices")
            if indices_acc_idx is not None and indices_acc_idx < len(accessors):
                ind_acc = accessors[indices_acc_idx]
                ind_bv_idx = ind_acc.get("bufferView")
                if ind_bv_idx is not None:
                    ind_data = get_buffer_data(ind_bv_idx)
                    ind_offset = ind_acc.get("byteOffset", 0)
                    ind_count = ind_acc.get("count", 0)
                    comp_type = ind_acc.get("componentType", 5123)  # 5123 = UNSIGNED_SHORT, 5125 = UNSIGNED_INT

                    raw_indices = []
                    if comp_type == 5123:  # uint16
                        for i in range(ind_count):
                            if ind_offset + i * 2 + 2 <= len(ind_data):
                                idx_val = struct.unpack_from("<H", ind_data, ind_offset + i * 2)[0]
                                raw_indices.append(idx_val)
                    elif comp_type == 5125:  # uint32
                        for i in range(ind_count):
                            if ind_offset + i * 4 + 4 <= len(ind_data):
                                idx_val = struct.unpack_from("<I", ind_data, ind_offset + i * 4)[0]
                                raw_indices.append(idx_val)
                    elif comp_type == 5121:  # uint8
                        for i in range(ind_count):
                            if ind_offset + i < len(ind_data):
                                idx_val = ind_data[ind_offset + i]
                                raw_indices.append(idx_val)

                    for i in range(0, len(raw_indices) - 2, 3):
                        v1 = vertex_offset_base + raw_indices[i] + 1
                        v2 = vertex_offset_base + raw_indices[i + 1] + 1
                        v3 = vertex_offset_base + raw_indices[i + 2] + 1
                        all_faces.append((v1, v2, v3))
            else:
                # Non-indexed triangles
                for i in range(0, count - 2, 3):
                    v1 = vertex_offset_base + i + 1
                    v2 = vertex_offset_base + i + 2
                    v3 = vertex_offset_base + i + 3
                    all_faces.append((v1, v2, v3))

    return all_vertices, all_faces


def parse_mesh_file(
    filepath: Union[str, Path],
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    rotation_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]:
    """
    Parse external 3D mesh asset (.obj, .gltf, .glb) and return scaled/rotated (vertices, 1-based faces).
    """
    path = Path(filepath)
    ext = path.suffix.lower()

    if ext == ".obj":
        raw_verts, faces = parse_obj_file(path)
    elif ext in (".gltf", ".glb"):
        raw_verts, faces = parse_gltf_glb_file(path)
    else:
        raise ValueError(f"Unsupported mesh asset format '{ext}'. Supported formats: .obj, .gltf, .glb")

    transformed_verts = _transform_vertices(raw_verts, scale=scale, rotation_offset=rotation_offset)
    return transformed_verts, faces


def get_mesh_dimensions(
    filepath: Union[str, Path],
    scale: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    rotation_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Optional[Dimensions]:
    """
    Calculate bounding box 3D dimensions (width, depth, height) for a mesh asset.
    """
    try:
        verts, _ = parse_mesh_file(filepath, scale=scale, rotation_offset=rotation_offset)
        if not verts:
            return None

        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        zs = [v[2] for v in verts]

        w = round(max(xs) - min(xs), 3)
        d = round(max(ys) - min(ys), 3)
        h = round(max(zs) - min(zs), 3)

        return Dimensions(
            width=max(w, 0.01),
            depth=max(d, 0.01),
            height=max(h, 0.01),
        )
    except Exception:
        return None
