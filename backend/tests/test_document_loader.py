import json
from pathlib import Path

import pandas as pd
import pytest
from langchain_core.documents import Document

from app.rag.document_loader import (
    DatasetReadError,
    EmptyDatasetError,
    HistoricalIncidentLoader,
    MissingRequiredColumnsError,
    UnsupportedSourceFormatError,
)


@pytest.fixture
def incident_record():
    return {
        "incident_id": "INC-TEST-001",
        "company": "Example Co",
        "date": "2026-10-01",
        "title": "API latency",
        "severity": "SEV-2",
        "service_stack": ["gateway", "payments"],
        "categories": ["LATENCY", "ERROR_RATE"],
        "symptom_logs": "Request latency increased.",
        "root_cause_analysis": "An upstream dependency was throttling.",
        "breaking_config_code": None,
        "remediation_patch": "Scaled healthy replicas.",
        "prevention_checklist": ["Add capacity alerts", "Test failover"],
        "source_url": "https://example.test/incident/1",
        "metadata": {"source_id": "record-1", "state": "resolved"},
    }


@pytest.fixture
def write_csv(tmp_path):
    def _write(path: Path, records, columns=None):
        frame = pd.DataFrame(records, columns=columns)
        frame.to_csv(path, index=False)
        return path

    return _write


def test_load_csv_and_convert_document(tmp_path, incident_record, write_csv):
    path = write_csv(tmp_path / "incidents.csv", [incident_record])

    loader = HistoricalIncidentLoader(path)
    documents = loader.load()

    assert len(documents) == 1
    assert isinstance(documents[0], Document)
    assert "Incident ID: INC-TEST-001" in documents[0].page_content
    assert "Incident Title:\nAPI latency" in documents[0].page_content
    assert "Root Cause Analysis:\n" in documents[0].page_content
    assert "An upstream dependency was throttling." in documents[0].page_content
    assert documents[0].metadata["source_file"] == "incidents.csv"
    assert documents[0].metadata["document_id"] == "INC-TEST-001"
    assert loader.get_loading_summary()["loading_status"] == "SUCCESS"


def test_load_jsonl(tmp_path, incident_record):
    path = tmp_path / "incidents.jsonl"
    path.write_text(json.dumps(incident_record) + "\n", encoding="utf-8")

    loader = HistoricalIncidentLoader(path)

    assert len(loader.load()) == 1
    assert loader.get_loading_summary()["total_records_detected"] == 1


def test_load_parquet(tmp_path, incident_record):
    path = tmp_path / "incidents.parquet"
    pd.DataFrame([incident_record]).to_parquet(path, engine="pyarrow", index=False)

    loader = HistoricalIncidentLoader(path)

    assert len(loader.load()) == 1
    assert loader.documents[0].metadata["incident_id"] == "INC-TEST-001"


def test_preserves_scalar_metadata_and_serializes_complex_values(
    tmp_path, incident_record, write_csv
):
    path = write_csv(tmp_path / "incidents.csv", [incident_record])
    document = HistoricalIncidentLoader(path).load()[0]

    assert document.metadata["company"] == "Example Co"
    assert document.metadata["date"] == "2026-10-01"
    assert json.loads(document.metadata["service_stack"]) == ["gateway", "payments"]
    assert json.loads(document.metadata["categories"]) == ["LATENCY", "ERROR_RATE"]
    assert json.loads(document.metadata["metadata"]) == {
        "source_id": "record-1",
        "state": "resolved",
    }
    assert document.metadata["has_root_cause"] is True
    assert document.metadata["has_remediation"] is True


def test_document_id_is_stable_and_metadata_is_vector_store_compatible(
    tmp_path, incident_record, write_csv
):
    path = write_csv(tmp_path / "incidents.csv", [incident_record])

    first = HistoricalIncidentLoader(path).load()[0]
    second = HistoricalIncidentLoader(path).load()[0]

    assert first.metadata["document_id"] == second.metadata["document_id"]
    assert first.metadata["document_id"] == first.metadata["incident_id"]
    assert all(
        isinstance(value, (str, int, float, bool))
        for value in first.metadata.values()
    )


def test_unicode_and_optional_metadata_are_preserved(tmp_path, write_csv):
    path = write_csv(
        tmp_path / "unicode.csv",
        [{
            "incident_id": "INC-UNICODE",
            "title": "Café API failure – 東京",
            "symptom_logs": "Réponse indisponible 🚨",
        }],
    )

    document = HistoricalIncidentLoader(path).load()[0]

    assert "Café API failure – 東京" in document.page_content
    assert "Réponse indisponible 🚨" in document.page_content
    assert "company" not in document.metadata
    assert "source_url" not in document.metadata


@pytest.mark.parametrize(
    ("field", "expected_flag", "section"),
    [
        ("root_cause_analysis", "has_root_cause", "Root Cause Analysis:"),
        ("remediation_patch", "has_remediation", "Remediation:"),
    ],
)
def test_missing_root_cause_or_remediation_is_explicit(
    tmp_path, incident_record, write_csv, field, expected_flag, section
):
    incident_record[field] = None
    document = HistoricalIncidentLoader(
        write_csv(tmp_path / f"{field}.csv", [incident_record])
    ).load()[0]

    assert document.metadata[expected_flag] is False
    assert section not in document.page_content
    summary = HistoricalIncidentLoader(
        write_csv(tmp_path / f"{field}-summary.csv", [incident_record])
    )
    summary.load()
    counts = summary.get_loading_summary()
    if expected_flag == "has_root_cause":
        assert counts["records_without_root_cause_information"] == 1
    else:
        assert counts["records_without_remediation"] == 1


def test_invalid_records_are_counted_and_logged(tmp_path, incident_record, caplog):
    path = tmp_path / "incidents.jsonl"
    invalid = {"incident_id": "INC-BAD", "company": "No description"}
    path.write_text(
        json.dumps(invalid) + "\n" + json.dumps(incident_record) + "\n", encoding="utf-8"
    )

    loader = HistoricalIncidentLoader(path)
    documents = loader.load()

    summary = loader.get_loading_summary()
    assert len(documents) == 1
    assert summary["total_records_detected"] == 2
    assert summary["invalid_records"] == 1
    assert summary["loading_status"] == "PARTIAL"
    assert "Skipping invalid incident record" in caplog.text


def test_missing_incident_id_row_is_invalid(tmp_path, incident_record):
    path = tmp_path / "missing-id.jsonl"
    invalid = dict(incident_record)
    invalid.pop("incident_id")
    path.write_text(json.dumps(invalid) + "\n", encoding="utf-8")

    loader = HistoricalIncidentLoader(path)

    assert loader.load() == []
    assert loader.get_loading_summary()["invalid_records"] == 1


def test_malformed_jsonl_records_are_counted(tmp_path, incident_record):
    path = tmp_path / "incidents.jsonl"
    path.write_text(
        "{not json}\n" + json.dumps(incident_record) + "\n", encoding="utf-8"
    )

    loader = HistoricalIncidentLoader(path)

    assert len(loader.load()) == 1
    assert loader.get_loading_summary()["invalid_records"] == 1
    assert loader.get_loading_summary()["loading_status"] == "PARTIAL"


def test_duplicate_ids_are_removed_and_counted(
    tmp_path, incident_record, write_csv, caplog
):
    duplicate = dict(incident_record, title="Different content with same ID")
    path = write_csv(tmp_path / "incidents.csv", [incident_record, duplicate])

    loader = HistoricalIncidentLoader(path)

    assert len(loader.load()) == 1
    summary = loader.get_loading_summary()
    assert summary["duplicate_records"] == 1
    assert summary["total_records_detected"] == 2
    assert summary["loading_status"] == "PARTIAL"
    assert "INC-TEST-001" not in caplog.text


def test_csv_invalid_rows_are_counted_without_logging_record_data(
    tmp_path, incident_record, write_csv, caplog
):
    invalid = {
        "incident_id": "INC-SENSITIVE",
        "company": "Sensitive customer",
        "title": "",
        "symptom_logs": "",
        "root_cause_analysis": "",
    }
    path = write_csv(tmp_path / "incidents.csv", [incident_record, invalid])

    loader = HistoricalIncidentLoader(path)
    documents = loader.load()

    assert len(documents) == 1
    assert loader.get_loading_summary()["invalid_records"] == 1
    assert "INC-SENSITIVE" not in caplog.text
    assert "Sensitive customer" not in caplog.text


def test_empty_dataset_raises(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("incident_id,title\n", encoding="utf-8")

    with pytest.raises(EmptyDatasetError):
        HistoricalIncidentLoader(path).load()


def test_zero_byte_dataset_raises_empty_error(tmp_path):
    path = tmp_path / "zero-byte.csv"
    path.write_bytes(b"")

    with pytest.raises(EmptyDatasetError):
        HistoricalIncidentLoader(path).load()


def test_unsupported_extension_raises(tmp_path):
    path = tmp_path / "incidents.txt"
    path.write_text("not a supported dataset", encoding="utf-8")

    with pytest.raises(UnsupportedSourceFormatError):
        HistoricalIncidentLoader(path)


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        HistoricalIncidentLoader(tmp_path / "missing.csv").load()


def test_missing_required_column_raises(tmp_path, write_csv):
    path = write_csv(
        tmp_path / "missing_id.csv",
        [{"title": "Incident without identifier"}],
        columns=["title"],
    )

    with pytest.raises(MissingRequiredColumnsError, match="incident_id"):
        HistoricalIncidentLoader(path).load()


def test_unreadable_parquet_raises(tmp_path):
    path = tmp_path / "unreadable.parquet"
    path.write_text("not parquet content", encoding="utf-8")

    with pytest.raises(DatasetReadError, match="Could not parse PARQUET"):
        HistoricalIncidentLoader(path).load()


def test_numpy_style_serialized_lists_are_parsed(tmp_path, write_csv):
    path = write_csv(
        tmp_path / "serialized.csv",
        [{
            "incident_id": "INC-1",
            "title": "Latency",
            "service_stack": "['gateway' 'payments']",
            "categories": "['TIMEOUT' 'LATENCY']",
        }],
    )

    document = HistoricalIncidentLoader(path).load()[0]

    assert json.loads(document.metadata["service_stack"]) == ["gateway", "payments"]
    assert json.loads(document.metadata["categories"]) == ["TIMEOUT", "LATENCY"]


def test_dictionary_field_is_rendered_as_json_in_page_content(tmp_path, write_csv):
    path = write_csv(
        tmp_path / "structured.csv",
        [{
            "incident_id": "INC-STRUCTURED",
            "symptom_logs": {"status": 503, "message": "Service unavailable"},
        }],
    )

    document = HistoricalIncidentLoader(path).load()[0]

    assert (
        'Symptoms and Logs:\n{"message": "Service unavailable", "status": 503}'
        in document.page_content
    )


def test_default_source_path_uses_backend_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HISTORICAL_INCIDENTS_PATH", raising=False)

    loader = HistoricalIncidentLoader()

    assert loader.source_path == (
        Path(__file__).resolve().parents[1]
        / "data"
        / "historical_incidents"
        / "raw"
        / "incidentdb.csv"
    ).resolve()


def test_jsonl_malformed_only_sets_partial_failure(tmp_path):
    path = tmp_path / "invalid.jsonl"
    path.write_text("{bad json}\n", encoding="utf-8")

    loader = HistoricalIncidentLoader(path)
    assert loader.load() == []
    summary = loader.get_loading_summary()
    assert summary["total_records_detected"] == 1
    assert summary["invalid_records"] == 1
    assert summary["loading_status"] == "PARTIAL"
