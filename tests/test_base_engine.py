"""
Unit tests for Issue #118: Base Engine & Dynamic IFC Entity Coverage & Fallback.
Tests dynamic entity compilation, 3D shape generation, bSDD Pset validation, and universal bounding box fallbacks.
"""

from pathlib import Path
import pytest
import ifcopenshell
import ifcopenshell.geom

from debim.bsdd import validate_manifest_psets, PropertyValidationStatus
from debim.compiler import compile_to_ifc
from debim.resolver import resolve_manifest
from debim.schema import (
    IfcBuildingElementProxy,
    ProjectManifest,
    ProxyGeometry,
    ProxyPlacement,
    load_manifest,
)


def test_dynamic_ifc_entity_compilation(tmp_path: Path):
    """Test compiling dynamic IFC classes (e.g. IfcPump, IfcBoiler, IfcSensor) with valid 3D shapes."""
    manifest_yaml = """
schema: IFC4-Minimal
project:
  id: PROJ-DYNAMIC-118
  name: Dynamic IFC Entity Test
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
  - tag: PUMP-01
    class: IfcPump
    predefined_type: CIRCULATOR
    material: MAT-STEEL
    geometry:
      box: [0.8, 0.6, 0.5]
    placement:
      storey: L1
      grid: [A, "1"]
    properties:
      Pset_PumpTypeCommon:
        FlowRate: 15.5
  - tag: BOILER-01
    class: IfcBoiler
    material: MAT-STEEL
    geometry:
      box: [1.2, 1.0, 1.8]
    placement:
      storey: L1
      grid: [A, "1"]
    properties:
      Pset_BoilerTypeCommon:
        NominalCapacity: 120.0
        EnergySource: GAS
  - tag: SENSOR-01
    class: IfcSensor
    material: MAT-STEEL
    geometry:
      box: [0.2, 0.2, 0.3]
    placement:
      storey: L1
      grid: [A, "1"]
"""
    m_file = tmp_path / "project.yaml"
    out_ifc = tmp_path / "output.ifc"
    m_file.write_text(manifest_yaml, encoding="utf-8")

    manifest = load_manifest(m_file)
    resolved = resolve_manifest(manifest)

    # 1. Test bSDD Pset Validation
    results = validate_manifest_psets(manifest)
    valid_results = [r for r in results if r.status == PropertyValidationStatus.VALID]
    assert len(valid_results) >= 3

    # 2. Test IFC Compilation
    compile_to_ifc(resolved, out_ifc, force_fallback=False)
    assert out_ifc.exists()

    ifc_f = ifcopenshell.open(str(out_ifc))
    pumps = ifc_f.by_type("IfcPump")
    boilers = ifc_f.by_type("IfcBoiler")
    sensors = ifc_f.by_type("IfcSensor")

    assert len(pumps) == 1
    assert len(boilers) == 1
    assert len(sensors) == 1

    # 3. Test 3D Shape Creation Parity
    settings = ifcopenshell.geom.settings()
    for elem in [pumps[0], boilers[0], sensors[0]]:
        shape = ifcopenshell.geom.create_shape(settings, elem)
        assert shape is not None
        assert len(shape.geometry.verts) > 0


def test_step_serializer_dynamic_fallback(tmp_path: Path):
    """Test StepSerializer fallback handling for dynamic entity classes."""
    manifest_yaml = """
schema: IFC4-Minimal
project:
  id: PROJ-STEP-118
  name: STEP Fallback Test
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
  - tag: FAN-01
    class: IfcFan
    geometry:
      box: [0.5, 0.5, 0.6]
    placement:
      storey: L1
      grid: [A, "1"]
"""
    m_file = tmp_path / "project.yaml"
    out_ifc = tmp_path / "output_fallback.ifc"
    m_file.write_text(manifest_yaml, encoding="utf-8")

    manifest = load_manifest(m_file)
    resolved = resolve_manifest(manifest)

    compile_to_ifc(resolved, out_ifc, force_fallback=True)
    assert out_ifc.exists()
    content = out_ifc.read_text(encoding="utf-8")
    assert "FAN-01" in content
    assert "IFCFAN" in content or "IFCBUILDINGELEMENTPROXY" in content
