import { useEffect, useRef } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { LogEntry } from "../state";
import { Icon, Spinner } from "./Icon";

const ROLE_LABEL: Record<LogEntry["role"], string> = { user: "You", advisor: "Advisor", error: "Error" };
const ROLE_BADGE: Record<LogEntry["role"], string> = { user: "YOU", advisor: "AI", error: "!" };

export function Activity({ log, busy }: { log: LogEntry[]; busy: boolean }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [log.length]);

  if (!log.length) return null;
  const turns = log.filter((e) => e.role === "user").length;
  return (
    <section className="card activity" aria-label="Activity" aria-live="polite" aria-busy={busy}>
      <header className="card-head">
        <h2 className="card-title">Dialogue</h2>
        <span className="card-meta mono">{turns} turn{turns === 1 ? "" : "s"}</span>
      </header>
      <ol className="log">
        {log.map((e) => (
          <li key={e.id} className={`log-entry ${e.role}`}>
            <span className="log-badge" aria-hidden="true">{ROLE_BADGE[e.role]}</span>
            <div className="log-body">
              {e.role !== "user" && (
                <span className="log-role">
                  {e.role === "error" ? <Icon name="alert" size={13} /> : <span className="dot cyan" />} {ROLE_LABEL[e.role]}
                </span>
              )}
              {e.role === "user" && <span className="sr-only">{ROLE_LABEL.user}: </span>}
              <div className="log-text">
                {e.role === "user" ? <p>{e.text}</p> : <Markdown remarkPlugins={[remarkGfm]}>{e.text}</Markdown>}
              </div>
            </div>
          </li>
        ))}
        {busy && (
          <li className="log-entry advisor thinking">
            <span className="log-badge" aria-hidden="true">AI</span>
            <div className="log-body"><span className="log-role"><Spinner size={12} /> Advisor is working…</span></div>
          </li>
        )}
      </ol>
      <div ref={end} />
    </section>
  );
}
