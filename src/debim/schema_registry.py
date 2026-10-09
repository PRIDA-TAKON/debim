"""
Universal Schema Entity Registry for debim.
Provides complete introspection for 800+ buildingSMART IFC4 / IFC4.3 entities,
inheritance tree inspection, required attribute validation, spatial containment rules,
and bSDD Property Set resolution.
"""

from typing import Any, Dict, List, Optional, Union
import ifcopenshell
from pydantic import BaseModel, Field

from debim.bsdd import BSDD_STANDARD_PSETS


class EntityAttributeInfo(BaseModel):
    name: str
    type_name: str
    optional: bool


class EntityInfo(BaseModel):
    name: str
    schema_version: str
    is_abstract: bool
    supertype: Optional[str] = None
    subtypes: List[str] = Field(default_factory=list)
    inheritance_chain: List[str] = Field(default_factory=list)
    is_product: bool = False
    is_element: bool = False
    is_spatial: bool = False
    required_attributes: List[EntityAttributeInfo] = Field(default_factory=list)
    attributes: List[EntityAttributeInfo] = Field(default_factory=list)
    allowed_predefined_types: Optional[List[str]] = None
    default_psets: List[str] = Field(default_factory=list)


class SchemaEntityRegistry:
    """
    Automated Schema Entity Registry powered by ifcopenshell.
    Supports IFC4 and IFC4.3 schema specifications.
    """

    def __init__(self, schema_version: str = "IFC4"):
        self.schema_version = schema_version.upper()
        try:
            self.schema = ifcopenshell.schema_by_name(self.schema_version)
        except Exception as err:
            # Fall back to IFC4 if specified schema is invalid or unavailable
            self.schema_version = "IFC4"
            self.schema = ifcopenshell.schema_by_name("IFC4")

        self._entity_cache: Dict[str, EntityInfo] = {}
        self._build_registry()

    def _build_registry(self) -> None:
        """Introspect and cache metadata for all schema entities."""
        all_entities = self.schema.entities()
        product_decl = self.schema.declaration_by_name("IfcProduct")
        element_decl = self.schema.declaration_by_name("IfcElement")
        spatial_decl = self.schema.declaration_by_name("IfcSpatialElement")

        for decl in all_entities:
            name = decl.name()

            # Inheritance chain
            chain = []
            curr = decl
            while curr:
                chain.append(curr.name())
                curr = curr.supertype()

            supertype_name = chain[1] if len(chain) > 1 else None

            # Subtypes
            subtypes = [s.name() for s in decl.subtypes()]

            # Entity classifications
            is_product = decl._is(product_decl) if product_decl else False
            is_element = decl._is(element_decl) if element_decl else False
            is_spatial = decl._is(spatial_decl) if spatial_decl else False

            # Attributes introspection
            attrs: List[EntityAttributeInfo] = []
            req_attrs: List[EntityAttributeInfo] = []
            allowed_predefined_types: Optional[List[str]] = None

            try:
                for attr in decl.all_attributes():
                    attr_name = attr.name()
                    attr_type = attr.type_of_attribute()
                    type_str = str(attr_type) if attr_type else "Any"
                    is_opt = attr.optional()

                    attr_info = EntityAttributeInfo(
                        name=attr_name,
                        type_name=type_str,
                        optional=is_opt,
                    )
                    attrs.append(attr_info)
                    if not is_opt:
                        req_attrs.append(attr_info)

                    if attr_name == "PredefinedType":
                        try:
                            # Try resolving enum choices
                            dt = getattr(attr_type, "declared_type", None)
                            if callable(dt):
                                declared = dt()
                                enum_type = declared.as_enumeration_type() if declared else None
                                if enum_type:
                                    allowed_predefined_types = list(enum_type.enumeration_items())
                        except Exception:
                            pass
            except Exception:
                pass

            # Match bSDD standard property sets
            default_psets: List[str] = []
            base_class_name = name.replace("Ifc", "")
            possible_psets = [
                f"Pset_{base_class_name}Common",
                f"Pset_{base_class_name}TypeCommon",
            ]
            for pset in possible_psets:
                if pset in BSDD_STANDARD_PSETS:
                    default_psets.append(pset)

            info = EntityInfo(
                name=name,
                schema_version=self.schema_version,
                is_abstract=decl.is_abstract(),
                supertype=supertype_name,
                subtypes=subtypes,
                inheritance_chain=chain,
                is_product=is_product,
                is_element=is_element,
                is_spatial=is_spatial,
                required_attributes=req_attrs,
                attributes=attrs,
                allowed_predefined_types=allowed_predefined_types,
                default_psets=default_psets,
            )
            self._entity_cache[name] = info
            self._entity_cache[name.upper()] = info

    def validate_entity_type(self, entity_type: str) -> bool:
        """Check if an entity type exists in the IFC schema."""
        return entity_type in self._entity_cache or entity_type.upper() in self._entity_cache

    def get_entity_info(self, entity_type: str) -> EntityInfo:
        """Get detailed metadata and inspection info for an entity type."""
        if entity_type in self._entity_cache:
            return self._entity_cache[entity_type]
        if entity_type.upper() in self._entity_cache:
            return self._entity_cache[entity_type.upper()]
        raise ValueError(f"Entity '{entity_type}' is not recognized in schema '{self.schema_version}'.")

    def get_inheritance_chain(self, entity_type: str) -> List[str]:
        """Get inheritance hierarchy chain from specific entity to root IfcRoot."""
        info = self.get_entity_info(entity_type)
        return info.inheritance_chain

    def is_product(self, entity_type: str) -> bool:
        """Check if entity inherits from IfcProduct."""
        return self.get_entity_info(entity_type).is_product

    def is_element(self, entity_type: str) -> bool:
        """Check if entity inherits from IfcElement."""
        return self.get_entity_info(entity_type).is_element

    def is_spatial(self, entity_type: str) -> bool:
        """Check if entity inherits from IfcSpatialElement."""
        return self.get_entity_info(entity_type).is_spatial

    def get_required_attributes(self, entity_type: str) -> List[EntityAttributeInfo]:
        """Get required (non-optional) attributes for an entity."""
        return self.get_entity_info(entity_type).required_attributes

    def get_allowed_predefined_types(self, entity_type: str) -> Optional[List[str]]:
        """Get allowed PredefinedType enumeration values for an entity if defined."""
        return self.get_entity_info(entity_type).allowed_predefined_types

    def get_default_psets(self, entity_type: str) -> List[str]:
        """Get standard bSDD Property Set names matching an entity."""
        return self.get_entity_info(entity_type).default_psets

    def validate_spatial_containment(self, child_type: str, parent_type: str) -> bool:
        """
        Validate spatial containment rules between a child entity and parent container.
        e.g., IfcElement inside IfcBuildingStorey, IfcBuildingStorey inside IfcBuilding, etc.
        """
        if not self.validate_entity_type(child_type) or not self.validate_entity_type(parent_type):
            return False

        child_info = self.get_entity_info(child_type)
        parent_info = self.get_entity_info(parent_type)

        child_chain = set(child_info.inheritance_chain)
        parent_chain = set(parent_info.inheritance_chain)

        # 1. Physical elements / products contained in spatial containers
        if "IfcProduct" in child_chain or "IfcElement" in child_chain:
            spatial_containers = {
                "IfcSpatialElement",
                "IfcSpatialStructureElement",
                "IfcBuildingStorey",
                "IfcBuilding",
                "IfcSite",
                "IfcSpace",
                "IfcExternalSpatialStructureElement",
                "IfcFacilityPart",
            }
            if parent_chain.intersection(spatial_containers):
                return True

        # 2. Aggregates: Storey in Building, Building in Site, Site in Project
        if "IfcBuildingStorey" in child_chain and parent_info.name in ("IfcBuilding", "IfcSite", "IfcProject"):
            return True
        if "IfcBuilding" in child_chain and parent_info.name in ("IfcSite", "IfcProject"):
            return True
        if "IfcSite" in child_chain and parent_info.name == "IfcProject":
            return True

        # 3. Spatial element hierarchy
        if "IfcSpatialElement" in child_chain and "IfcSpatialElement" in parent_chain:
            return True

        return False
