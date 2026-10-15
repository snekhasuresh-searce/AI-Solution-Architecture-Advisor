import { useEffect, useRef, useState } from "react";
import { Icon, Spinner } from "./Icon";

const MIN_PASSWORD = 10;

interface Props {
  title: string;
  description: string;
  /** Ask for the current password first (changing your own existing password). */
  needsCurrent: boolean;
  submitLabel: string;
  onSubmit: (newPassword: string, currentPassword?: string) => Promise<void>;
  onClose: () => void;
}

/** Modal for setting a password: your own (profile menu) or someone else's (admin). */
export function PasswordDialog({ title, description, needsCurrent, submitLabel, onSubmit, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Focus moves into the dialog and Escape closes it. No close() on cleanup: that fires onClose,
    // which would unmount the dialog during React's development double-mount.
    if (dialog.current && !dialog.current.open) dialog.current.showModal();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password !== confirm) return setError("The passwords do not match.");
    setBusy(true);
    try {
      await onSubmit(password, needsCurrent ? current : undefined);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <dialog ref={dialog} className="pw-dialog" aria-labelledby="password-dialog-title" onClose={onClose}
            onClick={(e) => { if (e.target === dialog.current) onClose(); }}>
      <form className="pw-dialog-body password-login" onSubmit={submit}>
        <header className="pw-dialog-head">
          <h2 id="password-dialog-title">{title}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="close" size={15} /></button>
        </header>
        <p className="muted small">{description}</p>
        {needsCurrent && (
          <label>
            Current password
            <input type="password" required value={current} onChange={(e) => setCurrent(e.target.value)}
                   autoComplete="current-password" />
          </label>
        )}
        <label>
          New password
          <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
                 autoComplete="new-password" minLength={MIN_PASSWORD} />
        </label>
        <label>
          Confirm new password
          <input type="password" required value={confirm} onChange={(e) => setConfirm(e.target.value)}
                 autoComplete="new-password" />
        </label>
        <p className="muted small field-hint">At least {MIN_PASSWORD} characters.</p>
        {error && <p className="inline-error" role="alert"><Icon name="alert" size={14} /> {error}</p>}
        <div className="pw-dialog-actions">
          <button type="button" className="btn ghost" onClick={onClose}>Cancel</button>
          <button type="submit" className="btn primary"
                  disabled={busy || password.length < MIN_PASSWORD || (needsCurrent && !current)}>
            {busy && <Spinner />} {submitLabel}
          </button>
        </div>
      </form>
    </dialog>
  );
}
