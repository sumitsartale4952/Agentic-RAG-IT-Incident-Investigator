import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Link } from "react-router-dom";
import PageHeader from "../components/common/PageHeader.jsx";
import DataUnavailable from "../components/common/DataUnavailable.jsx";
import { getErrorMessage, getReports } from "../services/api.js";
import { formatDate } from "../utils/formatters.js";
import { severityClass } from "../utils/constants.js";

export default function Reports() {
  const [reports, setReports] = useState([]);
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState("all");
  const [error, setError] = useState("");
  async function load() {
    try {
      const response = await getReports();
      setReports((Array.isArray(response) ? response : Array.isArray(response?.reports) ? response.reports : []).filter(Boolean));
      setError("");
    } catch (requestError) {
      setReports([]);
      setError(getErrorMessage(requestError));
    }
  }
  useEffect(() => { load(); }, []);
  const filtered = useMemo(() => reports.filter((report) =>
    (!query || `${report.report_id || ""} ${report.incident_id || ""} ${report.service || ""}`.toLowerCase().includes(query.toLowerCase()))
    && (severity === "all" || report.severity === severity),
  ), [reports, query, severity]);

  return (
    <main className="page-content">
      <PageHeader eyebrow="KNOWLEDGE & RCA" title="Reports" description="Browse generated incident reports and root-cause analyses." />
      <section className="panel list-panel">
        <div className="list-toolbar"><label className="search-field"><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search reports" /></label><select className="filter-select" value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="all">All severities</option><option>SEV-1</option><option>SEV-2</option><option>SEV-3</option><option>SEV-4</option></select></div>
        {error ? <DataUnavailable message={error} onRetry={load} /> : <div className="table-scroll"><table className="data-table"><thead><tr><th>Report ID</th><th>Incident ID</th><th>Service</th><th>Severity</th><th>RCA status</th><th>Generated</th><th /></tr></thead><tbody>
          {filtered.map((report, index) => <tr key={report.report_id || index}><td>{report.report_id || "—"}</td><td>{report.incident_id || "—"}</td><td>{report.service || report.service_name || "—"}</td><td><span className={`severity-pill severity-${severityClass[report.severity] || "unknown"}`}>{report.severity || "—"}</span></td><td>{report.rca_status || report.status || "—"}</td><td>{formatDate(report.generated_at)}</td><td>{(report.investigation_id || report.incident_id) ? <Link className="text-link" to={`/investigations/${report.investigation_id || report.incident_id}/report`}>View report →</Link> : "ID unavailable"}</td></tr>)}
        </tbody></table>{!filtered.length && <div className="empty-table">No reports returned by the configured API.</div>}</div>}
      </section>
    </main>
  );
}
