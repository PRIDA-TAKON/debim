import math
import pytest
import ifcopenshell
from debim.schema import ProjectManifest, Storey, Grids, IfcMarinePart, MarinePartPlacement
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.compiler import StepSerializer, compile_to_ifc


def create_sample_manifest():
    return ProjectManifest.model_validate({
        "project": {"id": "PROJ-MARINE-01", "name": "Coastal Defense Project"},
        "spatial_structure": {
            "storeys": [
                {"id": "GL", "name": "Ground Level", "elevation": 0.0, "height": 3.5}
            ]
        },
        "grids": {
            "axes_x": {"A": 0.0, "B": 100.0},
            "axes_y": {"1": 0.0, "2": 50.0},
        },
        "materials": [
            {"id": "ROCK", "name": "Riprap Rock Armor", "category": "CIVIL", "unit_cost_ref": "ROCK-01"},
            {"id": "CONCRETE", "name": "Precast Concrete Armor Units", "category": "CIVIL", "unit_cost_ref": "CONC-01"},
        ],
        "elements": [
            {
                "class": "IfcMarinePart",
                "tag": "BW-01",
                "predefined_type": "BREAKWATER",
                "material": "ROCK",
                "crest_width": 4.0,
                "crest_elevation": 3.0,
                "base_width": 13.0,
                "slope_ratio": 1.5,
                "armor_type": "ROCK",
                "armor_thickness": 1.0,
                "length": 100.0,
                "start_position": [0.0, 0.0, 0.0],
                "end_position": [100.0, 0.0, 0.0],
                "placement": {"storey": "GL"},
            },
            {
                "class": "IfcMarinePart",
                "tag": "SW-01",
                "predefined_type": "SEAWALL",
                "material": "CONCRETE",
                "crest_width": 3.0,
                "crest_elevation": 4.0,
                "slope_ratio": 1.0,
                "armor_type": "TETRAPOD",
                "armor_thickness": 1.2,
                "length": 50.0,
                "placement": {
                    "storey": "GL",
                    "from_grid": ["A", "1"],
                    "to_grid": ["A", "2"],
                },
            },
            {
                "class": "IfcMarinePart",
                "tag": "REV-01",
                "predefined_type": "REVETMENT",
                "material": "ROCK",
                "crest_width": 2.0,
                "crest_elevation": 2.5,
                "slope_ratio": 2.0,
                "armor_type": "CONCRETE_ACCROPODE",
                "armor_thickness": 0.8,
                "length": 80.0,
                "placement": {
                    "storey": "GL",
                    "grid": ["A", "1"],
                    "offset_x": 10.0,
                    "offset_y": 5.0,
                },
            },
        ]
    })


def test_marine_part_schema_and_defaults():
    mp = IfcMarinePart(
        tag="BW-TEST",
        predefined_type="BREAKWATER",
        crest_width=5.0,
        crest_elevation=4.0,
        slope_ratio=1.5,
    )
    assert mp.tag == "BW-TEST"
    assert mp.predefined_type == "BREAKWATER"
    assert mp.crest_width == 5.0
    assert mp.crest_elevation == 4.0
    assert mp.slope_ratio == 1.5
    assert mp.armor_type == "ROCK"
    assert mp.armor_thickness == 1.0


def test_spatial_resolver_trapezoidal_slicing_and_volumes():
    manifest = create_sample_manifest()
    resolved = resolve_manifest(manifest)

    assert len(resolved.marine_parts) == 3
    bw = next(m for m in resolved.marine_parts if m.tag == "BW-01")

    # Verify calculated geometry
    assert bw.crest_width == 4.0
    assert bw.crest_elevation == 3.0
    assert bw.base_width == 13.0
    assert bw.length == 100.0

    # Verify profile polygon coordinates
    # Polygon: [(-13/2, 0), (13/2, 0), (4/2, 3), (-4/2, 3)]
    assert bw.profile_polygon == [(-6.5, 0.0), (6.5, 0.0), (2.0, 3.0), (-2.0, 3.0)]

    # Verify total volume
    expected_total_area = (4.0 + 13.0) / 2.0 * 3.0 # 25.5 m2
    expected_total_vol = expected_total_area * 100.0 # 2550.0 m3
    assert math.isclose(bw.total_volume, expected_total_vol, rel_tol=1e-5)

    # Core vs Armor Volume
    assert bw.core_volume < bw.total_volume
    assert bw.armor_volume > 0.0
    assert math.isclose(bw.core_volume + bw.armor_volume, bw.total_volume, rel_tol=1e-5)

    # Rock Armor Weight in Metric Tons
    expected_weight = bw.armor_volume * 2.65
    assert math.isclose(bw.armor_weight_tons, expected_weight, rel_tol=1e-5)


def test_marine_part_qto_calculations():
    manifest = create_sample_manifest()
    resolved = resolve_manifest(manifest)

    proj_qto = calculate_qto(resolved)

    assert proj_qto.total_marine_embankment_volume > 0.0
    assert proj_qto.total_marine_core_volume > 0.0
    assert proj_qto.total_marine_armor_volume > 0.0
    assert proj_qto.total_marine_armor_weight_tons > 0.0

    bw_qto = next(e for e in proj_qto.elements if e.tag == "BW-01").marine_part
    assert bw_qto is not None
    assert bw_qto.crest_width == 4.0
    assert bw_qto.crest_elevation == 3.0
    assert bw_qto.base_width == 13.0
    assert bw_qto.total_volume == 2550.0


def test_marine_part_ifc_compilation():
    manifest = create_sample_manifest()
    resolved = resolve_manifest(manifest)

    # 1. Pure Python StepSerializer compilation
    serializer = StepSerializer()
    step_content = serializer.serialize(resolved)
    assert "IFCMARINEPART" in step_content or "IFCBUILDINGELEMENTPROXY" in step_content
    assert "IFCARBITRARYCLOSEDPROFILEDEF" in step_content
    assert "BW-01" in step_content

    # 2. IfcOpenShell compilation
    ifc_file_path = compile_to_ifc(manifest)
    ifc_model = ifcopenshell.open(str(ifc_file_path))
    try:
        marine_parts = ifc_model.by_type("IfcMarinePart")
    except Exception:
        marine_parts = ifc_model.by_type("IfcBuildingElementProxy")
    tags = [p.Name for p in marine_parts]
    assert "BW-01" in tags
    assert "SW-01" in tags
    assert "REV-01" in tags

    # Verify geometry creation with IfcOpenShell geom engine
    for mp in marine_parts:
        shape = ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(), mp)
        assert shape is not None
        assert len(shape.geometry.verts) > 0
