import axios from "axios";

const baseURL = localStorage.getItem("sentinel-api-base-url") || import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const healthPath = import.meta.env.VITE_API_HEALTH_PATH || "/health";

export const apiClient = axios.create({
  baseURL,
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
});

export class BackendContractUnavailableError extends Error {
  constructor(feature) {
    super(`Backend API for ${feature} is not implemented or documented in this workspace.`);
    this.name = "BackendContractUnavailableError";
    this.feature = feature;
  }
}

export function getErrorMessage(error) {
  if (error instanceof BackendContractUnavailableError) return error.message;
  const detail = error?.response?.data?.detail || error?.response?.data?.message;
  if (detail) return String(detail);
  if (error?.code === "ECONNABORTED") return "The backend did not respond before the request timed out.";
  if (error?.message === "Network Error") return "Could not reach the backend. Check the API URL and that the server is running.";
  return error?.message || "An unexpected API error occurred.";
}

export async function checkBackendHealth() {
  try {
    const response = await apiClient.get(healthPath, { timeout: 4000 });
    return { status: response.status >= 200 && response.status < 300 ? "connected" : "disconnected" };
  } catch (error) {
    return { status: "disconnected", error: getErrorMessage(error) };
  }
}

export async function createIncident(requestBody) {
  const { data } = await apiClient.post("/api/incidents", requestBody);
  return data;
}

export async function startInvestigation(requestBody) {
  const { data } = await apiClient.post("/api/investigations/run", requestBody);
  return data;
}

export async function getInvestigation(investigationId) {
  const { data } = await apiClient.get(`/api/investigations/${encodeURIComponent(investigationId)}`);
  return data;
}

export async function getDashboardData() {
  return getConfiguredData("dashboard", "VITE_API_DASHBOARD_PATH");
}

export async function getIncidents(params) {
  return getConfiguredData("incident history", "VITE_API_INCIDENTS_PATH", params);
}

export async function getInvestigationEvidence(investigationId) {
  const path = getConfiguredPath("investigation evidence", "VITE_API_INVESTIGATION_EVIDENCE_PATH");
  const { data } = await apiClient.get(path.replace("{id}", encodeURIComponent(investigationId)));
  return data;
}

export async function getLogs(params) {
  return getConfiguredData("filtered application logs", "VITE_API_LOGS_PATH", params);
}

export async function getMetrics(params) {
  return getConfiguredData("service metrics", "VITE_API_METRICS_PATH", params);
}

export async function getMCPStatus() {
  return getConfiguredData("MCP server status and tool discovery", "VITE_API_MCP_STATUS_PATH");
}

export async function getRAGStatus() {
  return getConfiguredData("RAG collection status and document listing", "VITE_API_RAG_STATUS_PATH");
}

export async function searchHistoricalIncidents(params) {
  return getConfiguredData("historical incident retrieval", "VITE_API_RAG_SEARCH_PATH", params);
}

export async function getReports() {
  return getConfiguredData("report history", "VITE_API_REPORTS_PATH");
}

function getConfiguredPath(feature, variable) {
  const path = import.meta.env[variable];
  if (!path) throw new BackendContractUnavailableError(feature);
  return path;
}

async function getConfiguredData(feature, variable, params) {
  const path = getConfiguredPath(feature, variable);
  const { data } = await apiClient.get(path, { params });
  return data;
}