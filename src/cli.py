from __future__ import annotations

# =========================
# ⭐ 关键：让 python cli.py 能找到 package
# =========================
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
SRC_DIR = CURRENT_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# =========================
# 现在可以安全 import 了
# =========================
import json
import os
from rich import print as rprint
from rich.panel import Panel
from dotenv import load_dotenv

from langpatch.config import get_settings
from langpatch.git_utils import (
    get_current_branch,
    list_tracked_files,
    get_head_commit,
    apply_check,
)
from langpatch.fs_utils import filter_files, DEFAULT_EXCLUDES
from langpatch.indexer import build_or_update_index
from langpatch.retriever import retrieve_top_chunks
from langpatch.planner import plan_changes
from langpatch.patcher import generate_file_patch, merge_diffs
from langpatch.diff_utils import looks_like_unified_diff, sanitize_diff


# =========================
# 从 .env 读取配置
# =========================
load_dotenv()

REPO_PATH = os.getenv("REPO_PATH")
REQUIREMENT = os.getenv("REQUIREMENT", "").strip()
PATCH_OUTPUT_DIR = os.getenv("PATCH_OUTPUT_DIR")
PATCH_FILE_NAME = os.getenv("PATCH_FILE_NAME", "generated.patch")

if not REPO_PATH:
    raise RuntimeError("缺少 REPO_PATH（请在 .env 中配置）")

if not REQUIREMENT:
    raise RuntimeError("缺少 REQUIREMENT（请在 .env 中配置）")

if not PATCH_OUTPUT_DIR:
    raise RuntimeError("缺少 PATCH_OUTPUT_DIR（请在 .env 中配置）")


# =========================
# 主流程
# =========================
def main() -> None:
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

    index_dir = (repo_root / settings.index_dir).resolve()

    build_or_update_index(
        index_dir=index_dir,
        embed_model=settings.embed_model,
        repo_root=repo_root,
        files=files,
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

    plan = plan_changes(settings, REQUIREMENT, chunks)

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
        rprint(f"[cyan]生成 patch:[/cyan] {rel_path}")
        fp = generate_file_patch(
            settings=settings,
            repo_root=repo_root,
            requirement=REQUIREMENT,
            design_notes=plan.get("design_notes", []),
            rel_path=rel_path,
        )

        diff = sanitize_diff(fp.diff)
        if not looks_like_unified_diff(diff):
            raise RuntimeError(f"{rel_path} 输出不是合法 unified diff")

        patches.append(fp.__class__(fp.rel_path, diff))

    final_patch = merge_diffs(patches)
    patch_path.write_text(final_patch, encoding="utf-8")

    rprint(f"[bold green]Patch 已生成:[/bold green] {patch_path}")

    ok, msg = apply_check(repo_root, patch_path)
    if ok:
        rprint("[bold green]git apply --check 通过 ✔[/bold green]")
        rprint(f"应用方式: git apply {patch_path}")
    else:
        rprint(Panel.fit(msg, title="[red]git apply --check 失败[/red]"))


if __name__ == "__main__":
    main()
