import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LineChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api/client";
import StatCard from "../components/StatCard";

export default function Dashboard() {
  const [health, setHealth] = useState(null);
  const [series, setSeries] = useState([]);
  const [dlq, setDlq] = useState([]);

  async function refresh() {
    const [h, s, d] = await Promise.all([
      api.systemHealth(),
      api.throughputSeries(),
      api.deadLetterEntries(),
    ]);
    setHealth(h);
    setSeries(s.map((p) => ({ ...p, label: new Date(p.bucket).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) })));
    setDlq(d.slice(0, 5));
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000); // simple polling for "live" updates
    return () => clearInterval(id);
  }, []);

  if (!health) return <div className="text-ink-500">Loading system health...</div>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">System Health</h1>
        <p className="text-ink-500 text-sm">Auto-refreshes every 5 seconds.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Queued" value={health.queued} accent="text-ink-100" />
        <StatCard label="Running" value={health.running} accent="text-accent-teal" />
        <StatCard label="Completed" value={health.completed} accent="text-accent-teal" />
        <StatCard label="Failed" value={health.failed} accent="text-accent-amber" />
        <StatCard label="Dead Letter" value={health.dead_letter} accent="text-accent-red" />
        <StatCard label="Active Workers" value={`${health.active_workers}/${health.total_workers}`} />
        <StatCard label="Throughput (1h)" value={health.throughput_last_hour} suffix="jobs" />
        <StatCard label="Total Jobs" value={health.total_jobs} />
      </div>

      <div className="panel p-4">
        <h2 className="text-sm font-medium text-ink-300 mb-3">Throughput — completions per minute (last 30m)</h2>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series}>
              <XAxis dataKey="label" stroke="#7C88A3" fontSize={11} tickLine={false} axisLine={false} />
              <YAxis stroke="#7C88A3" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip contentStyle={{ background: "#121A2B", border: "1px solid #1B2740", borderRadius: 8, fontSize: 12 }} />
              <Line type="monotone" dataKey="count" stroke="#2DD4BF" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="panel p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-ink-300">Recent Dead Letter Entries</h2>
          <Link to="/dead-letter" className="text-xs text-accent-teal">View all →</Link>
        </div>
        {dlq.length === 0 ? (
          <p className="text-sm text-ink-500">No dead-lettered jobs. Everything's healthy.</p>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {dlq.map((e) => (
                <tr key={e.id} className="border-t border-base-700">
                  <td className="py-2 font-mono text-ink-100">{e.job_name}</td>
                  <td className="py-2 text-ink-500 truncate max-w-xs">{e.reason}</td>
                  <td className="py-2 text-ink-500 text-right">{new Date(e.failed_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
