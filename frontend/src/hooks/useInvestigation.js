import { useCallback, useEffect, useState } from "react";
import { getErrorMessage, getInvestigation } from "../services/api.js";

const terminalStatuses = new Set(["completed", "complete", "failed", "error", "cancelled"]);

export function useInvestigation(investigationId) {
  const [investigation, setInvestigation] = useState(null);
  const [loading, setLoading] = useState(Boolean(investigationId));
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [pollingEnabled, setPollingEnabled] = useState(false);

  const refresh = useCallback(async () => {
    if (!investigationId) return;
    try {
      const result = await getInvestigation(investigationId);
      setInvestigation(result);
      setError("");
      setLastUpdated(new Date());
      setPollingEnabled(true);
    } catch (requestError) {
      setError(getErrorMessage(requestError));
      setPollingEnabled(false);
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  useEffect(() => {
    setLoading(Boolean(investigationId));
    setInvestigation(null);
    setError("");
    setPollingEnabled(false);
    if (!investigationId) return undefined;
    refresh();
    return undefined;
  }, [investigationId, refresh]);

  useEffect(() => {
    if (!investigationId || !pollingEnabled) return undefined;
    const status = String(investigation?.status || "").toLowerCase();
    if (terminalStatuses.has(status)) return undefined;
    const interval = window.setInterval(refresh, 5000);
    return () => window.clearInterval(interval);
  }, [investigationId, refresh, pollingEnabled, investigation?.status]);

  return { investigation, loading, error, lastUpdated, refresh };
}
