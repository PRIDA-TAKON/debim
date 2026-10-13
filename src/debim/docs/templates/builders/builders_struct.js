/**
 * Structural 3D Geometry Builders for debim Class Directory.
 * Covers: Column, Beam, Slab, Deep Foundation, Retaining Structure, Tendon Anchor, Structural Fastener, Rebar Cages.
 */

function buildRebarCage(sample3d) {
    const rebarType = sample3d.rebar_type || 'column';
    const group = new THREE.Group();
    group.isRebarGroup = true;

    const w = sample3d.width || 0.3;
    const d = sample3d.depth || 0.3;
    const h = sample3d.height || 1;
    const c = sample3d.cover || 0.035;

    const mainMat = new THREE.MeshStandardMaterial({
        color: 0xf59e0b, // Amber Gold
        metalness: 0.85,
        roughness: 0.25
    });
    const stirrupMat = new THREE.MeshStandardMaterial({
        color: 0x38bdf8, // Sky Blue / Cyan
        metalness: 0.85,
        roughness: 0.25
    });

    if (rebarType === 'column') {
        const rBar = 0.012;
        const barH = h - 0.04;
        const barGeom = new THREE.CylinderGeometry(rBar, rBar, barH, 12);
        const xOffsets = [-w / 2 + c, w / 2 - c];
        const zOffsets = [-d / 2 + c, d / 2 - c];
        xOffsets.forEach(bx => {
            zOffsets.forEach(bz => {
                const m = new THREE.Mesh(barGeom, mainMat);
                m.position.set(bx, 0, bz);
                group.add(m);
            });
        });

        const pitch = 0.20;
        const nRings = Math.max(2, Math.floor(h / pitch));
        const rw = w - 2 * c;
        const rd = d - 2 * c;
        const rStir = 0.005;
        for (let i = 1; i < nRings; i++) {
            const y = -h / 2 + i * pitch;
            const xBarGeom = new THREE.CylinderGeometry(rStir, rStir, rw, 8);
            xBarGeom.rotateZ(Math.PI / 2);
            [-rd / 2, rd / 2].forEach(bz => {
                const sm = new THREE.Mesh(xBarGeom, stirrupMat);
                sm.position.set(0, y, bz);
                group.add(sm);
            });
            const zBarGeom = new THREE.CylinderGeometry(rStir, rStir, rd, 8);
            zBarGeom.rotateX(Math.PI / 2);
            [-rw / 2, rw / 2].forEach(bx => {
                const sm = new THREE.Mesh(zBarGeom, stirrupMat);
                sm.position.set(bx, y, 0);
                group.add(sm);
            });
        }
    } else if (rebarType === 'beam') {
        const rBar = 0.011;
        const barL = w - 0.06;
        const barGeom = new THREE.CylinderGeometry(rBar, rBar, barL, 12);
        barGeom.rotateZ(Math.PI / 2);

        [-d / 2 + c, d / 2 - c].forEach(bz => {
            const m = new THREE.Mesh(barGeom, mainMat);
            m.position.set(0, h / 2 - c, bz);
            group.add(m);
        });
        [-d / 2 + c, 0, d / 2 - c].forEach(bz => {
            const m = new THREE.Mesh(barGeom, mainMat);
            m.position.set(0, -h / 2 + c, bz);
            group.add(m);
        });

        const pitch = 0.20;
        const nRings = Math.max(2, Math.floor(w / pitch));
        const rh = h - 2 * c;
        const rd = d - 2 * c;
        const rStir = 0.005;
        for (let i = 1; i < nRings; i++) {
            const x = -w / 2 + i * pitch;
            const vBarGeom = new THREE.CylinderGeometry(rStir, rStir, rh, 8);
            [-rd / 2, rd / 2].forEach(bz => {
                const sm = new THREE.Mesh(vBarGeom, stirrupMat);
                sm.position.set(x, 0, bz);
                group.add(sm);
            });
            const hBarGeom = new THREE.CylinderGeometry(rStir, rStir, rd, 8);
            hBarGeom.rotateX(Math.PI / 2);
            [-rh / 2, rh / 2].forEach(by => {
                const sm = new THREE.Mesh(hBarGeom, stirrupMat);
                sm.position.set(x, by, 0);
                group.add(sm);
            });
        }
    } else if (rebarType === 'footing') {
        const rBar = 0.008;
        const matL = w - 2 * c;
        const matW = d - 2 * c;
        const nX = 7;
        const nZ = 7;
        const barXGeom = new THREE.CylinderGeometry(rBar, rBar, matL, 8);
        barXGeom.rotateZ(Math.PI / 2);
        for (let i = 0; i < nZ; i++) {
            const z = -matW / 2 + (i / (nZ - 1)) * matW;
            const m = new THREE.Mesh(barXGeom, mainMat);
            m.position.set(0, -h / 2 + c, z);
            group.add(m);
        }
        const barZGeom = new THREE.CylinderGeometry(rBar, rBar, matW, 8);
        barZGeom.rotateX(Math.PI / 2);
        for (let i = 0; i < nX; i++) {
            const x = -matL / 2 + (i / (nX - 1)) * matL;
            const m = new THREE.Mesh(barZGeom, mainMat);
            m.position.set(x, -h / 2 + c + 0.015, 0);
            group.add(m);
        }
        const dowelH = h + 0.35;
        const dowelGeom = new THREE.CylinderGeometry(0.010, 0.010, dowelH, 8);
        [[-0.12, -0.12], [0.12, -0.12], [0.12, 0.12], [-0.12, 0.12]].forEach(([dx, dz]) => {
            const dm = new THREE.Mesh(dowelGeom, mainMat);
            dm.position.set(dx, 0.15, dz);
            group.add(dm);
        });
    } else if (rebarType === 'slab') {
        const rBar = 0.005;
        const matL = w - 2 * c;
        const matW = d - 2 * c;
        const nBars = 11;
        const barXGeom = new THREE.CylinderGeometry(rBar, rBar, matL, 8);
        barXGeom.rotateZ(Math.PI / 2);
        for (let i = 0; i < nBars; i++) {
            const z = -matW / 2 + (i / (nBars - 1)) * matW;
            const m = new THREE.Mesh(barXGeom, mainMat);
            m.position.set(0, -h / 2 + c, z);
            group.add(m);
        }
        const barZGeom = new THREE.CylinderGeometry(rBar, rBar, matW, 8);
        barZGeom.rotateX(Math.PI / 2);
        for (let i = 0; i < nBars; i++) {
            const x = -matL / 2 + (i / (nBars - 1)) * matL;
            const m = new THREE.Mesh(barZGeom, mainMat);
            m.position.set(x, -h / 2 + c + 0.012, 0);
            group.add(m);
        }
    } else if (rebarType === 'retaining_wall') {
        const rBar = 0.008;
        const nStem = 15;
        const stemH = h - c;
        const stemGeom = new THREE.CylinderGeometry(rBar, rBar, stemH, 8);
        for (let i = 0; i < nStem; i++) {
            const x = -w / 2 + c + (i / (nStem - 1)) * (w - 2 * c);
            const sm = new THREE.Mesh(stemGeom, mainMat);
            sm.position.set(x, 0, 0);
            group.add(sm);
        }
    } else if (rebarType === 'stair') {
        const rBar = 0.008;
        const rDist = 0.005;
        const length = Math.hypot(d, h);
        const angle = Math.atan2(h, d);
        const nMain = 6;
        const waistThick = 0.14;

        const mainBarGeom = new THREE.CylinderGeometry(rBar, rBar, length - 2 * c, 8);
        mainBarGeom.rotateX(Math.PI / 2);

        [-waistThick / 2 + c, waistThick / 2 - c].forEach(yLayer => {
            for (let i = 0; i < nMain; i++) {
                const x = -w / 2 + c + (i / (nMain - 1)) * (w - 2 * c);
                const m = new THREE.Mesh(mainBarGeom, mainMat);
                m.position.set(x, -waistThick * 0.50, 0);
                m.rotation.x = -angle;
                m.translateOnAxis(new THREE.Vector3(0, 1, 0), yLayer);
                group.add(m);
            }
        });

        const nDist = 10;
        const distBarGeom = new THREE.CylinderGeometry(rDist, rDist, w - 2 * c, 8);
        distBarGeom.rotateZ(Math.PI / 2);

        for (let i = 0; i < nDist; i++) {
            const frac = (i + 0.5) / nDist - 0.5;
            const z = frac * (d - 2 * c);
            const y = -waistThick * 0.50 + frac * (h - 2 * c);
            [-waistThick / 2 + c + 0.012, waistThick / 2 - c - 0.012].forEach(yOff => {
                const m = new THREE.Mesh(distBarGeom, stirrupMat);
                m.position.set(0, y + yOff * Math.cos(angle), z + yOff * Math.sin(angle));
                group.add(m);
            });
        }
    }

    return group;
}

function buildRetainingStructure(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 4.00;
    const d = sample3d.depth || 2.50;
    const h = sample3d.height || 3.00;

    const concreteMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.7,
        metalness: 0.1
    });

    const baseSlab = new THREE.Mesh(new THREE.BoxGeometry(w, 0.35, d), concreteMat);
    baseSlab.position.set(0, -h / 2.0 + 0.175, 0);
    group.add(baseSlab);

    const shape = new THREE.Shape();
    shape.moveTo(-0.15, 0);
    shape.lineTo(0.15, 0);
    shape.lineTo(0.10, h - 0.35);
    shape.lineTo(-0.10, h - 0.35);
    shape.closePath();

    const stemGeom = new THREE.ExtrudeGeometry(shape, { depth: w, bevelEnabled: false });
    stemGeom.rotateY(Math.PI / 2.0);
    stemGeom.center();
    const stemMesh = new THREE.Mesh(stemGeom, concreteMat);
    stemMesh.position.set(0, -h / 2.0 + 0.35 + (h - 0.35) / 2.0, -d / 4.0);
    group.add(stemMesh);

    const counterfortGeom = new THREE.BoxGeometry(0.20, h - 0.35, d * 0.50);
    [-w / 3.0, w / 3.0].forEach(cx => {
        const counterfort = new THREE.Mesh(counterfortGeom, concreteMat);
        counterfort.position.set(cx, -h / 2.0 + 0.35 + (h - 0.35) / 2.0, 0);
        group.add(counterfort);
    });

    return group;
}

function buildDeepFoundation(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 2.40;
    const d = sample3d.depth || 2.40;
    const h = sample3d.height || 4.00;

    const concreteMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.7,
        metalness: 0.1
    });
    const pileMat = new THREE.MeshStandardMaterial({
        color: 0x475569,
        wireframe: wireframeMode,
        roughness: 0.6,
        metalness: 0.2
    });

    const pileCapH = 0.80;
    const pileCap = new THREE.Mesh(new THREE.BoxGeometry(w, pileCapH, d), concreteMat);
    pileCap.position.set(0, h / 2.0 - pileCapH / 2.0, 0);
    group.add(pileCap);

    const pileRadius = 0.25;
    const pileLength = h - pileCapH;
    const pileGeom = new THREE.CylinderGeometry(pileRadius, pileRadius, pileLength, 24);

    const pxOffsets = [-w / 3.2, w / 3.2];
    const pzOffsets = [-d / 3.2, d / 3.2];

    pxOffsets.forEach(px => {
        pzOffsets.forEach(pz => {
            const pileMesh = new THREE.Mesh(pileGeom, pileMat);
            pileMesh.position.set(px, -h / 2.0 + pileLength / 2.0, pz);
            group.add(pileMesh);
        });
    });

    return group;
}

function buildTendonAnchor(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.40;
    const d = sample3d.depth || 0.40;
    const h = sample3d.height || 2.50;

    const steelMat = new THREE.MeshStandardMaterial({
        color: 0x334155,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });
    const strandMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.9
    });
    const anchorHeadMat = new THREE.MeshStandardMaterial({
        color: 0x1e293b,
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.95
    });

    const ductGeom = new THREE.CylinderGeometry(w * 0.25, w * 0.25, h - 0.40, 24);
    const ductMesh = new THREE.Mesh(ductGeom, steelMat);
    ductMesh.position.set(0, -0.20, 0);
    group.add(ductMesh);

    for (let i = 0; i < 7; i++) {
        const angle = (i / 6) * Math.PI * 2;
        const radius = i === 0 ? 0 : w * 0.12;
        const strandX = i === 0 ? 0 : Math.cos(angle) * radius;
        const strandZ = i === 0 ? 0 : Math.sin(angle) * radius;

        const strand = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, h, 12), strandMat);
        strand.position.set(strandX, 0, strandZ);
        group.add(strand);
    }

    const bearingPlate = new THREE.Mesh(new THREE.BoxGeometry(w, 0.08, d), steelMat);
    bearingPlate.position.set(0, h / 2.0 - 0.20, 0);
    group.add(bearingPlate);

    const trumpetGeom = new THREE.CylinderGeometry(w * 0.40, w * 0.25, 0.25, 24);
    const trumpet = new THREE.Mesh(trumpetGeom, steelMat);
    trumpet.position.set(0, h / 2.0 - 0.325, 0);
    group.add(trumpet);

    const anchorHead = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.38, w * 0.38, 0.14, 24), anchorHeadMat);
    anchorHead.position.set(0, h / 2.0 - 0.09, 0);
    group.add(anchorHead);

    return group;
}

function buildStructuralFastener(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.30;
    const d = sample3d.depth || 0.30;
    const h = sample3d.height || 0.40;

    const gussetMat = new THREE.MeshStandardMaterial({
        color: 0x475569,
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.7
    });
    const boltMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.2,
        metalness: 0.85
    });
    const washerMat = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });

    const plateThickness = 0.03;
    const gussetPlate = new THREE.Mesh(new THREE.BoxGeometry(w, h, plateThickness), gussetMat);
    group.add(gussetPlate);

    const bxOffsets = [-w * 0.28, w * 0.28];
    const byOffsets = [-h * 0.28, h * 0.28];

    bxOffsets.forEach(bx => {
        byOffsets.forEach(by => {
            const washerFront = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.028, 0.008, 16), washerMat);
            washerFront.rotateX(Math.PI / 2.0);
            washerFront.position.set(bx, by, plateThickness / 2.0 + 0.004);
            group.add(washerFront);

            const boltHeadFront = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.025, 6), boltMat);
            boltHeadFront.rotateX(Math.PI / 2.0);
            boltHeadFront.position.set(bx, by, plateThickness / 2.0 + 0.008 + 0.0125);
            group.add(boltHeadFront);

            const shank = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.08, 12), boltMat);
            shank.rotateX(Math.PI / 2.0);
            shank.position.set(bx, by, 0);
            group.add(shank);

            const washerBack = new THREE.Mesh(new THREE.CylinderGeometry(0.028, 0.028, 0.008, 16), washerMat);
            washerBack.rotateX(Math.PI / 2.0);
            washerBack.position.set(bx, by, -plateThickness / 2.0 - 0.004);
            group.add(washerBack);

            const hexNutBack = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.022, 6), boltMat);
            hexNutBack.rotateX(Math.PI / 2.0);
            hexNutBack.position.set(bx, by, -plateThickness / 2.0 - 0.008 - 0.011);
            group.add(hexNutBack);
        });
    });

    return group;
}

function buildStructuralMember(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 0.20;
    const d = sample3d.depth || 0.20;
    const h = sample3d.height || 3.00;
    const tf = 0.012; // flange thickness
    const tw = 0.008; // web thickness

    const memberMat = new THREE.MeshStandardMaterial({
        color: new THREE.Color(col),
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.85
    });

    // Top Flange
    const topFlange = new THREE.Mesh(new THREE.BoxGeometry(w, h, tf), memberMat);
    topFlange.position.set(0, 0, d / 2.0 - tf / 2.0);
    group.add(topFlange);

    // Bottom Flange
    const botFlange = new THREE.Mesh(new THREE.BoxGeometry(w, h, tf), memberMat);
    botFlange.position.set(0, 0, -d / 2.0 + tf / 2.0);
    group.add(botFlange);

    // Central Web
    const web = new THREE.Mesh(new THREE.BoxGeometry(tw, h, d - 2 * tf), memberMat);
    web.position.set(0, 0, 0);
    group.add(web);

    // Stiffener Plates at mid-height and ends
    [-h / 2.0 + 0.10, 0, h / 2.0 - 0.10].forEach(yPos => {
        [-w / 4.0, w / 4.0].forEach(xOff => {
            const stiffener = new THREE.Mesh(new THREE.BoxGeometry(w / 2.0 - tw / 2.0, tf, (d - 2 * tf) / 2.0 - 0.005), memberMat);
            stiffener.position.set(xOff > 0 ? (w / 4.0 + tw / 4.0) : (-w / 4.0 - tw / 4.0), yPos, (d - 2 * tf) / 4.0);
            group.add(stiffener);

            const stiffener2 = new THREE.Mesh(new THREE.BoxGeometry(w / 2.0 - tw / 2.0, tf, (d - 2 * tf) / 2.0 - 0.005), memberMat);
            stiffener2.position.set(xOff > 0 ? (w / 4.0 + tw / 4.0) : (-w / 4.0 - tw / 4.0), yPos, -(d - 2 * tf) / 4.0);
            group.add(stiffener2);
        });
    });

    return group;
}

function buildReinforcingBar(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const dia = sample3d.diameter || 0.02;
    const r = dia / 2.0;
    const h = sample3d.height || sample3d.length || 2.50;
    const barColor = new THREE.Color(col || "#f59e0b");

    const rebarMat = new THREE.MeshStandardMaterial({
        color: barColor,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });

    // Main vertical cylindrical shaft (straight body)
    const mainBodyLen = h - 0.30;
    const mainBodyGeom = new THREE.CylinderGeometry(r, r, mainBodyLen, 16);
    const mainBody = new THREE.Mesh(mainBodyGeom, rebarMat);
    group.add(mainBody);

    // Transverse ribbed lugs (บั้งเหล็กข้ออ้อย) along the length
    const nLugs = Math.floor(mainBodyLen / 0.04);
    const lugGeom = new THREE.TorusGeometry(r * 1.15, r * 0.25, 8, 16);
    lugGeom.rotateX(Math.PI / 2.0);

    for (let i = 0; i < nLugs; i++) {
        const yPos = -mainBodyLen / 2.0 + 0.02 + i * 0.04;
        const lug = new THREE.Mesh(lugGeom, rebarMat);
        lug.position.set(0, yPos, 0);
        lug.rotation.z = 0.25; // Angled rib lug orientation
        group.add(lug);
    }

    // Top End Hook (งอขอ 180° / 90° bend)
    const hookRadius = 0.08;
    const hookBendGeom = new THREE.TorusGeometry(hookRadius, r, 12, 24, Math.PI);
    const topHookBend = new THREE.Mesh(hookBendGeom, rebarMat);
    topHookBend.position.set(hookRadius, mainBodyLen / 2.0, 0);
    group.add(topHookBend);

    const topTailGeom = new THREE.CylinderGeometry(r, r, 0.12, 16);
    const topTail = new THREE.Mesh(topTailGeom, rebarMat);
    topTail.position.set(2 * hookRadius, mainBodyLen / 2.0 - 0.06, 0);
    group.add(topTail);

    // Bottom End Hook (งอขอ 90° bend)
    const botBendGeom = new THREE.TorusGeometry(hookRadius, r, 12, 24, Math.PI / 2.0);
    const botHookBend = new THREE.Mesh(botBendGeom, rebarMat);
    botHookBend.rotation.z = Math.PI;
    botHookBend.position.set(-hookRadius, -mainBodyLen / 2.0, 0);
    group.add(botHookBend);

    const botTailGeom = new THREE.CylinderGeometry(r, r, 0.15, 16);
    botTailGeom.rotateZ(Math.PI / 2.0);
    const botTail = new THREE.Mesh(botTailGeom, rebarMat);
    botTail.position.set(-hookRadius - 0.075, -mainBodyLen / 2.0 - hookRadius, 0);
    group.add(botTail);

    return group;
}

function buildReinforcingMesh(sample3d, options) {
    const { wireframeMode, col } = options;
    const group = new THREE.Group();
    const w = sample3d.width || 2.00;
    const d = sample3d.depth || 3.00;
    const dia = 0.008; // 8mm wire mesh
    const r = dia / 2.0;
    const pitch = 0.20; // 200mm grid spacing
    const meshColor = new THREE.Color(col || "#f59e0b");

    const wireMat = new THREE.MeshStandardMaterial({
        color: meshColor,
        wireframe: wireframeMode,
        roughness: 0.3,
        metalness: 0.8
    });

    const weldMat = new THREE.MeshStandardMaterial({
        color: meshColor.clone().multiplyScalar(0.85),
        wireframe: wireframeMode,
        roughness: 0.4,
        metalness: 0.9
    });

    // Longitudinal wires (parallel to Z axis)
    const nLong = Math.floor(w / pitch) + 1;
    const longWireGeom = new THREE.CylinderGeometry(r, r, d, 12);
    longWireGeom.rotateX(Math.PI / 2.0);

    for (let i = 0; i < nLong; i++) {
        const xPos = -w / 2.0 + i * pitch;
        const wire = new THREE.Mesh(longWireGeom, wireMat);
        wire.position.set(xPos, r, 0);
        group.add(wire);
    }

    // Transverse cross wires (parallel to X axis, laid on top)
    const nTrans = Math.floor(d / pitch) + 1;
    const transWireGeom = new THREE.CylinderGeometry(r, r, w, 12);
    transWireGeom.rotateZ(Math.PI / 2.0);

    for (let j = 0; j < nTrans; j++) {
        const zPos = -d / 2.0 + j * pitch;
        const wire = new THREE.Mesh(transWireGeom, wireMat);
        wire.position.set(0, 3 * r, zPos);
        group.add(wire);

        // Welding joint nuggets at grid intersections
        for (let i = 0; i < nLong; i++) {
            const xPos = -w / 2.0 + i * pitch;
            const joint = new THREE.Mesh(new THREE.SphereGeometry(r * 1.4, 8, 8), weldMat);
            joint.position.set(xPos, 2 * r, zPos);
            group.add(joint);
        }
    }

    return group;
}
