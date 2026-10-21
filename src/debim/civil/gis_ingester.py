"""
GIS and OpenStreetMap (OSM) Ingestion Pipeline for debim.
Parses OSM data (Overpass API) and GeoJSON features into native .debim urban schema elements:
- Buildings (footprint + levels/height) -> IfcBuildingElementProxy / IfcSlab
- Roads (highways + lanes/width) -> IfcRoad
- Waterways (drainage + width) -> IfcDistributionFlowElement / IfcMarinePart
Converts WGS84 coordinates (latitude, longitude) to local metric CRS (EPSG:32647).
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.request
import urllib.parse
import yaml

from debim.schema import (
    CRSConfig,
    Dimensions,
    Grids,
    IfcBuildingElementProxy,
    IfcDistributionFlowElement,
    IfcRoad,
    Material,
    ProjectInfo,
    ProjectManifest,
    ProxyPlacement,
    RoadPlacement,
    SpatialStructure,
    Storey,
)


def latlon_to_utm_32647(lat: float, lon: float) -> Tuple[float, float]:
    """
    Convert WGS84 latitude and longitude to UTM Zone 47N (EPSG:32647) Easting and Northing (meters).
    Uses standard Krüger/Redfearn series expansion for WGS84 ellipsoid.
    """
    # Try pyproj if available
    try:
        import pyproj
        transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32647", always_xy=True)
        easting, northing = transformer.transform(lon, lat)
        return float(easting), float(northing)
    except Exception:
        pass

    # Pure Python WGS84 Transverse Mercator formulation
    phi = math.radians(lat)
    lam = math.radians(lon)

    # UTM Zone 47 Central Meridian is 99.0 degrees East
    lam0 = math.radians(99.0)

    # WGS84 ellipsoid parameters
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = 2.0 * f - f * f
    ep2 = e2 / (1.0 - e2)
    k0 = 0.9996
    easting_0 = 500000.0
    northing_0 = 0.0  # Northern hemisphere

    N = a / math.sqrt(1.0 - e2 * (math.sin(phi) ** 2))
    T = math.tan(phi) ** 2
    C = ep2 * (math.cos(phi) ** 2)
    A = (lam - lam0) * math.cos(phi)

    # Meridional distance M
    M = a * (
        (1.0 - e2 / 4.0 - 3.0 * (e2**2) / 64.0 - 5.0 * (e2**3) / 256.0) * phi
        - (3.0 * e2 / 8.0 + 3.0 * (e2**2) / 32.0 + 45.0 * (e2**3) / 1024.0) * math.sin(2.0 * phi)
        + (15.0 * (e2**2) / 256.0 + 45.0 * (e2**3) / 1024.0) * math.sin(4.0 * phi)
        - (35.0 * (e2**3) / 3072.0) * math.sin(6.0 * phi)
    )

    easting = easting_0 + k0 * N * (
        A
        + (1.0 - T + C) * (A**3) / 6.0
        + (5.0 - 18.0 * T + T**2 + 72.0 * C - 58.0 * ep2) * (A**5) / 120.0
    )

    northing = northing_0 + k0 * (
        M
        + N
        * math.tan(phi)
        * (
            (A**2) / 2.0
            + (5.0 - T + 9.0 * C + 4.0 * (C**2)) * (A**4) / 24.0
            + (61.0 - 58.0 * T + T**2 + 600.0 * C - 330.0 * ep2) * (A**6) / 720.0
        )
    )

    return float(round(easting, 3)), float(round(northing, 3))


def latlon_to_utm(lat: float, lon: float, epsg: int = 32647) -> Tuple[float, float]:
    """Convert WGS84 lat/lon to target EPSG UTM coordinates."""
    if epsg == 32647:
        return latlon_to_utm_32647(lat, lon)
    try:
        import pyproj
        transformer = pyproj.Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
        easting, northing = transformer.transform(lon, lat)
        return float(round(easting, 3)), float(round(northing, 3))
    except Exception:
        # Fallback to EPSG:32647
        return latlon_to_utm_32647(lat, lon)


def parse_bbox_string(bbox_str: str) -> Tuple[float, float, float, float]:
    """
    Parse a bbox string formatted as 'lat_min,lon_min,lat_max,lon_max' or
    'south,west,north,east' or 'min_lon,min_lat,max_lon,max_lat'.
    Returns (min_lat, min_lon, max_lat, max_lon).
    """
    parts = [float(p.strip()) for p in bbox_str.split(",") if p.strip()]
    if len(parts) != 4:
        raise ValueError("bbox string must contain exactly 4 comma-separated values: south,west,north,east")

    val1, val2, val3, val4 = parts
    # Check if format is (lat, lon, lat, lon) or (lon, lat, lon, lat)
    # Latitudes are in [-90, 90], Longitudes for Thailand/SE Asia are ~[90, 120]
    if abs(val1) <= 90.0 and abs(val3) <= 90.0 and abs(val2) <= 180.0 and abs(val4) <= 180.0:
        min_lat, max_lat = min(val1, val3), max(val1, val3)
        min_lon, max_lon = min(val2, val4), max(val2, val4)
    else:
        min_lon, max_lon = min(val1, val3), max(val1, val3)
        min_lat, max_lat = min(val2, val4), max(val2, val4)

    return min_lat, min_lon, max_lat, max_lon


def fetch_osm_overpass(
    bbox: Tuple[float, float, float, float],
    endpoint_url: str = "https://overpass-api.de/api/interpreter",
    timeout_sec: int = 25,
) -> Dict[str, Any]:
    """
    Fetch OpenStreetMap data from Overpass API for a bounding box (min_lat, min_lon, max_lat, max_lon).
    Query includes buildings, highways, and waterways with geometry.
    """
    s, w, n, e = bbox
    overpass_ql = f"""[out:json][timeout:{timeout_sec}];
(
  way["building"]({s},{w},{n},{e});
  way["highway"]({s},{w},{n},{e});
  way["waterway"]({s},{w},{n},{e});
  relation["building"]({s},{w},{n},{e});
);
out body geom;
>;
out skel qt;
"""
    data_encoded = urllib.parse.urlencode({"data": overpass_ql}).encode("utf-8")
    req = urllib.request.Request(endpoint_url, data=data_encoded, headers={"User-Agent": "debim-gis-ingester/1.0"})

    with urllib.request.urlopen(req, timeout=timeout_sec + 5) as resp:
        raw_json = resp.read().decode("utf-8")
        return json.loads(raw_json)


def _extract_osm_ways(osm_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract way elements from OSM JSON response, resolving node coordinates if needed."""
    elements = osm_data.get("elements", [])
    nodes_map: Dict[int, Tuple[float, float]] = {}

    for elem in elements:
        if elem.get("type") == "node" and "lat" in elem and "lon" in elem:
            nodes_map[elem["id"]] = (float(elem["lat"]), float(elem["lon"]))

    ways = []
    for elem in elements:
        if elem.get("type") == "way":
            tags = elem.get("tags", {})
            geom = []
            if "geometry" in elem and elem["geometry"]:
                geom = [(float(pt["lat"]), float(pt["lon"])) for pt in elem["geometry"]]
            elif "nodes" in elem:
                geom = [nodes_map[nid] for nid in elem["nodes"] if nid in nodes_map]

            if geom:
                ways.append({
                    "id": elem.get("id"),
                    "tags": tags,
                    "geometry": geom,
                })

    return ways


def ingest_osm_data(
    osm_data: Union[Dict[str, Any], str, Path],
    crs_epsg: int = 32647,
    project_id: str = "PRJ-URBAN-OSM",
    project_name: str = "Ingested OSM Urban Site",
) -> ProjectManifest:
    """
    Ingest OpenStreetMap Overpass JSON data and build a ProjectManifest.
    Converts buildings, highways, and waterways into native .debim urban schema elements.
    """
    if isinstance(osm_data, (str, Path)):
        p = Path(osm_data)
        if p.exists():
            data_dict = json.loads(p.read_text(encoding="utf-8"))
        else:
            data_dict = json.loads(str(osm_data))
    else:
        data_dict = osm_data

    ways = _extract_osm_ways(data_dict)

    # Collect all lat/lon points to establish CRS origin (center or min)
    all_latlon = []
    for w in ways:
        all_latlon.extend(w["geometry"])

    if not all_latlon:
        # Default Bangkok center fallback
        all_latlon = [(13.7563, 100.5018)]

    lats = [pt[0] for pt in all_latlon]
    lons = [pt[1] for pt in all_latlon]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    center_lat = (min_lat + max_lat) / 2.0
    center_lon = (min_lon + max_lon) / 2.0
    origin_easting, origin_northing = latlon_to_utm(center_lat, center_lon, epsg=crs_epsg)

    elements: List[Any] = []
    all_x: List[float] = []
    all_y: List[float] = []

    building_idx = 1
    road_idx = 1
    drain_idx = 1

    for w in ways:
        tags = w["tags"]
        geom = w["geometry"]

        # Convert WGS84 points to local CRS metric coordinates relative to origin
        local_pts = []
        for lat, lon in geom:
            e, n = latlon_to_utm(lat, lon, epsg=crs_epsg)
            lx = round(e - origin_easting, 2)
            ly = round(n - origin_northing, 2)
            local_pts.append([lx, ly])
            all_x.append(lx)
            all_y.append(ly)

        # 1. Building
        if "building" in tags:
            b_type = tags.get("building", "yes")
            levels_raw = tags.get("building:levels", "1")
            try:
                levels = int(float(levels_raw))
            except Exception:
                levels = 1

            height_tag = tags.get("height")
            if height_tag:
                try:
                    clean_h = "".join(c for c in height_tag if c.isdigit() or c == ".")
                    height = float(clean_h)
                except Exception:
                    height = float(levels * 3.5)
            else:
                height = float(levels * 3.5)

            name = tags.get("name", f"Building {building_idx}")

            # Ensure polygon footprint is valid (closed loop or at least 3 points)
            if len(local_pts) >= 3:
                # Remove duplicate closing point for arbitrary profile if present
                pts = list(local_pts)
                if len(pts) > 3 and pts[0] == pts[-1]:
                    pts = pts[:-1]

                proxy_elem = IfcBuildingElementProxy(
                    tag=f"BLDG-{building_idx:03d}",
                    class_="IfcBuildingElementProxy",
                    ifc_class="IfcBuildingElementProxy",
                    material="CONCRETE",
                    geometry={
                        "profile": {
                            "shape": "ARBITRARY",
                            "points": pts,
                        },
                        "extrusion": round(height, 2),
                    },
                    placement=ProxyPlacement(
                        storey="GROUND",
                        position=(0.0, 0.0, 0.0),
                    ),
                    properties={
                        "OSM": {
                            "name": name,
                            "building_type": b_type,
                            "levels": levels,
                            "height": height,
                            "osm_id": w["id"],
                        }
                    },
                    layer="architecture/buildings",
                )
                elements.append(proxy_elem)
                building_idx += 1

        # 2. Highway / Road
        elif "highway" in tags:
            hw_type = tags.get("highway", "carriageway").upper()
            lanes_raw = tags.get("lanes", "2")
            try:
                lanes = int(float(lanes_raw))
            except Exception:
                lanes = 4 if hw_type in ("MOTORWAY", "TRUNK", "PRIMARY") else 2

            width_raw = tags.get("width")
            if width_raw:
                try:
                    clean_w = "".join(c for c in width_raw if c.isdigit() or c == ".")
                    road_w = float(clean_w)
                except Exception:
                    road_w = float(lanes * 3.5)
            else:
                road_w = float(lanes * 3.5)

            # Calculate polyline length
            length = 0.0
            for i in range(len(local_pts) - 1):
                p1 = local_pts[i]
                p2 = local_pts[i + 1]
                length += math.hypot(p2[0] - p1[0], p2[1] - p1[1])

            pts_3d = [[p[0], p[1], 0.0] for p in local_pts]

            road_elem = IfcRoad(
                tag=f"ROAD-{road_idx:03d}",
                class_="IfcRoad",
                material="ASPHALT",
                predefined_type="HIGHWAY" if hw_type in ("MOTORWAY", "TRUNK") else "CARRIAGEWAY",
                road_width=round(road_w, 2),
                corridor_length=round(length, 2),
                lanes_count=lanes,
                placement=RoadPlacement(
                    storey="GROUND",
                    points=pts_3d,
                ),
                layer="civil/infrastructure/roads",
            )
            elements.append(road_elem)
            road_idx += 1

        # 3. Waterway / Drainage
        elif "waterway" in tags:
            ww_type = tags.get("waterway", "drain").upper()
            width_raw = tags.get("width")
            if width_raw:
                try:
                    clean_w = "".join(c for c in width_raw if c.isdigit() or c == ".")
                    ww_width = float(clean_w)
                except Exception:
                    ww_width = 3.0 if ww_type in ("CANAL", "RIVER") else 1.5
            else:
                ww_width = 5.0 if ww_type in ("CANAL", "RIVER") else 1.5

            p_start = local_pts[0]
            p_end = local_pts[-1]

            flow_elem = IfcDistributionFlowElement(
                tag=f"DRAIN-{drain_idx:03d}",
                class_="IfcDistributionFlowElement",
                material="CONCRETE",
                predefined_type="DRAINAGE_CHANNEL" if ww_type in ("CANAL", "STREAM") else "CULVERT",
                internal_span=round(ww_width, 2),
                internal_rise=round(ww_width * 0.75, 2),
                wall_thickness=0.20,
                slab_thickness=0.20,
                placement={
                    "storey": "GROUND",
                    "start_point": [p_start[0], p_start[1], 0.0],
                    "end_point": [p_end[0], p_end[1], 0.0],
                },
                layer="civil/infrastructure/drainage",
            )
            elements.append(flow_elem)
            drain_idx += 1

    # Bounding grids
    if all_x and all_y:
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
    else:
        min_x, max_x = -50.0, 50.0
        min_y, max_y = -50.0, 50.0

    manifest = ProjectManifest(
        schema_version="IFC4X3",
        project=ProjectInfo(
            id=project_id,
            name=project_name,
            site_location=f"WGS84 ({center_lat:.6f}, {center_lon:.6f})",
            crs=CRSConfig(
                epsg=crs_epsg,
                name=f"WGS 84 / UTM zone {crs_epsg - 32600}N",
                easting=round(origin_easting, 2),
                northing=round(origin_northing, 2),
                elevation=0.0,
                rotation=0.0,
                scale=1.0,
            ),
        ),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="GROUND", name="Ground Level", elevation=0.0, height=3.5)
            ]
        ),
        grids=Grids(
            axes_x={"1": round(min_x, 2), "2": round(max_x, 2)},
            axes_y={"A": round(min_y, 2), "B": round(max_y, 2)},
        ),
        materials=[
            Material(
                id="CONCRETE",
                name="Reinforced Concrete",
                category="CONCRETE",
                unit_cost_ref="MAT-CONC",
            ),
            Material(
                id="ASPHALT",
                name="Asphalt Concrete Pavement",
                category="CIVIL",
                unit_cost_ref="MAT-ASPHALT",
            ),
            Material(
                id="MASONRY",
                name="Masonry Block Wall",
                category="MASONRY",
                unit_cost_ref="MAT-MASONRY",
            ),
        ],
        elements=elements,
    )

    return manifest


def ingest_geojson(
    geojson_data: Union[Dict[str, Any], str, Path],
    crs_epsg: int = 32647,
    project_id: str = "PRJ-GEOJSON-URBAN",
    project_name: str = "Ingested GeoJSON Urban Site",
) -> ProjectManifest:
    """
    Ingest GeoJSON FeatureCollection/Features and build a ProjectManifest.
    """
    if isinstance(geojson_data, (str, Path)):
        p = Path(geojson_data)
        if p.exists():
            data_dict = json.loads(p.read_text(encoding="utf-8"))
        else:
            data_dict = json.loads(str(geojson_data))
    else:
        data_dict = geojson_data

    features = []
    if data_dict.get("type") == "FeatureCollection":
        features = data_dict.get("features", [])
    elif data_dict.get("type") == "Feature":
        features = [data_dict]

    # Convert features to OSM-like way dicts
    ways = []
    for idx, feat in enumerate(features, start=1):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        gtype = geom.get("type")
        coords = geom.get("coordinates", [])

        geom_pts = []
        if gtype == "Polygon" and coords:
            geom_pts = [(float(pt[1]), float(pt[0])) for pt in coords[0]]
        elif gtype == "MultiPolygon" and coords:
            geom_pts = [(float(pt[1]), float(pt[0])) for pt in coords[0][0]]
        elif gtype == "LineString" and coords:
            geom_pts = [(float(pt[1]), float(pt[0])) for pt in coords]
        elif gtype == "MultiLineString" and coords:
            geom_pts = [(float(pt[1]), float(pt[0])) for pt in coords[0]]

        if geom_pts:
            ways.append({
                "id": props.get("id", idx),
                "tags": props,
                "geometry": geom_pts,
            })

    osm_format = {"elements": [{"type": "way", "id": w["id"], "tags": w["tags"], "geometry": [{"lat": pt[0], "lon": pt[1]} for pt in w["geometry"]]} for w in ways]}
    return ingest_osm_data(osm_format, crs_epsg=crs_epsg, project_id=project_id, project_name=project_name)


def ingest_gis_to_debim(
    bbox: Optional[Tuple[float, float, float, float]] = None,
    geojson_path: Optional[Union[str, Path]] = None,
    osm_file_path: Optional[Union[str, Path]] = None,
    output_path: Optional[Union[str, Path]] = None,
    crs_epsg: int = 32647,
    timeout_sec: int = 15,
) -> Path:
    """
    High-level ingestion pipeline entry point.
    Reads from bbox (Overpass API), GeoJSON file, or OSM JSON file,
    and emits a .debim manifest file.
    """
    if osm_file_path:
        manifest = ingest_osm_data(osm_file_path, crs_epsg=crs_epsg)
    elif geojson_path:
        manifest = ingest_geojson(geojson_path, crs_epsg=crs_epsg)
    elif bbox:
        osm_json = fetch_osm_overpass(bbox, timeout_sec=timeout_sec)
        manifest = ingest_osm_data(osm_json, crs_epsg=crs_epsg)
    else:
        raise ValueError("Must provide either bbox, geojson_path, or osm_file_path")

    out_p = Path(output_path) if output_path else Path("urban_project.debim")
    out_p.parent.mkdir(parents=True, exist_ok=True)

    dump_data = manifest.model_dump(mode="json", by_alias=True, exclude_none=True)
    header = (
        "# ==============================================================================\n"
        "# Open GIS & OSM Ingested Urban Site Manifest (.debim)\n"
        "# Generated by debim Urban GIS Ingestion Assistant v1.0.0\n"
        "# ==============================================================================\n\n"
    )
    yaml_str = yaml.safe_dump(dump_data, sort_keys=False, allow_unicode=True)
    out_p.write_text(header + yaml_str, encoding="utf-8")

    return out_p.resolve()
