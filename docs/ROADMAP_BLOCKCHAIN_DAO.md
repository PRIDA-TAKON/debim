# 🗺️ debim Blockchain & DAO Smart Escrow Roadmap
## Trustless Building-as-Code Delivery & Automated Milestone Settlement

> **Target Version:** `debim v1.4.0` (Blockchain & DAO Escrow Module)  
> **Status:** `PLANNED`  
> **Target Subsystem:** `debim.dao` / `debim-web3-bridge`  
> **Core Philosophy:** *Transforming Architecture Procurement: From Slow Paperwork & Bank Guarantees to Automated Code Verification and Trustless Smart Contract Settlements*

---

## 1. บทนำและวิสัยทัศน์ (Executive Summary & Vision)

ในวงการก่อสร้างและออกแบบสถาปัตยกรรมดั้งเดิม การจ่ายเงินงวดงานออกแบบระหว่าง **"ผู้ว่าจ้าง" (Client/Employer)** และ **"สถาปนิก" (Architect/Engineer)** มีอุปสรรคและต้นทุนแฝงมหาศาล:
1. **ต้นทุนและพิธีการของ Bank Guarantee:** ผู้ว่าจ้างหรือผู้รับเหมาต้องวางหลักประกันกับสถาบันการเงินเพื่อออกหนังสือค้ำประกัน (Letter of Credit / Bank Guarantee) ซึ่งเสียค่าธรรมเนียมรายปี 1–3% และใช้เวลาเดินเรื่องเอกสารนานหลายสัปดาห์
2. **ปัญหาการตรวจรับแบบที่เป็นอัตนัย (Subjective Review Bottleneck):** ผู้ว่าจ้างใช้เวลานานในการตรวจสอบแบบ Drawing (PDF/CAD) สุ่มตรวจด้วยสายตา ทำให้การตรวจรับงวดงานล่าช้าเป็นเดือน
3. **ความเสี่ยงการเบี้ยวหนี้และการดึงงวดเงิน (Payment Withholding Risk):** สถาปนิกส่งมอบแบบเรียบร้อยแล้ว แต่มักถูกดึงงวดเงิน เลื่อนการจ่าย หรือต้องรอการเคลียร์ริ่งเงินจากธนาคาร

**debim** ได้เปลี่ยนผ่านสถาปัตยกรรมสู่ **"Building-as-Code"** โดยทำให้แบบอาคารทั้งหลังถูกนิยามด้วยไฟล์ข้อความเชิงประกาศ (Declarative Text Manifest) ในฟอร์แมต `.debim` ที่ตรวจสอบความถูกต้องทางกฎหมายและวิศวกรรมได้ด้วยโค้ดทดสอบอัตโนมัติ (Automated Unit Tests)

ด้วยคุณสมบัตินี้ **debim v1.4.0** จึงเสนอสถาปัตยกรรม **"Web3 DAO & Smart Contract Escrow"** ที่ปฏิวัติกระบวนการจัดจ้างและส่งมอบแบบ:
* ผู้ว่าจ้างล็อกเงินงวด (Milestone Escrow) ด้วย Cryptocurrency หรือ Stablecoin (เช่น USDC / USDT) บน Smart Contract
* สถาปนิกส่งมอบงานเป็นไฟล์ **`.debim`** ต้นฉบับ
* ระบบรันชุดทดสอบอัตโนมัติ (Automated Script Test) เช่น การตรวจสอบกฎกระทรวง (MR 55), ระยะร่น, ความถูกต้องเชิงเรขาคณิต (AST Validation), และกรอบงบประมาณ
* **เมื่อสคริปต์เทสผ่าน 100% -> Smart Contract จะโอนเงินงวดจากบล็อกเชนเข้ากระเป๋าเงิน (Wallet) ของสถาปนิกทันทีโดยอัตโนมัติ** ไร้ตัวกลาง ไร้การดึงงวด และลดเวลาจากหลักเดือนเหลือเพียงไม่กี่วินาที

---

## 2. ทำไมต้องจัดเก็บเฉพาะ `.debim` บน DAO / บล็อกเชน? (Why Store ONLY `.debim`?)

> [!IMPORTANT]
> **จัดเก็บเฉพาะไฟล์ Source Code `.debim` บน DAO/Decentralized Storage เท่านั้น โดยไม่เก็บไฟล์ที่คอมไพล์แล้ว (Compiled Artifacts) เช่น IFC, BOQ, DXF, หรือ HTML Viewers**

| มิติการเปรียบเทียบ | ไฟล์ Source Code `.debim` | ไฟล์ที่คอมไพล์แล้ว (IFC, BOQ, DXF, GLB) |
| :--- | :--- | :--- |
| **ขนาดของไฟล์ (File Size)** | **เบามาก (Lightweight):** 5 KB – 200 KB ต่อทั้งอาคาร | **หนักมาก (Bloated):** 50 MB – 2 GB ต่อโมเดล |
| **ต้นทุนจัดเก็บ (Gas & Storage Cost)** | ต่ำมาก สามารถเก็บบน IPFS, Arweave หรือ Calldata/State ได้โดยตรง | ค่าจัดเก็บบนเชนหรือ Decentralized Storage สูงเกินความจำเป็น |
| **คุณสมบัติ Determinism** | **Single Source of Truth:** สามารถคอมไพล์ซ้ำได้ผลลัพธ์เหมือนเดิม 100% ทุกครั้ง | เกิดปัญหา Redundancy, Data Drift และแตกแขนงได้ง่าย |
| **การตรวจสอบด้วยโค้ด (Verifiability)** | สามารถ Parse เป็น AST และรัน Unit Test ใน Isolated Sandbox ได้อย่างรวดเร็ว | ไฟล์ Binary ซับซ้อน รันเทสบน Smart Contract / Oracle ได้ยาก |

**สรุป:** ในแนวคิด Building-as-Code ไฟล์ `.debim` เปรียบเสมือน Codebase บน Git ส่วน IFC และ BOQ เปรียบเสมือน Binary Artifacts (เช่น `.exe` หรือ `.dll`) ดังนั้นระบบ DAO จึงจัดการและปกป้องเฉพาะ Source Code `.debim` เท่านั้น ทุกฝ่ายสามารถนำ `.debim` ไปคอมไพล์เป็น IFC หรือ BOQ ในเครื่องตนเองได้ตลอดเวลา

---

## 3. เปรียบเทียบกระบวนทัศน์ (Paradigm Shift Comparison)

```
[กระบวนการเดิม: Traditional Bank Guarantee & Manual Drawdown]
┌────────────┐   ขอออก BG (1-3% fee)   ┌──────────────┐   สถาปนิกส่งแบบ (CAD/PDF)   ┌──────────────┐
│  ผู้ว่าจ้าง   ├───────────────────────►│  ธนาคารพาณิชย์ │◄────────────────────────────┤   สถาปนิก     │
└────────────┘                         └──────┬───────┘                             └──────▲───────┘
                                              │                                            │
                                              ▼ ตรวจเอกสาร Manual + รออนุมัติ (30-60 วัน)      │
                                              └────────────────────────────────────────────┘
                                                             เบิกเงินงวดล่าช้า

══════════════════════════════════════════════════════════════════════════════════════════════════════

[กระบวนทัศน์ใหม่: debim Blockchain DAO Smart Contract Escrow]
┌────────────┐        1. ล็อกเงินงวด (USDC)          ┌───────────────────────────────────┐
│  ผู้ว่าจ้าง   ├────────────────────────────────────►│ Smart Contract Escrow (DAO Vault) │
└────────────┘                                      └─────────────────┬─────────────────┘
                                                                      │
                                                    4. สคริปต์เทสผ่าน   │ 5. ปลดล็อกโอนเงินอัตโนมัติ
                                                       (Auto PASS)    │    เข้ากระเป๋าใน 10 วินาที
                                                                      ▼
┌────────────┐   2. ส่งมอบไฟล์ .debim   ┌──────────────────┐  3. ตรวจสอบ  ┌─────────────────────┐
│   สถาปนิก    ├──────────────────────►│ Decentralized    ├──อัตโนมัติ──►│ Verifiable Oracle   │
│  (Wallet)  │◄──────────────────────┤ DAO Registry     │             │ (debim test engine) │
└────────────┘  เงินเข้าบัญชีทันที         │ (IPFS / Arweave) ├─────────────┴─────────────────────┘
                                        └──────────────────┘
```

---

## 4. สถาปัตยกรรมทางเทคนิค 5 เสาหลัก (5 Core Technical Pillars)

```
                                [debim Web3 & DAO Ecosystem]
                                              │
      ┌──────────────────┬────────────────────┼───────────────────┬──────────────────┐
      ▼                  ▼                    ▼                   ▼                  ▼
1. Source Manifest   2. Milestone Escrow   3. Decentralized Test   4. Instant Payout  5. CLI & Web UI
   DAO Registry         Smart Contract        Oracle Engine          & Proof-NFT        Integration
   (Pure .debim CIDs)   (USDC/USDT Vault)     (debim test / MR55)    (Settlement)       (debim dao CLI)
```

---

### Pillar 1: Pure `.debim` Manifest Registry & Decentralized Storage
* **Content-Addressed Immutability:**  
  ไฟล์ `.debim` จะถูก Hash ด้วยอัลกอริทึมมาตรฐาน (`keccak256` และ IPFS `CIDv1`) ก่อนบันทึกลงสู่เครือข่าย Decentralized Storage (IPFS / Arweave / Filecoin)
* **Smart Contract Registry (`DebimProjectRegistry.sol`):**
  - บันทึก Metadata ของโครงการ: เจ้าของโครงการ (Client Address), สถาปนิกที่ได้รับมอบหมาย (Architect Address), แฮชของสัญญา และ Commit Hash ของ `.debim`
  - รองรับระบบ Versioning ในลักษณะ Semantic Versioning (เช่น `v0.1.0-milestone1`) ป้องกันการแก้ไขไฟล์ย้อนหลัง (Tamper-proof)

### Pillar 2: Milestone Escrow Smart Contract & Governance Vault (`DebimEscrow.sol`)
* **Conditional Milestone Locking:**  
  ผู้ว่าจ้างโอน Stablecoin (USDC, USDT หรือ Native Token) เข้าสู่ Escrow Vault โดยแบ่งสัดส่วนตามงวดงาน เช่น:
  - *งวดที่ 1 (30%):* ผังบริเวณและการวางตำแหน่งอาคาร (Site Layout, Setbacks, Building Footprint)
  - *งวดที่ 2 (40%):* โครงสร้างอาคารและสถาปัตยกรรมสมบูรณ์ (Slabs, Columns, Walls, Fenestration)
  - *งวดที่ 3 (30%):* งานระบบและข้อกำหนดเชิงวิศวกรรม (MEP Routing & Specs)
* **Decentralized Dispute Resolution (DAO Arbitration):**  
  หากเกิดกรณีขัดแย้งที่ไม่สามารถตัดสินด้วยสคริปต์ได้ (เช่น การเปลี่ยน Requirement กลางคัน หรือมุมมองความงาม) สามารถเปิดโหวตผ่านคณะกรรมการอนุญาโตตุลาการสถาปัตยกรรมแบบกระจายศูนย์ (Architectural Arbitration DAO) พร้อมระบบ Timelock และ Grace Period

### Pillar 3: Verifiable Test Oracle & Sandbox Engine (`debim-oracle`)
* **Automated Acceptance Criteria:**  
  หัวใจสำคัญของการเบิกงวดอัตโนมัติ คือการแปลงเงื่อนไขส่งมอบงานให้อยู่ในรูปของ **"สคริปต์ทดสอบ (Test Suites)"**
* **เกณฑ์การทดสอบที่รันบน Test Oracle:**
  1. **Syntax & AST Integrity:** ไฟล์ `.debim` ถูกต้องตามมาตรฐานไวยากรณ์ ไม่มี Syntax Error
  2. **Regulatory & Building Code Compliance:** รัน `debim compliance` เช่น ระยะร่นถนนสาธารณะ, พื้นที่ว่างไม่น้อยกว่า 30%, ช่องเปิดระบายอากาศ, ความสูงขั้นต่ำตามกฎกระทรวง ฉบับที่ 55
  3. **Geometric & Clash Sanity:** ไม่มี Geometry ที่ซ้อนทับกัน (Clash-free) หรือขอบเขตระนาบที่ผิดตรรกะ
  4. **Cost & Material Ceiling:** คำนวณปริมาณวัสดุผ่าน `debim boq` เบื้องต้น เพื่อยืนยันว่าโครงสร้างอยู่ในกรอบงบประมาณที่ผู้ว่าจ้างกำหนด
* **Verifiable Execution (Chainlink Functions / Phala TEE / ZK Proof):**  
  ชุดคำสั่งทดสอบจะถูกรันในสภาพแวดล้อมที่ตรวจสอบได้ (Trusted Execution Environment / Decentralized Oracle Node) และส่งผลลัพธ์พร้อม Digital Signature ยืนยันว่าผลเทสเป็น `PASS` เข้าสู่ Smart Contract

### Pillar 4: Instant Automated Settlement & Proof-of-Design NFT
* **Zero-Friction Liquidity:**  
  เมื่อ Callback ของ Oracle ส่งสถานะ `PASS` เข้ามา Smart Contract จะเรียกคำสั่ง `transfer()` โอนเงินงวดคริปโตตรงเข้ากระเป๋าเงินของสถาปนิกภายใน Block ถัดไปทันที
* **Proof-of-Design Token (ERC-721 / Soulbound Token):**  
  ระบบจะมิ้นต์ NFT รับรองการส่งมอบแบบแต่ละงวด เพื่อเป็นหลักฐานทางลิขสิทธิ์สถาปัตยกรรม (IP & Copyright Provenance) และใบเสร็จรับเงินบนบล็อกเชนสำหรับใช้ในระบบบัญชีและภาษี
* **Account Abstraction (ERC-4337):**  
  รองรับระบบ Sponsored Gas และ Social Login ทำให้ผู้ว่าจ้างและสถาปนิกใช้งานได้ง่ายผ่านอีเมล โดยไม่ต้องมีเหรียญสำหรับจ่ายค่า Gas ด้วยตนเอง

### Pillar 5: debim CLI & Ingetrazo UI Integration
* **Command Line Interface (`debim dao`):**
  - `debim dao project init --budget 50000 --token USDC` — เริ่มต้นสร้างสัญญาโครงการ
  - `debim dao milestone define --id M1 --amount 15000 --test tests/m1_compliance.py` — ผูกเงื่อนไขงวดงานกับสคริปต์
  - `debim dao submit --project-id 0x123... --file master.debim` — สถาปนิกส่งมอบแบบ
  - `debim dao verify --submission-id 0xabc...` — เรียก Test Oracle เพื่อประมวลผล
  - `debim dao status --project-id 0x123...` — ตรวจสอบสถานะการล็อกเงินและงวดงาน
* **Ingetrazo 3D Viewport & Web Dashboard:**  
  วิดเจ็ตแสดงผลสถานะ Smart Contract Escrow บนมุมจอ Ingetrazo: แสดงยอดเงินที่ล็อกอยู่, แถบสถานะงวดงาน, ปุ่ม Connect Wallet (MetaMask, Phantom), และปุ่ม 1-Click Submit & Claim Funds

---

## 5. แผนการพัฒนารายเฟส (Phase-by-Phase Implementation Roadmap)

```
[Phase 1: Foundation (Q1)]
  • สร้าง DebimProjectRegistry.sol สำหรับจัดเก็บ Manifest CIDs
  • พัฒนา debim dao hash & publish ลง IPFS/Arweave
    │
[Phase 2: Escrow Core (Q2)]
  • พัฒนา DebimEscrow.sol (ERC-20 Milestone Lock & Timelock)
  • สร้าง Mock Oracle สำหรับทดสอบ Flow ปลดล็อกเงินตามเงื่อนไข
    │
[Phase 3: Verifiable Test Oracle (Q3)]
  • เชื่อมต่อ Chainlink Functions / Phala TEE สำหรับรัน debim test / compliance
  • พัฒนา Script Test Templates มาตรฐาน (MR 55, Setbacks, Footprint)
    │
[Phase 4: Production Settlement & Dispute DAO (Q4)]
  • บูรณาการ Multi-sig DAO สำหรับกรณี Dispute Resolution
  • เปิดใช้งาน Proof-of-Design NFT (ERC-721)
  • ทำ Security Audit สำหรับ Smart Contracts ทั้งหมด
    │
[Phase 5: Seamless Ecosystem UX (Q1 Next)]
  • บูรณาการเข้ากับ IngeTrazo Web Viewer (Web3 Modal)
  • คำสั่งสมบูรณ์ใน debim CLI: debim dao submit / verify / claim
```

---

## 6. กรณีศึกษาเปรียบเทียบการใช้งานจริง (Real-World Scenario)

### กรณีศึกษา: งานออกแบบอาคารพักอาศัย 2 ชั้น มูลค่างานออกแบบ 150,000 บาท

1. **การตั้งค่าสัญญา (Setup):**
   * ผู้ว่าจ้างฝากเงิน 4,200 USDC (~150,000 บาท) เข้าสู่ `DebimEscrow` Contract
   * สัญญากำหนดงวดที่ 1 (1,200 USDC): แบบผังอาคาร ต้องผ่าน `tests/test_setback_mr55.py`
2. **การส่งมอบ (Submission):**
   * สถาปนิกทำงานบน `house.debim` ในเครื่องหรือผ่าน IngeTrazo
   * รันคำสั่ง `debim dao submit --file house.debim` ไฟล์ขนาด 18 KB ถูกบันทึกลง IPFS พร้อมบันทึก CID บนเชน
3. **การทดสอบอัตโนมัติ (Verification):**
   * Oracle รันคำสั่ง `debim compliance house.debim`
   * ตรวจสอบว่าระยะร่นจากถนนใหญ่เกิน 2.00 เมตร, ช่องเปิดแสงสว่างเกิน 10% ของพื้นที่ห้อง -> **Result: 14 passed in 0.12s**
4. **การจ่ายเงินทันที (Settlement):**
   * Oracle ส่ง Signature ยืนยันไปยัง Smart Contract
   * Smart Contract โอน 1,200 USDC เข้ากระเป๋าเงินของสถาปนิกทันทีภายใน 12 วินาที
   * ทั้งสองฝ่ายได้รับ Proof-of-Delivery NFT บนเครือข่าย ปราศจากข้อโต้แย้ง

---

## 7. มาตรการความปลอดภัยและธรรมาภิบาล (Security & Governance)

* **Re-entrancy Protection & OpenZeppelin Standard:** ใช้ไลบรารี Smart Contract ที่ผ่านการทดสอบระดับสากล
* **Sandboxed Test Execution:** Oracle รันการทดสอบใน Container / WebAssembly Sandbox แบบไร้การเชื่อมต่ออินเทอร์เน็ต เพื่อป้องกันสคริปต์ไม่พึงประสงค์ (No Malicious Code Execution)
* **Fail-safe Timelock & Refund:** หากสถาปนิกไม่ส่งมอบแบบภายในเวลาที่กำหนด ผู้ว่าจ้างสามารถกดขอคืนเงิน (Refund) ตามเงื่อนไข Timelock ที่ระบุไว้ในสัญญา
* **Privacy Option:** สำหรับโครงการที่ต้องการเก็บข้อมูลเป็นความลับ รองรับการเข้ารหัสไฟล์ `.debim` แบบ Asymmetric Encryption (เข้าถึงได้เฉพาะ Private Key ของผู้ว่าจ้าง, สถาปนิก, และ Oracle Sandbox)

---

## 8. สรุปคุณค่าทางธุรกิจ (Value Proposition)

| มิติ | โลกเดิม (Traditional Banking) | โลกใหม่ของ debim DAO |
| :--- | :--- | :--- |
| **ระยะเวลาอนุมัติและจ่ายเงิน** | 30 – 90 วัน | **< 1 นาที** หลังสคริปต์เทสผ่าน |
| **ค่าธรรมเนียมตัวกลาง** | 1% – 3% ต่อปี (Bank Guarantee Fees) | **ค่า Gas เพียงไม่กี่บาท** (L2 / Solana / Base) |
| **ความโปร่งใส** | ตรวจสอบยาก เอกสารกระจัดกระจาย | ตรวจสอบได้ 100% บนบล็อกเชนสาธารณะ |
| **เกณฑ์การตรวจรับ** | อัตนัย (ขึ้นกับอารมณ์และการสุ่มตรวจของบุคคล) | **ภววิสัย (Deterministic Test Suite ที่ตกลงกันไว้ล่วงหน้า)** |
