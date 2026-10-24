"""
Parametric Stair & Railing Geometry Generator for debim.
Calculates riser height (<= 0.20m), tread depth (>= 0.25m), flight distribution,
and landings compliant with building codes, and automatically generates IfcRailing instances.
"""

import math
from typing import Dict, List, Literal, Optional, Tuple, Union

from debim.schema import (
    IfcRailing,
    IfcStair,
    RailingPlacement,
    StairPlacement,
    StairRailingConfig,
)


def calculate_stair_parameters(
    total_height: float,
    max_riser: float = 0.20,
    min_tread: float = 0.25,
    flight_width: float = 1.00,
    stair_type: str = "STRAIGHT",
    landing_depth: Optional[float] = None,
) -> Dict[str, Union[int, float, List[int], str]]:
    """
    Calculate parametric stair geometry parameters compliant with building regulations.

    Rules:
    - Riser height <= max_riser (default 0.20m).
    - Tread depth >= min_tread (default 0.25m).
    - Number of risers = ceil(total_height / max_riser).
    - Actual riser height = total_height / num_risers.

    Returns dictionary with calculated values.
    """
    if total_height <= 0:
        raise ValueError("total_height must be positive.")

    # Calculate optimal riser count
    num_risers = max(1, math.ceil(total_height / max_riser))
    riser_height = round(total_height / num_risers, 4)

    # Ensure riser_height satisfies upper limit (if num_risers were small)
    if riser_height > max_riser:
        num_risers += 1
        riser_height = round(total_height / num_risers, 4)

    tread_depth = max(min_tread, 0.25)
    resolved_landing_depth = landing_depth if landing_depth is not None else max(1.00, flight_width)

    if stair_type.upper() in ("DOG_LEG", "U_SHAPE", "MULTI_FLIGHT"):
        # Split risers into 2 flights with landing
        flight1_risers = math.ceil(num_risers / 2.0)
        flight2_risers = num_risers - flight1_risers
        flight_steps = [flight1_risers, flight2_risers]
        landing_elev = round(flight1_risers * riser_height, 4)
    else:
        flight_steps = [num_risers]
        landing_elev = None

    return {
        "num_risers": num_risers,
        "riser_height": riser_height,
        "tread_depth": tread_depth,
        "num_treads": max(1, num_risers - (1 if len(flight_steps) == 1 else 2)),
        "flight_width": flight_width,
        "flight_steps": flight_steps,
        "landing_depth": resolved_landing_depth,
        "landing_elevation": landing_elev,
        "stair_type": stair_type.upper(),
        "total_height": round(total_height, 4),
    }


def generate_stair_railings(
    stair_tag: str,
    storey: str,
    from_grid: Tuple[str, str],
    to_grid: Optional[Tuple[str, str]] = None,
    stair_width: float = 1.00,
    railing_height: float = 0.90,
    material: str = "Stainless Steel / Glass",
    from_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    to_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> List[IfcRailing]:
    """
    Generate automated IfcRailing instances along both sides of a stair run or landing.
    Each railing has specified height (default 0.90m).
    """
    half_w = stair_width / 2.0
    ref_to_grid = to_grid or from_grid

    # Left railing (offset -half_w in lateral direction)
    left_railing = IfcRailing(
        tag=f"{stair_tag}-Railing-Left",
        material=material,
        predefined_type="HANDRAIL",
        height=railing_height,
        post_spacing=1.50,
        placement=RailingPlacement(
            storey=storey,
            from_grid=from_grid,
            to_grid=ref_to_grid,
            from_offset=(from_offset[0] - half_w, from_offset[1], from_offset[2]),
            to_offset=(to_offset[0] - half_w, to_offset[1], to_offset[2]),
        ),
        layer="circulation/railings",
    )

    # Right railing (offset +half_w in lateral direction)
    right_railing = IfcRailing(
        tag=f"{stair_tag}-Railing-Right",
        material=material,
        predefined_type="HANDRAIL",
        height=railing_height,
        post_spacing=1.50,
        placement=RailingPlacement(
            storey=storey,
            from_grid=from_grid,
            to_grid=ref_to_grid,
            from_offset=(from_offset[0] + half_w, from_offset[1], from_offset[2]),
            to_offset=(to_offset[0] + half_w, to_offset[1], to_offset[2]),
        ),
        layer="circulation/railings",
    )

    return [left_railing, right_railing]


def generate_parametric_stair(
    tag: str,
    total_height: float,
    grid_anchor: Tuple[str, str],
    from_storey: str,
    to_storey: Optional[str] = None,
    stair_type: str = "STRAIGHT",
    material: str = "Reinforced Concrete",
    width: float = 1.00,
    max_riser: float = 0.20,
    min_tread: float = 0.25,
    railing_height: float = 0.90,
    orientation: Literal["+X", "-X", "+Y", "-Y"] = "+Y",
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    offset_z: float = 0.0,
) -> Tuple[IfcStair, List[IfcRailing]]:
    """
    Generate a fully parametric IfcStair instance along with compliant automated IfcRailings (height = 0.90m).

    Returns:
    --------
    Tuple[IfcStair, List[IfcRailing]] : Parametric stair and generated railings.
    """
    params = calculate_stair_parameters(
        total_height=total_height,
        max_riser=max_riser,
        min_tread=min_tread,
        flight_width=width,
        stair_type=stair_type,
    )

    target_to_storey = to_storey if to_storey is not None else from_storey

    stair_obj = IfcStair(
        tag=tag,
        material=material,
        stair_type=params["stair_type"],
        width=width,
        waist_thickness=0.12,
        landing_depth=params["landing_depth"],
        landing_elevation=params["landing_elevation"],
        flight_steps=params["flight_steps"],
        riser_height=params["riser_height"],
        tread_depth=params["tread_depth"],
        placement=StairPlacement(
            grid_anchor=grid_anchor,
            from_storey=from_storey,
            to_storey=target_to_storey,
            offset_x=offset_x,
            offset_y=offset_y,
            offset_z=offset_z,
            orientation=orientation,
        ),
        railing=StairRailingConfig(
            has_handrail=True,
            railing_height=railing_height,
            handrail_side="BOTH",
        ),
        layer="circulation/stairs",
    )

    railings = generate_stair_railings(
        stair_tag=tag,
        storey=from_storey,
        from_grid=grid_anchor,
        stair_width=width,
        railing_height=railing_height,
        from_offset=(offset_x, offset_y, offset_z),
        to_offset=(offset_x, offset_y, offset_z + total_height),
    )

    return stair_obj, railings
