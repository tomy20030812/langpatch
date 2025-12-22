from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from sentence_transformers import SentenceTransformer

from .indexer import get_chroma_client, get_collection

def retrieve_top_chunks(
    index_dir: Path,
    embed_model: str,
    query: str,
    top_k: int,
) -> List[Dict[str, Any]]:
    client = get_chroma_client(index_dir)
    col = get_collection(client)
    model = SentenceTransformer(embed_model, device="cpu")

    q_emb = model.encode([query], normalize_embeddings=True).tolist()[0]
    res = col.query(query_embeddings=[q_emb], n_results=top_k, include=["documents", "metadatas", "distances"])

    out: List[Dict[str, Any]] = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({
            "document": doc,
            "meta": meta,
            "distance": dist,
        })
    return out
