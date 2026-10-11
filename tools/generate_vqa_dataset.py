"""
2D Construction Blueprint VQA Dataset Generator.
Synthesizes debim building models or loads project manifests, extracts ground truth across 4 categories
(Dimensions, Topology, Tags, Levels), constructs 4-choice close-set MCQs with distractors,
and renders 2D SVG blueprint references.
"""

import argparse
import datetime
import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from debim.draw.renderer import render_sheet
from debim.resolver import resolve_manifest
from debim.schema import (
    BeamPlacement,
    BoxProfile,
    ColumnPlacement,
    Dimensions,
    Grids,
    IfcBeam,
    IfcColumn,
    IfcDoor,
    IfcWall,
    IfcWindow,
    Material,
    ProjectInfo,
    ProjectManifest,
    SpatialStructure,
    Storey,
    WallPlacement,
    load_manifest,
)


def create_synthetic_manifest() -> ProjectManifest:
    """Generates a rich, multi-element synthetic debim ProjectManifest for VQA benchmark generation."""
    return ProjectManifest(
        project=ProjectInfo(id="PRJ-SYNTH-01", name="Synthetic Commercial Blueprint Model"),
        spatial_structure=SpatialStructure(
            storeys=[
                Storey(id="L1", name="Ground Level", elevation=0.0, height=3.5),
                Storey(id="L2", name="First Floor", elevation=3.5, height=3.2),
            ]
        ),
        grids=Grids(
            axes_x={"1": 0.0, "2": 4.0, "3": 8.0, "4": 12.0},
            axes_y={"A": 0.0, "B": 5.0, "C": 10.0},
        ),
        materials=[
            Material(id="CONC", name="Structural Concrete", category="concrete", unit_cost_ref="MAT-CONC-01"),
            Material(id="BRICK", name="Masonry Wall", category="masonry", unit_cost_ref="MAT-BRICK-01"),
            Material(id="STEEL", name="Structural Steel", category="steel", unit_cost_ref="MAT-STEEL-01"),
        ],
        elements=[
            # Columns along Grid Line A
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "C1",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.40, depth=0.40),
                    "placement": ColumnPlacement(grid=("1", "A"), base_storey="L1", top_storey="L2"),
                }
            ),
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "C2",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.40, depth=0.40),
                    "placement": ColumnPlacement(grid=("2", "A"), base_storey="L1", top_storey="L2"),
                }
            ),
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "C3",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.40, depth=0.40),
                    "placement": ColumnPlacement(grid=("3", "A"), base_storey="L1", top_storey="L2"),
                }
            ),
            # Columns along Grid Line B
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "C4",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.40, depth=0.40),
                    "placement": ColumnPlacement(grid=("1", "B"), base_storey="L1", top_storey="L2"),
                }
            ),
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "C5",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.40, depth=0.40),
                    "placement": ColumnPlacement(grid=("2", "B"), base_storey="L1", top_storey="L2"),
                }
            ),
            IfcColumn(
                **{
                    "class": "IfcColumn",
                    "tag": "C6",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.40, depth=0.40),
                    "placement": ColumnPlacement(grid=("3", "B"), base_storey="L1", top_storey="L2"),
                }
            ),
            # Structural & Partition Walls
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": "W1",
                    "material": "BRICK",
                    "thickness": 0.20,
                    "height": 3.50,
                    "placement": WallPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L1"),
                    "doors": [
                        IfcDoor(
                            **{
                                "class": "IfcDoor",
                                "tag": "D1",
                                "material": "TIMBER",
                                "dimensions": Dimensions(width=0.90, height=2.10),
                                "offset_distance": 1.20,
                            }
                        )
                    ],
                }
            ),
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": "W2",
                    "material": "BRICK",
                    "thickness": 0.20,
                    "height": 3.50,
                    "placement": WallPlacement(from_grid=("2", "A"), to_grid=("3", "A"), storey="L1"),
                    "windows": [
                        IfcWindow(
                            **{
                                "class": "IfcWindow",
                                "tag": "WIND1",
                                "material": "GLASS",
                                "dimensions": Dimensions(width=1.50, height=1.20),
                                "offset_distance": 1.00,
                                "sill_height": 0.90,
                            }
                        )
                    ],
                }
            ),
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": "W3",
                    "material": "BRICK",
                    "thickness": 0.20,
                    "height": 3.50,
                    "placement": WallPlacement(from_grid=("1", "A"), to_grid=("1", "B"), storey="L1"),
                }
            ),
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": "W4",
                    "material": "BRICK",
                    "thickness": 0.20,
                    "height": 3.50,
                    "placement": WallPlacement(from_grid=("3", "A"), to_grid=("3", "B"), storey="L1"),
                    "doors": [
                        IfcDoor(
                            **{
                                "class": "IfcDoor",
                                "tag": "D2",
                                "material": "TIMBER",
                                "dimensions": Dimensions(width=1.00, height=2.10),
                                "offset_distance": 2.00,
                            }
                        )
                    ],
                }
            ),
            # Beams
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": "B1",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.25, depth=0.50),
                    "placement": BeamPlacement(from_grid=("1", "A"), to_grid=("2", "A"), storey="L1"),
                }
            ),
            IfcBeam(
                **{
                    "class": "IfcBeam",
                    "tag": "B2",
                    "material": "CONC",
                    "profile": BoxProfile(width=0.25, depth=0.50),
                    "placement": BeamPlacement(from_grid=("2", "A"), to_grid=("3", "A"), storey="L1"),
                }
            ),
        ],
    )


def _make_choices(correct_val: str, distractors: List[str], rng: random.Random) -> Tuple[Dict[str, str], str]:
    """Combines correct answer and distractors into shuffled 4-choice dict (A, B, C, D)."""
    # Ensure distractor uniqueness and difference from correct_val
    clean_distractors = []
    for d in distractors:
        if d != correct_val and d not in clean_distractors:
            clean_distractors.append(d)

    while len(clean_distractors) < 3:
        clean_distractors.append(f"{correct_val}_alt_{len(clean_distractors)+1}")

    selected_distractors = clean_distractors[:3]
    all_options = [correct_val] + selected_distractors
    rng.shuffle(all_options)

    keys = ["A", "B", "C", "D"]
    choices_dict = {keys[i]: all_options[i] for i in range(4)}
    correct_key = [k for k, v in choices_dict.items() if v == correct_val][0]

    return choices_dict, correct_key


def generate_vqa_questions(
    manifest: ProjectManifest, seed: int = 42
) -> List[Dict[str, Any]]:
    """Extract Ground Truth properties and generate 4-category MCQ questions with distractors."""
    rng = random.Random(seed)
    questions: List[Dict[str, Any]] = []
    q_counter = 1

    try:
        resolved = resolve_manifest(manifest)
    except Exception:
        resolved = None

    # Category 1: Dimensions (มิติระยะ)
    # 1.1 Grid Spans (X & Y)
    grid_x = sorted([(k, v) for k, v in manifest.grids.axes_x.items()], key=lambda item: item[1])
    for i in range(len(grid_x) - 1):
        g1, x1 = grid_x[i]
        g2, x2 = grid_x[i + 1]
        dist = abs(x2 - x1)
        correct_str = f"{dist:.2f} m"
        distractors = [
            f"{dist + 1.00:.2f} m",
            f"{max(0.5, dist - 1.00):.2f} m",
            f"{dist + 2.00:.2f} m",
            f"{dist * 1.5:.2f} m",
        ]
        choices, correct_key = _make_choices(correct_str, distractors, rng)

        questions.append(
            {
                "question_id": f"q_dim_{q_counter:03d}",
                "category": "Dimensions",
                "category_th": "มิติระยะ",
                "question_text": f"What is the span distance between grid line {g1} and grid line {g2}?",
                "choices": choices,
                "correct_choice": correct_key,
                "ground_truth_value": correct_str,
                "metadata": {"target_type": "grid_span", "grids": [g1, g2]},
            }
        )
        q_counter += 1

    grid_y = sorted([(k, v) for k, v in manifest.grids.axes_y.items()], key=lambda item: item[1])
    for i in range(len(grid_y) - 1):
        g1, y1 = grid_y[i]
        g2, y2 = grid_y[i + 1]
        dist = abs(y2 - y1)
        correct_str = f"{dist:.2f} m"
        distractors = [
            f"{dist + 1.50:.2f} m",
            f"{max(0.5, dist - 1.00):.2f} m",
            f"{dist + 2.50:.2f} m",
        ]
        choices, correct_key = _make_choices(correct_str, distractors, rng)

        questions.append(
            {
                "question_id": f"q_dim_{q_counter:03d}",
                "category": "Dimensions",
                "category_th": "มิติระยะ",
                "question_text": f"What is the span distance between grid line {g1} and grid line {g2}?",
                "choices": choices,
                "correct_choice": correct_key,
                "ground_truth_value": correct_str,
                "metadata": {"target_type": "grid_span", "grids": [g1, g2]},
            }
        )
        q_counter += 1

    # 1.2 Overall Envelope Span
    if len(grid_x) >= 2:
        total_span_x = abs(grid_x[-1][1] - grid_x[0][1])
        correct_str = f"{total_span_x:.2f} m"
        distractors = [
            f"{total_span_x + 2.00:.2f} m",
            f"{max(1.0, total_span_x - 3.00):.2f} m",
            f"{total_span_x + 4.00:.2f} m",
        ]
        choices, correct_key = _make_choices(correct_str, distractors, rng)

        questions.append(
            {
                "question_id": f"q_dim_{q_counter:03d}",
                "category": "Dimensions",
                "category_th": "มิติระยะ",
                "question_text": f"What is the total building width along the X-axis from grid {grid_x[0][0]} to grid {grid_x[-1][0]}?",
                "choices": choices,
                "correct_choice": correct_key,
                "ground_truth_value": correct_str,
                "metadata": {"target_type": "total_width"},
            }
        )
        q_counter += 1

    # 1.3 Wall Lengths
    for elem in manifest.elements:
        if getattr(elem, "class_", "") == "IfcWall" or isinstance(elem, IfcWall):
            tag = getattr(elem, "tag", "Wall")
            plc = getattr(elem, "placement", None)
            if plc and hasattr(plc, "from_grid") and hasattr(plc, "to_grid"):
                g_from, g_to = plc.from_grid, plc.to_grid
                x_f = manifest.grids.axes_x.get(g_from[0], 0.0)
                y_f = manifest.grids.axes_y.get(g_from[1], 0.0)
                x_t = manifest.grids.axes_x.get(g_to[0], 0.0)
                y_t = manifest.grids.axes_y.get(g_to[1], 0.0)
                w_len = math.sqrt((x_t - x_f) ** 2 + (y_t - y_f) ** 2)
                correct_str = f"{w_len:.2f} m"
                distractors = [
                    f"{w_len + 1.00:.2f} m",
                    f"{max(0.5, w_len - 1.00):.2f} m",
                    f"{w_len + 2.50:.2f} m",
                ]
                choices, correct_key = _make_choices(correct_str, distractors, rng)

                questions.append(
                    {
                        "question_id": f"q_dim_{q_counter:03d}",
                        "category": "Dimensions",
                        "category_th": "มิติระยะ",
                        "question_text": f"What is the length of wall {tag} spanning from grid ({g_from[0]},{g_from[1]}) to grid ({g_to[0]},{g_to[1]})?",
                        "choices": choices,
                        "correct_choice": correct_key,
                        "ground_truth_value": correct_str,
                        "metadata": {"target_element": tag},
                    }
                )
                q_counter += 1

    # Category 2: Topology (ความสัมพันธ์ชิ้นงาน)
    # 2.1 Column grid intersections
    for elem in manifest.elements:
        if getattr(elem, "class_", "") == "IfcColumn" or isinstance(elem, IfcColumn):
            tag = getattr(elem, "tag", "C")
            plc = getattr(elem, "placement", None)
            if plc and hasattr(plc, "grid"):
                grid_pos = plc.grid
                correct_str = f"({grid_pos[0]}, {grid_pos[1]})"
                # Distractors: other grid positions
                all_intersections = [
                    f"({gx}, {gy})" for gx in manifest.grids.axes_x for gy in manifest.grids.axes_y
                ]
                distractors = [g for g in all_intersections if g != correct_str]
                if len(distractors) < 3:
                    distractors += ["(1, C)", "(2, C)", "(3, C)"]
                choices, correct_key = _make_choices(correct_str, distractors, rng)

                questions.append(
                    {
                        "question_id": f"q_top_{q_counter:03d}",
                        "category": "Topology",
                        "category_th": "ความสัมพันธ์ชิ้นงาน",
                        "question_text": f"Which grid line intersection is column {tag} located at?",
                        "choices": choices,
                        "correct_choice": correct_key,
                        "ground_truth_value": correct_str,
                        "metadata": {"target_element": tag},
                    }
                )
                q_counter += 1

    # 2.2 Column count along grid line
    for gy in manifest.grids.axes_y:
        cols_on_gy = [
            elem for elem in manifest.elements
            if (getattr(elem, "class_", "") == "IfcColumn" or isinstance(elem, IfcColumn))
            and getattr(getattr(elem, "placement", None), "grid", [None, None])[1] == gy
        ]
        cnt = len(cols_on_gy)
        if cnt > 0:
            correct_str = f"{cnt} columns"
            distractors = [
                f"{cnt + 1} columns",
                f"{max(0, cnt - 1)} columns",
                f"{cnt + 2} columns",
            ]
            choices, correct_key = _make_choices(correct_str, distractors, rng)

            questions.append(
                {
                    "question_id": f"q_top_{q_counter:03d}",
                    "category": "Topology",
                    "category_th": "ความสัมพันธ์ชิ้นงาน",
                    "question_text": f"How many structural columns are located along grid line {gy}?",
                    "choices": choices,
                    "correct_choice": correct_key,
                    "ground_truth_value": correct_str,
                    "metadata": {"target_grid": gy},
                }
            )
            q_counter += 1

    # Category 3: Tags (สัญลักษณ์ช่องเปิด/เบอร์ชิ้นงาน)
    # 3.1 Door tags and window tags
    for elem in manifest.elements:
        if getattr(elem, "class_", "") == "IfcWall" or isinstance(elem, IfcWall):
            wall_tag = getattr(elem, "tag", "W")
            doors = getattr(elem, "doors", []) or []
            windows = getattr(elem, "windows", []) or []

            for d in doors:
                d_tag = getattr(d, "tag", "D1")
                d_plc = getattr(d, "placement", None)
                d_w = getattr(d_plc, "width_m", 0.90) if d_plc else 0.90
                correct_str = d_tag
                distractors = ["D2", "D3", "D101", "D-MAIN"]
                choices, correct_key = _make_choices(correct_str, distractors, rng)

                questions.append(
                    {
                        "question_id": f"q_tag_{q_counter:03d}",
                        "category": "Tags",
                        "category_th": "สัญลักษณ์ช่องเปิด/เบอร์ชิ้นงาน",
                        "question_text": f"What is the door tag/mark assigned to the door on wall {wall_tag}?",
                        "choices": choices,
                        "correct_choice": correct_key,
                        "ground_truth_value": correct_str,
                        "metadata": {"target_element": d_tag, "host_wall": wall_tag},
                    }
                )
                q_counter += 1

            for w in windows:
                w_tag = getattr(w, "tag", "WIND1")
                correct_str = w_tag
                distractors = ["W1", "W2", "WIND2", "W101"]
                choices, correct_key = _make_choices(correct_str, distractors, rng)

                questions.append(
                    {
                        "question_id": f"q_tag_{q_counter:03d}",
                        "category": "Tags",
                        "category_th": "สัญลักษณ์ช่องเปิด/เบอร์ชิ้นงาน",
                        "question_text": f"What is the window tag/mark assigned to the window on wall {wall_tag}?",
                        "choices": choices,
                        "correct_choice": correct_key,
                        "ground_truth_value": correct_str,
                        "metadata": {"target_element": w_tag, "host_wall": wall_tag},
                    }
                )
                q_counter += 1

    # 3.2 Beam marks
    for elem in manifest.elements:
        if getattr(elem, "class_", "") == "IfcBeam" or isinstance(elem, IfcBeam):
            b_tag = getattr(elem, "tag", "B1")
            plc = getattr(elem, "placement", None)
            if plc and hasattr(plc, "from_grid") and hasattr(plc, "to_grid"):
                g1, g2 = plc.from_grid, plc.to_grid
                correct_str = b_tag
                distractors = ["B2", "B3", "GB1", "RB1"]
                choices, correct_key = _make_choices(correct_str, distractors, rng)

                questions.append(
                    {
                        "question_id": f"q_tag_{q_counter:03d}",
                        "category": "Tags",
                        "category_th": "สัญลักษณ์ช่องเปิด/เบอร์ชิ้นงาน",
                        "question_text": f"Which beam mark/tag spans from grid ({g1[0]},{g1[1]}) to grid ({g2[0]},{g2[1]})?",
                        "choices": choices,
                        "correct_choice": correct_key,
                        "ground_truth_value": correct_str,
                        "metadata": {"target_element": b_tag},
                    }
                )
                q_counter += 1

    # Category 4: Levels (ระดับความสูง)
    for st in manifest.spatial_structure.storeys:
        correct_str = f"+{st.elevation:.2f} m" if st.elevation >= 0 else f"{st.elevation:.2f} m"
        distractors = [
            f"+{st.elevation + 3.50:.2f} m",
            f"+{st.elevation + 1.20:.2f} m",
            f"+{st.elevation + 5.00:.2f} m",
        ]
        choices, correct_key = _make_choices(correct_str, distractors, rng)

        questions.append(
            {
                "question_id": f"q_lvl_{q_counter:03d}",
                "category": "Levels",
                "category_th": "ระดับความสูง",
                "question_text": f"What is the finished elevation level for {st.name} ({st.id})?",
                "choices": choices,
                "correct_choice": correct_key,
                "ground_truth_value": correct_str,
                "metadata": {"target_storey": st.id},
            }
        )
        q_counter += 1

    # Wall/Column height level questions
    for elem in manifest.elements:
        if getattr(elem, "class_", "") in ("IfcWall", "IfcColumn") or isinstance(elem, (IfcWall, IfcColumn)):
            tag = getattr(elem, "tag", "E")
            h = getattr(elem, "height", None)
            if h is not None:
                correct_str = f"{h:.2f} m"
                distractors = [
                    f"{h + 1.00:.2f} m",
                    f"{max(0.5, h - 1.00):.2f} m",
                    f"{h + 2.00:.2f} m",
                ]
                choices, correct_key = _make_choices(correct_str, distractors, rng)

                questions.append(
                    {
                        "question_id": f"q_lvl_{q_counter:03d}",
                        "category": "Levels",
                        "category_th": "ระดับความสูง",
                        "question_text": f"What is the total height of {elem.__class__.__name__} {tag}?",
                        "choices": choices,
                        "correct_choice": correct_key,
                        "ground_truth_value": correct_str,
                        "metadata": {"target_element": tag},
                    }
                )
                q_counter += 1

    return questions


def create_procedural_manifest(model_idx: int, seed: int = 42) -> ProjectManifest:
    """Generates randomized procedural buildings with varied grids, spans, columns, walls, doors and beams."""
    rng = random.Random(seed + model_idx * 1337)
    nx = rng.randint(3, 6)
    ny = rng.randint(3, 5)

    # Generate grid coordinates
    curr_x = 0.0
    x_coords: Dict[str, float] = {}
    for i in range(nx):
        x_coords[str(i + 1)] = round(curr_x, 2)
        curr_x += rng.uniform(3.5, 7.5)

    curr_y = 0.0
    y_coords: Dict[str, float] = {}
    y_letters = [chr(65 + j) for j in range(ny)]
    for j in range(ny):
        y_coords[y_letters[j]] = round(curr_y, 2)
        curr_y += rng.uniform(4.0, 8.0)

    storeys = [
        Storey(id="L1", name="Ground Level", elevation=0.0, height=round(rng.uniform(3.2, 4.0), 2)),
        Storey(id="L2", name="Second Floor", elevation=3.5, height=round(rng.uniform(3.0, 3.5), 2)),
    ]

    elements: List[Any] = []
    # 1. Structural Columns
    col_idx = 1
    for gx in x_coords:
        for gy in y_coords:
            col_w = round(rng.choice([0.30, 0.40, 0.50]), 2)
            elements.append(
                IfcColumn(
                    **{
                        "class": "IfcColumn",
                        "tag": f"C{col_idx}",
                        "material": "CONC",
                        "profile": BoxProfile(width=col_w, depth=col_w),
                        "placement": ColumnPlacement(grid=(gx, gy), base_storey="L1", top_storey="L2"),
                    }
                )
            )
            col_idx += 1

    # 2. Structural & Partition Walls
    x_keys = list(x_coords.keys())
    wall_idx = 1
    # Perimeter walls along Y=A and Y=top
    for i in range(len(x_keys) - 1):
        # Bottom perimeter wall
        doors_b = []
        if i == 0 or rng.random() > 0.6:
            doors_b.append(
                IfcDoor(
                    **{
                        "class": "IfcDoor",
                        "tag": f"D{wall_idx}",
                        "material": "TIMBER",
                        "dimensions": Dimensions(width=0.90, height=2.10),
                        "offset_distance": 1.20,
                    }
                )
            )
        elements.append(
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": f"W{wall_idx}",
                    "material": "BRICK",
                    "thickness": 0.20,
                    "height": storeys[0].height,
                    "placement": WallPlacement(from_grid=(x_keys[i], y_letters[0]), to_grid=(x_keys[i + 1], y_letters[0]), storey="L1"),
                    "doors": doors_b,
                }
            )
        )
        wall_idx += 1

        # Top perimeter wall
        windows_t = []
        if rng.random() > 0.4:
            windows_t.append(
                IfcWindow(
                    **{
                        "class": "IfcWindow",
                        "tag": f"WIND{wall_idx}",
                        "material": "GLASS",
                        "dimensions": Dimensions(width=1.50, height=1.20),
                        "offset_distance": 1.00,
                        "sill_height": 0.90,
                    }
                )
            )
        elements.append(
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": f"W{wall_idx}",
                    "material": "BRICK",
                    "thickness": 0.20,
                    "height": storeys[0].height,
                    "placement": WallPlacement(from_grid=(x_keys[i], y_letters[-1]), to_grid=(x_keys[i + 1], y_letters[-1]), storey="L1"),
                    "windows": windows_t,
                }
            )
        )
        wall_idx += 1

    # 3. Perimeter walls along X=1 and X=last
    for j in range(len(y_letters) - 1):
        elements.append(
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": f"W{wall_idx}",
                    "material": "BRICK",
                    "thickness": 0.20,
                    "height": storeys[0].height,
                    "placement": WallPlacement(from_grid=(x_keys[0], y_letters[j]), to_grid=(x_keys[0], y_letters[j + 1]), storey="L1"),
                }
            )
        )
        wall_idx += 1

        elements.append(
            IfcWall(
                **{
                    "class": "IfcWall",
                    "tag": f"W{wall_idx}",
                    "material": "BRICK",
                    "thickness": 0.20,
                    "height": storeys[0].height,
                    "placement": WallPlacement(from_grid=(x_keys[-1], y_letters[j]), to_grid=(x_keys[-1], y_letters[j + 1]), storey="L1"),
                }
            )
        )
        wall_idx += 1

    # 4. Structural Beams
    beam_idx = 1
    for i in range(len(x_keys) - 1):
        for j in range(len(y_letters)):
            elements.append(
                IfcBeam(
                    **{
                        "class": "IfcBeam",
                        "tag": f"B{beam_idx}",
                        "material": "CONC",
                        "profile": BoxProfile(width=0.25, depth=0.50),
                        "placement": BeamPlacement(from_grid=(x_keys[i], y_letters[j]), to_grid=(x_keys[i + 1], y_letters[j]), storey="L1"),
                    }
                )
            )
            beam_idx += 1

    return ProjectManifest(
        project=ProjectInfo(id=f"PRJ-SYNTH-{model_idx + 1:03d}", name=f"Synthetic Procedural Building {model_idx + 1}"),
        spatial_structure=SpatialStructure(storeys=storeys),
        grids=Grids(axes_x=x_coords, axes_y=y_coords),
        materials=[
            Material(id="CONC", name="Structural Concrete", category="concrete", unit_cost_ref="MAT-CONC-01"),
            Material(id="BRICK", name="Masonry Wall", category="masonry", unit_cost_ref="MAT-BRICK-01"),
            Material(id="STEEL", name="Structural Steel", category="steel", unit_cost_ref="MAT-STEEL-01"),
        ],
        elements=elements,
    )


def generate_vqa_dataset(
    manifest_path: Optional[Union[str, Path]] = None,
    output_dataset_path: Union[str, Path] = "dist/vqa_dataset.json",
    output_image_dir: Union[str, Path] = "dist/vqa_images",
    target_count: Optional[int] = None,
    seed: int = 42,
) -> Dict[str, Any]:
    """Generates 2D Construction Blueprint VQA MCQ dataset and exports dataset JSON and SVG blueprint images."""
    output_dataset_path = Path(output_dataset_path)
    output_image_dir = Path(output_image_dir)
    output_dataset_path.parent.mkdir(parents=True, exist_ok=True)
    output_image_dir.mkdir(parents=True, exist_ok=True)

    all_questions: List[Dict[str, Any]] = []
    manifests: List[ProjectManifest] = []

    if manifest_path and Path(manifest_path).exists():
        manifests = [load_manifest(manifest_path)]
    elif target_count is None:
        manifests = [create_synthetic_manifest()]
    else:
        # Generate multiple procedural buildings until target question count is reached
        m_idx = 0
        while len(all_questions) < target_count and m_idx < 100:
            m = create_procedural_manifest(model_idx=m_idx, seed=seed)
            manifests.append(m)

            # Render 2D SVG blueprint for this model
            svg_content = render_sheet(m)
            svg_file = output_image_dir / f"{m.project.id}_plan.svg"
            svg_file.write_text(svg_content, encoding="utf-8")

            # Generate questions for this building
            model_qs = generate_vqa_questions(m, seed=seed + m_idx)
            for q in model_qs:
                q["question_id"] = f"q_{len(all_questions) + 1:04d}"
                q["model_id"] = m.project.id
                q["image_path"] = str(svg_file.relative_to(output_dataset_path.parent) if output_dataset_path.parent in svg_file.parents else svg_file)
                q["image_mime_type"] = "image/svg+xml"
                all_questions.append(q)
                if len(all_questions) >= target_count:
                    break

            m_idx += 1

    # Single manifest flow (either manifest_path or default target_count=None)
    if (manifest_path or target_count is None) and manifests:
        m = manifests[0]
        svg_content = render_sheet(m)
        svg_file = output_image_dir / f"{m.project.id}_plan.svg"
        svg_file.write_text(svg_content, encoding="utf-8")
        all_questions = generate_vqa_questions(m, seed=seed)
        for q in all_questions:
            q["model_id"] = m.project.id
            q["image_path"] = str(svg_file.relative_to(output_dataset_path.parent) if output_dataset_path.parent in svg_file.parents else svg_file)
            q["image_mime_type"] = "image/svg+xml"

    # Calculate summary
    cat_counts: Dict[str, int] = {}
    for q in all_questions:
        c = q["category"]
        cat_counts[c] = cat_counts.get(c, 0) + 1

    is_single_manifest = len(manifests) == 1
    proj_id = manifests[0].project.id if (is_single_manifest and manifests) else "DEBIM-VQA-BENCHMARK-PROCEDURAL"
    proj_name = manifests[0].project.name if (is_single_manifest and manifests) else f"Procedural 2D Blueprint VQA Suite ({len(manifests)} Buildings)"

    dataset_dict = {
        "project_id": proj_id,
        "project_name": proj_name,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "image_path": str(all_questions[0]["image_path"]) if all_questions else "",
        "image_mime_type": "image/svg+xml",
        "building_count": len(manifests),
        "question_count": len(all_questions),
        "category_counts": cat_counts,
        "questions": all_questions,
    }

    with open(output_dataset_path, "w", encoding="utf-8") as f:
        json.dump(dataset_dict, f, indent=2, ensure_ascii=False)

    return dataset_dict


def main():
    parser = argparse.ArgumentParser(description="Generate 2D Construction Blueprint VQA Dataset")
    parser.add_argument("--model", "-m", type=str, default=None, help="Path to debim project manifest (.yaml)")
    parser.add_argument("--output", "-o", type=str, default="dist/vqa_dataset.json", help="Path to output dataset JSON")
    parser.add_argument("--image-dir", type=str, default="dist/vqa_images", help="Directory to save 2D blueprint SVG images")
    parser.add_argument("--target-count", "-n", type=int, default=500, help="Target total question count")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for distractor choices")

    args = parser.parse_args()
    ds = generate_vqa_dataset(
        manifest_path=args.model,
        output_dataset_path=args.output,
        output_image_dir=args.image_dir,
        target_count=args.target_count,
        seed=args.seed,
    )
    print(f"Successfully generated VQA dataset with {ds['question_count']} questions across {ds.get('building_count', 1)} buildings at '{args.output}'")


if __name__ == "__main__":
    main()
