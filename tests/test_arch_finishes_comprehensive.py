"""
Comprehensive Unit Test Suite for Architectural Finishes, Enclosure Systems & Interior Furnishings (~150 Entities).
"""

import tempfile
from pathlib import Path
import pytest
from debim.compiler import StepSerializer, compile_to_ifc, derive_custom_ifc_class
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    Dimensions,
    IfcBuildingElementProxy,
    IfcColumn,
    IfcCovering,
    IfcCurtainWall,
    IfcCustomElement,
    IfcDoor,
    IfcPlate,
    IfcRoof,
    IfcSlab,
    IfcWall,
    IfcWindow,
    ProjectManifest,
)
from debim.viewer import generate_viewer_html


def test_surface_coverings_claddings_resolution_and_clipping():
    """Test resolution and Shapely polygon offset/clipping for IfcCovering entities."""
    manifest = ProjectManifest(
        project={"id": "PROJ-FINISH", "name": "Architectural Finishes Test"},
        spatial_structure={
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.5},
            ]
        },
        grids={
            "axes_x": {"1": 0.0, "2": 6.0, "3": 12.0},
            "axes_y": {"A": 0.0, "B": 6.0, "C": 10.0},
        },
        materials=[
            {"id": "MAT_TILES", "name": "Ceramic Tiles", "category": "FINISH", "unit_cost_ref": "MAT-TILE"},
            {"id": "MAT_GYPSUM", "name": "Gypsum Board", "category": "FINISH", "unit_cost_ref": "MAT-GYP"},
            {"id": "MAT_CLADD", "name": "Aluminum Cladding", "category": "FINISH", "unit_cost_ref": "MAT-ALUM"},
            {"id": "MAT_CONC", "name": "Concrete", "category": "CONCRETE", "unit_cost_ref": "MAT-CONC"},
        ],
        elements=[
            IfcSlab(
                **{
                    "class": "IfcSlab",
                    "tag": "SLAB-L1",
                    "material": "MAT_CONC",
                    "thickness": 0.20,
                    "placement": {"boundary": [["1", "A"], ["3", "A"], ["3", "C"], ["1", "C"]], "storey": "L1"},
                }
            ),
            # Flooring clipped to slab with offset
            IfcCovering(
                tag="COV-FLOOR-1",
                class_="IfcCovering",
                covering_type="FLOORING",
                material="MAT_TILES",
                thickness=0.015,
                placement={
                    "boundary": [["1", "A"], ["3", "A"], ["3", "C"], ["1", "C"]],
                    "storey": "L1",
                    "offset_z": 0.20,
                    "boundary_offset": -0.05,
                    "clip_to_slab": True,
                },
            ),
            # Ceiling
            IfcCovering(
                tag="COV-CEIL-1",
                class_="IfcCovering",
                covering_type="CEILING",
                material="MAT_GYPSUM",
                thickness=0.009,
                placement={
                    "boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]],
                    "storey": "L1",
                    "offset_z": 2.80,
                },
            ),
            # Skirting
            IfcCovering(
                tag="COV-SKIRT-1",
                class_="IfcCovering",
                covering_type="SKIRTING",
                material="MAT_TILES",
                thickness=0.01,
                placement={
                    "boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]],
                    "storey": "L1",
                    "length": 24.0,
                },
            ),
            # Cladding
            IfcCovering(
                tag="COV-CLAD-1",
                class_="IfcCovering",
                covering_type="CLADDING",
                material="MAT_CLADD",
                thickness=0.02,
                placement={
                    "boundary": [["1", "A"], ["3", "A"], ["3", "B"]],
                    "storey": "L1",
                    "offset_z": 0.0,
                },
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.coverings) == 4

    cov_map = {c.tag: c for c in resolved.coverings}

    # Verify flooring resolution & offset reduction
    flr = cov_map["COV-FLOOR-1"]
    assert flr.covering_type == "FLOORING"
    assert flr.area < 120.0  # Reduced due to -0.05m offset from 12x10=120m²
    assert flr.polygon[0][2] == 0.20  # Storey 0 + 0.20 offset

    # Verify ceiling resolution
    ceil = cov_map["COV-CEIL-1"]
    assert ceil.covering_type == "CEILING"
    assert ceil.area == pytest.approx(36.0, rel=1e-3)  # 6m x 6m = 36m²
    assert ceil.polygon[0][2] == 2.80

    # Verify QTO takeoffs
    qto = calculate_qto(resolved)
    assert len(resolved.coverings) == 4
    assert qto.total_floor_tile_area > 0
    assert qto.total_ceiling_gypsum_area == pytest.approx(36.0, rel=1e-3)


def test_curtain_wall_facade_and_plate_resolution():
    """Test Curtain Wall, Transom/Mullion grids, and Glass Plate systems."""
    manifest = ProjectManifest(
        project={"id": "PROJ-FACADE", "name": "Curtain Wall & Facade Test"},
        spatial_structure={
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 4.0},
            ]
        },
        grids={
            "axes_x": {"1": 0.0, "2": 8.0},
            "axes_y": {"A": 0.0, "B": 6.0},
        },
        materials=[
            {"id": "MAT_GLASS", "name": "Double Glazed Glass", "category": "GLASS", "unit_cost_ref": "MAT-GLASS"},
            {"id": "MAT_ALUM", "name": "Aluminum Framing", "category": "ALUMINUM", "unit_cost_ref": "MAT-ALUM"},
        ],
        elements=[
            IfcCurtainWall(
                tag="CW-FACADE-01",
                class_="IfcCurtainWall",
                material="MAT_GLASS",
                frame_material="MAT_ALUM",
                height=4.0,
                mullion_spacing_h=2.0,
                mullion_spacing_v=1.0,
                mullion_width=0.06,
                mullion_depth=0.15,
                glass_thickness=0.012,
                placement={
                    "from_grid": ["1", "A"],
                    "to_grid": ["2", "A"],
                    "storey": "L1",
                },
            ),
            IfcPlate(
                tag="PLATE-GLASS-01",
                class_="IfcPlate",
                predefined_type="CURTAIN_PANEL",
                material="MAT_GLASS",
                thickness=0.012,
                width=2.0,
                depth=1.0,
                density_kg_m3=2500.0,
                placement={
                    "storey": "L1",
                    "grid": ["1", "A"],
                    "offset_z": 1.0,
                },
            ),
            IfcPlate(
                tag="PLATE-STEEL-BASE",
                class_="IfcPlate",
                predefined_type="BASE_PLATE",
                material="MAT_ALUM",
                thickness=0.020,
                width=0.40,
                depth=0.40,
                density_kg_m3=7850.0,
                placement={
                    "storey": "L1",
                    "grid": ["2", "A"],
                },
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.curtain_walls) == 1
    assert len(resolved.plates) == 2

    cw = resolved.curtain_walls[0]
    assert cw.length == pytest.approx(8.0)
    assert cw.height == pytest.approx(4.0)
    assert cw.gross_facade_area == pytest.approx(32.0)  # 8m x 4m
    assert cw.glass_panels_count == 16  # (8/2) * (4/1) = 4 x 4 = 16 panels
    assert len(cw.mullion_grid_lines) > 0

    p_glass = resolved.plates[0]
    assert p_glass.area == pytest.approx(2.0)
    assert p_glass.weight == pytest.approx(2.0 * 0.012 * 2500.0)

    p_steel = resolved.plates[1]
    assert p_steel.weight == pytest.approx(0.40 * 0.40 * 0.020 * 7850.0)


def test_doors_windows_openings_and_submeshes():
    """Test parametric Door/Window frame & panel sub-mesh dual resolution and openings."""
    manifest = ProjectManifest(
        project={"id": "PROJ-OPENINGS", "name": "Doors & Windows Test"},
        spatial_structure={
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0},
            ]
        },
        grids={
            "axes_x": {"1": 0.0, "2": 5.0},
            "axes_y": {"A": 0.0, "B": 5.0},
        },
        materials=[
            {"id": "MAT_BRICK", "name": "Brick Wall", "category": "MASONRY", "unit_cost_ref": "MAT-BRICK"},
            {"id": "MAT_WOOD", "name": "Teak Wood", "category": "WOOD", "unit_cost_ref": "MAT-WOOD"},
            {"id": "MAT_GLASS", "name": "Glass", "category": "GLASS", "unit_cost_ref": "MAT-GLASS"},
        ],
        elements=[
            IfcWall(
                tag="WALL-01",
                class_="IfcWall",
                material="MAT_BRICK",
                thickness=0.20,
                height=3.0,
                placement={
                    "from_grid": ["1", "A"],
                    "to_grid": ["2", "A"],
                    "storey": "L1",
                },
                children=[
                    IfcDoor(
                        tag="DOOR-01",
                        class_="IfcDoor",
                        material="MAT_WOOD",
                        dimensions={"width": 0.90, "height": 2.10},
                        offset_distance=1.0,
                        sill_height=0.0,
                        frame_thickness=0.05,
                    ),
                    IfcWindow(
                        tag="WIN-01",
                        class_="IfcWindow",
                        material="MAT_GLASS",
                        dimensions={"width": 1.20, "height": 1.10},
                        offset_distance=3.0,
                        sill_height=0.90,
                        frame_thickness=0.05,
                    ),
                ],
            )
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.walls) == 1
    assert len(resolved.doors) == 1
    assert len(resolved.windows) == 1

    door = resolved.doors[0]
    assert door.width == 0.90
    assert door.height == 2.10
    assert "frame" in door.sub_meshes
    assert "panel" in door.sub_meshes
    assert door.sub_meshes["frame"]["width"] == 0.90
    assert door.sub_meshes["panel"]["width"] == pytest.approx(0.80)  # 0.90 - 2*0.05

    win = resolved.windows[0]
    assert win.width == 1.20
    assert win.height == 1.10
    assert win.sub_meshes["frame"]["height"] == 1.10
    assert win.sub_meshes["panel"]["height"] == pytest.approx(1.00)  # 1.10 - 2*0.05


def test_furnishing_interior_fixtures_and_layer_derivation():
    """Test interior furnishings, proxy classes, and layer routing."""
    assert derive_custom_ifc_class("interior/furniture/desks") == "IfcFurnishingElement"
    assert derive_custom_ifc_class("architecture/railings") == "IfcRailing"
    assert derive_custom_ifc_class("structure/framing/members") == "IfcMember"

    manifest = ProjectManifest(
        project={"id": "PROJ-FURN", "name": "Furnishing Test"},
        spatial_structure={
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0},
            ]
        },
        grids={
            "axes_x": {"1": 0.0, "2": 4.0},
            "axes_y": {"A": 0.0, "B": 4.0},
        },
        materials=[
            {"id": "MAT_WOOD", "name": "Wood", "category": "WOOD", "unit_cost_ref": "MAT-WOOD"},
        ],
        elements=[
            IfcCustomElement(
                tag="DESK-OFFICE-01",
                name="Executive Desk",
                source="procedural",
                dimensions=Dimensions(width=1.60, depth=0.80, height=0.75),
                placement={"storey": "L1", "position": [1.5, 1.5, 0.0], "rotation": [0.0, 0.0, 90.0]},
                layer="interior/furniture/desks",
            ),
            IfcCustomElement(
                tag="CABINET-FILE-01",
                name="Filing Cabinet",
                source="procedural",
                dimensions=Dimensions(width=0.90, depth=0.50, height=1.20),
                placement={"storey": "L1", "position": [3.0, 1.0, 0.0]},
                layer="interior/furniture/cabinets",
            ),
            IfcBuildingElementProxy(
                tag="PROXY-DECOR-01",
                ifc_class="IfcFurnishingElement",
                material="MAT_WOOD",
                placement={"storey": "L1", "grid": ["1", "A"], "offset_x": 0.5, "offset_y": 0.5},
                dimensions=Dimensions(width=0.40, depth=0.40, height=1.50),
                properties={
                    "Pset_FurnitureType": {
                        "Manufacturer": "BIM Studio",
                        "ModelNumber": "DEC-101",
                    }
                },
            ),
        ],
    )

    resolved = resolve_manifest(manifest)
    assert len(resolved.custom_elements) == 2
    assert len(resolved.proxies) == 1

    desk = resolved.custom_elements[0]
    assert desk.dimensions.width == 1.60
    assert desk.dimensions.depth == 0.80
    assert desk.rotation == (0.0, 0.0, 90.0)

    proxy = resolved.proxies[0]
    assert proxy.ifc_class == "IfcFurnishingElement"
    assert "Pset_FurnitureType" in proxy.properties


def test_compiler_3d_solid_step_export(tmp_path):
    """Test compiling architectural components to 3D solid STEP physical format."""
    manifest = ProjectManifest(
        project={"id": "PROJ-COMP", "name": "Compiler Solid Test"},
        spatial_structure={
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0},
            ]
        },
        grids={
            "axes_x": {"1": 0.0, "2": 6.0},
            "axes_y": {"A": 0.0, "B": 6.0},
        },
        materials=[
            {"id": "MAT_GYP", "name": "Gypsum", "category": "FINISH", "unit_cost_ref": "MAT-GYP"},
            {"id": "MAT_GLASS", "name": "Glass", "category": "GLASS", "unit_cost_ref": "MAT-GLASS"},
        ],
        elements=[
            IfcCovering(
                tag="COV-01",
                class_="IfcCovering",
                covering_type="CEILING",
                material="MAT_GYP",
                thickness=0.01,
                placement={"boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]], "storey": "L1", "offset_z": 2.7},
            ),
            IfcCurtainWall(
                tag="CW-01",
                class_="IfcCurtainWall",
                material="MAT_GLASS",
                height=3.0,
                placement={"from_grid": ["1", "A"], "to_grid": ["2", "A"], "storey": "L1"},
            ),
            IfcPlate(
                tag="PLATE-01",
                class_="IfcPlate",
                material="MAT_GLASS",
                thickness=0.01,
                width=1.0,
                depth=1.0,
                placement={"storey": "L1", "grid": ["1", "A"]},
            ),
        ],
    )

    resolved = resolve_manifest(manifest)

    # Test StepSerializer fallback
    serializer = StepSerializer("Compiler Solid Test")
    step_str = serializer.serialize(resolved)

    assert "IFCCOVERING" in step_str
    assert "IFCCURTAINWALL" in step_str
    assert "IFCPLATE" in step_str
    assert "IFCEXTRUDEDAREASOLID" in step_str

    # Test full file compilation
    out_file = tmp_path / "model.ifc"
    compiled_path = compile_to_ifc(resolved, output_path=out_file, force_fallback=True)
    assert compiled_path.exists()
    assert compiled_path.stat().st_size > 0


def test_viewer_html_generation_for_arch_components():
    """Test 3D Viewer HTML generation containing all architectural finishes and envelope systems."""
    manifest = ProjectManifest(
        project={"id": "PROJ-VIEWER", "name": "Viewer Test"},
        spatial_structure={
            "storeys": [
                {"id": "L1", "name": "Level 1", "elevation": 0.0, "height": 3.0},
            ]
        },
        grids={
            "axes_x": {"1": 0.0, "2": 5.0},
            "axes_y": {"A": 0.0, "B": 5.0},
        },
        materials=[
            {"id": "MAT_TILES", "name": "Tiles", "category": "FINISH", "unit_cost_ref": "MAT-TILE"},
        ],
        elements=[
            IfcCovering(
                tag="COV-SKIRT-01",
                class_="IfcCovering",
                covering_type="SKIRTING",
                material="MAT_TILES",
                thickness=0.012,
                placement={"boundary": [["1", "A"], ["2", "A"], ["2", "B"], ["1", "B"]], "storey": "L1"},
            ),
        ],
    )

    html = generate_viewer_html(manifest)
    assert "COV-SKIRT-01" in html
    assert "IfcCovering" in html
    assert "Skirting" in html
    assert "THREE.WebGLRenderer" in html
