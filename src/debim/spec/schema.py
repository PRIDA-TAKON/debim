"""
Pydantic v2 schemas for architectural material specifications.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class IndustryStandards(BaseModel):
    """Industry standards reference (e.g., JIS, ASTM, DIN, ISO)."""
    model_config = ConfigDict(extra="allow")

    jis: Optional[str] = None
    astm: Optional[str] = None
    din: Optional[str] = None
    iso: Optional[str] = None


class StructuredClauses(BaseModel):
    """Structured clauses for specification text and rules."""
    model_config = ConfigDict(extra="allow")

    general_properties: Optional[Union[str, List[Any], Dict[str, Any]]] = None
    surface_preparation: Optional[Union[str, List[Any], Dict[str, Any]]] = None
    application_system: Optional[Union[str, List[Any], Dict[str, Any]]] = None


class MaterialSpec(BaseModel):
    """Material Specification model."""
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    manufacturer: Optional[str] = None
    masterformat: Optional[str] = None
    warranty_years: Optional[int] = None

    standards: IndustryStandards = Field(default_factory=IndustryStandards)
    clauses: StructuredClauses = Field(default_factory=StructuredClauses)

    @model_validator(mode="before")
    @classmethod
    def _coerce_nested_and_top_level(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            # Standards coercion
            standards_data = data.get("standards")
            if isinstance(standards_data, IndustryStandards):
                standards_dict = standards_data.model_dump()
            elif isinstance(standards_data, dict):
                standards_dict = dict(standards_data)
            else:
                standards_dict = {}

            for key in ["jis", "astm", "din", "iso"]:
                if key in data and key not in standards_dict:
                    standards_dict[key] = data[key]

            data["standards"] = standards_dict

            # Clauses coercion
            clauses_data = data.get("clauses")
            if isinstance(clauses_data, StructuredClauses):
                clauses_dict = clauses_data.model_dump()
            elif isinstance(clauses_data, dict):
                clauses_dict = dict(clauses_data)
            else:
                clauses_dict = {}

            for key in ["general_properties", "surface_preparation", "application_system"]:
                if key in data and key not in clauses_dict:
                    clauses_dict[key] = data[key]

            data["clauses"] = clauses_dict

        return data


class SpecificationManifest(BaseModel):
    """Collection/manifest of material specifications."""
    specifications: List[MaterialSpec] = Field(default_factory=list)


def load_spec_manifest(
    source: Union[str, Path, dict, List[Any], SpecificationManifest]
) -> SpecificationManifest:
    """
    Load SpecificationManifest from file path, directory path, dictionary, list, or existing manifest.
    """
    if isinstance(source, SpecificationManifest):
        return source

    if isinstance(source, (str, Path)):
        p = Path(source)
        if not p.exists():
            raise FileNotFoundError(f"Specification manifest path not found: {source}")

        if p.is_dir():
            all_specs = []
            for ext in ("*.yaml", "*.yml", "*.json"):
                for filepath in p.glob(ext):
                    sub_manifest = load_spec_manifest(filepath)
                    all_specs.extend(sub_manifest.specifications)
            return SpecificationManifest(specifications=all_specs)

        with open(p, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
        return load_spec_manifest(raw_data)

    if isinstance(source, list):
        parsed_specs = []
        for item in source:
            if isinstance(item, MaterialSpec):
                parsed_specs.append(item)
            elif isinstance(item, dict):
                parsed_specs.append(MaterialSpec.model_validate(item))
            else:
                raise ValueError(f"Invalid specification item type: {type(item)}")
        return SpecificationManifest(specifications=parsed_specs)

    if isinstance(source, dict):
        if "specifications" in source or "specs" in source:
            specs_list = source.get("specifications") or source.get("specs") or []
            return load_spec_manifest(specs_list)
        elif "id" in source and "name" in source:
            return SpecificationManifest(specifications=[MaterialSpec.model_validate(source)])
        else:
            # Check if dict keys are spec IDs or specs mapping
            if source:
                parsed_specs = []
                for key, val in source.items():
                    if isinstance(val, dict):
                        if "id" not in val:
                            val["id"] = key
                        if "name" not in val:
                            val["name"] = key
                        parsed_specs.append(MaterialSpec.model_validate(val))
                if parsed_specs:
                    return SpecificationManifest(specifications=parsed_specs)
            return SpecificationManifest()

    raise ValueError(f"Unsupported specification source type: {type(source)}")
