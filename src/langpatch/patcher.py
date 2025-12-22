from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Tuple

from langchain_core.messages import SystemMessage, HumanMessage

from .config import Settings
from .llm import get_llm
from .prompts import PATCH_SYSTEM, PATCH_USER
from .fs_utils import read_text_safely

@dataclass
class FilePatch:
    rel_path: str
    diff: str

def generate_file_patch(settings: Settings, repo_root: Path, requirement: str, design_notes: List[str], rel_path: str) -> FilePatch:
    llm = get_llm(settings)
    abs_path = (repo_root / rel_path).resolve()

    original = ""
    if abs_path.exists():
        original = read_text_safely(abs_path, max_chars=settings.max_chars_per_file)

    msg = [
        SystemMessage(content=PATCH_SYSTEM),
        HumanMessage(content=PATCH_USER.format(
            requirement=requirement,
            design_notes="\n".join(f"- {n}" for n in design_notes),
            path=rel_path,
            content=original,
        )),
    ]
    diff = llm.invoke(msg).content
    return FilePatch(rel_path=rel_path, diff=diff)

def merge_diffs(patches: List[FilePatch]) -> str:
    # simply concatenate with newlines
    return "\n".join(p.diff.rstrip() for p in patches).rstrip() + "\n"
