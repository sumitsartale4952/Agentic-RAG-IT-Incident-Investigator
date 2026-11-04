import pytest

from app.rag import ranking
from app.rag.ranking import RRF_K, ranked_hybrid_search, reciprocal_rank_fusion


def _result(chunk_id, text=None, metadata=None, **scores):
    return {
        "chunk_id": chunk_id,
        "text": text or f"Text for {chunk_id}",
        "metadata": metadata or {"incident_id": chunk_id},
        **scores,
    }


def test_rrf_score_uses_rank_and_configured_constant():
    semantic = [_result("chunk-a", distance=0.25)]

    fused = reciprocal_rank_fusion(semantic, [], top_k=1)

    assert fused[0]["rrf_score"] == pytest.approx(1 / (RRF_K + 1))
    assert fused[0]["semantic_rank"] == 1
    assert fused[0]["bm25_rank"] is None


def test_ranks_are_one_based():
    semantic = [_result("chunk-a"), _result("chunk-b"), _result("chunk-c")]

    fused = reciprocal_rank_fusion(semantic, [], top_k=3)

    assert [item["semantic_rank"] for item in fused] == [1, 2, 3]
    assert [item["rrf_score"] for item in fused] == pytest.approx(
        [1 / 61, 1 / 62, 1 / 63]
    )


def test_duplicate_ids_merge_and_sum_both_method_contributions():
    semantic = [_result("chunk-a"), _result("chunk-b")]
    bm25 = [_result("chunk-b"), _result("chunk-a")]

    fused = reciprocal_rank_fusion(semantic, bm25, top_k=2)
    by_id = {item["chunk_id"]: item for item in fused}

    assert len(fused) == 2
    assert by_id["chunk-a"]["rrf_score"] == pytest.approx(1 / 61 + 1 / 62)
    assert by_id["chunk-b"]["rrf_score"] == pytest.approx(1 / 62 + 1 / 61)
    assert by_id["chunk-a"]["retrieval_sources"] == ["semantic", "bm25"]
    assert by_id["chunk-a"]["semantic_rank"] == 1
    assert by_id["chunk-a"]["bm25_rank"] == 2


def test_single_list_results_get_only_its_contribution_and_missing_rank():
    semantic = [_result("semantic-only", distance=0.4)]
    bm25 = [_result("bm25-only", score=3.25)]

    fused = reciprocal_rank_fusion(semantic, bm25, top_k=2)
    by_id = {item["chunk_id"]: item for item in fused}

    assert by_id["semantic-only"]["rrf_score"] == pytest.approx(1 / 61)
    assert by_id["semantic-only"]["semantic_rank"] == 1
    assert by_id["semantic-only"]["bm25_rank"] is None
    assert by_id["semantic-only"]["retrieval_sources"] == ["semantic"]
    assert by_id["bm25-only"]["rrf_score"] == pytest.approx(1 / 61)
    assert by_id["bm25-only"]["semantic_rank"] is None
    assert by_id["bm25-only"]["bm25_rank"] == 1
    assert by_id["bm25-only"]["retrieval_sources"] == ["bm25"]


def test_results_are_sorted_by_descending_rrf_score():
    semantic = [_result("chunk-a"), _result("chunk-b")]
    bm25 = [_result("chunk-b"), _result("chunk-a")]

    fused = reciprocal_rank_fusion(semantic, bm25)

    assert [item["rrf_score"] for item in fused] == sorted(
        (item["rrf_score"] for item in fused),
        reverse=True,
    )


def test_text_and_metadata_are_preserved():
    semantic = [
        _result(
            "chunk-a",
            text="Original incident text",
            metadata={"service": "payment-api", "incident_id": "INC-1"},
            distance=0.12,
        )
    ]

    fused = reciprocal_rank_fusion(semantic, [])

    assert fused[0]["text"] == "Original incident text"
    assert fused[0]["metadata"] == {
        "service": "payment-api",
        "incident_id": "INC-1",
    }


def test_original_scores_are_preserved_for_shared_chunk():
    semantic = [_result("chunk-a", distance=0.12)]
    bm25 = [_result("chunk-a", score=8.42)]

    fused = reciprocal_rank_fusion(semantic, bm25)

    assert fused[0]["distance"] == 0.12
    assert fused[0]["score"] == 8.42
    assert fused[0]["rrf_score"] == pytest.approx(2 / 61)


def test_top_k_limits_fused_results():
    semantic = [_result("chunk-a"), _result("chunk-b"), _result("chunk-c")]

    assert len(reciprocal_rank_fusion(semantic, [], top_k=2)) == 2


@pytest.mark.parametrize(
    ("semantic", "bm25"),
    [([], []), ([], [_result("chunk-a")]), ([_result("chunk-a")], [])],
)
def test_empty_retrieval_list_is_supported(semantic, bm25):
    fused = reciprocal_rank_fusion(semantic, bm25)

    assert len(fused) == len(semantic) + len(bm25)


def test_ranked_hybrid_search_calls_hybrid_and_fuses_results(monkeypatch):
    hybrid_output = {
        "query": "database error",
        "semantic_results": [_result("semantic-hit", distance=0.3)],
        "bm25_results": [_result("keyword-hit", score=2.1)],
    }
    calls = []

    def fake_hybrid_search(query, top_k=5):
        calls.append((query, top_k))
        return hybrid_output

    monkeypatch.setattr(ranking, "hybrid_search", fake_hybrid_search)

    results = ranked_hybrid_search("database error", top_k=2)

    assert calls == [("database error", 2)]
    assert {item["chunk_id"] for item in results} == {"semantic-hit", "keyword-hit"}


@pytest.mark.parametrize("top_k", [0, -1, True, 1.5])
def test_invalid_top_k_raises(top_k):
    with pytest.raises(ValueError, match="top_k must be a positive integer"):
        reciprocal_rank_fusion([], [], top_k=top_k)


@pytest.mark.parametrize("k", [0, -1, True, 1.5])
def test_invalid_rrf_constant_raises(k):
    with pytest.raises(ValueError, match="k must be a positive integer"):
        reciprocal_rank_fusion([], [], k=k)
