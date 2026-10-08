"""
Tests for Material Specification Registry Client & Package Manager
"""

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
import yaml
from typer.testing import CliRunner

from debim.cli import app
from debim.spec.registry import (
    MaterialSpecPackage,
    SpecRegistryClient,
    parse_spec_content,
    resolve_package_urls,
)

runner = CliRunner()


def test_resolve_package_urls():
    # Scoped package
    urls_scoped = resolve_package_urls("@toa/supershield-exterior")
    assert any("raw.githubusercontent.com/toa/supershield-exterior/main/spec.yaml" in u for u in urls_scoped)

    # Org/Repo/Package shorthand
    urls_path = resolve_package_urls("toa/paints/supershield-exterior")
    assert any("raw.githubusercontent.com/toa/paints/main/supershield-exterior/spec.yaml" in u for u in urls_path)

    # Org/Repo shorthand
    urls_repo = resolve_package_urls("toa/paints")
    assert any("raw.githubusercontent.com/toa/paints/main/spec.yaml" in u for u in urls_repo)

    # Full raw URL
    raw_url = "https://raw.githubusercontent.com/toa/paint/main/spec.yaml"
    assert resolve_package_urls(raw_url) == [raw_url]

    # GitHub blob URL conversion
    blob_url = "https://github.com/toa/paint/blob/main/spec.yaml"
    assert resolve_package_urls(blob_url) == ["https://raw.githubusercontent.com/toa/paint/main/spec.yaml"]

    # Thai registry @th shorthand
    urls_th = resolve_package_urls("@th/toa-supershield-exterior")
    assert any("PRIDA-TAKON/debim-specs-th/main/packages/09-finishes/toa-supershield-exterior/spec.yaml" in u for u in urls_th)

    # Thai registry th/ shorthand
    urls_th_div = resolve_package_urls("th/03-concrete/concrete-readymix-240ksc")
    assert any("PRIDA-TAKON/debim-specs-th/main/packages/03-concrete/concrete-readymix-240ksc/spec.yaml" in u for u in urls_th_div)


def test_parse_spec_content_yaml():
    yaml_content = """
name: supershield-exterior
version: 2.1.0
manufacturer: TOA Paint
category: paints
description: Acrylic emulsion paint for exterior walls
properties:
  gloss_level: semi-gloss
  durability_years: 15
materials:
  - code: MAT-PAINT-EXT-01
    unit: m2
    coverage_m2_per_liter: 8.5
"""
    pkg = parse_spec_content(yaml_content, filename="spec.yaml")
    assert isinstance(pkg, MaterialSpecPackage)
    assert pkg.name == "supershield-exterior"
    assert pkg.version == "2.1.0"
    assert pkg.manufacturer == "TOA Paint"
    assert pkg.properties["gloss_level"] == "semi-gloss"
    assert len(pkg.materials) == 1


def test_parse_spec_content_json():
    json_content = json.dumps({
        "name": "scg-smartboard",
        "version": "1.0.0",
        "manufacturer": "SCG",
        "category": "boards",
        "description": "Fiber cement board for wall cladding",
    })
    pkg = parse_spec_content(json_content, filename="spec.json")
    assert pkg.name == "scg-smartboard"
    assert pkg.manufacturer == "SCG"


def test_parse_spec_content_markdown():
    md_content = """---
name: cpack-roof-tile
version: 1.2.0
manufacturer: SCG Building Materials
category: roofing
---
# CPAC Roof Tile Specification

Manufacturer: SCG Building Materials
Category: roofing
Description: Concrete roof tiles with solar reflection.
"""
    pkg = parse_spec_content(md_content, filename="spec.md")
    assert pkg.name == "cpack-roof-tile"
    assert pkg.version == "1.2.0"
    assert pkg.manufacturer == "SCG Building Materials"


def test_parse_spec_content_invalid():
    # Empty content
    with pytest.raises(ValueError, match="empty"):
        parse_spec_content("", filename="spec.yaml")

    # Missing required 'name' field
    invalid_yaml = "version: 1.0.0\nmanufacturer: Unknown"
    with pytest.raises(ValueError, match="validation failed"):
        parse_spec_content(invalid_yaml, filename="spec.yaml")


def test_fetch_and_cache_package_success(tmp_path):
    cache_dir = tmp_path / "cache"
    client = SpecRegistryClient(cache_dir=cache_dir)

    mock_yaml = """
name: supershield-exterior
version: 1.0.0
manufacturer: TOA
category: paints
"""

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = mock_yaml.encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        pkg = client.fetch_package("@toa/supershield-exterior")
        assert pkg.name == "supershield-exterior"
        assert pkg.manufacturer == "TOA"
        assert mock_urlopen.called

        # Second call should load from cache without network request
        mock_urlopen.reset_mock()
        pkg_cached = client.fetch_package("@toa/supershield-exterior")
        assert pkg_cached.name == "supershield-exterior"
        assert not mock_urlopen.called


def test_offline_fallback(tmp_path):
    cache_dir = tmp_path / "cache"
    client = SpecRegistryClient(cache_dir=cache_dir)

    # Populate cache manually
    slug = client._get_pkg_slug("@toa/supershield-exterior")
    cached_pkg_dir = cache_dir / slug
    cached_pkg_dir.mkdir(parents=True, exist_ok=True)
    cached_manifest = cached_pkg_dir / "spec.yaml"
    cached_manifest.write_text("""
name: supershield-exterior
version: 1.0.0-offline
manufacturer: TOA Offline
""", encoding="utf-8")

    # Mock network error
    with patch("urllib.request.urlopen", side_effect=Exception("Network unreachable")):
        pkg = client.fetch_package("@toa/supershield-exterior", force=True)
        assert pkg.name == "supershield-exterior"
        assert pkg.version == "1.0.0-offline"
        assert pkg.manufacturer == "TOA Offline"


def test_install_package_to_local_specs(tmp_path):
    cache_dir = tmp_path / "cache"
    specs_dir = tmp_path / "specs"
    client = SpecRegistryClient(cache_dir=cache_dir)

    mock_yaml = """
name: supershield-exterior
version: 2.0.0
manufacturer: TOA Paint
category: paints
"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = mock_yaml.encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        target_dir = client.install_package("@toa/supershield-exterior", specs_dir=specs_dir)
        assert target_dir.exists()
        assert (target_dir / "spec.yaml").is_file()

        installed_manifest = (target_dir / "spec.yaml").read_text(encoding="utf-8")
        assert "supershield-exterior" in installed_manifest


def test_list_installed_packages(tmp_path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir(parents=True, exist_ok=True)

    pkg1_dir = specs_dir / "pkg1"
    pkg1_dir.mkdir(parents=True, exist_ok=True)
    (pkg1_dir / "spec.yaml").write_text("""
name: pkg1
version: 1.0.0
category: paints
manufacturer: Brand A
""", encoding="utf-8")

    pkg2_dir = specs_dir / "pkg2"
    pkg2_dir.mkdir(parents=True, exist_ok=True)
    (pkg2_dir / "spec.yaml").write_text("""
name: pkg2
version: 2.1.0
category: masonry
manufacturer: Brand B
""", encoding="utf-8")

    client = SpecRegistryClient()
    installed = client.list_installed_packages(specs_dir=specs_dir)
    assert len(installed) == 2

    names = [i["name"] for i in installed]
    assert "pkg1" in names
    assert "pkg2" in names


def test_cli_spec_add_and_list(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    specs_dir = tmp_path / "specs"

    monkeypatch.setenv("DEBIM_REGISTRY_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("COLUMNS", "200")

    mock_yaml = """
name: supershield-exterior
version: 1.5.0
manufacturer: TOA
category: paints
description: High-performance acrylic paint
"""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = mock_yaml.encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response):
        res_add = runner.invoke(app, [
            "spec", "add", "@toa/supershield-exterior",
            "-s", str(specs_dir),
            "--cache-dir", str(cache_dir),
        ], env={"COLUMNS": "200"})
        assert res_add.exit_code == 0
        assert "Installed Successfully" in res_add.output
        assert "supershield-exterior" in res_add.output

    res_list = runner.invoke(app, [
        "spec", "list",
        "-s", str(specs_dir),
    ], env={"COLUMNS": "200"})
    assert res_list.exit_code == 0
    assert "supershield-exterior" in res_list.output
    assert "1.5.0" in res_list.output
