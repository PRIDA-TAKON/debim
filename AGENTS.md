# AGENTS.md — Instructions for AI Agents (Jules, etc.)

Welcome to **debim** (Declarative BIM / Building-as-Code). This repository implements a minimal, Git-native, declarative BIM compiler designed for AI agents and human architects/engineers.

---

## 🏛️ Project Philosophy & Overview

1. **Semantic Declarative Model:** Buildings are expressed as engineering logic and specifications in YAML (`project.yaml`), not complex, heavy 3D meshes.
2. **Human-First & Agent-Friendly:** Text-based format, easily version-controlled by Git, diff-friendly, and simple for LLM/Autonomous agents to inspect and modify.
3. **Dual Representation (Text-First + Fallback GLB):** 90% of building elements are mathematical primitives (Box, Cylinder, Extrusion) calculated from text specs; remaining 10% (custom shapes/furniture) load from `.glb` assets.
4. **Deterministic Code Compliance:** Building codes, municipal laws, and project feasibility constraints are written as executable Unit Tests (`pytest`).

---

## 📂 Repository Structure

```plaintext
debim/
├── src/
│   └── debim/
│       ├── __init__.py
│       ├── cli.py             # CLI entrypoints (debim / bim)
│       ├── schema.py          # Pydantic v2 data models for project.yaml
│       ├── resolver.py        # Resolves relative grid & storey coordinates to 3D world vectors
│       ├── qto.py             # Quantitative Take-Off (concrete vol, formwork area, rebar)
│       ├── cost.py            # Pricing engine matching QTO with prices.json
│       ├── compiler.py        # IFC4 compilation via IfcOpenShell
│       └── viewer.py          # Standalone lightweight 3D viewer generator
├── examples/
│   └── townhouse/
│       ├── project.yaml       # Sample project manifest
│       └── prices.json        # Sample price catalog
├── tests/
│   ├── conftest.py            # Pytest fixtures loading project.yaml
│   ├── test_schema.py         # Schema parsing & validation tests
│   ├── test_qto.py            # Volume & reinforcement calculation tests
│   └── test_compliance.py     # Building law compliance test suites
├── pyproject.toml
├── README.md
└── AGENTS.md
```

---

## 🛠️ Tech Stack & Conventions

- **Language:** Python 3.11+
- **CLI Framework:** Typer + Rich
- **Data Validation:** Pydantic v2
- **Data Serialization:** PyYAML
- **3D / Geometry:** Trimesh, NumPy
- **BIM / IFC:** IfcOpenShell (`ifcopenshell`)
- **Testing:** Pytest

---

## 🧪 Testing & Quality Standards

When working on any GitHub Issue or Pull Request:
1. **Always run unit tests:**
   ```bash
   pytest
   ```
2. **Surgical Updates:** Only modify lines and files relevant to your assigned task. Never perform unsolicited refactoring or file restructuring.
3. **Test-Driven:** Every new feature (QTO formula, schema validator, compliance rule) must include corresponding unit tests in `tests/`.
4. **Strict Schema Adherence:** Match entity names with standard buildingSMART IFC4 entities (`IfcColumn`, `IfcBeam`, `IfcWall`, `IfcDoor`, `IfcWindow`, `IfcSlab`).

---

## 📋 CLI Specification

The CLI tool exposes the binary aliases `debim` and `bim`:

| Command | Action |
|---|---|
| `bim init <name>` | Scaffold a new project with template `project.yaml` & `prices.json` |
| `bim validate` | Validate schema syntax, grid consistency, and placement links |
| `bim test` | Execute compliance & building law tests via pytest |
| `bim qto` | Calculate material quantities (concrete volume, formwork, rebar) |
| `bim cost` | Map QTO against `prices.json` and generate cost summary / CSV |
| `bim compile` | Compile declarative YAML to standardized IFC4 file (`dist/model.ifc`) |
| `bim view` | Launch a lightweight local 3D preview server in browser |
