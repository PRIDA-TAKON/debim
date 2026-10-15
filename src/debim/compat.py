"""
Pydantic v1 and v2 dual-compatibility shim for air-gapped sandboxes and legacy environments.
"""

import sys
from typing import Any, Callable, Dict, Generic, List, Optional, Tuple, Type, TypeVar, Union
import pydantic

# Detect Pydantic version
PYDANTIC_V2 = False
try:
    from pydantic.version import VERSION as _PYDANTIC_VERSION
    PYDANTIC_V2 = int(_PYDANTIC_VERSION.split(".")[0]) >= 2
except Exception:
    PYDANTIC_V2 = hasattr(pydantic, "RootModel")

if PYDANTIC_V2:
    from pydantic import (
        BaseModel,
        ConfigDict,
        Discriminator,
        Field,
        PrivateAttr,
        RootModel,
        Tag,
        ValidationError,
        field_validator,
        model_validator,
    )
else:
    # Pydantic 1.x fallback implementation
    from pydantic import (
        BaseModel as _v1_BaseModel,
        Field,
        PrivateAttr,
        ValidationError,
        root_validator,
        validator,
    )
    from pydantic.main import ModelMetaclass as _v1_ModelMetaclass

    def ConfigDict(**kwargs: Any) -> Dict[str, Any]:
        """v1 shim for ConfigDict. Maps v2 config keys to v1 Config attributes."""
        v1_mapping = {
            "populate_by_name": "allow_population_by_field_name",
            "extra": "extra",
            "from_attributes": "orm_mode",
            "str_strip_whitespace": "anystr_strip_whitespace",
            "validate_assignment": "validate_assignment",
        }
        res = {}
        for k, v in kwargs.items():
            mapped_key = v1_mapping.get(k, k)
            res[mapped_key] = v
        return res

    class BaseModelMeta(_v1_ModelMetaclass):
        """Metaclass for Pydantic v1 BaseModel to support model_config dicts."""

        def __new__(mcls, name: str, bases: Tuple[type, ...], namespace: Dict[str, Any], **kwargs: Any):
            if "model_config" in namespace and isinstance(namespace["model_config"], dict):
                cfg_dict = namespace["model_config"]
                existing_config = namespace.get("Config")
                if existing_config is None:
                    class Config:
                        pass
                    existing_config = Config
                    namespace["Config"] = existing_config
                for k, v in cfg_dict.items():
                    setattr(existing_config, k, v)
            return super().__new__(mcls, name, bases, namespace, **kwargs)

    class BaseModel(_v1_BaseModel, metaclass=BaseModelMeta):
        """v1 BaseModel shim providing v2 helper methods."""

        def model_dump(
            self,
            by_alias: bool = False,
            exclude_none: bool = False,
            mode: str = "python",
            **kwargs: Any,
        ) -> Dict[str, Any]:
            return self.dict(by_alias=by_alias, exclude_none=exclude_none, **kwargs)

        def model_dump_json(
            self,
            by_alias: bool = False,
            exclude_none: bool = False,
            **kwargs: Any,
        ) -> str:
            return self.json(by_alias=by_alias, exclude_none=exclude_none, **kwargs)

        @classmethod
        def model_validate(cls: Type["BaseModel"], obj: Any, **kwargs: Any) -> "BaseModel":
            return cls.parse_obj(obj)

        @classmethod
        def model_validate_json(cls: Type["BaseModel"], json_data: Union[str, bytes], **kwargs: Any) -> "BaseModel":
            return cls.parse_raw(json_data)

        @classmethod
        def model_json_schema(cls: Type["BaseModel"], **kwargs: Any) -> Dict[str, Any]:
            return cls.schema(**kwargs)

    T = TypeVar("T")

    class RootModel(BaseModel, Generic[T]):
        """v1 RootModel shim wrapping __root__."""

        __root__: Any

        def __init__(self, root: Any = ..., **data: Any):
            if root is not ...:
                data["__root__"] = root
            super().__init__(**data)

        @property
        def root(self) -> Any:
            return getattr(self, "__root__", None)

        @root.setter
        def root(self, value: Any) -> None:
            self.__root__ = value

        @classmethod
        def model_validate(cls, obj: Any, **kwargs: Any) -> "RootModel":
            if isinstance(obj, cls):
                return obj
            return cls(__root__=obj)

        def model_dump(self, *args: Any, **kwargs: Any) -> Any:
            res = self.dict(*args, **kwargs)
            if isinstance(res, dict) and "__root__" in res:
                return res["__root__"]
            return res

    def field_validator(*fields: str, mode: str = "after", **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """v1 field_validator shim mapping mode to validator(pre=...)."""
        pre = (mode == "before")

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            target_fn = fn.__func__ if isinstance(fn, classmethod) else fn
            return validator(*fields, pre=pre, allow_reuse=True, **kwargs)(target_fn)

        return decorator

    def model_validator(*, mode: str = "after", **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """v1 model_validator shim mapping mode to root_validator."""
        pre = (mode == "before")

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            target_fn = fn.__func__ if isinstance(fn, classmethod) else fn

            if mode == "after":
                def wrapper(cls: Type[BaseModel], values: Dict[str, Any]) -> Dict[str, Any]:
                    obj = cls.construct(**values)
                    res = target_fn(obj)
                    if hasattr(res, "__dict__"):
                        values.update({k: v for k, v in res.__dict__.items() if not k.startswith("_")})
                    return values

                return root_validator(pre=False, allow_reuse=True)(classmethod(wrapper))
            else:
                def wrapper(cls: Type[BaseModel], values: Any) -> Any:
                    return target_fn(cls, values)

                return root_validator(pre=True, allow_reuse=True)(classmethod(wrapper))

        return decorator

    class Discriminator:
        """v1 Discriminator placeholder shim."""

        def __init__(self, discriminator: Any):
            self.discriminator = discriminator

    class Tag:
        """v1 Tag placeholder shim."""

        def __init__(self, tag: str):
            self.tag = tag


__all__ = [
    "PYDANTIC_V2",
    "BaseModel",
    "ConfigDict",
    "Discriminator",
    "Field",
    "PrivateAttr",
    "RootModel",
    "Tag",
    "ValidationError",
    "field_validator",
    "model_validator",
]
