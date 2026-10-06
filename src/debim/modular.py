"""
Modular manifest decomposition (split) and aggregation (bundle) engine for debim.
"""

from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple
import yaml

from debim.schema import ProjectManifest, derive_default_layer, load_manifest


def get_split_target_path(elem_dict: dict, elem_obj: Any, by: str = "system") -> str:
    """
    Determine relative modular file path for an element based on grouping strategy.
    
    Strategies:
      - 'storey': Groups elements by level/storey (e.g. models/storeys/l1.yaml)
      - 'system': Groups elements by building system and category (e.g. models/structure/columns.yaml)
    """
    if by == "storey":
        storey = None
        placement = getattr(elem_obj, "placement", None)
        if placement:
            storey = (
                getattr(placement, "storey", None)
                or getattr(placement, "base_storey", None)
            )
        if not storey:
            storey = "unassigned"
        clean_storey = str(storey).replace(" ", "_").lower()
        return f"models/storeys/{clean_storey}.yaml"

    # Default: by == "system"
    layer = getattr(elem_obj, "layer", None) or derive_default_layer(elem_obj)
    parts = [p.strip().lower() for p in layer.split("/") if p.strip()]

    if len(parts) >= 2:
        subsystem = parts[0]  # structure, architecture, mep, general
        category = parts[-1]  # columns, beams, walls, etc.

        # Normalize common category filenames
        if category in ("columns", "framing") and subsystem == "structure":
            category = "columns"
        elif category in ("beams",) and subsystem == "structure":
            category = "beams"
        elif category in ("footings", "substructure") and subsystem == "structure":
            category = "foundations"
        elif category in ("slabs",) and subsystem == "structure":
            category = "slabs"
        elif category in ("doors", "windows", "openings"):
            category = "doors_windows"
        elif category in ("roofs", "roofing"):
            category = "roofs"
        elif category in ("stairs",):
            category = "stairs"
        elif category in ("skirting", "cladding", "ceiling", "flooring", "finishes"):
            category = "finishes"

        return f"models/{subsystem}/{category}.yaml"
    elif len(parts) == 1:
        return f"models/{parts[0]}.yaml"

    return "models/general/elements.yaml"


def split_manifest(
    manifest_path: Path | str,
    output_dir: Optional[Path | str] = None,
    by: str = "system",
    backup: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Split a monolithic or partially modular project.yaml manifest into a standard
    modular directory structure under models/.

    Returns a summary dictionary describing generated modules and element counts.
    """
    src_path = Path(manifest_path)
    if not src_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {src_path}")

    # Load and validate full manifest
    manifest = load_manifest(src_path)

    base_out = Path(output_dir) if output_dir else src_path.parent
    root_out_path = base_out / "project.yaml"

    # Group elements by target module path
    grouped_elements: Dict[str, List[dict]] = {}
    for elem_obj in manifest.elements:
        elem_dict = elem_obj.model_dump(by_alias=True, exclude_none=True)
        target_rel = get_split_target_path(elem_dict, elem_obj, by=by)
        if target_rel not in grouped_elements:
            grouped_elements[target_rel] = []
        grouped_elements[target_rel].append(elem_dict)

    # Sort modules for deterministic output
    sorted_modules = dict(sorted(grouped_elements.items()))

    # Build new root manifest without elements, pointing to includes
    root_data = {
        "schema": manifest.schema_version,
        "project": manifest.project.model_dump(by_alias=True, exclude_none=True),
        "spatial_structure": manifest.spatial_structure.model_dump(by_alias=True, exclude_none=True),
        "grids": manifest.grids.model_dump(by_alias=True, exclude_none=True),
        "materials": [m.model_dump(by_alias=True, exclude_none=True) for m in manifest.materials],
        "includes": ["models/**/*.yaml"],
    }

    if not dry_run:
        base_out.mkdir(parents=True, exist_ok=True)

        # Backup original root manifest if overwriting
        if backup and root_out_path.exists() and root_out_path.resolve() == src_path.resolve():
            bak_path = src_path.with_name(f"{src_path.name}.bak")
            shutil.copy2(src_path, bak_path)

        # Write each module file
        for rel_file, elems in sorted_modules.items():
            full_module_path = base_out / rel_file
            full_module_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_module_path, "w", encoding="utf-8") as f:
                yaml.safe_dump({"elements": elems}, f, sort_keys=False, allow_unicode=True)

        # Write root project.yaml
        with open(root_out_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(root_data, f, sort_keys=False, allow_unicode=True)

    module_counts = {rel: len(elems) for rel, elems in sorted_modules.items()}

    return {
        "root_file": str(root_out_path),
        "modules": module_counts,
        "total_elements": len(manifest.elements),
        "strategy": by,
        "dry_run": dry_run,
    }


def bundle_manifest(
    manifest_path: Path | str,
    output_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """
    Bundle a modular project manifest (with includes:) into a single self-contained
    dictionary and optionally write to a standalone project.yaml file.
    """
    src_path = Path(manifest_path)
    if not src_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {src_path}")

    # load_manifest automatically aggregates and deep-merges all included modules
    manifest = load_manifest(src_path)
    data = manifest.model_dump(by_alias=True, exclude_none=True)

    # In bundled standalone artifact, omit includes directive
    data.pop("includes", None)

    # Order keys cleanly for readability
    ordered_keys = ["schema", "project", "spatial_structure", "grids", "materials", "elements"]
    bundled_dict = {}
    for k in ordered_keys:
        if k in data:
            bundled_dict[k] = data[k]
    for k, v in data.items():
        if k not in bundled_dict:
            bundled_dict[k] = v

    if output_path is not None:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            yaml.safe_dump(bundled_dict, f, sort_keys=False, allow_unicode=True)

    return bundled_dict
