"""Store precomputed incident embeddings in a persistent Chroma collection."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from langchain_chroma import Chroma

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
EMBEDDINGS_PATH = BACKEND_ROOT / "data" / "processed" / "embeddings.jsonl"
DATABASE_DIRECTORY = BACKEND_ROOT / "data" / "vector_db" / "chroma"
COLLECTION_NAME = "historical_incidents"
BATCH_SIZE = 100


def _read_batches(
    input_path: Path, batch_size: int
) -> Iterable[List[Dict[str, Any]]]:
    """Read existing vector records from JSONL in manageable batches."""
    batch: List[Dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"Invalid embedding record on line {line_number}.")
            for field in ("chunk_id", "text", "metadata", "embedding"):
                if field not in record:
                    raise ValueError(
                        f"Embedding record on line {line_number} is missing {field!r}."
                    )
            batch.append(record)
            if len(batch) >= batch_size:
                yield batch
                batch = []
    if batch:
        yield batch


def store_embeddings(
    input_path: Path = EMBEDDINGS_PATH,
    database_directory: Path = DATABASE_DIRECTORY,
    batch_size: int = BATCH_SIZE,
    store: Optional[Chroma] = None,
) -> int:
    """Upsert saved vectors into Chroma using their stable chunk IDs."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    vector_store = store or Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(database_directory),
    )
    inserted = 0
    for batch in _read_batches(input_path, batch_size):
        # Chroma's LangChain wrapper has no public precomputed-vector method;
        # upsert through its collection to avoid embedding the text again.
        vector_store._collection.upsert(
            ids=[record["chunk_id"] for record in batch],
            documents=[record["text"] for record in batch],
            metadatas=[record["metadata"] for record in batch],
            embeddings=[record["embedding"] for record in batch],
        )
        inserted += len(batch)
    return inserted


def main() -> int:
    """Store the default embeddings file in the persistent Chroma collection."""
    try:
        count = store_embeddings()
        collection_count = Chroma(
            collection_name=COLLECTION_NAME,
            persist_directory=str(DATABASE_DIRECTORY),
        )._collection.count()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.error("Could not store embeddings in Chroma: %s", exc)
        return 1

    print(f"Collection name: {COLLECTION_NAME}")
    print(f"Vectors inserted: {count}")
    print(f"Vectors in collection: {collection_count}")
    print(f"Database directory: {DATABASE_DIRECTORY}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())
