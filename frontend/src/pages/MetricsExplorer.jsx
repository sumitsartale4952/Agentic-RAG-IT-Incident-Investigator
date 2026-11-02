import { useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, RefreshCw, Server } from "lucide-react";
import PageHeader from "../components/common/PageHeader.jsx";
import DataUnavailable from "../components/common/DataUnavailable.jsx";
import ChartCard from "../components/dashboard/ChartCard.jsx";
import StatCard from "../components/dashboard/StatCard.jsx";
import { getErrorMessage, getMetrics } from "../services/api.js";
import { services } from "../utils/constants.js";

export default function MetricsExplorer() {
  const [service, setService] = useState(services[0]);
  const [metrics, setMetrics] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  async function load() {
    setLoading(true);
    try {
      const response = await getMetrics({ service });
      setMetrics((Array.isArray(response) ? response : Array.isArray(response?.metrics) ? response.metrics : []).filter(Boolean));
      setError("");
    } catch (requestError) {
      setMetrics([]);
      setError(getErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, [service]);
  const latest = metrics[metrics.length - 1] || {};
  const errorRate = latest.request_count ? `${((latest.error_count || 0) / latest.request_count * 100).toFixed(2)}%` : "—";
  const stats = [
    ["CPU usage", latest.cpu_usage_percent, "%", Activity, "blue"],
    ["Memory usage", latest.memory_usage_percent, "%", Server, "purple"],
    ["Average latency", latest.avg_latency_ms ?? latest.api_latency_ms, " ms", Activity, "teal"],
    ["Error rate", errorRate, "", AlertTriangle, "red"],
    ["Active connections", latest.active_connections, "", Server, "orange"],
  ];
  return (
    <main className="page-content">
      <PageHeader eyebrow="OBSERVABILITY" title="Metrics explorer" description="Inspect service health metrics and anomaly signals reported by the backend." actions={<button className="button button-secondary" onClick={load} disabled={loading}><RefreshCw size={14} className={loading ? "spin" : ""} /> Refresh</button>} />
      <section className="panel service-selector"><div><strong>Selected service</strong><span>Changes query the configured metrics endpoint.</span></div><select value={service} onChange={(event) => setService(event.target.value)}>{services.map((name) => <option key={name}>{name}</option>)}</select></section>
      {error && <DataUnavailable message={error} onRetry={load} />}
      <section className="kpi-grid metrics-kpi-grid">{stats.map(([label, value, suffix, icon, tone]) => <StatCard key={label} label={label} value={loading ? "…" : value === undefined || value === null ? "—" : `${value}${suffix}`} detail={metrics.length ? "Latest returned sample" : "No backend data"} icon={icon} tone={tone} />)}</section>
      <div className="dashboard-chart-grid">
        <ChartCard title="CPU utilization" subtitle={service} data={metrics} dataKey="cpu_usage_percent" xKey="timestamp" type="area" />
        <ChartCard title="Memory utilization" subtitle={service} data={metrics} dataKey="memory_usage_percent" xKey="timestamp" type="area" color="#9b86ff" />
        <ChartCard title="API latency" subtitle={service} data={metrics} dataKey="avg_latency_ms" xKey="timestamp" type="line" color="#71b8ff" />
        <ChartCard title="Error count" subtitle={service} data={metrics} dataKey="error_count" xKey="timestamp" type="bar" color="#f07e8a" />
      </div>
      {metrics.some((metric) => metric.is_anomaly === true || metric.is_anomaly === 1) && <div className="inline-notice notice-warning"><AlertTriangle size={16} /><div><strong>Anomaly reported</strong><span>At least one returned metric is marked as an anomaly by the backend.</span></div></div>}
      {!metrics.length && !error && <DataUnavailable title="No metrics returned" message="Anomaly flags and time series appear only when returned by the backend." />}
    </main>
  );
}
