"""
Unit tests for IfcSlab native polygon voids and openings, QTO net area calculations, and IFC STEP / IfcOpenShell export.
"""

import pytest
import ifcopenshell
from debim import parse_debim
from debim.schema import ProjectManifest
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.compiler import compile_to_ifc, StepSerializer


SLAB_VOID_MANIFEST_YAML = """
schema: IFC4-Minimal
project:
  id: PROJ-VOID-001
  name: Slab Voids Test Project

spatial_structure:
  storeys:
    - id: STOREY-1
      name: Ground Floor
      elevation: 0.00
      height: 3.50

grids:
  axes_x:
    "1": 0.00
    "2": 4.00
    "3": 8.00
    "4": 12.00
  axes_y:
    "A": 0.00
    "B": 4.00
    "C": 8.00
    "D": 12.00

materials:
  - id: CONCRETE_C30
    name: Reinforced Concrete C30/37
    category: concrete
    unit_cost_ref: CONC-30

elements:
  # Standard slab 12m x 12m = 144 m2 outer area with a 4m x 4m inner void = 16 m2 -> net area = 128 m2
  - class: IfcSlab
    tag: SLAB-VOID-01
    material: CONCRETE_C30
    thickness: 0.20
    placement:
      storey: STOREY-1
      boundary:
        - ["1", "A"]
        - ["4", "A"]
        - ["4", "D"]
        - ["1", "D"]
      voids:
        - - ["2", "B"]
          - ["3", "B"]
          - ["3", "C"]
          - ["2", "C"]

  # Slab with openings definition (rectangular shaft 2m x 3m = 6 m2)
  - class: IfcSlab
    tag: SLAB-OPENING-01
    material: CONCRETE_C30
    thickness: 0.20
    placement:
      storey: STOREY-1
      boundary:
        - ["1", "A"]
        - ["3", "A"]
        - ["3", "C"]
        - ["1", "C"]
      openings:
        - tag: OP-SHAFT
          purpose: MEP_SHAFT
          grid: ["1", "A"]
          offset_x: 1.0
          offset_y: 1.0
          width: 2.0
          length: 3.0
"""


def test_slab_voids_qto_net_area():
    raw = parse_debim(SLAB_VOID_MANIFEST_YAML)
    manifest = ProjectManifest.model_validate(raw)
    resolved = resolve_manifest(manifest)

    slab_void = resolved.get_element_by_tag("SLAB-VOID-01")
    assert slab_void is not None
    # Outer area = 12m x 12m = 144 m2
    # Void area = 4m x 4m = 16 m2
    # Net area = 128 m2
    assert abs(slab_void.area - 128.0) < 1e-4
    assert len(slab_void.voids) == 1

    slab_op = resolved.get_element_by_tag("SLAB-OPENING-01")
    assert slab_op is not None
    # Outer area = 8m x 8m = 64 m2
    # Opening area = 2m x 3m = 6 m2
    # Net area = 58 m2
    assert abs(slab_op.area - 58.0) < 1e-4

    proj_qto = calculate_qto(resolved)

    eqto_void = next(e for e in proj_qto.elements if e.tag == "SLAB-VOID-01")
    # Concrete volume = 128 m2 * 0.20 m = 25.6 m3
    assert abs(eqto_void.concrete_volume - 25.6) < 1e-4


def test_slab_voids_ifc_export(tmp_path):
    raw = parse_debim(SLAB_VOID_MANIFEST_YAML)
    manifest = ProjectManifest.model_validate(raw)
    resolved = resolve_manifest(manifest)
    serializer = StepSerializer()

    # 1. Test STEP string output containing IfcArbitraryProfileDefWithVoids
    step_content = serializer.serialize(resolved)
    assert "IFCARBITRARYPROFILEDEFWITHVOIDS" in step_content.upper()
    assert "SLAB-VOID-01" in step_content

    # 2. Test IfcOpenShell model compilation
    out_file = tmp_path / "model.ifc"
    compile_to_ifc(manifest, out_file, force_fallback=False)
    ifc_model = ifcopenshell.open(str(out_file))
    slabs = ifc_model.by_type("IfcSlab")
    assert len(slabs) == 2

    slab_void_obj = next(s for s in slabs if s.Name == "SLAB-VOID-01")
    shape_rep = slab_void_obj.Representation.Representations[0]
    solid = shape_rep.Items[0]
    prof = solid.SweptArea

    assert prof.is_a("IfcArbitraryProfileDefWithVoids")
    assert len(prof.InnerCurves) == 1
