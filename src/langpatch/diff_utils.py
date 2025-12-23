from __future__ import annotations
import re


def looks_like_unified_diff(text: str) -> bool:
    """
    判断是否为 git 可接受的 unified diff（严格版）
    """
    return (
        text.startswith("diff --git ")
        and "\n--- " in text
        and "\n+++ " in text
        and "\n@@" in text
    )


def sanitize_diff(text: str) -> str:
    """
    清理 LLM 可能输出的 markdown 包裹或多余空白
    """
    text = re.sub(r"^```.*?\n", "", text.strip(), flags=re.DOTALL)
    text = re.sub(r"\n```$", "\n", text, flags=re.DOTALL)
    return text.rstrip() + "\n"


def extract_and_fix_hunks(text: str) -> str:
    """
    提取并修复 hunk 内容：

    规则：
    - 只处理 @@ 之后的内容
    - 允许的前缀：@@, +, -, " "
    - 其他非空行：自动补一个前导空格，视为上下文行
    - 空行直接丢弃
    """
    lines = text.splitlines()
    hunks: list[str] = []

    in_hunk = False
    has_content = False

    for line in lines:
        if line.startswith("@@"):
            in_hunk = True
            hunks.append(line)
            continue

        if not in_hunk:
            continue

        # hunk 内处理
        if not line.strip():
            # 空行直接丢弃，避免制造非法上下文
            continue

        if line.startswith(("+", "-", " ")):
            hunks.append(line)
            if not line.startswith("@@"):
                has_content = True
        else:
            # 自动补 diff 上下文前缀空格
            hunks.append(" " + line)
            has_content = True

    if not has_content:
        return ""

    return "\n".join(hunks).rstrip() + "\n"
