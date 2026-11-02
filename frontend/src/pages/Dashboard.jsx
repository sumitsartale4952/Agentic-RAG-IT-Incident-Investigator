import { useEffect, useState } from "react";
import { AlertTriangle, Activity, Clock3, Layers3, RadioTower, RefreshCw, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";
import ChartCard from "../components/dashboard/ChartCard.jsx";
import RecentIncidents from "../components/dashboard/RecentIncidents.jsx";
import StatCard from "../components/dashboard/StatCard.jsx";
import { getDashboardData, getErrorMessage } from "../services/api.js";
import { formatDate } from "../utils/formatters.js";

const kpis = [
  ["Total incidents", "total_incidents", Layers3, "blue"],
  ["Active incidents", "active_incidents", Activity, "orange"],
  ["Investigations", "investigations_completed", RadioTower, "purple"],
  ["Critical incidents", "critical_incidents", ShieldAlert, "red"],
  ["MCP servers", "mcp_servers_connected", RadioTower, "teal"],
  ["Avg. investigation", "average_investigation_duration", Clock3, "blue"],
];

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCharts, setShowCharts] = useState(() => localStorage.getItem("sentinel-show-charts") !== "false");

  async function load() {
    setLoading(true);
    try {
      setData(await getDashboardData());
      setError("");
    } catch (requestError) {
      setData(null);
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);
  const stats = data?.stats || data?.kpis || {};

  return (
    <main className="page-content dashboard-page">
      <div className="page-heading dashboard-heading">
        <div>
          <div className="eyebrow"><span className="eyebrow-dot" /> LIVE OPERATIONS</div>
          <h1>Good afternoon, operator <span className="wave">✦</span></h1>
          <p>Your incident intelligence at a glance. Backend data is never simulated.</p>
        </div>
        <div className="heading-actions">
          <span className="updated-label"><span className="live-ring" />{data?.updated_at ? `Updated ${formatDate(data.updated_at)}` : "Awaiting data source"}</span>
          <button className="button button-secondary" onClick={load} disabled={loading}><RefreshCw size={15} className={loading ? "spin" : ""} /> Refresh</button>
          <Link className="button button-primary" to="/investigations/new"><Activity size={15} /> New investigation</Link>
        </div>
      </div>

      <section className="kpi-grid" aria-label="Incident summary">
        {kpis.map(([label, key, icon, tone]) => {
          let value = stats[key];
          if (key === "average_investigation_duration" && typeof value === "number") value = `${Math.round(value)}s`;
          if (value === undefined || value === null || !["number", "string"].includes(typeof value)) value = "—";
          return <StatCard key={key} label={label} value={loading ? "…" : value} detail={data ? "From backend" : "No backend data"} icon={icon} tone={tone} />;
        })}
      </section>

      {error && <div className="inline-notice notice-warning"><AlertTriangle size={17} /><div><strong>Dashboard data unavailable</strong><span>{error}</span></div></div>}

      {showCharts && <div className="dashboard-chart-grid">
        <ChartCard title="Incident trend" subtitle="Incident volume over time" data={data?.incident_trend || []} type="area" />
        <ChartCard title="Severity distribution" subtitle="Open incidents by severity" data={data?.severity_distribution || []} type="donut" />
        <ChartCard title="Service health" subtitle="Current service health indicators" data={data?.service_health || []} type="bar" color="#9b86ff" />
        <ChartCard title="Investigation activity" subtitle="Completed investigations over time" data={data?.investigation_activity || []} type="line" color="#73b9ff" />
      </div>}
      <RecentIncidents incidents={Array.isArray(data?.incidents) ? data.incidents : []} />
      <div className="page-footnote"><span><span className="live-ring" /> Data source: backend API</span><span>Metrics are not available until a dashboard endpoint is configured.</span></div>
    </main>
  );
}