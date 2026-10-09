import type { ProviderUsage } from "../api";
import { providerLabel } from "./ModelMenu";

const compact = (n: number) =>
  n >= 1e6 ? `${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(n >= 1e4 ? 0 : 1)}k` : String(n);

interface Props {
  provider: string;
  usage: ProviderUsage | undefined;
  /** tokens used by the run in progress, not yet saved */
  live: { input: number; output: number };
}

/** Tokens used this month by the selected model, and what is left of its budget. */
export function UsageMeter({ provider, usage, live }: Props) {
  if (!usage) return null;
  const input = usage.input + live.input;
  const output = usage.output + live.output;
  const total = input + output;
  const remaining = usage.budget == null ? null : Math.max(usage.budget - total, 0);
  const share = usage.budget ? Math.min(total / usage.budget, 1) : 0;
  const level = share >= 0.9 ? "danger" : share >= 0.7 ? "warn" : "ok";
  const title = [
    `${providerLabel(provider)} tokens this month`,
    `Input: ${input.toLocaleString()}  Output: ${output.toLocaleString()}`,
    usage.budget == null
      ? "No budget set. Add the provider's TOKEN_BUDGET in .env to see a remaining balance."
      : `Budget: ${usage.budget.toLocaleString()}  Remaining: ${remaining!.toLocaleString()}`,
  ].join("\n");

  return (
    <span className="token-meter" title={title}>
      <span className="meter-text">
        <strong>{compact(total)}</strong> used
        {remaining != null && <> · <strong className={`meter-${level}`}>{compact(remaining)}</strong> left</>}
      </span>
      {usage.budget != null && (
        <span className="meter-bar" role="progressbar" aria-label="Token budget used"
              aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(share * 100)}>
          <span className={`meter-fill meter-${level}`} style={{ width: `${share * 100}%` }} />
        </span>
      )}
    </span>
  );
}
