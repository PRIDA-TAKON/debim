"""
Unit tests for buildingSMART IFC4.3 Civil Earthworks Gabion Basket & Crib Retaining Structures
(IfcEarthworksElement with predefined_type="GABION" or "CRIB_WALL").
Verifies stepped tiered retaining wall spatial resolution, stone rock fill volume arithmetic,
wire mesh cage area, geotextile filter fabric area, QTO calculations, cost estimation,
IFC STEP/IfcOpenShell compilation, and 3D web viewer generation.
"""

from pathlib import Path
import pytest

from debim.compiler import compile_to_ifc
from debim.cost import estimate_cost, generate_cost_template, load_price_catalog
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import IfcEarthworksElement, ProjectManifest
from debim.viewer import generate_viewer_html


def make_gabion_crib_manifest() -> ProjectManifest:
    """Build a manifest with gabion and crib wall retaining elements."""
    elements = [
        # 1. Stepped Tiered Gabion Basket Wall (3 tiers)
        {
            "class": "IfcEarthworksElement",
            "tag": "GABION-WALL-01",
            "predefined_type": "GABION",
            "material": "MAT_GABION_STONE",
            "length": 10.0,
            "height": 3.0,
            "base_thickness": 1.5,
            "step_batter": 0.15,
            "tier_height": 1.0,
            "mesh_wire_dia_mm": 3.0,
            "placement": {
                "storey": "L1",
                "grid": ["1", "A"],
                "offset_x": 0.0,
                "offset_y": 0.0,
                "offset_z": 0.0,
            },
        },
        # 2. Stepped Tiered Crib Retaining Structure (4 tiers)
        {
            "class": "IfcEarthworksElement",
            "tag": "CRIB-WALL-02",
            "predefined_type": "CRIB_WALL",
            "material": "MAT_GABION_STONE",
            "length": 12.0,
            "height": 4.0,
            "base_thickness": 2.0,
            "step_batter": 0.20,
            "tier_height": 1.0,
            "placement": {
                "storey": "L1",
                "grid": ["2", "A"],
                "offset_x": 0.0,
                "offset_y": 0.0,
                "offset_z": 0.0,
            },
        },
    ]

    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {
            "id": "CIVIL-GABION-001",
            "name": "Civil Gabion & Crib Retaining Structure Project",
            "units": {"length": "METER", "area": "SQUARE_METER", "volume": "CUBIC_METER"},
        },
        "spatial_structure": {
            "storeys": [
                {"id": "L1", "name": "Ground Level", "elevation": 0.0, "height": 3.0}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 20.0, "3": 40.0},
            "axes_y": {"A": 0.0, "B": 20.0, "C": 40.0},
        },
        "materials": [
            {
                "id": "MAT_GABION_STONE",
                "name": "Gabion Rock & Stone Fill",
                "category": "earthworks",
                "unit_cost_ref": "EARTH-GABION-STONE",
            },
        ],
        "elements": elements,
    }
    return ProjectManifest.model_validate(manifest_data)


def test_gabion_and_crib_schema_validation():
    manifest = make_gabion_crib_manifest()
    assert len(manifest.elements) == 2

    gabion_elem = manifest.elements[0]
    assert isinstance(gabion_elem, IfcEarthworksElement)
    assert gabion_elem.predefined_type == "GABION"
    assert gabion_elem.length == 10.0
    assert gabion_elem.height == 3.0
    assert gabion_elem.base_thickness == 1.5
    assert gabion_elem.step_batter == 0.15
    assert gabion_elem.mesh_wire_dia_mm == 3.0

    crib_elem = manifest.elements[1]
    assert isinstance(crib_elem, IfcEarthworksElement)
    assert crib_elem.predefined_type == "CRIB_WALL"
    assert crib_elem.length == 12.0
    assert crib_elem.height == 4.0
    assert crib_elem.base_thickness == 2.0
    assert crib_elem.step_batter == 0.20


def test_gabion_stepped_tier_resolution_and_geometry():
    manifest = make_gabion_crib_manifest()
    resolved = resolve_manifest(manifest)

    assert len(resolved.earthworks_elements) == 2
    gw = resolved.earthworks_elements[0]

    # Verify 3 tiers for Gabion Wall (height 3.0 / tier_height 1.0)
    assert len(gw.tiers) == 3

    # Tier 0: W0 = 1.5, L = 10, H = 1.0 -> Vol = 15.0 m3
    # Tier 1: W1 = 1.35, L = 10, H = 1.0 -> Vol = 13.5 m3
    # Tier 2: W2 = 1.20, L = 10, H = 1.0 -> Vol = 12.0 m3
    assert gw.tiers[0]["width"] == pytest.approx(1.50)
    assert gw.tiers[1]["width"] == pytest.approx(1.35)
    assert gw.tiers[2]["width"] == pytest.approx(1.20)

    # Total stone fill volume = 15 + 13.5 + 12 = 40.5 m3
    expected_vol = 15.0 + 13.5 + 12.0
    assert gw.gabion_stone_fill_volume == pytest.approx(expected_vol, rel=1e-3)
    assert gw.volume == pytest.approx(expected_vol, rel=1e-3)

    # Geotextile filter fabric area = L * (H + Base_W) = 10 * (3.0 + 1.5) = 45.0 m2
    assert gw.geotextile_area == pytest.approx(45.0, rel=1e-3)

    # Wire mesh cage area = sum of 2 * (L*W + L*H + W*H) for each tier
    # Tier 0 mesh = 2 * (10*1.5 + 10*1.0 + 1.5*1.0) = 2 * (15 + 10 + 1.5) = 53.0 m2
    # Tier 1 mesh = 2 * (10*1.35 + 10*1.0 + 1.35*1.0) = 2 * (13.5 + 10 + 1.35) = 49.7 m2
    # Tier 2 mesh = 2 * (10*1.20 + 10*1.0 + 1.20*1.0) = 2 * (12 + 10 + 1.20) = 46.4 m2
    # Total mesh = 53.0 + 49.7 + 46.4 = 149.1 m2
    expected_mesh = 53.0 + 49.7 + 46.4
    assert gw.wire_mesh_cage_area == pytest.approx(expected_mesh, rel=1e-3)


def test_crib_wall_stepped_tier_resolution():
    manifest = make_gabion_crib_manifest()
    resolved = resolve_manifest(manifest)

    cw = resolved.earthworks_elements[1]

    # Verify 4 tiers for Crib Wall (height 4.0 / tier_height 1.0)
    assert len(cw.tiers) == 4

    # Tier 0: W0 = 2.0, L = 12, H = 1.0 -> Vol = 24.0 m3
    # Tier 1: W1 = 1.8, L = 12, H = 1.0 -> Vol = 21.6 m3
    # Tier 2: W2 = 1.6, L = 12, H = 1.0 -> Vol = 19.2 m3
    # Tier 3: W3 = 1.4, L = 12, H = 1.0 -> Vol = 16.8 m3
    # Total stone fill volume = 24 + 21.6 + 19.2 + 16.8 = 81.6 m3
    expected_vol = 24.0 + 21.6 + 19.2 + 16.8
    assert cw.gabion_stone_fill_volume == pytest.approx(expected_vol, rel=1e-3)

    # Geotextile area = 12 * (4.0 + 2.0) = 72.0 m2
    assert cw.geotextile_area == pytest.approx(72.0, rel=1e-3)


def test_gabion_qto_and_cost_estimation(tmp_path: Path):
    manifest = make_gabion_crib_manifest()
    qto = calculate_qto(manifest)

    # Total stone fill volume: 40.5 (gabion) + 81.6 (crib) = 122.1 m3
    assert qto.total_gabion_stone_fill_volume == pytest.approx(122.1, rel=1e-3)
    # Total wire mesh area: 149.1 m2
    assert qto.total_wire_mesh_cage_area == pytest.approx(149.1, rel=1e-3)
    # Total geotextile area: 45.0 + 72.0 = 117.0 m2
    assert qto.total_geotextile_area == pytest.approx(117.0, rel=1e-3)

    # Cost Estimation
    template_path = generate_cost_template(manifest, tmp_path / "prices.yaml")
    catalog = load_price_catalog(template_path)

    if "EARTH-GABION-STONE" in catalog.items:
        catalog.items["EARTH-GABION-STONE"].material_cost = 450.0
    if "EARTH-WIRE-MESH-CAGE" in catalog.items:
        catalog.items["EARTH-WIRE-MESH-CAGE"].material_cost = 180.0
    if "EARTH-GEOTEXTILE-FABRIC" in catalog.items:
        catalog.items["EARTH-GEOTEXTILE-FABRIC"].material_cost = 65.0

    cost = estimate_cost(qto, catalog, manifest)
    assert cost.grand_total > 0
    item_codes = [li.code for li in cost.line_items]
    assert "EARTH-GABION-STONE" in item_codes
    assert "EARTH-WIRE-MESH-CAGE" in item_codes
    assert "EARTH-GEOTEXTILE-FABRIC" in item_codes


def test_gabion_ifc_compilation(tmp_path: Path):
    manifest = make_gabion_crib_manifest()

    # StepSerializer export
    step_out = tmp_path / "gabion_wall_fallback.ifc"
    step_path = compile_to_ifc(manifest, step_out, force_fallback=True)
    assert step_path.exists()
    content = step_path.read_text(encoding="utf-8")
    assert "GABION-WALL-01" in content
    assert "CRIB-WALL-02" in content

    # IfcOpenShell export
    ifc_out = tmp_path / "gabion_wall.ifc"
    ifc_path = compile_to_ifc(manifest, ifc_out)
    assert ifc_path.exists()


def test_gabion_viewer_html_generation():
    manifest = make_gabion_crib_manifest()
    html = generate_viewer_html(manifest)

    assert "IfcEarthworksElement" in html
    assert "GABION-WALL-01" in html
    assert "GABION-WALL-01-Tier-1" in html
    assert "GABION-WALL-01-Tier-2" in html
    assert "GABION-WALL-01-Tier-3" in html
    assert "CRIB-WALL-02-Tier-1" in html
