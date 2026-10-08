import { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, type ExportFormat } from "../api";
import type { Report } from "../state";
import { Icon, Spinner } from "./Icon";

async function download(runId: string, format: ExportFormat): Promise<void> {
  const res = await fetch(api.exportUrl(runId, format));
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Export failed (${res.status})`);
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `recommendation_${runId}.${format}`;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function ReportView({ report }: { report: Report }) {
  const [exporting, setExporting] = useState<ExportFormat | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const exportAs = async (format: ExportFormat) => {
    setExporting(format);
    setError(null);
    try {
      await download(report.runId, format);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setExporting(null);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(report.markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setError("Copy failed: the browser blocked clipboard access.");
    }
  };

  const approved = report.status === "APPROVED";
  const hasDiagram = report.markdown.includes(api.diagramUrl(report.runId, "svg"));
  return (
    <section className="card report" aria-label="Recommendation">
      <header className="report-bar">
        <div className="report-meta">
          <span className={`pill ${approved ? "ok" : "warn"}`}>{approved ? "Approved" : "Escalated"}</span>
          <span className="muted mono">run {report.runId}</span>
          {!report.live && <span className="muted">· from history</span>}
        </div>
        <div className="report-actions">
          <button type="button" className="btn" onClick={() => exportAs("docx")} disabled={exporting !== null}>
            {exporting === "docx" ? <Spinner /> : <Icon name="download" />} Export to DOCX
          </button>
          <button type="button" className="btn" onClick={() => exportAs("pdf")} disabled={exporting !== null}>
            {exporting === "pdf" ? <Spinner /> : <Icon name="download" />} Export to PDF
          </button>
          {hasDiagram && (
            <a className="btn" href={api.diagramUrl(report.runId, "png", true)} download>
              <Icon name="download" /> Diagram PNG
            </a>
          )}
          <button type="button" className="btn ghost" onClick={copy} title="Copy the report as Markdown">
            <Icon name={copied ? "check" : "copy"} /> {copied ? "Copied" : "Markdown"}
          </button>
        </div>
      </header>
      {error && <p className="inline-error"><Icon name="alert" size={14} /> {error}</p>}
      <article className="markdown">
        <Markdown
          remarkPlugins={[remarkGfm]}
          components={{
            table: (props) => <div className="table-wrap"><table {...props} /></div>,
            // The architecture diagram: full width, click to open at full size.
            img: ({ src, alt }) => (
              <a className="diagram" href={String(src)} target="_blank" rel="noreferrer" title="Open full size">
                <img src={String(src)} alt={alt ?? ""} loading="lazy" />
              </a>
            ),
          }}
        >
          {report.markdown}
        </Markdown>
      </article>
    </section>
  );
}
