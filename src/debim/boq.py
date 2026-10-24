"""
debim BOQ (Bill of Quantities) Module
Wrapper around QTO and Cost Estimation for project quantities and pricing sheets.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from debim.schema import ProjectManifest, load_manifest
from debim.resolver import ResolvedManifest, resolve_manifest
from debim.qto import calculate_qto, ProjectQTO
from debim.cost import estimate_cost, load_price_catalog, PriceCatalog


def generate_boq(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    price_catalog: Optional[Union[PriceCatalog, Path, str]] = None,
    include_earthwork: bool = True,
) -> Dict[str, Any]:
    """
    Generate Bill of Quantities (BOQ) with quantities and costs.
    """
    if isinstance(manifest_or_resolved, (str, Path)):
        manifest = load_manifest(manifest_or_resolved)
        resolved = resolve_manifest(manifest)
    elif isinstance(manifest_or_resolved, ProjectManifest):
        resolved = resolve_manifest(manifest_or_resolved)
    else:
        resolved = manifest_or_resolved

    qto = calculate_qto(resolved)

    earthwork_items = []
    if include_earthwork and getattr(resolved, "earthwork", None):
        ew = resolved.earthwork
        earthwork_items = [
            {
                "description": "งานดินขุด (Excavation/Cut Earthwork)",
                "quantity": ew.cut_volume,
                "unit": "m3",
            },
            {
                "description": "งานดินถมและบดอัด (Compacted Fill Earthwork)",
                "quantity": ew.fill_volume,
                "unit": "m3",
            },
            {
                "description": "ดินสุทธิที่ต้องจัดหาเพิ่ม/ขนทิ้ง (Net Earthwork Balance)",
                "quantity": ew.net_balance,
                "unit": "m3",
            },
        ]

    result = {
        "qto": qto,
        "earthwork": earthwork_items,
    }

    if price_catalog:
        if isinstance(price_catalog, (str, Path)):
            catalog = load_price_catalog(price_catalog)
        else:
            catalog = price_catalog
        cost_est = estimate_cost(qto, catalog)
        result["cost"] = cost_est

    return result
