"""
Unit and property tests for SchemaEntityRegistry and Universal Geometry Fallback Engine.
"""

import random
import time
import pytest
import ifcopenshell

from debim.compiler import (
    bind_default_psets_ifcopenshell,
    bind_default_psets_step,
    generate_fallback_solid_ifcopenshell,
    generate_fallback_solid_step,
    StepSerializer,
)
from debim.schema_registry import EntityInfo, SchemaEntityRegistry


def test_schema_registry_instantiation():
    reg = SchemaEntityRegistry("IFC4")
    assert reg.schema_version == "IFC4"
    assert len(reg._entity_cache) >= 700


def test_schema_registry_ifc43_support():
    reg_43 = SchemaEntityRegistry("IFC4X3")
    assert reg_43.schema_version == "IFC4X3"
    assert len(reg_43._entity_cache) >= 800


def test_schema_registry_entity_introspection():
    reg = SchemaEntityRegistry("IFC4")

    assert reg.validate_entity_type("IfcWall")
    assert reg.validate_entity_type("ifcwall")
    assert reg.validate_entity_type("IFCWALL")

    info = reg.get_entity_info("IfcWall")
    assert isinstance(info, EntityInfo)
    assert info.name == "IfcWall"
    assert info.is_product is True
    assert info.is_element is True
    assert info.is_spatial is False
    assert "IfcProduct" in info.inheritance_chain
    assert "IfcRoot" in info.inheritance_chain
    assert "Pset_WallCommon" in info.default_psets

    # Test predefined types for IfcWall
    allowed_types = reg.get_allowed_predefined_types("IfcWall")
    assert allowed_types is not None
    assert "SOLIDWALL" in allowed_types or "STANDARD" in allowed_types


def test_schema_registry_spatial_containment():
    reg = SchemaEntityRegistry("IFC4")

    # Valid containment
    assert reg.validate_spatial_containment("IfcWall", "IfcBuildingStorey")
    assert reg.validate_spatial_containment("IfcColumn", "IfcBuilding")
    assert reg.validate_spatial_containment("IfcBuildingStorey", "IfcBuilding")
    assert reg.validate_spatial_containment("IfcBuilding", "IfcSite")
    assert reg.validate_spatial_containment("IfcSite", "IfcProject")

    # Invalid containment
    assert not reg.validate_spatial_containment("IfcProject", "IfcWall")


def test_random_100_entities_introspection_and_fallback_timing():
    reg = SchemaEntityRegistry("IFC4")
    schema = ifcopenshell.schema_by_name("IFC4")
    all_entities = [e.name() for e in schema.entities()]

    # Seed random selection deterministically for reproducible test
    random.seed(42)
    sampled_entities = random.sample(all_entities, min(100, len(all_entities)))
    assert len(sampled_entities) == 100

    # Introspection check on all 100 sampled entities
    for entity_name in sampled_entities:
        assert reg.validate_entity_type(entity_name)
        info = reg.get_entity_info(entity_name)
        assert info.name == entity_name
        chain = reg.get_inheritance_chain(entity_name)
        assert chain[0] == entity_name
        assert len(chain) >= 1

    # Benchmark fallback solid generation execution time (<2ms per element)
    model = ifcopenshell.file(schema="IFC4")
    context = model.createIfcGeometricRepresentationContext(
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=model.createIfcAxis2Placement3D(
            model.createIfcCartesianPoint((0.0, 0.0, 0.0))
        ),
    )
    body_context = model.createIfcGeometricRepresentationSubContext(
        ContextIdentifier="Body",
        ContextType="Model",
        ParentContext=context,
        TargetView="MODEL_VIEW",
    )

    t0 = time.perf_counter()
    for i, entity_name in enumerate(sampled_entities):
        # Create product entity if supported
        try:
            prod = model.create_entity(entity_name, GlobalId=f"GUID_{i}")
        except Exception:
            prod = model.create_entity("IfcBuildingElementProxy", GlobalId=f"GUID_{i}")

        # Fallback solid generation
        generate_fallback_solid_ifcopenshell(
            model, prod, body_context, dimensions=(0.6, 0.6, 1.2)
        )
        # bSDD Pset binding
        bind_default_psets_ifcopenshell(model, prod, entity_name)

    t1 = time.perf_counter()
    total_time_ms = (t1 - t0) * 1000.0
    time_per_element_ms = total_time_ms / len(sampled_entities)

    print(f"Total time for 100 entities fallback: {total_time_ms:.2f} ms")
    print(f"Time per element fallback: {time_per_element_ms:.4f} ms")

    # Performance requirement assertion: Execution time under 2ms per element
    assert time_per_element_ms < 2.0


def test_step_serializer_fallback_and_psets():
    serializer = StepSerializer()
    body_context_ref = "#1"

    prod_shape_ref = generate_fallback_solid_step(
        serializer, body_context_ref, dimensions=(0.4, 0.4, 0.8)
    )
    assert prod_shape_ref.startswith("#")

    bound_psets = bind_default_psets_step(
        serializer, "#2", "IfcWall", custom_properties={"Pset_WallCommon": {"IsExternal": True}}
    )
    assert len(bound_psets) >= 1
    assert any("IFCPROPERTYSET" in line.upper() for line in serializer.lines)
