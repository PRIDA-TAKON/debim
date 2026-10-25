"""
Standalone Interactive HTML Schedule & 4D Progress Viewer Generator.
Combines Gantt chart, S-Curve chart, Milestone payment cards, and Three.js 4D BIM viewer.
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from debim.schedule.schema import ScheduleResult
from debim.resolver import ResolvedManifest, resolve_manifest
from debim.schema import ProjectManifest, load_manifest


def _extract_3d_elements_for_schedule(resolved: ResolvedManifest) -> List[Dict[str, Any]]:
    """Extract lightweight 3D element representation from ResolvedManifest for 4D WebGL viewer."""
    elements_data: List[Dict[str, Any]] = []

    # Footings
    for footing in resolved.footings:
        elements_data.append({
            "tag": footing.tag,
            "class": "IfcFooting",
            "material": footing.element.material,
            "position": [
                footing.position[0],
                footing.position[1],
                footing.position[2] + footing.thickness / 2.0,
            ],
            "dimensions": {
                "width": footing.width,
                "depth": footing.depth,
                "height": footing.thickness,
            },
            "color": "#6A6A6A",
        })

    # Columns
    for col in resolved.columns:
        cx = (col.start_point[0] + col.end_point[0]) / 2.0
        cy = (col.start_point[1] + col.end_point[1]) / 2.0
        cz = (col.start_point[2] + col.end_point[2]) / 2.0
        elements_data.append({
            "tag": col.tag,
            "class": "IfcColumn",
            "material": col.element.material,
            "position": [cx, cy, cz],
            "direction_vector_3d": col.direction_vector_3d,
            "dimensions": {
                "width": getattr(col.element.profile, "width", 0.3),
                "depth": getattr(col.element.profile, "depth", 0.3),
                "height": col.height,
            },
            "color": "#808080",
        })

    # Beams
    for beam in resolved.beams:
        cx = (beam.start_point[0] + beam.end_point[0]) / 2.0
        cy = (beam.start_point[1] + beam.end_point[1]) / 2.0
        b_depth = getattr(beam.element.profile, "depth", 0.3)
        cz = (beam.start_point[2] + beam.end_point[2]) / 2.0 - b_depth / 2.0
        elements_data.append({
            "tag": beam.tag,
            "class": "IfcBeam",
            "material": beam.element.material,
            "position": [cx, cy, cz],
            "direction_vector_3d": beam.direction_vector_3d,
            "rotation": [0, 0, beam.rotation_angle],
            "dimensions": {
                "length": beam.span_length,
                "width": getattr(beam.element.profile, "width", 0.2),
                "depth": b_depth,
            },
            "color": "#9A9A9A",
        })

    # Slabs
    for slab in resolved.slabs:
        xs = [pt[0] for pt in slab.polygon]
        ys = [pt[1] for pt in slab.polygon]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        w = max_x - min_x
        d = max_y - min_y
        h = slab.thickness
        cx = (min_x + max_x) / 2.0
        cy = (min_y + max_y) / 2.0
        cz = slab.center[2] - h / 2.0
        elements_data.append({
            "tag": slab.tag,
            "class": "IfcSlab",
            "material": slab.element.material,
            "position": [cx, cy, cz],
            "dimensions": {
                "width": w,
                "depth": d,
                "height": h,
                "polygon": [[pt[0], pt[1]] for pt in slab.polygon],
            },
            "color": "#A8B2C1",
        })

    # Walls
    for wall in resolved.walls:
        dx = wall.end_point[0] - wall.start_point[0]
        dy = wall.end_point[1] - wall.start_point[1]
        angle = math.atan2(dy, dx)
        cx = (wall.start_point[0] + wall.end_point[0]) / 2.0
        cy = (wall.start_point[1] + wall.end_point[1]) / 2.0
        cz = wall.start_point[2] + wall.height / 2.0
        elements_data.append({
            "tag": wall.tag,
            "class": "IfcWall",
            "material": wall.element.material,
            "position": [cx, cy, cz],
            "rotation": [0, 0, angle],
            "dimensions": {
                "length": wall.length,
                "thickness": wall.thickness,
                "height": wall.height,
            },
            "color": "#D3D3D3",
        })

    # Roofs
    for roof in resolved.roofs:
        for plane in roof.planes:
            elements_data.append({
                "tag": plane.tag,
                "class": "IfcRoofCovering",
                "geometry_type": "polygon",
                "points": plane.polygon,
                "color": "#9E4734",
            })

    # Stairs
    for stair in resolved.stairs:
        for step in stair.steps:
            elements_data.append({
                "tag": f"{stair.tag}-Step-{step.step_index}",
                "class": "IfcStairStep",
                "position": [step.position[0], step.position[1], step.position[2]],
                "dimensions": {
                    "width": step.width,
                    "depth": step.tread,
                    "height": step.riser,
                },
                "color": "#D4A373",
            })

    return elements_data


def generate_schedule_html(
    schedule_result: Union[ScheduleResult, Dict[str, Any]],
    manifest_obj: Optional[Union[ProjectManifest, ResolvedManifest, Path, str, Dict[str, Any]]] = None,
) -> str:
    """
    Generate a self-contained, standalone HTML Schedule & 4D Progress Viewer string.

    Includes:
      - Interactive Gantt chart (Planned vs Actual dual-bars)
      - Dynamic S-Curve chart (Planned Early, Planned Late, Actual)
      - Milestone payment cards with billing status badge and checklist
      - Three.js 4D BIM viewer with interactive time slider & play/pause animation
    """
    if isinstance(schedule_result, ScheduleResult):
        if hasattr(schedule_result, "model_dump"):
            schedule_dict = schedule_result.model_dump(by_alias=True)
        else:
            schedule_dict = schedule_result.dict(by_alias=True)
    elif isinstance(schedule_result, dict):
        schedule_dict = schedule_result
    else:
        raise TypeError(f"Unsupported schedule_result type: {type(schedule_result)}")

    elements_3d: List[Dict[str, Any]] = []
    if manifest_obj is not None:
        try:
            if isinstance(manifest_obj, (str, Path)):
                p = Path(manifest_obj)
                if p.exists():
                    m_obj = load_manifest(p)
                    resolved = resolve_manifest(m_obj)
                    elements_3d = _extract_3d_elements_for_schedule(resolved)
            elif isinstance(manifest_obj, ProjectManifest):
                resolved = resolve_manifest(manifest_obj)
                elements_3d = _extract_3d_elements_for_schedule(resolved)
            elif isinstance(manifest_obj, ResolvedManifest):
                elements_3d = _extract_3d_elements_for_schedule(manifest_obj)
        except Exception:
            elements_3d = []

    schedule_json_str = json.dumps(schedule_dict, ensure_ascii=False)
    elements_json_str = json.dumps(elements_3d, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>debim 4D Schedule & Progress Viewer - {schedule_dict.get('project_id', 'Project')}</title>
    <!-- Three.js CDN for 4D WebGL viewer -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }}
        header {{
            background: #1e293b;
            padding: 16px 24px;
            border-bottom: 1px solid #334155;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .header-title h1 {{
            font-size: 1.4rem;
            color: #38bdf8;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .header-title .subtitle {{
            font-size: 0.85rem;
            color: #94a3b8;
        }}
        .metrics-grid {{
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }}
        .metric-card {{
            background: #0f172a;
            border: 1px solid #334155;
            padding: 8px 16px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-card .val {{
            font-size: 1.2rem;
            font-weight: 700;
            color: #38bdf8;
        }}
        .metric-card .lbl {{
            font-size: 0.72rem;
            color: #94a3b8;
            text-transform: uppercase;
        }}

        main {{
            flex: 1;
            padding: 20px;
            display: grid;
            grid-template-columns: 1fr;
            gap: 24px;
            max-width: 1600px;
            margin: 0 auto;
            width: 100%;
        }}

        @media (min-width: 1100px) {{
            .two-col {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 24px;
            }}
        }}

        .panel-card {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            display: flex;
            flex-direction: column;
        }}
        .panel-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            border-bottom: 1px solid #334155;
            padding-bottom: 8px;
        }}
        .panel-header h2 {{
            font-size: 1.1rem;
            color: #f1f5f9;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        /* Timeline & Player Controls */
        .time-controller {{
            background: #0f172a;
            border: 1px solid #38bdf8;
            border-radius: 10px;
            padding: 12px 18px;
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 16px;
        }}
        .time-btn {{
            background: #38bdf8;
            color: #0f172a;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .time-btn:hover {{
            background: #0ea5e9;
            color: #ffffff;
        }}
        .slider-wrap {{
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .slider-wrap input[type=range] {{
            width: 100%;
            accent-color: #38bdf8;
            cursor: pointer;
        }}

        /* 3D WebGL Canvas Container */
        #bim3d-container {{
            width: 100%;
            height: 380px;
            background: #090d16;
            border-radius: 8px;
            position: relative;
            overflow: hidden;
        }}
        .bim3d-overlay {{
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(15, 23, 42, 0.85);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.8rem;
            border: 1px solid #334155;
            pointer-events: none;
        }}

        /* SVG S-Curve Chart */
        .chart-svg {{
            width: 100%;
            height: 280px;
            overflow: visible;
        }}

        /* Milestone Payment Cards */
        .milestones-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 16px;
        }}
        .ms-card {{
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 14px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .ms-card.ready {{
            border-color: #10b981;
            box-shadow: 0 0 10px rgba(16, 185, 129, 0.2);
        }}
        .ms-badge {{
            font-size: 0.7rem;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            text-transform: uppercase;
            display: inline-block;
        }}
        .ms-badge.pending {{ background: #334155; color: #94a3b8; }}
        .ms-badge.ready {{ background: #065f46; color: #34d399; }}
        .ms-badge.paid {{ background: #1e3a8a; color: #60a5fa; }}

        .checklist {{
            list-style: none;
            margin-top: 10px;
            font-size: 0.8rem;
        }}
        .checklist li {{
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 4px;
        }}
        .checklist li.done {{ color: #34d399; }}
        .checklist li.not-done {{ color: #94a3b8; }}

        /* Gantt Chart Table */
        .gantt-wrap {{
            overflow-x: auto;
            max-height: 400px;
            overflow-y: auto;
        }}
        .gantt-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.82rem;
            white-space: nowrap;
        }}
        .gantt-table th, .gantt-table td {{
            padding: 8px 12px;
            border-bottom: 1px solid #334155;
            text-align: left;
        }}
        .gantt-table th {{
            background: #0f172a;
            position: sticky;
            top: 0;
            z-index: 2;
            color: #94a3b8;
        }}
        .bar-container {{
            position: relative;
            width: 260px;
            height: 20px;
            background: #0f172a;
            border-radius: 4px;
            overflow: hidden;
        }}
        .bar-planned {{
            position: absolute;
            height: 8px;
            top: 2px;
            background: #0284c7;
            border-radius: 3px;
            opacity: 0.7;
        }}
        .bar-planned.critical {{
            background: #ef4444;
        }}
        .bar-actual {{
            position: absolute;
            height: 8px;
            bottom: 2px;
            background: #10b981;
            border-radius: 3px;
        }}
        .time-line-indicator {{
            position: absolute;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #f59e0b;
            z-index: 5;
        }}
    </style>
</head>
<body>

    <header>
        <div class="header-title">
            <h1><span>📅</span> debim 4D Schedule & Progress Viewer</h1>
            <div class="subtitle">Project ID: <strong id="hdr-proj-id">--</strong> | Time-Cost Trade-Off Engine</div>
        </div>
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="val" id="m-duration">0 d</div>
                <div class="lbl">Total Duration</div>
            </div>
            <div class="metric-card">
                <div class="val" id="m-progress">0%</div>
                <div class="lbl">Overall Progress</div>
            </div>
            <div class="metric-card">
                <div class="val" id="m-direct">฿0</div>
                <div class="lbl">Direct Cost</div>
            </div>
            <div class="metric-card">
                <div class="val" id="m-indirect">฿0</div>
                <div class="lbl">Indirect Cost</div>
            </div>
            <div class="metric-card">
                <div class="val" style="color:#10b981;" id="m-total">฿0</div>
                <div class="lbl">Grand Total</div>
            </div>
        </div>
    </header>

    <main>
        <!-- Time Travel Controller -->
        <div class="time-controller">
            <button class="time-btn" id="play-btn" onclick="togglePlay()">▶ Play 4D</button>
            <div class="slider-wrap">
                <div style="display:flex; justify-content:space-between; font-size:0.85rem; font-weight:600;">
                    <span>Timeline Time-Travel: <strong style="color:#38bdf8;" id="current-day-label">Day 0</strong></span>
                    <span style="color:#94a3b8;" id="current-date-label">Start Date</span>
                </div>
                <input type="range" id="time-slider" min="0" max="100" value="0" oninput="onTimeSliderChange(this.value)">
            </div>
        </div>

        <div class="two-col">
            <!-- 3D BIM Viewer Panel -->
            <div class="panel-card">
                <div class="panel-header">
                    <h2><span>🧱</span> 4D BIM WebGL Progress Model</h2>
                    <span style="font-size:0.75rem; color:#94a3b8;">Color-Coded Progress States</span>
                </div>
                <div id="bim3d-container">
                    <div class="bim3d-overlay">
                        Status at Day <span id="bim3d-day">0</span>:
                        <span style="color:#10b981;">■ Completed</span> |
                        <span style="color:#f97316;">■ In Progress</span> |
                        <span style="color:#64748b;">□ Wireframe</span>
                    </div>
                </div>
            </div>

            <!-- Dynamic S-Curve Panel -->
            <div class="panel-card">
                <div class="panel-header">
                    <h2><span>📈</span> Dynamic S-Curve Progress Chart</h2>
                    <div style="display:flex; gap:12px; font-size:0.75rem;">
                        <span style="color:#38bdf8;">-- Planned Early</span>
                        <span style="color:#94a3b8;">-- Planned Late</span>
                        <span style="color:#10b981;">— Actual Progress</span>
                    </div>
                </div>
                <div id="scurve-container">
                    <svg class="chart-svg" id="scurve-svg" viewBox="0 0 600 240"></svg>
                </div>
            </div>
        </div>

        <!-- Milestone Payment Cards -->
        <div class="panel-card">
            <div class="panel-header">
                <h2><span>💳</span> Payment Milestones & Billing Cards</h2>
                <span style="font-size:0.8rem; color:#94a3b8;" id="ms-summary-lbl">0 Milestones</span>
            </div>
            <div class="milestones-grid" id="milestones-container"></div>
        </div>

        <!-- Interactive Gantt Chart Panel -->
        <div class="panel-card">
            <div class="panel-header">
                <h2><span>📊</span> Interactive Gantt Chart (Planned vs Actual)</h2>
                <span style="font-size:0.75rem; color:#ef4444;">■ Critical Path Activity</span>
            </div>
            <div class="gantt-wrap">
                <table class="gantt-table">
                    <thead>
                        <tr>
                            <th>Activity ID</th>
                            <th>Task Name</th>
                            <th>Start</th>
                            <th>Finish</th>
                            <th>Dur (d)</th>
                            <th>Crashed</th>
                            <th>Status</th>
                            <th>Progress</th>
                            <th style="width:260px;">Timeline Schedule Bar</th>
                        </tr>
                    </thead>
                    <tbody id="gantt-tbody"></tbody>
                </table>
            </div>
        </div>
    </main>

    <script>
        const scheduleData = {schedule_json_str};
        const elementsData = {elements_json_str};

        let currentDay = 0;
        let isPlaying = false;
        let playInterval = null;
        const maxDuration = scheduleData.total_duration || 1;

        // Initialize Page Metrics
        document.getElementById('hdr-proj-id').textContent = scheduleData.project_id || 'PROJ';
        document.getElementById('m-duration').textContent = maxDuration + ' d';
        document.getElementById('m-progress').textContent = (scheduleData.overall_progress_percent || 0).toFixed(1) + '%';
        document.getElementById('m-direct').textContent = '฿' + (scheduleData.total_direct_cost || 0).toLocaleString();
        document.getElementById('m-indirect').textContent = '฿' + (scheduleData.total_indirect_cost || 0).toLocaleString();
        document.getElementById('m-total').textContent = '฿' + (scheduleData.total_cost || 0).toLocaleString();

        const slider = document.getElementById('time-slider');
        slider.max = maxDuration;
        slider.value = currentDay;

        // --- Render Milestone Cards ---
        const msContainer = document.getElementById('milestones-container');
        const msList = scheduleData.milestones || [];
        document.getElementById('ms-summary-lbl').textContent = msList.length + ' Milestones Defined';

        msList.forEach(ms => {{
            const card = document.createElement('div');
            const isReady = ms.billing_status === 'READY_FOR_BILLING' || ms.billing_status === 'PAID';
            card.className = 'ms-card ' + (isReady ? 'ready' : '');

            const totalProjectCost = scheduleData.total_cost || 1;
            const amt = (ms.payment_amount !== undefined && ms.payment_amount !== null)
                ? ms.payment_amount
                : (totalProjectCost * (ms.payment_percent || 0) / 100.0);

            const badgeClass = ms.billing_status.toLowerCase().replace(/_/g, '-');
            const badgeLabel = ms.billing_status === 'READY_FOR_BILLING' ? 'READY TO BILL' : ms.billing_status;

            let reqListHtml = '';
            if (ms.required_activities && ms.required_activities.length > 0) {{
                reqListHtml = '<ul class="checklist">';
                ms.required_activities.forEach(actId => {{
                    const act = scheduleData.activities[actId];
                    const isDone = act && (act.progress_percent >= 100 || act.status === 'COMPLETED');
                    const icon = isDone ? '✓' : '○';
                    const cls = isDone ? 'done' : 'not-done';
                    reqListHtml += `<li class="${{cls}}"><span>${{icon}}</span> <span>${{actId}} (${{act ? act.progress_percent : 0}}%)</span></li>`;
                }});
                reqListHtml += '</ul>';
            }}

            card.innerHTML = `
                <div>
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
                        <span style="font-weight:700; color:#f8fafc;">${{ms.id}}: ${{ms.name}}</span>
                        <span class="ms-badge ${{badgeClass}}">${{badgeLabel}}</span>
                    </div>
                    <div style="font-size:0.85rem; color:#38bdf8; font-weight:600;">
                        ${{(ms.payment_percent || 0).toFixed(1)}}% (฿${{amt.toLocaleString()}})
                    </div>
                    <div style="font-size:0.75rem; color:#94a3b8; margin-top:2px;">Planned Day: ${{ms.planned_completion_day}}</div>
                    ${{reqListHtml}}
                </div>
            `;
            msContainer.appendChild(card);
        }});

        // --- Render Gantt Chart Table ---
        const ganttTbody = document.getElementById('gantt-tbody');
        const actDict = scheduleData.activities || {{}};

        Object.entries(actDict).forEach(([actId, act]) => {{
            const tr = document.createElement('tr');
            const isCrit = act.is_critical;
            const startDay = act.start_day;
            const duration = act.duration;
            const finishDay = act.finish_day;

            const leftPct = (startDay / maxDuration) * 100;
            const widthPct = Math.max((duration / maxDuration) * 100, 1.5);

            tr.innerHTML = `
                <td style="font-weight:600; color:${{isCrit ? '#ef4444' : '#38bdf8'}}">${{actId}}</td>
                <td>${{act.name || actId}}</td>
                <td>${{startDay}}</td>
                <td>${{finishDay}}</td>
                <td>${{duration}}</td>
                <td>${{act.crashed_days || 0}}d</td>
                <td><span style="font-size:0.75rem; padding:2px 6px; border-radius:4px; background:${{act.status==='COMPLETED'?'#065f46':'#334155'}}">${{act.status}}</span></td>
                <td>${{(act.progress_percent || 0).toFixed(0)}}%</td>
                <td>
                    <div class="bar-container">
                        <div class="bar-planned ${{isCrit ? 'critical' : ''}}" style="left:${{leftPct}}%; width:${{widthPct}}%;"></div>
                        <div class="time-line-indicator" id="gantt-line-${{actId}}"></div>
                    </div>
                </td>
            `;
            ganttTbody.appendChild(tr);
        }});

        // --- Render Dynamic S-Curve SVG Chart ---
        function renderSCurve() {{
            const svg = document.getElementById('scurve-svg');
            const sc = scheduleData.s_curve || {{}};
            const dates = sc.dates || [];
            const early = sc.planned_early_percent || [];
            const late = sc.planned_late_percent || [];
            const actual = sc.actual_percent || [];

            const n = dates.length;
            if (n < 2) return;

            const w = 540, h = 180, padL = 40, padB = 30;

            function getPt(idx, val) {{
                const x = padL + (idx / (n - 1)) * (w - padL);
                const y = (h - padB) - (val / 100.0) * (h - padB - 10);
                return `${{x.toFixed(1)}},${{y.toFixed(1)}}`;
            }}

            let earlyPts = [], latePts = [], actualPts = [];
            for (let i = 0; i < n; i++) {{
                earlyPts.push(getPt(i, early[i] || 0));
                latePts.push(getPt(i, late[i] || 0));
                if (i < actual.length) {{
                    actualPts.push(getPt(i, actual[i] || 0));
                }}
            }}

            let svgContent = `
                <!-- Grid Lines -->
                <line x1="${{padL}}" y1="10" x2="${{w}}" y2="10" stroke="#334155" stroke-dasharray="2,2"/>
                <line x1="${{padL}}" y1="${{(h-padB)/2}}" x2="${{w}}" y2="${{(h-padB)/2}}" stroke="#334155" stroke-dasharray="2,2"/>
                <line x1="${{padL}}" y1="${{h-padB}}" x2="${{w}}" y2="${{h-padB}}" stroke="#475569"/>

                <!-- Y-Axis Labels -->
                <text x="${{padL-8}}" y="14" fill="#94a3b8" font-size="10" text-anchor="end">100%</text>
                <text x="${{padL-8}}" y="${{(h-padB)/2+4}}" fill="#94a3b8" font-size="10" text-anchor="end">50%</text>
                <text x="${{padL-8}}" y="${{h-padB}}" fill="#94a3b8" font-size="10" text-anchor="end">0%</text>

                <!-- Planned Late Curve -->
                <polyline points="${{latePts.join(' ')}}" fill="none" stroke="#94a3b8" stroke-width="2" stroke-dasharray="4,4"/>

                <!-- Planned Early Curve -->
                <polyline points="${{earlyPts.join(' ')}}" fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="4,4"/>

                <!-- Actual Progress Curve -->
                <polyline points="${{actualPts.join(' ')}}" fill="none" stroke="#10b981" stroke-width="3"/>
            `;

            // Render Clickable Milestone Pins
            msList.forEach(ms => {{
                const day = ms.planned_completion_day || 0;
                const idx = Math.min(Math.max(0, day), n - 1);
                const ptStr = getPt(idx, ms.payment_percent || 50);
                const [px, py] = ptStr.split(',').map(Number);

                svgContent += `
                    <g transform="translate(${{px}}, ${{py}})" style="cursor:pointer;" onclick="jumpToDay(${{day}})">
                        <circle r="6" fill="#f59e0b" stroke="#0f172a" stroke-width="2"/>
                        <text y="-10" fill="#f59e0b" font-size="9" font-weight="bold" text-anchor="middle">${{ms.id}}</text>
                    </g>
                `;
            }});

            // Render Data Date Marker Line
            const currIdx = Math.min(Math.max(0, currentDay), n - 1);
            const currX = padL + (currIdx / (n - 1)) * (w - padL);
            svgContent += `
                <line id="scurve-time-line" x1="${{currX}}" y1="10" x2="${{currX}}" y2="${{h-padB}}" stroke="#f59e0b" stroke-width="2"/>
            `;

            svg.innerHTML = svgContent;
        }}
        renderSCurve();

        window.jumpToDay = function(day) {{
            onTimeSliderChange(day);
            slider.value = day;
        }};

        // --- Three.js 4D BIM Viewer Engine ---
        let scene, camera, renderer, controls;
        const bimMeshMap = new Map();

        function init3DViewer() {{
            const container = document.getElementById('bim3d-container');
            if (!container) return;

            scene = new THREE.Scene();
            scene.background = new THREE.Color(0x090d16);

            camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
            camera.up.set(0, 0, 1);

            renderer = new THREE.WebGLRenderer({{ antialias: true }});
            renderer.setSize(container.clientWidth, container.clientHeight);
            renderer.setPixelRatio(window.devicePixelRatio);
            container.appendChild(renderer.domElement);

            controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;

            const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
            scene.add(ambientLight);
            const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
            dirLight.position.set(50, -20, 80);
            scene.add(dirLight);

            // Render 3D elements if available
            if (elementsData && elementsData.length > 0) {{
                const bbox = new THREE.Box3();
                elementsData.forEach(data => {{
                    let geometry;
                    const dim = data.dimensions || {{ width: 1, depth: 1, height: 1 }};
                    if (data.geometry_type === "polygon" && data.points) {{
                        const geom = new THREE.BufferGeometry();
                        const vertices = [];
                        const pts = data.points;
                        if (pts.length >= 3) {{
                            for (let i = 1; i < pts.length - 1; i++) {{
                                vertices.push(...pts[0], ...pts[i], ...pts[i + 1]);
                            }}
                        }}
                        geom.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
                        geometry = geom;
                    }} else {{
                        geometry = new THREE.BoxGeometry(dim.width || dim.length || 1, dim.depth || dim.thickness || 1, dim.height || 1);
                    }}

                    const material = new THREE.MeshStandardMaterial({{
                        color: new THREE.Color(data.color || "#808080"),
                        roughness: 0.5,
                        metalness: 0.1,
                        transparent: true,
                        opacity: 1.0,
                    }});

                    const mesh = new THREE.Mesh(geometry, material);
                    if (data.position) mesh.position.set(...data.position);
                    mesh.userData = data;

                    scene.add(mesh);
                    bimMeshMap.set(data.tag, mesh);
                    bbox.expandByObject(mesh);
                }});

                const center = new THREE.Vector3();
                bbox.getCenter(center);
                const size = new THREE.Vector3();
                bbox.getSize(size);
                const maxSpan = Math.max(size.x, size.y, size.z, 10);

                camera.position.set(center.x + maxSpan * 1.2, center.y - maxSpan * 1.5, center.z + maxSpan * 1.0);
                controls.target.copy(center);
                controls.update();
            }} else {{
                // Fallback placeholder geometric structure if no manifest provided
                const geom = new THREE.BoxGeometry(10, 8, 4);
                const mat = new THREE.MeshStandardMaterial({{ color: 0x38bdf8, wireframe: true }});
                const mesh = new THREE.Mesh(geom, mat);
                mesh.position.set(5, 4, 2);
                scene.add(mesh);
                camera.position.set(20, -15, 15);
                controls.target.set(5, 4, 2);
                controls.update();
            }}

            function animate3D() {{
                requestAnimationFrame(animate3D);
                controls.update();
                renderer.render(scene, camera);
            }}
            animate3D();
        }}

        init3DViewer();

        // Update 4D elements & timeline state on slider change
        window.onTimeSliderChange = function(val) {{
            currentDay = parseInt(val, 10);
            document.getElementById('current-day-label').textContent = 'Day ' + currentDay;
            document.getElementById('bim3d-day').textContent = currentDay;

            // Update S-Curve Data Date Marker
            const scLine = document.getElementById('scurve-time-line');
            if (scLine) {{
                const sc = scheduleData.s_curve || {{}};
                const n = (sc.dates || []).length || 1;
                const currIdx = Math.min(Math.max(0, currentDay), n - 1);
                const currX = 40 + (currIdx / Math.max(1, n - 1)) * (540 - 40);
                scLine.setAttribute('x1', currX);
                scLine.setAttribute('x2', currX);
            }}

            // Update 3D Element Materials
            bimMeshMap.forEach((mesh, tag) => {{
                let elemActivity = null;
                Object.values(actDict).forEach(act => {{
                    if (act.element_ids && act.element_ids.includes(tag)) {{
                        elemActivity = act;
                    }}
                }});

                if (!elemActivity) {{
                    // Unlinked element or structural fallback
                    mesh.material.color.setHex(0x94a3b8);
                    mesh.material.opacity = 0.85;
                }} else {{
                    const s = elemActivity.start_day;
                    const f = elemActivity.finish_day;

                    if (currentDay >= f) {{
                        // Completed activity
                        mesh.material.color.setHex(0x10b981); // Emerald Green
                        mesh.material.opacity = 0.95;
                    }} else if (currentDay >= s && currentDay < f) {{
                        // In Progress activity
                        mesh.material.color.setHex(0xf97316); // Orange Highlight
                        mesh.material.opacity = 1.0;
                    }} else {{
                        // Not Started activity (Ghost wireframe)
                        mesh.material.color.setHex(0x475569);
                        mesh.material.opacity = 0.20;
                    }}
                }}
            }});
        }};

        // Play / Pause Animation
        window.togglePlay = function() {{
            const btn = document.getElementById('play-btn');
            isPlaying = !isPlaying;

            if (isPlaying) {{
                btn.textContent = '⏸ Pause 4D';
                btn.style.background = '#ef4444';
                playInterval = setInterval(() => {{
                    currentDay++;
                    if (currentDay > maxDuration) {{
                        currentDay = 0;
                    }}
                    slider.value = currentDay;
                    onTimeSliderChange(currentDay);
                }}, 400);
            }} else {{
                btn.textContent = '▶ Play 4D';
                btn.style.background = '#38bdf8';
                if (playInterval) clearInterval(playInterval);
            }}
        }};

        // Initial trigger
        onTimeSliderChange(0);
    </script>
</body>
</html>
"""
    return html_content
