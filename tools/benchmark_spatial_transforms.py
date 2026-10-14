from __future__ import annotations

"""
Automated Visual Transformation and Sizing Benchmark for debim Class Directory.
Tests spatial positioning (X, Y, Z), Y-elevation ground plane rest alignment,
rotation invariance (Yaw), and parametric scaling fidelity across all 143 IFC classes.
"""

import argparse
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from playwright.sync_api import sync_playwright

# Project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from debim.docs import export_class_directory


# Representative element classes for visual snapshots across 4 disciplines
REPRESENTATIVE_CLASSES = [
    # Structure
    "IfcColumn",
    "IfcBeam",
    "IfcSlab",
    # Architecture
    "IfcWall",
    "IfcDoor",
    "IfcWindow",
    "IfcRoof",
    "IfcStair",
    # MEP
    "IfcPump",
    "IfcDuctSegment",
    "IfcAirTerminal",
    "IfcLightFixture",
    # Civil
    "IfcBridge",
    "IfcRoad",
    "IfcMarineFacility",
    "IfcRailway",
]


def run_spatial_transform_benchmark(
    output_dir: Path,
    headless: bool = True,
    save_snapshots: bool = True,
    classes_to_test: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Executes automated transformation and sizing benchmark across all 143 IFC classes using Playwright.
    """
    t0 = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshots_dir = output_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    # 1. Export HTML file
    html_path = output_dir / "directory_benchmark.html"
    print(f"\n[BENCHMARK] Generating Class Directory HTML at {html_path}...")
    export_class_directory(html_path)

    report_data: List[Dict[str, Any]] = []
    console_errors: List[str] = []
    page_errors: List[str] = []

    print("[BENCHMARK] Launching Playwright browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        file_url = f"file://{html_path.resolve()}"
        page.goto(file_url, wait_until="load")

        # Wait for scene initialization and classesData
        page.wait_for_function("typeof classesData !== 'undefined' && classesData.length > 0")

        total_classes = page.evaluate("classesData.length")
        print(f"[BENCHMARK] Total classes detected: {total_classes}")

        all_classes = page.evaluate("classesData.map(c => ({ class_name: c.class_name, discipline: c.discipline }))")

        for idx, cls_info in enumerate(all_classes):
            cls_name = cls_info["class_name"]
            discipline = cls_info.get("discipline", "Unknown")

            if classes_to_test and cls_name not in classes_to_test and cls_name.lower() not in [c.lower() for c in classes_to_test]:
                continue

            # Select class
            page.evaluate(f"selectClass({idx})")

            # ------------------------------------------------------------------
            # Test 1: Default Ground Plane Rest Verification (PosY = 0)
            # ------------------------------------------------------------------
            ground_res = page.evaluate("""() => {
                if (!currentMesh) return null;
                const bbox = new THREE.Box3().setFromObject(currentMesh);
                return {
                    minY: bbox.min.y,
                    maxY: bbox.max.y,
                    height: bbox.max.y - bbox.min.y,
                    centerX: (bbox.min.x + bbox.max.x) / 2,
                    centerZ: (bbox.min.z + bbox.max.z) / 2,
                    posY: currentMesh.position.y
                };
            }""")

            if not ground_res:
                report_data.append({
                    "class_name": cls_name,
                    "discipline": discipline,
                    "status": "FAIL",
                    "error": "currentMesh is null",
                    "ground_min_y": None,
                    "elev_offset_pass": False,
                    "yaw_rot_pass": False,
                    "scale_pass": False,
                })
                continue

            ground_min_y = ground_res["minY"]
            orig_centerX = ground_res["centerX"]
            orig_centerZ = ground_res["centerZ"]
            orig_height = ground_res["height"]

            ground_pass = abs(ground_min_y - 0.0) < 0.05

            # ------------------------------------------------------------------
            # Test 2: Elevation Offset Verification (+2.0m)
            # ------------------------------------------------------------------
            page.evaluate("""() => {
                document.getElementById('pos-y-num').value = '2.0';
                applyTransform();
            }""")

            elev_res = page.evaluate("""() => {
                if (!currentMesh) return null;
                const bbox = new THREE.Box3().setFromObject(currentMesh);
                return {
                    minY: bbox.min.y,
                    centerX: (bbox.min.x + bbox.max.x) / 2,
                    centerZ: (bbox.min.z + bbox.max.z) / 2,
                    meshPosY: currentMesh.position.y
                };
            }""")

            elev_pass = False
            if elev_res:
                elev_min_y = elev_res["minY"]
                elev_centerX = elev_res["centerX"]
                elev_centerZ = elev_res["centerZ"]
                # Assert Y shifted by ~2.0 and X, Z center unshifted
                elev_pass = (
                    abs(elev_min_y - 2.0) < 0.05
                    and abs(elev_centerX - orig_centerX) < 0.02
                    and abs(elev_centerZ - orig_centerZ) < 0.02
                )

            # ------------------------------------------------------------------
            # Test 3: Rotation Invariance (90° Yaw)
            # ------------------------------------------------------------------
            page.evaluate("""() => {
                document.getElementById('pos-y-num').value = '0.0';
                document.getElementById('rot-y-num').value = '90';
                applyTransform();
            }""")

            rot_res = page.evaluate("""() => {
                if (!currentMesh) return null;
                const bbox = new THREE.Box3().setFromObject(currentMesh);
                return {
                    minY: bbox.min.y,
                    centerX: (bbox.min.x + bbox.max.x) / 2,
                    centerZ: (bbox.min.z + bbox.max.z) / 2,
                    rotY: currentMesh.rotation.y
                };
            }""")

            yaw_pass = False
            if rot_res:
                # Ground rest preserved & centroid preserved
                yaw_pass = (
                    abs(rot_res["minY"] - 0.0) < 0.05
                    and abs(rot_res["centerX"] - orig_centerX) < 0.05
                    and abs(rot_res["centerZ"] - orig_centerZ) < 0.05
                    and abs(rot_res["rotY"] - math.pi / 2) < 0.01
                )

            # ------------------------------------------------------------------
            # Test 4: Parametric Scaling Verification (Scale H = 2.0x, Scale W = 1.5x)
            # ------------------------------------------------------------------
            page.evaluate("""() => {
                resetTransform();
                document.getElementById('scale-h-num').value = '2.0';
                document.getElementById('scale-w-num').value = '1.5';
                applyTransform();
            }""")

            scale_res = page.evaluate("""() => {
                if (!currentMesh) return null;
                const bbox = new THREE.Box3().setFromObject(currentMesh);
                return {
                    minY: bbox.min.y,
                    height: bbox.max.y - bbox.min.y,
                    hasEdges: !!edgesGroup && edgesGroup.children.length > 0,
                    hasBBox: !bboxHelper || bboxHelper.visible !== false
                };
            }""")

            scale_pass = False
            if scale_res:
                scaled_min_y = scale_res["minY"]
                scaled_height = scale_res["height"]
                # Height should scale up (~2x) and ground min Y stays at 0
                scale_pass = (
                    abs(scaled_min_y - 0.0) < 0.05
                    and scaled_height > orig_height * 1.2
                    and scale_res["hasEdges"]
                )

            # Reset transform back to default
            page.evaluate("resetTransform()")

            overall_class_pass = ground_pass and elev_pass and yaw_pass and scale_pass

            # Save snapshot for representative classes
            snapshot_path_rel = None
            if save_snapshots and cls_name in REPRESENTATIVE_CLASSES:
                snap_filename = f"{cls_name}_transformed.png"
                snap_file = snapshots_dir / snap_filename
                canvas_elem = page.query_selector("#canvas-3d")
                if canvas_elem:
                    canvas_elem.screenshot(path=str(snap_file))
                    snapshot_path_rel = f"snapshots/{snap_filename}"

            report_data.append({
                "class_name": cls_name,
                "discipline": discipline,
                "status": "PASS" if overall_class_pass else "FAIL",
                "ground_min_y": round(ground_min_y, 4),
                "ground_pass": ground_pass,
                "elev_offset_pass": elev_pass,
                "yaw_rot_pass": yaw_pass,
                "scale_pass": scale_pass,
                "snapshot": snapshot_path_rel or "",
            })

            status_icon = "🟢" if overall_class_pass else "🔴"
            print(f"  [{idx+1:03d}/{total_classes:03d}] {status_icon} {cls_name:30} | Ground: {ground_min_y:+.3f}m | Elev: {elev_pass} | Yaw: {yaw_pass} | Scale: {scale_pass}")

        browser.close()

    # 2. Compute Summary Metrics
    total_tested = len(report_data)
    total_passed = sum(1 for r in report_data if r["status"] == "PASS")
    ground_passes = sum(1 for r in report_data if r.get("ground_pass"))
    elev_passes = sum(1 for r in report_data if r.get("elev_offset_pass"))
    yaw_passes = sum(1 for r in report_data if r.get("yaw_rot_pass"))
    scale_passes = sum(1 for r in report_data if r.get("scale_pass"))

    duration = round(time.time() - t0, 2)

    # 3. Generate Markdown Summary Report
    report_md_path = output_dir / "spatial_transforms_report.md"
    print(f"\n[BENCHMARK] Writing Markdown report to {report_md_path}...")

    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write("# 📐 debim 3D Spatial Transformation & Sizing Benchmark Report\n\n")
        f.write(f"- **Total IFC Element Classes Evaluated:** {total_tested}\n")
        f.write(f"- **Overall Pass Rate:** {total_passed}/{total_tested} ({(total_passed/total_tested*100 if total_tested else 0):.1f}%)\n")
        f.write(f"- **Ground Plane Alignment Pass Rate (PosY = 0):** {ground_passes}/{total_tested} ({(ground_passes/total_tested*100 if total_tested else 0):.1f}%)\n")
        f.write(f"- **Elevation Offset Fidelity (+2.0m):** {elev_passes}/{total_tested} ({(elev_passes/total_tested*100 if total_tested else 0):.1f}%)\n")
        f.write(f"- **Yaw Rotation Invariance (90°):** {yaw_passes}/{total_tested} ({(yaw_passes/total_tested*100 if total_tested else 0):.1f}%)\n")
        f.write(f"- **Parametric Scaling Fidelity:** {scale_passes}/{total_tested} ({(scale_passes/total_tested*100 if total_tested else 0):.1f}%)\n")
        f.write(f"- **Page/Console Errors:** {len(page_errors)} page errors, {len(console_errors)} console errors\n")
        f.write(f"- **Benchmark Duration:** {duration} seconds\n\n")

        f.write("## Discipline Breakdown\n\n")
        f.write("| Discipline | Tested Classes | Overall Pass | Ground Rest | Elev Offset | Yaw Rotation | Parametric Scaling |\n")
        f.write("|---|---|---|---|---|---|---|\n")

        disciplines = ["Structure", "Architecture", "MEP", "Civil"]
        for disc in disciplines:
            disc_rows = [r for r in report_data if r["discipline"] == disc]
            if not disc_rows:
                continue
            cnt = len(disc_rows)
            p_tot = sum(1 for r in disc_rows if r["status"] == "PASS")
            p_grd = sum(1 for r in disc_rows if r.get("ground_pass"))
            p_elv = sum(1 for r in disc_rows if r.get("elev_offset_pass"))
            p_yaw = sum(1 for r in disc_rows if r.get("yaw_rot_pass"))
            p_scl = sum(1 for r in disc_rows if r.get("scale_pass"))
            f.write(f"| **{disc}** | {cnt} | {p_tot}/{cnt} | {p_grd}/{cnt} | {p_elv}/{cnt} | {p_yaw}/{cnt} | {p_scl}/{cnt} |\n")
        f.write("\n")

        f.write("## Representative Class Snapshots\n\n")
        f.write("| Class Name | Discipline | Ground Y | Status | Visual Snapshot |\n")
        f.write("|---|---|---|---|---|\n")
        for r in report_data:
            if r["class_name"] in REPRESENTATIVE_CLASSES and r["snapshot"]:
                icon = "🟢" if r["status"] == "PASS" else "🔴"
                f.write(f"| `{r['class_name']}` | {r['discipline']} | `{r['ground_min_y']}m` | {icon} {r['status']} | ![{r['class_name']}]({r['snapshot']}) |\n")
        f.write("\n")

        f.write("## Full 143 IFC Class Results Matrix\n\n")
        f.write("| Index | Class Name | Discipline | Ground Y (m) | Ground Rest | Elev Offset | Yaw Rot | Scaling | Status |\n")
        f.write("|---|---|---|---|---|---|---|---|---|\n")
        for i, r in enumerate(report_data, 1):
            icon = "🟢" if r["status"] == "PASS" else "🔴"
            grd_icon = "✅" if r.get("ground_pass") else "❌"
            elv_icon = "✅" if r.get("elev_offset_pass") else "❌"
            yaw_icon = "✅" if r.get("yaw_rot_pass") else "❌"
            scl_icon = "✅" if r.get("scale_pass") else "❌"
            f.write(f"| {i} | `{r['class_name']}` | {r['discipline']} | `{r['ground_min_y']}` | {grd_icon} | {elv_icon} | {yaw_icon} | {scl_icon} | {icon} {r['status']} |\n")

    print(f"[BENCHMARK] Benchmark complete in {duration}s! Overall pass: {total_passed}/{total_tested}")

    return {
        "total_tested": total_tested,
        "total_passed": total_passed,
        "ground_passes": ground_passes,
        "elev_passes": elev_passes,
        "yaw_passes": yaw_passes,
        "scale_passes": scale_passes,
        "duration": duration,
        "report_path": str(report_md_path),
        "data": report_data,
    }


def main():
    parser = argparse.ArgumentParser(description="debim Spatial Transform and Sizing Benchmark")
    parser.add_argument("--output", type=str, default="dist/spatial_transforms", help="Output directory")
    parser.add_argument("--no-headless", action="store_false", dest="headless", help="Run with visible browser window")
    parser.add_argument("--no-snapshots", action="store_false", dest="snapshots", help="Disable taking Playwright snapshots")
    parser.add_argument("--class", dest="target_class", type=str, default=None, help="Filter benchmark to specific element class")
    args = parser.parse_args()

    classes_to_test = [args.target_class] if args.target_class else None
    run_spatial_transform_benchmark(
        output_dir=Path(args.output),
        headless=args.headless,
        save_snapshots=args.snapshots,
        classes_to_test=classes_to_test,
    )


if __name__ == "__main__":
    main()
