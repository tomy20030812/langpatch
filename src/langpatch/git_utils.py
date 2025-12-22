from __future__ import annotations
import subprocess
from pathlib import Path
from typing import List, Tuple

def run(cmd: List[str], cwd: Path) -> str:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{p.stderr}")
    return p.stdout.strip()

def get_current_branch(repo: Path) -> str:
    return run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo)

def list_tracked_files(repo: Path) -> List[str]:
    out = run(["git", "ls-files"], repo)
    return [line.strip() for line in out.splitlines() if line.strip()]

def get_head_commit(repo: Path) -> str:
    return run(["git", "rev-parse", "HEAD"], repo)

def apply_check(repo: Path, patch_path: Path) -> Tuple[bool, str]:
    p = subprocess.run(
        ["git", "apply", "--check", str(patch_path)],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )
    if p.returncode == 0:
        return True, "OK"
    return False, (p.stderr.strip() or p.stdout.strip() or "git apply --check failed")
