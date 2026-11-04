"""Keyword search over the saved historical incident chunks."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CHUNKS_PATH = BACKEND_ROOT / "data" / "processed" / "cleaned_documents_chunks.jsonl"

# Keep identifiers such as payment-api, OOMKilled, and error code numbers intact.
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+(?:[_-][A-Za-z0-9]+)*")


def _tokenize(text: str) -> List[str]:
    """Split text into case-insensitive words and technical identifiers."""
    return [token.casefold() for token in TOKEN_PATTERN.findall(text)]


def read_chunks(input_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read chunk records from the processed UTF-8 JSONL file."""
    input_path = input_path or CHUNKS_PATH
    chunks: List[Dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"Invalid chunk record on line {line_number}.")
            for field in ("chunk_id", "text", "metadata"):
                if field not in record:
                    raise ValueError(
                        f"Chunk record on line {line_number} is missing {field!r}."
                    )
            if not isinstance(record["chunk_id"], str) or not isinstance(
                record["text"], str
            ):
                raise ValueError(
                    f"Chunk ID and text must be strings on line {line_number}."
                )
            if not isinstance(record["metadata"], dict):
                raise ValueError(f"Chunk metadata must be an object on line {line_number}.")
            chunks.append(record)
    return chunks


def chunks_to_documents(chunks: Sequence[Dict[str, Any]]) -> List[Document]:
    """Convert saved chunks to LangChain Documents without changing their text."""
    documents = []
    for chunk in chunks:
        metadata = dict(chunk["metadata"])
        metadata["chunk_id"] = chunk["chunk_id"]
        documents.append(Document(page_content=chunk["text"], metadata=metadata))
    return documents


def create_bm25_retriever(documents: Sequence[Document]) -> BM25Retriever:
    """Index Documents with LangChain's rank_bm25-backed retriever."""
    if not documents:
        raise ValueError("At least one document is required to initialize BM25.")
    return BM25Retriever.from_documents(
        list(documents),
        preprocess_func=_tokenize,
    )


def bm25_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Return chunk records ranked by their raw BM25 relevance scores."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string.")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer.")

    documents = chunks_to_documents(read_chunks())
    retriever = create_bm25_retriever(documents)
    tokens = retriever.preprocess_func(query.strip())
    scores = retriever.vectorizer.get_scores(tokens)

    ranked = sorted(
        zip(retriever.docs, scores),
        key=lambda item: float(item[1]),
        reverse=True,
    )[:top_k]
    return [
        {
            "chunk_id": document.metadata["chunk_id"],
            "text": document.page_content,
            "metadata": document.metadata,
            "score": float(score),
        }
        for document, score in ranked
    ]


def main() -> int:
    """Run and print an example keyword search against the saved chunk file."""
    query = "Payment API database connection errors and high latency"
    try:
        results = bm25_search(query, top_k=5)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.error("BM25 search failed: %s", exc)
        return 1

    print(f"Query: {query}")
    print("Score field: BM25 score (higher is a stronger keyword match)")
    for rank, result in enumerate(results, start=1):
        print(f"\nRank: {rank}")
        print(f"Chunk ID: {result['chunk_id']}")
        print(f"BM25 score: {result['score']:.4f}")
        print(f"Text: {result['text']}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())
