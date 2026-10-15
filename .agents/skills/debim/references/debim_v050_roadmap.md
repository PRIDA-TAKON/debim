# debim v0.5.0 Architecture & Roadmap Specification
## "The Mermaid.js of BIM" — Zero-Dependency Pure-Python Engine for AI Agents & Sandboxes

**Target Version:** `debim v0.5.0`  
**Core Tagline:**  
> *"A zero-dependency, pure-Python declarative BIM engine designed for AI Agents, LLM Code Interpreters, and air-gapped sandboxes."*

---

## 1. วิสัยทัศน์และการออกแบบสถาปัตยกรรม (Core Architecture Vision)

### 1.1 ปรัชญา "Mermaid.js แห่งวงการ BIM"
เหมือนที่ **Markdown** พลิกโฉมการเขียนเอกสาร และ **Mermaid.js** พลิกโฉมการวาดไดอะแกรมให้กลายเป็นข้อความธรรมดา (Plain Text) ที่ AI ทุกตัวสร้างได้:
* **AI Agent ใน Sandbox / VM:** ไม่จำเป็นต้องมีโปรแกรม BIM ขนาด 20GB, ไม่ต้องต่อเน็ต, และไม่ต้องติดตั้ง Library ภายนอก AI สามารถคิด วิเคราะห์ สังเคราะห์โครงสร้าง แล้วส่งออกไฟล์ **`.debim`** (หรือ Declarative JSON/YAML) ออกมาได้ภายใน 0.01 วินาที
* **Community Compilers:** มนุษย์หรือระบบภายนอกสามารถหยิบไฟล์ `.debim` ไปคอมไพล์ต่อยอดตามเป้าหมายของตนเอง ไม่ว่าจะเป็นการแปลงเป็น IFC มาตรฐาน, แบบก่อสร้าง 2D Blueprints, ตีราคา BOQ อัตโนมัติ, จำลองความร้อน HVAC, หรือนำไปสร้างฉาก 3D สมจริงใน Unreal Engine / Godot

---

### 1.2 สถาปัตยกรรมแบบสองชั้น (Two-Tier Architecture)

```
┌────────────────────────────────────────────────────────────────────────┐
│               debim-core (100% Pure Python Standard Library)           │
│   • CLI: argparse (แทน typer & rich)                                   │
│   • Schema Validation: dataclasses + json (แทน pydantic)               │
│   • Math & Geometry: math + vectors (แทน trimesh & shapely)            │
│   • Deterministic QTO: สูตรวิศวกรรมเพียวๆ (Shoelace, Rebar weights)   │
│   • Spatial Rules: Anchor points, Winding CCW, Radian rotations        │
│   • Formats: Native .debim (JSON / Lean YAML)                          │
│   • 3D Viewer: Standalone Self-contained HTML Generation               │
│   ───────────> รันได้ในทุก Sandbox / VM โดยไม่ต้อง pip install <────────│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Optional Ecosystem Plugins)
            ┌───────────────────────┼────────────────────────┐
            ▼                       ▼                        ▼
     debim[ifc]                debim[cad]                debim[mcp]
   (ifcopenshell)               (ezdxf)                    (mcp)
   คอมไพล์เป็น IFC4/STEP      เขียนแบบ DWG/DXF           FastMCP Server
```

---

## 2. ลำดับงานของ Jules (Step-by-Step Jules Issues Roadmap)

> [!IMPORTANT]
> **Trigger Condition:** Issue แรกของแผนงานนี้ (#1) จะเริ่มต้นสร้างและส่งให้ Jules ทำงานทันทีหลังจาก **PR IfcSpace (Issue #275)** ถูกส่งเข้ามา ตรวจสอบ CI ผ่าน และทำการรวมโค้ด (Squash Merge) เข้าสู่ branch `main` เรียบร้อยแล้ว

ลำดับงานถูกออกแบบให้แบ่งเป็น **6 Issues ย่อย** โดยเรียงลำดับจากฐานราก (Math/Geom) $\rightarrow$ CLI $\rightarrow$ Data Schema $\rightarrow$ Standalone Compilation เพื่อไม่ให้เกิด Regression:

---

### Issue 1: `feat(core): replace trimesh with pure-python/numpy vector math for mesh bounds & watertight volume`
* **วัตถุประสงค์:** ขจัด Dependency `trimesh` ออกจาก `importer.py` และ `qto.py`
* **รายละเอียดงาน:**
  1. ใน `src/debim/importer.py`: แทนที่การหา Bounding Box ด้วย `verts.min(axis=0)` และ `verts.max(axis=0)`
  2. ใน `src/debim/qto.py`: นำสูตร **Divergence Theorem** มาคำนวณปริมาตร Watertight 3D Mesh ด้วยเวกเตอร์:
     $$V = \frac{1}{6} \sum_{k} \vec{v}_{k,0} \cdot (\vec{v}_{k,1} \times \vec{v}_{k,2})$$
  3. ตัด `trimesh` ออกจาก `dependencies` ใน `pyproject.toml`
* **Acceptance Criteria:**
  * รัน `pytest tests/` ผ่าน 100% โดยไม่มีการเรียก `import trimesh`
  * ผลลัพธ์การคำนวณปริมาตรชิ้นงาน 3D ตรงกันกับค่าเดิมทุกประการ

---

### Issue 2: `feat(core): replace typer and rich with standard library argparse for zero-dependency CLI`
* **วัตถุประสงค์:** ขจัด Dependency `typer` และ `rich` ออกจากระบบ CLI หลัก
* **รายละเอียดงาน:**
  1. แปลงคำสั่งทั้งหมดใน `src/debim/cli.py` (เช่น `validate`, `qto`, `cost`, `compile`, `view`, `diff`) จาก `typer.Typer` มาเป็น `argparse.ArgumentParser` ของ Python Standard Library
  2. สร้าง Helper จัดการสีและตารางใน Terminal ด้วย ANSI Escape Codes แทน `rich.console` / `rich.table`
  3. ตัด `typer` และ `rich` ออกจาก `dependencies` ใน `pyproject.toml`
* **Acceptance Criteria:**
  * คำสั่ง `debim --help`, `debim validate`, `debim qto` ทำงานได้เหมือนเดิมทุกประการ
  * ทำงานได้บนเครื่องที่ไม่มี `typer` ติดตั้ง

---

### Issue 3: `feat(core): pure-python 2D polygon math engine (replacing shapely for boundary inset & areas)`
* **วัตถุประสงค์:** ทำฟังก์ชันเรขาคณิต 2D (Shoelace Area, Perimeter, Centroid, Polygon Insetting) ด้วย Pure Python Standard Library
* **รายละเอียดงาน:**
  1. พัฒนาโมดูล `src/debim/geometry2d.py` ด้วย Python Standard Library:
     * `shoelace_area(vertices)`
     * `polygon_perimeter(vertices)`
     * `polygon_inset(vertices, offset_distance)` (สำหรับ `inset` / `boundary_offset` ของผนังและห้อง)
     * `point_in_polygon(point, vertices)`
  2. ปรับให้ `debim-core` เรียกใช้โมดูลนี้แทน `shapely` (ย้าย `shapely` ไปอยู่ใน optional dependencies สำหรับงานตัด Section ขั้นสูง)
* **Acceptance Criteria:**
  * ทดสอบการคำนวณพื้นที่รูปหลายเหลี่ยมและรูปตัว L ได้ผลลัพธ์แม่นยำเท่ากับ Shapely
  * ตัด `shapely` ออกจาก core dependencies

---

### Issue 4: `feat(schema): enforce deterministic Anchor Points, Euler Rotations, and Dimension Keys in schema`
* **วัตถุประสงค์:** ประกาศกฎพิกัดและ Anchor Points ตายตัวลงใน Schema และ Docstrings เพื่อให้ AI Agent ตีความได้แม่นยำ 100%
* **รายละเอียดงาน:**
  1. เพิ่มกฎ Anchor Point ในคลาสหลัก:
     * `IfcWall`: `BOTTOM-START-CENTERLINE` (ใช้ `[thickness, height]`)
     * `IfcColumn`: `BOTTOM-CENTER` (ใช้ `[width, depth]`)
     * `IfcBeam`: `TOP-CENTERLINE` (ห้อยลง $-Z$, ใช้ `[width, depth]`)
     * `IfcSlab`: `TOP-FINISH` (จมลง $-Z$, ใช้ `[thickness]`)
     * `IfcSpace`: `BOTTOM-PERIMETER` (พุ่งขึ้น $+Z$, ใช้ `[height]`)
     * `IfcFurniture`: `BOTTOM-CENTER` (ฐานแตะพื้น $Z=0$, ใช้ `[width, depth, height]`)
  2. ระบุมาตรฐาน Rotation ใน Schema: ค่าเดี่ยวคือ Yaw (Radian รอบแกน $+Z$), สามมิติคือ Z-up Euler `[rx, ry, rz]`
  3. ปรับปรุง JSON Schema Exporter ให้สร้าง Schema ที่มี Metadata คำอธิบายเหล่านี้ครบถ้วน
* **Acceptance Criteria:**
  * อัปเดต `debim.schema.json` และทดสอบผ่านทุกตัวอย่าง

---

### Issue 5: `feat(core): native .debim file extension support with zero-dependency standalone loader`
* **วัตถุประสงค์:** ประกาศและรองรับนามสกุลไฟล์ `.debim` อย่างเป็นทางการ
* **รายละเอียดงาน:**
  1. รองรับการโหลดและบันทึกไฟล์นามสกุล `.debim` (โครงสร้าง JSON / Lean YAML)
  2. CLI สามารถรับคำสั่ง `debim validate project.debim`, `debim qto project.debim`
  3. AI Agent ใน Sandbox สามารถเซฟผลงานออกมาเป็น `building.debim` ได้ทันที
* **Acceptance Criteria:**
  * ตัวอย่างโครงการทั้งหมดในโฟลเดอร์ `examples/` มีเวอร์ชัน `.debim`
  * ตรวจสอบว่า `debim` CLI แยกแยะและประมวลผลไฟล์ `.debim` ได้อย่างถูกต้อง

---

### Issue 6: `feat(packaging): reorganize pyproject.toml into zero-dependency core and optional extras`
* **วัตถุประสงค์:** ปรับแต่ง `pyproject.toml` ให้ `debim` ติดตั้งแบบเพียวๆ โดยไม่มี Third-party Dependencies
* **รายละเอียดงาน:**
  1. Core Dependencies ใน `pyproject.toml`:
     ```toml
     dependencies = [] # Zero-dependency! Pure Python Standard Library
     ```
  2. จัดกลุ่ม Optional Dependencies:
     ```toml
     [project.optional-dependencies]
     all = ["ifcopenshell>=0.7.0", "ezdxf>=1.1.0", "pydantic>=2.7.0", "pyyaml>=6.0.1", "mcp>=1.0.0"]
     ifc = ["ifcopenshell>=0.7.0"]
     cad = ["ezdxf>=1.1.0"]
     mcp = ["mcp>=1.0.0"]
     ```
* **Acceptance Criteria:**
  * รันคำสั่ง `pip install .` ใน Virtual Environment ว่างเปล่า ต้องติดตั้งสำเร็จโดยไม่โหลดแพ็กเกจภายนอกใดๆ
  * รันคำสั่งพื้นฐาน `debim validate`, `debim qto`, `debim view` ได้สมบูรณ์

---

## 3. กลไกการเฝ้าติดตาม (Watchdog Pipeline)
1. สคริปต์ `tools/watchdog_jules_prs.py` จะคอยตรวจสอบ PR #275 (IfcSpace) ทุก 15 นาที
2. เมื่อ Jules เปิด PR:
   * ตรวจสอบ CI checks ผ่าน `gh pr checks`
   * ทดสอบรันชุดทดสอบ `pytest tests/`
   * ทำการ Squash Merge เข้าสู่ `main`
3. หลังจาก Issue #275 ถูก Merge แล้ว ระบบจะสร้าง **Issue 1** ตามแผนงานนี้ขึ้นสู่ GitHub และมอบหมายให้ Jules เริ่มทำงานต่อไปทันที
