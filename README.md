# debim 🏛️⚡

> **A minimal, Git-native, declarative BIM engine (Building-as-Code) designed for AI agents and humans.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![BIM: IFC4](https://img.shields.io/badge/IFC-IFC4--Minimal-brightgreen.svg)](https://technical.buildingsmart.org/)
[![Tests: 98 Passed](https://img.shields.io/badge/tests-98%20passed-success.svg)](tests/)
[![Benchmark: 407 Models (100% Median)](https://img.shields.io/badge/benchmark-407%20models%20(100%25%20median)-blue.svg)](docs/research/2026_empirical_study_407_ifc_models.md)

---

## 🎯 Why debim? (ทำไมเราถึงสร้าง debim ขึ้นมา?)

Traditional BIM tools (like Revit or Archicad) were built over 25 years ago for humans clicking with computer mice. They lock architectural data in heavy, proprietary gigabyte files (`.rvt`), charge thousands of dollars in annual licenses, and remain completely opaque to modern automation and AI agents.

**debim** introduces **Building-as-Code**:
1. **Human-First & Git-Native:** Architecture is expressed as plain text in YAML (`project.yaml`). Files are kilobytes instead of gigabytes. You can version-control buildings with Git and inspect design changes line-by-line.
2. **Agent-Friendly by Design:** LLMs and autonomous coding agents (Jules, Claude, Antigravity) can read, modify, and optimize building designs natively without needing proprietary APIs.
3. **Law-as-Code:** Building regulations (e.g. ministerial setback laws, clear heights, FAR) are codified as automated unit tests (`pytest`). If a design change violates local building codes, tests fail in CI/CD before breaking ground.
4. **Site-Reality Driven (Grid-Relative):** In real construction, builders pull measuring tapes from grid lines (`[A, 1] + offset`), not global Cartesian `(X, Y, Z)` coordinates. debim computes the math so humans and foremen don't have to.
5. **Open Standard Interoperability:** Compile directly into standard **IFC4** files (`dist/model.ifc`) to continue 2D drafting and documentation in BlenderBIM, FreeCAD, or Revit.

---

## 🤖 AI-Agent Installation (ติดตั้งง่ายที่สุดในโลกด้วย AI ของคุณ)

If you use an AI coding assistant (like **Antigravity, Cursor, Claude Code, Jules, or ChatGPT/Copilot**), you don't even need to install it manually!

Just copy and send this prompt to your AI:

> *"Please read https://github.com/PRIDA-TAKON/debim and `AGENTS.md`, install debim in my environment, and run `bim --help` to verify."*

Your agent will inspect the repository, install the dependencies, and verify everything automatically.

---

## 🚀 Manual Quickstart

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/PRIDA-TAKON/debim.git
cd debim

# Install in editable mode
pip install -e .

# Or with full dev & IFC compiler tools
pip install -e ".[ifc,dev]"
```

### 2. Basic Commands

```bash
# Initialize a new project
bim init my-project

# Validate schema syntax & grid references
bim validate -m examples/townhouse/project.yaml

# Run automated building code compliance checks (pytest)
bim test

# Calculate Quantitative Take-Off (Concrete vol, formwork, rebar schedule)
bim qto -m examples/townhouse/project.yaml

# Generate project-scoped price template with international classifications
bim cost template -m examples/townhouse/project.yaml -o prices.template.yaml

# Estimate project budget & export BOQ to CSV
bim cost -m examples/townhouse/project.yaml -p examples/townhouse/prices.json -o dist/boq.csv

# Scaffold a new BIM element class boilerplate
bim scaffold element IfcRailing

# Preview 3D model in your browser (Three.js with Hierarchical Layer Explorer)
bim view -m examples/townhouse/project.yaml

# Compile declarative YAML to standard IFC4 building model
bim compile -m examples/townhouse/project.yaml -o dist/model.ifc
```

---

## 🏗️ Example `project.yaml`

```yaml
schema: IFC4-Minimal
project:
  id: PRJ-2026-001
  name: "Townhouse-Feasibility"
  units: { length: METER, area: SQUARE_METER, volume: CUBIC_METER }

# 1. Spatial Structure
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

# 2. Reference Grid Axes
grids:
  axes_x: { A: 0.00, B: 4.00, C: 8.00 }
  axes_y: { 1: 0.00, 2: 5.00, 3: 10.00 }

# 3. Materials
materials:
  - id: CONC_240
    name: "Concrete 240 ksc"
    category: concrete
    unit_cost_ref: "MAT-CONC-01"
  - id: AAC_75
    name: "AAC Block 7.5cm"
    category: masonry
    unit_cost_ref: "MAT-AAC-01"

# 4. Elements
elements:
  # Column placed at grid intersection [A, 1]
  - class: IfcColumn
    tag: C-A1
    material: CONC_240
    profile: { shape: BOX, width: 0.20, depth: 0.20 }
    placement:
      grid: [A, 1]
      base_storey: L1
      top_storey: L2
    reinforcement:
      main: "4-DB16"
      stirrups: "RB6 @ 0.15m"

  # Beam spanning between [A, 1] and [B, 1]
  - class: IfcBeam
    tag: B-A1_B1
    material: CONC_240
    profile: { shape: BOX, width: 0.20, depth: 0.40 }
    placement:
      from_grid: [A, 1]
      to_grid: [B, 1]
      storey: L2
    reinforcement:
      main_top: "2-DB16"
      main_bottom: "3-DB20"
      stirrups: "RB9 @ 0.15m"

  # Wall with door host-child relationship
  - class: IfcWall
    tag: W-A1_A2
    material: AAC_75
    thickness: 0.075
    height: 3.10
    placement:
      from_grid: [A, 1]
      to_grid: [A, 2]
      storey: L1
    children:
      - class: IfcDoor
        tag: D1
        dimensions: { width: 0.90, height: 2.00 }
        offset_distance: 1.20
```

---

## 🔬 Empirical Research & Benchmark (การทดสอบระดับอุตสาหกรรม)

debim ได้รับการทดสอบอย่างเข้มงวดกับโมเดลอาคารจริงในระดับอุตสาหกรรมกว่า **407 โครงการ** (ทั้งสถาปัตยกรรม โครงสร้าง และงานระบบโรงพยาบาล/คลินิก MEP) บน **Kaggle Cloud Multi-Core Benchmark Suite**:

- **100.0% Median Retention Rate:** โมเดลส่วนใหญ่สามารถสกัดและ Re-compile กลับสู่มาตรฐาน IFC4 ได้ครบถ้วนทุกชิ้นงาน
- **91.6% Average Storage Reduction:** ลดขนาดไฟล์จาก IFC ดิบลงเฉลี่ย 91%
- **558M+ LLM Tokens Saved:** ประหยัดบริบทของโมเดลภาษาไปได้มากกว่า **558,629,804 โทเคน**
- **100.0% Modern Schema Crash-Resilience:** ไม่พบ Fatal Crash หรือ Unhandled Exception เลยแม้แต่ไฟล์เดียวบนมาตรฐาน IFC2X3 และ IFC4

📖 **อ่านรายงานวิจัยฉบับเต็ม:** [debim: An Empirical Study of Declarative Building-as-Code on 407 Heterogeneous Real-World OpenBIM Models](docs/research/2026_empirical_study_407_ifc_models.md) (Author: Prida Takon)  
📦 **Kaggle Public Benchmark Dataset:** [debim-5000-ifc-benchmark](https://www.kaggle.com/datasets/pridatakon/debim-5000-ifc-benchmark)  
⚡ **Kaggle Automated Runner:** [debim-ifc-stress-test](https://www.kaggle.com/code/pridatakon/debim-ifc-stress-test)

---

## ❓ Frequently Asked Questions (FAQ)

<details>
<summary><b>Why YAML instead of JSON, Python, or Excel?</b></summary>
<br>
YAML is clean, concise, supports nested hierarchies, and allows comments (essential for architectural notes). Unlike JSON, it has no noisy braces. Unlike Excel, it is 100% Git-friendly, diffable, and conflict-resolvable. It serves as a pure declarative DSL (Domain-Specific Language)—just like Kubernetes, Docker Compose, and GitHub Actions.
</details>

<details>
<summary><b>How do I place off-grid items (internal partitions, cantilever beams)?</b></summary>
<br>
Use relative offsets: `placement: { grid: [A, 1], offset: [1.20, 0.50] }`. Just like pulling a tape measure on site from the nearest grid line.
</details>

<details>
<summary><b>Does this replace Revit or AutoCAD?</b></summary>
<br>
No, it complements them. debim handles the early-stage upstream workload: rapid feasibility, parametric sizing, AI generation, instant QTO/costing, and automated building law validation. Once validated, run <code>bim compile</code> to export standard IFC4 and load it directly into BlenderBIM, FreeCAD, or Revit for 2D drafting and detail annotations.
</details>

---

## 📄 License & Attribution

- **Software Code:** Licensed under the [MIT License](LICENSE) — Copyright (c) 2026 Prida Takon.
- **Research & Technical Reports:** Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
- **Benchmark Datasets & Sample Models:** Test fixtures in `tests/fixtures/` originate from [buildingSMART International](https://github.com/buildingSMART) and the Open IFC Model Repository under CC BY 4.0 / CC-BY-3.0.
