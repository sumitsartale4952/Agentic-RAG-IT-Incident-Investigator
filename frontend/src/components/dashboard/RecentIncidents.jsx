import { ArrowUpRight } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import EmptyState from "../common/EmptyState.jsx";
import { formatDate } from "../../utils/formatters.js";
import { severityClass } from "../../utils/constants.js";

export default function RecentIncidents({ incidents = [] }) {
  const [severity, setSeverity] = useState("all");
  const [status, setStatus] = useState("all");
  const safeIncidents = Array.isArray(incidents) ? incidents : [];
  const visible = useMemo(() => safeIncidents.filter((incident) => incident && (
    (severity === "all" || incident.severity === severity)
    && (status === "all" || String(incident.status).toLowerCase() === status)
  )), [safeIncidents, severity, status]);

  return (
    <section className="panel incidents-panel">
      <div className="panel-heading incidents-heading">
        <div><h2>Recent incidents</h2><p>Latest activity across your services</p></div>
        <Link className="text-link" to="/incidents">All incidents <ArrowUpRight size={14} /></Link>
      </div>
      <div className="table-filters">
        <label className="filter-select"><span className="sr-only">Filter by severity</span><select value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="all">All severities</option><option>SEV-1</option><option>SEV-2</option><option>SEV-3</option><option>SEV-4</option></select></label>
        <label className="filter-select"><span className="sr-only">Filter by status</span><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All statuses</option><option value="active">Active</option><option value="resolved">Resolved</option></select></label>
        <span className="table-result-count">{safeIncidents.length} records</span>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead><tr><th>Incident</th><th>Service</th><th>Severity</th><th>Status</th><th>Created</th><th /></tr></thead>
          <tbody>
            {visible.map((incident, index) => (
              <tr key={incident.id || incident.incident_id || index}>
                <td><Link className="incident-title-cell" to={`/investigations/${incident.investigation_id || incident.id}`}>{incident.title || incident.incident_id || "Untitled incident"}</Link><span className="muted-cell">{incident.incident_id || incident.id || "—"}</span></td>
                <td><span className="service-cell"><i />{incident.service_name || incident.service || "—"}</span></td>
                <td><span className={`severity-pill severity-${severityClass[incident.severity] || "unknown"}`}>{incident.severity || "—"}</span></td>
                <td><span className="table-status">{incident.status || "—"}</span></td>
                <td>{formatDate(incident.created_at)}</td>
                <td><Link className="icon-button table-action" to={`/investigations/${incident.investigation_id || incident.id}`} aria-label="View incident"><ArrowUpRight size={15} /></Link></td>
              </tr>
            ))}
          </tbody>
        </table>
        {!visible.length && <EmptyState compact icon={safeIncidents.length ? "search" : "database"} title={safeIncidents.length ? "No matching incidents" : "No incidents returned"} description={safeIncidents.length ? "Try changing the severity or status filters." : "Incident history appears when a dashboard or incident-list API is configured."} />}
      </div>
    </section>
  );
}
