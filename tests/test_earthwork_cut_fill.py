"""
Tests for debim Earthwork Engine:
Building Pad Grading & Automated Cut & Fill Volumetric Balancing
"""

import json
import pytest
from pathlib import Path
from shapely.geometry import Polygon

from debim.terrain import SurveyPoint, SurveyData, generate_terrain_mesh
from debim.earthwork import calculate_cut_fill, EarthworkResult
from debim.schema import load_manifest, ProjectManifest
from debim.resolver import resolve_manifest
from debim.qto import calculate_qto
from debim.boq import generate_boq


def test_pure_cut_benchmark():
    # Flat ground at elevation Z = 3.0, pad at Z = 1.0, 10m x 10m area (100 m2)
    # Expected Cut = 100 m2 * (3.0 - 1.0) = 200.0 m3, Fill = 0.0 m3
    pts = [
        SurveyPoint(0.0, 0.0, 3.0),
        SurveyPoint(20.0, 0.0, 3.0),
        SurveyPoint(20.0, 20.0, 3.0),
        SurveyPoint(0.0, 20.0, 3.0),
        SurveyPoint(10.0, 10.0, 3.0),
    ]
    survey = SurveyData(points=pts)
    tin = generate_terrain_mesh(survey, clip_to_boundary=False)

    pad_poly = [(5.0, 5.0), (15.0, 5.0), (15.0, 15.0), (5.0, 15.0)]
    res = calculate_cut_fill(tin, pad_poly, pad_elevation=1.0)

    assert abs(res.pad_area - 100.0) < 1e-4
    assert abs(res.cut_volume - 200.0) < 2.0  # within 1% error
    assert res.fill_volume == 0.0
    assert res.net_balance == -res.cut_volume


def test_pure_fill_benchmark():
    # Flat ground at elevation Z = 0.5, pad at Z = 2.5, 10m x 10m area (100 m2)
    # Expected Fill = 100 m2 * (2.5 - 0.5) = 200.0 m3, Cut = 0.0 m3
    pts = [
        SurveyPoint(0.0, 0.0, 0.5),
        SurveyPoint(20.0, 0.0, 0.5),
        SurveyPoint(20.0, 20.0, 0.5),
        SurveyPoint(0.0, 20.0, 0.5),
        SurveyPoint(10.0, 10.0, 0.5),
    ]
    survey = SurveyData(points=pts)
    tin = generate_terrain_mesh(survey, clip_to_boundary=False)

    pad_poly = [(5.0, 5.0), (15.0, 5.0), (15.0, 15.0), (5.0, 15.0)]
    res = calculate_cut_fill(tin, pad_poly, pad_elevation=2.5)

    assert abs(res.pad_area - 100.0) < 1e-4
    assert abs(res.fill_volume - 200.0) < 2.0  # within 1% error
    assert res.cut_volume == 0.0
    assert res.net_balance == res.fill_volume


def test_balanced_slope_benchmark():
    # Ground sloping linearly in X: Z = 0.5 * X
    # Over square (0,0) to (20,20)
    pts = []
    for x in [0.0, 10.0, 20.0]:
        for y in [0.0, 10.0, 20.0]:
            pts.append(SurveyPoint(x, y, 0.5 * x))

    survey = SurveyData(points=pts)
    tin = generate_terrain_mesh(survey, clip_to_boundary=False)

    # Building pad from x=5 to x=15 (center is x=10, where ground elevation Z = 5.0)
    # Pad elevation set to Z = 5.0 -> Symmetrical cut (x > 10) and fill (x < 10)
    pad_poly = [(5.0, 5.0), (15.0, 5.0), (15.0, 15.0), (5.0, 15.0)]
    res = calculate_cut_fill(tin, pad_poly, pad_elevation=5.0)

    assert abs(res.pad_area - 100.0) < 1e-4
    assert res.cut_volume > 0.0
    assert res.fill_volume > 0.0
    # Symmetrical cut and fill means net balance should be approximately 0.0
    assert abs(res.cut_volume - res.fill_volume) < 1.0


def test_manifest_grading_and_boq_integration(tmp_path):
    survey_json = {
        "boundary": [[0.0, 0.0], [30.0, 0.0], [30.0, 30.0], [0.0, 30.0]],
        "points": [
            {"x": 0.0, "y": 0.0, "z": 2.0},
            {"x": 30.0, "y": 0.0, "z": 2.0},
            {"x": 30.0, "y": 30.0, "z": 4.0},
            {"x": 0.0, "y": 30.0, "z": 4.0},
            {"x": 15.0, "y": 15.0, "z": 3.0}
        ]
    }
    survey_file = tmp_path / "survey.json"
    survey_file.write_text(json.dumps(survey_json), encoding="utf-8")

    manifest_yaml = f"""
schema: IFC4-Minimal
project:
  id: PRJ-EARTHWORK-01
  name: Earthwork Test Project

materials:
  - id: CONC
    name: Concrete
    category: concrete
    unit_cost_ref: MAT-CONC

site:
  boundary: [[0.0, 0.0], [30.0, 0.0], [30.0, 30.0], [0.0, 30.0]]
  terrain:
    source: "{survey_file.as_posix()}"
    contour_interval: 0.50
    clip_to_boundary: true
  grading:
    building_pad:
      elevation: 2.0
      batter_slope: 1.5
      polygon: [[5.0, 5.0], [20.0, 5.0], [20.0, 20.0], [5.0, 20.0]]

spatial_structure:
  storeys:
    - id: L1
      name: Ground Floor
      elevation: 0.0
      height: 3.5

grids:
  axes_x: {{ "1": 0.0, "2": 10.0 }}
  axes_y: {{ "A": 0.0, "B": 10.0 }}

elements:
  - class: IfcColumn
    tag: C1
    material: CONC
    profile: {{ shape: BOX, width: 0.3, depth: 0.3 }}
    placement: {{ grid: ["1", "A"], storey: L1 }}
"""
    manifest_file = tmp_path / "model.debim"
    manifest_file.write_text(manifest_yaml, encoding="utf-8")

    manifest = load_manifest(manifest_file)
    resolved = resolve_manifest(manifest)

    assert resolved.earthwork is not None
    assert resolved.earthwork.pad_elevation == 2.0
    assert resolved.earthwork.cut_volume > 0.0

    # Calculate QTO
    qto = calculate_qto(resolved)
    assert qto.earthwork_cut_volume == resolved.earthwork.cut_volume

    # Generate BOQ
    boq = generate_boq(resolved)
    assert "earthwork" in boq
    assert len(boq["earthwork"]) == 3
    desc_list = [item["description"] for item in boq["earthwork"]]
    assert any("งานดินขุด" in d for d in desc_list)
    assert any("งานดินถม" in d for d in desc_list)
    assert any("ดินสุทธิ" in d for d in desc_list)
