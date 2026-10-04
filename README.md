<p align="center">
  <img src="docs/assets/logo.svg" alt="debim logo" width="740" />
</p>

<p align="center">
  <strong>A minimal, Git-native, declarative BIM engine (Building-as-Code) designed for AI agents and humans.</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/debim/"><img src="https://img.shields.io/pypi/v/debim.svg?color=blue" alt="PyPI Version" /></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python: 3.11+" /></a>
  <a href="https://technical.buildingsmart.org/"><img src="https://img.shields.io/badge/BIM-IFC4--Minimal-brightgreen.svg" alt="BIM: IFC4" /></a>
  <a href="tests/"><img src="https://img.shields.io/badge/tests-149%20passed-success.svg" alt="Tests: 149 Passed" /></a>
  <a href="https://www.kaggle.com/code/pridatakon/debim-3d-visual-balanced-benchmark"><img src="https://img.shields.io/badge/visual%20fidelity-85.5%25%20median-brightgreen.svg" alt="Visual Fidelity: 85.5% Median" /></a>
  <a href="https://prida-takon.github.io/debim/"><img src="https://img.shields.io/badge/Live%203D%20Demo-Interactive%20Viewer-2ea44f.svg?logo=three.js" alt="Live 3D Demo" /></a>
</p>

<p align="center">
  <a href="https://prida-takon.github.io/debim/">
    <img src="https://img.shields.io/badge/🔴%20Click%20Here-Open%20Live%203D%20Viewer%20(No%20Install)-2ea44f?style=for-the-badge&logo=three.js" alt="Open Live 3D Demo" />
  </a>
</p>

---

<p align="center">
  <table width="100%">
    <tr>
      <td width="50%" align="center" valign="top">
        <b>💻 Modern CLI, QTO & Costing Engine</b><br>
        <img src="docs/assets/terminal_preview.png" alt="debim Terminal CLI - Farnsworth House" width="100%" />
      </td>
      <td width="50%" align="center" valign="top">
        <b>🌐 Zero-Install 3D Web Viewer (<a href="https://prida-takon.github.io/debim/">Try Live Demo</a>)</b><br>
        <a href="https://prida-takon.github.io/debim/"><img src="docs/assets/viewer_preview.png" alt="debim 3D HTML Viewer - Farnsworth House (1951)" width="100%" /></a>
      </td>
    </tr>
  </table>
  <sub>🏛️ <i>Showcase: Ludwig Mies van der Rohe's iconic <b>Farnsworth House (1951)</b> — compiled from declarative YAML (<a href="examples/farnsworth_house/project.yaml">examples/farnsworth_house/project.yaml</a>) into standard IFC4 and rendered in real-time in a lightweight 3D web viewer.</i></sub>
</p>

> [!TIP]
> **🤖 Authored 100% by AI Agent (Antigravity powered by Gemini 3.8 Flash):**  
> โมเดลสถาปัตยกรรมระดับโลกชิ้นนี้ **ไม่ได้เขียนด้วยมือมนุษย์ทีละบรรทัด!** แต่เกิดจากการให้ **AI Coding Agent (Antigravity ขับเคลื่อนด้วย Gemini 3.8 Flash)** ทำการสืบค้นข้อมูลแบบแปลน มิติโครงสร้าง และระยะกริดทางประวัติศาสตร์ของ Farnsworth House ด้วยตนเอง แล้วสังเคราะห์โค้ด Declarative YAML (`project.yaml`) ออกมาโดยอัตโนมัติ ก่อนสั่งให้ `debim` ถอดปริมาณงาน (QTO) และคอมไพล์เป็น IFC4 มาตรฐานสากลในเสี้ยววินาที — ยืนยันว่า **คุณไม่จำเป็นต้องพิมพ์โค้ดเองทั้งหมดหากทำงานร่วมกับ AI Agent!**

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

## 🚀 Quickstart
 
### 1. Installation

Install directly from **[PyPI](https://pypi.org/project/debim/)**:

```bash
# Standard installation
pip install debim

# Or with full IFC compiler support
pip install "debim[ifc]"
```

Or install in editable mode from source:

```bash
git clone https://github.com/PRIDA-TAKON/debim.git
cd debim
pip install -e ".[ifc,dev]"
```

### 2. Basic Commands

```bash
# Initialize a new project
debim init my-project

# Validate schema syntax & grid references
debim validate -m examples/farnsworth_house/project.yaml

# Run automated building code compliance checks (pytest)
debim test

# Calculate Quantitative Take-Off (Steel weight, stone volume, glass area)
debim qto -m examples/farnsworth_house/project.yaml

# Generate project-scoped price template with international classifications
debim cost template -m examples/farnsworth_house/project.yaml -o prices.template.yaml

# Estimate project budget & export BOQ to CSV
debim cost -m examples/farnsworth_house/project.yaml -p examples/farnsworth_house/prices.yaml -o dist/boq.csv

# Scaffold a new BIM element class boilerplate
debim scaffold element IfcRailing

# Preview 3D model in your browser (Three.js with Hierarchical Layer Explorer)
debim view -m examples/farnsworth_house/project.yaml

# Compile declarative YAML to standard IFC4 building model
debim compile -m examples/farnsworth_house/project.yaml -o dist/farnsworth_house.ifc
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

debim ให้ความสำคัญกับความถูกต้องทางวิศวกรรมและการทดสอบแบบเปิดเผย ตรวจสอบซ้ำได้จริง (100% Reproducible Open Science) บน **Kaggle Cloud Multi-Core Benchmark Suite**:

### 1. ⚖️ 3D Visual Regression & Alignment Benchmark (255 อาคารจริงสากล)

<p align="center">
  <a href="https://www.kaggle.com/code/pridatakon/debim-3d-visual-balanced-benchmark">
    <img src="https://img.shields.io/badge/Kaggle-Run%20Reproducible%20Benchmark-20BEFF?logo=kaggle&style=for-the-badge" alt="Kaggle Benchmark" />
  </a>
</p>

การทดสอบความแม่นยำด้านเรขาคณิต 3 มิติ (3D Visual Fidelity) แบบปิดตาเทียบกับ IFC ต้นฉบับผ่าน **Geometry Variant Deduplication + Balanced Macro-Averaging** บน 4,695 ชิ้นส่วนตัวแทน:

- **🎯 85.50% Median Visual Fidelity:** ทะลุเกณฑ์มาตรฐานสากล ($\ge 85\%$) ครอบคลุมเกินกึ่งหนึ่งของโมเดลทดสอบ
- **🏗️ 89.07% Structural Match:** งานโครงสร้างรับแรงหลัก (เสา คาน ผนัง ฐานราก) มีความเสถียรระดับเกรด A+
- **⚡ 82.64% MEP System Match:** งานระบบท่อ ระบบปรับอากาศ และอุปกรณ์ไฟฟ้าอยู่ในตำแหน่งและระนาบที่ถูกต้อง

#### 📈 วิวัฒนาการเปรียบเทียบข้าม 3 เจเนอเรชัน (Progression Across Waves):

| ตัวชี้วัดสากล (Global Metric) | V1 (Baseline) | V2 (Wave 1-2) | V3 (Wave 4 ล่าสุด) | $\Delta$ พัฒนาขึ้นสะสม |
|---|:---:|:---:|:---:|:---:|
| **🎯 Median Visual Match (ค่ามัธยฐาน)** | 80.90% | 84.90% | **85.50%** | 🏆 **+4.60% (ทะลุเป้า 85%)** |
| **⚖️ Macro Average Visual Match** | 70.57% | 77.60% | **77.71%** | 🟢 **+7.13%** |
| **📊 Micro Average Visual Match** | 72.24% | 80.35% | **80.46%** | 🟢 **+8.23%** |
| **ชิ้นส่วนที่ผ่านเกณฑ์ ($\ge 85\%$)** | 2,865 ชิ้น | 3,140 ชิ้น | **3,135 ชิ้น** | 🟢 **+270 ชิ้น** |
| **หมวดหมู่งานระบบและตกแต่งที่ก้าวกระโดด** | | | | |
| • *ฝ้าเพดาน (`IfcCovering`)* | 11.4% | 89.0% | **89.0%** | 🟢 **+77.6% (ผ่านเกณฑ์)** |
| • *วาล์วระบบท่อ (`IfcValve`)* | 0.0% | 82.2% | **82.4%** | 🟢 **+82.4% (พุ่งจากศูนย์)** |
| • *แผ่นเหล็กโครงสร้าง (`IfcPlate`)* | 10.2% | 88.9% | **87.1%** | 🟢 **+76.9% (ผ่านเกณฑ์)** |
| • *เหล็กค้ำยันเฉียง (`IfcMember`)* | 91.8% | 91.6% | **92.4%** | 🟢 **+0.8% (3D Vector Pitch)** |

👉 *ต้องการตรวจสอบการทดลองเชิงลึกหรือรันซ้ำด้วยตนเอง? ดูโค้ดและดาต้าเซ็ตได้ที่ [Kaggle Benchmark Notebook](https://www.kaggle.com/code/pridatakon/debim-3d-visual-balanced-benchmark)*

---

### 2. 📦 Roundtrip Retention & Storage Reduction Study (407 อาคารสากล)

debim ได้รับการทดสอบอย่างเข้มงวดกับโมเดลอาคารจริงกว่า **407 โครงการ** (สถาปัตยกรรม โครงสร้าง และ MEP โรงพยาบาล):

- **100.0% Median Retention Rate:** โมเดลส่วนใหญ่สามารถสกัดและ Re-compile กลับสู่มาตรฐาน IFC4 ได้ครบถ้วนทุกชิ้นงาน
- **91.6% Average Storage Reduction:** ลดขนาดไฟล์จาก IFC ดิบลงเฉลี่ย 91%
- **558M+ LLM Tokens Saved:** ประหยัดบริบทของโมเดลภาษาไปได้มากกว่า **558,629,804 โทเคน**
- **100.0% Modern Schema Crash-Resilience:** ไม่พบ Fatal Crash หรือ Unhandled Exception บนมาตรฐาน IFC2X3 และ IFC4

📖 **อ่านรายงานวิจัยฉบับเต็ม:** [debim: An Empirical Study of Declarative Building-as-Code on 407 Heterogeneous Real-World OpenBIM Models](docs/research/2026_empirical_study_407_ifc_models.md)  
📦 **Kaggle Public Benchmark Dataset:** [debim-5000-ifc-benchmark](https://www.kaggle.com/datasets/pridatakon/debim-5000-ifc-benchmark)  
⚡ **Kaggle Automated Stress Test:** [debim-ifc-stress-test](https://www.kaggle.com/code/pridatakon/debim-ifc-stress-test)

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
