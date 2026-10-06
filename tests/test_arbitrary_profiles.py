"""
Unit tests for Arbitrary Closed Profiles with Voids:
- IfcArbitraryClosedProfileDef (Arbitrary closed polygon)
- IfcArbitraryProfileDefWithVoids (Arbitrary closed polygon with one or more internal voids/holes)
- IfcSlab with void openings

Verifies schema parsing, Shoelace area, perimeter, QTO formulas, IFC4 compilation, and 3D viewer.
"""

import math
from pathlib import Path
import pytest
from pydantic import ValidationError

from debim.compiler import compile_to_ifc
from debim.qto import calculate_element_qto, calculate_qto, compute_profile_geometry
from debim.resolver import resolve_manifest
from debim.schema import (
    ArbitraryProfile,
    BeamPlacement,
    ColumnPlacement,
    Grids,
    IfcBeam,
    IfcColumn,
    IfcSlab,
    Material,
    ProjectInfo,
    ProjectManifest,
    SlabPlacement,
    SpatialStructure,
    Storey,
    load_manifest,
)
from debim.viewer import generate_viewer_html


def test_arbitrary_profile_schema_validation():
    # 1. Simple arbitrary closed polygon (e.g. Trapezoid)
    pts = [[0.0, 0.0], [1.0, 0.0], [0.8, 0.5], [0.2, 0.5]]
    p1 = ArbitraryProfile(points=pts)
    assert p1.shape == "ARBITRARY"
    assert p1.points == pts
    assert p1.outer_curve == pts
    assert pytest.approx(p1.width) == 1.0
    assert pytest.approx(p1.depth) == 0.5

    # 2. Arbitrary polygon with voids (Box girder or hollow section)
    outer = [[0.0, 0.0], [0.8, 0.0], [0.8, 0.6], [0.0, 0.6]]
    void1 = [[0.1, 0.1], [0.7, 0.1], [0.7, 0.5], [0.1, 0.5]]
    p2 = ArbitraryProfile(
        shape="ARBITRARY_WITH_VOIDS",
        outer_curve=outer,
        inner_curves=[void1],
    )
    assert p2.shape == "ARBITRARY_WITH_VOIDS"
    assert p2.points == outer
    assert p2.voids == [void1]
    assert pytest.approx(p2.width) == 0.8
    assert pytest.approx(p2.depth) == 0.6

    # 3. Validation failure: fewer than 3 points
    with pytest.raises(ValidationError):
        ArbitraryProfile(points=[[0.0, 0.0], [1.0, 0.0]])

    # 4. Validation failure: void with fewer than 3 points
    with pytest.raises(ValidationError):
        ArbitraryProfile(
            points=[[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
            voids=[[[0.1, 0.1], [0.2, 0.2]]],
        )


def test_arbitrary_profile_geometry_and_qto():
    # Outer 1.0 x 1.0 square, Inner void 0.4 x 0.4 square
    outer = [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
    void1 = [[0.3, 0.3], [0.7, 0.3], [0.7, 0.7], [0.3, 0.7]]
    prof = ArbitraryProfile(
        shape="ARBITRARY_WITH_VOIDS",
        points=outer,
        voids=[void1],
    )

    area, perim, w, d = compute_profile_geometry(prof)
    # Outer area: 1.0, Void area: 0.16 -> Net area = 0.84
    assert pytest.approx(area) == 0.84
    # Outer perim: 4.0, Void perim: 1.6 -> Total perim = 5.6
    assert pytest.approx(perim) == 5.6
    assert pytest.approx(w) == 1.0
    assert pytest.approx(d) == 1.0

    # Column QTO with this profile
    col = IfcColumn(
        tag="C-HOLLOW-01",
        material="CONCRETE-C30",
        profile=prof,
        placement=ColumnPlacement(grid=("A", "1"), base_storey="GF", top_storey="2F"),
        **{"class": "IfcColumn"},
    )
    manifest = ProjectManifest(
        project=ProjectInfo(id="TEST", name="Hollow Column Test"),
        grids=Grids(axes_x={"A": 0.0, "B": 6.0}, axes_y={"1": 0.0, "2": 6.0}),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="GF", name="Ground Floor", elevation=0.0, height=3.5),
                Storey(id="2F", name="Second Floor", elevation=3.5, height=3.5),
            ]
        ),
        materials=[Material(id="CONCRETE-C30", name="Concrete 30 MPa", category="concrete", unit_cost_ref="concrete_c30")],
        elements=[col],
    )

    resolved = resolve_manifest(manifest)
    res_col = resolved.columns[0]
    qto = calculate_element_qto(res_col, manifest)

    # Concrete volume: 0.84 m2 * 3.5m = 2.94 m3
    assert pytest.approx(qto.concrete_volume) == 0.84 * 3.5
    # Formwork area: 5.6m * 3.5m = 19.6 m2 (outer surfaces + interior void box)
    assert pytest.approx(qto.formwork_area) == 5.6 * 3.5


def test_slab_with_voids_qto():
    # 6m x 6m slab with 2m x 2m stairwell/service void
    slab = IfcSlab(
        tag="SLAB-OPENING-01",
        material="CONCRETE-C30",
        thickness=0.20,
        placement=SlabPlacement(
            boundary=[("A", "1"), ("C", "1"), ("C", "3"), ("A", "3")],
            storey="GF",
            offset_z=0.0,
            voids=[[("B", "2"), ("C", "2"), ("C", "3"), ("B", "3")]],
        ),
        **{"class": "IfcSlab"},
    )
    manifest = ProjectManifest(
        project=ProjectInfo(id="TEST", name="Slab Void Test"),
        grids=Grids(
            axes_x={"A": 0.0, "B": 4.0, "C": 6.0},
            axes_y={"1": 0.0, "2": 4.0, "3": 6.0},
        ),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GF", name="Ground Floor", elevation=0.0, height=3.5)]
        ),
        materials=[Material(id="CONCRETE-C30", name="Concrete 30 MPa", category="concrete", unit_cost_ref="concrete_c30")],
        elements=[slab],
    )

    resolved = resolve_manifest(manifest)
    res_slab = resolved.slabs[0]

    # Gross slab area: 6m x 6m = 36 m2
    # Void area: (6 - 4) * (6 - 4) = 2m x 2m = 4 m2
    # Net slab area: 36 - 4 = 32 m2
    assert pytest.approx(res_slab.area) == 32.0
    assert len(res_slab.voids) == 1

    qto = calculate_element_qto(res_slab, manifest)
    # Volume: 32 m2 * 0.20m = 6.4 m3
    assert pytest.approx(qto.concrete_volume) == 6.4
    # Formwork: soffit area = 32 m2
    assert pytest.approx(qto.formwork_area) == 32.0


def test_ifc_step_and_ifcopenshell_compilation(tmp_path: Path):
    # Test column with arbitrary closed profile (no voids)
    prof_closed = ArbitraryProfile(
        shape="ARBITRARY_CLOSED",
        points=[[0.0, 0.0], [0.6, 0.0], [0.6, 0.4], [0.3, 0.5], [0.0, 0.4]],
    )
    col1 = IfcColumn(
        tag="C-PENTAGON-01",
        material="CONCRETE-C30",
        profile=prof_closed,
        placement=ColumnPlacement(grid=("A", "1"), base_storey="GF", top_storey="2F"),
        **{"class": "IfcColumn"},
    )

    # Test column with arbitrary profile with voids
    prof_voids = ArbitraryProfile(
        shape="ARBITRARY_WITH_VOIDS",
        points=[[0.0, 0.0], [0.8, 0.0], [0.8, 0.8], [0.0, 0.8]],
        voids=[[[0.2, 0.2], [0.6, 0.2], [0.6, 0.6], [0.2, 0.6]]],
    )
    col2 = IfcColumn(
        tag="C-VOID-01",
        material="CONCRETE-C30",
        profile=prof_voids,
        placement=ColumnPlacement(grid=("B", "1"), base_storey="GF", top_storey="2F"),
        **{"class": "IfcColumn"},
    )

    manifest = ProjectManifest(
        project=ProjectInfo(id="TEST", name="Arbitrary Profile IFC Test"),
        grids=Grids(axes_x={"A": 0.0, "B": 4.0}, axes_y={"1": 0.0}),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="GF", name="Ground Floor", elevation=0.0, height=3.5),
                Storey(id="2F", name="Second Floor", elevation=3.0, height=3.0),
            ]
        ),
        materials=[Material(id="CONCRETE-C30", name="Concrete 30 MPa", category="concrete", unit_cost_ref="concrete_c30")],
        elements=[col1, col2],
    )

    out_file = tmp_path / "model.ifc"
    res_path = compile_to_ifc(manifest, out_file)
    assert res_path.exists()
    content = res_path.read_text(encoding="utf-8")

    # Verify IFC entities in STEP file
    assert "IFCARBITRARYCLOSEDPROFILEDEF" in content
    assert "IFCARBITRARYPROFILEDEFWITHVOIDS" in content
    assert "IFCPOLYLINE" in content


def test_viewer_html_generation(tmp_path: Path):
    prof_voids = ArbitraryProfile(
        shape="ARBITRARY_WITH_VOIDS",
        points=[[0.0, 0.0], [0.7, 0.0], [0.7, 0.7], [0.0, 0.7]],
        voids=[[[0.2, 0.2], [0.5, 0.2], [0.5, 0.5], [0.2, 0.5]]],
    )
    col = IfcColumn(
        tag="C-CUSTOM-01",
        material="CONCRETE-C30",
        profile=prof_voids,
        placement=ColumnPlacement(grid=("A", "1"), base_storey="GF", top_storey="2F"),
        **{"class": "IfcColumn"},
    )
    slab = IfcSlab(
        tag="S-VOID-01",
        material="CONCRETE-C30",
        thickness=0.20,
        placement=SlabPlacement(
            boundary=[("A", "1"), ("B", "1"), ("B", "2"), ("A", "2")],
            storey="GF",
            offset_z=0.0,
            voids=[[("A", "1"), ("B", "1"), ("B", "2"), ("A", "2")]],
        ),
        **{"class": "IfcSlab"},
    )
    manifest = ProjectManifest(
        project=ProjectInfo(id="TEST", name="Viewer Arbitrary Test"),
        grids=Grids(axes_x={"A": 0.0, "B": 5.0}, axes_y={"1": 0.0, "2": 5.0}),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="GF", name="Ground Floor", elevation=0.0, height=3.5),
                Storey(id="2F", name="Second Floor", elevation=3.0, height=3.0),
            ]
        ),
        materials=[Material(id="CONCRETE-C30", name="Concrete 30 MPa", category="concrete", unit_cost_ref="concrete_c30")],
        elements=[col, slab],
    )

    html = generate_viewer_html(manifest)
    assert "ARBITRARY_WITH_VOIDS" in html
    assert "Arbitrary" in html
    assert "s.holes.push" in html


def test_arbitrary_profile_beam_and_multiple_voids():
    # Double-cell hollow box girder
    outer = [[0.0, 0.0], [2.0, 0.0], [2.0, 1.0], [0.0, 1.0]]
    void1 = [[0.2, 0.2], [0.9, 0.2], [0.9, 0.8], [0.2, 0.8]]
    void2 = [[1.1, 0.2], [1.8, 0.2], [1.8, 0.8], [1.1, 0.8]]
    prof = ArbitraryProfile(
        shape="ARBITRARY_WITH_VOIDS",
        points=outer,
        voids=[void1, void2],
    )
    # Area: 2.0*1.0 - (0.7*0.6 + 0.7*0.6) = 2.0 - 0.84 = 1.16 m2
    area, perim, w, d = compute_profile_geometry(prof)
    assert pytest.approx(area) == 1.16
    assert pytest.approx(w) == 2.0
    assert pytest.approx(d) == 1.0

    beam = IfcBeam(
        tag="B-GIRDER-01",
        material="CONCRETE-C30",
        profile=prof,
        placement=BeamPlacement(from_grid=("A", "1"), to_grid=("B", "1"), storey="GF"),
        **{"class": "IfcBeam"},
    )
    manifest = ProjectManifest(
        project=ProjectInfo(id="TEST", name="Double Cell Girder Test"),
        grids=Grids(axes_x={"A": 0.0, "B": 10.0}, axes_y={"1": 0.0}),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="GF", name="Ground Floor", elevation=0.0, height=3.5)]
        ),
        materials=[Material(id="CONCRETE-C30", name="Concrete 30 MPa", category="concrete", unit_cost_ref="concrete_c30")],
        elements=[beam],
    )

    resolved = resolve_manifest(manifest)
    res_beam = resolved.beams[0]
    qto = calculate_element_qto(res_beam, manifest)
    # Length = 10m, Volume = 1.16 * 10 = 11.6 m3
    assert pytest.approx(qto.concrete_volume) == 11.6


def test_step_serializer_arbitrary_profile():
    from debim.compiler import StepSerializer
    serializer = StepSerializer()
    p1 = ArbitraryProfile(
        shape="ARBITRARY_CLOSED",
        points=[[0.0, 0.0], [0.5, 0.0], [0.5, 0.5]],
    )
    ref1 = serializer.create_ifc_profile_def(p1, "COL1", "#99")
    text = "\n".join(serializer.lines)
    assert "IFCARBITRARYCLOSEDPROFILEDEF" in text
    assert "IFCPOLYLINE" in text

    serializer2 = StepSerializer()
    p2 = ArbitraryProfile(
        shape="ARBITRARY_WITH_VOIDS",
        points=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
        voids=[[[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]],
    )
    ref2 = serializer2.create_ifc_profile_def(p2, "COL2", "#99")
    text2 = "\n".join(serializer2.lines)
    assert "IFCARBITRARYPROFILEDEFWITHVOIDS" in text2

