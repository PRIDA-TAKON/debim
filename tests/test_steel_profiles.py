"""
Unit tests for Standard Structural Steel Profiles:
- IfcIShapeProfileDef (H-Beam / I-Beam / Wide Flange)
- IfcLShapeProfileDef (Equal / Unequal Angle)
- IfcUShapeProfileDef (C-Channel / U-Shape)
- IfcTShapeProfileDef (Tee Shape)
- IfcRectangleHollowProfileDef (RHS / SHS / Box Hollow)
- IfcCircleHollowProfileDef (CHS / Circular Hollow / Pipe)

Verifies schema parsing, section string extraction, QTO formulas, IFC compilation, and 3D viewer.
"""

import math
from pathlib import Path
import pytest
from pydantic import ValidationError

from debim.compiler import compile_to_ifc
from debim.qto import calculate_element_qto, calculate_qto, compute_profile_geometry
from debim.resolver import resolve_manifest
from debim.schema import (
    BeamPlacement,
    CircleHollowProfile,
    ColumnPlacement,
    Grids,
    IShapeProfile,
    IfcBeam,
    IfcColumn,
    LShapeProfile,
    Material,
    ProjectInfo,
    ProjectManifest,
    RectangleHollowProfile,
    SpatialStructure,
    Storey,
    TShapeProfile,
    UShapeProfile,
    load_manifest,
)
from debim.viewer import generate_viewer_html


def test_ishape_profile_validation():
    # 1. Explicit dimensions
    p1 = IShapeProfile(
        overall_depth=0.200,
        overall_width=0.200,
        web_thickness=0.008,
        flange_thickness=0.012,
    )
    assert p1.shape == "ISHAPE"
    assert p1.width == 0.200
    assert p1.depth == 0.200

    # 2. Section string parsing (TIS / JIS H-Beam)
    p2 = IShapeProfile(section="H200X200X8X12")
    assert pytest.approx(p2.overall_depth) == 0.200
    assert pytest.approx(p2.overall_width) == 0.200
    assert pytest.approx(p2.web_thickness) == 0.008
    assert pytest.approx(p2.flange_thickness) == 0.012
    assert p2.width == 0.200
    assert p2.depth == 0.200

    # 3. Missing dimensions without section raises ValidationError
    with pytest.raises(ValidationError):
        IShapeProfile()


def test_lshape_profile_validation():
    # 1. Explicit equal angle
    p1 = LShapeProfile(depth=0.050, thickness=0.005)
    assert p1.shape == "LSHAPE"
    assert p1.depth == 0.050
    assert p1.width == 0.050  # Default to depth
    assert p1.thickness == 0.005

    # 2. Section string parsing
    p2 = LShapeProfile(section="L50X50X5")
    assert pytest.approx(p2.depth) == 0.050
    assert pytest.approx(p2.width) == 0.050
    assert pytest.approx(p2.thickness) == 0.005

    # 3. Unequal angle
    p3 = LShapeProfile(section="L100X75X8")
    assert pytest.approx(p3.depth) == 0.100
    assert pytest.approx(p3.width) == 0.075
    assert pytest.approx(p3.thickness) == 0.008


def test_ushape_profile_validation():
    # 1. Explicit dimensions
    p1 = UShapeProfile(
        depth=0.150,
        flange_width=0.075,
        web_thickness=0.0065,
        flange_thickness=0.010,
    )
    assert p1.shape == "USHAPE"
    assert p1.depth == 0.150
    assert p1.width == 0.075

    # 2. Section string parsing (TIS C-Channel)
    p2 = UShapeProfile(section="C150X75X6.5X10")
    assert pytest.approx(p2.depth) == 0.150
    assert pytest.approx(p2.flange_width) == 0.075
    assert pytest.approx(p2.web_thickness) == 0.0065
    assert pytest.approx(p2.flange_thickness) == 0.010


def test_tshape_profile_validation():
    p1 = TShapeProfile(
        depth=0.150,
        flange_width=0.150,
        web_thickness=0.006,
        flange_thickness=0.009,
    )
    assert p1.shape == "TSHAPE"
    assert p1.depth == 0.150
    assert p1.width == 0.150

    p2 = TShapeProfile(section="T150X150X6X9")
    assert pytest.approx(p2.depth) == 0.150
    assert pytest.approx(p2.flange_width) == 0.150


def test_hollow_profiles_validation():
    # RHS (Rectangular Hollow Section)
    rhs = RectangleHollowProfile(section="RHS100X50X3.2")
    assert pytest.approx(rhs.depth) == 0.100
    assert pytest.approx(rhs.width) == 0.050
    assert pytest.approx(rhs.wall_thickness) == 0.0032

    # CHS (Circular Hollow Section)
    chs = CircleHollowProfile(section="CHS114.3X4.5")
    assert pytest.approx(chs.diameter) == 0.1143
    assert pytest.approx(chs.radius) == 0.05715
    assert pytest.approx(chs.wall_thickness) == 0.0045


def test_compute_profile_geometry_formulas():
    # 1. I-Shape: H200x200x8x12
    # Area = 2 * (0.200 * 0.012) + (0.200 - 2 * 0.012) * 0.008 = 0.0048 + 0.001408 = 0.006208 m2
    ishape = IShapeProfile(section="H200X200X8X12")
    area, perim, w, d = compute_profile_geometry(ishape)
    assert area == pytest.approx(0.006208)
    assert w == 0.200
    assert d == 0.200
    # Perimeter = 4*b + 2*h - 2*tw = 4*0.2 + 2*0.2 - 2*0.008 = 0.8 + 0.4 - 0.016 = 1.184 m
    assert perim == pytest.approx(1.184)

    # 2. L-Shape: L50x50x5
    # Area = (0.05 + 0.05 - 0.005) * 0.005 = 0.000475 m2
    lshape = LShapeProfile(section="L50X50X5")
    area_l, perim_l, w_l, d_l = compute_profile_geometry(lshape)
    assert area_l == pytest.approx(0.000475)
    assert perim_l == pytest.approx(2.0 * (0.05 + 0.05))

    # 3. RHS: 100x50x3.2
    # Area = 0.10*0.05 - (0.10 - 2*0.0032)*(0.05 - 2*0.0032)
    rhs = RectangleHollowProfile(section="RHS100X50X3.2")
    area_rhs, perim_rhs, w_rhs, d_rhs = compute_profile_geometry(rhs)
    expected_inner = (0.10 - 0.0064) * (0.05 - 0.0064)
    expected_area = (0.10 * 0.05) - expected_inner
    assert area_rhs == pytest.approx(expected_area)
    assert perim_rhs == pytest.approx(2.0 * (0.10 + 0.05))


def test_steel_elements_qto():
    manifest = ProjectManifest(
        project=ProjectInfo(id="PRJ-STEEL", name="Steel Test"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Level 1", elevation=0.0, height=3.5),
                Storey(id="L2", name="Level 2", elevation=3.5, height=3.5),
            ]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 6.0}, axes_y={"A": 0.0, "B": 6.0}),
        materials=[
            Material(id="MAT_STEEL", name="Structural Steel SS400", category="steel", unit_cost_ref="REF-STEEL")
        ],
        elements=[
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "COL-H1",
                    "material": "MAT_STEEL",
                    "profile": IShapeProfile(section="H200X200X8X12"),
                    "placement": ColumnPlacement(grid=("1", "A"), base_storey="L1", top_storey="L2"),
                }
            ),
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": "BM-C1",
                    "material": "MAT_STEEL",
                    "profile": UShapeProfile(section="C150X75X6.5X10"),
                    "placement": BeamPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L2"),
                }
            ),
        ],
    )

    qto = calculate_qto(manifest)

    # COL-H1: height = 3.5m, standard mass from table = 49.9 kg/m -> 3.5 * 49.9 = 174.65 kg
    col_qto = qto.get_element("COL-H1")
    assert col_qto is not None
    assert col_qto.concrete_volume == 0.0
    assert col_qto.formwork_area == 0.0
    assert col_qto.structural_steel_weight == pytest.approx(3.5 * 49.9)
    assert col_qto.painting_area > 0.0
    assert col_qto.weld_touchup_area > 0.0

    # BM-C1: span = 6.0m, standard mass from table = 18.6 kg/m -> 6.0 * 18.6 = 111.6 kg
    bm_qto = qto.get_element("BM-C1")
    assert bm_qto is not None
    assert bm_qto.concrete_volume == 0.0
    assert bm_qto.formwork_area == 0.0
    assert bm_qto.structural_steel_weight == pytest.approx(6.0 * 18.6)

    assert qto.total_structural_steel_weight == pytest.approx(174.65 + 111.6)


def test_steel_profile_ifc_compilation(tmp_path: Path):
    manifest = ProjectManifest(
        project=ProjectInfo(id="PRJ-STEEL-IFC", name="Steel IFC"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Level 1", elevation=0.0, height=3.0),
                Storey(id="L2", name="Level 2", elevation=3.0, height=3.0),
            ]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 4.0}, axes_y={"A": 0.0, "B": 4.0}),
        materials=[
            Material(id="MAT_STEEL", name="Steel", category="steel", unit_cost_ref="REF-STEEL")
        ],
        elements=[
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "COL-H1",
                    "material": "MAT_STEEL",
                    "profile": IShapeProfile(section="H200X200X8X12"),
                    "placement": ColumnPlacement(grid=("1", "A"), base_storey="L1", top_storey="L2"),
                }
            ),
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": "BM-C1",
                    "material": "MAT_STEEL",
                    "profile": UShapeProfile(section="C150X75X6.5X10"),
                    "placement": BeamPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L2"),
                }
            ),
        ],
    )

    out_file = tmp_path / "model.ifc"
    res_path = compile_to_ifc(manifest, out_file)
    assert res_path.exists()

    content = res_path.read_text(encoding="utf-8")
    assert "IFCISHAPEPROFILEDEF" in content
    assert "IFCUSHAPEPROFILEDEF" in content


def test_steel_profile_viewer_payload():
    manifest = ProjectManifest(
        project=ProjectInfo(id="PRJ-STEEL-VIEWER", name="Steel Viewer"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Level 1", elevation=0.0, height=3.0),
                Storey(id="L2", name="Level 2", elevation=3.0, height=3.0),
            ]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 5.0}, axes_y={"A": 0.0}),
        materials=[
            Material(id="MAT_STEEL", name="Steel", category="steel", unit_cost_ref="REF-STEEL")
        ],
        elements=[
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "COL-H1",
                    "material": "MAT_STEEL",
                    "profile": IShapeProfile(section="H200X200X8X12"),
                    "placement": ColumnPlacement(grid=("1", "A"), base_storey="L1", top_storey="L2"),
                }
            ),
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": "BM-L1",
                    "material": "MAT_STEEL",
                    "profile": LShapeProfile(section="L50X50X5"),
                    "placement": BeamPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L2"),
                }
            ),
        ],
    )

    html = generate_viewer_html(manifest)
    assert "ISHAPE" in html
    assert "LSHAPE" in html
    assert "ExtrudeGeometry" in html
