import { useEffect, useRef, type FormEvent, type ReactNode } from "react";
import { Icon } from "./Icon";

/** A modal form on the native <dialog> element (focus trap, Esc to close and backdrop come with it). */
export function Dialog({ title, open, onClose, onSubmit, submitLabel, submitDisabled, children }: {
  title: string; open: boolean; onClose: () => void; onSubmit: () => void;
  submitLabel: string; submitDisabled?: boolean; children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!submitDisabled) onSubmit();
  };

  return (
    <dialog ref={ref} className="dialog" onClose={onClose} onCancel={onClose} aria-label={title}>
      {open && (
        <form onSubmit={submit}>
          <header className="dialog-head">
            <h2>{title}</h2>
            <button type="button" className="toast-close" onClick={onClose} aria-label="Close"><Icon name="close" /></button>
          </header>
          <div className="dialog-body">{children}</div>
          <footer className="dialog-actions">
            <button type="button" className="btn" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn primary" disabled={submitDisabled}>{submitLabel}</button>
          </footer>
        </form>
      )}
    </dialog>
  );
}
