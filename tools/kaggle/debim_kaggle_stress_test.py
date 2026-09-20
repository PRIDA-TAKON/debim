"""
debim Ultra-Stress Testing Runner for Kaggle (and High-Performance Batch Benchmarking).
Processes thousands of real-world IFC files in parallel with process isolation,
hard timeouts, failure taxonomy categorization, and comprehensive KPI analytics.
"""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, TimeoutError
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

import ifcopenshell
import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from debim.importer import import_ifc_to_manifest
    from debim.compiler import compile_to_ifc
    from tools.compare_ifc import count_ifc_elements
except ImportError:
    # If running in bare environment where debim is installed via pip
    from debim.importer import import_ifc_to_manifest
    from debim.compiler import compile_to_ifc

    def count_ifc_elements(ifc_path: Path) -> Tuple[int, Counter]:
        ifc_file = ifcopenshell.open(str(ifc_path))
        elements = [e for e in ifc_file.by_type("IfcElement") if not e.is_a("IfcOpeningElement")]
        counter = Counter()
        for elem in elements:
            t = elem.is_a()
            if t == "IfcWallStandardCase":
                t = "IfcWall"
            elif t == "IfcDoorStandardCase":
                t = "IfcDoor"
            elif t == "IfcWindowStandardCase":
                t = "IfcWindow"
            counter[t] += 1
        return len(elements), counter


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            file_name TEXT PRIMARY KEY,
            file_path TEXT,
            file_size_bytes INTEGER,
            ifc_schema TEXT,
            authoring_app TEXT,
            orig_physical_count INTEGER,
            extracted_yaml_count INTEGER,
            recompiled_ifc_count INTEGER,
            retention_rate_pct REAL,
            yaml_size_bytes INTEGER,
            compression_ratio_pct REAL,
            estimated_tokens_ifc INTEGER,
            estimated_tokens_yaml INTEGER,
            token_saving_pct REAL,
            duration_sec REAL,
            status TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def get_completed_files(db_path: Path) -> set:
    if not db_path.exists():
        return set()
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT file_name FROM results")
    rows = cursor.fetchall()
    conn.close()
    return {r[0] for r in rows}


def process_single_ifc(args_tuple: Tuple[str, str, int]) -> Dict[str, Any]:
    """
    Worker function executed in an isolated process.
    """
    ifc_path_str, work_dir_str, file_idx = args_tuple
    ifc_path = Path(ifc_path_str)
    work_dir = Path(work_dir_str)
    file_name = ifc_path.name

    res = {
        "file_name": file_name,
        "file_path": str(ifc_path),
        "file_size_bytes": ifc_path.stat().st_size,
        "ifc_schema": "UNKNOWN",
        "authoring_app": "UNKNOWN",
        "orig_physical_count": 0,
        "extracted_yaml_count": 0,
        "recompiled_ifc_count": 0,
        "retention_rate_pct": 0.0,
        "yaml_size_bytes": 0,
        "compression_ratio_pct": 0.0,
        "estimated_tokens_ifc": int(ifc_path.stat().st_size / 3.5),
        "estimated_tokens_yaml": 0,
        "token_saving_pct": 0.0,
        "duration_sec": 0.0,
        "status": "INIT",
        "error_message": "",
    }

    start_time = time.time()
    try:
        # 1. Inspect IFC header & elements
        ifc_obj = ifcopenshell.open(str(ifc_path))
        res["ifc_schema"] = getattr(ifc_obj, "schema", "UNKNOWN")
        apps = ifc_obj.by_type("IfcApplication")
        if apps:
            app = apps[0]
            res["authoring_app"] = f"{getattr(app, 'ApplicationFullName', '')} {getattr(app, 'Version', '')}".strip()

        orig_count, _ = count_ifc_elements(ifc_path)
        res["orig_physical_count"] = orig_count

        # 2. Convert to declarative debim manifest
        manifest = import_ifc_to_manifest(ifc_path)
        res["extracted_yaml_count"] = len(manifest.elements)

        # 3. Serialize to YAML
        yaml_out = work_dir / f"temp_{file_idx}_{ifc_path.stem}.yaml"
        manifest_dict = json.loads(manifest.model_dump_json(by_alias=True, exclude_none=True))
        with open(yaml_out, "w", encoding="utf-8") as f:
            yaml.safe_dump(manifest_dict, f, allow_unicode=True, sort_keys=False)

        yaml_size = yaml_out.stat().st_size
        res["yaml_size_bytes"] = yaml_size
        res["estimated_tokens_yaml"] = int(yaml_size / 3.5)

        if res["file_size_bytes"] > 0:
            res["compression_ratio_pct"] = round((1.0 - yaml_size / res["file_size_bytes"]) * 100.0, 2)
            res["token_saving_pct"] = res["compression_ratio_pct"]

        # 4. Re-compile back to IFC
        recomp_out = work_dir / f"temp_{file_idx}_{ifc_path.stem}_recompiled.ifc"
        compile_to_ifc(yaml_out, recomp_out)

        # 5. Count recompiled physical elements
        recomp_count, _ = count_ifc_elements(recomp_out)
        res["recompiled_ifc_count"] = recomp_count

        if orig_count > 0:
            res["retention_rate_pct"] = round(min(100.0, (recomp_count / orig_count) * 100.0), 2)
        else:
            res["retention_rate_pct"] = 100.0

        res["status"] = "SUCCESS" if res["retention_rate_pct"] >= 95.0 else "PARTIAL_RETENTION"

        # Cleanup temp files to preserve disk space
        if yaml_out.exists():
            yaml_out.unlink()
        if recomp_out.exists():
            recomp_out.unlink()

    except Exception as e:
        res["status"] = "ERROR"
        res["error_message"] = f"{type(e).__name__}: {str(e)}"

    res["duration_sec"] = round(time.time() - start_time, 2)
    return res


def scan_for_ifc_files(search_paths: List[Path]) -> List[Path]:
    """
    Recursively scan directories for *.ifc and *.IFC files.
    """
    files: List[Path] = []
    seen = set()
    for sp in search_paths:
        if not sp.exists():
            continue
        if sp.is_file() and sp.suffix.lower() == ".ifc":
            if str(sp) not in seen:
                files.append(sp)
                seen.add(str(sp))
            continue

        for root, _, filenames in os.walk(sp):
            for fn in filenames:
                if fn.lower().endswith(".ifc"):
                    fp = Path(root) / fn
                    if str(fp) not in seen:
                        files.append(fp)
                        seen.add(str(fp))
    return sorted(files, key=lambda f: f.stat().st_size)


def run_stress_test(
    input_dirs: List[Path],
    output_dir: Path,
    max_files: Optional[int] = None,
    timeout_sec: int = 45,
    workers: int = 4,
    resume: bool = True,
):
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_work_dir = output_dir / "temp_run"
    temp_work_dir.mkdir(parents=True, exist_ok=True)

    db_path = output_dir / "debim_stress_test.sqlite"
    conn = init_db(db_path)

    completed = get_completed_files(db_path) if resume else set()
    print(f"[INFO] Found {len(completed)} already completed tasks in DB.")

    all_files = scan_for_ifc_files(input_dirs)
    print(f"[INFO] Discovered {len(all_files)} IFC files across input paths.")

    pending_files = [f for f in all_files if f.name not in completed]
    if max_files:
        pending_files = pending_files[:max_files]

    print(f"[INFO] Running stress test on {len(pending_files)} files using {workers} parallel workers (timeout: {timeout_sec}s)...")

    success_count = 0
    fail_count = 0
    timeout_count = 0

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {}
        for idx, ifc_f in enumerate(pending_files):
            task = (str(ifc_f), str(temp_work_dir), idx)
            fut = executor.submit(process_single_ifc, task)
            futures[fut] = (ifc_f.name, str(ifc_f), ifc_f.stat().st_size)

        for fut, (fname, fpath, fsize) in futures.items():
            try:
                res = fut.result(timeout=timeout_sec)
            except TimeoutError:
                timeout_count += 1
                res = {
                    "file_name": fname,
                    "file_path": fpath,
                    "file_size_bytes": fsize,
                    "ifc_schema": "UNKNOWN",
                    "authoring_app": "UNKNOWN",
                    "orig_physical_count": 0,
                    "extracted_yaml_count": 0,
                    "recompiled_ifc_count": 0,
                    "retention_rate_pct": 0.0,
                    "yaml_size_bytes": 0,
                    "compression_ratio_pct": 0.0,
                    "estimated_tokens_ifc": int(fsize / 3.5),
                    "estimated_tokens_yaml": 0,
                    "token_saving_pct": 0.0,
                    "duration_sec": float(timeout_sec),
                    "status": "TIMEOUT",
                    "error_message": f"Execution timed out after {timeout_sec}s",
                }
            except Exception as pe:
                fail_count += 1
                res = {
                    "file_name": fname,
                    "file_path": fpath,
                    "file_size_bytes": fsize,
                    "ifc_schema": "UNKNOWN",
                    "authoring_app": "UNKNOWN",
                    "orig_physical_count": 0,
                    "extracted_yaml_count": 0,
                    "recompiled_ifc_count": 0,
                    "retention_rate_pct": 0.0,
                    "yaml_size_bytes": 0,
                    "compression_ratio_pct": 0.0,
                    "estimated_tokens_ifc": int(fsize / 3.5),
                    "estimated_tokens_yaml": 0,
                    "token_saving_pct": 0.0,
                    "duration_sec": 0.0,
                    "status": "CRASH",
                    "error_message": f"Worker crashed: {str(pe)}",
                }

            if res["status"] in ("SUCCESS", "PARTIAL_RETENTION"):
                success_count += 1
            else:
                fail_count += 1

            # Save incrementally to SQLite
            conn.execute("""
                INSERT OR REPLACE INTO results (
                    file_name, file_path, file_size_bytes, ifc_schema, authoring_app,
                    orig_physical_count, extracted_yaml_count, recompiled_ifc_count,
                    retention_rate_pct, yaml_size_bytes, compression_ratio_pct,
                    estimated_tokens_ifc, estimated_tokens_yaml, token_saving_pct,
                    duration_sec, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                res["file_name"], res["file_path"], res["file_size_bytes"],
                res["ifc_schema"], res["authoring_app"], res["orig_physical_count"],
                res["extracted_yaml_count"], res["recompiled_ifc_count"],
                res["retention_rate_pct"], res["yaml_size_bytes"],
                res["compression_ratio_pct"], res["estimated_tokens_ifc"],
                res["estimated_tokens_yaml"], res["token_saving_pct"],
                res["duration_sec"], res["status"], res["error_message"],
            ))
            conn.commit()

            print(f"[{res['status']:<15}] {fname} | Ret: {res['retention_rate_pct']:.1f}% | Comp: {res['compression_ratio_pct']:.1f}% | Time: {res['duration_sec']:.1f}s")

    # Generate Export CSV and Markdown summary
    export_analytics(conn, output_dir)
    conn.close()
    print("[INFO] Stress test completed successfully.")


def export_analytics(conn: sqlite3.Connection, output_dir: Path):
    import pandas as pd
    df = pd.read_sql_query("SELECT * FROM results", conn)

    csv_path = output_dir / "debim_benchmark_summary.csv"
    df.to_csv(csv_path, index=False)
    print(f"[INFO] Exported summary CSV to {csv_path}")

    total_files = len(df)
    if total_files == 0:
        return

    success_df = df[df["status"].isin(["SUCCESS", "PARTIAL_RETENTION"])]
    crash_resilience_rate = (len(success_df) / total_files) * 100.0
    avg_retention = success_df["retention_rate_pct"].mean() if len(success_df) > 0 else 0.0
    median_retention = success_df["retention_rate_pct"].median() if len(success_df) > 0 else 0.0
    avg_compression = success_df["compression_ratio_pct"].mean() if len(success_df) > 0 else 0.0
    total_tokens_saved = (success_df["estimated_tokens_ifc"] - success_df["estimated_tokens_yaml"]).sum()

    report_md = output_dir / "debim_benchmark_report.md"
    content = f"""# 📊 debim Ultra-Stress Testing Report

- **Total IFC Models Evaluated:** {total_files}
- **Crash-Resilience Rate:** {crash_resilience_rate:.1f}% ({len(success_df)}/{total_files})
- **Average Retention Rate:** {avg_retention:.1f}% (Median: {median_retention:.1f}%)
- **Average File Compression:** {avg_compression:.1f}%
- **Total LLM Tokens Saved:** {total_tokens_saved:,} tokens

## Status Breakdown
{df['status'].value_counts().to_markdown()}

## Top Failure Patterns
{df[df['status'] != 'SUCCESS']['error_message'].value_counts().head(10).to_markdown()}
"""
    report_md.write_text(content, encoding="utf-8")
    print(f"[INFO] Exported markdown report to {report_md}")


def main():
    parser = argparse.ArgumentParser(description="debim Ultra-Stress Testing Runner")
    parser.add_argument(
        "--input-dirs",
        nargs="+",
        default=["/kaggle/input", "./tests/fixtures"],
        help="Input directories containing IFC files",
    )
    parser.add_argument(
        "--output-dir",
        default="/kaggle/working" if Path("/kaggle/working").exists() else "./benchmark_output",
        help="Directory to store sqlite DB, CSV, and markdown reports",
    )
    parser.add_argument("--max-files", type=int, default=None, help="Limit number of files to process")
    parser.add_argument("--timeout", type=int, default=45, help="Per-file execution timeout in seconds")
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1), help="Worker processes")
    parser.add_argument("--no-resume", action="store_true", help="Do not resume from existing sqlite DB")

    args = parser.parse_args()
    input_paths = [Path(p) for p in args.input_dirs]
    output_path = Path(args.output_dir)

    run_stress_test(
        input_dirs=input_paths,
        output_dir=output_path,
        max_files=args.max_files,
        timeout_sec=args.timeout,
        workers=args.workers,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
