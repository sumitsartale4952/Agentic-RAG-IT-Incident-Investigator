import { AlertTriangle, CheckCircle2, Copy, Printer } from "lucide-react";
import { useState } from "react";
import EmptyState from "../common/EmptyState.jsx";
import { formatDate } from "../../utils/formatters.js";

const reportSections = [
  ["summary", "Incident summary"],
  ["impact", "Severity and impact"],
  ["timeline", "Investigation timeline"],
  ["log_evidence", "Log evidence"],
  ["metrics_evidence", "Metrics evidence"],
  ["historical_incidents", "Retrieved historical incidents"],
  ["confirmed_facts", "Confirmed facts"],
  ["supporting_evidence", "Supporting evidence"],
  ["probable_causes", "Probable causes"],
  ["unverified_hypotheses", "Unverified hypotheses"],
  ["root_cause_evidence", "Root cause evidence"],
  ["missing_evidence", "Missing evidence"],
  ["recommended_actions", "Recommended actions"],
  ["verification_status", "Verification status"],
  ["limitations", "Investigation limitations"],
];

function renderContent(value) {
  if (value === null || value === undefined || value === "") return "Not provided by the backend.";
  if (Array.isArray(value)) return value.length ? <ul>{value.map((item, index) => <li key={index}>{typeof item === "string" ? item : item ? item.description || item.message || JSON.stringify(item) : "—"}</li>)}</ul> : "No evidence returned.";
  if (typeof value === "object") return <pre className="report-json">{JSON.stringify(value, null, 2)}</pre>;
  return String(value);
}

export default function RCAReport({ report, incident }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  const rootCause = report?.probable_root_cause || report?.root_cause;
  const verification = String(report?.root_cause_status || report?.verification_status || "").toLowerCase();
  const isConfirmed = verification === "confirmed" || verification === "verified";
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify({ incident, report }, null, 2));
      setCopied(true);
      setCopyError("");
      window.setTimeout(() => setCopied(false), 1800);
    } catch (error) {
      setCopyError(`Could not copy report: ${error.message}`);
    }
  };

  if (!report) return <EmptyState title="No RCA report returned" description="A report appears when the backend includes it in the investigation response." />;

  return (
    <article className="panel rca-report">
      <header className="report-header">
        <div><div className="eyebrow">INCIDENT ANALYSIS REPORT</div><h2>{incident?.title || "Investigation report"}</h2><p>{incident?.incident_id || incident?.id || "Incident ID unavailable"} · {incident?.service_name || incident?.service || "Service unavailable"} · Generated {formatDate(report.generated_at)}</p></div>
        <div className="heading-actions no-print"><button className="button button-secondary" onClick={onCopy}><Copy size={14} />{copied ? "Copied" : "Copy report"}</button><button className="button button-secondary" onClick={() => window.print()}><Printer size={14} />Print / PDF</button></div>
      </header>
      {copyError && <p className="field-error no-print">{copyError}</p>}
      <section className={`root-cause-card ${isConfirmed ? "root-cause-confirmed" : "root-cause-unverified"}`}>
        <div className="root-cause-heading">{isConfirmed ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}<strong>{isConfirmed ? "Confirmed root cause" : rootCause ? "Probable cause · unverified" : "Root cause inconclusive — additional evidence required."}</strong></div>
        {rootCause && <div className="root-cause-content">{renderContent(rootCause)}</div>}
        {!isConfirmed && rootCause && <small>The backend has not marked this cause as verified.</small>}
      </section>
      <div className="report-facts">
        <section><span>Incident severity</span><div>{renderContent(incident?.severity)}</div></section>
        <section><span>Investigation status</span><div>{renderContent(report.status)}</div></section>
        <section><span>Impact</span><div>{renderContent(report.impact_summary)}</div></section>
      </div>
      <div className="report-sections">
        {reportSections.map(([key, title]) => <section className="report-section" key={key}><h3>{title}</h3><div>{renderContent(report[key])}</div></section>)}
      </div>
    </article>
  );
}
