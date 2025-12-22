from __future__ import annotations
from pathlib import Path
from typing import Iterable, List

DEFAULT_EXCLUDES = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".idea", ".vscode",
}

def is_excluded(path: Path, repo_root: Path, excludes: set[str]) -> bool:
    rel = path.relative_to(repo_root)
    for part in rel.parts:
        if part in excludes:
            return True
    return False

def read_text_safely(path: Path, max_chars: int) -> str:
    data = path.read_bytes()
    # naive utf-8 decode fallback
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="ignore")
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n# [TRUNCATED]\n"
    return text

def filter_files(files: Iterable[str], repo_root: Path, excludes: set[str]) -> List[Path]:
    out: List[Path] = []
    for f in files:
        p = (repo_root / f).resolve()
        if not p.exists():
            continue
        if is_excluded(p, repo_root, excludes):
            continue
        out.append(p)
    return out
