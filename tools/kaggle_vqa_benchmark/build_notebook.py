"""Script to build Kaggle Notebook for debim 2D blueprint VQA benchmark."""
import nbformat as nbf

nb = nbf.v4.new_notebook()

cells = []

# Cell 1: Markdown Title
cells.append(nbf.v4.new_markdown_cell("""# 📐 debim: 2D Construction Blueprint VQA Cognitive Benchmark (Kaggle Edition)

[![GitHub Repository](https://img.shields.io/badge/GitHub-PRIDA--TAKON%2Fdebim-181717?logo=github&style=for-the-badge)](https://github.com/PRIDA-TAKON/debim)

> **Autonomous 2D Blueprint Multimodal Evaluation via Gemini 3.8 Live Extended Thinking**
> - Scans real-world IFC building models from Kaggle datasets (`pridatakon/debim-5000-ifc-benchmark`)
> - Extracts ground-truth floor plans, spatial grids, element schedules, and elevation heights
> - Renders production-grade 2D CAD blueprint sheets (SVG)
> - Formulates 500 Ground-Truth 4-Choice MCQs across 4 cognitive categories: **Dimensions**, **Topology**, **Tags**, and **Levels**
> - Evaluates multimodal cognitive comprehension using **Gemini 3.8 Live Extended Thinking** ($0 Free Tier Token Bucket)
"""))

# Cell 2: Install dependencies
cells.append(nbf.v4.new_code_cell("""# 1. Environment Setup & Dependency Installation
!pip install -q ifcopenshell "pydantic>=2.0" pyyaml rich httpx websockets pandas tabulate matplotlib pillow

!rm -rf /kaggle/working/debim
!git clone https://github.com/PRIDA-TAKON/debim.git /kaggle/working/debim

import sys
sys.path.insert(0, "/kaggle/working/debim/src")
sys.path.insert(0, "/kaggle/working/debim")
print("Environment successfully initialized with debim engine.")
"""))

# Cell 3: Discover IFC files
cells.append(nbf.v4.new_code_cell("""# 2. Discover Real-World IFC Models from Kaggle Datasets
from pathlib import Path

input_root = Path("/kaggle/input")
all_ifc_files = sorted(list(input_root.glob("**/*.ifc")))
print(f"Total discovered IFC files in datasets: {len(all_ifc_files)}")

# Filter and select candidate building models (size between 20KB and 15MB)
candidate_models = []
seen_names = set()
for p in all_ifc_files:
    sz = p.stat().st_size
    if 20_000 <= sz <= 15_000_000 and p.name not in seen_names:
        seen_names.add(p.name)
        candidate_models.append(p)

print(f"Selected {len(candidate_models)} candidate IFC models for 2D Blueprint VQA extraction.")
for p in candidate_models[:10]:
    print(f"  - {p.name} ({p.stat().st_size / 1024:.1f} KB)")
"""))

# Cell 4: Extract Ground Truth & Render 2D Blueprints
cells.append(nbf.v4.new_code_cell("""# 3. Extract 2D Blueprints and Generate 500 VQA Questions
import json
from debim.importer import import_ifc_to_manifest
from debim.draw.renderer import render_sheet
from tools.generate_vqa_dataset import generate_vqa_questions

out_dir = Path("/kaggle/working/vqa_kaggle")
out_img_dir = out_dir / "images"
out_img_dir.mkdir(parents=True, exist_ok=True)

all_kaggle_questions = []
successful_models = []

target_questions = 500

for ifc_file in candidate_models:
    if len(all_kaggle_questions) >= target_questions:
        break
    try:
        manifest = import_ifc_to_manifest(str(ifc_file))
        if not manifest.elements or len(manifest.grids.axes_x) < 2:
            continue
            
        svg_content = render_sheet(manifest)
        safe_id = "".join([c if c.isalnum() else "_" for c in ifc_file.stem])[:30]
        svg_file = out_img_dir / f"{safe_id}_plan.svg"
        svg_file.write_text(svg_content, encoding="utf-8")
        
        qs = generate_vqa_questions(manifest, seed=len(successful_models) * 42)
        if not qs:
            continue
            
        for q in qs:
            q["question_id"] = f"q_kgl_{len(all_kaggle_questions)+1:04d}"
            q["model_id"] = safe_id
            q["source_file"] = ifc_file.name
            q["image_path"] = str(svg_file.relative_to(out_dir))
            q["image_mime_type"] = "image/svg+xml"
            all_kaggle_questions.append(q)
            if len(all_kaggle_questions) >= target_questions:
                break
                
        successful_models.append(ifc_file.name)
        print(f"Extracted {len(qs)} questions from {ifc_file.name} (Total so far: {len(all_kaggle_questions)})")
    except Exception as e:
        continue

dataset_payload = {
    "project_id": "DEBIM-VQA-KAGGLE-REAL-WORLD",
    "project_name": f"Kaggle Real-World IFC Blueprint VQA Suite ({len(successful_models)} Models)",
    "question_count": len(all_kaggle_questions),
    "model_count": len(successful_models),
    "questions": all_kaggle_questions,
}

kaggle_dataset_path = out_dir / "vqa_kaggle_dataset_500.json"
with open(kaggle_dataset_path, "w", encoding="utf-8") as f:
    json.dump(dataset_payload, f, indent=2, ensure_ascii=False)

print(f"Generated Kaggle VQA Dataset: {len(all_kaggle_questions)} questions saved to {kaggle_dataset_path}")
"""))

# Cell 5: Gemini 3.8 Live Extended Thinking Execution
cells.append(nbf.v4.new_code_cell("""# 4. Evaluate Cognitive Benchmark via Gemini 3.8 Live Extended Thinking
import os
from kaggle_secrets import UserSecretsClient
from tools.benchmark_vqa_gemini import run_vqa_benchmark, generate_vqa_dataset

if not all_kaggle_questions:
    print("No valid IFC questions extracted. Generating procedural fallback dataset for benchmark evaluation...")
    ds_dict = generate_vqa_dataset(target_count=100, output_dataset_path=kaggle_dataset_path, output_image_dir=out_img_dir)
    print(f"Fallback dataset generated with {ds_dict['question_count']} questions.")

api_key = None
try:
    user_secrets = UserSecretsClient()
    api_key = user_secrets.get_secret("GEMINI_API_KEY")
    print("Found GEMINI_API_KEY from Kaggle Secrets!")
except Exception:
    api_key = os.getenv("GEMINI_API_KEY")

use_mock = not bool(api_key)
if use_mock:
    print("No GEMINI_API_KEY found. Running dry-run simulation mode (--mock-eval)...")
else:
    print("Running Live Multimodal Evaluation with models/gemini-3.8-live-extended-thinking...")

report = run_vqa_benchmark(
    dataset_path=kaggle_dataset_path,
    api_key=api_key,
    model_name="models/gemini-3.8-live-extended-thinking",
    mock_eval=use_mock,
    rpm=60,
    tpm=65000,
    thinking_budget=2048,
    output_report_path=out_dir / "kaggle_vqa_report.json",
    output_markdown_path=out_dir / "kaggle_vqa_report.md",
)

print(f"Benchmark finished! Overall Accuracy: {report.overall_accuracy * 100:.2f}% ({report.total_correct}/{report.total_questions})")
"""))

# Cell 6: Visual Analytics & Markdown Table
cells.append(nbf.v4.new_code_cell("""# 5. Visual Accuracy Breakdown & Category Analysis
from IPython.display import display, Markdown

report_md_file = out_dir / "kaggle_vqa_report.md"
if report_md_file.exists():
    md_content = report_md_file.read_text(encoding="utf-8")
    display(Markdown(md_content))
else:
    print("Report file not generated.")
"""))

nb.cells = cells
nb.metadata = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3"
    },
    "language_info": {
        "name": "python",
        "version": "3.11.9"
    }
}
with open("tools/kaggle_vqa_benchmark/debim_2d_blueprint_vqa_benchmark.ipynb", "w", encoding="utf-8") as f:
    nbf.write(nb, f)

print("Kaggle notebook generated successfully!")
