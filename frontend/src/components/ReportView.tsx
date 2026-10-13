import type { Editor } from "@tiptap/core";
import { EditorContent, useEditor, useEditorState } from "@tiptap/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, apiUrl, type DocJSON, type DocumentState, type ExportFormat } from "../api";
import { editorExtensions, FALLBACK_TITLE, imageToDataUrl, reportToDocument, sanitize, slug } from "../document/content";
import type { Report } from "../state";
import { useToast } from "../toast";
import { Dialog } from "./Dialog";
import { DocOutline } from "./DocOutline";
import { EditorToolbar } from "./EditorToolbar";
import { Icon, Spinner, type IconName } from "./Icon";
import { TracePanel } from "./TracePanel";
import { VersionHistory } from "./VersionHistory";

const AUTOSAVE_MS = 1500;     // after typing pauses
const MAX_WAIT_MS = 10_000;   // ... but at least this often while typing continuously
const DRAFT_MS = 600;         // local backup, so a crash or closed tab loses nothing
const message = (err: unknown) => (err instanceof Error ? err.message : String(err));
const FORMAT_LABEL: Record<ExportFormat, string> = { docx: "Word", pdf: "PDF", md: "Markdown" };

type Status = "original" | "saved" | "dirty" | "saving" | "error" | "conflict";

interface Draft {
  title: string;
  content: DocJSON;
  /** the server version the draft was edited from */
  baseVersion: number | null;
  at: number;
}

const draftKey = (runId: string) => `advisor.draft.${runId}`;
function readDraft(runId: string): Draft | null {
  try {
    const raw = localStorage.getItem(draftKey(runId));
    return raw ? (JSON.parse(raw) as Draft) : null;
  } catch {
    return null;
  }
}
function writeDraft(runId: string, draft: Draft): void {
  try {
    localStorage.setItem(draftKey(runId), JSON.stringify(draft));
  } catch {
    // storage full (large images) or blocked: the server autosave still runs
  }
}
function clearDraft(runId: string): void {
  try {
    localStorage.removeItem(draftKey(runId));
  } catch {
    // ignore
  }
}

async function download(runId: string, format: ExportFormat, filename: string): Promise<void> {
  const res = await fetch(api.exportUrl(runId, format), { credentials: "include" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Export failed (${res.status})`);
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function ago(iso: string | null): string {
  if (!iso) return "";
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

interface ReportViewProps {
  report: Report;
  /** hide the run history column to give the document more room */
  expanded: boolean;
  onToggleExpand: () => void;
  /** a save changed what the run history shows (title, edited mark) */
  onSaved: () => void;
  onSignedOut: () => void;
}

/** The recommendation as an editable document: loads the saved edit, or the AI-generated report. */
export function ReportView(props: ReportViewProps) {
  const { report, onSignedOut } = props;
  const [state, setState] = useState<DocumentState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setState(null);
    setLoadError(null);
    api.document(report.runId)
      .then((s) => { if (!cancelled) setState(s); })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) return onSignedOut();
        // Still show the report (read-only), so a broken document API never hides the result.
        setLoadError(message(err));
        setState({ run_id: report.runId, editable: false, document: null });
      });
    return () => { cancelled = true; };
  }, [report.runId, onSignedOut]);

  if (!state) {
    return (
      <section className="card report doc" aria-label="Recommendation" aria-busy="true">
        <p className="doc-loading muted"><Spinner /> Opening the document…</p>
      </section>
    );
  }
  return <Workspace key={report.runId} {...props} initial={state} loadError={loadError} />;
}

function Workspace({ report, expanded, onToggleExpand, onSaved, onSignedOut, initial, loadError }: ReportViewProps & {
  initial: DocumentState; loadError: string | null;
}) {
  const toast = useToast();
  const runId = report.runId;
  const editable = initial.editable;
  const [original] = useState(() => reportToDocument(report.markdown));
  const [title, setTitle] = useState(initial.document?.title ?? original.title);
  const [status, setStatusState] = useState<Status>(initial.document ? "saved" : "original");
  const [saved, setSaved] = useState({ at: initial.document?.updated_at ?? null, by: initial.document?.updated_by ?? null });
  const [lastError, setLastError] = useState<string | null>(null);
  const [edited, setEdited] = useState(Boolean(initial.document));
  const [panel, setPanel] = useState<"outline" | "history" | null>(() =>
    window.matchMedia("(min-width: 1200px)").matches ? "outline" : null);
  const [dialog, setDialog] = useState<"link" | "image" | null>(null);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [exportOpen, setExportOpen] = useState(false);

  // Mutable save state, read by timers and event handlers.
  const version = useRef<number | null>(initial.document?.version ?? null);
  const statusRef = useRef<Status>(status);
  const dirty = useRef(false);
  const seq = useRef(0);                       // +1 per change, to tell whether a save captured the latest
  const inflight = useRef<Promise<boolean> | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const draftTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const firstChange = useRef<number | null>(null);
  const retries = useRef(0);
  const titleRef = useRef(title);
  const savedTitle = useRef(initial.document?.title ?? original.title);
  const editorRef = useRef<Editor | null>(null);
  const changed = useRef<() => void>(() => {});

  const setStatus = (s: Status) => { statusRef.current = s; setStatusState(s); };

  const insertImages = async (files: File[], pos?: number) => {
    const editor = editorRef.current;
    if (!editor) return;
    for (const file of files) {
      try {
        const src = await imageToDataUrl(file);
        const chain = editor.chain().focus();
        (pos == null ? chain : chain.setTextSelection(pos)).setImage({ src, alt: file.name.replace(/\.[^.]+$/, "") }).run();
      } catch (err) {
        toast.error("Could not add the image", { message: message(err) });
      }
    }
  };

  const imageFiles = (data: DataTransfer | null) => {
    // Office apps put a picture of copied text on the clipboard too; then the text is what was meant.
    if (!data || data.types.includes("text/html") || data.types.includes("text/plain")) return [];
    return [...data.files].filter((f) => f.type.startsWith("image/"));
  };

  const editor = useEditor({
    extensions: editorExtensions(editable ? "Start writing your requirements…" : ""),
    content: initial.document?.content ?? original.html,
    editable,
    onUpdate: () => changed.current(),
    editorProps: {
      attributes: { class: "doc-content", spellcheck: "true", "aria-label": "Document body" },
      handlePaste: (_view, event) => {
        const files = imageFiles(event.clipboardData);
        if (!files.length) return false;
        void insertImages(files);
        return true;
      },
      handleDrop: (view, event) => {
        const files = imageFiles(event.dataTransfer);
        if (!files.length) return false;
        event.preventDefault();
        void insertImages(files, view.posAtCoords({ left: event.clientX, top: event.clientY })?.pos);
        return true;
      },
    },
  });
  editorRef.current = editor;

  const words = useEditorState({ editor, selector: ({ editor: e }) => e?.storage.characterCount.words() ?? 0 }) ?? 0;

  // ------------------------------------------------------------- saving
  const body = (manual: boolean) => ({
    title: titleRef.current.trim() || FALLBACK_TITLE,
    content: sanitize(editor!.getJSON() as DocJSON),
    base_version: version.current,
    manual,
  });

  const save = useCallback(async (manual: boolean): Promise<boolean> => {
    clearTimeout(timer.current);
    firstChange.current = null;
    if (!editable || !editor) return false;
    if (inflight.current) await inflight.current;
    if (statusRef.current === "conflict") return false;
    if (!dirty.current && !manual) return true;

    const run = (async () => {
      const mySeq = seq.current;
      const payload = body(manual);
      dirty.current = false;
      setStatus("saving");
      try {
        const doc = await api.saveDocument(runId, payload);
        version.current = doc.version;
        retries.current = 0;
        setSaved({ at: doc.updated_at, by: doc.updated_by });
        setLastError(null);
        setEdited(true);
        if (seq.current === mySeq) {
          clearDraft(runId);
          setStatus("saved");
        } else {
          dirty.current = true;  // edited while the save was in flight
          setStatus("dirty");
          schedule();
        }
        if (doc.title !== savedTitle.current || doc.version === 1) onSaved();
        savedTitle.current = doc.title;
        if (manual) toast.success("Document saved", { message: `Version ${doc.version}` });
        return true;
      } catch (err) {
        dirty.current = true;
        if (err instanceof ApiError && err.status === 401) {
          onSignedOut();
          return false;
        }
        if (err instanceof ApiError && err.status === 409) {
          setStatus("conflict");
          toast.error("Edited somewhere else", { message: "Choose whether to load the latest version or keep yours." });
          return false;
        }
        setStatus("error");
        setLastError(message(err));
        // Problems with the content or permissions do not go away by retrying.
        const permanent = err instanceof ApiError && [403, 413, 422].includes(err.status);
        if (!permanent) {
          retries.current += 1;
          timer.current = setTimeout(() => void save(false), Math.min(30_000, 2000 * 2 ** retries.current));
        }
        if (manual || retries.current <= 1 || permanent) {
          toast.error("Could not save the document", {
            message: permanent ? message(err) : `${message(err)} Your changes are kept on this device; retrying.`,
          });
        }
        return false;
      }
    })();
    inflight.current = run;
    try {
      return await run;
    } finally {
      if (inflight.current === run) inflight.current = null;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, editable, runId]);

  const schedule = () => {
    if (!editable || statusRef.current === "conflict") return;
    clearTimeout(timer.current);
    const now = Date.now();
    firstChange.current ??= now;
    const wait = Math.max(0, Math.min(AUTOSAVE_MS, firstChange.current + MAX_WAIT_MS - now));
    timer.current = setTimeout(() => void save(false), wait);
  };

  const backup = () => {
    if (!editor || !dirty.current) return;
    writeDraft(runId, { title: titleRef.current, content: editor.getJSON() as DocJSON,
                        baseVersion: version.current, at: Date.now() });
  };

  changed.current = () => {
    if (!editable) return;
    seq.current += 1;
    dirty.current = true;
    if (statusRef.current !== "conflict") setStatus(statusRef.current === "saving" ? "saving" : "dirty");
    clearTimeout(draftTimer.current);
    draftTimer.current = setTimeout(backup, DRAFT_MS);
    schedule();
  };

  const onTitle = (value: string) => {
    setTitle(value);
    titleRef.current = value;
    changed.current();
  };

  // Unsaved changes found on this device (a closed tab, a crash, or a failed save): bring them back.
  useEffect(() => {
    if (!editor || !editable) return;
    const draft = readDraft(runId);
    if (!draft) return;
    const same = JSON.stringify(draft.content) === JSON.stringify(editor.getJSON()) && draft.title === titleRef.current;
    if (same) return clearDraft(runId);
    const restore = () => {
      editor.commands.setContent(draft.content, { emitUpdate: false });
      setTitle(draft.title);
      titleRef.current = draft.title;
      changed.current();
    };
    const when = new Date(draft.at).toLocaleString();
    if (draft.baseVersion === version.current) {
      restore();
      toast.info("Recovered unsaved changes", {
        message: `From ${when}. They are being saved now.`, duration: 10_000,
        action: { label: "Discard", onClick: () => { discardTo(initial.document?.content ?? original.html, savedTitle.current); } },
      });
    } else {
      toast.info("You have older unsaved changes", {
        message: `From ${when}, made before the latest saved version.`, duration: 0,
        action: { label: "Restore them", onClick: restore },
      });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor]);

  /** Replace the editor content without saving (undo still brings the previous text back). */
  const discardTo = (content: DocJSON | string, newTitle: string) => {
    clearTimeout(timer.current);
    clearTimeout(draftTimer.current);
    editor?.commands.setContent(content, { emitUpdate: false });
    setTitle(newTitle);
    titleRef.current = newTitle;
    dirty.current = false;
    seq.current += 1;
    clearDraft(runId);
    setStatus(version.current == null ? "original" : "saved");
  };

  // Never lose work: warn before leaving with unsaved changes, back up and save when the tab is hidden,
  // and save on the way out when another run is opened.
  useEffect(() => {
    const beforeUnload = (e: BeforeUnloadEvent) => {
      if (dirty.current || inflight.current) {
        backup();
        e.preventDefault();
        e.returnValue = "";
      }
    };
    const hidden = () => {
      if (document.visibilityState === "hidden" && dirty.current) {
        backup();
        void save(false);
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("visibilitychange", hidden);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("visibilitychange", hidden);
      clearTimeout(timer.current);
      clearTimeout(draftTimer.current);
      if (dirty.current && editor && statusRef.current !== "conflict") {
        backup();
        const payload = body(false);  // read now: the editor is destroyed after this
        api.saveDocument(runId, payload).then(() => { clearDraft(runId); onSaved(); }).catch(() => {
          toast.error("Your last edits were not saved", { message: "They are kept on this device; open the run again to recover them." });
        });
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor, save]);

  // Ctrl/Cmd+S saves (and keeps a version), Ctrl/Cmd+K inserts a link.
  useEffect(() => {
    const keys = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
      const key = e.key.toLowerCase();
      if (key === "s") {
        e.preventDefault();
        void save(true);
      } else if (key === "k" && editable && editor?.isFocused) {
        e.preventDefault();
        setDialog("link");
      }
    };
    window.addEventListener("keydown", keys);
    return () => window.removeEventListener("keydown", keys);
  }, [save, editable, editor]);

  // The toolbar wraps to more rows on narrow screens: the scrolling workspace fills the space below it.
  const sectionRef = useRef<HTMLElement>(null);
  useEffect(() => {
    const section = sectionRef.current;
    const toolbar = section?.querySelector<HTMLElement>(".doc-toolbar");
    if (!section) return;
    if (!toolbar) {
      section.style.setProperty("--toolbar-h", "0px");  // view only: no toolbar
      return;
    }
    const observer = new ResizeObserver(() => section.style.setProperty("--toolbar-h", `${toolbar.offsetHeight}px`));
    observer.observe(toolbar);
    return () => observer.disconnect();
  }, [editor, editable]);

  // Refresh "Saved · 2 min ago".
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), 30_000);
    return () => clearInterval(id);
  }, []);

  // ------------------------------------------------------------- actions
  const exportAs = async (format: ExportFormat) => {
    setExportOpen(false);
    setExporting(format);
    const filename = `${slug(title)}.${format}`;
    try {
      if (dirty.current || inflight.current) {
        if (!(await save(false))) {
          throw new Error("Your latest changes could not be saved, so the export would be out of date. Save first, then export.");
        }
      }
      await download(runId, format, filename);
      toast.success(`Exported to ${FORMAT_LABEL[format]}`, { message: filename });
    } catch (err) {
      toast.error(`${FORMAT_LABEL[format]} export failed`, { message: message(err) });
    } finally {
      setExporting(null);
    }
  };

  const loadLatest = async () => {
    try {
      const latest = await api.document(runId);
      version.current = latest.document?.version ?? null;
      setEdited(Boolean(latest.document));
      if (latest.document) setSaved({ at: latest.document.updated_at, by: latest.document.updated_by });
      statusRef.current = "saved";
      discardTo(latest.document?.content ?? original.html, latest.document?.title ?? original.title);
      savedTitle.current = titleRef.current;
      toast.info("Loaded the latest version");
    } catch (err) {
      toast.error("Could not load the latest version", { message: message(err) });
    }
  };

  const keepMine = async () => {
    try {
      const latest = await api.document(runId);
      version.current = latest.document?.version ?? null;
      setStatus("dirty");
      await save(true);
    } catch (err) {
      toast.error("Could not save your version", { message: message(err) });
    }
  };

  const restoreVersion = (snapTitle: string, content: DocJSON, from: number) => {
    editor?.commands.setContent(content);  // undoable; triggers a change and so a save
    setTitle(snapTitle);
    titleRef.current = snapTitle;
    changed.current();
    void save(true).then((ok) => ok && toast.success(`Restored version ${from}`));
  };

  const resetToOriginal = async () => {
    if (!window.confirm("Go back to the AI-generated report? Your edits are kept in the version history.")) return;
    clearTimeout(timer.current);
    try {
      if (inflight.current) await inflight.current;
      await api.resetDocument(runId);
      version.current = null;
      setEdited(false);
      setSaved({ at: null, by: null });
      discardTo(original.html, original.title);
      savedTitle.current = original.title;
      onSaved();
      toast.success("Back to the AI-generated report");
    } catch (err) {
      toast.error("Could not reset the document", { message: message(err) });
    }
  };

  const approved = report.status === "APPROVED";
  const hasDiagram = report.markdown.includes(api.diagramPath(runId, "svg"));
  const statusView: Record<Status, { icon?: IconName; text: string; cls: string }> = {
    original: { text: editable ? "AI-generated · not edited" : "AI-generated", cls: "" },
    saved: { icon: "check", text: `Saved${saved.at ? ` · ${ago(saved.at)}` : ""}`, cls: "ok" },
    dirty: { text: "Unsaved changes", cls: "warn" },
    saving: { text: "Saving…", cls: "" },
    error: { icon: "alert", text: "Not saved · retrying", cls: "bad" },
    conflict: { icon: "alert", text: "Edited elsewhere", cls: "bad" },
  };
  const sv = statusView[status];

  return (
    <section ref={sectionRef} className="card report doc" aria-label="Recommendation">
      <header className="report-bar no-print">
        <div className="report-meta">
          <span className={`pill ${approved ? "ok" : "warn"}`}>{approved ? "Approved" : "Escalated"}</span>
          <span className="muted mono">run {runId}</span>
          {!report.live && <span className="muted">· from history</span>}
          {edited && <span className="pill edited">Edited</span>}
          {!editable && <span className="pill">View only</span>}
        </div>
        <button type="button" className="btn ghost small-btn expand-btn" onClick={onToggleExpand}
                title={expanded ? "Show run history" : "Hide run history to widen the document"}>
          <Icon name={expanded ? "collapse" : "expand"} size={14} /> {expanded ? "Exit full width" : "Full width"}
        </button>
      </header>
      <div className="no-print"><TracePanel runId={runId} /></div>
      {loadError && (
        <p className="inline-error doc-load-error no-print"><Icon name="alert" /> Editing is unavailable: {loadError}</p>
      )}

      <div className="doc-titlebar no-print">
        <input className="doc-title" value={title} onChange={(e) => onTitle(e.target.value)} readOnly={!editable}
               aria-label="Document title" maxLength={200} placeholder={FALLBACK_TITLE} />
        <div className="doc-titlebar-right">
          <span className={`doc-status ${sv.cls}`} role="status" aria-live="polite"
                title={saved.at ? `Last saved ${new Date(saved.at).toLocaleString()}${saved.by ? ` by ${saved.by}` : ""}` : undefined}>
            {status === "saving" ? <Spinner size={12} /> : sv.icon && <Icon name={sv.icon} size={13} />}
            {sv.text}
            {status === "error" && (
              <button type="button" className="link-btn" onClick={() => void save(true)} title={lastError ?? undefined}>Retry now</button>
            )}
          </span>
          <span className="doc-words muted">{words.toLocaleString()} words</span>
          <div className="doc-actions">
            <button type="button" className={`btn small-btn ${panel === "outline" ? "on" : ""}`} aria-pressed={panel === "outline"}
                    onClick={() => setPanel(panel === "outline" ? null : "outline")} title="Sections">
              <Icon name="sections" size={15} /><span className="hide-sm">Sections</span>
            </button>
            <button type="button" className={`btn small-btn ${panel === "history" ? "on" : ""}`} aria-pressed={panel === "history"}
                    onClick={() => setPanel(panel === "history" ? null : "history")} title="Version history">
              <Icon name="history" size={15} /><span className="hide-sm">History</span>
            </button>
            <button type="button" className="btn small-btn" onClick={() => window.print()} title="Print">
              <Icon name="print" size={15} /><span className="hide-sm">Print</span>
            </button>
            <div className="export-menu">
              <button type="button" className="btn small-btn" aria-expanded={exportOpen} aria-haspopup="menu"
                      onClick={() => setExportOpen(!exportOpen)} disabled={exporting !== null}>
                {exporting ? <Spinner /> : <Icon name="download" size={15} />} Export
                <Icon name="chevron" size={13} />
              </button>
              {exportOpen && (
                <div className="menu export-list" role="menu" onMouseLeave={() => setExportOpen(false)}>
                  <button type="button" role="menuitem" className="menu-item" onClick={() => exportAs("docx")}>
                    <Icon name="file" /> Word document (.docx)
                  </button>
                  <button type="button" role="menuitem" className="menu-item" onClick={() => exportAs("pdf")}>
                    <Icon name="file" /> PDF document (.pdf)
                  </button>
                  <button type="button" role="menuitem" className="menu-item" onClick={() => exportAs("md")}>
                    <Icon name="file" /> Markdown (.md)
                  </button>
                  {hasDiagram && (
                    <a role="menuitem" className="menu-item" href={apiUrl(api.diagramPath(runId, "png", true))} download
                       onClick={() => setExportOpen(false)}>
                      <Icon name="image" /> Architecture diagram (.png)
                    </a>
                  )}
                </div>
              )}
            </div>
            {editable && (
              <button type="button" className="btn primary small-btn" onClick={() => void save(true)}
                      disabled={status === "saving"} title="Save now and keep a version (Ctrl+S)">
                <Icon name="save" size={15} /> Save
              </button>
            )}
          </div>
        </div>
      </div>

      {status === "conflict" && (
        <div className="doc-alert no-print" role="alert">
          <Icon name="alert" />
          <span>This document was changed in another tab or by someone else. Your changes are not saved yet.</span>
          <button type="button" className="btn small-btn" onClick={loadLatest}>Load latest</button>
          <button type="button" className="btn small-btn primary" onClick={keepMine}>Keep mine</button>
        </div>
      )}

      {editor && editable && (
        <EditorToolbar editor={editor} onLink={() => setDialog("link")} onImage={() => setDialog("image")} />
      )}

      <div className="doc-workspace">
        {editor && panel === "outline" && <DocOutline editor={editor} editable={editable} onClose={() => setPanel(null)} />}
        <div className="doc-canvas" onMouseDown={(e) => {
          // Clicking the grey margin puts the cursor at the end, as in a word processor.
          if (e.target === e.currentTarget && editor) {
            e.preventDefault();
            editor.commands.focus("end");
          }
        }}>
          <article className="doc-paper">
            <h1 className="print-title">{title || FALLBACK_TITLE}</h1>
            <EditorContent editor={editor} />
          </article>
        </div>
        {panel === "history" && (
          <VersionHistory runId={runId} editable={editable} currentVersion={version.current} edited={edited}
                          onRestore={restoreVersion} onResetToOriginal={resetToOriginal} onClose={() => setPanel(null)} />
        )}
      </div>

      {editor && <LinkDialog editor={editor} open={dialog === "link"} onClose={() => setDialog(null)} />}
      {editor && <ImageDialog editor={editor} open={dialog === "image"} onClose={() => setDialog(null)} />}
    </section>
  );
}

// ------------------------------------------------------------------ dialogs
const SAFE_URL = /^(https?:\/\/|mailto:|#|\/(?!\/))/i;
const normalizeUrl = (raw: string) => {
  const url = raw.trim();
  if (!url || /^[a-z][a-z0-9+.-]*:|^#|^\//i.test(url)) return url;
  return url.includes("@") && !url.includes("/") ? `mailto:${url}` : `https://${url}`;
};

function LinkDialog({ editor, open, onClose }: { editor: Editor; open: boolean; onClose: () => void }) {
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const empty = editor.state.selection.empty;
  useEffect(() => {
    if (open) {
      setUrl(String(editor.getAttributes("link").href ?? ""));
      setText("");
    }
  }, [open, editor]);
  const href = normalizeUrl(url);
  const valid = SAFE_URL.test(href);

  const apply = () => {
    if (empty && !editor.isActive("link")) {
      editor.chain().focus().insertContent({ type: "text", text: text.trim() || href, marks: [{ type: "link", attrs: { href } }] }).run();
    } else {
      editor.chain().focus().extendMarkRange("link").setLink({ href }).run();
    }
    onClose();
  };

  return (
    <Dialog title="Insert link" open={open} onClose={onClose} onSubmit={apply} submitLabel="Apply" submitDisabled={!valid}>
      <label className="field">
        Link address
        <input type="text" inputMode="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com"
               autoFocus />
      </label>
      {url && !valid && <p className="inline-error small">Use a web address (https://…) or an email address.</p>}
      {empty && !editor.isActive("link") && (
        <label className="field">
          Text to show
          <input type="text" value={text} onChange={(e) => setText(e.target.value)} placeholder="Defaults to the address" />
        </label>
      )}
    </Dialog>
  );
}

function ImageDialog({ editor, open, onClose }: { editor: Editor; open: boolean; onClose: () => void }) {
  const toast = useToast();
  const [src, setSrc] = useState("");
  const [alt, setAlt] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"upload" | "url">("upload");
  useEffect(() => {
    if (open) {
      setSrc("");
      setAlt("");
      setMode("upload");
    }
  }, [open]);

  const pick = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    try {
      setSrc(await imageToDataUrl(file));
      setAlt((a) => a || file.name.replace(/\.[^.]+$/, ""));
    } catch (err) {
      toast.error("Could not use that image", { message: message(err) });
    } finally {
      setBusy(false);
    }
  };

  const url = mode === "url" ? normalizeUrl(src) : src;
  const valid = mode === "url" ? /^https?:\/\//i.test(url) : src.startsWith("data:image/");
  const insert = () => {
    editor.chain().focus().setImage({ src: url, alt: alt.trim() || undefined }).run();
    onClose();
  };

  return (
    <Dialog title="Insert image" open={open} onClose={onClose} onSubmit={insert} submitLabel="Insert" submitDisabled={!valid || busy}>
      <div className="tabs dialog-tabs" role="tablist">
        <button type="button" role="tab" aria-selected={mode === "upload"} className={`tab ${mode === "upload" ? "active" : ""}`}
                onClick={() => { setMode("upload"); setSrc(""); }}>Upload</button>
        <button type="button" role="tab" aria-selected={mode === "url"} className={`tab ${mode === "url" ? "active" : ""}`}
                onClick={() => { setMode("url"); setSrc(""); }}>By URL</button>
      </div>
      {mode === "upload" ? (
        <label className="field">
          Image file (PNG, JPEG, GIF or WebP; large images are scaled down)
          <input type="file" accept="image/png,image/jpeg,image/gif,image/webp" onChange={(e) => pick(e.target.files?.[0])} />
        </label>
      ) : (
        <label className="field">
          Image address
          <input type="text" inputMode="url" value={src} onChange={(e) => setSrc(e.target.value)} placeholder="https://…/picture.png" />
          <span className="muted small">Linked images appear in the editor; exports show them as a link.</span>
        </label>
      )}
      {busy && <p className="muted small"><Spinner /> Preparing the image…</p>}
      {valid && <img className="dialog-preview" src={url} alt="" />}
      <label className="field">
        Description (alt text)
        <input type="text" value={alt} onChange={(e) => setAlt(e.target.value)} placeholder="What the image shows" />
      </label>
    </Dialog>
  );
}
