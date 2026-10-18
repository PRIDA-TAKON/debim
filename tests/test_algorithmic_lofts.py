"""
Unit tests for mathematical macro-geometry & multi-storey hyperbolic loft engine.
Verifies parametric mathematical loft evaluation, multi-storey boundary morphing,
QTO takeoff calculations, and IFC4 compilation.
"""

import math
from pathlib import Path
import pytest
import numpy as np

from debim.compiler import compile_to_ifc
from debim.geometry.loft import (
    evaluate_loft_boundary,
    evaluate_loft_radii,
    generate_loft_storey_elements,
)
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import GeometryRules, Grids, Material, ProjectInfo, ProjectManifest, SpatialStructure, Storey


def test_evaluate_loft_radii_cylindrical():
    rules = GeometryRules(
        type="CYLINDRICAL_LOFT",
        base_radii=(10.0, 8.0),
        roof_radii=(10.0, 8.0),
    )
    a0, b0 = evaluate_loft_radii(rules, z=0.0, total_height=30.0)
    a1, b1 = evaluate_loft_radii(rules, z=15.0, total_height=30.0)
    a2, b2 = evaluate_loft_radii(rules, z=30.0, total_height=30.0)

    assert a0 == 10.0 and b0 == 8.0
    assert a1 == 10.0 and b1 == 8.0
    assert a2 == 10.0 and b2 == 8.0


def test_evaluate_loft_radii_conical():
    rules = GeometryRules(
        type="CONICAL_LOFT",
        base_radii=(10.0, 10.0),
        roof_radii=(20.0, 20.0),
    )
    a0, b0 = evaluate_loft_radii(rules, z=0.0, total_height=20.0)
    a1, b1 = evaluate_loft_radii(rules, z=10.0, total_height=20.0)
    a2, b2 = evaluate_loft_radii(rules, z=20.0, total_height=20.0)

    assert pytest.approx(a0, 1e-4) == 10.0
    assert pytest.approx(a1, 1e-4) == 15.0
    assert pytest.approx(a2, 1e-4) == 20.0


def test_evaluate_loft_radii_hyperbolic():
    rules = GeometryRules(
        type="HYPERBOLIC_LOFT",
        base_radii=(15.0, 12.0),
        waist_radii=(8.0, 6.0),
        roof_radii=(18.0, 14.0),
        cantilever_offset=(3.0, 2.0),
    )
    # Check at base (z=0)
    a_base, b_base = evaluate_loft_radii(rules, z=0.0, total_height=30.0)
    assert pytest.approx(a_base, 1e-4) == 15.0
    assert pytest.approx(b_base, 1e-4) == 12.0

    # Check at waist (z=15, t=0.5)
    a_waist, b_waist = evaluate_loft_radii(rules, z=15.0, total_height=30.0)
    assert pytest.approx(a_waist, 1e-4) == 8.0
    assert pytest.approx(b_waist, 1e-4) == 6.0

    # Check at roof (z=30, t=1.0)
    a_roof, b_roof = evaluate_loft_radii(rules, z=30.0, total_height=30.0)
    assert pytest.approx(a_roof, 1e-4) == 18.0
    assert pytest.approx(b_roof, 1e-4) == 14.0


def test_evaluate_loft_boundary_points_and_cantilever():
    rules = GeometryRules(
        type="HYPERBOLIC_LOFT",
        base_radii=(10.0, 8.0),
        waist_radii=(6.0, 5.0),
        roof_radii=(12.0, 10.0),
        cantilever_offset=(4.0, 2.0),
    )
    # Base (z=0)
    pts_base = evaluate_loft_boundary(rules, z=0.0, total_height=20.0, n_points=32)
    assert pts_base.shape == (32, 2)
    # At u=0, x = cx_z + a_z = 0 + 10 = 10
    assert pytest.approx(pts_base[0, 0], 1e-3) == 10.0
    assert pytest.approx(pts_base[0, 1], 1e-3) == 0.0

    # Top (z=20, t=1.0)
    pts_top = evaluate_loft_boundary(rules, z=20.0, total_height=20.0, n_points=32)
    # Center shifted by cantilever_offset (4.0, 2.0)
    center_top = pts_top.mean(axis=0)
    assert pytest.approx(center_top[0], 1e-3) == 4.0
    assert pytest.approx(center_top[1], 1e-3) == 2.0


def test_manifest_with_geometry_rules_compilation_and_qto(tmp_path: Path):
    manifest = ProjectManifest(
        project=ProjectInfo(id="PROJ-LOFT", name="Hyperbolic Tower"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="FL1", name="Floor 1", elevation=0.0, height=4.0),
                Storey(id="FL2", name="Floor 2", elevation=4.0, height=4.0),
                Storey(id="FL3", name="Floor 3", elevation=8.0, height=4.0),
            ]
        ),
        grids=Grids(axes_x={"1": 0.0, "2": 10.0}, axes_y={"A": 0.0, "B": 10.0}),
        materials=[Material(id="CONCRETE", name="Concrete", category="concrete", unit_cost_ref="MAT-C")],
        geometry_rules=GeometryRules(
            type="HYPERBOLIC_LOFT",
            base_radii=(12.0, 10.0),
            waist_radii=(7.0, 6.0),
            roof_radii=(14.0, 12.0),
            cantilever_offset=(2.0, 1.0),
        ),
    )

    # 1. Resolve manifest
    resolved = resolve_manifest(manifest)

    # Slabs and walls should be auto-generated for FL1, FL2, FL3
    assert len(resolved.slabs) == 3
    assert len(resolved.walls) > 0

    # Slabs morph smoothly according to mathematical radii equations
    # Base slab area ~ pi * 12 * 10 = 376.99
    # Mid slab area (at z=4, t=4/12=0.333)
    # Top slab area (at z=8, t=8/12=0.667)
    slab1_area = resolved.slabs[0].area
    slab2_area = resolved.slabs[1].area
    slab3_area = resolved.slabs[2].area

    expected_base_area = math.pi * 12.0 * 10.0
    assert pytest.approx(slab1_area, abs=5.0) == expected_base_area
    # Slab 2 (at waist region) should have smaller area than Slab 1
    assert slab2_area < slab1_area

    # 2. QTO takeoff
    qto = calculate_qto(resolved)
    assert qto.total_concrete_volume > 0.0
    assert qto.total_loft_slab_area > 0.0
    assert qto.total_loft_enclosure_surface_area > 0.0

    # 3. IFC4 Compilation
    ifc_file = tmp_path / "hyperbolic_loft.ifc"
    out_path = compile_to_ifc(resolved, output_path=ifc_file, force_fallback=True)

    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "IFCSLAB" in content
    assert "IFCARBITRARYCLOSEDPROFILEDEF" in content
    assert "IFCWALL" in content
