# debim 🏛️⚡

> **A minimal, Git-native, declarative BIM engine (Building-as-Code) designed for AI agents and humans.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![BIM: IFC4](https://img.shields.io/badge/IFC-IFC4--Minimal-brightgreen.svg)](https://technical.buildingsmart.org/)

---

## ✨ Highlights

- 📝 **Semantic Declarative Model:** Buildings defined in clean, human-readable YAML (`project.yaml`).
- 🤖 **Agent-Friendly & Git-Native:** Version control your architecture like code. AI agents can easily parse, review, diff, and modify designs.
- 📐 **Relative Spatial Placement:** Align elements by grid intersections (e.g. `grid: [A, 1]`) and storey elevations with zero cumulative measurement error.
- 🧪 **Law-as-Code (Automated Compliance):** Building codes, setbacks, FAR, OSR, and clearance heights checked automatically using `pytest`.
- 📊 **Instant QTO & Costing:** Calculate concrete volumes, formwork areas, rebar schedules, and cost estimates in seconds.
- 📦 **Standard IFC4 Compilation:** Compile declarative models directly into standard IFC for Revit, FreeCAD, and Blender.

---

## 🚀 Quickstart

### Installation

```bash
# Clone the repository
git clone https://github.com/PRIDA-TAKON/debim.git
cd debim

# Install in editable mode
pip install -e .

# Or with IFC compilation support
pip install -e ".[ifc,dev]"
```

### Basic Commands

```bash
# Create a new project scaffold
bim init my-project

# Validate syntax and placement references
bim validate

# Run building code compliance tests
bim test

# Calculate quantities of materials (QTO)
bim qto

# Estimate project cost with price catalog
bim cost

# Compile to IFC4 model
bim compile -o dist/model.ifc

# Launch browser-based 3D preview
bim view
```

---

## 🏗️ Example `project.yaml`

```yaml
schema: IFC4-Minimal
project:
  id: PRJ-2026-001
  name: "Townhouse-Feasibility"
  units: { length: METER, area: SQUARE_METER, volume: CUBIC_METER }

spatial_structure:
  storeys:
    - id: L1
      name: "Level 1"
      elevation: 0.00
      height: 3.50
    - id: L2
      name: "Level 2"
      elevation: 3.50
      height: 3.20

grids:
  axes_x: { A: 0.00, B: 4.00, C: 8.00 }
  axes_y: { 1: 0.00, 2: 5.00, 3: 10.00 }

materials:
  - id: CONC_240
    name: "Concrete 240 ksc"
    category: concrete
    unit_cost_ref: "MAT-CONC-01"

elements:
  - class: IfcColumn
    tag: C-A1
    material: CONC_240
    profile: { shape: BOX, width: 0.20, depth: 0.20 }
    placement:
      grid: [A, 1]
      base_storey: L1
      top_storey: L2
```

---

## 📄 License

This project is licensed under the terms of the [MIT License](LICENSE).
