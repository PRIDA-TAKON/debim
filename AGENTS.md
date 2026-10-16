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
│       ├── scaffold.py        # Element code generator & boilerplate scaffolder
│       ├── draw/              # 2D Architectural Blueprint & DXF Export Engine
│       │   ├── projection.py  # Horizontal cut-plane & 2D primitive slicing
│       │   ├── renderer.py    # SVG & CSS sheet renderer (Thai font support)
│       │   ├── viewer_2d.py   # Standalone 2D HTML blueprint viewer
│       │   └── dxf.py         # AutoCAD DXF export-only bridge
│       ├── spec/              # Declarative Architectural Specifications Engine
│       │   ├── schema.py      # Material specification schema (MasterFormat)
│       │   ├── audit.py       # Discrepancy auditor between 3D model & specs
│       │   ├── builder.py     # Specification book compiler (PDF/Markdown)
│       │   └── registry.py    # Open Material Registry client & cache
│       ├── cloud/             # Cloud Ephemeral Runner & Webhook Sync
│       │   ├── runner.py      # Zero-storage RAM/Temp runner for Cloud Run
│       │   ├── webhook.py     # GitHub Webhook HMAC SHA-256 verification
│       │   └── git_sync.py    # debim[bot] auto-committer
│       └── benchmark/         # Benchmarking Suites
│           ├── scalability.py # IFC generation speed & RAM scaling
│           └── cognitive.py   # Round-trip AI Vision cognitive regression benchmark
├── examples/
│   └── farnsworth_house/
│       ├── project.yaml       # Sample project manifest (Ludwig Mies van der Rohe, 1951)
│       ├── prices.yaml        # Sample price catalog
│       └── viewer.html        # Lightweight 3D HTML viewer
├── tests/                     # 325+ deterministic unit & compliance tests
├── pyproject.toml
├── README.md
└── AGENTS.md
```

---

## 🛠️ Tech Stack & Conventions (v0.6.0)

- **Language:** Python 3.11+
- **CLI Framework:** Python Standard Library `argparse` (Zero-dependency CLI architecture)
- **Data Validation:** Pydantic v2
- **Data Serialization:** PyYAML
- **Core 2D/3D Geometry:** Pure-Python `geometry2d.py`, NumPy (Divergence theorem for watertight volumes)
- **BIM Core:** Pure-Python `StepSerializer` (Built-in STEP ISO 10303-21 generation)
- **Optional Compilers:**
  - `debim[ifc]`: IfcOpenShell (`ifcopenshell`) for buildingSMART certification
  - `debim[docx]`: `python-docx` for Word specifications
  - `debim[mcp]`: Model Context Protocol FastMCP server
  - `ezdxf`: AutoCAD DXF export-only bridge
- **Testing:** Pytest (22/22 v0.6.0 suites passing)

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
3. **Test-Driven:** Every new feature (QTO formula, schema validator, compliance rule, 2D projection) must include corresponding unit tests in `tests/`.
4. **Strict Schema Adherence:** Match entity names with standard buildingSMART IFC4 entities (`IfcColumn`, `IfcBeam`, `IfcWall`, `IfcDoor`, `IfcWindow`, `IfcSlab`).

---

## 🏛️ Architectural Thinking & Modeling Sequence (The Architect's Two Hemispheres)

When tasked with creating, generating, or modifying building floor plans and models, agents MUST follow the two-phase architectural methodology detailed in `docs/ARCHITECTURAL_WORKFLOW.md`:

### Phase 1: Spatial Thinking & Programming (Before Drafting)
1. **Human Scale + 30% Circulation:** Compute room net areas by summing furniture/sanitary ware footprints and adding 30% intra-room circulation:
   $$\text{Area} = \left(\sum \text{Furniture Footprints}\right) \times 1.30$$
2. **Function Diagram & Adjacency:** Determine room-to-room connectivity and negative adjacencies (e.g. restrooms must not open directly into dining spaces; master bedrooms must not share walls with pump/mechanical rooms).
3. **Volumetric Spaces (`IfcSpace`):** Model invisible functional spaces. Add +30% overall circulation for hallways, corridors, and stairs.
4. **Site Boundaries & Stacking:** Comply with Thai building regulations (setbacks: 0.50m blind wall, 2.00m openings; OSR $\ge 30\%$; FAR). When ground floor coverage is exhausted, stack spaces vertically into upper storeys (Storey 1: Public/Semi-private, Storey 2: Private).
5. **MEP Coordination Hierarchy:**
   $$\textbf{MEP relocates first} \longrightarrow \textbf{Structure adapts second} \longrightarrow \textbf{Architectural Space & Clear Height are preserved}$$

### Phase 2: Drafting & BIM Modeling Sequence
1. **Schematic Layout:** Arrange functional spaces (`IfcSpace`).
2. **Columns (`IfcColumn`):** Place columns at regular structural spans (3.00m - 5.00m).
3. **Grid Axes (`grids`):** Establish reference grid lines through column centerlines.
4. **Framing (`IfcBeam`, `IfcSlab`):** Place beams, tie beams, and slabs floor-by-floor.
5. **Roof (`IfcRoof`):** Crown the structure with hip/gable roofs.
6. **Walls & Openings (`IfcWall`, `IfcDoor`, `IfcWindow`):** Place partitions. Place doors where `IfcSpace` entities connect in the Function Diagram.
7. **Verification & Error Detection:**
   - **Furniture Fit:** If Human Scale furniture cannot be accommodated or circulation path is $< 0.60$m, the layout is invalid.
   - **Adjacency Violation:** Verify no prohibited adjoining rooms.

---

## 📋 CLI Specification

The CLI tool exposes the binary command `debim`:

| Command | Action |
|---|---|
| `debim init <name>` | Scaffold a new project with template `project.yaml` & `prices.json` |
| `debim schema` | Export debim language specification as standalone JSON Schema (`--vscode` for IntelliSense) |
| `debim validate` | Validate schema syntax, grid consistency, placement links, and bSDD Psets |
| `debim test` | Execute compliance & building law tests via pytest |
| `debim qto` | Calculate material quantities (concrete volume, formwork, rebar) |
| `debim cost` | Map QTO against `prices.yaml`/`prices.json` (or stdin `-p -`) and generate cost summary / CSV |
| `debim cost template` | Scan project manifest & generate minimal, project-scoped price catalog template |
| `debim scaffold element <Name>` | Scaffold Pydantic model, resolver logic, QTO branch, and Pytest test skeleton |
| `debim compile` | Compile declarative YAML to standardized IFC4 file (`dist/model.ifc`) |
| `debim view` | Launch a lightweight local 3D preview server with hierarchical layer tree explorer |
| `debim split` | Decompose monolithic `project.yaml` into modular multi-file manifest under `models/` |
| `debim bundle` | Bundle modular multi-file manifest into a standalone single-file `project.yaml` |
| `debim diff` | Compare two YAML manifests and report 3D element deltas, QTO shifts, and cost variance |
| `debim draw view` | Generate standalone interactive 2D HTML blueprint viewer (`viewer_2d.html`) with pan-zoom & ruler |
| `debim draw export-dxf` | Export 2D section floor plan into AutoCAD DXF layers (`A-WALL`, `S-COLS`, `A-GRID`, ฯลฯ) |
| `debim spec audit` | Audit project manifest against material specifications to detect missing or unused specs |
| `debim spec build` | Scan active materials and compile a MasterFormat architectural Specification Book |
| `debim spec add <pkg>` | Install material specification package from open registry into `specs/` |
| `debim spec list` | List installed material specification packages in local project |
| `debim mcp` | Launch Model Context Protocol (MCP) server for AI coding agents |



