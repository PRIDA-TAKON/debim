#!/usr/bin/env python3
"""
Automated Golden Fixtures Generator for All IFC Element Classes.
Generates minimal, valid .yaml debim manifests mapped to 5 Geometric Families
(Extruded Solid, Swept Disk, Parametric Assembly, Civil Alignment, Complex Mesh)
for exhaustive round-trip compiler verification.
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

from debim.schema_registry import SchemaEntityRegistry


# Mapping from buildingSMART deprecated StandardCase/ElementedCase to Canonical Base Class
CANONICAL_CLASS_MAP = {
    "IfcBeamStandardCase": "IfcBeam",
    "IfcColumnStandardCase": "IfcColumn",
    "IfcWallStandardCase": "IfcWall",
    "IfcWallElementedCase": "IfcWall",
    "IfcSlabStandardCase": "IfcSlab",
    "IfcSlabElementedCase": "IfcSlab",
    "IfcDoorStandardCase": "IfcDoor",
    "IfcWindowStandardCase": "IfcWindow",
    "IfcPlateStandardCase": "IfcPlate",
    "IfcMemberStandardCase": "IfcMember",
}


# Geometric Family Classification & Dimensions Configuration
GEOMETRIC_FAMILIES = {
    "SweptDisk": {
        "pattern": lambda name: name.endswith("Segment"),
        "dimensions": {"width": 0.3, "depth": 0.3, "height": 3.0},
        "description": "Swept linear segment profile geometry",
    },
    "ParametricAssembly": {
        "pattern": lambda name: name in {
            "IfcCurtainWall", "IfcStair", "IfcStairFlight", "IfcRailing",
            "IfcRoof", "IfcDoor", "IfcWindow", "IfcRamp", "IfcRampFlight"
        },
        "dimensions": {"width": 1.2, "depth": 0.8, "height": 2.4},
        "description": "Parametric architectural assembly element",
    },
    "CivilAlignment": {
        "pattern": lambda name: name in {
            "IfcAlignment", "IfcRoad", "IfcRailway", "IfcBridge",
            "IfcBridgePart", "IfcTrackElement", "IfcEarthworksElement",
            "IfcBearing", "IfcMarineFacility", "IfcMarinePart", "IfcCaissonFoundation"
        },
        "dimensions": {"width": 2.0, "depth": 2.0, "height": 0.5},
        "description": "Civil infrastructure / alignment spatial component",
    },
    "ComplexMesh": {
        "pattern": lambda name: name in {
            "IfcBuildingElementProxy", "IfcDiscreteAccessory", "IfcFastener",
            "IfcMechanicalFastener", "IfcReinforcingBar", "IfcReinforcingMesh"
        },
        "dimensions": {"width": 0.4, "depth": 0.4, "height": 0.4},
        "description": "Generic proxy / accessory mesh component",
    },
    "ExtrudedSolid": {
        "pattern": lambda name: True,  # Fallback default
        "dimensions": {"width": 1.0, "depth": 0.5, "height": 2.0},
        "description": "Extruded prismatic solid profile geometry",
    },
}


def classify_geometric_family(class_name: str) -> Tuple[str, Dict[str, float]]:
    """Determine geometric family and appropriate default dimensions for a class."""
    for family, config in GEOMETRIC_FAMILIES.items():
        if config["pattern"](class_name):
            return family, config["dimensions"]
    return "ExtrudedSolid", GEOMETRIC_FAMILIES["ExtrudedSolid"]["dimensions"]


def build_native_element(class_name: str) -> Optional[Dict[str, Any]]:
    """Construct native debim element dict if class is a first-class native debim type."""
    canonical = CANONICAL_CLASS_MAP.get(class_name, class_name)
    tag = f"{class_name}-01"

    if canonical == "IfcBeam":
        return {
            "class": "IfcBeam",
            "tag": tag,
            "material": "MAT-01",
            "profile": {"shape": "BOX", "width": 0.3, "depth": 0.5},
            "placement": {
                "storey": "L1",
                "from_grid": ["GX1", "GY1"],
                "to_grid": ["GX2", "GY1"],
            },
            "layer": "structure/beams",
        }
    if canonical == "IfcColumn":
        return {
            "class": "IfcColumn",
            "tag": tag,
            "material": "MAT-01",
            "profile": {"shape": "BOX", "width": 0.4, "depth": 0.4},
            "placement": {
                "grid": ["GX1", "GY1"],
                "base_storey": "L1",
                "top_storey": "L2",
            },
            "layer": "structure/columns",
        }
    if canonical == "IfcWall":
        return {
            "class": "IfcWall",
            "tag": tag,
            "material": "MAT-01",
            "thickness": 0.2,
            "height": 3.0,
            "placement": {
                "storey": "L1",
                "from_grid": ["GX1", "GY1"],
                "to_grid": ["GX2", "GY1"],
            },
            "layer": "architecture/walls",
        }
    if canonical == "IfcSlab":
        return {
            "class": "IfcSlab",
            "tag": tag,
            "material": "MAT-01",
            "thickness": 0.2,
            "placement": {
                "storey": "L1",
                "boundary": [
                    ["GX1", "GY1"],
                    ["GX2", "GY1"],
                    ["GX2", "GY2"],
                    ["GX1", "GY2"],
                ],
            },
            "layer": "structure/slabs",
        }
    if canonical == "IfcCovering":
        return {
            "class": "IfcCovering",
            "tag": tag,
            "material": "MAT-01",
            "covering_type": "CEILING",
            "thickness": 0.02,
            "placement": {
                "storey": "L1",
                "boundary": [
                    ["GX1", "GY1"],
                    ["GX2", "GY1"],
                    ["GX2", "GY2"],
                    ["GX1", "GY2"],
                ],
            },
            "layer": "architecture/ceilings",
        }
    if canonical == "IfcRailing":
        return {
            "class": "IfcRailing",
            "tag": tag,
            "material": "MAT-01",
            "height": 1.0,
            "placement": {
                "storey": "L1",
                "from_grid": ["GX1", "GY1"],
                "to_grid": ["GX2", "GY1"],
            },
            "layer": "architecture/railings",
        }
    if canonical == "IfcRoof":
        return {
            "class": "IfcRoof",
            "tag": tag,
            "material": "MAT-01",
            "roof_type": "HIP",
            "placement": {
                "storey": "L1",
                "boundary": [
                    ["GX1", "GY1"],
                    ["GX2", "GY1"],
                    ["GX2", "GY2"],
                    ["GX1", "GY2"],
                ],
                "overhang": 0.0,
            },
            "covering": {
                "pitch": 20.0,
            },
            "layer": "architecture/roofs",
        }

    return None


def generate_manifest_dict(class_name: str, family: str, dims: Dict[str, float]) -> dict:
    """Generate a clean dictionary representation of a golden element manifest."""
    native_elem = build_native_element(class_name)
    if native_elem:
        elements_list = [native_elem]
    else:
        elements_list = [
            {
                "class": "IfcCustomElement",
                "tag": f"{class_name}-01",
                "name": f"{class_name}-GoldenTest",
                "source": f"ifc/{class_name}/{class_name}-01",
                "dimensions": {
                    "width": dims["width"],
                    "depth": dims["depth"],
                    "height": dims["height"],
                },
                "placement": {
                    "position": [0.0, 0.0, 0.0],
                    "rotation": [0.0, 0.0, 0.0],
                    "storey": "L1",
                },
                "layer": f"elements/{family}/{class_name}",
            }
        ]

    return {
        "schema": "IFC4-Minimal",
        "project": {
            "id": f"PRJ-{class_name.upper()}",
            "name": f"Golden Round-Trip Test - {class_name}",
            "units": {
                "length": "METRE",
                "angle": "RADIAN",
                "area": "SQUARE_METRE",
                "volume": "CUBIC_METRE",
            },
        },
        "spatial_structure": {
            "storeys": [
                {
                    "id": "L1",
                    "name": "Level 1",
                    "elevation": 0.0,
                    "height": 3.0,
                },
                {
                    "id": "L2",
                    "name": "Level 2",
                    "elevation": 3.0,
                    "height": 3.0,
                },
            ]
        },
        "grids": {
            "axes_x": {"GX1": 0.0, "GX2": 6.0},
            "axes_y": {"GY1": 0.0, "GY2": 6.0},
        },
        "materials": [
            {
                "id": "MAT-01",
                "name": "Standard Structural Material",
                "category": "CONCRETE",
                "unit_cost_ref": "MAT-01",
            }
        ],
        "elements": elements_list,
    }


def discover_element_classes(schema_version: str = "IFC4", include_features: bool = False) -> List[str]:
    """
    Introspect concrete IfcElement classes from the specified schema.
    By default excludes IfcFeatureElement (openings/voids) which require host attachment.
    """
    reg = SchemaEntityRegistry(schema_version)
    concrete_elements = []
    for name, info in reg._entity_cache.items():
        if name != info.name:
            continue
        if not info.is_element or info.is_abstract:
            continue
        if not include_features and "IfcFeatureElement" in info.inheritance_chain:
            continue
        concrete_elements.append(name)
    return sorted(concrete_elements)


def generate_golden_fixtures(
    output_dir: Path,
    schema_version: str = "IFC4",
    filter_classes: Optional[List[str]] = None,
    limit: Optional[int] = None,
    clean: bool = False,
) -> List[Path]:
    """Generate YAML golden fixture files for all concrete IFC element classes."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if clean:
        for f in output_dir.glob("*.yaml"):
            f.unlink()

    all_classes = discover_element_classes(schema_version)
    if filter_classes:
        allowed = set(filter_classes)
        all_classes = [c for c in all_classes if c in allowed]

    if limit is not None and limit > 0:
        all_classes = all_classes[:limit]

    created_paths = []
    family_counts: Dict[str, int] = {}

    for cls_name in all_classes:
        family, dims = classify_geometric_family(cls_name)
        manifest_data = generate_manifest_dict(cls_name, family, dims)
        file_path = output_dir / f"{cls_name}.yaml"
        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(manifest_data, f, sort_keys=False, default_flow_style=False)
        created_paths.append(file_path)
        family_counts[family] = family_counts.get(family, 0) + 1

    print(f"Generated {len(created_paths)} golden fixtures in: {output_dir}")
    print("Breakdown by Geometric Family:")
    for family, count in sorted(family_counts.items()):
        print(f"  - {family:20s}: {count:3d} classes")

    return created_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate automated golden fixtures for all concrete IFC element classes."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("tests/fixtures/golden_entities"),
        help="Target directory for generated .yaml fixture files (default: tests/fixtures/golden_entities)",
    )
    parser.add_argument(
        "--schema",
        "-s",
        type=str,
        default="IFC4",
        help="Target IFC Schema version: IFC4 or IFC4X3 (default: IFC4)",
    )
    parser.add_argument(
        "--classes",
        "-c",
        type=str,
        default=None,
        help="Comma-separated list of specific classes to generate (optional)",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=None,
        help="Maximum number of fixture files to generate",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean target directory before generating",
    )

    args = parser.parse_args()
    filter_classes = [c.strip() for c in args.classes.split(",")] if args.classes else None

    generate_golden_fixtures(
        output_dir=args.output,
        schema_version=args.schema,
        filter_classes=filter_classes,
        limit=args.limit,
        clean=args.clean,
    )


if __name__ == "__main__":
    main()
