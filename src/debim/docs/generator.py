"""
Interactive Class Directory & Encyclopedia Generator for debim.
Compiles 6-dimensional interactive webpage for BIM element classes across Structure, Architecture, MEP, and Civil.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml

from debim.docs.exemplar import generate_exemplar_element, get_supported_exemplar_classes
from debim.docs.thai_specs import get_thai_spec_clause
from debim.schema_registry import SchemaEntityRegistry

# Canonical Discipline Definitions
CIVIL_CLASSES = {
    "IfcAlignment", "IfcRoad", "IfcBridge", "IfcBridgePart", "IfcRailway", "IfcRailwayPart",
    "IfcTrackElement", "IfcCivilElement", "IfcEarthworksElement", "IfcEarthworksCut",
    "IfcEarthworksFill", "IfcGeotechnicalStratum", "IfcSoil", "IfcRetainingWall",
    "IfcGeographicElement", "IfcMarineFacility", "IfcMarinePart", "IfcMooringDevice",
    "IfcNavigationElement", "IfcBearing"
}

STRUCTURE_CLASSES = {
    "IfcBeam", "IfcBeamStandardCase", "IfcColumn", "IfcColumnStandardCase",
    "IfcFooting", "IfcPile", "IfcPlate", "IfcPlateStandardCase",
    "IfcMember", "IfcMemberStandardCase", "IfcReinforcingBar", "IfcReinforcingElement",
    "IfcReinforcingMesh", "IfcSlab", "IfcSlabElementedCase", "IfcSlabStandardCase",
    "IfcTendon", "IfcTendonAnchor", "IfcVibrationIsolator", "IfcDiscreteAccessory",
    "IfcMechanicalFastener", "IfcFastener"
}

ARCH_CLASSES = {
    "IfcWall", "IfcWallElementedCase", "IfcWallStandardCase", "IfcDoor", "IfcDoorStandardCase",
    "IfcWindow", "IfcWindowStandardCase", "IfcRoof", "IfcCurtainWall", "IfcCovering",
    "IfcStair", "IfcStairFlight", "IfcRamp", "IfcRampFlight", "IfcRailing",
    "IfcFurniture", "IfcFurnishingElement", "IfcSystemFurnitureElement", "IfcChimney",
    "IfcBuildingElementPart", "IfcBuildingElementProxy", "IfcShadingDevice",
    "IfcElementAssembly", "IfcTransportElement", "IfcVirtualElement", "IfcCustomElement"
}


def _get_discipline(class_name: str) -> str:
    """Classify IFC entity class name into canonical discipline."""
    if class_name in CIVIL_CLASSES:
        return "Civil"
    if class_name in STRUCTURE_CLASSES:
        return "Structure"
    if class_name in ARCH_CLASSES:
        return "Architecture"
    return "MEP"


def _get_thai_title(class_name: str, discipline: str) -> str:
    """Generate descriptive Thai title for an IFC entity class."""
    titles = {
        # Structure
        "IfcColumn": "เสาคอนกรีตเสริมเหล็ก / เสาเหล็ก (Structural Column)",
        "IfcColumnStandardCase": "เสามาตรฐานตามมาตรฐาน มอก./AISC (Standard Column)",
        "IfcBeam": "คานคอนกรีตเสริมเหล็ก / คานเหล็ก (Structural Beam)",
        "IfcBeamStandardCase": "คานมาตรฐานตามมาตรฐาน มอก./AISC (Standard Beam)",
        "IfcSlab": "แผ่นพื้นคอนกรีตเสริมเหล็ก / พื้นสำเร็จรูป (Floor Slab)",
        "IfcSlabStandardCase": "แผ่นพื้นคอนกรีตมาตรฐาน (Standard Slab)",
        "IfcSlabElementedCase": "แผ่นพื้นประกอบชิ้นส่วน (Elemented Slab)",
        "IfcFooting": "ฐานรากอาคาร (Foundation Footing)",
        "IfcPile": "เสาเข็มฐานราก (Foundation Pile)",
        "IfcPlate": "แผ่นเหล็กโครงสร้าง / แผ่นเพลท (Steel Plate)",
        "IfcPlateStandardCase": "แผ่นเพลทมาตรฐาน (Standard Plate)",
        "IfcMember": "ชิ้นส่วนโครงสร้าง / โครงข้อหมุน (Structural Member)",
        "IfcMemberStandardCase": "ชิ้นส่วนโครงสร้างมาตรฐาน (Standard Member)",
        "IfcReinforcingBar": "เหล็กเส้นเสริมคอนกรีต (Reinforcing Rebar)",
        "IfcReinforcingElement": "องค์ประกอบเหล็กเสริม (Reinforcing Element)",
        "IfcReinforcingMesh": "ตะแกรงเหล็กเสริมคอนกรีต (Reinforcing Wire Mesh)",
        "IfcTendon": "ลวดอัดแรงโครงสร้าง ค.ส.ล. (Prestressing Tendon)",
        "IfcTendonAnchor": "สมอยึดลวดอัดแรง (Tendon Anchor)",
        "IfcVibrationIsolator": "อุปกรณ์กันสั่นสะเทือนโครงสร้าง (Vibration Isolator)",
        "IfcDiscreteAccessory": "อุปกรณ์ฝังฝากและฟิตติ้งโครงสร้าง (Discrete Accessory)",
        "IfcMechanicalFastener": "สลักเกลียวและน็อตยึดโครงสร้าง (Mechanical Fastener)",
        "IfcFastener": "อุปกรณ์ยึดต่อโครงสร้าง (Fastener)",

        # Architecture
        "IfcWall": "ผนังอาคาร (Architectural Wall)",
        "IfcWallStandardCase": "ผนังคอนกรีต/ก่ออิฐมาตรฐาน (Standard Wall)",
        "IfcWallElementedCase": "ผนังสำเร็จรูปประกอบ (Elemented Wall)",
        "IfcDoor": "ประตูอาคาร (Door Assembly)",
        "IfcDoorStandardCase": "ประตูบานมาตรฐาน (Standard Door)",
        "IfcWindow": "หน้าต่างอาคาร (Window Assembly)",
        "IfcWindowStandardCase": "หน้าต่างบานมาตรฐาน (Standard Window)",
        "IfcRoof": "หลังคาและโครงหลังคา (Roof Assembly)",
        "IfcCurtainWall": "ผนังกระจกโชว์รูม / ผนังเคอร์เทนวอลล์ (Curtain Wall)",
        "IfcCovering": "วัสดุปูผิว / ฝ้าเพดาน (Finishes & Ceiling)",
        "IfcStair": "บันไดอาคาร (Stair Assembly)",
        "IfcStairFlight": "ช่วงบันได (Stair Flight)",
        "IfcRamp": "ทางลาดอาคาร (Ramp Assembly)",
        "IfcRampFlight": "ช่วงทางลาด (Ramp Flight)",
        "IfcRailing": "ราวกันตก / ราวบันได (Railing Guard)",
        "IfcFurniture": "เฟอร์นิเจอร์และครุภัณฑ์ (Furniture)",
        "IfcFurnishingElement": "องค์ประกอบตกแต่งภายใน (Furnishing Element)",
        "IfcSystemFurnitureElement": "เฟอร์นิเจอร์ระบบสำนักงาน (System Furniture)",
        "IfcChimney": "ปล่องควันและช่องระบายอากาศ (Chimney Structure)",
        "IfcShadingDevice": "อุปกรณ์แผงบังแดด (Shading Device)",
        "IfcBuildingElementPart": "ชิ้นส่วนส่วนประกอบอาคาร (Building Element Part)",
        "IfcBuildingElementProxy": "องค์อาคารจำลองอเนกประสงค์ (Generic Element Proxy)",
        "IfcElementAssembly": "ชุดประกอบอาคาร (Element Assembly)",
        "IfcTransportElement": "ระบบสัญจรแนวดิ่ง เช่น ลิฟต์/บันไดเลื่อน (Transport Element)",

        # MEP
        "IfcPipeSegment": "ท่อประปา / ท่อน้ำทิ้ง-โสโครก (Plumbing Pipe)",
        "IfcPipeFitting": "ข้อต่อท่อประปาและท่อน้ำทิ้ง (Pipe Fitting)",
        "IfcDuctSegment": "ท่อลมระบบปรับอากาศ (HVAC Duct Segment)",
        "IfcDuctFitting": "ข้อต่อท่อลมระบายอากาศ (Duct Fitting)",
        "IfcDuctSilencer": "อุปกรณ์เก็บเสียงท่อลม (Duct Silencer)",
        "IfcAirTerminal": "หัวจ่ายลม / พัดลมดูดอากาศ (Air Terminal)",
        "IfcAirTerminalBox": "กล่องควบคุมปริมาณลม VAV (Air Terminal Box)",
        "IfcAirToAirHeatRecovery": "เครื่องแลกเปลี่ยนความร้อนความเย็น (Heat Recovery)",
        "IfcSanitaryTerminal": "สุขภัณฑ์และอุปกรณ์ห้องน้ำ (Sanitary Fixture)",
        "IfcWasteTerminal": "ตะแกรงน้ำทิ้งและช่องระบายน้ำ (Waste Terminal)",
        "IfcLightFixture": "โคมไฟฟ้าและดวงโคม (Lighting Fixture)",
        "IfcLamp": "หลอดไฟและไดร์เวอร์ (Lamp Source)",
        "IfcOutlet": "เต้ารับไฟฟ้า / สวิตช์ไฟ (Power Outlet & Socket)",
        "IfcSwitchingDevice": "สวิตช์เปิด-ปิดไฟ (Switching Device)",
        "IfcDistributionBoard": "ตู้ควบคุมไฟฟ้า / ตู้โหลดเซ็นเตอร์ (Distribution Panel)",
        "IfcElectricDistributionBoard": "ตู้ควบคุมระบบไฟฟ้าเมน MDB/DB (Electric Distribution Board)",
        "IfcCableCarrierSegment": "รางรางร้อยสายไฟ / รางเทรย์ (Cable Carrier Segment)",
        "IfcCableCarrierFitting": "ข้อต่อรางร้อยสายไฟ (Cable Carrier Fitting)",
        "IfcCableSegment": "สายไฟฟ้าและสายสัญญาณ (Electric Cable Segment)",
        "IfcCableFitting": "ข้อต่อสายไฟและกล่องต่อสาย (Cable Fitting)",
        "IfcDamper": "แดมเปอร์ปรับปริมาณลม / วาล์วกันไฟ (Duct Damper)",
        "IfcFlowController": "อุปกรณ์ควบคุมการไหลของน้ำ/ลม (Flow Controller)",
        "IfcUnitaryEquipment": "เครื่องปรับอากาศแบบแยกส่วน (Unitary AC Equipment)",
        "IfcPump": "เครื่องสูบน้ำและปั๊มน้ำประปา (Water Pump)",
        "IfcBoiler": "เครื่องกำเนิดน้ำร้อน / บอยเลอร์ (Hot Water Boiler)",
        "IfcChiller": "เครื่องทำน้ำเย็นปรับอากาศ (Water Chiller)",
        "IfcFan": "พัดลมระบายอากาศและพัดลมเติมอากาศ (Ventilation Fan)",
        "IfcTank": "ถังเก็บน้ำประปาและถังสำรองน้ำ (Storage Water Tank)",
        "IfcValve": "วาล์วเปิด-ปิดน้ำและวาล์วควบคุม (Plumbing Valve)",
        "IfcSensor": "เซ็นเซอร์ตรวจวัดและอุปกรณ์ตรวจจับ (Sensor Device)",
        "IfcAlarm": "อุปกรณ์ส่งสัญญาณแจ้งเตือนภัย (Alarm Device)",
        "IfcFlowMeter": "มิเตอร์วัดปริมาณการไหล (Flow Meter)",
        "IfcTransformer": "หม้อแปลงไฟฟ้าแรงสูง/แรงต่ำ (Power Transformer)",
        "IfcElectricGenerator": "เครื่องกำเนิดไฟฟ้าสำรอง (Electric Generator)",
        "IfcElectricMotor": "มอเตอร์ไฟฟ้าขับเคลื่อน (Electric Motor)",

        # Civil
        "IfcAlignment": "แนวสายทางโครงการ (Civil Alignment)",
        "IfcRoad": "ถนนและโครงสร้างชั้นทาง (Road Structure)",
        "IfcBridge": "สะพานคอนกรีต / โครงสร้างสะพาน (Bridge Structure)",
        "IfcBridgePart": "ชิ้นส่วนสะพาน เช่น คาน/ตอม่อ (Bridge Part)",
        "IfcRailway": "ทางรถไฟและระบบราง (Railway Infrastructure)",
        "IfcRailwayPart": "ส่วนประกอบโครงสร้างทางรถไฟ (Railway Part)",
        "IfcTrackElement": "รางรถไฟและหมอนรองราง (Railway Track Element)",
        "IfcCivilElement": "องค์อาคารงานโยธาและสาธารณูปโภค (Civil Infrastructure Element)",
        "IfcEarthworksElement": "งานดินขุดและงานดินถม (Earthworks Element)",
        "IfcEarthworksCut": "งานขุดดินปรับระดับ (Earthworks Cut)",
        "IfcEarthworksFill": "งานถมดินบดแน่น (Earthworks Fill)",
        "IfcGeotechnicalStratum": "ชั้นดินทางปฐพีวิศวกรรม (Geotechnical Stratum)",
        "IfcSoil": "ชั้นมวลดินและวัสดุดิน (Soil Element)",
        "IfcRetainingWall": "กำแพงกันดิน ค.ส.ล. (Retaining Wall)",
        "IfcGeographicElement": "องค์ประกอบภูมิประเทศและงานภูมิทัศน์ (Geographic Element)",
        "IfcMarineFacility": "ท่าเรือและสิ่งก่อสร้างทางน้ำ (Marine Facility)",
        "IfcMarinePart": "ชิ้นส่วนโครงสร้างทางน้ำ/เขื่อนกันคลื่น (Marine Part)",
        "IfcMooringDevice": "หลักผูกเรือและอุปกรณ์เทียบเรือ (Mooring Device)",
        "IfcNavigationElement": "เครื่องหมายการเดินเรือและทุ่นไฟ (Navigation Element)",
        "IfcBearing": "แผ่นยางรองรับสะพาน (Structural Bearing Pad)",
    }
    if class_name in titles:
        return titles[class_name]

    clean_cls = class_name.replace("Ifc", "")
    return f"{clean_cls} ({discipline} Component)"


def _get_description(class_name: str, discipline: str) -> str:
    """Generate concise functional description in Thai for an IFC entity class."""
    clean_cls = class_name.replace("Ifc", "")
    if discipline == "Structure":
        return f"องค์อาคารโครงสร้าง {clean_cls} รองรับและถ่ายน้ำหนักบรรทุกตามหลักวิศวกรรมโครงสร้าง"
    elif discipline == "Architecture":
        return f"องค์อาคารสถาปัตยกรรม {clean_cls} กำหนดสัดส่วนพื้นที่ ใช้ประโยชน์ และตกแต่งอาคาร"
    elif discipline == "Civil":
        return f"โครงสร้างงานโยธาและสาธารณูปโภค {clean_cls} รองรับการคมนาคมและงานปฐพีวิศวกรรม"
    else:
        return f"อุปกรณ์และระบบวิศวกรรมประกอบอาคาร {clean_cls} สำหรับงานระบบ MEP"


def _generate_3d_payload(class_name: str, discipline: str) -> Dict[str, Any]:
    """Generate sample_3d payload with realistic geometric dimensions and color scheme."""
    c = class_name.lower()

    if "column" in c:
        return {"shape": "box", "width": 0.30, "depth": 0.30, "height": 3.50, "color": "#64748B", "is_reinforced_concrete": True, "rebar_type": "column"}
    elif "beam" in c:
        return {"shape": "box", "width": 4.00, "depth": 0.20, "height": 0.40, "color": "#475569", "is_reinforced_concrete": True, "rebar_type": "beam"}
    elif "slab" in c or "plate" in c:
        return {"shape": "box", "width": 4.00, "depth": 4.00, "height": 0.15, "color": "#94A3B8", "is_reinforced_concrete": True, "rebar_type": "slab"}
    elif "covering" in c:
        return {"shape": "covering", "width": 3.60, "depth": 3.60, "height": 0.10, "color": "#f8fafc"}
    elif "earthwork" in c or "soil" in c or "stratum" in c or "geotechnical" in c:
        return {"shape": "earthworks_embankment", "width": 6.00, "depth": 8.00, "height": 2.50, "color": "#d97706"}
    elif "retaining" in c or "geographic" in c:
        return {"shape": "retaining_structure", "width": 4.00, "depth": 2.50, "height": 3.00, "color": "#64748b", "is_reinforced_concrete": True, "rebar_type": "retaining_wall"}
    elif "footing" in c or "pile" in c:
        return {"shape": "deep_foundation", "width": 2.40, "depth": 2.40, "height": 4.00, "color": "#64748b", "is_reinforced_concrete": True, "rebar_type": "footing"}
    elif "tendon" in c:
        return {"shape": "tendon_anchor", "width": 0.40, "depth": 0.40, "height": 2.50, "color": "#f59e0b"}
    elif "fastener" in c or "accessory" in c:
        return {"shape": "structural_fastener", "width": 0.30, "depth": 0.30, "height": 0.40, "color": "#334155"}
    elif "vibration" in c:
        return {"shape": "vibration_isolator", "width": 0.50, "depth": 0.50, "height": 0.45, "color": "#0284c7"}
    elif "member" in c:
        return {"shape": "structural_member", "width": 0.20, "depth": 0.20, "height": 3.00, "color": "#475569"}
    elif "reinforcingmesh" in c:
        return {"shape": "reinforcing_mesh", "width": 2.00, "depth": 3.00, "height": 0.05, "color": "#f59e0b"}
    elif "reinforcing" in c:
        return {"shape": "reinforcing_bar", "diameter": 0.02, "length": 2.50, "height": 2.50, "color": "#f59e0b"}
    elif "pipe" in c or "conduit" in c or "cable" in c:
        return {"shape": "pipe", "radius": 0.025, "length": 5.0, "color": "#0284C7"}
    elif "duct" in c:
        return {"shape": "duct_assembly", "width": 2.4, "depth": 0.50, "height": 0.35, "color": "#cbd5e1"}
    elif "fan" in c or "heatrecovery" in c:
        return {"shape": "fan_assembly", "width": 1.2, "depth": 1.0, "height": 1.1, "color": "#0284c7"}
    elif "coolingtower" in c or "evaporativecooler" in c or "heatexchanger" in c:
        return {"shape": "cooling_tower", "width": 1.8, "depth": 1.8, "height": 2.4, "color": "#0284c7"}
    elif "coil" in c or "evaporator" in c or "condenser" in c:
        return {"shape": "coil_heat_exchanger", "width": 1.2, "depth": 0.40, "height": 0.80, "color": "#0284c7"}
    elif "filter" in c:
        return {"shape": "air_filter", "width": 0.60, "depth": 0.30, "height": 0.60, "color": "#cbd5e1"}
    elif "spaceheater" in c:
        return {"shape": "radiator_heater", "width": 1.0, "depth": 0.15, "height": 0.60, "color": "#f8fafc"}
    elif "burner" in c or "engine" in c:
        return {"shape": "combustion_burner", "width": 0.80, "depth": 0.50, "height": 0.50, "color": "#dc2626"}
    elif "firesuppression" in c or "stackterminal" in c:
        return {"shape": "fire_suppression", "width": 0.25, "depth": 0.25, "height": 0.35, "color": "#dc2626"}
    elif "transformer" in c or "electricgenerator" in c or "electricmotor" in c:
        return {"shape": "power_plant", "width": 1.6, "depth": 1.2, "height": 1.4, "color": "#475569"}
    elif "curtain" in c:
        return {"shape": "curtain_wall", "width": 4.00, "depth": 0.15, "height": 3.00, "color": "#38bdf8"}
    elif "shading" in c:
        return {"shape": "shading_device", "width": 2.40, "depth": 0.80, "height": 1.50, "color": "#64748b"}
    elif "wall" in c:
        return {"shape": "wall_system", "width": 4.00, "depth": 0.22, "height": 3.00, "color": "#cbd5e1"}
    elif "chimney" in c:
        return {"shape": "chimney", "width": 0.80, "depth": 0.80, "height": 4.50, "color": "#78350f"}
    elif "transport" in c:
        return {"shape": "transport_element", "width": 1.60, "depth": 1.80, "height": 2.60, "color": "#0284c7"}
    elif "door" in c:
        return {"shape": "door", "width": 0.9, "height": 2.1, "depth": 0.1, "color": "#78350F"}
    elif "window" in c:
        return {"shape": "window", "width": 1.5, "height": 1.2, "depth": 0.08, "color": "#0284C7"}
    elif "stairflight" in c or "stair_flight" in c:
        return {"shape": "stair_flight", "width": 1.2, "depth": 2.5, "height": 2.4, "steps": 10, "color": "#D4A373"}
    elif "stair" in c:
        return {"shape": "stair_concrete", "width": 1.2, "depth": 2.5, "height": 2.4, "steps": 10, "color": "#64748B", "is_reinforced_concrete": True, "rebar_type": "stair"}
    elif "ramp" in c:
        return {"shape": "ramp", "width": 1.5, "depth": 4.0, "height": 1.0, "color": "#94A3B8"}
    elif "railing" in c:
        return {"shape": "railing", "length": 3.0, "height": 1.0, "color": "#475569"}
    elif "roof" in c:
        return {"shape": "roof", "width": 6.0, "depth": 4.0, "height": 1.5, "color": "#B91C1C"}
    elif "furniture" in c or "furnish" in c:
        return {"shape": "furniture", "width": 1.4, "depth": 0.7, "height": 0.75, "color": "#A16207"}
    elif "pump" in c or "flowmovingdevice" in c:
        return {"shape": "pump", "width": 0.8, "depth": 0.45, "height": 0.55, "color": "#0284c7"}
    elif "valve" in c or "flowcontroller" in c:
        return {"shape": "valve", "width": 0.4, "depth": 0.25, "height": 0.45, "color": "#475569"}
    elif "sanitary" in c or "wasteterminal" in c:
        return {"shape": "sanitary_terminal", "width": 0.45, "depth": 0.65, "height": 0.80, "color": "#f8fafc"}
    elif "boiler" in c or "chiller" in c or "tank" in c or "energyconversion" in c or "compressor" in c:
        return {"shape": "equipment_vessel", "width": 1.4, "depth": 0.9, "height": 1.1, "color": "#0ea5e9"}
    elif "airterminal" in c or "damper" in c:
        return {"shape": "air_terminal", "width": 0.6, "depth": 0.6, "height": 0.2, "color": "#f1f5f9"}
    elif "lightfixture" in c or "lamp" in c:
        return {"shape": "light_fixture", "width": 0.60, "depth": 0.60, "height": 0.15, "color": "#fef08a"}
    elif "electricdistributionboard" in c or "distributionboard" in c or "electricappliance" in c:
        return {"shape": "electric_panel", "width": 0.60, "depth": 0.20, "height": 0.80, "color": "#475569"}
    elif "outlet" in c or "switchingdevice" in c or "sensor" in c:
        return {"shape": "outlet_switch", "width": 0.12, "depth": 0.04, "height": 0.12, "color": "#f8fafc"}
    elif "solardevice" in c or "solar" in c:
        return {"shape": "solar_panel", "width": 1.00, "depth": 1.60, "height": 0.15, "color": "#1e3a8a"}
    elif "junctionbox" in c:
        return {"shape": "junction_box", "width": 0.15, "depth": 0.15, "height": 0.10, "color": "#64748b"}
    elif "protectivedevice" in c:
        return {"shape": "circuit_breaker", "width": 0.18, "depth": 0.12, "height": 0.10, "color": "#f8fafc"}
    elif "alarm" in c:
        return {"shape": "alarm_device", "width": 0.15, "depth": 0.15, "height": 0.10, "color": "#dc2626"}
    elif "electricflowstoragedevice" in c or "flowstoragedevice" in c:
        return {"shape": "battery_storage", "width": 1.00, "depth": 0.80, "height": 2.00, "color": "#1e293b"}
    elif "bridge" in c or "bearing" in c:
        return {"shape": "bridge_structure", "width": 8.0, "depth": 4.0, "height": 3.50, "color": "#64748b"}
    elif "railway" in c or "trackelement" in c:
        return {"shape": "railway_infrastructure", "width": 3.0, "depth": 10.0, "height": 0.60, "color": "#78350f"}
    elif "road" in c or "alignment" in c:
        return {"shape": "road_infrastructure", "width": 7.0, "depth": 10.0, "height": 0.40, "color": "#334155"}
    elif "marine" in c or "mooringdevice" in c or "navigationelement" in c:
        return {"shape": "marine_facility", "width": 6.0, "depth": 8.0, "height": 2.50, "color": "#0284c7"}

    if discipline == "Structure":
        return {"shape": "box", "width": 1.0, "depth": 1.0, "height": 1.0, "color": "#64748B"}
    elif discipline == "Architecture":
        return {"shape": "box", "width": 1.0, "depth": 1.0, "height": 1.0, "color": "#CBD5E1"}
    elif discipline == "Civil":
        return {"shape": "box", "width": 2.0, "depth": 2.0, "height": 0.5, "color": "#D97706"}
    else:
        return {"shape": "box", "width": 0.50, "depth": 0.50, "height": 0.50, "color": "#0284C7"}


def _generate_2d_svg(class_name: str, discipline: str) -> str:
    """Generate representative 2D blueprint SVG diagram string."""
    clean_cls = class_name.replace("Ifc", "")
    if discipline == "Structure":
        return f'<svg viewBox="0 0 200 200" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="40" y="40" width="120" height="120" fill="#94a3b8" stroke="#0f172a" stroke-width="3"/><line x1="10" y1="100" x2="190" y2="100" stroke="#0284c7" stroke-width="1.5" stroke-dasharray="4,2"/><line x1="100" y1="10" x2="100" y2="190" stroke="#0284c7" stroke-width="1.5" stroke-dasharray="4,2"/><text x="50" y="30" fill="#0f172a" font-size="12" font-weight="bold">{clean_cls} Plan Cut</text></svg>'
    elif discipline == "Architecture":
        return f'<svg viewBox="0 0 240 100" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="30" width="200" height="40" fill="#cbd5e1" stroke="#0f172a" stroke-width="2"/><line x1="20" y1="50" x2="220" y2="50" stroke="#0f172a" stroke-dasharray="2,2"/><text x="75" y="22" fill="#0f172a" font-size="11" font-weight="bold">{clean_cls} Architectural Cut</text></svg>'
    elif discipline == "Civil":
        return f'<svg viewBox="0 0 240 100" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><rect x="20" y="20" width="200" height="50" fill="#475569" stroke="#0f172a" stroke-width="2"/><line x1="20" y1="45" x2="220" y2="45" stroke="#f59e0b" stroke-width="2" stroke-dasharray="8,4"/><text x="70" y="15" fill="#0f172a" font-size="11" font-weight="bold">{clean_cls} Corridor Plan</text></svg>'
    else:
        return f'<svg viewBox="0 0 200 100" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg"><circle cx="100" cy="50" r="30" fill="#e0f2fe" stroke="#0284c7" stroke-width="2"/><text x="60" y="15" fill="#0f172a" font-size="11" font-weight="bold">{clean_cls} MEP Element</text></svg>'


def _generate_qto_boq(class_name: str, discipline: str) -> List[Dict[str, Any]]:
    """Generate realistic takeoff line items with Thai unit rates and formulas."""
    clean_cls = class_name.replace("Ifc", "")
    code_prefix = clean_cls.upper()[:4]

    if discipline == "Structure":
        return [
            {
                "code": f"{code_prefix}-CONC",
                "name": f"คอนกรีตโครงสร้าง {clean_cls} 280 ksc",
                "formula": "Volume Calculation = 1.00 unit",
                "unit": "m3",
                "quantity": 1.0,
                "mat_rate": 2400.0,
                "labor_rate": 450.0,
            },
            {
                "code": f"{code_prefix}-FORM",
                "name": f"ไม้แบบโครงสร้าง {clean_cls} (Formwork)",
                "formula": "Formwork Area = 4.00 m2",
                "unit": "m2",
                "quantity": 4.0,
                "mat_rate": 320.0,
                "labor_rate": 180.0,
            },
        ]
    elif discipline == "Architecture":
        return [
            {
                "code": f"{code_prefix}-MAT",
                "name": f"งานประกอบและติดตั้ง {clean_cls}",
                "formula": "Area / Piece Count = 1.00 unit",
                "unit": "m2" if "Wall" in class_name or "Slab" in class_name else "set",
                "quantity": 1.0,
                "mat_rate": 1200.0,
                "labor_rate": 350.0,
            }
        ]
    elif discipline == "Civil":
        return [
            {
                "code": f"{code_prefix}-CIV",
                "name": f"งานก่อสร้างโยธา {clean_cls}",
                "formula": "Length / Area = 10.0 m",
                "unit": "m",
                "quantity": 10.0,
                "mat_rate": 850.0,
                "labor_rate": 250.0,
            }
        ]
    else:
        return [
            {
                "code": f"{code_prefix}-MEP",
                "name": f"งานติดตั้งอุปกรณ์ {clean_cls} พร้อมอุปกรณ์ประกอบ",
                "formula": "1.00 ชุด",
                "unit": "set",
                "quantity": 1.0,
                "mat_rate": 1500.0,
                "labor_rate": 400.0,
            }
        ]


def _synthesize_class_entry(class_name: str, registry: SchemaEntityRegistry) -> Dict[str, Any]:
    """
    Programmatically synthesize full 6-dimensional Class Directory & Encyclopedia record
    for any given IFC entity class name.
    """
    discipline = _get_discipline(class_name)
    schema_ver = "IFC4.3" if discipline == "Civil" else "IFC4"

    # Introspect metadata from SchemaEntityRegistry
    predefined_types = ["USERDEFINED", "NOTDEFINED"]
    bsdd_psets = [f"Pset_{class_name.replace('Ifc', '')}Common"]

    if registry.validate_entity_type(class_name):
        info = registry.get_entity_info(class_name)
        if info.allowed_predefined_types:
            predefined_types = list(info.allowed_predefined_types)
        if info.default_psets:
            bsdd_psets = list(info.default_psets)

    # Dimension 1: Declarative .debim YAML
    golden_file = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "golden_entities" / f"{class_name}.yaml"
    if not golden_file.exists():
        golden_file = Path("tests/fixtures/golden_entities") / f"{class_name}.yaml"

    if golden_file.exists():
        debim_yaml = golden_file.read_text(encoding="utf-8")
    else:
        elem_data = generate_exemplar_element(class_name)
        debim_yaml = yaml.safe_dump([elem_data], allow_unicode=True, sort_keys=False)

    # Dimension 2: IFC STEP
    clean_cls = class_name.replace("Ifc", "")
    ifc_step = f"#{1001}=IFCPRODUCTDEFINITIONSHAPE($,$,(#{1002}));\n#{1002}=IFCSHAPEREPRESENTATION(#{1003},'Body','SweptSolid',(#{1004}));\n#{1005}={class_name.upper()}('1aB2$cCd3E4f5G6h7I8j9K',#101,'{clean_cls}-01','Exemplar {clean_cls}',$,#103,#1001,$);"

    # Dimension 6: Thai Specifications Clause
    spec_clause = get_thai_spec_clause(class_name)
    thai_specs = {
        "materials": spec_clause.material_standards,
        "workmanship": spec_clause.workmanship_requirements,
        "testing": spec_clause.testing_inspection,
    }

    return {
        "id": class_name,
        "class_name": class_name,
        "name_th": _get_thai_title(class_name, discipline),
        "discipline": discipline,
        "schema_version": schema_ver,
        "description": _get_description(class_name, discipline),
        "predefined_types": predefined_types,
        "bsdd_psets": bsdd_psets,
        "debim_yaml": debim_yaml,
        "ifc_step": ifc_step,
        "qto_boq": _generate_qto_boq(class_name, discipline),
        "sample_3d": _generate_3d_payload(class_name, discipline),
        "sample_2d_svg": _generate_2d_svg(class_name, discipline),
        "thai_specs": thai_specs,
    }


def generate_all_class_directory_data() -> List[Dict[str, Any]]:
    """
    Generate dataset covering all 125+ IFC physical element classes
    discovered in tests/fixtures/golden_entities/*.yaml and SchemaEntityRegistry.
    """
    registry = SchemaEntityRegistry("IFC4")
    supported_classes = get_supported_exemplar_classes()

    data_list = []
    for cls_name in supported_classes:
        entry = _synthesize_class_entry(cls_name, registry)
        data_list.append(entry)

    return data_list


DEFAULT_CLASS_DIRECTORY_DATA: List[Dict[str, Any]] = generate_all_class_directory_data()


def _load_template_html() -> str:
    """
    Load HTML template, styles, and builder partials from src/debim/docs/templates/
    and assemble them into a unified standalone HTML template string.
    """
    tmpl_dir = Path(__file__).parent / "templates"
    tmpl_path = tmpl_dir / "directory.html"
    styles_path = tmpl_dir / "styles.css"
    builders_dir = tmpl_dir / "builders"

    if not tmpl_path.exists():
        raise FileNotFoundError(f"Class Directory HTML template not found at {tmpl_path}")

    html_content = tmpl_path.read_text(encoding="utf-8")

    # Load and inject CSS styles
    css_content = styles_path.read_text(encoding="utf-8") if styles_path.exists() else ""
    html_content = html_content.replace("__INJECT_CSS__", css_content)

    # Load and concatenate builder scripts in deterministic order
    builder_files = [
        "builders_struct.js",
        "builders_arch.js",
        "builders_mep.js",
        "builders_civil.js",
    ]
    builders_js_list = []
    for bf in builder_files:
        bf_path = builders_dir / bf
        if bf_path.exists():
            builders_js_list.append(bf_path.read_text(encoding="utf-8"))

    builders_content = "\n\n".join(builders_js_list)
    html_content = html_content.replace("__INJECT_BUILDERS__", builders_content)

    return html_content


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
