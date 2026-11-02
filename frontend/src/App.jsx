import { useCallback, useRef, useState } from "react";
import { Link, Route, Routes } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import AppLayout from "./components/layout/AppLayout.jsx";
import ErrorBoundary from "./components/common/ErrorBoundary.jsx";
import Toast from "./components/common/Toast.jsx";
import { useBackendHealth } from "./hooks/useBackendHealth.js";
import Dashboard from "./pages/Dashboard.jsx";
import Incidents from "./pages/Incidents.jsx";
import NewIncident from "./pages/NewIncident.jsx";
import InvestigationResult from "./pages/InvestigationResult.jsx";
import ReportDetail from "./pages/ReportDetail.jsx";
import AgentWorkflow from "./pages/AgentWorkflow.jsx";
import LogExplorer from "./pages/LogExplorer.jsx";
import MetricsExplorer from "./pages/MetricsExplorer.jsx";
import HistoricalKnowledge from "./pages/HistoricalKnowledge.jsx";
import MCPServers from "./pages/MCPServers.jsx";
import Reports from "./pages/Reports.jsx";
import Settings from "./pages/Settings.jsx";

function NotFound() {
  return <main className="not-found"><span>404 · PAGE NOT FOUND</span><h1>This route is outside the incident perimeter.</h1><p>The page may have moved or the URL may be incorrect.</p><Link className="button button-primary" to="/"><ArrowLeft size={14} /> Return to overview</Link></main>;
}

export default function App() {
  const health = useBackendHealth();
  const [toast, setToast] = useState(null);
  const timeout = useRef(null);
  const notify = useCallback((message) => {
    setToast(typeof message === "string" ? { type: "error", message } : message);
    if (timeout.current) window.clearTimeout(timeout.current);
    timeout.current = window.setTimeout(() => setToast(null), 6500);
  }, []);

  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<AppLayout health={health} onRefreshHealth={health.refresh} notify={notify} />}>
          <Route index element={<Dashboard />} />
          <Route path="incidents" element={<Incidents />} />
          <Route path="investigations/new" element={<NewIncident />} />
          <Route path="investigations/:id/report" element={<ReportDetail />} />
          <Route path="investigations/:id" element={<InvestigationResult />} />
          <Route path="workflow" element={<AgentWorkflow />} />
          <Route path="logs" element={<LogExplorer />} />
          <Route path="metrics" element={<MetricsExplorer />} />
          <Route path="knowledge" element={<HistoricalKnowledge />} />
          <Route path="mcp" element={<MCPServers />} />
          <Route path="reports" element={<Reports />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
      <Toast toast={toast} onDismiss={() => setToast(null)} />
    </ErrorBoundary>
  );
}