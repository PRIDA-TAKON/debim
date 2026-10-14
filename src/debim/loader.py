"""
Native .debim file extension loader with zero-dependency standalone YAML parser fallback.
Enables pure-Python VM/sandbox environments to load and parse declarative BIM models directly.
"""

import copy
import glob
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union, IO

# Try importing pyyaml if available
try:
    import yaml
    _HAS_PYYAML = True
except ImportError:
    yaml = None  # type: ignore
    _HAS_PYYAML = False


def _parse_scalar(val_str: str) -> Any:
    """Parse a single YAML scalar string value into Python primitive types."""
    v = val_str.strip()
    if not v:
        return None

    # Strip inline comments if not inside quotes
    if not (v.startswith('"') and v.endswith('"')) and not (v.startswith("'") and v.endswith("'")):
        if " #" in v:
            v = v.split(" #")[0].strip()

    if not v:
        return None

    # Quoted strings
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        if v.startswith('"'):
            # Double-quoted string JSON unescape
            try:
                return json.loads(v)
            except Exception:
                return v[1:-1]
        else:
            return v[1:-1]

    # Inline JSON flows [ ... ] or { ... }
    if (v.startswith("[") and v.endswith("]")) or (v.startswith("{") and v.endswith("}")):
        try:
            return _parse_flow(v)
        except Exception:
            pass

    # Booleans
    v_lower = v.lower()
    if v_lower in ("true", "yes", "on"):
        return True
    if v_lower in ("false", "no", "off"):
        return False

    # Nulls
    if v_lower in ("null", "none", "~"):
        return None

    # Integers
    if re.match(r"^[-+]?\d+$", v):
        try:
            return int(v)
        except ValueError:
            pass

    # Floats
    if re.match(r"^[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?$", v):
        try:
            return float(v)
        except ValueError:
            pass

    return v


def _parse_flow(v: str) -> Any:
    """Parse inline YAML/JSON flow constructs like [1, 2] or {a: 1, b: 2}."""
    v = v.strip()
    if not v:
        return None

    # Standard JSON attempt first
    try:
        # Convert unquoted keys in { key: val } to JSON quoted keys
        json_candidate = v
        # Fix unquoted dict keys: e.g. { shape: BOX, width: 0.25 } -> { "shape": "BOX", "width": 0.25 }
        if json_candidate.startswith("{") or json_candidate.startswith("["):
            # Simple conversion if standard json
            return json.loads(json_candidate)
    except Exception:
        pass

    # Custom flow parser for arrays [ ... ]
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        items = _split_flow_items(inner)
        return [_parse_scalar(item) for item in items]

    # Custom flow parser for dicts { ... }
    if v.startswith("{") and v.endswith("}"):
        inner = v[1:-1].strip()
        if not inner:
            return {}
        items = _split_flow_items(inner)
        res_dict = {}
        for item in items:
            if ":" in item:
                k, val = item.split(":", 1)
                k_clean = k.strip().strip("\"'")
                res_dict[k_clean] = _parse_scalar(val)
        return res_dict

    return _parse_scalar(v)


def _split_flow_items(s: str) -> List[str]:
    """Split comma-separated flow items respecting nested brackets/quotes."""
    items = []
    current = []
    depth_bracket = 0
    depth_brace = 0
    in_quote = False
    quote_char = ""

    for char in s:
        if in_quote:
            current.append(char)
            if char == quote_char:
                in_quote = False
        else:
            if char in ('"', "'"):
                in_quote = True
                quote_char = char
                current.append(char)
            elif char == "[":
                depth_bracket += 1
                current.append(char)
            elif char == "]":
                depth_bracket -= 1
                current.append(char)
            elif char == "{":
                depth_brace += 1
                current.append(char)
            elif char == "}":
                depth_brace -= 1
                current.append(char)
            elif char == "," and depth_bracket == 0 and depth_brace == 0:
                items.append("".join(current).strip())
                current = []
            else:
                current.append(char)

    if current:
        items.append("".join(current).strip())

    return items


def _pure_yaml_parse(content_str: str) -> Any:
    """
    Pure-Python fallback YAML subset parser for zero-dependency environments.
    Parses YAML maps, sequences, scalar types, inline flow arrays/maps, comments,
    and nested indentation.
    """
    if not content_str or not content_str.strip():
        return {}

    # Fast check if raw JSON
    trimmed = content_str.strip()
    if (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
        try:
            return json.loads(trimmed)
        except Exception:
            pass

    lines = content_str.splitlines()

    # Pre-clean lines: calculate indent, keep raw content, ignore empty/comment lines
    cleaned_lines: List[Tuple[int, str]] = []
    for line in lines:
        # Check comment before stripping
        l_no_trail = line.rstrip()
        if not l_no_trail:
            continue
        l_strip = l_no_trail.lstrip()
        if l_strip.startswith("#"):
            continue

        indent = len(l_no_trail) - len(l_strip)
        cleaned_lines.append((indent, l_strip))

    if not cleaned_lines:
        return {}

    def parse_block(idx: int, min_indent: int) -> Tuple[Any, int]:
        """Parse block starting at cleaned_lines[idx] with indentation >= min_indent."""
        if idx >= len(cleaned_lines):
            return None, idx

        first_indent, first_line = cleaned_lines[idx]
        if first_indent < min_indent:
            return None, idx

        # Determine if sequence (list) or mapping (dict)
        is_seq = first_line.startswith("- ") or first_line == "-"

        if is_seq:
            res_list = []
            curr_idx = idx
            while curr_idx < len(cleaned_lines):
                indent, line = cleaned_lines[curr_idx]
                if indent < first_indent:
                    break
                if indent > first_indent:
                    # Belongs to previous item, shouldn't happen at top of list item loop
                    curr_idx += 1
                    continue

                if not (line.startswith("- ") or line == "-"):
                    break

                # Process sequence item
                item_content = line[1:].strip() if line.startswith("- ") else line[1:].strip()
                curr_idx += 1

                if not item_content:
                    # List item with nested child on next line
                    if curr_idx < len(cleaned_lines) and cleaned_lines[curr_idx][0] > indent:
                        child_val, curr_idx = parse_block(curr_idx, cleaned_lines[curr_idx][0])
                        res_list.append(child_val)
                    else:
                        res_list.append(None)
                elif item_content.startswith("- "):
                    # Nested sequence on same line or offset
                    sub_str = item_content
                    item_val = _parse_scalar(sub_str)
                    res_list.append(item_val)
                elif ":" in item_content and not (item_content.startswith("[") or item_content.startswith("{")):
                    # List item is a dict entry, e.g. "- class: IfcColumn"
                    k, v_str = item_content.split(":", 1)
                    k_clean = k.strip().strip("\"'")
                    v_str = v_str.strip()

                    elem_dict = {}
                    if v_str:
                        elem_dict[k_clean] = _parse_scalar(v_str)
                    else:
                        if curr_idx < len(cleaned_lines) and cleaned_lines[curr_idx][0] > indent:
                            val_child, curr_idx = parse_block(curr_idx, cleaned_lines[curr_idx][0])
                            elem_dict[k_clean] = val_child
                        else:
                            elem_dict[k_clean] = None

                    # Collect additional dict fields at indent > first_indent
                    while curr_idx < len(cleaned_lines):
                        next_indent, next_line = cleaned_lines[curr_idx]
                        if next_indent <= indent:
                            break
                        if ":" in next_line and not (next_line.startswith("- ") or next_line == "-"):
                            nk, nv_str = next_line.split(":", 1)
                            nk_clean = nk.strip().strip("\"'")
                            nv_str = nv_str.strip()
                            curr_idx += 1
                            if nv_str:
                                elem_dict[nk_clean] = _parse_scalar(nv_str)
                            else:
                                if curr_idx < len(cleaned_lines) and cleaned_lines[curr_idx][0] > next_indent:
                                    sub_val, curr_idx = parse_block(curr_idx, cleaned_lines[curr_idx][0])
                                    elem_dict[nk_clean] = sub_val
                                else:
                                    elem_dict[nk_clean] = None
                        else:
                            break
                    res_list.append(elem_dict)
                else:
                    # Simple scalar item in sequence
                    res_list.append(_parse_scalar(item_content))

            return res_list, curr_idx

        else:
            # Mapping (dict)
            res_dict = {}
            curr_idx = idx
            while curr_idx < len(cleaned_lines):
                indent, line = cleaned_lines[curr_idx]
                if indent < first_indent:
                    break
                if indent > first_indent:
                    curr_idx += 1
                    continue

                if ":" not in line or line.startswith("- "):
                    break

                # Split key and value
                k, v_str = line.split(":", 1)
                k_clean = k.strip().strip("\"'")
                v_str = v_str.strip()
                curr_idx += 1

                if v_str:
                    res_dict[k_clean] = _parse_scalar(v_str)
                else:
                    # Value is nested block on subsequent lines
                    if curr_idx < len(cleaned_lines) and cleaned_lines[curr_idx][0] > indent:
                        child_indent = cleaned_lines[curr_idx][0]
                        child_val, curr_idx = parse_block(curr_idx, child_indent)
                        res_dict[k_clean] = child_val
                    else:
                        res_dict[k_clean] = None

            return res_dict, curr_idx

    result, _ = parse_block(0, 0)
    return result if result is not None else {}


def parse_debim(content_or_stream: Union[str, bytes, IO[Any]]) -> Any:
    """
    Parse declarative .debim / YAML / JSON content into Python dictionaries or lists.
    Uses PyYAML if installed; falls back to standalone zero-dependency pure-Python parser.
    """
    if hasattr(content_or_stream, "read"):
        content_str = content_or_stream.read()  # type: ignore
        if isinstance(content_str, bytes):
            content_str = content_str.decode("utf-8")
    elif isinstance(content_or_stream, bytes):
        content_str = content_or_stream.decode("utf-8")
    else:
        content_str = str(content_or_stream)

    if _HAS_PYYAML and yaml is not None:
        try:
            res = yaml.safe_load(content_str)
            return res if res is not None else {}
        except Exception:
            pass

    return _pure_yaml_parse(content_str)


def resolve_default_manifest_path(path: Optional[Union[Path, str]] = None) -> Path:
    """
    Auto-detect and resolve default .debim or .yaml manifest file paths.

    If path is specified, returns Path(path).resolve() if it exists, or Path(path) if it doesn't.
    If path is None, searches current working directory for candidates in priority order:
      1. project.debim
      2. house.debim
      3. main.debim
      4. project.yaml
      5. project.debim.yaml
      6. manifest.debim
      7. manifest.yaml

    Returns resolved existing Path if candidate found, or Path("project.debim").
    """
    if path is not None:
        p = Path(path)
        return p.resolve() if p.exists() else p

    candidates = [
        "project.debim",
        "house.debim",
        "main.debim",
        "project.yaml",
        "project.debim.yaml",
        "manifest.debim",
        "manifest.yaml",
    ]

    cwd = Path.cwd()
    for candidate in candidates:
        candidate_path = cwd / candidate
        if candidate_path.exists():
            return candidate_path.resolve()

    return Path("project.debim")


def load_debim_file(
    filepath: Union[Path, str],
    visited: Optional[Set[Path]] = None,
) -> Dict[str, Any]:
    """
    Load a .debim / YAML / JSON manifest file from disk, automatically resolving
    modular `includes` glob patterns across sub-manifest files.
    """
    file_path = Path(filepath).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {file_path}")

    if visited is None:
        visited = set()

    if file_path in visited:
        raise ValueError(f"Circular include detected: {file_path}")

    visited.add(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        data = parse_debim(f) or {}

    if isinstance(data, list):
        data = {"elements": data}
    elif not isinstance(data, dict):
        raise ValueError(f"Manifest file {file_path} must be a dictionary, list, or object")

    base_dir = file_path.parent
    includes = data.get("includes", []) or []

    if not includes:
        return data

    # Process includes
    merged_materials = list(data.get("materials", []) or [])
    mat_ids = {m["id"] for m in merged_materials if isinstance(m, dict) and "id" in m}

    merged_elements = list(data.get("elements", []) or [])
    railways_list = list(data.get("railways", []) or [])
    if railways_list:
        merged_elements.extend(railways_list)
    merged_proxies = list(data.get("proxies", []) or [])

    spatial_structure = data.get("spatial_structure", {}) or {}
    merged_storeys = list(spatial_structure.get("storeys", []) or [])
    storey_ids = {s["id"] for s in merged_storeys if isinstance(s, dict) and "id" in s}

    grids_data = data.get("grids", {}) or {}
    merged_axes_x = {str(k): float(v) for k, v in (grids_data.get("axes_x", {}) or {}).items()}
    merged_axes_y = {str(k): float(v) for k, v in (grids_data.get("axes_y", {}) or {}).items()}

    for pattern in includes:
        if not pattern or not isinstance(pattern, str) or not pattern.strip():
            continue

        is_glob = any(char in pattern for char in ["*", "?", "["])
        if is_glob:
            matching_paths = sorted(base_dir.glob(pattern))
            if not matching_paths:
                raise FileNotFoundError(f"No files matched include pattern: {pattern}")
        else:
            inc_path = base_dir / pattern
            if not inc_path.exists():
                raise FileNotFoundError(f"Included file not found: {pattern}")
            matching_paths = [inc_path]

        for inc_file in matching_paths:
            inc_data = load_debim_file(inc_file, visited=set(visited))

            # Merge sub-manifest
            sub_mats = list(inc_data.get("materials", []) or [])
            for m in sub_mats:
                if isinstance(m, dict) and "id" in m:
                    if m["id"] not in mat_ids:
                        mat_ids.add(m["id"])
                        merged_materials.append(m)
                else:
                    merged_materials.append(m)

            sub_elems = list(inc_data.get("elements", []) or [])
            merged_elements.extend(sub_elems)

            sub_proxies = list(inc_data.get("proxies", []) or [])
            merged_proxies.extend(sub_proxies)

            sub_storeys = []
            if "spatial_structure" in inc_data and isinstance(inc_data["spatial_structure"], dict):
                sub_storeys.extend(inc_data["spatial_structure"].get("storeys", []) or [])
            if "storeys" in inc_data and isinstance(inc_data["storeys"], list):
                sub_storeys.extend(inc_data["storeys"] or [])

            for s in sub_storeys:
                if isinstance(s, dict) and "id" in s:
                    if s["id"] not in storey_ids:
                        storey_ids.add(s["id"])
                        merged_storeys.append(s)
                else:
                    merged_storeys.append(s)

            if "grids" in inc_data and isinstance(inc_data["grids"], dict):
                sub_grids = inc_data["grids"]
                sub_x = sub_grids.get("axes_x", {}) or {}
                sub_y = sub_grids.get("axes_y", {}) or {}
                if isinstance(sub_x, dict):
                    for k, v in sub_x.items():
                        merged_axes_x[str(k)] = float(v)
                if isinstance(sub_y, dict):
                    for k, v in sub_y.items():
                        merged_axes_y[str(k)] = float(v)

    data["materials"] = merged_materials
    data["elements"] = merged_elements
    data["proxies"] = merged_proxies
    data["spatial_structure"] = {"storeys": merged_storeys}
    data["grids"] = {"axes_x": merged_axes_x, "axes_y": merged_axes_y}

    return data


def _remap_grid_pair(pair: Any, mapping_x: Dict[str, str], mapping_y: Dict[str, str]) -> Any:
    if not pair or not isinstance(pair, (list, tuple)) or len(pair) < 2:
        return pair
    gx, gy = str(pair[0]), str(pair[1])
    new_gx = mapping_x.get(gx, gx)
    new_gy = mapping_y.get(gy, gy)
    return [new_gx, new_gy] if isinstance(pair, list) else (new_gx, new_gy)


def _remap_placement_grids(placement: Dict[str, Any], mapping_x: Dict[str, str], mapping_y: Dict[str, str]) -> None:
    for key in ("grid", "top_grid", "from_grid", "to_grid", "grid_anchor", "grid_start", "grid_end"):
        if key in placement and placement[key]:
            placement[key] = _remap_grid_pair(placement[key], mapping_x, mapping_y)

    if "boundary" in placement and isinstance(placement["boundary"], list):
        new_b = []
        for pt in placement["boundary"]:
            new_b.append(_remap_grid_pair(pt, mapping_x, mapping_y))
        placement["boundary"] = new_b

    if "voids" in placement and isinstance(placement["voids"], list):
        new_v = []
        for loop in placement["voids"]:
            if isinstance(loop, list):
                new_loop = [_remap_grid_pair(pt, mapping_x, mapping_y) for pt in loop]
                new_v.append(new_loop)
            else:
                new_v.append(loop)
        placement["voids"] = new_v

    for key in ("waypoints", "path"):
        if key in placement and isinstance(placement[key], list):
            for item in placement[key]:
                if isinstance(item, dict) and "grid" in item and item["grid"]:
                    item["grid"] = _remap_grid_pair(item["grid"], mapping_x, mapping_y)

    if "openings" in placement and isinstance(placement["openings"], list):
        for op in placement["openings"]:
            if isinstance(op, dict):
                if "grid" in op and op["grid"]:
                    op["grid"] = _remap_grid_pair(op["grid"], mapping_x, mapping_y)
                if "boundary" in op and isinstance(op["boundary"], list):
                    op["boundary"] = [_remap_grid_pair(pt, mapping_x, mapping_y) for pt in op["boundary"]]


def expand_module_instances(manifest_or_data: Any) -> Any:
    """
    AST preprocessor for module macro expansion and grid replication.
    Expands `modules:` and `instances:` blocks into concrete elements.
    Accepts either a dict or a ProjectManifest object.
    """
    is_manifest_obj = False
    if hasattr(manifest_or_data, "modules") and hasattr(manifest_or_data, "instances"):
        is_manifest_obj = True
        data = manifest_or_data.model_dump(by_alias=True, exclude_none=True)
    elif isinstance(manifest_or_data, dict):
        data = manifest_or_data
    else:
        return manifest_or_data

    modules_raw = data.get("modules", []) or []
    instances_raw = data.get("instances", []) or []

    if not modules_raw or not instances_raw:
        if is_manifest_obj:
            return manifest_or_data
        return data

    modules_by_id = {}
    for mod in modules_raw:
        m_id = mod.get("id") if isinstance(mod, dict) else getattr(mod, "id", None)
        if m_id:
            modules_by_id[m_id] = mod

    grids_data = data.get("grids", {}) or {}
    global_axes_x_dict = grids_data.get("axes_x", {}) or {}
    global_axes_y_dict = grids_data.get("axes_y", {}) or {}

    global_x_axes = sorted(global_axes_x_dict.keys(), key=lambda k: global_axes_x_dict[k]) if global_axes_x_dict else []
    global_y_axes = sorted(global_axes_y_dict.keys(), key=lambda k: global_axes_y_dict[k]) if global_axes_y_dict else []

    existing_elements = list(data.get("elements", []) or [])
    existing_wall_keys = set()

    for elem in existing_elements:
        e_cls = elem.get("class") if isinstance(elem, dict) else getattr(elem, "class_", "")
        if e_cls == "IfcWall":
            place = elem.get("placement", {}) if isinstance(elem, dict) else getattr(elem, "placement", None)
            if place:
                st = place.get("storey") if isinstance(place, dict) else getattr(place, "storey", None)
                fg = place.get("from_grid") if isinstance(place, dict) else getattr(place, "from_grid", None)
                tg = place.get("to_grid") if isinstance(place, dict) else getattr(place, "to_grid", None)
                if st and fg and tg:
                    fg_t = (str(fg[0]), str(fg[1]))
                    tg_t = (str(tg[0]), str(tg[1]))
                    existing_wall_keys.add((st, frozenset([fg_t, tg_t])))

    expanded_elements = []

    for inst in instances_raw:
        inst_dict = inst if isinstance(inst, dict) else inst.model_dump(by_alias=True, exclude_none=True)
        module_id = inst_dict.get("module")
        replicate_cfg = inst_dict.get("replicate")

        if replicate_cfg:
            if isinstance(replicate_cfg, dict):
                r_module = replicate_cfg.get("module") or module_id
                count = replicate_cfg.get("count", 1)
                along = replicate_cfg.get("along", "grid_x")
                grid_x_mapping = replicate_cfg.get("grid_x_mapping")
                grid_y_mapping = replicate_cfg.get("grid_y_mapping")
                prefix_pattern = replicate_cfg.get("prefix_pattern", "U{index}_")
                party_wall_dedup = replicate_cfg.get("party_wall_deduplication", True)
            else:
                r_module = getattr(replicate_cfg, "module", module_id)
                count = getattr(replicate_cfg, "count", 1)
                along = getattr(replicate_cfg, "along", "grid_x")
                grid_x_mapping = getattr(replicate_cfg, "grid_x_mapping", None)
                grid_y_mapping = getattr(replicate_cfg, "grid_y_mapping", None)
                prefix_pattern = getattr(replicate_cfg, "prefix_pattern", "U{index}_")
                party_wall_dedup = getattr(replicate_cfg, "party_wall_deduplication", True)
            module_id = r_module
        else:
            count = 1
            along = "grid_x"
            grid_x_mapping = None
            grid_y_mapping = None
            prefix_pattern = inst_dict.get("id_prefix") or "U{index}_"
            party_wall_dedup = True

        if not module_id or module_id not in modules_by_id:
            continue

        target_module = modules_by_id[module_id]
        mod_dict = target_module if isinstance(target_module, dict) else target_module.model_dump(by_alias=True, exclude_none=True)
        mod_elements = mod_dict.get("elements", []) or []
        mod_local_grids = mod_dict.get("local_grids", {}) or {}

        local_x_dict = mod_local_grids.get("axes_x", {}) if isinstance(mod_local_grids, dict) else getattr(mod_local_grids, "axes_x", {})
        local_y_dict = mod_local_grids.get("axes_y", {}) if isinstance(mod_local_grids, dict) else getattr(mod_local_grids, "axes_y", {})

        local_x_axes = sorted(local_x_dict.keys(), key=lambda k: local_x_dict[k]) if local_x_dict else []
        local_y_axes = sorted(local_y_dict.keys(), key=lambda k: local_y_dict[k]) if local_y_dict else []

        num_bays_x = max(1, len(local_x_axes) - 1) if local_x_axes else 1
        num_bays_y = max(1, len(local_y_axes) - 1) if local_y_axes else 1

        for idx in range(1, count + 1):
            offset_i = idx - 1

            # Determine grid_x_mapping for this index
            mapping_x = {}
            if grid_x_mapping and len(grid_x_mapping) >= idx:
                item_x = grid_x_mapping[offset_i]
                if isinstance(item_x, dict):
                    if len(item_x) == 1 and isinstance(list(item_x.values())[0], dict):
                        item_x = list(item_x.values())[0]
                    mapping_x = {str(k): str(v) for k, v in item_x.items()}

            if not mapping_x:
                if along == "grid_x":
                    for p, loc_x in enumerate(local_x_axes):
                        target_p = p + offset_i * num_bays_x
                        if global_x_axes and target_p < len(global_x_axes):
                            mapping_x[str(loc_x)] = str(global_x_axes[target_p])
                        elif str(loc_x).isdigit():
                            mapping_x[str(loc_x)] = str(int(loc_x) + offset_i * num_bays_x)
                        elif len(str(loc_x)) == 1 and str(loc_x).isalpha():
                            mapping_x[str(loc_x)] = chr(ord(loc_x) + offset_i * num_bays_x)
                        else:
                            mapping_x[str(loc_x)] = f"{loc_x}_{offset_i}"
                else:
                    for loc_x in local_x_axes:
                        mapping_x[str(loc_x)] = str(loc_x)

            # Determine grid_y_mapping for this index
            mapping_y = {}
            if grid_y_mapping and len(grid_y_mapping) >= idx:
                item_y = grid_y_mapping[offset_i]
                if isinstance(item_y, dict):
                    if len(item_y) == 1 and isinstance(list(item_y.values())[0], dict):
                        item_y = list(item_y.values())[0]
                    mapping_y = {str(k): str(v) for k, v in item_y.items()}

            if not mapping_y:
                if along == "grid_y":
                    for p, loc_y in enumerate(local_y_axes):
                        target_p = p + offset_i * num_bays_y
                        if global_y_axes and target_p < len(global_y_axes):
                            mapping_y[str(loc_y)] = str(global_y_axes[target_p])
                        elif len(str(loc_y)) == 1 and str(loc_y).isalpha():
                            mapping_y[str(loc_y)] = chr(ord(loc_y) + offset_i * num_bays_y)
                        elif str(loc_y).isdigit():
                            mapping_y[str(loc_y)] = str(int(loc_y) + offset_i * num_bays_y)
                        else:
                            mapping_y[str(loc_y)] = f"{loc_y}_{offset_i}"
                else:
                    for loc_y in local_y_axes:
                        mapping_y[str(loc_y)] = str(loc_y)

            # Process elements in module
            for orig_elem in mod_elements:
                elem_copy = copy.deepcopy(orig_elem if isinstance(orig_elem, dict) else orig_elem.model_dump(by_alias=True, exclude_none=True))

                # Prefix tag
                orig_tag = elem_copy.get("tag", "")
                if "{tag}" in prefix_pattern or "{original_tag}" in prefix_pattern:
                    new_tag = prefix_pattern.format(index=idx, tag=orig_tag, original_tag=orig_tag)
                else:
                    new_tag = prefix_pattern.format(index=idx) + orig_tag
                elem_copy["tag"] = new_tag

                # Remap child element tags if any
                if "children" in elem_copy and isinstance(elem_copy["children"], list):
                    for child in elem_copy["children"]:
                        if isinstance(child, dict) and "tag" in child:
                            c_tag = child["tag"]
                            if "{tag}" in prefix_pattern or "{original_tag}" in prefix_pattern:
                                child["tag"] = prefix_pattern.format(index=idx, tag=c_tag, original_tag=c_tag)
                            else:
                                child["tag"] = prefix_pattern.format(index=idx) + c_tag

                # Remap placement grid references
                if "placement" in elem_copy and isinstance(elem_copy["placement"], dict):
                    _remap_placement_grids(elem_copy["placement"], mapping_x, mapping_y)

                # Check party wall deduplication
                e_cls = elem_copy.get("class") or elem_copy.get("class_")
                if e_cls == "IfcWall" and party_wall_dedup:
                    place = elem_copy.get("placement", {})
                    st = place.get("storey")
                    fg = place.get("from_grid")
                    tg = place.get("to_grid")
                    if st and fg and tg:
                        fg_t = (str(fg[0]), str(fg[1]))
                        tg_t = (str(tg[0]), str(tg[1]))
                        w_key = (st, frozenset([fg_t, tg_t]))
                        if w_key in existing_wall_keys:
                            # Skip coincident party wall
                            continue
                        existing_wall_keys.add(w_key)

                expanded_elements.append(elem_copy)

    data["elements"] = existing_elements + expanded_elements

    if is_manifest_obj:
        from debim.schema import ProjectManifest
        return ProjectManifest.model_validate(data)
    return data


def load_manifest(path: Optional[Union[Path, str]] = None) -> Any:
    """
    Load and validate .debim / project.yaml manifest file, resolving included modular files,
    expanding module instances, and returning a ProjectManifest instance.
    """
    from debim.schema import ProjectManifest

    resolved_path = resolve_default_manifest_path(path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Manifest file not found: {resolved_path}")

    data = load_debim_file(resolved_path)
    if data.get("modules") and data.get("instances"):
        data = expand_module_instances(data)
    return ProjectManifest.model_validate(data)
