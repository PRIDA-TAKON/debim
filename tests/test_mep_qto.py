"""
Unit & Integration Tests for MEP Pipe Length Aggregation, Fitting Take-Offs, and BOQ Reporting.
"""

from pathlib import Path
import pytest

from debim.cost import PriceCatalog, PriceItem, estimate_cost, generate_cost_template
from debim.qto import calculate_qto
from debim.schema import ProjectManifest


@pytest.fixture
def mep_qto_manifest_data():
    return {
        "schema": "IFC4-Minimal",
        "project": {"id": "PRJ-MEP-QTO-TEST", "name": "MEP QTO & BOQ Test Building"},
        "spatial_structure": {
            "storeys": [
                {"id": "STOREY-1", "name": "Ground Level", "elevation": 0.0, "height": 3.5}
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 4.0, "3": 8.0},
            "axes_y": {"A": 0.0, "B": 4.0, "C": 8.0},
        },
        "materials": [
            {"id": "MAT_PPR", "name": "PPR Pipe Material", "category": "mep", "unit_cost_ref": "MEP-PIPE-PPR-25"},
            {"id": "MAT_PVC", "name": "PVC Pipe Material", "category": "mep", "unit_cost_ref": "MEP-PIPE-PVC-100"},
        ],
        "elements": [
            {
                "class": "IfcSanitaryTerminal",
                "tag": "SAN_BASIN_1",
                "terminal_type": "LAVATORY",
                "placement": {"grid": ["1", "B"], "storey": "STOREY-1", "offset_z": 0.8},
            },
            {
                "class": "IfcSanitaryTerminal",
                "tag": "SAN_WC_1",
                "terminal_type": "WATER_CLOSET",
                "placement": {"grid": ["2", "B"], "storey": "STOREY-1", "offset_z": 0.4},
            },
            {
                "class": "IfcElectricDistributionBoard",
                "tag": "DB_1",
                "board_type": "CONSUMER_UNIT",
                "placement": {"grid": ["1", "A"], "storey": "STOREY-1", "offset_z": 1.8},
            },
            {
                "class": "IfcBuildingElementProxy",
                "tag": "JB_1",
                "ifc_class": "IfcJunctionBox",
                "placement": {"grid": ["2", "A"], "storey": "STOREY-1", "offset_z": 2.8},
            },
            {
                "class": "IfcLightFixture",
                "tag": "LIGHT_1",
                "fixture_type": "DOWNLIGHT",
                "power_watts": 15.0,
                "placement": {"grid": ["3", "A"], "storey": "STOREY-1", "offset_z": 2.8},
            },
            {
                "class": "IfcLightFixture",
                "tag": "LIGHT_2",
                "fixture_type": "DOWNLIGHT",
                "power_watts": 15.0,
                "placement": {"grid": ["2", "C"], "storey": "STOREY-1", "offset_z": 2.8},
            },
        ],
        "mep_systems": [
            # 1. Cold Water Supply System (PPR):
            # Main pipe has an elbow bend at waypoint (4.0, 0.0, 2.5), plus 3-way Tee branching to BASIN and WC
            {
                "id": "SYS_CW",
                "system_type": "DOMESTIC_COLD_WATER",
                "material": "PPR",
                "main_pipe": {
                    "tag": "PIPE_CW_MAIN",
                    "from": {"grid": ["1", "A"], "storey": "STOREY-1", "offset": [0.0, 0.0, 2.5]},
                    "to": {"grid": ["2", "B"], "storey": "STOREY-1", "offset": [0.0, 0.0, 2.5]},
                    "diameter": 0.025,
                },
                "branches": [
                    {
                        "tag": "BRANCH_CW_BASIN",
                        "branch_from": "PIPE_CW_MAIN",
                        "target_fixture": "SAN_BASIN_1",
                        "diameter": 0.015,
                        "auto_reducer": True,
                    },
                    {
                        "tag": "BRANCH_CW_WC",
                        "branch_from": "PIPE_CW_MAIN",
                        "target_fixture": "SAN_WC_1",
                        "diameter": 0.015,
                        "auto_reducer": True,
                    },
                ],
            },
            # 2. Sanitary Drainage System (PVC):
            # Collector main pipe discharge with Sanitary Wye branch from WC
            {
                "id": "SYS_SOIL_WASTE",
                "system_type": "SANITARY_DRAINAGE",
                "material": "PVC_CLASS_8.5",
                "collector_pipe": {
                    "tag": "PIPE_SOIL_MAIN",
                    "discharge_to": "RISER_STACK_01",
                    "from": {"grid": ["1", "B"], "storey": "STOREY-1", "offset": [0.0, 0.0, 0.5]},
                    "to": {"grid": ["3", "B"], "storey": "STOREY-1", "offset": [0.0, 0.0, 0.4]},
                    "slope": 0.01,
                    "diameter": 0.100,
                },
                "gather_fixtures": [
                    {
                        "fixture": "SAN_WC_1",
                        "branch_diameter": 0.050,
                    }
                ],
            },
            # 3. Electrical Conduit System with Junction Box
            {
                "id": "SYS_CONDUIT_LIGHTING",
                "system_type": "ELECTRICAL_CONDUIT",
                "material": "WHITE_UPVC",
                "home_run": {
                    "from_panel": "DB_1",
                    "to_junction_box": "JB_1",
                    "diameter": 0.020,
                },
                "distribution": {
                    "junction_box": "JB_1",
                    "drops": [
                        {"to_element": "LIGHT_1", "diameter": 0.020},
                        {"to_element": "LIGHT_2", "diameter": 0.020},
                    ],
                },
            },
        ],
    }


def test_mep_pipe_lengths_aggregation(mep_qto_manifest_data):
    """Test aggregation of pipe lengths categorized by material and nominal diameter."""
    manifest = ProjectManifest.model_validate(mep_qto_manifest_data)
    qto = calculate_qto(manifest)

    # Verify overall cold water and drainage pipe totals
    assert qto.total_cold_water_pipe_length > 0.0
    assert qto.total_soil_pipe_length > 0.0 or qto.total_drainage_pipe_length > 0.0 or qto.total_waste_pipe_length > 0.0

    # Verify categorized pipe lengths dictionary
    pipe_dict = qto.pipe_lengths_by_material_diameter
    assert len(pipe_dict) >= 2, "Expected multiple material:diameter pipe categories"

    # Check PPR 25mm (0.025m) and 15mm (0.015m) pipes
    ppr_25_key = [k for k in pipe_dict if "PPR" in k and "0.025" in k]
    ppr_15_key = [k for k in pipe_dict if "PPR" in k and "0.015" in k]
    assert len(ppr_25_key) == 1
    assert len(ppr_15_key) == 1
    assert pipe_dict[ppr_25_key[0]] > 0.0
    assert pipe_dict[ppr_15_key[0]] > 0.0

    # Check PVC 100mm (0.100m) pipe
    pvc_100_key = [k for k in pipe_dict if "PVC" in k and ("0.1" in k or "0.100" in k)]
    assert len(pvc_100_key) >= 1
    assert pipe_dict[pvc_100_key[0]] > 0.0


def test_mep_auto_fittings_counts(mep_qto_manifest_data):
    """Test auto-generated fitting counts for Elbows, Tees, Reducers, Wyes, and Junction Boxes."""
    manifest = ProjectManifest.model_validate(mep_qto_manifest_data)
    qto = calculate_qto(manifest)

    # Check total pipe and conduit fittings counts
    assert qto.total_pipe_fittings_count >= 3
    assert qto.total_conduit_fittings_count >= 1

    # Check breakdown of auto-generated fittings
    assert qto.total_elbows_count >= 1, f"Expected at least 1 Elbow, got {qto.total_elbows_count}"
    assert qto.total_tees_count >= 1, f"Expected at least 1 Tee, got {qto.total_tees_count}"
    assert qto.total_reducers_count >= 1, f"Expected at least 1 Concentric Reducer, got {qto.total_reducers_count}"
    assert qto.total_wyes_count >= 1, f"Expected at least 1 Sanitary Wye 45°, got {qto.total_wyes_count}"
    assert qto.total_junction_boxes_count >= 1, f"Expected at least 1 Junction Box, got {qto.total_junction_boxes_count}"

    # Verify fittings_by_type dictionary
    fit_map = qto.mep_fittings_by_type
    assert "ELBOW" in fit_map
    assert "TEE" in fit_map
    assert "CONCENTRIC_REDUCER" in fit_map
    assert "SANITARY_WYE_45" in fit_map
    assert "JUNCTION_BOX" in fit_map


def test_mep_boq_pr4_reporting(mep_qto_manifest_data, tmp_path):
    """Test cost estimation and Thai CGD/วสท. BOQ ปร.4 sheet generation for MEP items."""
    manifest = ProjectManifest.model_validate(mep_qto_manifest_data)
    qto = calculate_qto(manifest)

    # 1. Generate cost template catalog
    tmpl_path = tmp_path / "prices.yaml"
    generate_cost_template(manifest, output_path=tmpl_path)
    assert tmpl_path.exists()

    # 2. Construct catalog with prices for pipes and fittings
    catalog = PriceCatalog(
        currency="THB",
        items={
            "MEP-PIPE-PPR-25": PriceItem(name="PPR Pipe Ø 25mm (1\")", unit="m", material_cost=85.0, labor_cost=35.0),
            "MEP-PIPE-PPR-15": PriceItem(name="PPR Pipe Ø 15mm (1/2\")", unit="m", material_cost=55.0, labor_cost=25.0),
            "MEP-PIPE-PVC_CLASS_8.5-100": PriceItem(name="PVC Soil Pipe Ø 100mm (4\")", unit="m", material_cost=120.0, labor_cost=40.0),
            "MEP-FITTING-ELBOW": PriceItem(name="Pipe Fitting Elbow 90°", unit="set", material_cost=25.0, labor_cost=15.0),
            "MEP-FITTING-TEE": PriceItem(name="Pipe Fitting Tee", unit="set", material_cost=35.0, labor_cost=20.0),
            "MEP-FITTING-REDUCER": PriceItem(name="Pipe Fitting Concentric Reducer", unit="set", material_cost=30.0, labor_cost=18.0),
            "MEP-FITTING-WYE": PriceItem(name="Sanitary Wye 45°", unit="set", material_cost=65.0, labor_cost=30.0),
            "MEP-JUNCTION-BOX": PriceItem(name="Conduit Junction Box 2x4", unit="set", material_cost=45.0, labor_cost=25.0),
            "SAN-TOILET": PriceItem(name="Water Closet Set", unit="set", material_cost=3500.0, labor_cost=800.0),
            "SAN-BASIN": PriceItem(name="Lavatory Basin Set", unit="set", material_cost=2200.0, labor_cost=600.0),
        },
    )

    # 3. Estimate cost
    cost_estimate = estimate_cost(qto, catalog, manifest=manifest)
    assert cost_estimate.grand_total > 0.0

    # 4. Generate BOQ ปร.4 sheet
    pr4 = cost_estimate.generate_pr4(project_name="โครงการทดสอบระบบสุขาภิบาลและไฟฟ้า")
    assert len(pr4.items) >= 5, "Expected BOQ ปร.4 to contain pipe and fitting items"

    descriptions = [item.description for item in pr4.items]
    codes = [item.code for item in pr4.items]

    # Verify specific pipe and fitting descriptions exist in BOQ ปร.4
    assert any("MEP-PIPE-PPR" in c for c in codes)
    assert any("MEP-FITTING-ELBOW" in c for c in codes)
    assert any("MEP-FITTING-TEE" in c for c in codes)
    assert any("MEP-FITTING-REDUCER" in c for c in codes)
    assert any("MEP-FITTING-WYE" in c for c in codes)
    assert any("MEP-JUNCTION-BOX" in c for c in codes)

    # Check quantities matching 3D model
    elbow_item = next(item for item in pr4.items if item.code == "MEP-FITTING-ELBOW")
    assert elbow_item.quantity == float(qto.total_elbows_count)
    assert elbow_item.total_amount == float(qto.total_elbows_count) * (25.0 + 15.0)

    wye_item = next(item for item in pr4.items if item.code == "MEP-FITTING-WYE")
    assert wye_item.quantity == float(qto.total_wyes_count)
    assert wye_item.total_amount == float(qto.total_wyes_count) * (65.0 + 30.0)
