"""
Unit tests for debim IfcRoof (Roof Structure & Covering).
Validates schema, 3D coordinate resolution, QTO engine, cost estimation,
IFC compilation, and 3D web viewer generation.
"""

import math
from pathlib import Path
import pytest
from pydantic import ValidationError

from debim.schema import (
    Grids,
    IfcRoof,
    Material,
    ProjectInfo,
    ProjectManifest,
    RoofCoveringConfig,
    RoofFramingConfig,
    RoofPlacement,
    SpatialStructure,
    Storey,
    load_manifest,
)
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.cost import PriceCatalog, PriceItem, estimate_cost
from debim.compiler import compile_to_ifc
from debim.viewer import generate_viewer_html


@pytest.fixture
def sample_roof_manifest() -> ProjectManifest:
    """Fixture providing a minimal project manifest with a hip roof."""
    return ProjectManifest(
        project=ProjectInfo(id="PRJ-ROOF-TEST", name="Roof Test Pavilion"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Ground Level", elevation=0.0, height=3.0),
                Storey(id="L2_ROOF", name="Roof Level", elevation=3.0, height=1.5),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 8.0},
            axes_y={"A": 0.0, "B": 6.0},
        ),
        materials=[
            Material(
                id="STEEL_SS400",
                name="Structural Steel SS400",
                category="steel",
                unit_cost_ref="MAT-STEEL-01",
            ),
            Material(
                id="ROOF_TILE",
                name="Concrete Roof Tile",
                category="covering",
                unit_cost_ref="MAT-ROOF-TILE",
            ),
        ],
        elements=[
            IfcRoof(
                tag="ROOF-01",
                material="STEEL_SS400",
                roof_type="HIP",
                placement=RoofPlacement(
                    boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")],
                    storey="L2_ROOF",
                    offset_z=0.0,
                    overhang=1.0,  # 1.0m eave overhang
                    ridge_orientation="X",
                ),
                covering=RoofCoveringConfig(
                    tile_type="CONCRETE_TILE",
                    pitch=30.0,  # 30 degrees
                    insulation=True,
                    fascia_board=True,
                    ridge_cap=True,
                ),
                framing=RoofFramingConfig(
                    truss_type="STEEL_TRUSS",
                    material="STEEL_SS400",
                    spacing=1.0,
                    purlin_spacing=0.32,
                    steel_weight_per_sqm=18.0,
                ),
            )
        ],
    )


def test_roof_schema_validation(sample_roof_manifest):
    """Test schema validation for IfcRoof."""
    assert len(sample_roof_manifest.elements) == 1
    roof = sample_roof_manifest.elements[0]
    assert isinstance(roof, IfcRoof)
    assert roof.tag == "ROOF-01"
    assert roof.roof_type == "HIP"
    assert roof.placement.overhang == 1.0
    assert roof.covering.pitch == 30.0
    assert roof.framing.steel_weight_per_sqm == 18.0


def test_roof_schema_invalid_storey_or_grid():
    """Test that referencing invalid storeys or grids raises ValidationError."""
    with pytest.raises(ValidationError):
        ProjectManifest(
            project=ProjectInfo(id="PRJ-FAIL", name="Fail Project"),
            spatial_structure=SpatialStructure(
                storeys=[Storey(id="L1", name="Ground", elevation=0.0, height=3.0)]
            ),
            grids=Grids(axes_x={"1": 0.0}, axes_y={"A": 0.0}),
            materials=[
                Material(
                    id="STEEL_SS400",
                    name="Steel",
                    category="steel",
                    unit_cost_ref="MAT-STEEL-01",
                )
            ],
            elements=[
                IfcRoof(
                    tag="ROOF-BAD",
                    material="STEEL_SS400",
                    roof_type="HIP",
                    placement=RoofPlacement(
                        boundary=[("1", "A"), ("99", "A")],  # "99" does not exist
                        storey="L1",
                    ),
                )
            ],
        )


def test_roof_resolution_hip(sample_roof_manifest):
    """Test 3D coordinate resolution of Hip roof."""
    resolved = resolve_manifest(sample_roof_manifest)
    assert len(resolved.roofs) == 1
    r_roof = resolved.roofs[0]

    # Grid boundary is 0 to 8 in X, 0 to 6 in Y
    # Overhang is 1.0m, so eaves footprint is:
    # X: -1.0 to 9.0 (width = 10.0m)
    # Y: -1.0 to 7.0 (length = 8.0m)
    # Footprint area = 10.0 * 8.0 = 80.0 m2
    assert math.isclose(r_roof.total_footprint_area, 80.0, rel_tol=1e-3)

    # Eaves perimeter = 2 * (10 + 8) = 36.0m
    assert math.isclose(r_roof.total_eaves_length, 36.0, rel_tol=1e-3)

    # Sloped roof covering area = Footprint Area / cos(30 deg)
    expected_sloped_area = 80.0 / math.cos(math.radians(30.0))
    assert math.isclose(r_roof.total_sloped_area, expected_sloped_area, rel_tol=1e-2)

    # 4 sloped facet planes (2 triangular hips + 2 trapezoidal slopes)
    assert len(r_roof.planes) == 4
    for plane in r_roof.planes:
        assert plane.area > 0.0
        assert plane.slope_degrees == 30.0

    # Ridge line: since length (Y) is 8m, half-span is 4.0m
    # Width (X) is 10m. Ridge runs along X from x = (-1 + 4) = 3.0 to x = (9 - 4) = 5.0
    # Ridge length = 2.0m
    assert math.isclose(r_roof.total_ridge_length, 2.0, rel_tol=1e-2)

    # 4 Hips: each hip goes from corner to ridge end
    # dx = 4.0, dy = 4.0, dz = 4.0 * tan(30) = 2.3094
    # hip_len = sqrt(16 + 16 + 5.3333) = sqrt(37.333) = 6.110m
    # 4 hips total = 24.44m
    assert r_roof.total_hip_length > 20.0

    # Steel weight = 80.0 m2 * 18.0 kg/m2 = 1440.0 kg
    # Framing members verification (อะเส, อกไก่, ตะเข้สัน, เสาดั้ง, ขื่อ, จันทัน, แป)
    assert len(r_roof.framing_members) > 0
    m_types = {m.member_type for m in r_roof.framing_members}
    assert "WALL_PLATE" in m_types
    assert "RIDGE_BEAM" in m_types
    assert "HIP_RAFTER" in m_types
    assert "KING_POST" in m_types
    assert "TIE_BEAM" in m_types
    assert "PURLIN" in m_types
    assert any(m in m_types for m in ("COMMON_RAFTER", "JACK_RAFTER"))

    # Colors and Thai names exist
    for m in r_roof.framing_members:
        assert m.color.startswith("#")
        assert len(m.name_th) > 0
        assert m.length > 0.0


def test_roof_resolution_gable():
    """Test 3D coordinate resolution of Gable roof."""
    manifest = ProjectManifest(
        project=ProjectInfo(id="PRJ-GABLE", name="Gable Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="L1", name="Ground", elevation=0.0, height=3.0)]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 6.0}, axes_y={"A": 0.0, "B": 4.0}),
        materials=[Material(id="STEEL", name="Steel", category="steel", unit_cost_ref="MAT-STEEL")],
        elements=[
            IfcRoof(
                tag="ROOF-GABLE",
                material="STEEL",
                roof_type="GABLE",
                placement=RoofPlacement(
                    boundary=[("1", "A"), ("2", "A"), ("2", "B"), ("1", "B")],
                    storey="L1",
                    overhang=0.5,
                    ridge_orientation="X",
                ),
                covering=RoofCoveringConfig(pitch=25.0),
            )
        ],
    )
    resolved = resolve_manifest(manifest)
    r_roof = resolved.roofs[0]

    # X: -0.5 to 6.5 (width = 7.0m)
    # Y: -0.5 to 4.5 (length = 5.0m)
    # Footprint = 35.0 m2
    assert math.isclose(r_roof.total_footprint_area, 35.0, rel_tol=1e-3)
    # 2 planes for gable
    assert len(r_roof.planes) == 2
    # Ridge along X: length = width = 7.0m
    assert math.isclose(r_roof.total_ridge_length, 7.0, rel_tol=1e-3)
    # 0 hips for gable
    assert r_roof.total_hip_length == 0.0


def test_roof_qto_and_cost(sample_roof_manifest):
    """Test Quantitative Take-Off and Cost estimation matching for Roof."""
    resolved = resolve_manifest(sample_roof_manifest)
    qto = calculate_qto(resolved)

    assert qto.total_roof_covering_area > 90.0  # ~92.38 m2
    assert qto.total_roof_steel_weight == 1440.0
    assert qto.total_roof_ridge_length == 2.0
    assert qto.total_roof_hip_length > 20.0
    assert qto.total_roof_eaves_length == 36.0
    assert qto.total_roof_insulation_area == qto.total_roof_covering_area

    # Price catalog with roof items
    catalog = PriceCatalog(
        currency="THB",
        items={
            "MAT-STEEL-01": PriceItem(
                name="Structural Steel SS400",
                unit="kg",
                material_cost=32.0,
                labor_cost=8.0,
            ),
            "MAT-ROOF-TILE": PriceItem(
                name="Concrete Roof Tile",
                unit="m2",
                material_cost=250.0,
                labor_cost=70.0,
            ),
            "MAT-ROOF-RIDGE": PriceItem(
                name="Ridge & Hip Cap Tile",
                unit="m",
                material_cost=120.0,
                labor_cost=40.0,
            ),
            "MAT-FASCIA": PriceItem(
                name="Fascia Board (ไม้เชิงชาย)",
                unit="m",
                material_cost=95.0,
                labor_cost=35.0,
            ),
            "MAT-ROOF-INSUL": PriceItem(
                name="Aluminium Foil Roof Insulation",
                unit="m2",
                material_cost=45.0,
                labor_cost=15.0,
            ),
        },
    )

    cost_est = estimate_cost(qto, catalog, sample_roof_manifest)
    assert cost_est.grand_total > 0
    # Line items should contain steel, tiles, ridge caps, fascia, insulation
    codes = [item.code for item in cost_est.line_items]
    assert "MAT-STEEL-01" in codes
    assert "MAT-ROOF-TILE" in codes
    assert "MAT-ROOF-RIDGE" in codes
    assert "MAT-FASCIA" in codes
    assert "MAT-ROOF-INSUL" in codes


def test_roof_ifc_compilation(sample_roof_manifest, tmp_path):
    """Test compiling manifest with IfcRoof to IFC4 file."""
    out_ifc = tmp_path / "roof_test.ifc"
    compile_to_ifc(sample_roof_manifest, out_ifc)
    assert out_ifc.exists()
    content = out_ifc.read_text(encoding="utf-8")
    assert "IFCROOF" in content.upper()


def test_roof_viewer_generation(sample_roof_manifest):
    """Test generating 3D viewer HTML with IfcRoof."""
    html = generate_viewer_html(sample_roof_manifest)
    assert "IfcRoofCovering" in html
    assert "IfcRoofFraming" in html
    assert "polygon" in html
    assert "architecture/roofs/covering" in html
    assert "architecture/roofs/framing" in html
