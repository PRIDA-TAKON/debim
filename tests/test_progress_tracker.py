"""
Unit and CLI integration tests for 4D As-built Progress Tracking & Earned Value Scan Sync:
  - evaluate_element_presence
  - sync_scan_to_schedule
  - calculate_evm_metrics
  - CLI subcommand: debim progress sync
"""

from pathlib import Path
import numpy as np
import pytest
import yaml

from debim.cli import main
from debim.progress import (
    BoundingBox,
    EVMMetrics,
    calculate_evm_metrics,
    evaluate_element_presence,
    sync_scan_to_schedule,
)
from debim.scan.calibrator import save_ply
from debim.schedule.schema import (
    CrashingActivity,
    CrashingManifest,
    Milestone,
    ProgressLogEntry,
    load_schedule_yaml,
)


@pytest.fixture
def sample_bounding_box() -> BoundingBox:
    """1.0m x 1.0m x 1.0m box at origin (volume = 1.0 m3)."""
    return BoundingBox(min_x=0.0, min_y=0.0, min_z=0.0, max_x=1.0, max_y=1.0, max_z=1.0)


@pytest.fixture
def sample_crashing_manifest() -> CrashingManifest:
    """Sample CrashingManifest for progress tracking tests."""
    return CrashingManifest(
        project_id="PROJ-PROGRESS-TEST",
        as_of_date="Day 0",
        overhead_per_day=1000.0,
        milestones=[
            Milestone(
                id="MS-01",
                name="Milestone 1: Ground Structure",
                payment_percent=50.0,
                required_activities=["ACT_COL_01"],
            ),
            Milestone(
                id="MS-02",
                name="Milestone 2: Wall Enclosure",
                payment_percent=50.0,
                required_activities=["ACT_WALL_01"],
            ),
        ],
        activities=[
            CrashingActivity(
                id="ACT_COL_01",
                name="Construct Ground Column C1",
                element_ids=["C1"],
                normal_duration=5,
                crash_duration=3,
                normal_cost=50000.0,
                crash_cost=60000.0,
                cost_weight=50000.0,
            ),
            CrashingActivity(
                id="ACT_WALL_01",
                name="Erect Exterior Wall W1",
                element_ids=["W1"],
                predecessors=["ACT_COL_01"],
                normal_duration=10,
                crash_duration=7,
                normal_cost=100000.0,
                crash_cost=120000.0,
                cost_weight=100000.0,
            ),
        ],
    )


@pytest.fixture
def sample_model_manifest_yaml(tmp_path: Path) -> Path:
    """Create a minimal project.yaml BIM manifest defining C1 and W1 3D bounding boxes."""
    model_data = {
        "schema": "IFC4-Minimal",
        "version": "1.0.0",
        "project": {"id": "PROJ-PROGRESS-TEST", "name": "4D Progress Test Building"},
        "grids": {"axes_x": {"1": 0.0, "2": 5.0}, "axes_y": {"A": 0.0, "B": 5.0}},
        "spatial_structure": {
            "storeys": [{"id": "FL1", "name": "Floor 1", "elevation": 0.0, "height": 3.0}]
        },
        "materials": [{"id": "CONC", "name": "Concrete", "category": "concrete", "unit_cost_ref": "MAT-CONC-01"}],
        "elements": [
            {
                "class": "IfcColumn",
                "tag": "C1",
                "material": "CONC",
                "profile": {"shape": "BOX", "width": 0.4, "depth": 0.4},
                "placement": {"grid": ["1", "B"], "height": 3.0},
            },
            {
                "class": "IfcWall",
                "tag": "W1",
                "material": "CONC",
                "thickness": 0.2,
                "height": 3.0,
                "placement": {
                    "from_grid": ["1", "A"],
                    "to_grid": ["2", "A"],
                    "storey": "FL1",
                },
            },
        ],
    }

    model_path = tmp_path / "project.yaml"
    model_path.write_text(yaml.safe_dump(model_data), encoding="utf-8")
    return model_path


# --- Unit Tests for evaluate_element_presence ---

def test_evaluate_element_presence_full_density(sample_bounding_box: BoundingBox):
    rng = np.random.default_rng(42)
    # Generate 150 points inside 1.0m3 box -> density 150 pts/m3
    pts = rng.uniform(0.1, 0.9, (150, 3))

    ratio = evaluate_element_presence(sample_bounding_box, pts, min_point_density=100.0)
    assert ratio == 1.0


def test_evaluate_element_presence_partial_density(sample_bounding_box: BoundingBox):
    rng = np.random.default_rng(42)
    # Generate 50 points inside 1.0m3 box -> density 50 pts/m3
    pts = rng.uniform(0.1, 0.9, (50, 3))

    ratio = evaluate_element_presence(sample_bounding_box, pts, min_point_density=100.0)
    assert pytest.approx(ratio, abs=1e-3) == 0.5


def test_evaluate_element_presence_zero_points(sample_bounding_box: BoundingBox):
    # Scan points outside box
    pts = np.array([
        [10.0, 10.0, 10.0],
        [12.0, 15.0, 20.0],
    ])

    ratio = evaluate_element_presence(sample_bounding_box, pts, min_point_density=100.0)
    assert ratio == 0.0


def test_evaluate_element_presence_input_formats(sample_bounding_box: BoundingBox):
    rng = np.random.default_rng(42)
    pts = rng.uniform(0.1, 0.9, (100, 3))

    # Test tuple format
    tuple_box = (0.0, 0.0, 0.0, 1.0, 1.0, 1.0)
    ratio_t = evaluate_element_presence(tuple_box, pts, min_point_density=100.0)
    assert ratio_t == 1.0

    # Test dict format
    dict_box = {"min_x": 0.0, "min_y": 0.0, "min_z": 0.0, "max_x": 1.0, "max_y": 1.0, "max_z": 1.0}
    ratio_d = evaluate_element_presence(dict_box, pts, min_point_density=100.0)
    assert ratio_d == 1.0


# --- Unit Tests for EVM Metrics ---

def test_calculate_evm_metrics(sample_crashing_manifest: CrashingManifest):
    # Set progress
    sample_crashing_manifest.activities[0].progress_percent = 100.0 # C1 completed
    sample_crashing_manifest.activities[0].status = "COMPLETED"
    sample_crashing_manifest.activities[1].progress_percent = 50.0  # W1 half done
    sample_crashing_manifest.activities[1].status = "IN_PROGRESS"
    sample_crashing_manifest.as_of_date = "Day 5"

    evm = calculate_evm_metrics(sample_crashing_manifest)

    assert isinstance(evm, EVMMetrics)
    assert evm.as_of_date == "Day 5"
    assert evm.budget_at_completion > 0.0
    assert evm.earned_value > 0.0
    assert evm.planned_value >= 0.0
    assert evm.schedule_performance_index > 0.0
    assert evm.cost_performance_index > 0.0


# --- Integration Tests for sync_scan_to_schedule ---

def test_sync_scan_to_schedule(
    sample_crashing_manifest: CrashingManifest,
    sample_model_manifest_yaml: Path,
    tmp_path: Path,
):
    rng = np.random.default_rng(101)

    # C1 column bbox: x in [-0.2, 0.2], y in [-0.2, 0.2], z in [0, 3] -> volume = 0.4*0.4*3 = 0.48 m3
    # Generate 100 scan points inside C1 box -> density ~208 pts/m3 >= 100 -> C1 100% complete
        # C1 is at (0.0, 5.0)
    pts_c1 = np.column_stack([
        rng.uniform(-0.15, 0.15, 100),
            rng.uniform(4.85, 5.15, 100),
        rng.uniform(0.1, 2.9, 100),
    ])

    ply_path = tmp_path / "scan_week1.ply"
    save_ply(ply_path, pts_c1, binary=True)

    # Sync
    scan_date = "2026-10-15"
    updated_manifest = sync_scan_to_schedule(
        manifest=sample_crashing_manifest,
        scan_ply_path=ply_path,
        scan_date=scan_date,
        model_manifest=sample_model_manifest_yaml,
        min_point_density=100.0,
    )

    assert updated_manifest.as_of_date == scan_date

    # Act 1 (C1) should be COMPLETED (100%)
    act_c1 = updated_manifest.activities[0]
    assert act_c1.progress_percent == 100.0
    assert act_c1.status == "COMPLETED"
    assert act_c1.actual_start == scan_date
    assert act_c1.actual_finish == scan_date
    assert len(act_c1.progress_log) == 1
    assert act_c1.progress_log[0].date == scan_date
    assert act_c1.progress_log[0].percent == 100.0

    # Act 2 (W1) has no points -> NOT_STARTED (0%)
    act_w1 = updated_manifest.activities[1]
    assert act_w1.progress_percent == 0.0
    assert act_w1.status == "NOT_STARTED"

    # MS-01 (requires C1) should be READY_FOR_BILLING
    from debim.schedule.solver import solve_schedule
    res = solve_schedule(updated_manifest)
    ms1 = next(m for m in res.milestones if m.id == "MS-01")
    assert ms1.is_completed is True
    assert ms1.billing_status == "READY_FOR_BILLING"


# --- CLI Integration Tests ---

def test_cli_progress_sync(
    sample_crashing_manifest: CrashingManifest,
    sample_model_manifest_yaml: Path,
    tmp_path: Path,
    capsys,
):
    sched_yaml = tmp_path / "schedule.yaml"
    out_yaml = tmp_path / "updated_schedule.yaml"
    ply_path = tmp_path / "scan_site.ply"

    # Save schedule YAML
    dump_data = sample_crashing_manifest.model_dump(by_alias=True, exclude_none=True)
    sched_yaml.write_text(yaml.safe_dump(dump_data), encoding="utf-8")

    # Save PLY scan centered on C1 at (0.0, 5.0, 0.0)
    rng = np.random.default_rng(202)
    pts = np.column_stack([
        rng.uniform(-0.1, 0.1, 120),
        rng.uniform(4.9, 5.1, 120),
        rng.uniform(0.1, 2.9, 120),
    ])
    save_ply(ply_path, pts, binary=True)

    main([
        "progress",
        "sync",
        "--schedule",
        str(sched_yaml),
        "--scan",
        str(ply_path),
        "--date",
        "2026-11-01",
        "-o",
        str(out_yaml),
        "-m",
        str(sample_model_manifest_yaml),
    ])

    captured = capsys.readouterr()
    assert "Syncing 4D Site Scan with Schedule" in captured.out
    assert "Activity Actual Progress Updates" in captured.out
    assert "Earned Value Management (EVM) Metrics Snapshot" in captured.out
    assert "4D As-Built Progress Sync Complete!" in captured.out
    assert out_yaml.exists()

    # Verify updated_schedule.yaml
    loaded = load_schedule_yaml(out_yaml)
    assert loaded.as_of_date == "2026-11-01"
    assert loaded.activities[0].progress_percent == 100.0
