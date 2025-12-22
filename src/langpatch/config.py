from __future__ import annotations
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-coder")

    embed_model: str = os.getenv("EMBED_MODEL", "BAAI/bge-base-en-v1.5")
    index_dir: str = os.getenv("INDEX_DIR", ".langpatch_index")

    # retrieval
    top_k: int = 12

    # safety
    max_files_for_llm: int = 8
    max_chars_per_file: int = 120_000  # avoid huge files
    max_total_context_chars: int = 500_000

def get_settings() -> Settings:
    s = Settings()
    if not s.deepseek_api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in environment/.env")
    return s
