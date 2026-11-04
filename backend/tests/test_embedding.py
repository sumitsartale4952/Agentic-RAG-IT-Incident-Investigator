import json
import sys
from types import ModuleType

from app.rag.embedding import (
    EMBEDDING_DIMENSIONS,
    _create_embedding_model,
    embed_chunks,
    generate_embeddings,
    read_chunks,
)


class FakeEmbeddings:
    def __init__(self):
        self.batches = []

    def embed_documents(self, texts):
        self.batches.append(list(texts))
        return [
            [float(len(text)) / EMBEDDING_DIMENSIONS] * EMBEDDING_DIMENSIONS
            for text in texts
        ]


def test_embed_chunks_batches_and_preserves_chunk_fields():
    chunks = [
        {
            "chunk_id": f"INC-{index}",
            "text": f"incident {index}",
            "metadata": {"severity": "HIGH", "chunk_index": index},
        }
        for index in range(3)
    ]
    model = FakeEmbeddings()

    records = embed_chunks(chunks, model, batch_size=2)

    assert model.batches == [["incident 0", "incident 1"], ["incident 2"]]
    assert len(records) == len(chunks)
    for original, result in zip(chunks, records):
        assert result["chunk_id"] == original["chunk_id"]
        assert result["text"] == original["text"]
        assert result["metadata"] == original["metadata"]
        assert len(result["embedding"]) == EMBEDDING_DIMENSIONS
        assert all(isinstance(value, float) for value in result["embedding"])


def test_generate_embeddings_reads_and_writes_jsonl(tmp_path, monkeypatch):
    input_path = tmp_path / "chunks.jsonl"
    output_path = tmp_path / "embeddings.jsonl"
    chunks = [
        {"chunk_id": "INC-1_chunk_000", "text": "Short text.", "metadata": {"x": 1}},
        {"chunk_id": "INC-2_chunk_000", "text": "Another text.", "metadata": {"y": 2}},
    ]
    input_path.write_text(
        "\n".join(json.dumps(chunk) for chunk in chunks) + "\n", encoding="utf-8"
    )
    model = FakeEmbeddings()
    init_kwargs = {}

    def fake_model(batch_size):
        init_kwargs["batch_size"] = batch_size
        return model

    monkeypatch.setattr("app.rag.embedding._create_embedding_model", fake_model)

    assert read_chunks(input_path) == chunks
    assert generate_embeddings(input_path, output_path, batch_size=1) == 2
    assert init_kwargs == {"batch_size": 1}

    records = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == len(chunks)
    assert records[0]["chunk_id"] == chunks[0]["chunk_id"]
    assert records[0]["text"] == chunks[0]["text"]
    assert records[0]["metadata"] == chunks[0]["metadata"]
    assert len(records[0]["embedding"]) == EMBEDDING_DIMENSIONS


def test_model_uses_normalized_minilm_embeddings(monkeypatch):
    integration = ModuleType("langchain_huggingface")
    integration.HuggingFaceEmbeddings = lambda **kwargs: kwargs
    monkeypatch.setitem(sys.modules, "langchain_huggingface", integration)

    model_options = _create_embedding_model(batch_size=16)

    assert model_options["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert model_options["encode_kwargs"] == {
        "normalize_embeddings": True,
        "batch_size": 16,
    }
