"""
debim-urban: Kaggle Benchmark Starter Lab (Sukhumvit-Asoke Corridor)
-------------------------------------------------------------------
A lightweight benchmark pipeline for ingesting real GIS data (OSM Overpass / GeoJSON)
into debim-urban (.debim) and compiling to full IFC4.3.

Metrics measured:
- Ingestion Latency (ms)
- Compilation Latency (ms)
- Memory & Storage Compression (.debim vs .ifc)
- Entity Counts (Roads, Buildings, Waterways, Spatial Parts)
"""

import time
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from debim.civil.gis_ingester import ingest_gis_to_debim
from debim.schema import load_manifest
from debim.resolver import resolve_manifest
from debim.compiler import compile_to_ifc
import ifcopenshell


def run_benchmark():
    print("=" * 70)
    print("🏙️  debim-urban: Starter Benchmark Lab (Asoke-Sukhumvit BBox)")
    print("=" * 70)

    # 1. Define Target BBox (Asoke-Sukhumvit Intersection, Bangkok)
    # Bounding Box: 13.7340 to 13.7420 N, 100.5580 to 100.5660 E (~800m x 800m urban block)
    bbox = (13.7340, 100.5580, 13.7420, 100.5660)
    output_dir = Path("benchmarks/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    debim_path = output_dir / "asoke_starter.debim"
    ifc_path = output_dir / "asoke_starter.ifc"

    print(f"\n[1/3] Ingesting GIS Data for BBox: {bbox}...")
    t0 = time.time()
    try:
        # Fetch from OSM Overpass or fallback sample
        ingest_gis_to_debim(
            bbox=bbox,
            output_path=debim_path,
            crs_epsg=32647, # WGS 84 / UTM zone 47N
        )
    except Exception as e:
        print(f"Notice: Online Overpass fetch note ({e}), using built-in high-density mock...")
        from debim.civil.gis_ingester import ingest_osm_data
        # High density 50-building + 10-road mock for benchmark
        mock_elements = []
        # Roads
        for i in range(10):
            mock_elements.append({
                "type": "way", "id": 1000 + i,
                "tags": {"highway": "primary" if i < 3 else "residential", "lanes": "4" if i < 3 else "2", "name": f"Road Segment {i+1}"},
                "geometry": [{"lat": 13.734 + i*0.0008, "lon": 100.558}, {"lat": 13.734 + i*0.0008, "lon": 100.566}]
            })
        # Buildings
        for r in range(10):
            for c in range(10):
                b_id = 2000 + (r * 10) + c
                lat_base = 13.7345 + (r * 0.0007)
                lon_base = 100.5585 + (c * 0.0007)
                mock_elements.append({
                    "type": "way", "id": b_id,
                    "tags": {"building": "yes", "building:levels": str(2 + (r % 5) * 3), "name": f"Tower {r+1}-{c+1}"},
                    "geometry": [
                        {"lat": lat_base, "lon": lon_base},
                        {"lat": lat_base + 0.0005, "lon": lon_base},
                        {"lat": lat_base + 0.0005, "lon": lon_base + 0.0005},
                        {"lat": lat_base, "lon": lon_base + 0.0005},
                        {"lat": lat_base, "lon": lon_base},
                    ]
                })
        manifest_obj = ingest_osm_data({"elements": mock_elements}, crs_epsg=32647, project_name="Sukhumvit-Asoke Starter Benchmark")
        import yaml
        dump_data = manifest_obj.model_dump(by_alias=True, exclude_none=True)
        with open(debim_path, "w", encoding="utf-8") as f:
            yaml.dump(dump_data, f, allow_unicode=True)

    t_ingest = time.time() - t0
    debim_size_kb = os.path.getsize(debim_path) / 1024.0
    print(f"  ✓ Ingested successfully in {t_ingest:.3f}s (File size: {debim_size_kb:.1f} KB)")

    # 2. Resolve Manifest
    print("\n[2/3] Resolving Spatial & Civil Semantics...")
    t1 = time.time()
    manifest = load_manifest(debim_path)
    resolved = resolve_manifest(manifest)
    t_resolve = time.time() - t1
    print(f"  ✓ Resolved {len(resolved.elements)} elements in {t_resolve:.3f}s")
    print(f"    - Roads: {len(resolved.roads)}")
    print(f"    - Buildings/Proxies: {len(resolved.proxies)}")
    print(f"    - Facility Parts: {len(getattr(resolved, 'facility_parts', []))}")

    # 3. Compile to IFC4.3
    print("\n[3/3] Compiling to IFC4.3 (buildingSMART Standard)...")
    t2 = time.time()
    compiled_file = compile_to_ifc(resolved, output_path=ifc_path)
    t_compile = time.time() - t2
    ifc_size_kb = os.path.getsize(compiled_file) / 1024.0
    print(f"  ✓ Compiled to IFC4.3 in {t_compile:.3f}s (File size: {ifc_size_kb:.1f} KB)")

    # 4. Validate IFC4.3 Integrity
    print("\n🔬 Validating IFC4.3 Model Integrity...")
    model = ifcopenshell.open(str(compiled_file))
    print(f"  - Schema Version: {model.schema}")
    
    # Check Map Conversion
    map_convs = model.by_type("IfcMapConversion")
    print(f"  - IfcMapConversion: {'Found (' + str(len(map_convs)) + ')' if map_convs else 'Not Found'}")
    if map_convs:
        print(f"    Easting: {map_convs[0].Eastings:.2f}m, Northing: {map_convs[0].Northings:.2f}m")

    total_time = t_ingest + t_resolve + t_compile
    throughput = len(resolved.elements) / max(total_time, 0.001)

    print("\n" + "=" * 70)
    print("📊 BENCHMARK STARTER SUMMARY REPORT")
    print("=" * 70)
    print(f" Total Elements Processed: {len(resolved.elements):,} items")
    print(f" Ingestion Latency:        {t_ingest:.3f} s")
    print(f" Resolving Latency:        {t_resolve:.3f} s")
    print(f" IFC4.3 Compile Latency:   {t_compile:.3f} s")
    print(f" Total Pipeline Time:      {total_time:.3f} s")
    print(f" Throughput:               {throughput:,.1f} elements/sec")
    print(f" Compression Efficiency:   .debim is {ifc_size_kb / max(debim_size_kb, 0.1):.1f}x more compact than IFC4.3")
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()
