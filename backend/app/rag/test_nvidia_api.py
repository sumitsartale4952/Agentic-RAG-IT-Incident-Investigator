"""Verify connectivity to the configured NVIDIA NIM chat model."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA

BACKEND_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ENV_PATH = BACKEND_ROOT / ".env"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
TEST_MESSAGE = "Hello! Reply with exactly: NVIDIA API connection successful."


def _http_status(error: Exception) -> Any:
    """Return an HTTP status code when the provider exception exposes one."""
    for candidate in (error, getattr(error, "response", None)):
        status = getattr(candidate, "status_code", None)
        if status is not None:
            return status
    return None


def _safe_error_message(error: Exception, api_key: str) -> str:
    """Avoid printing credentials if an SDK exception includes request details."""
    message = str(error)
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    message = re.sub(r"(?i)\bnvapi-[A-Za-z0-9_-]+", "[REDACTED]", message)
    message = re.sub(
        r"(?i)(authorization:\s*bearer\s+)[^\s,;]+",
        r"\1[REDACTED]",
        message,
    )
    return message or type(error).__name__


def _response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            item if isinstance(item, str) else item.get("text", "")
            for item in content
            if isinstance(item, (str, dict))
        ]
        return "".join(part for part in parts if isinstance(part, str))
    return str(content)


def main() -> int:
    load_dotenv(BACKEND_ENV_PATH, override=False)
    model = os.getenv("NVIDIA_MODEL")
    api_key = os.getenv("NVIDIA_API_KEY")
    if not model or not api_key:
        print("API connection: FAILED")
        print("Error message: NVIDIA_MODEL or NVIDIA_API_KEY is not configured.")
        return 1

    started_at = time.perf_counter()
    try:
        chat = ChatNVIDIA(
            model=model,
            api_key=api_key,
            base_url=NVIDIA_BASE_URL,
            temperature=0.1,
            max_completion_tokens=32,
        )
        response = chat.invoke(TEST_MESSAGE)
    except Exception as exc:
        elapsed = time.perf_counter() - started_at
        print("API connection: FAILED")
        status = _http_status(exc)
        if status is not None:
            print(f"HTTP status code: {status}")
        print(f"Error message: {_safe_error_message(exc, api_key)}")
        print(f"Response time: {elapsed:.2f} seconds")
        return 1

    elapsed = time.perf_counter() - started_at
    print("API connection: SUCCESS")
    print(f"Model name: {model}")
    print(f"Response from NVIDIA: {_response_text(response)}")
    print(f"Response time: {elapsed:.2f} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
