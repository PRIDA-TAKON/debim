# The debim Foundation: Governance & Stewardship Model

โครงสร้างการกำกับดูแลและบริหารจัดการ **The debim Project / The debim Foundation** เพื่อให้การพัฒนาภาษา **debim (Declarative BIM)** ดำเนินไปอย่างโปร่งใส เป็นกลาง ปราศจากการครอบงำทางการค้า และยั่งยืนในระยะยาว

---

## 🏛️ 1. รูปแบบองค์กรและการบริหาร (Organization Structure)

เพื่อความมั่นคงและเป็นกลาง debim Foundation จะดำเนินงานในรูปแบบ **Non-profit Open Source Consortium** คล้ายคลึงกับ OpenTofu, CNCF หรือ Alliance for OpenUSD โดยมีโครงสร้างดังนี้:

```
              ┌─────────────────────────────────────────┐
              │          Steering Committee             │
              │  (คณะกรรมการกำกับทิศทางและยุทธศาสตร์)    │
              └────────────────────┬────────────────────┘
                                   │
       ┌───────────────────────────┼───────────────────────────┐
       ▼                           ▼                           ▼
┌──────────────┐           ┌──────────────┐            ┌──────────────┐
│  Spec & DSL  │           │ Compliance & │            │  QTO, Cost & │
│Working Group │           │ Legal Rules  │            │ Specification│
│ (ไวยากรณ์/สเปก)│           │(กฎหมาย/เทศบัญญัติ)│         │(ถอดแบบ/BOQ)  │
└──────────────┘           └──────────────┘            └──────────────┘
                                   │
                                   ▼
                   ┌──────────────────────────────┐
                   │   Tooling & Interoperability │
                   │(Compilers, IFC, Plugins, LSP)│
                   └──────────────────────────────┘
```

### 1.1 Steering Committee (คณะกรรมการกำกับ)
- ตัวแทนจากภาควิชาชีพสถาปัตยกรรม (Architectural Firms)
- ตัวแทนจากภาควิศวกรรมและผู้รับเหมา (General Contractors & Engineering)
- ตัวแทนจากภาคการศึกษาและสถาบันวิจัย (Universities & Research Institutes)
- ผู้พัฒนาแกนหลัก (Core Technical Contributors)

### 1.2 คณะทำงานเฉพาะด้าน (Working Groups - WGs)
1. **Language & Specification WG:** ดูแลโครงสร้างไวยากรณ์ (Syntax), AST, Schema definitions, การดูแลแค็ตตาล็อกระดับโลกบน **SchemaStore.org**, และกระบวนการ RFC
2. **Deterministic Compliance WG:** แปลงกฎหมายอาคาร, ข้อบัญญัติท้องถิ่น, และมาตรฐานวิศวกรรมให้เป็น Unit Test Suite
3. **QTO & Cost Estimation WG:** ดูแลมาตรฐานสูตรการถอดปริมาณงาน (Quantitative Take-Off), บัญชีราคากลาง, และ MasterFormat/Uniformat
4. **Tooling & Ecosystem WG:** ดูแล Reference Compilers, IFC4 Exporter, VS Code LSP, 3D Web Viewers (Live Hot-Reload), และปลั๊กอิน (BlenderBIM, Revit, Rhino)

---

## 📜 2. กระบวนการเสนอและปรับปรุงภาษา (The RFC Process)

การเปลี่ยนแปลงใดๆ ในระดับไวยากรณ์หรือความสามารถหลักของภาษา debim ต้องผ่านกระบวนการ **Request for Comments (RFC)**:

1. **Idea / Discussion:** นำเสนอไอเดียใน GitHub Discussions หรือ Community Forum
2. **Draft RFC:** ยื่น Pull Request เอกสาร RFC เข้าสู่โฟลเดอร์ `rfcs/` ตาม Template
3. **Community Review & Debate:** เปิดรับฟังความเห็นจากชุมชนเป็นเวลาอย่างน้อย 14 วัน
4. **WG & Committee Decision:** 
   - `Accepted`: ผ่านการอนุมัติและพร้อมนำไปบรรจุใน Roadmaps
   - `Needs Revision`: ส่งกลับไปแก้ไข
   - `Rejected`: ปฏิเสธพร้อมเหตุผลทางเทคนิค
5. **Implementation & Certification:** ทำการพัฒนา Reference Implementation และเขียน Test Cases ยืนยัน

---

## ⚖️ 3. นโยบายสิทธิบัตรและลิขสิทธิ์ (Licensing & Intellectual Property)

- **Language Specifications & Documentation:** เผยแพร่ภายใต้สัญญาอนุญาต **Creative Commons Attribution 4.0 International (CC-BY 4.0)** เพื่อให้ทุกคนสามารถนำสเปกไปใช้งานได้อย่างเสรี
- **Reference Compilers & Codebase:** เผยแพร่ภายใต้สัญญาอนุญาต **Apache License 2.0** หรือ **MIT License** เพื่อให้ทั้งภาคธุรกิจและนักพัฒนาอิสระนำไปต่อยอดได้โดยไม่มีข้อจำกัด
- **No Patent Traps:** มีข้อกำหนดสิทธิบัตรแบบไม่แสวงหาผลกำไร (Patent Grant) ป้องกันไม่ให้สมาชิกฟ้องร้องสิทธิบัตรซอฟต์แวร์ต่อชุมชน

---

## 🤝 4. ความร่วมมือกับองค์กรพันธมิตร (Ecosystem Partnerships)

- **buildingSMART International:** ส่งเสริมให้ debim เป็น Declarative Companion ที่คอมไพล์เป็น IFC4/IFC5 ได้อย่างสมบูรณ์แบบ
- **OSArch (Open Source Architecture):** เชื่อมโยงกับเครื่องมือสร้างสรรค์เสรี เช่น BlenderBIM, FreeCAD, และ IfcOpenShell
- **สภาวิชาชีพและหน่วยงานกำกับดูแลภาครัฐ:** ส่งเสริมการใช้โมเดล Declarative ตรวจสอบแบบขออนุญาตก่อสร้างอัตโนมัติ (Automated Code Compliance)
