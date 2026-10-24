"""
tests.test_scan_compiler

Tests for declarative .debim manifest compilation from point cloud scans
and IFC4 physical file rendering.
"""

from pathlib import Path
import numpy as np
import pytest
import yaml

from debim.scan.calibrator import save_ply
from debim.scan.compiler import compile_scan_to_manifest, scan_ingest
from debim.schema import ProjectManifest, load_manifest
from debim.compiler import compile_to_ifc
from debim.cli import main


@pytest.fixture
def synthetic_room_ply(tmp_path):
    """
    Generates a 3D point cloud PLY file for a 6.0m x 4.0m room (2.8m high) with:
    - Floor plane at Z = 0.0m
    - Ceiling plane at Z = 2.80m
    - Wall 1: X in [0, 6], Y=0, Z in [0, 2.8] with Door void at X in [1.0, 2.0], Z in [0, 2.0]
    - Wall 2: X in [0, 6], Y=4, Z in [0, 2.8] with Window void at X in [2.5, 4.0], Z in [0.8, 2.0]
    - Wall 3: X=0, Y in [0, 4], Z in [0, 2.8] solid
    - Wall 4: X=6, Y in [0, 4], Z in [0, 2.8] solid
    """
    rng = np.random.default_rng(2025)
    pts = []

    # 1. Floor points at Z = 0.0
    for x in np.linspace(0, 6.0, 60):
        for y in np.linspace(0, 4.0, 40):
            pts.append([x, y, float(rng.normal(0.0, 0.005))])

    # 2. Ceiling points at Z = 2.80
    for x in np.linspace(0, 6.0, 60):
        for y in np.linspace(0, 4.0, 40):
            pts.append([x, y, float(2.80 + rng.normal(0.0, 0.005))])

    # 3. Wall 1 along Y=0.0 (X in [0, 6]) with Door void (X in [1.0, 2.0], Z in [0, 2.0])
    for x in np.linspace(0, 6.0, 120):
        for z in np.linspace(0, 2.80, 50):
            is_door_void = (1.0 <= x <= 2.0) and (0.0 <= z < 2.0)
            if not is_door_void:
                y = float(rng.normal(0.0, 0.005))
                pts.append([x, y, z])

    # 4. Wall 2 along Y=4.0 (X in [0, 6]) with Window void (X in [2.5, 4.0], Z in [0.8, 2.0])
    for x in np.linspace(0, 6.0, 120):
        for z in np.linspace(0, 2.80, 50):
            is_window_void = (2.5 <= x <= 4.0) and (0.8 <= z < 2.0)
            if not is_window_void:
                y = float(4.0 + rng.normal(0.0, 0.005))
                pts.append([x, y, z])

    # 5. Wall 3 along X=0.0 (Y in [0, 4])
    for y in np.linspace(0, 4.0, 80):
        for z in np.linspace(0, 2.80, 50):
            x = float(rng.normal(0.0, 0.005))
            pts.append([x, y, z])

    # 6. Wall 4 along X=6.0 (Y in [0, 4])
    for y in np.linspace(0, 4.0, 80):
        for z in np.linspace(0, 2.80, 50):
            x = float(6.0 + rng.normal(0.0, 0.005))
            pts.append([x, y, z])

    pts_arr = np.array(pts, dtype=np.float64)

    # Save to binary PLY
    ply_path = tmp_path / "room_scan.ply"
    save_ply(ply_path, pts_arr, binary=True)
    return ply_path


def test_compile_scan_to_manifest(synthetic_room_ply, tmp_path):
    output_yaml = tmp_path / "project.yaml"

    manifest = compile_scan_to_manifest(
        synthetic_room_ply,
        output_path=output_yaml,
        project_id="PRJ-SCAN-TEST",
        project_name="Synthetic Scan Room",
    )

    # Verify manifest structure
    assert isinstance(manifest, ProjectManifest)
    assert manifest.project.id == "PRJ-SCAN-TEST"
    assert manifest.project.name == "Synthetic Scan Room"

    # Verify storey elevation and height
    assert len(manifest.spatial_structure.storeys) == 1
    st = manifest.spatial_structure.storeys[0]
    assert st.id == "STOREY-1"
    assert np.isclose(st.elevation, 0.0, atol=0.10)
    assert np.isclose(st.height, 2.80, atol=0.15)

    # Verify grids
    assert len(manifest.grids.axes_x) >= 2
    assert len(manifest.grids.axes_y) >= 2

    # Verify elements (walls extracted)
    assert len(manifest.elements) >= 3

    # Collect all doors and windows across wall children
    all_doors = []
    all_windows = []
    for elem in manifest.elements:
        if getattr(elem, "class_", "") == "IfcWall":
            for child in elem.children:
                if child.class_ == "IfcDoor":
                    all_doors.append(child)
                elif child.class_ == "IfcWindow":
                    all_windows.append(child)

    assert len(all_doors) >= 1
    assert len(all_windows) >= 1

    # Verify output YAML file
    assert output_yaml.exists()
    content = output_yaml.read_text(encoding="utf-8")
    assert "Point Cloud Scan Ingested Manifest" in content

    # Verify YAML loads with load_manifest
    reloaded = load_manifest(output_yaml)
    assert isinstance(reloaded, ProjectManifest)
    assert len(reloaded.elements) == len(manifest.elements)


def test_compile_scan_manifest_to_ifc4(synthetic_room_ply, tmp_path):
    output_yaml = tmp_path / "project.yaml"
    output_ifc = tmp_path / "model.ifc"

    # 1. Compile scan to manifest YAML
    compile_scan_to_manifest(
        synthetic_room_ply,
        output_path=output_yaml,
    )

    # 2. Render compiled YAML to IFC4 physical file
    ifc_path = compile_to_ifc(output_yaml, output_path=output_ifc)

    assert ifc_path.exists()
    assert ifc_path.stat().st_size > 500

    ifc_content = ifc_path.read_text(encoding="utf-8", errors="ignore")
    assert "IFCPROJECT" in ifc_content
    assert "IFCBUILDINGSTOREY" in ifc_content
    assert "IFCWALL" in ifc_content
    assert "IFCDOOR" in ifc_content or "IFCWINDOW" in ifc_content


def test_cli_scan_ingest(synthetic_room_ply, tmp_path):
    out_yaml = tmp_path / "scan_project.yaml"

    # Invoke CLI main
    main(["scan", "ingest", str(synthetic_room_ply), "-o", str(out_yaml)])

    assert out_yaml.exists()

    # Load emitted manifest
    manifest = load_manifest(out_yaml)
    assert isinstance(manifest, ProjectManifest)
    assert len(manifest.elements) >= 3


def test_scan_ingest_helper_function(synthetic_room_ply, tmp_path):
    out_yaml = tmp_path / "auto_project.yaml"

    res_path = scan_ingest(synthetic_room_ply, output_path=out_yaml)

    assert res_path.exists()
    assert res_path == out_yaml.resolve()

    manifest = load_manifest(res_path)
    assert isinstance(manifest, ProjectManifest)
