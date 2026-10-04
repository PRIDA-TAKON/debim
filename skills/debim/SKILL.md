---
name: debim
description: Deterministic BOQ generation, Quantitative Take-Off (QTO), and Declarative BIM modeling (Building-as-Code) using debim. Use when asked to generate a bill of quantities (BOQ), estimate construction costs, calculate concrete/steel/formwork quantities from architectural plans or sketches, compile IFC4 models, or produce 3D HTML web viewers.
---

# debim Skill — Deterministic BOQ & Declarative BIM Engine

This skill empowers AI agents to generate professional, deterministic **Bills of Quantities (BOQ)**, calculate structural material quantities (**QTO**), and compile international standard **IFC4 BIM models** from architectural descriptions or sketches without hallucinating numbers.

---

## 🏛️ Core Philosophy for AI Agents

> **"Never guess construction numbers or hallucinate math in text."**

Instead of guessing concrete cubic meters or estimating rebar weights with vague approximations, the agent synthesizes the building geometry into a minimal **Declarative YAML manifest** (`project.yaml`) and executes `debim` commands to produce mathematically exact figures.

---

## ⚡ Agent Workflow (Step-by-Step)

### Step 1: Check or Install `debim`
Ensure `debim` CLI is available in the environment:
```bash
debim --help
```
If not installed, install it via pip:
```bash
pip install debim
# Or with IFC compiler:
pip install "debim[ifc]"
```

### Step 2: Synthesize Declarative YAML (`project.yaml`)
Create a project manifest adhering to the `IFC4-Minimal` schema.

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
    - id: Upper
      name: "Second Floor"
      elevation: 3.50
      height: 3.20

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
    placement: { grid: [A, 1], base_storey: Ground, top_storey: Upper }

  # Beams
  - class: IfcBeam
    tag: B-A1-B1
    material: CONC_240
    profile: { shape: BOX, width: 0.20, depth: 0.40 }
    placement:
      storey: Upper
      from_grid: [A, 1]
      to_grid: [B, 1]

  # Slabs
  - class: IfcSlab
    tag: S-1
    material: CONC_240
    thickness: 0.15
    placement:
      storey: Upper
      boundary: [[A, 1], [B, 1], [B, 2], [A, 2]]

  # Walls
  - class: IfcWall
    tag: W-A1-A2
    material: BLOCK_AAC
    thickness: 0.10
    placement:
      storey: Ground
      from_grid: [A, 1]
      to_grid: [A, 2]
```

### Step 3: Validate Model Integrity
Always run `debim validate` to ensure 3D Cartesian coordinates, storey elevations, and grid alignments are consistent:
```bash
debim validate -m project.yaml
```

### Step 4: Calculate Quantitative Take-Off (QTO)
Extract exact concrete volume ($m^3$), formwork surface area ($m^2$), and rebar schedule ($kg$):
```bash
debim qto -m project.yaml
```

### Step 5: Generate Project-Scoped Price Catalog
Scaffold a minimal price catalog tailored specifically to the model's materials:
```bash
debim cost template -m project.yaml -o prices.yaml
```
Populate realistic benchmark prices (`material_cost` and `labor_cost`) in `prices.yaml` (using local standards or `thai_construction_material_prices` skill if in Thailand).

### Step 6: Compute Full Budget & Export BOQ
Calculate total project cost and generate `boq.csv`:
```bash
debim cost -m project.yaml -p prices.yaml -o boq.csv
```

### Step 7: Export 3D HTML Viewer for Client Verification
Generate a standalone zero-dependency 3D web viewer:
```bash
debim view -m project.yaml -e viewer.html --no-browser
```

### Step 8: Present Results to User
Format the output professionally:
1. **Summary Table:** High-level material volumes and cost breakdown (Concrete, Rebar, Formwork, Finishes).
2. **Deterministic Confidence:** State that quantities are calculated directly from 3D geometry rules.
3. **Artifacts:** Link to the generated `project.yaml`, `boq.csv`, and `viewer.html`.
