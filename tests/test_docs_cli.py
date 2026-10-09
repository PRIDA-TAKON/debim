import json
from pathlib import Path
from typer.testing import CliRunner
from debim.cli import app, _generate_docs_bundle

runner = CliRunner()


def test_generate_docs_bundle_directly(tmp_path: Path):
    out_dir = tmp_path / "docs_output"
    res_dir = _generate_docs_bundle(output_dir=out_dir, schema_version="IFC4")

    assert res_dir.exists()
    assert (res_dir / "index.html").exists()
    assert (res_dir / "entities.json").exists()

    index_html = (res_dir / "index.html").read_text(encoding="utf-8")
    assert "debim Interactive Class Directory" in index_html
    assert "IFC4" in index_html

    with open(res_dir / "entities.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "IfcWall" in data
    assert "IfcBeam" in data
    assert data["IfcWall"]["is_element"] is True


def test_docs_build_cli_default(tmp_path: Path):
    target_dir = tmp_path / "dist_docs_test"
    res = runner.invoke(app, ["docs", "build", "--output-dir", str(target_dir)])

    assert res.exit_code == 0
    assert "Interactive Class Directory Generated Successfully" in res.output
    assert (target_dir / "index.html").exists()
    assert (target_dir / "entities.json").exists()


def test_docs_build_cli_custom_schema(tmp_path: Path):
    target_dir = tmp_path / "dist_docs_ifc4x3"
    res = runner.invoke(app, ["docs", "build", "-o", str(target_dir), "-s", "IFC4X3"])

    assert res.exit_code == 0
    assert (target_dir / "index.html").exists()


def test_docs_serve_cli_options(tmp_path: Path):
    target_dir = tmp_path / "docs_to_serve"
    # Execute with invalid port or non-blocking check
    res = runner.invoke(app, ["docs", "serve", "--docs-dir", str(target_dir), "--no-browser", "--help"])
    assert res.exit_code == 0
    assert "Spins up a local HTTP server" in res.output
