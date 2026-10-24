"""
Tests for debim Terrain Engine:
AI Survey Ingestion, Delaunay TIN Mesh, Boundary Clipping, and Non-intersecting Contours.
"""

import json
import pytest
from pathlib import Path
from shapely.geometry import Polygon, Point, LineString

from debim.terrain import SurveyPoint, SurveyData, generate_terrain_mesh, extract_contours
from debim.schema import load_manifest, ProjectManifest
from debim.resolver import resolve_manifest
from debim.compiler import compile_to_ifc


def test_survey_data_from_json(tmp_path):
    survey_json = {
        "boundary": [
            [0.0, 0.0],
            [50.0, 0.0],
            [50.0, 40.0],
            [0.0, 40.0]
        ],
        "points": [
            {"x": 5.0, "y": 5.0, "z": 1.0},
            {"x": 25.0, "y": 5.0, "z": 2.5},
            {"x": 45.0, "y": 5.0, "z": 3.0},
            {"x": 5.0, "y": 20.0, "z": 1.5},
            {"x": 25.0, "y": 20.0, "z": 3.5},
            {"x": 45.0, "y": 20.0, "z": 2.0},
            {"x": 5.0, "y": 35.0, "z": 0.5},
            {"x": 25.0, "y": 35.0, "z": 1.8},
            {"x": 45.0, "y": 35.0, "z": 1.2}
        ]
    }
    json_file = tmp_path / "survey.json"
    json_file.write_text(json.dumps(survey_json), encoding="utf-8")

    survey = SurveyData.from_json(json_file)
    assert len(survey.points) == 9
    assert survey.boundary is not None
    assert len(survey.boundary) == 4
    assert survey.points[0].z == 1.0


def test_survey_data_from_csv(tmp_path):
    csv_content = """x,y,z
0.0, 0.0, 1.0
10.0, 0.0, 1.5
10.0, 10.0, 2.0
0.0, 10.0, 1.2
5.0, 5.0, 2.8
"""
    csv_file = tmp_path / "survey.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    survey = SurveyData.from_csv(csv_file)
    assert len(survey.points) == 5
    assert survey.points[4].z == 2.8


def test_terrain_mesh_generation_and_clipping():
    boundary = [(0.0, 0.0), (30.0, 0.0), (30.0, 30.0), (0.0, 30.0)]
    bound_poly = Polygon(boundary)

    # Points extending both inside and outside the boundary
    points = [
        SurveyPoint(5, 5, 1.0),
        SurveyPoint(25, 5, 2.0),
        SurveyPoint(25, 25, 3.0),
        SurveyPoint(5, 25, 2.5),
        SurveyPoint(15, 15, 4.0),
        SurveyPoint(40, 15, 1.0),  # Outside
        SurveyPoint(-10, 15, 0.5), # Outside
    ]
    survey = SurveyData(points=points, boundary=boundary)

    terrain = generate_terrain_mesh(survey, boundary=boundary, clip_to_boundary=True)

    assert terrain.vertex_count >= 3
    assert terrain.face_count >= 1

    # Every vertex of the clipped mesh must be within or on the site boundary
    for vx, vy, vz in terrain.vertices:
        p = Point(vx, vy)
        assert bound_poly.distance(p) < 1e-4, f"Vertex ({vx}, {vy}) leaked outside boundary!"

    # Elevation interpolation check
    z_center = terrain.get_elevation_at(15.0, 15.0)
    assert abs(z_center - 4.0) < 0.1


def test_contour_lines_non_intersecting():
    # Regular undulating grid
    points = []
    for x in range(0, 50, 10):
        for y in range(0, 50, 10):
            # Hill peak in the center
            z = 5.0 - 0.05 * ((x - 20)**2 + (y - 20)**2)
            points.append(SurveyPoint(float(x), float(y), float(z)))

    survey = SurveyData(points=points)
    terrain = generate_terrain_mesh(survey, contour_interval=0.5, clip_to_boundary=False)

    assert len(terrain.contours) > 0

    # Test contour invariants: contours at different levels must NEVER intersect
    lines_by_level = []
    for c in terrain.contours:
        if len(c.points) >= 2:
            ls = LineString([(p[0], p[1]) for p in c.points])
            lines_by_level.append((c.elevation, ls))

    for i in range(len(lines_by_level)):
        for j in range(i + 1, len(lines_by_level)):
            elev_i, line_i = lines_by_level[i]
            elev_j, line_j = lines_by_level[j]
            if elev_i != elev_j:
                assert not line_i.crosses(line_j), f"Contours at {elev_i}m and {elev_j}m cross each other!"


def test_manifest_integration_and_ifc_compilation(tmp_path):
    survey_json = {
        "boundary": [[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]],
        "points": [
            {"x": 2.0, "y": 2.0, "z": 0.5},
            {"x": 18.0, "y": 2.0, "z": 1.5},
            {"x": 18.0, "y": 18.0, "z": 2.0},
            {"x": 2.0, "y": 18.0, "z": 1.0},
            {"x": 10.0, "y": 10.0, "z": 3.0}
        ]
    }
    survey_file = tmp_path / "survey.json"
    survey_file.write_text(json.dumps(survey_json), encoding="utf-8")

    manifest_yaml = f"""
schema: IFC4-Minimal
project:
  id: PRJ-TERRAIN-01
  name: Terrain Test Project

materials:
  - id: CONC
    name: Concrete
    category: concrete
    unit_cost_ref: MAT-CONC

site:
  boundary: [[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]]
  terrain:
    source: "{survey_file.as_posix()}"
    contour_interval: 0.50
    clip_to_boundary: true

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

    assert resolved.terrain_mesh is not None
    assert resolved.terrain_mesh.vertex_count >= 3
    assert resolved.terrain_mesh.face_count >= 1

    # Compile to IFC
    out_ifc = tmp_path / "dist" / "terrain_model.ifc"
    res_path = compile_to_ifc(resolved, output_path=out_ifc)

    assert res_path.exists()
    content = res_path.read_text(encoding="utf-8")
    assert "IFCTRIANGULATEDFACESET" in content.upper()
    assert "TERRAIN_SURFACE" in content.upper()
