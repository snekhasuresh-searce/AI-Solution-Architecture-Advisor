import { useRef, useState } from "react";
import { api, type Scenario } from "../api";
import { useToast } from "../toast";
import { Icon, Spinner } from "./Icon";

interface Props {
  busy: boolean;
  awaitingAnswer: boolean;
  hasConversation: boolean;
  scenarios: Scenario[];
  onSubmit: (text: string) => void;
}

export function Composer({ busy, awaitingAnswer, hasConversation, scenarios, onSubmit }: Props) {
  const [text, setText] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const toast = useToast();

  const submit = () => {
    const value = text.trim();
    if (!value || busy) return;
    onSubmit(value);
    setText("");
  };

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    try {
      const extracted = await api.intake(file);
      if (!extracted.trim()) {
        toast.error(`No text found in ${file.name}`, { message: "Scanned PDFs need text; try a .docx or .txt version." });
        return;
      }
      setText(extracted);
      toast.success(`Loaded ${file.name}`, { message: "Review the requirement, then press Analyze." });
    } catch (err) {
      toast.error(`Could not read ${file.name}`, { message: err instanceof Error ? err.message : String(err) });
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const placeholder = awaitingAnswer
    ? "Answer the questions above, or reply “use your assumptions”."
    : hasConversation
      ? "Add details or changes and run again with this context…"
      : "Describe what you want to build. For example: a responsive company website with Home, About and Contact pages, frontend only.";

  const title = awaitingAnswer ? "Your answer" : hasConversation ? "Refine the requirement" : "Requirement";
  const examples = !hasConversation && scenarios.length > 0;

  return (
    <section className="card composer" aria-label="Requirement">
      <header className="card-head">
        <label htmlFor="requirement" className="card-title">
          <span className={`live-dot ${awaitingAnswer ? "on" : ""}`} aria-hidden="true" /> {title}
        </label>
        {awaitingAnswer && <span className="card-meta">The advisor is waiting for your answer</span>}
      </header>
      {(awaitingAnswer || examples) && (
        <div className="examples">
          <span className="muted mono">{awaitingAnswer ? "Quick reply:" : "Examples:"}</span>
          {awaitingAnswer && (
            <button type="button" className="chip" onClick={() => setText("Use your assumptions.")} disabled={busy}>
              <Icon name="bolt" size={12} /> Use your assumptions
            </button>
          )}
          {examples && scenarios.map((s) => (
            <button key={s.name} type="button" className="chip" onClick={() => setText(s.text)} disabled={busy}
                    title={s.text}>
              <Icon name="bolt" size={12} /> {s.name}
            </button>
          ))}
        </div>
      )}
      <div className="deck">
        <textarea
          id="requirement"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
          }}
          placeholder={placeholder}
          rows={hasConversation ? 3 : 6}
          disabled={busy}
        />
        <div className="deck-shelf">
          <span className="ftypes">
            Supported: <code>.txt</code> <code>.md</code> <code>.pdf</code> <code>.docx</code>
          </span>
          <span className="shortcut"><kbd>⌘/Ctrl</kbd> + <kbd>Enter</kbd> to send</span>
        </div>
      </div>
      <div className="composer-actions">
        <input ref={fileInput} type="file" accept=".txt,.md,.pdf,.docx" hidden
               onChange={(e) => upload(e.target.files?.[0])} />
        <button type="button" className="btn" onClick={() => fileInput.current?.click()}
                disabled={busy || uploading}>
          {uploading ? <Spinner /> : <Icon name="upload" />} Upload file
        </button>
        {text && !busy && (
          <button type="button" className="btn ghost" onClick={() => setText("")}>Clear</button>
        )}
        <button type="button" className="btn primary" onClick={submit} disabled={busy || !text.trim()}>
          {busy ? <Spinner /> : null}
          {busy ? "Working…" : awaitingAnswer ? "Send answer" : "Analyze requirement"}
          {!busy && <Icon name="send" />}
        </button>
      </div>
    </section>
  );
}
