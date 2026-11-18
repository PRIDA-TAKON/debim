"""
debim.calc_cli
~~~~~~~~~~~~~~

CLI subcommand handlers and argument parser registration for
physical engineering calculations in debim (`debim calc ...`).
"""

import argparse
import json
import sys
from typing import Dict, Any

from debim.engineering import (
    calculate_stormwater_retention,
    check_environmental_setbacks,
    calculate_noise_attenuation,
    calculate_wind_diaphragm_shear,
    calculate_seismic_diaphragm_shear,
    calculate_footing_settlement_clay,
    calculate_voltage_drop,
    size_data_center_generator_yard,
    size_mv_substation_transformers,
    calculate_data_hall_cooling_load,
    calculate_pipe_volume_and_flushing,
    calculate_pue_wue,
    size_data_hall_whitespace,
    check_tier_redundancy,
    calculate_data_hall_floor_load,
)


def _output_result(res: Dict[str, Any], title: str, args: argparse.Namespace):
    if getattr(args, "json", False):
        print(json.dumps(res, indent=2))
        return

    print(f"\n==================== [debim calc: {title}] ====================")
    for k, v in res.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for sub_k, sub_v in v.items():
                print(f"    - {sub_k}: {sub_v}")
        elif isinstance(v, list):
            print(f"  {k}: ({len(v)} items)")
            for item in v:
                print(f"    * {item}")
        else:
            print(f"  {k}: {v}")
    print("=================================================================\n")


# --- Civil Handlers ---

def cmd_calc_stormwater(args: argparse.Namespace):
    res = calculate_stormwater_retention(
        impervious_area_m2=args.area,
        design_factor=args.factor,
        runoff_coefficient=args.runoff_c,
        design_storm_depth_mm=args.depth_mm
    )
    _output_result(res, "Stormwater Retention Basin Sizing", args)


def cmd_calc_noise(args: argparse.Namespace):
    res = calculate_noise_attenuation(
        generator_sound_power_db=args.source_db,
        distance_to_boundary_m=args.distance_m,
        barrier_attenuation_db=args.barrier_db,
        ground_absorption_factor=args.ground_factor
    )
    _output_result(res, "Generator Noise Attenuation & Boundary SPL", args)


# --- Structural Handlers ---

def cmd_calc_wind_shear(args: argparse.Namespace):
    res = calculate_wind_diaphragm_shear(
        basic_wind_speed_mph=args.wind_speed,
        building_length_ft=args.length_ft,
        building_width_ft=args.width_ft,
        mean_roof_height_ft=args.height_ft,
        exposure_category=args.exposure,
        risk_category=args.risk
    )
    _output_result(res, "Wind Diaphragm Shear (ASCE 7)", args)


def cmd_calc_seismic_shear(args: argparse.Namespace):
    res = calculate_seismic_diaphragm_shear(
        seismic_weight_kips=args.weight_kips,
        sds=args.sds,
        sd1=args.sd1,
        r_factor=args.r_factor,
        importance_factor=args.importance,
        diaphragm_span_ft=args.span_ft
    )
    _output_result(res, "Seismic Diaphragm Shear & Base Shear (ASCE 7 / IBC)", args)


def cmd_calc_settlement(args: argparse.Namespace):
    res = calculate_footing_settlement_clay(
        footing_load_kips=args.load_kips,
        footing_width_b_ft=args.width_ft,
        footing_length_l_ft=args.length_ft,
        clay_layer_thickness_ft=args.thickness_ft,
        depth_to_mid_layer_ft=args.depth_ft,
        initial_void_ratio_e0=args.e0,
        compression_index_cc=args.cc,
        initial_effective_stress_psf=args.sigma_v0
    )
    _output_result(res, "Clay Consolidation Footing Settlement", args)


# --- Electrical Handlers ---

def cmd_calc_cable(args: argparse.Namespace):
    res = calculate_voltage_drop(
        current_amps=args.current_amps,
        length_ft=args.length_ft,
        nominal_voltage_v=args.voltage_v,
        system_type="1_phase" if args.single_phase else "3_phase",
        wire_size=args.wire_size,
        power_factor=args.pf,
        max_allowed_drop_percent=args.max_vd
    )
    _output_result(res, "Cable Sizing & Voltage Drop (NEC 310 / IEEE 141)", args)


def cmd_calc_generator_yard(args: argparse.Namespace):
    res = size_data_center_generator_yard(
        total_it_load_mw=args.it_mw,
        pue=args.pue,
        genset_capacity_mw=args.genset_mw,
        redundancy=args.redundancy,
        fuel_autonomy_hours=args.runtime_hours
    )
    _output_result(res, "Standby Generator Yard & Fuel Storage Sizing", args)


def cmd_calc_substation(args: argparse.Namespace):
    res = size_mv_substation_transformers(
        total_load_mva=args.load_mva,
        primary_kv=args.v_primary,
        secondary_kv=args.v_secondary,
        transformer_unit_mva=args.unit_mva,
        redundancy=args.redundancy
    )
    _output_result(res, "MV Substation Transformer Sizing", args)


# --- Mechanical Handlers ---

def cmd_calc_cooling(args: argparse.Namespace):
    res = calculate_data_hall_cooling_load(
        it_load_kw=args.it_kw,
        delta_t_fahrenheit=args.delta_t,
        chw_supply_temp_f=args.chw_supply,
        chw_return_temp_f=args.chw_return
    )
    _output_result(res, "Data Hall Heat Rejection & Chilled Water / CRAH", args)


def cmd_calc_pipe_volume(args: argparse.Namespace):
    res = calculate_pipe_volume_and_flushing(
        pipe_diameter_inches=args.diameter_in,
        total_pipe_length_ft=args.length_ft,
        chemical_passivation_ppm=args.passivation_ppm
    )
    _output_result(res, "Process Cooling Water Pipe Volume & Passivation", args)


# --- Data Center Handlers ---

def cmd_calc_datacenter(args: argparse.Namespace):
    pue_res = calculate_pue_wue(
        it_power_kw=args.it_mw * 1000.0,
        cooling_power_kw=args.it_mw * 1000.0 * 0.25,
        electrical_loss_kw=args.it_mw * 1000.0 * 0.08,
        lighting_misc_kw=args.it_mw * 1000.0 * 0.02
    )
    ws_res = size_data_hall_whitespace(
        total_it_mw=args.it_mw,
        avg_rack_kw=args.rack_kw
    )
    tier_res = check_tier_redundancy(
        tier_level=args.tier,
        it_load_mw=args.it_mw,
        generator_unit_mw=2.5,
        ups_unit_kw=1000.0,
        chiller_unit_tr=500.0
    )
    floor_res = calculate_data_hall_floor_load(
        rack_weight_kg=args.rack_weight_kg
    )

    combined = {
        "datacenter_overview": {
            "tier": tier_res["tier"],
            "it_capacity_mw": args.it_mw,
            "architecture": tier_res["architecture_summary"]
        },
        "efficiency": pue_res,
        "whitespace_layout": ws_res,
        "equipment_redundancy": {
            "generators": tier_res["generators"],
            "ups_units": tier_res["ups_units"],
            "chillers": tier_res["chillers"]
        },
        "floor_structural_check": floor_res
    }
    _output_result(combined, "Integrated Data Center Facility Sizing", args)


def register_calc_parser(subparsers):
    """Register 'calc' subparser and all physical engineering tools."""
    p_calc = subparsers.add_parser("calc", help="Physical engineering calculations (Civil, Structural, Electrical, Mechanical, DC)")
    calc_subparsers = p_calc.add_subparsers(dest="calc_subcommand")

    # --- Civil ---
    p_stormwater = calc_subparsers.add_parser("stormwater", help="Stormwater retention basin sizing")
    p_stormwater.add_argument("--area", type=float, required=True, help="Impervious area in m²")
    p_stormwater.add_argument("--factor", type=float, default=0.12, help="Retention area factor (default: 0.12 = 12%)")
    p_stormwater.add_argument("--runoff-c", type=float, default=0.90, help="Runoff coefficient C (default: 0.90)")
    p_stormwater.add_argument("--depth-mm", type=float, help="Design storm depth in mm")
    p_stormwater.add_argument("--json", action="store_true", help="Output JSON")
    p_stormwater.set_defaults(func=cmd_calc_stormwater)

    p_noise = calc_subparsers.add_parser("noise", help="Generator yard noise attenuation & boundary SPL")
    p_noise.add_argument("--source-db", type=float, default=105.0, help="Source sound power Lw in dBA")
    p_noise.add_argument("--distance-m", type=float, required=True, help="Distance to boundary in meters")
    p_noise.add_argument("--barrier-db", type=float, default=0.0, help="Acoustic wall attenuation in dBA")
    p_noise.add_argument("--ground-factor", type=float, default=0.5, help="Ground absorption factor (0.0 hard to 1.0 soft)")
    p_noise.add_argument("--json", action="store_true", help="Output JSON")
    p_noise.set_defaults(func=cmd_calc_noise)

    # --- Structural ---
    p_wind = calc_subparsers.add_parser("wind-shear", help="Wind diaphragm shear calculation (ASCE 7)")
    p_wind.add_argument("--wind-speed", type=float, required=True, help="Basic wind speed in mph (e.g. 115)")
    p_wind.add_argument("--length-ft", type=float, required=True, help="Building length parallel to wind in feet")
    p_wind.add_argument("--width-ft", type=float, required=True, help="Building width normal to wind in feet")
    p_wind.add_argument("--height-ft", type=float, required=True, help="Mean roof height in feet")
    p_wind.add_argument("--exposure", choices=["B", "C", "D"], default="C", help="Exposure category (B, C, or D)")
    p_wind.add_argument("--risk", choices=["I", "II", "III", "IV"], default="IV", help="ASCE 7 Risk category (default: IV)")
    p_wind.add_argument("--json", action="store_true", help="Output JSON")
    p_wind.set_defaults(func=cmd_calc_wind_shear)

    p_seismic = calc_subparsers.add_parser("seismic-shear", help="Seismic diaphragm shear & base shear (ASCE 7 / IBC)")
    p_seismic.add_argument("--weight-kips", type=float, required=True, help="Effective seismic tributary weight W in kips")
    p_seismic.add_argument("--sds", type=float, required=True, help="Design spectral acceleration SDS (g)")
    p_seismic.add_argument("--sd1", type=float, required=True, help="Design spectral acceleration SD1 (g)")
    p_seismic.add_argument("--r-factor", type=float, default=3.25, help="Response modification coefficient R")
    p_seismic.add_argument("--importance", type=float, default=1.5, help="Importance factor Ie (1.5 for Data Center)")
    p_seismic.add_argument("--span-ft", type=float, default=150.0, help="Diaphragm reaction boundary length in feet")
    p_seismic.add_argument("--json", action="store_true", help="Output JSON")
    p_seismic.set_defaults(func=cmd_calc_seismic_shear)

    p_settlement = calc_subparsers.add_parser("settlement", help="1D consolidation footing settlement in clay")
    p_settlement.add_argument("--load-kips", type=float, required=True, help="Total column load in kips")
    p_settlement.add_argument("--width-ft", type=float, required=True, help="Footing width B in feet")
    p_settlement.add_argument("--length-ft", type=float, required=True, help="Footing length L in feet")
    p_settlement.add_argument("--thickness-ft", type=float, required=True, help="Compressible clay thickness H in feet")
    p_settlement.add_argument("--depth-ft", type=float, required=True, help="Depth from footing base to clay mid-layer in feet")
    p_settlement.add_argument("--e0", type=float, default=0.85, help="Initial void ratio e0")
    p_settlement.add_argument("--cc", type=float, default=0.32, help="Compression index Cc")
    p_settlement.add_argument("--sigma-v0", type=float, default=2500.0, help="Initial in-situ effective vertical stress in psf")
    p_settlement.add_argument("--json", action="store_true", help="Output JSON")
    p_settlement.set_defaults(func=cmd_calc_settlement)

    # --- Electrical ---
    p_cable = calc_subparsers.add_parser("cable-size", help="Cable sizing & voltage drop (NEC 310 / IEEE 141)")
    p_cable.add_argument("--current-amps", type=float, required=True, help="Full load current in Amperes")
    p_cable.add_argument("--length-ft", type=float, required=True, help="One-way feeder length in feet")
    p_cable.add_argument("--voltage-v", type=float, default=480.0, help="Nominal voltage in Volts")
    p_cable.add_argument("--wire-size", default="500_kcmil", help="Conductor size (e.g. '4_awg', '2/0_awg', '500_kcmil')")
    p_cable.add_argument("--pf", type=float, default=0.90, help="Load power factor (default: 0.90)")
    p_cable.add_argument("--max-vd", type=float, default=3.0, help="Maximum allowable voltage drop percentage (default: 3%)")
    p_cable.add_argument("--single-phase", action="store_true", help="Calculate as single-phase (default: 3-phase)")
    p_cable.add_argument("--json", action="store_true", help="Output JSON")
    p_cable.set_defaults(func=cmd_calc_cable)

    p_genset = calc_subparsers.add_parser("generator-yard", help="Standby diesel generator yard & fuel storage sizing")
    p_genset.add_argument("--it-mw", type=float, required=True, help="Total IT capacity in MW")
    p_genset.add_argument("--pue", type=float, default=1.25, help="Facility PUE factor (default: 1.25)")
    p_genset.add_argument("--genset-mw", type=float, default=2.5, help="Generator unit rating in MW (default: 2.5 MW)")
    p_genset.add_argument("--redundancy", choices=["N+1", "N+2", "2N"], default="N+1", help="Redundancy configuration")
    p_genset.add_argument("--runtime-hours", type=float, default=48.0, help="Fuel autonomy runtime in hours (default: 48)")
    p_genset.add_argument("--json", action="store_true", help="Output JSON")
    p_genset.set_defaults(func=cmd_calc_generator_yard)

    p_sub = calc_subparsers.add_parser("substation", help="MV Substation transformer sizing")
    p_sub.add_argument("--load-mva", type=float, required=True, help="Total connected facility load in MVA")
    p_sub.add_argument("--v-primary", type=float, default=115.0, help="Primary MV voltage in kV")
    p_sub.add_argument("--v-secondary", type=float, default=13.8, help="Secondary distribution voltage in kV")
    p_sub.add_argument("--unit-mva", type=float, default=30.0, help="Transformer unit rating in MVA (default: 30)")
    p_sub.add_argument("--redundancy", choices=["N+1", "2N"], default="2N", help="Redundancy scheme (default: 2N)")
    p_sub.add_argument("--json", action="store_true", help="Output JSON")
    p_sub.set_defaults(func=cmd_calc_substation)

    # --- Mechanical ---
    p_cooling = calc_subparsers.add_parser("cooling-load", help="Data hall heat rejection & CHW/CRAH sizing")
    p_cooling.add_argument("--it-kw", type=float, required=True, help="Total IT electrical load in kW")
    p_cooling.add_argument("--delta-t", type=float, default=20.0, help="Supply to return air delta T in °F (default: 20)")
    p_cooling.add_argument("--chw-supply", type=float, default=55.0, help="CHW supply temperature in °F (default: 55)")
    p_cooling.add_argument("--chw-return", type=float, default=67.0, help="CHW return temperature in °F (default: 67)")
    p_cooling.add_argument("--json", action="store_true", help="Output JSON")
    p_cooling.set_defaults(func=cmd_calc_cooling)

    p_pipe = calc_subparsers.add_parser("pipe-volume", help="Process cooling water (PCW) pipe volume & chemical flushing")
    p_pipe.add_argument("--diameter-in", type=float, required=True, help="Pipe internal diameter in inches")
    p_pipe.add_argument("--length-ft", type=float, required=True, help="Total pipe run length in feet")
    p_pipe.add_argument("--passivation-ppm", type=float, default=50.0, help="Chemical inhibitor dosage in ppm (default: 50)")
    p_pipe.add_argument("--json", action="store_true", help="Output JSON")
    p_pipe.set_defaults(func=cmd_calc_pipe_volume)

    # --- Integrated Data Center ---
    p_dc = calc_subparsers.add_parser("datacenter", help="Integrated Hyperscale Data Center sizing (PUE, Redundancy, Floor Load)")
    p_dc.add_argument("--it-mw", type=float, required=True, help="Total IT capacity in MW")
    p_dc.add_argument("--tier", choices=["I", "II", "III", "IV"], default="III", help="Uptime Institute Tier level (default: III)")
    p_dc.add_argument("--rack-kw", type=float, default=12.0, help="Average power density per rack in kW")
    p_dc.add_argument("--rack-weight-kg", type=float, default=1400.0, help="Design rack weight in kg")
    p_dc.add_argument("--json", action="store_true", help="Output JSON")
    p_dc.set_defaults(func=cmd_calc_datacenter)
