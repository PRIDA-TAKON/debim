# SchemaStore.org Submission Blueprint & Global IDE Catalog Plan

แผนงานการส่งมอบ **`debim.schema.json`** เข้าสู่ **SchemaStore.org** เพื่อให้โปรแกรม Editor ทั่วโลก (VS Code, JetBrains IDEs, Visual Studio, Neovim, Sublime Text) เปิดใช้งาน Autocomplete และ Validation อัตโนมัติทันทีที่ผู้ใช้สร้างไฟล์ `*.debim` หรือ `*.debim.yaml`

---

## 🌍 1. ประโยชน์ของ SchemaStore.org ต่อ debim

เมื่อ `debim` ได้รับการบรรจุเข้าสู่แค็ตตาล็อกของ [SchemaStore.org](https://www.schemastore.org/):
1. **Zero-Configuration Experience:** ผู้ใช้และสถาปนิกทั่วโลกไม่จำเป็นต้องแก้ไข `.vscode/settings.json` เองอีกต่อไป
2. **Global Recognition:** เมื่อใครสร้างไฟล์ `house.debim` หรือ `project.debim.yaml` ตัว Editor ทุกค่ายจะดึงสเปกของ `debim` ไปเปิดใช้งาน IntelliSense ทันที
3. **Official Standard Presence:** เป็นหมุดหมายสำคัญที่พิสูจน์ความเป็น "Open Standard" ของภาษาในระดับเดียวกับ Dockerfile, Kubernetes YAML, และ GitHub Actions

---

## 📋 2. รายละเอียดการส่ง Pull Request (PR Blueprint)

### ที่อยู่ Repository:
- **Upstream:** `https://github.com/SchemaStore/schemastore`
- **Target File:** `src/api/json/catalog.json`

### ข้อมูล Catalog Entry ที่ต้องเพิ่มใน `src/api/json/catalog.json`:

```json
{
  "name": "debim",
  "description": "Official schema for debim (Declarative BIM / Building-as-Code) manifests",
  "fileMatch": [
    "*.debim",
    "*.debim.yaml",
    "*.debim.yml",
    "*.dbim",
    "*.dbim.yaml",
    "*.dbim.yml",
    "project.debim",
    "project.debim.yaml"
  ],
  "url": "https://raw.githubusercontent.com/PRIDA-TAKON/debim/main/debim.schema.json",
  "versions": {
    "1.0": "https://raw.githubusercontent.com/PRIDA-TAKON/debim/main/debim.schema.json"
  }
}
```

---

## 🧪 3. การเตรียมไฟล์ทดสอบสำหรับ SchemaStore CI (Positive/Negative Tests)

SchemaStore กำหนดให้มีไฟล์ตัวอย่างทดสอบในโฟลเดอร์ `src/test/`:

1. **Positive Test (`src/test/debim/test-house.debim.json` หรือ yaml):**
   - ใช้โมเดลบ้านมาตรฐาน `house.debim` หรือ `farnsworth_house` ตรวจสอบว่าผ่านการ Validate 100%
2. **Negative Test:**
   - ทดสอบว่าหากขาดคีย์บังคับ (เช่น ลืมใส่ `spatial_structure` หรือระบุรูปทรงนอกเหนือจาก Enum) ตัว Schema จะเตือน Error ทันที

---

## 🚀 4. แผนการยื่น PR (Execution Checklist)

- [x] ตรวจสอบว่า `debim.schema.json` ผ่านมาตรฐาน JSON Schema Draft 2020-12 / Draft-07
- [x] กำหนด `$id: "https://debim.org/schema/v1/debim.schema.json"` และ `$schema`
- [x] ทดสอบการแมปไฟล์ `*.debim` และ `*.debim.yaml`
- [ ] Fork `SchemaStore/schemastore` บน GitHub
- [ ] สร้าง Branch: `feat/add-debim-schema`
- [ ] เพิ่ม JSON Snippet ใน `src/api/json/catalog.json`
- [ ] รัน `npm test` ใน repo ของ SchemaStore เพื่อยืนยันว่า CI ผ่าน
- [ ] ยื่น Pull Request พร้อมคำอธิบาย Manifesto ของ debim Foundation
