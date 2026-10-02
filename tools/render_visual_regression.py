"""
3D Visual Regression & Component-Level Render Comparator for debim.
Renders individual architectural/structural elements from original IFC vs debim (YAML/recompiled),
computes 3D Bounding Box IoU, Pixel Difference, and generates side-by-side visual diff reports.
"""

import argparse
from collections import Counter
import io
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import ifcopenshell
import ifcopenshell.geom

# Project root in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 console output on Windows
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from debim.importer import import_ifc_to_manifest
from debim.resolver import resolve_manifest
from debim.compiler import compile_to_ifc


def extract_all_resolved_meshes(resolved: Any) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """
    Extracts 3D meshes (vertices, faces) for all elements resolved by debim.
    These are the exact same geometric representations rendered by the 3D HTML Viewer.
    """
    import trimesh
    meshes = {}

    for col in resolved.columns:
        w = float(col.element.profile.width)
        d = float(col.element.profile.depth)
        h = float(col.height)
        m = trimesh.creation.box(extents=(w, d, h))
        meshes[col.tag] = (np.array(m.vertices, dtype=np.float64), np.array(m.faces, dtype=np.int32))

    for beam in resolved.beams:
        w = float(beam.element.profile.width)
        d = float(beam.element.profile.depth)
        l = float(beam.span_length)
        m = trimesh.creation.box(extents=(l, w, d))
        meshes[beam.tag] = (np.array(m.vertices, dtype=np.float64), np.array(m.faces, dtype=np.int32))

    for wall in resolved.walls:
        l = float(wall.length)
        th = float(wall.thickness)
        h = float(wall.height)
        m = trimesh.creation.box(extents=(l, th, h))
        meshes[wall.tag] = (np.array(m.vertices, dtype=np.float64), np.array(m.faces, dtype=np.int32))

        for child in wall.children:
            cw = float(child.width)
            ch = float(child.height)
            cth = float(wall.thickness * 1.05)
            cm = trimesh.creation.box(extents=(cw, cth, ch))
            meshes[child.tag] = (np.array(cm.vertices, dtype=np.float64), np.array(cm.faces, dtype=np.int32))

    for slab in resolved.slabs:
        th = float(slab.thickness)
        pts = np.array([[p[0], p[1]] for p in slab.polygon])
        if len(pts) >= 3:
            w = float(np.max(pts[:, 0]) - np.min(pts[:, 0]))
            d = float(np.max(pts[:, 1]) - np.min(pts[:, 1]))
            w = max(w, 0.5)
            d = max(d, 0.5)
            m = trimesh.creation.box(extents=(w, d, th))
            meshes[slab.tag] = (np.array(m.vertices, dtype=np.float64), np.array(m.faces, dtype=np.int32))

    for cov in resolved.coverings:
        th = float(cov.thickness) if cov.thickness else 0.05
        pts = np.array([[p[0], p[1]] for p in cov.polygon])
        if len(pts) >= 3:
            w = float(np.max(pts[:, 0]) - np.min(pts[:, 0]))
            d = float(np.max(pts[:, 1]) - np.min(pts[:, 1]))
            w = max(w, 0.5)
            d = max(d, 0.5)
            m = trimesh.creation.box(extents=(w, d, th))
            meshes[cov.tag] = (np.array(m.vertices, dtype=np.float64), np.array(m.faces, dtype=np.int32))

    for custom in resolved.custom_elements:
        if custom.dimensions:
            w = float(custom.dimensions.width)
            d = float(custom.dimensions.depth if custom.dimensions.depth is not None else w)
            h = float(custom.dimensions.height)
            m = trimesh.creation.box(extents=(w, d, h))
            meshes[custom.tag] = (np.array(m.vertices, dtype=np.float64), np.array(m.faces, dtype=np.int32))

    return meshes


def get_element_type_signature(elem: Any, cls_name: str) -> str:
    """
    Extracts a canonical variant/family signature for an IFC element
    to prevent testing hundreds of identical repeated components (e.g. pipe elbows, identical bolts).
    """
    import re

    type_name = None
    try:
        # Check IFC4 IsTypedBy or IFC2x3 IsDefinedBy
        if hasattr(elem, "IsTypedBy") and elem.IsTypedBy:
            for rel in elem.IsTypedBy:
                if hasattr(rel, "RelatingType") and rel.RelatingType and rel.RelatingType.Name:
                    type_name = rel.RelatingType.Name
                    break
        if not type_name and hasattr(elem, "IsDefinedBy") and elem.IsDefinedBy:
            for rel in elem.IsDefinedBy:
                if rel.is_a("IfcRelDefinesByType") and hasattr(rel, "RelatingType") and rel.RelatingType and rel.RelatingType.Name:
                    type_name = rel.RelatingType.Name
                    break
    except Exception:
        pass

    if type_name:
        return f"{cls_name}::{type_name}"

    # Check ObjectType
    obj_type = getattr(elem, "ObjectType", None)
    if obj_type and str(obj_type).strip():
        return f"{cls_name}::{str(obj_type).strip()}"

    # Clean Name: strip trailing instance IDs, Revit IDs, or numbered duplicates
    # e.g. "Basic Wall:Interior - 100mm:382910" -> "Basic Wall:Interior - 100mm"
    # e.g. "Tee - PVC - Sch 40:Standard [12345]" -> "Tee - PVC - Sch 40:Standard"
    name = elem.Name or ""
    if name:
        cleaned_name = re.sub(r'[:#]\d+$', '', name)
        cleaned_name = re.sub(r'\s+\[\d+\]$', '', cleaned_name)
        cleaned_name = re.sub(r'\.\d{3,}$', '', cleaned_name)
        cleaned_name = re.sub(r'_\d+$', '', cleaned_name)
        if cleaned_name.strip():
            return f"{cls_name}::{cleaned_name.strip()}"

    return f"{cls_name}::default"


def extract_mesh_from_element(elem: Any, settings: Any) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """
    Extracts 3D vertices (N, 3) and triangular faces (M, 3) from an IFC element.
    Returns None if element has no 3D geometry.
    """
    try:
        shape = ifcopenshell.geom.create_shape(settings, elem)
        verts_flat = shape.geometry.verts
        faces_flat = shape.geometry.faces
        if not verts_flat or not faces_flat:
            return None
        verts = np.array(verts_flat, dtype=np.float64).reshape(-1, 3)
        faces = np.array(faces_flat, dtype=np.int32).reshape(-1, 3)
        return verts, faces
    except Exception:
        return None


def compute_bounding_box(verts: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Returns min_bound, max_bound, and dimensions (w, d, h)."""
    min_b = np.min(verts, axis=0)
    max_b = np.max(verts, axis=0)
    dims = np.maximum(0.0, max_b - min_b)
    return min_b, max_b, dims


def compute_bbox_iou(min1: np.ndarray, max1: np.ndarray, min2: np.ndarray, max2: np.ndarray) -> float:
    """Computes 3D Axis-Aligned Bounding Box Intersection over Union (IoU)."""
    inter_min = np.maximum(min1, min2)
    inter_max = np.minimum(max1, max2)
    inter_dims = np.maximum(0.0, inter_max - inter_min)
    inter_vol = float(np.prod(inter_dims))

    vol1 = float(np.prod(np.maximum(0.0, max1 - min1)))
    vol2 = float(np.prod(np.maximum(0.0, max2 - min2)))
    union_vol = vol1 + vol2 - inter_vol

    if union_vol <= 1e-9:
        return 0.0
    return float(np.clip(inter_vol / union_vol, 0.0, 1.0))


def render_mesh_to_image(
    verts: np.ndarray,
    faces: np.ndarray,
    img_size: int = 300,
    elev: float = 30.0,
    azim: float = 45.0,
    color: str = "#38bdf8",
    edge_color: str = "#0369a1",
    center_and_normalize: bool = True,
) -> Image.Image:
    """
    Renders a 3D mesh to a PIL Image offscreen at a fixed viewpoint.
    """
    v = verts.copy()
    if center_and_normalize:
        min_b = np.min(v, axis=0)
        max_b = np.max(v, axis=0)
        center = (min_b + max_b) / 2.0
        v = v - center
        max_span = max(float(np.max(max_b - min_b)), 1e-3)
        v = v / (max_span / 1.6)

    fig = plt.figure(figsize=(img_size / 100, img_size / 100), dpi=100)
    ax = fig.add_subplot(111, projection="3d")
    ax.set_facecolor("#0f172a")  # Dark sleek slate background
    fig.patch.set_facecolor("#0f172a")

    mesh_collection = Poly3DCollection(
        v[faces],
        facecolors=color,
        edgecolors=edge_color,
        linewidths=0.5,
        alpha=0.85,
    )
    ax.add_collection3d(mesh_collection)

    bound = 1.0
    ax.set_xlim([-bound, bound])
    ax.set_ylim([-bound, bound])
    ax.set_zlim([-bound, bound])

    ax.view_init(elev=elev, azim=azim)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", pad_inches=0, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGB").resize((img_size, img_size))


def compare_images(img1: Image.Image, img2: Image.Image) -> Tuple[float, Image.Image]:
    """
    Compares two rendered images.
    Returns:
      - similarity_score (0.0 to 1.0, where 1.0 is exact match)
      - diff_image with discrepancies highlighted in bright red.
    """
    arr1 = np.array(img1, dtype=np.float32)
    arr2 = np.array(img2, dtype=np.float32)

    # Pixel absolute difference
    diff = np.abs(arr1 - arr2)
    diff_mag = np.mean(diff, axis=-1)  # (H, W)

    # Threshold for noticeable discrepancy
    mask = diff_mag > 25.0
    similarity = 1.0 - float(np.mean(mask))

    # Diff visualization: Grayscale background + Bright Red highlights
    gray_bg = np.dot(arr1[..., :3], [0.2989, 0.5870, 0.1140])
    diff_vis = np.zeros_like(arr1, dtype=np.uint8)
    diff_vis[..., 0] = (gray_bg * 0.4).astype(np.uint8)
    diff_vis[..., 1] = (gray_bg * 0.4).astype(np.uint8)
    diff_vis[..., 2] = (gray_bg * 0.4).astype(np.uint8)

    # Highlight diff in neon red (#ef4444)
    diff_vis[mask] = [239, 68, 68]

    return similarity, Image.fromarray(diff_vis)


def generate_composite_panel(
    orig_img: Image.Image,
    recomp_img: Image.Image,
    diff_img: Image.Image,
    tag: str,
    cls_name: str,
    iou_score: float,
    pixel_score: float,
) -> Image.Image:
    """
    Creates a 3-panel comparison image with header annotations.
    """
    w, h = orig_img.size
    banner_h = 40
    total_w = w * 3 + 20
    total_h = h + banner_h

    canvas = Image.new("RGB", (total_w, total_h), "#0f172a")
    canvas.paste(orig_img, (0, banner_h))
    canvas.paste(recomp_img, (w + 10, banner_h))
    canvas.paste(diff_img, (w * 2 + 20, banner_h))

    # Simple canvas labels (top of each panel)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 12), f"Original: {tag} ({cls_name})", fill="#38bdf8")
    draw.text((w + 20, 12), f"debim Recompiled (IoU: {iou_score*100:.1f}%)", fill="#22c55e")
    diff_color = "#22c55e" if pixel_score > 0.90 else "#ef4444"
    draw.text((w * 2 + 30, 12), f"Diff Map (Match: {pixel_score*100:.1f}%)", fill=diff_color)

    return canvas


def run_visual_regression(
    ifc_path: Path,
    output_dir: Path,
    max_elements_per_type: int = 3,
    limit_total: int = 15,
    save_images: bool = True,
    save_passes_sample_limit: int = 2,
    dedup_by_variant: bool = True,
    max_samples_per_variant: int = 2,
) -> Dict[str, Any]:
    """
    Runs component-level visual regression between Original IFC and debim Recompiled model.
    Supports variant deduplication to prevent high-frequency repeated parts (e.g. pipe fittings)
    from causing extreme slowdowns and artificial accuracy inflation.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[3D-VERIFY] Starting Visual Regression: {ifc_path.name}")
    t0 = time.time()

    # 1. Compile through debim roundtrip and resolve 3D geometry
    print("  [1/4] Importing IFC to debim YAML & Resolving 3D Meshes...")
    try:
        manifest = import_ifc_to_manifest(ifc_path)
        resolved = resolve_manifest(manifest)
        debim_meshes = extract_all_resolved_meshes(resolved)
    except Exception as e:
        print(f"  [WARN] debim import/resolve skipped for {ifc_path.name}: {e}")
        return {
            "total_tested": 0,
            "pass_count": 0,
            "avg_match": 0.0,
            "macro_avg_match": 0.0,
            "structural_match": None,
            "mep_match": None,
            "avg_iou": 0.0,
            "macro_avg_iou": 0.0,
            "class_summary": {},
            "report_path": None,
            "duration": round(time.time() - t0, 2),
            "status": "IMPORT_ERROR",
            "error": str(e),
        }

    # 2. Open original IFC model
    try:
        orig_model = ifcopenshell.open(str(ifc_path))
        geom_settings = ifcopenshell.geom.settings()
    except Exception as e:
        print(f"  [WARN] IfcOpenShell failed to open {ifc_path.name}: {e}")
        return {
            "total_tested": 0,
            "pass_count": 0,
            "avg_match": 0.0,
            "macro_avg_match": 0.0,
            "structural_match": None,
            "mep_match": None,
            "avg_iou": 0.0,
            "macro_avg_iou": 0.0,
            "class_summary": {},
            "report_path": None,
            "duration": round(time.time() - t0, 2),
            "status": "OPEN_ERROR",
            "error": str(e),
        }

    # 3. Categorize original elements
    orig_elements = [e for e in orig_model.by_type("IfcElement") if not e.is_a("IfcOpeningElement")]
    by_category: Dict[str, List[Any]] = {}
    for e in orig_elements:
        t = e.is_a()
        if t == "IfcWallStandardCase":
            t = "IfcWall"
        by_category.setdefault(t, []).append(e)

    tested_count = 0
    passes_saved_per_class: Dict[str, int] = {}
    results: List[Dict[str, Any]] = []

    print(f"  [2/4] Testing isolated element shapes across {len(by_category)} categories (dedup_by_variant={dedup_by_variant})...")
    for cls_name, elems in by_category.items():
        if dedup_by_variant:
            variant_groups: Dict[str, List[Any]] = {}
            for e in elems:
                sig = get_element_type_signature(e, cls_name)
                variant_groups.setdefault(sig, []).append(e)

            sample_elems = []
            for sig, var_elems in variant_groups.items():
                sample_elems.extend(var_elems[:max_samples_per_variant])
                if max_elements_per_type and len(sample_elems) >= max_elements_per_type:
                    sample_elems = sample_elems[:max_elements_per_type]
                    break
        else:
            sample_elems = elems[:max_elements_per_type]

        for elem in sample_elems:
            if limit_total and tested_count >= limit_total:
                break

            tag = elem.Name or f"{cls_name}-{elem.GlobalId[:6]}"

            # Find matching debim mesh by tag or prefix
            debim_mesh = debim_meshes.get(tag)
            if not debim_mesh:
                # Fuzzy fallback by matching ID or class
                for k, v in debim_meshes.items():
                    if tag in k or k in tag or elem.GlobalId[:8] in k:
                        debim_mesh = v
                        break

            try:
                orig_mesh = extract_mesh_from_element(elem, geom_settings)
            except Exception:
                orig_mesh = None

            recomp_mesh = debim_mesh

            if orig_mesh is None:
                continue

            tested_count += 1
            o_verts, o_faces = orig_mesh

            # Render original
            img_orig = render_mesh_to_image(o_verts, o_faces, color="#38bdf8", edge_color="#0284c7")

            if recomp_mesh is not None:
                r_verts, r_faces = recomp_mesh
                img_recomp = render_mesh_to_image(r_verts, r_faces, color="#4ade80", edge_color="#16a34a")

                # Bounding Box IoU
                min1, max1, _ = compute_bounding_box(o_verts)
                min2, max2, _ = compute_bounding_box(r_verts)
                iou_score = compute_bbox_iou(min1, max1, min2, max2)

                # Pixel match & diff
                pixel_score, img_diff = compare_images(img_orig, img_recomp)
            else:
                img_recomp = Image.new("RGB", (300, 300), "#1e293b")
                img_diff = Image.new("RGB", (300, 300), "#7f1d1d")
                iou_score = 0.0
                pixel_score = 0.0

            status = "PASS" if pixel_score >= 0.85 else ("NEEDS_REVIEW" if pixel_score >= 0.60 else "FAIL")
            saved_img_rel = None

            if save_images:
                # Save all non-pass images; for pass images, save up to sample limit per class
                if status != "PASS" or passes_saved_per_class.get(cls_name, 0) < save_passes_sample_limit:
                    composite = generate_composite_panel(
                        img_orig, img_recomp, img_diff, tag, cls_name, iou_score, pixel_score
                    )
                    safe_name = f"{cls_name}_{tested_count:02d}_{tag}".replace(":", "_").replace("/", "_").replace(" ", "_")
                    img_filename = f"{safe_name}.png"
                    composite.save(images_dir / img_filename)
                    saved_img_rel = f"images/{img_filename}"
                    if status == "PASS":
                        passes_saved_per_class[cls_name] = passes_saved_per_class.get(cls_name, 0) + 1

            results.append({
                "tag": tag,
                "class": cls_name,
                "variant": get_element_type_signature(elem, cls_name),
                "iou": round(iou_score * 100, 1),
                "pixel_match": round(pixel_score * 100, 1),
                "status": status,
                "image": saved_img_rel or "",
            })
            print(f"    - [{status}] {cls_name:18} | {tag:20} | IoU: {iou_score*100:5.1f}% | Match: {pixel_score*100:5.1f}%")

    # 4. Calculate Balanced Macro & Micro Metrics
    micro_avg_match = float(np.mean([r["pixel_match"] for r in results])) if results else 0.0
    micro_avg_iou = float(np.mean([r["iou"] for r in results])) if results else 0.0
    pass_count = sum(1 for r in results if r["status"] == "PASS")

    class_scores: Dict[str, List[float]] = {}
    class_ious: Dict[str, List[float]] = {}
    for r in results:
        class_scores.setdefault(r["class"], []).append(r["pixel_match"])
        class_ious.setdefault(r["class"], []).append(r["iou"])

    class_summary: Dict[str, Dict[str, Any]] = {}
    structural_classes = {"IfcWall", "IfcColumn", "IfcBeam", "IfcSlab", "IfcFooting", "IfcMember", "IfcPlate"}
    mep_classes = {"IfcPipeSegment", "IfcPipeFitting", "IfcDuctSegment", "IfcDuctFitting", "IfcDistributionPort", "IfcFlowTerminal"}

    struct_matches: List[float] = []
    mep_matches: List[float] = []

    for cls, scores in class_scores.items():
        cls_avg = float(np.mean(scores))
        cls_iou = float(np.mean(class_ious.get(cls, [0.0])))
        class_summary[cls] = {
            "count": len(scores),
            "avg_match": round(cls_avg, 1),
            "avg_iou": round(cls_iou, 1),
        }
        if cls in structural_classes:
            struct_matches.append(cls_avg)
        elif cls in mep_classes:
            mep_matches.append(cls_avg)

    macro_avg_match = float(np.mean([cs["avg_match"] for cs in class_summary.values()])) if class_summary else 0.0
    macro_avg_iou = float(np.mean([cs["avg_iou"] for cs in class_summary.values()])) if class_summary else 0.0
    structural_match = round(float(np.mean(struct_matches)), 1) if struct_matches else None
    mep_match = round(float(np.mean(mep_matches)), 1) if mep_matches else None

    # 5. Generate Markdown Visual Report
    print("  [3/4] Generating Markdown Visual Regression Report...")
    report_md_path = output_dir / "visual_regression_report.md"

    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(f"# 📸 debim 3D Visual Regression Report: `{ifc_path.name}`\n\n")
        f.write(f"- **Total Components Tested:** {len(results)}\n")
        f.write(f"- **Pass Rate (>= 85% match):** {pass_count}/{len(results)} ({(pass_count/len(results)*100 if results else 0):.1f}%)\n")
        f.write(f"- **Macro Average Match (Unweighted Class Mean):** {macro_avg_match:.1f}%\n")
        f.write(f"- **Micro Average Match (All Samples):** {micro_avg_match:.1f}%\n")
        if structural_match is not None:
            f.write(f"- **Structural Elements Match:** {structural_match}%\n")
        if mep_match is not None:
            f.write(f"- **MEP Elements Match:** {mep_match}%\n")
        f.write(f"- **Execution Duration:** {time.time() - t0:.2f} seconds\n\n")

        f.write("## Category Breakdown\n\n")
        f.write("| Element Class | Tested Count | Mean Match (%) | Mean IoU (%) |\n")
        f.write("|---|---|---|---|\n")
        for cls, cs in class_summary.items():
            f.write(f"| `{cls}` | {cs['count']} | {cs['avg_match']}% | {cs['avg_iou']}% |\n")
        f.write("\n")

        f.write("## Component Comparison Matrix\n\n")
        f.write("| Element Class | Tag | Variant Signature | 3D BBox IoU | Visual Match | Status | Visual Inspection |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for r in results:
            status_icon = "🟢" if r["status"] == "PASS" else ("🟡" if r["status"] == "NEEDS_REVIEW" else "🔴")
            f.write(f"| {r['class']} | `{r['tag']}` | `{r.get('variant', '-')}` | {r['iou']}% | {r['pixel_match']}% | {status_icon} {r['status']} | ![{r['tag']}]({r['image']}) |\n")

    print(f"  [4/4] Done! Report written to: {report_md_path}\n")
    return {
        "total_tested": len(results),
        "pass_count": pass_count,
        "avg_match": round(micro_avg_match, 1),
        "macro_avg_match": round(macro_avg_match, 1),
        "structural_match": structural_match,
        "mep_match": mep_match,
        "avg_iou": round(micro_avg_iou, 1),
        "macro_avg_iou": round(macro_avg_iou, 1),
        "class_summary": class_summary,
        "report_path": str(report_md_path),
        "duration": round(time.time() - t0, 2),
        "status": "PASS" if (pass_count == len(results) and len(results) > 0) else ("PARTIAL" if len(results) > 0 else "NO_ELEMENTS"),
    }


def main():
    parser = argparse.ArgumentParser(description="debim 3D Visual Regression Comparator")
    parser.add_argument("--ifc", type=str, default=None, help="Path to a single IFC file")
    parser.add_argument("--dir", type=str, default=None, help="Path to directory containing multiple IFC files")
    parser.add_argument("--output", type=str, default="dist/visual_regression", help="Output directory for reports & images")
    parser.add_argument("--max-per-type", type=int, default=2, help="Max components per element class")
    parser.add_argument("--limit", type=int, default=10, help="Total component test limit per model")
    parser.add_argument("--dedup", action="store_true", default=True, help="Enable variant deduplication to prevent repetitive sampling")
    parser.add_argument("--no-dedup", action="store_false", dest="dedup", help="Disable variant deduplication")
    parser.add_argument("--max-per-variant", type=int, default=2, help="Max components per unique type variant")
    args = parser.parse_args()

    out_dir = Path(args.output)
    ifc_files: List[Path] = []

    if args.dir:
        dir_p = Path(args.dir)
        if not dir_p.exists():
            print(f"Error: Directory not found at {dir_p}")
            sys.exit(1)
        ifc_files = sorted(list(dir_p.glob("*.ifc")) + list(dir_p.glob("**/*.ifc")))
        if not ifc_files:
            print(f"Error: No .ifc files found in {dir_p}")
            sys.exit(1)
    elif args.ifc:
        ifc_path = Path(args.ifc)
        if not ifc_path.exists():
            print(f"Error: IFC file not found at {ifc_path}")
            sys.exit(1)
        ifc_files = [ifc_path]
    else:
        # Default to fixtures if neither specified
        default_file = Path("tests/fixtures/Duplex_A_20110907.ifc")
        if default_file.exists():
            ifc_files = [default_file]
        else:
            print("Error: Please provide --ifc or --dir")
            sys.exit(1)

    print(f"\n[BATCH] Running debim 3D Visual Regression across {len(ifc_files)} IFC models (dedup={args.dedup})...")
    summary_results = []
    for idx, f in enumerate(ifc_files, 1):
        print(f"\n[{idx}/{len(ifc_files)}] Processing: {f.name}")
        model_out = out_dir if len(ifc_files) == 1 else (out_dir / f.stem)
        try:
            stat = run_visual_regression(
                ifc_path=f,
                output_dir=model_out,
                max_elements_per_type=args.max_per_type,
                limit_total=args.limit,
                dedup_by_variant=args.dedup,
                max_samples_per_variant=args.max_per_variant,
            )
            summary_results.append({"name": f.name, **stat})
        except Exception as e:
            print(f"  [ERROR] Failed processing {f.name}: {e}")

    if len(ifc_files) > 1:
        # Generate Aggregated Batch Report
        batch_report_path = out_dir / "batch_visual_regression_summary.md"
        total_comps = sum(s.get("total_tested", 0) for s in summary_results)
        total_passed = sum(s.get("pass_count", 0) for s in summary_results)
        macro_score = np.mean([s.get("macro_avg_match", 0) for s in summary_results]) if summary_results else 0.0
        micro_score = np.mean([s.get("avg_match", 0) for s in summary_results]) if summary_results else 0.0

        with open(batch_report_path, "w", encoding="utf-8") as f:
            f.write("# debim Batch 3D Visual Regression Summary\n\n")
            f.write(f"- **Total IFC Models Evaluated:** {len(summary_results)}/{len(ifc_files)}\n")
            f.write(f"- **Total 3D Components Tested:** {total_comps}\n")
            f.write(f"- **Overall Pass Rate:** {total_passed}/{total_comps} ({(total_passed/total_comps*100 if total_comps else 0):.1f}%)\n")
            f.write(f"- **Macro Average Match (Balanced Across Classes):** {macro_score:.1f}%\n")
            f.write(f"- **Micro Average Match (All Elements):** {micro_score:.1f}%\n\n")
            f.write("| Model Name | Tested | Passed | Macro Match (%) | Micro Match (%) | Structural (%) | MEP (%) | Detailed Report |\n")
            f.write("|---|---|---|---|---|---|---|---|\n")
            for s in summary_results:
                struct_str = f"{s.get('structural_match')}%" if s.get('structural_match') is not None else "N/A"
                mep_str = f"{s.get('mep_match')}%" if s.get('mep_match') is not None else "N/A"
                f.write(f"| `{s['name']}` | {s.get('total_tested', 0)} | {s.get('pass_count', 0)} | {s.get('macro_avg_match', 0):.1f}% | {s.get('avg_match', 0):.1f}% | {struct_str} | {mep_str} | [View Report]({s['name']}/visual_regression_report.md) |\n")

        print(f"\n[DONE] Batch Visual Regression Complete! Summary written to: {batch_report_path}")


if __name__ == "__main__":
    main()
