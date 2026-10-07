import { useRef, useState } from "react";
import { api, type Scenario } from "../api";
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
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const submit = () => {
    const value = text.trim();
    if (!value || busy) return;
    onSubmit(value);
    setText("");
  };

  const upload = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    setUploadError(null);
    try {
      setText(await api.intake(file));
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : String(err));
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

  return (
    <section className="card composer" aria-label="Requirement">
      <label htmlFor="requirement" className="composer-label">
        {awaitingAnswer ? "Your answer" : hasConversation ? "Refine the requirement" : "Requirement"}
      </label>
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
      {!hasConversation && scenarios.length > 0 && (
        <div className="examples">
          <span className="muted">Examples:</span>
          {scenarios.map((s) => (
            <button key={s.name} type="button" className="chip" onClick={() => setText(s.text)} disabled={busy}
                    title={s.text}>
              {s.name}
            </button>
          ))}
        </div>
      )}
      {uploadError && <p className="inline-error"><Icon name="alert" size={14} /> {uploadError}</p>}
      <div className="composer-actions">
        <input ref={fileInput} type="file" accept=".txt,.md,.pdf,.docx" hidden
               onChange={(e) => upload(e.target.files?.[0])} />
        <button type="button" className="btn ghost" onClick={() => fileInput.current?.click()}
                disabled={busy || uploading}>
          {uploading ? <Spinner /> : <Icon name="upload" />} Upload file
        </button>
        <span className="muted hint">.txt, .md, .pdf or .docx · ⌘/Ctrl + Enter to send</span>
        <button type="button" className="btn primary" onClick={submit} disabled={busy || !text.trim()}>
          {busy ? <Spinner /> : <Icon name="send" />}
          {busy ? "Working…" : awaitingAnswer ? "Send answer" : "Analyze requirement"}
        </button>
      </div>
    </section>
  );
}
