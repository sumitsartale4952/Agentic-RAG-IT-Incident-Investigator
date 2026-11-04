import json

import pytest
from langchain_core.documents import Document
from transformers import PreTrainedTokenizer

from app.rag.chunking import (
    HistoricalIncidentChunker,
    TokenizerInitializationError,
)


class CharacterTokenizer(PreTrainedTokenizer):
    """Local deterministic tokenizer fixture that counts each character."""

    def __init__(self):
        special_tokens = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"]
        self.vocab = {token: index for index, token in enumerate(special_tokens)}
        for character in (
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "0123456789 .,!?;:-_/\n\té東京🚨"
        ):
            if character not in self.vocab:
                self.vocab[character] = len(self.vocab)
        self.ids_to_tokens = {value: key for key, value in self.vocab.items()}
        super().__init__(
            pad_token="[PAD]",
            unk_token="[UNK]",
            cls_token="[CLS]",
            sep_token="[SEP]",
            mask_token="[MASK]",
        )

    def _tokenize(self, text):
        return list(text)

    def _convert_token_to_id(self, token):
        return self.vocab.get(token, self.vocab["[UNK]"])

    def _convert_id_to_token(self, index):
        return self.ids_to_tokens.get(index, "[UNK]")

    def build_inputs_with_special_tokens(self, token_ids_0, token_ids_1=None):
        output = [self.cls_token_id] + list(token_ids_0) + [self.sep_token_id]
        if token_ids_1 is not None:
            output += list(token_ids_1) + [self.sep_token_id]
        return output

    def get_vocab(self):
        return dict(self.vocab)


@pytest.fixture
def tokenizer():
    return CharacterTokenizer()


@pytest.fixture
def make_chunker(tokenizer):
    def _make(**kwargs):
        return HistoricalIncidentChunker(tokenizer=tokenizer, **kwargs)

    return _make


def test_short_document_produces_one_chunk_and_preserves_metadata(make_chunker):
    document = Document(
        page_content="Incident ID: INC-1\n\nIncident Title:\nShort outage.",
        metadata={
            "incident_id": "INC-1",
            "document_id": "INC-1",
            "company": "Example",
            "severity": "HIGH",
            "categories": ["OUTAGE", "API"],
            "source_url": "https://example.test/1",
        },
    )
    chunker = make_chunker()

    chunks = chunker.chunk_documents([document])

    assert len(chunks) == 1
    assert chunks[0].page_content == document.page_content
    assert chunks[0].metadata["incident_id"] == "INC-1"
    assert chunks[0].metadata["company"] == "Example"
    assert chunks[0].metadata["severity"] == "HIGH"
    assert chunks[0].metadata["categories"] == ["OUTAGE", "API"]
    assert chunks[0].metadata["source_url"] == "https://example.test/1"
    assert chunks[0].metadata["document_id"] == "INC-1"
    assert chunks[0].metadata["chunk_id"] == "INC-1_chunk_000"
    assert chunks[0].metadata["chunk_index"] == 0
    assert chunks[0].metadata["total_chunks"] == 1
    assert chunks[0].metadata["chunk_size"] == 224
    assert chunks[0].metadata["chunk_overlap"] == 40
    assert chunks[0].metadata["chunking_strategy"] == "recursive_character_token_aware"
    assert chunks[0].metadata["embedding_model"] == (
        "sentence-transformers/all-MiniLM-L6-v2"
    )
    assert chunker.validate_chunks(chunks)


def test_long_document_is_split_at_token_limit(make_chunker, tokenizer):
    document = Document(
        page_content="Symptoms and Logs:\n" + ("incident evidence. " * 40),
        metadata={"incident_id": "INC-LONG"},
    )
    chunker = make_chunker()

    chunks = chunker.chunk_documents([document])

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(
            tokenizer.encode(
                chunk.page_content, add_special_tokens=False, truncation=False
            )
        ) <= 224
        assert len(
            tokenizer.encode(
                chunk.page_content, add_special_tokens=True, truncation=False
            )
        ) <= 256
    assert chunker.validate_chunks(chunks)


def test_adjacent_chunks_overlap(make_chunker):
    document = Document(page_content="alpha beta gamma. " * 35, metadata={"incident_id": "INC"})
    chunks = make_chunker(chunk_size=50, chunk_overlap=10).chunk_documents([document])

    assert len(chunks) > 1
    assert any(
        left.page_content[-10:] in right.page_content
        or right.page_content[:10] in left.page_content
        for left, right in zip(chunks, chunks[1:])
    )


def test_metadata_is_chroma_compatible_and_structures_are_retained(make_chunker):
    document = Document(
        page_content="An API failure.",
        metadata={
            "incident_id": "INC-META",
            "tags": ["API", "OUTAGE"],
            "nested": {"region": "west"},
        },
    )
    chunk = make_chunker().chunk_documents([document])[0]

    assert chunk.metadata["tags"] == ["API", "OUTAGE"]
    assert json.loads(chunk.metadata["nested"]) == {"region": "west"}
    assert all(
        isinstance(value, (str, int, float, bool))
        or (
            isinstance(value, list)
            and all(isinstance(item, (str, int, float, bool)) for item in value)
        )
        for value in chunk.metadata.values()
    )


def test_ids_and_indexes_are_unique_sequential_and_deterministic(make_chunker):
    document = Document(
        page_content="Root Cause Analysis:\n" + ("queue saturation. " * 35),
        metadata={"incident_id": "INC-SEQ", "document_id": "INC-SEQ"},
    )
    first = make_chunker(chunk_size=55, chunk_overlap=12).chunk_documents([document])
    second = make_chunker(chunk_size=55, chunk_overlap=12).chunk_documents([document])

    ids = [chunk.metadata["chunk_id"] for chunk in first]
    assert len(ids) == len(set(ids))
    assert ids == [chunk.metadata["chunk_id"] for chunk in second]
    assert [chunk.metadata["chunk_index"] for chunk in first] == list(range(len(first)))
    assert all(chunk.metadata["total_chunks"] == len(first) for chunk in first)


@pytest.mark.parametrize("content", ["", " \n\t  "])
def test_empty_and_whitespace_documents_are_reported(make_chunker, content):
    chunker = make_chunker()

    assert chunker.chunk_documents(
        [Document(page_content=content, metadata={"incident_id": "INC-EMPTY"})]
    ) == []
    summary = chunker.get_chunking_summary()
    assert summary["failed_document_count"] == 1
    assert summary["failed_documents"][0]["reason"] == "empty_page_content"
    assert summary["chunking_status"] == "FAILED"
    assert not chunker.validate_chunks()


def test_unicode_text_is_preserved_and_measured_with_tokenizer(make_chunker, tokenizer):
    source = "Café incidents in 東京 🚨. " * 18
    document = Document(page_content=source, metadata={"incident_id": "INC-UNICODE"})
    chunker = make_chunker(chunk_size=45, chunk_overlap=8)

    chunks = chunker.chunk_documents([document])

    assert len(chunks) > 1
    assert chunker._covers_source(source, [chunk.page_content for chunk in chunks])
    assert all(
        len(tokenizer.encode(chunk.page_content, add_special_tokens=False)) <= 45
        for chunk in chunks
    )


def test_missing_optional_metadata_uses_stable_parent_fallback(make_chunker):
    document = Document(page_content="No optional metadata.", metadata={})

    chunks = make_chunker().chunk_documents([document])

    assert chunks[0].metadata["document_id"].startswith("document_")
    assert chunks[0].metadata["parent_document_id"].startswith("document_")
    assert "incident_id" not in chunks[0].metadata
    assert chunks[0].metadata["chunk_id"].endswith("_chunk_000")


def test_multiple_documents_get_separate_chunk_relationships(make_chunker):
    documents = [
        Document(page_content="Same text.", metadata={"incident_id": "INC-A"}),
        Document(page_content="Same text.", metadata={"incident_id": "INC-B"}),
    ]

    chunker = make_chunker()
    chunks = chunker.chunk_documents(documents)

    assert len(chunks) == 2
    assert chunks[0].metadata["parent_document_id"] != chunks[1].metadata[
        "parent_document_id"
    ]
    assert chunks[0].metadata["incident_id"] == "INC-A"
    assert chunks[1].metadata["incident_id"] == "INC-B"
    assert chunker.get_chunking_summary()["input_documents"] == 2


def test_duplicate_fingerprints_are_reported_not_removed(make_chunker):
    documents = [
        Document(page_content="Repeated source text.", metadata={"incident_id": "INC-A"}),
        Document(page_content="Repeated source text.", metadata={"incident_id": "INC-B"}),
    ]
    chunker = make_chunker()

    chunks = chunker.chunk_documents(documents)

    assert len(chunks) == 2
    summary = chunker.get_chunking_summary()
    assert summary["duplicate_content_fingerprints"] == 1
    assert summary["cross_document_duplicate_fingerprints"] == 1
    assert summary["duplicate_chunk_ids"] == 0


def test_same_document_duplicate_chunks_are_reported_and_retained(make_chunker):
    chunker = make_chunker(chunk_size=50, chunk_overlap=49)
    chunks = chunker.chunk_documents(
        [Document(page_content="A" * 70, metadata={"incident_id": "INC-DUP"})]
    )

    summary = chunker.get_chunking_summary()

    assert len(chunks) > 1
    assert summary["same_document_duplicate_chunks"] > 0
    assert summary["duplicate_content_fingerprints"] > 0
    assert chunker.validate_chunks(chunks)


def test_very_long_unbroken_text_is_recursively_split(make_chunker, tokenizer):
    source = "X" * 800
    chunker = make_chunker(chunk_size=120, chunk_overlap=15)
    chunks = chunker.chunk_documents(
        [Document(page_content=source, metadata={"incident_id": "INC-UNBROKEN"})]
    )

    assert len(chunks) > 1
    assert chunker._covers_source(source, [chunk.page_content for chunk in chunks])
    assert max(
        len(tokenizer.encode(chunk.page_content, add_special_tokens=False))
        for chunk in chunks
    ) <= 120


def test_oversized_splitter_output_uses_safe_recursive_split(make_chunker, monkeypatch):
    source = "Y" * 700
    chunker = make_chunker(chunk_size=100, chunk_overlap=10)
    monkeypatch.setattr(chunker._splitter, "split_text", lambda text: [text])
    chunks = chunker.chunk_documents(
        [Document(page_content=source, metadata={"incident_id": "INC-OVERSIZE"})]
    )

    assert len(chunks) > 1
    assert chunker.validate_chunks(chunks)
    assert max(
        len(chunker.tokenizer.encode(chunk.page_content, add_special_tokens=False))
        for chunk in chunks
    ) <= 100


def test_original_documents_are_not_modified(make_chunker):
    metadata = {"incident_id": "INC-IMMUTABLE", "nested": {"state": ["resolved"]}}
    document = Document(page_content="Source evidence " * 30, metadata=metadata)
    original_content = document.page_content
    original_metadata = json.dumps(document.metadata, sort_keys=True)

    chunker = make_chunker(chunk_size=80, chunk_overlap=10)
    chunks = chunker.chunk_documents([document])

    assert chunker.validate_chunks(chunks)
    assert document.page_content == original_content
    assert json.dumps(document.metadata, sort_keys=True) == original_metadata


@pytest.mark.parametrize("chunk_size", [0, -1])
def test_invalid_chunk_size_raises(make_chunker, chunk_size):
    with pytest.raises(ValueError, match="chunk_size"):
        make_chunker(chunk_size=chunk_size)


@pytest.mark.parametrize("chunk_overlap", [-1, 224])
def test_invalid_overlap_raises(make_chunker, chunk_overlap):
    with pytest.raises(ValueError, match="chunk_overlap"):
        make_chunker(chunk_overlap=chunk_overlap)


def test_embedding_limit_may_reduce_effective_body_size(make_chunker, tokenizer):
    chunker = make_chunker(
        chunk_size=40,
        chunk_overlap=5,
        embedding_max_tokens=20,
    )
    chunks = chunker.chunk_documents(
        [Document(page_content="long evidence " * 12, metadata={"incident_id": "INC-MAX"})]
    )

    assert all(
        len(tokenizer.encode(chunk.page_content, add_special_tokens=False)) <= 18
        for chunk in chunks
    )
    assert all(
        len(tokenizer.encode(chunk.page_content, add_special_tokens=True)) <= 20
        for chunk in chunks
    )


def test_initialization_errors_are_explicit(monkeypatch):
    def fail_to_load(*args, **kwargs):
        raise OSError("tokenizer unavailable")

    monkeypatch.setattr("transformers.AutoTokenizer.from_pretrained", fail_to_load)

    with pytest.raises(TokenizerInitializationError, match="no character-count fallback"):
        HistoricalIncidentChunker(local_files_only=True)


def test_environment_configuration_is_centralized(monkeypatch, tokenizer):
    monkeypatch.setenv("RAG_CHUNK_SIZE", "128")
    monkeypatch.setenv("RAG_CHUNK_OVERLAP", "20")
    monkeypatch.setenv("RAG_EMBEDDING_MAX_TOKENS", "256")
    monkeypatch.setenv("RAG_EMBEDDING_MODEL", "test/model")

    chunker = HistoricalIncidentChunker(tokenizer=tokenizer)

    assert chunker.chunk_size == 128
    assert chunker.chunk_overlap == 20
    assert chunker.embedding_max_tokens == 256
    assert chunker.embedding_model == "test/model"


def test_heading_and_source_text_are_retained(make_chunker):
    content = (
        "Incident Title:\nA short outage\n\n"
        "Symptoms and Logs:\n" + ("error log line. " * 30)
    )
    chunks = make_chunker(chunk_size=100, chunk_overlap=15).chunk_documents(
        [Document(page_content=content, metadata={"incident_id": "INC-HEADING"})]
    )

    assert any("Incident Title:" in chunk.page_content for chunk in chunks)
    assert any("Symptoms and Logs:" in chunk.page_content for chunk in chunks)
    assert all(chunk.page_content.strip() for chunk in chunks)
    assert all(not chunk.page_content.strip().endswith(":") for chunk in chunks)
    assert make_chunker()._covers_source(content, [chunk.page_content for chunk in chunks])


def test_validation_detects_mutated_chunk_content(make_chunker):
    chunker = make_chunker()
    chunks = chunker.chunk_documents(
        [Document(page_content="original evidence", metadata={"incident_id": "INC-CHECK"})]
    )
    chunks[0].page_content = "changed evidence"

    assert not chunker.validate_chunks(chunks)
    assert any("does not cover source content" in error for error in chunker.validation_errors)


def test_summary_reports_actual_token_distribution(make_chunker):
    chunker = make_chunker(chunk_size=50, chunk_overlap=8)
    chunks = chunker.chunk_documents(
        [
            Document(page_content="short", metadata={"incident_id": "INC-SHORT"}),
            Document(
                page_content="long evidence. " * 15,
                metadata={"incident_id": "INC-LONG"},
            ),
        ]
    )

    summary = chunker.get_chunking_summary()

    assert summary["input_documents"] == 2
    assert summary["successfully_processed_documents"] == 2
    assert summary["total_output_chunks"] == len(chunks)
    assert summary["minimum_body_tokens"] == min(
        len(chunker.tokenizer.encode(chunk.page_content, add_special_tokens=False))
        for chunk in chunks
    )
    assert summary["maximum_body_tokens"] == max(
        len(chunker.tokenizer.encode(chunk.page_content, add_special_tokens=False))
        for chunk in chunks
    )
    assert summary["chunk_length_measurement"] == "Hugging Face tokenizer tokens"
    assert summary["chunking_status"] == "SUCCESS"
