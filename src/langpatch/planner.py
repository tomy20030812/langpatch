from __future__ import annotations
import json
import re
from typing import Any, Dict, List
from langchain_core.messages import SystemMessage, HumanMessage

from .prompts import PLANNER_SYSTEM, PLANNER_USER
from .llm import get_llm
from .config import Settings

def _format_snippets(chunks: List[dict], max_chars: int = 60_000) -> str:
    parts: List[str] = []
    total = 0
    for c in chunks:
        meta = c["meta"]
        header = f"[{meta.get('rel_path')} :: {meta.get('symbol')} :: lines {meta.get('start_line')}-{meta.get('end_line')}]"
        body = c["document"]
        block = header + "\n" + body + "\n"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n---\n".join(parts)

def plan_changes(settings: Settings, requirement: str, retrieved_chunks: List[dict]) -> Dict[str, Any]:
    llm = get_llm(settings)

    snippets = _format_snippets(retrieved_chunks)

    msg = [
        SystemMessage(content=PLANNER_SYSTEM),
        HumanMessage(content=PLANNER_USER.format(requirement=requirement, snippets=snippets)),
    ]
    resp = llm.invoke(msg).content

    return _parse_planner_json(resp)


def _parse_planner_json(raw: str) -> Dict[str, Any]:
    """Parse planner JSON output with small, safe repair attempts.

    The planner is instructed to output strict JSON, but LLMs occasionally wrap JSON
    in markdown fences or include stray text. We try a few low-risk extractions
    before failing with a user-friendly error.
    """
    s = (raw or "").strip()

    # 1) Direct JSON
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # 2) Extract ```json ... ``` or ``` ... ```
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", s, flags=re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # 3) Fallback: take the first balanced-ish object by outer braces.
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = s[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            raise ValueError(
                "Planner 输出不是合法 JSON（已尝试自动修复但失败）。\n"
                "建议：让需求更具体、减少歧义，或稍后重试。\n"
                f"原始输出片段（前 400 字符）：\n{candidate[:400]}"
            ) from e

    raise ValueError(
        "Planner 输出不包含可解析的 JSON 对象。\n"
        "建议：让需求更具体、减少歧义，或稍后重试。\n"
        f"原始输出片段（前 400 字符）：\n{s[:400]}"
    )
