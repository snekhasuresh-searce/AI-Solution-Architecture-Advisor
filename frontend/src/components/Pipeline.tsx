import { agentLabel, isSpecialist, type AgentStatus, type State } from "../state";
import { Icon, Spinner } from "./Icon";

const STATUS_TEXT: Record<AgentStatus | "standby", string> = {
  done: "Completed",
  running: "Running…",
  pending: "Queued",
  standby: "Standby",
};

function StatusMark({ status }: { status: AgentStatus | undefined }) {
  if (status === "running") return <Spinner size={12} />;
  if (status === "done") return <span className="mark done"><Icon name="check" size={11} /></span>;
  return <span className="mark pending" />;
}

function StageCard({ n, step, name, status, note }: {
  n: number; step: string; name: string; status: AgentStatus | "standby"; note?: string;
}) {
  return (
    <li className={`stage-card ${status}`}>
      <span className="stage-head">
        <span className="stage-num">{String(n).padStart(2, "0")} · {step}</span>
        {status === "done" && <Icon name="check" size={14} />}
        {status === "running" && <span className="pulse" aria-hidden="true" />}
      </span>
      <span className="stage-name">{name}</span>
      <span className="stage-status">{STATUS_TEXT[status]}{note && ` · ${note}`}</span>
    </li>
  );
}

/** Running if any specialist is, done once all are, otherwise queued. */
function groupStatus(statuses: (AgentStatus | undefined)[]): AgentStatus | "standby" {
  if (!statuses.length) return "standby";
  if (statuses.some((s) => s === "running")) return "running";
  if (statuses.every((s) => s === "done")) return "done";
  return "pending";
}

export function Pipeline({ state }: { state: State }) {
  const { agents, status, reworks, reviewRounds, busy } = state;
  if (!agents.length) return null;
  const specialists = agents.filter(isSpecialist);
  const stage = (name: string) => (agents.includes(name) ? status[name] ?? "pending" : "standby");

  return (
    <section className="card pipeline" aria-label="Agent progress">
      <header className="card-head">
        <h2 className="card-title"><span className={`live-dot ${busy ? "on" : ""}`} aria-hidden="true" /> Agents</h2>
        <span className="card-meta mono">
          {specialists.length > 0 && <>specialists: <b>{specialists.length}</b></>}
          {reviewRounds > 0 && <> · review rounds: <b>{reviewRounds}</b></>}
        </span>
      </header>
      <ol className="stages">
        <StageCard n={1} step="Analyze" name="Requirement analyzer" status={stage("analyzer")} />
        <StageCard n={2} step="Design" name={specialists.length ? `${specialists.length} specialists, in parallel` : "Specialists"}
                   status={groupStatus(specialists.map((a) => status[a]))} />
        <StageCard n={3} step="Review" name="Reviewer" status={stage("reviewer")}
                   note={reviewRounds ? `round ${reviewRounds}` : undefined} />
        <StageCard n={4} step="Estimate" name="Delivery estimator" status={stage("estimator")} />
        <StageCard n={5} step="Diagram" name="Solution architect" status={stage("architect")} />
      </ol>
      {specialists.length > 0 && (
        <div className="specialists">
          <span className="sub-title">Specialist agents</span>
          <ul>
            {specialists.map((a) => (
              <li key={a} className={`node ${status[a] ?? "pending"}`}>
                <StatusMark status={status[a]} />
                <span className="node-name">{agentLabel(a)}</span>
                {reworks[a] ? <span className="node-note">rework ×{reworks[a]}</span>
                  : <span className="node-state">{STATUS_TEXT[status[a] ?? "pending"]}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
