"""
Unit tests for CAD/DXF ingestion assistant (debim.ingest) and CLI command.
"""

from pathlib import Path
import ezdxf
import pytest

from debim.ingest import ingest_dxf_file, parse_dxf_grid_and_columns
from debim.schema import load_manifest


def create_sample_grid_dxf(output_path: Path) -> Path:
    """Create a sample DXF drawing containing 2x2 grid lines, labels, and 4 rectangular columns."""
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # Millimeters
    msp = doc.modelspace()

    # Add S-COLS layer
    doc.layers.add("S-COLS", color=3)
    doc.layers.add("A-GRID", color=1)

    # Grid Lines in mm (0,0 to 4000, 4000) -> 0m to 4m
    # X Grid 1 (x=0) and X Grid 2 (x=4000)
    msp.add_line((0, 0), (0, 4000), dxfattribs={"layer": "A-GRID"})
    msp.add_line((4000, 0), (4000, 4000), dxfattribs={"layer": "A-GRID"})

    # Y Grid A (y=0) and Y Grid B (y=4000)
    msp.add_line((0, 0), (4000, 0), dxfattribs={"layer": "A-GRID"})
    msp.add_line((0, 4000), (4000, 4000), dxfattribs={"layer": "A-GRID"})

    # Grid Text Labels
    msp.add_text("1", dxfattribs={"insert": (0, -200)})
    msp.add_text("2", dxfattribs={"insert": (4000, -200)})
    msp.add_text("A", dxfattribs={"insert": (-200, 0)})
    msp.add_text("B", dxfattribs={"insert": (-200, 4000)})

    # Column 1 at (0, 0)
    pts1 = [(-100, -100), (100, -100), (100, 100), (-100, 100)]
    msp.add_lwpolyline(pts1, close=True, dxfattribs={"layer": "S-COLS"})

    # Column 2 at (4000, 0)
    pts2 = [(3900, -100), (4100, -100), (4100, 100), (3900, 100)]
    msp.add_lwpolyline(pts2, close=True, dxfattribs={"layer": "S-COLS"})

    # Column 3 at (0, 4000)
    pts3 = [(-100, 3900), (100, 3900), (100, 4100), (-100, 4100)]
    msp.add_lwpolyline(pts3, close=True, dxfattribs={"layer": "S-COLS"})

    # Column 4 at (4000, 4000)
    pts4 = [(3900, 3900), (4100, 3900), (4100, 4100), (3900, 4100)]
    msp.add_lwpolyline(pts4, close=True, dxfattribs={"layer": "S-COLS"})

    doc.saveas(output_path)
    return output_path


def test_parse_dxf_grid_and_columns(tmp_path: Path):
    dxf_file = create_sample_grid_dxf(tmp_path / "plan.dxf")
    parsed = parse_dxf_grid_and_columns(dxf_file)

    assert "axes_x" in parsed
    assert "axes_y" in parsed
    assert "columns" in parsed

    axes_x = parsed["axes_x"]
    axes_y = parsed["axes_y"]
    columns = parsed["columns"]

    assert len(axes_x) >= 2
    assert len(axes_y) >= 2
    assert len(columns) == 4

    # Verify column tags and grid placement
    tags = [c["tag"] for c in columns]
    assert "C1" in tags
    assert "C4" in tags


def test_ingest_dxf_file_output(tmp_path: Path):
    dxf_file = create_sample_grid_dxf(tmp_path / "drawing.dxf")
    out_dir = tmp_path / "output_debim"

    emitted_manifest_path = ingest_dxf_file(dxf_file, output_dir=out_dir)
    assert emitted_manifest_path.exists()
    assert emitted_manifest_path.name == "project.debim"

    # Validate generated manifest using load_manifest
    manifest = load_manifest(emitted_manifest_path)
    assert manifest.project.id == "PRJ-DRAWING"
    assert len(manifest.elements) == 4
    assert manifest.elements[0].class_ == "IfcColumn"


def test_cli_ingest_command(tmp_path: Path, monkeypatch):
    dxf_file = create_sample_grid_dxf(tmp_path / "cad_test.dxf")
    out_dir = tmp_path / "cli_out"

    from debim.cli import main

    main(["ingest", str(dxf_file), "--out", str(out_dir)])

    generated_file = out_dir / "project.debim"
    assert generated_file.exists()

    manifest = load_manifest(generated_file)
    assert len(manifest.elements) == 4
