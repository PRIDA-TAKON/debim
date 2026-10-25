"""
Automated Construction Activity and Milestone Extractor for debim.
Scans spatial structure, storeys, and QTO quantities to generate a baseline schedule.yaml manifest.
"""

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from debim.qto import ElementQTO, ProjectQTO, calculate_qto
from debim.schema import ProjectManifest, load_manifest
from debim.schedule.schema import CrashingActivity, CrashingManifest, Milestone


def _estimate_element_cost(eqto: ElementQTO) -> float:
    """Calculate an estimated baseline cost (THB) for a QTO element."""
    cost = 0.0
    # Concrete: ~3,500 THB / m3
    if eqto.concrete_volume > 0:
        cost += eqto.concrete_volume * 3500.0
    # Rebar: ~35 THB / kg
    if eqto.total_rebar_weight > 0:
        cost += eqto.total_rebar_weight * 35.0
    # Structural steel: ~45 THB / kg
    if eqto.structural_steel_weight > 0:
        cost += eqto.structural_steel_weight * 45.0
    # Timber: ~15,000 THB / m3
    if eqto.timber_volume > 0:
        cost += eqto.timber_volume * 15000.0
    # Substructure items
    if eqto.substructure:
        if eqto.substructure.excavation_volume > 0:
            cost += eqto.substructure.excavation_volume * 150.0
        if eqto.substructure.pile_count > 0:
            cost += eqto.substructure.pile_total_length * 500.0
    # Wall finishes / masonry
    if eqto.wall_finishes:
        cost += eqto.wall_finishes.net_area_one_side * 600.0
    # Roof covering
    if eqto.roof and eqto.roof.sloped_area > 0:
        cost += eqto.roof.sloped_area * 450.0
    # Covering
    if eqto.covering and eqto.covering.area > 0:
        cost += eqto.covering.area * 350.0

    if cost == 0.0:
        cls_name = getattr(eqto, "element_class", "")
        if cls_name in ("IfcDoor", "IfcWindow"):
            cost = 5000.0
        elif cls_name in ("IfcSanitaryTerminal", "IfcWasteTerminal"):
            cost = 4000.0
        elif cls_name in ("IfcLightFixture", "IfcOutlet", "IfcSwitchingDevice"):
            cost = 1500.0
        else:
            cost = 3000.0
    return round(cost, 2)


def _get_element_storey_id(elem: Any) -> str:
    """Extract storey ID from an element placement."""
    placement = getattr(elem, "placement", None)
    if not placement:
        return ""
    if hasattr(placement, "storey") and placement.storey:
        return str(placement.storey)
    if hasattr(placement, "base_storey") and placement.base_storey:
        return str(placement.base_storey)
    if hasattr(placement, "from_storey") and placement.from_storey:
        return str(placement.from_storey)
    return ""


def extract_activities_from_manifest(
    manifest_obj: Union[ProjectManifest, Path, str, Dict[str, Any], Any],
    qto_results: Optional[ProjectQTO] = None,
) -> CrashingManifest:
    """
    Extract construction activities and payment milestones from debim spatial structure and QTO.

    Scans storeys and structural/architectural elements (footings, columns, beams,
    slabs, walls, roofs, stairs, etc.), groups them into construction phases, auto-wires
    logical predecessor relationships, distributes payment percentages across milestones,
    and returns a validated CrashingManifest instance.
    """
    if isinstance(manifest_obj, (str, Path)):
        manifest = load_manifest(manifest_obj)
    elif isinstance(manifest_obj, dict):
        manifest = ProjectManifest.model_validate(manifest_obj)
    elif hasattr(manifest_obj, "manifest") and manifest_obj.manifest:
        manifest = manifest_obj.manifest
    elif isinstance(manifest_obj, ProjectManifest):
        manifest = manifest_obj
    else:
        raise TypeError(f"Unsupported manifest_obj type: {type(manifest_obj)}")

    if qto_results is None:
        qto_results = calculate_qto(manifest_obj if isinstance(manifest_obj, ProjectManifest) else manifest)

    # Map element tags to estimated costs
    qto_cost_map: Dict[str, float] = {}
    if qto_results and hasattr(qto_results, "elements"):
        for eqto in qto_results.elements:
            qto_cost_map[eqto.tag] = _estimate_element_cost(eqto)

    # Retrieve storeys sorted by elevation ascending
    raw_storeys = manifest.spatial_structure.storeys if manifest.spatial_structure else []
    sorted_storeys = sorted(raw_storeys, key=lambda s: s.elevation)
    storey_ids = [s.id for s in sorted_storeys]

    # Collect all elements and map tags to categories and storeys
    substructure_tags: List[str] = []
    columns_by_storey: Dict[str, List[str]] = {sid: [] for sid in storey_ids}
    struct_by_storey: Dict[str, List[str]] = {sid: [] for sid in storey_ids}
    walls_by_storey: Dict[str, List[str]] = {sid: [] for sid in storey_ids}
    stairs_by_storey: Dict[str, List[str]] = {sid: [] for sid in storey_ids}
    finishes_by_storey: Dict[str, List[str]] = {sid: [] for sid in storey_ids}
    roof_tags: List[str] = []

    all_elements = list(manifest.elements)
    if hasattr(manifest, "proxies") and manifest.proxies:
        all_elements.extend(manifest.proxies)

    for elem in all_elements:
        tag = getattr(elem, "tag", None)
        if not tag:
            continue

        cls_name = getattr(elem, "class_", getattr(elem, "ifc_class", type(elem).__name__))
        sid = _get_element_storey_id(elem)
        if sid not in storey_ids and storey_ids:
            sid = storey_ids[0]

        if cls_name in (
            "IfcFooting",
            "IfcEarthworksElement",
            "IfcEarthworksCut",
            "IfcEarthworksFill",
            "IfcSoil",
            "IfcGeotechnicalStratum",
            "IfcRetainingWall",
        ) or "FOOTING" in tag.upper() or "F2" in tag.upper():
            substructure_tags.append(tag)
        elif cls_name == "IfcColumn":
            if sid in columns_by_storey:
                columns_by_storey[sid].append(tag)
            else:
                columns_by_storey[storey_ids[0]].append(tag)
        elif cls_name in ("IfcSlab", "IfcBeam", "IfcMember", "IfcPlate"):
            if "ROOF" in tag.upper() and cls_name in ("IfcSlab", "IfcBeam"):
                roof_tags.append(tag)
            else:
                if sid in struct_by_storey:
                    struct_by_storey[sid].append(tag)
                else:
                    struct_by_storey[storey_ids[0]].append(tag)
        elif cls_name in ("IfcWall", "IfcCurtainWall"):
            if sid in walls_by_storey:
                walls_by_storey[sid].append(tag)
            else:
                walls_by_storey[storey_ids[0]].append(tag)
            # Scan wall children for door/window tags
            children = getattr(elem, "children", []) or []
            for child in children:
                ctag = getattr(child, "tag", None)
                if ctag:
                    finishes_by_storey[sid].append(ctag)
        elif cls_name in ("IfcStair", "IfcStairFlight", "IfcRamp", "IfcRailing"):
            if sid in stairs_by_storey:
                stairs_by_storey[sid].append(tag)
            else:
                stairs_by_storey[storey_ids[0]].append(tag)
        elif cls_name == "IfcRoof":
            roof_tags.append(tag)
        else:
            if sid in finishes_by_storey:
                finishes_by_storey[sid].append(tag)
            else:
                finishes_by_storey[storey_ids[0]].append(tag)

    # Build CrashingActivity objects with logical predecessor relationships
    activities: List[CrashingActivity] = []
    last_structural_id: Optional[str] = None
    last_activity_id: Optional[str] = None

    # 1. Substructure
    if substructure_tags:
        act_id = "ACT_SUBSTRUCTURE"
        total_cost = sum(qto_cost_map.get(t, 5000.0) for t in substructure_tags)
        if total_cost == 0.0:
            total_cost = float(len(substructure_tags) * 5000.0)
        norm_dur = max(7, min(28, int(math.ceil(len(substructure_tags) * 2.5))))
        crash_dur = max(1, int(math.floor(norm_dur * 0.7)))

        act = CrashingActivity(
            id=act_id,
            name="Substructure & Foundation Work",
            element_ids=substructure_tags,
            predecessors=[],
            normal_duration=norm_dur,
            crash_duration=crash_dur,
            normal_cost=round(total_cost, 2),
            crash_cost=round(total_cost * 1.3, 2),
            cost_weight=round(total_cost, 2),
            status="NOT_STARTED",
            progress_percent=0.0,
            progress_log=[],
        )
        activities.append(act)
        last_structural_id = act_id
        last_activity_id = act_id

    # 2. Per-Storey Construction Activities
    for s in sorted_storeys:
        sid = s.id
        sname = s.name or sid

        # a) Columns
        cols = columns_by_storey.get(sid, [])
        if cols:
            act_id = f"ACT_COL_{sid}"
            preds = [last_structural_id] if last_structural_id else []
            total_cost = sum(qto_cost_map.get(t, 6000.0) for t in cols)
            if total_cost == 0.0:
                total_cost = float(len(cols) * 6000.0)
            norm_dur = max(5, min(21, int(math.ceil(len(cols) * 1.5))))
            crash_dur = max(1, int(math.floor(norm_dur * 0.7)))

            act = CrashingActivity(
                id=act_id,
                name=f"Structural Columns - {sname}",
                element_ids=cols,
                predecessors=preds,
                normal_duration=norm_dur,
                crash_duration=crash_dur,
                normal_cost=round(total_cost, 2),
                crash_cost=round(total_cost * 1.3, 2),
                cost_weight=round(total_cost, 2),
                status="NOT_STARTED",
                progress_percent=0.0,
                progress_log=[],
            )
            activities.append(act)
            last_activity_id = act_id

        # b) Beams & Slabs
        structs = struct_by_storey.get(sid, [])
        if structs:
            act_id = f"ACT_STRUCT_{sid}"
            col_act_id = f"ACT_COL_{sid}"
            if any(a.id == col_act_id for a in activities):
                preds = [col_act_id]
            elif last_structural_id:
                preds = [last_structural_id]
            else:
                preds = []

            total_cost = sum(qto_cost_map.get(t, 8000.0) for t in structs)
            if total_cost == 0.0:
                total_cost = float(len(structs) * 8000.0)
            norm_dur = max(7, min(28, int(math.ceil(len(structs) * 2.0))))
            crash_dur = max(1, int(math.floor(norm_dur * 0.7)))

            act = CrashingActivity(
                id=act_id,
                name=f"Floor Framing & Slabs - {sname}",
                element_ids=structs,
                predecessors=preds,
                normal_duration=norm_dur,
                crash_duration=crash_dur,
                normal_cost=round(total_cost, 2),
                crash_cost=round(total_cost * 1.3, 2),
                cost_weight=round(total_cost, 2),
                status="NOT_STARTED",
                progress_percent=0.0,
                progress_log=[],
            )
            activities.append(act)
            last_structural_id = act_id
            last_activity_id = act_id

        # c) Walls & Enclosure
        walls = walls_by_storey.get(sid, [])
        if walls:
            act_id = f"ACT_WALL_{sid}"
            struct_act_id = f"ACT_STRUCT_{sid}"
            col_act_id = f"ACT_COL_{sid}"
            if any(a.id == struct_act_id for a in activities):
                preds = [struct_act_id]
            elif any(a.id == col_act_id for a in activities):
                preds = [col_act_id]
            elif last_structural_id:
                preds = [last_structural_id]
            else:
                preds = []

            total_cost = sum(qto_cost_map.get(t, 5000.0) for t in walls)
            if total_cost == 0.0:
                total_cost = float(len(walls) * 5000.0)
            norm_dur = max(5, min(21, int(math.ceil(len(walls) * 1.5))))
            crash_dur = max(1, int(math.floor(norm_dur * 0.7)))

            act = CrashingActivity(
                id=act_id,
                name=f"Walls & Enclosure - {sname}",
                element_ids=walls,
                predecessors=preds,
                normal_duration=norm_dur,
                crash_duration=crash_dur,
                normal_cost=round(total_cost, 2),
                crash_cost=round(total_cost * 1.3, 2),
                cost_weight=round(total_cost, 2),
                status="NOT_STARTED",
                progress_percent=0.0,
                progress_log=[],
            )
            activities.append(act)
            last_activity_id = act_id

        # d) Stairs
        stairs = stairs_by_storey.get(sid, [])
        if stairs:
            act_id = f"ACT_STAIR_{sid}"
            struct_act_id = f"ACT_STRUCT_{sid}"
            preds = [struct_act_id] if any(a.id == struct_act_id for a in activities) else ([last_structural_id] if last_structural_id else [])
            total_cost = sum(qto_cost_map.get(t, 10000.0) for t in stairs)
            norm_dur = max(5, min(14, int(math.ceil(len(stairs) * 3.0))))
            crash_dur = max(1, int(math.floor(norm_dur * 0.7)))

            act = CrashingActivity(
                id=act_id,
                name=f"Stairs & Railings - {sname}",
                element_ids=stairs,
                predecessors=preds,
                normal_duration=norm_dur,
                crash_duration=crash_dur,
                normal_cost=round(total_cost, 2),
                crash_cost=round(total_cost * 1.3, 2),
                cost_weight=round(total_cost, 2),
                status="NOT_STARTED",
                progress_percent=0.0,
                progress_log=[],
            )
            activities.append(act)
            last_activity_id = act_id

        # e) Finishes & MEP
        finishes = finishes_by_storey.get(sid, [])
        if finishes:
            act_id = f"ACT_FINISH_{sid}"
            wall_act_id = f"ACT_WALL_{sid}"
            struct_act_id = f"ACT_STRUCT_{sid}"
            if any(a.id == wall_act_id for a in activities):
                preds = [wall_act_id]
            elif any(a.id == struct_act_id for a in activities):
                preds = [struct_act_id]
            elif last_activity_id:
                preds = [last_activity_id]
            else:
                preds = []

            total_cost = sum(qto_cost_map.get(t, 3000.0) for t in finishes)
            if total_cost == 0.0:
                total_cost = float(len(finishes) * 3000.0)
            norm_dur = max(5, min(21, int(math.ceil(len(finishes) * 1.5))))
            crash_dur = max(1, int(math.floor(norm_dur * 0.7)))

            act = CrashingActivity(
                id=act_id,
                name=f"Finishes, Doors & MEP - {sname}",
                element_ids=finishes,
                predecessors=preds,
                normal_duration=norm_dur,
                crash_duration=crash_dur,
                normal_cost=round(total_cost, 2),
                crash_cost=round(total_cost * 1.3, 2),
                cost_weight=round(total_cost, 2),
                status="NOT_STARTED",
                progress_percent=0.0,
                progress_log=[],
            )
            activities.append(act)
            last_activity_id = act_id

    # 3. Roof Phase
    if roof_tags:
        act_id = "ACT_ROOF"
        preds = [last_activity_id] if last_activity_id else ([last_structural_id] if last_structural_id else [])
        total_cost = sum(qto_cost_map.get(t, 12000.0) for t in roof_tags)
        if total_cost == 0.0:
            total_cost = float(len(roof_tags) * 12000.0)
        norm_dur = max(7, min(21, int(math.ceil(len(roof_tags) * 2.5))))
        crash_dur = max(1, int(math.floor(norm_dur * 0.7)))

        act = CrashingActivity(
            id=act_id,
            name="Roof Construction & Covering",
            element_ids=roof_tags,
            predecessors=preds,
            normal_duration=norm_dur,
            crash_duration=crash_dur,
            normal_cost=round(total_cost, 2),
            crash_cost=round(total_cost * 1.3, 2),
            cost_weight=round(total_cost, 2),
            status="NOT_STARTED",
            progress_percent=0.0,
            progress_log=[],
        )
        activities.append(act)

    # Standard Fallback: Ensure at least 1 activity exists if model was completely empty
    if not activities:
        act = CrashingActivity(
            id="ACT_GEN_01",
            name="General Construction Work",
            element_ids=[],
            predecessors=[],
            normal_duration=10,
            crash_duration=7,
            normal_cost=50000.0,
            crash_cost=65000.0,
            cost_weight=50000.0,
            status="NOT_STARTED",
            progress_percent=0.0,
            progress_log=[],
        )
        activities.append(act)

    # 4. Generate Payment Milestones
    total_project_cost = sum(a.normal_cost for a in activities)
    milestones: List[Milestone] = []

    # Partition activities into up to 4 standardized payment milestones
    n_act = len(activities)
    if n_act == 1:
        chunk_size = 1
    else:
        chunk_size = max(1, math.ceil(n_act / 4))

    chunks = [activities[i : i + chunk_size] for i in range(0, n_act, chunk_size)]
    num_milestones = len(chunks)

    # Equal payment percent distribution summing exactly to 100.0%
    base_percent = round(100.0 / num_milestones, 2)
    percents = [base_percent] * num_milestones
    percents[-1] = round(100.0 - sum(percents[:-1]), 2)

    milestone_titles = [
        "Substructure & Foundation",
        "Level 1 Structure & Framing",
        "Upper Level Structure & Enclosure",
        "Roofing & Project Completion",
    ]

    for idx, chunk in enumerate(chunks):
        ms_id = f"MS-0{idx + 1}"
        ms_name = f"งวดที่ {idx + 1}: {milestone_titles[idx] if idx < len(milestone_titles) else f'Phase {idx + 1} Completion'}"
        req_act_ids = [a.id for a in chunk]
        pct = percents[idx]
        amt = round(total_project_cost * (pct / 100.0), 2)

        milestones.append(
            Milestone(
                id=ms_id,
                name=ms_name,
                payment_percent=pct,
                payment_amount=amt,
                required_activities=req_act_ids,
            )
        )

    proj_id = manifest.project.id if manifest.project and manifest.project.id else "PROJECT-SCHEDULE"

    return CrashingManifest(
        project_id=proj_id,
        as_of_date=None,
        overhead_per_day=2000.0,
        max_budget=round(total_project_cost * 1.25, 2) if total_project_cost > 0 else None,
        milestones=milestones,
        activities=activities,
    )
