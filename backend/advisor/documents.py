"""Edited recommendations: the rich-text document a user edits in the web app, one per run.

The AI-generated Markdown (report.py) is never changed; it stays the original. The first save of an
edit creates a `documents` row holding the editor's content as JSON (TipTap / ProseMirror: headings,
paragraphs, lists, tables, links, images and text formatting). Each save bumps `version`, and the client
sends the version it started from, so a stale tab cannot overwrite newer edits (Conflict -> HTTP 409).

`document_versions` keeps a history: a snapshot on every manual save, and for autosaves at most one
every SNAPSHOT_EVERY. Resetting to the AI original also snapshots the edit first, so it can be restored.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (Column, DateTime, Integer, MetaData, String, Table, Text, delete, func, insert, select,
                        update)

from . import db

metadata = MetaData()

documents = Table(
    "documents", metadata,
    Column("run_id", String(16), primary_key=True),
    Column("title", String(200), nullable=False),
    Column("content", Text, nullable=False),               # editor JSON
    Column("version", Integer, nullable=False),            # 1 on first save, +1 on each save
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("updated_by", String(36)),                       # users.id
)

document_versions = Table(
    "document_versions", metadata,
    Column("id", String(32), primary_key=True),
    Column("run_id", String(16), nullable=False, index=True),
    Column("version", Integer, nullable=False),            # the document version this snapshot holds
    Column("title", String(200), nullable=False),
    Column("content", Text, nullable=False),
    Column("reason", String(10), nullable=False),          # manual | auto | reset
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("created_by", String(36)),
)

MAX_CONTENT_BYTES = 8 * 1024 * 1024  # pasted images are stored inline as data: URIs
MAX_DEPTH = 40
MAX_VERSIONS = 50                     # per run; the oldest are pruned
SNAPSHOT_EVERY = timedelta(minutes=10)

NODE_TYPES = {"doc", "paragraph", "heading", "text", "hardBreak", "bulletList", "orderedList", "listItem",
              "blockquote", "codeBlock", "horizontalRule", "image", "table", "tableRow", "tableHeader",
              "tableCell"}
MARK_TYPES = {"bold", "italic", "underline", "strike", "code", "link", "textStyle", "highlight"}
_SAFE_LINK = re.compile(r"^(https?:|mailto:|#|/(?!/))", re.I)
_SAFE_IMAGE = re.compile(r"^(https?://|data:image/(png|jpe?g|gif|webp);base64,|/api/runs/[0-9a-f]{8}/diagram\.(svg|png)$)",
                         re.I)

_tables_ready = False
_tables_lock = threading.Lock()


class DocumentError(ValueError):
    """The content is not a document this app can store and export."""


class Conflict(Exception):
    """The document changed since the client loaded it."""

    def __init__(self, current_version: int | None):
        super().__init__(current_version)
        self.current_version = current_version


def ensure_tables() -> None:
    """Create the tables on first use. Locked, so two first requests do not both try to create them."""
    global _tables_ready
    if _tables_ready:
        return
    with _tables_lock:
        if not _tables_ready:
            metadata.create_all(db.engine())
            _tables_ready = True


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()  # SQLite returns naive UTC


# --------------------------------------------------------------- validation
def validate(content: dict) -> str:
    """Check the editor JSON (known node and mark types, safe links and images, size) and return it
    serialised for storage."""
    if not isinstance(content, dict) or content.get("type") != "doc" or not isinstance(content.get("content"), list):
        raise DocumentError("Content must be an editor document: {\"type\": \"doc\", \"content\": [...]}.")
    body = json.dumps(content, separators=(",", ":"), ensure_ascii=False)
    if len(body.encode()) > MAX_CONTENT_BYTES:
        raise DocumentError(f"The document is larger than {MAX_CONTENT_BYTES // (1024 * 1024)} MB. "
                            "Remove or shrink some images.")
    stack = [(content, 0)]
    while stack:
        node, depth = stack.pop()
        if not isinstance(node, dict) or node.get("type") not in NODE_TYPES:
            raise DocumentError(f"Unsupported content: {node.get('type') if isinstance(node, dict) else node!r}")
        if depth > MAX_DEPTH:
            raise DocumentError("The document is nested too deeply.")
        attrs = node.get("attrs") or {}
        if node["type"] == "text" and not isinstance(node.get("text"), str):
            raise DocumentError("Text nodes need a text string.")
        if node["type"] == "image" and not _SAFE_IMAGE.match(str(attrs.get("src") or "")):
            raise DocumentError("Images must be uploaded files or http(s) links.")
        for mark in node.get("marks") or []:
            if not isinstance(mark, dict) or mark.get("type") not in MARK_TYPES:
                raise DocumentError(f"Unsupported formatting: {mark!r}")
            href = str((mark.get("attrs") or {}).get("href") or "")
            if mark["type"] == "link" and not _SAFE_LINK.match(href):
                raise DocumentError(f"Links must be http(s), mailto or in-document links, not {href[:40]!r}.")
        children = node.get("content") or []
        if not isinstance(children, list):
            raise DocumentError("Node content must be a list.")
        stack.extend((child, depth + 1) for child in children)
    return body


def clean_title(title: str) -> str:
    title = " ".join(title.split())
    if not title:
        raise DocumentError("The document needs a title.")
    return title[:200]


# -------------------------------------------------------------------- reads
def _public(row) -> dict:
    return {"run_id": row.run_id, "title": row.title, "content": json.loads(row.content), "version": row.version,
            "created_at": _iso(row.created_at), "updated_at": _iso(row.updated_at), "updated_by": row.updated_by}


def get(run_id: str) -> dict | None:
    ensure_tables()
    with db.engine().connect() as conn:
        row = conn.execute(select(documents).where(documents.c.run_id == run_id)).first()
    return _public(row) if row else None


def titles(run_ids: list[str]) -> dict[str, str]:
    """run_id -> edited title, for the runs that have an edited document."""
    if not run_ids:
        return {}
    ensure_tables()
    with db.engine().connect() as conn:
        return dict(conn.execute(select(documents.c.run_id, documents.c.title)
                                 .where(documents.c.run_id.in_(run_ids))).all())


def history(run_id: str) -> list[dict]:
    """Snapshots, newest first, without their content."""
    ensure_tables()
    cols = [document_versions.c[k] for k in ("id", "version", "title", "reason", "created_at", "created_by")]
    with db.engine().connect() as conn:
        rows = conn.execute(select(*cols).where(document_versions.c.run_id == run_id)
                            .order_by(document_versions.c.created_at.desc())).all()
    return [{"id": r.id, "version": r.version, "title": r.title, "reason": r.reason,
             "created_at": _iso(r.created_at), "created_by": r.created_by} for r in rows]


def snapshot(run_id: str, version_id: str) -> dict | None:
    ensure_tables()
    with db.engine().connect() as conn:
        row = conn.execute(select(document_versions).where(document_versions.c.run_id == run_id,
                                                           document_versions.c.id == version_id)).first()
    if row is None:
        return None
    return {"id": row.id, "version": row.version, "title": row.title, "reason": row.reason,
            "content": json.loads(row.content), "created_at": _iso(row.created_at), "created_by": row.created_by}


# ------------------------------------------------------------------- writes
def _add_snapshot(conn, run_id: str, version: int, title: str, body: str, reason: str, user_id: str | None) -> None:
    conn.execute(insert(document_versions).values(id=uuid.uuid4().hex, run_id=run_id, version=version, title=title,
                                                  content=body, reason=reason, created_at=_now(), created_by=user_id))
    stale = conn.execute(select(document_versions.c.id).where(document_versions.c.run_id == run_id)
                         .order_by(document_versions.c.created_at.desc()).offset(MAX_VERSIONS)).scalars().all()
    if stale:
        conn.execute(delete(document_versions).where(document_versions.c.id.in_(stale)))


def save(run_id: str, *, title: str, content: dict, base_version: int | None, user_id: str,
         manual: bool = False) -> dict:
    """Create (base_version None) or update the document. Raises Conflict when base_version is not the
    stored version, and DocumentError for invalid content."""
    title = clean_title(title)
    body = validate(content)
    ensure_tables()
    now = _now()
    with db.engine().begin() as conn:
        current = conn.execute(select(documents.c.version).where(documents.c.run_id == run_id)).scalar()
        if current != base_version:
            raise Conflict(current)
        if current is None:  # numbering carries on after a reset, so history versions stay unique
            version = (conn.execute(select(func.max(document_versions.c.version))
                                    .where(document_versions.c.run_id == run_id)).scalar() or 0) + 1
            conn.execute(insert(documents).values(run_id=run_id, title=title, content=body, version=version,
                                                  created_at=now, updated_at=now, updated_by=user_id))
        else:
            version = current + 1
            done = conn.execute(update(documents)
                                .where(documents.c.run_id == run_id, documents.c.version == current)
                                .values(title=title, content=body, version=version, updated_at=now,
                                        updated_by=user_id))
            if done.rowcount != 1:  # another save won the race
                raise Conflict(None)
        last = conn.execute(select(document_versions.c.created_at).where(document_versions.c.run_id == run_id)
                            .order_by(document_versions.c.created_at.desc()).limit(1)).scalar()
        if manual or last is None or now - (last if last.tzinfo else last.replace(tzinfo=timezone.utc)) >= SNAPSHOT_EVERY:
            _add_snapshot(conn, run_id, version, title, body, "manual" if manual else "auto", user_id)
        row = conn.execute(select(documents).where(documents.c.run_id == run_id)).first()
    return _public(row)


def reset(run_id: str, user_id: str) -> bool:
    """Drop the edits so the run shows its AI-generated report again. The edit is kept in the history."""
    ensure_tables()
    with db.engine().begin() as conn:
        row = conn.execute(select(documents).where(documents.c.run_id == run_id)).first()
        if row is None:
            return False
        _add_snapshot(conn, run_id, row.version, row.title, row.content, "reset", user_id)
        conn.execute(delete(documents).where(documents.c.run_id == run_id))
    return True
