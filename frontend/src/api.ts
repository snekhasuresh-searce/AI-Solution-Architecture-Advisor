// Typed client for the Python API (advisor/api.py).

export type AgentName = string; // "analyzer" | "reviewer" | specialist name
export type RunStatus = "APPROVED" | "ESCALATED";
export type ExportFormat = "docx" | "pdf";

export type AdvisorEvent =
  | { type: "agent_start"; agent: AgentName }
  | { type: "agent_done"; agent: AgentName }
  | { type: "plan"; agents: AgentName[] }
  | { type: "rework"; agents: AgentName[] }
  | { type: "message"; text: string }
  | { type: "report"; run_id: string; status: RunStatus; markdown: string }
  | { type: "error"; message: string }
  | { type: "end" };

export interface Health {
  status: string;
  provider: string;
  database: "postgres" | "sqlite";
}

export interface Scenario {
  name: string;
  text: string;
}

export interface RunSummary {
  run_id: string;
  created_at: string;
  domains: string[];
  agents: string[];
  status: RunStatus;
  overall: number | null;
  rounds: number;
  title: string | null;
  has_report: boolean;
  /** Email of the user who ran it; shown to reviewers and admins. */
  owner: string | null;
  /** From the run's trace; null for runs from before tracing. */
  duration_ms: number | null;
  tokens: number | null;
  cost_usd: number | null;
}

export interface TraceSpan {
  id: string;
  trace_id: string;
  parent_id: string | null;
  kind: "run" | "agent" | "llm";
  name: string;
  model: string | null;
  attempt: number;
  started_at: string;
  duration_ms: number;
  status: "ok" | "error";
  error: string | null;
  input_tokens: number;
  cached_tokens: number;
  output_tokens: number;
  thinking_tokens: number;
  /** null = no price configured for the model */
  cost_usd: number | null;
  attrs: Record<string, unknown>;
}

export interface UsageGroup {
  key: string | null;
  email?: string;
  count: number;
  duration_ms: number;
  tokens: number;
  cost_usd: number;
  unpriced: number;
}

export interface UsageRun {
  run_id: string;
  email: string;
  duration_ms: number;
  tokens: number;
  cost_usd: number | null;
  started_at: string;
}

export interface Usage {
  days: number;
  totals: UsageGroup;
  by_user: UsageGroup[];
  by_model: UsageGroup[];
  by_agent: UsageGroup[];
  slowest: UsageRun[];
  most_expensive: UsageRun[];
}

export type Role = "consultant" | "reviewer" | "admin";
export const ROLES: Role[] = ["consultant", "reviewer", "admin"];

export interface User {
  id: string;
  email: string;
  name: string | null;
  picture: string | null;
  role: Role;
}

export interface ManagedUser extends User {
  active: boolean;
  last_login_at: string | null;
}

export interface AuthConfig {
  mode: "google" | "dev";
  allowed_domains: string[];
  google_configured: boolean;
}

// Backend address. Empty = same origin (the Vite dev proxy, or a reverse proxy
// in production); set VITE_API_URL when the API is on another host.
const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");

/** Absolute URL for an API path such as "/api/runs" (also used for /api links inside reports). */
export const apiUrl = (path: string) => (path.startsWith("/api/") ? API_BASE + path : path);

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function check(res: Response): Promise<Response> {
  if (res.ok) return res;
  let detail = res.statusText;
  try {
    const body = await res.json();
    detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    // not JSON; keep the status text
  }
  throw new ApiError(detail || `Request failed (${res.status})`, res.status);
}

/** All API calls: send the session cookie, and the header the backend requires on writes. */
function request(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("X-Advisor-Client", "web");
  return fetch(apiUrl(path), { ...init, headers, credentials: "include" });
}

async function getJson<T>(url: string): Promise<T> {
  return (await check(await request(url))).json() as Promise<T>;
}

async function sendJson<T>(url: string, method: string, body?: unknown): Promise<T> {
  const res = await check(await request(url, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }));
  return res.json() as Promise<T>;
}

export const authApi = {
  config: () => getJson<AuthConfig>("/api/auth/config"),
  me: () => getJson<User>("/api/auth/me"),
  /** Full-page navigation to Google; comes back to `next` in this app. */
  googleLoginUrl: (next: string) => apiUrl(`/api/auth/login?next=${encodeURIComponent(next)}`),
  devLogin: (email: string, role?: Role) => sendJson<User>("/api/auth/dev-login", "POST", { email, role }),
  logout: () => sendJson<{ ok: boolean }>("/api/auth/logout", "POST"),
};

export const adminApi = {
  users: () => getJson<ManagedUser[]>("/api/admin/users"),
  update: (id: string, change: { role?: Role; active?: boolean }) =>
    sendJson<ManagedUser>(`/api/admin/users/${id}`, "PATCH", change),
};

export const api = {
  health: () => getJson<Health>("/api/health"),
  scenarios: () => getJson<Scenario[]>("/api/scenarios"),
  runs: () => getJson<RunSummary[]>("/api/runs"),
  report: (runId: string) => getJson<{ run_id: string; markdown: string }>(`/api/runs/${runId}/report`),
  trace: (runId: string) => getJson<{ run_id: string; spans: TraceSpan[] }>(`/api/runs/${runId}/trace`),
  usage: (days: number) => getJson<Usage>(`/api/usage?days=${days}`),
  exportUrl: (runId: string, format: ExportFormat) => apiUrl(`/api/runs/${runId}/export/${format}`),
  /** Path as it appears in report Markdown; wrap with apiUrl() to fetch it. */
  diagramPath: (runId: string, format: "svg" | "png", download = false) =>
    `/api/runs/${runId}/diagram.${format}${download ? "?download=true" : ""}`,

  async createSession(): Promise<string> {
    const res = await check(await request("/api/sessions", { method: "POST" }));
    return ((await res.json()) as { session_id: string }).session_id;
  },

  async intake(file: File): Promise<string> {
    const form = new FormData();
    form.append("file", file);
    const res = await check(await request("/api/intake", { method: "POST", body: form }));
    return ((await res.json()) as { text: string }).text;
  },

  /** Send a message and yield progress events as the server streams them (NDJSON). */
  async *send(sessionId: string, text: string): AsyncGenerator<AdvisorEvent> {
    const res = await check(
      await request(`/api/sessions/${sessionId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      }),
    );
    if (!res.body) throw new ApiError("The server returned no stream.", 500);
    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += value;
      let newline: number;
      while ((newline = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        if (line) yield JSON.parse(line) as AdvisorEvent;
      }
    }
    if (buffer.trim()) yield JSON.parse(buffer) as AdvisorEvent;
  },
};
