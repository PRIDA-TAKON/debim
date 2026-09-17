"""
Lightweight 3D Web Viewer generator and local HTTP preview server for debim.
"""

import json
import math
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Union
import webbrowser

from debim.resolver import (
    ResolvedDoor,
    ResolvedManifest,
    ResolvedWindow,
    resolve_manifest,
)
from debim.schema import ProjectManifest, load_manifest


def generate_viewer_html(
    manifest: Union[ProjectManifest, ResolvedManifest, Path, str]
) -> str:
    """
    Generate a self-contained, standalone 3D web viewer HTML string
    using CDN-hosted Three.js and OrbitControls.
    """
    if isinstance(manifest, (str, Path)):
        manifest_obj = load_manifest(manifest)
        resolved = resolve_manifest(manifest_obj)
    elif isinstance(manifest, ProjectManifest):
        resolved = resolve_manifest(manifest)
    elif isinstance(manifest, ResolvedManifest):
        resolved = manifest
    else:
        raise TypeError(f"Unsupported manifest type: {type(manifest)}")

    proj = resolved.manifest.project
    storeys_data = [s.model_dump() for s in resolved.manifest.spatial_structure.storeys]
    grids_data = {
        "axes_x": resolved.manifest.grids.axes_x,
        "axes_y": resolved.manifest.grids.axes_y,
    }

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
            "rotation": [0, 0, 0],
            "dimensions": {
                "width": footing.width,
                "depth": footing.depth,
                "height": footing.thickness,
            },
            "color": "#6A6A6A",
        })

    # Columns
    for col in resolved.columns:
        elements_data.append({
            "tag": col.tag,
            "class": "IfcColumn",
            "material": col.element.material,
            "position": [
                col.start_point[0],
                col.start_point[1],
                col.start_point[2] + col.height / 2.0,
            ],
            "rotation": [0, 0, 0],
            "dimensions": {
                "width": col.element.profile.width,
                "depth": col.element.profile.depth,
                "height": col.height,
            },
            "color": "#808080",
        })

    # Beams
    for beam in resolved.beams:
        cx = (beam.start_point[0] + beam.end_point[0]) / 2.0
        cy = (beam.start_point[1] + beam.end_point[1]) / 2.0
        cz = beam.start_point[2] - beam.element.profile.depth / 2.0
        elements_data.append({
            "tag": beam.tag,
            "class": "IfcBeam",
            "material": beam.element.material,
            "position": [cx, cy, cz],
            "rotation": [0, 0, beam.rotation_angle],
            "dimensions": {
                "length": beam.span_length,
                "width": beam.element.profile.width,
                "depth": beam.element.profile.depth,
            },
            "color": "#9A9A9A",
        })

    # Walls & Children
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

        for child in wall.children:
            if isinstance(child, ResolvedDoor):
                elements_data.append({
                    "tag": child.tag,
                    "class": "IfcDoor",
                    "material": "Wood",
                    "position": [
                        child.position[0],
                        child.position[1],
                        child.position[2] + child.height / 2.0,
                    ],
                    "rotation": [0, 0, angle],
                    "dimensions": {
                        "width": child.width,
                        "thickness": wall.thickness * 1.08,
                        "height": child.height,
                    },
                    "color": "#8B4513",
                })
            elif isinstance(child, ResolvedWindow):
                elements_data.append({
                    "tag": child.tag,
                    "class": "IfcWindow",
                    "material": "Glass",
                    "position": [
                        child.position[0],
                        child.position[1],
                        child.position[2] + child.height / 2.0,
                    ],
                    "rotation": [0, 0, angle],
                    "dimensions": {
                        "width": child.width,
                        "thickness": wall.thickness * 1.08,
                        "height": child.height,
                    },
                    "color": "#00FFFF",
                    "transparent": True,
                    "opacity": 0.6,
                })

    # Custom Elements
    for custom in resolved.custom_elements:
        tag_upper = custom.tag.upper()
        if "F2" in tag_upper or "FOOTING" in tag_upper:
            w, d, h = 0.8, 1.5, 0.8
            pos = [custom.position[0], custom.position[1], custom.position[2] - h / 2.0]
            color = "#8A8A8E"
        elif "PIN" in tag_upper:
            w, d, h = 0.35, 0.35, 0.8
            pos = [custom.position[0], custom.position[1], custom.position[2] + h / 2.0]
            color = "#E63946"
        elif "TRUSS" in tag_upper:
            w, d, h = 5.5, 0.8, 3.8
            pos = [custom.position[0] - w / 2.0, custom.position[1], custom.position[2] + h / 2.0]
            color = "#2A6F97"
        elif "LINE" in tag_upper or "BOUNDARY" in tag_upper:
            w, d, h = 134.0, 40.0, 0.05
            pos = [67.0, 20.0, 0.025]
            color = "#FFB703"
        else:
            w, d, h = 0.8, 0.8, 1.5
            pos = [custom.position[0], custom.position[1], custom.position[2] + 0.75]
            color = "#9370DB"

        elements_data.append({
            "tag": custom.tag,
            "class": "IfcCustomElement",
            "material": "Custom Asset",
            "position": pos,
            "rotation": [0, 0, 0],
            "dimensions": {
                "width": w,
                "depth": d,
                "height": h,
            },
            "color": color,
        })

    scene_json = json.dumps({
        "project": {
            "id": proj.id,
            "name": proj.name,
            "units": proj.units.model_dump(),
        },
        "storeys": storeys_data,
        "grids": grids_data,
        "elements": elements_data,
    }, indent=2)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>debim 3D Viewer - {proj.name}</title>
    <!-- CDN-hosted Three.js and OrbitControls -->
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
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #1a1a1e;
            color: #e0e0e0;
        }}
        #canvas-container {{
            width: 100%;
            height: 100%;
            display: block;
        }}
        .ui-panel {{
            position: absolute;
            background: rgba(25, 27, 31, 0.88);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
            pointer-events: auto;
            z-index: 10;
        }}
        #info-panel {{
            top: 16px;
            left: 16px;
            width: 300px;
        }}
        #inspector-panel {{
            top: 16px;
            right: 16px;
            width: 320px;
        }}
        h1 {{
            font-size: 1.1rem;
            color: #ffffff;
            margin-bottom: 4px;
        }}
        .subtitle {{
            font-size: 0.8rem;
            color: #8888aa;
            margin-bottom: 12px;
        }}
        .section-title {{
            font-size: 0.85rem;
            font-weight: 600;
            color: #4da6ff;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 12px;
            margin-bottom: 6px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding-bottom: 4px;
        }}
        .data-row {{
            display: flex;
            justify-content: space-between;
            font-size: 0.82rem;
            margin-bottom: 4px;
        }}
        .data-label {{
            color: #aaaaaa;
        }}
        .data-value {{
            font-weight: 500;
            color: #ffffff;
            text-align: right;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            background: #2a3a4e;
            color: #66b2ff;
        }}
        #view-toolbar {{
            position: absolute;
            top: 16px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            gap: 8px;
            background: rgba(20, 24, 33, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            padding: 6px 12px;
            border-radius: 30px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
            z-index: 100;
        }}
        .view-btn {{
            background: #2a3a4e;
            color: #e0e0e0;
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .view-btn:hover {{
            background: #3b82f6;
            color: #ffffff;
        }}
        #layer-toolbar {{
            position: absolute;
            top: 64px;
            left: 50%;
            transform: translateX(-50%);
            display: flex;
            gap: 8px;
            background: rgba(20, 24, 33, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            padding: 4px 10px;
            border-radius: 20px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
            z-index: 100;
        }}
        .layer-btn {{
            background: #222d3d;
            color: #94a3b8;
            border: 1px solid rgba(255, 255, 255, 0.08);
            padding: 4px 10px;
            border-radius: 14px;
            font-size: 0.75rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .layer-btn.active {{
            background: #1e3a8a;
            color: #60a5fa;
            border-color: #3b82f6;
        }}
        #axes-legend {{
            position: absolute;
            bottom: 16px;
            left: 20px;
            background: rgba(20, 24, 33, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.75rem;
            color: #ddd;
            z-index: 10;
            pointer-events: none;
        }}
        #instructions {{
            position: absolute;
            bottom: 16px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.6);
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.8rem;
            color: #cccccc;
            pointer-events: none;
        }}
    </style>
</head>
<body>
    <div id="canvas-container"></div>

    <div id="view-toolbar">
        <button class="view-btn" onclick="setView('top')">📐 ผังพื้น (Top View)</button>
        <button class="view-btn" onclick="setView('iso')">🏢 3D Isometric</button>
        <button class="view-btn" onclick="setView('front')">↔️ ด้านหน้า (Front)</button>
        <button class="view-btn" onclick="setView('side')">↕️ ด้านข้าง (Side)</button>
    </div>

    <div id="layer-toolbar">
        <span style="font-size: 0.75rem; color: #8888aa; align-self: center; margin-right: 4px;">เลเยอร์:</span>
        <button class="layer-btn active" id="btn-layer-footings" onclick="toggleLayer('footings')">🔲 ฐานราก</button>
        <button class="layer-btn active" id="btn-layer-structure" onclick="toggleLayer('structure')">🏛️ เสา/โครงสร้าง</button>
        <button class="layer-btn active" id="btn-layer-grids" onclick="toggleLayer('grids')">📐 ผังกริด/แนวเขต</button>
    </div>

    <div id="axes-legend">
        <div><span style="color:#ff4d4d; font-weight:bold;">🔴 แกน X:</span> กริด 1 ถึง 15 (แนวนอน)</div>
        <div><span style="color:#4dff4d; font-weight:bold;">🟢 แกน Y:</span> กริด E ถึง A (แนวตั้ง)</div>
        <div><span style="color:#4da6ff; font-weight:bold;">🔵 แกน Z:</span> ระดับความสูง Elevation (+0.00)</div>
    </div>

    <div id="info-panel" class="ui-panel">
        <h1>{proj.name}</h1>
        <div class="subtitle">Project ID: <span id="project-id">{proj.id}</span></div>

        <div class="section-title">Storeys</div>
        <div id="storeys-list"></div>
    </div>

    <div id="inspector-panel" class="ui-panel">
        <h1>Element Inspector</h1>
        <div class="subtitle">Click on any 3D element to inspect</div>

        <div id="inspector-content">
            <p style="color: #888; font-size: 0.85rem; font-style: italic;">No element selected</p>
        </div>
    </div>

    <div id="instructions">
        Rotate: Left Click + Drag | Pan: Right Click + Drag | Zoom: Scroll
    </div>

    <script>
        const sceneData = {scene_json};

        // Initialize Three.js Scene
        const container = document.getElementById('canvas-container');
        const scene = new THREE.Scene();
        scene.background = new THREE.Color(0x1a1a1e);

        if (THREE.Object3D.DefaultUp) {{
            THREE.Object3D.DefaultUp.set(0, 0, 1);
        }}

        const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
        camera.up.set(0, 0, 1);

        const renderer = new THREE.WebGLRenderer({{ antialias: true }});
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        renderer.shadowMap.enabled = true;
        container.appendChild(renderer.domElement);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
        scene.add(ambientLight);

        const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444455, 0.6);
        hemiLight.position.set(0, 0, 50);
        scene.add(hemiLight);

        const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight1.position.set(70, -20, 100);
        scene.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0xaaccff, 0.4);
        dirLight2.position.set(70, 60, 80);
        scene.add(dirLight2);

        // Build UI - Storeys list
        const storeysListEl = document.getElementById('storeys-list');
        sceneData.storeys.forEach(s => {{
            const row = document.createElement('div');
            row.className = 'data-row';
            row.innerHTML = `<span class="data-label">${{s.name}} (${{s.id}})</span><span class="data-value">+${{s.elevation.toFixed(2)}}m (h: ${{s.height.toFixed(2)}}m)</span>`;
            storeysListEl.appendChild(row);
        }});

        // Helper to create circular grid bubble sprites
        function makeGridSprite(name, color) {{
            const canvas = document.createElement('canvas');
            canvas.width = 128;
            canvas.height = 128;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = 'rgba(25, 30, 42, 0.88)';
            ctx.beginPath();
            ctx.arc(64, 64, 52, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = color || '#38bdf8';
            ctx.lineWidth = 6;
            ctx.stroke();
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 44px -apple-system, BlinkMacSystemFont, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(name, 64, 64);
            const texture = new THREE.CanvasTexture(canvas);
            const spriteMat = new THREE.SpriteMaterial({{ map: texture, depthTest: false }});
            const sprite = new THREE.Sprite(spriteMat);
            sprite.scale.set(4, 4, 1);
            return sprite;
        }}

        // Render Grid Lines & Ground
        const allX = Object.values(sceneData.grids.axes_x);
        const allY = Object.values(sceneData.grids.axes_y);
        const minGridX = Math.min(...allX);
        const maxGridX = Math.max(...allX);
        const minGridY = Math.min(...allY);
        const maxGridY = Math.max(...allY);
        const centerX = (minGridX + maxGridX) / 2;
        const centerY = (minGridY + maxGridY) / 2;
        const gridSize = Math.max(maxGridX - minGridX, maxGridY - minGridY) * 1.4;

        // Actual Project Grid Lines & Grids Group
        const gridGroup = new THREE.Group();
        scene.add(gridGroup);

        const gridLineMat = new THREE.LineDashedMaterial({{
            color: 0x475569,
            dashSize: 1,
            gapSize: 0.5,
            linewidth: 1
        }});

        // X Grids (Vertical lines running along Y)
        Object.entries(sceneData.grids.axes_x).forEach(([name, xVal]) => {{
            const pts = [
                new THREE.Vector3(xVal, minGridY - 6, 0),
                new THREE.Vector3(xVal, maxGridY + 6, 0)
            ];
            const geom = new THREE.BufferGeometry().setFromPoints(pts);
            const line = new THREE.Line(geom, gridLineMat);
            line.computeLineDistances();
            gridGroup.add(line);

            // Bubble at top and bottom
            const topBubble = makeGridSprite(name, '#38bdf8');
            topBubble.position.set(xVal, maxGridY + 8, 0.1);
            gridGroup.add(topBubble);
            const botBubble = makeGridSprite(name, '#38bdf8');
            botBubble.position.set(xVal, minGridY - 8, 0.1);
            gridGroup.add(botBubble);
        }});

        // Y Grids (Horizontal lines running along X)
        Object.entries(sceneData.grids.axes_y).forEach(([name, yVal]) => {{
            const pts = [
                new THREE.Vector3(minGridX - 6, yVal, 0),
                new THREE.Vector3(maxGridX + 6, yVal, 0)
            ];
            const geom = new THREE.BufferGeometry().setFromPoints(pts);
            const line = new THREE.Line(geom, gridLineMat);
            line.computeLineDistances();
            gridGroup.add(line);

            // Bubble at left and right
            const leftBubble = makeGridSprite(name, '#4ade80');
            leftBubble.position.set(minGridX - 8, yVal, 0.1);
            gridGroup.add(leftBubble);
            const rightBubble = makeGridSprite(name, '#4ade80');
            rightBubble.position.set(maxGridX + 8, yVal, 0.1);
            gridGroup.add(rightBubble);
        }});

        // Visible Coordinate Axes (Red = X, Green = Y, Blue = Z)
        const axesHelper = new THREE.AxesHelper(15);
        axesHelper.position.set(0, 0, 0.05);
        gridGroup.add(axesHelper);

        const gridHelper = new THREE.GridHelper(gridSize, 20, 0x223046, 0x15202e);
        gridHelper.rotation.x = Math.PI / 2;
        gridHelper.position.set(centerX, centerY, -0.05);
        gridGroup.add(gridHelper);

        // Storey elevation guide planes / lines
        sceneData.storeys.forEach(s => {{
            if (s.elevation > 0) {{
                const storeyGrid = new THREE.GridHelper(gridSize, 10, 0x334466, 0x112233);
                storeyGrid.rotation.x = Math.PI / 2;
                storeyGrid.position.set(centerX, centerY, s.elevation);
                gridGroup.add(storeyGrid);
            }}
        }});

        // Render Elements
        const pickableObjects = [];

        sceneData.elements.forEach(data => {{
            let geometry;
            const dim = data.dimensions;

            if (data.class === "IfcColumn") {{
                geometry = new THREE.BoxGeometry(dim.width, dim.depth, dim.height);
            }} else if (data.class === "IfcBeam") {{
                geometry = new THREE.BoxGeometry(dim.length, dim.width, dim.depth);
            }} else if (data.class === "IfcWall") {{
                geometry = new THREE.BoxGeometry(dim.length, dim.thickness, dim.height);
            }} else if (data.class === "IfcDoor" || data.class === "IfcWindow") {{
                geometry = new THREE.BoxGeometry(dim.width, dim.thickness, dim.height);
            }} else {{
                geometry = new THREE.BoxGeometry(dim.width, dim.depth, dim.height);
            }}

            const matOptions = {{
                color: new THREE.Color(data.color),
                roughness: 0.5,
                metalness: 0.1
            }};
            if (data.transparent) {{
                matOptions.transparent = true;
                matOptions.opacity = data.opacity || 0.6;
            }}

            const material = new THREE.MeshStandardMaterial(matOptions);
            const mesh = new THREE.Mesh(geometry, material);

            mesh.position.set(...data.position);
            mesh.rotation.set(...data.rotation);
            mesh.userData = data;

            // Layer assignment for filtering
            const tagUpper = (data.tag || "").toUpperCase();
            if (tagUpper.includes("F2") || tagUpper.includes("FOOTING") || data.class === "IfcFooting") {{
                mesh.userData.layer = "footings";
            }} else if (tagUpper.includes("PIN") || tagUpper.includes("BOUNDARY") || tagUpper.includes("LINE")) {{
                mesh.userData.layer = "grids";
            }} else {{
                mesh.userData.layer = "structure";
            }}

            // Wireframe / Edges for visual clarity
            const edges = new THREE.EdgesGeometry(geometry);
            const line = new THREE.LineSegments(
                edges,
                new THREE.LineBasicMaterial({{ color: 0x000000, linewidth: 1 }})
            );
            mesh.add(line);

            scene.add(mesh);
            pickableObjects.push(mesh);
        }});

        // Camera position setup - Start with Top View (locked to 2D Plan View)
        camera.position.set(centerX, centerY, 160);
        camera.up.set(0, 1, 0);
        controls.target.set(centerX, centerY, 0);
        controls.minPolarAngle = 0;
        controls.maxPolarAngle = 0; // 🔒 2D Plan view lock
        controls.update();

        window.setView = function(mode) {{
            if (mode === 'top') {{
                camera.position.set(centerX, centerY, 160);
                camera.up.set(0, 1, 0);
                controls.target.set(centerX, centerY, 0);
                controls.minPolarAngle = 0;
                controls.maxPolarAngle = 0; // 🔒 Lock to true 2D Plan View
            }} else if (mode === 'iso') {{
                camera.position.set(centerX + 60, centerY - 80, 60);
                camera.up.set(0, 0, 1);
                controls.target.set(centerX, centerY, 0);
                controls.minPolarAngle = 0;
                controls.maxPolarAngle = Math.PI; // 🔓 Unlock 3D rotation
            }} else if (mode === 'front') {{
                camera.position.set(centerX, minGridY - 90, 15);
                camera.up.set(0, 0, 1);
                controls.target.set(centerX, centerY, 0);
                controls.minPolarAngle = 0;
                controls.maxPolarAngle = Math.PI;
            }} else if (mode === 'side') {{
                camera.position.set(maxGridX + 70, centerY, 15);
                camera.up.set(0, 0, 1);
                controls.target.set(centerX, centerY, 0);
                controls.minPolarAngle = 0;
                controls.maxPolarAngle = Math.PI;
            }}
            controls.update();
        }};

        window.toggleLayer = function(layerName) {{
            const btn = document.getElementById('btn-layer-' + layerName);
            const isActive = btn.classList.toggle('active');
            if (layerName === 'grids') {{
                gridGroup.visible = isActive;
                pickableObjects.forEach(mesh => {{
                    if (mesh.userData.layer === 'grids') mesh.visible = isActive;
                }});
            }} else {{
                pickableObjects.forEach(mesh => {{
                    if (mesh.userData.layer === layerName) {{
                        mesh.visible = isActive;
                    }}
                }});
            }}
        }};

        // Select first element by default if available
        if (sceneData.elements.length > 0) {{
            showInspector(sceneData.elements[0]);
        }}

        // Element Selection / Raycasting
        const raycaster = new THREE.Raycaster();
        const mouse = new THREE.Vector2();
        let selectedMesh = null;
        let originalColor = null;

        window.addEventListener('click', (event) => {{
            // Ignore click if clicking on UI panels
            if (event.target.closest('.ui-panel')) return;

            mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
            mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

            raycaster.setFromCamera(mouse, camera);
            const intersects = raycaster.intersectObjects(pickableObjects);

            if (selectedMesh && originalColor) {{
                selectedMesh.material.color.copy(originalColor);
                selectedMesh = null;
            }}

            if (intersects.length > 0) {{
                selectedMesh = intersects[0].object;
                originalColor = selectedMesh.material.color.clone();
                selectedMesh.material.color.setHex(0xffaa00);

                showInspector(selectedMesh.userData);
            }} else {{
                showInspector(null);
            }}
        }});

        function showInspector(data) {{
            const contentEl = document.getElementById('inspector-content');
            if (!data) {{
                contentEl.innerHTML = '<p style="color: #888; font-size: 0.85rem; font-style: italic;">No element selected</p>';
                return;
            }}

            let dimText = '';
            if (data.dimensions.length !== undefined) {{
                dimText = `${{data.dimensions.length.toFixed(2)}}m (L)`;
                if (data.dimensions.width !== undefined) dimText += ` × ${{data.dimensions.width.toFixed(2)}}m (W)`;
                if (data.dimensions.thickness !== undefined) dimText += ` × ${{data.dimensions.thickness.toFixed(2)}}m (Thk)`;
                if (data.dimensions.height !== undefined) dimText += ` × ${{data.dimensions.height.toFixed(2)}}m (H)`;
                if (data.dimensions.depth !== undefined) dimText += ` × ${{data.dimensions.depth.toFixed(2)}}m (D)`;
            }} else {{
                dimText = `${{data.dimensions.width.toFixed(2)}}m (W) × ${{data.dimensions.depth.toFixed(2)}}m (D) × ${{data.dimensions.height.toFixed(2)}}m (H)`;
            }}

            contentEl.innerHTML = `
                <div style="margin-bottom: 8px;"><span class="badge">${{data.class}}</span></div>
                <div class="data-row"><span class="data-label">Tag</span><span class="data-value">${{data.tag}}</span></div>
                <div class="data-row"><span class="data-label">Material</span><span class="data-value">${{data.material || '-'}}</span></div>
                <div class="data-row"><span class="data-label">Dimensions</span><span class="data-value">${{dimText}}</span></div>
                <div class="data-row"><span class="data-label">Position</span><span class="data-value">(${{data.position[0].toFixed(2)}}, ${{data.position[1].toFixed(2)}}, ${{data.position[2].toFixed(2)}})</span></div>
            `;
        }}

        // Animation loop
        function animate() {{
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        }}
        animate();

        // Responsive resize
        window.addEventListener('resize', () => {{
            camera.aspect = window.innerWidth / window.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(window.innerWidth, window.innerHeight);
        }});
    </script>
</body>
</html>
"""
    return html_content


class _ViewerHTTPRequestHandler(BaseHTTPRequestHandler):
    html_content: bytes = b""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(self.html_content)))
        self.end_headers()
        self.wfile.write(self.html_content)

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress verbose standard HTTP server logging
        pass


def serve_viewer(
    html_content: str, port: int = 8000, open_browser: bool = True
) -> None:
    """
    Serve the viewer HTML content on a local HTTP server and optionally open in browser.
    """
    handler = type(
        "ViewerHandler",
        (_ViewerHTTPRequestHandler,),
        {"html_content": html_content.encode("utf-8")},
    )
    server = HTTPServer(("0.0.0.0", port), handler)
    url = f"http://localhost:{port}"

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
