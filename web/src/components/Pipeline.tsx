import { agentLabel, type AgentStatus, type State } from "../state";
import { Icon, Spinner } from "./Icon";

function StatusMark({ status }: { status: AgentStatus | undefined }) {
  if (status === "running") return <Spinner />;
  if (status === "done") return <span className="mark done"><Icon name="check" size={12} /></span>;
  return <span className="mark pending" />;
}

function Node({ name, status, note }: { name: string; status: AgentStatus | undefined; note?: string }) {
  return (
    <li className={`node ${status ?? "pending"}`}>
      <StatusMark status={status} />
      <span className="node-name">{agentLabel(name)}</span>
      {note && <span className="node-note">{note}</span>}
    </li>
  );
}

export function Pipeline({ state }: { state: State }) {
  const { agents, status, reworks, reviewRounds } = state;
  if (!agents.length) return null;
  const specialists = agents.filter((a) => a !== "analyzer" && a !== "reviewer");
  const hasReviewer = agents.includes("reviewer");

  return (
    <section className="card pipeline" aria-label="Agent progress">
      <h2 className="card-title">Agents</h2>
      <ol className="flow">
        <li className="stage">
          <span className="stage-label">1 · Analyze</span>
          <ul><Node name="analyzer" status={status.analyzer} /></ul>
        </li>
        {specialists.length > 0 && (
          <li className="stage">
            <span className="stage-label">2 · Specialists, in parallel</span>
            <ul className="grid">
              {specialists.map((a) => (
                <Node key={a} name={a} status={status[a]}
                      note={reworks[a] ? `rework ×${reworks[a]}` : undefined} />
              ))}
            </ul>
          </li>
        )}
        {hasReviewer && (
          <li className="stage">
            <span className="stage-label">3 · Review</span>
            <ul>
              <Node name="reviewer" status={status.reviewer}
                    note={reviewRounds ? `round ${reviewRounds}` : undefined} />
            </ul>
          </li>
        )}
      </ol>
    </section>
  );
}
