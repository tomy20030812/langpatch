from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable, List

DEFAULT_EXCLUDES = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".idea", ".vscode",
}


def is_excluded(path: Path, repo_root: Path, excludes: set[str]) -> bool:
    """
    判断路径是否应被排除：
    - 任一路径段命中 excludes 即视为排除
    - 不在 repo_root 下的路径视为排除
    """
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        return True

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


def filter_files(
    files: Iterable[Path],
    repo_root: Path,
    excludes: set[str],
) -> List[Path]:
    """
    过滤文件列表。

    约定：
    - files 必须是 Path 对象
    - 返回值是存在于 repo_root 下的 Path
    """
    out: List[Path] = []
    for p in files:
        if not p.exists():
            continue
        if is_excluded(p, repo_root, excludes):
            continue
        out.append(p)
    return out


def list_tracked_files(repo_root: Path) -> List[Path]:
    """
    列出 git 仓库中所有被追踪的文件（等价于 `git ls-files`）
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except Exception as e:
        raise RuntimeError(f"执行 git ls-files 失败: {e}")

    files: List[Path] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        files.append((repo_root / line).resolve())

    return files
