"""
Unit tests for debim.spec schema validation and discrepancy auditor.
"""

from pathlib import Path
import tempfile
import pytest
import yaml
from typer.testing import CliRunner

from debim.cli import app
from debim.schema import (
    Grids,
    IfcWall,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    WallPlacement,
)
from debim.spec.audit import SpecAuditResult, audit_project_specs
from debim.spec.schema import (
    IndustryStandards,
    MaterialSpec,
    SpecificationManifest,
    StructuredClauses,
    load_spec_manifest,
)


def test_material_spec_schema_and_coercion():
    # Test nested creation
    spec1 = MaterialSpec(
        id="CONCRETE_C30",
        name="High Strength Structural Concrete C30/37",
        manufacturer="Cemex Corp",
        masterformat="03 30 00",
        warranty_years=10,
        standards=IndustryStandards(
            jis="JIS A 5308",
            astm="ASTM C94",
            din="DIN 1045",
            iso="ISO 22965",
        ),
        clauses=StructuredClauses(
            general_properties="Compressive strength >= 30 MPa at 28 days.",
            surface_preparation="Clean subgrade and ensure formwork is oiled.",
            application_system="Pour within 90 minutes of batching; vibrate continuously.",
        ),
    )

    assert spec1.id == "CONCRETE_C30"
    assert spec1.manufacturer == "Cemex Corp"
    assert spec1.standards.jis == "JIS A 5308"
    assert spec1.standards.astm == "ASTM C94"
    assert spec1.clauses.general_properties == "Compressive strength >= 30 MPa at 28 days."

    # Test top-level dict coercion
    raw_dict = {
        "id": "STEEL_SS400",
        "name": "Structural Carbon Steel SS400",
        "jis": "JIS G 3101",
        "astm": "ASTM A36",
        "general_properties": ["Tensile strength 400-510 MPa", "Yield point >= 245 MPa"],
        "surface_preparation": "Sandblast to Sa 2.5 standard",
        "application_system": "Apply zinc-rich primer within 4 hours",
    }
    spec2 = MaterialSpec.model_validate(raw_dict)
    assert spec2.id == "STEEL_SS400"
    assert spec2.standards.jis == "JIS G 3101"
    assert spec2.standards.astm == "ASTM A36"
    assert isinstance(spec2.clauses.general_properties, list)


def test_load_spec_manifest_sources():
    raw_specs_list = [
        {"id": "MAT_01", "name": "Material 01", "warranty_years": 5},
        {"id": "MAT_02", "name": "Material 02", "warranty_years": 10},
    ]

    # Test loading list of dicts
    manifest_from_list = load_spec_manifest(raw_specs_list)
    assert len(manifest_from_list.specifications) == 2
    assert manifest_from_list.specifications[0].id == "MAT_01"

    # Test loading YAML file and directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        yaml_file = tmp_path / "specs.yaml"
        yaml_file.write_text(yaml.dump({"specifications": raw_specs_list}), encoding="utf-8")

        manifest_from_file = load_spec_manifest(yaml_file)
        assert len(manifest_from_file.specifications) == 2

        manifest_from_dir = load_spec_manifest(tmp_path)
        assert len(manifest_from_dir.specifications) == 2


@pytest.fixture
def sample_project_manifest():
    return ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="PROJ-01", name="Test Building Project"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="FL1", name="Ground Floor", elevation=0.0, height=3.5)]
        ),
        grids=Grids(
            axes_x={"A": 0.0, "B": 6.0},
            axes_y={"1": 0.0, "2": 6.0},
        ),
        materials=[
            Material(id="CONCRETE_C30", name="Concrete C30/37", category="CONCRETE", unit_cost_ref="C30"),
            Material(id="BRICK_RED", name="Red Clay Brick", category="MASONRY", unit_cost_ref="BRK"),
        ],
        elements=[
            IfcWall(
                tag="WAL-01",
                placement=WallPlacement(storey="FL1", from_grid=("A", "1"), to_grid=("B", "1")),
                material="CONCRETE_C30",
                thickness=0.2,
                height=3.0,
            ),
            IfcWall(
                tag="WAL-02",
                placement=WallPlacement(storey="FL1", from_grid=("A", "2"), to_grid=("B", "2")),
                material="BRICK_RED",
                thickness=0.15,
                height=3.0,
            ),
        ],
    )


def test_audit_project_specs_compliant(sample_project_manifest):
    spec_manifest = SpecificationManifest(
        specifications=[
            MaterialSpec(id="CONCRETE_C30", name="Concrete C30/37 Specification"),
            MaterialSpec(id="BRICK_RED", name="Red Clay Brick Specification"),
        ]
    )

    res = audit_project_specs(sample_project_manifest, spec_manifest)

    assert res.is_compliant is True
    assert res.missing_specs == []
    assert res.unused_specs == []
    assert sorted(res.referenced_materials) == ["BRICK_RED", "CONCRETE_C30"]
    assert sorted(res.spec_ids) == ["BRICK_RED", "CONCRETE_C30"]
    assert res.element_material_map["CONCRETE_C30"] == ["WAL-01"]
    assert res.element_material_map["BRICK_RED"] == ["WAL-02"]


def test_audit_project_specs_discrepancies(sample_project_manifest):
    # Spec manifest missing BRICK_RED, but containing unused PAINT_EPOXY
    spec_manifest = SpecificationManifest(
        specifications=[
            MaterialSpec(id="CONCRETE_C30", name="Concrete C30 Specification"),
            MaterialSpec(id="PAINT_EPOXY", name="Epoxy Paint Specification"),
        ]
    )

    res = audit_project_specs(sample_project_manifest, spec_manifest)

    assert res.is_compliant is False
    assert res.missing_specs == ["BRICK_RED"]
    assert res.unused_specs == ["PAINT_EPOXY"]
    assert "WAL-02" in res.element_material_map["BRICK_RED"]


def test_cli_spec_audit_command(sample_project_manifest):
    runner = CliRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        proj_file = tmp_path / "project.yaml"
        spec_file = tmp_path / "specs.yaml"

        # Dump project manifest
        proj_data = sample_project_manifest.model_dump(by_alias=True, mode="json")
        proj_file.write_text(yaml.dump(proj_data), encoding="utf-8")

        # Compliant spec package
        spec_data = {
            "specifications": [
                {"id": "CONCRETE_C30", "name": "Concrete C30"},
                {"id": "BRICK_RED", "name": "Brick Red"},
            ]
        }
        spec_file.write_text(yaml.dump(spec_data), encoding="utf-8")

        # Run CLI spec audit with compliant specs
        result = runner.invoke(app, ["spec", "audit", "-m", str(proj_file), "-s", str(spec_file)])
        assert result.exit_code == 0
        assert "Material Specification Discrepancy Audit" in result.output
        assert "MATCHED / OK" in result.output
        assert "COMPLIANT PASS" in result.output

        # Run CLI spec audit with strict mode on non-compliant specs
        spec_file.write_text(yaml.dump({"specifications": [{"id": "CONCRETE_C30", "name": "Concrete"}]}), encoding="utf-8")
        result_strict = runner.invoke(app, ["spec", "audit", "-m", str(proj_file), "-s", str(spec_file), "--strict"])
        assert result_strict.exit_code == 1
        assert "MISSING SPEC" in result_strict.output
        assert "BRICK_RED" in result_strict.output
