from __future__ import annotations
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from .chunker_py import chunk_python_file, CodeChunk
from .fs_utils import read_text_safely

HASH_FILE = "file_hashes.json"
COLLECTION_NAME = "code_chunks"

def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()

def get_chroma_client(index_dir: Path) -> chromadb.Client:
    index_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(index_dir),
        settings=ChromaSettings(anonymized_telemetry=False),
    )

def get_collection(client: chromadb.Client) -> chromadb.Collection:
    try:
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        return client.create_collection(COLLECTION_NAME)

def load_hashes(index_dir: Path) -> Dict[str, str]:
    p = index_dir / HASH_FILE
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_hashes(index_dir: Path, hashes: Dict[str, str]) -> None:
    p = index_dir / HASH_FILE
    p.write_text(json.dumps(hashes, indent=2, ensure_ascii=False), encoding="utf-8")

def build_or_update_index(
    repo_root: Path,
    index_dir: Path,
    files: List[Path],
    embed_model: str,
    batch_size: int = 32,
    max_chars_per_file: int = 80_000,
) -> None:
    client = get_chroma_client(index_dir)
    col = get_collection(client)

    model = SentenceTransformer(embed_model, device="cpu")
    hashes = load_hashes(index_dir)

    ids: List[str] = []
    docs: List[str] = []
    metas: List[dict] = []

    for f in tqdm(files, desc="Indexing"):
        text = read_text_safely(f, max_chars=max_chars_per_file)
        if not text:
            continue

        rel = str(f.relative_to(repo_root))
        h = _sha1(text)
        if hashes.get(str(f)) == h:
            continue

        chunks: List[CodeChunk] = chunk_python_file(str(f), text)

        # Delete old chunks for this file (by prefix match)
        # (Chroma doesn't support prefix delete directly; we just overwrite via new ids)
        # Note: If duplicates remain, it doesn't break retrieval but wastes space.

        for c in chunks:
            cid = f"{c.file_path}:{c.symbol}:{c.start_line}-{c.end_line}"
            ids.append(cid)
            docs.append(c.text)
            metas.append({
                "file_path": c.file_path,
                "symbol": c.symbol,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "rel_path": str(Path(c.file_path).relative_to(repo_root)),
                "snippet": c.text,
            })

        hashes[str(f)] = _sha1(text)

    if not ids:
        # nothing to add
        save_hashes(index_dir, hashes)
        return

    # upsert by adding; duplicates may occur if ids collide, but ids are stable per file+symbol+range
    # chroma will error if duplicate ids exist; so delete then add if needed.
    # here we attempt delete existing ids first.
    try:
        col.delete(ids=ids)
    except Exception:
        pass

    for i in range(0, len(ids), batch_size):
        batch_docs = docs[i:i+batch_size]
        embs = model.encode(batch_docs, normalize_embeddings=True).tolist()
        col.add(
            ids=ids[i:i+batch_size],
            documents=batch_docs,
            metadatas=metas[i:i+batch_size],
            embeddings=embs,
        )

    save_hashes(index_dir, hashes)
