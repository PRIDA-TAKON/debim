# debim: Building-as-Code & The Open Declarative BIM Standard
## Vision & Manifesto

> **"หัวใจของ debim เริ่มจากการอยากให้ AI ทำ BOQ แต่การให้ AI คำนวณตึกทั้งหลังตรงๆ AI ตายแน่ จึงต้องใช้แบบจำลองคณิตศาสตร์ (BIM) ทว่ามาตรฐาน IFC ดั้งเดิมก็ซับซ้อนเกินไป หนักสมอง AI อีก จึงกลั่นออกมาเป็น Declarative YAML — แต่ผลพลอยได้ที่ได้รับกลับยิ่งใหญ่กว่าเป้าหมายแรกเริ่ม"**

---

### 1. บทนำ: ทำไมโลกต้องมีภาษาสำหรับอาคาร? (Why an Architectural DSL?)

ในโลกการพัฒนาซอฟต์แวร์ เราก้าวข้ามการคลิกหน้าต่าง GUI เพื่อตั้งค่าเซิร์ฟเวอร์มาสู่ **Infrastructure-as-Code** (Terraform, Kubernetes) และเราเปลี่ยนการเขียนเอกสาร API แบบเดิมมาเป็น **OpenAPI / Swagger** ซึ่งทำให้คอมพิวเตอร์และมนุษย์เข้าใจตรงกันแบบ 100%

ทว่าในวงการสถาปัตยกรรมและวิศวกรรมก่อสร้าง (AEC):
1. **โมเดลยังถูกขังใน Proprietary Binary Formats (.rvt, .pln)** ที่มีขนาดหลายกิกะไบต์ ค่าลิขสิทธิ์ซอฟต์แวร์แสนแพง และไม่สามารถตรวจสอบความเปลี่ยนแปลง (Git diff) ได้
2. **IFC (Industry Foundation Classes) ซับซ้อนเกินไปสำหรับงานระดับต้นน้ำ** แม้ IFC จะเป็นมาตรฐานเปิดระดับสากล แต่ถูกออกแบบเป็น Low-level interchange format (STEP format) ที่มนุษย์อ่านไม่ออก และ AI ไม่สามารถสร้างหรือประมวลผลได้อย่างมีประสิทธิภาพ
3. **ขาดภาษากลางที่เป็น Declarative** ที่สถาปนิก วิศวกร ช่างประเมินราคา (QS) และปัญญาประดิษฐ์ (AI Agents) สามารถร่วมมือกันออกแบบและคำนวณผ่าน Version Control (Git) ได้อย่างแท้จริง

**`debim`** (Declarative BIM) ถูกสร้างขึ้นเพื่อเติมเต็มช่องว่างนี้ — ทำหน้าที่เป็น **"Markdown of Architecture"** และ **"Terraform of Buildings"**

---

### 2. 5 เสาหลักแห่งปรัชญา debim (The 5 Core Pillars)

1. **Building-as-Code & Git-Native (อาคารคือซอฟต์แวร์):**
   - อาคารทั้งหลังต้องสามารถแทนค่าด้วย Text/YAML หรือ Declarative DSL ขนาดกะทัดรัด (ระดับ Kilobytes ไม่ใช่ Gigabytes)
   - รองรับ Git Branching, Pull Requests, Code Review, และ Versioning แบบสมบูรณ์
2. **Deterministic Code Compliance (กฎหมายและวิศวกรรมคือ Unit Test):**
   - กฎกระทรวง เทศบัญญัติ ระยะร่น ระยะปลอดภัย และตรรกะโครงสร้าง ต้องตรวจสอบได้แบบ Deterministic ผ่าน Test Automation (`pytest` / CI-CD) ภายในเสี้ยววินาที ไม่ใช่การกะประมาณ
3. **Zero-License & Zero-Friction Visualization (เห็นจริงโดยไม่ต้องพึ่งพาซอฟต์แวร์แพง):**
   - ผลลัพธ์ต้องตรวจสอบด้วยสายตาได้ทันทีผ่าน 3D & 2D HTML Viewer น้ำหนักเบา เปิดได้บนเว็บเบราว์เซอร์ทุกอุปกรณ์โดยไม่ต้องลงโปรแกรมราคาแพง
4. **Universal Bridge & Dual Representation (เชื่อมโยงทุกค่าย ไม่ทิ้งความประณีต):**
   - เป็นสะพานเชื่อมระหว่าง 2D Blueprints, 3D Mesh (Blender, SketchUp), และ IFC สากล
   - ใช้หลักคิด **Dual Representation**: 90% Primitives สำหรับคำนวณโครงสร้างและ BOQ แม่นยำ + 10% Baked Asset GLB สำหรับดีเทลประณีต
5. **Human & AI Super-Collaboration (Explicit Uncertainty):**
   - ออกแบบไวยากรณ์ให้อ่านง่ายสำหรับทั้งมนุษย์และ AI
   - มีระบบระบุความไม่แน่นอนอย่างชัดเจน (`needs_review`) เพื่อให้มนุษย์และ AI ตรวจสอบและส่งต่องานกันได้อย่างไร้รอยต่อ

---

### 3. เป้าหมายระยะยาว: สู่ Open Standard & Foundation

debim ถูกออกแบบมาไม่ได้เพื่อเป็นแค่โปรเจกต์ของคนใดคนหนึ่งหรือบริษัทเดียว แต่มีเป้าหมายเพื่อเป็น:
- **เปิดกว้าง (Vendor-Neutral Open Standard):** ไม่ผูกขาดกับค่ายซอฟต์แวร์ใด
- **ดูแลโดยชุมชนและสภาวิชาชีพ (Stewardship by Foundation):** ผ่านโครงสร้างของ **The debim Foundation**
- **เป็นมิตรต่อ AI ยุคหน้า (AI-Native by Design):** รองรับ Context Window ขนาดเล็ก คำนวณราคา (BOQ) และถอดปริมาณงาน (QTO) ได้แม่นยำ 100%
