import { Check, Circle, LoaderCircle } from "lucide-react";
import { workflowStages } from "../../utils/constants.js";

export default function WorkflowProgress({ stages }) {
  const stageMap = Array.isArray(stages)
    ? new Map(stages.filter(Boolean).map((stage) => [String(stage.name || stage.stage || "").toLowerCase(), stage]))
    : new Map();
  return (
    <div className="workflow-progress">
      {workflowStages.map((label, index) => {
        const record = stageMap.get(label.toLowerCase()) || stageMap.get(label.toLowerCase().replaceAll(" ", "_"));
        const status = record?.status || "unavailable";
        return (
          <div className="workflow-stage" key={label}>
            <span className={`workflow-stage-marker marker-${status}`}>
              {status === "completed" || status === "complete" ? <Check size={13} /> : status === "running" ? <LoaderCircle size={13} className="spin" /> : <Circle size={9} />}
            </span>
            <div><strong>{label}</strong><small>{record?.status ? String(record.status).replaceAll("_", " ") : "Status unavailable"}</small></div>
            {index < workflowStages.length - 1 && <span className="workflow-stage-line" />}
          </div>
        );
      })}
    </div>
  );
}
