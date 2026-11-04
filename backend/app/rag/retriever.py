"""Common interface for retrieving ranked incident documents."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.rag.ranking import ranked_hybrid_search

logger = logging.getLogger(__name__)


def retrieve_documents(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Return RRF-ranked documents in a consistent downstream-friendly format."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string.")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer.")

    ranked_results = ranked_hybrid_search(query, top_k=top_k)
    documents = []
    for result in ranked_results[:top_k]:
        document = dict(result)
        rrf_score = document["rrf_score"]
        bm25_score = document.pop("score", None)
        document.update(
            {
                "score": rrf_score,
                "retrieval_method": "hybrid_rrf",
            }
        )
        if bm25_score is not None and "bm25_score" not in document:
            document["bm25_score"] = bm25_score
        documents.append(document)
    return documents


def main() -> int:
    """Run and print an example query through the common retriever."""
    query = "Payment API database connection errors and high latency"
    try:
        documents = retrieve_documents(query, top_k=5)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.error("Document retrieval failed: %s", exc)
        return 1

    print(f"Query: {query}")
    for rank, document in enumerate(documents, start=1):
        print(
            f"\nFinal rank: {rank} | Chunk ID: {document['chunk_id']} | "
            f"RRF score: {document['score']:.8f}"
        )
        print(f"Retrieval method: {document['retrieval_method']}")
        print(f"Semantic rank: {document['semantic_rank']}")
        print(f"BM25 rank: {document['bm25_rank']}")
        print(f"Text: {document['text']}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())