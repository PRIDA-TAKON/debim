# OpenBIM Standard Duplex House (บ้านดูเพล็กซ์มาตรฐานสากล OpenBIM)

ตัวอย่างโครงการแปลงจากมาตรฐานสากล OpenBIM (`buildingSMART International`) โดยรวบรวมข้อมูลครบทั้ง 4 สาขาวิชา:
1. **งานสถาปัตยกรรม (Architectural):** ผนัง (`IfcWall`), หลังคา (`IfcRoof`), ฝ้าและวัสดุปิดผิว (`IfcCovering`), ประตู, หน้าต่าง
2. **งานโครงสร้าง (Structural):** พื้นคอนกรีตเสริมเหล็ก (`IfcSlab`), คาน (`IfcBeam`)
3. **งานระบบอาคาร (MEP):**
   - สุขภัณฑ์ (`mep_fixtures.yaml`): โถสุขภัณฑ์, อ่างล้างหน้า, อ่างอาบน้ำ, ฝักบัว
   - ท่อและสุขาภิบาล (`mep_plumbing.yaml`): ท่อน้ำดี (Cold/Hot Water), ท่อน้ำเสีย (Waste), ท่อ PVC, ข้อต่อ (Elbow, Tee, Transition)
   - ปรับอากาศและการถ่ายเทอากาศ (`mep_hvac.yaml`): ท่อดักต์กลม (Round Duct), ท่อทางกล (Mechanical Pipe)
   - ไฟฟ้า (`mep_electrical.yaml`): ท่อร้อยสายไฟโลหะ EMT, ตู้พาเนลสวิตช์บอร์ด, โคมไฟ (Sconce Light, Pendant Light)
4. **งานเฟอร์นิเจอร์และการตกแต่ง (Furniture & Furnishing):** โต๊ะทำงาน, เก้าอี้, เตียง, โซฟา, เคาน์เตอร์ครัว, ตู้เสื้อผ้า (รวม 139 ชิ้น)

---

## โครงสร้างไฟล์ (File Structure)

```plaintext
examples/openbim_duplex/
├── project.yaml            # Declarative BIM Master Manifest
├── view.html               # 3D Interactive Web Viewer (พร้อมเปิดดูในเบราว์เซอร์)
├── viewer.html             # ลิงก์สำเนา 3D Viewer
├── prices.template.yaml    # เทมเพลตราคาวัสดุและค่าแรง
├── README.md               # เอกสารประกอบโครงการ
└── modules/
    ├── architecture.yaml   # งานสถาปัตย์ (71 elements)
    ├── structure.yaml      # งานโครงสร้าง (29 elements)
    ├── furniture.yaml      # งานเฟอร์นิเจอร์ (139 elements)
    ├── mep_fixtures.yaml   # สุขภัณฑ์ (18 elements)
    ├── mep_plumbing.yaml   # ระบบท่อและสุขาภิบาล (589 elements)
    ├── mep_hvac.yaml       # ระบบปรับอากาศและเครื่องกล (176 elements)
    └── mep_electrical.yaml # ระบบไฟฟ้าและแสงสว่าง (48 elements)
```

---

## คำสั่ง CLI ที่เกี่ยวข้อง

### 1. ตรวจสอบความถูกต้องของโมเดล
```powershell
python -m debim.cli validate -m examples/openbim_duplex/project.yaml
```

### 2. คำนวณปริมาณงาน (QTO)
```powershell
python -m debim.cli qto -m examples/openbim_duplex/project.yaml
```

### 3. ส่งออกหรือเปิดดู 3D Interactive Viewer
```powershell
# เปิดเซิร์ฟเวอร์ดูโมเดล 3D แบบ interactive:
python -m debim.cli view -m examples/openbim_duplex/project.yaml

# ส่งออกเป็นไฟล์ HTML แบบ standalone:
python -m debim.cli view -m examples/openbim_duplex/project.yaml -e examples/openbim_duplex/view.html --no-browser
```
