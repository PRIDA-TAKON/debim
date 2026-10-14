"""
Unit tests for module definitions (modules:) and array replication (instances: replicate:) in debim schema.
"""

import pytest
from pydantic import ValidationError
import yaml

from debim.schema import (
    Grids,
    InstanceConfig,
    ModuleDefinition,
    ProjectManifest,
    ReplicationConfig,
)


def test_module_definition_model():
    """Test ModuleDefinition model initialization and field validation."""
    mod = ModuleDefinition(
        id="BAY_UNIT_A",
        name="Standard 4m Bay Unit",
        local_grids=Grids(axes_x={"1": 0.0, "2": 4.0}, axes_y={"A": 0.0, "B": 8.0}),
        elements=[
            {
                "class": "IfcColumn",
                "tag": "COL-01",
                "material": "CONC_240",
                "profile": {"shape": "BOX", "width": 0.30, "depth": 0.30},
                "placement": {"grid": ["1", "A"], "base_storey": "L1", "top_storey": "L2"},
            }
        ],
    )
    assert mod.id == "BAY_UNIT_A"
    assert mod.name == "Standard 4m Bay Unit"
    assert mod.local_grids is not None
    assert mod.local_grids.axes_x == {"1": 0.0, "2": 4.0}
    assert mod.elements is not None
    assert len(mod.elements) == 1
    assert mod.elements[0].tag == "COL-01"


def test_replication_config_defaults_and_customs():
    """Test ReplicationConfig default values and custom overrides."""
    rep_default = ReplicationConfig(module="BAY_UNIT_A", count=4)
    assert rep_default.module == "BAY_UNIT_A"
    assert rep_default.count == 4
    assert rep_default.along == "grid_x"
    assert rep_default.prefix_pattern == "U{index}_"
    assert rep_default.party_wall_deduplication is True
    assert rep_default.grid_x_mapping is None
    assert rep_default.grid_y_mapping is None

    rep_custom = ReplicationConfig(
        module="BAY_UNIT_A",
        count=3,
        along="grid_y",
        grid_x_mapping=[{"1": "1"}, {"2": "2"}],
        grid_y_mapping=[{"A": "A"}, {"B": "B"}],
        prefix_pattern="UNIT_{index:02d}_",
        party_wall_deduplication=False,
    )
    assert rep_custom.along == "grid_y"
    assert rep_custom.count == 3
    assert rep_custom.prefix_pattern == "UNIT_{index:02d}_"
    assert rep_custom.party_wall_deduplication is False
    assert rep_custom.grid_x_mapping == [{"1": "1"}, {"2": "2"}]


def test_instance_config_model():
    """Test InstanceConfig parsing with single module instance or replicated instance."""
    inst_single = InstanceConfig(
        module="BAY_UNIT_A",
        origin={"grid_x": "1", "grid_y": "A"},
        id_prefix="U1_",
    )
    assert inst_single.module == "BAY_UNIT_A"
    assert inst_single.origin == {"grid_x": "1", "grid_y": "A"}
    assert inst_single.id_prefix == "U1_"

    inst_repl = InstanceConfig(
        replicate=ReplicationConfig(
            module="BAY_UNIT_A",
            count=4,
            along="grid_x",
            grid_x_mapping=[{"1": "1", "2": "2"}, {"1": "2", "2": "3"}],
        )
    )
    assert inst_repl.replicate is not None
    assert inst_repl.replicate.module == "BAY_UNIT_A"
    assert inst_repl.replicate.count == 4


def test_project_manifest_with_modules_and_instances():
    """Test full ProjectManifest parsing containing modules: and instances: blocks."""
    manifest_yaml = """
schema: IFC4-Minimal
project:
  id: PRJ-SHOPHOUSE-4BAY
  name: "4-Bay Shophouse Project"
  units:
    length: METER
    area: SQUARE_METER
    volume: CUBIC_METER
spatial_structure:
  storeys:
    - id: L1
      name: "Ground Floor"
      elevation: 0.00
      height: 3.50
    - id: L2
      name: "Second Floor"
      elevation: 3.50
      height: 3.20
grids:
  axes_x:
    "1": 0.0
    "2": 4.0
    "3": 8.0
    "4": 12.0
    "5": 16.0
  axes_y:
    "A": 0.0
    "B": 12.0
materials:
  - id: MAT_CONC
    name: "Concrete 240 ksc"
    category: concrete
    unit_cost_ref: REF-CONC
modules:
  - id: SHOPHOUSE_BAY
    name: "Standard Shophouse Bay Module"
    local_grids:
      axes_x:
        "1": 0.0
        "2": 4.0
      axes_y:
        "A": 0.0
        "B": 12.0
    elements:
      - class: IfcColumn
        tag: COL-C1
        material: MAT_CONC
        profile:
          shape: BOX
          width: 0.30
          depth: 0.30
        placement:
          grid: ["1", "A"]
          base_storey: L1
          top_storey: L2
      - class: IfcBeam
        tag: BM-B1
        material: MAT_CONC
        profile:
          shape: BOX
          width: 0.20
          depth: 0.40
        placement:
          from_grid: ["1", "A"]
          to_grid: ["2", "A"]
          storey: L2
instances:
  - module: SHOPHOUSE_BAY
    replicate:
      module: SHOPHOUSE_BAY
      count: 4
      along: grid_x
      grid_x_mapping:
        - {"1": "1", "2": "2"}
        - {"1": "2", "2": "3"}
        - {"1": "3", "2": "4"}
        - {"1": "4", "2": "5"}
      prefix_pattern: "U{index}_"
      party_wall_deduplication: true
"""
    data = yaml.safe_load(manifest_yaml)
    manifest = ProjectManifest.model_validate(data)

    assert manifest.project.id == "PRJ-SHOPHOUSE-4BAY"
    assert manifest.modules is not None
    assert len(manifest.modules) == 1
    assert manifest.modules[0].id == "SHOPHOUSE_BAY"
    assert manifest.modules[0].elements is not None
    assert len(manifest.modules[0].elements) == 2

    assert manifest.instances is not None
    assert len(manifest.instances) == 1
    assert manifest.instances[0].replicate is not None
    assert manifest.instances[0].replicate.count == 4
    assert manifest.instances[0].replicate.along == "grid_x"


def test_invalid_module_definition_raises_error():
    """Test that invalid ModuleDefinition fields raise Pydantic ValidationError."""
    # Missing required id
    with pytest.raises(ValidationError):
        ModuleDefinition.model_validate({"name": "No ID Module"})

    # Invalid element in elements list
    with pytest.raises(ValidationError):
        ModuleDefinition.model_validate(
            {
                "id": "MOD_INVALID",
                "elements": [{"class": "IfcUnknownClass", "tag": "UNK-1"}],
            }
        )


def test_invalid_replication_config_raises_error():
    """Test that invalid ReplicationConfig fields raise Pydantic ValidationError."""
    # Missing required count
    with pytest.raises(ValidationError):
        ReplicationConfig.model_validate({"module": "MOD_A"})

    # Invalid along literal value
    with pytest.raises(ValidationError):
        ReplicationConfig.model_validate({"module": "MOD_A", "count": 2, "along": "diagonal"})


def test_model_dump_roundtrip():
    """Test serialization roundtrip for ProjectManifest with modules and instances."""
    mod = ModuleDefinition(id="MOD_1", name="Module 1")
    inst = InstanceConfig(module="MOD_1", id_prefix="UNIT1_")
    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project={"id": "PRJ-1", "name": "Test Project"},
        spatial_structure={"storeys": [{"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0}]},
        grids={"axes_x": {"1": 0.0}, "axes_y": {"A": 0.0}},
        materials=[],
        modules=[mod],
        instances=[inst],
    )

    dumped = manifest.model_dump(by_alias=True, exclude_none=True)
    assert "modules" in dumped
    assert "instances" in dumped
    assert dumped["modules"][0]["id"] == "MOD_1"
    assert dumped["instances"][0]["module"] == "MOD_1"

    reloaded = ProjectManifest.model_validate(dumped)
    assert reloaded.modules is not None and reloaded.modules[0].id == "MOD_1"
    assert reloaded.instances is not None and reloaded.instances[0].id_prefix == "UNIT1_"
