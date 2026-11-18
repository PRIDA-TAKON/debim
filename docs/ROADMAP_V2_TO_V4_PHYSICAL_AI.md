# 🗺️ debim Master Roadmap (v2.0.0 ➔ v4.0.0)
## "The Physical AI, Open World Ontology & Synthetic World Model Paradigm"
### จากซอฟต์แวร์สถาปัตยกรรม สู่ภาษามาตรฐานของโลกกายภาพสำหรับหุ่นยนต์และปัญญาประดิษฐ์

> **Document Status:** Active Engineering Specification & Long-Term Strategic Roadmap  
> **Repository:** `PRIDA-TAKON/debim` | `PRIDA-TAKON/debim-standards` | `02_3DSCAN`  
> **License:** MIT (Radical Open Source — Free for all humans & robots)  
> **Philosophy:** *“The Single Source of Truth for Physical Reality: From Raw Photons/LiDAR to Living Git-native World Models”*

---

## 🏛️ ภาพรวมแผนยุทธศาสตร์ 3 ก้าวสำคัญ (Strategic Overview)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    debim EVOLUTIONARY TIMELINE                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                 │
                                                 ▼
 🚀 [debim v2.0.0] Scan-to-debim & Hardware Co-Design
    • พัฒนาฮาร์ดแวร์ 3D Scanner (`02_3DSCAN`: RGB + LiDAR + 3DGS) ควบคู่กับซอฟต์แวร์
    • สกัดสภาพแวดล้อมจริงเป็นไฟล์ `.debim` ขนาดเล็กด้วย Pure Python + NumPy
    • แปลงความจริงหน้างาน (As-Built) ให้กลายเป็น IFC4, DXF Blueprints, BOQ ปร.4-5-6, และตรวจกฎหมาย MR 55
                                                 │
                                                 ▼
 🌐 [debim v3.0.0] debim-standards for Everyone (The Living Robot & Human Swarm)
    • เปิดกว้างให้หุ่นยนต์ทุกตัวทั่วโลก (Robots Swarm) นิยามคลาสใหม่เมื่อเจอสิ่งที่ไม่เคยรู้จัก
    • หุ่นยนต์ส่ง Pull Request (PR) ผ่าน Git เข้าสู่คลัง `debim-standards` อัตโนมัติ
    • มนุษย์มีส่วนร่วมผ่าน Mobile App / เกมสแกนของในบ้านแบบ Crowdsourcing
    • บอทผู้คุมกฎ (Gatekeeper CI Bot) สแกนตรวจจับความซ้ำซ้อน (Deduplication) และผสานความรู้ (Consensus)
                                                 │
                                                 ▼
 🌌 [debim v4.0.0] debim to World Model (The Synthetic Simulation Engine)
    • นำคลัง `.debim` ที่ครอบคลุมทุกสิ่งบนโลก ไปสร้างแบบจำลองสภาพแวดล้อมเสมือนจริง (Synthetic Worlds)
    • คอมไพล์สู่ OpenUSD, NVIDIA Isaac Sim, MuJoCo โดยมีฟิสิกส์และ Affordance สมบูรณ์ 100%
    • กลายเป็น "ImageNet ของโลก 3 มิติ" เพื่อฝึกฝน Physical AI & Humanoid Robots แบบ Sim-to-Real
```

---

## 🛰️ Milestone 2.0.0 — Scan-to-debim & Hardware Co-Design
**เป้าหมาย:** สแกนโลกจริงรอบตัว แล้วถอดรหัสออกมาเป็นโค้ด `.debim` ทันทีด้วยการทำงานร่วมกันระหว่างฮาร์ดแวร์และซอฟต์แวร์

### 1. Hardware Co-Design (`02_3DSCAN`)
* **Sensor Fusion:** กล้อง RGB Stream ผสานกับ LiDAR Scanner & IMU ทราบมุมและทิศทางกล้องล่วงหน้า ($SE(3)$ Poses) โดยไม่ต้องพึ่งพา COLMAP Structure-from-Motion (Zero-SfM)
* **High-Speed 3D Gaussian Splatting (3DGS):**
  * เทรนฉาก 3 มิติได้เร็วกว่าเดิม 10–20 เท่า
  * ใช้ขอบเขตเรขาคณิตของ LiDAR ในการตัดก้อนฟุ้งลอยฟ้า (Floater Pruning) ได้คมชัด

### 2. Pure Python + NumPy Inverse Geometry Engine
* ออกแบบให้ทำงานได้บน **Pure Python Standard Library + NumPy** (Zero Heavy C++ Dependencies) เพื่อให้รันได้บนบอร์ด Edge Computing (เช่น Jetson, Raspberry Pi) บนตัวกล้องสแกนเนอร์โดยตรง
* **Z-Histogram Peak Finder:** คำนวณหาระดับพื้นและฝ้าเพดาน (Storeys & Heights) ในเสี้ยววินาที
* **Vectorized 2D RANSAC:** สกัดแนวเส้นกึ่งกลางผนัง (Wall Centerlines) จากระนาบตัด $+1.20$ ม.
* **Manhattan Orthogonal Rectifier:** ดึงมุมผนังที่เอียงหน้างานให้ได้ฉาก $90^\circ$ และ Snap พิกัดลง Grid อัตโนมัติ
* **Gap Analysis for Openings:** ตรวจจับช่องเปิดประตู-หน้าต่างจากความหนาแน่นของจุดที่เว้นว่าง

### 3. Immediate Downstream Compilation
* เมื่อได้ไฟล์ `.debim` หน้างาน สามารถคอมไพล์ต่อได้ทันที:
  * 📄 **CAD:** แบบแปลน 2D พร้อมบอกระยะ (DXF Blueprints)
  * 💰 **Cost:** ปริมาณวัสดุและราคากลางจริง (BOQ ปร.4, ปร.5, ปร.6 ว480)
  * ⚖️ **Law:** ตรวจสอบระยะร่นเทียบกับโฉนดตามกฎกระทรวงฉบับที่ 55
  * 🏛️ **BIM:** ส่งออกเป็นมาตรฐานสากล OpenBIM IFC4 / IFC4.3

---

## 🤖 Milestone 3.0.0 — debim-standards for Everyone
**เป้าหมาย:** สร้างคลังคำศัพท์และภาษาของโลกกายภาพ (Physical Ontology) ที่เติบโตได้เองแบบกระจายศูนย์ผ่านการส่ง PR ของหุ่นยนต์และมนุษย์

### 1. Autonomous Proto-Class Discovery by Robots
* เมื่อหุ่นยนต์ Physical AI (เช่น หุ่นดูดฝุ่น, แขนกล, หรือ Humanoid) เดินไปเจอวัตถุที่ไม่อยู่ในสารบบของ debim:
  * สกัดรูปทรง Bounding Box และเวกเตอร์ภาพ (Feature Embeddings)
  * สังเกตพฤติกรรมและการใช้งาน (Affordance Hypothesis) เช่น "ปล่อยไฟฟ้าได้", "เปิด-ปิดได้", "ห้ามเดินเหยียบ"
  * สร้างเป็น **Proto-Class** เก็บเป็นความจำท้องถิ่น (Local Episodic Memory)

### 2. Git-native PR Pipeline (`debim-standards`)
* หุ่นยนต์เปิดใช้งาน Git Protocol ในตัว:
  * สร้าง Branch และส่งคำขอรวมโค้ด: `gh pr create --repo PRIDA-TAKON/debim-standards`
  * บรรจุ Schema รายละเอียดของวัตถุ จุดเชื่อมต่อกลไก (Joints/Kinematics) และฟังก์ชันการใช้งาน

### 3. Crowdsourcing by Humans (Mobile App & Gamification)
* แอปพลิเคชันบนสมาร์ตโฟน (iOS / Android) และเกม AR/3D ที่เปิดให้คนทั่วโลกช่วยกัน "สแกนของในบ้าน":
  * สแกนเก้าอี้, เครื่องใช้ไฟฟ้า, ของเล่น, เครื่องมืองานช่าง
  * ผู้เล่นได้รับคะแนน/Badge (Gamified Data Collection) ขณะที่โมเดลส่งพิกัดและคุณสมบัติเข้ามายังฐานข้อมูลกลาง

### 4. The Gatekeeper CI Bot (Jules AI / debim-bot)
* ระบบตรวจสอบใน GitHub Actions ทำหน้าที่เป็นผู้คุมกฎ:
  * **Schema Linting:** ตรวจสอบความถูกต้องของโครงสร้างไวยากรณ์ตาม `.debim` spec
  * **Semantic Deduplication:** ตรวจสอบความคล้ายคลึงของเวกเตอร์ (Cosine Similarity) ป้องกันการตั้งชื่อคลาสซ้ำซ้อน หากซ้ำจะจัดเข้าเป็น Variant/Alias อัตโนมัติ
  * **Auto-Merge & Release:** รวมความรู้เข้าสู่กิ่ง `main` แล้วออกอัปเดตเวอร์ชันมาตรฐานใหม่ทันที

### 5. Swarm Knowledge Synchronization
* หุ่นยนต์ทุกตัวในเครือข่ายรันคำสั่ง `debim standards sync`:
  * ดึงความจำล่าสุดของโลกไปใช้ หุ่นยนต์รุ่นใหม่ที่เพิ่งเปิดใช้งานจะรู้จักสิ่งของทุกชิ้นในโลกที่หุ่นยนต์ตัวอื่นเคยเจอมาแล้วทันที

---

## 🌌 Milestone 4.0.0 — debim to World Model (The Synthetic Simulation Engine)
**เป้าหมาย:** นำคลังโครงสร้างและวัตถุทั่วโลกของ debim ไปสร้างโลกเสมือนจริงเพื่อฝึกฝน Physical AI ยุคต่อไป

### 1. Procedural World Generation (Building-as-Code at Infinite Scale)
* แปลง `.debim` ให้เป็นเครื่องมือผลิตโลกจำลองสังเคราะห์ (Synthetic Environment Generator):
  * สคริปต์สุ่มและผสมผสานแบบแปลนบ้าน ออฟฟิศ โรงงาน โรงพยาบาล ได้นับล้านรูปแบบที่ไม่ซ้ำกัน
  * ทุกฉากที่ถูกสร้างขึ้นมีความถูกต้องตามฟิสิกส์ 100% ปราศจากโครงสร้างบิดเบี้ยว (Zero Geometric Hallucination)

### 2. OpenUSD & Physics Engine Transpiler
* คอมไพล์ไฟล์ `.debim` ออกเป็น **OpenUSD (Universal Scene Description)** ของ Pixar / NVIDIA:
  * แนบคุณสมบัติทางฟิสิกส์ (Mass, Friction, Center of Mass)
  * แนบกลไกการเคลื่อนไหว (Kinematics & Articulated Joints) เช่น ลิ้นชักที่เลื่อนได้, ประตูที่มีบานพับหมุนได้
  * เชื่อมต่อเข้ากับ **NVIDIA Isaac Sim, Isaac Lab, และ MuJoCo** ได้อย่างไร้รอยต่อ

### 3. The "ImageNet" of Physical AI & Sim-to-Real Acceleration
* ตอบโจทย์ **The Robotics Data Crisis**:
  * ช่วยให้หุ่นยนต์ Humanoid ฝึกฝนการเดิน การทำงานบ้าน และการหยิบจับในโลกเสมือนจริงนับล้านๆ ชั่วโมงด้วยความเร็วสูง (Massive Parallel RL Simulation)
  * ถ่ายโอนสมองปัญญาประดิษฐ์จาก Simulation กลับสู่หุ่นยนต์ตัวจริง (Sim-to-Real Transfer) โดยไม่ต้องเสี่ยงให้หุ่นยนต์จริงเสียหายหน้างาน

---

## 📜 บทสรุปและคำมั่นสัญญา Open Source (The Open Ethos)
> *"เราเปิดพื้นที่แห่งนี้ให้ทุกคนอย่างเสรี ทั้งมนุษย์และหุ่นยนต์*  
> *ใครที่ต้องการร่วมสร้าง สามารถส่ง PR กลับเข้ามาแบ่งปันความรู้สู่ส่วนกลาง*  
> *หรือใครต้องการแยกสาขา (Fork) ไปสร้างโลกของตนเอง ก็สามารถทำได้อย่างอิสระโดยไม่มีข้อผูกมัด"*

**debim** จะไม่เป็นเพียงซอฟต์แวร์เขียนแบบอาคาร แต่จะวิวัฒนาการสู่ **"รากฐานภาษาแห่งโลกกายภาพ (The Lingua Franca of the Physical World)"** อย่างสมบูรณ์แบบ.
