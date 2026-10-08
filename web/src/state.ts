import type { AdvisorEvent, AgentName, RunStatus } from "./api";

export type AgentStatus = "pending" | "running" | "done";

export interface LogEntry {
  id: number;
  role: "user" | "advisor" | "error";
  text: string;
}

export interface Report {
  runId: string;
  status: RunStatus;
  markdown: string;
  /** true when produced in this session, false when opened from history */
  live: boolean;
}

export interface State {
  sessionId: string | null;
  busy: boolean;
  log: LogEntry[];
  /** Pipeline order: analyzer, selected specialists, reviewer */
  agents: AgentName[];
  status: Record<AgentName, AgentStatus>;
  reworks: Record<AgentName, number>;
  reviewRounds: number;
  report: Report | null;
  /** The last turn ended without a report: the advisor is waiting for an answer */
  awaitingAnswer: boolean;
  turnHadReport: boolean;
}

export type Action =
  | { type: "session"; id: string }
  | { type: "submit"; text: string }
  | { type: "event"; event: AdvisorEvent }
  | { type: "fail"; message: string }
  | { type: "finish" }
  | { type: "open_report"; report: Report }
  | { type: "reset" };

export const initialState: State = {
  sessionId: null,
  busy: false,
  log: [],
  agents: [],
  status: {},
  reworks: {},
  reviewRounds: 0,
  report: null,
  awaitingAnswer: false,
  turnHadReport: false,
};

let nextId = 1;
const entry = (role: LogEntry["role"], text: string): LogEntry => ({ id: nextId++, role, text });

const STAGES = new Set(["analyzer", "reviewer", "estimator"]);
export const isSpecialist = (a: AgentName) => !STAGES.has(a);

function onEvent(state: State, event: AdvisorEvent): State {
  switch (event.type) {
    case "agent_start":
      return { ...state, agents: state.agents.length ? state.agents : [event.agent],
               status: { ...state.status, [event.agent]: "running" } };
    case "plan": {
      const status: State["status"] = { ...state.status, reviewer: "pending", estimator: "pending" };
      for (const a of event.agents) status[a] = "running";
      return { ...state, agents: ["analyzer", ...event.agents, "reviewer", "estimator"], status };
    }
    case "agent_done": {
      const status = { ...state.status, [event.agent]: "done" as const };
      let reviewRounds = state.reviewRounds;
      if (event.agent === "reviewer") {
        reviewRounds += 1;
      } else if (isSpecialist(event.agent) && !state.agents.some((a) => isSpecialist(a) && status[a] === "running")) {
        status.reviewer = "running"; // every specialist has finished
      }
      return { ...state, status, reviewRounds };
    }
    case "rework": {
      const status: State["status"] = { ...state.status, reviewer: "pending" };
      const reworks = { ...state.reworks };
      const agents = [...state.agents];
      for (const a of event.agents) {
        status[a] = "running";
        reworks[a] = (reworks[a] ?? 0) + 1;
        if (!agents.includes(a)) agents.splice(agents.indexOf("reviewer"), 0, a); // reviewer pulled in a new specialist
      }
      return { ...state, agents, status, reworks };
    }
    case "message":
      return { ...state, log: [...state.log, entry("advisor", event.text)] };
    case "report":
      return { ...state, turnHadReport: true,
               report: { runId: event.run_id, status: event.status, markdown: event.markdown, live: true } };
    case "error":
      return { ...state, log: [...state.log, entry("error", event.message)] };
    case "end":
      return state;
  }
}

export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "session":
      return { ...state, sessionId: action.id };
    case "submit":
      return { ...state, busy: true, awaitingAnswer: false, turnHadReport: false, agents: [], status: {},
               reworks: {}, reviewRounds: 0, log: [...state.log, entry("user", action.text)] };
    case "event":
      return onEvent(state, action.event);
    case "fail":
      return { ...state, log: [...state.log, entry("error", action.message)] };
    case "finish": {
      // Mark anything still "running" as stopped, so an error does not leave spinners behind.
      const status = Object.fromEntries(
        Object.entries(state.status).map(([a, s]) => [a, s === "running" ? "pending" : s]),
      ) as State["status"];
      const stoppedEarly = !state.turnHadReport && state.agents.length <= 1;
      return { ...state, busy: false, status, awaitingAnswer: stoppedEarly && state.log.at(-1)?.role === "advisor" };
    }
    case "open_report":
      return { ...state, report: action.report };
    case "reset":
      return { ...initialState };
  }
}

export const AGENT_LABELS: Record<string, string> = {
  analyzer: "Requirement analyzer",
  frontend: "Frontend",
  uiux: "UI/UX",
  backend: "Backend",
  database: "Database",
  cloud: "Cloud",
  security: "Security",
  performance: "Performance",
  aiml: "AI/ML",
  reviewer: "Reviewer",
  estimator: "Delivery estimator",
};

export const agentLabel = (a: AgentName) => AGENT_LABELS[a] ?? a;
