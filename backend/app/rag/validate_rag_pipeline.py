"""Validate the incident RAG pipeline from retrieval through answer generation."""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List

from langchain_chroma import Chroma

from app.rag.bm25_retriever import bm25_search
from app.rag.hybrid_retriever import hybrid_search
from app.rag.rag_chain import answer_question
from app.rag.ranking import reciprocal_rank_fusion
from app.rag.retriever import retrieve_documents
from app.rag.semantic_retriever import semantic_search
from app.rag.vector_store import COLLECTION_NAME, DATABASE_DIRECTORY

logger = logging.getLogger(__name__)

QUERY = (
    "Payment API is experiencing high latency, database connection errors, and "
    "increased request failures. Investigate similar historical incidents and "
    "suggest the probable root cause and corrective actions."
)
TOP_K = 5


def _safe_error(error: Exception) -> str:
    """Redact configured tokens from exceptions before displaying them."""
    message = str(error)
    for name in ("NVIDIA_API_KEY",):
        secret = os.getenv(name)
        if secret:
            message = message.replace(secret, "[REDACTED]")
    message = re.sub(r"(?i)\bnvapi-[A-Za-z0-9_-]+", "[REDACTED]", message)
    message = re.sub(
        r"(?i)(authorization:\s*bearer\s+)[^\s,;]+",
        r"\1[REDACTED]",
        message,
    )
    return message or type(error).__name__


def _valid_retrieval_results(results: Any, score_field: str) -> bool:
    return isinstance(results, list) and bool(results) and all(
        isinstance(result, dict)
        and isinstance(result.get("chunk_id"), str)
        and bool(result["chunk_id"])
        and isinstance(result.get("text"), str)
        and score_field in result
        for result in results
    )


def _answer_quality(
    answer: str,
    documents: List[Dict[str, Any]],
    sources: List[Dict[str, Any]],
) -> Dict[str, str]:
    """Provide simple keyword checks, not a model-based factuality judgment."""
    lower_answer = answer.casefold()
    evidence = " ".join(
        document.get("text", "") for document in documents
    ).casefold()
    checks = {
        "symptoms identified": any(
            term in lower_answer for term in ("latency", "connection", "failure", "error")
        ),
        "probable root cause discussed": any(
            term in lower_answer
            for term in ("cause", "because", "pool", "database", "connection")
        ),
        "corrective actions discussed": any(
            term in lower_answer
            for term in ("action", "mitigat", "fix", "recommend", "increase", "monitor")
        ),
        "evidence and hypotheses distinguished": any(
            term in lower_answer
            for term in ("historical", "evidence", "possible", "may", "hypothesis", "not proof")
        ),
        "source IDs referenced in answer": any(
            identifier
            and identifier.casefold() in lower_answer
            for source in sources
            for identifier in (source.get("chunk_id"), source.get("incident_id"))
        ),
        "answer terms supported by retrieved evidence": any(
            term in evidence
            for term in ("database", "latency", "connection", "timeout", "failure")
            if term in lower_answer
        ),
    }
    return {
        name: ("PASS" if passed else "REVIEW")
        for name, passed in checks.items()
    }


def run_validation(*, display: bool = True) -> Dict[str, Any]:
    """Run each existing pipeline stage and return its validation results."""
    report: Dict[str, Any] = {
        "collection_name": COLLECTION_NAME,
        "collection_count": None,
        "semantic_results": [],
        "bm25_results": [],
        "hybrid_results": None,
        "fused_results": [],
        "retrieved_documents": [],
        "rag_result": None,
        "checks": {},
        "errors": {},
        "answer_time_seconds": None,
    }

    def show(message: str) -> None:
        if display:
            print(message)

    show(f"RAG pipeline validation query: {QUERY}")

    try:
        store = Chroma(
            collection_name=COLLECTION_NAME,
            persist_directory=str(DATABASE_DIRECTORY),
        )
        report["collection_count"] = store._collection.count()
        report["checks"]["ChromaDB connection"] = True
        report["checks"]["Collection validation"] = report["collection_count"] > 0
    except Exception as exc:
        report["checks"]["ChromaDB connection"] = False
        report["checks"]["Collection validation"] = False
        report["errors"]["ChromaDB"] = _safe_error(exc)

    try:
        report["semantic_results"] = semantic_search(QUERY, top_k=TOP_K)
        report["checks"]["Semantic retrieval"] = _valid_retrieval_results(
            report["semantic_results"], "distance"
        )
    except Exception as exc:
        report["checks"]["Semantic retrieval"] = False
        report["errors"]["Semantic retrieval"] = _safe_error(exc)

    try:
        report["bm25_results"] = bm25_search(QUERY, top_k=TOP_K)
        report["checks"]["BM25 retrieval"] = _valid_retrieval_results(
            report["bm25_results"], "score"
        )
    except Exception as exc:
        report["checks"]["BM25 retrieval"] = False
        report["errors"]["BM25 retrieval"] = _safe_error(exc)

    try:
        report["hybrid_results"] = hybrid_search(QUERY, top_k=TOP_K)
        semantic = report["hybrid_results"]["semantic_results"]
        bm25 = report["hybrid_results"]["bm25_results"]
        report["checks"]["Hybrid search"] = bool(semantic or bm25)
        report["fused_results"] = reciprocal_rank_fusion(
            semantic,
            bm25,
            top_k=TOP_K,
        )
        all_ids = [item["chunk_id"] for item in semantic + bm25]
        fused_ids = {item["chunk_id"] for item in report["fused_results"]}
        report["checks"]["RRF ranking"] = (
            bool(report["fused_results"])
            and len(report["fused_results"]) == len(fused_ids)
            and len(fused_ids) == len(set(all_ids))
        )
    except Exception as exc:
        report["checks"]["Hybrid search"] = False
        report["checks"]["RRF ranking"] = False
        report["errors"]["Hybrid/RRF"] = _safe_error(exc)

    try:
        report["retrieved_documents"] = retrieve_documents(QUERY, top_k=TOP_K)
        required_fields = {
            "text",
            "metadata",
            "score",
            "rrf_score",
            "retrieval_method",
            "retrieval_sources",
        }
        missing_fields = [
            f"{document.get('chunk_id', '<unknown chunk>')}: {', '.join(sorted(required_fields - document.keys()))}"
            for document in report["retrieved_documents"]
            if required_fields - document.keys()
        ]
        missing_ids = [
            document
            for document in report["retrieved_documents"]
            if not document.get("chunk_id")
            and not (document.get("metadata") or {}).get("chunk_id")
        ]
        report["checks"]["Retriever integration"] = (
            bool(report["retrieved_documents"]) and not missing_fields and not missing_ids
        )
        if missing_fields or missing_ids:
            report["errors"]["Retriever integration"] = {
                "missing_fields": missing_fields,
                "missing_chunk_id": len(missing_ids),
            }
    except Exception as exc:
        report["checks"]["Retriever integration"] = False
        report["errors"]["Retriever integration"] = _safe_error(exc)

    started_at = time.perf_counter()
    try:
        report["rag_result"] = answer_question(QUERY, top_k=TOP_K)
        report["answer_time_seconds"] = time.perf_counter() - started_at
        result = report["rag_result"]
        report["checks"]["NVIDIA live API call"] = bool(
            result.get("retrieved_documents")
            and isinstance(result.get("answer"), str)
            and result["answer"].strip()
        )
        report["checks"]["Final answer generation"] = report["checks"][
            "NVIDIA live API call"
        ]
        answer = result.get("answer", "").casefold()
        report["checks"]["Source references"] = bool(result.get("sources")) and any(
            identifier and identifier.casefold() in answer
            for source in result.get("sources", [])
            for identifier in (source.get("chunk_id"), source.get("incident_id"))
        )
        report["checks"]["Retrieved documents preserved"] = (
            result.get("retrieved_documents") is not None
        )
        report["checks"]["Answer evaluation"] = _answer_quality(
            result.get("answer", ""),
            result.get("retrieved_documents", []),
            result.get("sources", []),
        )
    except Exception as exc:
        report["answer_time_seconds"] = time.perf_counter() - started_at
        report["checks"]["NVIDIA live API call"] = False
        report["checks"]["Final answer generation"] = False
        report["checks"]["Source references"] = False
        report["errors"]["RAG/NVIDIA"] = _safe_error(exc)

    if display:
        show(f"\nChromaDB collection: {COLLECTION_NAME}")
        show(f"Stored document count: {report['collection_count']}")
        show(
            f"\nSemantic retrieval: {len(report['semantic_results'])} result(s)"
        )
        for result in report["semantic_results"][:3]:
            show(f"  {result['chunk_id']} | distance={result.get('distance')}")
        show(f"\nBM25 retrieval: {len(report['bm25_results'])} result(s)")
        for result in report["bm25_results"][:3]:
            show(f"  {result['chunk_id']} | score={result.get('score')}")
        if report["hybrid_results"] is not None:
            semantic = report["hybrid_results"]["semantic_results"]
            bm25 = report["hybrid_results"]["bm25_results"]
            show("\nHybrid/RRF:")
            show(f"  Semantic: {len(semantic)}; BM25: {len(bm25)}")
            show(f"  Unique fused results: {len(report['fused_results'])}")
            for result in report["fused_results"]:
                show(
                    f"  {result['chunk_id']} | RRF={result['rrf_score']:.8f} "
                    f"| sources={result['retrieval_sources']}"
                )
        show(f"\nRetriever integration: {len(report['retrieved_documents'])} document(s)")
        if report["rag_result"] is not None:
            show(f"NVIDIA model: {os.getenv('NVIDIA_MODEL', 'not configured')}")
            show(f"Response time: {report['answer_time_seconds']:.2f} seconds")
            show(f"\nFinal answer:\n{report['rag_result'].get('answer', '')}")
            show("\nSources:")
            for source in report["rag_result"].get("sources", []):
                show(
                    f"  {source.get('chunk_id')} | "
                    f"incident={source.get('incident_id', 'not available')}"
                )

        show("\nValidation checks:")
        for name, value in report["checks"].items():
            if isinstance(value, dict):
                for check_name, status in value.items():
                    show(f"  {check_name}: {status}")
            else:
                show(f"  {name}: {'PASS' if value else 'FAIL'}")
        for stage, error in report["errors"].items():
            show(f"  {stage} error: {error}")

    return report


def main() -> int:
    report = run_validation()
    successful = all(
        value
        for name, value in report["checks"].items()
        if name != "Answer evaluation" and not isinstance(value, dict)
    )
    return 0 if successful else 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())
