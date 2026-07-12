const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function getToken() {
  return localStorage.getItem("orbit_token");
}

export function setToken(token) {
  if (token) localStorage.setItem("orbit_token", token);
  else localStorage.removeItem("orbit_token");
}

async function request(path, { method = "GET", body, params } = {}) {
  let url = `${BASE_URL}${path}`;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
    ).toString();
    if (qs) url += `?${qs}`;
  }

  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const resp = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (resp.status === 204) return null;

  const data = await resp.json().catch(() => null);
  if (!resp.ok) {
    const detail = data?.detail || resp.statusText || "Request failed";
    const error = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    error.status = resp.status;
    throw error;
  }
  return data;
}

export const api = {
  register: (payload) => request("/api/auth/register", { method: "POST", body: payload }),
  login: (payload) => request("/api/auth/login", { method: "POST", body: payload }),
  me: () => request("/api/auth/me"),

  listProjects: () => request("/api/projects"),
  createProject: (payload) => request("/api/projects", { method: "POST", body: payload }),
  deleteProject: (id) => request(`/api/projects/${id}`, { method: "DELETE" }),

  listQueues: (projectId) => request(`/api/projects/${projectId}/queues`),
  createQueue: (projectId, payload) => request(`/api/projects/${projectId}/queues`, { method: "POST", body: payload }),
  getQueue: (queueId) => request(`/api/queues/${queueId}`),
  updateQueue: (queueId, payload) => request(`/api/queues/${queueId}`, { method: "PATCH", body: payload }),
  pauseQueue: (queueId) => request(`/api/queues/${queueId}/pause`, { method: "POST" }),
  resumeQueue: (queueId) => request(`/api/queues/${queueId}/resume`, { method: "POST" }),
  queueStats: (queueId) => request(`/api/queues/${queueId}/stats`),
  deleteQueue: (queueId) => request(`/api/queues/${queueId}`, { method: "DELETE" }),

  createJob: (queueId, payload) => request(`/api/queues/${queueId}/jobs`, { method: "POST", body: payload }),
  createBatchJobs: (queueId, payload) => request(`/api/queues/${queueId}/jobs/batch`, { method: "POST", body: payload }),
  listJobs: (queueId, params) => request(`/api/queues/${queueId}/jobs`, { params }),
  getJob: (jobId) => request(`/api/jobs/${jobId}`),
  retryJob: (jobId) => request(`/api/jobs/${jobId}/retry`, { method: "POST" }),
  cancelJob: (jobId) => request(`/api/jobs/${jobId}/cancel`, { method: "POST" }),

  listWorkers: () => request("/api/workers"),

  systemHealth: () => request("/api/dashboard/health"),
  deadLetterEntries: () => request("/api/dashboard/dead-letter"),
  throughputSeries: () => request("/api/dashboard/throughput-series"),
};
