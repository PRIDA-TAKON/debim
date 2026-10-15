"""
Modular manifest decomposition (split) and aggregation (bundle) engine for debim.
"""

from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Tuple
import yaml

import copy
from debim.compat import BaseModel, Field, RootModel, field_validator, model_validator
from debim.schema import ProjectManifest, derive_default_layer, load_manifest


def _to_dict(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(by_alias=True, exclude_none=True)
    elif isinstance(obj, dict):
        return copy.deepcopy(obj)
    return obj


def expand_macro_elements(manifest_or_data: Any) -> Any:
    """
    AST preprocessor for framing array macros (ColumnGrid and BeamBay generators).
    Expands `macro_elements:` definitions into discrete `IfcColumn` and `IfcBeam` elements.
    """
    is_manifest_obj = False
    if hasattr(manifest_or_data, "macro_elements"):
        is_manifest_obj = True
        if getattr(manifest_or_data, "_macro_elements_expanded", False):
            return manifest_or_data
        data = manifest_or_data.model_dump(by_alias=True, exclude_none=True)
    elif isinstance(manifest_or_data, dict):
        if manifest_or_data.get("_macro_elements_expanded"):
            return manifest_or_data
        data = manifest_or_data
    else:
        return manifest_or_data

    macro_elements = data.get("macro_elements", []) or []
    if not macro_elements:
        if is_manifest_obj:
            return manifest_or_data
        return data

    existing_elements = list(data.get("elements", []) or [])
    expanded_elements = []

    for macro in macro_elements:
        m_dict = _to_dict(macro)
        if not isinstance(m_dict, dict):
            continue

        m_type = str(m_dict.get("type") or m_dict.get("class") or "").strip()
        if m_type in ("ColumnGrid", "column_grid"):
            cols = _expand_column_grid(m_dict)
            expanded_elements.extend(cols)
        elif m_type in ("BeamBay", "beam_bay", "BeamGrid", "beam_grid"):
            beams = _expand_beam_bay(m_dict)
            expanded_elements.extend(beams)

    data["elements"] = existing_elements + expanded_elements
    data["_macro_elements_expanded"] = True

    if is_manifest_obj:
        from debim.schema import ProjectManifest
        res = ProjectManifest.model_validate(data)
        object.__setattr__(res, "_macro_elements_expanded", True) if hasattr(res, "__dict__") else setattr(res, "_macro_elements_expanded", True)
        return res
    return data


def _normalize_except_point(pt: Any) -> Tuple[str, str]:
    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
        return (str(pt[0]), str(pt[1]))
    return (str(pt), "")


def _expand_column_grid(macro: dict) -> List[dict]:
    grids_x = [str(x) for x in macro.get("grids_x", [])]
    grids_y = [str(y) for y in macro.get("grids_y", [])]
    material = macro.get("material", "CONCRETE")
    tag_prefix = macro.get("tag_prefix", "C_")
    if tag_prefix is None:
        tag_prefix = "C_"

    raw_except = macro.get("except_points") or []
    except_points = {_normalize_except_point(p) for p in raw_except}

    # Determine storey pairs
    storeys_raw = macro.get("storeys")
    storey_pairs: List[Tuple[str, str]] = []

    if storeys_raw and isinstance(storeys_raw, list):
        if storeys_raw and isinstance(storeys_raw[0], (list, tuple)):
            for pair in storeys_raw:
                if len(pair) >= 2:
                    storey_pairs.append((str(pair[0]), str(pair[1])))
                elif len(pair) == 1:
                    storey_pairs.append((str(pair[0]), str(pair[0])))
        elif len(storeys_raw) >= 2:
            for i in range(len(storeys_raw) - 1):
                storey_pairs.append((str(storeys_raw[i]), str(storeys_raw[i+1])))
        elif len(storeys_raw) == 1:
            s = str(storeys_raw[0])
            storey_pairs.append((s, s))
    else:
        b_st = macro.get("base_storey") or macro.get("storey") or "L1"
        t_st = macro.get("top_storey") or macro.get("storey") or "L2"
        storey_pairs.append((str(b_st), str(t_st)))

    fallback_profile = macro.get("profile") or {"shape": "BOX", "width": 0.30, "depth": 0.30}
    profiles_cfg = macro.get("profiles")
    reinforcement = macro.get("reinforcement")
    layer = macro.get("layer")

    columns = []

    for base_st, top_st in storey_pairs:
        # Resolve profile for this storey pair
        prof = None
        if isinstance(profiles_cfg, dict):
            prof = profiles_cfg.get(base_st) or profiles_cfg.get(f"{base_st}_{top_st}") or profiles_cfg.get("default")
        elif profiles_cfg is not None:
            prof = profiles_cfg

        if not prof:
            prof = fallback_profile

        prof_dict = _to_dict(prof)
        reinf_dict = _to_dict(reinforcement) if reinforcement else None

        for gx in grids_x:
            for gy in grids_y:
                if (gx, gy) in except_points:
                    continue

                if len(storey_pairs) > 1 or macro.get("storeys"):
                    tag = f"{tag_prefix}{gx}_{gy}_{base_st}"
                else:
                    tag = f"{tag_prefix}{gx}_{gy}"

                elem = {
                    "class": "IfcColumn",
                    "tag": tag,
                    "material": material,
                    "profile": prof_dict,
                    "placement": {
                        "grid": [gx, gy],
                        "base_storey": base_st,
                        "top_storey": top_st,
                    },
                }
                if reinf_dict:
                    elem["reinforcement"] = reinf_dict
                if layer:
                    elem["layer"] = layer

                columns.append(elem)

    return columns


def _normalize_except_beam(b: Any) -> Tuple[Tuple[str, str], Tuple[str, str]]:
    if isinstance(b, (list, tuple)) and len(b) >= 2:
        p1 = _normalize_except_point(b[0])
        p2 = _normalize_except_point(b[1])
        return (p1, p2)
    return (("", ""), ("", ""))


def _expand_beam_bay(macro: dict) -> List[dict]:
    grids_x = [str(x) for x in macro.get("grids_x", [])]
    grids_y = [str(y) for y in macro.get("grids_y", [])]
    material = macro.get("material", "CONCRETE")
    tag_prefix = macro.get("tag_prefix", "B_")
    if tag_prefix is None:
        tag_prefix = "B_"

    direction = str(macro.get("direction", "BOTH")).upper()

    raw_except_pts = macro.get("except_points") or []
    except_points = {_normalize_except_point(p) for p in raw_except_pts}

    raw_except_bm = macro.get("except_beams") or []
    except_beams = set()
    for eb in raw_except_bm:
        p1, p2 = _normalize_except_beam(eb)
        except_beams.add((p1, p2))
        except_beams.add((p2, p1))

    storeys_raw = macro.get("storeys")
    if storeys_raw and isinstance(storeys_raw, list):
        storeys = [str(s) for s in storeys_raw]
    elif macro.get("storey"):
        storeys = [str(macro["storey"])]
    else:
        storeys = ["L1"]

    fallback_profile = macro.get("profile") or {"shape": "BOX", "width": 0.20, "depth": 0.40}
    profiles_cfg = macro.get("profiles")
    reinforcement = macro.get("reinforcement")
    layer = macro.get("layer")

    beams = []

    for st in storeys:
        reinf_dict = _to_dict(reinforcement) if reinforcement else None

        # Beams along X direction
        if direction in ("X", "BOTH"):
            prof_x = None
            if isinstance(profiles_cfg, dict):
                prof_x = (
                    profiles_cfg.get(f"{st}_X")
                    or profiles_cfg.get(st)
                    or profiles_cfg.get("X")
                    or profiles_cfg.get("x")
                )
            elif profiles_cfg is not None:
                prof_x = profiles_cfg

            if not prof_x:
                prof_x = fallback_profile
            prof_x_dict = _to_dict(prof_x)

            for gy in grids_y:
                for i in range(len(grids_x) - 1):
                    gx1 = grids_x[i]
                    gx2 = grids_x[i+1]
                    pt1 = (gx1, gy)
                    pt2 = (gx2, gy)

                    if pt1 in except_points or pt2 in except_points:
                        continue
                    if (pt1, pt2) in except_beams or (pt2, pt1) in except_beams:
                        continue

                    if len(storeys) > 1 or macro.get("storeys"):
                        tag = f"{tag_prefix}{gx1}_{gx2}_{gy}_{st}"
                    else:
                        tag = f"{tag_prefix}{gx1}_{gx2}_{gy}"

                    elem = {
                        "class": "IfcBeam",
                        "tag": tag,
                        "material": material,
                        "profile": prof_x_dict,
                        "placement": {
                            "from_grid": [gx1, gy],
                            "to_grid": [gx2, gy],
                            "storey": st,
                        },
                    }
                    if reinf_dict:
                        elem["reinforcement"] = reinf_dict
                    if layer:
                        elem["layer"] = layer

                    beams.append(elem)

        # Beams along Y direction
        if direction in ("Y", "BOTH"):
            prof_y = None
            if isinstance(profiles_cfg, dict):
                prof_y = (
                    profiles_cfg.get(f"{st}_Y")
                    or profiles_cfg.get(st)
                    or profiles_cfg.get("Y")
                    or profiles_cfg.get("y")
                )
            elif profiles_cfg is not None:
                prof_y = profiles_cfg

            if not prof_y:
                prof_y = fallback_profile
            prof_y_dict = _to_dict(prof_y)

            for gx in grids_x:
                for j in range(len(grids_y) - 1):
                    gy1 = grids_y[j]
                    gy2 = grids_y[j+1]
                    pt1 = (gx, gy1)
                    pt2 = (gx, gy2)

                    if pt1 in except_points or pt2 in except_points:
                        continue
                    if (pt1, pt2) in except_beams or (pt2, pt1) in except_beams:
                        continue

                    if len(storeys) > 1 or macro.get("storeys"):
                        tag = f"{tag_prefix}{gx}_{gy1}_{gy2}_{st}"
                    else:
                        tag = f"{tag_prefix}{gx}_{gy1}_{gy2}"

                    elem = {
                        "class": "IfcBeam",
                        "tag": tag,
                        "material": material,
                        "profile": prof_y_dict,
                        "placement": {
                            "from_grid": [gx, gy1],
                            "to_grid": [gx, gy2],
                            "storey": st,
                        },
                    }
                    if reinf_dict:
                        elem["reinforcement"] = reinf_dict
                    if layer:
                        elem["layer"] = layer

                    beams.append(elem)

    return beams


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
