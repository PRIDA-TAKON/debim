import pytest
from debim.schema import (
    BoxProfile,
    BeamPlacement,
    ColumnPlacement,
    Grids,
    IfcBeam,
    IfcColumn,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    Units,
)
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto, calculate_element_qto


def test_steel_beam_qto():
    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="PRJ-STEEL", name="Steel Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="L1", name="Level 1", elevation=0.0, height=3.5)]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 5.0},
            axes_y={"A": 0.0, "B": 4.0},
        ),
        materials=[
            Material(
                id="STEEL_MAT",
                name="Structural Steel SS400",
                category="steel",
                unit_cost_ref="MAT-STEEL",
            )
        ],
        elements=[
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": "SB-W310X60",
                    "material": "STEEL_MAT",
                    "profile": BoxProfile(shape="BOX", width=0.20, depth=0.30),
                    "placement": BeamPlacement(
                        from_grid=("1", "A"),
                        to_grid=("2", "A"),
                        storey="L1",
                    ),
                }
            )
        ],
    )

    resolved = resolve_manifest(manifest)
    eqto = calculate_element_qto(resolved.beams[0], manifest=manifest)

    assert eqto.length == 5.0
    assert eqto.concrete_volume == 0.0
    assert eqto.formwork_area == 0.0
    assert eqto.total_rebar_weight == 0.0
    # W310X60 linear mass = 60.0 kg/m * 5.0m = 300.0 kg
    assert eqto.structural_steel_weight == 300.0
    # Perimeter = 2 * (0.20 + 0.30) = 1.0m; painting_area = 1.0 * 5.0 = 5.0 m2
    assert eqto.painting_area == 5.0
    # Weld touchup area = 10% of painting_area = 0.50 m2
    assert eqto.weld_touchup_area == 0.50


def test_timber_beam_and_column_qto():
    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="PRJ-TIMBER", name="Timber Test"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Level 1", elevation=0.0, height=3.0),
                Storey(id="L2", name="Level 2", elevation=3.0, height=3.0),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 4.0},
            axes_y={"A": 0.0, "B": 3.0},
        ),
        materials=[
            Material(
                id="WOOD_TEAK",
                name="Teak Wood Timber",
                category="timber",
                unit_cost_ref="MAT-WOOD",
            )
        ],
        elements=[
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": "TB-101",
                    "material": "WOOD_TEAK",
                    "profile": BoxProfile(shape="BOX", width=0.15, depth=0.20),
                    "placement": BeamPlacement(
                        from_grid=("1", "A"),
                        to_grid=("2", "A"),
                        storey="L1",
                    ),
                }
            ),
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "TC-101",
                    "material": "WOOD_TEAK",
                    "profile": BoxProfile(shape="BOX", width=0.15, depth=0.15),
                    "placement": ColumnPlacement(
                        grid=("1", "A"),
                        base_storey="L1",
                        top_storey="L2",
                    ),
                }
            ),
        ],
    )

    qto = calculate_qto(manifest)

    # Beam: length = 4.0m, vol = 0.15 * 0.20 * 4.0 = 0.12 m3, paint = 2 * (0.15+0.20) * 4.0 = 2.8 m2
    beam_eq = qto.get_element("TB-101")
    assert beam_eq is not None
    assert beam_eq.length == 4.0
    assert beam_eq.concrete_volume == 0.0
    assert beam_eq.timber_volume == 0.12
    assert beam_eq.painting_area == 2.8

    # Column: length = 3.0m, vol = 0.15 * 0.15 * 3.0 = 0.0675 m3, paint = 2 * (0.15+0.15) * 3.0 = 1.8 m2
    col_eq = qto.get_element("TC-101")
    assert col_eq is not None
    assert col_eq.length == 3.0
    assert col_eq.concrete_volume == 0.0
    assert pytest.approx(col_eq.timber_volume) == 0.0675
    assert pytest.approx(col_eq.painting_area) == 1.8

    # Project totals
    assert qto.total_concrete_volume == 0.0
    assert pytest.approx(qto.total_timber_volume) == 0.12 + 0.0675
    assert pytest.approx(qto.total_painting_area) == 2.8 + 1.8


def test_project_qto_steel_and_timber_aggregation():
    manifest = ProjectManifest(
        schema="IFC4-Minimal",
        project=ProjectInfo(id="PRJ-MIXED", name="Mixed Structural Test"),
        spatial_structure=SpatialStructure(
            storeys=[Storey(id="L1", name="Level 1", elevation=0.0, height=4.0)]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 6.0},
            axes_y={"A": 0.0, "B": 5.0},
        ),
        materials=[
            Material(id="CONC_280", name="Concrete", category="concrete", unit_cost_ref="M1"),
            Material(id="STEEL_SS400", name="Steel SS400", category="steel", unit_cost_ref="M2"),
            Material(id="WOOD_PINE", name="Pine Timber", category="timber", unit_cost_ref="M3"),
        ],
        elements=[
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": "CB-01",
                    "material": "CONC_280",
                    "profile": BoxProfile(shape="BOX", width=0.20, depth=0.40),
                    "placement": BeamPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L1"),
                }
            ),
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": "SB-W310X60",
                    "material": "STEEL_SS400",
                    "profile": BoxProfile(shape="BOX", width=0.20, depth=0.30),
                    "placement": BeamPlacement(from_grid=("1", "B"), to_grid=("2", "B"), storey="L1"),
                }
            ),
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": "TB-01",
                    "material": "WOOD_PINE",
                    "profile": BoxProfile(shape="BOX", width=0.10, depth=0.20),
                    "placement": BeamPlacement(from_grid=("1", "A"), to_grid=("1", "B"), storey="L1"),
                }
            ),
        ],
    )

    qto = calculate_qto(manifest)

    # Concrete beam: 0.20 * 0.40 * 6.0 = 0.48 m3
    assert pytest.approx(qto.total_concrete_volume) == 0.48
    # Steel beam: W310X60 * 6.0m = 360.0 kg
    assert pytest.approx(qto.total_structural_steel_weight) == 360.0
    # Timber beam: 0.10 * 0.20 * 5.0 = 0.10 m3
    assert pytest.approx(qto.total_timber_volume) == 0.10

    # Painting areas:
    # Steel beam: 2*(0.20+0.30)*6.0 = 6.0 m2
    # Timber beam: 2*(0.10+0.20)*5.0 = 3.0 m2
    assert pytest.approx(qto.total_painting_area) == 9.0
    # Weld touchup area: 10% of steel painting area = 0.60 m2
    assert pytest.approx(qto.total_weld_touchup_area) == 0.60
