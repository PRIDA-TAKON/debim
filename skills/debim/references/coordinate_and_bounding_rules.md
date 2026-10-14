# debim Coordinate, Anchor & Bounding Rules Specification
**Standard:** debim Standard Spatial Specification (v1.1 - AI Geometry Ready)  
**System:** Right-Handed Cartesian Coordinate System (IFC4 / ISO 16739 compliant)

---

## 1. หน่วยวัดมาตรฐาน (Measurement Units Standard)

debim บังคับใช้หน่วยวัดมาตรฐานระบบ **SI Metric** อย่างตายตัว ห้ามใช้หน่วยมิลลิเมตร (mm) หรือเซนติเมตร (cm) ในพิกัดเรขาคณิต:

| มิติ (Dimension) | หน่วยวัด (Unit) | สัญลักษณ์ | คำอธิบาย & ตัวอย่าง |
| :--- | :--- | :---: | :--- |
| **ระยะทาง / พิกัด (Length)** | **METER (เมตร)** | $m$ | ทศนิยม 2-4 ตำแหน่ง เช่น `0.20` (20cm), `3.50` (3.5m) |
| **พื้นที่ (Area)** | **SQUARE_METER (ตร.ม.)** | $m^2$ | เช่น `36.00` $m^2$ |
| **ปริมาตร (Volume)** | **CUBIC_METER (ลบ.ม.)** | $m^3$ | เช่น `7.20` $m^3$ |
| **มวล / น้ำหนักเหล็ก (Mass)** | **KILOGRAM (กิโลกรัม)** | $kg$ | เช่น `125.40` $kg$ |
| **มุมการหมุน (Rotation)** | **RADIAN (เรเดียน)** | $rad$ | หมุนรอบแกน $+Z$ (ทวนเข็มนาฬิกาเป็นบวก) เช่น `1.5708` ($\pi/2 = 90^\circ$) |

---

## 2. ระบบพิกัดและทิศทาง (Coordinate & Orientation Rules)

### 2.1 แกนหลัก 3 มิติ (Right-Handed Cartesian System)
* **แกน $+X$:** ทิศตะวันออก (East) / แนวราบขวามือของแปลนพื้น
* **แกน $+Y$:** ทิศเหนือ (North) / แนวดิ่งบนมือของแปลนพื้น
* **แกน $+Z$:** ระดับความสูง (Elevation) / พุ่งขึ้นสู่ท้องฟ้า

```
          +Z (Elevation / Sky)
          ^
          |
          |   +Y (North / Floor Plan Up)
          |  /
          | /
          +----------------> +X (East / Floor Plan Right)
```

### 2.2 กฎหน่วยการหมุนและลำดับแกน Euler (Rotation & Euler Angles)
* **Single Value (`rotation: float`):**
  * หมายถึง **Yaw Rotation (หมุนรอบแกน $+Z$)** ในหน่วย **Radian**
  * ทิศทาง: **ทวนเข็มนาฬิกา (CCW) เป็นบวก**
  * $0\text{ rad}$ = ขนานแกน $+X$ (หันหน้าไปทางทิศตะวันออก)
  * $+1.5708\text{ rad}$ ($+\pi/2$) = หมุน $90^\circ$ ขนานแกน $+Y$ (หันไปทางทิศเหนือ)
  * $+3.1416\text{ rad}$ ($+\pi$) = หมุน $180^\circ$ ขนานแกน $-X$
* **3D Euler Angles (`rotation: [rx, ry, rz]`):**
  * หน่วย: **Radians** ทั้งหมด
  * ลำดับแกน: **Z-up Extrinsic / Intrinsic Z-Y-X (Yaw $\rightarrow$ Pitch $\rightarrow$ Roll)**
    * `rz`: Yaw (หมุนรอบแกน $Z$)
    * `ry`: Pitch (หมุนรอบแกน $Y$)
    * `rx`: Roll (หมุนรอบแกน $X$)

---

## 3. กฎจุดอ้างอิงพิกัด (Position Anchor Points) แยกตาม Class

สิ่งที่ AI มักจะสับสนมากที่สุดคือตำแหน่ง $X, Y, Z$ อ้างอิงจากมุมไหนของชิ้นงาน ตารางนี้คือกฎตายตัวของ debim:

| IFC Class | จุดอ้างอิงพิกัด (Position Anchor) | ทิศทางการขยายตัวของเนื้อวัสดุ (Extrusion Direction) |
| :--- | :--- | :--- |
| **`IfcColumn`** (เสา) | **`BOTTOM-CENTER`**<br>(กึ่งกลางฐานเสาที่ระดับพื้นชั้นล่าง) | กึ่งกลางหน้าตัดอยู่ที่จุดตัดกริต $(X, Y)$ และเนื้อเสา **พุ่งขึ้นตามแนว $+Z$** ไปจนถึงระดับพื้นชั้นบน |
| **`IfcBeam`** (คาน) | **`TOP-CENTERLINE`**<br>(ระดับหลังคาน กึ่งกลางความกว้าง) | เส้นเชื่อมจาก `from_grid` $\rightarrow$ `to_grid` อยู่ที่ **ผิวบนสุด (Top of Beam)** ความลึก `depth` **จะห้อยจมลงด้านล่าง (Extrude downwards along $-Z$)** |
| **`IfcSlab`** (แผ่นพื้น) | **`TOP-FINISH`**<br>(ระดับหลังพื้นโครงสร้างชั้นนั้น) | ผิวบนของพื้นอยู่ที่ระดับ Storey Elevation (`+ offset_z`) ความหนา `thickness` **จะจมลงด้านล่าง (Extrude downwards along $-Z$)** เพื่อไม่ให้กินพื้นที่เคลียร์ของชั้นบน |
| **`IfcWall`** (ผนัง) | **`BOTTOM-START-CENTERLINE`**<br>(ริมล่างสุด ณ จุดเริ่ม `from_grid`) | ริมล่างสัมผัสระดับพื้นชั้น (`+ offset_z`) กึ่งกลางความหนาอยู่บนแนวเส้นตรง ความสูง `height` **ก่อสูงขึ้นตามแนว $+Z$** |
| **`IfcFooting`** (ฐานราก) | **`TOP-CENTER`**<br>(ระดับหลังฐานราก กึ่งกลางตอม่อ) | กึ่งกลางผิวบนฐานรากอยู่ที่พิกัดกริต $(X, Y)$ ความหนาฐานราก **จมลงดินตามแนว $-Z$** |
| **`IfcSpace`** (ห้อง/ก้อนอากาศ) | **`BOTTOM-PERIMETER`**<br>(ระนาบพื้นห้อง) | ระนาบขอบเขตแนบกับพื้นชั้น ความสูง `height` **พุ่งขึ้นตามแนว $+Z$** เป็นปริมาตรห้อง |
| **`IfcFurniture`** (เฟอร์นิเจอร์) | **`BOTTOM-CENTER`**<br>(กึ่งกลางฐานล่างที่สัมผัสพื้น) | $Z$ วางบนระดับพื้นพอดี ($Z_{\text{base}} = 0$) กึ่งกลางขนาด $(W, D)$ อยู่ที่ $(X, Y)$ ความสูงพุ่งขึ้น $+Z$ |
| **`IfcDoor` / `IfcWindow`** | **`BOTTOM-LEFT-SILL`**<br>(มุมล่างของช่องเจาะผนัง) | อ้างอิงจากจุดเริ่มของผนังแม่ (Host Wall) วัดตามระยะทางแนวนอนและระยะยกธรณีประตู/หน้าต่าง (`sill_height`) |

---

## 4. มิติของแต่ละ Class (Dimension Keys Standard)

เพื่อป้องกันไม่ให้ AI สับสนระหว่าง `depth`, `height`, `thickness`, และ `length` debim กำหนดคีย์มาตรฐานของแต่ละ Class ดังนี้:

### 4.1 โครงสร้างชิ้นงานหลัก (Structural Elements)

```yaml
# 1. IfcColumn: ใช้ width x depth (และ base_storey -> top_storey)
- class: IfcColumn
  tag: C-A1
  profile:
    shape: BOX
    width: 0.20   # มิติหน้าตัดตามแกน X (m)
    depth: 0.20   # มิติหน้าตัดตามแกน Y (m)
  placement:
    grid: [A, 1]
    base_storey: Ground
    top_storey: Upper

# 2. IfcBeam: ใช้ width x depth (ความยาว length คำนวณจากกริตอัตโนมัติ)
- class: IfcBeam
  tag: B-1
  profile:
    shape: BOX
    width: 0.20   # ความกว้างหน้าคาน (m)
    depth: 0.40   # ความลึกคานในแนวดิ่ง (m)  *ห้ามใช้ height*
  placement:
    from_grid: [A, 1]
    to_grid: [B, 1]
    storey: Upper

# 3. IfcWall: ใช้ thickness x height (ความยาว length คำนวณจากกริตอัตโนมัติ)
- class: IfcWall
  tag: W-1
  thickness: 0.15 # ความหนาผนัง (m) *ห้ามใช้ width หรือ depth*
  height: 2.80    # ความสูงผนังจากพื้นถึงใต้คาน/ฝ้า (m)
  placement:
    from_grid: [A, 1]
    to_grid: [A, 2]
    storey: Ground

# 4. IfcSlab: ใช้ thickness (ความกว้าง/ยาว คำนวณจากรูปหลายเหลี่ยม boundary)
- class: IfcSlab
  tag: S-1
  thickness: 0.15 # ความหนาพื้น (m)
  placement:
    storey: Ground
    boundary: [[A, 1], [B, 1], [B, 2], [A, 2]]

# 5. IfcSpace: ใช้ height (พื้นที่คำนวณจาก boundary)
- class: IfcSpace
  tag: living-room
  height: 2.80    # ความสูงโปร่งของห้องเคลียร์ถึงฝ้า (m)
  placement:
    storey: Ground
    boundary:
      - ["A + 0.10", "1 + 0.10"]
      - ["B - 0.10", "1 + 0.10"]
      - ["B - 0.10", "2 - 0.10"]
      - ["A + 0.10", "2 - 0.10"]
```

### 4.2 วัตถุลอยตัวและอุปกรณ์ (Furniture & Equipment)

สำหรับชิ้นงาน 3D กล่องทรงตัน (Bounding Box Object):
* `width` = ขนาดตามแกน $X$ ท้องถิ่น (Local X)
* `depth` = ขนาดตามแกน $Y$ ท้องถิ่น (Local Y - ความลึก/ความหนาด้านหน้าไปหลัง)
* `height` = ขนาดตามแกน $Z$ ท้องถิ่น (Local Z - ความสูงจากพื้นขึ้นไป)

```yaml
- class: IfcFurniture
  tag: desk-01
  dimensions:
    width: 1.20   # กว้าง (ซ้าย-ขวา) 1.20 ม.
    depth: 0.60   # ลึก (หน้า-หลัง) 0.60 ม.
    height: 0.75  # สูง (บน-ล่าง) 0.75 ม.
  placement:
    storey: Ground
    position: [2.50, 3.00, 0.00] # [X, Y, Z] ฐานล่างกึ่งกลางชิ้นงาน
    rotation: 0.0                # หมุนรอบแกน Z (Radian)
```

---

## 5. กฎเวกเตอร์และการเรียงลำดับจุดมุม (Winding & Vector Rules)

1. **กฎทวนเข็มนาฬิกา (CCW Winding Rule):**
   * จุดมุมใน `boundary` หรือ `boundary_points` ของ **Slab, Roof, Space** ต้องเรียงแบบ **Counter-Clockwise** เมื่อมองจากด้านบน ($+Z$) เสมอ
   * เพื่อให้ Normal Vector ชี้ขึ้นฟ้า $(0, 0, 1)$ และสูตร Shoelace Formula ให้ผลลัพธ์เป็นบวก
2. **กฎเวกเตอร์ผนัง (Wall Vector Rule):**
   * เวกเตอร์วิ่งจาก $\vec{v} = p_{\text{to}} - p_{\text{from}}$
   * ความยาวผนัง: $L = \|\vec{v}\|$
   * Normal ชี้ไปทางซ้ายมือ: $\hat{n} = \left(-\frac{v_y}{L}, \frac{v_x}{L}\right)$ (ปกติคือฝั่งภายนอกอาคาร Exterior)
