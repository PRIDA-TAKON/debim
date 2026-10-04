# AGENTS.md — Instructions for AI Agents (Jules, etc.)

Welcome to **debim** (Declarative BIM / Building-as-Code). This repository implements a minimal, Git-native, declarative BIM compiler designed for AI agents and human architects/engineers.

---

## 🏛️ Core Philosophy & Design Manifesto (เข็มทิศการออกแบบ debim)

> **"หัวใจของ debim เริ่มจากการอยากให้ AI ทำ BOQ แต่การให้ AI คำนวณตึกทั้งหลังตรงๆ AI ตายแน่ จึงต้องใช้แบบจำลองคณิตศาสตร์ (BIM) ทว่ามาตรฐาน IFC ดั้งเดิมก็ซับซ้อนเกินไป หนักสมอง AI อีก จึงกลั่นออกมาเป็น Declarative YAML — แต่ผลพลอยได้ที่ได้รับกลับยิ่งใหญ่กว่าเป้าหมายแรกเริ่ม"**

ทุกครั้งที่จะออกแบบฟีเจอร์ใหม่, ปรับปรุงสถาปัตยกรรม, หรือขยายความสามารถของระบบ **ห้ามละทิ้ง 5 เสาหลักนี้เด็ดขาด**:

1. **Building-as-Code & Git-Native (อาคารคือซอฟต์แวร์):**
   - อาคารต้องแสดงออกเป็น Text/YAML ที่กะทัดรัด (Kilobytes ไม่ใช่ Gigabytes) เพื่อให้ทำ Version Control, Git diff, และ Branching ได้อย่างโปร่งใสและเป็นมิตรกับ Context Window ของ AI
2. **Deterministic Code Compliance (กฎหมายและวิศวกรรมคือ Unit Test):**
   - กฎหมายควบคุมอาคาร, ข้อกำหนดวิศวกรรม, ระยะร่น, และตรรกะโครงสร้าง ต้องตรวจสอบได้แบบ Deterministic ผ่าน Test Automation (`pytest`) ในเสี้ยววินาที ไม่ใช่การเดาหรือกะประมาณ
3. **Zero-License & Zero-Friction Visualization (เห็นจริงโดยไม่ต้องพึ่งพาซอฟต์แวร์แพง):**
   - ผลลัพธ์ต้องตรวจสอบด้วยสายตาได้ทันทีผ่าน 3D HTML Viewer น้ำหนักเบาที่เปิดได้บนทุกอุปกรณ์โดยไม่ต้องติดตั้งซอฟต์แวร์ราคาแพง ตรวจสอบความถูกต้องได้ภายใน 2 วินาที
4. **Universal Bridge & Dual Representation (เชื่อมโยงทุกค่าย ไม่ทิ้งความประณีต):**
   - ทำหน้าที่เป็นตัวกลางเชื่อม 2D, 3D (SketchUp/Blender), และ IFC สากล โดยใช้วิธี Dual Representation (90% Primitives สำหรับคำนวณโครงสร้างและ BOQ + 10% Baked Asset GLB สำหรับชิ้นงานดีเทลประณีต)
5. **Human & AI Super-Collaboration (Explicit Uncertainty):**
   - ออกแบบโครงสร้างข้อมูลให้อ่านง่ายสำหรับทั้งมนุษย์และ AI เมื่อระบบไม่มั่นใจ ต้องมี Flag แสดงความไม่แน่นอน (`needs_review`) เพื่อให้มนุษย์และ AI ช่วยกันเติมเต็มและตรวจสอบได้อย่างไร้รอยต่อ

---

## 📂 Repository Structure

```plaintext
debim/
├── src/
│   └── debim/
│       ├── __init__.py
│       ├── cli.py             # CLI entrypoint (debim)
│       ├── schema.py          # Pydantic v2 data models for project.yaml
│       ├── resolver.py        # Resolves relative grid & storey coordinates to 3D world vectors
│       ├── qto.py             # Quantitative Take-Off (concrete vol, formwork area, rebar)
│       ├── cost.py            # Pricing engine matching QTO with prices.yaml/prices.json
│       ├── compiler.py        # IFC4 compilation via IfcOpenShell
│       ├── viewer.py          # Standalone lightweight 3D viewer generator
│       └── scaffold.py        # Element code generator & boilerplate scaffolder
├── examples/
│   └── farnsworth_house/
│       ├── project.yaml       # Sample project manifest (Ludwig Mies van der Rohe, 1951)
│       ├── prices.yaml        # Sample price catalog
│       └── viewer.html        # Lightweight 3D HTML viewer
├── tests/
│   ├── conftest.py            # Pytest fixtures loading project.yaml
│   ├── test_schema.py         # Schema parsing & validation tests
│   ├── test_qto.py            # Volume & reinforcement calculation tests
│   └── test_compliance.py     # Building law compliance test suites
├── pyproject.toml
├── README.md
└── AGENTS.md
```

---

## 🛠️ Tech Stack & Conventions

- **Language:** Python 3.11+
- **CLI Framework:** Typer + Rich
- **Data Validation:** Pydantic v2
- **Data Serialization:** PyYAML
- **3D / Geometry:** Trimesh, NumPy
- **BIM / IFC:** IfcOpenShell (`ifcopenshell`)
- **Testing:** Pytest

---

## 💰 Pricing Catalog Conventions (prices.yaml vs prices.json)

debim supports both YAML and JSON price catalogs with standard classification metadata (`standards: {masterformat: ..., uniformat: ...}`):

- **Default to `prices.yaml` (or modular `prices/modules/*.yaml`):**
  - Use when authoring, reviewing, or version-controlling prices with Git.
  - Allows human-readable comments (`# e.g. Q3-2026 commercial benchmark`).
  - Supports modular multi-file catalogs via `includes: ["modules/*.yaml"]` to prevent token bloat (saving up to 99% tokens for large catalogs).
- **Use `prices.json` or Stdin Pipe (`-p -`):**
  - Use when streaming raw price payloads directly from external REST APIs, ERP systems, or database queries.
- **Generate Project-Scoped Active Templates:**
  - Never parse tens of thousands of global catalog items into an agent's context.
  - Run `debim cost template -m project.yaml -o prices.template.yaml` to extract only the active items used by the building model.

---

## 🧪 Testing & Quality Standards

When working on any GitHub Issue or Pull Request:
1. **Always run unit tests:**
   ```bash
   pytest
   ```
2. **Surgical Updates:** Only modify lines and files relevant to your assigned task. Never perform unsolicited refactoring or file restructuring.
3. **Test-Driven:** Every new feature (QTO formula, schema validator, compliance rule) must include corresponding unit tests in `tests/`.
4. **Strict Schema Adherence:** Match entity names with standard buildingSMART IFC4 entities (`IfcColumn`, `IfcBeam`, `IfcWall`, `IfcDoor`, `IfcWindow`, `IfcSlab`).

---

## 📋 CLI Specification

The CLI tool exposes the binary command `debim`:

| Command | Action |
|---|---|
| `debim init <name>` | Scaffold a new project with template `project.yaml` & `prices.json` |
| `debim validate` | Validate schema syntax, grid consistency, and placement links |
| `debim test` | Execute compliance & building law tests via pytest |
| `debim qto` | Calculate material quantities (concrete volume, formwork, rebar) |
| `debim cost` | Map QTO against `prices.yaml`/`prices.json` (or stdin `-p -`) and generate cost summary / CSV |
| `debim cost template` | Scan project manifest & generate minimal, project-scoped price catalog template |
| `debim scaffold element <Name>` | Scaffold Pydantic model, resolver logic, QTO branch, and Pytest test skeleton |
| `debim compile` | Compile declarative YAML to standardized IFC4 file (`dist/model.ifc`) |
| `debim view` | Launch a lightweight local 3D preview server with hierarchical layer tree explorer |


