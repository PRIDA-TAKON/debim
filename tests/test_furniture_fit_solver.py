"""
Unit tests for 2D geometric furniture fit solver, SAT clearance collision checking,
walkway path connectivity verification, and CLI `debim fit` command.
"""

import time
import pytest
import yaml

from debim.solver import (
    sat_polygon_intersection,
    polygon_contains_polygon,
    check_walkway_connectivity,
    solve_space_furniture_fit,
    solve_manifest_furniture_fit,
    compute_item_polygons,
)
from debim.schema import ProjectManifest
from debim.cli import app
from cli_runner import CliRunner


def test_sat_polygon_intersection_overlapping_and_separated():
    poly_a = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    poly_b = [(1.0, 1.0), (3.0, 1.0), (3.0, 3.0), (1.0, 3.0)]
    poly_c = [(5.0, 5.0), (7.0, 5.0), (7.0, 7.0), (5.0, 7.0)]

    # Overlapping A and B
    assert sat_polygon_intersection(poly_a, poly_b) is True
    # Separated A and C
    assert sat_polygon_intersection(poly_a, poly_c) is False


def test_sat_polygon_intersection_rotated_obbs():
    # 45-degree rotated box centered at (2, 2)
    phys_a, clear_a = compute_item_polygons(2.0, 2.0, 2.0, 1.0, {"front": 0.5, "left": 0.5}, rotation_deg=45.0)
    # Box centered at (5, 5)
    phys_b, clear_b = compute_item_polygons(5.0, 5.0, 2.0, 1.0, {"front": 0.5, "left": 0.5}, rotation_deg=0.0)
    # Box centered at (2.5, 2.5)
    phys_c, clear_c = compute_item_polygons(2.5, 2.5, 1.5, 1.0, {"front": 0.5, "left": 0.5}, rotation_deg=0.0)

    assert sat_polygon_intersection(clear_a, clear_b) is False
    assert sat_polygon_intersection(clear_a, clear_c) is True


def test_polygon_contains_polygon():
    outer = [(0.0, 0.0), (6.0, 0.0), (6.0, 6.0), (0.0, 6.0)]
    inner_inside = [(1.0, 1.0), (3.0, 1.0), (3.0, 3.0), (1.0, 3.0)]
    inner_outside = [(5.0, 5.0), (7.0, 5.0), (7.0, 7.0), (5.0, 7.0)]

    assert polygon_contains_polygon(outer, inner_inside) is True
    assert polygon_contains_polygon(outer, inner_outside) is False


def test_fit_solver_undersized_space_fails_fast():
    # Small 2m x 2m space (4 m2)
    space_poly = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    items = [{
        "ref": "BED_KING_6FT",
        "physical_width": 1.83,
        "physical_depth": 1.98,
        "total_width": 3.03,
        "total_depth": 2.58,
        "total_area": 7.8174,
        "clearance": {"front": 0.6, "left": 0.6, "right": 0.6, "back": 0.0},
    }]

    t0 = time.perf_counter()
    res = solve_space_furniture_fit("SPACE-SMALL", space_poly, items)
    t_elapsed = time.perf_counter() - t0

    assert res.passed is False
    assert "smaller than total furniture envelope area" in res.errors[0]
    assert t_elapsed < 0.01  # Must fail in < 0.01s


def test_fit_solver_clearance_clash_detected():
    space_poly = [(0.0, 0.0), (6.0, 0.0), (6.0, 6.0), (0.0, 6.0)]
    items = [
        {
            "ref": "BED_KING_6FT",
            "physical_width": 1.83,
            "physical_depth": 1.98,
            "total_width": 3.03,
            "total_depth": 2.58,
            "total_area": 7.8174,
            "clearance": {"front": 0.6, "left": 0.6, "right": 0.6, "back": 0.0},
        },
        {
            "ref": "WARDROBE_2M",
            "physical_width": 2.00,
            "physical_depth": 0.60,
            "total_width": 2.00,
            "total_depth": 1.40,
            "total_area": 2.80,
            "clearance": {"front": 0.8, "left": 0.0, "right": 0.0, "back": 0.0},
        },
    ]

    # Explicit overlapping placements
    explicit_placements = [
        {"x": 2.0, "y": 2.0, "rotation_deg": 0.0},
        {"x": 2.5, "y": 2.5, "rotation_deg": 0.0},
    ]

    res = solve_space_furniture_fit(
        "SPACE-CLASH", space_poly, items, explicit_placements=explicit_placements
    )
    assert res.passed is False
    assert any("Clearance envelope clash" in err for err in res.errors)


def test_fit_solver_walkway_connectivity():
    space_poly = [(0.0, 0.0), (6.0, 0.0), (6.0, 6.0), (0.0, 6.0)]
    entrance = (0.5, 0.5)

    # Valid non-overlapping wall placement
    items = [
        {
            "ref": "WORKING_DESK",
            "physical_width": 1.20,
            "physical_depth": 0.60,
            "total_width": 1.20,
            "total_depth": 1.40,
            "total_area": 1.68,
            "clearance": {"front": 0.8, "left": 0.0, "right": 0.0, "back": 0.0},
        }
    ]
    explicit_placements = [{"x": 4.5, "y": 4.5, "rotation_deg": 0.0}]

    res = solve_space_furniture_fit(
        "SPACE-WALK", space_poly, items, entrance_point=entrance, explicit_placements=explicit_placements
    )
    assert res.passed is True
    assert res.walkway_connected is True


def test_solve_manifest_furniture_fit():
    manifest_yaml = """
schema: IFC4-Minimal
project:
  id: PROJ-FIT-TEST
  name: Furniture Fit Solver Test Project
spatial_structure:
  storeys:
    - id: FL1
      name: Floor 1
      elevation: 0.0
      height: 3.0
grids:
  axes_x:
    "1": 0.0
    "2": 5.0
    "3": 10.0
  axes_y:
    A: 0.0
    B: 6.0
materials:
  - id: CONCRETE
    name: Concrete C25/30
    category: Concrete
    unit_cost_ref: MAT-CONC
elements:
  - class: IfcSpace
    tag: SPACE-BED-01
    name: Master Bedroom
    placement:
      storey: FL1
      boundary:
        - ["1", "A"]
        - ["3", "A"]
        - ["3", "B"]
        - ["1", "B"]
    contains:
      - BED_KING_6FT
      - WARDROBE_2M
"""
    manifest_data = yaml.safe_load(manifest_yaml)
    manifest = ProjectManifest.model_validate(manifest_data)

    fit_res = solve_manifest_furniture_fit(manifest)
    assert fit_res.passed is True
    assert len(fit_res.spaces) == 1
    assert fit_res.spaces[0].space_tag == "SPACE-BED-01"
    assert len(fit_res.spaces[0].placements) == 2


def test_cli_debim_fit_command(tmp_path):
    manifest_file = tmp_path / "project.debim"
    manifest_file.write_text("""
schema: IFC4-Minimal
project:
  id: PROJ-CLI-FIT
  name: CLI Fit Test
spatial_structure:
  storeys:
    - id: FL1
      name: Floor 1
      elevation: 0.0
      height: 3.0
grids:
  axes_x:
    "1": 0.0
    "2": 6.0
  axes_y:
    A: 0.0
    B: 6.0
materials:
  - id: CONCRETE
    name: Concrete C25/30
    category: Concrete
    unit_cost_ref: MAT-CONC
elements:
  - class: IfcSpace
    tag: SPACE-OFFICE
    name: Office Room
    placement:
      storey: FL1
      boundary:
        - ["1", "A"]
        - ["2", "A"]
        - ["2", "B"]
        - ["1", "B"]
    contains:
      - WORKING_DESK
""", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["fit", "-m", str(manifest_file)])
    assert result.exit_code == 0
    assert "2D Furniture Fit Solver Report" in result.output
    assert "SPACE-OFFICE" in result.output
    assert "PASS" in result.output
