import { useCallback, useEffect, useState } from "react";
import { checkBackendHealth } from "../services/api.js";

export function useBackendHealth() {
  const [status, setStatus] = useState("checking");
  const [lastChecked, setLastChecked] = useState(null);
  const [error, setError] = useState("");
  const [refreshSeconds, setRefreshSeconds] = useState(() => Number(localStorage.getItem("sentinel-refresh-seconds")) || 30);

  const refresh = useCallback(async () => {
    setStatus("checking");
    const result = await checkBackendHealth();
    setStatus(result.status);
    setError(result.error || "");
    setLastChecked(new Date());
  }, []);

  useEffect(() => {
    const updateInterval = () => setRefreshSeconds(Number(localStorage.getItem("sentinel-refresh-seconds")) || 30);
    window.addEventListener("sentinel-settings-change", updateInterval);
    return () => window.removeEventListener("sentinel-settings-change", updateInterval);
  }, []);

  useEffect(() => {
    refresh();
    const interval = window.setInterval(refresh, refreshSeconds * 1000);
    return () => window.clearInterval(interval);
  }, [refresh, refreshSeconds]);

  return { status, lastChecked, error, refresh };
}
