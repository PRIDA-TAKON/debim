"""
debim.engineering.structural
Structural Analysis, Diaphragm Shear, Wind & Seismic Forces, and Foundation Calculations.
Conforming to ASCE 7-16/22, IBC, and ACI 318 standards.
"""

import math
from typing import Dict, Any, List, Optional

def calculate_wind_diaphragm_shear(
    basic_wind_speed_mph: float,
    building_length_ft: float,
    building_width_ft: float,
    mean_roof_height_ft: float,
    exposure_category: str = "C",
    risk_category: str = "IV", # Data Centers are Risk Category IV
    wall_sheathing_type: str = "tiltup_concrete"
) -> Dict[str, Any]:
    """
    Calculates design wind velocity pressure, total roof diaphragm lateral shear,
    and unit shear (plf) across main lateral force resisting system (MLFRS) per ASCE 7.
    """
    # 1. Importance factor / velocity pressure constants
    # Risk category IV for critical infrastructure (data centers)
    kd = 0.85 # Wind directionality factor
    kzt = 1.0 # Topographic factor
    ke = 1.0 # Ground elevation factor
    
    # Exposure coefficients Kz at mean roof height
    z = max(15.0, mean_roof_height_ft)
    if exposure_category.upper() == "B":
        kz = 2.01 * (z / 1200.0) ** (2.0 / 7.0)
    elif exposure_category.upper() == "D":
        kz = 2.01 * (z / 700.0) ** (2.0 / 11.5)
    else: # Category C (Default open terrain)
        kz = 2.01 * (z / 900.0) ** (2.0 / 9.5)
        
    # Velocity pressure qz (psf) = 0.00256 * Kz * Kzt * Kd * Ke * V^2
    qz = 0.00256 * kz * kzt * kd * ke * (basic_wind_speed_mph ** 2)
    
    # Gust effect factor G = 0.85 (rigid structures)
    G = 0.85
    
    # External pressure coefficients (Wall Windward Cp = 0.8, Leeward Cp = -0.5)
    cp_windward = 0.8
    cp_leeward = -0.5
    net_wall_cp = cp_windward - cp_leeward # 1.3
    
    # Tributary height to roof diaphragm = h / 2
    tributary_height_ft = mean_roof_height_ft / 2.0
    
    # Wind along width (loading on length)
    wind_force_on_length_lbs = qz * G * net_wall_cp * building_length_ft * tributary_height_ft
    unit_shear_along_width_plf = wind_force_on_length_lbs / (2.0 * building_width_ft)
    
    # Wind along length (loading on width)
    wind_force_on_width_lbs = qz * G * net_wall_cp * building_width_ft * tributary_height_ft
    unit_shear_along_length_plf = wind_force_on_width_lbs / (2.0 * building_length_ft)
    
    return {
        "qz_psf": round(qz, 2),
        "kz": round(kz, 3),
        "wind_force_loading_length_lbs": round(wind_force_on_length_lbs, 1),
        "wind_force_loading_width_lbs": round(wind_force_on_width_lbs, 1),
        "unit_shear_along_width_plf": round(unit_shear_along_width_plf, 2),
        "unit_shear_along_length_plf": round(unit_shear_along_length_plf, 2),
        "max_unit_shear_plf": round(max(unit_shear_along_width_plf, unit_shear_along_length_plf), 2),
        "governing_direction": "width_reaction" if unit_shear_along_width_plf >= unit_shear_along_length_plf else "length_reaction"
    }

def calculate_seismic_diaphragm_shear(
    s_ds: float,
    diaphragm_weight_kips: float,
    building_length_ft: float,
    building_width_ft: float,
    risk_category: str = "IV",
    r_factor: float = 3.0 # Ordinary steel braced or concrete shear wall
) -> Dict[str, Any]:
    """
    Calculates seismic diaphragm design force Fpx and unit shear per ASCE 7 Section 12.10.
    Fpx = (C_px * w_px) where 0.2*S_ds*Ie*wp <= Fpx <= 0.4*S_ds*Ie*wp.
    """
    # Importance factor Ie for Risk Category IV = 1.5
    ie = 1.5 if risk_category.upper() == "IV" else 1.0
    
    # Base diaphragm acceleration coefficient
    c_px = (0.4 * s_ds * ie)
    c_px_min = (0.2 * s_ds * ie)
    c_px_max = (0.4 * s_ds * ie)
    
    governing_cpx = max(c_px_min, min(c_px_max, c_px))
    f_px_kips = governing_cpx * diaphragm_weight_kips
    
    # Unit shears along both directions (plf)
    shear_width_plf = (f_px_kips * 1000.0) / (2.0 * building_width_ft)
    shear_length_plf = (f_px_kips * 1000.0) / (2.0 * building_length_ft)
    
    return {
        "s_ds": s_ds,
        "importance_factor_ie": ie,
        "governing_cpx": round(governing_cpx, 4),
        "f_px_kips": round(f_px_kips, 2),
        "unit_shear_width_plf": round(shear_width_plf, 2),
        "unit_shear_length_plf": round(shear_length_plf, 2),
        "max_seismic_unit_shear_plf": round(max(shear_width_plf, shear_length_plf), 2)
    }

def calculate_footing_settlement_clay(
    footing_width_b_m: float,
    footing_length_l_m: float,
    applied_load_kn: float,
    clay_layer_thickness_h_m: float,
    initial_void_ratio_e0: float,
    compression_index_cc: float,
    initial_effective_stress_kpa: float,
    depth_to_mid_layer_m: float = 3.0
) -> Dict[str, Any]:
    """
    Calculates 1D primary consolidation settlement in clay layer under spread footing.
    Formula: S = (Cc * H / (1 + e0)) * log10((sigma0 + delta_sigma) / sigma0)
    Uses 2:1 stress distribution method for delta_sigma.
    """
    # 2:1 stress distribution at depth z = depth_to_mid_layer_m
    z = depth_to_mid_layer_m
    effective_b = footing_width_b_m + z
    effective_l = footing_length_l_m + z
    delta_sigma_kpa = applied_load_kn / (effective_b * effective_l)
    
    final_stress_kpa = initial_effective_stress_kpa + delta_sigma_kpa
    
    settlement_m = (compression_index_cc * clay_layer_thickness_h_m / (1.0 + initial_void_ratio_e0)) * math.log10(final_stress_kpa / initial_effective_stress_kpa)
    settlement_mm = settlement_m * 1000.0
    
    # Data center strict criterion: max settlement usually <= 25 mm (1 inch)
    acceptable = settlement_mm <= 25.0
    
    return {
        "applied_stress_increase_delta_sigma_kpa": round(delta_sigma_kpa, 2),
        "initial_effective_stress_kpa": round(initial_effective_stress_kpa, 2),
        "final_stress_kpa": round(final_stress_kpa, 2),
        "settlement_mm": round(settlement_mm, 2),
        "settlement_inches": round(settlement_mm / 25.4, 3),
        "acceptable_for_data_center_under_25mm": acceptable,
        "recommendation": "Spread footings acceptable" if acceptable else "Recommend aggregate piers / deep foundation"
    }
