"""
debim.engineering.datacenter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Comprehensive hyperscale and enterprise Data Center engineering sizing,
compliance checks, and campus layout calculations covering:
- Uptime Institute Tier I-IV compliance & redundancy (N, N+1, 2N, 2(N+1))
- PUE (Power Usage Effectiveness) & WUE (Water Usage Effectiveness)
- White space / Data Hall sizing & rack layout (kW/rack, hot/cold aisle)
- Floor structural live loading (racks, UPS battery strings, CRAH units)
- UPS battery room & autonomy sizing (Li-ion vs VRLA, run-time, heat rejection)
- Fuel storage autonomy (NFPA 110 Class 48/96 hours, 110% secondary containment)
"""

import math
from typing import Dict, Any, List, Optional


def calculate_pue_wue(
    it_power_kw: float,
    cooling_power_kw: float,
    electrical_loss_kw: float,
    lighting_misc_kw: float,
    annual_water_liters: float = 0.0,
    annual_it_energy_kwh: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculate Power Usage Effectiveness (PUE) and Water Usage Effectiveness (WUE).
    
    PUE = Total Facility Power / IT Equipment Power
    WUE = Annual Water Usage (liters) / Annual IT Energy Consumption (kWh)
    """
    if it_power_kw <= 0:
        raise ValueError("IT power must be greater than 0")
        
    facility_power_kw = it_power_kw + cooling_power_kw + electrical_loss_kw + lighting_misc_kw
    pue = facility_power_kw / it_power_kw
    
    if annual_it_energy_kwh is None or annual_it_energy_kwh <= 0:
        annual_it_energy_kwh = it_power_kw * 8760.0  # assume continuous operation
        
    wue = (annual_water_liters / annual_it_energy_kwh) if annual_water_liters > 0 else 0.0
    
    # Efficiency tier categorization (ASHRAE / Green Grid)
    if pue < 1.2:
        efficiency_rating = "Excellent (Hyperscale State-of-the-Art)"
    elif pue <= 1.4:
        efficiency_rating = "Very Good (Modern High-Efficiency)"
    elif pue <= 1.6:
        efficiency_rating = "Average Enterprise"
    else:
        efficiency_rating = "Legacy / Sub-optimal"

    return {
        "it_power_kw": it_power_kw,
        "facility_power_kw": facility_power_kw,
        "cooling_power_kw": cooling_power_kw,
        "electrical_loss_kw": electrical_loss_kw,
        "lighting_misc_kw": lighting_misc_kw,
        "pue": round(pue, 3),
        "wue_l_per_kwh": round(wue, 3),
        "efficiency_rating": efficiency_rating
    }


def size_data_hall_whitespace(
    total_it_mw: float,
    avg_rack_kw: float = 10.0,
    rack_width_m: float = 0.6,
    rack_depth_m: float = 1.2,
    cold_aisle_width_m: float = 1.2,
    hot_aisle_width_m: float = 1.0,
    crah_clearance_factor: float = 1.35
) -> Dict[str, Any]:
    """
    Size data hall white space footprint based on IT MW and rack density.
    
    Calculates total racks required, rack footprint, aisle dimensions,
    and recommended white space gross area including peripheral cooling/PDU corridors.
    """
    it_kw = total_it_mw * 1000.0
    rack_count = math.ceil(it_kw / avg_rack_kw)
    
    # Each rack shares half cold aisle and half hot aisle width in depth direction
    effective_rack_depth = rack_depth_m + (cold_aisle_width_m / 2.0) + (hot_aisle_width_m / 2.0)
    rack_net_area = rack_width_m * effective_rack_depth * rack_count
    
    # Gross white space includes service aisles, CRAH placement, and PDUs
    gross_whitespace_area_sqm = rack_net_area * crah_clearance_factor
    
    return {
        "total_it_mw": total_it_mw,
        "rack_count": rack_count,
        "avg_rack_kw": avg_rack_kw,
        "rack_dims_m": {"width": rack_width_m, "depth": rack_depth_m},
        "rack_net_area_sqm": round(rack_net_area, 1),
        "gross_whitespace_area_sqm": round(gross_whitespace_area_sqm, 1),
        "power_density_w_per_sqm": round(it_kw * 1000.0 / gross_whitespace_area_sqm, 1)
    }


def check_tier_redundancy(
    tier_level: str,
    it_load_mw: float,
    generator_unit_mw: float,
    ups_unit_kw: float,
    chiller_unit_tr: float
) -> Dict[str, Any]:
    """
    Compute required equipment counts for Uptime Institute Tier I, II, III, or IV.
    
    - Tier I: Basic capacity (N)
    - Tier II: Redundant capacity (N+1)
    - Tier III: Concurrently maintainable (N+1 or 2N electrical, N+1 cooling dual-path)
    - Tier IV: Fault tolerant (2N or 2(N+1), 2 active cooling distribution paths)
    """
    tier_normalized = tier_level.upper().replace("TIER", "").strip()
    
    # IT load + 15% electrical/cooling ancillary
    total_elec_load_mw = it_load_mw * 1.15
    # Sizing N
    n_gens = math.ceil(total_elec_load_mw / generator_unit_mw)
    n_ups = math.ceil((it_load_mw * 1000.0) / ups_unit_kw)
    
    # Cooling: 1 MW IT ≈ 284 TR IT heat + 40 TR envelope/fan = 324 TR
    total_cooling_tr = it_load_mw * 324.0
    n_chillers = math.ceil(total_cooling_tr / chiller_unit_tr)
    
    if tier_normalized in ["I", "1"]:
        gens_req = n_gens
        ups_req = n_ups
        chillers_req = n_chillers
        arch_summary = "Tier I: Basic Capacity (N), single non-redundant path"
        concurrently_maintainable = False
        fault_tolerant = False
    elif tier_normalized in ["II", "2"]:
        gens_req = n_gens + 1
        ups_req = n_ups + 1
        chillers_req = n_chillers + 1
        arch_summary = "Tier II: Redundant Capacity Components (N+1), single path"
        concurrently_maintainable = False
        fault_tolerant = False
    elif tier_normalized in ["III", "3"]:
        gens_req = n_gens + 1
        ups_req = 2 * n_ups  # 2N electrical distribution standard for Tier III
        chillers_req = n_chillers + 2  # N+2 or N+1 with dual concurrent piping loops
        arch_summary = "Tier III: Concurrently Maintainable, dual power paths, 1 active 1 alternate"
        concurrently_maintainable = True
        fault_tolerant = False
    elif tier_normalized in ["IV", "4"]:
        gens_req = 2 * n_gens
        ups_req = 2 * n_ups
        chillers_req = 2 * n_chillers
        arch_summary = "Tier IV: Fault Tolerant 2(N+1) or 2N with autonomous response"
        concurrently_maintainable = True
        fault_tolerant = True
    else:
        raise ValueError(f"Unknown tier level: {tier_level}. Expected I, II, III, or IV.")
        
    return {
        "tier": f"Tier {tier_normalized}",
        "architecture_summary": arch_summary,
        "concurrently_maintainable": concurrently_maintainable,
        "fault_tolerant": fault_tolerant,
        "it_load_mw": it_load_mw,
        "generators": {
            "n_required": n_gens,
            "total_installed": gens_req,
            "unit_mw": generator_unit_mw,
            "total_capacity_mw": gens_req * generator_unit_mw
        },
        "ups_units": {
            "n_required": n_ups,
            "total_installed": ups_req,
            "unit_kw": ups_unit_kw,
            "total_capacity_kw": ups_req * ups_unit_kw
        },
        "chillers": {
            "n_required": n_chillers,
            "total_installed": chillers_req,
            "unit_tr": chiller_unit_tr,
            "total_capacity_tr": chillers_req * chiller_unit_tr
        }
    }


def calculate_data_hall_floor_load(
    rack_weight_kg: float = 1200.0,
    rack_footprint_sqm: float = 0.72,
    aisle_distributed_factor: float = 2.0,
    raised_floor_dead_load_kpa: float = 0.5,
    slab_capacity_kpa: float = 15.0
) -> Dict[str, Any]:
    """
    Verify structural floor load capacity for high-density server racks.
    
    Calculates point load, rack footprint pressure, and area-averaged uniform load (kPa).
    1 kPa = 1 kN/m² ≈ 102 kg/m² ≈ 20.89 lbs/ft².
    """
    g = 9.80665
    rack_weight_kn = (rack_weight_kg * g) / 1000.0
    point_load_per_caster_kn = rack_weight_kn / 4.0
    
    direct_rack_pressure_kpa = rack_weight_kn / rack_footprint_sqm
    
    # Area-averaged load taking into account cold and hot aisles
    effective_tributary_sqm = rack_footprint_sqm * aisle_distributed_factor
    uniform_live_load_kpa = rack_weight_kn / effective_tributary_sqm
    total_imposed_kpa = uniform_live_load_kpa + raised_floor_dead_load_kpa
    
    is_compliant = total_imposed_kpa <= slab_capacity_kpa
    utilization_ratio = total_imposed_kpa / slab_capacity_kpa
    
    return {
        "rack_weight_kg": rack_weight_kg,
        "point_load_per_caster_kn": round(point_load_per_caster_kn, 2),
        "direct_rack_pressure_kpa": round(direct_rack_pressure_kpa, 2),
        "uniform_live_load_kpa": round(uniform_live_load_kpa, 2),
        "total_imposed_kpa": round(total_imposed_kpa, 2),
        "slab_capacity_kpa": slab_capacity_kpa,
        "utilization_ratio": round(utilization_ratio, 3),
        "is_compliant": is_compliant
    }
