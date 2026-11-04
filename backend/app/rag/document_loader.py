"""Load historical incidents as LangChain documents without running a RAG pipeline."""

from __future__ import annotations

import ast
import json
import logging
import os
import tokenize
from dataclasses import dataclass
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import pandas as pd
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
DEFAULT_SOURCE = Path("data/historical_incidents/raw/incidentdb.csv")
REQUIRED_COLUMNS = {"incident_id"}
DESCRIPTION_FIELDS = ("title", "symptom_logs", "root_cause_analysis")
MISSING_STRINGS = {"", "nan", "nat", "none", "null", "<na>"}


class HistoricalIncidentLoaderError(Exception):
    """Base error for historical incident loading."""


class UnsupportedSourceFormatError(HistoricalIncidentLoaderError):
    """Raised when the source extension is not supported."""


class MissingRequiredColumnsError(HistoricalIncidentLoaderError):
    """Raised when a tabular source lacks required columns."""


class EmptyDatasetError(HistoricalIncidentLoaderError):
    """Raised when the selected source contains no records."""


class DatasetReadError(HistoricalIncidentLoaderError):
    """Raised when a source cannot be parsed."""


class InvalidIncidentRecordError(HistoricalIncidentLoaderError):
    """Raised when an individual incident record is invalid."""


@dataclass
class _LoadCounts:
    total_records: int = 0
    loaded_records: int = 0
    invalid_records: int = 0
    duplicate_records: int = 0
    records_with_root_cause: int = 0
    records_with_remediation: int = 0


def _is_missing(value: Any) -> bool:
    """Return whether a scalar represents an unavailable value."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in MISSING_STRINGS
    if isinstance(value, (list, tuple, dict)):
        return False
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    try:
        return bool(result)
    except (TypeError, ValueError):
        return False


def _parse_string_container(value: str) -> Any:
    """Safely parse JSON or Python-literal containers, including NumPy list reprs."""
    candidate = value.strip()
    if not candidate or candidate[0] not in "[{":
        return value

    if candidate.startswith("[") and candidate.endswith("]"):
        try:
            tokens = list(tokenize.generate_tokens(StringIO(candidate).readline))
            string_tokens = [
                ast.literal_eval(token.string)
                for token in tokens
                if token.type == tokenize.STRING
            ]
            has_separator = any(
                token.type == tokenize.OP and token.string == ","
                for token in tokens
            )
            if (
                len(string_tokens) > 1
                and not has_separator
                and all(isinstance(item, str) for item in string_tokens)
            ):
                return string_tokens
        except (IndentationError, SyntaxError, tokenize.TokenError, ValueError):
            pass

    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        pass

    try:
        parsed = ast.literal_eval(candidate)
        if isinstance(parsed, (list, tuple, dict)):
            return parsed
    except (SyntaxError, ValueError):
        pass

    return value


def _normalize_value(value: Any) -> Any:
    """Convert dataset values into standard Python scalars and containers."""
    if _is_missing(value):
        return None

    if isinstance(value, str):
        parsed = _parse_string_container(value)
        if parsed is not value:
            return _normalize_value(parsed)
        return value.strip()

    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()

    if hasattr(value, "tolist") and not isinstance(value, (str, bytes, dict)):
        try:
            return _normalize_value(value.tolist())
        except (AttributeError, TypeError, ValueError):
            pass

    if isinstance(value, Mapping):
        return {
            str(key): _normalize_value(item)
            for key, item in value.items()
            if not _is_missing(item)
        }

    if isinstance(value, (list, tuple)):
        return [
            normalized
            for item in value
            if (normalized := _normalize_value(item)) is not None
        ]

    if hasattr(value, "item"):
        try:
            return _normalize_value(value.item())
        except (AttributeError, TypeError, ValueError):
            pass

    if isinstance(value, (bool, int, float)):
        return value

    return str(value)


def _as_text(value: Any) -> Optional[str]:
    """Render a normalized field for document text, or return None if absent."""
    normalized = _normalize_value(value)
    if normalized is None:
        return None
    if isinstance(normalized, list):
        return ", ".join(_as_text(item) or "" for item in normalized)
    if isinstance(normalized, dict):
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return str(normalized).strip() or None


def _metadata_value(value: Any) -> Optional[Any]:
    """Convert a value to a scalar accepted by vector-store metadata."""
    normalized = _normalize_value(value)
    if normalized is None:
        return None
    if isinstance(normalized, (dict, list)):
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    if isinstance(normalized, (str, int, float, bool)):
        return normalized
    return str(normalized)


def _normalize_date(value: Any) -> Optional[str]:
    """Format dataset dates consistently, including epoch milliseconds in JSONL."""
    normalized = _normalize_value(value)
    if normalized is None:
        return None
    if isinstance(normalized, (int, float)) and not isinstance(normalized, bool):
        try:
            return pd.to_datetime(normalized, unit="ms", utc=True).date().isoformat()
        except (OverflowError, TypeError, ValueError):
            return str(normalized)
    return str(normalized)


class HistoricalIncidentLoader:
    """Load one historical incident export and convert valid records to Documents."""

    def __init__(self, source_path: Optional[os.PathLike] = None) -> None:
        configured_path = source_path or os.environ.get(
            "HISTORICAL_INCIDENTS_PATH", str(DEFAULT_SOURCE)
        )
        self.source_path = self._resolve_path(Path(configured_path))
        self.source_format = self.source_path.suffix.lower().lstrip(".")
        self.documents: List[Document] = []
        self._counts = _LoadCounts()
        self._status = "NOT_STARTED"

        if self.source_format not in {"csv", "jsonl", "parquet"}:
            raise UnsupportedSourceFormatError(
                "Unsupported historical incident format "
                f"'{self.source_path.suffix}'. Supported formats: CSV, JSONL, Parquet."
            )

    @staticmethod
    def _resolve_path(path: Path) -> Path:
        if path.is_absolute():
            return path.resolve()
        if path.parts and path.parts[0].lower() == "backend":
            return (PROJECT_ROOT / path).resolve()
        return (BACKEND_ROOT / path).resolve()

    def _read_records(self) -> Tuple[List[Dict[str, Any]], int, int]:
        """Return parsed rows, total source records, and malformed JSONL rows."""
        if not self.source_path.is_file():
            raise FileNotFoundError(
                f"Historical incident source was not found: {self.source_path}"
            )

        try:
            if self.source_format == "csv":
                frame = pd.read_csv(self.source_path, dtype=object, keep_default_na=False)
                if not len(frame.columns):
                    raise EmptyDatasetError(
                        f"Historical incident source is empty: {self.source_path}"
                    )
                missing_columns = REQUIRED_COLUMNS - set(frame.columns)
                if missing_columns:
                    raise MissingRequiredColumnsError(
                        "Historical incident source is missing required column(s): "
                        + ", ".join(sorted(missing_columns))
                    )
                total = len(frame.index)
                if total == 0:
                    raise EmptyDatasetError(
                        f"Historical incident source contains no records: {self.source_path}"
                    )
                return frame.to_dict(orient="records"), total, 0

            if self.source_format == "parquet":
                frame = pd.read_parquet(self.source_path, engine="pyarrow")
                missing_columns = REQUIRED_COLUMNS - set(frame.columns)
                if missing_columns:
                    raise MissingRequiredColumnsError(
                        "Historical incident source is missing required column(s): "
                        + ", ".join(sorted(missing_columns))
                    )
                total = len(frame.index)
                if total == 0:
                    raise EmptyDatasetError(
                        f"Historical incident source contains no records: {self.source_path}"
                    )
                return frame.to_dict(orient="records"), total, 0

            records: List[Dict[str, Any]] = []
            total = 0
            invalid = 0
            with self.source_path.open("r", encoding="utf-8-sig") as source:
                for line_number, line in enumerate(source, start=1):
                    if not line.strip():
                        continue
                    total += 1
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        invalid += 1
                        logger.warning(
                            "Skipping malformed JSONL record at line %d",
                            line_number,
                        )
                        continue
                    if not isinstance(record, dict):
                        invalid += 1
                        logger.warning(
                            "Skipping non-object JSONL record at line %d",
                            line_number,
                        )
                        continue
                    records.append(record)

            if total == 0:
                raise EmptyDatasetError(
                    f"Historical incident source contains no records: {self.source_path}"
                )
            return records, total, invalid
        except HistoricalIncidentLoaderError:
            raise
        except pd.errors.EmptyDataError as exc:
            raise EmptyDatasetError(
                f"Historical incident source is empty: {self.source_path}"
            ) from exc
        except (OSError, UnicodeError) as exc:
            logger.error(
                "Could not read historical incident source (%s)",
                type(exc).__name__,
            )
            raise DatasetReadError(
                f"Could not read historical incident source '{self.source_path}': {exc}"
            ) from exc
        except Exception as exc:
            logger.error(
                "Could not parse historical incident source format %s (%s)",
                self.source_format.upper(),
                type(exc).__name__,
            )
            raise DatasetReadError(
                f"Could not parse {self.source_format.upper()} source "
                f"'{self.source_path}': {exc}"
            ) from exc

    def validate_record(self, record: Mapping[str, Any]) -> bool:
        """Validate an incident record or raise with its specific reason."""
        if not isinstance(record, Mapping):
            raise InvalidIncidentRecordError("record must be a mapping")

        if _as_text(record.get("incident_id")) is None:
            raise InvalidIncidentRecordError("incident_id is missing or empty")

        if not any(_as_text(record.get(field)) for field in DESCRIPTION_FIELDS):
            raise InvalidIncidentRecordError(
                "record must include a title, symptom_logs, or root_cause_analysis"
            )
        return True

    def _record_to_document(self, record: Mapping[str, Any]) -> Document:
        incident_id = _as_text(record.get("incident_id"))
        if incident_id is None:
            raise InvalidIncidentRecordError("incident_id is missing or empty")

        field_specs: Sequence[Tuple[str, str]] = (
            ("company", "Company"),
            ("date", "Date"),
            ("title", "Incident Title"),
            ("severity", "Severity"),
            ("service_stack", "Service Stack"),
            ("categories", "Categories"),
            ("symptom_logs", "Symptoms and Logs"),
            ("root_cause_analysis", "Root Cause Analysis"),
            ("breaking_config_code", "Breaking Configuration"),
            ("remediation_patch", "Remediation"),
            ("prevention_checklist", "Prevention Checklist"),
            ("source_url", "Source"),
        )
        sections = [f"Incident ID: {incident_id}"]
        for field, label in field_specs:
            value = record.get(field)
            if field == "date":
                value = _normalize_date(value)
            rendered = _as_text(value)
            if rendered:
                sections.append(f"{label}:\n{rendered}")

        has_root_cause = _as_text(record.get("root_cause_analysis")) is not None
        has_remediation = _as_text(record.get("remediation_patch")) is not None

        metadata: Dict[str, Any] = {
            "incident_id": incident_id,
            "document_id": incident_id,
        }
        for field in (
            "company",
            "date",
            "title",
            "severity",
            "service_stack",
            "categories",
            "source_url",
        ):
            value = _normalize_date(record.get(field)) if field == "date" else record.get(field)
            scalar = _metadata_value(value)
            if scalar is not None:
                metadata[field] = scalar

        original_metadata = _metadata_value(record.get("metadata"))
        if original_metadata is not None:
            metadata["metadata"] = original_metadata
        metadata.update(
            {
                "source_file": self.source_path.name,
                "has_root_cause": has_root_cause,
                "has_remediation": has_remediation,
            }
        )
        return Document(page_content="\n\n".join(sections), metadata=metadata)

    def convert_to_documents(
        self, records: Iterable[Mapping[str, Any]]
    ) -> List[Document]:
        """Validate and convert records, tracking invalid and duplicate IDs."""
        self.documents = []
        self._counts = _LoadCounts()
        seen_ids = set()

        for index, record in enumerate(records, start=1):
            self._counts.total_records += 1
            try:
                self.validate_record(record)
                incident_id = _as_text(record.get("incident_id"))
                if incident_id in seen_ids:
                    self._counts.duplicate_records += 1
                    logger.warning(
                        "Skipping duplicate incident record %d from %s",
                        index,
                        self.source_path.name,
                    )
                    continue
                document = self._record_to_document(record)
            except InvalidIncidentRecordError as exc:
                self._counts.invalid_records += 1
                logger.warning(
                    "Skipping invalid incident record %d from %s: %s",
                    index,
                    self.source_path.name,
                    exc,
                )
                continue

            seen_ids.add(incident_id)
            self.documents.append(document)
            self._counts.loaded_records += 1
            self._counts.records_with_root_cause += bool(
                document.metadata["has_root_cause"]
            )
            self._counts.records_with_remediation += bool(
                document.metadata["has_remediation"]
            )

        self._status = (
            "SUCCESS"
            if self._counts.invalid_records == 0
            and self._counts.duplicate_records == 0
            else "PARTIAL"
        )
        return self.documents

    def load(self) -> List[Document]:
        """Load the selected source format and return valid unique incident documents."""
        self.documents = []
        self._counts = _LoadCounts()
        self._status = "FAILED"
        records, total, malformed = self._read_records()
        self._counts.total_records = total
        self._counts.invalid_records = malformed
        documents = self.convert_to_documents(records)
        self._counts.total_records = total
        self._counts.invalid_records += malformed
        if malformed:
            self._status = "PARTIAL"
        logger.info(
            "Loaded %d of %d incident records from %s",
            len(documents),
            total,
            self.source_path.name,
        )
        return documents

    def get_loading_summary(self) -> Dict[str, Any]:
        """Return calculated counts and source details for the most recent load."""
        return {
            "source_filename": self.source_path.name,
            "source_format": self.source_format.upper(),
            "total_records_detected": self._counts.total_records,
            "successfully_loaded": self._counts.loaded_records,
            "invalid_records": self._counts.invalid_records,
            "duplicate_records": self._counts.duplicate_records,
            "records_with_root_cause_information": self._counts.records_with_root_cause,
            "records_without_root_cause_information": (
                self._counts.loaded_records - self._counts.records_with_root_cause
            ),
            "records_with_remediation": self._counts.records_with_remediation,
            "records_without_remediation": (
                self._counts.loaded_records - self._counts.records_with_remediation
            ),
            "loading_status": self._status,
        }

    def format_loading_summary(self) -> str:
        """Render the most recent loading summary for command-line output."""
        summary = self.get_loading_summary()
        return "\n".join(
            (
                "HISTORICAL INCIDENT DOCUMENT LOADING",
                "",
                f"Source: {summary['source_filename']}",
                f"Format: {summary['source_format']}",
                f"Total records: {summary['total_records_detected']}",
                f"Successfully loaded: {summary['successfully_loaded']}",
                f"Invalid records: {summary['invalid_records']}",
                f"Duplicate records: {summary['duplicate_records']}",
                "Records with RCA information "
                "(confirmation not inferred): "
                f"{summary['records_with_root_cause_information']}",
                "Records without RCA information: "
                f"{summary['records_without_root_cause_information']}",
                f"Records with remediation: {summary['records_with_remediation']}",
                "Records without remediation: "
                f"{summary['records_without_remediation']}",
                f"Loading status: {summary['loading_status']}",
            )
        )


def main() -> int:
    """Load the default historical incident CSV and print two document previews."""
    try:
        loader = HistoricalIncidentLoader()
        documents = loader.load()
    except (HistoricalIncidentLoaderError, OSError) as exc:
        logger.error("Historical incident loading failed (%s)", type(exc).__name__)
        print(f"HISTORICAL INCIDENT DOCUMENT LOADING FAILED\n{exc}")
        return 1

    print(loader.format_loading_summary())
    for index, document in enumerate(documents[:2], start=1):
        print(f"\n--- Document preview {index} ---")
        print(f"Metadata: {json.dumps(document.metadata, ensure_ascii=False)}")
        print(document.page_content[:1000])
    return 0 if loader.get_loading_summary()["loading_status"] == "SUCCESS" else 2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    raise SystemExit(main())