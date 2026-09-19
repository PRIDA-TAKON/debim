"""
Cost Estimation Engine for debim.
Maps Quantitative Take-Off (QTO) results against price catalogs (prices.json)
to calculate material & labor costs and export BOQ breakdown to CSV.
"""

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, Field

from debim.qto import ProjectQTO, calculate_qto
from debim.resolver import resolve_manifest
from debim.schema import ProjectManifest, load_manifest


class PriceItem(BaseModel):
    name: str
    unit: str
    material_cost: float
    labor_cost: float


class PriceCatalog(BaseModel):
    currency: str = "THB"
    items: Dict[str, PriceItem] = Field(default_factory=dict)


def load_price_catalog(path: Union[str, Path]) -> PriceCatalog:
    """Load price catalog JSON file."""
    catalog_path = Path(path)
    if not catalog_path.exists():
        raise FileNotFoundError(f"Price catalog not found: {catalog_path}")

    with open(catalog_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return PriceCatalog.model_validate(data)


class CostLineItem(BaseModel):
    code: str
    name: str
    unit: str
    quantity: float
    unit_material_cost: float
    unit_labor_cost: float
    total_material_cost: float
    total_labor_cost: float
    total_amount: float


class CostEstimate(BaseModel):
    currency: str = "THB"
    line_items: List[CostLineItem] = Field(default_factory=list)
    total_material_cost: float = 0.0
    total_labor_cost: float = 0.0
    grand_total: float = 0.0

    def export_csv(self, filepath: Union[str, Path]) -> Path:
        """Export cost estimate breakdown to CSV file."""
        csv_path = Path(filepath)
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "Item Code",
            "Description",
            "Unit",
            "Quantity",
            "Unit Material Cost",
            "Unit Labor Cost",
            "Total Material Cost",
            "Total Labor Cost",
            "Total Amount",
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(fieldnames)

            for item in self.line_items:
                writer.writerow(
                    [
                        item.code,
                        item.name,
                        item.unit,
                        f"{item.quantity:.3f}",
                        f"{item.unit_material_cost:.2f}",
                        f"{item.unit_labor_cost:.2f}",
                        f"{item.total_material_cost:.2f}",
                        f"{item.total_labor_cost:.2f}",
                        f"{item.total_amount:.2f}",
                    ]
                )

            # Summary / Total row
            writer.writerow(
                [
                    "TOTAL",
                    "Project Grand Total",
                    "",
                    "",
                    "",
                    "",
                    f"{self.total_material_cost:.2f}",
                    f"{self.total_labor_cost:.2f}",
                    f"{self.grand_total:.2f}",
                ]
            )

        return csv_path


def estimate_cost(
    qto: ProjectQTO,
    catalog: PriceCatalog,
    manifest: Optional[ProjectManifest] = None,
) -> CostEstimate:
    """
    Calculate cost estimate by matching QTO quantities with price catalog.
    """
    quantities_by_code: Dict[str, float] = {}

    # 1. Map element materials
    if manifest:
        resolved = resolve_manifest(manifest)
        material_ref_map = {m.id: m.unit_cost_ref for m in manifest.materials}

        for resolved_elem in resolved.elements:
            eqto = qto.get_element(resolved_elem.tag)
            if not eqto or not eqto.material:
                continue

            cost_ref = material_ref_map.get(eqto.material)
            if not cost_ref or cost_ref not in catalog.items:
                continue

            price_item = catalog.items[cost_ref]
            unit = price_item.unit.lower()

            if unit in ("m3", "cubic_meter"):
                qty = eqto.concrete_volume
            elif unit in ("m2", "square_meter"):
                if eqto.roof:
                    qty = eqto.roof.sloped_area
                # For wall, net surface area = volume / thickness if thickness > 0
                elif hasattr(resolved_elem, "thickness") and resolved_elem.thickness > 0:
                    qty = eqto.concrete_volume / resolved_elem.thickness
                else:
                    qty = eqto.formwork_area
            elif unit in ("kg", "kilogram"):
                if eqto.roof:
                    qty = eqto.roof.structural_steel_weight
                else:
                    qty = eqto.total_rebar_weight
            elif unit in ("m", "meter", "linear_meter"):
                if eqto.mep:
                    qty = eqto.mep.length
                else:
                    qty = 1.0
            elif unit in ("set", "item", "ea", "ชุด", "จุด", "ตัว"):
                if eqto.mep:
                    qty = float(eqto.mep.count)
                else:
                    qty = 1.0
            else:
                qty = 1.0

            quantities_by_code[cost_ref] = (
                quantities_by_code.get(cost_ref, 0.0) + qty
            )

    # 2. Map formwork
    formwork_code: Optional[str] = None
    if "MAT-FORMWORK" in catalog.items:
        formwork_code = "MAT-FORMWORK"
    else:
        for code, item in catalog.items.items():
            if "formwork" in item.name.lower() or "formwork" in code.lower():
                formwork_code = code
                break

    if formwork_code and qto.total_formwork_area > 0:
        quantities_by_code[formwork_code] = (
            quantities_by_code.get(formwork_code, 0.0) + qto.total_formwork_area
        )

    # 3. Map rebar
    for bar_type, wt in qto.total_rebar_by_type.items():
        if wt <= 0:
            continue
        exact_code = f"MAT-REBAR-{bar_type}"
        if exact_code in catalog.items:
            rebar_code = exact_code
        else:
            # Fall back to any rebar item code
            rebar_code = None
            for code, item in catalog.items.items():
                if "rebar" in code.lower() or "rebar" in item.name.lower() or item.unit.lower() == "kg":
                    rebar_code = code
                    break
        if rebar_code:
            quantities_by_code[rebar_code] = (
                quantities_by_code.get(rebar_code, 0.0) + wt
            )

    # 4. Map substructure items (Lean concrete, Sand, Piles)
    if qto.total_lean_concrete_volume > 0:
        for code, item in catalog.items.items():
            if "lean" in code.lower() or "lean" in item.name.lower():
                quantities_by_code[code] = (
                    quantities_by_code.get(code, 0.0) + qto.total_lean_concrete_volume
                )
                break

    if qto.total_sand_bedding_volume > 0:
        for code, item in catalog.items.items():
            if "sand" in code.lower() or "sand" in item.name.lower():
                quantities_by_code[code] = (
                    quantities_by_code.get(code, 0.0) + qto.total_sand_bedding_volume
                )
                break

    if qto.total_pile_length > 0:
        for code, item in catalog.items.items():
            if "pile" in code.lower() or "เข็ม" in item.name or "pile" in item.name.lower():
                if "drive" not in code.lower() and "cut" not in code.lower() and "ตอก" not in item.name and "ตัด" not in item.name:
                    quantities_by_code[code] = (
                        quantities_by_code.get(code, 0.0) + qto.total_pile_length
                    )
                    break

    if qto.total_pile_count > 0:
        for code, item in catalog.items.items():
            if "drive" in code.lower() or "ตอก" in item.name or "กด" in item.name:
                quantities_by_code[code] = (
                    quantities_by_code.get(code, 0.0) + qto.total_pile_count
                )
                break
        for code, item in catalog.items.items():
            if "cut" in code.lower() or "ตัด" in item.name:
                quantities_by_code[code] = (
                    quantities_by_code.get(code, 0.0) + qto.total_pile_count
                )
                break

    # 5. Map wall finishes (Plaster, Interior Paint, Exterior Paint, Wall Tiles)
    if qto.total_wall_plaster_area > 0:
        for code, item in catalog.items.items():
            if "plaster" in code.lower() or "ฉาบ" in item.name or "plaster" in item.name.lower():
                quantities_by_code[code] = (
                    quantities_by_code.get(code, 0.0) + qto.total_wall_plaster_area
                )
                break

    if qto.total_wall_paint_interior_area > 0:
        for code, item in catalog.items.items():
            if "paint-int" in code.lower() or "ทาสีภายใน" in item.name or ("paint" in code.lower() and "int" in code.lower()):
                quantities_by_code[code] = (
                    quantities_by_code.get(code, 0.0) + qto.total_wall_paint_interior_area
                )
                break

    if qto.total_wall_paint_exterior_area > 0:
        for code, item in catalog.items.items():
            if "paint-ext" in code.lower() or "ทาสีภายนอก" in item.name or ("paint" in code.lower() and "ext" in code.lower()):
                quantities_by_code[code] = (
                    quantities_by_code.get(code, 0.0) + qto.total_wall_paint_exterior_area
                )
                break

    # If general paint is present in catalog without int/ext distinction:
    total_paint = qto.total_wall_paint_interior_area + qto.total_wall_paint_exterior_area
    if total_paint > 0:
        has_matched_paint = any("paint" in c.lower() for c in quantities_by_code.keys())
        if not has_matched_paint:
            for code, item in catalog.items.items():
                if "paint" in code.lower() or "ทาสี" in item.name:
                    quantities_by_code[code] = (
                        quantities_by_code.get(code, 0.0) + total_paint
                    )
                    break

    if qto.total_wall_tile_area > 0:
        for code, item in catalog.items.items():
            if "tile" in code.lower() or "กระเบื้อง" in item.name:
                quantities_by_code[code] = (
                    quantities_by_code.get(code, 0.0) + qto.total_wall_tile_area
                )
                break

    # 6. Map roof items (Structural steel truss, Roof tiles, Ridge/Hip caps, Fascia, Insulation)
    if qto.total_roof_steel_weight > 0:
        has_steel = any("steel" in c.lower() or "truss" in c.lower() for c in quantities_by_code.keys())
        if not has_steel:
            for code, item in catalog.items.items():
                if "steel" in code.lower() or "โครงเหล็ก" in item.name or "truss" in code.lower():
                    quantities_by_code[code] = (
                        quantities_by_code.get(code, 0.0) + qto.total_roof_steel_weight
                    )
                    break

    if qto.total_roof_covering_area > 0:
        has_roof_tile = any("roof-tile" in c.lower() for c in quantities_by_code.keys())
        if not has_roof_tile:
            for code, item in catalog.items.items():
                if "roof-tile" in code.lower() or "กระเบื้องหลังคา" in item.name or "กระเบื้องมุงหลังคา" in item.name or ("roof" in code.lower() and "tile" in code.lower()):
                    quantities_by_code[code] = (
                        quantities_by_code.get(code, 0.0) + qto.total_roof_covering_area
                    )
                    break

    total_ridge_hip = qto.total_roof_ridge_length + qto.total_roof_hip_length
    if total_ridge_hip > 0:
        for code, item in catalog.items.items():
            if "ridge" in code.lower() or "ครอบสันหลังคา" in item.name or "ครอบตะเข้" in item.name:
                quantities_by_code[code] = (
                    quantities_by_code.get(code, 0.0) + total_ridge_hip
                )
                break

    if qto.total_roof_eaves_length > 0:
        for code, item in catalog.items.items():
            if "fascia" in code.lower() or "เชิงชาย" in item.name:
                quantities_by_code[code] = (
                    quantities_by_code.get(code, 0.0) + qto.total_roof_eaves_length
                )
                break

    if qto.total_roof_insulation_area > 0:
        for code, item in catalog.items.items():
            if "insul" in code.lower() or "สะท้อนความร้อน" in item.name or "ฉนวน" in item.name:
                quantities_by_code[code] = (
                    quantities_by_code.get(code, 0.0) + qto.total_roof_insulation_area
                )
                break

    # 7. Map MEP system totals (Cold Water, Soil, Waste, Vent, Conduits, Terminals, HVAC)
    mep_maps = [
        (qto.total_cold_water_pipe_length, ["pipe-cold", "pipe-water", "ppr", "ท่อน้ำดี"]),
        (qto.total_soil_pipe_length, ["pipe-soil", "ท่อโสโครก", "pvc-soil"]),
        (qto.total_waste_pipe_length, ["pipe-waste", "ท่อน้ำทิ้ง", "pvc-waste"]),
        (qto.total_vent_pipe_length, ["pipe-vent", "ท่อระบายอากาศ", "pvc-vent"]),
        (qto.total_drainage_pipe_length, ["pipe-drain", "ท่อระบายน้ำ"]),
        (qto.total_refrigerant_pipe_length, ["refrigerant", "pipe-ref", "ท่อน้ำยาแอร์", "ท่อน้ำยา"]),
        (qto.total_condensate_pipe_length, ["condensate", "pipe-drain-ac", "ท่อน้ำทิ้งแอร์"]),
        (float(qto.total_pipe_fittings_count), ["pipe-fitting", "ข้อต่อท่อ"]),
        (qto.total_conduit_length, ["conduit", "ท่อร้อยสายไฟ"]),
        (float(qto.total_conduit_fittings_count), ["conduit-fitting", "กล่องพักสาย", "อุปกรณ์ร้อยสาย"]),
        (qto.total_duct_length, ["duct", "ท่อลม", "ท่อระบาย"]),
        (float(qto.total_duct_fittings_count), ["duct-fitting", "ข้อต่อท่อลม"]),
    ]
    for amount, keywords in mep_maps:
        if amount > 0:
            for code, item in catalog.items.items():
                if any(kw in code.lower() or kw in item.name.lower() for kw in keywords):
                    if code not in quantities_by_code:
                        quantities_by_code[code] = (
                            quantities_by_code.get(code, 0.0) + amount
                        )
                        break

    # Build line items
    line_items: List[CostLineItem] = []
    tot_mat_cost = 0.0
    tot_lab_cost = 0.0

    for code, item in catalog.items.items():
        qty = quantities_by_code.get(code, 0.0)
        if qty <= 0:
            continue

        mat_cost = qty * item.material_cost
        lab_cost = qty * item.labor_cost
        tot_amount = mat_cost + lab_cost

        tot_mat_cost += mat_cost
        tot_lab_cost += lab_cost

        line_items.append(
            CostLineItem(
                code=code,
                name=item.name,
                unit=item.unit,
                quantity=qty,
                unit_material_cost=item.material_cost,
                unit_labor_cost=item.labor_cost,
                total_material_cost=mat_cost,
                total_labor_cost=lab_cost,
                total_amount=tot_amount,
            )
        )

    grand_total = tot_mat_cost + tot_lab_cost

    return CostEstimate(
        currency=catalog.currency,
        line_items=line_items,
        total_material_cost=tot_mat_cost,
        total_labor_cost=tot_lab_cost,
        grand_total=grand_total,
    )
