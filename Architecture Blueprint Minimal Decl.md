Architecture Blueprint: Minimal Declarative BIM (Building-as-Code)1. Executive Summary & Philosophyระบบ BIM ยุคใหม่ที่ออกแบบภายใต้แนวคิด Human-First, Agent-Friendly & Git-Native:Semantic Declarative Model: อาคารคือชุดของ Logic และสเปกวิศวกรรม ไม่ใช่ 3D Mesh ซับซ้อนDual Representation (Text-First + Fallback GLB): 90% ขององค์อาคารใช้ Geometric Primitives ผ่าน Text (Box, Cylinder, Extrusion) ส่วน 10% ที่เป็น Freeform/Custom Shape ค่อยโหลดจาก external GLB assetZero-Accumulative Error: อ้างอิงตำแหน่งแบบสัมพัทธ์ (Relative Placement) ผ่าน Storey, Grid Intersection, และ Host-Child RelationshipsDeterministic Code Compliance: กฎหมายอาคารและข้อกำหนดโครงการถูกแปลงเป็น Unit Tests (pytest) รันแบบ CI/CD2. System ArchitecturePlaintext       +---------------------------------------------+
       |           Human / AI Agent (CLI)            |
       +---------------------------------------------+
                              |
       +----------------------v----------------------+
       |   Project Manifest & Data Layer             |
       |   - project.yaml (IFC-aligned Semantic DSL) |
       |   - prices.json  (Material/Labor Cost DB)   |
       |   - assets/*.glb (Optional Custom Meshes)   |
       +---------------------------------------------+
                              |
       +----------------------v----------------------+
       |   Core Engine (Python CLI / Headless)       |
       +---------------------------------------------+
        |                  |                       |
        v                  v                       v
[Analytical Math]  [Geometric Compiler]   [Rule Checking Engine]
- Exact Formulas   - Extrusions           - Building Code Tests
- Mesh Vol/Area    - Boolean/Clash (BVH)  - Pytest assertions
- Reinforcement    - Export IFC / GLB     - Spatial Constraints
        |                  |                       |
        v                  v                       v
[BOQ / Cost Table] [3D Viewer / IFC]      [CI/CD PASS / FAIL]
3. Core Schema Specification (project.yaml)โครงสร้างข้อมูลอิงมาตรฐาน buildingSMART (IFC4) เพื่อให้ Mapping ตรง 1:1 กับ IFC EntitiesYAMLschema: IFC4-Minimal
project:
  id: PRJ-2026-001
  name: "Townhouse-Feasibility"
  units: { length: METER, area: SQUARE_METER, volume: CUBIC_METER }

# 1. โครงสร้างเชิงพื้นที่และระดับชั้น
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

# 2. ระบบแนวแกนกริดอ้างอิง
grids:
  axes_x: { A: 0.00, B: 4.00, C: 8.00 }
  axes_y: { 1: 0.00, 2: 5.00, 3: 10.00 }

# 3. ฐานข้อมูลวัสดุ
materials:
  - id: CONC_240
    name: "Concrete 240 ksc"
    category: concrete
    unit_cost_ref: "MAT-CONC-01"
  - id: AAC_75
    name: "AAC Block 7.5cm"
    category: masonry
    unit_cost_ref: "MAT-AAC-01"

# 4. รายการองค์ประกอบอาคาร (Elements)
elements:
  # Case A: กล่องเรขาคณิตพื้นฐาน (ไม่ต้องพึ่งไฟล์ 3D)
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

  # Case B: คานเชื่อมต่อระหว่างจุดกริด
  - class: IfcBeam
    tag: B-A1_B1
    material: CONC_240
    profile: { shape: BOX, width: 0.20, depth: 0.40 }
    placement:
      from_grid: [A, 1]
      to_grid: [B, 1]
      storey: L2
      offset_z: 0.00
    reinforcement:
      main_top: "2-DB16"
      main_bottom: "3-DB20"
      stirrups: "RB9 @ 0.15m"

  # Case C: ผนังพร้อมช่องเปิด (Host-Child Relationship)
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
        sill_height: 0.00

  # Case D: วัตถุรูปทรงอิสระ (Custom Geometry Fallback)
  - class: IfcCustomElement
    tag: ST-01
    name: "Spiral Staircase"
    source: "assets/stairs/spiral_stair.glb"
    placement:
      position: [2.00, 2.50, 0.00]
      storey: L1
4. โครงสร้างโฟลเดอร์โครงการ (Git-Friendly Project Structure)Plaintexttownhouse-feasibility/
├── .gitignore
├── .gitattributes          # ตั้งค่า Git LFS สำหรับ assets/*.glb
├── project.yaml            # Master BIM Data (มนุษย์และ AI แก้ตรงนี้)
├── prices.json             # Price Catalog สำหรับประเมินงบ
│
├── assets/                 # คลังชิ้นส่วนเฉพาะกิจ (Fallback)
│   └── stairs/
│       └── spiral_stair.glb
│
├── tests/                  # Automated Code Compliance (Building Laws as Code)
│   ├── conftest.py         # Pytest fixture โหลด project.yaml
│   ├── test_compliance.py  # กฎกระทรวง ฉบับที่ 55, 39, ผังเมือง ฯลฯ
│   └── test_clashes.py     # ตรวจจับชิ้นส่วนชนกัน (Zero-Clash Rule)
│
└── dist/                   # Output folder (Ignored by Git)
    ├── model.ifc           # Standard IFC สำหรับส่งต่อซอฟต์แวร์อื่น
    ├── preview.glb         # 3D Mesh รวบชิ้น สำหรับ Web Viewer
    └── boq.csv             # ตารางปริมาณวัสดุและราคา
5. Automated Code Compliance: กฎหมายอาคารในรูป Unit Testsใช้ pytest ตรวจสอบข้อกำหนดอัตโนมัติ ช่วยให้ AI หรือทีมงานรู้ทันทีหากแก้มิติแล้วขัดต่อกฎหมาย:Python# tests/test_compliance.py
import pytest


def test_total_floor_area_limit(project):
  """ตรวจสอบพื้นที่รวมอาคาร (เช่น เพดานโครงการ Feasibility หรือ พ.ร.บ.

  ควบคุมอาคาร)
  """
  total_area = project.qto.get_total_floor_area()
  assert total_area <= 4000.0, (
      f"พื้นที่รวมเกินกำหนด: {total_area:.2f} ตร.ม. (เพดาน: 4000.0 ตร.ม.)"
  )


def test_setback_with_openings(project):
  """กฎกระทรวง ฉบับที่ 55: ผนังมีช่องเปิดต้องร่นห่างแนวเขตที่ดินอย่างน้อย 2.00 ม."""
  for wall in project.get_elements("IfcWall"):
    if wall.has_openings:
      dist = project.site.get_distance_to_boundary(wall)
      assert dist >= 2.00, (
          f"ผนัง {wall.tag} มีช่องเปิดแต่ระยะร่นห่างเขตที่ดินเพียง {dist:.2f} ม."
          " (ขั้นต่ำ 2.00 ม.)"
      )


def test_minimum_clear_ceiling_height(project):
  """ระยะดิ่งพื้นถึงคาน/ฝ้า ต้องไม่น้อยกว่า 2.40 ม."""
  for storey in project.spatial_structure.storeys:
    clear_height = storey.calculate_clear_height()
    assert (
        clear_height >= 2.40
    ), f"ชั้น {storey.name} มีระยะดิ่งต่ำกว่าเกณฑ์: {clear_height:.2f} ม."


def test_zero_spatial_clash(project):
  """ตรวจจับการซ้อนทับกันของชิ้นส่วนโครงสร้าง (Clash Detection)"""
  clashes = project.geometry.detect_clashes()
  assert (
      len(clashes) == 0
  ), f"พบชิ้นส่วนซ้อนทับกัน {len(clashes)} จุด: {clashes}"
6. CLI Command-Line Interface & Agent SkillsCLI ออกแบบเป็น Unix-style, Idempotent, และใช้งานทรัพยากรเบาที่สุด:Commandหน้าที่เบื้องหลังการทำงานbim init <name>สร้างโครงร่างโปรเจกต์ใหม่วาง template project.yaml, prices.json, tests/bim validateตรวจสอบ Syntax & Schemaตรวจความถูกต้องของ Grid, Type, และ Placement Linksbim testรันชุดกฎหมายและ Complianceเรียก pytest tests/ พ่นรายงานข้อที่ไม่ผ่านbim qtoคำนวณปริมาณงานวัสดุคิดปริมาตร Extrusion + Volume ของ GLB Mesh + ปริมาณเหล็กเสริมbim costคำนวณงบประมาณโครงการนำผล QTO แมปกับราคาต่อหน่วยใน prices.json พ่นเป็น CSV/JSONbim compile -o model.ifcแปลงเป็นไฟล์ IFC มาตรฐานเรียก IfcOpenShell ประกอบ Entity ส่งต่อ FreeCAD/Blenderbim viewเปิดดูโมเดล 3D แบบรวดเร็วรัน Local HTTP Server เปิด HTML Viewer เบาๆ บน Browser7. แผนขั้นตอนการพัฒนา (Roadmap Blueprint)Phase 1: Core Engine & Math Calculation (Minimal Viable Engine)พัฒนา Python CLI โหลด project.yamlสร้างฟังก์ชันคำนวณ Extrusion พื้นฐาน (Box, Cylinder, Slab Polygon)ระบบคำนวณ QTO เบื้องต้น (คอนกรีต ลบ.ม., พื้นที่ผิวไม้แบบ ตร.ม., ความยาวเหล็กเสริม)Phase 2: Custom Asset & Collision Detectionเพิ่มตัวโหลดไฟล์ .glb ด้วยไลบรารี trimesh เพื่อดึงปริมาตรจริงทำ Collision Manager ตรวจสอบ AABB Bounding Box และ Boolean OverlapPhase 3: Automated Compliance & Git Workflowเขียน Base Test Fixture สำหรับ pytest (กฎระยะร่น, OSR, FAR, บันได)ตั้งค่า Git Pre-commit Hook เพื่อบล็อกการ commit หากทดสอบไม่ผ่านPhase 4: Agent Skill & IFC Exporterนำ IfcOpenShell มา compile YAML ให้กลายเป็น .ifcบรรจุคำสั่ง CLI เข้าเป็น AI Agent Skill เพื่อให้ Agent สามารถอ่านแบบ 2D แล้วสร้าง YAML หรือสั่งแก้สเปกอาคารได้อัตโนมัติ