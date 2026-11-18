# debim v1.3.0 — Physical AI Engineering, Hyperscale Calculations & AI Clash Resolution Engine 🚀

> **"Unifying Building-as-Code with Mission-Critical Industrial Engineering Calculations, Automated Clash Funnel AI, and Kaggle Anti-Hallucination QTO Benchmarks."**

---

## 🌟 Highlights & Major Capabilities in v1.3.0

### 1. ⚡ Mission-Critical & Hyperscale Engineering Calculations (`debim calc`)
A native, decoupled engineering calculation engine designed for mission-critical facilities, industrial plants, and hyperscale data centers:
* **`debim calc datacenter`**: Integrated Hyperscale Data Center sizing (PUE, N+1 / 2N UPS Redundancy, Floor Load, Critical Power IT envelope).
* **`debim calc cooling-load`**: Data hall heat rejection, sensible cooling ratios, and CHW/CRAH volumetric sizing.
* **`debim calc pipe-volume`**: Process cooling water (PCW) volume calculation, pipe sizing, and chemical system flushing flush volumes.
* **`debim calc cable-size`**: Electrical cable sizing and 3-phase voltage drop analysis (NEC 310 / IEEE 141 standard compliant).
* **`debim calc generator-yard`**: Standby diesel generator capacity planning, bulk fuel tank storage, and day tank run-time sizing.
* **`debim calc substation`**: MV transformer load factor calculations and substation area footprints.
* **`debim calc stormwater`**: Rational method stormwater runoff retention pond sizing.
* **`debim calc noise`**: Free-field spherical and hemi-spherical acoustic attenuation from generator yards to site boundaries.
* **`debim calc wind-shear`**: ASCE 7 diaphragm shear distribution across building core shear walls.
* **`debim calc seismic-shear`**: ASCE 7 / IBC equivalent lateral force procedure and base shear calculation.
* **`debim calc settlement`**: 1D Terzaghi consolidation footing settlement analysis in cohesive clay soils.

---

### 2. 🎯 AI-Driven Clash Resolution & Visual Funnel Engine (`debim resolve`)
An automated geometric clash resolution workflow designed to work seamlessly with AI agents and human BIM coordinators:
* **`debim ingest-scan`**: Ingest point cloud scan regions and register as-built spatial anomalies.
* **`debim extract-roi`**: Isolate 3D Region of Interest (ROI) bounding volumes around identified clash points.
* **`debim resolve-clash`**: Generates auditable geometric remediation options (e.g., pipe reroute, duct offset, hanger shift).
* **`debim audit-options`**: Evaluates clearance, cost impact, and compliance for proposed clash solutions.
* **`debim commit-solution`**: Automatically patches declarative `.debim` element manifests to resolve spatial conflicts.

---

### 3. 🤖 LLM Multi-Model QTO Anti-Hallucination Benchmark
* Added full multi-model benchmark evaluation across **100 realistic construction scenarios** comparing unassisted LLMs against the deterministic `.debim` compiler.
* Empirically demonstrates up to **+98.0% Accuracy Gain** and eliminates spatial calculation hallucinations for lightweight open models (Qwen, Gemma, DeepSeek).
* Published public Kaggle dataset integration.

---

### 4. 📐 3D Viewer & Structural Geometry Refinements
* **Beam Profile Orientation Fix**: Corrected local coordinate transformations for 3D structural beam profiles.
* **Enhanced Layer Explorer UI**: Interactive multi-storey visibility toggles and material inspection in the HTML 3D viewer.

---

## 🛠️ CLI Quickstart for New Features

```bash
# Sizing an integrated 40MW Hyperscale Data Center
debim calc datacenter --it-load-mw 40 --pue 1.25 --tier 3

# Electrical cable sizing for 3-phase 400A feeder
debim calc cable-size --load-kw 250 --voltage 400 --length-m 120 --pf 0.85

# Cooling load calculation for Data Hall
debim calc cooling-load --it-load-kw 1500 --crah-kw 150

# Automated clash detection & resolution funnel
debim resolve --model project.debim --clashes clashes.json -o resolved/
```
