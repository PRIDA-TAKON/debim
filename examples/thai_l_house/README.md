# Baan Thai L-Shape Benchmark Model (บ้านไทยทรง L-Shape)

## Overview
**Baan Thai L-Shape** is a comprehensive 225+ element benchmark showcase project for `debim` v0.8.1.
It models a single-storey contemporary Thai residence featuring an L-shaped floor plan, substructure stub columns, cantilever balcony beams, host-wall door/window grid openings, composite L-hip roof framing, compound floor finishes, and complete MEP systems.

## Project Characteristics
- **Element Count:** 225+ Declarative BIM Elements
- **Structure:** Monolithic reinforced concrete ground beams, stub columns, FL1 columns, cantilever balcony beams (`support_type: CANTILEVER`), and C-channel steel roof trusses.
- **Architecture:** Red mon brick and AAC autoclaved aerated lightweight block composite masonry walls, host openings with grid-relative placements (`at_grid`), and Granito tile floor finishes with sunken bathroom drops (`drop_elevation: -0.10`).
- **Roof:** L-shaped composite gable-hip roof (`GABLE_HIP`), 30° pitch, C-channel purlins and rafters, CPAC Monier concrete roof tiles.
- **MEP:** Complete sanitary fixtures, soil/waste/water piping networks, split AC units, exhaust fans, lighting fixtures, switches, outlets, and electrical conduits.

## CLI Commands

### 1. Validate Manifest Topology & bSDD Psets
```bash
debim validate examples/thai_l_house/project.debim
```

### 2. Calculate Quantitative Take-Off (QTO)
```bash
debim qto -m examples/thai_l_house/project.debim
```

### 3. Generate Thai Public Works BOQ (กรมบัญชีกลาง ว480)
```bash
debim boq examples/thai_l_house/project.debim -p examples/thai_l_house/prices.yaml --province Chiang Mai --export-excel dist/thai_l_house_boq.xlsx
```

### 4. Compile to OpenBIM IFC4 STEP
```bash
debim compile -m examples/thai_l_house/project.debim -o dist/thai_l_house.ifc
```

### 5. Launch 3D Live Web Preview
```bash
debim view -m examples/thai_l_house/project.debim
```
