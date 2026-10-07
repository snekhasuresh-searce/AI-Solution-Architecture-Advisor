import type { RunSummary } from "../api";

const dateFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

interface Props {
  runs: RunSummary[] | null;
  error: string | null;
  activeRunId: string | undefined;
  onOpen: (run: RunSummary) => void;
}

export function RunHistory({ runs, error, activeRunId, onOpen }: Props) {
  return (
    <aside className="history" aria-label="Recent runs">
      <h2 className="card-title">Recent runs</h2>
      {error && <p className="muted small">Could not load runs: {error}</p>}
      {runs && runs.length === 0 && <p className="muted small">No runs yet. Your recommendations will appear here.</p>}
      <ul>
        {runs?.map((r) => (
          <li key={r.run_id}>
            <button
              type="button"
              className={`run ${r.run_id === activeRunId ? "active" : ""}`}
              onClick={() => onOpen(r)}
              disabled={!r.has_report}
              title={r.has_report ? "Open this recommendation" : "The report file for this run is missing"}
            >
              <span className="run-title">{r.title ?? `Run ${r.run_id}`}</span>
              <span className="run-meta">
                <span className={`dot ${r.status === "APPROVED" ? "ok" : "warn"}`} />
                {r.status === "APPROVED" ? "Approved" : "Escalated"}
                {r.overall != null && <> · {r.overall.toFixed(1)}</>}
                <span className="muted"> · {dateFmt.format(new Date(r.created_at))}</span>
              </span>
              {r.domains.length > 0 && <span className="run-domains">{r.domains.join(", ")}</span>}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}
