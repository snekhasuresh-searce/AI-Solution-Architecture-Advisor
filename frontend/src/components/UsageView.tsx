import { useEffect, useState } from "react";
import { api, type Usage, type UsageGroup, type UsageRun } from "../api";
import * as fmt from "../format";
import { agentLabel } from "../state";
import { Icon, Spinner } from "./Icon";

const PERIODS = [7, 30, 90];
const agentName = (k: string | null) =>
  !k ? "—" : agentLabel(k === "requirement_analyzer" ? "analyzer" : k.replace(/_agent$/, ""));

function GroupTable({ title, rows, name, unit }: {
  title: string; rows: UsageGroup[]; name: (g: UsageGroup) => string; unit: string;
}) {
  // Share by cost; by tokens when nothing was priced (mock or local models).
  const byCost = rows.some((r) => r.cost_usd > 0);
  const total = rows.reduce((t, r) => t + (byCost ? r.cost_usd : r.tokens), 0);
  return (
    <section className="card usage-card">
      <h2 className="card-title">{title}</h2>
      {rows.length === 0 ? <p className="muted small">No data in this period.</p> : (
        <div className="table-wrap">
          <table className="trace-table">
            <thead><tr><th>{unit}</th><th>Count</th><th>Time</th><th>Tokens</th><th>Cost</th><th>Share</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key ?? "none"}>
                  <td>{name(r)}{r.unpriced > 0 && <span className="muted small"> ({r.unpriced} unpriced)</span>}</td>
                  <td>{r.count}</td>
                  <td>{fmt.duration(r.duration_ms)}</td>
                  <td>{fmt.tokens(r.tokens)}</td>
                  <td>{fmt.cost(r.cost_usd)}</td>
                  <td><span className="share"><span style={{ width: `${total ? Math.round(((byCost ? r.cost_usd : r.tokens) / total) * 100) : 0}%` }} /></span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function RunList({ title, runs, onOpen }: { title: string; runs: UsageRun[]; onOpen: (runId: string) => void }) {
  return (
    <section className="card usage-card">
      <h2 className="card-title">{title}</h2>
      {runs.length === 0 ? <p className="muted small">No runs in this period.</p> : (
        <ol className="outliers">
          {runs.map((r) => (
            <li key={r.run_id}>
              <button type="button" className="run" onClick={() => onOpen(r.run_id)} title="Open this run">
                <span className="run-title mono">{r.run_id}</span>
                <span className="run-meta">
                  {fmt.duration(r.duration_ms)} · {fmt.tokens(r.tokens)} tokens · {fmt.cost(r.cost_usd)}
                </span>
                <span className="run-owner">by {r.email}</span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export function UsageView({ onOpenRun }: { onOpenRun: (runId: string) => void }) {
  const [days, setDays] = useState(30);
  const [data, setData] = useState<Usage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    api.usage(days).then(setData).catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [days]);

  const t = data?.totals;
  return (
    <div className="usage">
      <div className="admin-head">
        <div>
          <h1>Usage</h1>
          <p className="muted small">Time, tokens and estimated model cost across everyone's runs.</p>
        </div>
        <div className="tabs" role="group" aria-label="Period">
          {PERIODS.map((d) => (
            <button key={d} type="button" className={`tab ${d === days ? "active" : ""}`} onClick={() => setDays(d)}>
              {d} days
            </button>
          ))}
        </div>
      </div>
      {error && <p className="inline-error" role="alert"><Icon name="alert" size={14} /> {error}</p>}
      {!data && !error && <p className="muted"><Spinner /> Loading usage…</p>}
      {data && t && (
        <>
          <div className="stat-row">
            <div className="stat"><span className="stat-value">{t.count}</span><span className="stat-label">turns</span></div>
            <div className="stat"><span className="stat-value">{fmt.cost(t.cost_usd)}</span><span className="stat-label">estimated cost</span></div>
            <div className="stat"><span className="stat-value">{fmt.tokens(t.tokens)}</span><span className="stat-label">tokens</span></div>
            <div className="stat">
              <span className="stat-value">{fmt.duration(t.count ? Math.round(t.duration_ms / t.count) : 0)}</span>
              <span className="stat-label">average per turn</span>
            </div>
          </div>
          <div className="usage-grid">
            <RunList title="Most expensive runs" runs={data.most_expensive} onOpen={onOpenRun} />
            <RunList title="Slowest runs" runs={data.slowest} onOpen={onOpenRun} />
          </div>
          <GroupTable title="By person" rows={data.by_user} name={(g) => g.email ?? g.key ?? "—"} unit="Person" />
          <GroupTable title="By model" rows={data.by_model} name={(g) => g.key ?? "—"} unit="Model" />
          <GroupTable title="By agent" rows={data.by_agent} name={(g) => agentName(g.key)} unit="Agent" />
        </>
      )}
    </div>
  );
}
