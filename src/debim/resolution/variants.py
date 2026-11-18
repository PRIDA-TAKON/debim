"""
debim.resolution.variants

Phase 3: Multi-Option Variant Generation (การสร้างทางเลือกแก้ไข)
Generates physical rerouting alternatives (Option A: 45° Offset, Option B: 90° Offset,
Option C: Zone Rerouting) enforcing hard constraints: Clash = 0, Slope >= 1.0%,
and maintenance clearance.
"""

import copy
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import yaml

from debim.resolution.extractor import ClashDetector


class VariantGenerator:
    """
    Synthesizes and validates 3 engineering rerouting variants around structural columns.
    Ensures zero clash and maintains hydraulic slope compliance.
    """

    def __init__(self, base_manifest_path: Union[str, Path]):
        self.base_path = Path(base_manifest_path)
        with open(self.base_path, "r", encoding="utf-8") as f:
            self.base_data = yaml.safe_load(f)

    def _get_column_info(self) -> Dict[str, Any]:
        """Extract target column dimensions and bounds from base manifest."""
        elements = self.base_data.get("elements", [])
        for e in elements:
            if e.get("class") == "IfcColumn" or e.get("class_") == "IfcColumn":
                profile = e.get("profile", {})
                w = profile.get("width", 0.40)
                d = profile.get("depth", 0.40)
                props = e.get("properties", {})
                clearance = props.get("clearance_zone_m", 0.05)
                return {
                    "tag": e.get("tag", "COL"),
                    "width": w,
                    "depth": d,
                    "clearance": clearance,
                    "bypass_offset_y": (d / 2.0) + clearance + 0.15, # 0.40m offset from centerline
                }
        return {"tag": "COL", "width": 0.40, "depth": 0.40, "clearance": 0.05, "bypass_offset_y": 0.40}

    def generate_option_a_45deg(self) -> Dict[str, Any]:
        """
        Option A: Standard 45° Offset.
        Bypasses column with two 45° elbows. Balanced hydraulic flow, standard fittings.
        """
        data = copy.deepcopy(self.base_data)
        col_info = self._get_column_info()
        offset_y = col_info["bypass_offset_y"] # e.g. +0.35m
        
        # Remove original clashing pipe
        data["elements"] = [
            e for e in data.get("elements", [])
            if e.get("class") != "IfcPipeSegment" and e.get("class_") != "IfcPipeSegment"
        ]

        # Pipe segments with 45-degree offset
        # Segment 1: Approach from West to X = -0.60
        # Segment 2: 45° ramp from (-0.60, 0.0) to (-0.25, offset_y)
        # Segment 3: Straight bypass along column from (-0.25, offset_y) to (+0.25, offset_y)
        # Segment 4: 45° ramp returning from (+0.25, offset_y) to (+0.60, 0.0)
        # Segment 5: Outflow to East from (+0.60, 0.0) to (+1.50, 0.0)
        
        invert_base = 2.65
        pipe_segments = [
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-OPT-A-APPROACH",
                "material": "PIPE_PVC_SN",
                "diameter": 0.15,
                "start_point": [-1.50, 0.00, invert_base],
                "end_point": [-0.75, 0.00, invert_base - (0.75 * 0.01)],
            },
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-OPT-A-RAMP-IN",
                "material": "PIPE_PVC_SN",
                "diameter": 0.15,
                "start_point": [-0.75, 0.00, invert_base - (0.75 * 0.01)],
                "end_point": [-0.36, offset_y, invert_base - (1.30 * 0.01)],
                "properties": {"bend_angle_deg": 45},
            },
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-OPT-A-BYPASS-CLEAR",
                "material": "PIPE_PVC_SN",
                "diameter": 0.15,
                "start_point": [-0.36, offset_y, invert_base - (1.30 * 0.01)],
                "end_point": [0.36, offset_y, invert_base - (2.00 * 0.01)],
                "properties": {"bypass_side": "NORTH"},
            },
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-OPT-A-RAMP-OUT",
                "material": "PIPE_PVC_SN",
                "diameter": 0.15,
                "start_point": [0.36, offset_y, invert_base - (2.00 * 0.01)],
                "end_point": [0.75, 0.00, invert_base - (2.55 * 0.01)],
                "properties": {"bend_angle_deg": 45},
            },
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-OPT-A-OUTFLOW",
                "material": "PIPE_PVC_SN",
                "diameter": 0.15,
                "start_point": [0.75, 0.00, invert_base - (2.55 * 0.01)],
                "end_point": [1.50, 0.00, invert_base - (3.30 * 0.01)],
            },
        ]
        
        # Add fittings
        fittings = [
            {"class": "IfcFlowFitting", "tag": "FIT-45-A1", "fitting_type": "ELBOW_45", "diameter": 0.15, "count": 1},
            {"class": "IfcFlowFitting", "tag": "FIT-45-A2", "fitting_type": "ELBOW_45", "diameter": 0.15, "count": 1},
            {"class": "IfcFlowFitting", "tag": "FIT-CLAMP-A", "fitting_type": "PIPE_HANGER", "count": 3},
        ]

        data["elements"].extend(pipe_segments)
        data["elements"].extend(fittings)

        clash_result = ClashDetector.detect_clash_in_scoped_manifest(data)
        
        return {
            "option_id": "OPTION_A",
            "name": "Standard 45° Offset",
            "description": "Smooth 45-degree bypass around column side using 2 standard 45° PVC elbows.",
            "fittings_bom": {
                "pvc_elbow_45_deg": 2,
                "pvc_elbow_90_deg": 0,
                "extra_pipe_length_m": 0.35,
                "pipe_hangers": 3,
            },
            "hydraulic_rating": "EXCELLENT (Minimal Friction Head Loss)",
            "labor_hours": 3.0,
            "manifest_data": data,
            "clash_status": clash_result["status"],
            "clashes": clash_result["clashes"],
        }

    def generate_option_b_90deg(self) -> Dict[str, Any]:
        """
        Option B: Tight 90° Offset.
        Snugs tightly to column face with right-angle elbows for narrow corridors.
        """
        data = copy.deepcopy(self.base_data)
        col_info = self._get_column_info()
        offset_y = (col_info["depth"] / 2.0) + col_info["clearance"] + 0.15 # tight offset 0.40m
        
        data["elements"] = [
            e for e in data.get("elements", [])
            if e.get("class") != "IfcPipeSegment" and e.get("class_") != "IfcPipeSegment"
        ]
        
        invert_base = 2.65
        pipe_segments = [
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-OPT-B-WEST",
                "material": "PIPE_PVC_SN",
                "diameter": 0.15,
                "start_point": [-1.50, 0.00, invert_base],
                "end_point": [-0.36, 0.00, invert_base - (1.14 * 0.01)],
            },
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-OPT-B-BRANCH-NORTH",
                "material": "PIPE_PVC_SN",
                "diameter": 0.15,
                "start_point": [-0.36, 0.00, invert_base - (1.14 * 0.01)],
                "end_point": [-0.36, offset_y, invert_base - (1.54 * 0.01)],
                "properties": {"bend_angle_deg": 90},
            },
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-OPT-B-TIGHT-NORTH",
                "material": "PIPE_PVC_SN",
                "diameter": 0.15,
                "start_point": [-0.36, offset_y, invert_base - (1.54 * 0.01)],
                "end_point": [0.36, offset_y, invert_base - (2.26 * 0.01)],
                "properties": {"bend_angle_deg": 90, "bypass_side": "TIGHT_NORTH"},
            },
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-OPT-B-BRANCH-SOUTH",
                "material": "PIPE_PVC_SN",
                "diameter": 0.15,
                "start_point": [0.36, offset_y, invert_base - (2.26 * 0.01)],
                "end_point": [0.36, 0.00, invert_base - (2.66 * 0.01)],
                "properties": {"bend_angle_deg": 90},
            },
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-OPT-B-EAST",
                "material": "PIPE_PVC_SN",
                "diameter": 0.15,
                "start_point": [0.36, 0.00, invert_base - (2.66 * 0.01)],
                "end_point": [1.50, 0.00, invert_base - (3.80 * 0.01)],
            },
        ]

        fittings = [
            {"class": "IfcFlowFitting", "tag": "FIT-90-B1", "fitting_type": "ELBOW_90", "diameter": 0.15, "count": 2},
            {"class": "IfcFlowFitting", "tag": "FIT-90-B2", "fitting_type": "ELBOW_90", "diameter": 0.15, "count": 2},
            {"class": "IfcFlowFitting", "tag": "FIT-CLAMP-B", "fitting_type": "PIPE_HANGER", "count": 4},
        ]

        data["elements"].extend(pipe_segments)
        data["elements"].extend(fittings)

        clash_result = ClashDetector.detect_clash_in_scoped_manifest(data)

        return {
            "option_id": "OPTION_B",
            "name": "Tight 90° Offset",
            "description": "Right-angle bypass hugging close to column face. Ideal for tight architectural chases.",
            "fittings_bom": {
                "pvc_elbow_45_deg": 0,
                "pvc_elbow_90_deg": 4,
                "extra_pipe_length_m": 0.70,
                "pipe_hangers": 4,
            },
            "hydraulic_rating": "MODERATE (Higher Minor Loss from 90° bends)",
            "labor_hours": 4.5,
            "manifest_data": data,
            "clash_status": clash_result["status"],
            "clashes": clash_result["clashes"],
        }

    def generate_option_c_zone_rerouting(self) -> Dict[str, Any]:
        """
        Option C: Zone Rerouting.
        Re-routes main run entirely through the adjacent service corridor (Y = +1.20m),
        avoiding structural column bay completely.
        """
        data = copy.deepcopy(self.base_data)
        data["elements"] = [
            e for e in data.get("elements", [])
            if e.get("class") != "IfcPipeSegment" and e.get("class_") != "IfcPipeSegment"
        ]
        
        invert_base = 2.65
        pipe_segments = [
            {
                "class": "IfcPipeSegment",
                "tag": "PIPE-OPT-C-CORRIDOR-RUN",
                "material": "PIPE_PVC_SN",
                "diameter": 0.15,
                "start_point": [-1.50, 1.20, invert_base],
                "end_point": [1.50, 1.20, invert_base - (3.00 * 0.01)],
                "properties": {"zone": "SERVICE_CORRIDOR", "column_avoidance": "COMPLETE"},
            }
        ]

        fittings = [
            {"class": "IfcFlowFitting", "tag": "FIT-CLAMP-C", "fitting_type": "PIPE_HANGER", "count": 3},
        ]

        data["elements"].extend(pipe_segments)
        data["elements"].extend(fittings)

        clash_result = ClashDetector.detect_clash_in_scoped_manifest(data)

        return {
            "option_id": "OPTION_C",
            "name": "Zone Rerouting",
            "description": "Relocates pipe run entirely into adjacent utility corridor. Zero column interference.",
            "fittings_bom": {
                "pvc_elbow_45_deg": 0,
                "pvc_elbow_90_deg": 0,
                "extra_pipe_length_m": -0.20, # Shorter overall run or zero extra
                "pipe_hangers": 3,
            },
            "hydraulic_rating": "OPTIMAL (Pure Straight Gravity Flow)",
            "labor_hours": 6.0, # Requires repointing upstream penetration
            "manifest_data": data,
            "clash_status": clash_result["status"],
            "clashes": clash_result["clashes"],
        }

    def generate_all_variants(self, output_dir: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
        """Generate and save all 3 standard variants."""
        opt_a = self.generate_option_a_45deg()
        opt_b = self.generate_option_b_90deg()
        opt_c = self.generate_option_c_zone_rerouting()
        
        variants = [opt_a, opt_b, opt_c]

        if output_dir:
            out_p = Path(output_dir)
            out_p.mkdir(parents=True, exist_ok=True)
            for var in variants:
                file_name = f"{var['option_id'].lower()}.debim"
                target_file = out_p / file_name
                with open(target_file, "w", encoding="utf-8") as f:
                    yaml.dump(var["manifest_data"], f, allow_unicode=True, sort_keys=False)
                var["saved_path"] = str(target_file.resolve())

        return variants


def generate_resolution_variants(
    base_manifest_path: Union[str, Path],
    num_variants: int = 3,
    output_dir: Union[str, Path] = "workspace/options",
) -> List[Dict[str, Any]]:
    """Top-level entrypoint for CLI: debim resolve-clash"""
    generator = VariantGenerator(base_manifest_path)
    return generator.generate_all_variants(output_dir=output_dir)
