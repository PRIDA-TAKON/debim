"""
Schema Exporter and Validator Tool for debim v0.5.0.

Exports enriched debim JSON Schema with deterministic anchor points,
Euler rotations, dimension keys, and coordinate/bounding rules
to root `debim.schema.json` and `spec/debim.schema.json`.
"""

import sys
from pathlib import Path

# Add src/ directory to sys.path if running as standalone script
repo_root = Path(__file__).resolve().parent.parent
src_dir = repo_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from debim.schema import export_json_schema


def main():
    root_schema_path = repo_root / "debim.schema.json"
    spec_schema_path = repo_root / "spec" / "debim.schema.json"

    print("Generating enriched debim JSON schema...")
    schema = export_json_schema(output_path=root_schema_path)

    # Also sync to spec/debim.schema.json
    export_json_schema(output_path=spec_schema_path)

    # Validation check of exported schema rules
    defs = schema.get("$defs", {})
    required_classes = ["IfcWall", "IfcColumn", "IfcBeam", "IfcSlab", "IfcSpace", "IfcFurniture"]

    for cls_name in required_classes:
        if cls_name not in defs:
            raise RuntimeError(f"Missing required class definition in JSON Schema: {cls_name}")
        cls_def = defs[cls_name]
        if "x-debim-anchor-point" not in cls_def:
            raise RuntimeError(f"Missing x-debim-anchor-point metadata in {cls_name}")
        if "x-debim-dimension-keys" not in cls_def:
            raise RuntimeError(f"Missing x-debim-dimension-keys metadata in {cls_name}")

    print(f"Successfully exported debim schema ({len(defs)} definitions):")
    print(f" - {root_schema_path.relative_to(repo_root)}")
    print(f" - {spec_schema_path.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
