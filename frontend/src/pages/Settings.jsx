import { useState } from "react";
import { Check, Moon, Save, Sun } from "lucide-react";
import { useOutletContext } from "react-router-dom";
import PageHeader from "../components/common/PageHeader.jsx";
import StatusBadge from "../components/common/StatusBadge.jsx";
import { useTheme } from "../context/ThemeContext.jsx";
import { apiClient } from "../services/api.js";

const defaultApiUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export default function Settings() {
  const { theme, toggleTheme } = useTheme();
  const { health, notify } = useOutletContext();
  const [apiUrl, setApiUrl] = useState(localStorage.getItem("sentinel-api-base-url") || defaultApiUrl);
  const [refreshInterval, setRefreshInterval] = useState(localStorage.getItem("sentinel-refresh-seconds") || "30");
  const [showCharts, setShowCharts] = useState(localStorage.getItem("sentinel-show-charts") !== "false");
  const [saved, setSaved] = useState(false);

  function save() {
    let parsed;
    try {
      parsed = new URL(apiUrl);
      if (!["http:", "https:"].includes(parsed.protocol)) throw new Error("Use an http or https URL.");
    } catch (error) {
      notify({ type: "error", message: `Invalid backend URL: ${error.message}` });
      return;
    }
    const normalized = parsed.origin;
    localStorage.setItem("sentinel-api-base-url", normalized);
    localStorage.setItem("sentinel-refresh-seconds", refreshInterval);
    localStorage.setItem("sentinel-show-charts", String(showCharts));
    apiClient.defaults.baseURL = normalized;
    window.dispatchEvent(new Event("sentinel-settings-change"));
    health.refresh();
    setApiUrl(normalized);
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1800);
    notify({ type: "success", message: "Workspace preferences saved." });
  }

  return (
    <main className="page-content">
      <PageHeader eyebrow="WORKSPACE CONFIGURATION" title="Settings" description="Configure local preferences and the backend address. No credentials are stored here." />
      <div className="settings-layout">
        <section className="panel settings-section">
          <div className="settings-title"><div><h2>Backend connection</h2><p>API URL used by this browser session.</p></div><StatusBadge status={health.status} label={health.status} /></div>
          <label className="field"><span>Backend API URL</span><input value={apiUrl} onChange={(event) => setApiUrl(event.target.value)} placeholder="http://127.0.0.1:8000" /><small className="field-help">Health check endpoint: <code>{import.meta.env.VITE_API_HEALTH_PATH || "/health"}</code>. A successful response is required to show Connected.</small></label>
        </section>
        <section className="panel settings-section">
          <div className="settings-title"><div><h2>Appearance</h2><p>Choose a workspace color theme.</p></div></div>
          <div className="theme-choice-row">
            <button className={`theme-choice ${theme === "dark" ? "selected" : ""}`} onClick={() => theme !== "dark" && toggleTheme()}><Moon size={17} /><span><strong>Dark</strong><small>Low-light command center</small></span>{theme === "dark" && <Check size={16} />}</button>
            <button className={`theme-choice ${theme === "light" ? "selected" : ""}`} onClick={() => theme !== "light" && toggleTheme()}><Sun size={17} /><span><strong>Light</strong><small>Bright workspace surfaces</small></span>{theme === "light" && <Check size={16} />}</button>
          </div>
        </section>
        <section className="panel settings-section">
          <div className="settings-title"><div><h2>Refresh & dashboard</h2><p>Control how often the backend health status is checked.</p></div></div>
          <label className="field setting-inline"><span>Refresh interval</span><select value={refreshInterval} onChange={(event) => setRefreshInterval(event.target.value)}><option value="15">15 seconds</option><option value="30">30 seconds</option><option value="60">60 seconds</option></select></label>
          <label className="preference-toggle"><input type="checkbox" checked={showCharts} onChange={(event) => setShowCharts(event.target.checked)} /><span><strong>Show dashboard charts</strong><small>Display chart panels even when backend data is unavailable.</small></span></label>
        </section>
        <section className="panel settings-section">
          <div className="settings-title"><div><h2>Application information</h2><p>Runtime status and configuration.</p></div></div>
          <div className="app-info-grid"><span>Application</span><strong>Sentinel Incident Investigator</strong><span>Environment</span><strong>Development</strong><span>Backend</span><strong>{health.status}</strong><span>API credentials</span><strong>Not stored in frontend</strong></div>
        </section>
        <div className="settings-save"><button className="button button-primary" onClick={save}><Save size={14} />{saved ? "Saved" : "Save preferences"}</button></div>
      </div>
    </main>
  );
}
