import { AlertTriangle, RotateCcw } from "lucide-react";
import EmptyState from "./EmptyState.jsx";

export default function DataUnavailable({ title, message, onRetry }) {
  return (
    <div className="unavailable-panel">
      <div className="unavailable-banner"><AlertTriangle size={16} /><span>Backend data unavailable</span></div>
      <EmptyState title={title || "Waiting for a backend data source"} description={message || "This area stays empty until the backend exposes a supported API."} />
      {onRetry && <button className="button button-secondary" onClick={onRetry}><RotateCcw size={14} /> Retry</button>}
    </div>
  );
}
