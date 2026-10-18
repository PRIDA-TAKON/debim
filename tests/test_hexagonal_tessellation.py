"""
Unit tests for conformal hexagonal tessellation engine, high-performance IFC4 export,
QTO aggregation, and WebGL viewer payload generation.
"""

from pathlib import Path
import pytest
import numpy as np

from debim.compiler import StepSerializer, compile_to_ifc
from debim.geometry.tessellation import generate_facade_tessellation
from debim.qto import calculate_qto
from debim.resolver import SpatialResolver
from debim.schema import (
    FacadeConfig,
    FacadeEnvelopeSkin,
    GeometryRules,
    Grids,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
)
from debim.viewer import generate_viewer_html


def create_sample_hyperbolic_loft_manifest(pattern: str = "HEXAGONAL_CONFORMAL", ifc_rep: str = "IfcTriangulatedFaceSet") -> ProjectManifest:
    return ProjectManifest(
        project=ProjectInfo(id="PROJ-MUSEO", name="Museo Soumaya Loft"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="FL1", name="Ground Floor", elevation=0.0, height=4.5),
                Storey(id="FL2", name="First Floor", elevation=4.5, height=4.5),
                Storey(id="FL3", name="Second Floor", elevation=9.0, height=4.5),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 10.0, "3": 20.0},
            axes_y={"A": 0.0, "B": 10.0, "C": 20.0},
        ),
        materials=[
            Material(id="ALUMINUM_ANODIZED_SILVER", name="Anodized Aluminum", category="metal", unit_cost_ref="MAT-ALU"),
            Material(id="CONCRETE", name="Structural Concrete", category="concrete", unit_cost_ref="MAT-CONC"),
        ],
        geometry_rules=GeometryRules(
            type="HYPERBOLIC_LOFT",
            base_radii=(12.0, 10.0),
            waist_radii=(8.5, 7.0),
            roof_radii=(14.0, 11.0),
            cantilever_offset=(2.5, 1.0),
        ),
        facade=FacadeConfig(
            envelope_skin=FacadeEnvelopeSkin(
                target="HYPERBOLIC_LOFT",
                pattern=pattern,
                target_panel_size=0.55,
                joint_gap=0.02,
                material="ALUMINUM_ANODIZED_SILVER",
                ifc_representation=ifc_rep,
            )
        ),
    )


def test_facade_envelope_skin_schema_validation():
    skin = FacadeEnvelopeSkin(target="HYPERBOLIC_LOFT")
    assert skin.target == "HYPERBOLIC_LOFT"
    assert skin.pattern == "HEXAGONAL_CONFORMAL"
    assert skin.target_panel_size == 0.55
    assert skin.joint_gap == 0.02
    assert skin.material == "ALUMINUM_ANODIZED_SILVER"
    assert skin.ifc_representation == "IfcTriangulatedFaceSet"

    manifest = create_sample_hyperbolic_loft_manifest()
    assert manifest.facade is not None
    assert manifest.facade.envelope_skin is not None
    assert manifest.facade.envelope_skin.target_panel_size == 0.55


def test_conformal_hexagonal_tessellation_math():
    manifest = create_sample_hyperbolic_loft_manifest(pattern="HEXAGONAL_CONFORMAL")
    tess_result = generate_facade_tessellation(manifest)

    assert tess_result is not None
    assert tess_result.total_panel_count > 100
    assert tess_result.total_surface_area > 50.0

    # Test individual panel geometry properties
    sample_panel = tess_result.panels[0]
    assert sample_panel.panel_id.startswith("HEX-PANEL-")
    assert len(sample_panel.vertices) == 6
    assert len(sample_panel.faces) == 4
    assert sample_panel.area > 0.0

    # Check normal is unit vector
    norm = np.linalg.norm(sample_panel.normal)
    assert pytest.approx(norm, abs=1e-3) == 1.0

    # Check combined mesh indexing
    pts, indices = tess_result.get_combined_tessellation_mesh()
    assert len(pts) == len(tess_result.panels) * 6
    assert len(indices) == len(tess_result.panels) * 4
    assert min(idx for face in indices for idx in face) == 1  # 1-based indexing for IFC


def test_voronoi_centroidal_tessellation():
    manifest = create_sample_hyperbolic_loft_manifest(pattern="VORONOI_CENTROIDAL")
    tess_result = generate_facade_tessellation(manifest)

    assert tess_result is not None
    assert tess_result.pattern == "VORONOI_CENTROIDAL"
    assert tess_result.total_panel_count > 100
    assert tess_result.total_surface_area > 50.0


def test_qto_facade_panel_aggregation():
    manifest = create_sample_hyperbolic_loft_manifest()
    resolver = SpatialResolver(manifest)
    resolved = resolver.resolve()

    assert resolved.facade_tessellation is not None

    qto = calculate_qto(resolved)
    assert qto.total_facade_panels_count > 100
    assert qto.total_facade_skin_area_sqm > 50.0
    assert qto.total_aluminum_facade_weight_kg > 0.0
    assert pytest.approx(qto.total_aluminum_facade_weight_kg, abs=1e-2) == qto.total_facade_skin_area_sqm * 8.10


def test_ifc4_export_triangulated_face_set_and_mapped_item(tmp_path: Path):
    # Test IfcTriangulatedFaceSet export
    manifest_tfs = create_sample_hyperbolic_loft_manifest(ifc_rep="IfcTriangulatedFaceSet")
    resolver_tfs = SpatialResolver(manifest_tfs)
    resolved_tfs = resolver_tfs.resolve()

    serializer = StepSerializer()
    step_content_tfs = serializer.serialize(resolved_tfs)

    assert "FACADE-ENVELOPE-SKIN" in step_content_tfs
    assert "IFCTRIANGULATEDFACESET" in step_content_tfs or "IFCTRIANGULATEDFACESET" in step_content_tfs.upper()

    out_tfs = tmp_path / "facade_tfs.ifc"
    compile_to_ifc(resolved_tfs, output_path=out_tfs, force_fallback=True)
    assert out_tfs.exists()
    assert out_tfs.stat().st_size > 1000

    # Test IfcMappedItem export
    manifest_mapped = create_sample_hyperbolic_loft_manifest(ifc_rep="IfcMappedItem")
    resolver_mapped = SpatialResolver(manifest_mapped)
    resolved_mapped = resolver_mapped.resolve()

    step_content_mapped = serializer.serialize(resolved_mapped)
    assert "FACADE-ENVELOPE-SKIN" in step_content_mapped
    assert "IFCMAPPEDITEM" in step_content_mapped.upper() or "IFCREPRESENTATIONMAP" in step_content_mapped.upper()


def test_webgl_viewer_payload_generation():
    manifest = create_sample_hyperbolic_loft_manifest()
    resolver = SpatialResolver(manifest)
    resolved = resolver.resolve()

    html = generate_viewer_html(resolved)
    assert "FACADE-ENVELOPE-SKIN" in html
    assert "InstancedMesh" in html
    assert "sceneData.facade" in html
