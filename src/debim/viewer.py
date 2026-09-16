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
        elements_data.append({
            "tag": custom.tag,
            "class": "IfcCustomElement",
            "material": "Custom Asset",
            "position": [
                custom.position[0],
                custom.position[1],
                custom.position[2] + 0.75,
            ],
            "rotation": [0, 0, 0],
            "dimensions": {
                "width": 0.8,
                "depth": 0.8,
                "height": 1.5,
            },
            "color": "#9370DB",
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
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        scene.add(ambientLight);

        const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
        dirLight1.position.set(20, -20, 30);
        scene.add(dirLight1);

        const dirLight2 = new THREE.DirectionalLight(0x88aaff, 0.3);
        dirLight2.position.set(-20, 20, 10);
        scene.add(dirLight2);

        // Build UI - Storeys list
        const storeysListEl = document.getElementById('storeys-list');
        sceneData.storeys.forEach(s => {{
            const row = document.createElement('div');
            row.className = 'data-row';
            row.innerHTML = `<span class="data-label">${{s.name}} (${{s.id}})</span><span class="data-value">+${{s.elevation.toFixed(2)}}m (h: ${{s.height.toFixed(2)}}m)</span>`;
            storeysListEl.appendChild(row);
        }});

        // Render Grid Lines & Ground
        const maxGridX = Math.max(...Object.values(sceneData.grids.axes_x), 10);
        const maxGridY = Math.max(...Object.values(sceneData.grids.axes_y), 10);
        const gridSize = Math.max(maxGridX, maxGridY) * 2;

        const gridHelper = new THREE.GridHelper(gridSize, 20, 0x444466, 0x222233);
        gridHelper.rotation.x = Math.PI / 2;
        gridHelper.position.set(maxGridX / 2, maxGridY / 2, 0);
        scene.add(gridHelper);

        // Storey elevation guide planes / lines
        sceneData.storeys.forEach(s => {{
            if (s.elevation > 0) {{
                const storeyGrid = new THREE.GridHelper(gridSize, 10, 0x334466, 0x112233);
                storeyGrid.rotation.x = Math.PI / 2;
                storeyGrid.position.set(maxGridX / 2, maxGridY / 2, s.elevation);
                scene.add(storeyGrid);
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

        // Camera position setup
        const centerX = maxGridX / 2;
        const centerY = maxGridY / 2;
        camera.position.set(centerX + 15, centerY - 15, 12);
        controls.target.set(centerX, centerY, 2);
        controls.update();

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
