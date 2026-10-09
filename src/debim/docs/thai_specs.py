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
    material_standards: str
    workmanship_requirements: str
    testing_inspection: str

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
        material_standards=(
            "- ปูนซีเมนต์ปอร์ตแลนด์ประเภท 1 ตามมาตรฐาน มอก. 15 เล่ม 1 หรือ ASTM C150 Type I\n"
            "- คอนกรีตผสมเสร็จ ต้องมีกำลังอัดทรงกระบอกไม่น้อยกว่า 240 - 350 ksc ที่อายุ 28 วัน (มอก. 2137 / ASTM C94)\n"
            "- เหล็กเส้นเสริมคอนกรีต เหล็กเส้นกลม SR24 (มอก. 20) และเหล็กข้ออ้อย SD40 / SD50 (มอก. 24)\n"
            "- น้ำผสมคอนกรีต สะอาด ปราศจากกรด ด่าง น้ำมัน และสารเคมีที่เป็นอันตราย"
        ),
        workmanship_requirements=(
            "- การตั้งและประกอบแบบหล่อ (Formwork): แบบหล่อต้องแข็งแรง ไม่คดงอ ค้ำยันมั่นคง กันน้ำปูนรั่วซึมได้\n"
            "- ระยะทาบเหล็กเสริม (Lap Splicing): ระยะทาบต้องไม่น้อยกว่า 40 เท่าของเส้นผ่านศูนย์กลางเหล็ก (40d) หรือตามรายการคำนวณวิศวกร\n"
            "- การเทและจุ่มจีบหล่อคอนกรีต: จุ่มเครื่องสั่นคอนกรีต (Vibrator) อย่างถูกวิธี ป้องกันการแยกตัวของมอร์ต้าร์และเกสรหิน\n"
            "- การบ่มคอนกรีต (Concrete Curing): บ่มชื้นต่อเนื่องอย่างน้อย 7 วัน โดยการรดน้ำ บ่มด้วยกระสอบป่านชื้น หรือพ่นสารเคมีบ่มคอนกรีต"
        ),
        testing_inspection=(
            "- การทดสอบการยุบตัวของคอนกรีต (Slump Test) ตามมาตรฐาน ASTM C143 / มอก. 917 ค่ายุบตัว 7.5 - 12.5 ซม.\n"
            "- การเก็บตัวอย่างทดสอบกำลังอัด (Compressive Strength Test) หล่อลูกปูนทรงกระบอก (15x30 ซม.) หรือลูกกูบ (15x15x15 ซม.) ทุกๆ 50 ลบ.ม.\n"
            "- ตรวจสอบระยะคอนกรีตหุ้มเหล็ก (Concrete Covering) และความสะอาดภายในแบบหล่อก่อนการเทคอนกรีต"
        ),
    ),
    "04 20 00": ThaiSpecClause(
        masterformat_code="04 20 00",
        masterformat_title="Unit Masonry (งานผนังก่ออิฐและบล็อก)",
        material_standards=(
            "- อิฐมอญก่อผนัง คุณภาพมาตรฐาน มอก. 77\n"
            "- อิฐมวลเบา (Autoclaved Aerated Concrete - AAC) มอก. 1505 ชนิด G2 หรือ G4\n"
            "- ปูนปลาสเตอร์ก่อและฉาบสำเร็จรูป มอก. 1776 หรือ ASTM C270\n"
            "- ตะแกรงกรงไก่ และเหล็กหนวดกุ้ง (Wall Ties) Ø 6มม. ชุบสังกะสีกันสนิม"
        ),
        workmanship_requirements=(
            "- การก่ออิฐ: รดน้ำอิฐมอญให้อิ่มตัวก่อนก่อ เสียบเหล็กหนวดกุ้งยึดเสา-ผนังทุกระยะสูงไม่เกิน 0.40 ม. ยื่นเข้าผนังไม่น้อยกว่า 0.50 ม.\n"
            "- เสาเอ็นและทับหลัง (Lintel & Tie Beams): จัดทำเสาเอ็น ค.ส.ล. ทุกช่องเปิดประตู-หน้าต่าง และผนังก่อกว้างเกิน 2.50 ม. หรือสูงเกิน 3.00 ม.\n"
            "- งานฉาบปูน: จับเซี้ยมจับปุ่มได้ระดับดิ่งปราบ ติดตะแกรงกรงไก่บริเวณรอยต่อโครงสร้างและมุมช่องเปิด ป้องกันรอยแตกร้าว"
        ),
        testing_inspection=(
            "- ตรวจสอบความได้ดิ่ง ได้ระดับ และแนวระนาบของผนัง (Tolerance ไม่เกิน 3 มม. ต่อระยะ 2.00 ม.)\n"
            "- ตรวจสอบการยึดเกาะแน่นของปูนฉาบ ปราศจากเสียงโพรง (Hollow sound) และรอยแตกร้าวลายงา (Hairline cracks)"
        ),
    ),
    "05 12 00": ThaiSpecClause(
        masterformat_code="05 12 00",
        masterformat_title="Structural Steel Framing (งานโครงสร้างเหล็กรูปพรรณ)",
        material_standards=(
            "- เหล็กโครงสร้างรูปพรรณรีดร้อน มอก. 1227 ชนิดเกรด SS400 หรือ SM490\n"
            "- เหล็กโครงสร้างรูปพรรณขึ้นรูปเย็น มอก. 107 / มอก. 1228\n"
            "- น็อตและสลักเกลียวยึดโครงสร้าง High Strength Bolts ASTM A325 หรือ A490\n"
            "- สีรองพื้นกันสนิมอะคริลิกเรซิน หรืออีพ็อกซี่เรซิน มาตรฐาน มอก. 2387"
        ),
        workmanship_requirements=(
            "- การตัดและการเตรียมขอบเหล็ก: ตัดด้วยเครื่องจักรเรียบตรง ลบคมเสี้ยนรอยตัด\n"
            "- งานเชื่อม (Welding Workmanship): ช่างเชื่อมต้องผ่านการรับรอง (Certified Welder) ตามมาตรฐาน AWS D1.1 แนวเชื่อมสมบูรณ์ ปราศจากรอยร้าว\n"
            "- การทำความสะอาดผิวเหล็กและการทาสี: พ่นทำความสะอาดผิวเหล็กระดับ Sa 2.5 (ISO 8501-1) ทาสีรองพื้นกันสนิมความหนาฟิล์มแห้งไม่น้อยกว่า 80 ไมครอน"
        ),
        testing_inspection=(
            "- การตรวจสอบรอยเชื่อมด้วยสายตา (Visual Testing - VT) และการทดสอบแบบไม่ทำลาย (NDT: Ultrasonic / Radiography Test)\n"
            "- ตรวจสอบค่าแรงบิดสลักเกลียว (Torque Wrench Inspection) ตามมาตรฐาน AISC\n"
            "- ตรวจสอบความหนาฟิล์มสี (Dry Film Thickness - DFT) ด้วยเครื่องวัดความหนาฟิล์มสี"
        ),
    ),
    "08 10 00": ThaiSpecClause(
        masterformat_code="08 10 00",
        masterformat_title="Doors and Windows (งานประตู หน้าต่าง และกระจก)",
        material_standards=(
            "- กรอบบานอลูมิเนียมอบสีพาวเดอร์โค้ท (Powder Coated Aluminum) มอก. 218 / ASTM B221 ความหนาไม่น้อยกว่า 1.5 - 2.0 มม.\n"
            "- กระจกอินซูเลท / กระจกเทมเปอร์ / กระจกลามิเนต มอก. 965 / ASTM C1048\n"
            "- อุปกรณ์ฟิตติ้งและกุญแจยึดมาตรฐาน stainless steel 304"
        ),
        workmanship_requirements=(
            "- การติดตั้งกรอบประตูหน้าต่าง: ติดตั้งในแนวระดับและได้ดิ่ง ยึดพุกพลาสติก/พุกเหล็กแน่นหนาทุกระยะไม่เกิน 0.60 ม.\n"
            "- การยิงซิลิโคนซีลแลนท์: ยิงโพลียูรีเทนหรือซิลิโคนกันน้ำรอบขอบกรอบภายนอกและภายในเต็มร่อง เรียบสม่ำเสมอ"
        ),
        testing_inspection=(
            "- ทดสอบการรั่วซึมของน้ำ (Water Leakage Test) โดยการพ่นน้ำแรงดันสูงตามมาตรฐาน AAMA 501.2\n"
            "- ตรวจสอบการเปิด-ปิดราบรื่น ไม่ติดขัด และระบบล็อกทำงานสมบูรณ์"
        ),
    ),
    "22 11 00": ThaiSpecClause(
        masterformat_code="22 11 00",
        masterformat_title="Facility Water Distribution & Plumbing (งานระบบสุขาภิบาลและประปา)",
        material_standards=(
            "- ท่อน้ำดื่มและประปา PVC ชั้นคุณภาพ 13.5 ตามมาตรฐาน มอก. 17 หรือท่อ PPR Class PN20 มอก. 2135 / DIN 8077\n"
            "- ท่อโสโครกและท่อน้ำทิ้ง PVC ชั้นคุณภาพ 8.5 มอก. 17\n"
            "- วาล์วน้ำทองเหลือง/สแตนเลส มาตรฐาน มอก. 389 หรือ BS 5154"
        ),
        workmanship_requirements=(
            "- การต่อท่อและข้อต่อ: ทาเคมีประสานท่อตามมาตรฐานผู้ผลิต ท่อ PPR เชื่อมหลอมด้วยความร้อนเป็เนื้อเดียวกัน\n"
            "- การสโลปทางเดินท่อ (Pipe Slope): ท่อน้ำทิ้งและท่อโสโครกต้องมีความลาดเอียงไม่น้อยกว่า 1:100 (1%) หรือ 1:50 (2%)\n"
            "- การยึดแขวนท่อ (Pipe Hangers): ติดตั้งชีแคลมป์หรือพุกยึดรับน้ำหนักท่อทุกระยะไม่เกิน 1.50 - 2.00 ม."
        ),
        testing_inspection=(
            "- การทดสอบอัดแรงดันน้ำ (Hydrostatic Pressure Test): อัดแรงดันน้ำไม่น้อยกว่า 10 bar (150 psi) ค้างไว้อย่างน้อย 2 ชั่วโมง โดยแรงดันไม่ตก\n"
            "- การทดสอบการไหลลื่นของท่อน้ำทิ้ง (Flow & Leakage Test) ปราศจากการอุดตันและการรั่วซึม"
        ),
    ),
    "23 00 00": ThaiSpecClause(
        masterformat_code="23 00 00",
        masterformat_title="Heating, Ventilating, and Air Conditioning - HVAC (งานระบบปรับอากาศและระบายอากาศ)",
        material_standards=(
            "- ท่อลมระบายอากาศ แผ่นเหล็กอาบสังกะสี (Galvanized Steel Sheet) มอก. 50 / ASTM A653 ความหนาตามมาตรฐาน SMACNA\n"
            "- ฉนวนกันความร้อนท่อลม แผ่นยางอีลาสโตเมอร์ชนิดเซลล์ปิด (Closed-cell Elastomeric) มอก. 2652 / ASTM C534\n"
            "- หน้ากากแอร์และแดมเปอร์ (Diffusers, Dampers) ทำจากอลูมิเนียมอบสี พาวเดอร์โค้ท"
        ),
        workmanship_requirements=(
            "- การประกอบท่อลม: เข้าขอบท่อลมตามมาตรฐาน SMACNA ซีลรอยต่อด้วยดักท์ซีลแลนท์กันการรั่วซึมของลม\n"
            "- การหุ้มฉนวนท่อลม: หุ้มฉนวนแน่นสนิท รอยต่อฉนวนทาติดกาวและปิดทับด้วยเทปฟอยล์อลูมิเนียมกันไอน้ำควบแน่น"
        ),
        testing_inspection=(
            "- การทดสอบการรั่วไหลของท่อลม (Duct Leakage Test) ตามมาตรฐาน SMACNA HVAC Air Duct Leakage Test Manual\n"
            "- การปรับปริมาณลมและวัดความเร็วลม (Air Balancing & CFM Test) ตรงตามแบบวิศวกรรม"
        ),
    ),
    "26 05 00": ThaiSpecClause(
        masterformat_code="26 05 00",
        masterformat_title="Common Work Results for Electrical (งานระบบไฟฟ้าและสื่อสาร)",
        material_standards=(
            "- สายไฟฟ้าทองแดงหุ้มฉนวน PVC / XLPE มาตรฐาน มอก. 11-2553 หรือ IEC 60227 / IEC 60502\n"
            "- ท่อร้อยสายไฟฟ้า เหล็กกล้าอบสังกะสี EMT / IMC / RSC มอก. 770 หรือ ANSI C80.1 หรือท่อ UPVC เหลือง มอก. 216\n"
            "- ตู้เมนสวิตช์ MDB และตู้โหลดเซ็นเตอร์ มาตรฐาน IEC 61439 / มอก. 1436"
        ),
        workmanship_requirements=(
            "- การร้อยสายและการเข้าหัวสาย: ไม่ขูดขีดฉนวนสายไฟ การเข้าหัวสายใช้หางปลาบีบอัดแน่นหนา ยึดเทอร์มินัลสกรูกำหนดแรงบิดถูกต้อง\n"
            "- การต่อลงดิน (Grounding System): ต่อสายดินหลักเข้ากับหลักดินสแตนเลส/ทองแดงความยาวไม่น้อยกว่า 2.40 ม. ค่าความต้านทานดินไม่เกิน 5 โอห์ม"
        ),
        testing_inspection=(
            "- การทดสอบความต้านทานฉนวนสายไฟ (Insulation Resistance Test / Megger Test) ไม่น้อยกว่า 1 Megaohm ที่ 500V DC\n"
            "- การทดสอบความต้านทานหลักดิน (Earth Ground Resistance Test) ไม่เกิน 5 โอห์ม"
        ),
    ),
    "31 20 00": ThaiSpecClause(
        masterformat_code="31 20 00",
        masterformat_title="Earth Moving & Earthworks (งานดินขุด ถม และปรับระดับ)",
        material_standards=(
            "- วัสดุดินถม ดินลูกรัง หรือทรายถม ปราศจากเศษขยะ วัสดุย่อยสลายได้ หรือสารปนเปื้อน\n"
            "- แผ่นใยสังเคราะห์กั้นดิน (Geotextile) ASTM D4751 / D4632"
        ),
        workmanship_requirements=(
            "- งานขุดดิน (Excavation): ขุดตามขนาดและระดับที่กำหนด ทำลาดเอียงป้องกันดินถล่ม หรือติดตั้งระบบ Sheet Pile กันดินเคลื่อนตัว\n"
            "- งานถมดินและบดอัด (Backfilling & Compaction): ถมเป็นชั้นๆ หนาชั้นละไม่เกิน 0.20 - 0.30 ม. บดอัดความแน่นไม่น้อยกว่า 95% Modified Proctor Density"
        ),
        testing_inspection=(
            "- การทดสอบความแน่นของดินในสนาม (Field Density Test) ตามมาตรฐาน ASTM D1556 (Sand Cone Method)\n"
            "- ตรวจสอบระดับดินขุด-ถมด้วยกล้องสำรวจ"
        ),
    ),
    "34 11 00": ThaiSpecClause(
        masterformat_code="34 11 00",
        masterformat_title="Rail Tracks & Railways (งานระบบทางรถไฟและส่วนประกอบ)",
        material_standards=(
            "- เหล็กรางรถไฟ Standard Rail UIC60 / 50E1 หรือ BS11 ตามมาตรฐาน AREMA / EN 13674-1\n"
            "- หมอนรองรถไฟคอนกรีตอัดแรง (Prestressed Concrete Sleeper) EN 13230 / AREMA\n"
            "- หินโรยทาง (Railway Ballast) หินย่อยแกรนิตแข็งแกร่ง ตามมาตรฐาน AREMA Class 4"
        ),
        workmanship_requirements=(
            "- การวางหมอนและการยึดราง: ระยะห่างหมอน 0.60 ม. ยึดด้วยระบบ Elastic Rail Fastening System\n"
            "- การวางหินโรยทางและอัดหิน (Tamping Work): บดอัดหินโรยทางใต้หมอนให้ได้ค่าโปรไฟล์เกจและความสูงถูกต้องตามเกณฑ์ทางวิศวกรรม"
        ),
        testing_inspection=(
            "- ตรวจสอบระยะความกว้างทางรถไฟ (Track Gauge Alignment Inspection) พลาดได้ไม่เกิน ±2 มม.\n"
            "- ตรวจสอบรอยเชื่อมราง Thermite / Flash Butt Welding ด้วยระบบ NDT Ultrasonic Test"
        ),
    ),
}

# Mapping from IFC Class name to CSI MasterFormat Division Code
ENTITY_MASTERFORMAT_MAP: Dict[str, str] = {
    "IfcColumn": "03 30 00",
    "IfcBeam": "03 30 00",
    "IfcFooting": "03 30 00",
    "IfcSlab": "03 30 00",
    "IfcStair": "03 30 00",
    "IfcStairFlight": "03 30 00",
    "IfcRamp": "03 30 00",
    "IfcWall": "04 20 00",
    "IfcRailing": "05 12 00",
    "IfcPlate": "05 12 00",
    "IfcCurtainWall": "08 10 00",
    "IfcDoor": "08 10 00",
    "IfcWindow": "08 10 00",
    "IfcCovering": "04 20 00",
    "IfcRoof": "08 10 00",
    "IfcPipeSegment": "22 11 00",
    "IfcSanitaryTerminal": "22 11 00",
    "IfcWasteTerminal": "22 11 00",
    "IfcDuctSegment": "23 00 00",
    "IfcAirTerminal": "23 00 00",
    "IfcDamper": "23 00 00",
    "IfcFlowController": "23 00 00",
    "IfcUnitaryEquipment": "23 00 00",
    "IfcCableCarrierSegment": "26 05 00",
    "IfcDistributionBoard": "26 05 00",
    "IfcElectricDistributionBoard": "26 05 00",
    "IfcLightFixture": "26 05 00",
    "IfcSwitchingDevice": "26 05 00",
    "IfcOutlet": "26 05 00",
    "IfcEarthworksElement": "31 20 00",
    "IfcEarthworksCut": "31 20 00",
    "IfcEarthworksFill": "31 20 00",
    "IfcGeotechnicalStratum": "31 20 00",
    "IfcSoil": "31 20 00",
    "IfcRetainingWall": "03 30 00",
    "IfcAlignment": "31 20 00",
    "IfcRoad": "31 20 00",
    "IfcBridge": "03 30 00",
    "IfcRailway": "34 11 00",
    "IfcRailwayPart": "34 11 00",
    "IfcTrackElement": "34 11 00",
    "IfcCustomElement": "03 30 00",
    "IfcBuildingElementProxy": "05 12 00",
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
