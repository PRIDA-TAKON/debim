"""
Discrepancy Auditor for cross-referencing project elements with material specifications.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from pydantic import BaseModel, Field

from debim.schema import ProjectManifest, load_manifest
from debim.spec.schema import MaterialSpec, SpecificationManifest, load_spec_manifest


class SpecAuditResult(BaseModel):
    """Result of discrepancy audit between project manifest and material specifications."""
    missing_specs: List[str] = Field(default_factory=list)
    unused_specs: List[str] = Field(default_factory=list)
    referenced_materials: List[str] = Field(default_factory=list)
    spec_ids: List[str] = Field(default_factory=list)
    element_material_map: Dict[str, List[str]] = Field(default_factory=dict)
    is_compliant: bool = True


def _extract_material_refs_from_obj(
    obj: Any, tag: str, mat_set: Set[str], mat_elem_map: Dict[str, List[str]]
):
    """Recursively traverse pydantic model or dict to extract material reference strings."""
    if obj is None:
        return

    if isinstance(obj, str):
        return

    if isinstance(obj, (list, tuple)):
        for item in obj:
            _extract_material_refs_from_obj(item, tag, mat_set, mat_elem_map)
        return

    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and (
                "material" in k or k in ("tile_spec", "spec")
            ):
                mat_set.add(v)
                if tag:
                    mat_elem_map.setdefault(v, [])
                    if tag not in mat_elem_map[v]:
                        mat_elem_map[v].append(tag)
            elif isinstance(v, (dict, list, tuple)) or isinstance(v, BaseModel) or hasattr(v, "__dict__"):
                _extract_material_refs_from_obj(v, tag, mat_set, mat_elem_map)
        return

    if isinstance(obj, BaseModel):
        for field_name in obj.__class__.model_fields.keys():
            val = getattr(obj, field_name, None)
            if isinstance(val, str) and (
                "material" in field_name or field_name in ("tile_spec", "spec")
            ):
                mat_set.add(val)
                if tag:
                    mat_elem_map.setdefault(val, [])
                    if tag not in mat_elem_map[val]:
                        mat_elem_map[val].append(tag)
            elif val is not None and not isinstance(val, (int, float, bool, str)):
                _extract_material_refs_from_obj(val, tag, mat_set, mat_elem_map)


def extract_project_materials(
    manifest: ProjectManifest,
) -> Tuple[Set[str], Dict[str, List[str]]]:
    """Extract all material IDs referenced in project manifest and map to element tags."""
    mat_set: Set[str] = set()
    mat_elem_map: Dict[str, List[str]] = {}

    # Extract declared materials in manifest
    if hasattr(manifest, "materials") and manifest.materials:
        for m in manifest.materials:
            mat_set.add(m.id)

    # Extract material references from elements and proxies
    all_elements = list(manifest.elements) + list(manifest.proxies)
    for elem in all_elements:
        tag = getattr(elem, "tag", "")
        _extract_material_refs_from_obj(elem, tag, mat_set, mat_elem_map)

    return mat_set, mat_elem_map


def audit_project_specs(
    project_manifest: Union[ProjectManifest, str, Path, dict],
    spec_manifest: Optional[Union[SpecificationManifest, str, Path, List[Any], dict]] = None,
) -> SpecAuditResult:
    """
    Cross-reference project.yaml elements with material specifications to detect missing and unused specs.
    """
    manifest_obj: ProjectManifest
    manifest_path: Optional[Path] = None

    if isinstance(project_manifest, ProjectManifest):
        manifest_obj = project_manifest
    elif isinstance(project_manifest, (str, Path)):
        manifest_path = Path(project_manifest)
        manifest_obj = load_manifest(manifest_path)
    elif isinstance(project_manifest, dict):
        manifest_obj = ProjectManifest.model_validate(project_manifest)
    else:
        raise ValueError(f"Invalid project manifest type: {type(project_manifest)}")

    # Resolve specification manifest
    specs_obj: SpecificationManifest
    if spec_manifest is not None:
        specs_obj = load_spec_manifest(spec_manifest)
    else:
        # Check if project manifest contains embedded specifications
        raw_specs = getattr(manifest_obj, "specifications", None) or getattr(
            manifest_obj, "specs", None
        )

        if raw_specs:
            specs_obj = load_spec_manifest(raw_specs)
        elif manifest_path is not None and manifest_path.exists():
            # Search for spec files adjacent to manifest_path
            parent_dir = manifest_path.parent
            candidate_specs = [
                parent_dir / "specs.yaml",
                parent_dir / "specs.yml",
                parent_dir / "specifications.yaml",
                parent_dir / "specifications.yml",
                parent_dir / "specs",
            ]
            found_spec_path = None
            for cand in candidate_specs:
                if cand.exists():
                    found_spec_path = cand
                    break

            if found_spec_path:
                specs_obj = load_spec_manifest(found_spec_path)
            else:
                specs_obj = SpecificationManifest()
        else:
            specs_obj = SpecificationManifest()

    # Extract referenced materials and spec IDs
    referenced_mats_set, mat_elem_map = extract_project_materials(manifest_obj)
    spec_ids_set = {spec.id for spec in specs_obj.specifications}

    missing_specs = sorted(list(referenced_mats_set - spec_ids_set))
    unused_specs = sorted(list(spec_ids_set - referenced_mats_set))
    is_compliant = (len(missing_specs) == 0 and len(unused_specs) == 0)

    return SpecAuditResult(
        missing_specs=missing_specs,
        unused_specs=unused_specs,
        referenced_materials=sorted(list(referenced_mats_set)),
        spec_ids=sorted(list(spec_ids_set)),
        element_material_map=mat_elem_map,
        is_compliant=is_compliant,
    )
