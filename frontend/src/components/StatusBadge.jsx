const STYLES = {
  queued: "bg-ink-500/15 text-ink-300",
  scheduled: "bg-accent-blue/15 text-accent-blue",
  claimed: "bg-accent-blue/15 text-accent-blue",
  running: "bg-accent-teal/15 text-accent-teal animate-pulse",
  completed: "bg-accent-teal/15 text-accent-teal",
  failed: "bg-accent-amber/15 text-accent-amber",
  dead_letter: "bg-accent-red/15 text-accent-red",
  cancelled: "bg-ink-500/15 text-ink-500",
  idle: "bg-ink-500/15 text-ink-300",
  busy: "bg-accent-teal/15 text-accent-teal",
  offline: "bg-accent-red/15 text-accent-red",
};

export default function StatusBadge({ status }) {
  const cls = STYLES[status] || "bg-ink-500/15 text-ink-300";
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-mono font-medium ${cls}`}>
      {status}
    </span>
  );
}
