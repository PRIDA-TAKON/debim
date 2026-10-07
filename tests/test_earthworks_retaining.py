"""
Unit tests for Earthworks & Retaining Structures
(IfcEarthworksCut, IfcEarthworksFill, IfcRetainingWall).
"""

from pathlib import Path
import pytest
from pydantic import ValidationError

from debim.compiler import compile_to_ifc
from debim.cost import estimate_cost, generate_cost_template, load_price_catalog
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    EarthworksPlacement,
    IfcEarthworksCut,
    IfcEarthworksFill,
    IfcRetainingWall,
    ProjectManifest,
    RetainingWallPlacement,
    RetainingWallReinforcement,
)
from debim.viewer import generate_viewer_html


def make_sample_manifest() -> ProjectManifest:
    """Helper fixture building a project manifest with civil earthworks and retaining wall elements."""
    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {
            "id": "CIVIL-001",
            "name": "Civil Ground & Retaining Structure Project",
            "units": {"length": "METER", "area": "SQUARE_METER", "volume": "CUBIC_METER"},
        },
        "spatial_structure": {
            "storeys": [
                {"id": "L1", "name": "Ground Level", "elevation": 0.0, "height": 3.0}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 10.0, "3": 20.0},
            "axes_y": {"A": 0.0, "B": 10.0, "C": 20.0},
        },
        "materials": [
            {"id": "MAT_SOIL_CUT", "name": "Natural Ground Earth Cut", "category": "earthworks", "unit_cost_ref": "EARTH-CUT-EXCAVATION"},
            {"id": "MAT_SOIL_FILL", "name": "Engineered Compacted Soil Fill", "category": "earthworks", "unit_cost_ref": "EARTH-FILL-COMPACTED"},
            {"id": "MAT_CONC_RETAINING", "name": "Reinforced Concrete 280 ksc", "category": "concrete", "unit_cost_ref": "RC-RETAINING-WALL"},
        ],
        "elements": [
            {
                "class": "IfcEarthworksCut",
                "tag": "CUT-PIT-01",
                "predefined_type": "BASEMENT_EXCAVATION",
                "material": "MAT_SOIL_CUT",
                "depth": 2.50,
                "placement": {
                    "storey": "L1",
                    "boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]],
                    "offset_z": 0.0,
                },
            },
            {
                "class": "IfcEarthworksFill",
                "tag": "FILL-EMBANK-01",
                "predefined_type": "EMBANKMENT",
                "material": "MAT_SOIL_FILL",
                "material_type": "gravel",
                "compaction_ratio": 0.92,
                "depth": 1.50,
                "placement": {
                    "storey": "L1",
                    "boundary": [["2", "A"], ["3", "A"], ["3", "B"], ["2", "B"]],
                    "offset_z": 0.0,
                },
            },
            {
                "class": "IfcRetainingWall",
                "tag": "RW-WALL-01",
                "predefined_type": "CANTILEVER_WALL",
                "material": "MAT_CONC_RETAINING",
                "length": 10.0,
                "stem_height": 3.50,
                "stem_thickness": 0.35,
                "footing_base_width": 2.20,
                "toe_length": 0.70,
                "heel_length": 1.15,
                "footing_thickness": 0.45,
                "placement": {
                    "storey": "L1",
                    "from_grid": ["1", "A"],
                    "to_grid": ["2", "A"],
                    "offset_z": 0.0,
                },
                "reinforcement": {
                    "stem_main": "DB16 @ 0.15m",
                    "stem_distribution": "DB12 @ 0.20m",
                    "footing_mesh": "DB16 @ 0.15m",
                },
            },
        ],
    }
    return ProjectManifest.model_validate(manifest_data)


def test_earthworks_and_retaining_wall_schema_validation():
    manifest = make_sample_manifest()
    assert len(manifest.elements) == 3

    cut_elem = manifest.elements[0]
    assert isinstance(cut_elem, IfcEarthworksCut)
    assert cut_elem.tag == "CUT-PIT-01"
    assert cut_elem.predefined_type == "BASEMENT_EXCAVATION"
    assert cut_elem.depth == 2.50

    fill_elem = manifest.elements[1]
    assert isinstance(fill_elem, IfcEarthworksFill)
    assert fill_elem.tag == "FILL-EMBANK-01"
    assert fill_elem.compaction_ratio == 0.92

    rw_elem = manifest.elements[2]
    assert isinstance(rw_elem, IfcRetainingWall)
    assert rw_elem.tag == "RW-WALL-01"
    assert rw_elem.stem_height == 3.50


def test_schema_invalid_reference():
    manifest = make_sample_manifest()
    # Test invalid storey
    invalid_data = manifest.model_dump(by_alias=True)
    invalid_data["elements"][0]["placement"]["storey"] = "NON_EXISTENT"
    with pytest.raises(ValidationError):
        ProjectManifest.model_validate(invalid_data)


def test_spatial_resolution():
    manifest = make_sample_manifest()
    resolved = resolve_manifest(manifest)

    assert len(resolved.earthworks_cuts) == 1
    assert len(resolved.earthworks_fills) == 1
    assert len(resolved.retaining_walls) == 1

    cut = resolved.earthworks_cuts[0]
    assert cut.tag == "CUT-PIT-01"
    assert cut.footprint_area == pytest.approx(100.0, rel=1e-3)
    assert cut.cut_volume == pytest.approx(250.0, rel=1e-3)
    assert cut.layer == "civil/earthworks/cut"

    fill = resolved.earthworks_fills[0]
    assert fill.tag == "FILL-EMBANK-01"
    assert fill.surface_area == pytest.approx(100.0, rel=1e-3)
    assert fill.fill_volume == pytest.approx(150.0, rel=1e-3)
    assert fill.compacted_volume == pytest.approx(150.0 * 0.92, rel=1e-3)
    assert fill.layer == "civil/earthworks/fill"

    rw = resolved.retaining_walls[0]
    assert rw.tag == "RW-WALL-01"
    assert rw.length == pytest.approx(10.0, rel=1e-3)
    # Stem volume: 0.35 * 3.50 * 10 = 12.25 m3
    # Footing volume: 2.20 * 0.45 * 10 = 9.9 m3
    # Total conc vol: 22.15 m3
    assert rw.concrete_volume == pytest.approx(22.15, rel=1e-3)
    assert rw.formwork_area > 0
    assert rw.layer == "civil/structures/retaining_walls"


def test_qto_and_cost_estimation(tmp_path: Path):
    manifest = make_sample_manifest()
    qto = calculate_qto(manifest)

    assert qto.total_cut_volume == pytest.approx(250.0, rel=1e-3)
    assert qto.total_fill_volume == pytest.approx(150.0, rel=1e-3)
    assert qto.total_compacted_fill_volume == pytest.approx(138.0, rel=1e-3)
    assert qto.total_retaining_wall_concrete_volume == pytest.approx(22.15, rel=1e-3)
    assert qto.total_retaining_wall_formwork_area > 0

    # Generate price catalog template
    template_path = generate_cost_template(manifest, tmp_path / "prices.template.yaml")
    catalog = load_price_catalog(template_path)

    # Set costs
    catalog.items["EARTH-CUT-EXCAVATION"].material_cost = 120.0
    catalog.items["EARTH-FILL-COMPACTED"].material_cost = 250.0
    catalog.items["RC-RETAINING-WALL"].material_cost = 2400.0

    cost = estimate_cost(qto, catalog, manifest)
    assert cost.grand_total > 0
    assert len(cost.line_items) >= 3

    csv_out = tmp_path / "cost_breakdown.csv"
    cost.export_csv(csv_out)
    assert csv_out.exists()


def test_ifc_compilation(tmp_path: Path):
    manifest = make_sample_manifest()

    # StepSerializer fallback compilation
    step_path = compile_to_ifc(manifest, tmp_path / "model_fallback.ifc", force_fallback=True)
    assert step_path.exists()
    content = step_path.read_text(encoding="utf-8")
    assert "IFCGEOGRAPHICELEMENT" in content
    assert "CUT-PIT-01" in content
    assert "FILL-EMBANK-01" in content
    assert "RW-WALL-01" in content

    # Standard / IfcOpenShell compilation
    ifc_path = compile_to_ifc(manifest, tmp_path / "model.ifc")
    assert ifc_path.exists()


def test_viewer_generation():
    manifest = make_sample_manifest()
    html = generate_viewer_html(manifest)

    assert "IfcEarthworksCut" in html
    assert "CUT-PIT-01" in html
    assert "IfcEarthworksFill" in html
    assert "FILL-EMBANK-01" in html
    assert "IfcRetainingWall" in html
    assert "RW-WALL-01" in html
    assert "civil/earthworks/cut" in html
    assert "civil/structures/retaining_walls" in html
