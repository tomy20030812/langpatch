from __future__ import annotations

# =========================
# ⭐ 确保 src/ 在 sys.path 中
# =========================
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# =========================
# 正常 import 项目模块
# =========================
import os
import json
from dotenv import load_dotenv

from rich import print as rprint
from rich.panel import Panel

from langpatch.config import get_settings
from langpatch.fs_utils import filter_files, list_tracked_files
from langpatch.git_utils import get_current_branch, get_head_commit, apply_check
from langpatch.indexer import build_or_update_index
from langpatch.retriever import retrieve_top_chunks
from langpatch.planner import plan_changes
from langpatch.patcher import generate_file_patch, merge_diffs
from langpatch.diff_utils import looks_like_unified_diff, sanitize_diff


load_dotenv()

REPO_PATH = os.getenv("REPO_PATH")
REQUIREMENT = os.getenv("REQUIREMENT", "").strip()
PATCH_OUTPUT_DIR = os.getenv("PATCH_OUTPUT_DIR", "./patches")
PATCH_FILE_NAME = os.getenv("PATCH_FILE_NAME", "langpatch.patch")

DEFAULT_EXCLUDES = [
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
]


def main() -> None:
    if not REPO_PATH:
        rprint("[bold red]未设置 REPO_PATH[/bold red]")
        return
    if not REQUIREMENT:
        rprint("[bold red]未设置 REQUIREMENT[/bold red]")
        return

    settings = get_settings()
    repo_root = Path(REPO_PATH).resolve()
    patch_dir = Path(PATCH_OUTPUT_DIR).resolve()
    patch_dir.mkdir(parents=True, exist_ok=True)
    patch_path = patch_dir / PATCH_FILE_NAME

    rprint(Panel.fit(
        f"[bold]Repo[/bold]: {repo_root}\n"
        f"[bold]Patch 输出[/bold]: {patch_path}\n"
        f"[bold]需求[/bold]: {REQUIREMENT}",
        title="LangPatch"
    ))

    branch = get_current_branch(repo_root)
    head = get_head_commit(repo_root)

    rprint(Panel.fit(
        f"[bold]Branch[/bold]: {branch}\n"
        f"[bold]HEAD[/bold]: {head}",
        title="Git Info"
    ))

    tracked = list_tracked_files(repo_root)
    files = filter_files(tracked, repo_root, DEFAULT_EXCLUDES)

    rprint(f"[cyan]扫描到文件数:[/cyan] {len(files)}")

    index_dir = repo_root / ".langpatch_index"
    build_or_update_index(
        repo_root=repo_root,
        index_dir=index_dir,
        files=files,
        embed_model=settings.embed_model,
        max_chars_per_file=settings.max_chars_per_file,
    )

    rprint("[green]Embedding 索引完成[/green]")

    chunks = retrieve_top_chunks(
        index_dir=index_dir,
        embed_model=settings.embed_model,
        query=REQUIREMENT,
        top_k=settings.top_k,
    )

    rprint(f"[cyan]命中代码块:[/cyan] {len(chunks)}")

    if not chunks:
        rprint("[yellow]未检索到相关代码片段[/yellow]")
        return

    try:
        plan = plan_changes(settings, REQUIREMENT, chunks)
    except Exception as e:
        rprint(f"[bold red]Planner 失败:[/bold red] {e}")
        return

    rprint(Panel.fit(
        json.dumps(plan, indent=2, ensure_ascii=False),
        title="Planner 输出"
    ))

    targets = [x["path"] for x in plan.get("files_to_modify", [])]
    targets += [x["path"] for x in plan.get("new_files", [])]

    if not targets:
        rprint("[yellow]Planner 未返回任何修改目标[/yellow]")
        return

    patches = []
    for rel_path in targets[: settings.max_files_for_llm]:
        fp = generate_file_patch(
            settings=settings,
            repo_root=repo_root,
            rel_path=rel_path,
            requirement=REQUIREMENT,
            design_notes=plan.get("design_notes", []),
        )

        diff = sanitize_diff(fp.diff)
        if not looks_like_unified_diff(diff):
            raise RuntimeError(f"{rel_path} 输出不是合法 unified diff")

        patches.append(fp.__class__(fp.rel_path, diff))

    final_patch = merge_diffs(patches)
    if not final_patch.strip():
        rprint("[bold red]Patch 为空，已中止[/bold red]")
        return

    patch_path.write_text(final_patch, encoding="utf-8")
    rprint(f"[bold green]Patch 已生成:[/bold green] {patch_path}")

    ok, msg = apply_check(repo_root, patch_path)
    if ok:
        rprint("[bold green]git apply --check 通过 ✔[/bold green]")
    else:
        rprint("[bold red]git apply --check 失败 ✘[/bold red]")
        rprint(msg)


if __name__ == "__main__":
    main()
