import type { Editor } from "@tiptap/core";
import type { Node as PMNode } from "@tiptap/pm/model";
import { useEditorState } from "@tiptap/react";
import { useEffect, useRef, useState } from "react";
import { STANDARD_SECTIONS } from "../document/content";
import { Icon } from "./Icon";

/** A Heading 1 or 2 at the top level, and the document range up to the next heading of the same or a higher level. */
interface Section {
  pos: number;
  end: number;
  level: number;
  text: string;
}

function sectionsOf(doc: PMNode): Section[] {
  const heads: Omit<Section, "end">[] = [];
  doc.forEach((node, offset) => {
    if (node.type.name === "heading" && node.attrs.level <= 2) {
      heads.push({ pos: offset, level: node.attrs.level, text: node.textContent.trim() });
    }
  });
  return heads.map((h, i) => ({
    ...h,
    end: heads.slice(i + 1).find((n) => n.level <= h.level)?.pos ?? doc.content.size,
  }));
}

const bare = (s: string) => s.toLowerCase().replace(/^[\d.\s]+/, "").replace(/[^a-z]+/g, " ").trim();

export function DocOutline({ editor, editable, onClose }: { editor: Editor; editable: boolean; onClose: () => void }) {
  const { sections, cursor } = useEditorState({
    editor,
    selector: ({ editor: e }) => ({ sections: sectionsOf(e.state.doc), cursor: e.state.selection.from }),
  })!;
  const [adding, setAdding] = useState(false);
  const [renaming, setRenaming] = useState<number | null>(null);
  const addRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!adding) return;
    const close = (e: MouseEvent) => { if (!addRef.current?.contains(e.target as Node)) setAdding(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [adding]);

  const active = [...sections].reverse().find((s) => cursor >= s.pos && cursor <= s.end);

  const jump = (s: Section) => {
    editor.chain().focus().setTextSelection(s.pos + 1).run();
    editor.view.focus();
    (editor.view.nodeDOM(s.pos) as HTMLElement | null)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  /** Swap a section with its neighbour at the same level (headings, content and subsections move together). */
  const move = (s: Section, dir: -1 | 1) => {
    const list = sectionsOf(editor.state.doc);
    const i = list.findIndex((x) => x.pos === s.pos);
    const [a, b] = dir === -1
      ? [list.slice(0, i).reverse().find((x) => x.level === s.level && x.end === s.pos), list[i]]
      : [list[i], list.slice(i + 1).find((x) => x.level === s.level && x.pos === s.end)];
    if (!a || !b) return;
    const content = editor.state.doc.slice(b.pos, b.end).content;
    const tr = editor.state.tr.delete(b.pos, b.end).insert(a.pos, content);
    editor.view.dispatch(tr);
    const moved = dir === -1 ? a.pos : a.pos + (b.end - b.pos);
    requestAnimationFrame(() => (editor.view.nodeDOM(moved) as HTMLElement | null)?.scrollIntoView({ block: "nearest" }));
  };

  const remove = (s: Section) => {
    if (!window.confirm(`Delete the section "${s.text || "Untitled"}" and everything in it? You can undo with Ctrl+Z.`)) return;
    editor.view.dispatch(editor.state.tr.delete(s.pos, s.end));
    editor.commands.focus();
  };

  const rename = (s: Section, text: string) => {
    setRenaming(null);
    const name = text.trim();
    const node = editor.state.doc.nodeAt(s.pos);
    if (!name || !node || name === s.text) return;
    editor.view.dispatch(editor.state.tr.insertText(name, s.pos + 1, s.pos + 1 + node.content.size));
  };

  /** Insert a Heading 1 after the section holding the cursor (or at the end), with an empty paragraph to type in. */
  const add = (name: string | null) => {
    setAdding(false);
    const text = name ?? "New section";
    const top = sectionsOf(editor.state.doc).filter((x) => x.level === 1);
    const at = top.find((x) => cursor >= x.pos && cursor <= x.end)?.end ?? editor.state.doc.content.size;
    editor.chain()
      .insertContentAt(at, [{ type: "heading", attrs: { level: 1 }, content: [{ type: "text", text }] }, { type: "paragraph" }])
      .run();
    // Custom: select the placeholder name to type over it; standard: start writing in the section.
    const sel = name ? { from: at + text.length + 3, to: at + text.length + 3 } : { from: at + 1, to: at + 1 + text.length };
    editor.chain().focus().setTextSelection(sel).run();
    editor.view.focus();  // now, not on the next frame: the user types straight away
    requestAnimationFrame(() => (editor.view.nodeDOM(at) as HTMLElement | null)?.scrollIntoView({ behavior: "smooth", block: "center" }));
  };

  const present = new Set(sections.map((s) => bare(s.text)));
  const missing = STANDARD_SECTIONS.filter((n) => !present.has(bare(n)));

  return (
    <nav className="doc-outline no-print" aria-label="Document sections">
      <div className="outline-head">
        <h2>Sections</h2>
        <button type="button" className="toast-close outline-close" onClick={onClose} aria-label="Hide sections">
          <Icon name="close" size={14} />
        </button>
      </div>
      {editable && (
        <div className="outline-add" ref={addRef}>
          <button type="button" className="btn small-btn block-btn" aria-expanded={adding} onClick={() => setAdding(!adding)}>
            <Icon name="plus" size={14} /> Add section
          </button>
          {adding && (
            <ul className="outline-menu" role="menu">
              <li><button type="button" role="menuitem" onClick={() => add(null)}><b>Custom section…</b></button></li>
              {missing.map((n) => (
                <li key={n}><button type="button" role="menuitem" onClick={() => add(n)}>{n}</button></li>
              ))}
            </ul>
          )}
        </div>
      )}
      {sections.length === 0 ? (
        <p className="muted small outline-empty">Headings you add (Heading 1 and 2) appear here.</p>
      ) : (
        <ol className="outline-list">
          {sections.map((s, i) => (
            <li key={`${s.pos}-${i}`} className={`outline-item level-${s.level} ${active?.pos === s.pos ? "active" : ""}`}>
              {renaming === s.pos ? (
                <input className="outline-rename" defaultValue={s.text} autoFocus aria-label="Section name"
                       onBlur={(e) => rename(s, e.target.value)}
                       onKeyDown={(e) => {
                         if (e.key === "Enter") rename(s, e.currentTarget.value);
                         if (e.key === "Escape") setRenaming(null);
                       }} />
              ) : (
                <button type="button" className="outline-link" onClick={() => jump(s)}
                        onDoubleClick={() => editable && setRenaming(s.pos)} title={s.text}>
                  {s.text || <span className="muted">Untitled</span>}
                </button>
              )}
              {editable && renaming !== s.pos && (
                <span className="outline-actions">
                  <button type="button" title="Move up" aria-label={`Move ${s.text} up`} onClick={() => move(s, -1)}>
                    <Icon name="arrowUp" size={13} />
                  </button>
                  <button type="button" title="Move down" aria-label={`Move ${s.text} down`} onClick={() => move(s, 1)}>
                    <Icon name="arrowDown" size={13} />
                  </button>
                  <button type="button" title="Rename" aria-label={`Rename ${s.text}`} onClick={() => setRenaming(s.pos)}>
                    <Icon name="edit" size={13} />
                  </button>
                  <button type="button" title="Delete section" aria-label={`Delete ${s.text}`} className="danger"
                          onClick={() => remove(s)}>
                    <Icon name="trash" size={13} />
                  </button>
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
    </nav>
  );
}
