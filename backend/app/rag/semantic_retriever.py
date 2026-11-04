"""Semantic search over the persistent historical incident Chroma collection."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from langchain_chroma import Chroma

from app.rag.embedding import EMBEDDING_MODEL, _create_embedding_model
from app.rag.vector_store import COLLECTION_NAME, DATABASE_DIRECTORY

logger = logging.getLogger(__name__)


def _create_query_embedder() -> Any:
    """Create the same normalized embedding model used for stored chunks."""
    return _create_embedding_model(batch_size=1)


def semantic_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Return matching chunks ordered by ascending Chroma L2 distance."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string.")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer.")

    store = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(DATABASE_DIRECTORY),
    )
    query_vector = _create_query_embedder().embed_query(query.strip())
    matches = store._collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    ids = matches["ids"][0]
    documents = matches["documents"][0]
    metadatas = matches["metadatas"][0]
    distances = matches["distances"][0]
    results = [
        {
            "chunk_id": chunk_id,
            "text": text,
            "metadata": metadata or {},
            "distance": float(distance),
        }
        for chunk_id, text, metadata, distance in zip(
            ids, documents, metadatas, distances
        )
    ]
    return sorted(results, key=lambda result: result["distance"])


def main() -> int:
    """Run and print a small example semantic search."""
    query = "Payment API is experiencing high latency and database connection errors"
    try:
        results = semantic_search(query, top_k=5)
    except (OSError, ValueError) as exc:
        logger.error("Semantic search failed: %s", exc)
        return 1

    print(f"Query: {query}")
    print("Score field: distance (lower is more similar)")
    for result in results:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())
