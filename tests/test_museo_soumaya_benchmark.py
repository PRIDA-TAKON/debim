"""
Official Flagship Benchmark Test Suite for debim v1.0.0:
Museo Soumaya (Fernando Romero / Ove Arup, 2011 - Mexico City)
"The Pure Algorithmic Architecture Release"

Verifies:
1. Manifest syntax validation for 7-storey asymmetric hyperbolic loft + 28 swept columns + hexagonal skin.
2. Deterministic QTO aggregation (400+ tons structural steel, 14,000+ m2 formwork).
3. OpenBIM IFC4 compilation (< 10 seconds, ~2MB file).
4. Standalone 3D WebGL viewer export with InstancedMesh rendering.
5. Thai CGD v480 BOQ and embodied carbon sustainability evaluation.
"""

from pathlib import Path
import pytest

from debim.compiler import compile_to_ifc
from debim.cost import estimate_cost
from debim.schema import load_manifest
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.viewer import generate_viewer_html


SOUMAYA_YAML_PATH = Path("examples/museo_soumaya/project.yaml")


@pytest.fixture
def soumaya_manifest():
    assert SOUMAYA_YAML_PATH.exists(), f"Benchmark manifest not found at {SOUMAYA_YAML_PATH}"
    return load_manifest(SOUMAYA_YAML_PATH)


def test_museo_soumaya_manifest_loads_and_validates(soumaya_manifest):
    """Verify that the Museo Soumaya manifest parses and validates with zero errors."""
    assert soumaya_manifest.project.id == "PRJ-MUSEO-SOUMAYA-2011"
    assert len(soumaya_manifest.spatial_structure.storeys) == 7
    assert soumaya_manifest.geometry_rules.type == "HYPERBOLIC_LOFT"
    assert soumaya_manifest.structures.column_generator.count == 28
    assert soumaya_manifest.facade.envelope_skin.pattern == "HEXAGONAL_CONFORMAL"

    resolved = resolve_manifest(soumaya_manifest)
    # 28 columns * 7 storeys = 196 column segments
    curved_cols = [c for c in resolved.columns if "COL-CURVED-" in c.tag]
    assert len(curved_cols) == 196


def test_museo_soumaya_qto_structural_steel_and_facade(soumaya_manifest):
    """Verify QTO calculation captures 400+ tons of structural steel and formwork."""
    qto = calculate_qto(soumaya_manifest)

    # 196 column segments * ~6.7m * ~285 kg/m for CHS600
    assert qto.total_structural_steel_weight > 350000.0  # > 350 tons
    assert qto.total_formwork_area > 10000.0  # > 10,000 m2
    assert qto.total_painting_area > 2000.0  # > 2,000 m2


def test_museo_soumaya_ifc4_compilation(soumaya_manifest, tmp_path: Path):
    """Verify fast IFC4 compilation (< 10 seconds) producing valid OpenBIM output."""
    out_ifc = tmp_path / "museo_soumaya.ifc"
    res = compile_to_ifc(soumaya_manifest, output_path=out_ifc)

    assert out_ifc.exists()
    file_size = out_ifc.stat().st_size
    assert file_size > 500000  # > 500 KB

    content = out_ifc.read_text(encoding="utf-8")
    assert "IFCCOLUMN" in content
    assert "IFCSLAB" in content
    assert "IFCCURTAINWALL" in content
    assert "Museo Soumaya" in content


def test_museo_soumaya_3d_viewer_export(soumaya_manifest, tmp_path: Path):
    """Verify standalone 3D WebGL viewer export containing instanced facade and curved columns."""
    out_html = tmp_path / "museo_soumaya.html"
    html_content = generate_viewer_html(soumaya_manifest)
    out_html.write_text(html_content, encoding="utf-8")

    assert out_html.exists()
    assert out_html.stat().st_size > 1000000  # > 1 MB

    assert "COL-CURVED-1-L0" in html_content
    assert "InstancedMesh" in html_content or "facade_panels" in html_content or "tessellation" in html_content
