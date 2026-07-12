export default function StatCard({ label, value, accent = "text-ink-100", suffix }) {
  return (
    <div className="panel p-4 flex flex-col gap-1">
      <span className="label">{label}</span>
      <span className={`text-2xl font-mono font-semibold ${accent}`}>
        {value}
        {suffix && <span className="text-sm text-ink-500 ml-1">{suffix}</span>}
      </span>
    </div>
  );
}
