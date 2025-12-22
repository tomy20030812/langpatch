from __future__ import annotations
from .config import Settings
from langchain_openai import ChatOpenAI

def get_llm(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
        api_key=settings.deepseek_api_key,
        temperature=0,
    )
