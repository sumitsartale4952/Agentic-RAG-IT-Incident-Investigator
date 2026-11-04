import json

import pytest
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from app.rag.bm25_retriever import (
    CHUNKS_PATH,
    bm25_search,
    chunks_to_documents,
    create_bm25_retriever,
    read_chunks,
)


@pytest.fixture
def incident_chunks():
    return [
        {
            "chunk_id": "payment-1",
            "text": "payment-api returned HTTP 503 after ConnectionTimeout; database connection caused high latency.",
            "metadata": {"incident_id": "INC-1", "service": "payment-api"},
        },
        {
            "chunk_id": "payment-2",
            "text": "payment-api database connection failures caused high latency and request retries.",
            "metadata": {"incident_id": "INC-2", "service": "payment-api"},
        },
        {
            "chunk_id": "worker-1",
            "text": "worker process terminated because of OOMKilled during a memory spike.",
            "metadata": {"incident_id": "INC-3", "service": "worker"},
        },
        {
            "chunk_id": "cache-1",
            "text": "Cache cluster failover completed after a network partition.",
            "metadata": {"incident_id": "INC-4", "service": "cache"},
        },
    ]


def _write_chunks(path, chunks):
    path.write_text(
        "".join(json.dumps(chunk) + "\n" for chunk in chunks),
        encoding="utf-8",
    )


def test_read_chunks_loads_existing_processed_jsonl():
    chunks = read_chunks(CHUNKS_PATH)

    assert chunks
    assert all({"chunk_id", "text", "metadata"} <= chunk.keys() for chunk in chunks)


def test_read_chunks_loads_temporary_jsonl(tmp_path, incident_chunks):
    input_path = tmp_path / "chunks.jsonl"
    _write_chunks(input_path, incident_chunks)

    assert read_chunks(input_path) == incident_chunks


def test_chunks_convert_to_documents_without_losing_metadata(incident_chunks):
    documents = chunks_to_documents(incident_chunks)

    assert len(documents) == len(incident_chunks)
    assert isinstance(documents[0], Document)
    assert documents[0].page_content == incident_chunks[0]["text"]
    assert documents[0].metadata == {
        **incident_chunks[0]["metadata"],
        "chunk_id": incident_chunks[0]["chunk_id"],
    }


def test_bm25_retriever_initializes_with_documents(incident_chunks):
    retriever = create_bm25_retriever(chunks_to_documents(incident_chunks))

    assert isinstance(retriever, BM25Retriever)
    assert retriever.vectorizer is not None
    assert len(retriever.docs) == len(incident_chunks)


def test_bm25_search_returns_requested_results_and_consistent_structure(
    monkeypatch, tmp_path, incident_chunks
):
    input_path = tmp_path / "chunks.jsonl"
    _write_chunks(input_path, incident_chunks)
    monkeypatch.setattr("app.rag.bm25_retriever.CHUNKS_PATH", input_path)

    results = bm25_search("database connection", top_k=2)

    assert len(results) == 2
    assert all(
        set(result) == {"chunk_id", "text", "metadata", "score"} for result in results
    )
    assert all(isinstance(result["score"], float) for result in results)
    assert all(isinstance(result["metadata"], dict) for result in results)


def test_results_are_sorted_by_descending_bm25_score(
    monkeypatch, tmp_path, incident_chunks
):
    input_path = tmp_path / "chunks.jsonl"
    _write_chunks(input_path, incident_chunks)
    monkeypatch.setattr("app.rag.bm25_retriever.CHUNKS_PATH", input_path)

    results = bm25_search("database connection", top_k=4)

    assert [result["score"] for result in results] == sorted(
        (result["score"] for result in results),
        reverse=True,
    )


@pytest.mark.parametrize(
    ("query", "expected_chunk_id"),
    [
        ("payment-api", "payment-1"),
        ("HTTP 503", "payment-1"),
        ("ConnectionTimeout", "payment-1"),
        ("OOMKilled", "worker-1"),
        ("database connection failures causing high latency", "payment-2"),
    ],
)
def test_keyword_queries_retrieve_matching_incident(
    monkeypatch, tmp_path, incident_chunks, query, expected_chunk_id
):
    input_path = tmp_path / "chunks.jsonl"
    _write_chunks(input_path, incident_chunks)
    monkeypatch.setattr("app.rag.bm25_retriever.CHUNKS_PATH", input_path)

    results = bm25_search(query, top_k=1)

    assert results[0]["chunk_id"] == expected_chunk_id


@pytest.mark.parametrize("query", ["", "  ", None, 123])
def test_empty_or_invalid_query_raises(query):
    with pytest.raises(ValueError, match="non-empty"):
        bm25_search(query)


@pytest.mark.parametrize("top_k", [0, -1, 1.5, True])
def test_invalid_top_k_raises(top_k):
    with pytest.raises(ValueError, match="positive integer"):
        bm25_search("valid query", top_k=top_k)


def test_retriever_requires_at_least_one_document():
    with pytest.raises(ValueError, match="At least one document"):
        create_bm25_retriever([])
