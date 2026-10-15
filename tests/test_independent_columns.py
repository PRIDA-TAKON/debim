"""
Unit tests for independent height and elevation parameters for stub columns and roof posts (debim v0.8.1).
Tests ColumnPlacement with explicit base_elevation, top_elevation, and height parameters.
"""

import pytest
import os
import tempfile
from pathlib import Path

from debim.schema import (
    ProjectManifest,
    ProjectInfo,
    Grids,
    SpatialStructure,
    Storey,
    IfcColumn,
    ColumnPlacement,
    BoxProfile,
    CircularProfile,
    Material,
)
from debim.resolver import SpatialResolver, resolve_manifest
from debim.qto import calculate_qto, calculate_element_qto
from debim.compiler import compile_to_ifc


@pytest.fixture
def base_manifest():
    return ProjectManifest(
        schema_version="0.8.1",
        project=ProjectInfo(id="PROJ-STUB-01", name="Stub Column Test Project", code="STUB-01"),
        grids=Grids(
            axes_x={"1": 0.0, "2": 4.0, "3": 8.0},
            axes_y={"A": 0.0, "B": 6.0},
        ),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="FL1", name="Floor 1", elevation=0.0, height=3.5),
                Storey(id="FL2", name="Floor 2", elevation=3.5, height=3.5),
            ]
        ),
        materials=[Material(id="CONC_240", name="Concrete 240", category="concrete", unit_cost_ref="MAT-CONC")],
        elements=[],
    )


def test_stair_landing_stub_column_with_height(base_manifest):
    """
    Test stair landing post (CN-1) from +0.00m to +2.35m
    using base_storey='FL1', base_elevation=0.0, and height=2.35.
    """
    col = IfcColumn(
        **{
            "class": "IfcColumn",
            "tag": "CN-1",
            "material": "CONC_240",
            "profile": BoxProfile(shape="BOX", width=0.20, depth=0.20),
            "placement": ColumnPlacement(
                grid=("1", "A"),
                base_storey="FL1",
                base_elevation=0.0,
                height=2.35,
            ),
        }
    )
    base_manifest.elements = [col]

    resolver = SpatialResolver(base_manifest)
    resolved_col = resolver.resolve_column(col)

    assert resolved_col.start_point == (0.0, 0.0, 0.0)
    assert resolved_col.end_point == (0.0, 0.0, 2.35)
    assert pytest.approx(resolved_col.height, 1e-5) == 2.35

    # Check QTO
    qto_item = calculate_element_qto(resolved_col)
    # Volume: 0.20 * 0.20 * 2.35 = 0.094 m3
    assert pytest.approx(qto_item.concrete_volume, 1e-4) == 0.094
    # Formwork: 2 * (0.20 + 0.20) * 2.35 = 1.88 m2
    assert pytest.approx(qto_item.formwork_area, 1e-4) == 1.88


def test_roof_ridge_post_explicit_elevations(base_manifest):
    """
    Test roof ridge post (CX-1) on tie beam from +7.45m up to +10.65m ridge
    using explicit base_elevation=7.45 and top_elevation=10.65 without base_storey or top_storey.
    """
    col = IfcColumn(
        **{
            "class": "IfcColumn",
            "tag": "CX-1",
            "material": "CONC_240",
            "profile": BoxProfile(shape="BOX", width=0.25, depth=0.25),
            "placement": ColumnPlacement(
                grid=("2", "B"),
                base_elevation=7.45,
                top_elevation=10.65,
            ),
        }
    )
    base_manifest.elements = [col]

    resolver = SpatialResolver(base_manifest)
    resolved_col = resolver.resolve_column(col)

    assert resolved_col.start_point == (4.0, 6.0, 7.45)
    assert resolved_col.end_point == (4.0, 6.0, 10.65)
    assert pytest.approx(resolved_col.height, 1e-5) == 3.20

    # Check QTO
    qto_item = calculate_element_qto(resolved_col)
    # Volume: 0.25 * 0.25 * 3.20 = 0.20 m3
    assert pytest.approx(qto_item.concrete_volume, 1e-4) == 0.20
    # Formwork: 4 * 0.25 * 3.20 = 3.20 m2
    assert pytest.approx(qto_item.formwork_area, 1e-4) == 3.20


def test_column_base_elevation_and_height_without_storeys():
    """
    Test column created in a manifest with no storeys defined,
    using base_elevation and height.
    """
    manifest = ProjectManifest(
        schema_version="0.8.1",
        project=ProjectInfo(id="PROJ-NOST-01", name="No Storeys Project", code="NOST-01"),
        grids=Grids(
            axes_x={"1": 0.0},
            axes_y={"A": 0.0},
        ),
        spatial_structure=SpatialStructure(storeys=[]),
        materials=[Material(id="CONC_240", name="Concrete 240", category="concrete", unit_cost_ref="MAT-CONC")],
        elements=[
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "POST-1",
                    "material": "CONC_240",
                    "profile": CircularProfile(shape="CIRCULAR", radius=0.15),
                    "placement": ColumnPlacement(
                        grid=("1", "A"),
                        base_elevation=1.50,
                        height=2.00,
                    ),
                }
            )
        ],
    )

    resolved_manifest = resolve_manifest(manifest)
    resolved_col = resolved_manifest.columns[0]

    assert resolved_col.start_point == (0.0, 0.0, 1.50)
    assert resolved_col.end_point == (0.0, 0.0, 3.50)
    assert pytest.approx(resolved_col.height, 1e-5) == 2.00

    qto_project = calculate_qto(resolved_manifest)
    col_qto = qto_project.get_element("POST-1")
    # Volume: pi * 0.15^2 * 2.0 = 0.14137 m3
    assert pytest.approx(col_qto.concrete_volume, 1e-3) == 0.14137


def test_ifc_compilation_independent_columns(base_manifest):
    """
    Test exporting independent columns to IFC STEP physical format via compile_to_ifc.
    """
    c1 = IfcColumn(
        **{
            "class": "IfcColumn",
            "tag": "C-STUB",
            "material": "CONC_240",
            "profile": BoxProfile(shape="BOX", width=0.30, depth=0.30),
            "placement": ColumnPlacement(
                grid=("1", "A"),
                base_elevation=0.50,
                height=1.50,
            ),
        }
    )
    c2 = IfcColumn(
        **{
            "class": "IfcColumn",
            "tag": "C-ROOF",
            "material": "CONC_240",
            "profile": BoxProfile(shape="BOX", width=0.20, depth=0.20),
            "placement": ColumnPlacement(
                grid=("2", "B"),
                base_elevation=7.00,
                top_elevation=9.50,
            ),
        }
    )
    base_manifest.elements = [c1, c2]

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_ifc = Path(tmp_dir) / "test_columns.ifc"
        compiled_path = compile_to_ifc(base_manifest, output_path=output_ifc, force_fallback=True)

        assert compiled_path.exists()
        content = compiled_path.read_text(encoding="utf-8")

        assert "C-STUB" in content
        assert "C-ROOF" in content
        assert "IFCCOLUMN" in content
