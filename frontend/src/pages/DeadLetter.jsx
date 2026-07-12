import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export default function DeadLetter() {
  const [entries, setEntries] = useState([]);

  async function refresh() {
    setEntries(await api.deadLetterEntries());
  }

  useEffect(() => { refresh(); }, []);

  async function onRetry(jobId) {
    await api.retryJob(jobId);
    refresh();
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Dead Letter Queue</h1>
        <p className="text-ink-500 text-sm">Jobs that exhausted all retries. Inspect and re-queue manually.</p>
      </div>

      <div className="panel p-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-ink-500 text-xs uppercase tracking-wider">
              <th className="pb-2">Job</th>
              <th className="pb-2">Reason</th>
              <th className="pb-2">Retries used</th>
              <th className="pb-2">Failed at</th>
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.id} className="border-t border-base-700">
                <td className="py-2"><Link to={`/jobs/${e.job_id}`} className="font-mono hover:text-accent-teal">{e.job_name}</Link></td>
                <td className="py-2 text-accent-red text-xs max-w-sm truncate">{e.reason}</td>
                <td className="py-2 font-mono text-ink-500">{e.retry_count_at_failure}</td>
                <td className="py-2 text-ink-500">{new Date(e.failed_at).toLocaleString()}</td>
                <td className="py-2 text-right">
                  <button className="btn-ghost" onClick={() => onRetry(e.job_id)}>Requeue</button>
                </td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr><td colSpan={5} className="py-6 text-ink-500 text-center">Nothing here. All jobs are healthy 🎉</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
