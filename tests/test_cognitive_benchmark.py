"""
Unit tests for Round-Trip Cognitive Regression Benchmark Engine (debim.benchmark).
"""

import json
from pathlib import Path
import pytest

from debim.benchmark import (
    CognitiveBenchmarkEngine,
    CognitiveBenchmarkResult,
    generate_json_report,
    generate_markdown_report,
    run_cognitive_benchmark,
)
from debim.schema import (
    BoxProfile,
    Grids,
    IfcColumn,
    IfcWall,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    WallPlacement,
    ColumnPlacement,
)


@pytest.fixture
def sample_gt_manifest() -> ProjectManifest:
    """Fixture providing a ground truth project manifest with structural elements."""
    return ProjectManifest(
        project=ProjectInfo(id="PRJ-BENCH-01", name="Benchmark Ground Truth Model"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Ground Level", elevation=0.0, height=3.5),
                Storey(id="L2", name="Level 2", elevation=3.5, height=3.5),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 6.0},
            axes_y={"A": 0.0, "B": 6.0},
        ),
        materials=[
            Material(id="CONC", name="Structural Concrete", category="concrete", unit_cost_ref="MAT-CONC-01"),
        ],
        elements=[
            # 1. Structural Columns
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "C1",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.40, depth=0.40),
                    "placement": ColumnPlacement(grid=("1", "A"), base_storey="L1", top_storey="L2"),
                }
            ),
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "C2",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.40, depth=0.40),
                    "placement": ColumnPlacement(grid=("2", "A"), base_storey="L1", top_storey="L2"),
                }
            ),
            # 2. Wall
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": "W1",
                    "material": "CONC",
                    "thickness": 0.20,
                    "height": 3.50,
                    "placement": WallPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L1"),
                }
            ),
        ],
    )


def test_perfect_match_benchmark(sample_gt_manifest):
    """Test 100% perfect match between Ground Truth and Reconstructed models."""
    res = run_cognitive_benchmark(
        ground_truth=sample_gt_manifest,
        reconstructed_or_callback=sample_gt_manifest,
        model_name="perfect_vision_model",
        scene_id="scene_01",
    )

    assert isinstance(res, CognitiveBenchmarkResult)
    assert res.cdqs == 100.0
    assert res.entity_retention_rate == 100.0
    assert res.gt_element_count == 3
    assert res.reconstructed_element_count == 3
    assert res.matched_element_count == 3
    assert res.phantom_element_count == 0
    assert res.coordinate_mae == 0.0
    assert res.dimension_mae == 0.0
    assert res.hallucination_score == 0.0
    assert res.structural_fail_flag is False
    assert res.retention_by_category["IfcColumn"] == 100.0
    assert res.retention_by_category["IfcWall"] == 100.0


def test_missing_structural_columns_penalty(sample_gt_manifest):
    """Test structural fail flag when critical columns vanish in reconstructed manifest."""
    # Reconstructed model missing columns (only has wall W1)
    rec_manifest = ProjectManifest(
        project=ProjectInfo(id="PRJ-BENCH-REC", name="Reconstructed Missing Columns"),
        spatial_structure=sample_gt_manifest.spatial_structure,
        grids=sample_gt_manifest.grids,
        materials=sample_gt_manifest.materials,
        elements=[
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": "W1",
                    "material": "CONC",
                    "thickness": 0.20,
                    "height": 3.50,
                    "placement": WallPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L1"),
                }
            ),
        ],
    )

    res = run_cognitive_benchmark(
        ground_truth=sample_gt_manifest,
        reconstructed_or_callback=rec_manifest,
        model_name="failing_vision_model",
        scene_id="scene_01",
    )

    assert res.structural_fail_flag is True
    assert res.retention_by_category["IfcColumn"] == 0.0
    assert res.retention_by_category["IfcWall"] == 100.0
    assert res.matched_element_count == 1
    assert res.cdqs <= 20.0  # Severe structural failure penalty applied


def test_coordinate_mae_and_dimension_drift(sample_gt_manifest):
    """Test coordinate MAE and dimension error calculations when spatial drift occurs."""
    # Displace column C1 by 0.10m in X direction and drift width by 0.10m
    rec_manifest = ProjectManifest(
        project=ProjectInfo(id="PRJ-BENCH-DRIFT", name="Reconstructed Drift Model"),
        spatial_structure=sample_gt_manifest.spatial_structure,
        grids=sample_gt_manifest.grids,
        materials=sample_gt_manifest.materials,
        elements=[
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "C1",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.50, depth=0.40),  # 0.10m width drift
                    "placement": ColumnPlacement(
                        grid=("1", "A"),
                        base_storey="L1",
                        top_storey="L2",
                        offset_base=(0.10, 0.0, 0.0),
                        offset_top=(0.10, 0.0, 0.0),
                    ),
                }
            ),
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "C2",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.40, depth=0.40),
                    "placement": ColumnPlacement(grid=("2", "A"), base_storey="L1", top_storey="L2"),
                }
            ),
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": "W1",
                    "material": "CONC",
                    "thickness": 0.20,
                    "height": 3.50,
                    "placement": WallPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L1"),
                }
            ),
        ],
    )

    engine = CognitiveBenchmarkEngine()
    res = engine.evaluate(
        ground_truth=sample_gt_manifest,
        reconstructed=rec_manifest,
        model_name="drift_vision_model",
    )

    assert res.structural_fail_flag is False
    assert res.entity_retention_rate == 100.0
    assert res.coordinate_mae > 0.0
    assert res.dimension_mae > 0.0
    assert res.cdqs < 100.0
    assert res.cdqs > 80.0


def test_phantom_elements_clutter_penalty(sample_gt_manifest):
    """Test clutter and hallucination score penalties when phantom elements are introduced."""
    # Introduce 2 extra phantom columns
    rec_manifest = ProjectManifest(
        project=ProjectInfo(id="PRJ-BENCH-PHANTOM", name="Reconstructed Phantom Model"),
        spatial_structure=sample_gt_manifest.spatial_structure,
        grids=sample_gt_manifest.grids,
        materials=sample_gt_manifest.materials,
        elements=list(sample_gt_manifest.elements) + [
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "C_PHANTOM_1",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.40, depth=0.40),
                    "placement": ColumnPlacement(grid=("1", "B"), base_storey="L1", top_storey="L2"),
                }
            ),
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "C_PHANTOM_2",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.40, depth=0.40),
                    "placement": ColumnPlacement(grid=("2", "B"), base_storey="L1", top_storey="L2"),
                }
            ),
        ],
    )

    res = run_cognitive_benchmark(
        ground_truth=sample_gt_manifest,
        reconstructed_or_callback=rec_manifest,
        model_name="hallucinating_model",
    )

    assert res.phantom_element_count == 2
    assert res.hallucination_score == pytest.approx(2.0 / 3.0, rel=1e-2)
    assert res.cdqs < 100.0


def test_closed_loop_roundtrip_workflow(sample_gt_manifest):
    """Test closed-loop roundtrip execution using mock AI agent callback."""
    # Mock callback receives 2D blueprint SVG string and returns reconstructed manifest
    def mock_agent_callback(blueprint_svg: str) -> ProjectManifest:
        assert isinstance(blueprint_svg, str)
        assert "<svg" in blueprint_svg
        return sample_gt_manifest

    engine = CognitiveBenchmarkEngine(agent_callback=mock_agent_callback)
    res = engine.run_roundtrip(
        ground_truth=sample_gt_manifest,
        model_name="mock_vision_assistant_v1",
        scene_id="scene_townhouse",
    )

    assert res.model_name == "mock_vision_assistant_v1"
    assert res.scene_id == "scene_townhouse"
    assert res.cdqs == 100.0
    assert res.execution_time_ms >= 0.0


def test_leaderboard_and_reports(sample_gt_manifest):
    """Test Markdown leaderboard table and JSON report generation."""
    res1 = run_cognitive_benchmark(
        ground_truth=sample_gt_manifest,
        reconstructed_or_callback=sample_gt_manifest,
        model_name="Claude_3_7_Sonnet",
        scene_id="scene_01",
    )

    res2 = CognitiveBenchmarkResult(
        model_name="Legacy_Vision_Model",
        scene_id="scene_01",
        cdqs=45.5,
        entity_retention_rate=66.7,
        gt_element_count=3,
        reconstructed_element_count=2,
        matched_element_count=2,
        phantom_element_count=0,
        structural_fail_flag=True,
        coordinate_mae=0.25,
        dimension_mae=0.05,
        hallucination_score=0.0,
        execution_time_ms=120.0,
    )

    # 1. JSON Report
    json_str = generate_json_report([res1, res2])
    data = json.loads(json_str)
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["cdqs"] == 100.0

    # 2. Markdown Leaderboard
    md_str = generate_markdown_report([res1, res2])
    assert "# Cognitive Regression Benchmark Leaderboard" in md_str
    assert "| Rank | AI Model | Scene | CDQS Score |" in md_str
    assert "`Claude_3_7_Sonnet`" in md_str
    assert "`Legacy_Vision_Model`" in md_str
    assert "**FAIL**" in md_str
    assert "PASS" in md_str
