import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const linkClass = ({ isActive }) =>
  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
    isActive ? "bg-base-700 text-accent-teal" : "text-ink-300 hover:text-ink-100"
  }`;

export default function Navbar() {
  const { user, logout } = useAuth();
  return (
    <header className="border-b border-base-700 bg-base-900/80 backdrop-blur sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <span className="font-mono font-semibold text-accent-teal tracking-tight">◆ Orbit</span>
          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={linkClass}>Dashboard</NavLink>
            <NavLink to="/projects" className={linkClass}>Projects</NavLink>
            <NavLink to="/workers" className={linkClass}>Workers</NavLink>
            <NavLink to="/dead-letter" className={linkClass}>Dead Letter</NavLink>
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm text-ink-300">
          <span className="font-mono">{user?.email}</span>
          <button onClick={logout} className="btn-ghost">Sign out</button>
        </div>
      </div>
    </header>
  );
}
