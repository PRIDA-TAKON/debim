# 🗺️ debim v1.0.0 Master Roadmap & Technical Specification
## "The Pure Algorithmic Architecture & Open Standards Release"
### จากเส้นตรงสู่สมการ: เมื่อสถาปัตยกรรมระดับปฏิมากรรมและรังผึ้ง (Sculptural & Hexagonal Tessellation) ถูกคอมไพล์ด้วยสมการคณิตศาสตร์

> **Target Version:** `debim v1.0.0` (Milestone 1.0 General Availability)  
> **Status:** `PLANNED`  
> **Flagship Benchmark:** Museo Soumaya (Fernando Romero / Arup — 16,000 Hexagonal Tiles, 28 Curved Columns, 7-Storey Hyperbolic Loft)  
> **Core Philosophy:** *Architecture is Mathematical Truth: From Cartesian Primitives to Pure Algorithmic Geometry and Live Open Standards Ecosystem*

---

## 1. บทนำและปรัชญาการออกแบบ (Executive Summary & Vision)

ในยุค **debim v0.1.0 – v0.9.0** เราได้พิสูจน์แล้วว่าอาคารแบบ Prismatic Architecture (เส้นตรง, ผนังฉาก, และระนาบเรขาคณิตแบบ Modernist / Brutalist เช่น Farnsworth House และ Church of the Light) สามารถถูกอธิบายด้วย **Declarative Text Manifest (.debim)** และคอมไพล์ออกมาเป็นโมเดล OpenBIM IFC4 พร้อมถอด BOQ ได้อย่างแม่นยำ

แต่ในโลกของสถาปัตยกรรมชั้นสูง สถาปัตยกรรมไม่ได้มีเพียงแค่กล่องสี่เหลี่ยม:
* สถาปัตยกรรมอย่าง **Museo Soumaya** (Mexico City) โดย Fernando Romero และ Ove Arup ไม่ได้เกิดจากการลากเส้นทีละเส้นในโปรแกรม CAD
* มันถือกำเนิดขึ้นจาก **"สมการคณิตศาสตร์สองชั้น (Macro & Micro Mathematics)"**:
  1. **Macro Mathematics:** รูปทรงบิดคอดคล้ายนาฬิกาทราย (Hyperboloid / Asymmetric Loft Surface) ขับเคลื่อนด้วยเสาเหล็กโค้ง 28 ต้นที่ร้อยผ่านวงแหวนพื้น 7 ชั้น
  2. **Micro Mathematics:** การคลุมเปลือกอาคารด้วยแผ่นอะลูมิเนียมหกเหลี่ยม 16,000 แผ่น (Hexagonal Tessellation) ที่คำนวณผ่านอัลกอริทึม Conformal Hexagonal Mapping / Centroidal Voronoi Tessellation (CVT) เพื่อให้แผ่นลอยตัวแนบไปกับความโค้งคู่ (Double-Curved Surface) ได้อย่างแนบเนียน

**debim v1.0.0** จึงก้าวข้ามขีดจำกัดเดิม สู่ยุคของ **"Pure Algorithmic Architecture"**:
เปิดรับสมการคณิตศาสตร์เข้ามาเป็นพลเมืองชั้นหนึ่ง (First-class Citizens) ในสถาปัตยกรรม Building-as-Code ผสานการดึงข้อมูลสดจากระบบ **debim-standards** แบบไร้รอยต่อ

---

## 2. ห้าเสาหลักทางเทคนิคของ debim v1.0.0 (Core Technical Pillars)

```
                                    [debim v1.0.0 Pillars]
                                              │
     ┌──────────────────┬─────────────┼─────────────┬──────────────────┬──────────────────┐
     ▼                  ▼             ▼             ▼                  ▼                  ▼
1. Pure Algorithmic  2. Tessellation &  3. Directrix Swept    4. Live Standards  5. Open-Source Ecosystem
   Surface Lofts        Hexagonal Panels   Spine Columns         Ecosystem          Interoperability
   (Macro Equations)    (Micro Voronoi)    (Curved Geometry)     (debim-standards)  (CadCraft/Bonsai/PdfCraft)
```

---

### Pillar 1: Pure Algorithmic Macro-Geometry (Hyperbolic Lofts & Math Manifests)
* **Mathematical Function Declarations:**  
  อนุญาตให้ประกาศรูปทรงอาคารด้วยสมการพารามิเตอร์ (Parametric Functions) ภายในไฟล์ `.debim`:
  $$\mathbf{P}(u, z) = \mathbf{C}(z) + \mathbf{R}(z) \begin{bmatrix} a(z)\cos(u) \\ b(z)\sin(u) \end{bmatrix}$$
* **Multi-Storey Morphing Loft Engine:**  
  คอมไพเลอร์ของ debim จะคำนวณระนาบพื้นในแต่ละชั้น ($z$) ตามสมการปิดล้อม แล้วแปลงเป็น `IfcSlab` และ Boundary Enclosure โดยอัตโนมัติ

---

### Pillar 2: Micro-Geometry & Conformal Hexagonal Tessellation (16,000 Panels)
* **Algorithmic Surface Discretization:**  
  รองรับการซอยพื้นผิว Double-Curved Surface ออกเป็นโครงข่ายเซลล์หกเหลี่ยม (Hexagonal Grid) ผ่าน Centroidal Voronoi Tessellation (CVT)
* **High-Performance IFC4 Export (`IfcTriangulatedFaceSet`):**  
  แทนที่จะสร้าง Mesh ก้อนโตที่ทำให้โปรแกรมค้าง debim v1.0.0 จะคอมไพล์แผ่น Cladding นับหมื่นชิ้นให้อยู่ในรูปของ:
  - `IfcCurtainWall` รวบยอด
  - ภายในบรรจุ `IfcTriangulatedFaceSet` ที่มี Coordinates และ Index น้ำหนักเบา
  - หรือใช้ Instanced Geometry (`IfcMappedItem`) ร่วมกับระบบ Material PVD/Aluminum เพื่อให้เบราว์เซอร์แสดงผลได้ 60 FPS บน WebGL

---

### Pillar 3: 3D Directrix Spine & Swept Columns (`IfcSectionedSpine`)
* **เสาและโครงสร้างโค้ง 3 มิติ (Curved Structural Ribs):**  
  รองรับเสาโครงสร้างที่เลี้ยวโค้งไปตามเส้นทาง 3 มิติ (3D Spline Curves) เช่น เสา 28 ต้นของ Soumaya
* **IFC4.3 Infrastructure & Organic Solid:**  
  คอมไพล์เสาโค้งออกเป็น `IfcColumn` โดยใช้รูปทรงเรขาคณิตขั้นสูง:
  - `IfcDirectrixDistanceSweptAreaSolid`
  - หรือชุด Swept Disks ต่อเนื่อง เพื่อให้ส่งต่อไปวิเคราะห์โครงสร้าง Finite Element (FEM) ได้ทันที

---

### Pillar 4: Live Open Standards Integration (`debim-standards`)
* เชื่อมโยง debim เข้ากับคลังมาตรฐานเปิด `PRIDA-TAKON/debim-standards` แบบ Native:
  - **Human Scale Baseline:** เข้าถึงข้อมูลมิติและระยะ Clearance จากคลังสากลอัตโนมัติ
  - **Thai Building Control Act (MR 55):** การตรวจแบบสถาปัตยกรรมอัตโนมัติอ้างอิงข้อกฎหมายฉบับล่าสุด
  - **CGD ว480 Pricing & Carbon Metrics:** ถอดราคากลางงานก่อสร้างภาครัฐและประเมินค่า Embodied Carbon (kgCO2e) ทันทีที่รัน `debim boq --standards`

---

### Pillar 5: Open-Source Ecosystem Interoperability (CadCraft + Bonsai BIM + IngeTrazo + PdfCraft)
ขจัดปัญหา Vendor Lock-in และการแปลงไฟล์แล้วข้อมูลเพี้ยน ด้วยการเชื่อมต่อกับซอฟต์แวร์ Open Source ชั้นนำแบบ Native เพื่อส่งงานต่อไปยังขั้นตอนเขียนแบบ 2D, ประสานงานโมเดล 3D, ตกแต่งด้วย Direct Modeling, และรวมเล่มเอกสารได้อย่างไร้รอยต่อ (Lossless Data & Geometry Roundtrip):

* **1. 2D Drafting & Details — CadCraft Integration & Auto-Drafting Engine (Rust Engine):**
  - **Reusable DXF Blocks (`BLOCK` & `INSERT`):** ชิ้นส่วนสถาปัตยกรรมที่เกิดขึ้นซ้ำ เช่น ประตู (`D1`, `D2`), หน้าต่าง (`W1`, `W2`), สุขภัณฑ์ (`WC`, `BASIN`), สัญลักษณ์ Grid Bubble, และหน้าตัดเสา (`C1`) จะถูกคอมไพล์เป็น **Native DXF Blocks** แล้ววางตำแหน่งด้วย `INSERT` (ไม่แตกกระจายเป็น Loose Polylines) ทำให้ช่างเขียนแบบสามารถแก้ไขหน้าตาบล็อกเพียงครั้งเดียวใน CadCraft หรือ AutoCAD (ผ่านคำสั่ง `BEDIT`) แล้วตัวสัญลักษณ์จะอัปเดตเปลี่ยนหน้าตาทั้งโปรเจกต์ในทุกแผ่นแบบทันที 100%!
  - **Automated Multi-Discipline XREF Decoupling:** รองรับการสร้างไฟล์อ้างอิงภายนอก (External Reference / XREF Overlay) อัตโนมัติ โดย debim จะคอมไพล์แยกไฟล์แม่แบบสถาปัตยกรรม (`xref/A_PLAN_L01.dxf`) และสร้างไฟล์งานระบบไฟฟ้า (`E_PLAN_L01.dxf`), สุขาภิบาล (`M_PLAN_L01.dxf`) ที่ผูก XREF สถาปัตย์ไว้เป็น Background อัตโนมัติ เมื่อสถาปนิกขยับผนังในโค้ด `.debim` วิศวกรระบบไฟฟ้าที่เปิดแบบใน CadCraft จะเห็นผนังขยับตามทันที 100% โดยไม่ต้อง Copy-Paste แปลนใหม่
  - **Auto 3-Tier Dimensioning:** คำนวณและวางเส้นบอกระยะอัตโนมัติ 3 ชั้นรอบอาคาร (ชั้นใน: ช่องเปิดประตู-หน้าต่าง, ชั้นกลาง: ศูนย์กลางเสากริด, ชั้นนอก: ระยะมิติรวมอาคาร) โดยที่ดราฟต์แมนไม่ต้องคลิกเมาส์จับมุมเอง
  - **Smart Room Centroid & Level Tags:** วางชื่อห้อง, ขนาดพื้นที่ (`ตร.ม.`), และสัญลักษณ์ระดับพื้น (`FL.1 +0.10 ม.`) กลางพื้นที่ใช้งานอัตโนมัติ
  - **Ready-to-Plot Paper Space Layouts & Viewports (A3/A2):** debim จะจัดหน้ากระดาษใน Paper Space (Layout Tabs เช่น `A-101`, `A-102`, `S-101`) ไว้ให้แบบ 1:1 โดยอัตโนมัติ ประกอบด้วย **Title Block (กรอบแบบสากลและตารางชื่อแบบ)**, ล็อคมาตราส่วนจริง (`Scale 1:100` / `1:50`), และเปิด **Floating Viewport (`VIEWPORT`)** ล็อคตำแหน่งกึ่งกลางอาคารไว้เรียบร้อย ช่างเขียนแบบหรือผู้ใช้งานใน CadCraft และ AutoCAD เพียงแค่สลับมาแท็บ Layout แล้วกด `Ctrl + P` (Plot to PDF) ได้ทันที 100% โดยไม่ต้องมานั่งตีกรอบหรือตั้งค่าสเกลเองทีละแผ่น!
  - **DXF Layout & Viewports:** ส่งออกเส้น 2D Floor Plans, Sections, Elevations และ Detail Drawings ในฟอร์แมต DXF R12–2018 ที่จัดแบ่งเลเยอร์มาตรฐาน (`A-WALL`, `A-DOOR`, `A-FLOR`, `S-COLS`) รองรับ Paper Space Layout / Floating Viewports ของ CadCraft โดยตรง
  - **Annotation & Dimension Continuity:** ค่าพิกัด, เส้น Grid, และเส้นบอกระยะไม่เคลื่อน ข้อมูลหัวกระดาษ (Title Block) และมาตราส่วนคงที่ 100%
* **2. 3D BIM Authoring & Coordination — Bonsai BIM (BlenderBIM) Native Bridge:**
  - **Direct IFC Data Graph:** ทั้ง debim และ Bonsai ขับเคลื่อนด้วย `IfcOpenShell` เหมือนกัน ทำให้เปิดไฟล์ IFC4 / IFC4.3 ของ debim ได้โดยตรงโดยไม่ต้องผ่านการ Convert เป็น proprietary schema
  - **Zero Geometry & Parameter Drift:** รักษา GUIDs, Spatial Tree (`IfcProject` ➔ `IfcSite` ➔ `IfcBuilding` ➔ `IfcBuildingStorey`), Property Sets (`Pset_MR55`, `Pset_CGD480`), Materials, และ Quantities ครบถ้วน 100%
  - **Extreme Mesh Performance:** รองรับการเปิดและจัดการโมเดล Algorithmic Facade ระดับ 16,000 แผ่นรังผึ้ง (`IfcTriangulatedFaceSet`) บน 3D Viewport ได้อย่างลื่นไหลที่ 60 FPS
* **3. Intuitive Direct Modeling — IngeTrazo Official Extension (`debim-ingetrazo`):**
  - **Python-to-Python Native Architecture:** IngeTrazo มี Plugin API เป็น **Pure Python** ตรงกับ debim โดยสมบูรณ์ ไม่ต้องผ่านภาษาตัวกลาง (ต่างจาก SketchUp ที่ต้องพึ่งพา Ruby)
  - **Native Extension Plugin (`debim_tool.py`):** ติดตั้งในโฟลเดอร์ Plugins ของ IngeTrazo เพิ่มเมนู `Extensions > debim > Import / Sync .debim` สถาปนิกสามารถเปิดไฟล์ `.debim` หรือรันคอมไพล์แล้วสร้างระนาบ Solid, Component, และ BIM Tags บน Viewport ของ IngeTrazo ทันที
  - **Interactive Push/Pull & Live Feedback:** สถาปนิกสามารถใช้เครื่องมือ Push/Pull, Move, Offset ดั้งเดิมที่ถนัดเพื่อปรับแต่งพื้นที่หรืออินทีเรีย แล้วส่งกลับมาอัปเดตมิติพารามิเตอร์ในโค้ด `.debim` (Bi-directional Concept)
  - **Official Extensions Hub Submission:** เผยแพร่ขึ้นสู่แคตตาล็อกกลางของ IngeTrazo (`ingelibre/ingetrazo-extensions`) ให้ผู้ใช้งานทั่วโลกติดตั้งได้ในคลิกเดียว
* **4. PDF & Permit Document Workbench — PdfCraft Integration (Rust Engine):**
  - **Automated Blueprint Bookbinder:** ระบบคำสั่งเชื่อมต่อเพื่อรวมแผ่นแบบพิมพ์เขียว 2D (Arch/Struc/MEP) เข้ากับเล่ม BOQ และรายงานตรวจกฎหมาย (MR 55 Compliance Report) ออกมาเป็นเล่มเอกสารขออนุญาตก่อสร้าง PDF ชุดสมบูรณ์
  - **Digital Signatures & Professional Stamping Hand-off:** ยกภาระการเซ็นชื่อรับรองแบบและประทับตรายางอิเล็กทรอนิกส์ (Digital Signatures, Wet Signatures, & Professional Stamp) ให้เป็นหน้าที่ของ **PdfCraft** โดย debim จะรับหน้าที่เพียงสร้างช่องลงลายมือชื่อกำกับชื่อ-สกุลและเลขที่ใบอนุญาตประกอบวิชาชีพไว้ใน Title Block อย่างถูกต้อง ช่วยลดภาระการพัฒนาใน debim Core ให้กระชับ คลีน และไม่บวม (Zero Bloat)
  - **Lossless Vector & Precision Printing:** รักษาเวกเตอร์เส้น ลายเส้น และตัวอักษรให้อยู่ในสถานะ Pure Vector โดยไม่มีการลดทอนความละเอียดหรือเกิดปัญหาฟอนต์ภาษาไทยเพี้ยน

---

## 3. แผนงานการพัฒนา (Implementation Roadmap Waves)

| Wave | เป้าหมายหลัก (Milestone) | รายละเอียดทางเทคนิค (Deliverables) | Flagship Test Case |
| :---: | :--- | :--- | :--- |
| **Wave 1** | **Live Standards Integration** | เชื่อมต่อ `debim-standards` ผ่าน `src/debim/standards.py`, Cache ออฟไลน์, และผูกกับ Audit/BOQ | TDAD House + MR 55 Compliance |
| **Wave 2** | **Parametric Surface & Loft Engine** | ฟังก์ชันสมการคณิตศาสตร์ `math:` ใน Manifest, การคำนวณ Loft สเปซระหว่าง Storeys | Hyperbolic Cooling Tower / Loft Volume |
| **Wave 3** | **3D Curved Spine Columns** | เสาและคานโค้งตามเส้น 3D Splines, การคอมไพล์ `IfcColumn` ตามแนว Directrix | 28 Curved Tubular Steel Columns |
| **Wave 4** | **Conformal Hexagonal Tessellation** | อัลกอริทึมแบ่งแผ่นรังผึ้ง Voronoi/Hexagonal บนพื้นผิวโค้ง, คอมไพล์ `IfcTriangulatedFaceSet` | 16,000 Hexagonal Aluminum Panels |
| **Wave 5** | **Open Ecosystem & Auto-Drafting** | Bridge ส่งออกงานสู่ **CadCraft** (DXF Blocks & 3-Tier Dimensions), **Bonsai BIM** (Lossless IFC4), **IngeTrazo** (Python Extension), และ **PdfCraft** (Permit Bookbinder) | Zero-Loss Roundtrip Suite Test |
| **Wave 6** | **Museo Soumaya Milestone (v1.0.0 GA)** | คอมไพล์โมเดลสถาปัตยกรรม Museo Soumaya ครบวงจร 100%, ทดสอบ 3D Web Viewer & IFC4 Validation | **Museo Soumaya Benchmark Project** |

---

## 4. ตัวอย่างไวยากรณ์ในอนาคต (debim v1.0.0 Syntax Preview)

```yaml
# ==============================================================================
# Museo Soumaya (Plaza Carso, Mexico City) — Pure Algorithmic Architecture
# ==============================================================================
schema: "IFC4-Algorithmic"
project:
  id: "PRJ-MUSEO-SOUMAYA-2011"
  name: "Museo Soumaya — Pure Algorithmic Architecture Benchmark"
  architect: "FR-EE (Fernando Romero Enterprise)"

parameters:
  total_height: 46.00
  num_storeys: 7
  columns_count: 28

# 1. Macro-Geometry: Asymmetric Hyperbolic Ring Loft Equation
geometry_rules:
  envelope_loft:
    type: "HYPERBOLIC_LOFT"
    base_radii: [14.0, 18.0]    # Ground floor ellipse
    waist_radii: [11.0, 13.5]   # Mid-height pinch at z = 22.0m
    roof_radii: [22.0, 26.0]    # Cantilevered flaring crown
    cantilever_offset: [6.5, 0] # Asymmetrical forward lean

# 2. 28 Curved Structural Ribs (Swept Steel Columns)
structures:
  column_generator:
    count: 28
    distribution: "RADIAL_ELLIPTIC"
    profile: "CIRCULAR_HOLLOW_D600"
    trajectory: "LOFT_SURFACE_ISOPARAMETRIC"

# 3. Micro-Geometry: 16,000 Floating Hexagonal Aluminum Panels
facade:
  envelope_skin:
    target: "envelope_loft"
    tessellation:
      pattern: "HEXAGONAL_CONFORMAL"
      target_panel_size: 0.55   # ~55cm hexagonal diameter
      joint_gap: 0.02          # 20mm floating reveal gap
      material: "ALUMINUM_ANODIZED_SILVER"
      ifc_representation: "IfcTriangulatedFaceSet"
```

### คำสั่ง CLI สำหรับ Open-Source Toolchain Workflow (Lossless Roundtrip):

```bash
# 1. ส่งออกเส้นแบบ 2D ไปเขียนแบบต่อใน CadCraft (DXF พร้อม Paper Space Layouts & Layers)
debim export --target cadcraft --input model.debim --out ./drawings/cadcraft/

# 2. คอมไพล์โมเดล 3D แบบ Lossless สำหรับเปิดและทำงานต่อใน Bonsai BIM (BlenderBIM)
debim export --target bonsai --input model.debim --out ./models/soumaya_bonsai.ifc --verify-lossless

# 3. ส่งออกโมเดลตรงสู่ IngeTrazo หรือติดตั้ง Extension สำหรับ Live Sync (Direct Push/Pull)
debim export --target ingetrazo --input model.debim --out ./models/project.skp
debim extension install --target ingetrazo   # ติดตั้ง debim-ingetrazo Python Extension อัตโนมัติ

# 4. รวบรวมแผ่นแบบพิมพ์เขียว, เล่ม BOQ, และรายงานผลตรวจ MR 55 เข้าเล่ม PDF ผ่าน PdfCraft
debim publish --binder pdfcraft --manifest model.debim --out ./output/soumaya_permit_package.pdf
```

---

## 5. บทสรุปผลกระทบเชิงกลยุทธ์ (Strategic Conclusion)

เมื่อ **debim** ก้าวสู่เวอร์ชัน **v1.0.0** พร้อมกับปรัชญา **Pure Algorithmic Architecture**:
1. **ปลดล็อกขีดจำกัดเดิม:** debim จะไม่ใช่เครื่องมือที่สร้างได้เฉพาะอาคารกล่องหรือระนาบตรงอีกต่อไป แต่สามารถคอมไพล์สถาปัตยกรรมระดับประติมากรรมอัลกอริทึมที่ซับซ้อนที่สุดในโลกได้ด้วยสมการเพียงไม่กี่บรรทัด
2. **สร้างมาตรฐานใหม่ให้วงการ Building-as-Code:** การผสานระหว่าง **คณิตศาสตร์เชิงกำเนิด (Generative Math)**, **มาตรฐานเปิดระดับชาติ (debim-standards)**, และ **OpenBIM IFC4** จะทำให้ debim เป็น Engine เดียวในโลกที่เขียนอาคารระดับไอคอนิกได้ด้วย Code ขนาดไม่ถึง 100 บรรทัด!
