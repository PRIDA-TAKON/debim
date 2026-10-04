# Farnsworth House (1951) — debim Example Showcase

> **Architect:** Ludwig Mies van der Rohe  
> **Location:** Plano, Illinois, USA  
> **Status:** National Historic Landmark (Public Domain)  
> **Authored by:** AI Coding Agent (Google Antigravity powered by Gemini 3.8 Flash)

This directory contains the complete declarative BIM specification for Ludwig Mies van der Rohe's iconic **Farnsworth House**.

---

## 📁 Files

- `project.yaml`: Minimal Declarative BIM manifest specifying columns, travertine slabs, glass facades, and teak core.
- `prices.yaml`: Material and labor price catalog formatted with MasterFormat / UniFormat standards.
- `farnsworth_house.ifc`: Standard IFC4 compiled model (~4.8 KB).
- `viewer.html`: Standalone lightweight 3D HTML viewer.

---

## ⚡ Quick Commands

```bash
# 1. Validate geometric & structural integrity
debim validate -m examples/farnsworth_house/project.yaml

# 2. Extract material quantities (QTO)
debim qto -m examples/farnsworth_house/project.yaml

# 3. Calculate full cost estimate (BOQ)
debim cost -m examples/farnsworth_house/project.yaml -p examples/farnsworth_house/prices.yaml

# 4. Compile to IFC4 standard
debim compile -m examples/farnsworth_house/project.yaml -o dist/farnsworth_house.ifc

# 5. Open interactive 3D Web Viewer
debim view -m examples/farnsworth_house/project.yaml
```
