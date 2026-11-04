"""Token-aware chunking for historical incident LangChain documents."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import statistics
from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 224
DEFAULT_CHUNK_OVERLAP = 40
DEFAULT_EMBEDDING_MAX_TOKENS = 256
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNKING_STRATEGY = "recursive_character_token_aware"
SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
CHUNK_METADATA_KEYS = {
    "chunk_id",
    "chunk_index",
    "total_chunks",
    "chunk_size",
    "chunk_overlap",
    "chunking_strategy",
    "embedding_model",
    "parent_document_id",
}


class HistoricalIncidentChunkerError(Exception):
    """Base error for historical incident chunking."""


class TokenizerInitializationError(HistoricalIncidentChunkerError):
    """Raised when the configured Hugging Face tokenizer cannot be loaded."""


class ChunkValidationError(HistoricalIncidentChunkerError):
    """Raised for invalid chunk output when validation is requested."""


def _environment_integer(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {value!r}") from exc


def _json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _metadata_value(value: Any) -> Any:
    """Convert metadata to scalar or scalar-list values accepted by Chroma."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        values = list(value)
        types = {type(item) for item in values}
        if values and len(types) == 1 and all(
            isinstance(item, (str, int, float, bool)) for item in values
        ):
            return values
        if not values:
            return _json_value(values)
    return _json_value(value)


def _normalized_metadata(metadata: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        str(key): normalized
        for key, value in metadata.items()
        if (normalized := _metadata_value(value)) is not None
    }


def _stable_document_identity(document: Document) -> str:
    for key in ("document_id", "incident_id"):
        value = document.metadata.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    fingerprint = hashlib.sha256(
        (document.page_content + "\0" + _json_value(document.metadata)).encode("utf-8")
    ).hexdigest()
    return f"document_{fingerprint}"


def _safe_identifier(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return safe or hashlib.sha256(value.encode("utf-8")).hexdigest()


def _percentile(values: Sequence[int], percentile: int) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    index = max(0, math.ceil(percentile * len(ordered) / 100) - 1)
    return ordered[index]


class HistoricalIncidentChunker:
    """Split incident Documents with a model-matched tokenizer and preserve metadata.

    Chunk sizes and token measurements are based on the configured Hugging Face
    tokenizer, not character counts. Body-token counts exclude special tokens;
    embedding-input counts include the tokenizer's special tokens.
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        embedding_max_tokens: Optional[int] = None,
        embedding_model: Optional[str] = None,
        *,
        tokenizer: Any = None,
        local_files_only: Optional[bool] = None,
    ) -> None:
        self.chunk_size = (
            chunk_size
            if chunk_size is not None
            else _environment_integer("RAG_CHUNK_SIZE", DEFAULT_CHUNK_SIZE)
        )
        self.chunk_overlap = (
            chunk_overlap
            if chunk_overlap is not None
            else _environment_integer("RAG_CHUNK_OVERLAP", DEFAULT_CHUNK_OVERLAP)
        )
        self.embedding_max_tokens = (
            embedding_max_tokens
            if embedding_max_tokens is not None
            else _environment_integer(
                "RAG_EMBEDDING_MAX_TOKENS", DEFAULT_EMBEDDING_MAX_TOKENS
            )
        )
        self.embedding_model = (
            embedding_model
            or os.environ.get("RAG_EMBEDDING_MODEL")
            or DEFAULT_EMBEDDING_MODEL
        )
        self._validate_settings()
        self.tokenizer = tokenizer or self._load_tokenizer(local_files_only)
        try:
            self.special_token_count = int(
                self.tokenizer.num_special_tokens_to_add(pair=False)
            )
        except Exception as exc:
            raise TokenizerInitializationError(
                "The configured tokenizer does not expose special-token behavior."
            ) from exc
        if self.special_token_count < 0:
            raise TokenizerInitializationError(
                "The configured tokenizer reported an invalid special-token count."
            )

        self.effective_chunk_size = min(
            self.chunk_size,
            self.embedding_max_tokens - self.special_token_count,
        )
        if self.effective_chunk_size <= 0:
            raise ValueError(
                "RAG_EMBEDDING_MAX_TOKENS must exceed the tokenizer's "
                "special-token count."
            )
        if self.chunk_overlap >= self.effective_chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than the effective body token limit "
                f"({self.effective_chunk_size})."
            )

        self._splitter = self._make_splitter(
            self.effective_chunk_size, self.chunk_overlap, SEPARATORS
        )
        self._character_splitter = self._make_splitter(
            self.effective_chunk_size, 0, [""]
        )
        self._documents: List[Document] = []
        self._document_snapshots: List[Tuple[str, Dict[str, Any]]] = []
        self._parent_metadata: Dict[str, Dict[str, Any]] = {}
        self._parent_identities: Dict[int, str] = {}
        self._coverage_verified: set = set()
        self._chunks: List[Document] = []
        self._summary: Dict[str, Any] = self._empty_summary()
        self.validation_errors: List[str] = []

    def _validate_settings(self) -> None:
        for name, value in (
            ("chunk_size", self.chunk_size),
            ("chunk_overlap", self.chunk_overlap),
            ("embedding_max_tokens", self.embedding_max_tokens),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer.")
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero.")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative.")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size.")
        if self.embedding_max_tokens <= 0:
            raise ValueError("embedding_max_tokens must be greater than zero.")
        if not self.embedding_model.strip():
            raise ValueError("embedding_model must not be empty.")

    def _load_tokenizer(self, local_files_only: Optional[bool]) -> Any:
        if local_files_only is None:
            local_files_only = any(
                os.environ.get(name, "").casefold() in {"1", "true", "yes"}
                for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
            )
        try:
            from transformers import AutoTokenizer

            return AutoTokenizer.from_pretrained(
                self.embedding_model,
                local_files_only=local_files_only,
            )
        except Exception as exc:
            mode = "locally cached" if local_files_only else "available"
            raise TokenizerInitializationError(
                f"Could not load {mode} tokenizer for embedding model "
                f"'{self.embedding_model}'. Check model access and tokenizer "
                "configuration; token-based chunking has no character-count fallback."
            ) from exc

    def _make_splitter(
        self, body_limit: int, overlap: int, separators: Sequence[str]
    ) -> RecursiveCharacterTextSplitter:
        try:
            return RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
                self.tokenizer,
                chunk_size=body_limit + self.special_token_count,
                chunk_overlap=overlap,
                separators=list(separators),
                keep_separator=True,
                strip_whitespace=False,
            )
        except Exception as exc:
            raise TokenizerInitializationError(
                "Could not initialize LangChain's Hugging Face token-aware "
                "RecursiveCharacterTextSplitter."
            ) from exc

    def _token_counts(self, text: str) -> Tuple[int, int]:
        try:
            body_tokens = len(
                self.tokenizer.encode(
                    text, add_special_tokens=False, truncation=False
                )
            )
            embedding_tokens = len(
                self.tokenizer.encode(
                    text, add_special_tokens=True, truncation=False
                )
            )
        except Exception as exc:
            raise HistoricalIncidentChunkerError(
                "The configured tokenizer failed to measure chunk tokens."
            ) from exc
        return body_tokens, embedding_tokens

    def _split_with_limits(self, text: str) -> List[str]:
        pieces = self._repair_heading_boundaries(self._splitter.split_text(text))
        safe_pieces: List[str] = []
        for piece in pieces:
            body_tokens, embedding_tokens = self._token_counts(piece)
            if (
                body_tokens <= self.chunk_size
                and embedding_tokens <= self.embedding_max_tokens
            ):
                safe_pieces.append(piece)
                continue
            safe_pieces.extend(self._character_splitter.split_text(piece))

        for piece in safe_pieces:
            body_tokens, embedding_tokens = self._token_counts(piece)
            if (
                not piece.strip()
                or body_tokens > self.chunk_size
                or embedding_tokens > self.embedding_max_tokens
            ):
                raise HistoricalIncidentChunkerError(
                    "Recursive token-aware splitting could not meet configured "
                    "chunk and embedding input limits."
                )
        return safe_pieces

    def _repair_heading_boundaries(self, pieces: Sequence[str]) -> List[str]:
        repaired: List[str] = []
        index = 0
        while index < len(pieces):
            piece = pieces[index]
            if piece.strip() and not self._is_heading_only(piece):
                repaired.append(piece)
                index += 1
                continue

            combined = piece
            index += 1
            while index < len(pieces):
                next_piece = pieces[index]
                overlap = self._suffix_prefix_overlap(combined, next_piece)
                combined += next_piece[overlap:]
                index += 1
                if combined.strip() and not self._is_heading_only(combined):
                    break

            if not combined.strip():
                if repaired:
                    repaired[-1] += combined
                else:
                    repaired.append(combined)
                continue

            body_tokens, embedding_tokens = self._token_counts(combined)
            if (
                body_tokens <= self.chunk_size
                and embedding_tokens <= self.embedding_max_tokens
            ):
                repaired.append(combined)
            else:
                repaired.extend(self._character_splitter.split_text(combined))
        return repaired

    @staticmethod
    def _is_heading_only(text: str) -> bool:
        stripped = text.strip()
        return "\n" not in stripped and stripped.endswith(":")

    @staticmethod
    def _suffix_prefix_overlap(left: str, right: str) -> int:
        maximum = min(len(left), len(right))
        for size in range(maximum, 0, -1):
            if left[-size:] == right[:size]:
                return size
        return 0

    @staticmethod
    def _covers_source(source: str, pieces: Sequence[str]) -> bool:
        """Check that ordered chunk text covers every source character."""
        if not source or not pieces:
            return not source and not pieces

        @lru_cache(maxsize=None)
        def covers_from(index: int, previous_start: int, covered_until: int) -> bool:
            if index == len(pieces):
                return covered_until >= len(source)
            piece = pieces[index]
            positions: List[int] = []
            search_from = previous_start
            while True:
                start = source.find(piece, search_from)
                if start < 0:
                    break
                positions.append(start)
                search_from = start + 1
            for start in reversed(positions):
                end = start + len(piece)
                if (
                    start <= covered_until
                    and end > covered_until
                    and end <= len(source)
                    and covers_from(index + 1, start, end)
                ):
                    return True
            return False

        if not pieces[0] or not source.startswith(pieces[0]):
            return False
        return covers_from(1, 0, len(pieces[0]))

    def _parent_ids(self, documents: Sequence[Document]) -> Dict[int, str]:
        identities = [_stable_document_identity(document) for document in documents]
        totals = Counter(identities)
        seen: Counter = Counter()
        result: Dict[int, str] = {}
        for index, identity in enumerate(identities):
            seen[identity] += 1
            parent_id = _safe_identifier(identity)
            if totals[identity] > 1:
                parent_id = f"{parent_id}__doc_{seen[identity]:03d}"
            result[index] = parent_id
        return result

    def chunk_documents(self, documents: Iterable[Document]) -> List[Document]:
        """Chunk Documents, reporting rather than hiding empty or failed inputs."""
        self._documents = list(documents)
        for document in self._documents:
            if not isinstance(document, Document):
                raise TypeError(
                    "chunk_documents expects langchain_core.documents.Document "
                    f"objects; got {type(document).__name__}."
                )
            if not isinstance(document.page_content, str):
                raise TypeError("Every source Document page_content must be a string.")

        self._document_snapshots = [
            (document.page_content, deepcopy(document.metadata))
            for document in self._documents
        ]
        self._parent_identities = self._parent_ids(self._documents)
        self._parent_metadata = {}
        self._coverage_verified = set()
        self._chunks = []
        self.validation_errors = []
        per_document_counts = {parent_id: 0 for parent_id in self._parent_identities.values()}
        failed_documents: List[Dict[str, str]] = []
        generated: List[Tuple[str, int, Dict[str, Any], str]] = []

        for index, document in enumerate(self._documents):
            parent_id = self._parent_identities[index]
            source_metadata = _normalized_metadata(document.metadata)
            self._parent_metadata[parent_id] = source_metadata
            identity = str(
                document.metadata.get("document_id")
                or document.metadata.get("incident_id")
                or parent_id
            )
            if not document.page_content.strip():
                failed_documents.append(
                    {"document_id": identity, "reason": "empty_page_content"}
                )
                logger.warning(
                    "Could not chunk source document %s: page_content is empty.",
                    parent_id,
                )
                continue

            try:
                pieces = self._split_with_limits(document.page_content)
                if not pieces or not self._covers_source(document.page_content, pieces):
                    raise HistoricalIncidentChunkerError(
                        "Generated chunks did not preserve complete source text."
                    )
                self._coverage_verified.add(parent_id)
                per_document_counts[parent_id] = len(pieces)
                for chunk_index, piece in enumerate(pieces):
                    metadata = dict(source_metadata)
                    metadata.setdefault("document_id", parent_id)
                    metadata["parent_document_id"] = parent_id
                    metadata.update(
                        {
                            "chunk_id": f"{parent_id}_chunk_{chunk_index:03d}",
                            "chunk_index": chunk_index,
                            "total_chunks": len(pieces),
                            "chunk_size": self.chunk_size,
                            "chunk_overlap": self.chunk_overlap,
                            "chunking_strategy": CHUNKING_STRATEGY,
                            "embedding_model": self.embedding_model,
                        }
                    )
                    generated.append((parent_id, chunk_index, metadata, piece))
            except Exception as exc:
                failed_documents.append(
                    {
                        "document_id": identity,
                        "reason": f"{type(exc).__name__}: {exc}",
                    }
                )
                logger.error(
                    "Could not safely chunk source document %s (%s).",
                    parent_id,
                    type(exc).__name__,
                )

        totals = Counter(parent_id for parent_id, _, _, _ in generated)
        self._chunks = [
            Document(
                page_content=text,
                metadata={**metadata, "total_chunks": totals[parent_id]},
            )
            for parent_id, _, metadata, text in generated
        ]
        self._summary = self._build_summary(per_document_counts, failed_documents)
        if not self.validate_chunks(self._chunks):
            self._summary["chunking_status"] = (
                "PARTIAL" if self._summary["successfully_processed_documents"] else "FAILED"
            )
        return self._chunks

    def _build_summary(
        self,
        per_document_counts: Mapping[str, int],
        failed_documents: Sequence[Mapping[str, str]],
    ) -> Dict[str, Any]:
        token_counts = [self._token_counts(chunk.page_content) for chunk in self._chunks]
        body_lengths = [body for body, _ in token_counts]
        embedding_lengths = [total for _, total in token_counts]
        id_counts = Counter(chunk.metadata["chunk_id"] for chunk in self._chunks)
        fingerprint_parents: Dict[str, set] = defaultdict(set)
        fingerprint_counts: Counter = Counter()
        for chunk in self._chunks:
            fingerprint = hashlib.sha256(chunk.page_content.encode("utf-8")).hexdigest()
            fingerprint_counts[fingerprint] += 1
            fingerprint_parents[fingerprint].add(chunk.metadata["parent_document_id"])

        duplicate_fingerprints = {
            fingerprint
            for fingerprint, count in fingerprint_counts.items()
            if count > 1
        }
        same_document_duplicates = sum(
            fingerprint_counts[fingerprint] - 1
            for fingerprint in duplicate_fingerprints
            if len(fingerprint_parents[fingerprint]) == 1
        )
        cross_document_duplicate_fingerprints = sum(
            1
            for fingerprint in duplicate_fingerprints
            if len(fingerprint_parents[fingerprint]) > 1
        )
        input_count = len(self._documents)
        counts = list(per_document_counts.values())
        successful_count = sum(count > 0 for count in counts)
        median_chunks = statistics.median(
            [count for count in counts if count > 0]
        ) if successful_count else 0
        high_chunk_threshold = max(10, math.ceil(median_chunks * 2))
        unusually_high = [
            parent_id
            for parent_id, count in per_document_counts.items()
            if count > high_chunk_threshold
        ]
        return {
            "input_documents": input_count,
            "successfully_processed_documents": successful_count,
            "failed_documents": list(failed_documents),
            "failed_document_count": len(failed_documents),
            "total_output_chunks": len(self._chunks),
            "average_chunks_per_document": (
                len(self._chunks) / input_count if input_count else 0.0
            ),
            "minimum_chunks_per_document": min(counts, default=0),
            "maximum_chunks_per_document": max(counts, default=0),
            "average_body_tokens": (
                sum(body_lengths) / len(body_lengths) if body_lengths else 0.0
            ),
            "median_body_tokens": (
                statistics.median(body_lengths) if body_lengths else 0
            ),
            "p95_body_tokens": _percentile(body_lengths, 95),
            "p99_body_tokens": _percentile(body_lengths, 99),
            "minimum_body_tokens": min(body_lengths, default=0),
            "maximum_body_tokens": max(body_lengths, default=0),
            "average_embedding_input_tokens": (
                sum(embedding_lengths) / len(embedding_lengths)
                if embedding_lengths
                else 0.0
            ),
            "maximum_embedding_input_tokens": max(embedding_lengths, default=0),
            "chunks_below_50_tokens": sum(count < 50 for count in body_lengths),
            "chunks_below_100_tokens": sum(count < 100 for count in body_lengths),
            "chunks_above_chunk_size": sum(
                count > self.chunk_size for count in body_lengths
            ),
            "chunks_above_embedding_max_tokens": sum(
                count > self.embedding_max_tokens for count in embedding_lengths
            ),
            "empty_chunks": sum(not chunk.page_content.strip() for chunk in self._chunks),
            "duplicate_chunk_ids": sum(count - 1 for count in id_counts.values() if count > 1),
            "duplicate_content_fingerprints": len(duplicate_fingerprints),
            "same_document_duplicate_chunks": same_document_duplicates,
            "cross_document_duplicate_fingerprints": cross_document_duplicate_fingerprints,
            "unusually_high_chunk_count_threshold": high_chunk_threshold,
            "documents_with_unusually_high_chunk_counts": unusually_high,
            "target_body_size_tokens": self.chunk_size,
            "embedding_input_limit_tokens": self.embedding_max_tokens,
            "embedding_model": self.embedding_model,
            "chunk_length_measurement": "Hugging Face tokenizer tokens",
            "chunking_status": (
                "SUCCESS"
                if not failed_documents and not self.validation_errors
                else "PARTIAL"
                if successful_count
                else "FAILED"
            ),
        }

    def validate_chunks(self, chunks: Optional[Sequence[Document]] = None) -> bool:
        """Validate chunk relationships, metadata, token limits, and source coverage."""
        selected = list(self._chunks if chunks is None else chunks)
        errors: List[str] = []
        chunk_ids: List[str] = []
        for chunk in selected:
            if not isinstance(chunk, Document):
                errors.append("output contains a non-LangChain Document")
                continue
            chunk_id = chunk.metadata.get("chunk_id")
            if not isinstance(chunk_id, str) or not chunk_id:
                errors.append("chunk is missing a valid string chunk_id")
            else:
                chunk_ids.append(chunk_id)
        if len(chunk_ids) != len(set(chunk_ids)):
            errors.append("chunk IDs are not unique")

        grouped: Dict[str, List[Document]] = defaultdict(list)
        for chunk in selected:
            if not isinstance(chunk, Document):
                continue
            metadata = chunk.metadata
            parent_id = metadata.get("parent_document_id")
            if not parent_id:
                errors.append("chunk is missing parent_document_id")
                continue
            parent_id = str(parent_id)
            grouped[parent_id].append(chunk)
            if (
                metadata.get("chunk_size") != self.chunk_size
                or metadata.get("chunk_overlap") != self.chunk_overlap
                or metadata.get("chunking_strategy") != CHUNKING_STRATEGY
                or metadata.get("embedding_model") != self.embedding_model
            ):
                errors.append(f"{parent_id}: chunking configuration metadata is invalid")
            if not chunk.page_content.strip():
                errors.append(f"{parent_id}: empty chunk")
            if any(
                not (
                    isinstance(value, (str, int, float, bool))
                    or (
                        isinstance(value, list)
                        and all(
                            isinstance(item, (str, int, float, bool))
                            for item in value
                        )
                    )
                )
                for value in metadata.values()
            ):
                errors.append(f"{parent_id}: metadata is not Chroma-compatible")
            if parent_id not in self._parent_metadata:
                errors.append(f"{parent_id}: no matching source document")
            else:
                expected_metadata = self._parent_metadata[parent_id]
                for key, value in expected_metadata.items():
                    if metadata.get(key) != value:
                        errors.append(f"{parent_id}: source metadata {key!r} changed")
                        break
                source_document = next(
                    (
                        self._documents[index]
                        for index, identity in self._parent_identities.items()
                        if identity == parent_id
                    ),
                    None,
                )
                if (
                    source_document is not None
                    and "incident_id" in source_document.metadata
                    and metadata.get("incident_id")
                    != _metadata_value(source_document.metadata["incident_id"])
                ):
                    errors.append(f"{parent_id}: incident_id was not preserved")
            try:
                body_tokens, embedding_tokens = self._token_counts(chunk.page_content)
                if body_tokens > self.chunk_size:
                    errors.append(f"{parent_id}: body exceeds target token size")
                if embedding_tokens > self.embedding_max_tokens:
                    errors.append(f"{parent_id}: embedding input exceeds token limit")
            except HistoricalIncidentChunkerError as exc:
                errors.append(f"{parent_id}: {exc}")

        for parent_id, parent_chunks in grouped.items():
            indexes = [chunk.metadata.get("chunk_index") for chunk in parent_chunks]
            expected_indexes = list(range(len(parent_chunks)))
            if indexes != expected_indexes:
                errors.append(f"{parent_id}: chunk indexes are not sequential")
            total_chunks = len(parent_chunks)
            if any(chunk.metadata.get("total_chunks") != total_chunks for chunk in parent_chunks):
                errors.append(f"{parent_id}: total_chunks is inconsistent")
            for index, chunk in enumerate(parent_chunks):
                expected_id = f"{parent_id}_chunk_{index:03d}"
                if chunk.metadata.get("chunk_id") != expected_id:
                    errors.append(f"{parent_id}: chunk ID is not deterministic")
            source_document = next(
                (
                    self._documents[index]
                    for index, identity in self._parent_identities.items()
                    if identity == parent_id
                ),
                None,
            )
            if source_document is not None and not self._covers_source(
                source_document.page_content,
                [chunk.page_content for chunk in parent_chunks],
            ):
                errors.append(f"{parent_id}: chunk text does not cover source content")

        for index, document in enumerate(self._documents):
            parent_id = self._parent_identities[index]
            original_content, original_metadata = self._document_snapshots[index]
            if (
                document.page_content != original_content
                or document.metadata != original_metadata
            ):
                errors.append(f"{parent_id}: source Document was modified")
            if original_content.strip() and parent_id not in self._coverage_verified:
                errors.append(f"{parent_id}: source text was not fully represented")
        if self._summary.get("failed_documents"):
            errors.append("one or more source documents could not be chunked safely")

        self.validation_errors = list(dict.fromkeys(errors))
        if self._summary:
            self._summary["validation_errors"] = list(self.validation_errors)
        if self.validation_errors:
            logger.error(
                "Chunk validation failed with %d error(s).",
                len(self.validation_errors),
            )
        return not self.validation_errors

    def _empty_summary(self) -> Dict[str, Any]:
        return {
            "input_documents": 0,
            "successfully_processed_documents": 0,
            "failed_documents": [],
            "failed_document_count": 0,
            "total_output_chunks": 0,
            "average_chunks_per_document": 0.0,
            "minimum_chunks_per_document": 0,
            "maximum_chunks_per_document": 0,
            "average_body_tokens": 0.0,
            "median_body_tokens": 0,
            "p95_body_tokens": 0,
            "p99_body_tokens": 0,
            "minimum_body_tokens": 0,
            "maximum_body_tokens": 0,
            "average_embedding_input_tokens": 0.0,
            "maximum_embedding_input_tokens": 0,
            "chunks_below_50_tokens": 0,
            "chunks_below_100_tokens": 0,
            "chunks_above_chunk_size": 0,
            "chunks_above_embedding_max_tokens": 0,
            "empty_chunks": 0,
            "duplicate_chunk_ids": 0,
            "duplicate_content_fingerprints": 0,
            "same_document_duplicate_chunks": 0,
            "cross_document_duplicate_fingerprints": 0,
            "unusually_high_chunk_count_threshold": 10,
            "documents_with_unusually_high_chunk_counts": [],
            "target_body_size_tokens": self.chunk_size,
            "embedding_input_limit_tokens": self.embedding_max_tokens,
            "embedding_model": self.embedding_model,
            "chunk_length_measurement": "Hugging Face tokenizer tokens",
            "chunking_status": "NOT_STARTED",
            "validation_errors": [],
        }

    def get_chunking_summary(self) -> Dict[str, Any]:
        """Return calculated counts and token statistics for the latest run."""
        return deepcopy(self._summary)

    def format_chunking_summary(self) -> str:
        """Render the most recent chunk audit for command-line output."""
        summary = self.get_chunking_summary()
        failed = ", ".join(
            f"{item['document_id']} ({item['reason']})"
            for item in summary["failed_documents"]
        ) or "none"
        high_count_docs = ", ".join(
            summary["documents_with_unusually_high_chunk_counts"]
        ) or "none"
        return "\n".join(
            (
                "DOCUMENT CHUNKING AUDIT",
                "",
                f"Input documents: {summary['input_documents']}",
                "Successfully processed documents: "
                f"{summary['successfully_processed_documents']}",
                f"Failed documents: {summary['failed_document_count']} ({failed})",
                f"Total output chunks: {summary['total_output_chunks']}",
                "Average chunks per document: "
                f"{summary['average_chunks_per_document']:.2f}",
                "Minimum chunks per document: "
                f"{summary['minimum_chunks_per_document']}",
                "Maximum chunks per document: "
                f"{summary['maximum_chunks_per_document']}",
                "Average body tokens: "
                f"{summary['average_body_tokens']:.2f}",
                f"Median body tokens: {summary['median_body_tokens']}",
                f"P95 body tokens: {summary['p95_body_tokens']}",
                f"P99 body tokens: {summary['p99_body_tokens']}",
                f"Minimum body tokens: {summary['minimum_body_tokens']}",
                f"Maximum body tokens: {summary['maximum_body_tokens']}",
                f"Average complete embedding-input tokens: "
                f"{summary['average_embedding_input_tokens']:.2f}",
                "Maximum complete embedding-input tokens: "
                f"{summary['maximum_embedding_input_tokens']}",
                f"Chunks below 50 body tokens: {summary['chunks_below_50_tokens']}",
                f"Chunks below 100 body tokens: {summary['chunks_below_100_tokens']}",
                "Chunks above target body size: "
                f"{summary['chunks_above_chunk_size']}",
                "Chunks above complete embedding-input limit: "
                f"{summary['chunks_above_embedding_max_tokens']}",
                f"Empty chunks: {summary['empty_chunks']}",
                f"Duplicate chunk IDs: {summary['duplicate_chunk_ids']}",
                "Duplicate content fingerprints: "
                f"{summary['duplicate_content_fingerprints']}",
                "Same-document duplicate chunks: "
                f"{summary['same_document_duplicate_chunks']}",
                "Cross-document duplicate fingerprints: "
                f"{summary['cross_document_duplicate_fingerprints']}",
                "Unusually high chunk count threshold (> "
                f"{summary['unusually_high_chunk_count_threshold']} chunks): "
                f"{high_count_docs}",
                f"Chunk length measurement: {summary['chunk_length_measurement']}",
                f"Chunking status: {summary['chunking_status']}",
            )
        )


def main() -> int:
    """Run the default CSV loader and chunker without creating embeddings."""
    from app.rag.document_loader import (
        HistoricalIncidentLoader,
        HistoricalIncidentLoaderError,
    )

    try:
        loader = HistoricalIncidentLoader()
        documents = loader.load()
        chunker = HistoricalIncidentChunker()
    except (HistoricalIncidentLoaderError, OSError, HistoricalIncidentChunkerError) as exc:
        logger.error("Historical incident chunking could not start (%s).", type(exc).__name__)
        print(f"DOCUMENT CHUNKING FAILED\n{exc}")
        return 1

    chunks = chunker.chunk_documents(documents)
    print(loader.format_loading_summary())
    print()
    print(chunker.format_chunking_summary())
    for index, chunk in enumerate(chunks[:2], start=1):
        print(f"\n--- Chunk preview {index} ---")
        print(json.dumps(chunk.metadata, ensure_ascii=False, sort_keys=True))
        print(chunk.page_content)

    loader_status = loader.get_loading_summary()["loading_status"]
    return (
        0
        if chunker.validate_chunks(chunks)
        and loader_status == "SUCCESS"
        and chunker.get_chunking_summary()["chunking_status"] == "SUCCESS"
        else 2
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())
