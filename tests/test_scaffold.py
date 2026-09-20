"""
Unit tests for Element Scaffolding tool and CLI command (debim.scaffold / bim scaffold element)
"""

import ast
from pathlib import Path
from typer.testing import CliRunner
from debim.cli import app
from debim.scaffold import scaffold_element, generate_scaffold_artifacts, snake_case

runner = CliRunner()


def test_snake_case():
    assert snake_case("IfcRailing") == "ifc_railing"
    assert snake_case("IfcCurtainWall") == "ifc_curtain_wall"
    assert snake_case("Railing") == "railing"


def test_generate_scaffold_artifacts():
    artifacts = generate_scaffold_artifacts("IfcRailing", placement_type="grid", layer="architecture/openings/railings")
    assert "class IfcRailing(BaseModel):" in artifacts["schema_code"]
    assert "class ResolvedRailing(BaseModel):" in artifacts["resolver_code"]
    assert "elif isinstance(resolved, ResolvedRailing):" in artifacts["qto_code"]
    assert "def test_ifc_railing_instantiation():" in artifacts["test_code"]

    # Verify python syntax validity of test code
    ast.parse(artifacts["test_code"])


def test_cli_scaffold_element_dry_run():
    result = runner.invoke(app, ["scaffold", "element", "IfcRailing", "--layer", "architecture/openings/railings"])
    assert result.exit_code == 0
    assert "IfcRailing" in result.output
    assert "architecture/openings/railings" in result.output
    assert "Dry-run complete!" in result.output


def test_cli_scaffold_element_no_dry_run(tmp_path: Path):
    out_dir = tmp_path / "gen"
    result = runner.invoke(app, ["scaffold", "element", "IfcCurtainWall", "--no-dry-run", "-o", str(out_dir)])
    assert result.exit_code == 0
    assert (out_dir / "ifc_curtain_wall_schema.py").exists()
    assert (out_dir / "ifc_curtain_wall_resolver.py").exists()
    assert (out_dir / "ifc_curtain_wall_qto.py").exists()
    assert (out_dir / "test_ifc_curtain_wall.py").exists()
