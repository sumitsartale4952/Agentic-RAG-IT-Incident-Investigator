import pytest

from app.rag import semantic_retriever
from app.rag.vector_store import DATABASE_DIRECTORY
from app.rag.semantic_retriever import semantic_search


class FakeEmbedder:
    def __init__(self):
        self.queries = []

    def embed_query(self, query):
        self.queries.append(query)
        return [0.25, 0.75]


class FakeCollection:
    def __init__(self):
        self.query_arguments = None

    def query(self, **kwargs):
        self.query_arguments = kwargs
        result = {
            "ids": [["chunk-a", "chunk-b", "chunk-c"]],
            "documents": [["nearest", "middle", "farthest"]],
            "metadatas": [
                [
                    {"incident_id": "INC-A"},
                    {"incident_id": "INC-B"},
                    {"incident_id": "INC-C"},
                ]
            ],
            "distances": [[0.1, 0.4, 0.9]],
        }
        count = kwargs["n_results"]
        return {key: [values[0][:count]] for key, values in result.items()}


class FakeChroma:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._collection = FakeCollection()
        self.instances.append(self)


@pytest.fixture
def fake_retrieval(monkeypatch):
    FakeChroma.instances = []
    embedder = FakeEmbedder()
    monkeypatch.setattr(semantic_retriever, "_create_query_embedder", lambda: embedder)
    monkeypatch.setattr(semantic_retriever, "Chroma", FakeChroma)
    return embedder


def test_query_is_embedded_once_and_collection_is_reused(fake_retrieval):
    results = semantic_search("  payment API latency  ", top_k=2)

    assert fake_retrieval.queries == ["payment API latency"]
    store = FakeChroma.instances[0]
    assert store.kwargs["collection_name"] == "historical_incidents"
    assert store.kwargs["persist_directory"] == str(DATABASE_DIRECTORY)
    assert store._collection.query_arguments["query_embeddings"] == [[0.25, 0.75]]
    assert store._collection.query_arguments["n_results"] == 2
    assert len(results) == 2
    assert [result["chunk_id"] for result in results] == ["chunk-a", "chunk-b"]


def test_results_include_chunk_data_and_ascending_distance(fake_retrieval):
    results = semantic_search("database connection errors", top_k=3)

    assert [result["chunk_id"] for result in results] == [
        "chunk-a",
        "chunk-b",
        "chunk-c",
    ]
    assert [result["distance"] for result in results] == [0.1, 0.4, 0.9]
    assert results[0]["text"] == "nearest"
    assert results[0]["metadata"] == {"incident_id": "INC-A"}


@pytest.mark.parametrize("query", ["", "  ", None, 123])
def test_invalid_query_raises(query, fake_retrieval):
    with pytest.raises(ValueError, match="non-empty"):
        semantic_search(query)


@pytest.mark.parametrize("top_k", [0, -1, 1.5, True])
def test_invalid_top_k_raises(top_k, fake_retrieval):
    with pytest.raises(ValueError, match="positive integer"):
        semantic_search("valid query", top_k=top_k)


def test_stored_document_vectors_are_not_reembedded(fake_retrieval):
    semantic_search("query only")

    assert fake_retrieval.queries == ["query only"]
    assert FakeChroma.instances[0]._collection.query_arguments["query_embeddings"] == [
        [0.25, 0.75]
    ]
