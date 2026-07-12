import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Navbar from "./components/Navbar";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Projects from "./pages/Projects";
import ProjectDetail from "./pages/ProjectDetail";
import QueueDetail from "./pages/QueueDetail";
import JobDetail from "./pages/JobDetail";
import Workers from "./pages/Workers";
import DeadLetter from "./pages/DeadLetter";

function ProtectedLayout({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-ink-500">Loading...</div>;
  if (!user) return <Navigate to="/login" replace />;
  return (
    <div className="min-h-screen">
      <Navbar />
      <main className="max-w-7xl mx-auto px-6 py-8">{children}</main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<ProtectedLayout><Dashboard /></ProtectedLayout>} />
          <Route path="/projects" element={<ProtectedLayout><Projects /></ProtectedLayout>} />
          <Route path="/projects/:projectId" element={<ProtectedLayout><ProjectDetail /></ProtectedLayout>} />
          <Route path="/queues/:queueId" element={<ProtectedLayout><QueueDetail /></ProtectedLayout>} />
          <Route path="/jobs/:jobId" element={<ProtectedLayout><JobDetail /></ProtectedLayout>} />
          <Route path="/workers" element={<ProtectedLayout><Workers /></ProtectedLayout>} />
          <Route path="/dead-letter" element={<ProtectedLayout><DeadLetter /></ProtectedLayout>} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
