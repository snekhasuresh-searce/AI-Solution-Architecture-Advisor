import { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, apiUrl, type ExportFormat } from "../api";
import type { Report } from "../state";
import { useToast } from "../toast";
import { Icon, Spinner } from "./Icon";
import { TracePanel } from "./TracePanel";

async function download(runId: string, format: ExportFormat): Promise<void> {
  const res = await fetch(api.exportUrl(runId, format), { credentials: "include" });
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
  const toast = useToast();

  const exportAs = async (format: ExportFormat) => {
    setExporting(format);
    try {
      await download(report.runId, format);
      toast.success(`Exported to ${format.toUpperCase()}`, { message: `recommendation_${report.runId}.${format}` });
    } catch (err) {
      toast.error(`${format.toUpperCase()} export failed`, { message: err instanceof Error ? err.message : String(err) });
    } finally {
      setExporting(null);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(report.markdown);
      toast.success("Copied as Markdown", { message: "Paste it into any Markdown editor or doc." });
    } catch {
      toast.error("Copy failed", { message: "The browser blocked clipboard access." });
    }
  };

  const approved = report.status === "APPROVED";
  const hasDiagram = report.markdown.includes(api.diagramPath(report.runId, "svg"));
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
            <a className="btn" href={apiUrl(api.diagramPath(report.runId, "png", true))} download>
              <Icon name="download" /> Diagram PNG
            </a>
          )}
          <button type="button" className="btn ghost" onClick={copy} title="Copy the report as Markdown">
            <Icon name="copy" /> Markdown
          </button>
        </div>
      </header>
      <TracePanel runId={report.runId} />
      <article className="markdown">
        <Markdown
          remarkPlugins={[remarkGfm]}
          components={{
            table: (props) => <div className="table-wrap"><table {...props} /></div>,
            // The architecture diagram: full width, click to open at full size.
            img: ({ src, alt }) => (
              <a className="diagram" href={apiUrl(String(src))} target="_blank" rel="noreferrer" title="Open full size">
                <img src={apiUrl(String(src))} alt={alt ?? ""} loading="lazy" />
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
