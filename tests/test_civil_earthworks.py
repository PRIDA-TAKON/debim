"""
Comprehensive unit tests for buildingSMART IFC4.3 Civil Earthworks & Geotechnical entities
(IfcEarthworksElement, IfcEarthworksCut, IfcEarthworksFill, IfcSoil, IfcGeotechnicalStratum).
Verifies cut/fill volume arithmetic, spatial resolution, QTO calculations, cost estimation,
IFC STEP serialization, and 3D web viewer generation.
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
    IfcEarthworksElement,
    IfcEarthworksFill,
    IfcGeotechnicalStratum,
    IfcSoil,
    ProjectManifest,
)
from debim.viewer import generate_viewer_html


def make_civil_earthworks_manifest() -> ProjectManifest:
    """Build a project manifest with ~20 civil earthworks & geotechnical elements."""
    elements = []

    # 1-5: Earthworks Cut elements (EXCAVATION, CUT, CUTTING, TRENCH, BASEMENT_EXCAVATION)
    cut_types = [
        ("CUT-EXCAV-01", "EXCAVATION", 3.0, [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]]),  # 10x10x3 = 300 m3
        ("CUT-PIT-02", "CUT", 2.0, [["2", "A"], ["3", "A"], ["3", "B"], ["2", "B"]]),          # 10x10x2 = 200 m3
        ("CUT-HILL-03", "CUTTING", 1.5, [["1", "B"], ["2", "B"], ["2", "C"], ["1", "C"]]),      # 10x10x1.5 = 150 m3
        ("CUT-TRENCH-04", "TRENCH", 1.2, [["2", "B"], ["3", "B"], ["3", "C"], ["2", "C"]]),     # 10x10x1.2 = 120 m3
        ("CUT-BASE-05", "BASEMENT_EXCAVATION", 4.0, [["1", "C"], ["2", "C"], ["2", "D"], ["1", "D"]]), # 10x10x4 = 400 m3
    ]
    for tag, ptype, depth, bnd in cut_types:
        elements.append({
            "class": "IfcEarthworksCut",
            "tag": tag,
            "predefined_type": ptype,
            "material": "MAT_SOIL_CUT",
            "depth": depth,
            "placement": {
                "storey": "L1",
                "boundary": bnd,
                "offset_z": 0.0,
            },
        })

    # 6-10: Earthworks Fill elements (EMBANKMENT, BACKFILL, BERM, SLOPE_FILL, SUBGRADE)
    fill_types = [
        ("FILL-EMBANK-01", "EMBANKMENT", "soil", 0.95, 2.0, [["3", "A"], ["4", "A"], ["4", "B"], ["3", "B"]]), # 10x10x2 = 200 m3, compacted=190
        ("FILL-BACK-02", "BACKFILL", "gravel", 0.90, 1.0, [["3", "B"], ["4", "B"], ["4", "C"], ["3", "C"]]),   # 10x10x1 = 100 m3, compacted=90
        ("FILL-BERM-03", "BERM", "soil", 0.92, 1.5, [["3", "C"], ["4", "C"], ["4", "D"], ["3", "D"]]),        # 10x10x1.5 = 150 m3, compacted=138
        ("FILL-SLOPE-04", "SLOPE_FILL", "sand", 0.88, 1.2, [["2", "C"], ["3", "C"], ["3", "D"], ["2", "D"]]), # 10x10x1.2 = 120 m3, compacted=105.6
        ("FILL-SUB-05", "SUBGRADE", "crushed_rock", 0.98, 0.5, [["1", "D"], ["2", "D"], ["2", "E"], ["1", "E"]]), # 10x10x0.5 = 50 m3, compacted=49
    ]
    for tag, ptype, mtype, comp, depth, bnd in fill_types:
        elements.append({
            "class": "IfcEarthworksFill",
            "tag": tag,
            "predefined_type": ptype,
            "material": "MAT_SOIL_FILL",
            "material_type": mtype,
            "compaction_ratio": comp,
            "depth": depth,
            "placement": {
                "storey": "L1",
                "boundary": bnd,
                "offset_z": 0.0,
            },
        })

    # 11-14: General Earthworks Elements (RETAINING_STRUCTURE, BERM, GABION, REINFORCED_SOIL)
    ew_elems = [
        ("EW-RETAIN-01", "RETAINING_STRUCTURE", 1.8, [["4", "A"], ["5", "A"], ["5", "B"], ["4", "B"]]), # 100 * 1.8 = 180 m3
        ("EW-BERM-02", "BERM", 2.2, [["4", "B"], ["5", "B"], ["5", "C"], ["4", "C"]]),                 # 100 * 2.2 = 220 m3
        ("EW-GABION-03", "GABION", 1.0, [["4", "C"], ["5", "C"], ["5", "D"], ["4", "D"]]),               # 100 * 1.0 = 100 m3
        ("EW-SOIL-04", "REINFORCED_SOIL", 2.5, [["4", "D"], ["5", "D"], ["5", "E"], ["4", "E"]]),        # 100 * 2.5 = 250 m3
    ]
    for tag, ptype, depth, bnd in ew_elems:
        elements.append({
            "class": "IfcEarthworksElement",
            "tag": tag,
            "predefined_type": ptype,
            "material": "MAT_SOIL_FILL",
            "depth": depth,
            "placement": {
                "storey": "L1",
                "boundary": bnd,
                "offset_z": 0.0,
            },
        })

    # 15-17: Geotechnical Strata (SOLID, SOIL, ROCK)
    strata = [
        ("STRAT-CLAY-01", "SOLID", "clay", 3.0, [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]]),    # 100 * 3.0 = 300 m3
        ("STRAT-SAND-02", "SOIL", "sand", 2.5, [["2", "A"], ["3", "A"], ["3", "B"], ["2", "B"]]),     # 100 * 2.5 = 250 m3
        ("STRAT-ROCK-03", "ROCK", "rock", 5.0, [["3", "A"], ["4", "A"], ["4", "B"], ["3", "B"]]),     # 100 * 5.0 = 500 m3
    ]
    for tag, ptype, stype, thk, bnd in strata:
        elements.append({
            "class": "IfcGeotechnicalStratum",
            "tag": tag,
            "predefined_type": ptype,
            "soil_type": stype,
            "thickness": thk,
            "material": "MAT_SOIL_CUT",
            "placement": {
                "storey": "L1",
                "boundary": bnd,
                "offset_z": -thk,
            },
        })

    # 18-20: Soil Layers (topsoil, clay, gravel)
    soils = [
        ("SOIL-TOP-01", "topsoil", 1600.0, 0.30, [["1", "A"], ["3", "A"], ["3", "C"], ["1", "C"]]),   # 400 m2 * 0.3m = 120 m3
        ("SOIL-CLAY-02", "clay", 1850.0, 1.50, [["3", "A"], ["5", "A"], ["5", "C"], ["3", "C"]]),     # 400 m2 * 1.5m = 600 m3
        ("SOIL-GRAVEL-03", "gravel", 2100.0, 0.80, [["1", "C"], ["5", "C"], ["5", "E"], ["1", "E"]]), # 800 m2 * 0.8m = 640 m3
    ]
    for tag, stype, dens, thk, bnd in soils:
        elements.append({
            "class": "IfcSoil",
            "tag": tag,
            "soil_type": stype,
            "density_kg_m3": dens,
            "thickness": thk,
            "material": "MAT_SOIL_CUT",
            "placement": {
                "storey": "L1",
                "boundary": bnd,
                "offset_z": -thk,
            },
        })

    manifest_data = {
        "schema": "IFC4-Minimal",
        "project": {
            "id": "CIVIL-EARTH-001",
            "name": "Comprehensive Civil Earthworks & Cut/Fill Project",
            "units": {"length": "METER", "area": "SQUARE_METER", "volume": "CUBIC_METER"},
        },
        "spatial_structure": {
            "storeys": [
                {"id": "L1", "name": "Ground Level", "elevation": 0.0, "height": 3.0}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 10.0, "3": 20.0, "4": 30.0, "5": 40.0},
            "axes_y": {"A": 0.0, "B": 10.0, "C": 20.0, "D": 30.0, "E": 40.0},
        },
        "materials": [
            {"id": "MAT_SOIL_CUT", "name": "Excavated Natural Ground", "category": "earthworks", "unit_cost_ref": "EARTH-CUT-EXCAVATION"},
            {"id": "MAT_SOIL_FILL", "name": "Compacted Earth Fill", "category": "earthworks", "unit_cost_ref": "EARTH-FILL-COMPACTED"},
        ],
        "elements": elements,
    }
    return ProjectManifest.model_validate(manifest_data)


def test_civil_earthworks_schema_and_element_counts():
    manifest = make_civil_earthworks_manifest()
    assert len(manifest.elements) == 20

    cuts = [e for e in manifest.elements if isinstance(e, IfcEarthworksCut)]
    fills = [e for e in manifest.elements if isinstance(e, IfcEarthworksFill)]
    ew_elems = [e for e in manifest.elements if isinstance(e, IfcEarthworksElement)]
    strata = [e for e in manifest.elements if isinstance(e, IfcGeotechnicalStratum)]
    soils = [e for e in manifest.elements if isinstance(e, IfcSoil)]

    assert len(cuts) == 5
    assert len(fills) == 5
    assert len(ew_elems) == 4
    assert len(strata) == 3
    assert len(soils) == 3


def test_spatial_resolution_and_volume_arithmetic():
    manifest = make_civil_earthworks_manifest()
    resolved = resolve_manifest(manifest)

    assert len(resolved.earthworks_cuts) == 5
    assert len(resolved.earthworks_fills) == 5
    assert len(resolved.earthworks_elements) == 4
    assert len(resolved.geotechnical_strata) == 3
    assert len(resolved.soils) == 3

    # Cut volumes sum: 300 + 200 + 150 + 120 + 400 = 1170 m3
    total_cut = sum(c.cut_volume for c in resolved.earthworks_cuts)
    assert total_cut == pytest.approx(1170.0, rel=1e-3)

    # Fill baseline volumes sum: 200 + 100 + 150 + 120 + 50 = 620 m3
    total_fill = sum(f.fill_volume for f in resolved.earthworks_fills)
    assert total_fill == pytest.approx(620.0, rel=1e-3)

    # Fill compacted volumes sum: 190 + 90 + 138 + 105.6 + 49 = 572.6 m3
    total_compacted = sum(f.compacted_volume for f in resolved.earthworks_fills)
    assert total_compacted == pytest.approx(572.6, rel=1e-3)

    # Earthworks elements volumes: 180 + 220 + 100 + 250 = 750 m3
    total_ew_vol = sum(e.volume for e in resolved.earthworks_elements)
    assert total_ew_vol == pytest.approx(750.0, rel=1e-3)

    # Strata volumes: 300 + 250 + 500 = 1050 m3
    total_strata_vol = sum(s.volume for s in resolved.geotechnical_strata)
    assert total_strata_vol == pytest.approx(1050.0, rel=1e-3)

    # Soil volumes: 120 + 600 + 640 = 1360 m3
    total_soil_vol = sum(s.volume for s in resolved.soils)
    assert total_soil_vol == pytest.approx(1360.0, rel=1e-3)


def test_qto_calculation():
    manifest = make_civil_earthworks_manifest()
    qto = calculate_qto(manifest)

    # Earthworks Cut QTO total includes Cuts
    assert qto.total_cut_volume == pytest.approx(1170.0, rel=1e-3)
    # Earthworks Fill QTO total includes Fills, EarthworksElements, Strata & Soil: 620 + 750 + 1050 + 1360 = 3780.0
    assert qto.total_fill_volume == pytest.approx(3780.0, rel=1e-3)
    assert qto.total_compacted_fill_volume == pytest.approx(572.6, rel=1e-3)


def test_cost_estimation(tmp_path: Path):
    manifest = make_civil_earthworks_manifest()
    qto = calculate_qto(manifest)

    template_path = generate_cost_template(manifest, tmp_path / "prices.yaml")
    catalog = load_price_catalog(template_path)

    # Assign unit costs
    if "EARTH-CUT-EXCAVATION" in catalog.items:
        catalog.items["EARTH-CUT-EXCAVATION"].material_cost = 150.0
    if "EARTH-FILL-COMPACTED" in catalog.items:
        catalog.items["EARTH-FILL-COMPACTED"].material_cost = 280.0

    cost = estimate_cost(qto, catalog, manifest)
    assert cost.grand_total > 0
    assert len(cost.line_items) >= 2


def test_ifc_compilation(tmp_path: Path):
    manifest = make_civil_earthworks_manifest()

    # StepSerializer fallback export
    step_out = tmp_path / "civil_earthworks_fallback.ifc"
    step_path = compile_to_ifc(manifest, step_out, force_fallback=True)
    assert step_path.exists()
    content = step_path.read_text(encoding="utf-8")
    assert "IFCGEOGRAPHICELEMENT" in content
    assert "CUT-EXCAV-01" in content
    assert "FILL-EMBANK-01" in content
    assert "EW-RETAIN-01" in content
    assert "STRAT-CLAY-01" in content
    assert "SOIL-TOP-01" in content

    # IfcOpenShell export
    ifc_out = tmp_path / "civil_earthworks.ifc"
    ifc_path = compile_to_ifc(manifest, ifc_out)
    assert ifc_path.exists()


def test_viewer_html_generation():
    manifest = make_civil_earthworks_manifest()
    html = generate_viewer_html(manifest)

    assert "IfcEarthworksCut" in html
    assert "IfcEarthworksFill" in html
    assert "IfcEarthworksElement" in html
    assert "IfcGeotechnicalStratum" in html
    assert "IfcSoil" in html
    assert "CUT-EXCAV-01" in html
    assert "FILL-EMBANK-01" in html
    assert "EW-RETAIN-01" in html
    assert "STRAT-CLAY-01" in html
    assert "SOIL-TOP-01" in html
