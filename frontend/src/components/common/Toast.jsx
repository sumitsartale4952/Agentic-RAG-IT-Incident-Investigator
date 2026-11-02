import { AlertCircle, CheckCircle2, X } from "lucide-react";

export default function Toast({ toast, onDismiss }) {
  if (!toast) return null;
  const Icon = toast.type === "success" ? CheckCircle2 : AlertCircle;
  return (
    <div className={`toast toast-${toast.type || "error"}`} role="status">
      <Icon size={17} />
      <span>{toast.message}</span>
      <button className="icon-button toast-close" aria-label="Dismiss notification" onClick={onDismiss}>
        <X size={15} />
      </button>
    </div>
  );
}
