/**
 * Civil Infrastructure 3D Geometry Builders for debim Class Directory.
 * Covers: Bridge Structure, Road Infrastructure, Railway Infrastructure, Marine Facility, Earthworks Embankment.
 */

function buildBridgeStructure(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 8.0;
    const d = sample3d.depth || 4.0;
    const h = sample3d.height || 3.5;

    const concreteMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.6,
        metalness: 0.1
    });
    const girderMat = new THREE.MeshStandardMaterial({
        color: 0x475569,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.5
    });
    const bearingMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });

    const pierCol = new THREE.Mesh(new THREE.CylinderGeometry(0.50, 0.60, h * 0.45, 16), concreteMat);
    pierCol.position.set(0, -h / 2.0 + h * 0.225, 0);
    group.add(pierCol);

    const pierCap = new THREE.Mesh(new THREE.BoxGeometry(1.20, 0.40, d * 0.85), concreteMat);
    pierCap.position.set(0, -h / 2.0 + h * 0.45 + 0.20, 0);
    group.add(pierCap);

    [-d / 3.0, -d / 8.0, d / 8.0, d / 3.0].forEach(zBearing => {
        const pad = new THREE.Mesh(new THREE.BoxGeometry(0.25, 0.08, 0.25), bearingMat);
        pad.position.set(0, -h / 2.0 + h * 0.45 + 0.44, zBearing);
        group.add(pad);
    });

    [-d / 4.0, d / 4.0].forEach(zGirder => {
        const girder = new THREE.Mesh(new THREE.BoxGeometry(w, h * 0.22, 0.35), girderMat);
        girder.position.set(0, -h / 2.0 + h * 0.45 + 0.48 + (h * 0.11), zGirder);
        group.add(girder);
    });

    const deckSlab = new THREE.Mesh(new THREE.BoxGeometry(w, 0.25, d), concreteMat);
    deckSlab.position.set(0, h / 2.0 - 0.20, 0);
    group.add(deckSlab);

    [-d / 2.0 + 0.08, d / 2.0 - 0.08].forEach(zBarrier => {
        const barrier = new THREE.Mesh(new THREE.BoxGeometry(w, 0.35, 0.16), concreteMat);
        barrier.position.set(0, h / 2.0 + 0.08, zBarrier);
        group.add(barrier);
    });

    return group;
}

function buildRailwayInfrastructure(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 3.0;
    const d = sample3d.depth || 10.0;
    const h = sample3d.height || 0.6;

    const ballastMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.9,
        metalness: 0.1
    });
    const sleeperMat = new THREE.MeshStandardMaterial({
        color: 0x44403c,
        wireframe: wireframeMode,
        roughness: 0.7,
        metalness: 0.2
    });
    const railMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.8
    });

    const shape = new THREE.Shape();
    shape.moveTo(-w / 2.0, -h / 2.0);
    shape.lineTo(w / 2.0, -h / 2.0);
    shape.lineTo(w * 0.38, -h / 2.0 + 0.35);
    shape.lineTo(-w * 0.38, -h / 2.0 + 0.35);
    shape.closePath();

    const ballastGeom = new THREE.ExtrudeGeometry(shape, { depth: d, bevelEnabled: false });
    ballastGeom.center();
    const ballastMesh = new THREE.Mesh(ballastGeom, ballastMat);
    group.add(ballastMesh);

    const nSleepers = 16;
    const sleeperY = -h / 2.0 + 0.35 + 0.06;
    for (let i = 0; i < nSleepers; i++) {
        const zPos = -d / 2.0 + (i + 0.5) * (d / nSleepers);
        const sleeper = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.12, 0.22), sleeperMat);
        sleeper.position.set(0, sleeperY, zPos);
        group.add(sleeper);
    }

    const railY = sleeperY + 0.06 + 0.07;
    [-0.715, 0.715].forEach(xRail => {
        const rail = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.14, d), railMat);
        rail.position.set(xRail, railY, 0);
        group.add(rail);
    });

    return group;
}

function buildRoadInfrastructure(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 7.0;
    const d = sample3d.depth || 10.0;
    const h = sample3d.height || 0.4;

    const baseMat = new THREE.MeshStandardMaterial({
        color: 0x475569,
        wireframe: wireframeMode,
        roughness: 0.8
    });
    const asphaltMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.85,
        metalness: 0.1
    });
    const curbMat = new THREE.MeshStandardMaterial({
        color: 0xe2e8f0,
        wireframe: wireframeMode,
        roughness: 0.5
    });
    const stripeMat = new THREE.MeshStandardMaterial({
        color: 0xfef08a,
        wireframe: wireframeMode
    });

    const baseMesh = new THREE.Mesh(new THREE.BoxGeometry(w, 0.20, d), baseMat);
    baseMesh.position.set(0, -h / 2.0 + 0.10, 0);
    group.add(baseMesh);

    [-w / 4.0, w / 4.0].forEach((xLane, idx) => {
        const laneMesh = new THREE.Mesh(new THREE.BoxGeometry(w / 2.0 - 0.25, 0.12, d), asphaltMat);
        laneMesh.position.set(xLane, -h / 2.0 + 0.26, 0);
        laneMesh.rotation.z = (idx === 0) ? 0.02 : -0.02;
        group.add(laneMesh);
    });

    [-w / 2.0 + 0.125, w / 2.0 - 0.125].forEach(xCurb => {
        const curb = new THREE.Mesh(new THREE.BoxGeometry(0.25, 0.25, d), curbMat);
        curb.position.set(xCurb, -h / 2.0 + 0.225, 0);
        group.add(curb);
    });

    for (let zStripe = -d / 2.0 + 1.0; zStripe < d / 2.0; zStripe += 2.5) {
        const stripe = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.01, 1.40), stripeMat);
        stripe.position.set(0, -h / 2.0 + 0.325, zStripe);
        group.add(stripe);
    }

    return group;
}

function buildMarineFacility(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 6.0;
    const d = sample3d.depth || 8.0;
    const h = sample3d.height || 2.5;

    const dockMat = new THREE.MeshStandardMaterial({
        color: 0x64748b,
        wireframe: wireframeMode,
        roughness: 0.6,
        metalness: 0.2
    });
    const waterMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        transparent: true,
        opacity: 0.55,
        roughness: 0.1
    });
    const bollardMat = new THREE.MeshStandardMaterial({
        color: 0xeab308,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.7
    });
    const fenderMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        wireframe: wireframeMode,
        roughness: 0.8
    });

    const waterMesh = new THREE.Mesh(new THREE.BoxGeometry(w + 1.0, 0.05, d * 0.45), waterMat);
    waterMesh.position.set(0, -h / 2.0 + 0.50, d / 2.0 - d * 0.225);
    group.add(waterMesh);

    const dockSlab = new THREE.Mesh(new THREE.BoxGeometry(w, h * 0.75, d * 0.55), dockMat);
    dockSlab.position.set(0, -h / 2.0 + h * 0.375, -d / 2.0 + d * 0.275);
    group.add(dockSlab);

    [-w / 3.0, 0, w / 3.0].forEach(bx => {
        const bollardStem = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.10, 0.35, 16), bollardMat);
        bollardStem.position.set(bx, -h / 2.0 + h * 0.75 + 0.175, 0.05);
        group.add(bollardStem);

        const bollardCap = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.14, 0.08, 16), bollardMat);
        bollardCap.position.set(bx, -h / 2.0 + h * 0.75 + 0.35, 0.05);
        group.add(bollardCap);
    });

    [-w * 0.35, -w * 0.12, w * 0.12, w * 0.35].forEach(fx => {
        const fender = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.60, 16), fenderMat);
        fender.position.set(fx, -h / 2.0 + h * 0.40, 0.18);
        group.add(fender);
    });

    return group;
}

function buildEarthworksEmbankment(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 6.00;
    const d = sample3d.depth || 8.00;
    const h = sample3d.height || 2.50;

    const topsoilMat = new THREE.MeshStandardMaterial({
        color: 0x3f6212,
        wireframe: wireframeMode,
        roughness: 0.9,
        metalness: 0.1
    });
    const subsoilMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.8,
        metalness: 0.1
    });
    const bedrockMat = new THREE.MeshStandardMaterial({
        color: 0x475569,
        wireframe: wireframeMode,
        roughness: 0.7,
        metalness: 0.2
    });

    const shapeBedrock = new THREE.Shape();
    shapeBedrock.moveTo(-w / 2.0, -h / 2.0);
    shapeBedrock.lineTo(w / 2.0, -h / 2.0);
    shapeBedrock.lineTo(w * 0.42, -h / 2.0 + h * 0.35);
    shapeBedrock.lineTo(-w * 0.42, -h / 2.0 + h * 0.35);
    shapeBedrock.closePath();
    const bedrockGeom = new THREE.ExtrudeGeometry(shapeBedrock, { depth: d, bevelEnabled: false });
    bedrockGeom.center();
    const bedrockMesh = new THREE.Mesh(bedrockGeom, bedrockMat);
    bedrockMesh.position.set(0, 0, 0);
    group.add(bedrockMesh);

    const shapeSubsoil = new THREE.Shape();
    shapeSubsoil.moveTo(-w * 0.42, -h / 2.0 + h * 0.35);
    shapeSubsoil.lineTo(w * 0.42, -h / 2.0 + h * 0.35);
    shapeSubsoil.lineTo(w * 0.28, -h / 2.0 + h * 0.85);
    shapeSubsoil.lineTo(-w * 0.28, -h / 2.0 + h * 0.85);
    shapeSubsoil.closePath();
    const subsoilGeom = new THREE.ExtrudeGeometry(shapeSubsoil, { depth: d, bevelEnabled: false });
    subsoilGeom.center();
    const subsoilMesh = new THREE.Mesh(subsoilGeom, subsoilMat);
    subsoilMesh.position.set(0, h * 0.10, 0);
    group.add(subsoilMesh);

    const shapeTopsoil = new THREE.Shape();
    shapeTopsoil.moveTo(-w * 0.28, -h / 2.0 + h * 0.85);
    shapeTopsoil.lineTo(w * 0.28, -h / 2.0 + h * 0.85);
    shapeTopsoil.lineTo(w * 0.24, h / 2.0);
    shapeTopsoil.lineTo(-w * 0.24, h / 2.0);
    shapeTopsoil.closePath();
    const topsoilGeom = new THREE.ExtrudeGeometry(shapeTopsoil, { depth: d, bevelEnabled: false });
    topsoilGeom.center();
    const topsoilMesh = new THREE.Mesh(topsoilGeom, topsoilMat);
    topsoilMesh.position.set(0, h * 0.22, 0);
    group.add(topsoilMesh);

    return group;
}
