import { useEffect, useMemo, useState } from "react";
import { api, ApiError, type TraceSpan } from "../api";
import * as fmt from "../format";
import { agentLabel } from "../state";
import { Icon, Spinner } from "./Icon";

const ORCHESTRATOR = "solution_advisor";

/** ADK agent name -> the short name used across the app. */
const agentKey = (name: string) => (name === "requirement_analyzer" ? "analyzer" : name.replace(/_agent$/, ""));
const label = (name: string) => agentLabel(agentKey(name));

interface AgentRow {
  name: string;
  attempts: number;
  calls: number;
  ms: number;
  input: number;
  output: number;
  cost: number | null;
  errors: number;
}

function sumCost(spans: TraceSpan[]): number | null {
  return spans.some((s) => s.cost_usd == null) ? null : spans.reduce((t, s) => t + (s.cost_usd ?? 0), 0);
}

function analyse(spans: TraceSpan[]) {
  const turns = spans.filter((s) => s.kind === "run");
  const calls = spans.filter((s) => s.kind === "llm");
  const agents = spans.filter((s) => s.kind === "agent" && s.name !== ORCHESTRATOR);
  const wall = turns.reduce((t, s) => t + s.duration_ms, 0);
  const cost = sumCost(turns);
  const input = calls.reduce((t, s) => t + s.input_tokens, 0);
  const cached = calls.reduce((t, s) => t + s.cached_tokens, 0);
  const output = calls.reduce((t, s) => t + s.output_tokens + s.thinking_tokens, 0);

  const rows = new Map<string, AgentRow>();
  for (const a of agents) {
    const r = rows.get(a.name) ?? { name: a.name, attempts: 0, calls: 0, ms: 0, input: 0, output: 0, cost: 0, errors: 0 };
    r.attempts = Math.max(r.attempts, a.attempt);
    r.ms += a.duration_ms;
    r.input += a.input_tokens;
    r.output += a.output_tokens + a.thinking_tokens;
    r.cost = r.cost == null || a.cost_usd == null ? null : r.cost + a.cost_usd;
    rows.set(a.name, r);
  }
  for (const c of calls) {
    const r = rows.get(c.name);
    if (r) {
      r.calls += 1;
      if (c.status === "error") r.errors += 1;
    }
  }
  const byAgent = [...rows.values()].sort((a, b) => (b.cost ?? 0) - (a.cost ?? 0) || b.ms - a.ms);

  // Plain-language reasons, most useful first.
  const reasons: string[] = [];
  const slowest = [...byAgent].sort((a, b) => b.ms - a.ms)[0];
  if (slowest && wall) {
    reasons.push(`Slowest step: ${label(slowest.name)}, ${fmt.duration(slowest.ms)} (${fmt.percent(slowest.ms, wall)} of the run's time).`);
  }
  const priced = cost != null && cost > 0;
  const costliest = priced
    ? [...byAgent].sort((a, b) => (b.cost ?? 0) - (a.cost ?? 0))[0]
    : [...byAgent].sort((a, b) => b.input + b.output - (a.input + a.output))[0];
  if (costliest) {
    reasons.push(priced
      ? `Most expensive step: ${label(costliest.name)}, ${fmt.cost(costliest.cost)} (${fmt.percent(costliest.cost ?? 0, cost ?? 0)} of the cost).`
      : `Most tokens: ${label(costliest.name)}, ${fmt.tokens(costliest.input + costliest.output)} (${fmt.percent(costliest.input + costliest.output, input + output)}).`);
  }
  const reworked = agents.filter((a) => a.attempt > 1);
  if (reworked.length) {
    const names = [...new Set(reworked.map((a) => label(a.name)))].join(", ");
    const extraCost = sumCost(reworked);
    reasons.push(`Rework rounds re-ran ${names}, adding ${fmt.duration(reworked.reduce((t, a) => t + a.duration_ms, 0))}` +
      `${priced ? ` and ${fmt.cost(extraCost)}` : ""}.`);
  }
  if (turns.length > 1) {
    const earlier = [...turns].sort((a, b) => a.started_at.localeCompare(b.started_at)).slice(0, -1);
    reasons.push(`${earlier.length} earlier turn${earlier.length > 1 ? "s" : ""} asked clarifying questions ` +
      `(${fmt.duration(earlier.reduce((t, s) => t + s.duration_ms, 0))}, included in the totals).`);
  }
  const slowCall = [...calls].sort((a, b) => b.duration_ms - a.duration_ms)[0];
  if (slowCall && wall && slowCall.duration_ms > wall * 0.25) {
    reasons.push(`Longest single model call: ${label(slowCall.name)} on ${slowCall.model}, ${fmt.duration(slowCall.duration_ms)}` +
      ` for ${fmt.tokens(slowCall.output_tokens + slowCall.thinking_tokens)} output tokens.`);
  }
  if (cached) reasons.push(`${fmt.tokens(cached)} input tokens were served from the prompt cache at a lower price.`);
  const unpriced = [...new Set(calls.filter((c) => c.cost_usd == null).map((c) => c.model ?? "?"))];
  if (unpriced.length) reasons.push(`No price configured for ${unpriced.join(", ")}: add it to backend/advisor/data/pricing.json.`);

  const errors = spans.filter((s) => s.status === "error" && s.kind !== "run");
  return { turns, calls, wall, cost, input, cached, output, byAgent, reasons, errors };
}

function Timeline({ turn, spans }: { turn: TraceSpan; spans: TraceSpan[] }) {
  const start = Date.parse(turn.started_at);
  const total = Math.max(turn.duration_ms, 1);
  const rows = spans
    .filter((s) => s.kind === "agent" && s.trace_id === turn.trace_id && s.name !== ORCHESTRATOR)
    .sort((a, b) => a.started_at.localeCompare(b.started_at));
  return (
    <ol className="waterfall">
      {rows.map((s) => {
        const left = Math.min(Math.max((Date.parse(s.started_at) - start) / total, 0), 1);
        const width = Math.max(s.duration_ms / total, 0.004);
        const tip = `${label(s.name)}${s.attempt > 1 ? ` (attempt ${s.attempt})` : ""}: ${fmt.duration(s.duration_ms)}, ` +
          `${fmt.tokens(s.input_tokens)} in / ${fmt.tokens(s.output_tokens + s.thinking_tokens)} out, ${fmt.cost(s.cost_usd)}` +
          (s.error ? ` — ${s.error}` : "");
        return (
          <li key={s.id} title={tip}>
            <span className="wf-name">{label(s.name)}{s.attempt > 1 && <em> ×{s.attempt}</em>}</span>
            <span className="wf-track">
              <span className={`wf-bar ${s.status === "error" ? "error" : s.attempt > 1 ? "rework" : ""}`}
                    style={{ left: `${left * 100}%`, width: `${Math.min(width, 1 - left) * 100}%` }} />
            </span>
            <span className="wf-time">{fmt.duration(s.duration_ms)}</span>
          </li>
        );
      })}
    </ol>
  );
}

export function TracePanel({ runId }: { runId: string }) {
  const [spans, setSpans] = useState<TraceSpan[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSpans(null);
    setError(null);
    api.trace(runId).then((r) => setSpans(r.spans)).catch((err) =>
      setError(err instanceof ApiError && err.status === 404 ? "none" : err instanceof Error ? err.message : String(err)));
  }, [runId]);

  const a = useMemo(() => (spans ? analyse(spans) : null), [spans]);

  if (error === "none") return null; // run from before tracing
  if (error) return <p className="inline-error trace-error"><Icon name="alert" size={14} /> Run details unavailable: {error}</p>;
  if (!a) return <p className="muted small trace-loading"><Spinner /> Loading run details…</p>;

  const turns = [...a.turns].sort((x, y) => x.started_at.localeCompare(y.started_at));
  return (
    <details className="trace">
      <summary>
        <span className="trace-title">Run details</span>
        <span className="trace-chips">
          <span className="chip-stat" title="Total processing time">{fmt.duration(a.wall)}</span>
          <span className="chip-stat" title="Model calls">{a.calls.length} calls</span>
          <span className="chip-stat" title="Input / output tokens (output includes thinking)">
            {fmt.tokens(a.input)} in · {fmt.tokens(a.output)} out
          </span>
          <span className="chip-stat strong" title="Estimated model cost">{fmt.cost(a.cost)}</span>
          {a.errors.length > 0 && <span className="chip-stat bad">{a.errors.length} error{a.errors.length > 1 ? "s" : ""}</span>}
        </span>
      </summary>

      <div className="trace-body">
        <h3>Why it took this long and cost this much</h3>
        <ul className="reasons">{a.reasons.map((r) => <li key={r}>{r}</li>)}</ul>

        {a.errors.length > 0 && (
          <>
            <h3>Errors</h3>
            <ul className="trace-errors">
              {a.errors.map((e) => (
                <li key={e.id}><strong>{label(e.name)}</strong> {e.kind === "llm" ? `model call (${e.model})` : "agent"}: {e.error}</li>
              ))}
            </ul>
          </>
        )}

        <h3>Timeline</h3>
        {turns.map((t, i) => (
          <div key={t.id} className="turn">
            {turns.length > 1 && (
              <p className="muted small turn-label">
                Turn {i + 1}{i < turns.length - 1 ? " · clarifying questions" : ""} · {fmt.duration(t.duration_ms)} · {fmt.cost(t.cost_usd)}
              </p>
            )}
            <Timeline turn={t} spans={spans!} />
          </div>
        ))}
        <p className="muted small legend">
          <span className="wf-key" /> agent <span className="wf-key rework" /> rework <span className="wf-key error" /> error ·
          specialists overlap because they run in parallel
        </p>

        <h3>By agent</h3>
        <div className="table-wrap">
          <table className="trace-table">
            <thead>
              <tr><th>Agent</th><th>Runs</th><th>Calls</th><th>Time</th><th>Tokens in</th><th>Tokens out</th><th>Cost</th><th>Share</th></tr>
            </thead>
            <tbody>
              {a.byAgent.map((r) => {
                const share = a.cost ? (r.cost ?? 0) / a.cost : (r.input + r.output) / Math.max(a.input + a.output, 1);
                return (
                  <tr key={r.name}>
                    <td>{label(r.name)}{r.errors > 0 && <span className="bad-dot" title={`${r.errors} failed call(s)`} />}</td>
                    <td>{r.attempts}</td>
                    <td>{r.calls}</td>
                    <td>{fmt.duration(r.ms)}</td>
                    <td>{fmt.tokens(r.input)}</td>
                    <td>{fmt.tokens(r.output)}</td>
                    <td>{fmt.cost(r.cost)}</td>
                    <td><span className="share"><span style={{ width: `${Math.round(share * 100)}%` }} /></span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="muted small">
          Costs are estimates from token counts and the price table in <code>backend/advisor/data/pricing.json</code>;
          thinking tokens are billed as output. Share is by cost, or by tokens when the run cost nothing.
        </p>
      </div>
    </details>
  );
}
