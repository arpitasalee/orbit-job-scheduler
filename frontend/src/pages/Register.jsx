import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [orgName, setOrgName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await register(orgName, email, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="font-mono text-2xl font-semibold text-accent-teal mb-1">◆ Orbit</div>
          <p className="text-ink-500 text-sm">Distributed job scheduler</p>
        </div>
        <form onSubmit={onSubmit} className="panel p-6 flex flex-col gap-4">
          <h1 className="text-lg font-semibold">Create your organization</h1>
          {error && <div className="text-sm text-accent-red bg-accent-red/10 rounded px-3 py-2">{error}</div>}
          <div className="flex flex-col gap-1">
            <label className="label">Organization name</label>
            <input className="input" value={orgName} onChange={(e) => setOrgName(e.target.value)} required />
          </div>
          <div className="flex flex-col gap-1">
            <label className="label">Email</label>
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="flex flex-col gap-1">
            <label className="label">Password</label>
            <input className="input" type="password" minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <button className="btn-primary justify-center mt-1" disabled={busy}>
            {busy ? "Creating..." : "Create account"}
          </button>
          <p className="text-sm text-ink-500 text-center">
            Already have an account? <Link to="/login" className="text-accent-teal">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
