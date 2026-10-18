# 🏛️ Museo Soumaya (Fernando Romero / Ove Arup, 2011)
## The Pure Algorithmic Architecture Benchmark for debim v1.0.0

<p align="center">
  <strong>An iconic 46-meter sculptural masterpiece compiled deterministically from mathematical equations into OpenBIM IFC4 in seconds.</strong>
</p>

---

## 🎯 Architecture as Mathematical Truth

Traditional BIM software forces architects and engineers to click with mice to draft thousands of individual elements, producing multi-gigabyte proprietary files that crash web browsers and choke AI context windows.

In **debim v1.0.0 ("The Pure Algorithmic Architecture Release")**, complex organic double-curved architecture is expressed as **concise declarative code**:

```yaml
# 1. Macro-Geometry: Asymmetric Hyperbolic Ring Loft Equation
geometry_rules:
  type: HYPERBOLIC_LOFT
  base_radii: [16.0, 20.0]     # Ground lobby ellipse (meters)
  waist_radii: [12.0, 15.0]    # Mid-height pinch at z = 22.0m
  roof_radii: [24.0, 28.0]     # Cantilevered flaring crown
  cantilever_offset: [6.5, 0.0] # 6.5m asymmetrical forward lean

# 2. 28 Curved Structural Ribs (Swept Steel Columns along Directrix)
structures:
  column_generator:
    count: 28
    distribution: RADIAL_ELLIPTIC
    profile: CIRCULAR_HOLLOW_D600
    trajectory: LOFT_SURFACE_ISOPARAMETRIC
    material: STEEL_WHITE

# 3. Micro-Geometry: Floating Hexagonal Aluminum Facade Panels
facade:
  envelope_skin:
    target: HYPERBOLIC_LOFT
    pattern: HEXAGONAL_CONFORMAL
    target_panel_size: 1.2
    joint_gap: 0.02
    material: ALUMINUM_ANODIZED_SILVER
    ifc_representation: IfcTriangulatedFaceSet
```

---

## 🚀 Instant Verification Commands

### 1. Validate Geometry & Topology
```bash
debim validate examples/museo_soumaya/project.yaml
```
Output:
```
Pydantic Schema Validation passed.
Topological Continuity Validation passed (no floating columns or unsupported beams).
AABB Clash Detection passed (no MEP-structure intersections).
Validation completed successfully with 0 warnings or errors.
```

### 2. Quantitative Take-Off (QTO)
```bash
debim qto -m examples/museo_soumaya/project.yaml
```
- **Structural Steel (28 Swept CHS600 Columns across 7 Storeys):** 406.86 metric tons
- **Formwork Area:** 14,705 m²
- **Painting Area:** 2,680 m²

### 3. Compile to OpenBIM IFC4
```bash
debim compile -m examples/museo_soumaya/project.yaml -o dist/soumaya.ifc
```
- Generates a fully compliant BuildingSMART **IFC4** model in ~4 seconds (~2.2 MB).

### 4. Zero-Install 3D WebGL Viewer
```bash
debim view -m examples/museo_soumaya/project.yaml -e dist/soumaya.html
```
- Standalone HTML viewer with Three.js `InstancedMesh` rendering at 60 FPS.

### 5. Thai CGD v480 BOQ & Carbon Footprint
```bash
debim boq -m examples/museo_soumaya/project.yaml
```
- Computes standard forms (ปร.4, ปร.4(พ), ปร.5) with Factor F and embodied carbon metrics (kgCO2e) synced from `PRIDA-TAKON/debim-standards`.
