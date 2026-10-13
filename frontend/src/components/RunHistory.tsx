import type { RunSummary } from "../api";
import * as fmt from "../format";
import { Icon } from "./Icon";

const dateFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

interface Props {
  runs: RunSummary[] | null;
  error: string | null;
  activeRunId: string | undefined;
  onOpen: (run: RunSummary) => void;
  onCollapse: () => void;
  /** Reviewers and admins see everyone's runs, so show whose each one is. */
  currentEmail?: string;
}

/** Totals over the runs in the list: estimated cost and average processing time. */
function totals(runs: RunSummary[]) {
  const traced = runs.filter((r) => r.duration_ms != null);
  return {
    cost: runs.reduce((t, r) => t + (r.cost_usd ?? 0), 0),
    avg: traced.length ? traced.reduce((t, r) => t + r.duration_ms!, 0) / traced.length : null,
  };
}

function Summary({ runs }: { runs: RunSummary[] }) {
  const { cost, avg } = totals(runs);
  const approved = runs.filter((r) => r.status === "APPROVED").length;
  return (
    <section className="card history-summary" aria-label="Run totals">
      <header className="card-head">
        <h2 className="card-title">Cost &amp; runs</h2>
        <span className="tag ok mono">{approved}/{runs.length} approved</span>
      </header>
      <p className="big-number">{fmt.cost(cost)} <span className="muted mono small">estimated, last {runs.length} runs</span></p>
      <div className="mini-stats">
        <span><span className="mini-label">Runs</span><b>{runs.length}</b></span>
        <span><span className="mini-label">Avg processing time</span><b className="cyan">{fmt.duration(avg)}</b></span>
      </div>
    </section>
  );
}

/** The rail when the sidebar is closed: an expand button, the run count and the total cost. */
export function CollapsedRail({ runs, onExpand }: { runs: RunSummary[] | null; onExpand: () => void }) {
  const count = runs?.length ?? 0;
  const { cost } = totals(runs ?? []);
  return (
    <aside className="card mini-rail" aria-label="Recent runs (hidden)">
      <button type="button" className="mini-expand" onClick={onExpand} aria-label="Show recent runs"
              title="Show recent runs (⌘/Ctrl + B)">
        <Icon name="railExpand" size={18} />
      </button>
      <span className="mini-divider" aria-hidden="true" />
      <button type="button" className="mini-stat" onClick={onExpand} title={`${count} recent runs`}>
        <span className="mini-icon"><Icon name="clock" size={17} /></span>
        <b className="mono">{count}</b>
      </button>
      <button type="button" className="mini-stat cost" onClick={onExpand}
              title={`${fmt.cost(cost)} estimated cost of the last ${count} runs`}>
        <span className="mini-icon"><Icon name="dollar" size={17} /></span>
        <b className="mono">{fmt.cost(cost)}</b>
      </button>
      <span className="live-dot on" aria-hidden="true" />
      <span className="mini-caption mono" aria-hidden="true">Runs feed</span>
    </aside>
  );
}

export function RunHistory({ runs, error, activeRunId, onOpen, onCollapse, currentEmail }: Props) {
  return (
    <aside id="runs-rail" className="history" aria-label="Recent runs">
      {runs && runs.length > 0 && <Summary runs={runs} />}
      <section className="card history-list">
        <header className="card-head">
          <h2 className="card-title"><Icon name="clock" size={15} /> Recent runs</h2>
          <button type="button" className="icon-btn" onClick={onCollapse} aria-label="Hide recent runs"
                  title="Hide recent runs (⌘/Ctrl + B)">
            <Icon name="railCollapse" size={15} />
          </button>
        </header>
        {error && <p className="muted small">Could not load runs: {error}</p>}
        {runs && runs.length === 0 && <p className="muted small">No runs yet. Your recommendations will appear here.</p>}
        <ul>
          {runs?.map((r) => {
            const approved = r.status === "APPROVED";
            return (
              <li key={r.run_id}>
                <button
                  type="button"
                  className={`run ${r.run_id === activeRunId ? "active" : ""}`}
                  onClick={() => onOpen(r)}
                  disabled={!r.has_report}
                  title={r.has_report ? "Open this recommendation" : "The report file for this run is missing"}
                >
                  <span className="run-head">
                    <span className={`dot ${approved ? "ok" : "warn"}`} />
                    <span className="run-title">{r.title ?? `Run ${r.run_id}`}</span>
                    <span className="run-date mono">{dateFmt.format(new Date(r.created_at))}</span>
                  </span>
                  <span className="run-meta">
                    <span className={`tag mono ${approved ? "ok" : "warn"}`}>
                      {approved ? "Approved" : "Escalated"}{r.overall != null && <> · {r.overall.toFixed(1)}</>}
                    </span>
                    {r.rounds > 1 && <span className="muted mono small">{r.rounds} review rounds</span>}
                    {r.edited && <span className="pill edited" title="Edited after generation">Edited</span>}
                  </span>
                  {r.domains.length > 0 && (
                    <span className="run-domains">{r.domains.map((d) => <span key={d} className="domain mono">{d}</span>)}</span>
                  )}
                  {currentEmail && r.owner && r.owner !== currentEmail && (
                    <span className="run-owner">by {r.owner}</span>
                  )}
                  {r.duration_ms != null && (
                    <span className="run-cost mono" title="Processing time · tokens · estimated cost">
                      <span>{fmt.duration(r.duration_ms)} · {fmt.tokens(r.tokens)} tok</span>
                      <span className={approved ? "ok-text" : ""}>{fmt.cost(r.cost_usd)}</span>
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </section>
    </aside>
  );
}
