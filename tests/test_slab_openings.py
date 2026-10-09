"""
Tests for Slab Openings & Voids (Shafts, Pipes, Stairs, Elevators).
"""

from pathlib import Path
import pytest

from debim.schema import IfcSlab, SlabPlacement, SlabOpening, load_manifest
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.compiler import compile_to_ifc


def test_slab_openings_offset_shaft(tmp_path):
    project_yaml = """
schema: IFC4-Minimal
project:
  id: PRJ-SLAB-OPENINGS
  name: "Slab Openings Test"
  units: { length: METER, area: SQUARE_METER, volume: CUBIC_METER }
spatial_structure:
  storeys:
    - id: L1
      name: "Ground Floor"
      elevation: 0.0
      height: 3.5
grids:
  axes_x: { "1": 0.0, "2": 4.0 }
  axes_y: { "A": 0.0, "B": 5.0 }
materials:
  - id: CONC_240
    name: "Concrete 240 ksc"
    category: concrete
    unit_cost_ref: "C240"
elements:
  - class: IfcSlab
    tag: "S-01"
    material: CONC_240
    thickness: 0.15
    placement:
      boundary: [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]]
      storey: L1
      openings:
        - tag: "MEP-SHAFT-01"
          purpose: "MEP_SHAFT"
          grid: ["1", "A"]
          offset_x: 0.50
          offset_y: 0.50
          width: 1.00
          length: 2.00
"""
    p_file = tmp_path / "project.yaml"
    p_file.write_text(project_yaml, encoding="utf-8")

    manifest = load_manifest(p_file)
    assert len(manifest.elements) == 1
    s = manifest.elements[0]
    assert s.placement.openings is not None
    assert len(s.placement.openings) == 1
    op = s.placement.openings[0]
    assert op.width == 1.00
    assert op.length == 2.00

    resolved = resolve_manifest(manifest)
    r_slabs = [e for e in resolved.elements if getattr(e, "tag", "") == "S-01"]
    assert len(r_slabs) == 1
    r_slab = r_slabs[0]

    # Gross area: 4.0 * 5.0 = 20.0 m2
    # Shaft area: 1.0 * 2.0 = 2.0 m2
    # Net area should be exactly 18.0 m2
    assert pytest.approx(r_slab.area, 1e-3) == 18.0
    assert len(r_slab.voids) == 1

    # Check QTO
    qto = calculate_qto(resolved)
    eqto = qto.get_element("S-01")
    assert eqto is not None
    # Concrete volume: 18.0 m2 * 0.15 m = 2.70 m3
    assert pytest.approx(eqto.concrete_volume, 1e-3) == 2.70

    # Check IFC compilation
    out_ifc = tmp_path / "model.ifc"
    compile_to_ifc(resolved, str(out_ifc))
    assert out_ifc.exists()
