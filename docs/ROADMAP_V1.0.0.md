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

## 2. สี่เสาหลักทางเทคนิคของ debim v1.0.0 (Core Technical Pillars)

```
                            [debim v1.0.0 Pillars]
                                      │
     ┌──────────────────┬─────────────┴─────────────┬──────────────────┐
     ▼                  ▼                           ▼                  ▼
1. Pure Algorithmic  2. Tessellation &        3. Directrix Swept    4. Live Standards
   Surface Lofts        Hexagonal Panels         Spine Columns         Ecosystem
   (Macro Equations)    (Micro Voronoi Mesh)     (Curved Geometry)     (debim-standards)
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

## 3. แผนงานการพัฒนา (Implementation Roadmap Waves)

| Wave | เป้าหมายหลัก (Milestone) | รายละเอียดทางเทคนิค (Deliverables) | Flagship Test Case |
| :---: | :--- | :--- | :--- |
| **Wave 1** | **Live Standards Integration** | เชื่อมต่อ `debim-standards` ผ่าน `src/debim/standards.py`, Cache ออฟไลน์, และผูกกับ Audit/BOQ | TDAD House + MR 55 Compliance |
| **Wave 2** | **Parametric Surface & Loft Engine** | ฟังก์ชันสมการคณิตศาสตร์ `math:` ใน Manifest, การคำนวณ Loft สเปซระหว่าง Storeys | Hyperbolic Cooling Tower / Loft Volume |
| **Wave 3** | **3D Curved Spine Columns** | เสาและคานโค้งตามเส้น 3D Splines, การคอมไพล์ `IfcColumn` ตามแนว Directrix | 28 Curved Tubular Steel Columns |
| **Wave 4** | **Conformal Hexagonal Tessellation** | อัลกอริทึมแบ่งแผ่นรังผึ้ง Voronoi/Hexagonal บนพื้นผิวโค้ง, คอมไพล์ `IfcTriangulatedFaceSet` | 16,000 Hexagonal Aluminum Panels |
| **Wave 5** | **Museo Soumaya Milestone (v1.0.0 GA)** | คอมไพล์โมเดลสถาปัตยกรรม Museo Soumaya ครบวงจร 100%, ทดสอบ 3D Web Viewer & IFC4 Validation | **Museo Soumaya Benchmark Project** |

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

---

## 5. บทสรุปผลกระทบเชิงกลยุทธ์ (Strategic Conclusion)

เมื่อ **debim** ก้าวสู่เวอร์ชัน **v1.0.0** พร้อมกับปรัชญา **Pure Algorithmic Architecture**:
1. **ปลดล็อกขีดจำกัดเดิม:** debim จะไม่ใช่เครื่องมือที่สร้างได้เฉพาะอาคารกล่องหรือระนาบตรงอีกต่อไป แต่สามารถคอมไพล์สถาปัตยกรรมระดับประติมากรรมอัลกอริทึมที่ซับซ้อนที่สุดในโลกได้ด้วยสมการเพียงไม่กี่บรรทัด
2. **สร้างมาตรฐานใหม่ให้วงการ Building-as-Code:** การผสานระหว่าง **คณิตศาสตร์เชิงกำเนิด (Generative Math)**, **มาตรฐานเปิดระดับชาติ (debim-standards)**, และ **OpenBIM IFC4** จะทำให้ debim เป็น Engine เดียวในโลกที่เขียนอาคารระดับไอคอนิกได้ด้วย Code ขนาดไม่ถึง 100 บรรทัด!
