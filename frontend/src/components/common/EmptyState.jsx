import { Database, SearchX } from "lucide-react";

export default function EmptyState({
  title = "No data available",
  description = "Data will appear here when the backend provides it.",
  icon = "database",
  action,
  compact = false,
}) {
  const Icon = icon === "search" ? SearchX : Database;
  return (
    <div className={`empty-state ${compact ? "empty-state-compact" : ""}`}>
      <span className="empty-icon"><Icon size={19} /></span>
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}
