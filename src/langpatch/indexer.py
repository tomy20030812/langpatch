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
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

def load_hashes(index_dir: Path) -> Dict[str, str]:
    p = index_dir / HASH_FILE
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))

def save_hashes(index_dir: Path, hashes: Dict[str, str]) -> None:
    (index_dir / HASH_FILE).write_text(json.dumps(hashes, indent=2), encoding="utf-8")

def get_chroma_client(index_dir: Path) -> chromadb.Client:
    index_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(index_dir),
        settings=ChromaSettings(anonymized_telemetry=False),
    )

def get_collection(client: chromadb.Client):
    return client.get_or_create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})

def build_or_update_index(
    index_dir: Path,
    embed_model: str,
    repo_root: Path,
    files: List[Path],
    max_chars_per_file: int,
) -> None:
    client = get_chroma_client(index_dir)
    col = get_collection(client)
    model = SentenceTransformer(embed_model, device="cpu")

    hashes = load_hashes(index_dir)

    to_update: List[Tuple[Path, str]] = []
    for f in files:
        text = read_text_safely(f, max_chars=max_chars_per_file)
        h = _sha1(text)
        if hashes.get(str(f)) != h:
            to_update.append((f, text))

    if not to_update:
        return

    # remove old chunks for updated files
    # (simple approach: delete by where metadata.file_path == ...)
    for f, _ in to_update:
        try:
            col.delete(where={"file_path": str(f)})
        except Exception:
            pass

    ids: List[str] = []
    docs: List[str] = []
    metas: List[dict] = []

    for f, text in tqdm(to_update, desc="Indexing changed files"):
        if f.suffix == ".py":
            chunks = chunk_python_file(f, text)
        else:
            # non-py fallback: whole file chunk
            chunks = [CodeChunk(str(f), "__file__", 1, max(1, text.count("\n")+1), text)]

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
            })

        hashes[str(f)] = _sha1(text)

    # embed in batches
    batch_size = 16
    for i in tqdm(range(0, len(docs), batch_size), desc="Embedding"):
        batch_docs = docs[i:i+batch_size]
        embs = model.encode(batch_docs, normalize_embeddings=True).tolist()
        col.add(
            ids=ids[i:i+batch_size],
            documents=batch_docs,
            metadatas=metas[i:i+batch_size],
            embeddings=embs,
        )

    save_hashes(index_dir, hashes)
