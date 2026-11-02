import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import PageHeader from "../components/common/PageHeader.jsx";
import DataUnavailable from "../components/common/DataUnavailable.jsx";
import LoadingSkeleton from "../components/common/LoadingSkeleton.jsx";
import RCAReport from "../components/investigation/RCAReport.jsx";
import { useInvestigation } from "../hooks/useInvestigation.js";

export default function ReportDetail() {
  const { id } = useParams();
  const { investigation, loading, error, refresh } = useInvestigation(id);
  const incident = investigation?.incident || investigation;
  const report = investigation?.report || investigation?.rca_report;
  return (
    <main className="page-content">
      <PageHeader eyebrow="RCA REPORT" title={incident?.title || "Investigation report"} description={`Incident ${id}`} actions={<Link className="button button-secondary" to={`/investigations/${id}`}><ArrowLeft size={14} /> Investigation</Link>} />
      {loading && !investigation && <div className="panel loading-panel"><LoadingSkeleton rows={5} /></div>}
      {error && <DataUnavailable title="Report data unavailable" message={error} onRetry={refresh} />}
      {investigation && <RCAReport report={report} incident={incident} />}
    </main>
  );
}
