import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

export default function Projects() {
  const [projects, setProjects] = useState([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");

  async function refresh() {
    setProjects(await api.listProjects());
  }

  useEffect(() => { refresh(); }, []);

  async function onCreate(e) {
    e.preventDefault();
    setError("");
    try {
      await api.createProject({ name, description: description || undefined });
      setName("");
      setDescription("");
      refresh();
    } catch (err) {
      setError(err.message);
    }
  }

  async function onDelete(id) {
    if (!confirm("Delete this project and all its queues/jobs?")) return;
    await api.deleteProject(id);
    refresh();
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">Projects</h1>

      <form onSubmit={onCreate} className="panel p-4 flex flex-col md:flex-row gap-3 md:items-end">
        <div className="flex flex-col gap-1 flex-1">
          <label className="label">Name</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <div className="flex flex-col gap-1 flex-1">
          <label className="label">Description (optional)</label>
          <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} />
        </div>
        <button className="btn-primary">New project</button>
      </form>
      {error && <div className="text-sm text-accent-red">{error}</div>}

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {projects.map((p) => (
          <div key={p.id} className="panel p-4 flex flex-col gap-2">
            <div className="flex items-start justify-between">
              <Link to={`/projects/${p.id}`} className="font-medium hover:text-accent-teal">{p.name}</Link>
              <button onClick={() => onDelete(p.id)} className="text-ink-500 hover:text-accent-red text-xs">delete</button>
            </div>
            <p className="text-sm text-ink-500">{p.description || "No description"}</p>
            <span className="text-xs text-ink-500 font-mono">created {new Date(p.created_at).toLocaleDateString()}</span>
          </div>
        ))}
        {projects.length === 0 && <p className="text-ink-500 text-sm">No projects yet — create one above.</p>}
      </div>
    </div>
  );
}
