"""
Automated Structural & Architectural Derivation Engine for debim (debim derive).

Converts topological / relative touching space declarations (touching: { target, side, align })
into complete, engineering-compliant 3D BIM elements (Walls, Doors, Windows, Columns, Beams, Slabs, Footings).
"""

import math
from typing import Dict, List, Literal, Optional, Set, Tuple, Any
from debim.schema import (
    BeamPlacement,
    BoxProfile,
    ColumnPlacement,
    Dimensions,
    FootingPlacement,
    FootingProfile,
    Grids,
    IfcBeam,
    IfcColumn,
    IfcDoor,
    IfcFooting,
    IfcSlab,
    IfcSpace,
    IfcWall,
    IfcWindow,
    Material,
    ProjectInfo,
    ProjectManifest,
    SlabPlacement,
    SpacePlacement,
    SpatialStructure,
    Storey,
    WallPlacement,
)


class Space2DBounds:
    def __init__(self, tag: str, min_x: float, min_y: float, max_x: float, max_y: float, raw_space: Any = None):
        self.tag = tag
        self.min_x = round(min_x, 4)
        self.min_y = round(min_y, 4)
        self.max_x = round(max_x, 4)
        self.max_y = round(max_y, 4)
        self.raw_space = raw_space

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def center_x(self) -> float:
        return (self.min_x + self.max_x) / 2.0

    @property
    def center_y(self) -> float:
        return (self.min_y + self.max_y) / 2.0

    def polygon_corners(self) -> List[Tuple[float, float]]:
        return [
            (self.min_x, self.min_y),
            (self.max_x, self.min_y),
            (self.max_x, self.max_y),
            (self.min_x, self.max_y),
        ]


def solve_relative_space_positions(spaces: List[Any]) -> Dict[str, Space2DBounds]:
    """
    Solves 2D absolute coordinates for spaces defined with origin/dimensions or touching relative constraints.
    """
    resolved: Dict[str, Space2DBounds] = {}
    pending = list(spaces)

    # First pass: resolve spaces with explicit origin & dimensions
    unresolved = []
    for sp in pending:
        tag = getattr(sp, "tag", None) or (sp.get("tag") if isinstance(sp, dict) else None)
        orig = getattr(sp, "origin", None) or (sp.get("placement", {}).get("origin") if isinstance(sp, dict) and isinstance(sp.get("placement"), dict) else getattr(sp.placement, "origin", None) if hasattr(sp, "placement") and sp.placement else None)
        dims = getattr(sp, "dimensions", None) or (sp.get("placement", {}).get("dimensions") if isinstance(sp, dict) and isinstance(sp.get("placement"), dict) else getattr(sp.placement, "dimensions", None) if hasattr(sp, "placement") and sp.placement else None)

        if orig is None and isinstance(sp, dict):
            orig = sp.get("origin")
        if dims is None and isinstance(sp, dict):
            dims = sp.get("dimensions")

        if orig is not None and dims is not None:
            x, y = float(orig[0]), float(orig[1])
            w, h = float(dims[0]), float(dims[1])
            resolved[tag] = Space2DBounds(tag, x, y, x + w, y + h, raw_space=sp)
        else:
            unresolved.append(sp)

    # If no space had explicit origin, pick the first unresolved space and place at (0, 0)
    if not resolved and unresolved:
        first_sp = unresolved.pop(0)
        tag = getattr(first_sp, "tag", None) or (first_sp.get("tag") if isinstance(first_sp, dict) else None)
        dims = getattr(first_sp, "dimensions", None) or (first_sp.get("placement", {}).get("dimensions") if isinstance(first_sp, dict) and isinstance(first_sp.get("placement"), dict) else getattr(first_sp.placement, "dimensions", None) if hasattr(first_sp, "placement") and first_sp.placement else None)
        if dims is None and isinstance(first_sp, dict):
            dims = first_sp.get("dimensions")
        w = float(dims[0]) if dims else 4.0
        h = float(dims[1]) if dims else 4.0
        resolved[tag] = Space2DBounds(tag, 0.0, 0.0, w, h, raw_space=first_sp)

    # Iterative resolution for spaces using touching constraints
    max_passes = len(spaces) * 2 + 5
    for _ in range(max_passes):
        if not unresolved:
            break
        still_unresolved = []
        for sp in unresolved:
            tag = getattr(sp, "tag", None) or (sp.get("tag") if isinstance(sp, dict) else None)
            touching = getattr(sp, "touching", None) or (sp.get("placement", {}).get("touching") if isinstance(sp, dict) and isinstance(sp.get("placement"), dict) else getattr(sp.placement, "touching", None) if hasattr(sp, "placement") and sp.placement else None)
            if touching is None and isinstance(sp, dict):
                touching = sp.get("touching")

            dims = getattr(sp, "dimensions", None) or (sp.get("placement", {}).get("dimensions") if isinstance(sp, dict) and isinstance(sp.get("placement"), dict) else getattr(sp.placement, "dimensions", None) if hasattr(sp, "placement") and sp.placement else None)
            if dims is None and isinstance(sp, dict):
                dims = sp.get("dimensions")

            w = float(dims[0]) if dims else 4.0
            h = float(dims[1]) if dims else 4.0

            target_tag = getattr(touching, "target", None) or (touching.get("target") if isinstance(touching, dict) else None) if touching else None
            side = getattr(touching, "side", None) or (touching.get("side") if isinstance(touching, dict) else "NORTH") if touching else "NORTH"
            align = getattr(touching, "align", None) or (touching.get("align") if isinstance(touching, dict) else "LEFT") if touching else "LEFT"

            if target_tag in resolved:
                target = resolved[target_tag]
                side_str = str(side).upper()
                align_str = str(align or "LEFT").upper()

                if side_str == "NORTH":
                    min_y = target.max_y
                    max_y = min_y + h
                    if align_str == "LEFT":
                        min_x = target.min_x
                    elif align_str == "RIGHT":
                        min_x = target.max_x - w
                    elif align_str == "CENTER":
                        min_x = target.center_x - w / 2.0
                    else:
                        min_x = target.min_x
                    max_x = min_x + w

                elif side_str == "SOUTH":
                    max_y = target.min_y
                    min_y = max_y - h
                    if align_str == "LEFT":
                        min_x = target.min_x
                    elif align_str == "RIGHT":
                        min_x = target.max_x - w
                    elif align_str == "CENTER":
                        min_x = target.center_x - w / 2.0
                    else:
                        min_x = target.min_x
                    max_x = min_x + w

                elif side_str == "EAST":
                    min_x = target.max_x
                    max_x = min_x + w
                    if align_str in ("BOTTOM", "LEFT"):
                        min_y = target.min_y
                    elif align_str in ("TOP", "RIGHT"):
                        min_y = target.max_y - h
                    elif align_str == "CENTER":
                        min_y = target.center_y - h / 2.0
                    else:
                        min_y = target.min_y
                    max_y = min_y + h

                elif side_str == "WEST":
                    max_x = target.min_x
                    min_x = max_x - w
                    if align_str in ("BOTTOM", "LEFT"):
                        min_y = target.min_y
                    elif align_str in ("TOP", "RIGHT"):
                        min_y = target.max_y - h
                    elif align_str == "CENTER":
                        min_y = target.center_y - h / 2.0
                    else:
                        min_y = target.min_y
                    max_y = min_y + h

                else:
                    min_x, min_y = 0.0, 0.0
                    max_x, max_y = w, h

                resolved[tag] = Space2DBounds(tag, min_x, min_y, max_x, max_y, raw_space=sp)
            else:
                still_unresolved.append(sp)

        unresolved = still_unresolved

    return resolved


class Segment2D:
    def __init__(self, p1: Tuple[float, float], p2: Tuple[float, float], space_tag: str):
        if (p1[0] < p2[0]) or (math.isclose(p1[0], p2[0], abs_tol=1e-4) and p1[1] < p2[1]):
            self.p1 = (round(p1[0], 4), round(p1[1], 4))
            self.p2 = (round(p2[0], 4), round(p2[1], 4))
        else:
            self.p1 = (round(p2[0], 4), round(p2[1], 4))
            self.p2 = (round(p1[0], 4), round(p1[1], 4))
        self.space_tag = space_tag

    @property
    def is_horizontal(self) -> bool:
        return math.isclose(self.p1[1], self.p2[1], abs_tol=1e-4)

    @property
    def is_vertical(self) -> bool:
        return math.isclose(self.p1[0], self.p2[0], abs_tol=1e-4)

    @property
    def length(self) -> float:
        return math.hypot(self.p2[0] - self.p1[0], self.p2[1] - self.p1[1])


class AtomicWallSegment:
    def __init__(self, p1: Tuple[float, float], p2: Tuple[float, float], spaces: Set[str]):
        if (p1[0] < p2[0]) or (math.isclose(p1[0], p2[0], abs_tol=1e-4) and p1[1] < p2[1]):
            self.p1 = (round(p1[0], 4), round(p1[1], 4))
            self.p2 = (round(p2[0], 4), round(p2[1], 4))
        else:
            self.p1 = (round(p2[0], 4), round(p2[1], 4))
            self.p2 = (round(p1[0], 4), round(p1[1], 4))
        self.spaces = set(spaces)

    @property
    def is_shared(self) -> bool:
        return len(self.spaces) >= 2

    @property
    def length(self) -> float:
        return math.hypot(self.p2[0] - self.p1[0], self.p2[1] - self.p1[1])


def extract_atomic_wall_segments(resolved_spaces: Dict[str, Space2DBounds]) -> List[AtomicWallSegment]:
    """
    Decomposes overlapping space boundaries into disjoint atomic 2D wall segments,
    classifying each segment as shared (internal) or exterior.
    """
    horiz_segments: List[Segment2D] = []
    vert_segments: List[Segment2D] = []

    for tag, bounds in resolved_spaces.items():
        p1 = (bounds.min_x, bounds.min_y)
        p2 = (bounds.max_x, bounds.min_y)
        p3 = (bounds.max_x, bounds.max_y)
        p4 = (bounds.min_x, bounds.max_y)

        horiz_segments.append(Segment2D(p1, p2, tag))  # South
        horiz_segments.append(Segment2D(p4, p3, tag))  # North
        vert_segments.append(Segment2D(p1, p4, tag))   # West
        vert_segments.append(Segment2D(p2, p3, tag))   # East

    atomic_segments: List[AtomicWallSegment] = []

    # Process Horizontal Segments (grouped by Y coordinate)
    y_groups: Dict[float, List[Segment2D]] = {}
    for seg in horiz_segments:
        y_val = seg.p1[1]
        matched_y = None
        for k in y_groups.keys():
            if math.isclose(k, y_val, abs_tol=1e-4):
                matched_y = k
                break
        if matched_y is None:
            matched_y = y_val
            y_groups[matched_y] = []
        y_groups[matched_y].append(seg)

    for y_val, segs in y_groups.items():
        x_points = set()
        for s in segs:
            x_points.add(s.p1[0])
            x_points.add(s.p2[0])
        sorted_x = sorted(list(x_points))

        for i in range(len(sorted_x) - 1):
            x_start = sorted_x[i]
            x_end = sorted_x[i + 1]
            if x_end - x_start < 1e-4:
                continue

            mid_x = (x_start + x_end) / 2.0
            covering_spaces = set()
            for s in segs:
                if s.p1[0] <= mid_x <= s.p2[0]:
                    covering_spaces.add(s.space_tag)

            if covering_spaces:
                atomic_segments.append(
                    AtomicWallSegment((x_start, y_val), (x_end, y_val), covering_spaces)
                )

    # Process Vertical Segments (grouped by X coordinate)
    x_groups: Dict[float, List[Segment2D]] = {}
    for seg in vert_segments:
        x_val = seg.p1[0]
        matched_x = None
        for k in x_groups.keys():
            if math.isclose(k, x_val, abs_tol=1e-4):
                matched_x = k
                break
        if matched_x is None:
            matched_x = x_val
            x_groups[matched_x] = []
        x_groups[matched_x].append(seg)

    for x_val, segs in x_groups.items():
        y_points = set()
        for s in segs:
            y_points.add(s.p1[1])
            y_points.add(s.p2[1])
        sorted_y = sorted(list(y_points))

        for i in range(len(sorted_y) - 1):
            y_start = sorted_y[i]
            y_end = sorted_y[i + 1]
            if y_end - y_start < 1e-4:
                continue

            mid_y = (y_start + y_end) / 2.0
            covering_spaces = set()
            for s in segs:
                if s.p1[1] <= mid_y <= s.p2[1]:
                    covering_spaces.add(s.space_tag)

            if covering_spaces:
                atomic_segments.append(
                    AtomicWallSegment((x_val, y_start), (x_val, y_end), covering_spaces)
                )

    return atomic_segments


def derive_project_from_spaces(manifest_or_dict: Any) -> ProjectManifest:
    """
    Core debim derive auto-framing engine.
    Converts relative touching spaces into complete structural and architectural BIM elements.
    """
    from pathlib import Path
    import yaml

    if isinstance(manifest_or_dict, (str, Path)):
        p = Path(manifest_or_dict)
        with open(p, "r", encoding="utf-8") as f:
            raw_dict = yaml.safe_load(f) or {}
        spaces_data = raw_dict.get("spaces", []) or raw_dict.get("elements", [])
    elif isinstance(manifest_or_dict, dict):
        raw_dict = manifest_or_dict
        spaces_data = raw_dict.get("spaces", []) or raw_dict.get("elements", [])
    else:
        raw_dict = manifest_or_dict.model_dump(by_alias=True, exclude_none=True)
        spaces_data = manifest_or_dict.elements

    # Extract variables if present
    raw_variables = raw_dict.get("variables")
    parsed_variables = None
    if raw_variables and isinstance(raw_variables, dict):
        from debim.schema import FurnitureVariable
        parsed_variables = {
            k: FurnitureVariable.model_validate(v) if isinstance(v, dict) else v
            for k, v in raw_variables.items()
        }

    spaces_list = []
    if isinstance(spaces_data, dict):
        for tag, info in spaces_data.items():
            if isinstance(info, dict):
                info["tag"] = tag
                spaces_list.append(IfcSpace.model_validate(info))
    elif isinstance(spaces_data, list):
        for item in spaces_data:
            if isinstance(item, IfcSpace):
                spaces_list.append(item)
            elif isinstance(item, dict) and item.get("class") in ("IfcSpace", None):
                spaces_list.append(IfcSpace.model_validate(item))

    # 1. Solve 2D coordinates for all touching spaces
    resolved_spaces = solve_relative_space_positions(spaces_list)

    # 2. Build Grid Axes from space corner coordinates
    all_x = set()
    all_y = set()
    for bounds in resolved_spaces.values():
        all_x.add(bounds.min_x)
        all_x.add(bounds.max_x)
        all_y.add(bounds.min_y)
        all_y.add(bounds.max_y)

    sorted_x = sorted(list(all_x))
    sorted_y = sorted(list(all_y))

    grid_x_map: Dict[float, str] = {}
    axes_x_dict: Dict[str, float] = {}
    for idx, x_val in enumerate(sorted_x):
        grid_name = str(idx + 1)
        grid_x_map[x_val] = grid_name
        axes_x_dict[grid_name] = x_val

    grid_y_map: Dict[float, str] = {}
    axes_y_dict: Dict[str, float] = {}
    y_labels = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N"]
    for idx, y_val in enumerate(sorted_y):
        grid_name = y_labels[idx] if idx < len(y_labels) else f"Y{idx+1}"
        grid_y_map[y_val] = grid_name
        axes_y_dict[grid_name] = y_val

    def get_grid_ref(x: float, y: float) -> Tuple[str, str]:
        gx_name = None
        for k_x, name_x in grid_x_map.items():
            if math.isclose(k_x, x, abs_tol=1e-3):
                gx_name = name_x
                break
        if gx_name is None:
            gx_name = str(round(x, 2))

        gy_name = None
        for k_y, name_y in grid_y_map.items():
            if math.isclose(k_y, y, abs_tol=1e-3):
                gy_name = name_y
                break
        if gy_name is None:
            gy_name = str(round(y, 2))

        return (gx_name, gy_name)

    # 3. Extract atomic 2D wall segments
    atomic_segments = extract_atomic_wall_segments(resolved_spaces)

    # Prepare standard materials
    materials = [
        Material(id="CONCRETE", name="Reinforced Concrete 240 ksc", category="structural", unit_cost_ref="MAT-CONC-240KSC"),
        Material(id="BRICK_MASONRY", name="Clay Brick Masonry", category="architectural", unit_cost_ref="MAT-BRICK-MASONRY"),
        Material(id="GLASS", name="Clear Float Glass 6mm", category="architectural", unit_cost_ref="MAT-GLASS-6MM"),
        Material(id="STEEL", name="Structural Steel SS400", category="structural", unit_cost_ref="MAT-STEEL-SS400"),
    ]

    elements: List[Any] = []

    # Map of space connectivity requirements
    must_connect_pairs: Set[Tuple[str, str]] = set()
    for sp in spaces_list:
        sp_tag = sp.tag
        must_conn = sp.must_connect or []
        if sp.design_spec and sp.design_spec.adjacencies and sp.design_spec.adjacencies.must_connect:
            must_conn.extend(sp.design_spec.adjacencies.must_connect)
        for target in must_conn:
            pair = tuple(sorted([sp_tag, target]))
            must_connect_pairs.add(pair)

    # 4. Generate Walls, Doors, Windows, Beams (Ground Tie Beams & Top Beams)
    wall_index = 1
    door_index = 1
    window_index = 1

    for seg in atomic_segments:
        g1 = get_grid_ref(seg.p1[0], seg.p1[1])
        g2 = get_grid_ref(seg.p2[0], seg.p2[1])

        wall_tag = f"WALL-{g1[0]}{g1[1]}_{g2[0]}{g2[1]}"
        is_shared = seg.is_shared

        wall_children = []

        if is_shared:
            spaces_tuple = tuple(sorted(list(seg.spaces)))
            if len(spaces_tuple) == 2 and (spaces_tuple in must_connect_pairs or seg.length >= 1.20):
                door_tag = f"D-{spaces_tuple[0]}_{spaces_tuple[1]}" if spaces_tuple in must_connect_pairs else f"D-{door_index:02d}"
                door_index += 1
                door = IfcDoor(
                    tag=door_tag,
                    material="WOOD",
                    dimensions=Dimensions(width=0.90, height=2.00),
                    offset_distance=round(seg.length / 2.0, 3),
                    sill_height=0.00,
                    host_wall=wall_tag,
                )
                wall_children.append(door)
        else:
            habitable = True
            for st in seg.spaces:
                if "BATH" in st or "TOILET" in st or "STORE" in st or "PUMP" in st:
                    habitable = False
            if seg.length >= 1.50:
                win_w = 1.20 if seg.length >= 2.0 else 0.90
                win_tag = f"W-{window_index:02d}"
                window_index += 1
                window = IfcWindow(
                    tag=win_tag,
                    material="GLASS",
                    dimensions=Dimensions(width=win_w, height=1.20),
                    offset_distance=round(seg.length / 2.0, 3),
                    sill_height=0.90,
                    host_wall=wall_tag,
                )
                wall_children.append(window)

        wall = IfcWall(
            tag=wall_tag,
            material="BRICK_MASONRY",
            thickness=0.15 if is_shared else 0.20,
            height=2.80,
            placement=WallPlacement(
                from_grid=g1,
                to_grid=g2,
                storey="STOREY-1",
            ),
            children=wall_children,
        )
        elements.append(wall)

        # Ground Tie Beam (คานคอดิน)
        gb = IfcBeam(
            tag=f"GB-{g1[0]}{g1[1]}_{g2[0]}{g2[1]}",
            material="CONCRETE",
            profile=BoxProfile(shape="BOX", width=0.20, depth=0.40),
            placement=BeamPlacement(
                from_grid=g1,
                to_grid=g2,
                storey="STOREY-1",
                offset_z=0.00,
            ),
        )
        elements.append(gb)

        # Top Ring Beam (คานรับชั้นสอง/คานรับหลังคา)
        beam = IfcBeam(
            tag=f"B-{g1[0]}{g1[1]}_{g2[0]}{g2[1]}",
            material="CONCRETE",
            profile=BoxProfile(shape="BOX", width=0.20, depth=0.40),
            placement=BeamPlacement(
                from_grid=g1,
                to_grid=g2,
                storey="STOREY-1",
                offset_z=2.80,
            ),
        )
        elements.append(beam)

    # 5. Generate Columns & Footings at unique corner vertices
    corner_vertices: Set[Tuple[float, float]] = set()
    for bounds in resolved_spaces.values():
        for pt in bounds.polygon_corners():
            corner_vertices.add((round(pt[0], 4), round(pt[1], 4)))

    for pt in sorted(list(corner_vertices)):
        gx, gy = get_grid_ref(pt[0], pt[1])
        col_tag = f"C-{gx}_{gy}"
        ftg_tag = f"F-{gx}_{gy}"

        column = IfcColumn(
            tag=col_tag,
            material="CONCRETE",
            profile=BoxProfile(shape="BOX", width=0.20, depth=0.20),
            placement=ColumnPlacement(
                grid=(gx, gy),
                base_storey="STOREY-1",
                top_storey="STOREY-1",
                height=2.80,
            ),
        )
        elements.append(column)

        footing = IfcFooting(
            tag=ftg_tag,
            material="CONCRETE",
            profile=FootingProfile(shape="BOX", width=1.00, depth=1.00, thickness=0.35),
            placement=FootingPlacement(
                grid=(gx, gy),
                storey="STOREY-1",
                offset_z=-0.50,
            ),
        )
        elements.append(footing)

    # 6. Generate Slabs for each Space
    for tag, bounds in resolved_spaces.items():
        c1 = get_grid_ref(bounds.min_x, bounds.min_y)
        c2 = get_grid_ref(bounds.max_x, bounds.min_y)
        c3 = get_grid_ref(bounds.max_x, bounds.max_y)
        c4 = get_grid_ref(bounds.min_x, bounds.max_y)

        slab = IfcSlab(
            tag=f"SLAB-{tag}",
            material="CONCRETE",
            thickness=0.12,
            placement=SlabPlacement(
                boundary=[c1, c2, c3, c4],
                storey="STOREY-1",
            ),
        )
        elements.append(slab)

        sp_obj = bounds.raw_space
        if isinstance(sp_obj, IfcSpace):
            sp_obj.placement = SpacePlacement(
                boundary=[c1, c2, c3, c4],
                storey="STOREY-1",
            )
            elements.append(sp_obj)

    spatial = SpatialStructure(
        storeys=[
            Storey(id="STOREY-1", name="Ground Floor (FL1)", elevation=0.0, height=2.80),
        ]
    )

    project_info = ProjectInfo(
        id=raw_dict.get("project", {}).get("id", "PRJ-DERIVED-HOUSE"),
        name=raw_dict.get("project", {}).get("name", "Auto-Derived House Model"),
        description="Complete 3D BIM Model generated from relative touching spaces via debim derive",
    )

    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project=project_info,
        spatial_structure=spatial,
        grids=Grids(axes_x=axes_x_dict, axes_y=axes_y_dict),
        materials=materials,
        elements=elements,
        variables=parsed_variables,
    )

    return manifest
