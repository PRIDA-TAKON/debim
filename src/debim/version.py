"""
PyPI version checker and update notifier for debim
"""

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console

__version__ = "0.3.1"

PYPI_URL = "https://pypi.org/pypi/debim/json"
DEFAULT_CACHE_TTL = 86400  # 24 hours in seconds


def get_cache_path() -> Path:
    """Return path to cache file (~/.debim/version_cache.json or DEBIM_CACHE_FILE override)."""
    env_path = os.environ.get("DEBIM_CACHE_FILE")
    if env_path:
        return Path(env_path)
    return Path.home() / ".debim" / "version_cache.json"


def parse_version(v_str: str) -> tuple:
    """Parse a version string like '0.2.1' or '0.2.1b1' into a tuple for comparison."""
    if not v_str:
        return ()
    parts = []
    for part in v_str.strip().split("."):
        match = re.match(r"^(\d+)(.*)$", part)
        if match:
            num = int(match.group(1))
            suffix = match.group(2)
            parts.append((num, suffix))
        else:
            parts.append((0, part))
    return tuple(parts)


def fetch_pypi_version(timeout: float = 0.5) -> Optional[str]:
    """Fetch latest debim version from PyPI JSON API with a short timeout."""
    try:
        req = urllib.request.Request(
            PYPI_URL,
            headers={"User-Agent": f"debim/{__version__}"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                version = data.get("info", {}).get("version")
                if isinstance(version, str):
                    return version.strip()
    except Exception:
        pass
    return None


def read_cache(cache_path: Path) -> tuple[Optional[float], Optional[str]]:
    """Read last check timestamp and latest version from cache file."""
    try:
        if cache_path.exists():
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            last_check = data.get("last_check")
            latest_version = data.get("latest_version")
            if isinstance(last_check, (int, float)) and (
                latest_version is None or isinstance(latest_version, str)
            ):
                return last_check, latest_version
    except Exception:
        pass
    return None, None


def write_cache(cache_path: Path, last_check: float, latest_version: Optional[str]) -> None:
    """Write last check timestamp and latest version to cache file."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_check": last_check,
            "latest_version": latest_version,
        }
        cache_path.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        pass


def check_for_updates(
    cache_ttl: int = DEFAULT_CACHE_TTL,
    timeout: float = 0.5,
    force_fetch: bool = False,
    cache_path: Optional[Path] = None,
) -> Optional[str]:
    """
    Check PyPI for a newer version of debim, using 24-hour caching.
    Returns latest version string if fetched/cached, or None.
    Never raises exceptions.
    """
    if cache_path is None:
        cache_path = get_cache_path()

    now = time.time()
    last_check, cached_version = read_cache(cache_path)

    # If cache is valid (< 24 hours old) and not force_fetch, return cached version
    if (
        not force_fetch
        and last_check is not None
        and (now - last_check) < cache_ttl
    ):
        return cached_version

    # Fetch latest version from PyPI
    pypi_version = fetch_pypi_version(timeout=timeout)

    # On network failure, retain cached version if available, but update last_check timestamp
    latest = pypi_version or cached_version
    write_cache(cache_path, now, latest)

    return latest


def should_suppress_update_check(
    ctx: Optional[typer.Context] = None,
    quiet: bool = False,
    force_tty: Optional[bool] = None,
) -> bool:
    """
    Determine if update check / notification should be suppressed.
    """
    # 1. Environment variable suppression
    if os.environ.get("DEBIM_NO_UPDATE_CHECK", "").lower() in ("1", "true", "yes"):
        return True

    # 2. Quiet flag or DEBIM_QUIET env var
    if quiet or os.environ.get("DEBIM_QUIET", "").lower() in ("1", "true", "yes"):
        return True

    # 3. Piped / non-TTY check
    is_tty = sys.stdout.isatty() if force_tty is None else force_tty
    if not is_tty:
        return True

    # 4. MCP mode or machine-readable subcommands
    if ctx is not None and ctx.invoked_subcommand in ("mcp",):
        return True
    if any(cmd in sys.argv for cmd in ("mcp",)):
        return True

    return False


def check_and_notify_updates(
    console: Optional[Console] = None,
    quiet: bool = False,
    ctx: Optional[typer.Context] = None,
    cache_path: Optional[Path] = None,
    force_tty: Optional[bool] = None,
) -> None:
    """
    Check for updates and display a subtle notification if a newer release exists.
    Never raises exceptions.
    """
    try:
        if should_suppress_update_check(ctx=ctx, quiet=quiet, force_tty=force_tty):
            return

        latest_version = check_for_updates(cache_path=cache_path)
        if latest_version and parse_version(latest_version) > parse_version(__version__):
            if console is None:
                console = Console()
            notice_str = (
                r"[bold #f59e0b]\[notice][/bold #f59e0b] "
                f"[bold #94a3b8]A new release of debim is available:[/bold #94a3b8] "
                f"[bold #ef4444]{__version__}[/bold #ef4444] -> [bold #10b981]{latest_version}[/bold #10b981]\n"
                r"[bold #94a3b8]Run:[/bold #94a3b8] [bold #22d3ee]pip install -U debim[/bold #22d3ee]"
            )
            console.print(f"\n{notice_str}\n")
    except Exception:
        pass
