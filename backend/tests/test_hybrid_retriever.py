import pytest

from app.rag import hybrid_retriever
from app.rag.hybrid_retriever import hybrid_search


@pytest.fixture
def retrieval_results(monkeypatch):
    calls = []
    semantic = [
        {
            "chunk_id": "shared-chunk",
            "text": "Semantic match",
            "metadata": {"source": "semantic-index"},
            "distance": 0.14,
        },
        {
            "chunk_id": "semantic-only",
            "text": "Another semantic match",
            "metadata": {"source": "semantic-index"},
            "distance": 0.35,
        },
    ]
    bm25 = [
        {
            "chunk_id": "shared-chunk",
            "text": "Keyword match",
            "metadata": {"source": "bm25-index"},
            "score": 8.42,
        },
        {
            "chunk_id": "bm25-only",
            "text": "Another keyword match",
            "metadata": {"source": "bm25-index"},
            "score": 4.12,
        },
    ]

    def fake_semantic_search(query, top_k=5):
        calls.append(("semantic", query, top_k))
        return semantic[:top_k]

    def fake_bm25_search(query, top_k=5):
        calls.append(("bm25", query, top_k))
        return bm25[:top_k]

    monkeypatch.setattr(hybrid_retriever, "semantic_search", fake_semantic_search)
    monkeypatch.setattr(hybrid_retriever, "bm25_search", fake_bm25_search)
    return calls, semantic, bm25


def test_both_retrievers_receive_same_query_and_requested_top_k(retrieval_results):
    calls, _, _ = retrieval_results

    hybrid_search("  payment API latency  ", top_k=2)

    assert calls == [
        ("semantic", "  payment API latency  ", 2),
        ("bm25", "  payment API latency  ", 2),
    ]


def test_returns_both_result_sets_with_retrieval_method_labels(retrieval_results):
    _, _, _ = retrieval_results

    results = hybrid_search("payment API", top_k=2)

    assert results["query"] == "payment API"
    assert [item["retrieval_method"] for item in results["semantic_results"]] == [
        "semantic",
        "semantic",
    ]
    assert [item["retrieval_method"] for item in results["bm25_results"]] == [
        "bm25",
        "bm25",
    ]


def test_preserves_scores_metadata_and_independent_orderings(retrieval_results):
    _, semantic, bm25 = retrieval_results

    results = hybrid_search("database error", top_k=2)

    for actual, expected in zip(results["semantic_results"], semantic):
        assert {key: value for key, value in actual.items() if key != "retrieval_method"} == expected
    for actual, expected in zip(results["bm25_results"], bm25):
        assert {key: value for key, value in actual.items() if key != "retrieval_method"} == expected


def test_duplicate_chunk_ids_are_retained_in_both_result_sets(retrieval_results):
    results = hybrid_search("payment API", top_k=2)

    assert results["semantic_results"][0]["chunk_id"] == "shared-chunk"
    assert results["bm25_results"][0]["chunk_id"] == "shared-chunk"
    assert results["semantic_results"][0]["retrieval_method"] == "semantic"
    assert results["bm25_results"][0]["retrieval_method"] == "bm25"


@pytest.mark.parametrize("query", ["", "  ", None, 123])
def test_empty_or_invalid_query_raises(query, retrieval_results):
    with pytest.raises(ValueError, match="non-empty"):
        hybrid_search(query)


@pytest.mark.parametrize("top_k", [0, -1, 1.5, True])
def test_invalid_top_k_raises(top_k, retrieval_results):
    with pytest.raises(ValueError, match="positive integer"):
        hybrid_search("valid query", top_k=top_k)


def test_semantic_failure_propagates_without_fabricated_results(monkeypatch):
    def fail_semantic(query, top_k=5):
        raise RuntimeError("semantic retrieval unavailable")

    monkeypatch.setattr(hybrid_retriever, "semantic_search", fail_semantic)
    monkeypatch.setattr(
        hybrid_retriever,
        "bm25_search",
        lambda query, top_k=5: pytest.fail("BM25 should not run after failure"),
    )

    with pytest.raises(RuntimeError, match="semantic retrieval unavailable"):
        hybrid_search("database error")


def test_bm25_failure_propagates_without_partial_success(monkeypatch):
    monkeypatch.setattr(hybrid_retriever, "semantic_search", lambda query, top_k=5: [])

    def fail_bm25(query, top_k=5):
        raise RuntimeError("BM25 retrieval unavailable")

    monkeypatch.setattr(hybrid_retriever, "bm25_search", fail_bm25)

    with pytest.raises(RuntimeError, match="BM25 retrieval unavailable"):
        hybrid_search("database error")
