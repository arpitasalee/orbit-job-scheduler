import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import StatusBadge from "../components/StatusBadge";

export default function JobDetail() {
  const { jobId } = useParams();
  const [job, setJob] = useState(null);

  async function refresh() {
    setJob(await api.getJob(jobId));
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [jobId]);

  async function onRetry() {
    await api.retryJob(jobId);
    refresh();
  }
  async function onCancel() {
    await api.cancelJob(jobId);
    refresh();
  }

  if (!job) return <div className="text-ink-500">Loading job...</div>;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold font-mono">{job.name}</h1>
          <div className="flex items-center gap-2 mt-1">
            <StatusBadge status={job.status} />
            <span className="text-xs text-ink-500 font-mono">{job.job_type} · retry {job.retry_count}</span>
          </div>
        </div>
        <div className="flex gap-2">
          {(job.status === "failed" || job.status === "dead_letter") && (
            <button className="btn-primary" onClick={onRetry}>Retry now</button>
          )}
          {!["completed", "running", "cancelled", "dead_letter"].includes(job.status) && (
            <button className="btn-danger" onClick={onCancel}>Cancel</button>
          )}
        </div>
      </div>

      <div className="panel p-4">
        <h2 className="text-sm font-medium text-ink-300 mb-2">Payload</h2>
        <pre className="text-xs font-mono text-ink-300 bg-base-900 rounded p-3 overflow-x-auto">
          {JSON.stringify(job.payload, null, 2)}
        </pre>
      </div>

      <div className="panel p-4">
        <h2 className="text-sm font-medium text-ink-300 mb-3">Execution history</h2>
        {job.executions.length === 0 ? (
          <p className="text-sm text-ink-500">No execution attempts yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-ink-500 text-xs uppercase tracking-wider">
                <th className="pb-2">Attempt</th>
                <th className="pb-2">Status</th>
                <th className="pb-2">Duration</th>
                <th className="pb-2">Started</th>
                <th className="pb-2">Error</th>
              </tr>
            </thead>
            <tbody>
              {job.executions.map((ex) => (
                <tr key={ex.id} className="border-t border-base-700">
                  <td className="py-2 font-mono">{ex.attempt_number}</td>
                  <td className="py-2"><StatusBadge status={ex.status} /></td>
                  <td className="py-2 font-mono text-ink-500">{ex.duration_ms ?? "-"}ms</td>
                  <td className="py-2 text-ink-500">{new Date(ex.started_at).toLocaleString()}</td>
                  <td className="py-2 text-accent-red text-xs">{ex.error || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="panel p-4">
        <h2 className="text-sm font-medium text-ink-300 mb-3">Logs</h2>
        {job.logs.length === 0 ? (
          <p className="text-sm text-ink-500">No logs yet.</p>
        ) : (
          <div className="flex flex-col gap-1 font-mono text-xs">
            {job.logs.map((l) => (
              <div key={l.id} className="flex gap-3">
                <span className="text-ink-500">{new Date(l.timestamp).toLocaleTimeString()}</span>
                <span className={
                  l.level === "error" ? "text-accent-red" : l.level === "warning" ? "text-accent-amber" : "text-ink-300"
                }>[{l.level}]</span>
                <span className="text-ink-100">{l.message}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
