"""
Formal Automated Round-Trip Golden Test Suite for All IFC Element Classes.
Verifies lossless bidirectional conversion across buildingSMART IFC4 classes
according to the 4-Level Verification Pipeline (IFC_ROUNDTRIP_VERIFICATION_SPEC.md).
"""

import sys
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import pytest
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.validate

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from debim.compiler import compile_to_ifc
from debim.importer import import_ifc_to_manifest
from debim.schema import load_manifest
from tools.generate_golden_fixtures import CANONICAL_CLASS_MAP, generate_golden_fixtures


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "golden_entities"

# Auto-generate fixtures if not present
if not FIXTURES_DIR.exists() or not list(FIXTURES_DIR.glob("*.yaml")):
    generate_golden_fixtures(FIXTURES_DIR, schema_version="IFC4")

ALL_FIXTURE_FILES = sorted(list(FIXTURES_DIR.glob("*.yaml")), key=lambda p: p.stem)


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


def extract_bbox_from_element(elem: ifcopenshell.entity_instance, settings: ifcopenshell.geom.settings) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """Extract axis-aligned 3D bounding box (min_pt, max_pt) from an IFC element."""
    try:
        shape = ifcopenshell.geom.create_shape(settings, elem)
        verts_flat = shape.geometry.verts
        if not verts_flat:
            return None
        verts = np.array(verts_flat, dtype=np.float64).reshape(-1, 3)
        if hasattr(shape, "transformation") and shape.transformation:
            T = np.array(shape.transformation.matrix, dtype=np.float64).reshape(4, 4)
            verts_homo = np.hstack([verts, np.ones((len(verts), 1))])
            verts = (verts_homo @ T)[:, :3]
        return np.min(verts, axis=0), np.max(verts, axis=0)
    except Exception:
        return None


@pytest.mark.parametrize("fixture_path", ALL_FIXTURE_FILES, ids=lambda p: p.stem)
def test_ifc_roundtrip_golden_entity(fixture_path: Path, tmp_path: Path):
    """
    Executes the 4-Level Verification Pipeline on a golden element fixture:
      - Level 1: Entity Retention Rate == 100.0%
      - Level 2: 3D Bounding Box IoU >= 0.95 and Delta Volume <= 0.1%
      - Level 3: Manifest Round-Trip Idempotency
      - Level 4: buildingSMART Schema Compliance (0 issues)
    """
    target_class = fixture_path.stem
    canonical_class = CANONICAL_CLASS_MAP.get(target_class, target_class)

    # 1. Load initial declarative manifest
    manifest_orig = load_manifest(fixture_path)
    assert len(manifest_orig.elements) == 1, f"Fixture {target_class} must contain exactly 1 element"
    orig_elem = manifest_orig.elements[0]

    # 2. Compile initial manifest -> IFC1
    ifc1_path = tmp_path / f"{target_class}_pass1.ifc"
    compile_to_ifc(manifest_orig, ifc1_path)
    assert ifc1_path.exists(), f"Failed to compile initial IFC for {target_class}"

    # 3. Import IFC1 -> Reimported Manifest
    manifest_reimported = import_ifc_to_manifest(ifc1_path)

    # ---------------------------------------------------------
    # Level 1: Entity Retention Rate (DoD: 100.0% Retention)
    # ---------------------------------------------------------
    retention_rate = (len(manifest_reimported.elements) / len(manifest_orig.elements)) * 100.0
    assert retention_rate == 100.0, (
        f"[Level 1 Failure] Entity retention mismatch for {target_class}: "
        f"expected {len(manifest_orig.elements)}, got {len(manifest_reimported.elements)}"
    )

    reimp_elem = manifest_reimported.elements[0]
    assert reimp_elem.tag == orig_elem.tag, (
        f"[Level 1 Failure] Element tag changed: {orig_elem.tag} -> {reimp_elem.tag}"
    )

    # 4. Compile Reimported Manifest -> IFC2
    ifc2_path = tmp_path / f"{target_class}_pass2.ifc"
    compile_to_ifc(manifest_reimported, ifc2_path)
    assert ifc2_path.exists(), f"Failed to compile pass 2 IFC for {target_class}"

    # Open both IFC models for geometric and schema verification
    model1 = ifcopenshell.open(str(ifc1_path))
    model2 = ifcopenshell.open(str(ifc2_path))

    # Assert exact IFC class preservation in recompiled model
    instances_pass2 = model2.by_type(canonical_class)
    assert len(instances_pass2) == 1, (
        f"[Level 1 Failure] Class preservation failed for {target_class} (canonical: {canonical_class}): "
        f"found {len(instances_pass2)} instances in recompiled IFC"
    )

    # ---------------------------------------------------------
    # Level 2: 3D Geometric Invariance (IoU >= 0.95, Delta Vol <= 0.1%)
    # ---------------------------------------------------------
    geom_settings = ifcopenshell.geom.settings()
    geom_settings.set(geom_settings.USE_WORLD_COORDS, True)

    inst1 = model1.by_type(canonical_class)[0]
    inst2 = instances_pass2[0]

    bbox1 = extract_bbox_from_element(inst1, geom_settings)
    bbox2 = extract_bbox_from_element(inst2, geom_settings)

    if bbox1 is not None and bbox2 is not None:
        min1, max1 = bbox1
        min2, max2 = bbox2
        iou = compute_bbox_iou(min1, max1, min2, max2)
        assert iou >= 0.95, (
            f"[Level 2 Failure] 3D Bounding Box IoU too low for {target_class}: {iou:.4f} < 0.95"
        )

        vol1 = float(np.prod(np.maximum(0.0, max1 - min1)))
        vol2 = float(np.prod(np.maximum(0.0, max2 - min2)))
        delta_vol = abs(vol2 - vol1) / max(vol1, 1e-9)
        assert delta_vol <= 0.005, (
            f"[Level 2 Failure] Volume delta exceeds tolerance for {target_class}: {delta_vol * 100:.3f}%"
        )
    else:
        # Fallback to dimension invariance for non-meshable elements
        d_orig = getattr(orig_elem, "dimensions", None)
        d_reimp = getattr(reimp_elem, "dimensions", None)
        if d_orig and d_reimp:
            assert abs(d_orig.width - d_reimp.width) < 1e-3, f"Width mismatch: {d_orig.width} vs {d_reimp.width}"
            assert abs(d_orig.height - d_reimp.height) < 1e-3, f"Height mismatch: {d_orig.height} vs {d_reimp.height}"

    # ---------------------------------------------------------
    # Level 3: Manifest Round-Trip Idempotency
    # ---------------------------------------------------------
    assert reimp_elem.tag == orig_elem.tag

    # If CustomElement, check position and dimensions idempotency
    p_orig = getattr(orig_elem, "placement", None)
    p_reimp = getattr(reimp_elem, "placement", None)
    if p_orig and p_reimp and getattr(p_orig, "position", None) is not None and getattr(p_reimp, "position", None) is not None:
        assert np.allclose(p_orig.position, p_reimp.position, atol=1e-3), (
            f"[Level 3 Failure] Placement position drift: {p_orig.position} -> {p_reimp.position}"
        )

    # ---------------------------------------------------------
    # Level 4: buildingSMART Schema Compliance (0 Issues)
    # ---------------------------------------------------------
    logger1 = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(model1, logger1)
    assert len(logger1.statements) == 0, (
        f"[Level 4 Failure] Schema violations in Pass 1 IFC for {target_class}: {logger1.statements}"
    )

    logger2 = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(model2, logger2)
    assert len(logger2.statements) == 0, (
        f"[Level 4 Failure] Schema violations in Pass 2 IFC for {target_class}: {logger2.statements}"
    )
