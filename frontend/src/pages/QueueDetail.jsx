import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import StatCard from "../components/StatCard";

const JOB_TYPES = ["immediate", "delayed", "scheduled", "recurring", "batch"];
const STATUSES = ["queued", "scheduled", "claimed", "running", "completed", "failed", "dead_letter", "cancelled"];

export default function QueueDetail() {
  const { queueId } = useParams();
  const [queue, setQueue] = useState(null);
  const [stats, setStats] = useState(null);
  const [jobsPage, setJobsPage] = useState({ items: [], total: 0, page: 1, page_size: 10 });
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    name: "", job_type: "immediate", payload: '{"duration_ms": 500}', run_at: "", cron_expression: "",
  });

  async function refresh() {
    const [q, s, j] = await Promise.all([
      api.getQueue(queueId),
      api.queueStats(queueId),
      api.listJobs(queueId, { status: statusFilter || undefined, page, page_size: 10 }),
    ]);
    setQueue(q);
    setStats(s);
    setJobsPage(j);
  }

  useEffect(() => { refresh(); }, [queueId, statusFilter, page]);
  useEffect(() => {
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [queueId, statusFilter, page]);

  async function onCreateJob(e) {
    e.preventDefault();
    setError("");
    let payload;
    try {
      payload = JSON.parse(form.payload || "{}");
    } catch {
      setError("Payload must be valid JSON");
      return;
    }
    try {
      await api.createJob(queueId, {
        name: form.name,
        job_type: form.job_type,
        payload,
        run_at: ["delayed", "scheduled"].includes(form.job_type) && form.run_at
          ? new Date(form.run_at).toISOString() : undefined,
        cron_expression: form.job_type === "recurring" ? form.cron_expression : undefined,
      });
      setShowForm(false);
      setForm({ ...form, name: "" });
      setPage(1);
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function onRetry(jobId) {
    await api.retryJob(jobId);
    refresh();
  }

  if (!queue) return <div className="text-ink-500">Loading queue...</div>;

  const totalPages = Math.max(1, Math.ceil(jobsPage.total / jobsPage.page_size));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold font-mono">{queue.name}</h1>
          <p className="text-ink-500 text-sm">
            priority {queue.priority} · concurrency {queue.concurrency_limit} · {queue.is_paused ? "paused" : "active"}
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm((s) => !s)}>
          {showForm ? "Cancel" : "New job"}
        </button>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <StatCard label="Queued" value={stats.queued} />
          <StatCard label="Running" value={stats.running} accent="text-accent-teal" />
          <StatCard label="Completed" value={stats.completed} accent="text-accent-teal" />
          <StatCard label="Failed" value={stats.failed} accent="text-accent-amber" />
          <StatCard label="Dead Letter" value={stats.dead_letter} accent="text-accent-red" />
        </div>
      )}

      {showForm && (
        <form onSubmit={onCreateJob} className="panel p-4 grid md:grid-cols-2 gap-4">
          <div className="flex flex-col gap-1">
            <label className="label">Job name</label>
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div className="flex flex-col gap-1">
            <label className="label">Job type</label>
            <select className="input" value={form.job_type} onChange={(e) => setForm({ ...form, job_type: e.target.value })}>
              {JOB_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          {["delayed", "scheduled"].includes(form.job_type) && (
            <div className="flex flex-col gap-1">
              <label className="label">Run at</label>
              <input type="datetime-local" className="input" value={form.run_at} onChange={(e) => setForm({ ...form, run_at: e.target.value })} required />
            </div>
          )}
          {form.job_type === "recurring" && (
            <div className="flex flex-col gap-1">
              <label className="label">Cron expression</label>
              <input className="input" placeholder="*/5 * * * *" value={form.cron_expression} onChange={(e) => setForm({ ...form, cron_expression: e.target.value })} required />
            </div>
          )}
          <div className="flex flex-col gap-1 md:col-span-2">
            <label className="label">Payload (JSON) — try {"{"}"fail": true{"}"} to see retries/DLQ in action</label>
            <textarea className="input font-mono h-20" value={form.payload} onChange={(e) => setForm({ ...form, payload: e.target.value })} />
          </div>
          <div className="md:col-span-2">
            <button className="btn-primary">Create job</button>
          </div>
          {error && <div className="md:col-span-2 text-sm text-accent-red">{error}</div>}
        </form>
      )}

      <div className="panel p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-ink-300">Jobs</h2>
          <select className="input !py-1" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-ink-500 text-xs uppercase tracking-wider">
              <th className="pb-2">Name</th>
              <th className="pb-2">Type</th>
              <th className="pb-2">Status</th>
              <th className="pb-2">Retries</th>
              <th className="pb-2">Created</th>
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {jobsPage.items.map((j) => (
              <tr key={j.id} className="border-t border-base-700">
                <td className="py-2"><Link to={`/jobs/${j.id}`} className="font-mono hover:text-accent-teal">{j.name}</Link></td>
                <td className="py-2 text-ink-500">{j.job_type}</td>
                <td className="py-2"><StatusBadge status={j.status} /></td>
                <td className="py-2 font-mono text-ink-500">{j.retry_count}</td>
                <td className="py-2 text-ink-500">{new Date(j.created_at).toLocaleString()}</td>
                <td className="py-2 text-right">
                  {(j.status === "failed" || j.status === "dead_letter") && (
                    <button className="text-xs text-accent-teal" onClick={() => onRetry(j.id)}>retry</button>
                  )}
                </td>
              </tr>
            ))}
            {jobsPage.items.length === 0 && (
              <tr><td colSpan={6} className="py-4 text-ink-500 text-center">No jobs match this filter.</td></tr>
            )}
          </tbody>
        </table>
        <div className="flex items-center justify-between mt-3 text-sm text-ink-500">
          <span>{jobsPage.total} total</span>
          <div className="flex items-center gap-2">
            <button className="btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Prev</button>
            <span>page {page} / {totalPages}</span>
            <button className="btn-ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        </div>
      </div>
    </div>
  );
}
