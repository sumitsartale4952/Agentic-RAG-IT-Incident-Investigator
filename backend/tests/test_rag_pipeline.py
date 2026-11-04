from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from app.rag import rag_chain
from app.rag import validate_rag_pipeline as pipeline


def _documents():
    return [
        {
            "chunk_id": "chunk-shared",
            "text": "Database connection errors caused high latency.",
            "metadata": {"incident_id": "INC-1", "service": "payment-api"},
            "distance": 0.1,
            "score": 5.2,
            "rrf_score": 0.03,
            "retrieval_method": "hybrid_rrf",
            "retrieval_sources": ["semantic", "bm25"],
            "semantic_rank": 1,
            "bm25_rank": 1,
        },
        {
            "chunk_id": "chunk-semantic",
            "text": "Database pool exhaustion increased request latency.",
            "metadata": {"incident_id": "INC-2"},
            "score": 0.016,
            "distance": 0.2,
            "rrf_score": 0.016,
            "retrieval_method": "hybrid_rrf",
            "retrieval_sources": ["semantic"],
            "semantic_rank": 2,
            "bm25_rank": None,
        },
    ]


def _configure_success(monkeypatch, *, empty=False):
    semantic = [] if empty else [
        {
            key: value
            for key, value in _documents()[0].items()
            if key in {"chunk_id", "text", "metadata", "distance"}
        }
    ]
    bm25 = [] if empty else [
        {
            key: value
            for key, value in _documents()[0].items()
            if key in {"chunk_id", "text", "metadata", "score"}
        }
    ]
    hybrid = {
        "semantic_results": semantic,
        "bm25_results": bm25,
    }
    answer = {
        "query": pipeline.QUERY,
        "answer": (
            "Historical evidence indicates database connection pool exhaustion "
            "may cause latency. Consider monitoring and mitigating pool exhaustion. "
            "This is not proof of the current root cause. Sources: chunk-shared, INC-1."
        ),
        "sources": [] if empty else [{"chunk_id": "chunk-shared", "incident_id": "INC-1"}],
        "retrieved_documents": [] if empty else _documents(),
    }

    class FakeCollection:
        def count(self):
            return 25

    class FakeChroma:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self._collection = FakeCollection()

    monkeypatch.setattr(pipeline, "Chroma", FakeChroma)
    monkeypatch.setattr(pipeline, "semantic_search", lambda query, top_k=5: semantic)
    monkeypatch.setattr(pipeline, "bm25_search", lambda query, top_k=5: bm25)
    monkeypatch.setattr(pipeline, "hybrid_search", lambda query, top_k=5: hybrid)
    monkeypatch.setattr(
        pipeline,
        "retrieve_documents",
        lambda query, top_k=5: [] if empty else _documents(),
    )
    monkeypatch.setattr(pipeline, "answer_question", lambda query, top_k=5: answer)
    return answer


def test_chromadb_collection_count_and_name(monkeypatch):
    _configure_success(monkeypatch)

    report = pipeline.run_validation(display=False)

    assert report["collection_count"] == 25
    assert report["collection_name"] == "historical_incidents"
    assert report["checks"]["ChromaDB connection"] is True
    assert report["checks"]["Collection validation"] is True


def test_semantic_and_bm25_retrieval_validation(monkeypatch):
    _configure_success(monkeypatch)

    report = pipeline.run_validation(display=False)

    assert report["checks"]["Semantic retrieval"] is True
    assert report["checks"]["BM25 retrieval"] is True


def test_hybrid_search_and_rrf_merge_duplicate_ids(monkeypatch):
    _configure_success(monkeypatch)

    report = pipeline.run_validation(display=False)

    assert report["checks"]["Hybrid search"] is True
    assert report["checks"]["RRF ranking"] is True
    assert len(report["fused_results"]) == 1
    assert report["fused_results"][0]["chunk_id"] == "chunk-shared"
    assert report["fused_results"][0]["retrieval_sources"] == ["semantic", "bm25"]


def test_retriever_and_rag_answer_keep_expected_fields_and_sources(monkeypatch):
    answer = _configure_success(monkeypatch)

    report = pipeline.run_validation(display=False)

    assert report["checks"]["Retriever integration"] is True
    assert report["checks"]["NVIDIA live API call"] is True
    assert report["checks"]["Final answer generation"] is True
    assert report["checks"]["Source references"] is True
    assert report["rag_result"] == answer


def test_rag_chain_receives_retrieved_historical_context(monkeypatch):
    documents = _documents()
    captured = {}
    _configure_success(monkeypatch)
    monkeypatch.setattr(
        rag_chain,
        "retrieve_documents",
        lambda query, top_k=5: documents,
    )

    def fake_model(prompt_value):
        messages = prompt_value.to_messages()
        captured["system"] = messages[0].content
        captured["user"] = messages[1].content
        return AIMessage(content="Historical evidence points to database saturation.")

    monkeypatch.setattr(
        rag_chain,
        "create_nvidia_llm",
        lambda: RunnableLambda(fake_model),
    )
    monkeypatch.setattr(pipeline, "answer_question", rag_chain.answer_question)

    pipeline.run_validation(display=False)

    assert "chunk-shared" in captured["user"]
    assert "INC-1" in captured["user"]
    assert documents[0]["text"] in captured["user"]


def test_failed_nvidia_call_does_not_create_fabricated_answer(monkeypatch):
    _configure_success(monkeypatch)

    def fail_answer(query, top_k=5):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(pipeline, "answer_question", fail_answer)

    report = pipeline.run_validation(display=False)

    assert report["checks"]["NVIDIA live API call"] is False
    assert report["checks"]["Final answer generation"] is False
    assert "model unavailable" in report["errors"]["RAG/NVIDIA"]
    assert report["rag_result"] is None


def test_empty_retrieval_fails_retriever_and_source_checks(monkeypatch):
    _configure_success(monkeypatch, empty=True)

    report = pipeline.run_validation(display=False)

    assert report["checks"]["Retriever integration"] is False
    assert report["checks"]["Source references"] is False


def test_invalid_retriever_structure_is_reported(monkeypatch):
    _configure_success(monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "retrieve_documents",
        lambda query, top_k=5: [{"chunk_id": "broken", "text": "missing fields"}],
    )

    report = pipeline.run_validation(display=False)

    assert report["checks"]["Retriever integration"] is False
    assert "Retriever integration" in report["errors"]
