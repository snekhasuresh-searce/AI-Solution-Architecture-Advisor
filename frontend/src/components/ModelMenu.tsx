import { useEffect, useRef, useState } from "react";
import type { ProviderInfo } from "../api";

export const PROVIDER_LABELS: Record<string, string> = { gemini: "Gemini", claude: "Claude", mock: "Mock", ollama: "Ollama" };
export const providerLabel = (id: string) => PROVIDER_LABELS[id] ?? id;

interface Props {
  providers: ProviderInfo[];
  selected: string;
  disabled: boolean;
  onSelect: (id: string) => void;
}

/** Button that opens a menu to pick the model provider used for the next run. */
export function ModelMenu({ providers, selected, disabled, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !root.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  const current = providers.find((p) => p.id === selected);
  return (
    <div className="model-menu" ref={root}>
      <button type="button" className="badge model-trigger" aria-haspopup="listbox" aria-expanded={open}
              disabled={disabled} onClick={() => setOpen(!open)}
              title={disabled ? "Finish the current run to switch model" : "Choose the model"}>
        model: {providerLabel(selected)} <span aria-hidden="true">▾</span>
      </button>
      {open && (
        <ul className="model-list" role="listbox" aria-label="Model">
          {providers.map((p) => (
            <li key={p.id} role="option" aria-selected={p.id === selected}>
              <button type="button" className={`model-option${p.id === selected ? " active" : ""}`}
                      disabled={!p.configured} onClick={() => { setOpen(false); onSelect(p.id); }}>
                <strong>{providerLabel(p.id)}</strong>
                <span className="muted small">
                  {p.configured ? p.models.strong : "API key not set on the server"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {current && !current.configured && <span className="sr-only">No API key for {current.id}</span>}
    </div>
  );
}
