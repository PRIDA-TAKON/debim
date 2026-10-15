#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thai Construction Material Price Searcher (yotathai.com / TPSO Ministry of Commerce)
Created for Antigravity AI Agent Skill.
"""

import sys
import os
import json
import urllib.request
import ssl
import argparse
from datetime import datetime

# Ensure utf-8 stdout on Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
API_BASE = 'https://app.yotathai.com/mat/api/tpso'

PROVINCE_ALIAS = {
    'กทม': '10',
    'กรุงเทพ': '10',
    'กรุงเทพมหานคร': '10',
    'ส่วนกลาง': '10',
    'กลาง': '10',
    'อยุธยา': '14',
    'พระนครศรีอยุธยา': '14',
    'อ่างทอง': '15',
    'ลพบุรี': '16',
    'สิงห์บุรี': '17',
    'ชัยนาท': '18',
    'สระบุรี': '19',
    'ชลบุรี': '20',
    'ระยอง': '21',
    'จันทบุรี': '22',
    'ตราด': '23',
    'ฉะเชิงเทรา': '24',
    'แปดริ้ว': '24',
    'ปราจีนบุรี': '25',
    'นครนายก': '26',
    'สระแก้ว': '27',
    'โคราช': '30',
    'นครราชสีมา': '30',
    'บุรีรัมย์': '31',
    'สุรินทร์': '32',
    'ศรีสะเกษ': '33',
    'อุบลราชธานี': '34',
    'อุบล': '34',
    'ยโสธร': '35',
    'ชัยภูมิ': '36',
    'อำนาจเจริญ': '37',
    'บึงกาฬ': '38',
    'หนองบัวลำภู': '39',
    'ขอนแก่น': '40',
    'อุดรธานี': '41',
    'อุดร': '41',
    'เลย': '42',
    'หนองคาย': '43',
    'มหาสารคาม': '44',
    'ร้อยเอ็ด': '45',
    'กาฬสินธุ์': '46',
    'สกลนคร': '47',
    'นครพนม': '48',
    'มุกดาหาร': '49',
    'เชียงใหม่': '50',
    'ลำพูน': '51',
    'ลำปาง': '52',
    'อุตรดิตถ์': '53',
    'แพร่': '54',
    'น่าน': '55',
    'พะเยา': '56',
    'เชียงราย': '57',
    'แม่ฮ่องสอน': '58',
    'นครสวรรค์': '60',
    'อุทัยธานี': '61',
    'กำแพงเพชร': '62',
    'ตาก': '63',
    'สุโขทัย': '64',
    'พิษณุโลก': '65',
    'พิจิตร': '66',
    'เพชรบูรณ์': '67',
    'ราชบุรี': '70',
    'กาญจนบุรี': '71',
    'สุพรรณบุรี': '72',
    'นครปฐม': '73',
    'สมุทรสาคร': '74',
    'สมุทรสงคราม': '75',
    'เพชรบุรี': '76',
    'ประจวบคีรีขันธ์': '77',
    'ประจวบ': '77',
    'นครศรีธรรมราช': '80',
    'กระบี่': '81',
    'พังงา': '82',
    'ภูเก็ต': '83',
    'สุราษฎร์ธานี': '84',
    'สุราษฎร์': '84',
    'ระนอง': '85',
    'ชุมพร': '86',
    'สงขลา': '90',
    'หาดใหญ่': '90',
    'สตูล': '91',
    'ตรัง': '92',
    'พัทลุง': '93',
    'ปัตตานี': '94',
    'ยะลา': '95',
    'นราธิวาส': '96'
}

def get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def resolve_province_code(name_or_code):
    if not name_or_code:
        return '10', 'ส่วนกลาง (กรุงเทพฯ)'
    cleaned = name_or_code.strip()
    if cleaned.isdigit():
        return cleaned, f'รหัส {cleaned}'
    for alias, code in PROVINCE_ALIAS.items():
        if alias in cleaned:
            return code, alias
    return '10', 'ส่วนกลาง (กรุงเทพฯ) [Default]'

def fetch_data(year, month, prov_code):
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f'cmi_{prov_code}_{year}_{month:02d}.json')
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass

    payload = json.dumps({'year': int(year), 'month': int(month), 'type': int(prov_code)}).encode('utf-8')
    req = urllib.request.Request(
        f'{API_BASE}/CmiPrice/Month',
        data=payload,
        headers={'User-Agent': 'Mozilla/5.0 (Antigravity AI)', 'Content-Type': 'application/json'}
    )
    
    try:
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and isinstance(data, list):
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
                return data
    except Exception as e:
        print(f"[Warning] Failed to fetch live data: {e}", file=sys.stderr)
    return []

def search_materials(query, year=2567, month=6, province='10', limit=20):
    prov_code, prov_name = resolve_province_code(province)
    data = fetch_data(year, month, prov_code)
    
    if not data:
        # Fallback try month 1 of same year if month had no data
        if month != 1:
            data = fetch_data(year, 1, prov_code)
            if data:
                month = 1
                
    if not data:
        return {'status': 'error', 'message': f'ไม่พบข้อมูลราคาของรหัสจังหวัด {prov_code} ปี {year} เดือน {month}', 'results': []}

    terms = [t.strip().lower() for t in query.split() if t.strip()]
    matches = []
    
    for item in data:
        name = item.get('commodityNameTH', '')
        name_lower = name.lower()
        if all(t in name_lower for t in terms):
            matches.append({
                'id': item.get('id'),
                'name': name,
                'unit': item.get('unitName'),
                'price': item.get('priceCur'),
                'province': item.get('typeName', prov_name),
                'year': item.get('curYear', year),
                'month': item.get('curMonth', month),
                'is_central_fallback': False
            })
            
    is_fallback = False
    if not matches and prov_code != '10':
        # Fallback to Central (code 10)
        central_data = fetch_data(year, month, '10')
        if not central_data and month != 1:
            central_data = fetch_data(year, 1, '10')
        for item in central_data:
            name = item.get('commodityNameTH', '')
            name_lower = name.lower()
            if all(t in name_lower for t in terms):
                matches.append({
                    'id': item.get('id'),
                    'name': name,
                    'unit': item.get('unitName'),
                    'price': item.get('priceCur'),
                    'province': 'ส่วนกลาง (อ้างอิงแทนเนื่องจากไม่พบในจังหวัด)',
                    'year': item.get('curYear', year),
                    'month': item.get('curMonth', month),
                    'is_central_fallback': True
                })
        if matches:
            is_fallback = True

    return {
        'status': 'success',
        'query': query,
        'province': prov_name,
        'is_fallback': is_fallback,
        'year': year,
        'month': month,
        'count': len(matches),
        'results': matches[:limit]
    }

def main():
    parser = argparse.ArgumentParser(description='Thai Construction Material Price Search')
    parser.add_argument('query', nargs='?', default='', help='Keyword to search (e.g. หินคลุก, คอนกรีต)')
    parser.add_argument('-q', '--keyword', dest='query_flag', help='Keyword alias')
    parser.add_argument('-p', '--province', default='ส่วนกลาง', help='Province name or code (default: ส่วนกลาง)')
    parser.add_argument('-y', '--year', type=int, default=2567, help='Year in B.E. (default: 2567)')
    parser.add_argument('-m', '--month', type=int, default=6, help='Month 1-12 (default: 6)')
    parser.add_argument('-l', '--limit', type=int, default=20, help='Max items to return')
    parser.add_argument('--json', action='store_true', help='Output JSON instead of table')
    
    args = parser.parse_args()
    query = args.query_flag or args.query
    if not query:
        print("กรุณาระบุคำค้นหา เช่น: python search_material_price.py หินคลุก -p ชลบุรี")
        sys.exit(1)
        
    res = search_materials(query, year=args.year, month=args.month, province=args.province, limit=args.limit)
    
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    prov_str = res.get('province')
    if res.get('is_fallback'):
        prov_str += " (ไม่พบในจังหวัดที่เลือก จึงใช้อ้างอิงราคาจากส่วนกลาง)"
    print(f"\n=======================================================")
    print(f" 📊 ผลการค้นหาราคาวัสดุก่อสร้าง: '{query}'")
    print(f" 📍 พื้นที่: {prov_str} | ปี: {res.get('year')} เดือน: {res.get('month')}")
    print(f" 🔢 พบทั้งหมด: {res.get('count')} รายการ (แสดง {len(res.get('results', []))} รายการแรก)")
    print(f"=======================================================\n")
    
    if not res.get('results'):
        print("❌ ไม่พบรายการวัสดุที่ตรงกับคำค้นหา")
        return
        
    print(f"{'รายการวัสดุ':<55} | {'หน่วย':<10} | {'ราคา (บาท)':>12}")
    print("-" * 83)
    for r in res['results']:
        name = r['name']
        if len(name) > 52:
            name = name[:49] + "..."
        print(f"{name:<55} | {str(r['unit']):<10} | {float(r['price']):>12,.2f}")
    print("-" * 83)
    print("แหล่งข้อมูล: ดัชนีราคาวัสดุก่อสร้าง กระทรวงพาณิชย์ (ผ่าน yotathai.com)\n")

if __name__ == '__main__':
    main()
