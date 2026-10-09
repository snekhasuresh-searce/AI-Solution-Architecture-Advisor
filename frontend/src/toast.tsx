// Toast notifications: short-lived feedback on actions (exported, saved, failed...).
// Persistent page state (e.g. "API unreachable") stays inline instead.

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Icon } from "./components/Icon";

export type ToastKind = "success" | "error" | "info";

export interface ToastOptions {
  message?: string;
  action?: { label: string; onClick: () => void };
  /** ms before it hides; errors stay longer. 0 = until closed. */
  duration?: number;
}

interface Toast extends ToastOptions {
  id: number;
  kind: ToastKind;
  title: string;
}

interface ToastApi {
  success: (title: string, options?: ToastOptions) => number;
  error: (title: string, options?: ToastOptions) => number;
  info: (title: string, options?: ToastOptions) => number;
  dismiss: (id: number) => void;
}

const DEFAULT_MS: Record<ToastKind, number> = { success: 4000, info: 5000, error: 8000 };
const MAX_VISIBLE = 4;

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error("useToast must be used inside <ToastProvider>");
  return api;
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: (id: number) => void }) {
  const onClose = useCallback(() => onDismiss(toast.id), [onDismiss, toast.id]);
  const [paused, setPaused] = useState(false);
  const remaining = useRef(toast.duration ?? DEFAULT_MS[toast.kind]);
  const startedAt = useRef(Date.now());

  // Pause the countdown while hovered or focused, so it can be read and its action clicked.
  useEffect(() => {
    if (paused || remaining.current <= 0) return;
    startedAt.current = Date.now();
    const timer = setTimeout(onClose, remaining.current);
    return () => {
      clearTimeout(timer);
      remaining.current -= Date.now() - startedAt.current;
    };
  }, [paused, onClose]);

  const icon = toast.kind === "success" ? "check" : toast.kind === "error" ? "alert" : "info";
  return (
    <li
      className={`toast ${toast.kind}`}
      role={toast.kind === "error" ? "alert" : "status"}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <span className="toast-icon" aria-hidden="true"><Icon name={icon} size={15} /></span>
      <div className="toast-text">
        <p className="toast-title">{toast.title}</p>
        {toast.message && <p className="toast-message">{toast.message}</p>}
      </div>
      {toast.action && (
        <button type="button" className="toast-action" onClick={() => { toast.action!.onClick(); onClose(); }}>
          {toast.action.label}
        </button>
      )}
      <button type="button" className="toast-close" onClick={onClose} aria-label="Dismiss notification">
        <Icon name="close" size={14} />
      </button>
    </li>
  );
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setToasts((list) => list.filter((t) => t.id !== id)), []);

  const api = useMemo<ToastApi>(() => {
    const show = (kind: ToastKind) => (title: string, options: ToastOptions = {}) => {
      const id = nextId.current++;
      // Newest last; drop the oldest beyond the limit. Identical repeats replace each other.
      setToasts((list) => [...list.filter((t) => !(t.title === title && t.kind === kind)), { id, kind, title, ...options }]
        .slice(-MAX_VISIBLE));
      return id;
    };
    return { success: show("success"), error: show("error"), info: show("info"), dismiss };
  }, [dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <section className="toasts" aria-label="Notifications">
        <ol>
          {toasts.map((t) => <ToastItem key={t.id} toast={t} onDismiss={dismiss} />)}
        </ol>
      </section>
    </ToastContext.Provider>
  );
}
