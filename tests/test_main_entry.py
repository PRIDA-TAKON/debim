import subprocess
import sys


def test_main_module_entry_help():
    res = subprocess.run(
        [sys.executable, "-m", "debim", "--help"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "Minimal Declarative BIM" in res.stdout or "Available subcommands" in res.stdout


def test_main_submodule_entry_help():
    res = subprocess.run(
        [sys.executable, "-m", "debim.main", "--help"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "Minimal Declarative BIM" in res.stdout or "Available subcommands" in res.stdout
