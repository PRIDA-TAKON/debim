import pytest
from debim.schema import load_manifest, ProjectManifest
from debim.resolver import resolve_manifest, ResolvedSpace
from debim.qto import calculate_qto
from debim.compiler import compile_to_ifc
from pathlib import Path
import tempfile
import ifcopenshell

SAMPLE_SPACE_YAML = """
schema: IFC4-Minimal
project:
  id: PRJ-TEST-SPACE
  name: "Space Verification Model"
  units:
    length: METER
    area: SQUARE_METER
    volume: CUBIC_METER

spatial_structure:
  storeys:
    - id: Ground
      name: "Ground Floor"
      elevation: 0.00
      height: 3.50

grids:
  axes_x:
    A: 0.00
    B: 5.00
    C: 10.00
  axes_y:
    1: 0.00
    2: 4.00
    3: 8.00

materials:
  - id: CONC_240
    name: "Ready-Mixed Concrete"
    category: concrete
    unit_cost_ref: "MAT-CONC-01"

elements:
  # 1. Pure Grid Space
  - class: IfcSpace
    tag: room-living
    name: "Living Room"
    long_name: "Living Room 101"
    room_number: "101"
    height: 3.00
    placement:
      storey: Ground
      boundary:
        - [A, 1]
        - [B, 1]
        - [B, 2]
        - [A, 2]

  # 2. Grid-Offset Expression Space
  - class: IfcSpace
    tag: room-bed
    name: "Master Bedroom"
    long_name: "Bedroom 102"
    room_number: "102"
    height: 2.80
    placement:
      storey: Ground
      boundary:
        - ["B + 0.10", "1 + 0.10"]
        - ["C - 0.10", "1 + 0.10"]
        - ["C - 0.10", "2 - 0.10"]
        - ["B + 0.10", "2 - 0.10"]

  # 3. Explicit Boundary Points Space
  - class: IfcSpace
    tag: room-bath
    name: "Restroom"
    room_number: "103"
    height: 2.60
    placement:
      storey: Ground
      boundary_points:
        - [1.0, 5.0]
        - [3.0, 5.0]
        - [3.0, 7.0]
        - [1.0, 7.0]
"""

def test_ifc_space_resolution_and_qto():
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_SPACE_YAML)
        tmp_path = Path(f.name)

    try:
        manifest = load_manifest(tmp_path)
        assert len(manifest.elements) == 3

        resolved = resolve_manifest(manifest)
        assert len(resolved.spaces) == 3

        # Test Room 1: 5m x 4m = 20m2, air volume = 20 * 3.0 = 60m3
        r1 = resolved.get_element_by_tag("room-living")
        assert isinstance(r1, ResolvedSpace)
        assert r1.net_floor_area == pytest.approx(20.0, rel=0.01)
        assert r1.air_volume == pytest.approx(60.0, rel=0.01)
        assert r1.perimeter == pytest.approx(18.0, rel=0.01)

        # Test Room 2: (5 - 0.2) x (4 - 0.2) = 4.8 x 3.8 = 18.24m2
        r2 = resolved.get_element_by_tag("room-bed")
        assert isinstance(r2, ResolvedSpace)
        assert r2.net_floor_area == pytest.approx(18.24, rel=0.01)
        assert r2.air_volume == pytest.approx(18.24 * 2.80, rel=0.01)

        # Test Room 3: 2m x 2m = 4m2
        r3 = resolved.get_element_by_tag("room-bath")
        assert isinstance(r3, ResolvedSpace)
        assert r3.net_floor_area == pytest.approx(4.0, rel=0.01)
        assert r3.air_volume == pytest.approx(10.40, rel=0.01)

        # Test QTO
        qto = calculate_qto(resolved)
        assert qto.total_spaces_count == 3
        expected_area = 20.0 + 18.24 + 4.0
        assert qto.total_usable_floor_area == pytest.approx(expected_area, rel=0.01)

        # Test IFC Compilation
        ifc_out = tmp_path.with_suffix(".ifc")
        compile_to_ifc(manifest, ifc_out)
        assert ifc_out.exists()

        f_ifc = ifcopenshell.open(str(ifc_out))
        ifc_spaces = f_ifc.by_type("IfcSpace")
        assert len(ifc_spaces) == 3
        tags = {s.Name for s in ifc_spaces}
        # Test IFC Import Roundtrip
        from debim.importer import import_ifc_to_manifest
        reimported = import_ifc_to_manifest(ifc_out)
        reimported_spaces = [e for e in reimported.elements if e.class_ == "IfcSpace"]
        assert len(reimported_spaces) == 3
        reimported_tags = {s.tag for s in reimported_spaces}
        assert "room-living" in reimported_tags
        assert "room-bed" in reimported_tags
        assert "room-bath" in reimported_tags

    finally:
        if tmp_path.exists():
            tmp_path.unlink()
        ifc_file = tmp_path.with_suffix(".ifc")
        if ifc_file.exists():
            ifc_file.unlink()
