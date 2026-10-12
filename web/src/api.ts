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
  | { type: "usage"; provider: string; input: number; output: number }
  | { type: "error"; message: string }
  | { type: "end" };

export interface Health {
  status: string;
  provider: string;
  database: "postgres" | "sqlite";
}

export interface ProviderInfo {
  id: string;
  models: { strong: string; fast: string };
  /** false when the provider's API key is missing on the server */
  configured: boolean;
}

export interface ModelsInfo {
  default: string;
  providers: ProviderInfo[];
}

export interface ProviderUsage {
  input: number;
  output: number;
  total: number;
  /** monthly token budget from GEMINI_TOKEN_BUDGET / CLAUDE_TOKEN_BUDGET, null when unset */
  budget: number | null;
  remaining: number | null;
}

export interface Usage {
  period: "month";
  providers: Record<string, ProviderUsage>;
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
}

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

async function getJson<T>(url: string): Promise<T> {
  return (await check(await fetch(url))).json() as Promise<T>;
}

export const api = {
  health: () => getJson<Health>("/api/health"),
  models: () => getJson<ModelsInfo>("/api/models"),
  usage: () => getJson<Usage>("/api/usage"),
  scenarios: () => getJson<Scenario[]>("/api/scenarios"),
  runs: () => getJson<RunSummary[]>("/api/runs"),
  report: (runId: string) => getJson<{ run_id: string; markdown: string }>(`/api/runs/${runId}/report`),
  exportUrl: (runId: string, format: ExportFormat) => `/api/runs/${runId}/export/${format}`,
  diagramUrl: (runId: string, format: "svg" | "png", download = false) =>
    `/api/runs/${runId}/diagram.${format}${download ? "?download=true" : ""}`,

  async createSession(provider?: string): Promise<string> {
    const res = await check(await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider }),
    }));
    return ((await res.json()) as { session_id: string }).session_id;
  },

  async intake(file: File): Promise<string> {
    const form = new FormData();
    form.append("file", file);
    const res = await check(await fetch("/api/intake", { method: "POST", body: form }));
    return ((await res.json()) as { text: string }).text;
  },

  /** Send a message and yield progress events as the server streams them (NDJSON). */
  async *send(sessionId: string, text: string): AsyncGenerator<AdvisorEvent> {
    const res = await check(
      await fetch(`/api/sessions/${sessionId}/messages`, {
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
