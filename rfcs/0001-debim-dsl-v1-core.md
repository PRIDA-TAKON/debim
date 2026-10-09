# RFC 0001: debim DSL v1.0 Core Specification

- **RFC Number:** 0001
- **Author(s):** debim Core Team
- **Status:** Active / Living
- **Created Date:** 2026-10-09
- **Target Version:** debim v1.0

---

## 1. บทสรุปย่อ (Summary)

ข้อเสนอนี้กำหนดมาตรฐานและโครงสร้างไวยากรณ์หลักของภาษา **debim (Declarative BIM)** เวอร์ชัน 1.0 ซึ่งเป็นภาษาเฉพาะโดเมน (Domain-Specific Language - DSL) ในรูปแบบ Declarative YAML สำหรับนิยามอาคารทั้งหลัง (Building-as-Code) เพื่อให้มนุษย์และ AI สามารถออกแบบ ทำงานร่วมกันผ่าน Git คำนวณปริมาณงาน (QTO) และตรวจสอบกฎหมายอาคารได้แบบ Deterministic

---

## 2. โครงสร้างพื้นฐานของภาษา debim (Syntax Architecture)

ไฟล์เอกสารของ debim ประกอบด้วย 6 ส่วนหลัก:

```yaml
version: "1.0"
project:
  name: "โครงการบ้านพักอาศัยตัวอย่าง"
  standards:
    classification: "MasterFormat-2020"
    compliance_regulations: ["TH-BMA-Building-Code-2544"]

site:
  boundary: ...
  setbacks: ...

grids:
  x: ["A", "B", "C"]
  y: ["1", "2", "3"]
  spacings_x: [4.0, 4.0]
  spacings_y: [5.0, 5.0]

storeys:
  - id: "L1"
    name: "Ground Floor"
    elevation: 0.0
    height: 3.5

elements:
  columns: [...]
  beams: [...]
  walls: [...]
  slabs: [...]
  doors: [...]
  windows: [...]

compliances:
  - rule: "setback_front >= 3.0"
  - rule: "far <= 2.0"
```

---

## 3. หลักการสำคัญของ DSL (Core Language Principles)

### 3.1 Relative Grid-Based Placement (การระบุตำแหน่งอิงกริด)
แทนที่จะต้องระบุพิกัด X, Y, Z ลอยๆ ที่มนุษย์และ AI จำยาก debim อนุญาตให้อ้างอิงเสาและคานด้วยชื่อกริดและระดับชั้น:
```yaml
columns:
  - id: "C1"
    grid: "A-1"          # อยู่ที่จุดตัดกริด A และ 1
    storey: "L1"         # อยู่ที่ชั้น 1
    profile:
      type: "rectangular"
      width: 0.3
      depth: 0.3
    material: "concrete_c240"
```

### 3.2 Topological Beam Spanning (คานเชื่อมต่อระหว่างจุดกริด)
```yaml
beams:
  - id: "B1"
    from: "A-1"
    to: "A-2"
    storey: "L1"
    profile:
      width: 0.2
      depth: 0.4
    material: "concrete_c240"
```

### 3.3 Explicit Uncertainty (`needs_review`)
สำหรับงานที่ AI ช่วยร่างแต่ยังต้องการให้มนุษย์ตรวจสอบอย่างชัดเจน:
```yaml
walls:
  - id: "W101"
    start: "A-1"
    end: "B-1"
    material: "brick_masonry"
    needs_review: true
    review_notes: "ตรวจสอบประเภทอิฐมวลเบาหรืออิฐมอญตามสเปกสถาปัตย์"
```

### 3.4 Dual Representation (90% Primitives + 10% Baked Assets)
เพื่อความสมดุลระหว่างความเร็วในการคำนวณและดีเทลที่ประณีต:
- โครงสร้างหลัก (เสา คาน ผนัง พื้น) ใช้คณิตศาสตร์พรีมิตีฟเพื่อคำนวณคอนกรีต/เหล็กเสริม/ไม้แบบได้เป๊ะ 100%
- เฟอร์นิเจอร์และสุขภัณฑ์ประณีต สามารถผูกกับโมเดล 3D ได้:
```yaml
furnishings:
  - id: "FUR-01"
    name: "Lounge Chair"
    placement: { x: 2.5, y: 3.0, z: 0.0 }
    asset_uri: "assets/chair_mies.glb"
```

---

## 4. Pipeline การประมวลผล (The debim Pipeline)

```
[ project.debim.yaml ] 
         │
         ▼
 ┌───────────────┐
 │ debim Engine  │ ──► [ debim test ]      (Automated Building Code & Unit Tests)
 └───────┬───────┘ ──► [ debim qto / cost ](BOQ / Material Quantities & Prices)
         ├───────────► [ debim draw ]      (2D SVG / DXF Blueprint Engine)
         ├───────────► [ debim view ]      (Lightweight 3D Web Viewer)
         └───────────► [ debim compile ]   (Standardized IFC4 Certification)
```

---

## 5. แผนการเปิดรับฟังความคิดเห็น (Next Steps)
- เปิดรับข้อเสนอเรื่อง MEP Routing (ท่อประปา, ไฟฟ้า, HVAC)
- การกำหนด Schema มาตรฐานสำหรับ Localized Building Codes (กฎกระทรวงไทยฉบับต่างๆ)
