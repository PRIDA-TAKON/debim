"""
Material Specification Registry Client & Package Manager
"""

import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field, ValidationError


class MaterialSpecPackage(BaseModel):
    """Data model for a material specification package manifest."""

    name: str = Field(..., description="Unique specification package identifier or name")
    version: str = Field("1.0.0", description="Semantic version string")
    description: Optional[str] = Field(None, description="Package description")
    category: Optional[str] = Field(None, description="Material category (e.g. paints, masonry, metals)")
    manufacturer: Optional[str] = Field(None, description="Manufacturer name")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Custom material properties")
    materials: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of material items or specifications"
    )
    raw_content: Optional[str] = Field(None, description="Raw downloaded spec content")
    manifest_filename: str = Field("spec.yaml", description="Primary manifest filename")


def resolve_package_urls(pkg_identifier: str) -> List[str]:
    """
    Resolve package identifier into candidate raw HTTP/HTTPS URLs.

    Supported formats:
    - Full URL: "https://raw.githubusercontent.com/org/repo/main/spec.yaml" or GitHub blob URL
    - Scoped package: "@toa/supershield-exterior"
    - GitHub shorthand org/repo/package: "toa/paints/supershield-exterior"
    - GitHub shorthand org/repo: "toa/supershield-exterior"
    """
    pkg_str = pkg_identifier.strip()
    if pkg_str.startswith("http://") or pkg_str.startswith("https://"):
        if "github.com/" in pkg_str and "/blob/" in pkg_str:
            raw_url = pkg_str.replace("github.com/", "raw.githubusercontent.com/").replace("/blob/", "/")
            return [raw_url]
        return [pkg_str]

    filenames = [
        "spec.yaml",
        "spec.yml",
        "spec.json",
        "spec.md",
        "package.yaml",
        "package.yml",
        "package.json",
    ]
    branches = ["main", "master"]

    if pkg_str.startswith("@"):
        clean_str = pkg_str[1:]
        parts = clean_str.split("/", 1)
        if len(parts) == 2:
            scope, pkg_name = parts[0], parts[1]
            candidates = []
            for b in branches:
                for fn in filenames:
                    candidates.append(f"https://raw.githubusercontent.com/{scope}/{pkg_name}/{b}/{fn}")
                    candidates.append(
                        f"https://raw.githubusercontent.com/{scope}/debim-specs/{b}/packages/{pkg_name}/{fn}"
                    )
                    candidates.append(
                        f"https://raw.githubusercontent.com/{scope}/materials/{b}/{pkg_name}/{fn}"
                    )
            return candidates
        else:
            scope = "debim"
            pkg_name = clean_str
            candidates = []
            for b in branches:
                for fn in filenames:
                    candidates.append(f"https://raw.githubusercontent.com/{scope}/{pkg_name}/{b}/{fn}")
            return candidates

    parts = [p for p in pkg_str.split("/") if p]
    if len(parts) == 2:
        org, repo = parts[0], parts[1]
        candidates = []
        for b in branches:
            for fn in filenames:
                candidates.append(f"https://raw.githubusercontent.com/{org}/{repo}/{b}/{fn}")
        return candidates
    elif len(parts) >= 3:
        org, repo = parts[0], parts[1]
        subpath = "/".join(parts[2:])
        candidates = []
        for b in branches:
            for fn in filenames:
                candidates.append(
                    f"https://raw.githubusercontent.com/{org}/{repo}/{b}/{subpath}/{fn}"
                )
        return candidates

    candidates = []
    for b in branches:
        for fn in filenames:
            candidates.append(f"https://raw.githubusercontent.com/debim-packages/{pkg_str}/{b}/{fn}")
    return candidates


def _parse_markdown_spec(content: str) -> Dict[str, Any]:
    """Parse Markdown spec document with optional YAML frontmatter or title headers."""
    data: Dict[str, Any] = {}
    lines = content.strip().splitlines()

    if lines and lines[0].strip() == "---":
        fm_lines = []
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            fm_lines.append(lines[i])
            i += 1
        if i < len(lines):
            try:
                fm_data = yaml.safe_load("\n".join(fm_lines))
                if isinstance(fm_data, dict):
                    data.update(fm_data)
            except Exception:
                pass

    if "name" not in data:
        for line in lines:
            if line.startswith("# "):
                data["name"] = line[2:].strip().lower().replace(" ", "-")
                break

    for line in lines:
        if ":" in line and not line.startswith("http") and not line.startswith("#"):
            k, v = line.split(":", 1)
            k_clean = k.strip().lower().replace(" ", "_")
            v_clean = v.strip()
            if k_clean in ("manufacturer", "category", "version", "description") and k_clean not in data:
                data[k_clean] = v_clean

    return data


def parse_spec_content(content: str, filename: str = "spec.yaml") -> MaterialSpecPackage:
    """
    Parse raw Markdown, YAML, or JSON content into a validated MaterialSpecPackage.
    Raises ValueError or ValidationError if invalid.
    """
    if not content or not content.strip():
        raise ValueError("Specification content is empty")

    ext = Path(filename).suffix.lower()
    data: Dict[str, Any] = {}

    if ext in (".yaml", ".yml") or ("name:" in content and ext not in (".json", ".md")):
        try:
            parsed = yaml.safe_load(content)
            if isinstance(parsed, dict):
                data = parsed
        except Exception as e:
            if ext in (".yaml", ".yml"):
                raise ValueError(f"Invalid YAML content: {e}")

    if not data and (ext == ".json" or content.strip().startswith("{")):
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                data = parsed
        except Exception as e:
            if ext == ".json":
                raise ValueError(f"Invalid JSON content: {e}")

    if not data and (ext == ".md" or "---" in content or "# " in content):
        data = _parse_markdown_spec(content)

    if not data:
        try:
            parsed = yaml.safe_load(content)
            if isinstance(parsed, dict):
                data = parsed
        except Exception:
            pass

    if not data or not isinstance(data, dict):
        raise ValueError("Could not parse specification package into structured manifest dictionary")

    data_copy = dict(data)
    data_copy["raw_content"] = content
    data_copy["manifest_filename"] = filename

    try:
        return MaterialSpecPackage.model_validate(data_copy)
    except ValidationError as e:
        raise ValueError(f"Specification package schema validation failed: {e}")


class SpecRegistryClient:
    """Client for fetching, caching, and installing material specification packages."""

    def __init__(self, cache_dir: Optional[Path] = None):
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            env_dir = os.getenv("DEBIM_REGISTRY_CACHE_DIR")
            if env_dir:
                self.cache_dir = Path(env_dir)
            else:
                self.cache_dir = Path.home() / ".debim" / "registry_cache"

        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_pkg_slug(self, pkg_identifier: str) -> str:
        s = pkg_identifier.strip().lstrip("@")
        s = re.sub(r"[^a-zA-Z0-9_\-\./]", "_", s)
        s = s.replace("/", "__")
        return s

    def get_cache_path(self, pkg_identifier: str) -> Path:
        slug = self._get_pkg_slug(pkg_identifier)
        return self.cache_dir / slug

    def fetch_package(self, pkg_identifier: str, force: bool = False) -> MaterialSpecPackage:
        cache_pkg_dir = self.get_cache_path(pkg_identifier)

        if not force and cache_pkg_dir.exists():
            for fn in ["spec.yaml", "spec.yml", "spec.json", "spec.md", "package.yaml"]:
                manifest_file = cache_pkg_dir / fn
                if manifest_file.is_file():
                    try:
                        content = manifest_file.read_text(encoding="utf-8")
                        pkg = parse_spec_content(content, filename=fn)
                        return pkg
                    except Exception:
                        pass

        candidate_urls = resolve_package_urls(pkg_identifier)
        last_error = None
        fetched_content = None
        used_filename = "spec.yaml"

        headers = {"User-Agent": "debim-registry-client/1.0 (declarative-bim)"}

        for url in candidate_urls:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        fetched_content = resp.read().decode("utf-8")
                        used_filename = Path(url).name
                        break
            except Exception as e:
                last_error = e

        if fetched_content is None:
            if cache_pkg_dir.exists():
                for fn in ["spec.yaml", "spec.yml", "spec.json", "spec.md"]:
                    manifest_file = cache_pkg_dir / fn
                    if manifest_file.is_file():
                        content = manifest_file.read_text(encoding="utf-8")
                        return parse_spec_content(content, filename=fn)
            raise RuntimeError(
                f"Failed to fetch package '{pkg_identifier}' from remote repositories. "
                f"Last error: {last_error}"
            )

        pkg = parse_spec_content(fetched_content, filename=used_filename)

        cache_pkg_dir.mkdir(parents=True, exist_ok=True)
        out_file = cache_pkg_dir / used_filename
        out_file.write_text(fetched_content, encoding="utf-8")

        meta_yaml = cache_pkg_dir / "spec.yaml"
        if not meta_yaml.exists():
            clean_dict = pkg.model_dump(exclude_none=True, exclude={"raw_content"})
            meta_yaml.write_text(
                yaml.safe_dump(clean_dict, sort_keys=False, allow_unicode=True), encoding="utf-8"
            )

        return pkg

    def install_package(
        self,
        pkg_identifier: str,
        specs_dir: Path = Path("specs"),
        force: bool = False,
    ) -> Path:
        pkg = self.fetch_package(pkg_identifier, force=force)

        pkg_slug = pkg.name if pkg.name else self._get_pkg_slug(pkg_identifier)
        pkg_slug = re.sub(r"[^a-zA-Z0-9_\-]", "_", pkg_slug)

        target_dir = specs_dir / pkg_slug
        target_dir.mkdir(parents=True, exist_ok=True)

        manifest_name = pkg.manifest_filename or "spec.yaml"
        target_manifest = target_dir / manifest_name

        if pkg.raw_content:
            target_manifest.write_text(pkg.raw_content, encoding="utf-8")
        else:
            clean_dict = pkg.model_dump(exclude_none=True, exclude={"raw_content"})
            target_manifest.write_text(
                yaml.safe_dump(clean_dict, sort_keys=False, allow_unicode=True), encoding="utf-8"
            )

        if manifest_name != "spec.yaml":
            clean_dict = pkg.model_dump(exclude_none=True, exclude={"raw_content"})
            (target_dir / "spec.yaml").write_text(
                yaml.safe_dump(clean_dict, sort_keys=False, allow_unicode=True), encoding="utf-8"
            )

        return target_dir

    def list_installed_packages(self, specs_dir: Path = Path("specs")) -> List[Dict[str, Any]]:
        installed = []
        if not specs_dir.exists() or not specs_dir.is_dir():
            return installed

        for pkg_dir in sorted(specs_dir.iterdir()):
            if pkg_dir.is_dir():
                for fn in ["spec.yaml", "spec.yml", "spec.json", "spec.md", "package.yaml"]:
                    manifest_file = pkg_dir / fn
                    if manifest_file.is_file():
                        try:
                            content = manifest_file.read_text(encoding="utf-8")
                            pkg = parse_spec_content(content, filename=fn)
                            installed.append(
                                {
                                    "name": pkg.name,
                                    "version": pkg.version,
                                    "category": pkg.category or "-",
                                    "manufacturer": pkg.manufacturer or "-",
                                    "description": pkg.description or "-",
                                    "path": str(pkg_dir),
                                }
                            )
                            break
                        except Exception:
                            pass
        return installed
