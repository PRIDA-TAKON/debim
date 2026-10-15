---
name: debim
description: Deterministic BOQ generation, Quantitative Take-Off (QTO), and Declarative BIM modeling (Building-as-Code) using debim. Use when asked to generate a bill of quantities (BOQ), estimate construction costs, calculate concrete/steel/formwork quantities from architectural plans or sketches, compile IFC4 models, or produce 3D HTML web viewers.
---

# debim Skill — Deterministic BOQ & Declarative BIM Engine
**Version:** 0.6.0 (Zero-Dependency & Offline VM Ready)
**Specification:** debim Standard Spatial & Declarative Language Specification

This skill empowers AI agents to generate professional, deterministic **Bills of Quantities (BOQ)**, calculate structural material quantities (**QTO**), and compile international standard **IFC4 BIM models** from architectural descriptions or sketches without hallucinating numbers.

---

## 🏛️ Core Philosophy for AI Agents

> **"Never guess construction numbers or hallucinate math in text."**

Instead of guessing concrete cubic meters or estimating rebar weights with vague approximations, the agent synthesizes the building geometry into a minimal **Declarative YAML/JSON manifest** (`project.yaml` or `project.json`) and executes deterministic calculation rules to produce mathematically exact figures.

---

## 🔒 Zero-Dependency & Offline Air-Gapped Operation

In air-gapped Virtual Machines (VMs) without internet connection or external package installations:
1. **Zero External Dependencies:**
   - debim relies on standard Python libraries (`argparse`, `json`, `math`, `re`, `pathlib`) and standard numerical tools (`numpy`).
   - CLI is migrating from `typer` to Python standard library `argparse`.
   - 3D mesh volume and bounding boxes are calculated directly via NumPy / divergence theorem, eliminating `trimesh`.
2. **Offline VM Execution via `scripts/debim_zero.py`:**
   - When running inside a pure Python 3 VM with **NO pip packages installed**, run:
     ```bash
     python scripts/debim_zero.py validate project.json
     python scripts/debim_zero.py qto project.json
     ```
3. **Local Schema Validation via `schemas/debim.schema.json`:**
   - A complete, self-contained JSON Schema is bundled at `schemas/debim.schema.json`.
   - AI agents and IDEs can perform static validation, schema enforcement, and parameter validation offline without querying any remote servers.

---

## 📐 Coordinate & Bounding Rules (Immutable Standards)

### 1. Right-Handed Coordinate System
* **$+X$ Axis:** East / Grid Horizontal (Rightwards on 2D floor plans).
* **$+Y$ Axis:** North / Grid Vertical (Upwards on 2D floor plans).
* **$+Z$ Axis:** Elevation (Upwards towards the sky).
* **Base Units:** Meters ($m$), Square Meters ($m^2$), Cubic Meters ($m^3$), Radians ($rad$) or Degrees ($^\circ$).

### 2. Storey Elevation Inheritance
* Each storey defines base `elevation` (e.g. Ground = `0.00m`, First Floor = `3.50m`) and `height`.
* Elements assigned to a `storey` inherit that storey's elevation as their base $Z=0$ datum.
* `offset_z`: Positive lifts above floor line; negative lowers below floor line.

### 3. Counter-Clockwise (CCW) Vertex Ordering Rule
* For all horizontal area elements (**Slabs**, **Roofs**, and **Spaces**), polygon boundary vertices **MUST be listed in Counter-Clockwise (CCW)** order when looking down from $+Z$.
* CCW ordering guarantees positive upward normal $(0, 0, 1)$ and deterministic positive area calculation via the Shoelace Formula.

### 4. Wall Orientation & Thickness Centering
* Wall vector is defined by `from_grid` $\rightarrow$ `to_grid`.
* Looking along the vector:
  * **LEFT Side:** $90^\circ$ CCW normal vector (typically exterior).
  * **RIGHT Side:** $90^\circ$ CW normal vector (typically interior).
  * **CENTER (Default):** Wall baseline lies directly on grid axis; thickness expands $\pm t/2$ symmetrically.

---

## 🎯 AI Geometry Interpretation Standards (Anchor Points & Dimensions)

To eliminate AI ambiguity when synthesizing or modifying BIM elements, debim enforces deterministic **Anchor Points**, **Euler Rotations**, and **Dimension Keys**:

### 1. Position Anchor Points (จุดอ้างอิงพิกัดตายตัว)
* **`IfcColumn`:** `BOTTOM-CENTER` — กึ่งกลางฐานเสาที่ระดับพื้นชั้นล่าง ($Z=0$), เนื้อเสาพุ่งขึ้น $+Z$ สู่ชั้นบน.
* **`IfcBeam`:** `TOP-CENTERLINE` — แนวเส้นเชื่อมระดับ **หลังคาน** ($Z=0$), ความลึก `depth` **ห้อยจมลงด้านล่าง ($-Z$)**.
* **`IfcSlab`:** `TOP-FINISH` — ผิวบนสุดของพื้นอยู่ที่ระดับชั้น ($Z=0$), ความหนา `thickness` **จมลงด้านล่าง ($-Z$)** เพื่อรักษาความสูงเคลียร์ของห้องชั้นบน.
* **`IfcWall`:** `BOTTOM-START-CENTERLINE` — จุดเริ่มต้นผนังริมล่างสุดบนพื้นชั้น, ความหนาสมมาตรรอบแนวกริต, ความสูง `height` **ก่อขึ้นสู่ $+Z$**.
* **`IfcFooting`:** `TOP-CENTER` — ผิวบนสุดระดับหลังฐานราก, ความหนาจมลงดิน ($-Z$).
* **`IfcFurniture` / `IfcEquipment`:** `BOTTOM-CENTER` — ฐานล่างกึ่งกลางชิ้นงานแตะระดับพื้นพอดี ($Z_{\text{base}} = 0$).
* **`IfcSpace`:** `BOTTOM-PERIMETER` — ระนาบพื้นห้อง, ความสูง `height` พุ่งขึ้น $+Z$ สู่ฝ้าเพดาน.

### 2. Rotation & Euler Axis Order
* **Standard Unit:** **Radian** (ทวนเข็มนาฬิกาเป็นบวก, $0 = +X\text{ East}$, $+\frac{\pi}{2} = +Y\text{ North}$).
* **3D Euler Angles:** `[rx, ry, rz]` in **Radians** with **Z-up Extrinsic / Intrinsic Z-Y-X** order:
  * `rz`: Yaw (หมุนระนาบพื้นราบรอบแกน $Z$)
  * `ry`: Pitch (หมุนเงยรอบแกน $Y$)
  * `rx`: Roll (หมุนเอียงรอบแกน $X$)

### 3. Dimension Keys Per Class (ป้องกัน AI สับสน)
* **`IfcWall`:** `[thickness, height]` — *ห้ามใส่ length หรือ width* (ความยาวคำนวณจากระยะกริตอัตโนมัติ).
* **`IfcBeam`:** `[width, depth]` — *ห้ามใช้ height* (width = ความกว้างหน้าคาน, depth = ความลึกคานในแนวดิ่ง).
* **`IfcColumn`:** `[width, depth]` — มิติหน้าตัดตามแกน $X \times Y$.
* **`IfcSlab`:** `[thickness]` — ความหนาแผ่นพื้น.
* **`IfcSpace`:** `[height]` — ความสูงเคลียร์ของห้อง.
* **`IfcFurniture`:** `[width, depth, height]` — ขนาดตามแกน $X \times Y \times Z$.

---

## 🎯 Hybrid Reference Design (Grid + Offset + Inset)

Room boundaries and partitions rarely align perfectly with structural column grids. debim supports 3 flexible, interchangeable reference modes:

### Mode 1: Grid-Offset Mathematical Expressions
Human-readable arithmetic strings referencing grid centerlines with offsets:
```yaml
placement:
  boundary:
    - ["GX_1 + 0.10", "GY_1 + 0.10"]   # Offset 10cm inside from structural column grid
    - ["GX_2 - 0.10", "GY_1 + 0.10"]
    - ["GX_2 - 0.10", "GY_2 - 0.10"]
    - ["GX_1 + 0.10", "GY_2 - 0.10"]
```

### Mode 2: Automatic Inset (`inset` / `boundary_offset`)
Define the main column grids and automatically shrink/expand the polygon:
```yaml
placement:
  boundary:
    - [GX_1, GY_1]
    - [GX_2, GY_1]
    - [GX_2, GY_2]
    - [GX_1, GY_2]
  inset: 0.10   # Shrinks polygon inward by 10cm to account for half-wall thickness
```

### Mode 3: Explicit Cartesian Coordinates (`boundary_points`)
Direct $(X, Y)$ coordinate tuples in meters, ideal for irregular rooms or imported CAD/IFC polygons:
```yaml
placement:
  boundary_points:
    - [2.50, 1.20]
    - [6.50, 1.20]
    - [6.50, 4.80]
    - [2.50, 4.80]
```

---

## 🏢 Room & Space Modeling (`IfcSpace`)

Representing room geometry, usable areas, and HVAC volumes:
```yaml
- class: IfcSpace
  tag: master-bedroom
  name: "Master Bedroom"
  long_name: "Master Bedroom 101"
  room_number: "101"
  height: 2.80
  placement:
    storey: 00 groundfloor
    boundary:
      - ["GX_1 + 0.10", "GY_1 + 0.10"]
      - ["GX_3 - 0.10", "GY_1 + 0.10"]
      - ["GX_3 - 0.10", "GY_3 - 0.10"]
      - ["GX_1 + 0.10", "GY_3 - 0.10"]
  properties:
    occupancy: 2
    hvac_zone: "ZONE-AC-01"
    finish_floor: "FIN-PARQUET-01"
    finish_ceiling: "FIN-GYPSUM-01"
```
* **Net Floor Area ($m^2$):** Calculated via Shoelace Formula on boundary.
* **Air Volume ($m^3$):** $\text{Floor Area} \times \text{Height}$ for cooling load calculations.

---

## ⚡ Agent Workflow (Step-by-Step)

### Step 1: Synthesize Declarative Manifest (`project.yaml` or `project.json`)
Create the building manifest adhering to `schemas/debim.schema.json`.

```yaml
schema: IFC4-Minimal
project:
  id: PRJ-HOUSE-01
  name: "Modern Residence"
  units:
    length: METER
    area: SQUARE_METER
    volume: CUBIC_METER

spatial_structure:
  storeys:
    - id: Ground
      name: "Ground Floor"
      elevation: 0.00
      height: 3.50

grids:
  axes_x:
    A: 0.00
    B: 4.00
    C: 8.00
  axes_y:
    1: 0.00
    2: 5.00
    3: 10.00

materials:
  - id: CONC_240
    name: "Ready-Mixed Concrete 240 ksc"
    category: concrete
    unit_cost_ref: "MAT-CONC-01"
  - id: STEEL_RB9
    name: "Round Bar Steel RB9"
    category: rebar
    unit_cost_ref: "MAT-STEEL-01"
  - id: BLOCK_AAC
    name: "Autoclaved Aerated Concrete 7.5cm"
    category: masonry
    unit_cost_ref: "MAT-BLOCK-01"

elements:
  # Columns
  - class: IfcColumn
    tag: C-A1
    material: CONC_240
    profile: { shape: BOX, width: 0.20, depth: 0.20 }
    placement: { grid: [A, 1], base_storey: Ground, top_storey: Ground }

  # Beams
  - class: IfcBeam
    tag: B-A1-B1
    material: CONC_240
    profile: { shape: BOX, width: 0.20, depth: 0.40 }
    placement:
      storey: Ground
      from_grid: [A, 1]
      to_grid: [B, 1]

  # Slabs
  - class: IfcSlab
    tag: S-1
    material: CONC_240
    thickness: 0.15
    placement:
      storey: Ground
      boundary: [[A, 1], [B, 1], [B, 2], [A, 2]]

  # Spaces (Rooms)
  - class: IfcSpace
    tag: living-room
    name: "Living Room"
    height: 3.00
    placement:
      storey: Ground
      boundary:
        - ["A + 0.10", "1 + 0.10"]
        - ["B - 0.10", "1 + 0.10"]
        - ["B - 0.10", "2 - 0.10"]
        - ["A + 0.10", "2 - 0.10"]
```

### Step 2: Validate Model Integrity & Continuity
Run validation for schema syntax, structural topological continuity (floating columns / unsupported beams), and MEP vs structural AABB clash detection:
```bash
# Standard CLI
debim validate -m project.yaml

# Strict schema & bSDD validation
debim validate -m project.yaml --bsdd --strict-psets

# Offline VM (Zero-Dependency)
python scripts/debim_zero.py validate project.yaml
```

### Step 3: Calculate Quantitative Take-Off (QTO)
```bash
# Standard CLI
debim qto -m project.yaml

# Offline VM (Zero-Dependency)
python scripts/debim_zero.py qto project.yaml
```

### Step 4: Generate Cost Estimation & Public Works BOQ
```bash
debim cost template -m project.yaml -o prices.yaml
debim cost -m project.yaml -p prices.yaml -o boq.csv

# Official Thai CGD ว480 BOQ with provincial pricing & Excel export (ปร.4, ปร.4(พ), ปร.5 sheets)
debim boq -m project.yaml --rules cg-v480 --province nakhon_ratchasima --export-excel boq_cgd.xlsx
```

### Step 5: Compile IFC4 & 3D Web Viewer
```bash
debim compile -m project.yaml -o model.ifc
debim view -m project.yaml -e viewer.html --no-browser
```

---

## 📂 Bundled Skill Assets

* **`SKILL.md`:** This master guide.
* **`schemas/debim.schema.json`:** Official offline JSON Schema (Draft 2020-12).
* **`scripts/debim_zero.py`:** Standalone Python standard library engine for air-gapped VMs.
* **`references/coordinate_and_bounding_rules.md`:** Formal specification of coordinate systems, winding rules, and vector formulas.
