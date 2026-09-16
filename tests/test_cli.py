"""
Basic smoke tests for CLI entrypoint
"""

from typer.testing import CliRunner
from debim.cli import app

runner = CliRunner()

def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Minimal Declarative BIM" in result.output

def test_cli_validate_missing_file():
    result = runner.invoke(app, ["validate", "--manifest", "non_existent.yaml"])
    assert result.exit_code == 1
    assert "Error" in result.output
