"""
debim.engineering.civil
Civil & Site Infrastructure Engineering for Hyperscale Data Centers and Industrial Campuses.
"""

import math
from typing import List, Dict, Any, Tuple, Optional

def calculate_stormwater_retention(
    impervious_area_m2: float,
    design_factor: float = 0.12,
    runoff_coefficient: float = 0.90,
    design_storm_depth_mm: Optional[float] = None
) -> Dict[str, Any]:
    """
    Sizes data center stormwater retention basins.
    Matches benchmark rule: surface area >= design_factor (default 12%) of impervious area,
    or volumetric sizing based on design storm depth (Rational / SCS curve).
    """
    required_area_m2 = impervious_area_m2 * design_factor
    
    # If storm depth given (e.g. 50 mm / 2-inch storm): Volume = C * P * A
    volume_m3 = None
    if design_storm_depth_mm is not None:
        rainfall_m = design_storm_depth_mm / 1000.0
        volume_m3 = runoff_coefficient * rainfall_m * impervious_area_m2
    else:
        # Assuming average effective water depth of 1.5 m
        volume_m3 = required_area_m2 * 1.5
        
    return {
        "impervious_area_m2": round(impervious_area_m2, 2),
        "design_factor": design_factor,
        "required_retention_area_m2": round(required_area_m2, 2),
        "estimated_retention_volume_m3": round(volume_m3, 2),
        "assumed_depth_m": 1.5 if design_storm_depth_mm is None else round(volume_m3 / required_area_m2, 2)
    }

def check_environmental_setbacks(
    building_footprints: List[Dict[str, Any]],
    property_boundary: List[Tuple[float, float]],
    wetland_polygons: List[List[Tuple[float, float]]],
    min_property_setback_m: float = 18.0,
    min_wetland_buffer_m: float = 0.0
) -> Dict[str, Any]:
    """
    Validates setback distances from site boundaries and wetland buffers.
    Uses point-to-polygon and polygon-to-polygon minimum Euclidean distance.
    """
    violations = []
    
    def min_dist_pt_to_seg(p, a, b):
        px, py = p
        ax, ay = a
        bx, by = b
        dx = bx - ax
        dy = by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        proj_x = ax + t * dx
        proj_y = ay + t * dy
        return math.hypot(px - proj_x, py - proj_y)

    for b in building_footprints:
        b_id = b.get("id", "unknown")
        pts = b.get("points", [])
        
        # Check against property boundary segments
        min_prop_dist = float("inf")
        n_prop = len(property_boundary)
        for p in pts:
            for i in range(n_prop):
                p1 = property_boundary[i]
                p2 = property_boundary[(i + 1) % n_prop]
                dist = min_dist_pt_to_seg(p, p1, p2)
                if dist < min_prop_dist:
                    min_prop_dist = dist
                    
        if min_prop_dist < min_property_setback_m:
            violations.append({
                "building": b_id,
                "type": "property_setback",
                "distance_m": round(min_prop_dist, 3),
                "required_m": min_property_setback_m,
                "deficit_m": round(min_property_setback_m - min_prop_dist, 3)
            })
            
        # Check against wetlands
        for w_idx, wetland in enumerate(wetland_polygons):
            min_w_dist = float("inf")
            n_w = len(wetland)
            for p in pts:
                for i in range(n_w):
                    w1 = wetland[i]
                    w2 = wetland[(i + 1) % n_w]
                    dist = min_dist_pt_to_seg(p, w1, w2)
                    if dist < min_w_dist:
                        min_w_dist = dist
                        
            if min_w_dist < min_wetland_buffer_m:
                violations.append({
                    "building": b_id,
                    "type": "wetland_buffer",
                    "wetland_index": w_idx,
                    "distance_m": round(min_w_dist, 3),
                    "required_m": min_wetland_buffer_m,
                    "deficit_m": round(min_wetland_buffer_m - min_w_dist, 3)
                })

    return {
        "pass": len(violations) == 0,
        "violations": violations,
        "total_buildings_checked": len(building_footprints)
    }

def calculate_noise_attenuation(
    generator_sound_power_db: float,
    distance_to_boundary_m: float,
    barrier_attenuation_db: float = 0.0,
    ground_absorption_factor: float = 0.5
) -> Dict[str, Any]:
    """
    Calculates sound pressure level (dBA) at site boundary from standby generators.
    Formula: Lp = Lw - 20*log10(r) - 11 - A_barrier + A_ground
    """
    if distance_to_boundary_m <= 0:
        distance_to_boundary_m = 1.0
        
    divergence_loss = 20.0 * math.log10(distance_to_boundary_m) + 11.0
    ground_loss = ground_absorption_factor * 2.0
    
    spl_boundary = generator_sound_power_db - divergence_loss - barrier_attenuation_db - ground_loss
    
    return {
        "generator_sound_power_db": generator_sound_power_db,
        "distance_to_boundary_m": round(distance_to_boundary_m, 2),
        "barrier_attenuation_db": barrier_attenuation_db,
        "sound_pressure_level_at_boundary_dba": round(spl_boundary, 2),
        "compliant_with_residential_55dba": spl_boundary <= 55.0,
        "compliant_with_commercial_65dba": spl_boundary <= 65.0
    }
