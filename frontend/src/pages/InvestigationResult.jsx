import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { AlertTriangle, ArrowLeft, FileText, RefreshCw } from "lucide-react";
import PageHeader from "../components/common/PageHeader.jsx";
import DataUnavailable from "../components/common/DataUnavailable.jsx";
import LoadingSkeleton from "../components/common/LoadingSkeleton.jsx";
import StatusBadge from "../components/common/StatusBadge.jsx";
import AgentTimeline from "../components/investigation/AgentTimeline.jsx";
import EvidencePanel from "../components/investigation/EvidencePanel.jsx";
import WorkflowProgress from "../components/investigation/WorkflowProgress.jsx";
import { useInvestigation } from "../hooks/useInvestigation.js";
import { getErrorMessage, getInvestigationEvidence } from "../services/api.js";
import { formatDate, humanize } from "../utils/formatters.js";
import { severityClass } from "../utils/constants.js";

export default function InvestigationResult() {
  const { id } = useParams();
  const { investigation, loading, error, lastUpdated, refresh } = useInvestigation(id);
  const [separateEvidence, setSeparateEvidence] = useState(null);
  const [evidenceError, setEvidenceError] = useState("");
  const incident = investigation?.incident || investigation || {};
  const severity = incident.severity || "—";
  const hasInvestigation = Boolean(investigation);
  const inlineEvidence = investigation?.evidence;
  const hasInlineEvidence = Boolean(inlineEvidence && (typeof inlineEvidence !== "object" || Object.keys(inlineEvidence).length));

  useEffect(() => {
    if (!hasInvestigation || hasInlineEvidence || !import.meta.env.VITE_API_INVESTIGATION_EVIDENCE_PATH) return undefined;
    let active = true;
    setSeparateEvidence(null);
    setEvidenceError("");
    getInvestigationEvidence(id)
      .then((result) => {
        if (active) {
          setSeparateEvidence(result?.evidence || result);
          setEvidenceError("");
        }
      })
      .catch((requestError) => {
        if (active) setEvidenceError(getErrorMessage(requestError));
      });
    return () => { active = false; };
  }, [id, hasInvestigation, hasInlineEvidence]);

  return (
    <main className="page-content result-page">
      <PageHeader
        eyebrow="INVESTIGATION WORKSPACE"
        title={incident.title || "Investigation details"}
        description={incident.service_name || incident.service ? `Service · ${incident.service_name || incident.service}` : `Investigation ${id}`}
        actions={<><button className="button button-secondary" onClick={refresh} disabled={loading}><RefreshCw size={14} className={loading ? "spin" : ""} /> Refresh</button>{investigation && <Link className="button button-primary" to={`/investigations/${id}/report`}><FileText size={14} /> RCA report</Link>}</>}
      />
      {error && <div className="inline-notice notice-warning"><AlertTriangle size={17} /><div><strong>Investigation data unavailable</strong><span>{error}</span></div></div>}
      {loading && !investigation ? <div className="panel loading-panel"><LoadingSkeleton rows={5} /></div> : null}
      {investigation && <>
        <section className="panel incident-overview">
          <div className="incident-overview-title"><div><span className="muted-cell">INCIDENT ID</span><strong>{incident.incident_id || incident.id || id}</strong></div><span className={`severity-pill severity-${severityClass[severity] || "unknown"}`}>{severity}</span></div>
          <div className="incident-meta-grid">
            <div><span>Investigation status</span><StatusBadge status={investigation.status || "unavailable"} /></div>
            <div><span>Service</span><strong>{incident.service_name || incident.service || "—"}</strong></div>
            <div><span>Started at</span><strong>{formatDate(investigation.started_at)}</strong></div>
            <div><span>Completed at</span><strong>{formatDate(investigation.completed_at)}</strong></div>
          </div>
          <div className="updated-note">Last checked {lastUpdated ? formatDate(lastUpdated) : "—"} · Status refreshes every 5 seconds while active</div>
        </section>
        <div className="result-grid">
          <section className="panel">
            <div className="panel-heading"><div><h2>Agent execution</h2><p>Agent states reflect backend responses</p></div><StatusBadge status={investigation.status || "unavailable"} /></div>
            <AgentTimeline agents={investigation.agents || investigation.agent_runs} />
          </section>
          <section className="panel progress-panel">
            <div className="panel-heading"><div><h2>Workflow progress</h2><p>{investigation.progress !== undefined ? `${investigation.progress}% reported by backend` : "Stage states are not inferred"}</p></div></div>
            <WorkflowProgress stages={investigation.stages || investigation.workflow_stages} />
          </section>
        </div>
        {evidenceError && <DataUnavailable title="Separate evidence endpoint unavailable" message={evidenceError} />}
        <EvidencePanel evidence={investigation.evidence || separateEvidence || {}} />
        <div className="result-footer"><span>{investigation.limitation || "Investigation limitations will be included when provided by the backend."}</span><Link to="/incidents"><ArrowLeft size={13} /> Back to incidents</Link></div>
      </>}
      {!investigation && !loading && !error && <DataUnavailable message="No investigation object was returned for this identifier." onRetry={refresh} />}
      {!investigation && error && <DataUnavailable title="Cannot load this investigation" message={error} onRetry={refresh} />}
    </main>
  );
}