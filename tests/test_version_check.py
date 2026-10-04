"""
Unit tests for PyPI version checker and update notifier in debim
"""

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner

from debim.cli import app
from debim.version import (
    __version__,
    check_and_notify_updates,
    check_for_updates,
    fetch_pypi_version,
    parse_version,
    read_cache,
    should_suppress_update_check,
    write_cache,
)

runner = CliRunner()


def test_parse_version():
    """Verify version string parsing and comparison tuples."""
    assert parse_version("0.2.1") > parse_version("0.2.0")
    assert parse_version("0.2.0") == parse_version("0.2.0")
    assert parse_version("1.0.0") > parse_version("0.2.0")
    assert parse_version("0.2.0") > parse_version("0.1.9")
    assert parse_version("0.2.1") > parse_version("0.2.0b1")
    assert parse_version("") == ()


def test_cache_read_write(tmp_path: Path):
    """Verify writing and reading from version cache file."""
    cache_file = tmp_path / "version_cache.json"
    now = time.time()

    write_cache(cache_file, now, "0.2.1")
    assert cache_file.exists()

    last_check, version = read_cache(cache_file)
    assert last_check == pytest.approx(now, abs=1.0)
    assert version == "0.2.1"


def test_check_for_updates_cache_hit(tmp_path: Path):
    """Verify 24-hour cache hit avoids network calls."""
    cache_file = tmp_path / "version_cache.json"
    now = time.time()
    # Write fresh cache (10 seconds ago)
    write_cache(cache_file, now - 10, "0.2.1")

    with patch("debim.version.fetch_pypi_version") as mock_fetch:
        latest = check_for_updates(cache_path=cache_file, cache_ttl=86400)
        assert latest == "0.2.1"
        # Network fetch should NOT be called
        mock_fetch.assert_not_called()


def test_check_for_updates_cache_stale(tmp_path: Path):
    """Verify stale cache (>24 hours old) triggers network fetch."""
    cache_file = tmp_path / "version_cache.json"
    now = time.time()
    # Write stale cache (25 hours ago)
    write_cache(cache_file, now - 90000, "0.2.0")

    with patch("debim.version.fetch_pypi_version", return_value="0.2.2") as mock_fetch:
        latest = check_for_updates(cache_path=cache_file, cache_ttl=86400)
        assert latest == "0.2.2"
        mock_fetch.assert_called_once()

    # Cache file should be updated with new version
    _, updated_version = read_cache(cache_file)
    assert updated_version == "0.2.2"


def test_fetch_pypi_version_success():
    """Verify fetching version from PyPI JSON API response."""
    mock_response_bytes = json.dumps({"info": {"version": "0.2.5"}}).encode("utf-8")

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = mock_response_bytes
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        v = fetch_pypi_version()
        assert v == "0.2.5"


def test_fetch_pypi_version_failure_handled():
    """Verify network timeouts / errors return None without raising exceptions."""
    with patch("urllib.request.urlopen", side_effect=OSError("Network timeout")):
        v = fetch_pypi_version()
        assert v is None


def test_check_for_updates_offline_fallback(tmp_path: Path):
    """Verify offline / network failure falls back to cached version."""
    cache_file = tmp_path / "version_cache.json"
    now = time.time()
    write_cache(cache_file, now - 90000, "0.2.0")

    with patch("debim.version.fetch_pypi_version", return_value=None):
        latest = check_for_updates(cache_path=cache_file, cache_ttl=86400)
        # Should fall back to cached version
        assert latest == "0.2.0"


def test_suppression_logic():
    """Verify suppression rules (DEBIM_NO_UPDATE_CHECK, quiet, non-TTY, mcp)."""
    # DEBIM_NO_UPDATE_CHECK=1
    with patch.dict(os.environ, {"DEBIM_NO_UPDATE_CHECK": "1"}):
        assert should_suppress_update_check(force_tty=True) is True

    with patch.dict(os.environ, {"DEBIM_NO_UPDATE_CHECK": "true"}):
        assert should_suppress_update_check(force_tty=True) is True

    # Quiet flag
    with patch.dict(os.environ, {}, clear=True):
        assert should_suppress_update_check(quiet=True, force_tty=True) is True

    # Non-TTY
    with patch.dict(os.environ, {}, clear=True):
        assert should_suppress_update_check(quiet=False, force_tty=False) is True

    # Normal TTY without suppression env vars
    with patch.dict(os.environ, {}, clear=True):
        assert should_suppress_update_check(quiet=False, force_tty=True) is False


def test_notification_displayed_when_outdated(tmp_path: Path):
    """Verify update notification is printed when newer version exists."""
    cache_file = tmp_path / "version_cache.json"
    write_cache(cache_file, time.time(), "0.3.0")

    mock_console = MagicMock()

    with patch("debim.version.__version__", "0.2.0"):
        check_and_notify_updates(
            console=mock_console,
            cache_path=cache_file,
            force_tty=True,
            quiet=False,
        )

    mock_console.print.assert_called_once()
    printed_str = mock_console.print.call_args[0][0]
    assert r"\[notice]" in printed_str or "[notice]" in printed_str
    assert "0.2.0" in printed_str
    assert "0.3.0" in printed_str
    assert "pip install -U debim" in printed_str


def test_notification_suppressed_when_up_to_date(tmp_path: Path):
    """Verify no update notification if current version is up to date."""
    cache_file = tmp_path / "version_cache.json"
    write_cache(cache_file, time.time(), "0.2.0")

    mock_console = MagicMock()

    with patch("debim.version.__version__", "0.2.0"):
        check_and_notify_updates(
            console=mock_console,
            cache_path=cache_file,
            force_tty=True,
            quiet=False,
        )

    mock_console.print.assert_not_called()


def test_cli_version_flag_with_quiet(tmp_path: Path):
    """Test running CLI with --version and --quiet flag."""
    result = runner.invoke(app, ["--version", "--quiet"])
    assert result.exit_code == 0
    assert "debim" in result.output
    assert "[notice]" not in result.output
