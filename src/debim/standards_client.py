"""
debim Multi-Jurisdiction Standards Linker & Repository Client.
Connects debim dynamically with local and remote standards repository (PRIDA-TAKON/debim-standards)
supporting multi-country regulations (Thailand, Singapore, US, UK), building codes, material specifications,
pricing catalogs, and human scale clearance envelopes.
"""

import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml

# Cache directory
DEFAULT_CACHE_DIR = Path.home() / ".debim" / "standards_cache"
REPO_RAW_URL = "https://raw.githubusercontent.com/PRIDA-TAKON/debim-standards/main"

# Default Offline Regulations by Jurisdiction
DEFAULT_REGULATIONS: Dict[str, Dict[str, Any]] = {
    "TH": {
        "jurisdiction": "TH",
        "name": "Thailand",
        "standard": "TH-MINISTERIAL-REG-55",
        "title": "Thai Building Control Act Ministerial Regulation No. 55 (B.E. 2543)",
        "currency": "THB",
        "natural_ventilation_ratio": 0.10,  # Ventilation window opening >= 10% floor area
        "stair_riser_max": 0.20,            # Riser height <= 0.20m
        "stair_tread_min": 0.22,            # Tread depth >= 0.22m
        "corridor_width_min": 1.00,         # Corridor clear width >= 1.00m
        "door_clear_width_min": 0.80,       # Door clear width >= 0.80m
        "bathroom_slab_drop_max": -0.10,    # Wet room sunken slab drop <= -0.10m
        "clear_headroom_min": 2.60,         # Minimum habitable clear headroom >= 2.60m
        "open_space_ratio_min": 0.30,       # Minimum open space ratio >= 30%
        "setback_front_min": 2.00,          # Front setback >= 2.00m
        "setback_rear_min": 2.00,           # Rear setback >= 2.00m
        "setback_side_min": 1.00,           # Side setback >= 1.00m
        "rules": {
            "LAYER2_NATURAL_VENTILATION": {"min_ratio": 0.10, "description": "Natural ventilation opening >= 10% floor area"},
            "LAYER2_STAIR_GEOMETRY": {"max_riser": 0.20, "min_tread": 0.22, "description": "Stair riser <= 0.20m and tread >= 0.22m"},
            "LAYER2_EGRESS_CORRIDOR": {"min_width": 1.00, "description": "Egress corridor width >= 1.00m"},
            "LAYER2_DOOR_CLEAR_WIDTH": {"min_width": 0.80, "description": "Door clear width >= 0.80m"},
            "LAYER2_BATHROOM_SLAB_DROP": {"max_drop": -0.10, "description": "Sunken bathroom slab drop <= -0.10m"},
        },
    },
    "SG": {
        "jurisdiction": "SG",
        "name": "Singapore",
        "standard": "SG-BCA-BUILDING-CODE",
        "title": "Singapore BCA Building Control Regulations & Code on Accessibility",
        "currency": "SGD",
        "natural_ventilation_ratio": 0.10,
        "stair_riser_max": 0.175,           # Riser height <= 0.175m
        "stair_tread_min": 0.275,           # Tread depth >= 0.275m
        "corridor_width_min": 1.20,         # Corridor clear width >= 1.20m
        "door_clear_width_min": 0.85,       # Door clear width >= 0.85m
        "bathroom_slab_drop_max": -0.05,
        "clear_headroom_min": 2.60,
        "open_space_ratio_min": 0.35,
        "setback_front_min": 3.00,
        "setback_rear_min": 2.00,
        "setback_side_min": 2.00,
        "rules": {
            "LAYER2_NATURAL_VENTILATION": {"min_ratio": 0.10, "description": "Singapore BCA natural ventilation >= 10% floor area"},
            "LAYER2_STAIR_GEOMETRY": {"max_riser": 0.175, "min_tread": 0.275, "description": "Stair riser <= 0.175m and tread >= 0.275m"},
            "LAYER2_EGRESS_CORRIDOR": {"min_width": 1.20, "description": "Egress corridor width >= 1.20m"},
            "LAYER2_DOOR_CLEAR_WIDTH": {"min_width": 0.85, "description": "Door clear width >= 0.85m"},
            "LAYER2_BATHROOM_SLAB_DROP": {"max_drop": -0.05, "description": "Bathroom slab drop <= -0.05m"},
        },
    },
    "US": {
        "jurisdiction": "US",
        "name": "United States",
        "standard": "US-IBC-ADA-2021",
        "title": "International Building Code (IBC 2021) & ADA Standards for Accessible Design",
        "currency": "USD",
        "natural_ventilation_ratio": 0.08,
        "stair_riser_max": 0.178,           # 7.0 inches max
        "stair_tread_min": 0.279,           # 11.0 inches min
        "corridor_width_min": 1.118,        # 44 inches min
        "door_clear_width_min": 0.813,      # 32 inches clear min
        "bathroom_slab_drop_max": -0.05,
        "clear_headroom_min": 2.286,        # 7ft 6in min
        "open_space_ratio_min": 0.25,
        "setback_front_min": 4.572,         # 15 feet
        "setback_rear_min": 3.048,          # 10 feet
        "setback_side_min": 1.524,          # 5 feet
        "rules": {
            "LAYER2_NATURAL_VENTILATION": {"min_ratio": 0.08, "description": "IBC natural ventilation >= 8% floor area"},
            "LAYER2_STAIR_GEOMETRY": {"max_riser": 0.178, "min_tread": 0.279, "description": "Stair riser <= 0.178m (7in) and tread >= 0.279m (11in)"},
            "LAYER2_EGRESS_CORRIDOR": {"min_width": 1.118, "description": "Egress corridor width >= 1.118m (44in)"},
            "LAYER2_DOOR_CLEAR_WIDTH": {"min_width": 0.813, "description": "Door clear width >= 0.813m (32in)"},
            "LAYER2_BATHROOM_SLAB_DROP": {"max_drop": -0.05, "description": "Sunken bathroom drop <= -0.05m"},
        },
    },
    "UK": {
        "jurisdiction": "UK",
        "name": "United Kingdom",
        "standard": "UK-BUILDING-REGS-2022",
        "title": "UK Building Regulations Approved Documents (Part K/M/F/L 2022)",
        "currency": "GBP",
        "natural_ventilation_ratio": 0.05,
        "stair_riser_max": 0.20,
        "stair_tread_min": 0.22,
        "corridor_width_min": 1.00,
        "door_clear_width_min": 0.80,
        "bathroom_slab_drop_max": -0.05,
        "clear_headroom_min": 2.30,
        "open_space_ratio_min": 0.30,
        "setback_front_min": 2.00,
        "setback_rear_min": 2.00,
        "setback_side_min": 1.00,
        "rules": {
            "LAYER2_NATURAL_VENTILATION": {"min_ratio": 0.05, "description": "UK Building Regs Part F natural ventilation >= 5% floor area"},
            "LAYER2_STAIR_GEOMETRY": {"max_riser": 0.20, "min_tread": 0.22, "description": "Stair riser <= 0.20m and tread >= 0.22m"},
            "LAYER2_EGRESS_CORRIDOR": {"min_width": 1.00, "description": "Egress corridor Part M width >= 1.00m"},
            "LAYER2_DOOR_CLEAR_WIDTH": {"min_width": 0.80, "description": "Door clear width Part M >= 0.80m"},
            "LAYER2_BATHROOM_SLAB_DROP": {"max_drop": -0.05, "description": "Wet room drop <= -0.05m"},
        },
    },
}

DEFAULT_MATERIAL_PRICES: Dict[str, Dict[str, Any]] = {
    "MAT-CONC-240": {
        "name": "Ready-Mixed Concrete 240 ksc Cylinder",
        "unit": "m3",
        "material_cost": 2400.0,
        "labor_cost": 450.0,
        "total_price": 2850.0,
        "currency": "THB",
        "embodied_carbon": 350.0,  # kgCO2e/m3
        "category": "structure",
        "standards": {"masterformat": "03 30 00", "uniformat": "B1010"},
    },
    "MAT-CONC-280": {
        "name": "Ready-Mixed Concrete 280 ksc Cylinder",
        "unit": "m3",
        "material_cost": 2600.0,
        "labor_cost": 480.0,
        "total_price": 3080.0,
        "currency": "THB",
        "embodied_carbon": 380.0,
        "category": "structure",
        "standards": {"masterformat": "03 30 00", "uniformat": "B1010"},
    },
    "MAT-REBAR-DB12": {
        "name": "Steel Reinforcement Deformed Bar DB12 SD40",
        "unit": "kg",
        "material_cost": 31.5,
        "labor_cost": 4.5,
        "total_price": 36.0,
        "currency": "THB",
        "embodied_carbon": 1.80,
        "category": "structure",
        "standards": {"masterformat": "03 21 00", "uniformat": "B1010"},
    },
    "MAT-FORMWORK": {
        "name": "Timber Formwork and Support",
        "unit": "m2",
        "material_cost": 350.0,
        "labor_cost": 120.0,
        "total_price": 470.0,
        "currency": "THB",
        "embodied_carbon": 8.5,
        "category": "structure",
        "standards": {"masterformat": "03 11 00", "uniformat": "B1010"},
    },
    "FIN-WALL-PLASTER": {
        "name": "Cement Mortar Wall Plastering 1.5cm",
        "unit": "m2",
        "material_cost": 85.0,
        "labor_cost": 95.0,
        "total_price": 180.0,
        "currency": "THB",
        "embodied_carbon": 5.4,
        "category": "finishes",
        "standards": {"masterformat": "09 24 00", "uniformat": "C2010"},
    },
}

DEFAULT_HUMAN_SCALE_FURNITURE: Dict[str, Dict[str, Any]] = {
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
    "WORKING_DESK": {
        "name": "Working Desk",
        "dimensions": {"width": 1.20, "depth": 0.60, "height": 0.75},
        "footprint_area": 0.72,
        "clearance": {"front": 0.80, "left": 0.00, "right": 0.00, "rear": 0.00, "back": 0.00},
        "category": "office",
    },
    "TOILET_STANDARD": {
        "name": "Standard Toilet",
        "dimensions": {"width": 0.45, "depth": 0.70, "height": 0.75},
        "footprint_area": 0.315,
        "clearance": {"front": 0.60, "left": 0.20, "right": 0.20, "rear": 0.00, "back": 0.00},
        "category": "bathroom",
    },
    "DINING_TABLE_6SEAT": {
        "name": "Dining Table 6-Seat",
        "dimensions": {"width": 1.60, "depth": 0.90, "height": 0.75},
        "footprint_area": 1.44,
        "clearance": {"front": 0.90, "rear": 0.90, "back": 0.90, "left": 0.80, "right": 0.80},
        "category": "dining",
    },
    "SOFA_3SEATER": {
        "name": "Sofa 3-Seater",
        "dimensions": {"width": 2.10, "depth": 0.85, "height": 0.80},
        "footprint_area": 1.785,
        "clearance": {"front": 0.60, "left": 0.20, "right": 0.20, "rear": 0.00, "back": 0.00},
        "category": "living",
    },
}


class StandardsClient:
    """
    Dynamic Loader & Repository Linker for debim-standards catalog repository.
    Supports local directory lookup, fallback to cached clone, and remote HTTP downloads
    across multiple jurisdictions (th, sg, us, uk).
    """

    def __init__(
        self,
        standards_dir: Optional[Union[str, Path]] = None,
        cache_dir: Optional[Union[str, Path]] = None,
    ):
        self.standards_dir = self._find_local_standards_dir(standards_dir)
        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _find_local_standards_dir(self, custom_dir: Optional[Union[str, Path]] = None) -> Optional[Path]:
        """Discovers local debim-standards repository directory if available."""
        candidates = []
        if custom_dir:
            candidates.append(Path(custom_dir))

        env_dir = os.environ.get("DEBIM_STANDARDS_DIR")
        if env_dir:
            candidates.append(Path(env_dir))

        # Common relative paths
        cwd = Path.cwd()
        candidates.extend([
            cwd / "debim-standards",
            cwd.parent / "debim-standards",
            Path.home() / "debim-standards",
            Path.home() / ".debim" / "standards_repo",
        ])

        for cand in candidates:
            if cand.exists() and cand.is_dir():
                return cand.resolve()

        return None

    def _load_yaml_or_json(self, path: Path) -> Dict[str, Any]:
        """Loads data from a YAML or JSON file path."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                if path.suffix in (".yaml", ".yml"):
                    return yaml.safe_load(f) or {}
                return json.load(f) or {}
        except Exception:
            return {}

    def fetch_remote(self, rel_path: str) -> Optional[Dict[str, Any]]:
        """Attempts to fetch catalog raw JSON/YAML from remote GitHub repo."""
        url = f"{REPO_RAW_URL}/{rel_path}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "debim-standards-client"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    content = response.read().decode("utf-8")
                    if rel_path.endswith((".yaml", ".yml")):
                        return yaml.safe_load(content)
                    return json.loads(content)
        except Exception:
            pass
        return None

    def load_catalog_file(self, rel_path: str) -> Optional[Dict[str, Any]]:
        """
        Loads catalog file or directory of YAML/JSON files using 3-tier lookup:
        1. Local directory (`debim-standards/...`)
        2. Cached file/directory (`~/.debim/standards_cache/...`)
        3. Remote HTTP fetch with automatic caching
        """
        # Tier 1: Local directory lookup
        if self.standards_dir:
            local_target = self.standards_dir / rel_path
            if local_target.exists() and local_target.is_dir():
                merged = {}
                for child in sorted(local_target.glob("*")):
                    if child.suffix in (".yaml", ".yml", ".json"):
                        d = self._load_yaml_or_json(child)
                        if isinstance(d, dict):
                            merged.update(d)
                if merged:
                    return merged

            if local_target.exists() and local_target.is_file():
                data = self._load_yaml_or_json(local_target)
                if data:
                    return data

            # Check alternative extensions
            base_path = self.standards_dir / rel_path.rsplit(".", 1)[0]
            for ext in [".yaml", ".yml", ".json"]:
                alt_file = Path(f"{base_path}{ext}")
                if alt_file.exists() and alt_file.is_file():
                    data = self._load_yaml_or_json(alt_file)
                    if data:
                        return data

        # Tier 2: Cached file/directory lookup
        cache_file = self.cache_dir / rel_path.replace("/", "_")
        if cache_file.exists() and cache_file.is_file():
            data = self._load_yaml_or_json(cache_file)
            if data:
                return data

        # Tier 3: Remote fetch and save to cache
        data = self.fetch_remote(rel_path)
        if data:
            try:
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
            return data

        return None

    def get_regulations(self, jurisdiction: str = "th") -> Dict[str, Any]:
        """
        Returns building regulations & legal clauses for the specified jurisdiction
        ('th', 'sg', 'us', 'uk', etc.).
        """
        jur_code = jurisdiction.upper()

        # Try loading regulations for jurisdiction directory or files
        rel_paths = [
            f"regulations/{jurisdiction.lower()}",
            f"regulations/{jurisdiction.lower()}.yaml",
            f"regulations/{jurisdiction.lower()}.json",
            f"catalogs/regulations_{jurisdiction.lower()}.json",
            "catalogs/regulations.json",
        ]

        for path in rel_paths:
            data = self.load_catalog_file(path)
            if data and isinstance(data, dict):
                if jur_code in data and isinstance(data[jur_code], dict):
                    return data[jur_code]
                elif data.get("jurisdiction", "").upper() == jur_code:
                    return data
                elif "natural_ventilation_ratio" in data or "rules" in data:
                    res = dict(data)
                    res["jurisdiction"] = jur_code
                    return res

        # Fallback to built-in regulations
        return DEFAULT_REGULATIONS.get(jur_code, DEFAULT_REGULATIONS["TH"])

    def get_material_spec(self, ref: str, jurisdiction: str = "th") -> Optional[Dict[str, Any]]:
        """
        Retrieves material specification details by reference ID or material code for specified jurisdiction.
        """
        jur_code = jurisdiction.upper()
        rel_paths = [
            f"material_specs/{jurisdiction.lower()}.yaml",
            f"catalogs/material_specs_{jurisdiction.lower()}.json",
            "catalogs/material_prices.json",
        ]

        catalog = None
        for path in rel_paths:
            data = self.load_catalog_file(path)
            if data:
                catalog = data
                break

        if not catalog:
            catalog = DEFAULT_MATERIAL_PRICES

        # Lookup in catalog
        item = catalog.get(ref) or catalog.get(ref.upper())
        if not item:
            for k, v in catalog.items():
                if k.lower() == ref.lower():
                    item = v
                    break

        if not item and ref in DEFAULT_MATERIAL_PRICES:
            item = DEFAULT_MATERIAL_PRICES[ref]

        if item:
            result = dict(item)
            result["ref"] = ref
            result["jurisdiction"] = jur_code
            return result

        return None

    def get_unit_cost(self, ref: str, jurisdiction: str = "th") -> Optional[Dict[str, Any]]:
        """
        Retrieves unit cost, labor cost, total price, currency, and embodied carbon metric
        for specified reference code and jurisdiction.
        """
        spec = self.get_material_spec(ref, jurisdiction=jurisdiction)
        if not spec:
            return None

        currency_map = {"TH": "THB", "SG": "SGD", "US": "USD", "UK": "GBP"}
        currency = spec.get("currency") or currency_map.get(jurisdiction.upper(), "THB")

        return {
            "ref": ref,
            "name": spec.get("name", ref),
            "unit": spec.get("unit", "m3"),
            "material_cost": float(spec.get("material_cost", 0.0)),
            "labor_cost": float(spec.get("labor_cost", 0.0)),
            "total_price": float(spec.get("total_price", spec.get("material_cost", 0.0) + spec.get("labor_cost", 0.0))),
            "currency": currency,
            "embodied_carbon": float(spec.get("embodied_carbon", 0.0)),
            "jurisdiction": jurisdiction.upper(),
        }

    def get_human_scale(self, room_type_or_ref: str, jurisdiction: str = "th") -> Optional[Dict[str, Any]]:
        """
        Retrieves human scale furniture clearance definition or room type requirement
        for specified reference or room category.
        """
        rel_paths = [
            f"human_scale/{jurisdiction.lower()}.yaml",
            "catalogs/furniture.json",
        ]

        catalog = None
        for path in rel_paths:
            data = self.load_catalog_file(path)
            if data:
                catalog = data
                break

        if not catalog:
            catalog = DEFAULT_HUMAN_SCALE_FURNITURE

        ref_upper = room_type_or_ref.upper()
        item = catalog.get(room_type_or_ref) or catalog.get(ref_upper)

        if not item:
            for k, v in catalog.items():
                if k.lower() == room_type_or_ref.lower():
                    item = v
                    break

        if not item:
            # Check by category or room type match
            for k, v in catalog.items():
                if v.get("category", "").lower() == room_type_or_ref.lower():
                    item = v
                    break

        if not item and ref_upper in DEFAULT_HUMAN_SCALE_FURNITURE:
            item = DEFAULT_HUMAN_SCALE_FURNITURE[ref_upper]

        if item:
            res = dict(item)
            res["ref"] = room_type_or_ref
            res["jurisdiction"] = jurisdiction.upper()
            return res

        return None


# Global singleton client instance
_default_client: Optional[StandardsClient] = None

def get_standards_client(standards_dir: Optional[Union[str, Path]] = None) -> StandardsClient:
    """Returns or initializes the global StandardsClient instance."""
    global _default_client
    if _default_client is None or standards_dir is not None:
        _default_client = StandardsClient(standards_dir=standards_dir)
    return _default_client


def get_regulations(jurisdiction: str = "th") -> Dict[str, Any]:
    """Helper method: returns building regulations for given jurisdiction."""
    client = get_standards_client()
    return client.get_regulations(jurisdiction=jurisdiction)


def get_material_spec(ref: str, jurisdiction: str = "th") -> Optional[Dict[str, Any]]:
    """Helper method: returns material specification details for given ref and jurisdiction."""
    client = get_standards_client()
    return client.get_material_spec(ref, jurisdiction=jurisdiction)


def get_unit_cost(ref: str, jurisdiction: str = "th") -> Optional[Dict[str, Any]]:
    """Helper method: returns unit cost & carbon metrics for given ref and jurisdiction."""
    client = get_standards_client()
    return client.get_unit_cost(ref, jurisdiction=jurisdiction)


def get_human_scale(room_type: str, jurisdiction: str = "th") -> Optional[Dict[str, Any]]:
    """Helper method: returns human scale clearance envelope for given room type or furniture ref."""
    client = get_standards_client()
    return client.get_human_scale(room_type, jurisdiction=jurisdiction)


def get_material_price(ref: str, jurisdiction: str = "th") -> Optional[Dict[str, Any]]:
    """Helper method: returns material price spec for given ref and jurisdiction."""
    client = get_standards_client()
    return client.get_material_spec(ref, jurisdiction=jurisdiction)
