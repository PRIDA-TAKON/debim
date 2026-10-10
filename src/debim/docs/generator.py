"""
Interactive Class Directory & Encyclopedia Generator for debim.
Compiles 6-dimensional interactive webpage for BIM element classes across Structure, Architecture, MEP, and Civil.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

DEFAULT_CLASS_DIRECTORY_DATA: List[Dict[str, Any]] = [
    # --- STRUCTURE ---
    {
        "id": "IfcColumn",
        "class_name": "IfcColumn",
        "name_th": "เสาคอนกรีตเสริมเหล็ก / เสาเหล็ก (Structural Column)",
        "discipline": "Structure",
        "schema_version": "IFC4",
        "description": "องค์อาคารรับแรงอัดแนวแกนและแรงดัด (Structural Column) รองรับน้ำหนักบรรทุกจากคานและพื้น ถ่ายลงสู่ฐานราก",
        "predefined_types": ["COLUMN", "USERDEFINED", "NOTDEFINED"],
        "bsdd_psets": ["Pset_ColumnCommon", "Pset_ConcreteElementGeneral"],
        "debim_yaml": """- tag: C1
  class: IfcColumn
  storey: STOREY_1
  material: MAT_CONC_280
  profile:
    shape: RECTANGULAR
    width: 0.30
    depth: 0.30
  placement:
    grid: A-1
    offset_base: 0.0
    height: 3.50
  reinforcement:
    main: 4-DB20
    stirrups: RB6@0.15""",
        "ifc_step": """#101=IFCCOLUMN('2bV1$aXq1F3w0Z2k4L5mN6',#102,'C1','Main Column',$,#103,#104,$,.COLUMN.);
#103=IFCLOCALPLACEMENT($,#105);
#104=IFCPRODUCTDEFINITIONSHAPE($,$,(#106));
#106=IFCSHAPEREPRESENTATION(#107,'Body','SweptSolid',(#108));
#108=IFCEXTRUDEDAREASOLID(#109,#110,#111,3.5);
#109=IFCRECTANGLEPROFILEDEF(.AREA.,'C30x30',$,0.3,0.3);
#120=IFCREINFORCINGBAR('2cV2$bYr2G4w0Z2k4L5mN7',#102,'C1-MAIN','4-DB20 Main Bars',$,#103,$,$,.MAIN.,20.,$,3.5,$,$);
#121=IFCREINFORCINGBAR('2dW3$cZs3H5x1A3l5M6nO8',#102,'C1-TIE','RB6@0.15 Stirrups',$,#103,$,$,.RING.,6.,$,1.1,$,$);""",
        "qto_boq": [
            {
                "code": "CONC-C30",
                "name": "คอนกรีตเสา 280 ksc C30/37",
                "formula": "Width × Depth × Height = 0.30 × 0.30 × 3.50",
                "unit": "m3",
                "quantity": 0.315,
                "mat_rate": 2400.0,
                "labor_rate": 450.0,
            },
            {
                "code": "FORM-COL",
                "name": "ไม้แบบเสาคอนกรีต (Formwork)",
                "formula": "2 × (Width + Depth) × Height = 2 × (0.3+0.3) × 3.5",
                "unit": "m2",
                "quantity": 4.20,
                "mat_rate": 320.0,
                "labor_rate": 180.0,
            },
            {
                "code": "REBAR-DB20",
                "name": "เหล็กข้ออ้อย DB20 (Main Rebar)",
                "formula": "4 × 3.5m × 2.47 kg/m × 1.15 (Lap)",
                "unit": "kg",
                "quantity": 39.77,
                "mat_rate": 32.0,
                "labor_rate": 5.0,
            },
            {
                "code": "REBAR-RB6",
                "name": "เหล็กปลอกเสา RB6 (Stirrups @0.15m)",
                "formula": "24 ปลอก × 1.10m × 0.222 kg/m",
                "unit": "kg",
                "quantity": 5.86,
                "mat_rate": 30.0,
                "labor_rate": 5.0,
            },
        ],
        "thai_specs": {
            "materials": "คอนกรีตทรงลูกบาศก์แรงอัดไม่น้อยกว่า 280 ksc ที่อายุ 28 วัน (มอก. 213-2552) เหล็กข้ออ้อยชั้นคุณภาพ SD40 (มอก. 24-2548)",
            "workmanship": "เข้าไม้แบบเสาให้ได้แนวฉิ่งระดับ ค่าคลาดเคลื่อนไม่เกิน 3 มม. ดิ่งตลอดความสูง หล่อคอนกรีตด้วยเครื่องเขย่าสารสั่น (Vibrator) อย่างทั่วถึง",
            "testing": "ทดสอบแรงอัดคอนกรีต (Cylinder/Cube Strength Test) ตามมาตรฐาน ASTM C39 และสุ่มทดสอบการรับน้ำหนัก/สแกนระยะหุ้มเหล็ก (Rebar Cover Scanner)",
        },
        "sample_3d": {
            "shape": "box",
            "width": 0.30,
            "depth": 0.30,
            "height": 3.50,
            "color": "#64748B",
            "is_reinforced_concrete": True,
            "rebar_type": "column",
        },
        "sample_2d_svg": """<svg viewBox="0 0 200 200" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="50" y="50" width="100" height="100" fill="#94a3b8" stroke="#0f172a" stroke-width="3"/><line x1="10" y1="100" x2="190" y2="100" stroke="#0284c7" stroke-width="1.5" stroke-dasharray="4,2"/><line x1="100" y1="10" x2="100" y2="190" stroke="#0284c7" stroke-width="1.5" stroke-dasharray="4,2"/><text x="105" y="40" fill="#0f172a" font-size="12" font-weight="bold">C1 (300x300mm)</text><circle x="100" y="100" r="4" fill="#0284c7"/></svg>""",
    },
    {
        "id": "IfcBeam",
        "class_name": "IfcBeam",
        "name_th": "คานคอนกรีตเสริมเหล็ก / คานเหล็ก (Structural Beam)",
        "discipline": "Structure",
        "schema_version": "IFC4",
        "description": "องค์อาคารรับแรงดัดแนวนอน (Structural Beam) รับน้ำหนักจากแผ่นพื้นและผนัง แล้วถ่ายลงสู่เสา",
        "predefined_types": ["BEAM", "JOIST", "GIRDER", "USERDEFINED"],
        "bsdd_psets": ["Pset_BeamCommon", "Pset_ConcreteElementGeneral"],
        "debim_yaml": """- tag: B1
  class: IfcBeam
  storey: STOREY_1
  material: MAT_CONC_280
  profile:
    shape: RECTANGULAR
    width: 0.20
    depth: 0.40
  placement:
    from_grid: A-1
    to_grid: A-2
    offset_z: 0.0
  reinforcement:
    main_top: 2-DB16
    main_bottom: 3-DB20
    stirrups: RB9@0.15""",
        "ifc_step": """#201=IFCBEAM('3cW2$bYr2G4x1A3l5M6nO7',#102,'B1','Floor Beam',$,#203,#204,$,.BEAM.);
#204=IFCPRODUCTDEFINITIONSHAPE($,$,(#206));
#206=IFCSHAPEREPRESENTATION(#107,'Body','SweptSolid',(#208));
#208=IFCEXTRUDEDAREASOLID(#209,#210,#211,4.0);
#209=IFCRECTANGLEPROFILEDEF(.AREA.,'B20x40',$,0.2,0.4);
#220=IFCREINFORCINGBAR('3dX3$cZs3H5y2B4m6N7oP8',#102,'B1-BOT','3-DB20 Main Bottom',$,#203,$,$,.MAIN.,20.,$,4.0,$,$);
#221=IFCREINFORCINGBAR('3eY4$dAt4I6z3C5n7O8pQ9',#102,'B1-TOP','2-DB16 Main Top',$,#203,$,$,.MAIN.,16.,$,4.0,$,$);
#222=IFCREINFORCINGBAR('3fZ5$eBu5J7a4D6o8P9qR0',#102,'B1-STIRRUP','RB9@0.15 Stirrups',$,#203,$,$,.RING.,9.,$,1.1,$,$);""",
        "qto_boq": [
            {
                "code": "CONC-C30",
                "name": "คอนกรีตคาน B1 (280 ksc)",
                "formula": "Width × Depth × Span = 0.20 × 0.40 × 4.00",
                "unit": "m3",
                "quantity": 0.320,
                "mat_rate": 2400.0,
                "labor_rate": 450.0,
            },
            {
                "code": "FORM-BEAM",
                "name": "ไม้แบบคานคอนกรีต (Side & Bottom Formwork)",
                "formula": "(2×Depth + Width) × Span = (2×0.4 + 0.2) × 4.0",
                "unit": "m2",
                "quantity": 4.00,
                "mat_rate": 320.0,
                "labor_rate": 180.0,
            },
            {
                "code": "REBAR-DB20",
                "name": "เหล็กข้ออ้อยล่าง DB20 (Main Bottom Rebar)",
                "formula": "3 เส้น × 4.0m × 2.47 kg/m × 1.15",
                "unit": "kg",
                "quantity": 34.09,
                "mat_rate": 32.0,
                "labor_rate": 5.0,
            },
            {
                "code": "REBAR-DB16",
                "name": "เหล็กข้ออ้อยบน DB16 (Main Top Rebar)",
                "formula": "2 เส้น × 4.0m × 1.58 kg/m × 1.15",
                "unit": "kg",
                "quantity": 14.54,
                "mat_rate": 32.0,
                "labor_rate": 5.0,
            },
            {
                "code": "REBAR-RB9",
                "name": "เหล็กปลอกคาน RB9 (Stirrups @0.15m)",
                "formula": "27 ปลอก × 1.10m × 0.499 kg/m",
                "unit": "kg",
                "quantity": 14.82,
                "mat_rate": 30.0,
                "labor_rate": 5.0,
            },
        ],
        "thai_specs": {
            "materials": "คอนกรีตผสมเสร็จ มอก. 213 แรงอัดไม่น้อยกว่า 280 ksc เหล็กเสริม SD40/RB9 มอก. 24",
            "workmanship": "ตั้งค้ำยันและไม้แบบคานรับน้ำหนัก ค้ำยันชั่วคราวไว้อย่างน้อย 14 วันก่อนถอดแบบ",
            "testing": "เก็บตัวอย่างลูกปูนสดทดสอบแรงอัด ตรวจวัดค่าการยุบตัว (Slump Test 7.5-10 ซม.)",
        },
        "sample_3d": {
            "shape": "box",
            "width": 4.00,
            "depth": 0.20,
            "height": 0.40,
            "color": "#475569",
            "is_reinforced_concrete": True,
            "rebar_type": "beam",
        },
        "sample_2d_svg": """<svg viewBox="0 0 240 120" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="30" width="200" height="60" fill="#cbd5e1" stroke="#0f172a" stroke-width="2"/><line x1="20" y1="60" x2="220" y2="60" stroke="#0284c7" stroke-width="1" stroke-dasharray="3,3"/><text x="100" y="55" fill="#0f172a" font-size="11" font-weight="bold">B1 (200x400mm)</text></svg>""",
    },
    {
        "id": "IfcSlab",
        "class_name": "IfcSlab",
        "name_th": "แผ่นพื้นคอนกรีตเสริมเหล็ก / พื้นสำเร็จรูป (Floor Slab)",
        "discipline": "Structure",
        "schema_version": "IFC4",
        "description": "องค์อาคารแผ่นระนาบแนวนอน (Floor Slab) รับน้ำหนักบรรทุกจรและถ่ายลงสู่คานรอบข้าง",
        "predefined_types": ["FLOOR", "ROOF", "LANDING", "BASESLAB"],
        "bsdd_psets": ["Pset_SlabCommon", "Pset_ConcreteElementGeneral"],
        "debim_yaml": """- tag: S1
  class: IfcSlab
  storey: STOREY_1
  material: MAT_CONC_280
  thickness: 0.12
  polygon:
    - [0.0, 0.0]
    - [4.0, 0.0]
    - [4.0, 4.0]
    - [0.0, 4.0]
  reinforcement:
    main_bottom: DB10@0.20
    main_top: DB10@0.20""",
        "ifc_step": """#301=IFCSLAB('4dX3$cZs3H5y2B4m6N7oP8',#102,'S1','Floor Slab',$,#303,#304,$,.FLOOR.);
#304=IFCPRODUCTDEFINITIONSHAPE($,$,(#306));
#306=IFCSHAPEREPRESENTATION(#107,'Body','SweptSolid',(#308));
#308=IFCEXTRUDEDAREASOLID(#309,#310,#311,0.12);
#320=IFCREINFORCINGMESH('4eY4$dAt4I6z3C5n7O8pQ9',#102,'S1-MESH','Rebar Mesh DB10@0.20m Top/Bottom',$,#303,$,$,.USERDEFINED.,10.,10.,0.20,0.20,$,$);""",
        "qto_boq": [
            {
                "code": "CONC-SLAB",
                "name": "คอนกรีตพื้นหล่อในที่ S1 (t=12cm)",
                "formula": "Area × Thickness = 16.0 m2 × 0.12 m",
                "unit": "m3",
                "quantity": 1.92,
                "mat_rate": 2400.0,
                "labor_rate": 450.0,
            },
            {
                "code": "REBAR-DB10",
                "name": "เหล็กเสริมตะแกรงพื้น บน-ล่าง DB10@0.20m",
                "formula": "2 ชั้น × (21+21 เส้น × 4m) × 0.617 kg/m",
                "unit": "kg",
                "quantity": 207.31,
                "mat_rate": 32.0,
                "labor_rate": 5.0,
            },
            {
                "code": "WIRE-MESH",
                "name": "ตะแกรงเหล็กไวร์เมช (Wire Mesh 6mm @0.20m)",
                "formula": "Area × 1.05 = 16.0 × 1.05",
                "unit": "m2",
                "quantity": 16.80,
                "mat_rate": 65.0,
                "labor_rate": 15.0,
            },
        ],
        "thai_specs": {
            "materials": "คอนกรีตแรงอัด 280 ksc ตะแกรงเหล็กกล้าเชื่อมติดเสริมคอนกรีต มอก. 737",
            "workmanship": "บ่มคอนกรีตชื้นอย่างน้อย 7 วัน หลังเทคอนกรีต ขัดเรียบ/ขัดมันตามแบบระบุ",
            "testing": "ทดสอบความหนาแผ่นพื้นและระดับความสม่ำเสมอสโลปด้วยระดับน้ำเลเซอร์",
        },
        "sample_3d": {
            "shape": "box",
            "width": 4.00,
            "depth": 4.00,
            "height": 0.12,
            "color": "#94A3B8",
            "is_reinforced_concrete": True,
            "rebar_type": "slab",
        },
        "sample_2d_svg": """<svg viewBox="0 0 200 200" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="20" width="160" height="160" fill="#e2e8f0" stroke="#0f172a" stroke-width="2"/><text x="80" y="105" fill="#0f172a" font-size="13" font-weight="bold">S1 (t=12cm)</text></svg>""",
    },
    {
        "id": "IfcFooting",
        "class_name": "IfcFooting",
        "name_th": "ฐานรากอาคาร (Foundation Footing)",
        "discipline": "Structure",
        "schema_version": "IFC4",
        "description": "ฐานรากแผ่หรือฐานรากเสาเข็ม (Footing) กระจายน้ำหนักอาคารลงสู่ดินหรือเสาเข็ม",
        "predefined_types": ["PAD_FOOTING", "STRIP_FOOTING", "PILE_CAP"],
        "bsdd_psets": ["Pset_FootingCommon"],
        "debim_yaml": """- tag: F1
  class: IfcFooting
  material: MAT_CONC_280
  dimensions:
    width: 1.20
    depth: 1.20
    thickness: 0.50
  placement:
    grid: A-1
    offset_z: -1.50
  reinforcement:
    mesh_bottom: DB16@0.15
    dowels: 4-DB20""",
        "ifc_step": """#401=IFCFOOTING('5eY4$dAt4I6z3C5n7O8pQ9',#102,'F1','Pile Cap',$,#403,#404,$,.PAD_FOOTING.);
#410=IFCREINFORCINGMESH('5fZ5$eBu5J7a4D6o8P9qR0',#102,'F1-MAT','Mat DB16@0.15 (X & Y)',$,#403,$,$,.USERDEFINED.,16.,16.,0.15,0.15,$,$);
#411=IFCREINFORCINGBAR('5gA6$fCv6K8b5E7p9Q0rS1',#102,'F1-DOWEL','Column Dowels 4-DB20',$,#403,$,$,.DOWEL.,20.,$,1.2,$,$);""",
        "qto_boq": [
            {
                "code": "CONC-F1",
                "name": "คอนกรีตฐานราก F1 (280 ksc)",
                "formula": "1.20 × 1.20 × 0.50",
                "unit": "m3",
                "quantity": 0.72,
                "mat_rate": 2400.0,
                "labor_rate": 450.0,
            },
            {
                "code": "REBAR-DB16",
                "name": "เหล็กตะแกรงก้นฐานราก DB16@0.15m (2 ทาง)",
                "formula": "16 เส้น × 1.10m × 1.58 kg/m",
                "unit": "kg",
                "quantity": 27.81,
                "mat_rate": 32.0,
                "labor_rate": 5.0,
            },
            {
                "code": "DOWEL-DB20",
                "name": "เหล็กเดือยฝังต่อเสาตอม่อ 4-DB20 (Dowels L=1.20m)",
                "formula": "4 เส้น × 1.20m × 2.47 kg/m",
                "unit": "kg",
                "quantity": 11.86,
                "mat_rate": 32.0,
                "labor_rate": 5.0,
            },
        ],
        "thai_specs": {
            "materials": "คอนกรีตผสมเสร็จแรงอัด 280 ksc คอนกรีตหยาบรองฐานราก 1:3:5 หนา 5 ซม.",
            "workmanship": "ขุดดินปรับระดับ เททรายหยาบอัดแน่น และเทคอนกรีตหยาบก่อนวางตะแกรงเหล็กฐานราก",
            "testing": "ตรวจสอบตำแหน่งศูนย์กลางเสาเข็มและระยะฝังเหล็กเดือย (Dowel bar)",
        },
        "sample_3d": {
            "shape": "box",
            "width": 1.20,
            "depth": 1.20,
            "height": 0.50,
            "color": "#64748B",
            "is_reinforced_concrete": True,
            "rebar_type": "footing",
        },
        "sample_2d_svg": """<svg viewBox="0 0 160 160" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="30" y="30" width="100" height="100" fill="#94a3b8" stroke="#0f172a" stroke-width="2"/><circle cx="80" cy="80" r="12" fill="#0284c7"/><text x="60" y="22" fill="#0f172a" font-size="11" font-weight="bold">F1 (1.2x1.2m)</text></svg>""",
    },
    {
        "id": "IfcPile",
        "class_name": "IfcPile",
        "name_th": "เสาเข็มฐานราก (Foundation Pile)",
        "discipline": "Structure",
        "schema_version": "IFC4",
        "description": "เสาเข็มคอนกรีตอัดแรง/เสาเข็มเจาะ (Foundation Pile) ถ่ายน้ำหนักลงสู่ชั้นดินแข็ง",
        "predefined_types": ["BORED", "DRIVEN", "JETGROUTING"],
        "bsdd_psets": ["Pset_PileCommon"],
        "debim_yaml": """- tag: P1
  class: IfcPile
  predefined_type: DRIVEN
  dimension: 0.26
  length: 16.0
  placement:
    grid: A-1""",
        "ifc_step": """#450=IFCPILE('6fZ5$eBu5J7a4D6o8P9qR0',#102,'P1','Driven Pile',$,#451,#452,$,.DRIVEN.);""",
        "qto_boq": [
            {
                "code": "PILE-I26",
                "name": "เสาเข็มคอนกรีตอัดแรงไอ 26 ซม. ยาว 16 ม.",
                "formula": "1 ต้น × 16.0 ม.",
                "unit": "m",
                "quantity": 16.0,
                "mat_rate": 380.0,
                "labor_rate": 120.0,
            }
        ],
        "thai_specs": {
            "materials": "เสาเข็มคอนกรีตอัดแรง มอก. 396-2549 แรงอัดไม่น้อยกว่า 350 ksc",
            "workmanship": "ตอกเสาเข็มด้วยปั่นจั่น บันทึกการจมของเสาเข็ม 10 ครั้งสุดท้าย (Last 10 Blows)",
            "testing": "ทดสอบความสมบูรณ์เสาเข็มด้วยคลื่นความถี่สูง (Seismic Integrity Test)",
        },
        "sample_3d": {
            "shape": "cylinder",
            "radius": 0.13,
            "height": 4.0,
            "color": "#475569",
        },
        "sample_2d_svg": """<svg viewBox="0 0 120 120" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><circle cx="60" cy="60" r="30" fill="#64748b" stroke="#0f172a" stroke-width="2"/><text x="40" y="65" fill="#ffffff" font-size="10" font-weight="bold">I-26</text></svg>""",
    },
    {
        "id": "IfcPlate",
        "class_name": "IfcPlate",
        "name_th": "แผ่นเหล็กโครงสร้าง / แผ่นเพลท (Steel Plate)",
        "discipline": "Structure",
        "schema_version": "IFC4",
        "description": "แผ่นเพลทเหล็กรับแรง ยึดต่อโครงสร้างเสา คาน หรือแผ่นเพลทฐานราก (Base Plate)",
        "predefined_types": ["BASE_PLATE", "FLANGE_PLATE", "CURTAIN_PANEL"],
        "bsdd_psets": ["Pset_PlateCommon"],
        "debim_yaml": """- tag: PL1
  class: IfcPlate
  predefined_type: BASE_PLATE
  material: STEEL_SS400
  thickness: 0.02
  width: 0.40
  depth: 0.40""",
        "ifc_step": """#480=IFCPLATE('7gA6$fCv6K8b5E7p9Q0rS1',#102,'PL1','Base Plate',$,#481,#482,$,.BASE_PLATE.);""",
        "qto_boq": [
            {
                "code": "STEEL-PLATE",
                "name": "แผ่นเหล็กเพลท SS400 หนา 20 มม.",
                "formula": "0.4 × 0.4 × 0.02m × 7850 kg/m3",
                "unit": "kg",
                "quantity": 25.12,
                "mat_rate": 45.0,
                "labor_rate": 12.0,
            }
        ],
        "thai_specs": {
            "materials": "เหล็กแผ่นโครงสร้างทั่วไป SS400 มาตรฐาน มอก. 1479-2558",
            "workmanship": "เจาะรูน็อตพุกเจาะด้วยเครื่องเจาะ พ่นทรายและทาสีกันสนิมอีพ็อกซี่หนา 100 ไมครอน",
            "testing": "ตรวจวัดความหนาชั้นสีกันสนิม (Dry Film Thickness) และทดสอบรอยเชื่อมด้วยน้ำยาแทรกซึม (PT)",
        },
        "sample_3d": {
            "shape": "box",
            "width": 0.40,
            "depth": 0.40,
            "height": 0.02,
            "color": "#334155",
        },
        "sample_2d_svg": """<svg viewBox="0 0 140 140" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="20" width="100" height="100" fill="#475569" stroke="#0f172a" stroke-width="2"/><circle cx="35" cy="35" r="5" fill="#0284c7"/><circle cx="105" cy="35" r="5" fill="#0284c7"/><circle cx="35" cy="105" r="5" fill="#0284c7"/><circle cx="105" cy="105" r="5" fill="#0284c7"/></svg>""",
    },
    # --- ARCHITECTURE ---
    {
        "id": "IfcWall",
        "class_name": "IfcWall",
        "name_th": "ผนังอาคาร (Architectural Wall)",
        "discipline": "Architecture",
        "schema_version": "IFC4",
        "description": "องค์อาคารผนังแนวดิ่ง แบ่งพื้นที่สัดส่วน กั้นห้อง หรือผนังรับน้ำหนัก (Bearing Wall)",
        "predefined_types": ["SOLIDWALL", "PARAPET", "PARTITIONING"],
        "bsdd_psets": ["Pset_WallCommon"],
        "debim_yaml": """- tag: W1
  class: IfcWall
  storey: STOREY_1
  material: BRICK_RED
  thickness: 0.10
  height: 2.80
  placement:
    from_grid: A-1
    to_grid: A-2""",
        "ifc_step": """#501=IFCWALL('8hB7$gDw7L9c6F8q0R1sT2',#102,'W1','Brick Wall',$,#503,#504,$,.SOLIDWALL.);""",
        "qto_boq": [
            {
                "code": "BRICK-RED",
                "name": "งานก่ออิฐมอญครึ่งแผ่น ฉาบปูนเรียบ 2 ด้าน",
                "formula": "4.0m × 2.8m = 11.20 m2",
                "unit": "m2",
                "quantity": 11.20,
                "mat_rate": 350.0,
                "labor_rate": 150.0,
            }
        ],
        "thai_specs": {
            "materials": "อิฐมอญสามัญ มอก. 153-2540 ปูนฉาบสำเร็จรูปสำหรับงานอิฐมอญ",
            "workmanship": "ทำเสาเอ็น-คานเอ็น ค.ส.ล. ทุกระยะกว้างเกิน 2.5 ม. หรือสูงเกิน 1.5 ม. รดน้ำอิฐก่อนก่อ",
            "testing": "ตรวจสอบดิ่งฉากผนังและความเรียบระนาบผนังฉาบ คลาดเคลื่อนไม่เกิน 2 มม./2ม.",
        },
        "sample_3d": {
            "shape": "box",
            "width": 4.00,
            "depth": 0.10,
            "height": 2.80,
            "color": "#CBD5E1",
        },
        "sample_2d_svg": """<svg viewBox="0 0 240 80" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="25" width="200" height="30" fill="#94a3b8" stroke="#0f172a" stroke-width="2"/><line x1="20" y1="40" x2="220" y2="40" stroke="#0f172a" stroke-dasharray="2,2"/><text x="90" y="20" fill="#0f172a" font-size="11" font-weight="bold">W1 (100mm Brick)</text></svg>""",
    },
    {
        "id": "IfcDoor",
        "class_name": "IfcDoor",
        "name_th": "ประตูอาคาร (Door Assembly)",
        "discipline": "Architecture",
        "schema_version": "IFC4",
        "description": "ช่องเปิดประตูสำหรับเข้าออกพื้นที่ พร้อมวงกบ บานประตู และอุปกรณ์ฟิตติ้ง",
        "predefined_types": ["DOOR", "GATE", "USERDEFINED"],
        "bsdd_psets": ["Pset_DoorCommon"],
        "debim_yaml": """- tag: D1
  class: IfcDoor
  host_wall: W1
  offset_distance: 1.0
  width: 0.90
  height: 2.00
  operation_type: SINGLE_SWING_LEFT""",
        "ifc_step": """#601=IFCDOOR('9iC8$hEx8M0d7G9r1S2tU3',#102,'D1','Single Swing Door',$,#603,#604,$,.DOOR.,2.0,0.9);""",
        "qto_boq": [
            {
                "code": "DOOR-D1",
                "name": "ชุดประตูไม้สังเคราะห์ UPVC 0.90x2.00ม. พร้อมวงกบและลูกบิด",
                "formula": "1 ชุด",
                "unit": "set",
                "quantity": 1.0,
                "mat_rate": 3500.0,
                "labor_rate": 600.0,
            }
        ],
        "thai_specs": {
            "materials": "บานประตู UPVC เกรดภายนอกทนแดดทนฝน วงกบ UPVC พร้อมซีลยางกันเสียง",
            "workmanship": "ติดตั้งวงกบได้ระดับดิ่งฉาก ยึดพุกพลาสติกและสกรูแข็งแรง ติดตั้งบานประตูเปิด-ปิดคล่อง",
            "testing": "ทดสอบการเปิด-ปิดบานประตู การทำงานของกลอนและลูกบิดสลักล็อก",
        },
        "sample_3d": {
            "shape": "box",
            "width": 0.90,
            "depth": 0.10,
            "height": 2.00,
            "color": "#8B4513",
        },
        "sample_2d_svg": """<svg viewBox="0 0 160 120" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="50" width="120" height="20" fill="#cbd5e1"/><line x1="40" y1="50" x2="40" y2="10" stroke="#0284c7" stroke-width="2"/><path d="M 40 10 A 40 40 0 0 1 80 50" fill="none" stroke="#0284c7" stroke-width="1.5" stroke-dasharray="3,2"/><text x="50" y="85" fill="#0f172a" font-size="11" font-weight="bold">D1 (900x2000mm)</text></svg>""",
    },
    {
        "id": "IfcWindow",
        "class_name": "IfcWindow",
        "name_th": "หน้าต่างอาคาร (Window Assembly)",
        "discipline": "Architecture",
        "schema_version": "IFC4",
        "description": "ช่องเปิดหน้าต่างรับแสงและระบายอากาศ พร้อมกรอบบานอลูมิเนียม/ไม้ และกระจก",
        "predefined_types": ["WINDOW", "LIGHTDOME", "USERDEFINED"],
        "bsdd_psets": ["Pset_WindowCommon"],
        "debim_yaml": """- tag: WN1
  class: IfcWindow
  host_wall: W1
  offset_distance: 2.2
  width: 1.20
  height: 1.10
  sill_height: 0.90""",
        "ifc_step": """#650=IFCWINDOW('0jD9$iFy9N1e8H0s2T3uV4',#102,'WN1','Aluminium Window',$,#651,#652,$,.WINDOW.,1.1,1.2);""",
        "qto_boq": [
            {
                "code": "WIN-ALU",
                "name": "ชุดหน้าต่างอลูมิเนียมบานเลื่อนคู่ กระจกเขียวตัดแสง 6mm",
                "formula": "1.20 × 1.10 m = 1.32 m2",
                "unit": "m2",
                "quantity": 1.32,
                "mat_rate": 2200.0,
                "labor_rate": 350.0,
            }
        ],
        "thai_specs": {
            "materials": "อลูมิเนียมอบสีขาว หนา 1.2 มม. กระจกอินสุเลต/กระจกเขียวตัดแสงหนา 6 มม.",
            "workmanship": "ยิงซิลิโคนกันน้ำรั่วซึมขอบวงกบภายนอกรอบด้าน ติดตั้งยางกันชนและลูกล้อบานเลื่อน",
            "testing": "ทดสอบการรั่วซึมของน้ำฝน (Water Leakage Test) ด้วยสเปรย์น้ำแรงดันสูง",
        },
        "sample_3d": {
            "shape": "box",
            "width": 1.20,
            "depth": 0.10,
            "height": 1.10,
            "color": "#38BDF8",
        },
        "sample_2d_svg": """<svg viewBox="0 0 160 100" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="35" width="120" height="30" fill="#e0f2fe" stroke="#0284c7" stroke-width="2"/><line x1="80" y1="35" x2="80" y2="65" stroke="#0284c7" stroke-width="2"/><text x="45" y="25" fill="#0f172a" font-size="11" font-weight="bold">WN1 (1200x1100mm)</text></svg>""",
    },
    {
        "id": "IfcRoof",
        "class_name": "IfcRoof",
        "name_th": "หลังคาและโครงหลังคา (Roof Assembly)",
        "discipline": "Architecture",
        "schema_version": "IFC4",
        "description": "โครงสร้างและกระเบื้องมุงหลังคา กันแดดฝน พร้อมโครงแป จันทัน และไม้เชิงชาย",
        "predefined_types": ["GABLE_ROOF", "HIP_ROOF", "FLAT_ROOF"],
        "bsdd_psets": ["Pset_RoofCommon"],
        "debim_yaml": """- tag: R1
  class: IfcRoof
  roof_type: GABLE_ROOF
  pitch_degrees: 30.0
  covering:
    tile_type: CONCRETE_CPAC
  framing:
    rafter_profile: C150X50X20X3.2
    purlin_profile: C75X45X15X2.3""",
        "ifc_step": """#701=IFCROOF('1kE0$jGz0O2f9I1t3U4vW5',#102,'R1','Gable Roof',$,#703,#704,$,.GABLE_ROOF.);""",
        "qto_boq": [
            {
                "code": "ROOF-TILE",
                "name": "กระเบื้องหลังคาซีแพคโมเนีย พร้อมครอบสันหลังคา",
                "formula": "Area / cos(30°) = 48.0 m2",
                "unit": "m2",
                "quantity": 48.0,
                "mat_rate": 380.0,
                "labor_rate": 150.0,
            }
        ],
        "thai_specs": {
            "materials": "กระเบื้องหลังคาคอนกรีตซีแพคโมเนีย มอก. 535-2556 โครงหลังคาเหล็กกัลวาไนซ์ปลอดสนิม",
            "workmanship": "มุงกระเบื้องตามทิศทางลม ยึดสกรูเกลียวปล่อยพร้อมยางกันรั่วซึมทุกแผ่น",
            "testing": "ตรวจสอบความลาดเอียงและทดสอบการขังของน้ำฉีดกระจายทั่วหลังคา",
        },
        "sample_3d": {
            "shape": "polygon",
            "points": [[0,0,3], [4,0,3], [2,2,4.5]],
            "color": "#9E4734",
        },
        "sample_2d_svg": """<svg viewBox="0 0 200 120" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><polygon points="20,90 100,20 180,90" fill="#f87171" stroke="#0f172a" stroke-width="2"/><text x="75" y="110" fill="#0f172a" font-size="11" font-weight="bold">R1 (Gable 30°)</text></svg>""",
    },
    {
        "id": "IfcCurtainWall",
        "class_name": "IfcCurtainWall",
        "name_th": "ผนังกระจกโชว์รูม / ผนังเคอร์เทนวอลล์ (Curtain Wall)",
        "discipline": "Architecture",
        "schema_version": "IFC4",
        "description": "ผนังกระจกโครงอลูมิเนียมภายนอกอาคาร (Non-load bearing curtain wall)",
        "predefined_types": ["USERDEFINED", "NOTDEFINED"],
        "bsdd_psets": ["Pset_CurtainWallCommon"],
        "debim_yaml": """- tag: CW1
  class: IfcCurtainWall
  height: 3.50
  mullion_spacing: 1.20
  glass_thickness: 0.010
  placement:
    from_grid: A-1
    to_grid: A-3""",
        "ifc_step": """#750=IFCCURTAINWALL('2lF1$kHA1P3g0J2u4V5wX6',#102,'CW1','Curtain Wall',$,#751,#752,$);""",
        "qto_boq": [
            {
                "code": "CW-GLASS",
                "name": "ผนังกระจกเคอร์เทนวอลล์ กระจกเทมเปอร์หนา 10 มม. พร้อมโครงอลูมิเนียม",
                "formula": "6.0m × 3.5m = 21.0 m2",
                "unit": "m2",
                "quantity": 21.0,
                "mat_rate": 3800.0,
                "labor_rate": 650.0,
            }
        ],
        "thai_specs": {
            "materials": "กระจกเทมเปอร์ใส/เขียวตัดแสง หนา 10 มม. มอก. 965 โครงอลูมิเนียมอลูไมต์หนา 2.0 มม.",
            "workmanship": "ติดตั้งยึดฉากแบร็กเก็ตกับโครงสร้าง ค.ส.ล. ใส่ประเก็นยาง EPDM และซิลิโคนซีลแลนท์ประเภท Structural Silicone",
            "testing": "ทดสอบแรงลม (Wind Pressure Test) และทดสอบความคงทนต่อการรั่วซึมของอากาศและน้ำ",
        },
        "sample_3d": {
            "shape": "box",
            "width": 6.0,
            "depth": 0.12,
            "height": 3.5,
            "color": "#38BDF8",
        },
        "sample_2d_svg": """<svg viewBox="0 0 240 60" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="20" width="200" height="20" fill="#e0f2fe" stroke="#0284c7" stroke-width="2"/><line x1="70" y1="20" x2="70" y2="40" stroke="#0284c7" stroke-width="2"/><line x1="120" y1="20" x2="120" y2="40" stroke="#0284c7" stroke-width="2"/><line x1="170" y1="20" x2="170" y2="40" stroke="#0284c7" stroke-width="2"/><text x="85" y="15" fill="#0f172a" font-size="10" font-weight="bold">CW1 Glass Facade</text></svg>""",
    },
    {
        "id": "IfcCovering",
        "class_name": "IfcCovering",
        "name_th": "วัสดุปูผิว / ฝ้าเพดาน (Finishes & Ceiling)",
        "discipline": "Architecture",
        "schema_version": "IFC4",
        "description": "วัสดุตกแต่งปูผิวพื้น ผนัง หรือฝ้าเพดาน (Ceiling / Flooring / Skirting Finishes)",
        "predefined_types": ["CEILING", "FLOORING", "CLADDING", "SKIRTING"],
        "bsdd_psets": ["Pset_CoveringCommon"],
        "debim_yaml": """- tag: COV1
  class: IfcCovering
  covering_type: CEILING
  material: GYPSUM_BOARD_9MM
  area: 25.0
  placement:
    storey: STOREY_1
    offset_z: 2.70""",
        "ifc_step": """#780=IFCCOVERING('3mG2$lIB2Q4h1K3v5W6xY7',#102,'COV1','Ceiling Finish',$,#781,#782,$,.CEILING.);""",
        "qto_boq": [
            {
                "code": "CEIL-GYP",
                "name": "งานฝ้าเพดานยิปซั่มฉาบเรียบ หนา 9 มม. พร้อมโครงคร่าว C-Line",
                "formula": "25.0 m2",
                "unit": "m2",
                "quantity": 25.0,
                "mat_rate": 220.0,
                "labor_rate": 110.0,
            }
        ],
        "thai_specs": {
            "materials": "แผ่นยิปซั่มขอบลาดหนา 9 มม. มอก. 219 โครงคร่าวสังกะสี C-Line หนา 0.50 มม.",
            "workmanship": "แขวนชุดฉากยึดพุกพลาสติกกับโครงสร้างคาน/พื้น ระยะห่างโครงคร่าวไม่เกิน 0.40 ม.",
            "testing": "ตรวจระดับฝ้าเพดานด้วยฉากเลเซอร์ และตรวจรอยฉาบรอยต่อก่อนทาสี",
        },
        "sample_3d": {
            "shape": "box",
            "width": 5.0,
            "depth": 5.0,
            "height": 0.01,
            "color": "#EDE8F5",
        },
        "sample_2d_svg": """<svg viewBox="0 0 160 160" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="20" width="120" height="120" fill="#f1f5f9" stroke="#64748b" stroke-width="1.5" stroke-dasharray="4,4"/><text x="35" y="85" fill="#0f172a" font-size="11" font-weight="bold">Gypsum Ceiling 25m2</text></svg>""",
    },
    {
        "id": "IfcStair",
        "class_name": "IfcStair",
        "name_th": "บันไดอาคาร (Stair Assembly)",
        "discipline": "Architecture",
        "schema_version": "IFC4",
        "description": "ชุดบันไดสัญจรแนวดิ่ง พร้อมลูกขั้น ลูกนอน ชานพัก และราวบันได",
        "predefined_types": ["STRAIGHT", "QUARTER_TURN", "HALF_TURN", "SPIRAL"],
        "bsdd_psets": ["Pset_StairCommon"],
        "debim_yaml": """- tag: ST1
  class: IfcStair
  stair_type: STRAIGHT
  width: 1.20
  riser_height: 0.175
  tread_depth: 0.25
  steps_count: 16
  reinforcement:
    waist_main: DB12@0.15
    cross_bars: RB9@0.20""",
        "ifc_step": """#801=IFCSTAIR('4nH3$mJC3R5i2L4w6X7yZ8',#102,'ST1','Main Stair',$,#803,#804,$,.STRAIGHT.);
#810=IFCREINFORCINGBAR('4oI4$nKD4S6j3M5x7Y8z0A',#102,'ST1-MAIN','Waist Rebar DB12@0.15',$,#803,$,$,.MAIN.,12.,$,4.5,$,$);""",
        "qto_boq": [
            {
                "code": "STAIR-CONC",
                "name": "งานบันได ค.ส.ล. พร้อมปูลูกนอนไม้จริงหนา 1.5 นิ้ว",
                "formula": "16 ขั้น × 1.20 ม.",
                "unit": "m",
                "quantity": 19.20,
                "mat_rate": 1200.0,
                "labor_rate": 450.0,
            },
            {
                "code": "REBAR-STAIR",
                "name": "เหล็กเสริมท้องบันได ค.ส.ล. DB12@0.15m + RB9@0.20m",
                "formula": "16 ขั้น × 1.20 ม. × 4.2 kg/m",
                "unit": "kg",
                "quantity": 80.64,
                "mat_rate": 32.0,
                "labor_rate": 5.0,
            },
        ],
        "thai_specs": {
            "materials": "คอนกรีต 280 ksc ไม้ลูกนอนไม้แดง/ไม้เต็งอบแห้ง หนาไม่น้อยกว่า 35 มม.",
            "workmanship": "ระยะลูกตั้งสูงไม่เกิน 18 ซม. ลูกนอนกว้างไม่น้อยกว่า 25 ซม. ตามกฎหมายควบคุมอาคาร",
            "testing": "ตรวจสอบความสม่ำเสมอของระยะลูกตั้งทุกขั้น คลาดเคลื่อนไม่เกิน 3 มม.",
        },
        "sample_3d": {
            "shape": "stair_flight",
            "width": 1.20,
            "steps": 8,
            "color": "#D4A373",
        },
        "sample_2d_svg": """<svg viewBox="0 0 200 120" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><path d="M 20 100 L 20 85 L 40 85 L 40 70 L 60 70 L 60 55 L 80 55 L 80 40 L 100 40 L 100 25 L 180 25 L 180 100 Z" fill="#cbd5e1" stroke="#0f172a" stroke-width="2"/><text x="90" y="75" fill="#0f172a" font-size="11" font-weight="bold">ST1 (16 Risers)</text></svg>""",
    },
    {
        "id": "IfcRailing",
        "class_name": "IfcRailing",
        "name_th": "ราวกันตก / ราวบันได (Railing Guard)",
        "discipline": "Architecture",
        "schema_version": "IFC4",
        "description": "ราวกันตกป้องกันการตกจากที่สูง บริเวณบันได ระเบียง หรือดาดฟ้า",
        "predefined_types": ["HANDRAIL", "GUARDRAIL", "BALUSTRADE"],
        "bsdd_psets": ["Pset_RailingCommon"],
        "debim_yaml": """- tag: RL1
  class: IfcRailing
  railing_type: GUARDRAIL
  height: 1.10
  length: 6.00
  material: STAINLESS_STEEL""",
        "ifc_step": """#850=IFCRAILING('5oI4$nKD4S6j3M5x7Y8z0A',#102,'RL1','Balcony Railing',$,#851,#852,$,.GUARDRAIL.);""",
        "qto_boq": [
            {
                "code": "RAIL-SS",
                "name": "ราวกันตกสแตนเลส SUS304 สูง 1.10 ม. พร้อมกระจกเทมเปอร์ 10 มม.",
                "formula": "6.0 ม.",
                "unit": "m",
                "quantity": 6.0,
                "mat_rate": 2800.0,
                "labor_rate": 450.0,
            }
        ],
        "thai_specs": {
            "materials": "สแตนเลสกลม SUS304 เกรดปลอดสนิม ผิวแฮร์ไลน์/เงา กระจกเทมเปอร์นิรภัย",
            "workmanship": "เชื่อมประกอบขัดรอยเชื่อมเรียบเนียน ยึดพุกสแตนเลสเข้ากับโครงสร้าง ค.ส.ล. แข็งแรงรับแรงกดได้ 100 kg/m",
            "testing": "ทดสอบแรงผลักแนวนอน (Horizontal Push Load Test) ที่ราวบนไม่น้อยกว่า 1.0 kN/m",
        },
        "sample_3d": {
            "shape": "box",
            "width": 6.0,
            "depth": 0.05,
            "height": 1.10,
            "color": "#E11D48",
        },
        "sample_2d_svg": """<svg viewBox="0 0 200 80" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><line x1="20" y1="20" x2="180" y2="20" stroke="#e11d48" stroke-width="3"/><line x1="30" y1="20" x2="30" y2="60" stroke="#0f172a" stroke-width="2"/><line x1="100" y1="20" x2="100" y2="60" stroke="#0f172a" stroke-width="2"/><line x1="170" y1="20" x2="170" y2="60" stroke="#0f172a" stroke-width="2"/><text x="70" y="75" fill="#0f172a" font-size="10" font-weight="bold">Railing H=1.10m</text></svg>""",
    },
    # --- MEP ---
    {
        "id": "IfcPipeSegment",
        "class_name": "IfcPipeSegment",
        "name_th": "ท่อประปา / ท่อน้ำทิ้ง-โสโครก (Plumbing Pipe)",
        "discipline": "MEP",
        "schema_version": "IFC4",
        "description": "ท่อส่งน้ำประปา น้ำร้อน น้ำทิ้ง น้ำโสโครก และท่อระบายน้ำฝน",
        "predefined_types": ["CULVERT", "GUTTER", "RIGIDSEGMENT", "FLEXIBLESEGMENT"],
        "bsdd_psets": ["Pset_PipeSegmentCommon"],
        "debim_yaml": """- tag: P-CW-01
  class: IfcPipeSegment
  system_type: COLD_WATER
  nominal_diameter: 0.025
  material: PPR_GREEN
  waypoints:
    - [0.0, 0.0, 0.5]
    - [5.0, 0.0, 0.5]""",
        "ifc_step": """#901=IFCPIPESEGMENT('6pJ5$oLE5T7k4N6y8Z9a1B',#102,'P-CW-01','PPR Cold Water Pipe',$,#903,#904,$,.RIGIDSEGMENT.);""",
        "qto_boq": [
            {
                "code": "PIPE-PPR25",
                "name": "ท่อประปา PPR Class 20 ขนาด Ø 25มม. (1 นิ้ว)",
                "formula": "5.0 ม.",
                "unit": "m",
                "quantity": 5.0,
                "mat_rate": 110.0,
                "labor_rate": 45.0,
            }
        ],
        "thai_specs": {
            "materials": "ท่อเขียว PPR (Polypropylene Random) มอก. 2185-2547 ทนแรงดัน 20 บาร์",
            "workmanship": "เชื่อมต่อท่อด้วยเครื่องเชื่อมความร้อน (Socket Fusion) ที่อุณหภูมิ 260°C",
            "testing": "ทดสอบแรงดันน้ำ (Hydrostatic Pressure Test) ที่ 1.5 เท่าของแรงดันใช้งาน (10 บาร์) เป็นเวลา 2 ชั่วโมง",
        },
        "sample_3d": {
            "shape": "pipe",
            "radius": 0.025,
            "length": 5.0,
            "color": "#0284C7",
        },
        "sample_2d_svg": """<svg viewBox="0 0 200 60" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><line x1="20" y1="30" x2="180" y2="30" stroke="#0284c7" stroke-width="6"/><circle cx="20" cy="30" r="6" fill="#0284c7"/><circle cx="180" cy="30" r="6" fill="#0284c7"/><text x="65" y="20" fill="#0f172a" font-size="11" font-weight="bold">Ø25mm PPR Pipe</text></svg>""",
    },
    {
        "id": "IfcSanitaryTerminal",
        "class_name": "IfcSanitaryTerminal",
        "name_th": "สุขภัณฑ์และอุปกรณ์ห้องน้ำ (Sanitary Fixture)",
        "discipline": "MEP",
        "schema_version": "IFC4",
        "description": "สุขภัณฑ์โถส้วม อ่างล้างหน้า โถปัสสาวะ อ่างอาบน้ำ และสุขภัณฑ์ห้องน้ำ",
        "predefined_types": ["WATERCLOSET", "WASHHANDBASIN", "URINAL", "BATH", "SHOWER"],
        "bsdd_psets": ["Pset_SanitaryTerminalCommon"],
        "debim_yaml": """- tag: WC1
  class: IfcSanitaryTerminal
  predefined_type: WATERCLOSET
  material: CERAMIC_WHITE
  cold_water_inlet_diameter: 0.015
  waste_outlet_diameter: 0.100
  placement:
    storey: STOREY_1
    offset_x: 1.50""",
        "ifc_step": """#950=IFCSANITARYTERMINAL('7qK6$pMF6U8l5O7z9A0b2C',#102,'WC1','Water Closet',$,#951,#952,$,.WATERCLOSET.);""",
        "qto_boq": [
            {
                "code": "SAN-WC",
                "name": "โถส้วมชักโครกสองชิ้น ประหยัดน้ำ 3/4.5 ลิตร พร้อมสายฉีดชำระและสต็อปวาล์ว",
                "formula": "1 ชุด",
                "unit": "set",
                "quantity": 1.0,
                "mat_rate": 4500.0,
                "labor_rate": 600.0,
            }
        ],
        "thai_specs": {
            "materials": "โถสุขภัณฑ์เซรามิควิเทรียสไชนา สีขาว มอก. 792-2554 ระบบชำระล้าง SIPHON JET",
            "workmanship": "ติดตั้งประเก็นขี้ผึ้ง (Wax Ring) กันกลิ่นรั่วซึมที่ท่อน้ำทิ้งใต้พื้น ยึดน็อตลงพื้น ค.ส.ล. แข็งแรง",
            "testing": "ทดสอบการกดชำระล้างน้ำ (Flushing Performance Test) และตรวจรอยรั่วซึมรอบโถ",
        },
        "sample_3d": {
            "shape": "box",
            "width": 0.45,
            "depth": 0.70,
            "height": 0.75,
            "color": "#FFFFFF",
        },
        "sample_2d_svg": """<svg viewBox="0 0 120 140" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="35" y="20" width="50" height="30" rx="4" fill="#f8fafc" stroke="#0f172a" stroke-width="2"/><ellipse cx="60" cy="85" rx="30" ry="40" fill="#ffffff" stroke="#0f172a" stroke-width="2"/><text x="40" y="135" fill="#0f172a" font-size="10" font-weight="bold">WC Toilet</text></svg>""",
    },
    {
        "id": "IfcDuctSegment",
        "class_name": "IfcDuctSegment",
        "name_th": "ท่อลมระบบปรับอากาศ (HVAC Duct Segment)",
        "discipline": "MEP",
        "schema_version": "IFC4",
        "description": "ท่อลมส่ง (Supply Duct) ท่อลมกลับ (Return Duct) และท่อลมระบายอากาศ",
        "predefined_types": ["RIGIDSEGMENT", "FLEXIBLESEGMENT"],
        "bsdd_psets": ["Pset_DuctSegmentCommon"],
        "debim_yaml": """- tag: D-SA-01
  class: IfcDuctSegment
  system_type: SUPPLY_AIR
  width: 0.40
  height: 0.25
  material: GALVANIZED_STEEL
  waypoints:
    - [0.0, 0.0, 3.0]
    - [6.0, 0.0, 3.0]""",
        "ifc_step": """#1001=IFCDUCTSEGMENT('8rL7$qNG7V9m6P8a0B1c3D',#102,'D-SA-01','Supply Air Duct',$,#1003,#1004,$,.RIGIDSEGMENT.);""",
        "qto_boq": [
            {
                "code": "DUCT-GALV",
                "name": "ท่อลมสังกะสีสี่เหลี่ยม เบอร์ 24 พร้อมหุ้มฉนวนใยแก้ว หนา 1 นิ้ว",
                "formula": "2 × (0.40+0.25) × 6.0m = 7.80 m2",
                "unit": "m2",
                "quantity": 7.80,
                "mat_rate": 650.0,
                "labor_rate": 220.0,
            }
        ],
        "thai_specs": {
            "materials": "แผ่นเหล็กเคลือบสังกะสี มอก. 50-2561 ฉนวนใยแก้วหุ้มท่อลมฟอยล์อลูมิเนียมกันความชื้น",
            "workmanship": "เข้าพับขอบหน้าแปลน TDC/TDF ซีลซิลิโคนกันลมรั่วตามรอยต่อทุกจุด แขวนด้วยสตัดเกลียว",
            "testing": "ทดสอบการรั่วไหลของอากาศ (Duct Leakage Test) ตามมาตรฐาน SMACNA",
        },
        "sample_3d": {
            "shape": "box",
            "width": 6.0,
            "depth": 0.40,
            "height": 0.25,
            "color": "#CBD5E1",
        },
        "sample_2d_svg": """<svg viewBox="0 0 200 70" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="20" width="160" height="30" fill="#e2e8f0" stroke="#0f172a" stroke-width="2"/><line x1="20" y1="20" x2="180" y2="50" stroke="#64748b" stroke-dasharray="2,2"/><text x="55" y="40" fill="#0f172a" font-size="10" font-weight="bold">Duct 400x250mm</text></svg>""",
    },
    {
        "id": "IfcAirTerminal",
        "class_name": "IfcAirTerminal",
        "name_th": "หัวจ่ายลม / พัดลมดูดอากาศ (Air Terminal)",
        "discipline": "MEP",
        "schema_version": "IFC4",
        "description": "หัวจ่ายลมเย็น Diffuser หน้ากากแอร์ Grille และพัดลมระบายอากาศ Exhaust Fan",
        "predefined_types": ["DIFFUSER", "GRILLE", "REGISTER", "LOUVRE"],
        "bsdd_psets": ["Pset_AirTerminalCommon"],
        "debim_yaml": """- tag: EF-01
  class: IfcAirTerminal
  terminal_type: EXHAUST_FAN_CEILING
  flow_rate_cfm: 120.0
  air_flow_rate_m3h: 200.0
  dimensions: [0.30, 0.30, 0.20]""",
        "ifc_step": """#1050=IFCAIRTERMINAL('9sM8$rOH8W0n7Q9b1C2d4E',#102,'EF-01','Exhaust Fan',$,#1051,#1052,$,.GRILLE.);""",
        "qto_boq": [
            {
                "code": "FAN-EXH",
                "name": "พัดลมดูดอากาศติดฝ้าเพดาน 120 CFM พร้อมท่อระบายลมออกภายนอก",
                "formula": "1 เครื่อง",
                "unit": "set",
                "quantity": 1.0,
                "mat_rate": 1800.0,
                "labor_rate": 350.0,
            }
        ],
        "thai_specs": {
            "materials": "พัดลมดูดอากาศมอเตอร์ประหยัดไฟ บัตเตอร์ฟลายแดมเปอร์กันลมตีกลับ มอก. 934-2558",
            "workmanship": "ยึดโครงแขวนกับพื้น ค.ส.ล. ต่อท่ออ่อนอลูมิเนียมฟอยล์ทนความร้อนออกนอกอาคาร",
            "testing": "วัดปริมาณลมระบายอากาศ (Air Flow Measurement) ด้วย Anemometer ให้ได้ตามสเปก",
        },
        "sample_3d": {
            "shape": "box",
            "width": 0.30,
            "depth": 0.30,
            "height": 0.20,
            "color": "#38BDF8",
        },
        "sample_2d_svg": """<svg viewBox="0 0 120 120" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="25" y="25" width="70" height="70" fill="#f0f9ff" stroke="#0284c7" stroke-width="2"/><circle cx="60" cy="60" r="25" fill="none" stroke="#0284c7" stroke-width="1.5"/><line x1="60" y1="35" x2="60" y2="85" stroke="#0284c7"/><line x1="35" y1="60" x2="85" y2="60" stroke="#0284c7"/><text x="35" y="110" fill="#0f172a" font-size="10" font-weight="bold">Exhaust Fan</text></svg>""",
    },
    {
        "id": "IfcLightFixture",
        "class_name": "IfcLightFixture",
        "name_th": "โคมไฟฟ้าและดวงโคม (Lighting Fixture)",
        "discipline": "MEP",
        "schema_version": "IFC4",
        "description": "โคมไฟดาวน์ไลท์ โคมฟลูออเรสเซนต์/LED โคมไฟกิ่ง และไฟฉุกเฉิน",
        "predefined_types": ["POINTSOURCE", "DIRECTIONSOURCE", "SECURITYLIGHTING"],
        "bsdd_psets": ["Pset_LightFixtureCommon"],
        "debim_yaml": """- tag: L1
  class: IfcLightFixture
  fixture_type: DOWNLIGHT
  power_watts: 12.0
  luminous_flux_lumens: 1080.0
  color_temperature_kelvin: 3000""",
        "ifc_step": """#1101=IFCLIGHTFIXTURE('0tN9$sPI9X1o8R0c2D3e5F',#102,'L1','LED Downlight',$,#1103,#1104,$,.POINTSOURCE.);""",
        "qto_boq": [
            {
                "code": "LIGHT-DL",
                "name": "โคมไฟดาวน์ไลท์ฝังฝ้า LED 12W Warm White 3000K",
                "formula": "1 ชุด",
                "unit": "set",
                "quantity": 1.0,
                "mat_rate": 320.0,
                "labor_rate": 120.0,
            }
        ],
        "thai_specs": {
            "materials": "โคมไฟดาวน์ไลท์แผง LED ถนอมสายตา ปราศจาก UV/IR มอก. 1955-2551 อายุใช้งาน 25,000 ชั่วโมง",
            "workmanship": "เจาะช่องฝ้าเพดานเรียบร้อย ต่อสายไฟผ่านขั้วเสียบต่อสายแบบสปริงล็อกปลอดภัย",
            "testing": "วัดความสว่างของแสง (Lux Test) ด้วยเครื่องวัดแสง Lux Meter ตามเกณฑ์มาตรฐาน มอก.",
        },
        "sample_3d": {
            "shape": "cylinder",
            "radius": 0.10,
            "height": 0.08,
            "color": "#FDE047",
        },
        "sample_2d_svg": """<svg viewBox="0 0 100 100" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="25" fill="#fef08a" stroke="#ca8a04" stroke-width="2"/><line x1="25" y1="50" x2="75" y2="50" stroke="#ca8a04"/><line x1="50" y1="25" x2="50" y2="75" stroke="#ca8a04"/><text x="25" y="90" fill="#0f172a" font-size="10" font-weight="bold">LED 12W</text></svg>""",
    },
    {
        "id": "IfcOutlet",
        "class_name": "IfcOutlet",
        "name_th": "เต้ารับไฟฟ้า / สวิตช์ไฟ (Power Outlet & Socket)",
        "discipline": "MEP",
        "schema_version": "IFC4",
        "description": "เต้ารับไฟฟ้ามีกราวด์ เต้ารับกันน้ำ เต้ารับสัญญาณแลน/โทรศัพท์",
        "predefined_types": ["POWEROUTLET", "DATAOUTLET", "TELEPHONEOUTLET"],
        "bsdd_psets": ["Pset_OutletCommon"],
        "debim_yaml": """- tag: SK1
  class: IfcOutlet
  outlet_type: DUPLEX_GROUNDED
  voltage: 220
  placement:
    storey: STOREY_1
    offset_z: 0.30""",
        "ifc_step": """#1150=IFCOUTLET('1uO0$tQJ0Y2p9S1d3E4f6G',#102,'SK1','Duplex Outlet',$,#1151,#1152,$,.POWEROUTLET.);""",
        "qto_boq": [
            {
                "code": "OUTLET-DUP",
                "name": "เต้ารับคู่เสียบขากลม-แบน มีกราวด์และม่านนิรภัย 16A 250V พร้อมหน้ากาก",
                "formula": "1 ชุด",
                "unit": "set",
                "quantity": 1.0,
                "mat_rate": 180.0,
                "labor_rate": 90.0,
            }
        ],
        "thai_specs": {
            "materials": "เต้ารับไฟฟ้าทำจากโพลีคาร์บอเนตทนความร้อนสูง มอก. 166-2549 ขั้วเสียบทองเหลืองหนา",
            "workmanship": "ฝังบล็อกเหล็กในผนัง ขันสกรูสายไฟ L, N, Ground แน่นหนาตามรหัสสีมาตรฐาน IEC",
            "testing": "ทดสอบแรงดันไฟฟ้าและสอบทานสายดินด้วย Socket Tester ตรวจสอบตัดไฟรั่ว RCD",
        },
        "sample_3d": {
            "shape": "box",
            "width": 0.08,
            "depth": 0.05,
            "height": 0.12,
            "color": "#F1F5F9",
        },
        "sample_2d_svg": """<svg viewBox="0 0 100 100" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="25" y="20" width="50" height="60" rx="4" fill="#f8fafc" stroke="#0f172a" stroke-width="2"/><circle cx="50" cy="40" r="6" fill="#0f172a"/><circle cx="50" cy="60" r="6" fill="#0f172a"/><text x="25" y="92" fill="#0f172a" font-size="10" font-weight="bold">Outlet 16A</text></svg>""",
    },
    {
        "id": "IfcDistributionBoard",
        "class_name": "IfcDistributionBoard",
        "name_th": "ตู้ควบคุมไฟฟ้า / ตู้โหลดเซ็นเตอร์ (Distribution Panel)",
        "discipline": "MEP",
        "schema_version": "IFC4",
        "description": "ตู้สวิตช์บอร์ดควบคุมไฟ ตู้คอนซูมเมอร์ยูนิต (Consumer Unit) และแผงจ่ายไฟ",
        "predefined_types": ["CONSUMERUNIT", "DISTRIBUTIONBOARD"],
        "bsdd_psets": ["Pset_DistributionBoardCommon"],
        "debim_yaml": """- tag: DB-MAIN
  class: IfcDistributionBoard
  board_type: CONSUMER_UNIT
  voltage: 220
  main_breaker_rating_amperes: 63
  circuits_count: 12""",
        "ifc_step": """#1201=IFCDISTRIBUTIONBOARD('2vP1$uRK1Z3q0T2e4F5g7H',#102,'DB-MAIN','Consumer Unit 12-Way',$,#1203,#1204,$,.CONSUMERUNIT.);""",
        "qto_boq": [
            {
                "code": "DB-12WAY",
                "name": "ตู้คอนซูมเมอร์ยูนิต 12 ช่อง พร้อมเมนเซอร์กิตเบรกเกอร์ 63A และลูกย่อย",
                "formula": "1 ตู้",
                "unit": "set",
                "quantity": 1.0,
                "mat_rate": 4200.0,
                "labor_rate": 850.0,
            }
        ],
        "thai_specs": {
            "materials": "ตู้ไฟเหล็กพ่นสีฝุ่นอบอย่างดี มอก. 1436-2540 เบรกเกอร์มาตรฐาน IEC 60898 และ RCD กันไฟดูด",
            "workmanship": "ติดตู้สูงจากพื้น 1.50 ม. เข้าสายไฟด้วยหางปลาบีบยึด เรียงสายไฟในตู้เป็นระเบียบพร้อมป้ายชื่อวงจร",
            "testing": "ทดสอบฉนวนไฟฟ้า (Megger Test) และทดสอบความไวการตัดกระแสไฟรั่ว RCD (30mA / 0.04 sec)",
        },
        "sample_3d": {
            "shape": "box",
            "width": 0.45,
            "depth": 0.15,
            "height": 0.65,
            "color": "#475569",
        },
        "sample_2d_svg": """<svg viewBox="0 0 120 140" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="20" width="80" height="100" fill="#334155" stroke="#0f172a" stroke-width="2"/><rect x="30" y="30" width="60" height="40" fill="#f8fafc"/><text x="28" y="135" fill="#0f172a" font-size="10" font-weight="bold">DB-MAIN (12W)</text></svg>""",
    },
    # --- CIVIL ---
    {
        "id": "IfcAlignment",
        "class_name": "IfcAlignment",
        "name_th": "แนวสายทางโครงการ (Civil Alignment)",
        "discipline": "Civil",
        "schema_version": "IFC4.3",
        "description": "แนวสายทาง 3 มิติ ประกอบด้วยแนวราบ (Horizontal) แนวตั้ง (Vertical) และระดับยกโค้ง (Cant/Superelevation)",
        "predefined_types": ["USERDEFINED", "NOTDEFINED"],
        "bsdd_psets": ["Pset_AlignmentCommon"],
        "debim_yaml": """- tag: ALIGN-MAIN
  class: IfcAlignment
  start_chainage: 0.0
  points_3d:
    - [0.0, 0.0, 10.0]
    - [100.0, 50.0, 12.0]
    - [250.0, 120.0, 15.0]""",
        "ifc_step": """#1301=IFCALIGNMENT('3wQ2$vSL2a4r1U3f5G6h8I',#102,'ALIGN-MAIN','Road Alignment',$,#1303,#1304,$);""",
        "qto_boq": [
            {
                "code": "ALIGN-SURVEY",
                "name": "งานสำรวจและกำหนดแนวศูนย์กลางสายทาง (Centerline Alignment)",
                "formula": "250.0 m",
                "unit": "m",
                "quantity": 250.0,
                "mat_rate": 0.0,
                "labor_rate": 150.0,
            }
        ],
        "thai_specs": {
            "materials": "หมุดหลักฐานแผนที่คอนกรีตมาตรฐานกรมทางหลวง พร้อมเป้าสำรวจสะท้อนแสง",
            "workmanship": "รังวัดกำหนดแนวสายทางด้วยกล้องรวมแสง Total Station หรือ GNSS RTK ความละเอียดสูง",
            "testing": "ตรวจสอบความคลาดเคลื่อนตำแหน่งแนวราบไม่เกิน ±10 มม. และแนวตั้งไม่เกิน ±5 มม.",
        },
        "sample_3d": {
            "shape": "path",
            "points": [[0,0,0], [20,10,2], [50,15,5]],
            "color": "#F59E0B",
        },
        "sample_2d_svg": """<svg viewBox="0 0 220 100" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><path d="M 20 80 Q 100 20 200 60" fill="none" stroke="#f59e0b" stroke-width="4"/><circle cx="20" cy="80" r="4" fill="#0f172a"/><circle cx="200" cy="60" r="4" fill="#0f172a"/><text x="70" y="85" fill="#0f172a" font-size="11" font-weight="bold">Alignment (Sta 0+000 - 0+250)</text></svg>""",
    },
    {
        "id": "IfcRoad",
        "class_name": "IfcRoad",
        "name_th": "ถนนและโครงสร้างชั้นทาง (Road Structure)",
        "discipline": "Civil",
        "schema_version": "IFC4.3",
        "description": "โครงสร้างถนน ประกอบด้วยชั้นผิวจราจรลาดยาง/คอนกรีต ชั้นพื้นทาง และชั้นรองพื้นทาง",
        "predefined_types": ["CARRIAGEWAY", "PAVEMENT", "USERDEFINED"],
        "bsdd_psets": ["Pset_RoadCommon"],
        "debim_yaml": """- tag: ROAD-01
  class: IfcRoad
  road_width: 7.00
  corridor_length: 100.0
  pavement_layers:
    asphalt_thickness: 0.05
    base_thickness: 0.15
    subbase_thickness: 0.20""",
        "ifc_step": """#1350=IFCROAD('4xR3$wTM3b5s2V4g6H7i9J',#102,'ROAD-01','Asphalt Road',$,#1351,#1352,$,.CARRIAGEWAY.);""",
        "qto_boq": [
            {
                "code": "PAVE-ASP",
                "name": "งานผิวจราจรแอสฟัลต์คอนกรีต หนา 5 ซม. (Asphalt Concrete Wearing Course)",
                "formula": "7.0m × 100.0m = 700 m2",
                "unit": "m2",
                "quantity": 700.0,
                "mat_rate": 280.0,
                "labor_rate": 80.0,
            }
        ],
        "thai_specs": {
            "materials": "แอสฟัลต์คอนกรีตบดแน่นเกรด AC 60/70 มาตรฐานกรมทางหลวง ทรายรองพื้นและหินคลุกบดแน่น 95% Modified AASHTO",
            "workmanship": "ปูผิวจราจรด้วยเครื่องปูแอสฟัลต์ (Paver) ควบคุมอุณหภูมิปูไม่ต่ำกว่า 130°C บดทับด้วยรถบดเหล็กสั่นสะเทือน",
            "testing": "เจาะเก็บตัวอย่างผิวทาง (Core Drilling) ทดสอบความหนาและความบดแน่นแห้ง (Field Density)",
        },
        "sample_3d": {
            "shape": "box",
            "width": 10.0,
            "depth": 7.0,
            "height": 0.40,
            "color": "#334155",
        },
        "sample_2d_svg": """<svg viewBox="0 0 220 80" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="20" width="180" height="40" fill="#475569" stroke="#0f172a" stroke-width="2"/><line x1="20" y1="40" x2="200" y2="40" stroke="#f59e0b" stroke-width="2" stroke-dasharray="8,4"/><text x="65" y="15" fill="#0f172a" font-size="11" font-weight="bold">Road 2-Lane (7.0m)</text></svg>""",
    },
    {
        "id": "IfcBridge",
        "class_name": "IfcBridge",
        "name_th": "สะพานคอนกรีต / โครงสร้างสะพาน (Bridge Structure)",
        "discipline": "Civil",
        "schema_version": "IFC4.3",
        "description": "สะพาน ค.ส.ล. / คอนกรีตอัดแรง ประกอบด้วยตอม่อสะพาน คานสะพาน (Girder) และพื้นสะพาน",
        "predefined_types": ["GIRDER", "SUSPENSION", "USERDEFINED"],
        "bsdd_psets": ["Pset_BridgeCommon"],
        "debim_yaml": """- tag: BRIDGE-01
  class: IfcBridge
  span_length: 20.0
  deck_width: 9.0
  deck_thickness: 0.25
  pier_height: 6.0""",
        "ifc_step": """#1401=IFCBRIDGE('5yS4$xUN4c6t3W5h7I8j0K',#102,'BRIDGE-01','RC Bridge',$,#1403,#1404,$,.GIRDER.);""",
        "qto_boq": [
            {
                "code": "BRID-DECK",
                "name": "คอนกรีตพื้นสะพานอัดแรง 350 ksc (Bridge Deck Slab)",
                "formula": "20.0m × 9.0m × 0.25m",
                "unit": "m3",
                "quantity": 45.0,
                "mat_rate": 2800.0,
                "labor_rate": 550.0,
            }
        ],
        "thai_specs": {
            "materials": "คอนกรีตโครงสร้างอัดแรงแรงอัดไม่น้อยกว่า 350 ksc คานพรีสเตสลวดอัดแรง PC Strand 15.2 mm",
            "workmanship": "ยกติดตั้งคานสะพานด้วยเครนขนาดใหญ่ ยึดแผ่นลูกยางรองสะพาน (Elastomeric Bearing Pad)",
            "testing": "ทดสอบการรับน้ำหนักบรรทุกทดสอบสะพาน (Bridge Proof Load Test) และวัดค่าการแอ่นตัว (Deflection)",
        },
        "sample_3d": {
            "shape": "box",
            "width": 12.0,
            "depth": 9.0,
            "height": 0.25,
            "color": "#94A3B8",
        },
        "sample_2d_svg": """<svg viewBox="0 0 240 100" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="30" width="200" height="15" fill="#94a3b8" stroke="#0f172a" stroke-width="2"/><rect x="50" y="45" width="20" height="40" fill="#64748b"/><rect x="170" y="45" width="20" height="40" fill="#64748b"/><text x="80" y="20" fill="#0f172a" font-size="11" font-weight="bold">RC Bridge Span 20m</text></svg>""",
    },
    {
        "id": "IfcEarthworksElement",
        "class_name": "IfcEarthworksElement",
        "name_th": "งานดินขุดและงานดินถม (Earthworks Cut & Fill)",
        "discipline": "Civil",
        "schema_version": "IFC4.3",
        "description": "ปริมาตรงานปรับระดับดิน ดินขุดฐานราก (Cut) และดินถมบดแน่น (Fill)",
        "predefined_types": ["EXCAVATION", "EMBANKMENT", "CUT", "FILL"],
        "bsdd_psets": ["Pset_EarthworksElementCommon"],
        "debim_yaml": """- tag: EW-CUT-01
  class: IfcEarthworksElement
  predefined_type: CUT
  width: 10.0
  length: 15.0
  depth: 2.0""",
        "ifc_step": """#1450=IFCEARTHWORKSELEMENT('6zT5$yVO5d7u4X6i8J9k1L',#102,'EW-CUT-01','Site Cut',$,#1451,#1452,$,.CUT.);""",
        "qto_boq": [
            {
                "code": "EW-CUT",
                "name": "งานขุดปรับระดับดินและขนย้ายออกภายนอก",
                "formula": "10.0m × 15.0m × 2.0m",
                "unit": "m3",
                "quantity": 300.0,
                "mat_rate": 0.0,
                "labor_rate": 85.0,
            }
        ],
        "thai_specs": {
            "materials": "ดินถมคัดเลือกคุณภาพปลอดเศษขยะและรากไม้ ค่า CBR ไม่น้อยกว่า 6%",
            "workmanship": "ขุดปรับระดับด้วยรถแบคโฮ ถมดินเป็นชั้นๆ หนาไม่เกิน 30 ซม. บดแน่นด้วยรถบดตีนแกะ",
            "testing": "ทดสอบความแน่นของชั้นดินถม (Sand Cone Field Density Test) ไม่น้อยกว่า 95% Standard Proctor",
        },
        "sample_3d": {
            "shape": "box",
            "width": 10.0,
            "depth": 15.0,
            "height": 2.0,
            "color": "#D97706",
        },
        "sample_2d_svg": """<svg viewBox="0 0 200 100" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><polygon points="20,20 180,20 160,80 40,80" fill="#fef3c7" stroke="#d97706" stroke-width="2"/><text x="65" y="55" fill="#0f172a" font-size="11" font-weight="bold">Excavation Cut 300m3</text></svg>""",
    },
    {
        "id": "IfcRetainingWall",
        "class_name": "IfcRetainingWall",
        "name_th": "กำแพงกันดิน ค.ส.ล. (Retaining Wall)",
        "discipline": "Civil",
        "schema_version": "IFC4.3",
        "description": "โครงสร้างกำแพงกันดิน ค.ส.ล. ป้องกันการพังทลายของดินขอบคันทางหรือลาดดิน",
        "predefined_types": ["CANTILEVER", "GRAVITY", "ANCHORED"],
        "bsdd_psets": ["Pset_RetainingWallCommon"],
        "debim_yaml": """- tag: RW1
  class: IfcRetainingWall
  predefined_type: CANTILEVER
  length: 12.0
  stem_height: 3.0
  stem_thickness: 0.30
  footing_base_width: 1.80
  reinforcement:
    stem_vertical: DB16@0.15
    stem_horizontal: DB12@0.20
    base_bottom: DB16@0.15""",
        "ifc_step": """#1501=IFCRETAININGWALL('7aU6$zWP6e8v5Y7j9K0l2M',#102,'RW1','Cantilever Retaining Wall',$,#1503,#1504,$,.CANTILEVER.);
#1510=IFCREINFORCINGBAR('7bV7$aXQ7f9w6Z8k0L1m3N',#102,'RW1-STEM','Stem Vertical Rebar DB16@0.15',$,#1503,$,$,.MAIN.,16.,$,3.2,$,$);
#1511=IFCREINFORCINGBAR('7cW8$bYR8g0x7A9l1M2n4O',#102,'RW1-BASE','Base Mat Rebar DB16@0.15',$,#1503,$,$,.MAIN.,16.,$,1.8,$,$);""",
        "qto_boq": [
            {
                "code": "CONC-RW",
                "name": "คอนกรีตกำแพงกันดิน 280 ksc",
                "formula": "12.0m × (0.3×3.0 + 1.8×0.4)",
                "unit": "m3",
                "quantity": 19.44,
                "mat_rate": 2400.0,
                "labor_rate": 450.0,
            },
            {
                "code": "REBAR-DB16",
                "name": "เหล็กเสริมหลักกำแพงกันดิน DB16@0.15m (Stem & Footing)",
                "formula": "12.0m × (3.2m + 1.8m)/0.15 × 1.58 kg/m",
                "unit": "kg",
                "quantity": 632.0,
                "mat_rate": 32.0,
                "labor_rate": 5.0,
            },
            {
                "code": "REBAR-DB12",
                "name": "เหล็กเสริมแนวนอนกำแพงกันดิน DB12@0.20m",
                "formula": "15 เส้น × 12.0m × 0.888 kg/m",
                "unit": "kg",
                "quantity": 159.84,
                "mat_rate": 32.0,
                "labor_rate": 5.0,
            },
        ],
        "thai_specs": {
            "materials": "คอนกรีตผสมเสร็จ 280 ksc เหล็กเสริม SD40 ท่อระบายน้ำทิ้งพีวีซี Ø 2 นิ้ว ระบายน้ำหลังกำแพง",
            "workmanship": "จัดทำช่องระบายน้ำ (Weep Holes) ทุกระยะ 1.50 ม. ปูแผ่นใยสังเคราะห์กั้นดิน (Geotextile Filter)",
            "testing": "ตรวจสอบเสถียรภาพการเลื่อนไถล (Sliding) และการพลิกคว่ำ (Overturning) ตามหลักวิศวกรรมปฐพี",
        },
        "sample_3d": {
            "shape": "box",
            "width": 12.0,
            "depth": 1.80,
            "height": 3.0,
            "color": "#64748B",
            "is_reinforced_concrete": True,
            "rebar_type": "retaining_wall",
        },
        "sample_2d_svg": """<svg viewBox="0 0 160 140" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><path d="M 40 20 L 70 20 L 70 100 L 130 100 L 130 120 L 20 120 L 20 100 L 40 100 Z" fill="#94a3b8" stroke="#0f172a" stroke-width="2"/><text x="45" y="70" fill="#0f172a" font-size="10" font-weight="bold">Cantilever RW</text></svg>""",
    },
]


def _load_template_html() -> str:
    """Load HTML template from src/debim/docs/templates/directory.html."""
    tmpl_path = Path(__file__).parent / "templates" / "directory.html"
    if tmpl_path.exists():
        return tmpl_path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Class Directory HTML template not found at {tmpl_path}")


def generate_class_directory_html(classes_data: Optional[List[Dict[str, Any]]] = None) -> str:
    """
    Generate interactive standalone Class Directory & Encyclopedia HTML string.
    Zero runtime npm/node dependencies.
    """
    data = classes_data or DEFAULT_CLASS_DIRECTORY_DATA
    json_payload = json.dumps(data, ensure_ascii=False)

    template_html = _load_template_html()
    html_content = template_html.replace("__CLASS_DIRECTORY_JSON__", json_payload)
    return html_content


def export_class_directory(
    output_path: Union[Path, str] = "dist/class_directory.html",
    classes_data: Optional[List[Dict[str, Any]]] = None,
) -> Path:
    """
    Export Class Directory HTML webpage to output path.
    """
    import shutil

    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    html_content = generate_class_directory_html(classes_data)
    out_p.write_text(html_content, encoding="utf-8")

    # Ensure Farnsworth House viewer is bundled alongside for working live link
    farnsworth_src = Path(__file__).resolve().parent.parent.parent.parent / "examples" / "farnsworth_house" / "viewer.html"
    if not farnsworth_src.exists():
        farnsworth_src = Path("examples/farnsworth_house/viewer.html")
    if farnsworth_src.exists():
        try:
            target_farnsworth = out_p.parent / "farnsworth.html"
            shutil.copyfile(farnsworth_src, target_farnsworth)
        except Exception:
            pass

    return out_p
