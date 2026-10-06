"""
Unit tests for Circular and Elliptical profiles (IfcCircleProfileDef, IfcEllipseProfileDef).
Verifies schema parsing, QTO volume/formwork formulas, 3D viewer payload, and IFC export.
"""

import math
from pathlib import Path
import pytest
from pydantic import ValidationError

from debim.compiler import compile_to_ifc
from debim.qto import calculate_element_qto, calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    BoxProfile,
    CircularProfile,
    ColumnPlacement,
    BeamPlacement,
    ColumnReinforcement,
    EllipseProfile,
    Grids,
    IfcBeam,
    IfcColumn,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def test_circular_profile_schema_validation():
    # Test via radius
    cp1 = CircularProfile(radius=0.20)
    assert cp1.shape == "CIRCULAR"
    assert pytest.approx(cp1.radius) == 0.20
    assert pytest.approx(cp1.diameter) == 0.40

    # Test via diameter
    cp2 = CircularProfile(diameter=0.60)
    assert cp2.shape == "CIRCULAR"
    assert pytest.approx(cp2.radius) == 0.30
    assert pytest.approx(cp2.diameter) == 0.60

    # Test missing both radius and diameter
    with pytest.raises(ValidationError):
        CircularProfile()


def test_ellipse_profile_schema_validation():
    # Test via semi axes
    ep1 = EllipseProfile(semi_major_axis=0.30, semi_minor_axis=0.15)
    assert ep1.shape == "ELLIPSE"
    assert pytest.approx(ep1.semi_major_axis) == 0.30
    assert pytest.approx(ep1.semi_minor_axis) == 0.15
    assert pytest.approx(ep1.major_diameter) == 0.60
    assert pytest.approx(ep1.minor_diameter) == 0.30

    # Test via major and minor diameters
    ep2 = EllipseProfile(major_diameter=0.80, minor_diameter=0.40)
    assert ep2.shape == "ELLIPSE"
    assert pytest.approx(ep2.semi_major_axis) == 0.40
    assert pytest.approx(ep2.semi_minor_axis) == 0.20
    assert pytest.approx(ep2.major_diameter) == 0.80
    assert pytest.approx(ep2.minor_diameter) == 0.40

    # Test missing minor axis
    with pytest.raises(ValidationError):
        EllipseProfile(semi_major_axis=0.30)


def create_curved_profile_manifest() -> ProjectManifest:
    return ProjectManifest(
        project=ProjectInfo(id="P_CURVED", name="Curved Profiles Test Project"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Ground Floor", elevation=0.0, height=3.5),
                Storey(id="L2", name="Second Floor", elevation=3.5, height=3.5),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 6.0, "3": 12.0},
            axes_y={"A": 0.0, "B": 6.0, "C": 12.0},
        ),
        materials=[
            Material(
                id="CONC_280",
                name="Concrete 280 ksc",
                category="concrete",
                unit_cost_ref="REF_CONC",
            ),
            Material(
                id="STEEL_SS400",
                name="Structural Steel SS400",
                category="steel",
                unit_cost_ref="REF_STEEL",
            ),
        ],
        elements=[
            # 1. Circular Concrete Column (Radius 0.25m -> Diameter 0.50m, Height 3.5m)
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "COL-CIRCULAR-01",
                    "material": "CONC_280",
                    "profile": CircularProfile(diameter=0.50),
                    "placement": ColumnPlacement(grid=("1", "A"), base_storey="L1", top_storey="L2"),
                    "reinforcement": ColumnReinforcement(main="6-DB16", stirrups="RB6 @ 0.15m"),
                }
            ),
            # 2. Elliptical Concrete Column (a=0.30m, b=0.15m, Height 3.5m)
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "COL-ELLIPSE-01",
                    "material": "CONC_280",
                    "profile": EllipseProfile(semi_major_axis=0.30, semi_minor_axis=0.15),
                    "placement": ColumnPlacement(grid=("2", "A"), base_storey="L1", top_storey="L2"),
                    "reinforcement": ColumnReinforcement(main="8-DB16", stirrups="RB6 @ 0.15m"),
                }
            ),
            # 3. Circular Concrete Beam (Radius 0.20m, Length 6.0m)
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": "BM-CIRCULAR-01",
                    "material": "CONC_280",
                    "profile": CircularProfile(radius=0.20),
                    "placement": BeamPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L1"),
                }
            ),
            # 4. Elliptical Steel Bridge Pylon Beam (a=0.40m, b=0.20m, Length 6.0m)
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": "BM-ELLIPSE-STEEL-01",
                    "material": "STEEL_SS400",
                    "profile": EllipseProfile(major_diameter=0.80, minor_diameter=0.40),
                    "placement": BeamPlacement(from_grid=("2", "A"), to_grid=("3", "A"), storey="L1"),
                }
            ),
        ],
    )


def test_curved_profiles_qto_calculations():
    manifest = create_curved_profile_manifest()
    resolved = resolve_manifest(manifest)
    project_qto = calculate_qto(resolved)

    # 1. Circular Column: d = 0.50m (r = 0.25m), h = 3.5m
    col_circ = resolved.get_element_by_tag("COL-CIRCULAR-01")
    assert col_circ is not None
    qto_col_circ = calculate_element_qto(col_circ, manifest)

    expected_circ_vol = math.pi * (0.25**2) * 3.5
    expected_circ_formwork = math.pi * 0.50 * 3.5
    assert qto_col_circ.concrete_volume == pytest.approx(expected_circ_vol, abs=1e-4)
    assert qto_col_circ.formwork_area == pytest.approx(expected_circ_formwork, abs=1e-4)

    # 2. Elliptical Column: a = 0.30m, b = 0.15m, h = 3.5m
    col_ell = resolved.get_element_by_tag("COL-ELLIPSE-01")
    assert col_ell is not None
    qto_col_ell = calculate_element_qto(col_ell, manifest)

    expected_ell_vol = math.pi * 0.30 * 0.15 * 3.5
    a, b = 0.30, 0.15
    ramanujan_p = math.pi * (3.0 * (a + b) - math.sqrt((3.0 * a + b) * (a + 3.0 * b)))
    expected_ell_formwork = ramanujan_p * 3.5

    assert qto_col_ell.concrete_volume == pytest.approx(expected_ell_vol, abs=1e-4)
    assert qto_col_ell.formwork_area == pytest.approx(expected_ell_formwork, abs=1e-4)

    # 3. Circular Beam: r = 0.20m (d = 0.40m), span = 6.0m
    bm_circ = resolved.get_element_by_tag("BM-CIRCULAR-01")
    assert bm_circ is not None
    qto_bm_circ = calculate_element_qto(bm_circ, manifest)

    expected_bm_circ_vol = math.pi * (0.20**2) * 6.0
    expected_bm_circ_formwork = math.pi * 0.40 * 6.0
    assert qto_bm_circ.concrete_volume == pytest.approx(expected_bm_circ_vol, abs=1e-4)
    assert qto_bm_circ.formwork_area == pytest.approx(expected_bm_circ_formwork, abs=1e-4)

    # 4. Elliptical Steel Beam: a = 0.40m, b = 0.20m, span = 6.0m
    bm_ell = resolved.get_element_by_tag("BM-ELLIPSE-STEEL-01")
    assert bm_ell is not None
    qto_bm_ell = calculate_element_qto(bm_ell, manifest)

    expected_steel_vol = math.pi * 0.40 * 0.20 * 6.0
    expected_steel_weight = expected_steel_vol * 7850.0
    assert qto_bm_ell.structural_steel_weight == pytest.approx(expected_steel_weight, abs=1e-2)


def test_curved_profiles_3d_viewer_payload():
    manifest = create_curved_profile_manifest()
    html_content = generate_viewer_html(manifest)

    assert "IfcColumn" in html_content
    assert "COL-CIRCULAR-01" in html_content
    assert "COL-ELLIPSE-01" in html_content
    assert "BM-CIRCULAR-01" in html_content
    assert "BM-ELLIPSE-STEEL-01" in html_content

    # Verify Three.js CylinderGeometry logic exists in script
    assert "THREE.CylinderGeometry" in html_content
    assert "CIRCULAR" in html_content
    assert "ELLIPSE" in html_content


def test_curved_profiles_ifc_compilation_ifcopenshell(tmp_path):
    import ifcopenshell

    manifest = create_curved_profile_manifest()
    output_path = tmp_path / "curved_model.ifc"

    result_path = compile_to_ifc(manifest, output_path)

    assert result_path.exists()
    assert result_path.stat().st_size > 0

    model = ifcopenshell.open(str(result_path))

    circle_profs = model.by_type("IfcCircleProfileDef")
    assert len(circle_profs) >= 2  # Column & Beam

    ellipse_profs = model.by_type("IfcEllipseProfileDef")
    assert len(ellipse_profs) >= 2  # Column & Beam

    # Check circle profile dimensions
    circ_radii = {float(p.Radius) for p in circle_profs}
    assert 0.25 in circ_radii or 0.20 in circ_radii

    # Check ellipse profile dimensions
    ell_axes = {(float(p.SemiAxis1), float(p.SemiAxis2)) for p in ellipse_profs}
    assert (0.3, 0.15) in ell_axes or (0.4, 0.2) in ell_axes


def test_curved_profiles_ifc_compilation_fallback(tmp_path):
    manifest = create_curved_profile_manifest()
    output_path = tmp_path / "curved_model_fallback.ifc"

    result_path = compile_to_ifc(manifest, output_path, force_fallback=True)

    assert result_path.exists()
    content = result_path.read_text(encoding="utf-8")

    assert "IFCCIRCLEPROFILEDEF" in content
    assert "IFCELLIPSEPROFILEDEF" in content
    assert "0.25" in content  # radius of circular column
    assert "0.3" in content   # semi_major_axis of ellipse column
