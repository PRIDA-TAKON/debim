"""
debim.engineering
~~~~~~~~~~~~~~~~~

Data Center, Civil, Structural, Electrical, and Mechanical Engineering calculation
and verification tools for deterministic Building-as-Code engineering.
"""

from .civil import (
    calculate_stormwater_retention,
    check_environmental_setbacks,
    calculate_noise_attenuation
)

from .structural import (
    calculate_wind_diaphragm_shear,
    calculate_seismic_diaphragm_shear,
    calculate_footing_settlement_clay
)

from .electrical import (
    calculate_voltage_drop,
    size_data_center_generator_yard,
    size_mv_substation_transformers
)

from .mechanical import (
    calculate_data_hall_cooling_load,
    calculate_pipe_volume_and_flushing
)

from .datacenter import (
    calculate_pue_wue,
    size_data_hall_whitespace,
    check_tier_redundancy,
    calculate_data_hall_floor_load
)

__all__ = [
    # Civil
    "calculate_stormwater_retention",
    "check_environmental_setbacks",
    "calculate_noise_attenuation",
    # Structural
    "calculate_wind_diaphragm_shear",
    "calculate_seismic_diaphragm_shear",
    "calculate_footing_settlement_clay",
    # Electrical
    "calculate_voltage_drop",
    "size_data_center_generator_yard",
    "size_mv_substation_transformers",
    # Mechanical
    "calculate_data_hall_cooling_load",
    "calculate_pipe_volume_and_flushing",
    # Data Center
    "calculate_pue_wue",
    "size_data_hall_whitespace",
    "check_tier_redundancy",
    "calculate_data_hall_floor_load"
]
