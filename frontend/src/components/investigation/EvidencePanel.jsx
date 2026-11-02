import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, Search } from "lucide-react";
import ChartCard from "../dashboard/ChartCard.jsx";
import EmptyState from "../common/EmptyState.jsx";
import { formatDate } from "../../utils/formatters.js";

const tabs = ["Logs", "Metrics", "Historical incidents"];

function LogsEvidence({ logs = [] }) {
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("all");
  const [expanded, setExpanded] = useState(null);
  const safeLogs = logs.filter(Boolean);
  const filtered = useMemo(() => safeLogs.filter((log) =>
    (!query || String(log.message || "").toLowerCase().includes(query.toLowerCase()))
    && (level === "all" || String(log.level || "").toLowerCase() === level),
  ), [safeLogs, query, level]);
  if (!safeLogs.length) return <EmptyState compact title="No log evidence returned" description="Evidence will display here if included in the investigation response." />;
  return (
    <>
      <div className="evidence-filters"><label className="search-field"><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search log messages" /></label><select value={level} onChange={(event) => setLevel(event.target.value)}><option value="all">All levels</option><option value="error">Error</option><option value="warning">Warning</option><option value="info">Info</option></select></div>
      <div className="table-scroll"><table className="data-table evidence-table"><thead><tr><th>Time</th><th>Level</th><th>Service</th><th>Message</th></tr></thead><tbody>
        {filtered.map((log, index) => <><tr key={log.id || index} onClick={() => setExpanded(expanded === index ? null : index)} className="expandable-row"><td>{formatDate(log.timestamp)}</td><td><span className={`log-level level-${String(log.level || "unknown").toLowerCase()}`}>{log.level || "—"}</span></td><td>{log.service || log.service_name || "—"}</td><td className="log-message">{log.message || "—"}{expanded === index ? <ChevronUp size={13} /> : <ChevronDown size={13} />}</td></tr>{expanded === index && <tr key={`detail-${index}`} className="expanded-detail"><td colSpan="4"><pre>{log.raw || log.message || JSON.stringify(log, null, 2)}</pre></td></tr>}</>)}
      </tbody></table></div>
    </>
  );
}

function MetricsEvidence({ metrics = [] }) {
  const safeMetrics = metrics.filter(Boolean);
  if (!safeMetrics.length) return <EmptyState compact title="No metric evidence returned" description="Time-series evidence will show up when supplied by the backend." />;
  const hasCpu = safeMetrics.some((row) => row.cpu_usage_percent !== undefined);
  return (
    <div className="evidence-metrics">
      {hasCpu && <ChartCard title="CPU utilization" subtitle="Investigation evidence" data={safeMetrics} dataKey="cpu_usage_percent" xKey="timestamp" type="line" />}
      <div className="table-scroll"><table className="data-table"><thead><tr><th>Timestamp</th><th>CPU</th><th>Memory</th><th>Latency</th><th>Errors</th></tr></thead><tbody>
        {safeMetrics.map((metric, index) => <tr key={metric.timestamp || index}><td>{formatDate(metric.timestamp)}</td><td>{metric.cpu_usage_percent ?? "—"}</td><td>{metric.memory_usage_percent ?? "—"}</td><td>{metric.avg_latency_ms ?? metric.api_latency_ms ?? "—"}</td><td>{metric.error_count ?? "—"}</td></tr>)}
      </tbody></table></div>
    </div>
  );
}

function HistoricalEvidence({ documents = [] }) {
  const [open, setOpen] = useState(null);
  const safeDocuments = documents.filter(Boolean);
  if (!safeDocuments.length) return <EmptyState compact title="No historical matches returned" description="Retrieved documents will appear here with similarity only when the backend provides it." />;
  return <div className="historical-list">{safeDocuments.map((doc, index) => <article className="historical-item" key={doc.id || doc.incident_id || index}>
    <button className="historical-toggle" onClick={() => setOpen(open === index ? null : index)}>
      <span><strong>{doc.title || doc.incident_id || "Historical incident"}</strong><small>{doc.service || doc.service_name || "—"} · {doc.severity || "Severity unavailable"}</small></span>
      <span className="historical-score">{doc.similarity_score ?? doc.score ?? "—"}</span>
      {open === index ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
    </button>
    {open === index && <div className="historical-preview"><p>{doc.snippet || doc.text || doc.retrieved_text || "No snippet provided."}</p>{doc.root_cause && <div><b>Root cause from source</b><span>{doc.root_cause}</span></div>}</div>}
  </article>)}</div>;
}

export default function EvidencePanel({ evidence = {} }) {
  const [active, setActive] = useState(tabs[0]);
  const logs = Array.isArray(evidence.logs) ? evidence.logs : [];
  const metrics = Array.isArray(evidence.metrics) ? evidence.metrics : [];
  const documents = Array.isArray(evidence.historical_incidents) ? evidence.historical_incidents : Array.isArray(evidence.documents) ? evidence.documents : [];
  return (
    <section className="panel evidence-panel">
      <div className="panel-heading"><div><h2>Evidence explorer</h2><p>Signals returned by this investigation only</p></div><span className="evidence-count">{logs.length + metrics.length + documents.length} items</span></div>
      <div className="evidence-tabs" role="tablist">{tabs.map((tab) => <button key={tab} role="tab" aria-selected={active === tab} className={active === tab ? "evidence-tab active" : "evidence-tab"} onClick={() => setActive(tab)}>{tab}</button>)}</div>
      <div className="evidence-content">
        {active === "Logs" && <LogsEvidence logs={logs} />}
        {active === "Metrics" && <MetricsEvidence metrics={metrics} />}
        {active === "Historical incidents" && <HistoricalEvidence documents={documents} />}
      </div>
    </section>
  );
}
