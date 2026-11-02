import { Link } from "react-router-dom";
import { ArrowRight, GitBranch } from "lucide-react";
import PageHeader from "../components/common/PageHeader.jsx";
import AgentTimeline from "../components/investigation/AgentTimeline.jsx";
import WorkflowProgress from "../components/investigation/WorkflowProgress.jsx";
import EmptyState from "../components/common/EmptyState.jsx";

export default function AgentWorkflow() {
  return (
    <main className="page-content">
      <PageHeader eyebrow="ORCHESTRATION" title="Agent workflow" description="Follow each specialist agent from supervisor routing through RCA generation." />
      <div className="workflow-intro panel">
        <div className="workflow-intro-icon"><GitBranch size={19} /></div>
        <div><h2>LangGraph investigation pipeline</h2><p>Workflow state and agent execution are displayed only when returned by an investigation API.</p></div>
        <Link className="button button-secondary" to="/incidents">Browse incidents <ArrowRight size={14} /></Link>
      </div>
      <div className="result-grid">
        <section className="panel"><div className="panel-heading"><div><h2>Agent execution timeline</h2><p>Agent order is descriptive; execution status is not inferred.</p></div></div><AgentTimeline /></section>
        <section className="panel progress-panel"><div className="panel-heading"><div><h2>Workflow stages</h2><p>Stages remain unreported until a run is selected.</p></div></div><WorkflowProgress /></section>
      </div>
      <section className="panel workflow-empty">
        <EmptyState title="Select an investigation to inspect its run" description="Open an investigation from the incident list. Agent status, timestamps, and evidence are read from the backend response." />
        <Link className="button button-primary" to="/investigations/new">Start with an incident <ArrowRight size={14} /></Link>
      </section>
    </main>
  );
}
