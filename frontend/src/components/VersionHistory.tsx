import { useEffect, useState } from "react";
import { api, type DocJSON, type DocumentVersion } from "../api";
import { Icon, Spinner } from "./Icon";

const REASON: Record<DocumentVersion["reason"], string> = {
  manual: "Saved",
  auto: "Autosaved",
  reset: "Before reset to AI version",
};

const when = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** Saved snapshots of the document; restoring one loads it into the editor (it is saved like any edit). */
export function VersionHistory({ runId, editable, currentVersion, edited, onRestore, onResetToOriginal, onClose }: {
  runId: string;
  editable: boolean;
  currentVersion: number | null;
  /** false while the run still shows its AI-generated report */
  edited: boolean;
  onRestore: (title: string, content: DocJSON, version: number) => void;
  onResetToOriginal: () => void;
  onClose: () => void;
}) {
  const [versions, setVersions] = useState<DocumentVersion[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingId, setLoadingId] = useState<string | null>(null);

  useEffect(() => {
    api.documentVersions(runId).then(setVersions).catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [runId, currentVersion]);

  const restore = async (v: DocumentVersion) => {
    if (!window.confirm(`Restore version ${v.version} (${when(v.created_at)})? Your current text is kept in the history.`)) return;
    setLoadingId(v.id);
    try {
      const snap = await api.documentVersion(runId, v.id);
      onRestore(snap.title, snap.content, snap.version);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <aside className="doc-history no-print" aria-label="Version history">
      <div className="outline-head">
        <h2>Version history</h2>
        <button type="button" className="toast-close" onClick={onClose} aria-label="Close version history">
          <Icon name="close" size={14} />
        </button>
      </div>
      {error && <p className="inline-error small"><Icon name="alert" /> {error}</p>}
      {!versions && !error && <p className="muted small"><Spinner /> Loading…</p>}
      <ol className="version-list">
        {versions?.map((v) => (
          <li key={v.id} className={`version ${v.version === currentVersion && v.reason !== "reset" ? "current" : ""}`}>
            <div className="version-text">
              <span className="version-title">Version {v.version}{v.version === currentVersion && v.reason !== "reset" ? " · current" : ""}</span>
              <span className="muted small">{REASON[v.reason]} · {when(v.created_at)}</span>
              {v.created_by && <span className="muted small version-by">{v.created_by}</span>}
            </div>
            {editable && !(v.version === currentVersion && v.reason !== "reset") && (
              <button type="button" className="btn small-btn" disabled={loadingId !== null} onClick={() => restore(v)}>
                {loadingId === v.id ? <Spinner /> : null} Restore
              </button>
            )}
          </li>
        ))}
        <li className={`version ${edited ? "" : "current"}`}>
          <div className="version-text">
            <span className="version-title">AI-generated original{edited ? "" : " · current"}</span>
            <span className="muted small">As produced by the advisor</span>
          </div>
          {editable && edited && (
            <button type="button" className="btn small-btn" onClick={onResetToOriginal}>Restore</button>
          )}
        </li>
      </ol>
      {versions?.length === 0 && <p className="muted small">No saved edits yet. Versions are kept on every Save and every 10 minutes while autosaving.</p>}
    </aside>
  );
}
