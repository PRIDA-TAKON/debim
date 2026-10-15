#!/usr/bin/env python3
"""
Automated Watchdog for Jules PRs & Multi-Step Roadmap Orchestrator.
Monitors GitHub PRs periodically (default 5 minutes / 300s).
When a PR from Jules arrives:
1. Validates CI checks and auto-promotes draft PRs.
2. Performs squash merge and pulls to main.
3. Runs regression tests.
4. Automatically opens the next Roadmap Issue for Jules.
5. Stops cleanly upon reaching the final wave (prevents infinite loop).

Usage:
  python tools/watchdog_jules_prs.py [--once] [--interval 300] [--config tools/roadmap_v081.json]
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Safe Unicode output for Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def safe_print(msg: str):
    """Print message safely without encoding errors on any console."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="replace").decode("ascii"))


def run(cmd, cwd=None):
    res = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd
    )
    return res.returncode, res.stdout.strip(), res.stderr.strip()


def check_existing_issue(title, cwd=None):
    """Check if an issue with this title already exists in EITHER open OR closed state."""
    code, stdout, _ = run("gh issue list --state all --limit 100 --json title", cwd=cwd)
    if code == 0 and stdout:
        try:
            issues = json.loads(stdout)
            norm_target = title.strip().lower()
            for iss in issues:
                if iss.get("title", "").strip().lower() == norm_target:
                    return True
        except Exception:
            pass
    return False


def load_roadmap(config_path: Path):
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            safe_print(f"[WARN] Failed to load custom roadmap from {config_path}: {e}")
    
    safe_print(f"[ERROR] Roadmap configuration not found at {config_path}")
    return []


def trigger_next_roadmap_issue(merged_title, roadmap, cwd=None):
    title_lower = merged_title.lower()
    for item in roadmap:
        matched = any(kw.lower() in title_lower for kw in item.get("match_keywords", []))
        if matched:
            wave_num = item.get("wave", "?")
            is_final = item.get("is_final_wave", False)
            next_issue = item.get("next_issue")

            # Protection against infinite loops: Check if this was the final wave
            if is_final or not next_issue:
                safe_print(f"\n[ROADMAP COMPLETE] Wave {wave_num} was the final wave!")
                safe_print("All planned roadmap milestones have been successfully merged.")
                safe_print("No further issues will be created (infinite loop prevented).\n")
                return True

            iss_title = next_issue.get("title", "").strip()
            iss_body = next_issue.get("body", "").strip()
            iss_label = next_issue.get("label", "jules")

            # Double check if issue already exists (open OR closed) to prevent duplicates
            if check_existing_issue(iss_title, cwd=cwd):
                safe_print(f"[SKIP] Issue '{iss_title}' already exists in GitHub (open or closed). Skipping creation to avoid loop.")
                return True

            safe_print(f"\n[NEXT WAVE TRIGGERED] Matched Wave {wave_num}! Triggering next issue for Jules:")
            safe_print(f"Title: {iss_title}")
            cmd = [
                "gh", "issue", "create",
                "--title", iss_title,
                "--body", iss_body,
                "--label", iss_label
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd)
            if res.returncode == 0:
                safe_print(f"Successfully created next issue:\n{res.stdout.strip()}")
            else:
                safe_print(f"Failed to create issue:\n{res.stderr.strip()}")
            return True

    safe_print(f"[INFO] No matching next roadmap wave for merged PR: '{merged_title}'")
    return False


def check_and_process_prs(roadmap, cwd=None):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    safe_print(f"[{now_str}] Checking open PRs...")
    code, stdout, _ = run("gh pr list --state open --json number,title,isDraft,headRefName", cwd=cwd)
    if code != 0 or not stdout:
        safe_print(f"[{now_str}] No PRs or error listing PRs.")
        return False

    try:
        prs = json.loads(stdout)
    except Exception as e:
        safe_print(f"Error parsing PR list: {e}")
        return False

    if not prs:
        safe_print(f"[{now_str}] No open PRs found. Watching and waiting for Jules...")
        return False

    merged_any = False
    for pr in prs:
        num = pr["number"]
        title = pr["title"]
        is_draft = pr["isDraft"]
        branch = pr["headRefName"]
        safe_print(f"[{now_str}] Found PR #{num}: {title} (Draft: {is_draft}, Branch: {branch})")

        # 1. Inspect CI checks
        code, checks_out, _ = run(f"gh pr checks {num}", cwd=cwd)
        safe_print(f"Checks for #{num}:\n{checks_out}")

        if "fail" in checks_out.lower():
            safe_print(f"PR #{num} has failed checks. Skipping auto-merge.")
            continue

        if any(w in checks_out.lower() for w in ["pending", "in_progress", "queued"]):
            safe_print(f"PR #{num} has checks still in progress. Waiting for CI to complete...")
            continue

        # 2. Mark ready for review if draft
        if is_draft:
            safe_print(f"Marking PR #{num} ready for review...")
            run(f"gh pr ready {num}", cwd=cwd)

        # 3. Squash merge
        safe_print(f"Attempting squash merge for #{num}...")
        m_code, m_out, m_err = run(f"gh pr merge {num} --squash --delete-branch", cwd=cwd)
        safe_print(f"Merge result: {m_out} {m_err}")

        if m_code == 0:
            merged_any = True
            safe_print(f"Successfully merged PR #{num}!")

            # 4. Pull to main cleanly and verify
            run("git checkout -- debim.schema.json spec/debim.schema.json docs/index.html", cwd=cwd)
            run("git checkout main", cwd=cwd)
            run("git pull origin main", cwd=cwd)
            safe_print("Verifying core test suite on main...")
            t_code, t_out, _ = run("pytest tests/test_cantilever_beams.py tests/test_main_entry.py", cwd=cwd)
            if t_code == 0:
                safe_print("Core tests verified successfully!")
            else:
                safe_print(f"Notice: Tests reported output: {t_out}")

            # 5. Open next roadmap issue
            trigger_next_roadmap_issue(title, roadmap, cwd=cwd)

    return merged_any


def main():
    parser = argparse.ArgumentParser(description="Automated Watchdog for Jules PRs & Multi-Step Roadmap Orchestrator")
    parser.add_argument("--interval", type=int, default=300, help="Polling interval in seconds (default: 300s / 5m)")
    parser.add_argument("--once", action="store_true", help="Run once and exit immediately")
    parser.add_argument("--config", type=str, default="tools/roadmap_v081.json", help="Path to custom roadmap JSON file")
    parser.add_argument("--cwd", type=str, default=None, help="Working directory for git and gh commands")
    args = parser.parse_args()

    work_dir = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    config_file = Path(args.config)
    if not config_file.is_absolute():
        config_file = work_dir / config_file

    roadmap = load_roadmap(config_file)
    if not roadmap:
        safe_print("[FATAL] Cannot run watchdog without a valid roadmap configuration.")
        sys.exit(1)

    if args.once:
        check_and_process_prs(roadmap, cwd=work_dir)
        return

    safe_print("=== Starting Jules PR Watchdog Orchestrator ===")
    safe_print(f"Target Directory: {work_dir}")
    safe_print(f"Roadmap Config:   {config_file.name} ({len(roadmap)} waves configured)")
    safe_print(f"Polling Interval: {args.interval} seconds ({args.interval / 60:.1f} minutes)")
    safe_print(f"Loop Protection:  Active (checks all open/closed issues, final wave halts)")
    safe_print("Press Ctrl+C to stop.\n")

    while True:
        try:
            check_and_process_prs(roadmap, cwd=work_dir)
            time.sleep(args.interval)
        except KeyboardInterrupt:
            safe_print("\nWatchdog stopped by user.")
            break
        except Exception as e:
            safe_print(f"Unexpected error in watchdog loop: {e}")
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
