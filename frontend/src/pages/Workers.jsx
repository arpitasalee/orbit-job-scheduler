import { useEffect, useState } from "react";
import { api } from "../api/client";
import StatusBadge from "../components/StatusBadge";

export default function Workers() {
  const [workers, setWorkers] = useState([]);

  async function refresh() {
    setWorkers(await api.listWorkers());
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, []);

  function isStale(w) {
    if (!w.last_heartbeat_at) return true;
    return Date.now() - new Date(w.last_heartbeat_at).getTime() > 30000;
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Workers</h1>
        <p className="text-ink-500 text-sm">In-process worker pool. Heartbeats every 5s; stale after 30s.</p>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        {workers.map((w) => (
          <div key={w.id} className="panel p-4 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="font-mono font-medium">{w.name}</span>
              <StatusBadge status={w.status} />
            </div>
            <div className="text-xs text-ink-500 font-mono">
              last heartbeat: {w.last_heartbeat_at ? new Date(w.last_heartbeat_at).toLocaleTimeString() : "never"}
            </div>
            {isStale(w) && w.status !== "offline" && (
              <span className="text-xs text-accent-amber">⚠ heartbeat is stale</span>
            )}
          </div>
        ))}
        {workers.length === 0 && <p className="text-ink-500 text-sm">No workers registered yet.</p>}
      </div>
    </div>
  );
}
