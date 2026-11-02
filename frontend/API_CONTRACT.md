# Backend integration status

The checked-in Python route, schema, and application files are empty in this workspace. The frontend therefore does not assume response shapes, fabricate telemetry, report MCP/RAG connectivity, or send an undocumented incident payload.

## Confirmed from the requested interface

These endpoint paths were explicitly specified in the product requirements, but the backend implementations and Pydantic contracts are not present:

| Purpose | Path | Frontend behavior |
|---|---|---|
| Health | Configurable with `VITE_API_HEALTH_PATH` (default `/health`) | Shows Connected only for a successful 2xx response; otherwise Disconnected |
| Create incident | `POST /api/incidents` | API helper exists; form submission is blocked until the request/response schema is supplied |
| Start investigation | `POST /api/investigations/run` | API helper exists; not called without the backend contract |
| Investigation detail/status | `GET /api/investigations/{id}` | Used by the investigation workspace; polling begins only after a successful response and stops for terminal status |

## Optional data endpoints

Dashboard, incident history, logs, metrics, MCP discovery, RAG status/search, report history, and separate investigation evidence routes were not found in the backend source. The UI displays an explicit unavailable state until the corresponding path below is configured and implemented. No optional path is assumed by default.

| Environment variable | Purpose |
|---|---|
| `VITE_API_DASHBOARD_PATH` | KPI aggregates, trends, service health, severity distribution, recent incidents |
| `VITE_API_INCIDENTS_PATH` | Incident list; should support server-side search, severity, and status filters |
| `VITE_API_LOGS_PATH` | Filtered application logs and timestamps |
| `VITE_API_METRICS_PATH` | Service metrics time series |
| `VITE_API_MCP_STATUS_PATH` | MCP server status, transport, tool schemas, and last-call details |
| `VITE_API_RAG_STATUS_PATH` | Vector-store/collection status and indexed documents |
| `VITE_API_RAG_SEARCH_PATH` | Historical incident retrieval results and optional similarity scores |
| `VITE_API_REPORTS_PATH` | Report history |
| `VITE_API_INVESTIGATION_EVIDENCE_PATH` | Optional standalone investigation evidence route, with `{id}` replaced by the investigation ID |

The backend should document response contracts (including status values, timestamps, evidence, and RCA verification state) before enabling write workflows or interpreting returned records.

## Local preferences

The API base URL, refresh interval, theme, and dashboard chart visibility can be changed in Settings. No API credentials are stored in the browser.
