"""
debim.engineering.electrical
Electrical Engineering, Power Sizing, Voltage Drop, Cable Schedules, and Substation Calculations.
Conforming to NEC (NFPA 70), IEEE 141/399, and IEC 60364.
"""

import math
from typing import Dict, Any, List, Optional

# Standard copper conductor resistance (ohms / 1000 ft at 75°C, steel conduit)
COPPER_RESISTANCE_OHMS_PER_1000FT = {
    "14_AWG": 3.1,
    "12_AWG": 2.0,
    "10_AWG": 1.2,
    "8_AWG": 0.78,
    "6_AWG": 0.49,
    "4_AWG": 0.31,
    "2_AWG": 0.19,
    "1/0_AWG": 0.12,
    "2/0_AWG": 0.10,
    "3/0_AWG": 0.077,
    "4/0_AWG": 0.062,
    "250_kcmil": 0.052,
    "350_kcmil": 0.038,
    "500_kcmil": 0.027,
    "750_kcmil": 0.019
}

# Standard NEC 310.16 75°C Copper Ampacities
NEC_COPPER_AMPACITY_75C = {
    "14_AWG": 20,
    "12_AWG": 25,
    "10_AWG": 35,
    "8_AWG": 50,
    "6_AWG": 65,
    "4_AWG": 85,
    "2_AWG": 115,
    "1/0_AWG": 150,
    "2/0_AWG": 175,
    "3/0_AWG": 200,
    "4/0_AWG": 230,
    "250_kcmil": 255,
    "350_kcmil": 310,
    "500_kcmil": 380,
    "750_kcmil": 475
}

def calculate_voltage_drop(
    current_amps: float,
    length_ft: float,
    nominal_voltage_v: float,
    system_type: str = "3_phase", # "3_phase" or "1_phase"
    wire_size: str = "500_kcmil",
    power_factor: float = 0.90,
    max_allowed_drop_percent: float = 3.0
) -> Dict[str, Any]:
    """
    Calculates voltage drop in volts and percentage per NEC guidelines (max 3% for branch, 5% total).
    Formula:
      3-Phase: Vd = sqrt(3) * I * L * (R*cos_phi + X*sin_phi) / 1000
      1-Phase: Vd = 2 * I * L * (R*cos_phi + X*sin_phi) / 1000
    """
    r = COPPER_RESISTANCE_OHMS_PER_1000FT.get(wire_size, 0.027)
    x = 0.05 # Typical AC reactance in steel conduit ohms/1000ft
    sin_phi = math.sqrt(max(0.0, 1.0 - power_factor ** 2))
    
    impedance = (r * power_factor) + (x * sin_phi)
    
    if system_type.lower() == "3_phase":
        vd_volts = math.sqrt(3) * current_amps * (length_ft / 1000.0) * impedance
    else:
        vd_volts = 2.0 * current_amps * (length_ft / 1000.0) * impedance
        
    vd_percent = (vd_volts / nominal_voltage_v) * 100.0
    compliant = vd_percent <= max_allowed_drop_percent
    
    return {
        "current_amps": current_amps,
        "length_ft": length_ft,
        "wire_size": wire_size,
        "voltage_drop_volts": round(vd_volts, 2),
        "voltage_drop_percent": round(vd_percent, 2),
        "max_allowed_percent": max_allowed_drop_percent,
        "compliant": compliant,
        "base_ampacity": NEC_COPPER_AMPACITY_75C.get(wire_size, 0)
    }

def size_data_center_generator_yard(
    total_it_load_mw: float,
    pue: float = 1.25,
    genset_capacity_mw: float = 2.5,
    redundancy: str = "N+1",
    fuel_autonomy_hours: float = 48.0
) -> Dict[str, Any]:
    """
    Sizes standby diesel generators and fuel oil storage for a data center campus.
    """
    total_facility_load_mw = total_it_load_mw * pue
    base_gensets_needed = math.ceil(total_facility_load_mw / genset_capacity_mw)
    
    if redundancy.upper() == "2N":
        total_gensets = base_gensets_needed * 2
    elif redundancy.upper() == "N+2":
        total_gensets = base_gensets_needed + 2
    else: # N+1
        total_gensets = base_gensets_needed + 1
        
    total_generation_capacity_mw = total_gensets * genset_capacity_mw
    
    # Specific fuel consumption ~ 0.25 liters/kWh (approx 0.066 gallons/kWh)
    liters_per_mwh = 250.0
    gallons_per_mwh = liters_per_mwh * 0.264172 # ~66.04 gal/MWh
    
    fuel_needed_liters = total_facility_load_mw * fuel_autonomy_hours * liters_per_mwh
    fuel_needed_gallons = fuel_needed_liters * 0.264172
    
    return {
        "it_load_mw": total_it_load_mw,
        "pue": pue,
        "facility_load_mw": round(total_facility_load_mw, 2),
        "base_gensets_n": base_gensets_needed,
        "redundancy": redundancy,
        "total_gensets": total_gensets,
        "genset_unit_rating_mw": genset_capacity_mw,
        "installed_capacity_mw": round(total_generation_capacity_mw, 2),
        "fuel_autonomy_hours": fuel_autonomy_hours,
        "fuel_storage_required_liters": round(fuel_needed_liters, 0),
        "fuel_storage_required_gallons": round(fuel_needed_gallons, 0),
        "min_fire_separation_distance_m": 28.0 # Standard data center boundary requirement
    }

def size_mv_substation_transformers(
    total_load_mva: float,
    primary_kv: float = 115.0,
    secondary_kv: float = 13.8,
    transformer_unit_mva: float = 30.0,
    redundancy: str = "2N"
) -> Dict[str, Any]:
    """
    Sizes medium-voltage site distribution substation transformers (e.g. 115 kV to 13.8 kV).
    """
    base_tx = math.ceil(total_load_mva / transformer_unit_mva)
    if redundancy.upper() == "2N":
        total_tx = base_tx * 2
    else:
        total_tx = base_tx + 1
        
    rated_secondary_amps = (transformer_unit_mva * 1000.0) / (math.sqrt(3) * secondary_kv)
    
    return {
        "total_load_mva": total_load_mva,
        "primary_kv": primary_kv,
        "secondary_kv": secondary_kv,
        "transformer_unit_mva": transformer_unit_mva,
        "total_transformers": total_tx,
        "redundancy": redundancy,
        "secondary_full_load_current_amps": round(rated_secondary_amps, 1),
        "topology": "Ring/Loop topology recommended for high availability"
    }
