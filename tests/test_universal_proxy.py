"""
Unit tests for Universal Declarative Proxy Engine (IfcBuildingElementProxy and dynamic IFC entity mapping).
"""

from pathlib import Path
import pytest
import yaml

from debim.compiler import compile_to_ifc
from debim.cost import estimate_cost, load_price_catalog
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Dimensions,
    IfcBuildingElementProxy,
    ProjectManifest,
    ProxyGeometry,
    ProxyPlacement,
    load_manifest,
)
from debim.viewer import generate_viewer_html


def test_proxy_model_and_geometry():
    p_box = IfcBuildingElementProxy(
        tag="CHILLER-01",
        class_="IfcChiller",
        predefined_type="WATERCOOLED",
        geometry=ProxyGeometry(box=[3.2, 1.8, 2.0]),
        placement=ProxyPlacement(
            storey="L1",
            grid=("A", "1"),
            offset=(0.5, 0.0, 0.1),
        ),
        properties={
            "Pset_ChillerTypeCommon": {
                "NominalCapacity": "500kW",
                "RefrigerantClass": "R134a",
            }
        },
    )

    assert p_box.tag == "CHILLER-01"
    assert p_box.ifc_class == "IfcChiller"
    assert p_box.predefined_type == "WATERCOOLED"
    dims = p_box.get_resolved_dimensions()
    assert dims.width == 3.2
    assert dims.depth == 1.8
    assert dims.height == 2.0
    assert p_box.properties["Pset_ChillerTypeCommon"]["NominalCapacity"] == "500kW"


def test_proxy_cylinder_geometry():
    p_cyl = IfcBuildingElementProxy(
        tag="SOLAR-01",
        class_="IfcSolarDevice",
        geometry=ProxyGeometry(cylinder=[0.6, 1.5]),
        placement=ProxyPlacement(storey="L1"),
    )
    dims = p_cyl.get_resolved_dimensions()
    assert dims.width == 1.2
    assert dims.depth == 1.2
    assert dims.height == 1.5


def test_proxy_yaml_manifest_loading(tmp_path: Path):
    manifest_yaml = """
schema: IFC4-Minimal
project:
  id: PROJ-PROXY-01
  name: Proxy Test Project
  units:
    length: METER
spatial_structure:
  storeys:
    - id: L1
      name: Level 1
      elevation: 0.0
      height: 3.5
grids:
  axes_x:
    A: 0.0
    B: 5.0
  axes_y:
    "1": 0.0
    "2": 5.0
materials:
  - id: MAT-EQ
    name: Equipment Steel
    category: steel
    unit_cost_ref: MAT-EQUIPMENT
proxies:
  - tag: CHILLER-01
    class: IfcChiller
    predefined_type: WATERCOOLED
    material: MAT-EQ
    geometry:
      box: [3.2, 1.8, 2.0]
    placement:
      storey: L1
      grid: [A, "1"]
      offset: [0.5, 1.0, 0.2]
    properties:
      Pset_ChillerTypeCommon:
        NominalCapacity: 500kW
        RefrigerantClass: R134a
elements:
  - tag: COMPRESSOR-01
    class: IfcCompressor
    material: MAT-EQ
    geometry:
      box: [1.5, 1.0, 1.2]
    placement:
      storey: L1
      grid: [B, "2"]
"""
    m_file = tmp_path / "project.yaml"
    m_file.write_text(manifest_yaml, encoding="utf-8")

    manifest = load_manifest(m_file)
    assert len(manifest.proxies) == 1
    assert len(manifest.elements) == 1

    p1 = manifest.proxies[0]
    assert p1.tag == "CHILLER-01"
    assert p1.ifc_class == "IfcChiller"

    p2 = manifest.elements[0]
    assert isinstance(p2, IfcBuildingElementProxy)
    assert p2.tag == "COMPRESSOR-01"
    assert p2.ifc_class == "IfcCompressor"


def test_proxy_resolver_and_qto(tmp_path: Path):
    manifest_yaml = """
schema: IFC4-Minimal
project:
  id: PROJ-PROXY-02
  name: Proxy Resolver Test
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
elements:
  - tag: INTERCEPTOR-01
    class: IfcInterceptor
    material: MAT-STEEL
    geometry:
      box: [2.0, 2.0, 1.5]
    placement:
      storey: L1
      grid: [A, "1"]
"""
    m_file = tmp_path / "project.yaml"
    m_file.write_text(manifest_yaml, encoding="utf-8")

    manifest = load_manifest(m_file)
    resolved = resolve_manifest(manifest)

    assert len(resolved.proxies) == 1
    rp = resolved.proxies[0]
    assert rp.tag == "INTERCEPTOR-01"
    assert rp.ifc_class == "IfcInterceptor"
    assert rp.layer == "equipment/ifcinterceptor"
    assert rp.position == (0.0, 0.0, 0.0)
    assert rp.bounding_box["volume"] == pytest.approx(6.0)
    assert rp.bounding_box["footprint_area"] == pytest.approx(4.0)

    qto = calculate_qto(resolved)
    assert qto.total_proxies_count == 1
    assert qto.total_proxies_volume == pytest.approx(6.0)
    assert qto.total_proxies_footprint_area == pytest.approx(4.0)

    elem_qto = [item for item in qto.elements if item.tag == "INTERCEPTOR-01"][0]
    assert elem_qto.element_class == "IfcInterceptor"
    assert elem_qto.concrete_volume == pytest.approx(6.0)


def test_proxy_cost_estimation(tmp_path: Path):
    manifest_yaml = """
schema: IFC4-Minimal
project:
  id: PROJ-PROXY-COST
  name: Proxy Cost Test
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
elements:
  - tag: CHILLER-01
    class: IfcChiller
    material: MAT-STEEL
    geometry:
      box: [2.0, 1.0, 1.0]
    placement:
      storey: L1
      grid: [A, "1"]
"""
    prices_yaml = """
currency: THB
catalog_version: "2025.1"
items:
  IfcChiller:
    name: Industrial Water Chiller
    description: Industrial Water Chiller
    unit: SET
    material_cost: 250000.0
"""
    m_file = tmp_path / "project.yaml"
    p_file = tmp_path / "prices.yaml"
    m_file.write_text(manifest_yaml, encoding="utf-8")
    p_file.write_text(prices_yaml, encoding="utf-8")

    manifest = load_manifest(m_file)
    resolved = resolve_manifest(manifest)
    qto = calculate_qto(resolved)
    catalog = load_price_catalog(p_file)
    cost = estimate_cost(qto, catalog)

    assert cost.grand_total == 250000.0
    assert len(cost.line_items) == 1
    assert cost.line_items[0].name == "Industrial Water Chiller"


def test_proxy_ifc_compilation(tmp_path: Path):
    manifest_yaml = """
schema: IFC4-Minimal
project:
  id: PROJ-PROXY-IFC
  name: Proxy IFC Test
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
elements:
  - tag: CHILLER-01
    class: IfcChiller
    predefined_type: WATERCOOLED
    material: MAT-STEEL
    geometry:
      box: [3.0, 1.5, 2.0]
    placement:
      storey: L1
      grid: [A, "1"]
    properties:
      Pset_ChillerTypeCommon:
        NominalCapacity: 500kW
        RefrigerantClass: R134a
"""
    m_file = tmp_path / "project.yaml"
    out_ifc = tmp_path / "output.ifc"
    m_file.write_text(manifest_yaml, encoding="utf-8")

    manifest = load_manifest(m_file)
    resolved = resolve_manifest(manifest)
    compile_to_ifc(resolved, out_ifc, force_fallback=True)

    assert out_ifc.exists()
    content = out_ifc.read_text(encoding="utf-8")

    assert "CHILLER-01" in content
    assert "IFCCHILLER" in content or "IFCBUILDINGELEMENTPROXY" in content
    assert "Pset_ChillerTypeCommon" in content
    assert "NominalCapacity" in content
    assert "500kW" in content


def test_proxy_viewer_generation(tmp_path: Path):
    manifest_yaml = """
schema: IFC4-Minimal
project:
  id: PROJ-PROXY-VIEWER
  name: Proxy Viewer Test
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
elements:
  - tag: BURNER-01
    class: IfcBurner
    material: MAT-STEEL
    geometry:
      box: [1.2, 0.8, 1.0]
    placement:
      storey: L1
      grid: [A, "1"]
    properties:
      Pset_BurnerTypeCommon:
        EnergySource: GAS
"""
    m_file = tmp_path / "project.yaml"
    m_file.write_text(manifest_yaml, encoding="utf-8")

    manifest = load_manifest(m_file)
    resolved = resolve_manifest(manifest)
    html = generate_viewer_html(resolved)

    assert "BURNER-01" in html
    assert "IfcBurner" in html
    assert "Pset_BurnerTypeCommon" in html
    assert "EnergySource" in html
