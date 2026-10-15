import { useEffect, useRef, useState } from "react";
import { authApi, type User } from "../api";
import { Avatar } from "./Avatar";
import { Icon, Spinner } from "./Icon";

const MAX_BYTES = 5 * 1024 * 1024;
const TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];

interface Props {
  user: User;
  onSaved: (user: User, message: string) => void;
  onClose: () => void;
}

/** Choose, preview and save a profile photo, or go back to the Google photo. */
export function PhotoDialog({ user, onSaved, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState<"save" | "remove" | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // No close() on cleanup: it fires onClose, which would unmount the dialog in React's dev double-mount.
    if (dialog.current && !dialog.current.open) dialog.current.showModal();
  }, []);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const choose = (picked: File | undefined) => {
    setError(null);
    if (!picked) return;
    if (!TYPES.includes(picked.type)) return setError("Use a PNG, JPEG, WebP or GIF image.");
    if (picked.size > MAX_BYTES) return setError("The image is larger than 5 MB.");
    const url = URL.createObjectURL(picked);
    const probe = new Image();  // the type comes from the file name, so check it really is an image
    probe.onload = () => { setFile(picked); setPreview(url); };
    probe.onerror = () => {
      URL.revokeObjectURL(url);
      setError("That file is not an image this app can read.");
      if (input.current) input.current.value = "";
    };
    probe.src = url;
  };

  const run = async (kind: "save" | "remove") => {
    setBusy(kind);
    setError(null);
    try {
      if (kind === "save" && file) onSaved(await authApi.uploadPicture(file), "Profile photo updated");
      else onSaved(await authApi.removePicture(), "Profile photo removed");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
      if (input.current) input.current.value = "";
    }
  };

  return (
    <dialog ref={dialog} className="pw-dialog" aria-labelledby="photo-dialog-title" onClose={onClose}
            onClick={(e) => { if (e.target === dialog.current) onClose(); }}>
      <div className="pw-dialog-body photo-dialog">
        <header className="pw-dialog-head">
          <h2 id="photo-dialog-title">Profile photo</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close"><Icon name="close" size={15} /></button>
        </header>
        <div className="photo-preview">
          {preview
            ? <img className="avatar" src={preview} alt="Preview of the new photo" style={{ width: 120, height: 120 }} />
            : <Avatar user={user} size={120} />}
        </div>
        <p className="muted small photo-hint">
          {preview
            ? "It will be cropped to a square from the centre."
            : user.has_custom_picture
              ? "Your uploaded photo is shown instead of your Google photo."
              : "PNG, JPEG, WebP or GIF, up to 5 MB. It replaces your Google photo in this app only."}
        </p>
        <input ref={input} type="file" accept={TYPES.join(",")} hidden onChange={(e) => choose(e.target.files?.[0])} />
        {error && <p className="inline-error" role="alert"><Icon name="alert" size={14} /> {error}</p>}
        <div className="pw-dialog-actions photo-actions">
          {user.has_custom_picture && !preview && (
            <button type="button" className="btn ghost danger-text" disabled={busy !== null} onClick={() => run("remove")}>
              {busy === "remove" && <Spinner />} Remove photo
            </button>
          )}
          <button type="button" className="btn" disabled={busy !== null} onClick={() => input.current?.click()}>
            <Icon name="upload" /> {preview ? "Choose another" : "Choose image"}
          </button>
          <button type="button" className="btn primary" disabled={!file || busy !== null} onClick={() => run("save")}>
            {busy === "save" && <Spinner />} Save
          </button>
        </div>
      </div>
    </dialog>
  );
}
