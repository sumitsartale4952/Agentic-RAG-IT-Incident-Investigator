import { Activity, Check, Circle, FileSearch, GitBranch, LoaderCircle, Radio, X } from "lucide-react";
import { agentNames } from "../../utils/constants.js";
import { formatDate, humanize } from "../../utils/formatters.js";

const icons = [GitBranch, FileSearch, Radio, Activity];

function findAgent(agents, name) {
  if (!Array.isArray(agents)) return null;
  return agents.find((agent) => agent && String(agent.name || agent.agent_name || "").toLowerCase() === name.toLowerCase());
}

function AgentIcon({ status, icon: Icon }) {
  if (status === "completed" || status === "complete") return <Check size={16} />;
  if (status === "running") return <LoaderCircle size={16} className="spin" />;
  if (status === "failed" || status === "error") return <X size={16} />;
  return <Icon size={16} />;
}

export default function AgentTimeline({ agents }) {
  return (
    <div className="agent-timeline">
      {agentNames.map((name, index) => {
        const agent = findAgent(agents, name);
        const status = agent?.status ? String(agent.status).toLowerCase() : "unavailable";
        return (
          <div className="agent-step" key={name}>
            <div className={`agent-step-icon agent-${status}`}><AgentIcon status={status} icon={icons[index]} /></div>
            <div className="agent-step-content">
              <div className="agent-step-head"><strong>{name}</strong><span className="agent-status-text">{humanize(status)}</span></div>
              <p>{agent?.activity || agent?.description || "Execution details will appear when reported by the backend."}</p>
              <div className="agent-step-meta">
                {agent?.started_at && <span>Started {formatDate(agent.started_at)}</span>}
                {agent?.completed_at && <span>Completed {formatDate(agent.completed_at)}</span>}
                {agent?.evidence_count !== undefined && <span>{agent.evidence_count} evidence items</span>}
                {!agent && <span>Waiting for backend status</span>}
              </div>
            </div>
            <div className="agent-step-rail" />
          </div>
        );
      })}
    </div>
  );
}
