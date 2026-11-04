"""Fuse semantic and BM25 rankings using Reciprocal Rank Fusion."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Sequence

from app.rag.hybrid_retriever import hybrid_search

logger = logging.getLogger(__name__)

RRF_K = 60


def _validate_positive_integer(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")


def reciprocal_rank_fusion(
    semantic_results: Sequence[Dict[str, Any]],
    bm25_results: Sequence[Dict[str, Any]],
    top_k: int = 5,
    k: int = RRF_K,
) -> List[Dict[str, Any]]:
    """Combine rankings by chunk ID without comparing their raw scores."""
    _validate_positive_integer(top_k, "top_k")
    _validate_positive_integer(k, "k")

    fused: Dict[str, Dict[str, Any]] = {}
    for source, results, rank_field in (
        ("semantic", semantic_results, "semantic_rank"),
        ("bm25", bm25_results, "bm25_rank"),
    ):
        for rank, result in enumerate(results, start=1):
            chunk_id = result.get("chunk_id")
            if not isinstance(chunk_id, str) or not chunk_id:
                raise ValueError("Each retrieval result must have a non-empty chunk_id.")

            if chunk_id not in fused:
                fused_result = {
                    key: value
                    for key, value in result.items()
                    if key != "retrieval_method"
                }
                fused_result.update(
                    {
                        "rrf_score": 0.0,
                        "retrieval_sources": [],
                        "semantic_rank": None,
                        "bm25_rank": None,
                    }
                )
                fused[chunk_id] = fused_result

            fused_result = fused[chunk_id]
            if source not in fused_result["retrieval_sources"]:
                fused_result["retrieval_sources"].append(source)
            fused_result[rank_field] = rank
            fused_result["rrf_score"] += 1 / (k + rank)

            # Keep each method's original score field when a chunk appears in both lists.
            if source == "bm25" and "score" in result:
                fused_result["score"] = result["score"]
            elif source == "semantic" and "distance" in result:
                fused_result["distance"] = result["distance"]

    ranked_results = sorted(
        fused.values(),
        key=lambda result: result["rrf_score"],
        reverse=True,
    )
    return ranked_results[:top_k]


def ranked_hybrid_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Run hybrid retrieval and return its RRF-ranked results."""
    hybrid_results = hybrid_search(query, top_k=top_k)
    return reciprocal_rank_fusion(
        hybrid_results["semantic_results"],
        hybrid_results["bm25_results"],
        top_k=top_k,
    )


def main() -> int:
    """Run and print an example fused search using the existing retrievers."""
    query = "Payment API database connection errors and high latency"
    try:
        results = ranked_hybrid_search(query, top_k=5)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.error("Ranked hybrid search failed: %s", exc)
        return 1

    print(f"Query: {query}")
    print(f"RRF constant: {RRF_K}")
    for rank, result in enumerate(results, start=1):
        print(
            f"\nFinal rank: {rank} | Chunk ID: {result['chunk_id']} | "
            f"RRF score: {result['rrf_score']:.8f}"
        )
        print(f"Semantic rank: {result['semantic_rank']}")
        print(f"BM25 rank: {result['bm25_rank']}")
        print(f"Retrieval sources: {result['retrieval_sources']}")
        print(f"Text: {result['text']}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())
