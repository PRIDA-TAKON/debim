<p align="center">
  <img src="docs/assets/logo.svg" alt="debim logo" width="740" />
</p>

<p align="center">
  <strong>A minimal, Git-native, declarative BIM engine (Building-as-Code) designed for AI agents and humans.</strong>
</p>

<p align="center">
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python: 3.11+" /></a>
  <a href="https://technical.buildingsmart.org/"><img src="https://img.shields.io/badge/BIM-IFC4--Minimal-brightgreen.svg" alt="BIM: IFC4" /></a>
  <a href="tests/"><img src="https://img.shields.io/badge/tests-98%20passed-success.svg" alt="Tests: 98 Passed" /></a>
  <a href="docs/research/2026_empirical_study_407_ifc_models.md"><img src="https://img.shields.io/badge/benchmark-407%20models%20(100%25%20median)-blue.svg" alt="Benchmark" /></a>
</p>

---

## 🎯 Why debim? (จุดกำเนิดและปรัชญาของ debim)

> *"หัวใจของ debim เริ่มจากการอยากให้ AI ทำ BOQ แต่การให้ AI คำนวณตึกทั้งหลังตรงๆ AI ตายแน่ จึงต้องใช้แบบจำลองคณิตศาสตร์ (BIM) ทว่ามาตรฐาน IFC ดั้งเดิมก็ซับซ้อนเกินไป หนักสมอง AI อีก จึงกลั่นออกมาเป็น Declarative YAML — แต่ผลพลอยได้ที่ได้รับกลับยิ่งใหญ่กว่าเป้าหมายแรกเริ่ม"*

Traditional BIM tools (like Revit or Archicad) were built over 25 years ago for humans clicking with computer mice. They lock architectural data in heavy, proprietary gigabyte files (`.rvt`), charge thousands of dollars in annual licenses, and remain completely opaque to modern automation and AI agents.

**debim** ยึดมั่นใน **5 เสาหลักแห่งการออกแบบ (Core Tenets)**:
1. **Building-as-Code & Git-Native:** อาคารคือซอฟต์แวร์ แสดงออกเป็นข้อความ YAML ขนาดกะทัดรัด (Kilobytes ไม่ใช่ Gigabytes) เพื่อให้ทำ Version Control, Git diff, และ Branching ตรวจสอบการแก้ไขได้ทีละบรรทัด
2. **Deterministic Code Compliance:** กฎหมายอาคารและข้อกำหนดวิศวกรรมถูกแปลงเป็น Unit Test (`pytest`) รันตรวจจับข้อผิดพลาดและระยะร่นใน 0.01 วินาทีก่อนลงมือก่อสร้างจริง
3. **Zero-License & Zero-Friction Visualization:** ตรวจสอบความถูกต้องทางเรขาคณิตได้ทันทีผ่าน 3D HTML Viewer น้ำหนักเบา เปิดบนเบราว์เซอร์หรือมือถือได้ทันที ไม่ต้องมีไลเซนส์ซอฟต์แวร์ราคาแพง
4. **Universal Bridge & Dual Representation:** ตัวกลางเชื่อมโยง 2D, 3D (SketchUp/Blender), และ IFC โดยผสมผสาน 90% Primitives สำหรับคำนวณโครงสร้างและ BOQ + 10% Baked GLB Asset สำหรับงานสถาปัตย์ประณีต
5. **Human & AI Super-Collaboration:** ออกแบบให้มี Explicit Uncertainty (`review_status: needs_review`) ให้มนุษย์และ AI ร่วมมือกันตรวจและเติมเต็มสเปกได้อย่างไร้รอยต่อ

---

## 🤖 AI-Agent Installation (ติดตั้งง่ายที่สุดในโลกด้วย AI ของคุณ)

If you use an AI coding assistant (like **Antigravity, Cursor, Claude Code, Jules, or ChatGPT/Copilot**), you don't even need to install it manually!

Just copy and send this prompt to your AI:

> *"Please read https://github.com/PRIDA-TAKON/debim and `AGENTS.md`, install debim in my environment, and run `debim --help` to verify."*

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
debim init my-project

# Validate schema syntax & grid references
debim validate -m examples/townhouse/project.yaml

# Run automated building code compliance checks (pytest)
debim test

# Calculate Quantitative Take-Off (Concrete vol, formwork, rebar schedule)
debim qto -m examples/townhouse/project.yaml

# Generate project-scoped price template with international classifications
debim cost template -m examples/townhouse/project.yaml -o prices.template.yaml

# Estimate project budget & export BOQ to CSV
debim cost -m examples/townhouse/project.yaml -p examples/townhouse/prices.json -o dist/boq.csv

# Scaffold a new BIM element class boilerplate
debim scaffold element IfcRailing

# Preview 3D model in your browser (Three.js with Hierarchical Layer Explorer)
debim view -m examples/townhouse/project.yaml

# Compile declarative YAML to standard IFC4 building model
debim compile -m examples/townhouse/project.yaml -o dist/model.ifc
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
No, it complements them. debim handles the early-stage upstream workload: rapid feasibility, parametric sizing, AI generation, instant QTO/costing, and automated building law validation. Once validated, run <code>debim compile</code> to export standard IFC4 and load it directly into BlenderBIM, FreeCAD, or Revit for 2D drafting and detail annotations.
</details>

---

## 📄 License & Attribution

- **Software Code:** Licensed under the [MIT License](LICENSE) — Copyright (c) 2026 Prida Takon.
- **Research & Technical Reports:** Licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
- **Benchmark Datasets & Sample Models:** Test fixtures in `tests/fixtures/` originate from [buildingSMART International](https://github.com/buildingSMART) and the Open IFC Model Repository under CC BY 4.0 / CC-BY-3.0.
