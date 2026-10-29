"""
debim.diff.viewer_html

Standalone interactive 3D WebGL HTML heatmap viewer for debim models,
combining debim wireframe/transparent geometry overlayed with deviation point clouds
and interactive tolerance threshold sliders.
"""

import json
from pathlib import Path
from typing import Optional, Union
import numpy as np

from debim.diff.heatmap import generate_deviation_heatmap, HeatmapResult
from debim.resolver import ResolvedManifest, resolve_manifest
from debim.schema import ProjectManifest, load_manifest


def generate_heatmap_html(
    manifest_or_resolved: Union[ProjectManifest, ResolvedManifest, Path, str],
    points: np.ndarray,
    deviations: np.ndarray,
    tolerance_mm: float = 10.0,
) -> str:
    """
    Generate self-contained standalone 3D WebGL HTML page showing as-planned debim model
    wireframe/translucent overlayed with colorized deviation point cloud and interactive slider.

    Args:
        manifest_or_resolved: Project manifest path, object, or resolved manifest.
        points: (N, 3) float array of point cloud scan coordinates.
        deviations: (N,) float array of signed deviations in mm.
        tolerance_mm: Default tolerance threshold in mm (default: 10.0 mm).

    Returns:
        str: HTML markup string containing Three.js standalone viewer.
    """
    if isinstance(manifest_or_resolved, (str, Path)):
        m_obj = load_manifest(manifest_or_resolved)
        resolved = resolve_manifest(m_obj)
    elif isinstance(manifest_or_resolved, ProjectManifest):
        resolved = resolve_manifest(manifest_or_resolved)
    elif isinstance(manifest_or_resolved, ResolvedManifest):
        resolved = manifest_or_resolved
    else:
        raise TypeError(f"Unsupported manifest type: {type(manifest_or_resolved)}")

    heatmap_res = generate_deviation_heatmap(points, deviations, tolerance_mm=tolerance_mm)

    proj_name = resolved.manifest.project.name or "debim Project"
    proj_id = resolved.manifest.project.id or "P1"

    # Prepare point cloud data payload
    pts_flat = points.astype(np.float32).ravel().tolist()
    devs_list = deviations.astype(np.float32).ravel().tolist()

    # Prepare element wireframe bounds / geometry payload
    elements_data = []
    for elem in resolved.elements:
        tag = getattr(elem, "tag", None) or getattr(elem, "id", None) or "UNKNOWN"
        cls_name = getattr(elem, "element_class", None) or type(elem).__name__.replace("Resolved", "Ifc")

        pos = getattr(elem, "center", None) or getattr(elem, "start_point", None) or getattr(elem, "position", None)
        pos_list = [float(p) for p in pos] if pos and len(pos) >= 3 else [0.0, 0.0, 0.0]

        elements_data.append({
            "tag": tag,
            "class": cls_name,
            "position": pos_list,
        })

    payload_json = json.dumps({
        "project": {"id": proj_id, "name": proj_name},
        "tolerance_mm": tolerance_mm,
        "summary": {
            "pass_percentage": heatmap_res.pass_percentage,
            "within_tolerance_count": heatmap_res.within_tolerance_count,
            "out_of_tolerance_count": heatmap_res.out_of_tolerance_count,
            "rmse_mm": heatmap_res.rmse_mm,
            "max_deviation_mm": heatmap_res.max_deviation_mm,
            "min_deviation_mm": heatmap_res.min_deviation_mm,
            "mean_deviation_mm": heatmap_res.mean_deviation_mm,
            "total_points": len(points),
        },
        "points": pts_flat,
        "deviations": devs_list,
        "elements": elements_data,
    }, ensure_ascii=False)

    html_str = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>debim Deviation Tolerance Heatmap - {proj_name}</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            width: 100vw;
            height: 100vh;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
        }}
        #canvas-container {{
            width: 100%;
            height: 100%;
            display: block;
        }}
        .ui-card {{
            position: absolute;
            background: rgba(15, 23, 42, 0.88);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            pointer-events: auto;
            z-index: 10;
        }}
        #header-card {{
            top: 16px;
            left: 16px;
            width: 320px;
        }}
        #controls-card {{
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%);
            width: 440px;
            text-align: center;
        }}
        #stats-card {{
            top: 16px;
            right: 16px;
            width: 300px;
        }}
        h1 {{
            font-size: 1.1rem;
            color: #38bdf8;
            margin-bottom: 4px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .subtitle {{
            font-size: 0.8rem;
            color: #94a3b8;
            margin-bottom: 12px;
        }}
        .stat-row {{
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
            margin-bottom: 6px;
        }}
        .stat-label {{
            color: #94a3b8;
        }}
        .stat-value {{
            font-weight: 600;
            color: #f8fafc;
        }}
        .stat-value.pass {{
            color: #22c55e;
        }}
        .stat-value.fail {{
            color: #ef4444;
        }}
        .slider-container {{
            margin: 12px 0;
        }}
        .slider-label {{
            font-size: 0.85rem;
            font-weight: 600;
            color: #38bdf8;
            margin-bottom: 6px;
            display: flex;
            justify-content: space-between;
        }}
        input[type=range] {{
            width: 100%;
            accent-color: #38bdf8;
            cursor: pointer;
        }}
        .legend-bar {{
            display: flex;
            height: 12px;
            border-radius: 6px;
            overflow: hidden;
            margin-top: 8px;
        }}
        .legend-sec {{
            flex: 1;
            font-size: 0.7rem;
            text-align: center;
            line-height: 12px;
            font-weight: bold;
            color: #ffffff;
        }}
        .legend-recessed {{ background: #3b82f6; }}
        .legend-within {{ background: #22c55e; }}
        .legend-protrusion {{ background: #ef4444; }}
        #instructions {{
            position: absolute;
            top: 16px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(15, 23, 42, 0.7);
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.8rem;
            color: #cbd5e1;
            pointer-events: none;
        }}
    </style>
</head>
<body>
    <div id="canvas-container"></div>

    <div id="instructions">
        Rotate: Left Click + Drag | Pan: Right Click + Drag | Zoom: Scroll
    </div>

    <div id="header-card" class="ui-card">
        <h1>📊 Deviation Heatmap</h1>
        <div class="subtitle">{proj_name} ({proj_id})</div>
        <div class="stat-row">
            <span class="stat-label">Point Cloud Size:</span>
            <span class="stat-value" id="val-total-pts">{len(points):,} pts</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Model Alignment:</span>
            <span class="stat-value" style="color: #38bdf8;">ICP Fine Origin Registered</span>
        </div>
    </div>

    <div id="stats-card" class="ui-card">
        <h1 style="font-size: 0.95rem; color: #a78bfa;">🎯 Compliance Summary</h1>
        <div class="subtitle">As-Built Scan vs As-Planned BIM</div>

        <div class="stat-row">
            <span class="stat-label">Tolerance Pass Rate:</span>
            <span class="stat-value pass" id="val-pass-rate">{heatmap_res.pass_percentage:.1f}%</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Within Tolerance:</span>
            <span class="stat-value" id="val-within-count" style="color: #22c55e;">{heatmap_res.within_tolerance_count:,}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Out of Tolerance:</span>
            <span class="stat-value" id="val-out-count" style="color: #ef4444;">{heatmap_res.out_of_tolerance_count:,}</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">RMSE Error:</span>
            <span class="stat-value" id="val-rmse">{heatmap_res.rmse_mm:.2f} mm</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Max Protrusion:</span>
            <span class="stat-value" id="val-max-dev" style="color: #ef4444;">+{heatmap_res.max_deviation_mm:.1f} mm</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Max Recess:</span>
            <span class="stat-value" id="val-min-dev" style="color: #3b82f6;">{heatmap_res.min_deviation_mm:.1f} mm</span>
        </div>
    </div>

    <div id="controls-card" class="ui-card">
        <div class="slider-container">
            <div class="slider-label">
                <span>Deviation Tolerance Threshold:</span>
                <span id="tol-val-display" style="color: #38bdf8; font-size: 0.95rem;">±{tolerance_mm:.1f} mm</span>
            </div>
            <input type="range" id="tolerance-slider" min="1.0" max="50.0" step="0.5" value="{tolerance_mm}" oninput="updateTolerance(this.value)">
        </div>

        <div class="legend-bar">
            <div class="legend-sec legend-recessed" id="lbl-blue">Recessed (&lt; -{tolerance_mm:.0f}mm)</div>
            <div class="legend-sec legend-within" id="lbl-green">Pass (±{tolerance_mm:.0f}mm)</div>
            <div class="legend-sec legend-protrusion" id="lbl-red">Protrusion (&gt; +{tolerance_mm:.0f}mm)</div>
        </div>
    </div>

    <script>
        const payload = {payload_json};

        // Three.js Scene Setup
        const container = document.getElementById('canvas-container');
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x0f172a);

        if (THREE.Object3D.DefaultUp) {{
            THREE.Object3D.DefaultUp.set(0, 0, 1);
        }}

        const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.up.set(0, 0, 1);

        const renderer = new THREE.WebGLRenderer({{ antialias: true }});
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        container.appendChild(renderer.domElement);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;

        // Lights
        scene.add(new THREE.AmbientLight(0xffffff, 0.7));
        const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight.position.set(50, 50, 100);
        scene.add(dirLight);

        // Point Cloud Setup
        const numPoints = payload.points.length / 3;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(payload.points);
        const colors = new Float32Array(numPoints * 3);

        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const pointMaterial = new THREE.PointsMaterial({{
            size: 0.05,
            vertexColors: true,
            sizeAttenuation: true,
        }});

        const pointCloud = new THREE.Points(geometry, pointMaterial);
        scene.add(pointCloud);

        // Dynamic Color Mapping Function based on Slider
        function applyToleranceColoring(tolMm) {{
            const devs = payload.deviations;
            const colorAttr = geometry.attributes.color;

            let withinCount = 0;
            let sumSq = 0;

            for (let i = 0; i < numPoints; i++) {{
                const d = devs[i];
                sumSq += d * d;

                if (Math.abs(d) <= tolMm) {{
                    // Green [34, 197, 94]
                    colors[i * 3] = 34 / 255.0;
                    colors[i * 3 + 1] = 197 / 255.0;
                    colors[i * 3 + 2] = 94 / 255.0;
                    withinCount++;
                }} else if (d > tolMm) {{
                    // Red [239, 68, 68]
                    colors[i * 3] = 239 / 255.0;
                    colors[i * 3 + 1] = 68 / 255.0;
                    colors[i * 3 + 2] = 68 / 255.0;
                }} else {{
                    // Blue [59, 130, 246]
                    colors[i * 3] = 59 / 255.0;
                    colors[i * 3 + 1] = 130 / 255.0;
                    colors[i * 3 + 2] = 246 / 255.0;
                }}
            }}

            colorAttr.needsUpdate = true;

            const passPct = numPoints > 0 ? (withinCount / numPoints) * 100.0 : 100.0;
            const outCount = numPoints - withinCount;

            document.getElementById('tol-val-display').textContent = '±' + parseFloat(tolMm).toFixed(1) + ' mm';
            document.getElementById('val-pass-rate').textContent = passPct.toFixed(1) + '%';
            document.getElementById('val-within-count').textContent = withinCount.toLocaleString();
            document.getElementById('val-out-count').textContent = outCount.toLocaleString();

            document.getElementById('lbl-blue').textContent = 'Recessed (< -' + parseFloat(tolMm).toFixed(0) + 'mm)';
            document.getElementById('lbl-green').textContent = 'Pass (±' + parseFloat(tolMm).toFixed(0) + 'mm)';
            document.getElementById('lbl-red').textContent = 'Protrusion (> +' + parseFloat(tolMm).toFixed(0) + 'mm)';
        }}

        window.updateTolerance = function(val) {{
            applyToleranceColoring(parseFloat(val));
        }};

        // Apply initial coloring
        applyToleranceColoring(payload.tolerance_mm);

        // Center Camera on Point Cloud
        geometry.computeBoundingBox();
        const bbox = geometry.boundingBox;
        const center = new THREE.Vector3();
        const size = new THREE.Vector3();
        bbox.getCenter(center);
        bbox.getSize(size);

        const maxSpan = Math.max(size.x, size.y, size.z, 5.0);
        camera.position.set(center.x + maxSpan * 1.2, center.y - maxSpan * 1.5, center.z + maxSpan * 1.2);
        controls.target.copy(center);
        controls.update();

        // Add Grid Helper at Base
        const gridHelper = new THREE.GridHelper(maxSpan * 2.5, 20, 0x334155, 0x1e293b);
        gridHelper.rotation.x = Math.PI / 2;
        gridHelper.position.set(center.x, center.y, bbox.min.z);
        scene.add(gridHelper);

        // Render Loop
        function animate() {{
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        }}
        animate();

        window.addEventListener('resize', () => {{
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }});
    </script>
</body>
</html>
"""
    return html_str
