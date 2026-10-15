"""
Unit tests for Pydantic v1 and v2 compatibility shim in debim.compat.
"""

from typing import Dict, List, Optional
import pytest
from debim.compat import (
    PYDANTIC_V2,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationError,
    field_validator,
    model_validator,
)


class SampleRootList(RootModel[List[str]]):
    pass


class SampleRootDict(RootModel[Dict[str, float]]):
    pass


class SampleItemModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    tag: str = Field(alias="element_tag")
    value: float

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, v):
        if isinstance(v, str):
            return float(v)
        return v

    @model_validator(mode="after")
    def check_tag_format(self) -> "SampleItemModel":
        if not self.tag.startswith("TAG-"):
            self.tag = f"TAG-{self.tag}"
        return self


def test_root_model_instantiation():
    rl = SampleRootList.model_validate(["a", "b", "c"])
    assert rl.root == ["a", "b", "c"]
    assert rl.model_dump() == ["a", "b", "c"]

    rd = SampleRootDict.model_validate({"x": 1.5, "y": 2.5})
    assert rd.root == {"x": 1.5, "y": 2.5}
    assert rd.model_dump() == {"x": 1.5, "y": 2.5}


def test_field_and_model_validator():
    item = SampleItemModel.model_validate({"element_tag": "001", "value": "12.5"})
    assert item.tag == "TAG-001"
    assert item.value == 12.5
    assert item.model_dump(by_alias=True)["element_tag"] == "TAG-001"


def test_config_dict():
    item = SampleItemModel(element_tag="002", value=42.0)
    assert item.tag == "TAG-002"
    assert item.value == 42.0


def test_schema_export():
    schema = SampleItemModel.model_json_schema()
    assert isinstance(schema, dict)
    assert "properties" in schema or "$defs" in schema or "title" in schema
