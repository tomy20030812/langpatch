from __future__ import annotations
import json
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

    # strict JSON parse with a tiny repair attempt
    try:
        return json.loads(resp)
    except json.JSONDecodeError:
        # attempt to extract first/last braces
        start = resp.find("{")
        end = resp.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(resp[start:end+1])
        raise
