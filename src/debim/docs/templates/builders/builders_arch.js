/**
 * Architectural 3D Geometry Builders for debim Class Directory.
 * Covers: Stair Concrete, Stair Flight, Ramp, Railing, Door, Window, Roof, Furniture, Transport Element, Curtain Wall, Shading Device, Wall System, Covering, Chimney.
 */

function buildStairConcrete(sample3d, options) {
    const { wireframeMode, xrayMode, isRC, col } = options;
    const concreteGroup = new THREE.Group();
    const steps = sample3d.steps || 10;
    const w = sample3d.width || 1.2;
    const h = sample3d.height || 2.4;
    const d = sample3d.depth || 2.5;
    const rh = h / steps;
    const td = d / steps;
    const slopeAngle = Math.atan2(h, d);
    const slopeLen = Math.hypot(d, h);
    const waistThick = 0.14;

    const isTransparent = isRC && xrayMode;
    const concreteMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.7,
        metalness: 0.1,
        transparent: isTransparent,
        opacity: isTransparent ? 0.38 : 1.0,
        depthWrite: !isTransparent
    });

    const slabGeom = new THREE.BoxGeometry(w, waistThick, slopeLen);
    const slabMesh = new THREE.Mesh(slabGeom, concreteMat);
    slabMesh.position.set(0, -waistThick * 0.50, 0);
    slabMesh.rotation.x = -slopeAngle;
    concreteGroup.add(slabMesh);

    const stepGeom = new THREE.BoxGeometry(w, rh, td);
    for (let i = 0; i < steps; i++) {
        const stepMesh = new THREE.Mesh(stepGeom, concreteMat);
        const yPos = -h / 2.0 + i * rh + rh / 2.0;
        const zPos = -d / 2.0 + i * td + td / 2.0;
        stepMesh.position.set(0, yPos, zPos);
        concreteGroup.add(stepMesh);
    }

    return concreteGroup;
}

function buildStairFlight(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const steps = sample3d.steps || 10;
    const w = sample3d.width || 1.2;
    const h = sample3d.height || 2.4;
    const d = sample3d.depth || 2.5;
    const rh = h / steps;
    const td = d / steps;

    const stringerLength = Math.hypot(d, h) + 0.30;
    const stringerAngle = Math.atan2(h, d);
    const stringerGeom = new THREE.BoxGeometry(0.06, 0.22, stringerLength);
    const stringerMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col).multiplyScalar(0.7),
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.5
    });

    [-w / 2.0 + 0.03, w / 2.0 - 0.03].forEach(xOffset => {
        const stringerMesh = new THREE.Mesh(stringerGeom, stringerMat);
        stringerMesh.position.set(xOffset, 0, 0);
        stringerMesh.rotation.x = -stringerAngle;
        group.add(stringerMesh);
    });

    const treadMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.2
    });
    const treadThick = 0.04;
    const treadGeom = new THREE.BoxGeometry(w - 0.10, treadThick, td);

    for (let i = 0; i < steps; i++) {
        const treadMesh = new THREE.Mesh(treadGeom, treadMat);
        const yPos = -h / 2.0 + (i + 1) * rh - treadThick / 2.0;
        const zPos = -d / 2.0 + i * td + td / 2.0;
        treadMesh.position.set(0, yPos, zPos);
        group.add(treadMesh);
    }

    return group;
}

function buildRamp(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 1.5;
    const d = sample3d.depth || 4.0;
    const h = sample3d.height || 1.0;
    const rampLength = Math.hypot(d, h);
    const rampAngle = Math.atan2(h, d);

    const rampMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.6,
        metalness: 0.1
    });

    const slabGeom = new THREE.BoxGeometry(w, 0.12, rampLength);
    const slabMesh = new THREE.Mesh(slabGeom, rampMat);
    slabMesh.rotation.x = -rampAngle;
    group.add(slabMesh);

    const curbGeom = new THREE.BoxGeometry(0.08, 0.25, rampLength);
    const curbMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col).multiplyScalar(0.75),
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.2
    });

    [-w / 2.0 + 0.04, w / 2.0 - 0.04].forEach(xOffset => {
        const curbMesh = new THREE.Mesh(curbGeom, curbMat);
        curbMesh.position.set(xOffset, 0.08 * Math.cos(rampAngle), 0);
        curbMesh.rotation.x = -rampAngle;
        group.add(curbMesh);
    });

    return group;
}

function buildRailing(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const len = sample3d.length || 3.0;
    const h = sample3d.height || 1.0;

    const metalMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.7
    });

    const topGeom = new THREE.CylinderGeometry(0.025, 0.025, len, 16);
    topGeom.rotateZ(Math.PI / 2.0);
    const topMesh = new THREE.Mesh(topGeom, metalMat);
    topMesh.position.set(0, h / 2.0 - 0.025, 0);
    group.add(topMesh);

    const botGeom = new THREE.CylinderGeometry(0.015, 0.015, len, 16);
    botGeom.rotateZ(Math.PI / 2.0);
    const botMesh = new THREE.Mesh(botGeom, metalMat);
    botMesh.position.set(0, -h / 2.0 + 0.05, 0);
    group.add(botMesh);

    const postSpacing = 0.15;
    const nPosts = Math.max(2, Math.floor(len / postSpacing) + 1);
    const postHeight = h - 0.08;
    const postGeom = new THREE.CylinderGeometry(0.012, 0.012, postHeight, 8);

    for (let i = 0; i < nPosts; i++) {
        const xPos = -len / 2.0 + (i / (nPosts - 1)) * len;
        const postMesh = new THREE.Mesh(postGeom, metalMat);
        postMesh.position.set(xPos, 0, 0);
        group.add(postMesh);
    }

    return group;
}

function buildDoor(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.9;
    const h = sample3d.height || 2.1;
    const d = sample3d.depth || 0.1;

    const frameMat = new THREE.MeshStandardMaterial({
        color: 0x475569,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.3
    });

    const leafMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.1
    });

    const handleMat = new THREE.MeshStandardMaterial({
        color: 0xe2e8f0,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.9
    });

    const jambGeom = new THREE.BoxGeometry(0.06, h, d);
    const leftJamb = new THREE.Mesh(jambGeom, frameMat);
    leftJamb.position.set(-w / 2.0 + 0.03, 0, 0);
    group.add(leftJamb);

    const rightJamb = new THREE.Mesh(jambGeom, frameMat);
    rightJamb.position.set(w / 2.0 - 0.03, 0, 0);
    group.add(rightJamb);

    const headerGeom = new THREE.BoxGeometry(w - 0.12, 0.06, d);
    const headerMesh = new THREE.Mesh(headerGeom, frameMat);
    headerMesh.position.set(0, h / 2.0 - 0.03, 0);
    group.add(headerMesh);

    const leafGeom = new THREE.BoxGeometry(w - 0.12, h - 0.06, 0.04);
    const leafMesh = new THREE.Mesh(leafGeom, leafMat);
    leafMesh.position.set(0, -0.03, 0);
    group.add(leafMesh);

    const knobBaseGeom = new THREE.CylinderGeometry(0.015, 0.015, 0.05, 12);
    knobBaseGeom.rotateX(Math.PI / 2.0);
    const knobBase = new THREE.Mesh(knobBaseGeom, handleMat);
    knobBase.position.set(w / 2.0 - 0.12, -h / 2.0 + 1.0, 0.03);
    group.add(knobBase);

    const leverBarGeom = new THREE.CylinderGeometry(0.01, 0.01, 0.10, 12);
    leverBarGeom.rotateZ(Math.PI / 2.0);
    const leverBar = new THREE.Mesh(leverBarGeom, handleMat);
    leverBar.position.set(w / 2.0 - 0.16, -h / 2.0 + 1.0, 0.055);
    group.add(leverBar);

    return group;
}

function buildWindow(sample3d, options) {
    const { wireframeMode } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 1.5;
    const h = sample3d.height || 1.2;
    const d = sample3d.depth || 0.08;

    const frameMat = new THREE.MeshStandardMaterial({
        color: 0xe2e8f0,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.5
    });

    const mullionMat = new THREE.MeshStandardMaterial({
        color: 0xcbd5e1,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.5
    });

    const glassMat = new THREE.MeshStandardMaterial({
        color: 0x38bdf8,
        wireframe: wireframeMode,
        transparent: true,
        opacity: 0.35,
        roughness: 0.1,
        metalness: 0.1
    });

    const vertFrameGeom = new THREE.BoxGeometry(0.05, h, d);
    const leftFrame = new THREE.Mesh(vertFrameGeom, frameMat);
    leftFrame.position.set(-w / 2.0 + 0.025, 0, 0);
    group.add(leftFrame);

    const rightFrame = new THREE.Mesh(vertFrameGeom, frameMat);
    rightFrame.position.set(w / 2.0 - 0.025, 0, 0);
    group.add(rightFrame);

    const horizFrameGeom = new THREE.BoxGeometry(w - 0.10, 0.05, d);
    const topFrame = new THREE.Mesh(horizFrameGeom, frameMat);
    topFrame.position.set(0, h / 2.0 - 0.025, 0);
    group.add(topFrame);

    const botFrame = new THREE.Mesh(horizFrameGeom, frameMat);
    botFrame.position.set(0, -h / 2.0 + 0.025, 0);
    group.add(botFrame);

    const vertMullion = new THREE.Mesh(new THREE.BoxGeometry(0.03, h - 0.10, d * 0.8), mullionMat);
    group.add(vertMullion);

    const horizMullion = new THREE.Mesh(new THREE.BoxGeometry(w - 0.10, 0.03, d * 0.8), mullionMat);
    group.add(horizMullion);

    const glassMesh = new THREE.Mesh(new THREE.BoxGeometry(w - 0.10, h - 0.10, 0.01), glassMat);
    group.add(glassMesh);

    return group;
}

function buildRoof(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 6.0;
    const d = sample3d.depth || 4.0;
    const h = sample3d.height || 1.5;

    const roofMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.1
    });

    const shape = new THREE.Shape();
    shape.moveTo(-w / 2.0, -h / 2.0);
    shape.lineTo(w / 2.0, -h / 2.0);
    shape.lineTo(0, h / 2.0);
    shape.closePath();

    const extrudeSettings = { depth: d, bevelEnabled: false };
    const roofGeom = new THREE.ExtrudeGeometry(shape, extrudeSettings);
    roofGeom.center();

    const roofMesh = new THREE.Mesh(roofGeom, roofMat);
    group.add(roofMesh);

    return group;
}

function buildFurniture(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 1.4;
    const d = sample3d.depth || 0.7;
    const h = sample3d.height || 0.75;

    const topMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.1
    });

    const legMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });

    const topMesh = new THREE.Mesh(new THREE.BoxGeometry(w, 0.04, d), topMat);
    topMesh.position.set(0, h / 2.0 - 0.02, 0);
    group.add(topMesh);

    const legHeight = h - 0.04;
    const legGeom = new THREE.CylinderGeometry(0.025, 0.025, legHeight, 12);

    const xOffsets = [-w / 2.0 + 0.08, w / 2.0 - 0.08];
    const zOffsets = [-d / 2.0 + 0.08, d / 2.0 - 0.08];

    xOffsets.forEach(lx => {
        zOffsets.forEach(lz => {
            const legMesh = new THREE.Mesh(legGeom, legMat);
            legMesh.position.set(lx, -0.02, lz);
            group.add(legMesh);
        });
    });

    return group;
}

function buildTransportElement(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 1.60;
    const d = sample3d.depth || 1.80;
    const h = sample3d.height || 2.60;

    const cabinMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.6
    });
    const doorMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.8
    });
    const interiorMat = new THREE.MeshStandardMaterial({
        color: 0xf8fafc,
        wireframe: wireframeMode,
        roughness: 0.1
    });

    const cabinOuter = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), cabinMat);
    group.add(cabinOuter);

    const doorPanelGeom = new THREE.BoxGeometry(w * 0.42, h * 0.85, 0.04);
    const leftDoor = new THREE.Mesh(doorPanelGeom, doorMat);
    leftDoor.position.set(-w * 0.22, -h * 0.05, d / 2.0 + 0.01);
    group.add(leftDoor);

    const rightDoor = new THREE.Mesh(doorPanelGeom, doorMat);
    rightDoor.position.set(w * 0.22, -h * 0.05, d / 2.0 + 0.01);
    group.add(rightDoor);

    const lightPanel = new THREE.Mesh(new THREE.BoxGeometry(w * 0.70, 0.02, d * 0.70), interiorMat);
    lightPanel.position.set(0, h / 2.0 - 0.02, 0);
    group.add(lightPanel);

    return group;
}

function buildCurtainWall(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 4.00;
    const d = sample3d.depth || 0.15;
    const h = sample3d.height || 3.00;

    const mullionMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });
    const glassMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        transparent: true,
        opacity: 0.45,
        roughness: 0.1,
        metalness: 0.1
    });

    const numCols = 4;
    const numRows = 3;
    const mullionW = 0.06;

    for (let i = 0; i <= numCols; i++) {
        const x = -w / 2.0 + i * (w / numCols);
        const vertMullion = new THREE.Mesh(new THREE.BoxGeometry(mullionW, h, d), mullionMat);
        vertMullion.position.set(x, 0, 0);
        group.add(vertMullion);
    }

    for (let j = 0; j <= numRows; j++) {
        const y = -h / 2.0 + j * (h / numRows);
        const horizMullion = new THREE.Mesh(new THREE.BoxGeometry(w, mullionW, d), mullionMat);
        horizMullion.position.set(0, y, 0);
        group.add(horizMullion);
    }

    const panelW = w / numCols - mullionW;
    const panelH = h / numRows - mullionW;
    const panelGeom = new THREE.BoxGeometry(panelW, panelH, 0.015);

    for (let i = 0; i < numCols; i++) {
        const px = -w / 2.0 + (i + 0.5) * (w / numCols);
        for (let j = 0; j < numRows; j++) {
            const py = -h / 2.0 + (j + 0.5) * (h / numRows);
            const glassMesh = new THREE.Mesh(panelGeom, glassMat);
            glassMesh.position.set(px, py, 0);
            group.add(glassMesh);
        }
    }

    return group;
}

function buildShadingDevice(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 2.40;
    const d = sample3d.depth || 0.80;
    const h = sample3d.height || 1.50;

    const structMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.7
    });
    const louverMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.5
    });

    const bracketGeom = new THREE.BoxGeometry(0.06, h, 0.06);
    [-w / 2.0 + 0.10, w / 2.0 - 0.10].forEach(bx => {
        const bracket = new THREE.Mesh(bracketGeom, structMat);
        bracket.position.set(bx, 0, -d / 2.0 + 0.03);
        group.add(bracket);

        const armGeom = new THREE.BoxGeometry(0.05, 0.05, d - 0.06);
        [-h / 3.0, h / 3.0].forEach(ay => {
            const arm = new THREE.Mesh(armGeom, structMat);
            arm.position.set(bx, ay, 0);
            group.add(arm);
        });
    });

    const numLouvers = 6;
    const louverGeom = new THREE.BoxGeometry(w, 0.02, 0.22);

    for (let i = 0; i < numLouvers; i++) {
        const ly = -h / 2.0 + 0.15 + (i / (numLouvers - 1)) * (h - 0.30);
        const louver = new THREE.Mesh(louverGeom, louverMat);
        louver.position.set(0, ly, 0.05);
        louver.rotation.x = 0.45;
        group.add(louver);
    }

    return group;
}

function buildWallSystem(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 4.00;
    const d = sample3d.depth || 0.22;
    const h = sample3d.height || 3.00;

    const wallMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.7,
        metalness: 0.1
    });
    const trimMat = new THREE.MeshStandardMaterial({
        color: 0x475569,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.3
    });

    const coreMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h - 0.16, d - 0.02), wallMat);
    coreMesh.position.set(0, 0, 0);
    group.add(coreMesh);

    const skirtingGeom = new THREE.BoxGeometry(w, 0.10, 0.015);
    [-d / 2.0 + 0.0075, d / 2.0 - 0.0075].forEach(sz => {
        const skirting = new THREE.Mesh(skirtingGeom, trimMat);
        skirting.position.set(0, -h / 2.0 + 0.05, sz);
        group.add(skirting);
    });

    const copingMesh = new THREE.Mesh(new THREE.BoxGeometry(w + 0.04, 0.06, d + 0.04), trimMat);
    copingMesh.position.set(0, h / 2.0 - 0.03, 0);
    group.add(copingMesh);

    return group;
}

function buildCovering(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 3.60;
    const d = sample3d.depth || 3.60;
    const h = sample3d.height || 0.10;

    const baseMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.6,
        metalness: 0.1
    });
    const tileMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.1
    });
    const gridMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });

    const baseSlab = new THREE.Mesh(new THREE.BoxGeometry(w, h * 0.4, d), baseMat);
    baseSlab.position.set(0, -h / 2.0 + h * 0.2, 0);
    group.add(baseSlab);

    const gridCount = 6;
    const tileSizeX = w / gridCount - 0.02;
    const tileSizeZ = d / gridCount - 0.02;
    const tileGeom = new THREE.BoxGeometry(tileSizeX, h * 0.5, tileSizeZ);

    for (let i = 0; i < gridCount; i++) {
        const tx = -w / 2.0 + (i + 0.5) * (w / gridCount);
        for (let j = 0; j < gridCount; j++) {
            const tz = -d / 2.0 + (j + 0.5) * (d / gridCount);
            const tileMesh = new THREE.Mesh(tileGeom, tileMat);
            tileMesh.position.set(tx, h / 2.0 - h * 0.25, tz);
            group.add(tileMesh);
        }
    }

    for (let i = 0; i <= gridCount; i++) {
        const gx = -w / 2.0 + i * (w / gridCount);
        const runnerZ = new THREE.Mesh(new THREE.BoxGeometry(0.015, h * 0.55, d), gridMat);
        runnerZ.position.set(gx, h / 2.0 - h * 0.275, 0);
        group.add(runnerZ);

        const gz = -d / 2.0 + i * (d / gridCount);
        const runnerX = new THREE.Mesh(new THREE.BoxGeometry(w, h * 0.55, 0.015), gridMat);
        runnerX.position.set(0, h / 2.0 - h * 0.275, gz);
        group.add(runnerX);
    }

    return group;
}

function buildParametricComponentProxy(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.80;
    const d = sample3d.depth || 0.80;
    const h = sample3d.height || 1.00;

    const proxyMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.5
    });
    const pedestalMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.6
    });

    // Chamfered mounting pedestal base
    const baseMesh = new THREE.Mesh(new THREE.BoxGeometry(w * 1.10, h * 0.15, d * 1.10), pedestalMat);
    baseMesh.position.set(0, -h / 2.0 + h * 0.075, 0);
    group.add(baseMesh);

    // Main engineering component box body
    const bodyMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h * 0.70, d), proxyMat);
    bodyMesh.position.set(0, -h / 2.0 + h * 0.15 + (h * 0.35), 0);
    group.add(bodyMesh);

    // Alignment Datums on four corners
    const datumMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, wireframe: wireframeMode });
    [-w * 0.42, w * 0.42].forEach(dx => {
        [-d * 0.42, d * 0.42].forEach(dz => {
            const datum = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.04, 12), datumMat);
            datum.position.set(dx, -h / 2.0 + h * 0.15, dz);
            group.add(datum);
        });
    });

    // Center-of-gravity trihedron marker (R=X, G=Y, B=Z axes)
    const cogY = h * 0.10;
    const axisMatX = new THREE.MeshBasicMaterial({ color: 0xef4444 });
    const axisMatY = new THREE.MeshBasicMaterial({ color: 0x22c55e });
    const axisMatZ = new THREE.MeshBasicMaterial({ color: 0x3b82f6 });

    const axisX = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, w * 0.40, 12), axisMatX);
    axisX.rotation.z = -Math.PI / 2.0;
    axisX.position.set(w * 0.20, cogY, 0);
    group.add(axisX);

    const axisY = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, h * 0.40, 12), axisMatY);
    axisY.position.set(0, cogY + h * 0.20, 0);
    group.add(axisY);

    const axisZ = new THREE.Mesh(new THREE.CylinderGeometry(0.008, 0.008, d * 0.40, 12), axisMatZ);
    axisZ.rotation.x = Math.PI / 2.0;
    axisZ.position.set(0, cogY, d * 0.20);
    group.add(axisZ);

    const cogSphere = new THREE.Mesh(new THREE.SphereGeometry(0.03, 16, 16), datumMat);
    cogSphere.position.set(0, cogY, 0);
    group.add(cogSphere);

    return group;
}

function buildVirtualBoundaryZone(sample3d, options) {
    const { col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 2.00;
    const d = sample3d.depth || 2.00;
    const h = sample3d.height || 2.50;

    const zoneMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        transparent: true,
        opacity: 0.20,
        roughness: 0.1,
        metalness: 0.1,
        depthWrite: false
    });

    const frameMat = new THREE.LineDashedMaterial({
        color: 0x0284c7,
        dashSize: 0.10,
        gapSize: 0.05,
        linewidth: 2
    });

    // Semi-transparent spatial clearance bounding volume
    const zoneMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), zoneMat);
    group.add(zoneMesh);

    // Dashed perimeter edge wireframe frames
    const bboxEdges = new THREE.EdgesGeometry(new THREE.BoxGeometry(w, h, d));
    const lineSegments = new THREE.LineSegments(bboxEdges, frameMat);
    lineSegments.computeLineDistances();
    group.add(lineSegments);

    return group;
}

function buildChimney(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.80;
    const d = sample3d.depth || 0.80;
    const h = sample3d.height || 4.50;

    const shaftMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.8,
        metalness: 0.1
    });
    const crownMat = new THREE.MeshStandardMaterial({
        color: 0x475569,
        wireframe: wireframeMode,
        roughness: 0.5,
        metalness: 0.3
    });
    const flueMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.7
    });

    const shaftMesh = new THREE.Mesh(new THREE.BoxGeometry(w, h - 0.40, d), shaftMat);
    shaftMesh.position.set(0, -0.20, 0);
    group.add(shaftMesh);

    const crownMesh = new THREE.Mesh(new THREE.BoxGeometry(w + 0.16, 0.12, d + 0.16), crownMat);
    crownMesh.position.set(0, h / 2.0 - 0.34, 0);
    group.add(crownMesh);

    const flueGeom = new THREE.CylinderGeometry(w * 0.25, w * 0.25, 0.35, 24);
    const flueMesh = new THREE.Mesh(flueGeom, flueMat);
    flueMesh.position.set(0, h / 2.0 - 0.10, 0);
    group.add(flueMesh);

    const capHoodGeom = new THREE.ConeGeometry(w * 0.40, 0.18, 24);
    const capHoodMesh = new THREE.Mesh(capHoodGeom, crownMat);
    capHoodMesh.position.set(0, h / 2.0 + 0.18, 0);
    group.add(capHoodMesh);

    const stemGeom = new THREE.CylinderGeometry(0.015, 0.015, 0.20, 8);
    [[-w * 0.18, -d * 0.18], [w * 0.18, -d * 0.18],
     [-w * 0.18, d * 0.18], [w * 0.18, d * 0.18]].forEach(([sx, sz]) => {
        const stem = new THREE.Mesh(stemGeom, crownMat);
        stem.position.set(sx, h / 2.0 + 0.02, sz);
        group.add(stem);
    });

    return group;
}
