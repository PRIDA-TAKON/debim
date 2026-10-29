# 🗺️ debim v1.3.0 Master Roadmap & Technical Specification
## As-built vs As-planned Diff Engine, 4D Site Progress & Git CI/CD for Building-as-Code

> **Target Version:** `debim v1.3.0`  
> **Status:** `IN PROGRESS`  
> **Target Repository:** `PRIDA-TAKON/debim`  
> **Core Philosophy:** *Transforming Building-as-Code from Visual 3D Models to Automated Construction Quality Verification, Time-series Progress Tracking, and DevOps CI/CD*

---

## 1. วิสัยทัศน์และเหตุผลความจำเป็น (Vision & Value Proposition)

ในการพัฒนา debim ที่ผ่านมา เราได้พิสูจน์แล้วว่าอาคารสามารถถูกเขียนเป็น Code (Building-as-Code) และคอมไพล์เป็น OpenBIM IFC4, ถอด BOQ, ตรวจสอบกฎกระทรวง, และวางผัง CPM 4D Schedule ได้สำเร็จ

อย่างไรก็ตาม ในไซต์งานก่อสร้างจริง ปัญหาเรื้อรังที่สร้างความสูญเสียทางมูลค่ามากที่สุดคือ:
1. **Human Inspector Bottleneck:** การตรวจสอบคุณภาพหน้างาน (QC/QA) ใช้เวลานาน ใช้สายตาหรือตลับเมตรวัดสุ่มตัวอย่าง ไม่ครอบคลุมทั้งอาคาร
2. **Delayed Progress Billing:** การตรวจรับงวดงานล่าช้าเนื่องจากขาดหลักฐานเชิงพื้นที่ (Spatial Data) ที่โปร่งใสและเป็นกลาง
3. **As-built Drift:** แบบที่สร้างจริงหน้างานเบี่ยงเบนจากแบบก่อสร้าง (As-planned) โดยไม่มีการซิงก์กลับเข้าไฟล์ต้นฉบับ ทำให้แบบส่งมอบ (As-built Drawing) ไม่ตรงกับความจริง
4. **Lack of DevOps in Architecture:** แบบอาคารยังคงถูกส่งตรวจและคำนวณราคาแบบ Manual ขาด Automated CI/CD ที่ช่วยตรวจสอบผลกระทบด้านราคาและกฎหมายทันทีที่มีการแก้แบบ

**debim v1.3.0** จึงถูกออกแบบขึ้นเพื่อปิดช่องว่างเหล่านี้ด้วย 5 ขั้นตอนการพัฒนา:

```
[Phase 1: Quick Win & Adoption]
  Step 1: Git CI/CD & PR Diff Bot for Building-as-Code
    │
[Phase 2: Core Technological Moat]
  Step 2: Point-to-Mesh / Point-to-Plane Distance Engine
    │
  Step 3: Fine Registration (ICP) & Deviation Tolerance Heatmap (Color Mapping & Web 3D)
    │
[Phase 3: Automated Business Value]
  Step 4: 4D Time-series Site Progress Tracking (Volumetric Presence & EVM Sync)
    │
[Phase 4: Closed-loop Sync]
  Step 5: Change Detection & Smart As-built Sync (Surgical .debim AST Patcher)
```

---

## 2. ขั้นตอนการพัฒนารายละเอียด (Detailed Implementation Steps)

### Step 1: Git CI/CD Workflow & PR Diff Bot for Building-as-Code
* **เป้าหมาย:** สร้าง Automated PR Bot และ GitHub Action ที่วิเคราะห์การเปลี่ยนแปลงของแบบ `.debim` ทุกครั้งที่มีการเปิด PR
* **ฟังก์ชันการทำงาน:**
  - เปรียบเทียบ Cost & QTO ระหว่าง Branch เป้าหมายกับ PR Branch (เช่น "เหล็กเส้นเพิ่มขึ้น +3.5%, คอนกรีตลดลง -1.2%, มูลค่างานก่อสร้างสุทธิ +45,000 บาท")
  - ตรวจสอบ Rule Compliance ด้วย `debim compliance` (กฎกระทรวง MR 55, โครงสร้าง, ระยะร่น)
  - สร้าง Markdown Summary Card สำหรับโพสต์เป็น PR Comment อัตโนมัติ

### Step 2: Point-to-Mesh / Point-to-Plane Distance Engine
* **เป้าหมาย:** เขียน Engine คำนวณระยะห่างระหว่างจุดใน Point Cloud สแกนจริง (As-built) กับพื้นผิว Geometry ที่คอมไพล์จาก .debim (As-planned)
* **ฟังก์ชันการทำงาน:**
  - รองรับ Input จุดพิกัดจากไฟล์ `.ply` ในโมดูล `debim.scan` (Calibrated Metric Point Clouds)
  - คำนวณ Signed Distance (บวก = ปูด/ล้ำแนว, ลบ = ขาด/เว้า) และ Absolute Distance เทียบกับระนาบชิ้นงาน (ผนัง, เสา, คาน, พื้น)
  - ประสิทธิภาพระดับ Vectorized NumPy / SciPy รันเร็วระดับ Real-time

### Step 3: Fine Registration (ICP) & Deviation Tolerance Heatmap
* **เป้าหมาย:** จัดวางพิกัดสแกนให้ตรงกับโมเดลอย่างแม่นยำ พร้อมสร้างแผนที่ความคลาดเคลื่อนสี (Heatmap)
* **ฟังก์ชันการทำงาน:**
  - Fine ICP (Iterative Closest Point) เพื่อ Alignment สแกนเข้ากับ IFC Origin
  - Color Mapping ตามเกณฑ์ Tolerance เช่น เกณฑ์ $\pm 10\text{ mm}$ (สีเขียว = ถูกต้อง, สีแดง = ล้ำแนว, สีน้ำเงิน = ขาด)
  - แสดงผลบน Standalone 3D HTML Viewer ซ้อนทับระหว่างแบบ Wireframe กับ Point Cloud Heatmap

### Step 4: 4D Time-series Site Progress Tracking (Volumetric Presence & EVM Sync)
* **เป้าหมาย:** แปลงข้อมูลสแกนตามช่วงเวลา (Weekly Snapshots) ให้กลายเป็นความคืบหน้างวดงานใน `debim.schedule`
* **ฟังก์ชันการทำงาน:**
  - อัลกอริทึม Point Density / Bounding Box Volume Analyzer เพื่อตรวจสอบว่าชิ้นส่วนโครงสร้างถูกสร้างจริงแล้วกี่ %
  - Auto-populate ข้อมูลเข้า `CrashingActivity.progress_percent` และบันทึก `ProgressLogEntry`
  - ประเมินสถานะการจ่ายเงินงวดงาน (Earned Value & Payment Milestones) เทียบกับ S-Curve อัตโนมัติ

### Step 5: Change Detection & Smart As-built Sync (Surgical AST Patcher)
* **เป้าหมาย:** บันทึกการเปลี่ยนแปลงหน้างานย้อนกลับเข้าสู่โค้ด `.debim` ต้นทางแบบอัตโนมัติ
* **ฟังก์ชันการทำงาน:**
  - ตรวจจับตำแหน่งชิ้นงานที่มีการขยับย้ายเกินพิกัดควบคุม แล้วสร้าง Change Proposal Patch
  - Surgical AST Patcher: แก้ไขเฉพาะตัวเลขพิกัดในไฟล์ `.debim` เดิม โดยรักษา Comments, โครงสร้างไฟล์ และ Whitespace ไว้อย่างสมบูรณ์
