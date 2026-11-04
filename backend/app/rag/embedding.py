"""Generate normalized LangChain embeddings for saved incident chunks."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence

# SentenceTransformers uses PyTorch; avoid importing unrelated ML backends.
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = BACKEND_ROOT / "data" / "processed" / "cleaned_documents_chunks.jsonl"
OUTPUT_PATH = BACKEND_ROOT / "data" / "processed" / "embeddings.jsonl"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384
BATCH_SIZE = 32


def _create_embedding_model(batch_size: int) -> Any:
    """Create the configured normalized LangChain embedding model."""
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True, "batch_size": batch_size},
    )


def read_chunks(input_path: Path = INPUT_PATH) -> List[Dict[str, Any]]:
    """Read chunk records from a UTF-8 JSONL file."""
    chunks: List[Dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict) or not isinstance(record.get("text"), str):
                raise ValueError(f"Invalid chunk record on line {line_number}.")
            chunks.append(record)
    return chunks


def embed_chunks(
    chunks: Sequence[Dict[str, Any]],
    embeddings: Any,
    batch_size: int = BATCH_SIZE,
) -> List[Dict[str, Any]]:
    """Embed text in batches while retaining each chunk's original fields."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    output_records: List[Dict[str, Any]] = []
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        vectors = embeddings.embed_documents([chunk["text"] for chunk in batch])
        if len(vectors) != len(batch):
            raise ValueError("Embedding model returned an unexpected number of vectors.")
        for chunk, vector in zip(batch, vectors):
            if len(vector) != EMBEDDING_DIMENSIONS:
                raise ValueError(
                    f"Expected {EMBEDDING_DIMENSIONS} embedding values for "
                    f"{chunk.get('chunk_id', 'unknown chunk')}; got {len(vector)}."
                )
            output_records.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk["text"],
                    "metadata": chunk["metadata"],
                    "embedding": [float(value) for value in vector],
                }
            )
    return output_records


def generate_embeddings(
    input_path: Path = INPUT_PATH,
    output_path: Path = OUTPUT_PATH,
    batch_size: int = BATCH_SIZE,
) -> int:
    """Load the model once, embed all chunks, and write JSONL output."""
    chunks = read_chunks(input_path)
    model = _create_embedding_model(batch_size)
    records = embed_chunks(chunks, model, batch_size=batch_size)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
    return len(records)


def main() -> int:
    """Run the default chunk-to-embedding JSONL pipeline."""
    started_at = time.perf_counter()
    try:
        count = generate_embeddings()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.error("Embedding generation failed: %s", exc)
        return 1
    elapsed = time.perf_counter() - started_at
    print(f"Embedding model: {EMBEDDING_MODEL}")
    print(f"Processed chunks: {count}")
    print(f"Embedding dimensions: {EMBEDDING_DIMENSIONS}")
    print(f"Output file: {OUTPUT_PATH}")
    print(f"Execution time: {elapsed:.2f} seconds")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())
