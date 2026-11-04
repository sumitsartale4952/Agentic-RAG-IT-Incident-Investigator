import pytest

from app.rag import retriever
from app.rag.retriever import retrieve_documents


@pytest.fixture
def ranked_results(monkeypatch):
    results = [
        {
            "chunk_id": "chunk-a",
            "text": "Original incident content.",
            "metadata": {"incident_id": "INC-1", "service": "payment-api"},
            "rrf_score": 0.03252,
            "retrieval_sources": ["semantic", "bm25"],
            "semantic_rank": 1,
            "bm25_rank": 2,
            "distance": 0.14,
            "score": 8.42,
        },
        {
            "chunk_id": "chunk-b",
            "text": "Second incident content.",
            "metadata": {"incident_id": "INC-2"},
            "rrf_score": 0.01612,
            "retrieval_sources": ["bm25"],
            "semantic_rank": None,
            "bm25_rank": 3,
            "score": 3.75,
        },
    ]
    calls = []

    def fake_ranked_hybrid_search(query, top_k=5):
        calls.append((query, top_k))
        return results

    monkeypatch.setattr(retriever, "ranked_hybrid_search", fake_ranked_hybrid_search)
    return calls, results


def test_common_retriever_calls_ranking_with_query_and_top_k(ranked_results):
    calls, _ = ranked_results

    retrieve_documents("database connection", top_k=2)

    assert calls == [("database connection", 2)]


def test_returns_standard_document_structure_with_ranks_and_sources(ranked_results):
    documents = retrieve_documents("database connection")

    assert documents[0] == {
        "chunk_id": "chunk-a",
        "text": "Original incident content.",
        "metadata": {"incident_id": "INC-1", "service": "payment-api"},
        "score": 0.03252,
        "rrf_score": 0.03252,
        "retrieval_method": "hybrid_rrf",
        "retrieval_sources": ["semantic", "bm25"],
        "semantic_rank": 1,
        "bm25_rank": 2,
        "distance": 0.14,
        "bm25_score": 8.42,
    }


def test_preserves_text_and_metadata(ranked_results):
    document = retrieve_documents("payment API")[0]

    assert document["text"] == "Original incident content."
    assert document["metadata"] == {
        "incident_id": "INC-1",
        "service": "payment-api",
    }


def test_maps_rrf_score_and_labels_hybrid_method(ranked_results):
    document = retrieve_documents("payment API")[0]

    assert document["score"] == 0.03252
    assert document["retrieval_method"] == "hybrid_rrf"


def test_preserves_method_ranks_and_retrieval_sources(ranked_results):
    documents = retrieve_documents("payment API")

    assert documents[0]["semantic_rank"] == 1
    assert documents[0]["bm25_rank"] == 2
    assert documents[0]["retrieval_sources"] == ["semantic", "bm25"]
    assert documents[1]["semantic_rank"] is None
    assert documents[1]["bm25_rank"] == 3


def test_preserves_original_distance_and_bm25_score(ranked_results):
    document = retrieve_documents("payment API")[0]

    assert document["distance"] == 0.14
    assert document["bm25_score"] == 8.42


def test_respects_top_k_even_if_ranking_returns_more_results(monkeypatch):
    monkeypatch.setattr(
        retriever,
        "ranked_hybrid_search",
        lambda query, top_k=5: [
            {
                "chunk_id": f"chunk-{index}",
                "text": f"text {index}",
                "metadata": {},
                "rrf_score": 0.01,
                "retrieval_sources": ["semantic"],
                "semantic_rank": index + 1,
                "bm25_rank": None,
            }
            for index in range(4)
        ],
    )

    assert len(retrieve_documents("query", top_k=2)) == 2


def test_empty_ranking_results_return_empty_list(monkeypatch):
    monkeypatch.setattr(retriever, "ranked_hybrid_search", lambda query, top_k=5: [])

    assert retrieve_documents("query") == []


@pytest.mark.parametrize("query", ["", "  ", None, 123])
def test_empty_or_invalid_query_raises(query, ranked_results):
    with pytest.raises(ValueError, match="non-empty"):
        retrieve_documents(query)


@pytest.mark.parametrize("top_k", [0, -1, 1.5, True])
def test_invalid_top_k_raises(top_k, ranked_results):
    with pytest.raises(ValueError, match="positive integer"):
        retrieve_documents("valid query", top_k=top_k)
