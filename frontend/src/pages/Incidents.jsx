import { useEffect, useMemo, useState } from "react";
import { Search, SlidersHorizontal } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import PageHeader from "../components/common/PageHeader.jsx";
import DataUnavailable from "../components/common/DataUnavailable.jsx";
import { getErrorMessage, getIncidents } from "../services/api.js";
import { formatDate } from "../utils/formatters.js";
import { severityClass } from "../utils/constants.js";

export default function Incidents() {
  const location = useLocation();
  const initialQuery = new URLSearchParams(location.search).get("search") || "";
  const [query, setQuery] = useState(initialQuery);
  const [severity, setSeverity] = useState("all");
  const [status, setStatus] = useState("all");
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");

  async function load(searchTerm = query) {
    try {
      const response = await getIncidents({ search: searchTerm || undefined, severity: severity === "all" ? undefined : severity, status: status === "all" ? undefined : status });
      setItems((Array.isArray(response) ? response : Array.isArray(response?.incidents) ? response.incidents : []).filter(Boolean));
      setError("");
    } catch (requestError) {
      setItems([]);
      setError(getErrorMessage(requestError));
    }
  }

  useEffect(() => {
    const searchTerm = new URLSearchParams(location.search).get("search") || "";
    setQuery(searchTerm);
    load(searchTerm);
  }, [location.search]);
  const visible = useMemo(() => items.filter((item) =>
    (!query || `${item.title || ""} ${item.service_name || ""} ${item.incident_id || ""}`.toLowerCase().includes(query.toLowerCase()))
    && (severity === "all" || item.severity === severity)
    && (status === "all" || String(item.status).toLowerCase() === status),
  ), [items, query, severity, status]);

  return (
    <main className="page-content">
      <PageHeader eyebrow="INCIDENT MANAGEMENT" title="Incidents" description="Review incident history and track active investigations." actions={<Link className="button button-primary" to="/investigations/new">New investigation</Link>} />
      <section className="panel list-panel">
        <form className="list-toolbar" onSubmit={(event) => { event.preventDefault(); load(); }}>
          <label className="search-field"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by incident, service, or ID" /></label>
          <label className="filter-select"><SlidersHorizontal size={14} /><select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="all">All severities</option><option>SEV-1</option><option>SEV-2</option><option>SEV-3</option><option>SEV-4</option></select></label>
          <label className="filter-select"><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All statuses</option><option value="active">Active</option><option value="resolved">Resolved</option></select></label>
          <button type="submit" className="button button-secondary">Apply</button>
        </form>
        {error ? <DataUnavailable message={error} onRetry={load} /> : (
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>Incident</th><th>Service</th><th>Severity</th><th>Status</th><th>Created</th><th>Investigation</th></tr></thead>
              <tbody>{visible.map((item, index) => <tr key={item.id || item.incident_id || index}>
                <td><strong>{item.title || item.incident_id || "Untitled incident"}</strong><span className="muted-cell">{item.incident_id || item.id || "—"}</span></td>
                <td>{item.service_name || item.service || "—"}</td>
                <td><span className={`severity-pill severity-${severityClass[item.severity] || "unknown"}`}>{item.severity || "—"}</span></td>
                <td>{item.status || "—"}</td><td>{formatDate(item.created_at)}</td>
                <td><Link className="text-link" to={`/investigations/${item.investigation_id || item.id}`}>Open details →</Link></td>
              </tr>)}</tbody>
            </table>
            {!visible.length && <div className="empty-table">{items.length ? "No incidents match the selected filters." : "No incidents returned by the configured API."}</div>}
          </div>
        )}
      </section>
    </main>
  );
}
