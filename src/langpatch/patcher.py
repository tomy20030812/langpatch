from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List

from langchain_core.messages import SystemMessage, HumanMessage

from .config import Settings
from .llm import get_llm
from .prompts import PATCH_SYSTEM, PATCH_USER
from .fs_utils import read_text_safely
from .diff_utils import (
    sanitize_diff,
    extract_and_fix_hunks,
    looks_like_unified_diff,
)


@dataclass
class FilePatch:
    rel_path: str
    diff: str


def _make_diff_header(rel_path: str) -> str:
    return (
        f"diff --git a/{rel_path} b/{rel_path}\n"
        f"--- a/{rel_path}\n"
        f"+++ b/{rel_path}\n"
    )


def generate_file_patch(
    settings: Settings,
    repo_root: Path,
    requirement: str,
    design_notes: List[str],
    rel_path: str,
) -> FilePatch:
    llm = get_llm(settings)
    abs_path = (repo_root / rel_path).resolve()

    original = ""
    if abs_path.exists():
        original = read_text_safely(abs_path, max_chars=settings.max_chars_per_file)

    msg = [
        SystemMessage(content=PATCH_SYSTEM),
        HumanMessage(
            content=PATCH_USER.format(
                requirement=requirement,
                design_notes="\n".join(f"- {n}" for n in design_notes),
                path=rel_path,
                content=original,
            )
        ),
    ]

    raw = llm.invoke(msg).content
    raw = sanitize_diff(raw)

    hunks = extract_and_fix_hunks(raw)
    if not hunks:
        raise RuntimeError(f"{rel_path}: 未生成任何合法 diff hunk")

    diff = _make_diff_header(rel_path) + hunks
    return FilePatch(rel_path=rel_path, diff=diff)


def merge_diffs(patches: List[FilePatch]) -> str:
    out: List[str] = []

    for p in patches:
        if not looks_like_unified_diff(p.diff):
            raise RuntimeError(f"{p.rel_path}: 非法 unified diff，拒绝合并")
        out.append(p.diff.rstrip())

    return "\n\n".join(out).rstrip() + "\n"
