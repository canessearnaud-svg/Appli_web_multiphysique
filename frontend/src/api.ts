const TOKEN_KEY = "awm_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
}

async function req(path: string, options: RequestInit = {}) {
  const token = getToken();
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    logout();
    throw new Error("session expirée, reconnecte-toi");
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const api = {
  login: (email: string, name = "") =>
    req("/api/auth/dev-login", { method: "POST", body: JSON.stringify({ email, name }) }),
  projects: () => req("/api/projects"),
  createProject: (name: string, description = "") =>
    req("/api/projects", { method: "POST", body: JSON.stringify({ name, description }) }),
  project: (id: number) => req(`/api/projects/${id}`),
  diagrams: (pid: number) => req(`/api/projects/${pid}/diagrams`),
  saveDiagram: (pid: number, domain: string, data: object) =>
    req(`/api/projects/${pid}/diagrams/${domain}`, {
      method: "PUT",
      body: JSON.stringify({ domain, data }),
    }),
  analyze: (pid: number, domain: string, data: object) =>
    req(`/api/projects/${pid}/analyze`, { method: "POST", body: JSON.stringify({ domain, data }) }),
  createRun: (pid: number, type: string, params: object) =>
    req(`/api/projects/${pid}/runs`, { method: "POST", body: JSON.stringify({ type, params }) }),
  run: (id: number) => req(`/api/runs/${id}`),
};
