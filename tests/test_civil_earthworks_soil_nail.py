"""
Unit tests for Slope Stabilization, Soil Nailing, and Rock Bolts (IfcEarthworksElement).
"""

import math
from pathlib import Path
import pytest

from debim.compiler import compile_to_ifc
from debim.qto import calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import (
    EarthworksPlacement,
    IfcEarthworksElement,
    ProjectManifest,
    SlopeStabilizationConfig,
)
from debim.viewer import generate_viewer_html


def test_earthworks_soil_nailing_schema_defaults():
    """Test schema instantiation and defaults for SOIL_NAILING and ROCK_BOLT."""
    elem1 = IfcEarthworksElement(
        tag="EW-NAIL-01",
        predefined_type="SOIL_NAILING",
        placement=EarthworksPlacement(storey="ST-1"),
        width=12.0,
        length=6.0,
        depth=0.10,
    )
    assert elem1.slope_stabilization is not None
    assert elem1.slope_stabilization.nail_length == 6.0
    assert elem1.slope_stabilization.spacing_x == 1.5
    assert elem1.slope_stabilization.spacing_y == 1.5
    assert elem1.slope_stabilization.inclination_deg == 15.0
    assert elem1.slope_stabilization.shotcrete_thickness == 0.10

    elem2 = IfcEarthworksElement(
        tag="EW-BOLT-01",
        predefined_type="ROCK_BOLT",
        placement=EarthworksPlacement(storey="ST-1"),
        width=10.0,
        length=5.0,
        depth=0.10,
        slope_stabilization=SlopeStabilizationConfig(
            nail_length=4.0,
            spacing_x=2.0,
            spacing_y=2.0,
            inclination_deg=20.0,
            shotcrete_thickness=0.15,
            hole_diameter=0.12,
        ),
    )
    assert elem2.slope_stabilization.nail_length == 4.0
    assert elem2.slope_stabilization.spacing_x == 2.0
    assert elem2.slope_stabilization.spacing_y == 2.0
    assert elem2.slope_stabilization.inclination_deg == 20.0
    assert elem2.slope_stabilization.shotcrete_thickness == 0.15
    assert elem2.slope_stabilization.hole_diameter == 0.12


def test_soil_nail_resolver_and_qto():
    """Test spatial resolution and QTO metrics calculation for slope stabilization."""
    data = {
        "project": {"id": "PROJ-CIVIL", "name": "Slope Stabilization Project"},
        "spatial_structure": {
            "storeys": [{"id": "ST-GROUND", "name": "Ground Level", "elevation": 0.0, "height": 4.0}]
        },
        "grids": {"axes_x": {"1": 0.0, "2": 10.0}, "axes_y": {"A": 0.0, "B": 10.0}},
        "materials": [],
        "elements": [
            {
                "tag": "EW-NAIL-SLOPE1",
                "class": "IfcEarthworksElement",
                "predefined_type": "SOIL_NAILING",
                "placement": {"storey": "ST-GROUND"},
                "width": 12.0,
                "length": 6.0,
                "depth": 0.10,
                "slope_stabilization": {
                    "nail_length": 6.0,
                    "spacing_x": 1.5,
                    "spacing_y": 1.5,
                    "inclination_deg": 15.0,
                    "shotcrete_thickness": 0.10,
                    "hole_diameter": 0.15,
                },
            }
        ],
    }

    manifest = ProjectManifest.model_validate(data)
    resolved = resolve_manifest(manifest)

    assert len(resolved.earthworks_elements) == 1
    ew = resolved.earthworks_elements[0]

    # Check grid resolution:
    # count_x = max(1, round(12.0 / 1.5)) = 8
    # count_y = max(1, round(6.0 / 1.5)) = 4
    # expected total count = 32
    assert ew.soil_nail_count == 32
    assert ew.facing_shotcrete_area == pytest.approx(12.0 * 6.0, abs=0.01)

    expected_drilling = 32 * 6.0
    assert ew.total_drilling_depth == pytest.approx(expected_drilling, abs=0.01)

    r_hole = 0.15 / 2.0
    expected_grout = 32 * (math.pi * r_hole * r_hole * 6.0)
    assert ew.grout_volume == pytest.approx(expected_grout, abs=0.01)

    # Validate 3D inclination of soil nails
    assert len(ew.soil_nails) == 32
    nail1 = ew.soil_nails[0]
    assert nail1["tag"] == "EW-NAIL-SLOPE1-NAIL-1"
    assert nail1["length"] == 6.0
    assert nail1["inclination_deg"] == 15.0

    s_pt = nail1["start_point"]
    e_pt = nail1["end_point"]
    dx = e_pt[0] - s_pt[0]
    dy = e_pt[1] - s_pt[1]
    dz = e_pt[2] - s_pt[2]
    # inclination 15 deg downwards along +Y
    assert dz == pytest.approx(-6.0 * math.sin(math.radians(15.0)), abs=0.01)
    assert dy == pytest.approx(6.0 * math.cos(math.radians(15.0)), abs=0.01)

    # QTO test
    qto = calculate_qto(resolved)

    assert qto.total_soil_nail_count == 32
    assert qto.total_drilling_depth == pytest.approx(expected_drilling, abs=0.01)
    assert qto.total_grout_volume == pytest.approx(expected_grout, abs=0.01)
    assert qto.total_facing_shotcrete_area == pytest.approx(72.0, abs=0.01)


def test_soil_nail_compiler_and_viewer(tmp_path: Path):
    """Test IFC export and 3D viewer generation for slope stabilization elements."""
    data = {
        "project": {"id": "PROJ-CIVIL", "name": "Slope Stabilization Project"},
        "spatial_structure": {
            "storeys": [{"id": "ST-GROUND", "name": "Ground Level", "elevation": 0.0, "height": 4.0}]
        },
        "grids": {"axes_x": {"1": 0.0, "2": 10.0}, "axes_y": {"A": 0.0, "B": 10.0}},
        "materials": [],
        "elements": [
            {
                "tag": "EW-BOLT-01",
                "class": "IfcEarthworksElement",
                "predefined_type": "ROCK_BOLT",
                "placement": {"storey": "ST-GROUND"},
                "width": 8.0,
                "length": 4.0,
                "depth": 0.10,
                "slope_stabilization": {
                    "nail_length": 5.0,
                    "spacing_x": 2.0,
                    "spacing_y": 2.0,
                    "inclination_deg": 10.0,
                    "shotcrete_thickness": 0.15,
                },
            }
        ],
    }

    manifest = ProjectManifest.model_validate(data)
    resolved = resolve_manifest(manifest)

    # Test IFC STEP physical file compiler (fallback mode)
    out_step = tmp_path / "model_soil_nail.ifc"
    compile_to_ifc(resolved, output_path=out_step, force_fallback=True)
    assert out_step.exists()

    step_text = out_step.read_text(encoding="utf-8")
    assert "IfcEarthworksElement.ROCK_BOLT" in step_text
    assert "IFCSWEPTDISKSOLID" in step_text

    # Test 3D Web Viewer generation
    html = generate_viewer_html(resolved)
    assert "IfcEarthworksElement" in html
    assert "soil_nail_count" in html
    assert "facing_shotcrete_area" in html
    assert "SOIL_NAILING" in html
