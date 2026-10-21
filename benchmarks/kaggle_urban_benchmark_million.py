"""
debim-urban: Kaggle Million-Scale Benchmark Lab
------------------------------------------------
High-throughput processing of 100,000+ to 1,000,000 urban elements
via DuckDB + Overture Maps GeoParquet / Geofabrik OSM PBF.

Streams and compiles to IFC4.3 with memory profiling and chunked serialization.
"""

import os
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from debim.civil.gis_ingester import ingest_osm_data, latlon_to_utm_32647
from debim.resolver import resolve_manifest
from debim.compiler import compile_to_ifc
import ifcopenshell


def stream_overture_data(min_lon=100.40, min_lat=13.65, max_lon=100.75, max_lat=13.90, limit=100000):
    """
    Query Greater Bangkok Area directly from Overture Maps S3 bucket using DuckDB.
    """
    import duckdb

    print(f"\n[Data Ingestion] Connecting to Overture Maps S3 via DuckDB...")
    con = duckdb.connect()
    con.install_extension("spatial")
    con.load_extension("spatial")
    con.install_extension("httpfs")
    con.load_extension("httpfs")

    query = f"""
    SELECT 
        id, 
        names.primary AS name,
        height, 
        num_floors,
        ST_AsGeoJSON(geometry) as geojson
    FROM read_parquet('s3://overturemaps-us-west-2/release/2024-09-18.0/theme=buildings/type=building/*', hive_partitioning=true)
    WHERE bbox.xmin BETWEEN {min_lon} AND {max_lon}
      AND bbox.ymin BETWEEN {min_lat} AND {max_lat}
    LIMIT {limit};
    """
    t0 = time.time()
    df = con.execute(query).df()
    t_fetch = time.time() - t0
    print(f"  ✓ Fetched {len(df):,} buildings from cloud in {t_fetch:.2f}s")
    return df


def run_million_scale_benchmark(target_count=100000):
    print("=" * 75)
    print(f"🏙️  debim-urban: Massive Urban Scale Benchmark ({target_count:,} Target Elements)")
    print("=" * 75)

    output_dir = Path("benchmarks/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_debim = output_dir / f"bangkok_{target_count}.debim"
    out_ifc = output_dir / f"bangkok_{target_count}.ifc"

    # 1. Fetching or Synthetic Generation for Stress Test
    t0 = time.time()
    try:
        import duckdb
        df = stream_overture_data(limit=target_count)
        use_synthetic = len(df) == 0
    except Exception as e:
        print(f"Notice: S3 DuckDB streaming not available ({e}), switching to high-throughput synthetic batch generator...")
        use_synthetic = True

    mock_elements = []
    if use_synthetic:
        print(f"Generating {target_count:,} procedural urban assets (Roads, Buildings, Infrastructure)...")
        roads_count = int(target_count * 0.2)
        bldgs_count = target_count - roads_count

        # Procedural Roads
        for i in range(roads_count):
            mock_elements.append({
                "type": "way", "id": 1000000 + i,
                "tags": {"highway": "primary" if i % 5 == 0 else "residential", "lanes": "4" if i % 5 == 0 else "2", "name": f"Highway-TH-{i}"},
                "geometry": [
                    {"lat": 13.70 + (i * 0.0001), "lon": 100.50},
                    {"lat": 13.70 + (i * 0.0001), "lon": 100.60}
                ]
            })

        # Procedural Buildings
        side = int(bldgs_count ** 0.5)
        for r in range(side):
            for c in range(side):
                b_id = 2000000 + (r * side) + c
                lat_base = 13.70 + (r * 0.0005)
                lon_base = 100.50 + (c * 0.0005)
                mock_elements.append({
                    "type": "way", "id": b_id,
                    "tags": {"building": "yes", "building:levels": str(1 + (r % 20)), "name": f"City-Tower-{b_id}"},
                    "geometry": [
                        {"lat": lat_base, "lon": lon_base},
                        {"lat": lat_base + 0.0003, "lon": lon_base},
                        {"lat": lat_base + 0.0003, "lon": lon_base + 0.0003},
                        {"lat": lat_base, "lon": lon_base + 0.0003},
                        {"lat": lat_base, "lon": lon_base},
                    ]
                })

    t_prep = time.time() - t0
    print(f"  ✓ Data ready: {len(mock_elements):,} elements ({t_prep:.2f}s)")

    # 2. Ingest to .debim
    print(f"\n[Pipeline 1/3] Parsing into .debim AST...")
    t1 = time.time()
    manifest = ingest_osm_data({"elements": mock_elements}, crs_epsg=32647, project_name=f"Bangkok {target_count:,} Scale")
    t_ingest = time.time() - t1
    print(f"  ✓ Ingested in {t_ingest:.2f}s ({len(mock_elements) / max(t_ingest, 0.001):,.0f} elements/sec)")

    # 3. Resolve semantics
    print(f"\n[Pipeline 2/3] Resolving Spatial & Coordinate Graph...")
    t2 = time.time()
    resolved = resolve_manifest(manifest)
    t_resolve = time.time() - t2
    print(f"  ✓ Resolved {len(resolved.elements):,} elements in {t_resolve:.2f}s ({len(resolved.elements) / max(t_resolve, 0.001):,.0f} elements/sec)")

    # 4. Compile to IFC4.3
    print(f"\n[Pipeline 3/3] Compiling to IFC4.3 (Memory-Streamed)...")
    t3 = time.time()
    compiled_file = compile_to_ifc(resolved, output_path=out_ifc)
    t_compile = time.time() - t3
    ifc_size_mb = os.path.getsize(compiled_file) / (1024.0 * 1024.0)
    print(f"  ✓ Compiled in {t_compile:.2f}s (File size: {ifc_size_mb:.2f} MB)")

    total_time = t_ingest + t_resolve + t_compile
    print("\n" + "=" * 75)
    print("📈 FINAL BENCHMARK PERFORMANCE RESULTS")
    print("=" * 75)
    print(f" Total Elements:           {len(resolved.elements):,} items")
    print(f" Ingestion Speed:          {len(mock_elements) / max(t_ingest, 0.001):,.0f} elem/sec ({t_ingest:.2f}s)")
    print(f" Resolving Speed:          {len(resolved.elements) / max(t_resolve, 0.001):,.0f} elem/sec ({t_resolve:.2f}s)")
    print(f" Compilation Speed:        {len(resolved.elements) / max(t_compile, 0.001):,.0f} elem/sec ({t_compile:.2f}s)")
    print(f" Total End-to-End Speed:   {len(resolved.elements) / max(total_time, 0.001):,.0f} elem/sec ({total_time:.2f}s)")
    print(f" Output File Size (IFC):   {ifc_size_mb:.2f} MB")
    print("=" * 75)


if __name__ == "__main__":
    count = 100000
    if len(sys.argv) > 1:
        count = int(sys.argv[1])
    run_million_scale_benchmark(target_count=count)
