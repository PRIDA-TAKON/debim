"""
debim.engineering.mechanical
Mechanical & HVAC Engineering for Data Centers: Cooling Loads, Chilled Water, CRAH Airflow, and Pipe Sizing.
Conforming to ASHRAE TC 9.9 Thermal Guidelines for Data Processing Environments.
"""

import math
from typing import Dict, Any, List, Optional

def calculate_data_hall_cooling_load(
    it_load_kw: float,
    delta_t_fahrenheit: float = 20.0, # Typical 75°F supply, 95°F return
    chw_supply_temp_f: float = 55.0,
    chw_return_temp_f: float = 67.0,
    fan_heat_ratio: float = 0.05,
    ups_pdu_loss_ratio: float = 0.04
) -> Dict[str, Any]:
    """
    Calculates total heat rejection load, cooling capacity in Tons of Refrigeration,
    chilled water GPM, and CRAH airflow CFM for a data hall.
    """
    # 1 kW = 3412.142 BTU/hr
    it_heat_btu_hr = it_load_kw * 3412.142
    ancillary_losses_btu_hr = it_heat_btu_hr * (fan_heat_ratio + ups_pdu_loss_ratio)
    total_cooling_btu_hr = it_heat_btu_hr + ancillary_losses_btu_hr
    
    # 1 Ton of Refrigeration = 12,000 BTU/hr
    tons_refrigeration = total_cooling_btu_hr / 12000.0
    
    # Airflow CFM = Q_sensible / (1.08 * Delta_T)
    cfm = total_cooling_btu_hr / (1.08 * delta_t_fahrenheit)
    
    # Chilled Water GPM = Q_total / (500 * Delta_T_water)
    chw_delta_t = max(1.0, chw_return_temp_f - chw_supply_temp_f)
    chw_gpm = total_cooling_btu_hr / (500.0 * chw_delta_t)
    
    return {
        "it_load_kw": it_load_kw,
        "total_cooling_btu_hr": round(total_cooling_btu_hr, 1),
        "tons_of_refrigeration": round(tons_refrigeration, 2),
        "supply_return_air_delta_t_f": delta_t_fahrenheit,
        "required_airflow_cfm": round(cfm, 1),
        "chw_supply_f": chw_supply_temp_f,
        "chw_return_f": chw_return_temp_f,
        "chilled_water_flow_gpm": round(chw_gpm, 1),
        "ashrae_class": "A1/A2 Recommended (Air Supply 64.4°F - 80.6°F)"
    }

def calculate_pipe_volume_and_flushing(
    pipe_diameter_inches: float,
    total_pipe_length_ft: float,
    chemical_passivation_ppm: float = 50.0 # Standard corrosion inhibitor dosage
) -> Dict[str, Any]:
    """
    Calculates pipe water volume (gallons and liters) and required chemical passivation dosage.
    Used for Process Cooling Water (PCW) flush and passivation plans.
    """
    # Internal radius in feet
    radius_ft = (pipe_diameter_inches / 2.0) / 12.0
    volume_cu_ft = math.pi * (radius_ft ** 2) * total_pipe_length_ft
    
    # 1 cu ft = 7.48052 US gallons
    gallons = volume_cu_ft * 7.48052
    liters = gallons * 3.78541
    
    # Chemical dosage (kg) = (liters * ppm) / 1,000,000
    chemical_kg = (liters * chemical_passivation_ppm) / 1000000.0
    
    return {
        "pipe_diameter_inches": pipe_diameter_inches,
        "total_length_ft": total_pipe_length_ft,
        "volume_gallons": round(gallons, 2),
        "volume_liters": round(liters, 2),
        "passivation_dosage_ppm": chemical_passivation_ppm,
        "chemical_required_kg": round(chemical_kg, 3),
        "recommended_flushing_velocity_fps": 6.0 # Min 5-6 fps for effective scouring
    }
