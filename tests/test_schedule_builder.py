"""
Unit tests for debim.schedule.builder activity and milestone extractor.
"""

from pathlib import Path
import pytest
import yaml

from debim.loader import load_manifest
from debim.qto import calculate_qto
from debim.schedule.builder import extract_activities_from_manifest
from debim.schedule.schema import CrashingManifest, load_schedule_yaml


FARNSWORTH_PATH = Path("examples/farnsworth_house/project.debim")


def test_extract_activities_farnsworth_house():
    """Test activity and milestone extraction on Farnsworth House model."""
    assert FARNSWORTH_PATH.exists()

    # Test passing file path directly
    manifest = extract_activities_from_manifest(FARNSWORTH_PATH)

    assert isinstance(manifest, CrashingManifest)
    assert "FARNSWORTH" in manifest.project_id.upper()
    assert len(manifest.activities) > 0
    assert len(manifest.milestones) > 0

    # Validate milestones payment percentage sum
    total_payment = sum(ms.payment_percent for ms in manifest.milestones)
    assert abs(total_payment - 100.0) < 1e-5

    # Collect all activity IDs
    act_ids = {a.id for a in manifest.activities}

    # Verify every activity meets bounds constraints
    for act in manifest.activities:
        assert act.normal_duration >= 0
        assert act.crash_duration >= 0
        assert act.crash_duration <= act.normal_duration
        assert act.normal_cost >= 0.0
        assert act.crash_cost >= 0.0
        assert act.cost_weight == act.normal_cost
        assert act.status == "NOT_STARTED"
        assert act.progress_percent == 0.0
        assert act.progress_log == []

        # Ensure all predecessor IDs exist in the activity set
        for pred in act.predecessors:
            assert pred in act_ids, f"Predecessor '{pred}' for activity '{act.id}' not found in activity IDs"

    # Verify that every milestone's required_activities exist in act_ids
    for ms in manifest.milestones:
        assert ms.payment_percent > 0.0
        for req_act in ms.required_activities:
            assert req_act in act_ids, f"Required activity '{req_act}' in milestone '{ms.id}' not found in activity IDs"


def test_extract_activities_with_explicit_qto():
    """Test passing explicit ProjectQTO to extract_activities_from_manifest."""
    parsed_manifest = load_manifest(FARNSWORTH_PATH)
    qto = calculate_qto(parsed_manifest)

    schedule = extract_activities_from_manifest(parsed_manifest, qto_results=qto)

    assert isinstance(schedule, CrashingManifest)
    assert schedule.project_id == parsed_manifest.project.id
    assert len(schedule.activities) > 0

    # Check that element tags from QTO match elements in activities
    all_elem_ids = []
    for act in schedule.activities:
        all_elem_ids.extend(act.element_ids)

    assert "COL-A1" in all_elem_ids
    assert "SLAB-ROOF" in all_elem_ids


def test_extract_activities_yaml_roundtrip(tmp_path: Path):
    """Verify serialization of extracted CrashingManifest to schedule.yaml and parsing back."""
    manifest = extract_activities_from_manifest(FARNSWORTH_PATH)

    yaml_data = manifest.model_dump(mode="json")
    schedule_file = tmp_path / "schedule.yaml"
    with open(schedule_file, "w", encoding="utf-8") as f:
        yaml.dump(yaml_data, f, allow_unicode=True, sort_keys=False)

    loaded_manifest = load_schedule_yaml(schedule_file)
    assert loaded_manifest.project_id == manifest.project_id
    assert len(loaded_manifest.activities) == len(manifest.activities)
    assert len(loaded_manifest.milestones) == len(manifest.milestones)


def test_extract_activities_synthetic_multistorey():
    """Test activity and milestone extraction on a synthetic multi-storey model."""
    synthetic_manifest = {
        "schema": "IFC4-Minimal",
        "project": {
            "id": "PROJ-MULTI-STOREY",
            "name": "Two Storey Building",
        },
        "spatial_structure": {
            "storeys": [
                {"id": "Ground", "name": "Ground Level", "elevation": 0.0, "height": 3.5},
                {"id": "Level_2", "name": "Second Floor", "elevation": 3.5, "height": 3.2},
            ]
        },
        "grids": {
            "axes_x": {"1": 0.0, "2": 6.0},
            "axes_y": {"A": 0.0, "B": 6.0},
        },
        "materials": [
            {"id": "CONC", "name": "Concrete", "category": "concrete", "unit_cost_ref": "MAT-01"}
        ],
        "elements": [
            {
                "class": "IfcFooting",
                "tag": "F1",
                "material": "CONC",
                "profile": {"shape": "BOX", "width": 1.5, "depth": 1.5, "thickness": 0.5},
                "placement": {"grid": ["1", "A"], "storey": "Ground"},
            },
            {
                "class": "IfcColumn",
                "tag": "COL-1A",
                "material": "CONC",
                "profile": {"shape": "BOX", "width": 0.3, "depth": 0.3},
                "placement": {"grid": ["1", "A"], "base_storey": "Ground", "top_storey": "Level_2"},
            },
            {
                "class": "IfcBeam",
                "tag": "BEAM-L1-1",
                "material": "CONC",
                "profile": {"shape": "BOX", "width": 0.25, "depth": 0.50},
                "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "Ground"},
            },
            {
                "class": "IfcSlab",
                "tag": "SLAB-L1",
                "material": "CONC",
                "thickness": 0.15,
                "placement": {"storey": "Ground", "boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]]},
            },
            {
                "class": "IfcWall",
                "tag": "WALL-L1-A",
                "material": "CONC",
                "thickness": 0.15,
                "height": 3.0,
                "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "Ground"},
            },
            {
                "class": "IfcSlab",
                "tag": "SLAB-L2",
                "material": "CONC",
                "thickness": 0.15,
                "placement": {"storey": "Level_2", "boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]]},
            },
            {
                "class": "IfcWall",
                "tag": "WALL-L2-A",
                "material": "CONC",
                "thickness": 0.15,
                "height": 3.0,
                "placement": {"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "Level_2"},
            },
            {
                "class": "IfcRoof",
                "tag": "ROOF-TOP",
                "material": "CONC",
                "placement": {"storey": "Level_2", "boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]]},
            },
        ],
    }

    schedule = extract_activities_from_manifest(synthetic_manifest)
    assert isinstance(schedule, CrashingManifest)
    assert schedule.project_id == "PROJ-MULTI-STOREY"

    # Verify activity sequence and predecessor wiring
    act_map = {a.id: a for a in schedule.activities}

    assert "ACT_SUBSTRUCTURE" in act_map
    assert "ACT_COL_Ground" in act_map
    assert "ACT_STRUCT_Ground" in act_map
    assert "ACT_WALL_Ground" in act_map
    assert "ACT_STRUCT_Level_2" in act_map
    assert "ACT_WALL_Level_2" in act_map
    assert "ACT_ROOF" in act_map

    # Predecessor checks
    assert act_map["ACT_COL_Ground"].predecessors == ["ACT_SUBSTRUCTURE"]
    assert act_map["ACT_STRUCT_Ground"].predecessors == ["ACT_COL_Ground"]
    assert act_map["ACT_WALL_Ground"].predecessors == ["ACT_STRUCT_Ground"]
    assert act_map["ACT_STRUCT_Level_2"].predecessors == ["ACT_STRUCT_Ground"]
    assert act_map["ACT_WALL_Level_2"].predecessors == ["ACT_STRUCT_Level_2"]
    assert "ACT_WALL_Level_2" in act_map["ACT_ROOF"].predecessors

    # Validate payment percentage distribution
    assert len(schedule.milestones) > 0
    total_pct = sum(m.payment_percent for m in schedule.milestones)
    assert abs(total_pct - 100.0) < 1e-5
