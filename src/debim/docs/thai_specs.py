"""
Thai Architectural Specification & Workmanship Standard Library for debim.
Maps IFC entities to MasterFormat / CSI divisions and provides standard Thai specification clauses:
- Material standards (TIS / มอก., ASTM, JIS, ISO)
- Workmanship & installation requirements (การเข้าแบบ, ระยะทาบ, การบ่ม, การติดตั้ง)
- Testing & inspection standards (Slump test, Compressive strength test, Hydrostatic test, ฯลฯ)
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class ThaiSpecClause(BaseModel):
    masterformat_code: str
    masterformat_title: str
    masterformat_title_en: Optional[str] = ""
    material_standards: str
    material_standards_en: Optional[str] = ""
    workmanship_requirements: str
    workmanship_requirements_en: Optional[str] = ""
    testing_inspection: str
    testing_inspection_en: Optional[str] = ""

    def to_markdown(self) -> str:
        return (
            f"### Division {self.masterformat_code} - {self.masterformat_title}\n\n"
            f"**1. มาตรฐานวัสดุ (Material Standards):**\n{self.material_standards}\n\n"
            f"**2. ข้อกำหนดการทำงานและการติดตั้ง (Workmanship & Installation):**\n{self.workmanship_requirements}\n\n"
            f"**3. การทดสอบและการตรวจสอบ (Testing & Inspection):**\n{self.testing_inspection}\n"
        )


THAI_SPEC_LIBRARY: Dict[str, ThaiSpecClause] = {
    "03 30 00": ThaiSpecClause(
        masterformat_code="03 30 00",
        masterformat_title="Cast-in-Place Concrete (งานคอนกรีตโครงสร้างหล่อในที่)",
        masterformat_title_en="Cast-in-Place Concrete Structure",
        material_standards=(
            "- ปูนซีเมนต์ปอร์ตแลนด์ประเภท 1 ตามมาตรฐาน มอก. 15 เล่ม 1 หรือ ASTM C150 Type I\n"
            "- คอนกรีตผสมเสร็จ ต้องมีกำลังอัดทรงกระบอกไม่น้อยกว่า 240 - 350 ksc ที่อายุ 28 วัน (มอก. 2137 / ASTM C94)\n"
            "- เหล็กเส้นเสริมคอนกรีต เหล็กเส้นกลม SR24 (มอก. 20) และเหล็กข้ออ้อย SD40 / SD50 (มอก. 24)\n"
            "- น้ำผสมคอนกรีต สะอาด ปราศจากกรด ด่าง น้ำมัน และสารเคมีที่เป็นอันตราย"
        ),
        material_standards_en=(
            "- Portland Cement Type 1 complying with TIS 15 Vol 1 or ASTM C150 Type I\n"
            "- Ready-mixed concrete specified cylinder compressive strength >= 240 - 350 ksc at 28 days (TIS 2137 / ASTM C94)\n"
            "- Concrete reinforcing rebar: Round bars SR24 (TIS 20) and Deformed bars SD40 / SD50 (TIS 24)\n"
            "- Mixing water shall be clean and free from harmful acids, alkalis, oils, or organic materials"
        ),
        workmanship_requirements=(
            "- การตั้งและประกอบแบบหล่อ (Formwork): แบบหล่อต้องแข็งแรง ไม่คดงอ ค้ำยันมั่นคง กันน้ำปูนรั่วซึมได้\n"
            "- ระยะทาบเหล็กเสริม (Lap Splicing): ระยะทาบต้องไม่น้อยกว่า 40 เท่าของเส้นผ่านศูนย์กลางเหล็ก (40d) หรือตามรายการคำนวณวิศวกร\n"
            "- การเทและจุ่มจีบหล่อคอนกรีต: จุ่มเครื่องสั่นคอนกรีต (Vibrator) อย่างถูกวิธี ป้องกันการแยกตัวของมอร์ต้าร์และเกสรหิน\n"
            "- การบ่มคอนกรีต (Concrete Curing): บ่มชื้นต่อเนื่องอย่างน้อย 7 วัน โดยการรดน้ำ บ่มด้วยกระสอบป่านชื้น หรือพ่นสารเคมีบ่มคอนกรีต"
        ),
        workmanship_requirements_en=(
            "- Formwork erection: Forms shall be rigid, leak-tight, adequately braced, and aligned to maintain tolerances\n"
            "- Rebar lap splicing: Minimum lap length shall be 40 times bar diameter (40d) or per structural calculations\n"
            "- Concrete placement: Consolidate properly using internal mechanical vibrators without causing segregation\n"
            "- Curing process: Maintain moist curing for at least 7 continuous days using water sprays, wet burlap, or curing compounds"
        ),
        testing_inspection=(
            "- การทดสอบการยุบตัวของคอนกรีต (Slump Test) ตามมาตรฐาน ASTM C143 / มอก. 917 ค่ายุบตัว 7.5 - 12.5 ซม.\n"
            "- การเก็บตัวอย่างทดสอบกำลังอัด (Compressive Strength Test) หล่อลูกปูนทรงกระบอก (15x30 ซม.) หรือลูกกูบ (15x15x15 ซม.) ทุกๆ 50 ลบ.ม.\n"
            "- ตรวจสอบระยะคอนกรีตหุ้มเหล็ก (Concrete Covering) และความสะอาดภายในแบบหล่อก่อนการเทคอนกรีต"
        ),
        testing_inspection_en=(
            "- Slump test per ASTM C143 / TIS 917 with target range 7.5 - 12.5 cm\n"
            "- Compressive strength test cylinders (15x30 cm) or cubes (15x15x15 cm) sampled every 50 m3\n"
            "- Rebar clearance and formwork cleanout verification prior to concrete pouring"
        ),
    ),
    "04 20 00": ThaiSpecClause(
        masterformat_code="04 20 00",
        masterformat_title="Unit Masonry (งานผนังก่ออิฐและบล็อก)",
        masterformat_title_en="Unit Masonry Work",
        material_standards=(
            "- อิฐมอญก่อผนัง คุณภาพมาตรฐาน มอก. 77\n"
            "- อิฐมวลเบา (Autoclaved Aerated Concrete - AAC) มอก. 1505 ชนิด G2 หรือ G4\n"
            "- ปูนปลาสเตอร์ก่อและฉาบสำเร็จรูป มอก. 1776 หรือ ASTM C270\n"
            "- ตะแกรงกรงไก่ และเหล็กหนวดกุ้ง (Wall Ties) Ø 6มม. ชุบสังกะสีกันสนิม"
        ),
        material_standards_en=(
            "- Clay brick masonry conforming to TIS 77 standards\n"
            "- Autoclaved Aerated Concrete (AAC) blocks conforming to TIS 1505 Class G2 / G4\n"
            "- Pre-blended masonry mortar and plaster complying with TIS 1776 or ASTM C270\n"
            "- Galvanized steel wire mesh and wall ties (Ø 6mm) for structural interface anchorage"
        ),
        workmanship_requirements=(
            "- การก่ออิฐ: รดน้ำอิฐมอญให้อิ่มตัวก่อนก่อ เสียบเหล็กหนวดกุ้งยึดเสา-ผนังทุกระยะสูงไม่เกิน 0.40 ม. ยื่นเข้าผนังไม่น้อยกว่า 0.50 ม.\n"
            "- เสาเอ็นและทับหลัง (Lintel & Tie Beams): จัดทำเสาเอ็น ค.ส.ล. ทุกช่องเปิดประตู-หน้าต่าง และผนังก่อกว้างเกิน 2.50 ม. หรือสูงเกิน 3.00 ม.\n"
            "- งานฉาบปูน: จับเซี้ยมจับปุ่มได้ระดับดิ่งปราบ ติดตะแกรงกรงไก่บริเวณรอยต่อโครงสร้างและมุมช่องเปิด ป้องกันรอยแตกร้าว"
        ),
        workmanship_requirements_en=(
            "- Bricklaying: Pre-dampen clay bricks; anchor wall ties to concrete columns every 0.40m vertical interval\n"
            "- Lintels and tie beams: Provide RC stiffener columns/lintels at openings and wall panels exceeding 2.50m width or 3.00m height\n"
            "- Plastering: Install corner beads and metal mesh across concrete-masonry junctions to prevent hairline cracking"
        ),
        testing_inspection=(
            "- ตรวจสอบความได้ดิ่ง ได้ระดับ และแนวระนาบของผนัง (Tolerance ไม่เกิน 3 มม. ต่อระยะ 2.00 ม.)\n"
            "- ตรวจสอบการยึดเกาะแน่นของปูนฉาบ ปราศจากเสียงโพรง (Hollow sound) และรอยแตกร้าวลายงา (Hairline cracks)"
        ),
        testing_inspection_en=(
            "- Plumbness and levelness tolerance inspection (max 3mm variation per 2.00m)\n"
            "- Plaster adhesion sounding test to verify absence of hollow sounds or hairline shrink cracks"
        ),
    ),
    "05 12 00": ThaiSpecClause(
        masterformat_code="05 12 00",
        masterformat_title="Structural Steel Framing (งานโครงสร้างเหล็กรูปพรรณ)",
        masterformat_title_en="Structural Steel Framing",
        material_standards=(
            "- เหล็กโครงสร้างรูปพรรณรีดร้อน มอก. 1227 ชนิดเกรด SS400 หรือ SM490\n"
            "- เหล็กโครงสร้างรูปพรรณขึ้นรูปเย็น มอก. 107 / มอก. 1228\n"
            "- น็อตและสลักเกลียวยึดโครงสร้าง High Strength Bolts ASTM A325 หรือ A490\n"
            "- สีรองพื้นกันสนิมอะคริลิกเรซิน หรืออีพ็อกซี่เรซิน มาตรฐาน มอก. 2387"
        ),
        material_standards_en=(
            "- Hot-rolled structural steel shapes complying with TIS 1227 Grade SS400 or SM490\n"
            "- Cold-formed structural steel tubing per TIS 107 / TIS 1228\n"
            "- High-strength structural bolts, nuts, and washers complying with ASTM A325 or A490\n"
            "- Anti-corrosive primer coating (acrylic or epoxy) complying with TIS 2387"
        ),
        workmanship_requirements=(
            "- การตัดและการเตรียมขอบเหล็ก: ตัดด้วยเครื่องจักรเรียบตรง ลบคมเสี้ยนรอยตัด\n"
            "- งานเชื่อม (Welding Workmanship): ช่างเชื่อมต้องผ่านการรับรอง (Certified Welder) ตามมาตรฐาน AWS D1.1 แนวเชื่อมสมบูรณ์ ปราศจากรอยร้าว\n"
            "- การทำความสะอาดผิวเหล็กและการทาสี: พ่นทำความสะอาดผิวเหล็กระดับ Sa 2.5 (ISO 8501-1) ทาสีรองพื้นกันสนิมความหนาฟิล์มแห้งไม่น้อยกว่า 80 ไมครอน"
        ),
        workmanship_requirements_en=(
            "- Cutting and edge preparation: Machine cut edges smoothly and deburr all joint edges\n"
            "- Structural welding: Certified welders per AWS D1.1 code; welds shall be full penetration without cracks\n"
            "- Surface preparation: Abrasive blast clean to Sa 2.5 (ISO 8501-1) and apply anti-rust primer to dry film thickness >= 80 microns"
        ),
        testing_inspection=(
            "- การตรวจสอบรอยเชื่อมด้วยสายตา (Visual Testing - VT) และการทดสอบแบบไม่ทำลาย (NDT: Ultrasonic / Radiography Test)\n"
            "- ตรวจสอบค่าแรงบิดสลักเกลียว (Torque Wrench Inspection) ตามมาตรฐาน AISC\n"
            "- ตรวจสอบความหนาฟิล์มสี (Dry Film Thickness - DFT) ด้วยเครื่องวัดความหนาฟิล์มสี"
        ),
        testing_inspection_en=(
            "- Weld visual testing (VT) and non-destructive testing (NDT: Ultrasonic / Radiographic testing)\n"
            "- Bolt torque wrench calibration inspection per AISC specifications\n"
            "- Dry film thickness (DFT) paint gauge measurement"
        ),
    ),
    "08 10 00": ThaiSpecClause(
        masterformat_code="08 10 00",
        masterformat_title="Doors and Windows (งานประตู หน้าต่าง และกระจก)",
        masterformat_title_en="Doors, Windows & Glazing",
        material_standards=(
            "- กรอบบานอลูมิเนียมอบสีพาวเดอร์โค้ท (Powder Coated Aluminum) มอก. 218 / ASTM B221 ความหนาไม่น้อยกว่า 1.5 - 2.0 มม.\n"
            "- กระจกอินซูเลท / กระจกเทมเปอร์ / กระจกลามิเนต มอก. 965 / ASTM C1048\n"
            "- อุปกรณ์ฟิตติ้งและกุญแจยึดมาตรฐาน stainless steel 304"
        ),
        material_standards_en=(
            "- Powder-coated architectural aluminum extrusions complying with TIS 218 / ASTM B221 (thickness >= 1.5 - 2.0 mm)\n"
            "- Tempered, laminated, or insulated glass units complying with TIS 965 / ASTM C1048\n"
            "- Stainless steel 304 hardware fittings, hinges, handles, and locksets"
        ),
        workmanship_requirements=(
            "- การติดตั้งกรอบประตูหน้าต่าง: ติดตั้งในแนวระดับและได้ดิ่ง ยึดพุกพลาสติก/พุกเหล็กแน่นหนาทุกระยะไม่เกิน 0.60 ม.\n"
            "- การยิงซิลิโคนซีลแลนท์: ยิงโพลียูรีเทนหรือซิลิโคนกันน้ำรอบขอบกรอบภายนอกและภายในเต็มร่อง เรียบสม่ำเสมอ"
        ),
        workmanship_requirements_en=(
            "- Frame installation: Anchor frames plumb and level using structural fasteners at <= 0.60m intervals\n"
            "- Weather sealing: Apply continuous perimeter polyurethane or silicone sealant along interior and exterior joints"
        ),
        testing_inspection=(
            "- ทดสอบการรั่วซึมของน้ำ (Water Leakage Test) โดยการพ่นน้ำแรงดันสูงตามมาตรฐาน AAMA 501.2\n"
            "- ตรวจสอบการเปิด-ปิดราบรื่น ไม่ติดขัด และระบบล็อกทำงานสมบูรณ์"
        ),
        testing_inspection_en=(
            "- Field water penetration hose testing per AAMA 501.2 standard\n"
            "- Smooth operation, alignment, and multi-point lock mechanism verification"
        ),
    ),
    "12 00 00": ThaiSpecClause(
        masterformat_code="12 00 00",
        masterformat_title="Furnishings & Interior Elements (งานครุภัณฑ์ตกแต่งภายใน)",
        masterformat_title_en="Furnishings & Interior Elements",
        material_standards=(
            "- ไม้อัดสัก หรือไม้สังเคราะห์คุณภาพเกรด E1 ปราศจากสารระเหยฟอร์มาลดีไฮด์\n"
            "- อุปกรณ์ฟิตติ้งบานพับเปิด-ปิดระบบ Soft-Close มาตรฐาน ISO 9001\n"
            "- ผ้าหุ้มเบาะและวัสดุซับเสียงทนไฟมาตรฐาน มอก. 838"
        ),
        material_standards_en=(
            "- Teak plywood or E1 low-formaldehyde emission engineered wood panels\n"
            "- Heavy-duty soft-close hinges and drawer slides complying with ISO 9001\n"
            "- Fire-retardant upholstery fabrics and acoustic core materials complying with TIS 838"
        ),
        workmanship_requirements=(
            "- ติดตั้งประกอบลอยตัวและลอยแขวนยึดพุกแน่นหนา ได้ระดับฉากตามแบบสถาปัตยกรรม\n"
            "- ทำความสะอาดผิว ปิดขอบลามิเนตเนียนเรียบ ปราศจากรอยขีดข่วน"
        ),
        workmanship_requirements_en=(
            "- Assembly and installation: Anchor wall-hung and fixed furniture plumb, level, and square per architectural drawings\n"
            "- Edge banding: Smooth flush high-pressure laminate (HPL) edge banding without gaps or scratches"
        ),
        testing_inspection=(
            "- ตรวจสอบการรับน้ำหนักลิ้นชักและบานตู้ (Load Bearing Test) ปราศจากการตกท้องช้าง\n"
            "- ตรวจสอบการยึดติดของวัสดุผิวปิด (Adhesion Test)"
        ),
        testing_inspection_en=(
            "- Load-bearing deflection testing for drawers and shelving units\n"
            "- Surface laminate adhesion and finish inspection"
        ),
    ),
    "22 11 00": ThaiSpecClause(
        masterformat_code="22 11 00",
        masterformat_title="Facility Water Distribution & Plumbing (งานระบบสุขาภิบาลและประปา)",
        masterformat_title_en="Plumbing & Sanitation Systems",
        material_standards=(
            "- ท่อน้ำดื่มและประปา PVC ชั้นคุณภาพ 13.5 ตามมาตรฐาน มอก. 17 หรือท่อ PPR Class PN20 มอก. 2135 / DIN 8077\n"
            "- ท่อโสโครกและท่อน้ำทิ้ง PVC ชั้นคุณภาพ 8.5 มอก. 17\n"
            "- วาล์วน้ำทองเหลือง/สแตนเลส มาตรฐาน มอก. 389 หรือ BS 5154"
        ),
        material_standards_en=(
            "- Potable water supply pipes: PVC Class 13.5 per TIS 17 or PPR PN20 per TIS 2135 / DIN 8077\n"
            "- Soil, waste, and vent pipes: PVC Class 8.5 per TIS 17\n"
            "- Brass or stainless steel valves conforming to TIS 389 or BS 5154"
        ),
        workmanship_requirements=(
            "- การต่อท่อและข้อต่อ: ทาเคมีประสานท่อตามมาตรฐานผู้ผลิต ท่อ PPR เชื่อมหลอมด้วยความร้อนเป็นเนื้อเดียวกัน\n"
            "- การสโลปทางเดินท่อ (Pipe Slope): ท่อน้ำทิ้งและท่อโสโครกต้องมีความลาดเอียงไม่น้อยกว่า 1:100 (1%) หรือ 1:50 (2%)\n"
            "- การยึดแขวนท่อ (Pipe Hangers): ติดตั้งชีแคลมป์หรือพุกยึดรับน้ำหนักท่อทุกระยะไม่เกิน 1.50 - 2.00 ม."
        ),
        workmanship_requirements_en=(
            "- Pipe jointing: Apply approved solvent cement; heat-fusion weld PPR joints homogeneously\n"
            "- Drainage slope: Maintain minimum 1:100 (1%) or 1:50 (2%) downward slope for gravity drain lines\n"
            "- Pipe support: Install clevis hangers or brackets at intervals <= 1.50 - 2.00m"
        ),
        testing_inspection=(
            "- การทดสอบอัดแรงดันน้ำ (Hydrostatic Pressure Test): อัดแรงดันน้ำไม่น้อยกว่า 10 bar (150 psi) ค้างไว้อย่างน้อย 2 ชั่วโมง โดยแรงดันไม่ตก\n"
            "- การทดสอบการไหลลื่นของท่อน้ำทิ้ง (Flow & Leakage Test) ปราศจากการอุดตันและการรั่วซึม"
        ),
        testing_inspection_en=(
            "- Hydrostatic pressure testing: Pressurize water lines to 10 bar (150 psi) for at least 2 hours without pressure drop\n"
            "- Gravity drain flow and leak test to confirm unobstructed discharge"
        ),
    ),
    "23 00 00": ThaiSpecClause(
        masterformat_code="23 00 00",
        masterformat_title="Heating, Ventilating, and Air Conditioning - HVAC (งานระบบปรับอากาศและระบายอากาศ)",
        masterformat_title_en="HVAC & Mechanical Systems",
        material_standards=(
            "- ท่อลมระบายอากาศ แผ่นเหล็กอาบสังกะสี (Galvanized Steel Sheet) มอก. 50 / ASTM A653 ความหนาตามมาตรฐาน SMACNA\n"
            "- ฉนวนกันความร้อนท่อลม แผ่นยางอีลาสโตเมอร์ชนิดเซลล์ปิด (Closed-cell Elastomeric) มอก. 2652 / ASTM C534\n"
            "- หน้ากากแอร์และแดมเปอร์ (Diffusers, Dampers) ทำจากอลูมิเนียมอบสี พาวเดอร์โค้ท"
        ),
        material_standards_en=(
            "- Galvanized steel duct sheet complying with TIS 50 / ASTM A653; sheet gauges per SMACNA\n"
            "- Closed-cell elastomeric thermal insulation complying with TIS 2652 / ASTM C534\n"
            "- Powder-coated aluminum air diffusers, grilles, and volume dampers"
        ),
        workmanship_requirements=(
            "- การประกอบท่อลม: เข้าขอบท่อลมตามมาตรฐาน SMACNA ซีลรอยต่อด้วยดักท์ซีลแลนท์กันการรั่วซึมของลม\n"
            "- การหุ้มฉนวนท่อลม: หุ้มฉนวนแน่นสนิท รอยต่อฉนวนทาติดกาวและปิดทับด้วยเทปฟอยล์อลูมิเนียมกันไอน้ำควบแน่น"
        ),
        workmanship_requirements_en=(
            "- Duct fabrication: Assemble lock seams per SMACNA standards and seal all joints with mastic sealant\n"
            "- Insulation wrapping: Fit insulation snugly with glued butt joints sealed with aluminum foil tape"
        ),
        testing_inspection=(
            "- การทดสอบการรั่วไหลของท่อลม (Duct Leakage Test) ตามมาตรฐาน SMACNA HVAC Air Duct Leakage Test Manual\n"
            "- การปรับปริมาณลมและวัดความเร็วลม (Air Balancing & CFM Test) ตรงตามแบบวิศวกรรม"
        ),
        testing_inspection_en=(
            "- Duct leakage testing per SMACNA HVAC Air Duct Leakage Test Manual\n"
            "- Air balancing, airflow rate (CFM), and velocity testing using calibrated anemometers"
        ),
    ),
    "26 05 00": ThaiSpecClause(
        masterformat_code="26 05 00",
        masterformat_title="Common Work Results for Electrical (งานระบบไฟฟ้าและสื่อสาร)",
        masterformat_title_en="Electrical & Communication Systems",
        material_standards=(
            "- สายไฟฟ้าทองแดงหุ้มฉนวน PVC / XLPE มาตรฐาน มอก. 11-2553 หรือ IEC 60227 / IEC 60502\n"
            "- ท่อร้อยสายไฟฟ้า เหล็กกล้าอบสังกะสี EMT / IMC / RSC มอก. 770 หรือ ANSI C80.1 หรือท่อ UPVC เหลือง มอก. 216\n"
            "- ตู้เมนสวิตช์ MDB และตู้โหลดเซ็นเตอร์ มาตรฐาน IEC 61439 / มอก. 1436"
        ),
        material_standards_en=(
            "- Copper electrical wires with PVC/XLPE insulation conforming to TIS 11-2553 or IEC 60227 / IEC 60502\n"
            "- Galvanized steel conduits EMT / IMC / RSC per TIS 770 or ANSI C80.1, or yellow UPVC per TIS 216\n"
            "- Main Distribution Boards (MDB) and load centers complying with IEC 61439 / TIS 1436"
        ),
        workmanship_requirements=(
            "- การร้อยสายและการเข้าหัวสาย: ไม่ขูดขีดฉนวนสายไฟ การเข้าหัวสายใช้หางปลาบีบอัดแน่นหนา ยึดเทอร์มินัลสกรูกำหนดแรงบิดถูกต้อง\n"
            "- การต่อลงดิน (Grounding System): ต่อสายดินหลักเข้ากับหลักดินสแตนเลส/ทองแดงความยาวไม่น้อยกว่า 2.40 ม. ค่าความต้านทานดินไม่เกิน 5 โอห์ม"
        ),
        workmanship_requirements_en=(
            "- Wire pulling and termination: Protect wire jackets; terminate conductors using compression lugs torque-tightened to specification\n"
            "- Grounding system: Connect main ground conductor to copper ground rod (length >= 2.40m); earth resistance <= 5 ohms"
        ),
        testing_inspection=(
            "- การทดสอบความต้านทานฉนวนสายไฟ (Insulation Resistance Test / Megger Test) ไม่น้อยกว่า 1 Megaohm ที่ 500V DC\n"
            "- การทดสอบความต้านทานหลักดิน (Earth Ground Resistance Test) ไม่เกิน 5 โอห์ม"
        ),
        testing_inspection_en=(
            "- Insulation resistance Megger testing (>= 1 MΩ at 500V DC)\n"
            "- Earth ground resistance testing (<= 5 ohms threshold)"
        ),
    ),
    "31 20 00": ThaiSpecClause(
        masterformat_code="31 20 00",
        masterformat_title="Earth Moving & Earthworks (งานดินขุด ถม และปรับระดับ)",
        masterformat_title_en="Earthworks & Grading",
        material_standards=(
            "- วัสดุดินถม ดินลูกรัง หรือทรายถม ปราศจากเศษขยะ วัสดุย่อยสลายได้ หรือสารปนเปื้อน\n"
            "- แผ่นใยสังเคราะห์กั้นดิน (Geotextile) ASTM D4751 / D4632"
        ),
        material_standards_en=(
            "- Approved soil, lateral soil, or sand fill free from organic matter and debris\n"
            "- Woven or non-woven geotextile fabrics complying with ASTM D4751 / D4632"
        ),
        workmanship_requirements=(
            "- งานขุดดิน (Excavation): ขุดตามขนาดและระดับที่กำหนด ทำลาดเอียงป้องกันดินถล่ม หรือติดตั้งระบบ Sheet Pile กันดินเคลื่อนตัว\n"
            "- งานถมดินและบดอัด (Backfilling & Compaction): ถมเป็นชั้นๆ หนาชั้นละไม่เกิน 0.20 - 0.30 ม. บดอัดความแน่นไม่น้อยกว่า 95% Modified Proctor Density"
        ),
        workmanship_requirements_en=(
            "- Excavation: Excavate to specified invert levels; slope cut banks or install shoring to prevent cave-in\n"
            "- Backfilling and compaction: Place fill in lifts not exceeding 0.20 - 0.30m; compact to >= 95% Modified Proctor Density"
        ),
        testing_inspection=(
            "- การทดสอบความแน่นของดินในสนาม (Field Density Test) ตามมาตรฐาน ASTM D1556 (Sand Cone Method)\n"
            "- ตรวจสอบระดับดินขุด-ถมด้วยกล้องสำรวจ"
        ),
        testing_inspection_en=(
            "- Field density compaction testing via sand-cone method per ASTM D1556\n"
            "- Topographic optical survey level inspection"
        ),
    ),
    "34 11 00": ThaiSpecClause(
        masterformat_code="34 11 00",
        masterformat_title="Rail Tracks & Railways (งานระบบทางรถไฟและส่วนประกอบ)",
        masterformat_title_en="Railway Track Systems",
        material_standards=(
            "- เหล็กรางรถไฟ Standard Rail UIC60 / 50E1 หรือ BS11 ตามมาตรฐาน AREMA / EN 13674-1\n"
            "- หมอนรองรถไฟคอนกรีตอัดแรง (Prestressed Concrete Sleeper) EN 13230 / AREMA\n"
            "- หินโรยทาง (Railway Ballast) หินย่อยแกรนิตแข็งแกร่ง ตามมาตรฐาน AREMA Class 4"
        ),
        material_standards_en=(
            "- Steel rail sections UIC60 / 50E1 or BS11 complying with AREMA / EN 13674-1\n"
            "- Prestressed concrete sleepers conforming to EN 13230 / AREMA\n"
            "- Granite ballast aggregate complying with AREMA Class 4 requirements"
        ),
        workmanship_requirements=(
            "- การวางหมอนและการยึดราง: ระยะห่างหมอน 0.60 ม. ยึดด้วยระบบ Elastic Rail Fastening System\n"
            "- การวางหินโรยทางและอัดหิน (Tamping Work): บดอัดหินโรยทางใต้หมอนให้ได้ค่าโปรไฟล์เกจและความสูงถูกต้องตามเกณฑ์ทางวิศวกรรม"
        ),
        workmanship_requirements_en=(
            "- Sleeper spacing at 0.60m intervals; secure rails using elastic rail fastening systems\n"
            "- Ballast tamping: Tamp granite ballast under sleepers to achieve specified gauge and elevation profile"
        ),
        testing_inspection=(
            "- ตรวจสอบระยะความกว้างทางรถไฟ (Track Gauge Alignment Inspection) พลาดได้ไม่เกิน ±2 มม.\n"
            "- ตรวจสอบรอยเชื่อมราง Thermite / Flash Butt Welding ด้วยระบบ NDT Ultrasonic Test"
        ),
        testing_inspection_en=(
            "- Track gauge laser survey alignment inspection (tolerance <= ±2 mm)\n"
            "- Thermite and flash-butt rail weld non-destructive ultrasonic testing (NDT)"
        ),
    ),
}

# Mapping from IFC Class name to CSI MasterFormat Division Code
ENTITY_MASTERFORMAT_MAP: Dict[str, str] = {
    # Structure (03 30 00 & 05 12 00)
    "IfcColumn": "03 30 00",
    "IfcColumnStandardCase": "03 30 00",
    "IfcBeam": "03 30 00",
    "IfcBeamStandardCase": "03 30 00",
    "IfcFooting": "03 30 00",
    "IfcPile": "03 30 00",
    "IfcSlab": "03 30 00",
    "IfcSlabStandardCase": "03 30 00",
    "IfcSlabElementedCase": "03 30 00",
    "IfcStair": "03 30 00",
    "IfcStairFlight": "03 30 00",
    "IfcRamp": "03 30 00",
    "IfcRampFlight": "03 30 00",
    "IfcReinforcingBar": "03 30 00",
    "IfcReinforcingElement": "03 30 00",
    "IfcReinforcingMesh": "03 30 00",
    "IfcTendon": "03 30 00",
    "IfcTendonAnchor": "03 30 00",
    "IfcVibrationIsolator": "03 30 00",
    "IfcMember": "05 12 00",
    "IfcMemberStandardCase": "05 12 00",
    "IfcPlate": "05 12 00",
    "IfcPlateStandardCase": "05 12 00",
    "IfcRailing": "05 12 00",
    "IfcFastener": "05 12 00",
    "IfcMechanicalFastener": "05 12 00",
    "IfcDiscreteAccessory": "05 12 00",

    # Architecture (04 20 00, 08 10 00, 12 00 00)
    "IfcWall": "04 20 00",
    "IfcWallStandardCase": "04 20 00",
    "IfcWallElementedCase": "04 20 00",
    "IfcCovering": "04 20 00",
    "IfcChimney": "04 20 00",
    "IfcDoor": "08 10 00",
    "IfcDoorStandardCase": "08 10 00",
    "IfcWindow": "08 10 00",
    "IfcWindowStandardCase": "08 10 00",
    "IfcRoof": "08 10 00",
    "IfcCurtainWall": "08 10 00",
    "IfcShadingDevice": "08 10 00",
    "IfcFurniture": "12 00 00",
    "IfcFurnishingElement": "12 00 00",
    "IfcSystemFurnitureElement": "12 00 00",
    "IfcBuildingElementPart": "04 20 00",
    "IfcBuildingElementProxy": "05 12 00",
    "IfcElementAssembly": "05 12 00",
    "IfcTransportElement": "05 12 00",
    "IfcVirtualElement": "04 20 00",

    # Plumbing & Water (22 11 00)
    "IfcPipeSegment": "22 11 00",
    "IfcPipeFitting": "22 11 00",
    "IfcSanitaryTerminal": "22 11 00",
    "IfcWasteTerminal": "22 11 00",
    "IfcStackTerminal": "22 11 00",
    "IfcFireSuppressionTerminal": "22 11 00",
    "IfcPump": "22 11 00",
    "IfcTank": "22 11 00",
    "IfcInterceptor": "22 11 00",
    "IfcValve": "22 11 00",
    "IfcFlowTreatmentDevice": "22 11 00",
    "IfcFlowStorageDevice": "22 11 00",

    # HVAC & Mechanical (23 00 00)
    "IfcDuctSegment": "23 00 00",
    "IfcDuctFitting": "23 00 00",
    "IfcDuctSilencer": "23 00 00",
    "IfcAirTerminal": "23 00 00",
    "IfcAirTerminalBox": "23 00 00",
    "IfcAirToAirHeatRecovery": "23 00 00",
    "IfcDamper": "23 00 00",
    "IfcFlowController": "23 00 00",
    "IfcUnitaryEquipment": "23 00 00",
    "IfcBoiler": "23 00 00",
    "IfcChiller": "23 00 00",
    "IfcBurner": "23 00 00",
    "IfcCoil": "23 00 00",
    "IfcCompressor": "23 00 00",
    "IfcCondenser": "23 00 00",
    "IfcCooledBeam": "23 00 00",
    "IfcCoolingTower": "23 00 00",
    "IfcEvaporativeCooler": "23 00 00",
    "IfcEvaporator": "23 00 00",
    "IfcFan": "23 00 00",
    "IfcFilter": "23 00 00",
    "IfcHeatExchanger": "23 00 00",
    "IfcHumidifier": "23 00 00",
    "IfcSpaceHeater": "23 00 00",
    "IfcTubeBundle": "23 00 00",
    "IfcEnergyConversionDevice": "23 00 00",
    "IfcEngine": "23 00 00",

    # Electrical & Communications (26 05 00)
    "IfcCableCarrierSegment": "26 05 00",
    "IfcCableCarrierFitting": "26 05 00",
    "IfcCableSegment": "26 05 00",
    "IfcCableFitting": "26 05 00",
    "IfcDistributionBoard": "26 05 00",
    "IfcElectricDistributionBoard": "26 05 00",
    "IfcLightFixture": "26 05 00",
    "IfcLamp": "26 05 00",
    "IfcSwitchingDevice": "26 05 00",
    "IfcOutlet": "26 05 00",
    "IfcJunctionBox": "26 05 00",
    "IfcElectricAppliance": "26 05 00",
    "IfcElectricGenerator": "26 05 00",
    "IfcElectricMotor": "26 05 00",
    "IfcElectricTimeControl": "26 05 00",
    "IfcElectricFlowStorageDevice": "26 05 00",
    "IfcMotorConnection": "26 05 00",
    "IfcProtectiveDevice": "26 05 00",
    "IfcProtectiveDeviceTrippingUnit": "26 05 00",
    "IfcSolarDevice": "26 05 00",
    "IfcTransformer": "26 05 00",
    "IfcActuator": "26 05 00",
    "IfcAlarm": "26 05 00",
    "IfcAudioVisualAppliance": "26 05 00",
    "IfcCommunicationsAppliance": "26 05 00",
    "IfcController": "26 05 00",
    "IfcDistributionControlElement": "26 05 00",
    "IfcDistributionElement": "26 05 00",
    "IfcDistributionFlowElement": "26 05 00",
    "IfcDistributionChamberElement": "26 05 00",
    "IfcFlowInstrument": "26 05 00",
    "IfcFlowMeter": "26 05 00",
    "IfcFlowMovingDevice": "26 05 00",
    "IfcFlowSegment": "26 05 00",
    "IfcFlowFitting": "26 05 00",
    "IfcFlowTerminal": "26 05 00",
    "IfcMedicalDevice": "26 05 00",
    "IfcSensor": "26 05 00",
    "IfcUnitaryControlElement": "26 05 00",

    # Civil & Infrastructure (31 20 00 & 34 11 00)
    "IfcAlignment": "31 20 00",
    "IfcRoad": "31 20 00",
    "IfcBridge": "03 30 00",
    "IfcEarthworksElement": "31 20 00",
    "IfcEarthworksCut": "31 20 00",
    "IfcEarthworksFill": "31 20 00",
    "IfcGeotechnicalStratum": "31 20 00",
    "IfcSoil": "31 20 00",
    "IfcRetainingWall": "03 30 00",
    "IfcCivilElement": "31 20 00",
    "IfcGeographicElement": "31 20 00",
    "IfcRailway": "34 11 00",
    "IfcRailwayPart": "34 11 00",
    "IfcTrackElement": "34 11 00",

    # Custom
    "IfcCustomElement": "03 30 00",
}


def get_masterformat_code(class_name: str) -> str:
    """Get CSI MasterFormat division code for an entity class name."""
    clean_cls = class_name.strip()
    return ENTITY_MASTERFORMAT_MAP.get(clean_cls, "03 30 00")


def get_thai_spec_clause(class_name_or_code: str) -> ThaiSpecClause:
    """
    Retrieve ThaiSpecClause by IFC entity class name OR MasterFormat code.
    Falls back to Cast-in-Place Concrete (03 30 00) if not explicitly found.
    """
    target = class_name_or_code.strip()
    if target in THAI_SPEC_LIBRARY:
        return THAI_SPEC_LIBRARY[target]

    code = get_masterformat_code(target)
    return THAI_SPEC_LIBRARY.get(code, THAI_SPEC_LIBRARY["03 30 00"])
