import { CheckCircle2, Circle, LoaderCircle, XCircle } from "lucide-react";

const stateIcons = {
  connected: CheckCircle2,
  completed: CheckCircle2,
  complete: CheckCircle2,
  running: LoaderCircle,
  checking: LoaderCircle,
  failed: XCircle,
  error: XCircle,
  disconnected: Circle,
  pending: Circle,
};

export default function StatusBadge({ status = "unavailable", label, className = "" }) {
  const normalized = String(status).toLowerCase().replaceAll(" ", "_");
  const Icon = stateIcons[normalized] || Circle;
  const tone = ["connected", "completed", "complete"].includes(normalized)
    ? "success"
    : ["running", "checking"].includes(normalized)
      ? "active"
      : ["failed", "error"].includes(normalized)
        ? "danger"
        : ["disconnected", "pending", "skipped"].includes(normalized)
          ? "muted"
          : "neutral";
  return (
    <span className={`status-badge status-${tone} ${className}`}>
      <Icon size={13} className={["running", "checking"].includes(normalized) ? "spin" : ""} />
      {label || String(status).replaceAll("_", " ")}
    </span>
  );
}
