"""High-level solution architecture diagram, drawn from the architect's JSON.

One deterministic layout produces a list of drawing primitives; three small
back-ends render them as SVG (web app), a reportlab Drawing (vector, PDF export)
and PNG (DOCX export). Layout:

    [ title ]
    [ Users & stakeholders                    ]
    +-- Cloud boundary ------------------------+  +- External -+
    | Security |  infrastructure band          |  | systems    |
    | (cross-  |  application band             |  | and        |
    | cutting) |  API & services band          |  | integra-   |
    |          |  AI band                      |  | tions      |
    |          |  data band                    |  |            |
    | Monitoring & operations band             |  |            |
    +------------------------------------------+  +------------+
    [ legend ]

Arrows are routed orthogonally through the gaps between bands ("gutters") and
dedicated vertical lanes, so they never cross a box. Numbered badges match the
step list in the report's data-flow section (1, 2, ... for the request flow,
A1, A2, ... for the AI flow).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from reportlab.pdfbase.pdfmetrics import stringWidth

from .architecture import KIND_TITLES, LAYER_TITLES

# ------------------------------------------------------------------ palette
KIND_STYLE = {  # fill, stroke
    "actor": ("#f1f5f9", "#475569"),
    "client_system": ("#f3f4f6", "#6b7280"),
    "proposed": ("#e8f0fe", "#1a56db"),
    "third_party": ("#fff4e5", "#c2410c"),
    "cloud_service": ("#e6f6f4", "#0f766e"),
    "ai": ("#f3e8ff", "#7e22ce"),
    "data_store": ("#e9f7ec", "#15803d"),
}
INK, MUTED, BAND_FILL, BAND_LINE, CLOUD_LINE = "#0f172a", "#475569", "#f8fafc", "#cbd5e1", "#2563eb"
FLOW_COLOR = {"request": "#334155", "ai": "#7e22ce"}

# ------------------------------------------------------------------ geometry
W, M = 1480, 24
HEADER = 58
SIDE_W, INT_W = 196, 220
SIDE_GAP = 40          # security column -> center (holds the left routing lane)
INT_GAP = 34           # cloud boundary -> integrations column (right routing lane)
LANE_W = 30            # free strip at the right of the center bands (vertical routing lane)
BAND_HEAD, NODE_H, BAND_PAD = 24, 60, 12
BAND_H = BAND_HEAD + NODE_H + BAND_PAD
GUTTER = 42
NODE_GAP = 14
SIDE_NODE_H = 50
CENTER_LAYERS = ["users", "infrastructure", "application", "api", "ai", "data", "operations"]

FONT, FONT_BOLD = "Helvetica", "Helvetica-Bold"


@dataclass
class Box:
    x: float
    y: float
    w: float
    h: float
    band: int | str  # center band index, or "security" / "integrations"
    order: int = 0

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


def _wrap(text: str, width: float, font: str, size: float, max_lines: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if stringWidth(trial, font, size) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _ellipsis(lines[-1] + "…", width, font, size)
    return [_ellipsis(line, width, font, size) for line in lines]


def _ellipsis(text: str, width: float, font: str, size: float) -> str:
    if stringWidth(text, font, size) <= width:
        return text
    while text and stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text.rstrip() + "…"


# ------------------------------------------------------------------ layout
class Scene:
    """Primitives, in paint order. Coordinates: origin top-left, y down."""

    def __init__(self) -> None:
        self.items: list[tuple] = []
        self.width = W
        self.height = 0.0

    def rect(self, x, y, w, h, fill, stroke, sw=1.0, dash=False, r=6.0):
        self.items.append(("rect", x, y, w, h, fill, stroke, sw, dash, r))

    def cylinder(self, x, y, w, h, fill, stroke, dash=False):
        self.items.append(("cyl", x, y, w, h, fill, stroke, dash))

    def text(self, x, y, s, size=11.0, bold=False, color=INK, anchor="start"):
        self.items.append(("text", x, y, s, size, bold, color, anchor))

    def line(self, points, color, width=1.4, dash=False):
        self.items.append(("line", points, color, width, dash))

    def poly(self, points, fill):
        self.items.append(("poly", points, fill))

    def circle(self, cx, cy, r, fill, stroke):
        self.items.append(("circle", cx, cy, r, fill, stroke))

    def person(self, cx, cy, color):
        self.circle(cx, cy - 7, 5, "#ffffff", color)
        self.items.append(("arc", cx, cy + 9, 9, color))


def _draw_node(scene: Scene, node: dict, b: Box) -> None:
    fill, stroke = KIND_STYLE.get(node["kind"], KIND_STYLE["proposed"])
    dash = node.get("status") == "recommended"
    if node["kind"] == "data_store":
        scene.cylinder(b.x, b.y, b.w, b.h, fill, stroke, dash)
    else:
        scene.rect(b.x, b.y, b.w, b.h, fill, stroke, 1.4, dash, 7)
    left = b.x + 8
    if node["kind"] == "actor":
        scene.person(b.x + 18, b.cy, stroke)
        left = b.x + 34
    inner = b.x + b.w - 8 - left
    cx = left + inner / 2
    label = _wrap(node["label"], inner, FONT_BOLD, 11.5, 2)
    tech = _ellipsis(node["technology"], inner, FONT, 10) if node.get("technology") else ""
    total = 14 * len(label) + (13 if tech else 0)
    top = b.cy - total / 2 + (3 if node["kind"] == "data_store" else 0)
    y = top + 11
    for line in label:
        scene.text(cx, y, line, 11.5, True, INK, "middle")
        y += 14
    if tech:
        scene.text(cx, y, tech, 10, False, MUTED, "middle")


def layout(arch: dict) -> Scene:
    scene = Scene()
    nodes = arch.get("nodes", [])
    by_layer: dict[str, list[dict]] = {}
    for n in nodes:
        by_layer.setdefault(n["layer"], []).append(n)
    security, integrations = by_layer.get("security", []), by_layer.get("integrations", [])

    # Horizontal extents ----------------------------------------------------
    cloud_left = M
    sec_left = cloud_left + 12
    center_left = sec_left + SIDE_W + SIDE_GAP if security else cloud_left + 16
    int_left = W - M - INT_W
    cloud_right = int_left - INT_GAP if integrations else W - M
    center_right = cloud_right - 12
    nodes_right = center_right - LANE_W  # right strip stays free for the vertical lane

    # Header ----------------------------------------------------------------
    scene.text(M, M + 20, arch.get("title") or "Solution architecture", 19, True)
    scene.text(M, M + 40, "High-level solution architecture  ·  cloud: " + arch.get("cloud_provider", "To be confirmed"),
               11.5, False, MUTED)

    # Bands -----------------------------------------------------------------
    bands = [layer for layer in CENTER_LAYERS if by_layer.get(layer)]
    band_box: dict[int, tuple[float, float]] = {}  # index -> (top, bottom)
    boxes: dict[str, Box] = {}
    y = M + HEADER
    cloud_top = cloud_first = None
    for i, layer in enumerate(bands):
        if layer != "users" and cloud_top is None:
            cloud_top = y - (14 if i else 0)
            y = cloud_top + 30
            cloud_first = y
        top = y
        if layer == "operations":
            bx, bw = sec_left, center_right - sec_left
            nl, nr = sec_left + 12, center_right - 12
        else:
            bx, bw = center_left, center_right - center_left
            nl, nr = center_left + 12, nodes_right
        scene.rect(bx, top, bw, BAND_H, BAND_FILL, BAND_LINE, 1, False, 8)
        scene.text(bx + 12, top + 17, LAYER_TITLES[layer].upper(), 9.5, True, MUTED)
        items = by_layer[layer]
        n = len(items)
        nw = min(210, (nr - nl - NODE_GAP * (n - 1)) / n)
        span = n * nw + (n - 1) * NODE_GAP
        x0 = nl + (nr - nl - span) / 2
        for k, node in enumerate(items):
            boxes[node["id"]] = Box(x0 + k * (nw + NODE_GAP), top + BAND_HEAD, nw, NODE_H, i, k)
        band_box[i] = (top, top + BAND_H)
        y = top + BAND_H + GUTTER
    last_band_bottom = y - GUTTER
    if cloud_top is None:  # only users: still draw an (empty) boundary for context
        cloud_top = cloud_first = y
        last_band_bottom = y + 20
    ops_present = "operations" in bands
    side_bottom = band_box[bands.index("operations") - 1][1] if ops_present and len(bands) > 1 else last_band_bottom
    side_bottom = max(side_bottom, cloud_first + 60)

    # Side columns ------------------------------------------------------------
    def column(items, left, width, title, outside):
        top = cloud_first
        needed = 30 + len(items) * (SIDE_NODE_H + 10) + 4
        bottom = max(side_bottom, top + needed)
        fill = "#ffffff" if outside else BAND_FILL
        scene.rect(left, top, width, bottom - top, fill, "#94a3b8" if outside else BAND_LINE, 1, outside, 8)
        scene.text(left + 12, top + 18, title.upper(), 9.5, True, MUTED)
        for k, node in enumerate(items):
            boxes[node["id"]] = Box(left + 10, top + 30 + k * (SIDE_NODE_H + 10), width - 20, SIDE_NODE_H,
                                    node["layer"], k)
        return bottom

    col_bottom = last_band_bottom
    if security:
        col_bottom = max(col_bottom, column(security, sec_left, SIDE_W, "Security (cross-cutting)", False))
    if integrations:
        col_bottom = max(col_bottom, column(integrations, int_left, INT_W, "External integrations", True))

    cloud_bottom = max(last_band_bottom, col_bottom) + 14
    # Cloud boundary, drawn first so everything sits on top of it.
    cloud_label = f"Cloud: {arch.get('cloud_provider', 'To be confirmed')}  (proposed solution boundary)"
    scene.items.insert(0, ("rect", cloud_left, cloud_top, cloud_right - cloud_left, cloud_bottom - cloud_top,
                           "#fbfdff", CLOUD_LINE, 1.4, True, 12))
    scene.items.insert(1, ("text", cloud_left + 12, cloud_top + 19, cloud_label, 11, True, CLOUD_LINE, "start"))

    for node in nodes:
        if node["id"] in boxes:
            _draw_node(scene, node, boxes[node["id"]])

    # Edges -------------------------------------------------------------------
    _draw_edges(scene, arch, boxes, band_box, bands, center_right, sec_left + SIDE_W, int_left, cloud_bottom)

    # Legend ------------------------------------------------------------------
    y = cloud_bottom + 26
    x = M
    used = [k for k in KIND_STYLE if any(n["kind"] == k for n in nodes)]
    for kind in used:
        fill, stroke = KIND_STYLE[kind]
        scene.rect(x, y - 10, 16, 12, fill, stroke, 1.2, False, 3)
        scene.text(x + 22, y, KIND_TITLES[kind], 10.5, False, INK)
        x += 34 + stringWidth(KIND_TITLES[kind], FONT, 10.5)
    y += 22
    x = M
    scene.rect(x, y - 10, 16, 12, "#ffffff", MUTED, 1.2, True, 3)
    scene.text(x + 22, y, "Dashed = recommended / proposed (not stated in requirements)", 10.5, False, INK)
    x += 40 + stringWidth("Dashed = recommended / proposed (not stated in requirements)", FONT, 10.5)
    for kind, title in (("request", "Request / response flow (1, 2, …)"), ("ai", "AI flow (A1, A2, …)")):
        if any(f["kind"] == kind for f in arch.get("flows", [])):
            scene.line([(x, y - 4), (x + 26, y - 4)], FLOW_COLOR[kind], 2)
            scene.text(x + 32, y, title, 10.5, False, INK)
            x += 50 + stringWidth(title, FONT, 10.5)
    scene.height = y + M
    return scene


def _draw_edges(scene, arch, boxes, band_box, bands, center_right, sec_right, int_left, cloud_bottom) -> None:
    # Merge steps into one edge per node pair; a reply on the same pair becomes a two-headed arrow.
    edges: dict[frozenset, dict] = {}
    for flow in arch.get("flows", []):
        prefix = "A" if flow["kind"] == "ai" else ""
        for k, s in enumerate(flow["steps"], 1):
            a, b = s["source"], s["target"]
            if a not in boxes or b not in boxes:
                continue
            key = frozenset((a, b))
            e = edges.setdefault(key, {"a": a, "b": b, "head_a": False, "head_b": False, "kind": flow["kind"],
                                       "tags": []})
            if a == e["a"]:
                e["head_b"] = True
            else:
                e["head_a"] = True
            if flow["kind"] == "request":
                e["kind"] = "request"
            e["tags"].append(f"{prefix}{k}")

    tracks: dict[str, int] = {}

    def track(name: str, step: float, limit: int) -> float:
        n = tracks.get(name, 0)
        tracks[name] = n + 1
        return (n % limit) * step

    def gutter_below(i: int) -> float:
        bottom = band_box[i][1]
        nxt = band_box.get(i + 1)
        height = (nxt[0] - bottom) if nxt else 20
        return bottom + 7 + track(f"g{i}", 6, max(1, int((height - 12) // 6)))

    ports: dict[tuple[int, str], int] = {}

    def px(box: Box, side: str) -> float:
        """x of the next free attachment point on a box's top/bottom: centre, then alternating sides."""
        n = ports.get((id(box), side), 0)
        ports[(id(box), side)] = n + 1
        step = min(26.0, box.w / 6)
        off = ((n + 1) // 2) * step * (1 if n % 2 else -1)
        return box.cx + max(-box.w / 2 + 10, min(box.w / 2 - 10, off))

    def is_center(box: Box) -> bool:
        return isinstance(box.band, int)

    def route(a: str, b: str) -> list[tuple[float, float]]:
        A, B = boxes[a], boxes[b]
        if is_center(A) and is_center(B):
            if A.band == B.band:
                if abs(A.order - B.order) == 1:
                    left, right = (A, B) if A.x < B.x else (B, A)
                    pts = [(left.x + left.w, left.cy), (right.x, right.cy)]
                    return pts if left is A else pts[::-1]
                gy = gutter_below(A.band)
                ax, bx = px(A, "bottom"), px(B, "bottom")
                return [(ax, A.y + A.h), (ax, gy), (bx, gy), (bx, B.y + B.h)]
            up, low = (A, B) if A.band < B.band else (B, A)
            ux, lx_ = px(up, "bottom"), px(low, "top")
            if low.band - up.band == 1:
                gy = gutter_below(up.band)
                pts = [(ux, up.y + up.h), (ux, gy), (lx_, gy), (lx_, low.y)]
                if abs(ux - lx_) < 2:
                    pts = [pts[0], pts[-1]]
            else:
                g1 = gutter_below(up.band)
                g2 = gutter_below(low.band - 1)
                lx = center_right - LANE_W + 6 + track("lane", 5, 4)
                pts = [(ux, up.y + up.h), (ux, g1), (lx, g1), (lx, g2), (lx_, g2), (lx_, low.y)]
            return pts if up is A else pts[::-1]
        if is_center(A) or is_center(B):
            c, s = (A, B) if is_center(A) else (B, A)
            is_ops = bands[c.band] == "operations"
            gy = c.y - 8 if is_ops else gutter_below(c.band)
            exit_y = c.y if is_ops else c.y + c.h
            cx = px(c, "top" if is_ops else "bottom")
            if s.band == "integrations":
                lx = int_left - 10 - track("int_lane", 5, 4)
                end = (s.x, s.cy)
            else:
                lx = sec_right + 10 + track("sec_lane", 5, 5)
                end = (s.x + s.w, s.cy)
            pts = [(cx, exit_y), (cx, gy), (lx, gy), (lx, s.cy), end]
            return pts if c is A else pts[::-1]
        return [(A.cx, A.cy), (B.cx, B.cy)]  # side column to side column: rare, keep it simple

    badges = []
    for e in edges.values():
        pts = _dedupe(route(e["a"], e["b"]))
        color = FLOW_COLOR[e["kind"]]
        scene.line(pts, color, 1.6, e["kind"] == "ai")
        if e["head_b"]:
            scene.poly(_arrow(pts[-2], pts[-1]), color)
        if e["head_a"]:
            scene.poly(_arrow(pts[1], pts[0]), color)
        badges.append((pts, ", ".join(dict.fromkeys(e["tags"])), color))
    for pts, tag, color in badges:  # on top of every line
        (x1, y1), (x2, y2) = max(zip(pts, pts[1:]), key=lambda s: abs(s[0][0] - s[1][0]) + abs(s[0][1] - s[1][1]))
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        tw = stringWidth(tag, FONT_BOLD, 9) + 10
        scene.rect(mx - tw / 2, my - 8, max(tw, 16), 16, color, "#ffffff", 1, False, 8)
        scene.text(mx, my + 3.2, tag, 9, True, "#ffffff", "middle")


def _dedupe(pts):
    out = []
    for p in pts:
        if not out or abs(out[-1][0] - p[0]) > 0.1 or abs(out[-1][1] - p[1]) > 0.1:
            out.append(p)
    return out if len(out) > 1 else pts[:2]


def _arrow(p1, p2, size=8.0):
    import math

    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    left = (p2[0] - size * math.cos(ang - 0.42), p2[1] - size * math.sin(ang - 0.42))
    right = (p2[0] - size * math.cos(ang + 0.42), p2[1] - size * math.sin(ang + 0.42))
    return [p2, left, right]


# ------------------------------------------------------------------ SVG
def to_svg(arch: dict) -> str:
    from xml.sax.saxutils import escape

    scene = layout(arch)
    w, h = scene.width, scene.height
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" '
           f'height="{h:.0f}" font-family="Helvetica, Arial, sans-serif" role="img" '
           f'aria-label="{escape(arch.get("title", "Solution architecture"))}">',
           f'<rect width="{w:.0f}" height="{h:.0f}" fill="#ffffff"/>']
    for item in scene.items:
        kind = item[0]
        if kind == "rect":
            _, x, y, rw, rh, fill, stroke, sw, dash, r = item
            d = ' stroke-dasharray="6 4"' if dash else ""
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{rw:.1f}" height="{rh:.1f}" rx="{r}" fill="{fill}" '
                       f'stroke="{stroke}" stroke-width="{sw}"{d}/>')
        elif kind == "cyl":
            _, x, y, cw, ch, fill, stroke, dash = item
            ry = 7
            d = ' stroke-dasharray="6 4"' if dash else ""
            out.append(f'<path d="M{x:.1f},{y + ry:.1f} L{x:.1f},{y + ch - ry:.1f} A{cw / 2:.1f},{ry} 0 0 0 '
                       f'{x + cw:.1f},{y + ch - ry:.1f} L{x + cw:.1f},{y + ry:.1f}" fill="{fill}" stroke="{stroke}" '
                       f'stroke-width="1.4"{d}/>')
            out.append(f'<ellipse cx="{x + cw / 2:.1f}" cy="{y + ry:.1f}" rx="{cw / 2:.1f}" ry="{ry}" fill="{fill}" '
                       f'stroke="{stroke}" stroke-width="1.4"{d}/>')
        elif kind == "text":
            _, x, y, s, size, bold, color, anchor = item
            weight = ' font-weight="700"' if bold else ""
            out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color}" text-anchor="{anchor}"'
                       f'{weight}>{escape(s)}</text>')
        elif kind == "line":
            _, pts, color, width, dash = item
            d = ' stroke-dasharray="5 3"' if dash else ""
            p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            out.append(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{width}" '
                       f'stroke-linejoin="round"{d}/>')
        elif kind == "poly":
            _, pts, fill = item
            p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            out.append(f'<polygon points="{p}" fill="{fill}"/>')
        elif kind == "circle":
            _, cx, cy, r, fill, stroke = item
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" stroke="{stroke}" '
                       f'stroke-width="1.4"/>')
        elif kind == "arc":
            _, cx, cy, r, color = item
            out.append(f'<path d="M{cx - r:.1f},{cy:.1f} A{r},{r} 0 0 1 {cx + r:.1f},{cy:.1f}" fill="none" '
                       f'stroke="{color}" stroke-width="1.4"/>')
    out.append("</svg>")
    return "\n".join(out)


# ------------------------------------------------------------------ reportlab (PDF)
def to_drawing(arch: dict, max_width: float, max_height: float):
    """Vector reportlab Drawing scaled to fit the given box (points)."""
    from reportlab.graphics.shapes import Circle, Drawing, Ellipse, Group, Path, PolyLine, Polygon, Rect, String
    from reportlab.lib.colors import HexColor

    scene = layout(arch)
    H = scene.height
    s = min(max_width / scene.width, max_height / H)
    g = Group()
    for item in scene.items:
        kind = item[0]
        if kind == "rect":
            _, x, y, w, h, fill, stroke, sw, dash, r = item
            g.add(Rect(x, H - y - h, w, h, rx=r, ry=r, fillColor=HexColor(fill), strokeColor=HexColor(stroke),
                       strokeWidth=sw, strokeDashArray=[6, 4] if dash else None))
        elif kind == "cyl":
            _, x, y, w, h, fill, stroke, dash = item
            da = [6, 4] if dash else None
            ry = 7
            g.add(Ellipse(x + w / 2, H - (y + h - ry), w / 2, ry, fillColor=HexColor(fill),
                          strokeColor=HexColor(stroke), strokeWidth=1.4, strokeDashArray=da))
            g.add(Rect(x, H - (y + h - ry), w, h - 2 * ry, fillColor=HexColor(fill), strokeColor=None))
            for lx in (x, x + w):
                g.add(PolyLine([lx, H - y - ry, lx, H - (y + h - ry)], strokeColor=HexColor(stroke), strokeWidth=1.4,
                               strokeDashArray=da))
            g.add(Ellipse(x + w / 2, H - y - ry, w / 2, ry, fillColor=HexColor(fill), strokeColor=HexColor(stroke),
                          strokeWidth=1.4, strokeDashArray=da))
        elif kind == "text":
            _, x, y, text, size, bold, color, anchor = item
            g.add(String(x, H - y, text, fontName=FONT_BOLD if bold else FONT, fontSize=size,
                         fillColor=HexColor(color), textAnchor=anchor))
        elif kind == "line":
            _, pts, color, width, dash = item
            g.add(PolyLine([c for x, y in pts for c in (x, H - y)], strokeColor=HexColor(color), strokeWidth=width,
                           strokeDashArray=[5, 3] if dash else None, strokeLineJoin=1))
        elif kind == "poly":
            _, pts, fill = item
            g.add(Polygon([c for x, y in pts for c in (x, H - y)], fillColor=HexColor(fill), strokeColor=None))
        elif kind == "circle":
            _, cx, cy, r, fill, stroke = item
            g.add(Circle(cx, H - cy, r, fillColor=HexColor(fill), strokeColor=HexColor(stroke), strokeWidth=1.4))
        elif kind == "arc":
            _, cx, cy, r, color = item
            p = Path(strokeColor=HexColor(color), strokeWidth=1.4, fillColor=None)
            p.moveTo(cx - r, H - cy)
            p.curveTo(cx - r, H - cy + r * 1.33, cx + r, H - cy + r * 1.33, cx + r, H - cy)
            g.add(p)
    g.scale(s, s)
    d = Drawing(scene.width * s, H * s)
    d.add(g)
    return d


# ------------------------------------------------------------------ PNG (DOCX)
_TTF = [
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]


def to_png(arch: dict, scale: float = 2.0) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    scene = layout(arch)
    S = scale
    img = Image.new("RGB", (int(scene.width * S), int(scene.height * S)), "#ffffff")
    dr = ImageDraw.Draw(img)
    fonts: dict[tuple, object] = {}
    regular_path = bold_path = None
    for r, b in _TTF:
        if Path(r).exists() and Path(b).exists():
            regular_path, bold_path = r, b
            break

    def font(size: float, bold: bool):
        key = (size, bold)
        if key not in fonts:
            path = bold_path if bold else regular_path
            fonts[key] = (ImageFont.truetype(path, int(size * S)) if path
                          else ImageFont.load_default(size=int(size * S)))
        return fonts[key]

    def P(pts):
        return [(x * S, y * S) for x, y in pts]

    def dashed(pts, color, width, on=6.0, off=4.0):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            t = 0.0
            while t < length:
                t2 = min(t + on, length)
                a = (x1 + (x2 - x1) * t / length, y1 + (y2 - y1) * t / length)
                b = (x1 + (x2 - x1) * t2 / length, y1 + (y2 - y1) * t2 / length)
                dr.line(P([a, b]), fill=color, width=max(1, int(width * S)))
                t += on + off

    for item in scene.items:
        kind = item[0]
        if kind == "rect":
            _, x, y, w, h, fill, stroke, sw, dash, r = item
            box = [x * S, y * S, (x + w) * S, (y + h) * S]
            if dash:
                dr.rounded_rectangle(box, radius=r * S, fill=fill)
                dashed([(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)], stroke, sw)
            else:
                dr.rounded_rectangle(box, radius=r * S, fill=fill, outline=stroke, width=max(1, int(sw * S)))
        elif kind == "cyl":
            _, x, y, w, h, fill, stroke, dash = item
            ry = 7
            lw = max(1, int(1.4 * S))
            dr.ellipse([x * S, (y + h - 2 * ry) * S, (x + w) * S, (y + h) * S], fill=fill, outline=stroke, width=lw)
            dr.rectangle([x * S, (y + ry) * S, (x + w) * S, (y + h - ry) * S], fill=fill)
            for lx in (x, x + w):
                (dashed if dash else lambda p, c, wd: dr.line(P(p), fill=c, width=lw))(
                    [(lx, y + ry), (lx, y + h - ry)], stroke, 1.4)
            dr.ellipse([x * S, y * S, (x + w) * S, (y + 2 * ry) * S], fill=fill, outline=stroke, width=lw)
        elif kind == "text":
            _, x, y, text, size, bold, color, anchor = item
            dr.text((x * S, y * S), text, fill=color, font=font(size, bold),
                    anchor={"start": "ls", "middle": "ms", "end": "rs"}[anchor])
        elif kind == "line":
            _, pts, color, width, dash = item
            if dash:
                dashed(pts, color, width, 5, 3)
            else:
                dr.line(P(pts), fill=color, width=max(1, int(width * S)), joint="curve")
        elif kind == "poly":
            _, pts, fill = item
            dr.polygon(P(pts), fill=fill)
        elif kind == "circle":
            _, cx, cy, r, fill, stroke = item
            dr.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=fill, outline=stroke,
                       width=max(1, int(1.4 * S)))
        elif kind == "arc":
            _, cx, cy, r, color = item
            dr.arc([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], 180, 360, fill=color,
                   width=max(1, int(1.4 * S)))
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
