from __future__ import annotations
import re

def looks_like_unified_diff(text: str) -> bool:
    return ("--- " in text and "+++ " in text and "@@" in text)

def sanitize_diff(text: str) -> str:
    # remove markdown fences if model accidentally adds them
    text = re.sub(r"^```.*?\n", "", text.strip(), flags=re.DOTALL)
    text = re.sub(r"\n```$", "\n", text, flags=re.DOTALL)
    return text.strip() + "\n"
