import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import StatusBadge from "../components/StatusBadge";

export default function ProjectDetail() {
  const { projectId } = useParams();
  const [queues, setQueues] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "", priority: 0, concurrency_limit: 1,
    strategy: "exponential", base_delay_seconds: 5, max_delay_seconds: 300, max_retries: 3,
  });
  const [error, setError] = useState("");

  async function refresh() {
    setQueues(await api.listQueues(projectId));
  }

  useEffect(() => { refresh(); }, [projectId]);

  async function onCreate(e) {
    e.preventDefault();
    setError("");
    try {
      await api.createQueue(projectId, {
        name: form.name,
        priority: Number(form.priority),
        concurrency_limit: Number(form.concurrency_limit),
        retry_policy: {
          strategy: form.strategy,
          base_delay_seconds: Number(form.base_delay_seconds),
          max_delay_seconds: Number(form.max_delay_seconds),
          max_retries: Number(form.max_retries),
        },
      });
      setShowForm(false);
      setForm({ ...form, name: "" });
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function togglePause(q) {
    if (q.is_paused) await api.resumeQueue(q.id);
    else await api.pauseQueue(q.id);
    refresh();
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Queues</h1>
        <button className="btn-primary" onClick={() => setShowForm((s) => !s)}>
          {showForm ? "Cancel" : "New queue"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={onCreate} className="panel p-4 grid md:grid-cols-3 gap-4">
          <div className="flex flex-col gap-1">
            <label className="label">Queue name</label>
            <input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          </div>
          <div className="flex flex-col gap-1">
            <label className="label">Priority (higher = more urgent)</label>
            <input type="number" className="input" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="label">Concurrency limit</label>
            <input type="number" min={1} className="input" value={form.concurrency_limit} onChange={(e) => setForm({ ...form, concurrency_limit: e.target.value })} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="label">Retry strategy</label>
            <select className="input" value={form.strategy} onChange={(e) => setForm({ ...form, strategy: e.target.value })}>
              <option value="fixed">Fixed delay</option>
              <option value="linear">Linear backoff</option>
              <option value="exponential">Exponential backoff</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="label">Base delay (s)</label>
            <input type="number" className="input" value={form.base_delay_seconds} onChange={(e) => setForm({ ...form, base_delay_seconds: e.target.value })} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="label">Max retries</label>
            <input type="number" min={0} className="input" value={form.max_retries} onChange={(e) => setForm({ ...form, max_retries: e.target.value })} />
          </div>
          <div className="md:col-span-3">
            <button className="btn-primary">Create queue</button>
          </div>
          {error && <div className="md:col-span-3 text-sm text-accent-red">{error}</div>}
        </form>
      )}

      <div className="flex flex-col gap-3">
        {queues.map((q) => (
          <div key={q.id} className="panel p-4 flex items-center justify-between">
            <div className="flex flex-col gap-1">
              <Link to={`/queues/${q.id}`} className="font-medium font-mono hover:text-accent-teal">{q.name}</Link>
              <div className="flex items-center gap-3 text-xs text-ink-500">
                <span>priority {q.priority}</span>
                <span>concurrency {q.concurrency_limit}</span>
                <span>{q.retry_policy?.strategy} backoff, max {q.retry_policy?.max_retries} retries</span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {q.is_paused ? <StatusBadge status="cancelled" /> : <StatusBadge status="running" />}
              <button className="btn-ghost" onClick={() => togglePause(q)}>
                {q.is_paused ? "Resume" : "Pause"}
              </button>
            </div>
          </div>
        ))}
        {queues.length === 0 && !showForm && <p className="text-ink-500 text-sm">No queues yet — create one above.</p>}
      </div>
    </div>
  );
}
