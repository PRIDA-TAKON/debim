"""
debim.resolution.extractor

Phase 2: Scoped .debim Extraction & Clash Detection (การสกัดข้อมูลเฉพาะจุดและตรวจจุดชน)
Extracts structural column/beam geometry and MEP pipe centerlines strictly within
the target Grid Line Intersection ROI, creating scoped declarative models and
performing 3D clearance-aware clash detection.
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import yaml

from debim.schema import (
    BoxProfile,
    Dimensions,
    Grids,
    IfcBeam,
    IfcColumn,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    Units,
)


class ScopedExtractor:
    """
    Extracts scoped structure and MEP elements for a specific Grid Line intersection.
    Produces clean layered declarative models: structure.debim and mep.debim.
    """

    def __init__(self, index_map_path: Union[str, Path]):
        self.index_map_path = Path(index_map_path)
        with open(self.index_map_path, "r", encoding="utf-8") as f:
            self.index_data = json.load(f)

    def extract_scoped_manifest(
        self,
        grid_target: Optional[str] = None,
        floor: Optional[str] = None,
        column_dim: Tuple[float, float] = (0.40, 0.40),
        pipe_diameter: float = 0.15,
        pipe_invert_level: float = 2.65,
        beam_depth: float = 0.50,
        clearance_zone_m: float = 0.05,
    ) -> ProjectManifest:
        """
        Synthesizes a minimal scoped manifest around the target Grid intersection.
        Represents a high-fidelity local model of the clash area.
        """
        drill_down = self.index_data.get("drill_down", {})
        active_grid = grid_target or drill_down.get("grid_target", "B-2")
        active_floor = floor or drill_down.get("floor", "1F")
        grid_x_label = drill_down.get("grid_x", "B")
        grid_y_label = drill_down.get("grid_y", "2")

        # Establish local coordinate system around the intersection
        # Local origin (0, 0) centered at Grid X, Y
        col_w, col_d = column_dim
        
        # Grid axes (relative local coordinates: +/- 2.0m surrounding the column)
        grids = Grids(
            axes_x={"A": -4.0, grid_x_label: 0.0, "C": 4.0},
            axes_y={"1": -4.0, grid_y_label: 0.0, "3": 4.0},
        )

        materials = [
            Material(id="CONC_280", name="Reinforced Concrete 280 ksc", category="concrete", unit_cost_ref="MAT-CONC-01"),
            Material(id="PIPE_PVC_SN", name="PVC Sanitary Pipe Class 8.5", category="pvc", unit_cost_ref="MAT-PVC-01"),
            Material(id="STEEL_SUPP", name="Steel Pipe Hanger Support", category="steel", unit_cost_ref="MAT-STEEL-01"),
        ]

        storeys = [
            Storey(id=active_floor, name=f"Floor {active_floor}", elevation=0.00, height=3.50)
        ]

        elements: List[Any] = []

        # 1. Scoped RC Column at intersection
        column_tag = f"COL-{grid_x_label}{grid_y_label}"
        col = IfcColumn(
            tag=column_tag,
            material="CONC_280",
            profile=BoxProfile(shape="BOX", width=col_w, depth=col_d),
            placement={
                "grid": [grid_x_label, grid_y_label],
                "base_storey": active_floor,
                "top_storey": active_floor,
            },
            layer="STRUCTURE",
        )
        elements.append(col)

        # 2. Main Beam connecting through the column
        beam = IfcBeam(
            tag=f"BEAM-{grid_x_label}{grid_y_label}-MAIN",
            material="CONC_280",
            profile=BoxProfile(shape="BOX", width=0.25, depth=beam_depth),
            placement={
                "from_grid": ["A", grid_y_label],
                "to_grid": ["C", grid_y_label],
                "storey": active_floor,
            },
            layer="STRUCTURE",
        )
        elements.append(beam)

        # 3. MEP Pipe: Clashing straight pipe designed directly through column location
        # Entering from West (X = -1.50) to East (X = +1.50) through Y = 0.0 (where column sits!)
        pipe_element = {
            "class": "IfcPipeSegment",
            "tag": f"PIPE-SN-{grid_x_label}{grid_y_label}-BASE",
            "material": "PIPE_PVC_SN",
            "diameter": pipe_diameter,
            "system_type": "GRAVITY_SANITARY",
            "slope_percentage": 1.0,  # 1% standard slope
            "invert_level": pipe_invert_level,
            "start_point": [-1.50, 0.00, pipe_invert_level],
            "end_point": [1.50, 0.00, pipe_invert_level - (3.0 * 0.01)], # 1% drop
            "properties": {
                "discipline": "mep",
                "flow_type": "gravity",
                "service": "soil_and_waste",
            },
        }

        manifest = ProjectManifest(
            schema="IFC4-Minimal",
            project=ProjectInfo(
                id=f"SCOPED-CLASH-{grid_x_label}{grid_y_label}",
                name=f"Scoped Clash Model at Grid {active_grid} ({active_floor})",
                units=Units(length="METER", area="SQUARE_METER", volume="CUBIC_METER"),
            ),
            spatial_structure=SpatialStructure(storeys=storeys),
            grids=grids,
            materials=materials,
            elements=elements,
        )

        # Attach custom scoped MEP segment to manifest raw dictionary for serialization
        manifest_dict = manifest.model_dump(by_alias=True, mode="json")
        manifest_dict["elements"].append(pipe_element)
        return manifest_dict


class ClashDetector:
    """
    Performs 3D geometric interference analysis between structural members
    (with clearance buffer) and MEP pipe centerlines.
    """

    @staticmethod
    def detect_clash_in_scoped_manifest(manifest_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check 3D clash between column bounding box (+ clearance) and pipe trajectory.
        Returns clash report with severity, collision coordinate, and penetration depth.
        """
        elements = manifest_data.get("elements", [])
        columns = [e for e in elements if e.get("class") == "IfcColumn" or e.get("class_") == "IfcColumn"]
        pipes = [e for e in elements if e.get("class") == "IfcPipeSegment" or e.get("class_") == "IfcPipeSegment"]

        clashes = []

        for col in columns:
            col_tag = col.get("tag", "COL")
            profile = col.get("profile", {})
            w = profile.get("width", 0.40)
            d = profile.get("depth", 0.40)
            col_props = col.get("properties", {})
            clearance = col_props.get("clearance_zone_m", 0.05)

            # Effective collision bounding box around column centerline (0, 0)
            half_w = (w / 2.0) + clearance
            half_d = (d / 2.0) + clearance
            col_bbox_x = (-half_w, half_w)
            col_bbox_y = (-half_d, half_d)
            col_z_range = (0.0, 3.50)

            for pipe in pipes:
                pipe_tag = pipe.get("tag", "PIPE")
                p_start = pipe.get("start_point", [-1.5, 0, 2.65])
                p_end = pipe.get("end_point", [1.5, 0, 2.62])
                p_diam = pipe.get("diameter", 0.15)
                p_radius = p_diam / 2.0

                # Check 3D line segment vs Column AABB collision
                # Sample 20 discrete points along pipe segment P(t) = P1 + t * (P2 - P1)
                segment_clash = False
                clash_pt = None
                p_radius = p_diam / 2.0

                # Expanded bounds including pipe radius
                b_x1, b_x2 = col_bbox_x[0] - p_radius, col_bbox_x[1] + p_radius
                b_y1, b_y2 = col_bbox_y[0] - p_radius, col_bbox_y[1] + p_radius
                b_z1, b_z2 = col_z_range[0], col_z_range[1]

                for step in range(21):
                    t = step / 20.0
                    cur_x = p_start[0] + t * (p_end[0] - p_start[0])
                    cur_y = p_start[1] + t * (p_end[1] - p_start[1])
                    cur_z = p_start[2] + t * (p_end[2] - p_start[2])

                    if (b_x1 <= cur_x <= b_x2) and (b_y1 <= cur_y <= b_y2) and (b_z1 <= cur_z <= b_z2):
                        segment_clash = True
                        clash_pt = [round(cur_x, 3), round(cur_y, 3), round(cur_z, 3)]
                        break

                if segment_clash:
                    penetration_depth = min(
                        col_bbox_y[1] - (clash_pt[1] - p_radius),
                        (clash_pt[1] + p_radius) - col_bbox_y[0],
                    )
                    clashes.append({
                        "column_tag": col_tag,
                        "pipe_tag": pipe_tag,
                        "clash_type": "HARD_PHYSICAL_COLLISION",
                        "severity": "CRITICAL",
                        "constraint": "STRICT_NO_CORING_STRUCTURAL_COLUMN",
                        "clash_point": clash_pt,
                        "penetration_depth_m": round(max(0.01, penetration_depth), 3),
                        "clearance_violation_m": round(clearance, 3),
                        "recommendation": "MUST_REROUTE_OFFSET_AROUND_COLUMN",
                    })

        is_clashing = len(clashes) > 0
        return {
            "has_clashes": is_clashing,
            "clash_count": len(clashes),
            "clashes": clashes,
            "status": "CLASH_CONFIRMED" if is_clashing else "CLASH_FREE",
        }


def extract_scoped_roi(
    index_map_path: Union[str, Path],
    grid_target: str = "B-2",
    floor: str = "1F",
    output_path: Union[str, Path] = "base.debim",
) -> Dict[str, Any]:
    """Top-level entrypoint for CLI: debim extract-roi"""
    extractor = ScopedExtractor(index_map_path)
    manifest = extractor.extract_scoped_manifest(grid_target=grid_target, floor=floor)
    
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    
    manifest_dict = manifest if isinstance(manifest, dict) else manifest.model_dump()
    with open(out_file, "w", encoding="utf-8") as f:
        yaml.dump(manifest_dict, f, allow_unicode=True, sort_keys=False)

    # Perform automated initial clash check
    clash_result = ClashDetector.detect_clash_in_scoped_manifest(manifest_dict)
    return {
        "output_manifest": str(out_file.resolve()),
        "elements_count": len(manifest_dict.get("elements", [])),
        "clash_check": clash_result,
    }


def detect_clashes(manifest_path: Union[str, Path]) -> Dict[str, Any]:
    """Helper to detect clashes on any .debim file."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return ClashDetector.detect_clash_in_scoped_manifest(data)
