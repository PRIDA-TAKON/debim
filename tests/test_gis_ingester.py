"""
Unit tests for Open GIS to .debim Ingestion Pipeline (debim urban ingest).
Tests WGS84 -> UTM EPSG:32647 conversion, OSM building/road/waterway parsing,
GeoJSON ingestion, and CLI sub-command execution.
"""

import json
import pytest
from pathlib import Path

from debim.civil.gis_ingester import (
    latlon_to_utm_32647,
    latlon_to_utm,
    parse_bbox_string,
    ingest_osm_data,
    ingest_geojson,
    ingest_gis_to_debim,
)
from debim.schema import load_manifest, ProjectManifest
from debim.cli import app
from cli_runner import CliRunner


def test_latlon_to_utm_conversion():
    """Test WGS84 to UTM Zone 47N (EPSG:32647) coordinate projection."""
    # Bangkok Grand Palace coordinates: 13.7500 N, 100.4913 E
    easting, northing = latlon_to_utm_32647(13.7500, 100.4913)

    # Expected Easting ~661225m, Northing ~1520703m
    assert 660000.0 <= easting <= 663000.0
    assert 1519000.0 <= northing <= 1522000.0

    # General function fallback check
    e2, n2 = latlon_to_utm(13.7500, 100.4913, epsg=32647)
    assert pytest.approx(easting, 0.01) == e2
    assert pytest.approx(northing, 0.01) == n2


def test_parse_bbox_string():
    """Test parsing bounding box strings."""
    s, w, n, e = parse_bbox_string("13.75,100.50,13.76,100.51")
    assert s == 13.75
    assert w == 100.50
    assert n == 13.76
    assert e == 100.51

    # Alternative ordering (min_lon, min_lat, max_lon, max_lat)
    s2, w2, n2, e2 = parse_bbox_string("100.50,13.75,100.51,13.76")
    assert s2 == 13.75
    assert w2 == 100.50
    assert n2 == 13.76
    assert e2 == 100.51


def test_ingest_osm_data():
    """Test parsing OpenStreetMap ways (buildings, roads, waterways) into .debim urban schema."""
    sample_osm = {
        "elements": [
            {
                "type": "way",
                "id": 101,
                "tags": {
                    "building": "commercial",
                    "building:levels": "4",
                    "name": "Asoke Smart Tower",
                },
                "geometry": [
                    {"lat": 13.750, "lon": 100.500},
                    {"lat": 13.751, "lon": 100.500},
                    {"lat": 13.751, "lon": 100.501},
                    {"lat": 13.750, "lon": 100.501},
                    {"lat": 13.750, "lon": 100.500},
                ],
            },
            {
                "type": "way",
                "id": 102,
                "tags": {
                    "highway": "primary",
                    "lanes": "4",
                    "width": "14",
                    "name": "Sukhumvit Road",
                },
                "geometry": [
                    {"lat": 13.749, "lon": 100.499},
                    {"lat": 13.752, "lon": 100.502},
                ],
            },
            {
                "type": "way",
                "id": 103,
                "tags": {
                    "waterway": "canal",
                    "width": "6",
                    "name": "Khlong Saen Saeb",
                },
                "geometry": [
                    {"lat": 13.748, "lon": 100.498},
                    {"lat": 13.753, "lon": 100.503},
                ],
            },
        ]
    }

    manifest = ingest_osm_data(sample_osm, crs_epsg=32647)
    assert isinstance(manifest, ProjectManifest)
    assert manifest.project.crs is not None
    assert manifest.project.crs.epsg == 32647

    # Validate elements breakdown
    buildings = [e for e in manifest.elements if getattr(e, "class_", "") == "IfcBuildingElementProxy"]
    roads = [e for e in manifest.elements if getattr(e, "class_", "") == "IfcRoad"]
    waterways = [e for e in manifest.elements if getattr(e, "class_", "") == "IfcDistributionFlowElement"]

    assert len(buildings) == 1
    assert len(roads) == 1
    assert len(waterways) == 1

    # Check building properties
    bldg = buildings[0]
    assert bldg.tag == "BLDG-001"
    assert bldg.properties["OSM"]["building_type"] == "commercial"
    assert bldg.properties["OSM"]["levels"] == 4
    ext_val = getattr(bldg.geometry, "extrusion", None) or bldg.geometry.get("extrusion")
    assert pytest.approx(ext_val, 0.1) == 14.0  # 4 levels * 3.5m

    # Check road properties
    road = roads[0]
    assert road.tag == "ROAD-001"
    assert road.road_width == 14.0
    assert road.lanes_count == 4
    assert road.predefined_type in ("HIGHWAY", "CARRIAGEWAY")

    # Check waterway properties
    ww = waterways[0]
    assert ww.tag == "DRAIN-001"
    assert ww.internal_span == 6.0


def test_ingest_geojson():
    """Test parsing GeoJSON FeatureCollection into .debim urban schema."""
    sample_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": 201,
                    "building": "residential",
                    "building:levels": "2",
                    "name": "Baan Thai House",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [100.500, 13.750],
                        [100.500, 13.751],
                        [100.501, 13.751],
                        [100.501, 13.750],
                        [100.500, 13.750],
                    ]],
                },
            },
            {
                "type": "Feature",
                "properties": {
                    "id": 202,
                    "highway": "secondary",
                    "lanes": 2,
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [100.499, 13.749],
                        [100.502, 13.752],
                    ],
                },
            },
        ],
    }

    manifest = ingest_geojson(sample_geojson, crs_epsg=32647)
    assert isinstance(manifest, ProjectManifest)
    assert len(manifest.elements) == 2


def test_cli_urban_ingest(tmp_path):
    """Test CLI subcommand 'debim urban ingest'."""
    osm_file = tmp_path / "test_site.osm.json"
    osm_file.write_text(json.dumps({
        "elements": [
            {
                "type": "way",
                "id": 301,
                "tags": {"building": "yes", "building:levels": "3"},
                "geometry": [
                    {"lat": 13.750, "lon": 100.500},
                    {"lat": 13.751, "lon": 100.500},
                    {"lat": 13.751, "lon": 100.501},
                    {"lat": 13.750, "lon": 100.500},
                ],
            }
        ]
    }), encoding="utf-8")

    out_file = tmp_path / "output_urban.debim"

    runner = CliRunner()
    result = runner.invoke(app, ["urban", "ingest", "--from-file", str(osm_file), "-o", str(out_file)])
    assert result.exit_code == 0
    assert "Open GIS to .debim Urban Ingestion Complete!" in result.stdout
    assert out_file.exists()

    loaded = load_manifest(out_file)
    assert loaded.project.crs.epsg == 32647
    assert len(loaded.elements) == 1


def test_ingest_gis_to_debim_geojson_file(tmp_path):
    """Test ingest_gis_to_debim with a GeoJSON file."""
    geojson_file = tmp_path / "site.geojson"
    geojson_file.write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"highway": "residential", "width": "8"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[100.50, 13.75], [100.51, 13.75]],
                },
            }
        ]
    }), encoding="utf-8")

    out_file = tmp_path / "geojson_urban.debim"
    result_path = ingest_gis_to_debim(geojson_path=geojson_file, output_path=out_file)
    assert result_path.exists()

    manifest = load_manifest(result_path)
    assert len(manifest.elements) == 1
