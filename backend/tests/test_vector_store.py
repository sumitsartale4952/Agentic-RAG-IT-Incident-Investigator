import json

from langchain_chroma import Chroma

from app.rag.vector_store import COLLECTION_NAME, store_embeddings


def _write_embeddings(path):
    records = [
        {
            "chunk_id": f"INC-{index}_chunk_000",
            "text": f"Incident text {index}",
            "metadata": {"incident_id": f"INC-{index}", "severity": "HIGH"},
            "embedding": [float(index), 0.25, 0.5],
        }
        for index in range(3)
    ]
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    return records


def test_stores_and_reopens_existing_vectors(tmp_path):
    input_path = tmp_path / "embeddings.jsonl"
    database_directory = tmp_path / "chroma"
    records = _write_embeddings(input_path)

    inserted = store_embeddings(
        input_path=input_path,
        database_directory=database_directory,
        batch_size=2,
    )

    reopened = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(database_directory),
    )
    assert inserted == len(records)
    assert reopened._collection.count() == len(records)
    stored = reopened._collection.get(
        ids=[record["chunk_id"] for record in records],
        include=["metadatas", "documents", "embeddings"],
    )
    assert stored["ids"] == [record["chunk_id"] for record in records]
    assert stored["documents"] == [record["text"] for record in records]
    assert stored["metadatas"] == [record["metadata"] for record in records]
    assert len(stored["embeddings"]) == len(records)
    assert stored["embeddings"][0].tolist() == records[0]["embedding"]


def test_repeated_run_upserts_without_duplicate_ids(tmp_path):
    input_path = tmp_path / "embeddings.jsonl"
    database_directory = tmp_path / "chroma"
    records = _write_embeddings(input_path)

    store_embeddings(input_path, database_directory, batch_size=2)
    inserted_again = store_embeddings(input_path, database_directory, batch_size=2)

    reopened = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(database_directory),
    )
    assert inserted_again == len(records)
    assert reopened._collection.count() == len(records)
