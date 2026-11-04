"""Run semantic and BM25 retrieval independently for the same query."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.rag.bm25_retriever import bm25_search
from app.rag.semantic_retriever import semantic_search

logger = logging.getLogger(__name__)


def hybrid_search(query: str, top_k: int = 5) -> Dict[str, Any]:
    """Return separate semantic and BM25 rankings without combining scores."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string.")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer.")

    semantic_results = semantic_search(query, top_k=top_k)
    bm25_results = bm25_search(query, top_k=top_k)

    return {
        "query": query,
        "semantic_results": [
            {**result, "retrieval_method": "semantic"} for result in semantic_results
        ],
        "bm25_results": [
            {**result, "retrieval_method": "bm25"} for result in bm25_results
        ],
    }


def main() -> int:
    """Run and print the example hybrid search against the existing indexes."""
    query = "Payment API database connection errors and high latency"
    try:
        results = hybrid_search(query, top_k=5)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.error("Hybrid search failed: %s", exc)
        return 1

    print(f"Query: {results['query']}")
    for result_key, label, score_label in (
        ("semantic_results", "Semantic retrieval", "L2 distance (lower is closer)"),
        ("bm25_results", "BM25 retrieval", "BM25 score (higher is stronger)"),
    ):
        print(f"\n{label} - {score_label}")
        for rank, result in enumerate(results[result_key], start=1):
            score_field = "distance" if result_key == "semantic_results" else "score"
            print(
                f"Rank: {rank} | Chunk ID: {result['chunk_id']} | "
                f"{score_label.split(' (')[0]}: {result[score_field]} | "
                f"Retrieval method: {result['retrieval_method']}"
            )
            print(f"Text: {result['text']}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())
