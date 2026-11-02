import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import EmptyState from "../common/EmptyState.jsx";

const chartColors = ["#54d6c9", "#9585ff", "#ffae6b", "#f4778d"];

export default function ChartCard({
  title,
  subtitle,
  type = "line",
  data = [],
  dataKey = "value",
  xKey = "label",
  color = "#62d4ca",
  valueFormatter,
  className = "",
}) {
  const chartData = Array.isArray(data) ? data.filter((entry) => entry && typeof entry === "object") : [];
  const formattedTooltip = (value, name) => [valueFormatter ? valueFormatter(value) : value, name];

  function renderChart() {
    if (type === "donut") {
      return (
        <PieChart>
          <Pie data={chartData} dataKey={dataKey} nameKey={xKey} innerRadius="62%" outerRadius="84%" paddingAngle={4} stroke="none">
            {chartData.map((entry, index) => <Cell key={entry[xKey] || index} fill={entry.color || chartColors[index % chartColors.length]} />)}
          </Pie>
          <Tooltip formatter={formattedTooltip} />
        </PieChart>
      );
    }
    const Chart = type === "area" ? AreaChart : type === "bar" ? BarChart : LineChart;
    return (
      <Chart data={chartData} margin={{ top: 8, right: 12, bottom: 0, left: -14 }}>
        <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
        <XAxis dataKey={xKey} tickLine={false} axisLine={false} tick={{ fill: "var(--text-muted)", fontSize: 10 }} />
        <YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--text-muted)", fontSize: 10 }} width={36} />
        <Tooltip formatter={formattedTooltip} contentStyle={{ background: "var(--surface-raised)", border: "1px solid var(--border-strong)", borderRadius: 9, color: "var(--text-primary)" }} />
        {type === "area" && <Area type="monotone" dataKey={dataKey} stroke={color} fill={`${color}26`} strokeWidth={2} />}
        {type === "bar" && <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} />}
        {type === "line" && <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />}
      </Chart>
    );
  }

  return (
    <section className={`panel chart-panel ${className}`}>
      <div className="panel-heading">
        <div><h2>{title}</h2><p>{subtitle}</p></div>
        <span className="chart-period">BACKEND DATA</span>
      </div>
      <div className={`chart-body ${type === "donut" ? "chart-donut" : ""}`}>
        {chartData.length
          ? <ResponsiveContainer width="100%" height="100%">{renderChart()}</ResponsiveContainer>
          : <EmptyState compact title="No telemetry available" description="This chart will populate when the backend exposes this data." />}
      </div>
    </section>
  );
}
