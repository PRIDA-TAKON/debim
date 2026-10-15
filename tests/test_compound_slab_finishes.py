"""Unit tests for compound slab space finishes decoupled from structural RC slab

and QTO takeoff accounting for sunken bathroom drops and distinct room flooring.
"""

from pathlib import Path
import pytest

from debim.schema import (
    ProjectManifest,
    ProjectInfo,
    SpatialStructure,
    Storey,
    Grids,
    Material,
    IfcSlab,
    SlabPlacement,
    IfcSpace,
    SpacePlacement,
)
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.compiler import compile_to_ifc


@pytest.fixture
def compound_slab_manifest() -> ProjectManifest:
    """Fixture providing a project manifest with continuous RC slab and distinct space floor finishes."""
    axes_x = {"1": 0.00, "2": 5.00, "3": 10.00}
    axes_y = {"A": 0.00, "B": 4.00, "C": 8.00}

    # Continuous structural RC slab covering entire 10m x 8m floor plan
    slab = IfcSlab(
        tag="SLAB-ST-01",
        material="CONCRETE_C25",
        thickness=0.15,
        placement=SlabPlacement(
            storey="ST-01",
            boundary=[("1", "A"), ("3", "A"), ("3", "C"), ("1", "C")],
        ),
    )

    # Room spaces with distinct floor finish materials, thicknesses, and sunken slab drop
    living_room = IfcSpace(
        tag="SPACE-LIVING",
        name="Living Room",
        room_number="101",
        height=2.80,
        floor_material="GRANITO_TILES",
        floor_thickness=0.02,
        drop_elevation=0.00,
        placement=SpacePlacement(
            storey="ST-01",
            boundary=[("1", "A"), ("2", "A"), ("2", "C"), ("1", "C")],  # 5m x 8m = 40m2
        ),
    )

    bedroom = IfcSpace(
        tag="SPACE-BEDROOM",
        name="Master Bedroom",
        room_number="102",
        height=2.80,
        floor_material="PARQUET_WOOD",
        floor_thickness=0.015,
        drop_elevation=0.00,
        placement=SpacePlacement(
            storey="ST-01",
            boundary=[("2", "A"), ("3", "A"), ("3", "B"), ("2", "B")],  # 5m x 4m = 20m2
        ),
    )

    bathroom = IfcSpace(
        tag="SPACE-BATHROOM",
        name="Sunken Bathroom",
        room_number="103",
        height=2.80,
        floor_material="CERAMIC_TILES",
        floor_thickness=0.015,
        drop_elevation=-0.10,  # Sunken slab depression -0.10m
        placement=SpacePlacement(
            storey="ST-01",
            boundary=[("2", "B"), ("3", "B"), ("3", "C"), ("2", "C")],  # 5m x 4m = 20m2
        ),
    )

    return ProjectManifest(
        project=ProjectInfo(id="PRJ-SLAB-FINISH", name="Compound Slab Finishes Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="ST-01", name="First Floor", elevation=0.0, height=3.2),
            ]
        ),
        grids=Grids(axes_x=axes_x, axes_y=axes_y),
        materials=[
            Material(id="CONCRETE_C25", name="Reinforced Concrete C25/30", category="concrete", unit_cost_ref="MAT-C25"),
            Material(id="GRANITO_TILES", name="Granito Tile 60x60", category="finishes", unit_cost_ref="MAT-TILE"),
            Material(id="PARQUET_WOOD", name="Teak Wood Parquet", category="finishes", unit_cost_ref="MAT-WOOD"),
            Material(id="CERAMIC_TILES", name="Non-slip Ceramic Tiles", category="finishes", unit_cost_ref="MAT-TILE"),
        ],
        elements=[slab, living_room, bedroom, bathroom],
    )


def test_space_finish_resolution_and_decoupling(compound_slab_manifest):
    """Test space finish resolution and separation from continuous structural slab."""
    resolved = resolve_manifest(compound_slab_manifest)

    assert len(resolved.slabs) == 1
    assert len(resolved.spaces) == 3

    # Structural slab resolution
    res_slab = resolved.slabs[0]
    assert res_slab.tag == "SLAB-ST-01"
    assert res_slab.thickness == 0.15
    assert pytest.approx(res_slab.area, abs=1e-3) == 80.0  # 10m x 8m

    # Spaces resolution
    spaces_by_tag = {s.tag: s for s in resolved.spaces}

    living = spaces_by_tag["SPACE-LIVING"]
    assert living.floor_material == "GRANITO_TILES"
    assert living.floor_thickness == 0.02
    assert living.drop_elevation == 0.00
    assert pytest.approx(living.net_floor_area, abs=1e-3) == 40.0
    assert pytest.approx(living.floor_finish_volume, abs=1e-3) == 40.0 * 0.02

    bedroom = spaces_by_tag["SPACE-BEDROOM"]
    assert bedroom.floor_material == "PARQUET_WOOD"
    assert bedroom.floor_thickness == 0.015
    assert bedroom.drop_elevation == 0.00
    assert pytest.approx(bedroom.net_floor_area, abs=1e-3) == 20.0

    bathroom = spaces_by_tag["SPACE-BATHROOM"]
    assert bathroom.floor_material == "CERAMIC_TILES"
    assert bathroom.floor_thickness == 0.015
    assert bathroom.drop_elevation == -0.10
    assert pytest.approx(bathroom.net_floor_area, abs=1e-3) == 20.0
    assert pytest.approx(bathroom.floor_finish_volume, abs=1e-3) == 20.0 * 0.015


def test_compound_slab_qto_reporting(compound_slab_manifest):
    """Test separate reporting of structural concrete and architectural floor finishes in QTO."""
    qto = calculate_qto(compound_slab_manifest)

    # Continuous structural slab concrete volume: 10m x 8m x 0.15m = 12.0 m3
    slab_qto = qto.get_element("SLAB-ST-01")
    assert slab_qto is not None
    assert pytest.approx(slab_qto.concrete_volume, abs=1e-3) == 12.0

    # Total project structural concrete volume
    assert pytest.approx(qto.total_concrete_volume, abs=1e-3) == 12.0

    # Separate space floor finish QTO
    bath_qto = qto.get_element("SPACE-BATHROOM")
    assert bath_qto is not None
    assert bath_qto.space is not None
    assert bath_qto.space.floor_material == "CERAMIC_TILES"
    assert bath_qto.space.drop_elevation == -0.10
    assert pytest.approx(bath_qto.space.floor_finish_area, abs=1e-3) == 20.0

    # Total room floor finish area & volume in ProjectQTO
    assert pytest.approx(qto.total_usable_floor_area, abs=1e-3) == 80.0  # 40 + 20 + 20
    assert pytest.approx(qto.total_floor_finish_area, abs=1e-3) == 80.0
    expected_finish_vol = (40.0 * 0.02) + (20.0 * 0.015) + (20.0 * 0.015)
    assert pytest.approx(qto.total_floor_finish_volume, abs=1e-3) == expected_finish_vol


def test_compound_slab_ifc_export(compound_slab_manifest, tmp_path: Path):
    """Test IFC file compilation containing structural slab and spaces."""
    out_ifc = tmp_path / "compound_slab.ifc"
    compile_to_ifc(compound_slab_manifest, out_ifc)

    assert out_ifc.exists()
    assert out_ifc.stat().st_size > 1000

    content = out_ifc.read_text(encoding="utf-8")
    assert "IFCSLAB" in content or "IfcSlab" in content
    assert "IFCSPACE" in content or "IfcSpace" in content
