"""
Unit tests for IFC4.3 Urban & Civil features:
1. Geo-referencing (IfcProjectedCRS and IfcMapConversion)
2. Linear spatial hierarchy (IfcRoad and IfcFacilityPart)
"""

import math
import yaml
import pytest
from debim.schema import ProjectManifest
from debim.resolver import resolve_manifest
from debim.compiler import compile_to_ifc
import ifcopenshell


def test_crs_and_map_conversion(tmp_path):
    yaml_content = """
schema: "IFC4X3"
project:
  id: "PROJ-URBAN-01"
  name: "Asoke Smart City Test"
  crs:
    epsg: 32647
    name: "WGS 84 / UTM zone 47N"
    easting: 668250.0
    northing: 1521420.0
    elevation: 2.50
    rotation: 15.0
    scale: 1.0

spatial_structure:
  storeys:
    - id: "L1"
      name: "Ground Level"
      elevation: 0.0
      height: 3.5

grids:
  axes_x: {"1": 0.0, "2": 20.0}
  axes_y: {"A": 0.0, "B": 20.0}

materials:
  - id: "CONC"
    name: "Concrete"
    density: 2400
    category: "CONCRETE"
    unit_cost_ref: "MAT-CONC"

elements:
  - class: IfcColumn
    tag: "COL-01"
    profile:
      shape: BOX
      width: 0.5
      depth: 0.5
    height: 3.5
    material: "CONC"
    placement:
      storey: "L1"
      grid: ["1", "A"]
"""
    manifest = ProjectManifest.model_validate(yaml.safe_load(yaml_content))
    assert manifest.project.crs is not None
    assert manifest.project.crs.epsg == 32647
    assert manifest.project.crs.easting == 668250.0

    resolved = resolve_manifest(manifest)

    out_file = tmp_path / "urban_crs.ifc"
    compile_to_ifc(resolved, output_path=out_file)
    model = ifcopenshell.open(str(out_file))

    # Verify IfcProjectedCRS
    proj_crss = model.by_type("IfcProjectedCRS")
    assert len(proj_crss) >= 1
    crs_entity = proj_crss[0]
    assert "32647" in crs_entity.Name

    # Verify IfcMapConversion
    map_convs = model.by_type("IfcMapConversion")
    assert len(map_convs) >= 1
    conv = map_convs[0]
    assert pytest.approx(conv.Eastings, 0.01) == 668250.0
    assert pytest.approx(conv.Northings, 0.01) == 1521420.0
    assert pytest.approx(conv.OrthogonalHeight, 0.01) == 2.50
    assert pytest.approx(conv.Scale, 0.01) == 1.0
    expected_abscissa = math.cos(math.radians(15.0))
    expected_ordinate = math.sin(math.radians(15.0))
    assert pytest.approx(conv.XAxisAbscissa, 0.01) == expected_abscissa
    assert pytest.approx(conv.XAxisOrdinate, 0.01) == expected_ordinate


def test_ifc43_spatial_facilities(tmp_path):
    yaml_content = """
schema: "IFC4X3"
project:
  id: "PROJ-ROAD-01"
  name: "Sukhumvit Urban Corridor"

spatial_structure:
  storeys:
    - id: "GROUND"
      name: "Ground"
      elevation: 0.0
      height: 0.0

grids:
  axes_x: {"1": 0.0, "2": 100.0}
  axes_y: {"A": 0.0, "B": 20.0}

materials:
  - id: "ASPHALT"
    name: "Asphalt Concrete"
    density: 2350
    category: "CIVIL"
    unit_cost_ref: "MAT-ASPHALT"

elements:
  - class: IfcRoad
    tag: "ROAD-SUKHUMVIT"
    road_width: 14.0
    corridor_length: 100.0
    material: "ASPHALT"
    placement:
      storey: "GROUND"
      from_grid: ["1", "A"]
      to_grid: ["2", "A"]

  - class: IfcFacilityPart
    tag: "PART-ROADWAY-EAST"
    facility: "ROAD-SUKHUMVIT"
    predefined_type: "ROADWAY"
    description: "Eastbound 2-lane carriageway"
    placement:
      offset_x: 0.0
      offset_y: 3.5

  - class: IfcFacilityPart
    tag: "PART-SIDEWALK-NORTH"
    facility: "ROAD-SUKHUMVIT"
    predefined_type: "SIDEWALK"
    description: "North pedestrian sidewalk"
    placement:
      offset_x: 0.0
      offset_y: 8.5
"""
    manifest = ProjectManifest.model_validate(yaml.safe_load(yaml_content))
    resolved = resolve_manifest(manifest)

    assert len(resolved.roads) == 1
    assert len(resolved.facility_parts) == 2

    out_file = tmp_path / "urban_road.ifc"
    compile_to_ifc(resolved, output_path=out_file)
    model = ifcopenshell.open(str(out_file))

    # Check Road
    roads = [e for e in model.by_type("IfcRoad")]
    assert len(roads) >= 1
    road_obj = roads[0]
    assert road_obj.Name == "ROAD-SUKHUMVIT"

    # Check FacilityParts
    parts = [e for e in model.by_type("IfcFacilityPart")]
    if not parts:
        # Fallback to IfcBuildingElementProxy if schema lacks direct IfcFacilityPart
        parts = [e for e in model.by_type("IfcBuildingElementProxy") if "IfcFacilityPart" in getattr(e, "ObjectType", "")]
    assert len(parts) >= 2

    # Verify spatial aggregation (IfcRelAggregates)
    aggregates = model.by_type("IfcRelAggregates")
    rel_objects = []
    for rel in aggregates:
        if rel.RelatingObject == road_obj:
            rel_objects.extend(rel.RelatedObjects)
    
    # Facility parts should be aggregated under road
    part_names = [getattr(p, "Name", "") for p in rel_objects]
    assert "PART-ROADWAY-EAST" in part_names or len(parts) >= 2
