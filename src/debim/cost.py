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


class PriceItemStandards(BaseModel):
    masterformat: Optional[str] = None  # e.g. "03 31 00"
    uniformat: Optional[str] = None     # e.g. "B1010"
    unspsc: Optional[str] = None


class PriceItem(BaseModel):
    name: str
    unit: str
    material_cost: float = 0.0
    labor_cost: float = 0.0
    standards: Optional[PriceItemStandards] = None


class PriceCatalog(BaseModel):
    currency: str = "THB"
    includes: List[str] = Field(default_factory=list)
    items: Dict[str, PriceItem] = Field(default_factory=dict)


def _process_price_includes(
    includes: List[str], base_dir: Path, visited: set, merged_items: Dict[str, dict]
) -> None:
    import yaml

    for pattern in includes:
        is_glob = any(char in pattern for char in ["*", "?", "["])
        if is_glob:
            matching_paths = sorted(base_dir.glob(pattern))
            if not matching_paths:
                raise FileNotFoundError(f"No files matched price include pattern: {pattern}")
        else:
            inc_path = base_dir / pattern
            if not inc_path.exists():
                raise FileNotFoundError(f"Included price file not found: {pattern}")
            matching_paths = [inc_path]

        for inc_path in matching_paths:
            inc_canonical = inc_path.resolve()
            if inc_canonical in visited:
                raise ValueError(f"Circular price include detected: {pattern}")

            sub_visited = set(visited)
            sub_visited.add(inc_canonical)

            with open(inc_canonical, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f) or {}

            if not isinstance(content, dict):
                raise ValueError(
                    f"Invalid content in included price file {inc_path}: expected dictionary"
                )

            sub_items = content.get("items", {}) or {}
            for code, item_data in sub_items.items():
                if code in merged_items:
                    raise ValueError(
                        f"Duplicate item code '{code}' found in price catalog include {inc_path}"
                    )
                merged_items[code] = item_data

            sub_includes = content.get("includes", []) or []
            if sub_includes:
                _process_price_includes(
                    sub_includes, inc_canonical.parent, sub_visited, merged_items
                )


def load_price_catalog(path: Union[str, Path]) -> PriceCatalog:
    """Load price catalog JSON or YAML file, with support for modular includes:."""
    import sys
    import yaml

    if str(path) == "-" or (isinstance(path, Path) and str(path) == "-"):
        content = sys.stdin.read()
        data = yaml.safe_load(content) or {}
        base_dir = Path.cwd()
        visited = set()
    else:
        catalog_path = Path(path)
        if not catalog_path.exists():
            raise FileNotFoundError(f"Price catalog not found: {catalog_path}")

        canonical_path = catalog_path.resolve()
        base_dir = canonical_path.parent
        visited = {canonical_path}

        with open(canonical_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Price catalog must be a dictionary, got {type(data)}")

    includes = data.get("includes", []) or []
    merged_items = dict(data.get("items", {}) or {})

    if includes:
        _process_price_includes(includes, base_dir, visited, merged_items)

    data["items"] = merged_items
    return PriceCatalog.model_validate(data)


def generate_cost_template(
    manifest: Union[ProjectManifest, Path, str],
    output_path: Optional[Union[Path, str]] = None,
    format: str = "yaml",
    modular: bool = False,
) -> Path:
    """
    Generate a minimal, project-scoped price catalog template by scanning a project manifest
    and QTO requirements.
    """
    import yaml

    if isinstance(manifest, (str, Path)):
        manifest_obj = load_manifest(manifest)
    else:
        manifest_obj = manifest

    qto = calculate_qto(manifest_obj)

    if output_path is None:
        ext = "json" if format.lower() == "json" else "yaml"
        output_path = Path(f"prices.template.{ext}")
    else:
        output_path = Path(output_path)

    required_items: Dict[str, PriceItem] = {}
    item_disciplines: Dict[str, str] = {}

    # 1. Manifest materials
    for m in manifest_obj.materials:
        cost_ref = m.unit_cost_ref
        if cost_ref not in required_items:
            cat = (m.category or "structure").lower()
            mat_name_lower = (m.name or "").lower()
            if "conc" in cat or "conc" in m.id.lower() or "conc" in mat_name_lower:
                unit = "m3"
                mf, uf = "03 30 00", "B1010"
                disc = "structure"
            elif "block" in cat or "brick" in cat or "aac" in m.id.lower() or "aac" in mat_name_lower:
                unit = "m2"
                mf, uf = "04 20 00", "C1010"
                disc = "architecture"
            elif "steel" in cat or "metal" in cat:
                unit = "kg"
                mf, uf = "05 12 00", "B10"
                disc = "structure"
            else:
                unit = "m3"
                mf, uf = "03 00 00", "B10"
                disc = cat if cat in ("structure", "architecture", "mep", "finishes", "substructure", "roof") else "structure"

            required_items[cost_ref] = PriceItem(
                name=m.name or m.id,
                unit=unit,
                material_cost=0.0,
                labor_cost=0.0,
                standards=PriceItemStandards(masterformat=mf, uniformat=uf),
            )
            item_disciplines[cost_ref] = disc

    # 2. Formwork
    if qto.total_formwork_area > 0 and "MAT-FORMWORK" not in required_items:
        required_items["MAT-FORMWORK"] = PriceItem(
            name="Timber Formwork",
            unit="m2",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="03 11 00", uniformat="B1010"),
        )
        item_disciplines["MAT-FORMWORK"] = "structure"

    # 3. Rebars
    for bar_type, wt in qto.total_rebar_by_type.items():
        if wt > 0:
            code = f"MAT-REBAR-{bar_type}"
            if code not in required_items:
                required_items[code] = PriceItem(
                    name=f"Steel Reinforcement Bar {bar_type}",
                    unit="kg",
                    material_cost=0.0,
                    labor_cost=0.0,
                    standards=PriceItemStandards(masterformat="03 21 00", uniformat="B1010"),
                )
                item_disciplines[code] = "structure"

    # 4. Substructure
    if qto.total_excavation_volume > 0 and "EARTH-EXCAVATION" not in required_items:
        required_items["EARTH-EXCAVATION"] = PriceItem(
            name="Earth Excavation for Substructure",
            unit="m3",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="31 23 16", uniformat="A1010"),
        )
        item_disciplines["EARTH-EXCAVATION"] = "substructure"

    if qto.total_lean_concrete_volume > 0 and "MAT-LEAN-CONC" not in required_items:
        required_items["MAT-LEAN-CONC"] = PriceItem(
            name="Lean Concrete Bedding (1:3:6)",
            unit="m3",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="03 30 00", uniformat="A1010"),
        )
        item_disciplines["MAT-LEAN-CONC"] = "substructure"

    if qto.total_sand_bedding_volume > 0 and "MAT-SAND-BEDDING" not in required_items:
        required_items["MAT-SAND-BEDDING"] = PriceItem(
            name="Compacted Sand Bedding",
            unit="m3",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="31 23 23", uniformat="A1010"),
        )
        item_disciplines["MAT-SAND-BEDDING"] = "substructure"

    if qto.total_pile_length > 0 and "MAT-PILE-PC" not in required_items:
        required_items["MAT-PILE-PC"] = PriceItem(
            name="Precast Concrete Pile",
            unit="m",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="31 62 00", uniformat="A1020"),
        )
        item_disciplines["MAT-PILE-PC"] = "substructure"

    if qto.total_pile_count > 0:
        if "MAT-PILE-DRIVE" not in required_items:
            required_items["MAT-PILE-DRIVE"] = PriceItem(
                name="Pile Driving Service",
                unit="set",
                material_cost=0.0,
                labor_cost=0.0,
                standards=PriceItemStandards(masterformat="31 62 00", uniformat="A1020"),
            )
            item_disciplines["MAT-PILE-DRIVE"] = "substructure"
        if "MAT-PILE-CUT" not in required_items:
            required_items["MAT-PILE-CUT"] = PriceItem(
                name="Pile Head Cut & Trimming",
                unit="set",
                material_cost=0.0,
                labor_cost=0.0,
                standards=PriceItemStandards(masterformat="31 62 00", uniformat="A1020"),
            )
            item_disciplines["MAT-PILE-CUT"] = "substructure"

    # 5. Finishes
    if qto.total_wall_plaster_area > 0 and "FIN-WALL-PLASTER" not in required_items:
        required_items["FIN-WALL-PLASTER"] = PriceItem(
            name="Cement Mortar Wall Plastering",
            unit="m2",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="09 24 00", uniformat="C2010"),
        )
        item_disciplines["FIN-WALL-PLASTER"] = "finishes"

    if qto.total_wall_paint_interior_area > 0 and "FIN-WALL-PAINT-INT" not in required_items:
        required_items["FIN-WALL-PAINT-INT"] = PriceItem(
            name="Interior Acrylic Wall Paint",
            unit="m2",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="09 91 23", uniformat="C2010"),
        )
        item_disciplines["FIN-WALL-PAINT-INT"] = "finishes"

    if qto.total_wall_paint_exterior_area > 0 and "FIN-WALL-PAINT-EXT" not in required_items:
        required_items["FIN-WALL-PAINT-EXT"] = PriceItem(
            name="Exterior Weatherproof Wall Paint",
            unit="m2",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="09 91 13", uniformat="C2010"),
        )
        item_disciplines["FIN-WALL-PAINT-EXT"] = "finishes"

    if qto.total_wall_tile_area > 0 and "FIN-WALL-TILE" not in required_items:
        required_items["FIN-WALL-TILE"] = PriceItem(
            name="Ceramic Wall Tiles",
            unit="m2",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="09 30 00", uniformat="C2010"),
        )
        item_disciplines["FIN-WALL-TILE"] = "finishes"

    if qto.total_ceiling_gypsum_area > 0 and "FIN-CEIL-GYPSUM" not in required_items:
        required_items["FIN-CEIL-GYPSUM"] = PriceItem(
            name="Gypsum Board Ceiling",
            unit="m2",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="09 29 00", uniformat="C3010"),
        )
        item_disciplines["FIN-CEIL-GYPSUM"] = "finishes"

    if qto.total_ceiling_tbar_area > 0 and "FIN-CEIL-TBAR" not in required_items:
        required_items["FIN-CEIL-TBAR"] = PriceItem(
            name="Moisture-Resistant T-Bar Ceiling",
            unit="m2",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="09 51 00", uniformat="C3010"),
        )
        item_disciplines["FIN-CEIL-TBAR"] = "finishes"

    if qto.total_ceiling_eaves_area > 0 and "FIN-CEIL-EAVES" not in required_items:
        required_items["FIN-CEIL-EAVES"] = PriceItem(
            name="Ventilated Eaves Ceiling Panel",
            unit="m2",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="09 54 00", uniformat="C3010"),
        )
        item_disciplines["FIN-CEIL-EAVES"] = "finishes"

    if qto.total_floor_tile_area > 0 and "FIN-FLOOR-TILE" not in required_items:
        required_items["FIN-FLOOR-TILE"] = PriceItem(
            name="Floor Ceramic / Granito Tiles",
            unit="m2",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="09 30 00", uniformat="C1010"),
        )
        item_disciplines["FIN-FLOOR-TILE"] = "finishes"

    if qto.total_floor_polish_area > 0 and "FIN-FLOOR-POLISH" not in required_items:
        required_items["FIN-FLOOR-POLISH"] = PriceItem(
            name="Polished Concrete Floor Finish",
            unit="m2",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="03 35 00", uniformat="C1010"),
        )
        item_disciplines["FIN-FLOOR-POLISH"] = "finishes"

    if qto.total_skirting_length > 0 and "FIN-SKIRTING" not in required_items:
        required_items["FIN-SKIRTING"] = PriceItem(
            name="Wall Skirting Board",
            unit="m",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="09 65 00", uniformat="C1010"),
        )
        item_disciplines["FIN-SKIRTING"] = "finishes"

    # 6. Roof
    if qto.total_roof_steel_weight > 0 and "ROOF-STEEL-TRUSS" not in required_items:
        required_items["ROOF-STEEL-TRUSS"] = PriceItem(
            name="Roof Structural Steel Truss",
            unit="kg",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="05 12 00", uniformat="B1020"),
        )
        item_disciplines["ROOF-STEEL-TRUSS"] = "roof"

    if qto.total_roof_covering_area > 0 and "ROOF-TILE-CONC" not in required_items:
        required_items["ROOF-TILE-CONC"] = PriceItem(
            name="Roof Tile Covering",
            unit="m2",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="07 31 00", uniformat="B1020"),
        )
        item_disciplines["ROOF-TILE-CONC"] = "roof"

    if (qto.total_roof_ridge_length + qto.total_roof_hip_length) > 0 and "ROOF-RIDGE-CAP" not in required_items:
        required_items["ROOF-RIDGE-CAP"] = PriceItem(
            name="Roof Ridge / Hip Cap Tiles",
            unit="m",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="07 31 00", uniformat="B1020"),
        )
        item_disciplines["ROOF-RIDGE-CAP"] = "roof"

    if qto.total_roof_eaves_length > 0 and "ROOF-FASCIA" not in required_items:
        required_items["ROOF-FASCIA"] = PriceItem(
            name="Fascia Board",
            unit="m",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="06 20 00", uniformat="B1020"),
        )
        item_disciplines["ROOF-FASCIA"] = "roof"

    if qto.total_roof_insulation_area > 0 and "ROOF-INSULATION" not in required_items:
        required_items["ROOF-INSULATION"] = PriceItem(
            name="Roof Thermal Foil Insulation",
            unit="m2",
            material_cost=0.0,
            labor_cost=0.0,
            standards=PriceItemStandards(masterformat="07 21 00", uniformat="B1020"),
        )
        item_disciplines["ROOF-INSULATION"] = "roof"

    # 7. MEP
    mep_specs = [
        (qto.total_cold_water_pipe_length, "MEP-PIPE-COLD", "Cold Water Pipe", "m", "22 11 16", "D20"),
        (qto.total_soil_pipe_length, "MEP-PIPE-SOIL", "Soil Drainage Pipe", "m", "22 13 16", "D20"),
        (qto.total_waste_pipe_length, "MEP-PIPE-WASTE", "Waste Water Pipe", "m", "22 13 16", "D20"),
        (qto.total_vent_pipe_length, "MEP-PIPE-VENT", "Vent Pipe", "m", "22 13 16", "D20"),
        (qto.total_drainage_pipe_length, "MEP-PIPE-DRAIN", "Site Drainage Pipe", "m", "22 13 16", "D20"),
        (qto.total_refrigerant_pipe_length, "MEP-PIPE-REF", "AC Refrigerant Piping", "m", "23 23 00", "D30"),
        (qto.total_condensate_pipe_length, "MEP-PIPE-COND", "AC Condensate Pipe", "m", "23 23 00", "D30"),
        (float(qto.total_pipe_fittings_count), "MEP-PIPE-FITTING", "Pipe Fittings & Valves", "set", "22 11 00", "D20"),
        (qto.total_conduit_length, "MEP-CONDUIT", "Electrical Conduit", "m", "26 05 33", "D50"),
        (float(qto.total_conduit_fittings_count), "MEP-CONDUIT-FITTING", "Conduit Junction Boxes & Fittings", "set", "26 05 33", "D50"),
        (qto.total_duct_length, "MEP-DUCT", "HVAC Air Ductwork", "m", "23 31 00", "D30"),
        (float(qto.total_duct_fittings_count), "MEP-DUCT-FITTING", "Duct Fittings & Dampers", "set", "23 31 00", "D30"),
        (float(qto.total_distribution_boards_count), "MEP-DIST-BOARD", "Electrical Distribution Board", "set", "26 24 16", "D50"),
        (float(qto.total_lighting_fixtures_count), "MEP-LIGHT-FIXTURE", "Lighting Fixture", "set", "26 51 00", "D50"),
        (float(qto.total_switches_count), "MEP-SWITCH", "Wall Switch", "set", "26 27 26", "D50"),
        (float(qto.total_outlets_count), "MEP-OUTLET", "Power Wall Outlet", "set", "26 27 26", "D50"),
        (float(qto.total_sanitary_terminals_count), "MEP-SANITARY-FIXTURE", "Sanitary Plumbing Fixture", "set", "22 40 00", "D20"),
        (float(qto.total_air_terminals_count), "MEP-AIR-TERMINAL", "Ventilation Fan / Diffuser", "set", "23 37 13", "D30"),
        (float(qto.total_unitary_equipment_count), "MEP-HVAC-UNITARY", "Air Conditioner Unit", "set", "23 81 00", "D30"),
    ]
    for amt, code, name, unit, mf, uf in mep_specs:
        if amt > 0 and code not in required_items:
            required_items[code] = PriceItem(
                name=name,
                unit=unit,
                material_cost=0.0,
                labor_cost=0.0,
                standards=PriceItemStandards(masterformat=mf, uniformat=uf),
            )
            item_disciplines[code] = "mep"

    # Save logic
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if modular:
        modules_dir = output_path.parent / "modules"
        modules_dir.mkdir(parents=True, exist_ok=True)

        disc_groups: Dict[str, Dict[str, dict]] = {}
        for code, item in required_items.items():
            disc = item_disciplines.get(code, "general")
            if disc not in disc_groups:
                disc_groups[disc] = {}
            disc_groups[disc][code] = item.model_dump(exclude_none=True)

        for disc, items_dict in disc_groups.items():
            mod_path = modules_dir / f"{disc}.yaml"
            with open(mod_path, "w", encoding="utf-8") as f:
                yaml.safe_dump({"items": items_dict}, f, allow_unicode=True, sort_keys=False)

        catalog_data = {
            "currency": "THB",
            "includes": ["modules/*.yaml"],
            "items": {},
        }
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(catalog_data, f, allow_unicode=True, sort_keys=False)
    else:
        catalog_dict = {
            "currency": "THB",
            "items": {
                code: item.model_dump(exclude_none=True) for code, item in required_items.items()
            },
        }

        if format.lower() == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(catalog_dict, f, indent=2, ensure_ascii=False)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(catalog_dict, f, allow_unicode=True, sort_keys=False)

    return output_path


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

        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
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
                elif eqto.covering:
                    qty = eqto.covering.area
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
                elif eqto.covering:
                    qty = eqto.covering.length
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

    # 8. Map Earth excavation
    if qto.total_excavation_volume > 0:
        has_excav = any("excav" in c.lower() or "ขุด" in c.lower() for c in quantities_by_code.keys())
        if not has_excav:
            for code, item in catalog.items.items():
                if "excav" in code.lower() or "ขุด" in item.name:
                    quantities_by_code[code] = quantities_by_code.get(code, 0.0) + qto.total_excavation_volume
                    break

    # 9. Map Ceilings (Gypsum, T-Bar, Eaves) if not already mapped via material ref
    if qto.total_ceiling_gypsum_area > 0:
        has_gyp = any("ceil-gypsum" in c.lower() or "gypsum" in c.lower() for c in quantities_by_code.keys())
        if not has_gyp:
            for code, item in catalog.items.items():
                if "ceil-gypsum" in code.lower() or "ยิปซั่ม" in item.name:
                    quantities_by_code[code] = quantities_by_code.get(code, 0.0) + qto.total_ceiling_gypsum_area
                    break

    if qto.total_ceiling_tbar_area > 0:
        has_tbar = any("ceil-tbar" in c.lower() or "tbar" in c.lower() for c in quantities_by_code.keys())
        if not has_tbar:
            for code, item in catalog.items.items():
                if "ceil-tbar" in code.lower() or "tbar" in code.lower() or "ทีบาร์" in item.name:
                    quantities_by_code[code] = quantities_by_code.get(code, 0.0) + qto.total_ceiling_tbar_area
                    break

    if qto.total_ceiling_eaves_area > 0:
        has_eaves = any("ceil-eaves" in c.lower() or "eaves" in c.lower() for c in quantities_by_code.keys())
        if not has_eaves:
            for code, item in catalog.items.items():
                if "ceil-eaves" in code.lower() or "ชายคาระบาย" in item.name or ("ระบาย" in item.name and "ฝ้า" in item.name):
                    quantities_by_code[code] = quantities_by_code.get(code, 0.0) + qto.total_ceiling_eaves_area
                    break

    # 10. Map Floor finishes (Tile, Polished concrete, Skirting)
    if qto.total_floor_tile_area > 0:
        has_floor_tile = any("tile-floor" in c.lower() for c in quantities_by_code.keys())
        if not has_floor_tile:
            for code, item in catalog.items.items():
                if "tile-floor" in code.lower() or "กระเบื้องพื้น" in item.name or ("tile" in code.lower() and "floor" in item.name.lower()):
                    quantities_by_code[code] = quantities_by_code.get(code, 0.0) + qto.total_floor_tile_area
                    break

    if qto.total_floor_polish_area > 0:
        has_polish = any("conc-polish" in c.lower() or "polish" in c.lower() for c in quantities_by_code.keys())
        if not has_polish:
            for code, item in catalog.items.items():
                if "conc-polish" in code.lower() or "polish" in code.lower() or "ขัดเรียบ" in item.name or "ขัดมัน" in item.name:
                    quantities_by_code[code] = quantities_by_code.get(code, 0.0) + qto.total_floor_polish_area
                    break

    if qto.total_skirting_length > 0:
        has_skirt = any("skirting" in c.lower() for c in quantities_by_code.keys())
        if not has_skirt:
            for code, item in catalog.items.items():
                if "skirting" in code.lower() or "บัวเชิง" in item.name:
                    quantities_by_code[code] = quantities_by_code.get(code, 0.0) + qto.total_skirting_length
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
