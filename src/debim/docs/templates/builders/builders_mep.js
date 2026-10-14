/**
 * MEP 3D Geometry Builders for debim Class Directory.
 * Covers: Pipe, Duct, Fan, Cooling Tower, Fire Suppression, Power Plant, Equipment Vessel, Pump, Valve, Sanitary Terminal, Air Terminal, Light Fixture, Electric Panel, Outlet/Switch, Vibration Isolator.
 */

function buildPump(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const h = sample3d.height || 0.55;

    const baseMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.7
    });
    const pumpMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.5
    });
    const motorMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.6
    });

    const baseMesh = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.06, 0.45), baseMat);
    baseMesh.position.set(0, -h / 2.0 + 0.03, 0);
    group.add(baseMesh);

    const casingGeom = new THREE.CylinderGeometry(0.18, 0.18, 0.20, 24);
    casingGeom.rotateZ(Math.PI / 2);
    const casingMesh = new THREE.Mesh(casingGeom, pumpMat);
    casingMesh.position.set(-0.15, -h / 2.0 + 0.24, 0);
    group.add(casingMesh);

    const motorGeom = new THREE.CylinderGeometry(0.14, 0.14, 0.35, 24);
    motorGeom.rotateZ(Math.PI / 2);
    const motorMesh = new THREE.Mesh(motorGeom, motorMat);
    motorMesh.position.set(0.15, -h / 2.0 + 0.24, 0);
    group.add(motorMesh);

    const capGeom = new THREE.CylinderGeometry(0.145, 0.145, 0.04, 24);
    capGeom.rotateZ(Math.PI / 2);
    const capMesh = new THREE.Mesh(capGeom, baseMat);
    capMesh.position.set(0.33, -h / 2.0 + 0.24, 0);
    group.add(capMesh);

    const suctionGeom = new THREE.CylinderGeometry(0.06, 0.06, 0.12, 16);
    suctionGeom.rotateZ(Math.PI / 2);
    const suctionMesh = new THREE.Mesh(suctionGeom, pumpMat);
    suctionMesh.position.set(-0.31, -h / 2.0 + 0.24, 0);
    group.add(suctionMesh);

    const suctionFlange = new THREE.Mesh(new THREE.TorusGeometry(0.08, 0.015, 8, 24), baseMat);
    suctionFlange.rotation.y = Math.PI / 2;
    suctionFlange.position.set(-0.36, -h / 2.0 + 0.24, 0);
    group.add(suctionFlange);

    const dischargeGeom = new THREE.CylinderGeometry(0.05, 0.05, 0.15, 16);
    const dischargeMesh = new THREE.Mesh(dischargeGeom, pumpMat);
    dischargeMesh.position.set(-0.15, -h / 2.0 + 0.39, 0);
    group.add(dischargeMesh);

    const dischargeFlange = new THREE.Mesh(new THREE.TorusGeometry(0.07, 0.015, 8, 24), baseMat);
    dischargeFlange.rotation.x = Math.PI / 2;
    dischargeFlange.position.set(-0.15, -h / 2.0 + 0.46, 0);
    group.add(dischargeFlange);

    return group;
}

function buildPipeFittingTee(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const r = sample3d.radius || 0.08;
    const l = sample3d.length || 0.35;
    const h = sample3d.height || 0.25;

    const pipeMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.7
    });
    const flangeMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });
    const weldMat = new THREE.MeshStandardMaterial({
        color: 0x475569,
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.6
    });

    // Main run pipe (horizontal along X axis)
    const runGeom = new THREE.CylinderGeometry(r, r, l, 24);
    runGeom.rotateZ(Math.PI / 2.0);
    const runMesh = new THREE.Mesh(runGeom, pipeMat);
    group.add(runMesh);

    // Branch pipe (vertical along +Y axis)
    const branchGeom = new THREE.CylinderGeometry(r, r, h, 24);
    const branchMesh = new THREE.Mesh(branchGeom, pipeMat);
    branchMesh.position.set(0, h / 2.0, 0);
    group.add(branchMesh);

    // Weld neck reinforcement collar at junction
    const neckReinf = new THREE.Mesh(new THREE.CylinderGeometry(r * 1.35, r * 1.15, r * 0.8, 24), weldMat);
    neckReinf.position.set(0, r * 0.4, 0);
    group.add(neckReinf);

    // Raised-face welded neck flanges on 3 ports
    const flangeR = r * 1.55;
    const flangeThickness = 0.025;

    // Run Port 1 (Left)
    const f1 = new THREE.Mesh(new THREE.CylinderGeometry(flangeR, flangeR, flangeThickness, 24), flangeMat);
    f1.rotation.z = Math.PI / 2.0;
    f1.position.set(-l / 2.0 + flangeThickness / 2.0, 0, 0);
    group.add(f1);
    const r1 = new THREE.Mesh(new THREE.TorusGeometry(flangeR * 0.95, 0.008, 8, 24), weldMat);
    r1.rotation.y = Math.PI / 2.0;
    r1.position.set(-l / 2.0, 0, 0);
    group.add(r1);

    // Run Port 2 (Right)
    const f2 = new THREE.Mesh(new THREE.CylinderGeometry(flangeR, flangeR, flangeThickness, 24), flangeMat);
    f2.rotation.z = Math.PI / 2.0;
    f2.position.set(l / 2.0 - flangeThickness / 2.0, 0, 0);
    group.add(f2);
    const r2 = new THREE.Mesh(new THREE.TorusGeometry(flangeR * 0.95, 0.008, 8, 24), weldMat);
    r2.rotation.y = Math.PI / 2.0;
    r2.position.set(l / 2.0, 0, 0);
    group.add(r2);

    // Branch Port (Top)
    const f3 = new THREE.Mesh(new THREE.CylinderGeometry(flangeR, flangeR, flangeThickness, 24), flangeMat);
    f3.position.set(0, h - flangeThickness / 2.0, 0);
    group.add(f3);
    const r3 = new THREE.Mesh(new THREE.TorusGeometry(flangeR * 0.95, 0.008, 8, 24), weldMat);
    r3.rotation.x = Math.PI / 2.0;
    r3.position.set(0, h, 0);
    group.add(r3);

    return group;
}

function buildInsulatedFlowSegment(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const r = sample3d.radius || 0.08;
    const l = sample3d.length || 2.0;

    const pipeMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.85
    });
    const jacketMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.3
    });
    const strapMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.9
    });

    // Inner fluid pipe body
    const pipeGeom = new THREE.CylinderGeometry(r, r, l + 0.10, 24);
    pipeGeom.rotateZ(Math.PI / 2.0);
    const pipeMesh = new THREE.Mesh(pipeGeom, pipeMat);
    group.add(pipeMesh);

    // Outer thermal insulation jacket wrapping
    const jacketR = r * 1.45;
    const jacketGeom = new THREE.CylinderGeometry(jacketR, jacketR, l, 24);
    jacketGeom.rotateZ(Math.PI / 2.0);
    const jacketMesh = new THREE.Mesh(jacketGeom, jacketMat);
    group.add(jacketMesh);

    // Metallic end caps & connecting flanges
    [-l / 2.0 - 0.02, l / 2.0 + 0.02].forEach(xPos => {
        const flange = new THREE.Mesh(new THREE.CylinderGeometry(r * 1.6, r * 1.6, 0.03, 24), strapMat);
        flange.rotation.z = Math.PI / 2.0;
        flange.position.set(xPos, 0, 0);
        group.add(flange);
    });

    // Metallic banding straps along the insulated length
    const nStraps = 6;
    for (let i = 0; i < nStraps; i++) {
        const sx = -l / 2.0 + 0.15 + (i / (nStraps - 1)) * (l - 0.30);
        const strap = new THREE.Mesh(new THREE.TorusGeometry(jacketR + 0.004, 0.008, 8, 24), strapMat);
        strap.rotation.y = Math.PI / 2.0;
        strap.position.set(sx, 0, 0);
        group.add(strap);
    }

    return group;
}

function buildFloorDrainTerminal(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.30;
    const h = sample3d.height || 0.25;

    const bronzeMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });
    const pvcMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.3
    });
    const holeMat = new THREE.MeshStandardMaterial({
        color: 0x0f172a,
        wireframe: wireframeMode
    });

    // Circular strainer rim face plate
    const topRimR = w * 0.45;
    const rimMesh = new THREE.Mesh(new THREE.CylinderGeometry(topRimR, topRimR * 0.95, 0.02, 24), bronzeMat);
    rimMesh.position.set(0, h / 2.0 - 0.01, 0);
    group.add(rimMesh);

    // Perforated strainer grate holes pattern
    for (let ring = 1; ring <= 3; ring++) {
        const rPos = ring * (topRimR * 0.22);
        const nHoles = ring * 6;
        for (let i = 0; i < nHoles; i++) {
            const angle = (i / nHoles) * Math.PI * 2.0;
            const hole = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.022, 12), holeMat);
            hole.position.set(Math.cos(angle) * rPos, h / 2.0 - 0.008, Math.sin(angle) * rPos);
            group.add(hole);
        }
    }

    // Clamping ring collar
    const clampRing = new THREE.Mesh(new THREE.CylinderGeometry(topRimR * 1.08, topRimR * 1.08, 0.025, 24), bronzeMat);
    clampRing.position.set(0, h / 2.0 - 0.03, 0);
    group.add(clampRing);

    // Drainage funnel Sump body
    const funnelGeom = new THREE.CylinderGeometry(topRimR * 0.90, w * 0.25, h * 0.45, 24);
    const funnelMesh = new THREE.Mesh(funnelGeom, pvcMat);
    funnelMesh.position.set(0, h / 2.0 - 0.22, 0);
    group.add(funnelMesh);

    // Water seal trap bucket & outlet tailpiece
    const trapBody = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.25, w * 0.25, h * 0.35, 24), pvcMat);
    trapBody.position.set(0, -h / 2.0 + h * 0.175, 0);
    group.add(trapBody);

    const outletPipe = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.18, w * 0.18, w * 0.35, 20), pvcMat);
    outletPipe.rotation.z = Math.PI / 2.0;
    outletPipe.position.set(w * 0.20, -h / 2.0 + h * 0.15, 0);
    group.add(outletPipe);

    return group;
}

function buildFlexibleShaftCoupling(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.25;
    const h = sample3d.height || 0.30;

    const hubMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });
    const spiderMat = new THREE.MeshStandardMaterial({
        color: 0xdc2626, // Red elastomeric insert
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.2
    });
    const shaftMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.85
    });

    const hubR = h * 0.38;

    // Left Shaft & Clamping Hub (Motor side)
    const shaftL = new THREE.Mesh(new THREE.CylinderGeometry(hubR * 0.45, hubR * 0.45, w * 0.50, 20), shaftMat);
    shaftL.rotation.z = Math.PI / 2.0;
    shaftL.position.set(-w * 0.45, 0, 0);
    group.add(shaftL);

    const hubL = new THREE.Mesh(new THREE.CylinderGeometry(hubR, hubR, w * 0.35, 24), hubMat);
    hubL.rotation.z = Math.PI / 2.0;
    hubL.position.set(-w * 0.18, 0, 0);
    group.add(hubL);

    // Right Shaft & Clamping Hub (Pump side)
    const shaftR = new THREE.Mesh(new THREE.CylinderGeometry(hubR * 0.45, hubR * 0.45, w * 0.50, 20), shaftMat);
    shaftR.rotation.z = Math.PI / 2.0;
    shaftR.position.set(w * 0.45, 0, 0);
    group.add(shaftR);

    const hubRMesh = new THREE.Mesh(new THREE.CylinderGeometry(hubR, hubR, w * 0.35, 24), hubMat);
    hubRMesh.rotation.z = Math.PI / 2.0;
    hubRMesh.position.set(w * 0.18, 0, 0);
    group.add(hubRMesh);

    // Center elastomeric spider coupling insert
    const spiderDisc = new THREE.Mesh(new THREE.CylinderGeometry(hubR * 1.05, hubR * 1.05, w * 0.12, 24), spiderMat);
    spiderDisc.rotation.z = Math.PI / 2.0;
    spiderDisc.position.set(0, 0, 0);
    group.add(spiderDisc);

    // Interlocking jaw teeth (4 prongs per side)
    for (let i = 0; i < 4; i++) {
        const angle = (i / 4) * Math.PI * 2.0;
        const jawL = new THREE.Mesh(new THREE.BoxGeometry(w * 0.18, hubR * 0.40, hubR * 0.30), hubMat);
        jawL.position.set(-w * 0.06, Math.cos(angle) * hubR * 0.60, Math.sin(angle) * hubR * 0.60);
        group.add(jawL);

        const jawR = new THREE.Mesh(new THREE.BoxGeometry(w * 0.18, hubR * 0.40, hubR * 0.30), hubMat);
        jawR.position.set(w * 0.06, Math.cos(angle + Math.PI / 4) * hubR * 0.60, Math.sin(angle + Math.PI / 4) * hubR * 0.60);
        group.add(jawR);
    }

    return group;
}

function buildAudiovisualDisplay(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 1.20;
    const h = sample3d.height || 0.70;
    const d = sample3d.depth || 0.10;

    const bezelMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.8
    });
    const screenMat = new THREE.MeshStandardMaterial({
        color: 0x0284c7,
        emissive: 0x0284c7,
        emissiveIntensity: 0.3,
        wireframe: wireframeMode,
        roughness: 0.1,
        metalness: 0.9
    });
    const bracketMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.7
    });
    const speakerMat = new THREE.MeshStandardMaterial({
        color: 0x64748b,
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.3
    });

    // Main widescreen monitor body
    const bezelMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d * 0.4), bezelMat);
    bezelMesh.position.set(0, 0, 0);
    group.add(bezelMesh);

    // Front screen glass display panel
    const screenMesh = new THREE.Mesh(new THREE.BoxGeometry(w * 0.94, h * 0.90, 0.005), screenMat);
    screenMesh.position.set(0, 0, d * 0.20 + 0.003);
    group.add(screenMesh);

    // VESA wall mounting bracket at rear
    const wallPlate = new THREE.Mesh(new THREE.BoxGeometry(w * 0.35, h * 0.45, 0.015), bracketMat);
    wallPlate.position.set(0, 0, -d * 0.20 - 0.015);
    group.add(wallPlate);

    const armUpper = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.04, d * 0.30), bracketMat);
    armUpper.position.set(0, h * 0.10, -d * 0.10);
    group.add(armUpper);

    const armLower = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.04, d * 0.30), bracketMat);
    armLower.position.set(0, -h * 0.10, -d * 0.10);
    group.add(armLower);

    // PA Ceiling / Wall Horn Speaker accessory mounted below screen
    const hornBase = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 0.04, 16), speakerMat);
    hornBase.position.set(0, -h / 2.0 - 0.10, 0);
    group.add(hornBase);

    const hornCone = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.05, 0.14, 20), speakerMat);
    hornCone.rotation.x = Math.PI / 2.0;
    hornCone.position.set(0, -h / 2.0 - 0.10, 0.08);
    group.add(hornCone);

    const hornBezel = new THREE.Mesh(new THREE.TorusGeometry(0.12, 0.012, 8, 24), bezelMat);
    hornBezel.position.set(0, -h / 2.0 - 0.10, 0.15);
    group.add(hornBezel);

    return group;
}

function buildNetworkRouterRack(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.48;
    const d = sample3d.depth || 0.35;
    const h = sample3d.height || 0.08;

    const chassisMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });
    const earMat = new THREE.MeshStandardMaterial({
        color: 0x475569,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.9
    });
    const portMat = new THREE.MeshStandardMaterial({
        color: 0x0f172a,
        wireframe: wireframeMode,
        roughness: 0.8,
        metalness: 0.2
    });
    const ledGreen = new THREE.MeshStandardMaterial({
        color: 0x22c55e,
        emissive: 0x22c55e,
        emissiveIntensity: 0.8,
        wireframe: wireframeMode
    });
    const ledAmber = new THREE.MeshStandardMaterial({
        color: 0xf59e0b,
        emissive: 0xf59e0b,
        emissiveIntensity: 0.8,
        wireframe: wireframeMode
    });

    // 19-inch 1U/2U metal rack chassis body
    const bodyMesh = new THREE.Mesh(new THREE.BoxGeometry(w * 0.88, h, d), chassisMat);
    group.add(bodyMesh);

    // 19-inch rack mounting ears on left and right sides
    [-w * 0.47, w * 0.47].forEach(xPos => {
        const ear = new THREE.Mesh(new THREE.BoxGeometry(w * 0.06, h, 0.015), earMat);
        ear.position.set(xPos, 0, d / 2.0 - 0.008);
        group.add(ear);

        // Rack screw holes
        [-h * 0.30, h * 0.30].forEach(yPos => {
            const hole = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.005, 0.02, 12), portMat);
            hole.rotation.x = Math.PI / 2.0;
            hole.position.set(xPos, yPos, d / 2.0 - 0.008);
            group.add(hole);
        });
    });

    // RJ45 Port Arrays on front face (2 banks of 12 ports)
    [-w * 0.20, w * 0.15].forEach(bankX => {
        const bankHousing = new THREE.Mesh(new THREE.BoxGeometry(w * 0.28, h * 0.50, 0.012), portMat);
        bankHousing.position.set(bankX, 0, d / 2.0 + 0.004);
        group.add(bankHousing);

        for (let row = 0; row < 2; row++) {
            for (let colIdx = 0; colIdx < 6; colIdx++) {
                const px = bankX - w * 0.11 + colIdx * (w * 0.042);
                const py = -h * 0.12 + row * (h * 0.24);

                const rj45 = new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.010, 0.008), chassisMat);
                rj45.position.set(px, py, d / 2.0 + 0.008);
                group.add(rj45);

                // Blinking activity LED indicators above each port
                const ledMat = (row + colIdx) % 3 === 0 ? ledAmber : ledGreen;
                const led = new THREE.Mesh(new THREE.BoxGeometry(0.004, 0.004, 0.004), ledMat);
                led.position.set(px, py + 0.008, d / 2.0 + 0.009);
                group.add(led);
            }
        }
    });

    // Status display & console port section on far right
    const consolePort = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.012, 12), chassisMat);
    consolePort.rotation.x = Math.PI / 2.0;
    consolePort.position.set(w * 0.34, -h * 0.10, d / 2.0 + 0.005);
    group.add(consolePort);

    for (let i = 0; i < 4; i++) {
        const sysLed = new THREE.Mesh(new THREE.SphereGeometry(0.003, 8, 8), i === 0 ? ledGreen : ledAmber);
        sysLed.position.set(w * 0.34 + i * 0.012 - 0.018, h * 0.20, d / 2.0 + 0.005);
        group.add(sysLed);
    }

    return group;
}

function buildThermostatController(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.12;
    const h = sample3d.height || 0.12;
    const d = sample3d.depth || 0.03;

    const bodyMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.1
    });
    const lcdMat = new THREE.MeshStandardMaterial({
        color: 0x0284c7,
        emissive: 0x0284c7,
        emissiveIntensity: 0.4,
        wireframe: wireframeMode,
        roughness: 0.1,
        metalness: 0.8
    });
    const ringMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.9
    });
    const backPlateMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.4
    });

    // Wall back mounting plate
    const backPlate = new THREE.Mesh(new THREE.BoxGeometry(w * 0.95, h * 0.95, 0.008), backPlateMat);
    backPlate.position.set(0, 0, -d / 2.0 + 0.004);
    group.add(backPlate);

    // Front main housing body (rounded smart thermostat enclosure)
    const bodyMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d * 0.70), bodyMat);
    bodyMesh.position.set(0, 0, 0);
    group.add(bodyMesh);

    // Backlit LCD digital temperature display screen
    const lcdMesh = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.32, w * 0.32, 0.006, 32), lcdMat);
    lcdMesh.rotation.x = Math.PI / 2.0;
    lcdMesh.position.set(0, h * 0.10, d / 2.0 + 0.002);
    group.add(lcdMesh);

    // Circular metallic rotary encoder dial ring
    const ringMesh = new THREE.Mesh(new THREE.TorusGeometry(w * 0.34, 0.008, 12, 32), ringMat);
    ringMesh.position.set(0, h * 0.10, d / 2.0 + 0.004);
    group.add(ringMesh);

    // Lower capacitive touch / push buttons
    [-w * 0.22, 0, w * 0.22].forEach(xPos => {
        const btn = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.004, 16), ringMat);
        btn.rotation.x = Math.PI / 2.0;
        btn.position.set(xPos, -h * 0.30, d / 2.0 + 0.002);
        group.add(btn);
    });

    return group;
}

function buildTimerRelay(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.07;
    const d = sample3d.depth || 0.06;
    const h = sample3d.height || 0.09;

    const bodyMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.2
    });
    const dialMat = new THREE.MeshStandardMaterial({
        color: 0x0f172a,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.3
    });
    const pinMat = new THREE.MeshStandardMaterial({
        color: 0xdc2626,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.5
    });
    const terminalMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.9
    });

    // DIN-rail modular casing body
    const bodyMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), bodyMat);
    group.add(bodyMesh);

    // Front raised section with transparent window cover
    const faceMesh = new THREE.Mesh(new THREE.BoxGeometry(w * 0.88, h * 0.65, d * 0.35), bodyMat);
    faceMesh.position.set(0, 0, d / 2.0 + d * 0.175);
    group.add(faceMesh);

    // Analog 24-hr dial clock face
    const dialFace = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.35, w * 0.35, 0.006, 24), dialMat);
    dialFace.rotation.x = Math.PI / 2.0;
    dialFace.position.set(0, h * 0.05, d / 2.0 + d * 0.35 + 0.002);
    group.add(dialFace);

    // 24-hr programming pushpins surrounding the dial
    for (let i = 0; i < 12; i++) {
        const angle = (i / 12.0) * Math.PI * 2.0;
        const pinX = Math.cos(angle) * (w * 0.30);
        const pinY = h * 0.05 + Math.sin(angle) * (w * 0.30);

        const pin = new THREE.Mesh(new THREE.BoxGeometry(0.003, 0.003, 0.008), pinMat);
        pin.position.set(pinX, pinY, d / 2.0 + d * 0.35 + 0.006);
        group.add(pin);
    }

    // Screw terminals on top and bottom
    [-h * 0.42, h * 0.42].forEach(yPos => {
        [-w * 0.28, w * 0.28].forEach(xPos => {
            const terminal = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.010, 12), terminalMat);
            terminal.position.set(xPos, yPos, d / 2.0 - 0.015);
            group.add(terminal);
        });
    });

    return group;
}

function buildSolarPanel(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 1.00;
    const d = sample3d.depth || 1.60;

    const frameMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });
    const panelMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.5
    });
    const rackMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.7
    });
    const gridMat = new THREE.MeshStandardMaterial({
        color: 0x38bdf8,
        wireframe: wireframeMode
    });

    const panelGroup = new THREE.Group();

    // Aluminum extruded frame
    const frameMesh = new THREE.Mesh(new THREE.BoxGeometry(w, 0.04, d), frameMat);
    panelGroup.add(frameMesh);

    // Dark blue PV cell glass surface
    const glassMesh = new THREE.Mesh(new THREE.BoxGeometry(w * 0.94, 0.008, d * 0.94), panelMat);
    glassMesh.position.set(0, 0.018, 0);
    panelGroup.add(glassMesh);

    // Grid lines for solar cells
    for (let i = -3; i <= 3; i++) {
        const lineV = new THREE.Mesh(new THREE.BoxGeometry(0.005, 0.002, d * 0.92), gridMat);
        lineV.position.set(i * (w * 0.12), 0.023, 0);
        panelGroup.add(lineV);
    }
    for (let j = -5; j <= 5; j++) {
        const lineH = new THREE.Mesh(new THREE.BoxGeometry(w * 0.92, 0.002, 0.005), gridMat);
        lineH.position.set(0, 0.023, j * (d * 0.08));
        panelGroup.add(lineH);
    }

    // Tilt angle (30 deg rack mount)
    panelGroup.rotation.x = Math.PI / 6.0;
    panelGroup.position.set(0, 0.35, 0);
    group.add(panelGroup);

    // Mounting tilt rack leg supports
    [-w * 0.38, w * 0.38].forEach(xPos => {
        const frontLeg = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.20, 12), rackMat);
        frontLeg.position.set(xPos, 0.10, d * 0.35);
        group.add(frontLeg);

        const backLeg = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.55, 12), rackMat);
        backLeg.position.set(xPos, 0.275, -d * 0.35);
        group.add(backLeg);

        const baseRail = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.03, d * 0.85), rackMat);
        baseRail.position.set(xPos, 0.015, 0);
        group.add(baseRail);
    });

    return group;
}

function buildJunctionBox(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.15;
    const d = sample3d.depth || 0.15;
    const h = sample3d.height || 0.10;

    const boxMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.7
    });
    const screwMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.9
    });
    const knockoutMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.6
    });

    // Enclosure base body
    const bodyMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), boxMat);
    group.add(bodyMesh);

    // Lid cover plate with gasket margin
    const lidMesh = new THREE.Mesh(new THREE.BoxGeometry(w * 1.04, 0.012, d * 1.04), boxMat);
    lidMesh.position.set(0, h / 2.0 + 0.006, 0);
    group.add(lidMesh);

    // 4 corner lid screws
    [-w * 0.42, w * 0.42].forEach(xPos => {
        [-d * 0.42, d * 0.42].forEach(zPos => {
            const screw = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.008, 12), screwMat);
            screw.position.set(xPos, h / 2.0 + 0.014, zPos);
            group.add(screw);
        });
    });

    // Threaded conduit knockouts on all 4 sides
    const sideOffsets = [
        { pos: [0, 0, d / 2.0 + 0.004], rot: [Math.PI / 2, 0, 0] },
        { pos: [0, 0, -d / 2.0 - 0.004], rot: [Math.PI / 2, 0, 0] },
        { pos: [w / 2.0 + 0.004, 0, 0], rot: [0, 0, Math.PI / 2] },
        { pos: [-w / 2.0 - 0.004, 0, 0], rot: [0, 0, Math.PI / 2] }
    ];

    sideOffsets.forEach(so => {
        const knockout = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.008, 16), knockoutMat);
        knockout.position.set(...so.pos);
        knockout.rotation.set(...so.rot);
        group.add(knockout);
    });

    return group;
}

function buildCircuitBreaker(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.18;
    const d = sample3d.depth || 0.12;
    const h = sample3d.height || 0.10;

    const bodyMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.1
    });
    const leverMat = new THREE.MeshStandardMaterial({
        color: 0xdc2626,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.2
    });
    const terminalMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.9
    });
    const chuteMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.5
    });

    // Modular DIN-rail housing
    const bodyMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), bodyMat);
    group.add(bodyMesh);

    // Front raised face
    const faceMesh = new THREE.Mesh(new THREE.BoxGeometry(w * 0.85, h * 0.40, d * 0.35), bodyMat);
    faceMesh.position.set(0, h * 0.10, d / 2.0 + (d * 0.175));
    group.add(faceMesh);

    // Toggle switch lever
    const leverGeom = new THREE.BoxGeometry(w * 0.15, h * 0.25, d * 0.15);
    const leverMesh = new THREE.Mesh(leverGeom, leverMat);
    leverMesh.position.set(0, h * 0.15, d / 2.0 + d * 0.30);
    leverMesh.rotation.x = -0.25;
    group.add(leverMesh);

    // Screw terminals on top and bottom
    [-h * 0.40, h * 0.40].forEach(yPos => {
        [-w * 0.30, 0, w * 0.30].forEach(xPos => {
            const terminal = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.012, 12), terminalMat);
            terminal.position.set(xPos, yPos, d / 2.0 - 0.02);
            group.add(terminal);
        });
    });

    // Arc chute chamber side vents
    for (let i = -2; i <= 2; i++) {
        const slot = new THREE.Mesh(new THREE.BoxGeometry(0.005, h * 0.50, 0.008), chuteMat);
        slot.position.set(w / 2.0 + 0.001, 0, i * 0.015);
        group.add(slot);
    }

    return group;
}

function buildAlarmDevice(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.15;
    const h = sample3d.height || 0.10;

    const housingMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.2
    });
    const strobeMat = new THREE.MeshStandardMaterial({
        color: 0xfef08a,
        emissive: 0xfef08a,
        emissiveIntensity: 0.6,
        wireframe: wireframeMode,
        transparent: true,
        opacity: 0.85
    });
    const grillMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.5
    });

    // Wall/ceiling red housing
    const baseMesh = new THREE.Mesh(new THREE.BoxGeometry(w, w, 0.03), housingMat);
    baseMesh.position.set(0, 0, -0.015);
    group.add(baseMesh);

    const bodyMesh = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.45, w * 0.48, h, 24), housingMat);
    bodyMesh.rotation.x = Math.PI / 2.0;
    group.add(bodyMesh);

    // Fluted xenon flash lens
    const lensGeom = new THREE.CylinderGeometry(w * 0.22, w * 0.25, 0.03, 16);
    lensGeom.rotateX(Math.PI / 2.0);
    const lensMesh = new THREE.Mesh(lensGeom, strobeMat);
    lensMesh.position.set(0, h * 0.20, h / 2.0 + 0.012);
    group.add(lensMesh);

    // Horn / bell sounder grill slots
    for (let i = -2; i <= 2; i++) {
        const slot = new THREE.Mesh(new THREE.BoxGeometry(w * 0.40, 0.004, 0.01), grillMat);
        slot.position.set(0, -h * 0.15 + i * 0.012, h / 2.0 + 0.002);
        group.add(slot);
    }

    return group;
}

function buildBatteryStorage(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 1.00;
    const d = sample3d.depth || 0.80;
    const h = sample3d.height || 2.00;

    const cabinetMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.6
    });
    const moduleMat = new THREE.MeshStandardMaterial({
        color: 0x0284c7,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.4
    });
    const terminalMat = new THREE.MeshStandardMaterial({
        color: 0xef4444,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.8
    });
    const ventMat = new THREE.MeshStandardMaterial({
        color: 0x0f172a,
        wireframe: wireframeMode,
        roughness: 0.6,
        metalness: 0.3
    });

    // Cabinet enclosure
    const cabMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), cabinetMat);
    group.add(cabMesh);

    // Battery cell module drawers (4 tiers)
    for (let tier = 0; tier < 4; tier++) {
        const yPos = -h * 0.35 + tier * (h * 0.22);
        const moduleMesh = new THREE.Mesh(new THREE.BoxGeometry(w * 0.88, h * 0.16, d * 0.05), moduleMat);
        moduleMesh.position.set(0, yPos, d / 2.0 + 0.01);
        group.add(moduleMesh);

        // Positive/negative terminal lugs
        [-w * 0.30, w * 0.30].forEach(xPos => {
            const lug = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 0.02, 12), terminalMat);
            lug.rotation.x = Math.PI / 2.0;
            lug.position.set(xPos, yPos, d / 2.0 + 0.04);
            group.add(lug);
        });
    }

    // Cooling vent louvers at top and bottom
    [-h * 0.45, h * 0.45].forEach(yPos => {
        const ventMesh = new THREE.Mesh(new THREE.BoxGeometry(w * 0.80, h * 0.06, 0.01), ventMat);
        ventMesh.position.set(0, yPos, d / 2.0 + 0.008);
        group.add(ventMesh);
    });

    return group;
}

function buildValve(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const bodyMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.6
    });
    const flangeMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.7
    });
    const handwheelMat = new THREE.MeshStandardMaterial({
        color: 0xdc2626,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.4
    });

    const pipeGeom = new THREE.CylinderGeometry(0.06, 0.06, 0.40, 16);
    pipeGeom.rotateZ(Math.PI / 2);
    const pipeMesh = new THREE.Mesh(pipeGeom, bodyMat);
    group.add(pipeMesh);

    [-0.20, 0.20].forEach(x => {
        const flangeGeom = new THREE.CylinderGeometry(0.09, 0.09, 0.02, 16);
        flangeGeom.rotateZ(Math.PI / 2);
        const flangeMesh = new THREE.Mesh(flangeGeom, flangeMat);
        flangeMesh.position.set(x, 0, 0);
        group.add(flangeMesh);
    });

    const casingMesh = new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 16), bodyMat);
    group.add(casingMesh);

    const neckMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.04, 0.15, 16), bodyMat);
    neckMesh.position.set(0, 0.12, 0);
    group.add(neckMesh);

    const rodMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.10, 12), flangeMat);
    rodMesh.position.set(0, 0.22, 0);
    group.add(rodMesh);

    const wheelMesh = new THREE.Mesh(new THREE.TorusGeometry(0.10, 0.015, 8, 24), handwheelMat);
    wheelMesh.rotation.x = Math.PI / 2;
    wheelMesh.position.set(0, 0.27, 0);
    group.add(wheelMesh);

    const spokeGeom = new THREE.CylinderGeometry(0.008, 0.008, 0.20, 8);
    const spoke1 = new THREE.Mesh(spokeGeom, handwheelMat);
    spoke1.rotation.z = Math.PI / 2;
    spoke1.position.set(0, 0.27, 0);
    group.add(spoke1);

    const spoke2 = new THREE.Mesh(spokeGeom, handwheelMat);
    spoke2.rotation.x = Math.PI / 2;
    spoke2.position.set(0, 0.27, 0);
    group.add(spoke2);

    return group;
}

function buildSanitaryTerminal(sample3d, options) {
    const { wireframeMode } = options;
    const group = new THREE.Group();
    const ceramicMat = new THREE.MeshStandardMaterial({
        color: 0xf8fafc,
        wireframe: wireframeMode,
        roughness: 0.1,
        metalness: 0.05
    });
    const chromeMat = new THREE.MeshStandardMaterial({
        color: 0xe2e8f0,
        wireframe: wireframeMode,
        roughness: 0.1,
        metalness: 0.9
    });
    const waterMat = new THREE.MeshStandardMaterial({
        color: 0x38bdf8,
        wireframe: wireframeMode,
        transparent: true,
        opacity: 0.6,
        roughness: 0.1
    });

    const baseGeom = new THREE.CylinderGeometry(0.15, 0.18, 0.38, 16);
    const baseMesh = new THREE.Mesh(baseGeom, ceramicMat);
    baseMesh.position.set(0, -0.21, 0.05);
    group.add(baseMesh);

    const bowlOuterGeom = new THREE.CylinderGeometry(0.20, 0.16, 0.38, 24);
    bowlOuterGeom.scale(1.0, 1.0, 1.3);
    const bowlOuter = new THREE.Mesh(bowlOuterGeom, ceramicMat);
    bowlOuter.position.set(0, -0.01, 0.08);
    group.add(bowlOuter);

    const rimGeom = new THREE.CylinderGeometry(0.21, 0.21, 0.03, 24);
    rimGeom.scale(1.0, 1.0, 1.3);
    const rimMesh = new THREE.Mesh(rimGeom, ceramicMat);
    rimMesh.position.set(0, 0.18, 0.08);
    group.add(rimMesh);

    const waterGeom = new THREE.CylinderGeometry(0.14, 0.12, 0.02, 16);
    waterGeom.scale(1.0, 1.0, 1.2);
    const waterMesh = new THREE.Mesh(waterGeom, waterMat);
    waterMesh.position.set(0, 0.05, 0.08);
    group.add(waterMesh);

    const tankGeom = new THREE.BoxGeometry(0.42, 0.45, 0.20);
    const tankMesh = new THREE.Mesh(tankGeom, ceramicMat);
    tankMesh.position.set(0, 0.175, -0.18);
    group.add(tankMesh);

    const btnGeom = new THREE.CylinderGeometry(0.025, 0.025, 0.015, 16);
    const btnMesh = new THREE.Mesh(btnGeom, chromeMat);
    btnMesh.position.set(0, 0.408, -0.18);
    group.add(btnMesh);

    return group;
}

function buildEquipmentVessel(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const vesselMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.6
    });
    const steelMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.7
    });

    const bodyGeom = new THREE.CylinderGeometry(0.45, 0.45, 1.0, 24);
    bodyGeom.rotateZ(Math.PI / 2);
    const bodyMesh = new THREE.Mesh(bodyGeom, vesselMat);
    group.add(bodyMesh);

    [-0.50, 0.50].forEach((x, idx) => {
        const capGeom = new THREE.SphereGeometry(0.45, 24, 16, 0, Math.PI * 2, 0, Math.PI / 2);
        capGeom.rotateZ(idx === 0 ? -Math.PI / 2 : Math.PI / 2);
        const capMesh = new THREE.Mesh(capGeom, vesselMat);
        capMesh.position.set(x, 0, 0);
        group.add(capMesh);
    });

    [-0.30, 0.30].forEach(x => {
        const cradleGeom = new THREE.BoxGeometry(0.08, 0.20, 0.92);
        const cradleMesh = new THREE.Mesh(cradleGeom, steelMat);
        cradleMesh.position.set(x, -0.42, 0);
        group.add(cradleMesh);
    });

    const hatchBase = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.08, 16), steelMat);
    hatchBase.position.set(0, 0.48, 0);
    group.add(hatchBase);

    const hatchCover = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 0.02, 16), steelMat);
    hatchCover.position.set(0, 0.52, 0);
    group.add(hatchCover);

    [-0.25, 0.25].forEach(x => {
        const nozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.12, 12), steelMat);
        nozzle.position.set(x, 0.48, 0);
        group.add(nozzle);
    });

    return group;
}

function buildAirTerminal(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const frameMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.2
    });
    const coreMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.3
    });

    const faceGeom = new THREE.BoxGeometry(0.60, 0.03, 0.60);
    const faceMesh = new THREE.Mesh(faceGeom, frameMat);
    faceMesh.position.set(0, -0.015, 0);
    group.add(faceMesh);

    const backMesh = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.01, 0.52), coreMat);
    backMesh.position.set(0, -0.01, 0);
    group.add(backMesh);

    [0.44, 0.32, 0.20].forEach((size, i) => {
        const louverGeom = new THREE.BoxGeometry(size, 0.015, size);
        const louverMesh = new THREE.Mesh(louverGeom, frameMat);
        louverMesh.position.set(0, -0.02 - i * 0.005, 0);
        group.add(louverMesh);
    });

    const collarGeom = new THREE.CylinderGeometry(0.18, 0.18, 0.12, 24);
    const collarMesh = new THREE.Mesh(collarGeom, coreMat);
    collarMesh.position.set(0, 0.06, 0);
    group.add(collarMesh);

    return group;
}

function buildLightFixture(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const frameMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.7
    });
    const diffuserMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        emissive: new THREE.Color(col),
        emissiveIntensity: 0.4,
        wireframe: wireframeMode,
        transparent: true,
        opacity: 0.85
    });

    const bodyGeom = new THREE.BoxGeometry(0.60, 0.10, 0.60);
    const bodyMesh = new THREE.Mesh(bodyGeom, frameMat);
    bodyMesh.position.set(0, 0.02, 0);
    group.add(bodyMesh);

    const panelGeom = new THREE.BoxGeometry(0.54, 0.01, 0.54);
    const panelMesh = new THREE.Mesh(panelGeom, diffuserMat);
    panelMesh.position.set(0, -0.03, 0);
    group.add(panelMesh);

    return group;
}

function buildElectricPanel(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.60;
    const h = sample3d.height || 0.80;
    const d = sample3d.depth || 0.20;

    const cabinetMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.6
    });
    const handleMat = new THREE.MeshStandardMaterial({
        color: 0x0f172a,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.9
    });

    const cabMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), cabinetMat);
    group.add(cabMesh);

    const doorMesh = new THREE.Mesh(new THREE.BoxGeometry(w * 0.92, h * 0.92, 0.015), cabinetMat);
    doorMesh.position.set(0, 0, d / 2.0 + 0.008);
    group.add(doorMesh);

    const handleMesh = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.12, 0.03), handleMat);
    handleMesh.position.set(w / 2.0 - 0.06, 0, d / 2.0 + 0.025);
    group.add(handleMesh);

    return group;
}

function buildOutletSwitch(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.12;
    const h = sample3d.height || 0.12;
    const d = sample3d.depth || 0.04;

    const plateMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.1
    });
    const boxMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.5
    });
    const slotMat = new THREE.MeshStandardMaterial({
        color: 0x0f172a,
        wireframe: wireframeMode
    });

    const facePlate = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.012), plateMat);
    facePlate.position.set(0, 0, 0.006);
    group.add(facePlate);

    const backBox = new THREE.Mesh(new THREE.BoxGeometry(w * 0.85, h * 0.85, d - 0.015), boxMat);
    backBox.position.set(0, 0, -(d - 0.015) / 2.0);
    group.add(backBox);

    [-w / 4.0, w / 4.0].forEach(xPos => {
        const ringGeom = new THREE.CylinderGeometry(0.022, 0.022, 0.005, 16);
        ringGeom.rotateX(Math.PI / 2.0);
        const ringMesh = new THREE.Mesh(ringGeom, plateMat);
        ringMesh.position.set(xPos, 0, 0.016);
        group.add(ringMesh);

        [-0.008, 0.008].forEach(dx => {
            const slot = new THREE.Mesh(new THREE.BoxGeometry(0.005, 0.012, 0.008), slotMat);
            slot.position.set(xPos + dx, 0, 0.017);
            group.add(slot);
        });
    });

    const rockerBtn = new THREE.Mesh(new THREE.BoxGeometry(w * 0.28, h * 0.38, 0.012), plateMat);
    rockerBtn.position.set(0, 0, 0.018);
    rockerBtn.rotation.x = 0.08;
    group.add(rockerBtn);

    return group;
}

function buildDuctAssembly(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 2.4;
    const h = sample3d.height || 0.35;
    const d = sample3d.depth || 0.50;

    const sheetMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.7
    });
    const flangeMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });

    const ductGeom = new THREE.BoxGeometry(w, h, d);
    const ductMesh = new THREE.Mesh(ductGeom, sheetMat);
    group.add(ductMesh);

    [-w / 2.0, 0, w / 2.0].forEach(xPos => {
        const flangeGeom = new THREE.BoxGeometry(0.03, h + 0.04, d + 0.04);
        const flangeMesh = new THREE.Mesh(flangeGeom, flangeMat);
        flangeMesh.position.set(xPos, 0, 0);
        group.add(flangeMesh);
    });

    return group;
}

function buildFanAssembly(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 1.2;
    const h = sample3d.height || 1.1;
    const d = sample3d.depth || 1.0;

    const casingMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.5
    });
    const motorMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.7
    });

    const casingGeom = new THREE.CylinderGeometry(h * 0.45, h * 0.45, d * 0.70, 24);
    casingGeom.rotateX(Math.PI / 2.0);
    const casingMesh = new THREE.Mesh(casingGeom, casingMat);
    casingMesh.position.set(-0.10, 0, 0);
    group.add(casingMesh);

    const outletGeom = new THREE.BoxGeometry(w * 0.45, h * 0.50, d * 0.50);
    const outletMesh = new THREE.Mesh(outletGeom, casingMat);
    outletMesh.position.set(w * 0.25, h * 0.15, 0);
    group.add(outletMesh);

    const motorGeom = new THREE.CylinderGeometry(0.12, 0.12, d * 0.35, 16);
    motorGeom.rotateX(Math.PI / 2.0);
    const motorMesh = new THREE.Mesh(motorGeom, motorMat);
    motorMesh.position.set(-0.10, 0, -d * 0.45);
    group.add(motorMesh);

    const beltGuard = new THREE.Mesh(new THREE.BoxGeometry(0.08, h * 0.65, d * 0.15), motorMat);
    beltGuard.position.set(-0.10, 0.05, -d * 0.12);
    group.add(beltGuard);

    return group;
}

function buildCoolingTower(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 1.8;
    const h = sample3d.height || 2.4;
    const d = sample3d.depth || 1.8;

    const casingMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.3
    });
    const louverMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        wireframe: wireframeMode,
        roughness: 0.6,
        metalness: 0.4
    });
    const pipeMat = new THREE.MeshStandardMaterial({
        color: 0x475569,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.8
    });

    const bodyMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h * 0.55, d), casingMat);
    bodyMesh.position.set(0, h * 0.05, 0);
    group.add(bodyMesh);

    const inletMesh = new THREE.Mesh(new THREE.BoxGeometry(w * 0.95, h * 0.25, d * 0.95), louverMat);
    inletMesh.position.set(0, -h / 2.0 + h * 0.125, 0);
    group.add(inletMesh);

    const cowlGeom = new THREE.CylinderGeometry(w * 0.28, w * 0.36, h * 0.20, 24);
    const cowlMesh = new THREE.Mesh(cowlGeom, casingMat);
    cowlMesh.position.set(0, h / 2.0 - h * 0.10, 0);
    group.add(cowlMesh);

    const fanHub = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 0.04, 16), pipeMat);
    fanHub.position.set(0, h / 2.0, 0);
    group.add(fanHub);

    const guardRing = new THREE.Mesh(new THREE.TorusGeometry(w * 0.27, 0.015, 8, 24), pipeMat);
    guardRing.rotation.x = Math.PI / 2.0;
    guardRing.position.set(0, h / 2.0, 0);
    group.add(guardRing);

    const pipeHeader = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, w * 0.60, 16), pipeMat);
    pipeHeader.rotation.z = Math.PI / 2.0;
    pipeHeader.position.set(0, h * 0.10, d / 2.0 + 0.06);
    group.add(pipeHeader);

    [-w * 0.20, w * 0.20].forEach(px => {
        const flange = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.02, 16), pipeMat);
        flange.rotation.z = Math.PI / 2.0;
        flange.position.set(px, h * 0.10, d / 2.0 + 0.06);
        group.add(flange);
    });

    return group;
}

function buildFireSuppression(sample3d, options) {
    const { wireframeMode } = options;
    const group = new THREE.Group();
    const h = sample3d.height || 0.35;

    const brassMat = new THREE.MeshStandardMaterial({
        color: 0xd97706,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });
    const bulbMat = new THREE.MeshStandardMaterial({
        color: 0xef4444,
        emissive: 0xdc2626,
        emissiveIntensity: 0.5,
        wireframe: wireframeMode,
        transparent: true,
        opacity: 0.85
    });

    const nippleMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, h * 0.25, 16), brassMat);
    nippleMesh.position.set(0, h / 2.0 - h * 0.125, 0);
    group.add(nippleMesh);

    [-0.012, 0.012].forEach(ry => {
        const threadRing = new THREE.Mesh(new THREE.TorusGeometry(0.026, 0.003, 8, 16), brassMat);
        threadRing.rotation.x = Math.PI / 2.0;
        threadRing.position.set(0, h / 2.0 - h * 0.125 + ry, 0);
        group.add(threadRing);
    });

    const armGeom = new THREE.CylinderGeometry(0.006, 0.006, h * 0.45, 12);
    [-0.03, 0.03].forEach((ax, idx) => {
        const arm = new THREE.Mesh(armGeom, brassMat);
        arm.position.set(ax, 0, 0);
        arm.rotation.z = idx === 0 ? -0.15 : 0.15;
        group.add(arm);
    });

    const bulbMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.009, 0.009, h * 0.22, 12), bulbMat);
    bulbMesh.position.set(0, 0.02, 0);
    group.add(bulbMesh);

    const deflectorMesh = new THREE.Mesh(new THREE.CylinderGeometry(h * 0.35, h * 0.35, 0.008, 16), brassMat);
    deflectorMesh.position.set(0, -h / 2.0 + 0.02, 0);
    group.add(deflectorMesh);

    for (let i = 0; i < 8; i++) {
        const angle = (i / 8) * Math.PI * 2.0;
        const notch = new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.009, h * 0.12), brassMat);
        notch.position.set(Math.cos(angle) * h * 0.25, -h / 2.0 + 0.02, Math.sin(angle) * h * 0.25);
        notch.rotation.y = -angle;
        group.add(notch);
    }

    return group;
}

function buildPowerPlant(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 1.6;
    const h = sample3d.height || 1.4;
    const d = sample3d.depth || 1.2;

    const bodyMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.6
    });
    const skidMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });
    const porcelainMat = new THREE.MeshStandardMaterial({
        color: 0x78350f,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.2
    });

    const skidMesh = new THREE.Mesh(new THREE.BoxGeometry(w * 1.05, 0.08, d * 1.05), skidMat);
    skidMesh.position.set(0, -h / 2.0 + 0.04, 0);
    group.add(skidMesh);

    const mainTank = new THREE.Mesh(new THREE.BoxGeometry(w * 0.70, h * 0.58, d * 0.60), bodyMat);
    mainTank.position.set(0, -0.02, 0);
    group.add(mainTank);

    [-w * 0.40, w * 0.40].forEach(rx => {
        for (let i = -3; i <= 3; i++) {
            const fin = new THREE.Mesh(new THREE.BoxGeometry(0.015, h * 0.48, d * 0.10), bodyMat);
            fin.position.set(rx, -0.02, i * (d * 0.08));
            group.add(fin);
        }
    });

    [-w * 0.18, 0, w * 0.18].forEach(bx => {
        const bushingBase = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.045, h * 0.15, 12), porcelainMat);
        bushingBase.position.set(bx, h * 0.32, -d * 0.10);
        group.add(bushingBase);

        for (let r = 0; r < 3; r++) {
            const rib = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.03, 0.015, 12), porcelainMat);
            rib.position.set(bx, h * 0.28 + r * 0.04, -d * 0.10);
            group.add(rib);
        }
    });

    const conservatorGeom = new THREE.CylinderGeometry(0.12, 0.12, w * 0.50, 20);
    conservatorGeom.rotateZ(Math.PI / 2.0);
    const conservator = new THREE.Mesh(conservatorGeom, bodyMat);
    conservator.position.set(0, h * 0.38, d * 0.15);
    group.add(conservator);

    return group;
}

function buildVibrationIsolator(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.50;
    const d = sample3d.depth || 0.50;
    const h = sample3d.height || 0.45;

    const plateMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });
    const springMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.85
    });
    const padMat = new THREE.MeshStandardMaterial({
        color: 0x0f172a,
        wireframe: wireframeMode,
        roughness: 0.9,
        metalness: 0.05
    });

    const plateThickness = 0.025;
    const topPlate = new THREE.Mesh(new THREE.BoxGeometry(w, plateThickness, d), plateMat);
    topPlate.position.set(0, h / 2.0 - plateThickness / 2.0, 0);
    group.add(topPlate);

    const botPlate = new THREE.Mesh(new THREE.BoxGeometry(w, plateThickness, d), plateMat);
    botPlate.position.set(0, -h / 2.0 + plateThickness / 2.0, 0);
    group.add(botPlate);

    const topPad = new THREE.Mesh(new THREE.BoxGeometry(w * 0.90, 0.02, d * 0.90), padMat);
    topPad.position.set(0, h / 2.0 - plateThickness - 0.01, 0);
    group.add(topPad);

    const botPad = new THREE.Mesh(new THREE.BoxGeometry(w * 0.90, 0.02, d * 0.90), padMat);
    botPad.position.set(0, -h / 2.0 + plateThickness + 0.01, 0);
    group.add(botPad);

    const springRadius = 0.08;
    const springTubeRadius = 0.015;
    const springH = h - 2 * plateThickness - 0.04;
    const nTurns = 4;

    const sxOffsets = [-w * 0.25, w * 0.25];
    const szOffsets = [-d * 0.25, d * 0.25];

    sxOffsets.forEach(sx => {
        szOffsets.forEach(sz => {
            for (let t = 0; t < nTurns; t++) {
                const torusY = -springH / 2.0 + (t + 0.5) * (springH / nTurns);
                const springTurn = new THREE.Mesh(new THREE.TorusGeometry(springRadius, springTubeRadius, 10, 24), springMat);
                springTurn.rotation.x = Math.PI / 2.0;
                springTurn.position.set(sx, torusY, sz);
                group.add(springTurn);
            }
        });
    });

    return group;
}

function buildCoilHeatExchanger(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 1.2;
    const h = sample3d.height || 0.80;
    const d = sample3d.depth || 0.40;

    const frameMat = new THREE.MeshStandardMaterial({
        color: 0x475569,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.6
    });
    const finMat = new THREE.MeshStandardMaterial({
        color: 0xcbd5e1,
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.5
    });
    const copperMat = new THREE.MeshStandardMaterial({
        color: 0xb45309,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });
    const headerMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.7
    });

    const topFrame = new THREE.Mesh(new THREE.BoxGeometry(w, 0.03, d), frameMat);
    topFrame.position.set(0, h / 2.0 - 0.015, 0);
    group.add(topFrame);

    const botFrame = new THREE.Mesh(new THREE.BoxGeometry(w, 0.03, d), frameMat);
    botFrame.position.set(0, -h / 2.0 + 0.015, 0);
    group.add(botFrame);

    const sideL = new THREE.Mesh(new THREE.BoxGeometry(0.03, h - 0.06, d), frameMat);
    sideL.position.set(-w / 2.0 + 0.015, 0, 0);
    group.add(sideL);

    const sideR = new THREE.Mesh(new THREE.BoxGeometry(0.03, h - 0.06, d), frameMat);
    sideR.position.set(w / 2.0 - 0.015, 0, 0);
    group.add(sideR);

    const finPack = new THREE.Mesh(new THREE.BoxGeometry(w * 0.78, h * 0.88, d * 0.55), finMat);
    group.add(finPack);

    const nFins = 8;
    for (let i = 0; i < nFins; i++) {
        const fy = -h * 0.40 + (i + 0.5) * (h * 0.80 / nFins);
        const finLine = new THREE.Mesh(new THREE.BoxGeometry(w * 0.80, 0.01, d * 0.58), finMat);
        finLine.position.set(0, fy, 0);
        group.add(finLine);
    }

    const rows = 4;
    const cols = 2;
    for (let r = 0; r < rows; r++) {
        const ry = -h * 0.32 + r * (h * 0.22);
        for (let c = 0; c < cols; c++) {
            const rz = -d * 0.15 + c * (d * 0.30);

            const tube = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, w * 0.82, 12), copperMat);
            tube.rotation.z = Math.PI / 2.0;
            tube.position.set(0, ry, rz);
            group.add(tube);

            const ubend = new THREE.Mesh(new THREE.TorusGeometry(0.03, 0.015, 8, 16, Math.PI), copperMat);
            ubend.position.set(-w * 0.39, ry, rz);
            ubend.rotation.y = Math.PI / 2.0;
            group.add(ubend);
        }
    }

    [-d * 0.15, d * 0.15].forEach((hz, idx) => {
        const header = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, h * 0.90, 16), headerMat);
        header.position.set(w * 0.42, 0, hz);
        group.add(header);

        const nozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.12, 12), headerMat);
        nozzle.rotation.z = Math.PI / 2.0;
        nozzle.position.set(w * 0.42 + 0.06, idx === 0 ? h * 0.25 : -h * 0.25, hz);
        group.add(nozzle);

        const flange = new THREE.Mesh(new THREE.TorusGeometry(0.045, 0.01, 8, 16), frameMat);
        flange.rotation.y = Math.PI / 2.0;
        flange.position.set(w * 0.42 + 0.12, idx === 0 ? h * 0.25 : -h * 0.25, hz);
        group.add(flange);
    });

    return group;
}

function buildAirFilter(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.60;
    const h = sample3d.height || 0.60;
    const d = sample3d.depth || 0.30;

    const frameMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.7
    });
    const mediaMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.8,
        metalness: 0.1
    });
    const sealMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        wireframe: wireframeMode,
        roughness: 0.9,
        metalness: 0.1
    });

    const frameThickness = 0.025;

    const topFrame = new THREE.Mesh(new THREE.BoxGeometry(w, frameThickness, d), frameMat);
    topFrame.position.set(0, h / 2.0 - frameThickness / 2.0, 0);
    group.add(topFrame);

    const botFrame = new THREE.Mesh(new THREE.BoxGeometry(w, frameThickness, d), frameMat);
    botFrame.position.set(0, -h / 2.0 + frameThickness / 2.0, 0);
    group.add(botFrame);

    const leftFrame = new THREE.Mesh(new THREE.BoxGeometry(frameThickness, h - 2 * frameThickness, d), frameMat);
    leftFrame.position.set(-w / 2.0 + frameThickness / 2.0, 0, 0);
    group.add(leftFrame);

    const rightFrame = new THREE.Mesh(new THREE.BoxGeometry(frameThickness, h - 2 * frameThickness, d), frameMat);
    rightFrame.position.set(w / 2.0 - frameThickness / 2.0, 0, 0);
    group.add(rightFrame);

    const headerLip = new THREE.Mesh(new THREE.BoxGeometry(w + 0.02, h + 0.02, 0.015), frameMat);
    headerLip.position.set(0, 0, d / 2.0);
    group.add(headerLip);

    const gasket = new THREE.Mesh(new THREE.BoxGeometry(w + 0.01, h + 0.01, 0.01), sealMat);
    gasket.position.set(0, 0, -d / 2.0);
    group.add(gasket);

    const nVBanks = 4;
    const vWidth = (w - 2 * frameThickness) / nVBanks;
    const innerH = h - 2 * frameThickness;
    const innerD = d - 0.04;

    for (let i = 0; i < nVBanks; i++) {
        const vx = -w / 2.0 + frameThickness + (i + 0.5) * vWidth;

        const leg1 = new THREE.Mesh(new THREE.BoxGeometry(0.01, innerH, innerD * 0.95), mediaMat);
        leg1.position.set(vx - vWidth * 0.22, 0, 0);
        leg1.rotation.y = 0.28;
        group.add(leg1);

        const leg2 = new THREE.Mesh(new THREE.BoxGeometry(0.01, innerH, innerD * 0.95), mediaMat);
        leg2.position.set(vx + vWidth * 0.22, 0, 0);
        leg2.rotation.y = -0.28;
        group.add(leg2);
    }

    return group;
}

function buildRadiatorHeater(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 1.0;
    const h = sample3d.height || 0.60;
    const d = sample3d.depth || 0.15;

    const bodyMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.1
    });
    const valveMat = new THREE.MeshStandardMaterial({
        color: 0xf8fafc,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.3
    });
    const chromeMat = new THREE.MeshStandardMaterial({
        color: 0xe2e8f0,
        wireframe: wireframeMode,
        roughness: 0.1,
        metalness: 0.9
    });

    const topPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, w, 16), chromeMat);
    topPipe.rotation.z = Math.PI / 2.0;
    topPipe.position.set(0, h / 2.0 - 0.03, 0);
    group.add(topPipe);

    const botPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, w, 16), chromeMat);
    botPipe.rotation.z = Math.PI / 2.0;
    botPipe.position.set(0, -h / 2.0 + 0.03, 0);
    group.add(botPipe);

    const nCols = 10;
    for (let i = 0; i < nCols; i++) {
        const cx = -w / 2.0 + (i + 0.5) * (w / nCols);

        const column = new THREE.Mesh(new THREE.CylinderGeometry(0.032, 0.032, h - 0.08, 16), bodyMat);
        column.position.set(cx, 0, 0);
        group.add(column);

        const finFront = new THREE.Mesh(new THREE.BoxGeometry(w / nCols * 0.85, h - 0.08, 0.01), bodyMat);
        finFront.position.set(cx, 0, d / 2.0 - 0.01);
        group.add(finFront);

        const finBack = new THREE.Mesh(new THREE.BoxGeometry(w / nCols * 0.85, h - 0.08, 0.01), bodyMat);
        finBack.position.set(cx, 0, -d / 2.0 + 0.01);
        group.add(finBack);
    }

    const trvBase = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.08, 12), chromeMat);
    trvBase.position.set(w / 2.0 + 0.04, h / 2.0 - 0.03, 0);
    trvBase.rotation.z = Math.PI / 2.0;
    group.add(trvBase);

    const trvKnob = new THREE.Mesh(new THREE.CylinderGeometry(0.032, 0.035, 0.06, 16), valveMat);
    trvKnob.position.set(w / 2.0 + 0.10, h / 2.0 - 0.03, 0);
    trvKnob.rotation.z = Math.PI / 2.0;
    group.add(trvKnob);

    const dialRing = new THREE.Mesh(new THREE.TorusGeometry(0.034, 0.005, 8, 16), chromeMat);
    dialRing.rotation.y = Math.PI / 2.0;
    dialRing.position.set(w / 2.0 + 0.08, h / 2.0 - 0.03, 0);
    group.add(dialRing);

    const retElbow = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.08, 12), chromeMat);
    retElbow.position.set(w / 2.0 + 0.04, -h / 2.0 + 0.03, 0);
    retElbow.rotation.z = Math.PI / 2.0;
    group.add(retElbow);

    return group;
}

function buildCombustionBurner(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.80;
    const h = sample3d.height || 0.50;
    const d = sample3d.depth || 0.50;

    const casingMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.5
    });
    const stainlessMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.8
    });
    const darkMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.6
    });
    const brassMat = new THREE.MeshStandardMaterial({
        color: 0xd97706,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.7
    });

    const housing = new THREE.Mesh(new THREE.BoxGeometry(w * 0.50, h * 0.75, d * 0.70), casingMat);
    housing.position.set(-w * 0.15, 0, 0);
    group.add(housing);

    const motor = new THREE.Mesh(new THREE.CylinderGeometry(h * 0.22, h * 0.22, d * 0.35, 20), darkMat);
    motor.rotation.x = Math.PI / 2.0;
    motor.position.set(-w * 0.15, 0, -d * 0.42);
    group.add(motor);

    const blastTube = new THREE.Mesh(new THREE.CylinderGeometry(h * 0.22, h * 0.22, w * 0.45, 24), stainlessMat);
    blastTube.rotation.z = Math.PI / 2.0;
    blastTube.position.set(w * 0.25, h * 0.05, 0);
    group.add(blastTube);

    const mountingFlange = new THREE.Mesh(new THREE.CylinderGeometry(h * 0.32, h * 0.32, 0.025, 24), stainlessMat);
    mountingFlange.rotation.z = Math.PI / 2.0;
    mountingFlange.position.set(w * 0.12, h * 0.05, 0);
    group.add(mountingFlange);

    const fuelPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, d * 0.60, 16), brassMat);
    fuelPipe.rotation.x = Math.PI / 2.0;
    fuelPipe.position.set(-w * 0.10, -h * 0.38, d * 0.15);
    group.add(fuelPipe);

    const solenoidValve = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.12, 0.08), darkMat);
    solenoidValve.position.set(-w * 0.10, -h * 0.32, d * 0.15);
    group.add(solenoidValve);

    const valveCoil = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.06, 12), brassMat);
    valveCoil.position.set(-w * 0.10, -h * 0.23, d * 0.15);
    group.add(valveCoil);

    const controlBox = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.18, 0.08), darkMat);
    controlBox.position.set(-w * 0.15, h * 0.20, d * 0.38);
    group.add(controlBox);

    const flameScanner = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.15, 12), brassMat);
    flameScanner.rotation.z = Math.PI / 2.0;
    flameScanner.position.set(0, h * 0.20, d * 0.38);
    group.add(flameScanner);

    return group;
}

function buildFlowMeter(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.35;
    const d = sample3d.depth || 0.20;
    const h = sample3d.height || 0.25;

    const brassMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });
    const stainlessMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.85
    });
    const housingMat = new THREE.MeshStandardMaterial({
        color: 0x0284c7,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.5
    });
    const lcdMat = new THREE.MeshStandardMaterial({
        color: 0x065f46,
        emissive: 0x047857,
        emissiveIntensity: 0.4,
        wireframe: wireframeMode
    });
    const darkMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        wireframe: wireframeMode
    });

    const tubeGeom = new THREE.CylinderGeometry(0.045, 0.045, w, 24);
    tubeGeom.rotateZ(Math.PI / 2.0);
    const tubeMesh = new THREE.Mesh(tubeGeom, brassMat);
    group.add(tubeMesh);

    [-w / 2.0 + 0.01, w / 2.0 - 0.01].forEach(xPos => {
        const flangeGeom = new THREE.CylinderGeometry(0.075, 0.075, 0.02, 20);
        flangeGeom.rotateZ(Math.PI / 2.0);
        const flangeMesh = new THREE.Mesh(flangeGeom, brassMat);
        flangeMesh.position.set(xPos, 0, 0);
        group.add(flangeMesh);

        const ringMesh = new THREE.Mesh(new THREE.TorusGeometry(0.065, 0.01, 8, 20), darkMat);
        ringMesh.rotation.y = Math.PI / 2.0;
        ringMesh.position.set(xPos, 0, 0);
        group.add(ringMesh);
    });

    const sensorBodyGeom = new THREE.CylinderGeometry(0.06, 0.06, w * 0.40, 20);
    sensorBodyGeom.rotateZ(Math.PI / 2.0);
    const sensorBody = new THREE.Mesh(sensorBodyGeom, housingMat);
    group.add(sensorBody);

    const neckMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.025, h * 0.35, 16), stainlessMat);
    neckMesh.position.set(0, h * 0.15, 0);
    group.add(neckMesh);

    const headHousing = new THREE.Mesh(new THREE.CylinderGeometry(d * 0.40, d * 0.40, h * 0.38, 24), housingMat);
    headHousing.rotation.x = Math.PI / 2.0;
    headHousing.position.set(0, h * 0.35, 0);
    group.add(headHousing);

    const screenMesh = new THREE.Mesh(new THREE.BoxGeometry(d * 0.50, h * 0.22, 0.008), lcdMat);
    screenMesh.position.set(0, h * 0.35, d * 0.20 + 0.005);
    group.add(screenMesh);

    const bezelMesh = new THREE.Mesh(new THREE.BoxGeometry(d * 0.58, h * 0.28, 0.005), darkMat);
    bezelMesh.position.set(0, h * 0.35, d * 0.20 + 0.002);
    group.add(bezelMesh);

    return group;
}

function buildFlowInstrument(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.15;
    const h = sample3d.height || 0.25;

    const stainlessMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.85
    });
    const brassMat = new THREE.MeshStandardMaterial({
        color: 0xd97706,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });
    const dialMat = new THREE.MeshStandardMaterial({
        color: 0xf8fafc,
        wireframe: wireframeMode,
        roughness: 0.1
    });
    const needleMat = new THREE.MeshStandardMaterial({
        color: 0xdc2626,
        wireframe: wireframeMode
    });
    const glassMat = new THREE.MeshStandardMaterial({
        color: 0xe0f2fe,
        transparent: true,
        opacity: 0.4,
        wireframe: wireframeMode
    });

    const probeMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, h * 0.45, 12), stainlessMat);
    probeMesh.position.set(0, -h * 0.22, 0);
    group.add(probeMesh);

    const hexFitting = new THREE.Mesh(new THREE.CylinderGeometry(0.016, 0.016, 0.025, 6), brassMat);
    hexFitting.position.set(0, -0.02, 0);
    group.add(hexFitting);

    const caseGeom = new THREE.CylinderGeometry(w * 0.45, w * 0.45, 0.035, 24);
    caseGeom.rotateX(Math.PI / 2.0);
    const caseMesh = new THREE.Mesh(caseGeom, stainlessMat);
    caseMesh.position.set(0, h * 0.20, 0);
    group.add(caseMesh);

    const dialGeom = new THREE.CylinderGeometry(w * 0.40, w * 0.40, 0.004, 24);
    dialGeom.rotateX(Math.PI / 2.0);
    const dialMesh = new THREE.Mesh(dialGeom, dialMat);
    dialMesh.position.set(0, h * 0.20, 0.018);
    group.add(dialMesh);

    const needleMesh = new THREE.Mesh(new THREE.BoxGeometry(0.004, w * 0.30, 0.002), needleMat);
    needleMesh.position.set(0, h * 0.20 + 0.02, 0.021);
    needleMesh.rotation.z = -Math.PI / 4.0;
    group.add(needleMesh);

    const pinMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, 0.006, 12), brassMat);
    pinMesh.rotation.x = Math.PI / 2.0;
    pinMesh.position.set(0, h * 0.20, 0.022);
    group.add(pinMesh);

    const bezelMesh = new THREE.Mesh(new THREE.TorusGeometry(w * 0.44, 0.006, 8, 24), stainlessMat);
    bezelMesh.position.set(0, h * 0.20, 0.020);
    group.add(bezelMesh);

    const glassGeom = new THREE.CylinderGeometry(w * 0.42, w * 0.42, 0.002, 24);
    glassGeom.rotateX(Math.PI / 2.0);
    const glassMesh = new THREE.Mesh(glassGeom, glassMat);
    glassMesh.position.set(0, h * 0.20, 0.023);
    group.add(glassMesh);

    return group;
}

function buildValveActuator(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.25;
    const d = sample3d.depth || 0.20;
    const h = sample3d.height || 0.30;

    const housingMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.5
    });
    const steelMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.7
    });
    const leverMat = new THREE.MeshStandardMaterial({
        color: 0xdc2626,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.3
    });
    const indicatorMat = new THREE.MeshStandardMaterial({
        color: 0x16a34a,
        wireframe: wireframeMode
    });

    const housingMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h * 0.55, d), housingMat);
    group.add(housingMesh);

    const stemMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, h * 0.25, 16), steelMat);
    stemMesh.position.set(0, -h * 0.38, 0);
    group.add(stemMesh);

    const flangeMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.065, 0.065, 0.015, 16), steelMat);
    flangeMesh.position.set(0, -h * 0.48, 0);
    group.add(flangeMesh);

    const leverShaft = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, w * 0.65, 12), steelMat);
    leverShaft.rotation.z = Math.PI / 2.0;
    leverShaft.position.set(0, h * 0.30, 0);
    group.add(leverShaft);

    const leverHandle = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.012, 0.08, 12), leverMat);
    leverHandle.position.set(w * 0.32, h * 0.30, 0);
    group.add(leverHandle);

    const indicatorDome = new THREE.Mesh(new THREE.CylinderGeometry(0.035, 0.035, 0.025, 16), indicatorMat);
    indicatorDome.position.set(0, h * 0.31, 0);
    group.add(indicatorDome);

    const arrowLine = new THREE.Mesh(new THREE.BoxGeometry(0.008, 0.004, 0.05), leverMat);
    arrowLine.position.set(0, h * 0.325, 0);
    group.add(arrowLine);

    const glandBox = new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.08, 0.05), housingMat);
    glandBox.position.set(-w / 2.0 - 0.02, -h * 0.08, 0);
    group.add(glandBox);

    const glandNut = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.03, 12), steelMat);
    glandNut.rotation.z = Math.PI / 2.0;
    glandNut.position.set(-w / 2.0 - 0.04, -h * 0.08, 0);
    group.add(glandNut);

    return group;
}

function buildGreaseOilInterceptor(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 1.20;
    const d = sample3d.depth || 0.80;
    const h = sample3d.height || 0.70;

    const tankMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.3
    });
    const baffleMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.6
    });
    const pipeMat = new THREE.MeshStandardMaterial({
        color: 0x0284c7,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.5
    });
    const coverMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        wireframe: wireframeMode,
        roughness: 0.6,
        metalness: 0.4
    });

    const tankMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), tankMat);
    group.add(tankMesh);

    const rimFrame = new THREE.Mesh(new THREE.BoxGeometry(w * 1.04, 0.03, d * 1.04), tankMat);
    rimFrame.position.set(0, h / 2.0 + 0.015, 0);
    group.add(rimFrame);

    const baffle1 = new THREE.Mesh(new THREE.BoxGeometry(0.015, h * 0.75, d * 0.92), baffleMat);
    baffle1.position.set(-w * 0.18, -h * 0.10, 0);
    group.add(baffle1);

    const baffle2 = new THREE.Mesh(new THREE.BoxGeometry(0.015, h * 0.70, d * 0.92), baffleMat);
    baffle2.position.set(w * 0.18, h * 0.08, 0);
    group.add(baffle2);

    const inletPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.15, 16), pipeMat);
    inletPipe.rotation.z = Math.PI / 2.0;
    inletPipe.position.set(-w / 2.0 - 0.06, h * 0.18, 0);
    group.add(inletPipe);

    const inletDrop = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, h * 0.40, 16), pipeMat);
    inletDrop.position.set(-w / 2.0 + 0.05, 0, 0);
    group.add(inletDrop);

    const outletPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.15, 16), pipeMat);
    outletPipe.rotation.z = Math.PI / 2.0;
    outletPipe.position.set(w / 2.0 + 0.06, h * 0.12, 0);
    group.add(outletPipe);

    const outletDrop = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, h * 0.45, 16), pipeMat);
    outletDrop.position.set(w / 2.0 - 0.05, -h * 0.05, 0);
    group.add(outletDrop);

    [-w * 0.25, w * 0.25].forEach(xPos => {
        const manhole = new THREE.Mesh(new THREE.CylinderGeometry(d * 0.24, d * 0.24, 0.025, 20), coverMat);
        manhole.position.set(xPos, h / 2.0 + 0.03, 0);
        group.add(manhole);

        const boltRing = new THREE.Mesh(new THREE.TorusGeometry(d * 0.22, 0.008, 8, 20), baffleMat);
        boltRing.rotation.x = Math.PI / 2.0;
        boltRing.position.set(xPos, h / 2.0 + 0.04, 0);
        group.add(boltRing);
    });

    return group;
}

function buildHumidifierUnit(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.80;
    const d = sample3d.depth || 0.50;
    const h = sample3d.height || 0.60;

    const cabinetMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.5
    });
    const panelMat = new THREE.MeshStandardMaterial({
        color: 0x0f172a,
        wireframe: wireframeMode
    });
    const stainlessMat = new THREE.MeshStandardMaterial({
        color: 0xcbd5e1,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.85
    });
    const brassMat = new THREE.MeshStandardMaterial({
        color: 0xd97706,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });

    const cabinetMesh = new THREE.Mesh(new THREE.BoxGeometry(w * 0.48, h, d), cabinetMat);
    cabinetMesh.position.set(-w * 0.25, 0, 0);
    group.add(cabinetMesh);

    const controlPanel = new THREE.Mesh(new THREE.BoxGeometry(0.01, h * 0.35, d * 0.45), panelMat);
    controlPanel.position.set(-w * 0.49 - 0.002, h * 0.15, 0);
    group.add(controlPanel);

    [-h * 0.15, h * 0.15].forEach(yPos => {
        const manifoldTube = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, w * 0.58, 16), stainlessMat);
        manifoldTube.rotation.z = Math.PI / 2.0;
        manifoldTube.position.set(w * 0.18, yPos, 0);
        group.add(manifoldTube);

        for (let i = 0; i < 5; i++) {
            const nx = -w * 0.05 + i * (w * 0.11);
            const nozzle = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.005, 0.018, 12), stainlessMat);
            nozzle.position.set(nx, yPos + 0.02, 0);
            group.add(nozzle);
        }
    });

    const waterInlet = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.06, 12), brassMat);
    waterInlet.position.set(-w * 0.35, -h / 2.0 - 0.03, d * 0.20);
    group.add(waterInlet);

    const drainValve = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.06, 12), brassMat);
    drainValve.position.set(-w * 0.35, -h / 2.0 - 0.03, -d * 0.20);
    group.add(drainValve);

    return group;
}
