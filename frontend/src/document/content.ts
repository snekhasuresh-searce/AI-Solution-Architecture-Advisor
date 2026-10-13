// Editor content: the AI report as editor HTML, the editor's extensions, and checks before saving.
//
// Heading levels: the report's "# title" becomes the document title (edited above the toolbar), and the
// other headings move up one level, so "## 1. Executive summary" is Heading 1. Exports map them back
// (backend doc_export.py), so an unedited and an edited export look the same.

import { Extension, type Extensions } from "@tiptap/core";
import Highlight from "@tiptap/extension-highlight";
import Image from "@tiptap/extension-image";
import { TableKit } from "@tiptap/extension-table";
import TextAlign from "@tiptap/extension-text-align";
import { Color, FontFamily, FontSize, TextStyle } from "@tiptap/extension-text-style";
import { CharacterCount, Placeholder } from "@tiptap/extensions";
import StarterKit from "@tiptap/starter-kit";
import { marked } from "marked";
import { apiUrl, type DocJSON } from "../api";

export const FALLBACK_TITLE = "Solution recommendation";

/** The AI-generated Markdown report as editor HTML, with its title taken out. */
export function reportToDocument(markdown: string): { title: string; html: string } {
  const html = marked.parse(markdown, { gfm: true, async: false });
  const dom = new DOMParser().parseFromString(html, "text/html");
  const h1 = dom.body.querySelector("h1");
  const title = h1?.textContent?.trim() || FALLBACK_TITLE;
  h1?.remove();
  for (const h of [...dom.body.querySelectorAll("h2, h3, h4, h5, h6")]) {
    const next = dom.createElement(`h${Math.min(Number(h.tagName[1]) - 1, 3)}`);
    next.innerHTML = h.innerHTML;
    h.replaceWith(next);
  }
  return { title, html: dom.body.innerHTML };
}

// Must match backend documents.py, which rejects anything else.
const SAFE_LINK = /^(https?:|mailto:|#|\/(?!\/))/i;
const SAFE_IMAGE = /^(https?:\/\/|data:image\/(png|jpe?g|gif|webp);base64,|\/api\/runs\/[0-9a-f]{8}\/diagram\.(svg|png)$)/i;

declare module "@tiptap/core" {
  interface Commands<ReturnType> {
    blockLineHeight: {
      setBlockLineHeight: (value: string) => ReturnType;
      unsetBlockLineHeight: () => ReturnType;
    };
  }
}

/** Line spacing for whole paragraphs and headings (TipTap's own LineHeight styles text runs). */
const BlockLineHeight = Extension.create({
  name: "blockLineHeight",
  addGlobalAttributes() {
    return [{
      types: ["paragraph", "heading"],
      attributes: {
        lineHeight: {
          default: null,
          parseHTML: (el) => el.style.lineHeight || null,
          renderHTML: (attrs) => (attrs.lineHeight ? { style: `line-height: ${attrs.lineHeight}` } : {}),
        },
      },
    }];
  },
  addCommands() {
    return {
      setBlockLineHeight: (value) => ({ commands }) =>
        [commands.updateAttributes("paragraph", { lineHeight: value }),
         commands.updateAttributes("heading", { lineHeight: value })].some(Boolean),
      unsetBlockLineHeight: () => ({ commands }) =>
        [commands.resetAttributes("paragraph", "lineHeight"), commands.resetAttributes("heading", "lineHeight")].some(Boolean),
    };
  },
});

/** Images keep API paths (the run's diagram) relative in the document, and load them from the API host. */
const ApiImage = Image.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      src: {
        default: null,
        parseHTML: (el) => el.getAttribute("src")?.replace(apiUrl("/api/"), "/api/") ?? null,
        renderHTML: (attrs) => ({ src: attrs.src ? apiUrl(String(attrs.src)) : null }),
      },
    };
  },
});

export function editorExtensions(placeholder: string): Extensions {
  return [
    StarterKit.configure({
      heading: { levels: [1, 2, 3] },
      link: {
        openOnClick: false,
        autolink: true,
        defaultProtocol: "https",
        isAllowedUri: (url, ctx) => ctx.defaultValidate(url) && SAFE_LINK.test(url),
      },
    }),
    TextStyle,
    Color,
    FontFamily,
    FontSize,
    Highlight.configure({ multicolor: true }),
    TextAlign.configure({ types: ["heading", "paragraph"] }),
    BlockLineHeight,
    TableKit.configure({ table: { resizable: false } }),
    ApiImage.configure({ allowBase64: true }),
    Placeholder.configure({ placeholder }),
    CharacterCount,
  ];
}

type Node = { type: string; attrs?: Record<string, unknown>; marks?: { type: string; attrs?: Record<string, unknown> }[];
  content?: Node[]; text?: string };

/** Drop what the server would reject (images from blob:/file: URLs, javascript: links), e.g. after a paste. */
export function sanitize(doc: DocJSON): DocJSON {
  const clean = (node: Node): Node => {
    if (node.type === "image" && !SAFE_IMAGE.test(String(node.attrs?.src ?? ""))) return { type: "paragraph" };
    const out: Node = { ...node };
    if (node.marks) {
      out.marks = node.marks.filter((m) => m.type !== "link" || SAFE_LINK.test(String(m.attrs?.href ?? "")));
    }
    if (node.content) out.content = node.content.map(clean);
    return out;
  };
  return clean(doc as Node) as DocJSON;
}

/** A picked or pasted image as a data: URL, scaled down so documents stay small (max 1600 px, PNG or JPEG). */
export async function imageToDataUrl(file: File, maxSide = 1600): Promise<string> {
  if (!/^image\/(png|jpeg|gif|webp)$/.test(file.type)) throw new Error("Use a PNG, JPEG, GIF or WebP image.");
  if (file.size > 15 * 1024 * 1024) throw new Error("The image is larger than 15 MB.");
  const url = URL.createObjectURL(file);
  try {
    const img = new window.Image();
    img.src = url;
    await img.decode();
    const scale = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight));
    const keepAsIs = scale === 1 && file.size <= 1024 * 1024 && file.type !== "image/webp";
    if (keepAsIs) {
      return await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(reader.error);
        reader.readAsDataURL(file);
      });
    }
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(img.naturalWidth * scale);
    canvas.height = Math.round(img.naturalHeight * scale);
    canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
    return file.type === "image/jpeg" ? canvas.toDataURL("image/jpeg", 0.85) : canvas.toDataURL("image/png");
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** "My Report: v2" -> "my-report-v2", for download names. */
export const slug = (title: string) =>
  title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60) || "recommendation";

/** The standard requirement sections, offered when adding a section. */
export const STANDARD_SECTIONS = [
  "Project Overview",
  "Business Objectives",
  "User Requirements",
  "Functional Requirements",
  "Non-Functional Requirements",
  "User Roles and Permissions",
  "User Workflows",
  "Technical Requirements",
  "Assumptions and Constraints",
  "Acceptance Criteria",
];
