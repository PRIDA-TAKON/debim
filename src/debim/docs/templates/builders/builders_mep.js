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
