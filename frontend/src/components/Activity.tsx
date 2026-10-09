import { useEffect, useRef } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { LogEntry } from "../state";
import { Icon } from "./Icon";

const ROLE_LABEL: Record<LogEntry["role"], string> = { user: "You", advisor: "Advisor", error: "Error" };

export function Activity({ log, busy }: { log: LogEntry[]; busy: boolean }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [log.length]);

  if (!log.length) return null;
  return (
    <section className="card activity" aria-label="Activity" aria-live="polite" aria-busy={busy}>
      <h2 className="card-title">Activity</h2>
      <ol className="log">
        {log.map((e) => (
          <li key={e.id} className={`log-entry ${e.role}`}>
            <span className="log-role">
              {e.role === "error" && <Icon name="alert" size={13} />} {ROLE_LABEL[e.role]}
            </span>
            <div className="log-text">
              {e.role === "user" ? <p>{e.text}</p> : <Markdown remarkPlugins={[remarkGfm]}>{e.text}</Markdown>}
            </div>
          </li>
        ))}
      </ol>
      <div ref={end} />
    </section>
  );
}
