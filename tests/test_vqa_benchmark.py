"""
Unit and integration tests for 2D Construction Blueprint VQA Cognitive Benchmark Engine via Gemini Multimodal.
"""

import json
import sys
from pathlib import Path

# Ensure repo root is in sys.path for tools package imports
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import pytest
from typer.testing import CliRunner

from debim.cli import app
from tools.benchmark_vqa_gemini import (
    TokenBucketRateLimiter,
    VQABenchmarkReport,
    ensure_raster_image,
    evaluate_question_gemini_api,
    rasterize_svg_to_png,
    run_vqa_benchmark,
)
from tools.generate_vqa_dataset import (
    create_synthetic_manifest,
    generate_vqa_dataset,
    generate_vqa_questions,
)


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    out_dir = tmp_path / "vqa_dist"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def test_create_synthetic_manifest_and_questions():
    """Test synthetic building model generation and VQA question extraction across 4 categories."""
    manifest = create_synthetic_manifest()
    assert manifest.project.id == "PRJ-SYNTH-01"
    assert len(manifest.elements) > 0

    questions = generate_vqa_questions(manifest, seed=42)
    assert len(questions) > 0

    categories = {q["category"] for q in questions}
    expected_categories = {"Dimensions", "Topology", "Tags", "Levels"}
    assert expected_categories.issubset(categories)

    for q in questions:
        assert "question_id" in q
        assert "choices" in q
        assert set(q["choices"].keys()) == {"A", "B", "C", "D"}
        assert q["correct_choice"] in {"A", "B", "C", "D"}
        assert q["choices"][q["correct_choice"]] == q["ground_truth_value"]


def test_generate_vqa_dataset_file_export(tmp_output_dir: Path):
    """Test generating and exporting vqa_dataset.json and 2D SVG blueprint image."""
    ds_json_path = tmp_output_dir / "vqa_dataset.json"
    img_dir = tmp_output_dir / "vqa_images"

    ds_dict = generate_vqa_dataset(
        manifest_path=None,  # Synthetic fallback
        output_dataset_path=ds_json_path,
        output_image_dir=img_dir,
        seed=123,
    )

    assert ds_json_path.exists()
    assert len(list(img_dir.glob("*.svg"))) == 1

    with open(ds_json_path, "r", encoding="utf-8") as f:
        loaded_ds = json.load(f)

    assert loaded_ds["project_id"] == "PRJ-SYNTH-01"
    assert loaded_ds["question_count"] == len(loaded_ds["questions"])
    assert loaded_ds["question_count"] > 0


def test_rate_limiter_acquire():
    """Test TokenBucketRateLimiter token leakage and acquisition interval."""
    limiter = TokenBucketRateLimiter(rpm=600, tpm=600000)
    t0 = limiter.last_request_time
    limiter.acquire(estimated_tokens=100)
    assert limiter.last_request_time >= t0


def test_benchmark_vqa_mock_eval(tmp_output_dir: Path):
    """Test VQA evaluation runner in mock evaluation mode."""
    ds_json_path = tmp_output_dir / "vqa_dataset.json"
    img_dir = tmp_output_dir / "vqa_images"

    generate_vqa_dataset(
        manifest_path="examples/farnsworth_house/project.yaml",
        output_dataset_path=ds_json_path,
        output_image_dir=img_dir,
    )

    report_json_path = tmp_output_dir / "vqa_report.json"
    report_md_path = tmp_output_dir / "vqa_report.md"

    report = run_vqa_benchmark(
        dataset_path=ds_json_path,
        mock_eval=True,
        output_report_path=report_json_path,
        output_markdown_path=report_md_path,
    )

    assert isinstance(report, VQABenchmarkReport)
    assert report.total_questions > 0
    assert 0.0 <= report.overall_accuracy_pct <= 100.0
    assert len(report.category_accuracy) > 0

    assert report_json_path.exists()
    assert report_md_path.exists()

    md_content = report_md_path.read_text(encoding="utf-8")
    assert "# 2D Construction Blueprint VQA Cognitive Benchmark Report" in md_content
    assert "Overall VQA Accuracy" in md_content


def test_ensure_raster_image_svg_conversion():
    """Test converting SVG blueprint image bytes to PNG raster image format for Gemini API."""
    svg_data = b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100"/></svg>'
    png_bytes, mime = ensure_raster_image(svg_data, "image/svg+xml")

    assert mime == "image/png"
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_gemini_38_extended_thinking_endpoint_and_payload(monkeypatch):
    """Test Gemini 3.8 Live Extended Thinking v1alpha URL construction, model stripping, and thinking_config payload."""
    import base64

    captured_requests = []

    class MockResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "question_id": "Q-101",
                                            "selected_choice": "B",
                                            "visual_confidence": 0.95,
                                            "readability_notes": "Clear rendering",
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            }

    class MockClient:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def post(self, url, headers=None, json=None):
            captured_requests.append({"url": url, "headers": headers, "json": json})
            return MockResponse()

    monkeypatch.setattr("httpx.Client", MockClient)

    limiter = TokenBucketRateLimiter(rpm=6000, tpm=600000)
    question = {
        "question_id": "Q-101",
        "question_text": "What is the wall thickness?",
        "choices": {"A": "100 mm", "B": "200 mm", "C": "300 mm", "D": "400 mm"},
        "correct_choice": "B",
    }
    dummy_svg_b64 = base64.b64encode(b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>').decode("utf-8")

    result = evaluate_question_gemini_api(
        question=question,
        image_base64=dummy_svg_b64,
        image_mime_type="image/svg+xml",
        api_key="TEST_API_KEY",
        model_name="models/gemini-3.8-live-extended-thinking",
        limiter=limiter,
        thinking_budget=2048,
    )

    assert result["selected_choice"] == "B"
    assert len(captured_requests) == 1

    req = captured_requests[0]
    expected_url = "https://generativelanguage.googleapis.com/v1alpha/models/gemini-3.8-live-extended-thinking:generateContent?key=TEST_API_KEY"
    assert req["url"] == expected_url

    gen_cfg = req["json"]["generationConfig"]
    assert gen_cfg["thinking_config"]["thinking_budget"] == 2048

    inline_part = req["json"]["contents"][0]["parts"][0]["inline_data"]
    assert inline_part["mime_type"] == "image/png"


def test_vqa_cli_integration(tmp_output_dir: Path):
    """Test debim draw generate-vqa and debim draw benchmark-vqa CLI commands."""
    runner = CliRunner()
    ds_json_path = tmp_output_dir / "cli_dataset.json"
    img_dir = tmp_output_dir / "cli_images"
    report_json_path = tmp_output_dir / "cli_report.json"
    report_md_path = tmp_output_dir / "cli_report.md"

    # 1. debim draw generate-vqa
    res_gen = runner.invoke(
        app,
        [
            "draw",
            "generate-vqa",
            "-m",
            "examples/farnsworth_house/project.yaml",
            "-o",
            str(ds_json_path),
            "--image-dir",
            str(img_dir),
        ],
    )
    assert res_gen.exit_code == 0
    assert ds_json_path.exists()

    # 2. debim draw benchmark-vqa --mock-eval
    res_bench = runner.invoke(
        app,
        [
            "draw",
            "benchmark-vqa",
            "-d",
            str(ds_json_path),
            "--mock-eval",
            "-o",
            str(report_json_path),
            "--markdown-output",
            str(report_md_path),
        ],
    )
    assert res_bench.exit_code == 0
    assert report_json_path.exists()
    assert report_md_path.exists()
