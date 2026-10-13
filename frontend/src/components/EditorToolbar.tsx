import type { Editor } from "@tiptap/core";
import { useEditorState } from "@tiptap/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useToast } from "../toast";
import { Icon, type IconName } from "./Icon";

const FONTS = [
  { label: "Default font", value: "" },
  { label: "Arial", value: "Arial" },
  { label: "Calibri", value: "Calibri" },
  { label: "Georgia", value: "Georgia" },
  { label: "Times New Roman", value: "Times New Roman" },
  { label: "Verdana", value: "Verdana" },
  { label: "Courier New", value: "Courier New" },
];
const SIZES = ["8", "9", "10", "11", "12", "14", "16", "18", "20", "24", "28", "32", "36"];
const SPACING = [
  { label: "Single", value: "1" },
  { label: "1.15", value: "1.15" },
  { label: "1.5", value: "1.5" },
  { label: "Double", value: "2" },
];
// Google Docs-like swatches: dark to light per hue.
const COLORS = ["#000000", "#434343", "#666666", "#999999", "#b7b7b7", "#ffffff",
  "#c21f45", "#e67e22", "#d4a017", "#137a4a", "#1f5fbf", "#3b2bf0",
  "#f4cccc", "#fce5cd", "#fff2cc", "#d9ead3", "#cfe2f3", "#d9d2e9"];
const HIGHLIGHTS = ["#fff59d", "#ffe0b2", "#c8e6c9", "#b3e5fc", "#e1bee7", "#ffcdd2"];

function Btn({ icon, label, active, disabled, onClick, children }: {
  icon?: IconName; label: string; active?: boolean; disabled?: boolean; onClick: () => void; children?: ReactNode;
}) {
  return (
    <button type="button" className={`tb-btn ${active ? "active" : ""}`} title={label} aria-label={label}
            aria-pressed={active ?? undefined} disabled={disabled}
            onMouseDown={(e) => e.preventDefault() /* keep the editor's selection */} onClick={onClick}>
      {icon ? <Icon name={icon} size={17} /> : children}
    </button>
  );
}

const Sep = () => <span className="tb-sep" aria-hidden="true" />;

/** A toolbar button that opens a small panel of colour swatches. */
function ColorMenu({ icon, label, current, swatches, onPick, onClear }: {
  icon: IconName; label: string; current: string | null; swatches: string[];
  onPick: (color: string) => void; onClear: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);
  return (
    <div className="tb-popover-wrap" ref={ref}>
      <button type="button" className={`tb-btn color ${open ? "active" : ""}`} title={label} aria-label={label}
              aria-expanded={open} onMouseDown={(e) => e.preventDefault()} onClick={() => setOpen(!open)}>
        <Icon name={icon} size={16} />
        <span className="tb-swatch-bar" style={{ background: current ?? "transparent" }} />
      </button>
      {open && (
        <div className="tb-popover" role="dialog" aria-label={label}>
          <div className="swatches">
            {swatches.map((c) => (
              <button key={c} type="button" className="swatch" style={{ background: c }} title={c} aria-label={c}
                      onMouseDown={(e) => e.preventDefault()} onClick={() => { onPick(c); setOpen(false); }} />
            ))}
          </div>
          <div className="tb-popover-row">
            <label className="custom-color">
              Custom <input type="color" value={current?.startsWith("#") ? current.slice(0, 7) : "#000000"}
                            onChange={(e) => onPick(e.target.value)} />
            </label>
            <button type="button" className="btn ghost small-btn" onMouseDown={(e) => e.preventDefault()}
                    onClick={() => { onClear(); setOpen(false); }}>None</button>
          </div>
        </div>
      )}
    </div>
  );
}

export function EditorToolbar({ editor, onLink, onImage }: {
  editor: Editor; onLink: () => void; onImage: () => void;
}) {
  const toast = useToast();
  const s = useEditorState({
    editor,
    selector: ({ editor: e }) => ({
      canUndo: e.can().undo(),
      canRedo: e.can().redo(),
      bold: e.isActive("bold"),
      italic: e.isActive("italic"),
      underline: e.isActive("underline"),
      strike: e.isActive("strike"),
      block: e.isActive("heading", { level: 1 }) ? "1" : e.isActive("heading", { level: 2 }) ? "2"
        : e.isActive("heading", { level: 3 }) ? "3" : "0",
      font: String(e.getAttributes("textStyle").fontFamily ?? ""),
      size: String(e.getAttributes("textStyle").fontSize ?? "").replace(/pt$/, ""),
      color: (e.getAttributes("textStyle").color as string | undefined) ?? null,
      highlight: (e.getAttributes("highlight").color as string | undefined) ?? null,
      align: ["center", "right", "justify"].find((a) => e.isActive({ textAlign: a })) ?? "left",
      spacing: String(e.getAttributes("paragraph").lineHeight ?? e.getAttributes("heading").lineHeight ?? ""),
      bullet: e.isActive("bulletList"),
      ordered: e.isActive("orderedList"),
      link: e.isActive("link"),
      table: e.isActive("table"),
      canIndent: e.can().sinkListItem("listItem"),
      canOutdent: e.can().liftListItem("listItem"),
      canMerge: e.can().mergeCells(),
      canSplit: e.can().splitCell(),
    }),
  })!;
  const chain = () => editor.chain().focus();

  const clipboard = async (action: "cut" | "copy" | "paste") => {
    editor.commands.focus();
    if (action !== "paste") {
      if (!document.execCommand(action)) toast.info(`Use ${action === "cut" ? "Ctrl+X" : "Ctrl+C"} to ${action}`);
      return;
    }
    try {
      const items = navigator.clipboard.read ? await navigator.clipboard.read() : [];
      const html = items.find((i) => i.types.includes("text/html"));
      if (html) {
        editor.chain().focus().insertContent(await (await html.getType("text/html")).text()).run();
        return;
      }
      const text = await navigator.clipboard.readText();
      if (text) editor.chain().focus().insertContent(text.replace(/[&<>]/g, (c) => `&#${c.charCodeAt(0)};`)
        .replace(/\n/g, "<br>")).run();
    } catch {
      toast.info("Use Ctrl+V to paste", { message: "The browser did not allow reading the clipboard." });
    }
  };

  return (
    <div className="doc-toolbar no-print" role="toolbar" aria-label="Formatting">
      <div className="tb-row">
        <Btn icon="undo" label="Undo (Ctrl+Z)" disabled={!s.canUndo} onClick={() => chain().undo().run()} />
        <Btn icon="redoEdit" label="Redo (Ctrl+Y)" disabled={!s.canRedo} onClick={() => chain().redo().run()} />
        <Sep />
        <Btn icon="cut" label="Cut" onClick={() => clipboard("cut")} />
        <Btn icon="copy" label="Copy" onClick={() => clipboard("copy")} />
        <Btn icon="paste" label="Paste" onClick={() => clipboard("paste")} />
        <Btn icon="selectAll" label="Select all (Ctrl+A)" onClick={() => chain().selectAll().run()} />
        <Sep />
        <select className="tb-select style" aria-label="Paragraph style" value={s.block}
                onChange={(e) => {
                  const level = Number(e.target.value) as 0 | 1 | 2 | 3;
                  if (level === 0) chain().setParagraph().run();
                  else chain().setHeading({ level }).run();
                }}>
          <option value="0">Normal text</option>
          <option value="1">Heading 1</option>
          <option value="2">Heading 2</option>
          <option value="3">Heading 3</option>
        </select>
        <select className="tb-select font" aria-label="Font" value={FONTS.some((f) => f.value === s.font) ? s.font : ""}
                onChange={(e) => (e.target.value ? chain().setFontFamily(e.target.value).run() : chain().unsetFontFamily().run())}>
          {FONTS.map((f) => <option key={f.label} value={f.value} style={{ fontFamily: f.value || undefined }}>{f.label}</option>)}
        </select>
        <select className="tb-select size" aria-label="Font size (pt)" value={SIZES.includes(s.size) ? s.size : ""}
                onChange={(e) => (e.target.value ? chain().setFontSize(`${e.target.value}pt`).run() : chain().unsetFontSize().run())}>
          <option value="">Size</option>
          {SIZES.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
        <Sep />
        <Btn label="Bold (Ctrl+B)" active={s.bold} onClick={() => chain().toggleBold().run()}><b>B</b></Btn>
        <Btn label="Italic (Ctrl+I)" active={s.italic} onClick={() => chain().toggleItalic().run()}><i>I</i></Btn>
        <Btn label="Underline (Ctrl+U)" active={s.underline} onClick={() => chain().toggleUnderline().run()}><u>U</u></Btn>
        <Btn label="Strikethrough" active={s.strike} onClick={() => chain().toggleStrike().run()}><s>S</s></Btn>
        <ColorMenu icon="textColor" label="Text colour" current={s.color} swatches={COLORS}
                   onPick={(c) => chain().setColor(c).run()} onClear={() => chain().unsetColor().run()} />
        <ColorMenu icon="highlight" label="Highlight colour" current={s.highlight} swatches={HIGHLIGHTS}
                   onPick={(c) => chain().setHighlight({ color: c }).run()} onClear={() => chain().unsetHighlight().run()} />
        <Btn icon="clearFormat" label="Clear formatting" onClick={() => chain().unsetAllMarks().unsetBlockLineHeight().run()} />
        <Sep />
        <Btn icon="alignLeft" label="Align left" active={s.align === "left"} onClick={() => chain().setTextAlign("left").run()} />
        <Btn icon="alignCenter" label="Align centre" active={s.align === "center"} onClick={() => chain().setTextAlign("center").run()} />
        <Btn icon="alignRight" label="Align right" active={s.align === "right"} onClick={() => chain().setTextAlign("right").run()} />
        <Btn icon="alignJustify" label="Justify" active={s.align === "justify"} onClick={() => chain().setTextAlign("justify").run()} />
        <select className="tb-select spacing" aria-label="Line spacing" value={SPACING.some((o) => o.value === s.spacing) ? s.spacing : ""}
                onChange={(e) => (e.target.value ? chain().setBlockLineHeight(e.target.value).run() : chain().unsetBlockLineHeight().run())}>
          <option value="">Spacing</option>
          {SPACING.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <Sep />
        <Btn icon="listBullet" label="Bulleted list" active={s.bullet} onClick={() => chain().toggleBulletList().run()} />
        <Btn icon="listOrdered" label="Numbered list" active={s.ordered} onClick={() => chain().toggleOrderedList().run()} />
        <Btn icon="outdent" label="Decrease indent" disabled={!s.canOutdent} onClick={() => chain().liftListItem("listItem").run()} />
        <Btn icon="indent" label="Increase indent" disabled={!s.canIndent} onClick={() => chain().sinkListItem("listItem").run()} />
        <Sep />
        <Btn icon={s.link ? "unlink" : "link"} label={s.link ? "Remove link" : "Insert link (Ctrl+K)"} active={s.link}
             onClick={() => (s.link ? chain().extendMarkRange("link").unsetLink().run() : onLink())} />
        <Btn icon="image" label="Insert image" onClick={onImage} />
        <Btn icon="table" label="Insert table" active={s.table}
             onClick={() => chain().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()} />
        <Btn icon="rule" label="Horizontal divider" onClick={() => chain().setHorizontalRule().run()} />
      </div>
      {s.table && (
        <div className="tb-row table-tools" aria-label="Table">
          <span className="tb-label">Table</span>
          <button type="button" className="tb-text" onClick={() => chain().addRowBefore().run()}>Row above</button>
          <button type="button" className="tb-text" onClick={() => chain().addRowAfter().run()}>Row below</button>
          <button type="button" className="tb-text" onClick={() => chain().addColumnBefore().run()}>Column left</button>
          <button type="button" className="tb-text" onClick={() => chain().addColumnAfter().run()}>Column right</button>
          <Sep />
          <button type="button" className="tb-text" onClick={() => chain().deleteRow().run()}>Delete row</button>
          <button type="button" className="tb-text" onClick={() => chain().deleteColumn().run()}>Delete column</button>
          <Sep />
          <button type="button" className="tb-text" disabled={!s.canMerge} onClick={() => chain().mergeCells().run()}>Merge cells</button>
          <button type="button" className="tb-text" disabled={!s.canSplit} onClick={() => chain().splitCell().run()}>Split cell</button>
          <button type="button" className="tb-text" onClick={() => chain().toggleHeaderRow().run()}>Header row</button>
          <Sep />
          <button type="button" className="tb-text danger" onClick={() => chain().deleteTable().run()}>Delete table</button>
        </div>
      )}
    </div>
  );
}
