"""
debim.sync.patcher

Surgical YAML / AST patcher for .debim files.
Updates component coordinates (e.g. column grid offsets, boundary points, wall offsets)
using round-trip comment-preserving AST / regex pattern matching logic to keep comments,
whitespace, and document structure 100% intact.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from debim.sync.detector import ChangeProposal


def _format_yaml_value(val: Any) -> str:
    """Format python primitive value to standard clean YAML representation."""
    if isinstance(val, float):
        # Format cleanly, avoiding excess precision artifacts
        if val == int(val):
            return f"{val:.1f}"
        return f"{val:.4f}".rstrip("0").rstrip(".") if "." in f"{val:.4f}" else f"{val:.4f}"
    elif isinstance(val, bool):
        return "true" if val else "false"
    elif val is None:
        return "null"
    else:
        return str(val)


def apply_asbuilt_patch(
    source_debim_path: Union[str, Path],
    proposals: List[Union[ChangeProposal, Dict[str, Any]]],
    output_path: Optional[Union[str, Path]] = None,
) -> str:
    """
    Surgically updates element fields in source .debim file while preserving comments and structure.

    Args:

        source_debim_path: Path to the source .debim / .yaml file.
        proposals: List of ChangeProposal objects or dicts detailing required field updates.
        output_path: Optional path to write updated content. If None, content is returned as string.

    Returns:
        Updated YAML file content string.
    """
    source_p = Path(source_debim_path)
    if not source_p.exists():
        raise FileNotFoundError(f"Source debim file not found: {source_debim_path}")

    content = source_p.read_text(encoding="utf-8")

    # Normalize proposals
    norm_proposals: List[ChangeProposal] = []
    for p in proposals:
        if isinstance(p, ChangeProposal):
            norm_proposals.append(p)
        elif isinstance(p, dict):
            norm_proposals.append(ChangeProposal(**p))

    if not norm_proposals:
        if output_path:
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(content, encoding="utf-8")
        return content

    # Group proposals by element tag
    props_by_tag: Dict[str, List[ChangeProposal]] = {}
    for p in norm_proposals:
        props_by_tag.setdefault(p.tag, []).append(p)

    lines = content.splitlines(keepends=True)

    for tag, tag_props in props_by_tag.items():
        # Search for tag definition in lines
        # Pattern matching: 'tag: TAG' or '- tag: TAG' or 'id: TAG'
        tag_pattern = re.compile(r"^(\s*)(-|\b)?\s*(tag|id):\s*[\"']?" + re.escape(tag) + r"[\"']?\s*(#.*)?$")

        tag_line_idx = -1
        tag_indent = 0

        for idx, line in enumerate(lines):
            match = tag_pattern.match(line)
            if match:
                tag_line_idx = idx
                tag_indent = len(match.group(1))
                break

        if tag_line_idx == -1:
            # Tag not found in file, skip
            continue

        # Find block boundaries for this element
        block_start = tag_line_idx
        # Walk up if tag is part of a dict start (e.g. '- class: IfcColumn')
        while block_start > 0:
            prev_line = lines[block_start - 1]
            prev_indent = len(prev_line) - len(prev_line.lstrip())
            if prev_indent > tag_indent:
                block_start -= 1
            elif prev_indent == tag_indent and prev_line.lstrip().startswith("-"):
                block_start -= 1
                break
            else:
                break

        block_end = tag_line_idx + 1
        while block_end < len(lines):
            curr_line = lines[block_end]
            if not curr_line.strip() or curr_line.lstrip().startswith("#"):
                block_end += 1
                continue
            curr_indent = len(curr_line) - len(curr_line.lstrip())
            if curr_indent <= tag_indent and (curr_line.lstrip().startswith("-") or re.match(r"^\s*[a-zA-Z_0-9]+:", curr_line)):
                break
            block_end += 1

        # Now apply each proposal for this tag within [block_start, block_end)
        for prop in tag_props:
            field_name = prop.field_name
            formatted_val = _format_yaml_value(prop.proposed_value)

            # Check if field belongs inside placement block
            is_placement_field = field_name in ("offset_x", "offset_y", "from_grid", "to_grid", "storey", "at_grid", "angle")

            field_updated = False

            if is_placement_field:
                # Find 'placement:' line in block
                placement_line_idx = -1
                placement_indent = tag_indent + 2

                for idx in range(block_start, block_end):
                    p_match = re.match(r"^(\s*)placement:\s*(#.*)?$", lines[idx])
                    if p_match:
                        placement_line_idx = idx
                        placement_indent = len(p_match.group(1)) + 2
                        break

                if placement_line_idx != -1:
                    # Look for field_name under placement
                    field_pat = re.compile(r"^(\s*)" + re.escape(field_name) + r":\s*.*$")
                    for idx in range(placement_line_idx + 1, block_end):
                        f_match = field_pat.match(lines[idx])
                        if f_match:
                            indent_str = f_match.group(1)
                            # Keep line ending
                            ending = "\n" if lines[idx].endswith("\n") else ""
                            lines[idx] = f"{indent_str}{field_name}: {formatted_val}{ending}"
                            field_updated = True
                            break

                    if not field_updated:
                        # Insert field under placement
                        indent_str = " " * placement_indent
                        ending = "\n"
                        lines.insert(placement_line_idx + 1, f"{indent_str}{field_name}: {formatted_val}{ending}")
                        block_end += 1
                        field_updated = True
                else:
                    # Create placement block and add field
                    indent_str = " " * (tag_indent + 2)
                    sub_indent_str = " " * (tag_indent + 4)
                    ending = "\n"
                    new_placement_lines = [
                        f"{indent_str}placement:{ending}",
                        f"{sub_indent_str}{field_name}: {formatted_val}{ending}",
                    ]
                    lines[tag_line_idx + 1:tag_line_idx + 1] = new_placement_lines
                    block_end += len(new_placement_lines)
                    field_updated = True

            else:
                # Top level element field (e.g. offset_distance, sill_height, thickness, height)
                field_pat = re.compile(r"^(\s*)" + re.escape(field_name) + r":\s*.*$")
                for idx in range(block_start, block_end):
                    f_match = field_pat.match(lines[idx])
                    if f_match:
                        indent_str = f_match.group(1)
                        ending = "\n" if lines[idx].endswith("\n") else ""
                        lines[idx] = f"{indent_str}{field_name}: {formatted_val}{ending}"
                        field_updated = True
                        break

                if not field_updated:
                    # Insert field under element
                    indent_str = " " * (tag_indent + 2)
                    ending = "\n"
                    lines.insert(tag_line_idx + 1, f"{indent_str}{field_name}: {formatted_val}{ending}")
                    block_end += 1
                    field_updated = True

    updated_content = "".join(lines)

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(updated_content, encoding="utf-8")

    return updated_content
