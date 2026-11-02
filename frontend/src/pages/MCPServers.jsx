import { useEffect, useMemo, useState } from "react";
import { ChevronRight, Radio, Server, Wrench } from "lucide-react";
import PageHeader from "../components/common/PageHeader.jsx";
import DataUnavailable from "../components/common/DataUnavailable.jsx";
import StatusBadge from "../components/common/StatusBadge.jsx";
import { getErrorMessage, getMCPStatus } from "../services/api.js";

const serverDefinitions = [
  { id: "log", name: "Log MCP Server", transport: "Backend managed", tools: ["read_application_logs", "search_logs_by_service", "search_error_logs", "count_errors_by_type", "get_recent_errors"] },
  { id: "metrics", name: "Metrics MCP Server", transport: "Backend managed", tools: ["get_service_metrics", "calculate_average_latency", "get_cpu_usage", "get_memory_usage", "detect_metric_anomalies"] },
];

export default function MCPServers() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  async function load() {
    try {
      setData(await getMCPStatus());
      setError("");
    } catch (requestError) {
      setData(null);
      setError(getErrorMessage(requestError));
    }
  }
  useEffect(() => { load(); }, []);
  const reportedServers = Array.isArray(data) ? data : Array.isArray(data?.servers) ? data.servers : [];
  const selectedServerId = selected?.split(":")[0];
  const selectedServer = useMemo(() => reportedServers.find((server) => server &&
    String(server.name || server.server_name || "").toLowerCase().includes(selectedServerId || "___"),
  ), [reportedServers, selectedServerId]);
  const selectedTool = selected && selected.includes(":") ? selected.split(":")[1] : "";
  const actualTool = Array.isArray(selectedServer?.tools) ? selectedServer.tools.find((tool) => (typeof tool === "string" ? tool : tool?.name) === selectedTool) : null;

  return (
    <main className="page-content">
      <PageHeader eyebrow="TOOLING PLANE" title="MCP servers" description="Inspect backend-managed MCP connections and the tools exposed to the investigation workflow." />
      {error && <DataUnavailable message={error} onRetry={load} />}
      <section className="mcp-server-grid">
        {serverDefinitions.map((definition) => {
          const actual = reportedServers.find((server) => server && String(server.name || server.server_name || "").toLowerCase().includes(definition.id));
          const actualTools = Array.isArray(actual?.tools) ? actual.tools : [];
          return <article className="panel mcp-server-card" key={definition.id}>
            <div className="mcp-card-top"><div className={`mcp-server-icon mcp-${definition.id}`}><Server size={18} /></div><StatusBadge status={actual?.status || "unavailable"} label={actual?.status ? String(actual.status).replaceAll("_", " ") : "Status unavailable"} /></div>
            <h2>{definition.name}</h2><p>Connection details and discovery are supplied by the backend.</p>
            <div className="mcp-detail-list"><div><span>Transport</span><strong>{actual?.transport || actual?.transport_type || "Unavailable"}</strong></div><div><span>Discovered tools</span><strong>{actualTools.length || "—"}</strong></div><div><span>Last successful call</span><strong>{actual?.last_successful_call ? new Date(actual.last_successful_call).toLocaleString() : "Unavailable"}</strong></div></div>
            <div className="mcp-tool-list"><div className="tool-list-title"><span>Reference tool names</span><small>Not backend-verified</small></div>
              {definition.tools.map((tool) => <button key={tool} className={`mcp-tool-row ${selected === `${definition.id}:${tool}` ? "selected" : ""}`} onClick={() => setSelected(`${definition.id}:${tool}`)}><Wrench size={13} /><code>{tool}</code><ChevronRight size={14} /></button>)}
            </div>
          </article>;
        })}
      </section>
      <section className="panel tool-explorer">
        <div className="panel-heading"><div><h2>Tool explorer</h2><p>Select a reference tool to inspect its backend discovery state.</p></div><span className="tool-explorer-icon"><Radio size={16} /></span></div>
        {selected ? <div className="tool-detail-grid"><div><span className="detail-label">Tool</span><code>{selectedTool}</code><span className="detail-label">Description</span><p>{actualTool?.description || "Description unavailable until the backend exposes MCP tool discovery."}</p><span className="detail-label">Input parameters</span><p>{actualTool?.parameters ? JSON.stringify(actualTool.parameters) : "Parameters unavailable"}</p></div><div><span className="detail-label">Input schema</span><pre>{actualTool?.inputSchema ? JSON.stringify(actualTool.inputSchema, null, 2) : "Schema unavailable"}</pre><span className="detail-label">Execution result</span><p>{actualTool?.last_result || "No execution result returned."}</p><span className="detail-label">Error details</span><p>{actualTool?.last_error || "No error details returned."}</p></div></div> : <div className="tool-select-empty">Choose a tool above to inspect it.</div>}
      </section>
      <div className="page-footnote"><span><Radio size={13} /> Browser is not connected directly to MCP.</span><span>Tool calls are backend-mediated only.</span></div>
    </main>
  );
}
