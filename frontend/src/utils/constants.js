import {
  Activity, BookOpen, ChartNoAxesCombined, FileText, GitBranch, Gauge,
  LayoutDashboard, ListChecks, Radio, Server, Settings2, Siren,
} from "lucide-react";

export const navigation = [
  { label: "Overview", path: "/", icon: LayoutDashboard },
  { label: "Incidents", path: "/incidents", icon: Siren },
  { label: "New investigation", path: "/investigations/new", icon: Activity },
  { label: "Agent workflow", path: "/workflow", icon: GitBranch },
  { label: "Log explorer", path: "/logs", icon: ListChecks },
  { label: "Metrics explorer", path: "/metrics", icon: ChartNoAxesCombined },
  { label: "Historical knowledge", path: "/knowledge", icon: BookOpen },
  { label: "MCP servers", path: "/mcp", icon: Server },
  { label: "Reports", path: "/reports", icon: FileText },
  { label: "Settings", path: "/settings", icon: Settings2 },
];

export const agentNames = [
  "Supervisor Agent",
  "Log Analysis Agent",
  "Monitoring Agent",
  "RCA & Report Agent",
];

export const services = ["payment-api", "auth-service", "order-service", "database-service"];

export const severityOptions = [
  { value: "SEV-1", label: "SEV-1 · Critical" },
  { value: "SEV-2", label: "SEV-2 · High" },
  { value: "SEV-3", label: "SEV-3 · Medium" },
  { value: "SEV-4", label: "SEV-4 · Low" },
];

export const severityClass = {
  "SEV-1": "critical",
  "SEV-2": "high",
  "SEV-3": "medium",
  "SEV-4": "low",
};

export const workflowStages = [
  "Incident received",
  "Supervisor routing",
  "Log analysis",
  "Metrics analysis",
  "Historical retrieval",
  "RCA generation",
  "Report completed",
];
