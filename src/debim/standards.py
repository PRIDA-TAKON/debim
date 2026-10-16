"""
debim Standards Engine & Repository Client.
Connects debim directly with open-source debim-standards catalog repository (PRIDA-TAKON/debim-standards).
Provides local caching (~/.debim/standards_cache/), HTTP fetching fallback, and built-in offline default standards
for human scale furniture clearances, Thai building control laws (MR 55), CGD v480 pricing, and embodied carbon metrics.
"""

import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Local cache directory path
CACHE_DIR = Path.home() / ".debim" / "standards_cache"
REPO_RAW_URL = "https://raw.githubusercontent.com/PRIDA-TAKON/debim-standards/main/catalogs"

# Built-in offline default fallback catalogs
DEFAULT_FURNITURE_CATALOG: Dict[str, Dict[str, Any]] = {
    "BED_KING_6FT": {
        "name": "King Bed 6ft",
        "dimensions": {"width": 1.83, "depth": 1.98, "height": 0.90},
        "footprint_area": 3.6234,
        "clearance": {"front": 0.60, "left": 0.60, "right": 0.60, "rear": 0.00, "back": 0.00},
        "category": "bedroom",
    },
    "BED_QUEEN_5FT": {
        "name": "Queen Bed 5ft",
        "dimensions": {"width": 1.52, "depth": 1.98, "height": 0.90},
        "footprint_area": 3.0096,
        "clearance": {"front": 0.60, "left": 0.60, "right": 0.60, "rear": 0.00, "back": 0.00},
        "category": "bedroom",
    },
    "BED_SINGLE_3FT": {
        "name": "Single Bed 3ft",
        "dimensions": {"width": 1.07, "depth": 1.98, "height": 0.90},
        "footprint_area": 2.1186,
        "clearance": {"front": 0.60, "left": 0.60, "right": 0.60, "rear": 0.00, "back": 0.00},
        "category": "bedroom",
    },
    "WARDROBE_2M": {
        "name": "Wardrobe 2m",
        "dimensions": {"width": 2.00, "depth": 0.60, "height": 2.20},
        "footprint_area": 1.20,
        "clearance": {"front": 0.80, "left": 0.00, "right": 0.00, "rear": 0.00, "back": 0.00},
        "category": "bedroom",
    },
    "WORKING_DESK": {
        "name": "Working Desk",
        "dimensions": {"width": 1.20, "depth": 0.60, "height": 0.75},
        "footprint_area": 0.72,
        "clearance": {"front": 0.80, "left": 0.00, "right": 0.00, "rear": 0.00, "back": 0.00},
        "category": "office",
    },
    "EXECUTIVE_DESK": {
        "name": "Executive Desk",
        "dimensions": {"width": 1.60, "depth": 0.80, "height": 0.75},
        "footprint_area": 1.28,
        "clearance": {"front": 0.90, "left": 0.20, "right": 0.20, "rear": 0.00, "back": 0.00},
        "category": "office",
    },
    "TOILET_STANDARD": {
        "name": "Standard Toilet",
        "dimensions": {"width": 0.45, "depth": 0.70, "height": 0.75},
        "footprint_area": 0.315,
        "clearance": {"front": 0.60, "left": 0.20, "right": 0.20, "rear": 0.00, "back": 0.00},
        "category": "bathroom",
    },
    "SHOWER_ENCLOSURE": {
        "name": "Shower Enclosure",
        "dimensions": {"width": 0.90, "depth": 0.90, "height": 2.00},
        "footprint_area": 0.81,
        "clearance": {"front": 0.60, "left": 0.00, "right": 0.00, "rear": 0.00, "back": 0.00},
        "category": "bathroom",
    },
    "DINING_TABLE_6SEAT": {
        "name": "Dining Table 6-Seat",
        "dimensions": {"width": 1.60, "depth": 0.90, "height": 0.75},
        "footprint_area": 1.44,
        "clearance": {"front": 0.90, "rear": 0.90, "back": 0.90, "left": 0.80, "right": 0.80},
        "category": "kitchen",
    },
    "SOFA_3SEATER": {
        "name": "Sofa 3-Seater",
        "dimensions": {"width": 2.10, "depth": 0.85, "height": 0.80},
        "footprint_area": 1.785,
        "clearance": {"front": 0.60, "left": 0.20, "right": 0.20, "rear": 0.00, "back": 0.00},
        "category": "living",
    },
    "CAR_SEDAN": {
        "name": "Sedan Car",
        "dimensions": {"width": 1.80, "depth": 4.80, "height": 1.50},
        "footprint_area": 8.64,
        "clearance": {"front": 0.50, "rear": 0.50, "back": 0.50, "left": 0.60, "right": 0.60},
        "category": "parking",
    },
}

DEFAULT_REGULATIONS_CATALOG: Dict[str, Dict[str, Any]] = {
    "TH": {
        "jurisdiction": "TH",
        "standard": "TH-MINISTERIAL-REG-55",
        "title": "Thai Building Control Act Ministerial Regulation No. 55 (B.E. 2543)",
        "natural_ventilation_ratio": 0.10,  # Ventilation window opening >= 10% floor area
        "stair_riser_max": 0.20,            # Riser height <= 0.20m
        "stair_tread_min": 0.22,            # Tread depth >= 0.22m
        "corridor_width_min": 1.00,         # Corridor clear width >= 1.00m
        "door_clear_width_min": 0.80,       # Door clear width >= 0.80m
        "bathroom_slab_drop_max": -0.10,    # Wet room sunken slab drop <= -0.10m
        "clear_headroom_min": 2.60,         # Minimum habitable clear headroom >= 2.60m
        "rules": {
            "LAYER2_NATURAL_VENTILATION": {"min_ratio": 0.10, "description": "Natural ventilation opening >= 10% floor area"},
            "LAYER2_STAIR_GEOMETRY": {"max_riser": 0.20, "min_tread": 0.22, "description": "Stair riser <= 0.20m and tread >= 0.22m"},
            "LAYER2_EGRESS_CORRIDOR": {"min_width": 1.00, "description": "Egress corridor width >= 1.00m"},
            "LAYER2_DOOR_CLEAR_WIDTH": {"min_width": 0.80, "description": "Door clear width >= 0.80m"},
            "LAYER2_BATHROOM_SLAB_DROP": {"max_drop": -0.10, "description": "Sunken bathroom slab drop <= -0.10m"},
        },
    }
}

DEFAULT_MATERIAL_PRICES_CATALOG: Dict[str, Dict[str, Any]] = {
    "MAT-CONC-240": {
        "name": "Ready-Mixed Concrete 240 ksc Cylinder",
        "unit": "m3",
        "material_cost": 2400.0,
        "labor_cost": 450.0,
        "total_price": 2850.0,
        "embodied_carbon": 350.0,  # kgCO2e/m3
    },
    "MAT-CONC-280": {
        "name": "Ready-Mixed Concrete 280 ksc Cylinder",
        "unit": "m3",
        "material_cost": 2600.0,
        "labor_cost": 480.0,
        "total_price": 3080.0,
        "embodied_carbon": 380.0,  # kgCO2e/m3
    },
    "MAT-REBAR-RB9": {
        "name": "Steel Reinforcement Round Bar RB9 SD30",
        "unit": "kg",
        "material_cost": 32.0,
        "labor_cost": 5.0,
        "total_price": 37.0,
        "embodied_carbon": 1.85,  # kgCO2e/kg
    },
    "MAT-REBAR-DB12": {
        "name": "Steel Reinforcement Deformed Bar DB12 SD40",
        "unit": "kg",
        "material_cost": 31.5,
        "labor_cost": 4.5,
        "total_price": 36.0,
        "embodied_carbon": 1.80,  # kgCO2e/kg
    },
    "MAT-REBAR-DB16": {
        "name": "Steel Reinforcement Deformed Bar DB16 SD40",
        "unit": "kg",
        "material_cost": 31.0,
        "labor_cost": 4.5,
        "total_price": 35.5,
        "embodied_carbon": 1.80,  # kgCO2e/kg
    },
    "MAT-REBAR-DB20": {
        "name": "Steel Reinforcement Deformed Bar DB20 SD40",
        "unit": "kg",
        "material_cost": 31.0,
        "labor_cost": 4.5,
        "total_price": 35.5,
        "embodied_carbon": 1.80,  # kgCO2e/kg
    },
    "MAT-FORMWORK": {
        "name": "Timber Formwork and Support",
        "unit": "m2",
        "material_cost": 350.0,
        "labor_cost": 120.0,
        "total_price": 470.0,
        "embodied_carbon": 8.5,  # kgCO2e/m2
    },
    "MAT-BRICK-AAC": {
        "name": "Autoclaved Aerated Concrete (AAC) Block 7.5cm",
        "unit": "m2",
        "material_cost": 280.0,
        "labor_cost": 110.0,
        "total_price": 390.0,
        "embodied_carbon": 18.2,  # kgCO2e/m2
    },
    "FIN-WALL-PLASTER": {
        "name": "Cement Mortar Wall Plastering 1.5cm",
        "unit": "m2",
        "material_cost": 85.0,
        "labor_cost": 95.0,
        "total_price": 180.0,
        "embodied_carbon": 5.4,  # kgCO2e/m2
    },
    "FIN-WALL-PAINT-INT": {
        "name": "Interior Acrylic Wall Paint 2-Coats",
        "unit": "m2",
        "material_cost": 65.0,
        "labor_cost": 45.0,
        "total_price": 110.0,
        "embodied_carbon": 2.1,  # kgCO2e/m2
    },
    "FIN-WALL-PAINT-EXT": {
        "name": "Exterior Weatherproof Wall Paint 2-Coats",
        "unit": "m2",
        "material_cost": 95.0,
        "labor_cost": 55.0,
        "total_price": 150.0,
        "embodied_carbon": 2.8,  # kgCO2e/m2
    },
    "FIN-FLOOR-TILE": {
        "name": "Granito Ceramic Floor Tile 60x60cm",
        "unit": "m2",
        "material_cost": 450.0,
        "labor_cost": 180.0,
        "total_price": 630.0,
        "embodied_carbon": 12.6,  # kgCO2e/m2
    },
    "FIN-CEIL-GYPSUM": {
        "name": "Smooth Gypsum Board Ceiling 9mm",
        "unit": "m2",
        "material_cost": 190.0,
        "labor_cost": 110.0,
        "total_price": 300.0,
        "embodied_carbon": 6.8,  # kgCO2e/m2
    },
    "EARTH-EXCAVATION": {
        "name": "Earth Excavation for Footings",
        "unit": "m3",
        "material_cost": 0.0,
        "labor_cost": 150.0,
        "total_price": 150.0,
        "embodied_carbon": 1.2,  # kgCO2e/m3 (equipment fuel)
    },
}


def _get_cache_dir() -> Path:
    """Returns local standards cache directory path and ensures existence."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def fetch_catalog(catalog_name: str, force_download: bool = False) -> Dict[str, Any]:
    """
    Retrieves standard catalog dictionary from local cache (~/.debim/standards_cache/{catalog_name}.json),
    falling back to HTTP fetch from PRIDA-TAKON/debim-standards and offline defaults.
    """
    cache_file = _get_cache_dir() / f"{catalog_name}.json"

    if not force_download and cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Try HTTP download from debim-standards repository
    url = f"{REPO_RAW_URL}/{catalog_name}.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "debim-standards-client"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                return data
    except Exception:
        pass

    # Fallback to local cached file if fetch failed
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # Fallback to built-in defaults
    if catalog_name == "furniture":
        return DEFAULT_FURNITURE_CATALOG
    elif catalog_name == "regulations":
        return DEFAULT_REGULATIONS_CATALOG
    elif catalog_name in ("material_prices", "cgd_v480"):
        return DEFAULT_MATERIAL_PRICES_CATALOG

    return {}


def sync_standards(force: bool = True) -> Dict[str, bool]:
    """
    Prefetches and updates local standards cache for all catalogs.
    """
    catalogs = ["furniture", "regulations", "material_prices", "cgd_v480"]
    results = {}
    for cat in catalogs:
        data = fetch_catalog(cat, force_download=force)
        results[cat] = len(data) > 0
    return results


def list_standards() -> Dict[str, Any]:
    """
    Lists available standard catalogs and their active item counts.
    """
    catalogs = ["furniture", "regulations", "material_prices"]
    info = {}
    for cat in catalogs:
        data = fetch_catalog(cat, force_download=False)
        info[cat] = {
            "count": len(data),
            "keys": list(data.keys())[:10],
            "cached": (_get_cache_dir() / f"{cat}.json").exists(),
        }
    return info


class StandardFurnitureItem:
    """Helper class providing dual dictionary & attribute access for furniture standards."""

    def __init__(self, data: Dict[str, Any], ref: str):
        self.ref = ref
        self.name = data.get("name", ref)
        self.category = data.get("category", "general")
        dims = data.get("dimensions", {})
        self.width = float(dims.get("width", 1.0))
        self.depth = float(dims.get("depth", dims.get("width", 1.0)))
        self.height = float(dims.get("height", 1.0))
        self.dimensions = {"width": self.width, "depth": self.depth, "height": self.height}
        self.footprint_area = data.get("footprint_area", self.width * self.depth)

        clr = data.get("clearance", {})
        self.clearance = {
            "front": float(clr.get("front", 0.60)),
            "left": float(clr.get("left", 0.20)),
            "right": float(clr.get("right", 0.20)),
            "rear": float(clr.get("rear", clr.get("back", 0.00))),
            "back": float(clr.get("back", clr.get("rear", 0.00))),
        }

    def __getitem__(self, key: str) -> Any:
        if key == "ref":
            return self.ref
        elif key == "name":
            return self.name
        elif key == "width":
            return self.width
        elif key == "depth":
            return self.depth
        elif key == "height":
            return self.height
        elif key == "dimensions":
            return self.dimensions
        elif key == "footprint_area":
            return self.footprint_area
        elif key == "clearance":
            return self.clearance
        elif key == "category":
            return self.category
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref": self.ref,
            "name": self.name,
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
            "dimensions": self.dimensions,
            "footprint_area": self.footprint_area,
            "clearance": self.clearance,
            "category": self.category,
        }


def get_furniture(ref: str) -> Optional[StandardFurnitureItem]:
    """
    Returns human scale furniture standard definition by reference ID (e.g., 'BED_KING_6FT', 'WORKING_DESK').
    Returns item with dimensions (width, depth, height), footprint area, and clearance envelope (front, left, right, rear/back).
    """
    catalog = fetch_catalog("furniture")
    item_data = catalog.get(ref)
    if not item_data:
        # Check case-insensitive match
        for k, v in catalog.items():
            if k.lower() == ref.lower():
                item_data = v
                break

    if not item_data:
        return None

    return StandardFurnitureItem(item_data, ref)


def get_regulations(jurisdiction: str = "TH") -> Dict[str, Any]:
    """
    Returns legal clauses and regulatory metrics for given jurisdiction (default 'TH' for Thai Building Control Act MR 55).
    Metrics include ventilation ratio (>= 0.10), stair riser (<= 0.20m), tread (>= 0.22m), corridor width (>= 1.0m),
    door clear width (>= 0.80m), and bathroom slab drop (<= -0.10m).
    """
    catalog = fetch_catalog("regulations")
    reg_data = catalog.get(jurisdiction.upper())
    if not reg_data:
        reg_data = DEFAULT_REGULATIONS_CATALOG.get("TH", {})
    return reg_data


class StandardMaterialPrice:
    """Helper class providing dual dictionary & attribute access for material price and carbon standards."""

    def __init__(self, data: Dict[str, Any], ref: str):
        self.ref = ref
        self.name = data.get("name", ref)
        self.unit = data.get("unit", "m3")
        self.material_cost = float(data.get("material_cost", 0.0))
        self.labor_cost = float(data.get("labor_cost", 0.0))
        self.total_price = float(data.get("total_price", self.material_cost + self.labor_cost))
        self.embodied_carbon = float(data.get("embodied_carbon", 0.0))  # kgCO2e per unit

    def __getitem__(self, key: str) -> Any:
        if key == "ref":
            return self.ref
        elif key == "name":
            return self.name
        elif key == "unit":
            return self.unit
        elif key == "material_cost":
            return self.material_cost
        elif key == "labor_cost":
            return self.labor_cost
        elif key == "total_price":
            return self.total_price
        elif key == "embodied_carbon":
            return self.embodied_carbon
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref": self.ref,
            "name": self.name,
            "unit": self.unit,
            "material_cost": self.material_cost,
            "labor_cost": self.labor_cost,
            "total_price": self.total_price,
            "embodied_carbon": self.embodied_carbon,
        }


def get_material_price(ref: str) -> Optional[StandardMaterialPrice]:
    """
    Returns CGD v480 material cost, labor cost, total price, and embodied carbon metric (kgCO2e) for given ref code.
    """
    catalog = fetch_catalog("material_prices")
    item_data = catalog.get(ref)
    if not item_data:
        # Check case-insensitive match or substring
        for k, v in catalog.items():
            if k.lower() == ref.lower():
                item_data = v
                break

    if not item_data:
        # Try generic fallback matching based on code keywords
        ref_upper = ref.upper()
        if "CONC" in ref_upper:
            item_data = catalog.get("MAT-CONC-240")
        elif "REBAR" in ref_upper:
            item_data = catalog.get("MAT-REBAR-DB12")
        elif "FORMWORK" in ref_upper:
            item_data = catalog.get("MAT-FORMWORK")

    if not item_data:
        return None

    return StandardMaterialPrice(item_data, ref)
