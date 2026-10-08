"""Final recommendation package as Markdown (9 parts, incl. the solution architecture)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .catalogue import load_catalogue, technologies_in
from .config import settings
from .consistency import find_conflicts

SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _bullets(items) -> str:
    items = list(items)
    return "\n".join(f"- {i}" for i in items) if items else "- None stated"


def _merge_components(outputs: dict[str, dict]) -> list[dict]:
    """One row per component name; the first agent's description is kept."""
    merged: dict[str, dict] = {}
    for agent, out in outputs.items():
        for c in out.get("components", []):
            key = " ".join(c.get("name", "").lower().split())
            row = merged.setdefault(key, {"name": c.get("name", ""), "responsibility": c.get("responsibility", ""),
                                          "agents": []})
            if agent not in row["agents"]:
                row["agents"].append(agent)
    return list(merged.values())


def _merge_choices(outputs: dict[str, dict]) -> list[dict]:
    """One row per (category, technology), in catalogue order; alternatives are unioned."""
    merged: dict[tuple, dict] = {}
    for agent, out in outputs.items():
        for t in out.get("technology_choices", []):
            choice = t.get("choice", "")
            key = (t.get("category", ""), tuple(technologies_in(choice)) or choice.strip().lower())
            row = merged.setdefault(key, {"category": key[0], "choice": choice, "rationale": t.get("rationale", ""),
                                          "alternatives": [], "agents": []})
            row["alternatives"] += [a for a in t.get("alternatives", []) if a not in row["alternatives"]]
            if agent not in row["agents"]:
                row["agents"].append(agent)
    order = {c: i for i, c in enumerate(load_catalogue())}
    rows = sorted(merged.values(), key=lambda r: order.get(r["category"], len(order)))
    for r in rows:  # an alternative that another row already chose is not an alternative
        chosen = {x["choice"] for x in rows if x["category"] == r["category"]}
        r["alternatives"] = [a for a in r["alternatives"] if a not in chosen]
    return rows


def diagram_url(run_id: str) -> str:
    return f"/api/runs/{run_id}/diagram.svg"


def _cell(text) -> str:
    return " ".join(str(text).split()).replace("|", "/")


def architecture_markdown(run_id: str, arch: dict, section: int) -> list[str]:
    """The presales architecture section: diagram, data flow, components, assumptions,
    stack, security and scalability, plus requirement traceability."""
    from .architecture import LAYER_TITLES, LAYERS

    names = {n["id"]: n["label"] for n in arch.get("nodes", [])}
    s = section
    lines = [f"## {s}. Solution architecture", ""]
    if arch.get("overview"):
        lines += [arch["overview"], ""]

    lines += [f"### {s}.1 High-level solution architecture diagram", "",
              f"![High-level solution architecture]({diagram_url(run_id)})", "",
              f"**Cloud:** {arch.get('cloud_provider', 'To be confirmed')}. Boxes are grouped by layer and coloured "
              "by type (client system, proposed component, third-party, managed cloud service, AI, data store). "
              "Dashed boxes are recommended additions that the requirement did not state.", ""]

    lines += [f"### {s}.2 End-to-end data flow", ""]
    for flow in arch.get("flows", []):
        prefix = "A" if flow["kind"] == "ai" else ""
        lines += [f"**{flow['name']}**" + (" (AI workflow)" if flow["kind"] == "ai" else ""), ""]
        lines += [f"- **{prefix}{k}.** {names.get(st['source'], st['source'])} → "
                  f"{names.get(st['target'], st['target'])}: {st['label']}" for k, st in enumerate(flow["steps"], 1)]
        lines.append("")
    if not arch.get("flows"):
        lines += ["- No flow was produced.", ""]

    lines += [f"### {s}.3 Major components", "", "| Layer | Component | Technology | Type | Status | Purpose |",
              "| --- | --- | --- | --- | --- | --- |"]
    for layer in LAYERS:
        for n in (x for x in arch.get("nodes", []) if x["layer"] == layer):
            lines.append(f"| {LAYER_TITLES[layer]} | {_cell(n['label'])} | {_cell(n['technology'] or '-')} | "
                         f"{n['kind'].replace('_', ' ')} | {n['status']} | {_cell(n['purpose'])} |")
    lines.append("")

    lines += [f"### {s}.4 Requirement traceability", "", "| Requirement | Delivered by |", "| --- | --- |"]
    for m in arch.get("requirement_mapping", []):
        comps = ", ".join(names.get(c, c) for c in m["components"]) or "**Not mapped**"
        lines.append(f"| {_cell(m['requirement'])} | {comps} |")
    if arch.get("unmapped"):
        lines += ["", f"> {len(arch['unmapped'])} requirement(s) are not yet mapped to a component; "
                      "confirm scope with the client."]
    lines.append("")

    lines += [f"### {s}.5 Key assumptions", "", _bullets(arch.get("assumptions", [])), ""]

    lines += [f"### {s}.6 Recommended technology stack", "", "| Layer | Technology | Purpose | Status |",
              "| --- | --- | --- | --- |"]
    order = {k: i for i, k in enumerate(LAYERS)}
    for t in sorted(arch.get("technology_stack", []), key=lambda t: order.get(t.get("layer"), 99)):
        lines.append(f"| {LAYER_TITLES.get(t.get('layer'), t.get('layer', ''))} | {_cell(t['technology'])} | "
                     f"{_cell(t.get('purpose', ''))} | {t.get('status', 'recommended')} |")
    lines.append("")

    lines += [f"### {s}.7 Security considerations", "", _bullets(arch.get("security_considerations", [])), ""]
    lines += [f"### {s}.8 Scalability and future enhancements", "", "**Scalability**", "",
              _bullets(arch.get("scalability_considerations", [])), "", "**Future enhancements**", "",
              _bullets(arch.get("future_enhancements", [])), ""]
    return lines


def build_markdown(*, run_id, status, brief, domains, plan_text, outputs, review, score, history, unknown_tech,
                   architecture=None) -> str:
    title = brief.get("title", "Solution recommendation")
    lines: list[str] = [f"# {title}", ""]
    badge = {"APPROVED": "Approved by reviewer", "ESCALATED": "Escalated - needs human architect review"}[status]
    lines += [f"**Status:** {badge}  ", f"**Run:** {run_id} - {datetime.now():%Y-%m-%d %H:%M}  ",
              f"**Domains:** {', '.join(domains)}", ""]

    # 1. Executive summary
    lines += ["## 1. Executive summary", "", brief.get("summary", ""), ""]
    if review.get("summary"):
        lines += [f"**Reviewer:** {review['summary']}", ""]

    # 2. Solution architecture (diagram + presales narrative); later sections shift by one
    n = 2
    if architecture:
        lines += architecture_markdown(run_id, architecture, n)
        n += 1

    # Solution design
    lines += [f"## {n}. Solution design", "", "### Agents used", "", plan_text, ""]
    lines += ["### Components", "", "| Component | Responsibility | From |", "| --- | --- | --- |"]
    for c in _merge_components(outputs):
        lines.append(f"| {c['name']} | {c['responsibility']} | {', '.join(c['agents'])} |")
    lines += ["", "### Technology choices", "", "| Category | Choice | Rationale | Alternatives | From |",
              "| --- | --- | --- | --- | --- |"]
    for t in _merge_choices(outputs):
        lines.append(f"| {t['category']} | {t['choice']} | {t['rationale']} | "
                     f"{', '.join(t['alternatives'])} | {', '.join(t['agents'])} |")
    conflicts = find_conflicts(outputs)
    if conflicts:
        lines += ["", "**Unresolved conflicts:**", "", _bullets(c["description"] for c in conflicts)]
    lines.append("")

    # 3. Specialist findings
    lines += [f"## {n + 1}. Specialist findings", ""]
    for agent, out in outputs.items():
        lines += [f"### {agent}", "", out.get("summary", ""), "", _bullets(out.get("design_notes", [])), ""]

    # 4. Alternatives (already per choice) -> pointer
    lines += [f"## {n + 2}. Alternatives", "", f"Listed per technology choice in section {n}.", ""]

    # 5. Risks
    lines += [f"## {n + 3}. Risks", "", "| Risk | Severity | Likelihood | Mitigation | From |", "| --- | --- | --- | --- | --- |"]
    risks = [(a, r) for a, o in outputs.items() for r in o.get("risks", [])]
    risks.sort(key=lambda x: SEV_ORDER.get(x[1].get("severity", "low"), 9))
    for agent, r in risks:
        lines.append(f"| {r.get('description','')} | {r.get('severity','')} | {r.get('likelihood','')} | "
                     f"{r.get('mitigation','')} | {agent} |")
    for t in unknown_tech:
        lines.append(f"| '{t}' is not in the approved catalogue | medium | - | Verify or add to catalogue | auto-check |")
    lines.append("")

    # 6. Score
    lines += [f"## {n + 4}. Quality score", ""]
    if score:
        lines += [f"**Overall: {score.overall}/100**", "", "| Dimension | Weight % | Score |", "| --- | --- | --- |"]
        for dim, w in sorted(score.weights.items(), key=lambda x: -x[1]):
            lines.append(f"| {dim} | {w} | {score.scores.get(dim, '-')} |")
        if score.blockers:
            lines += ["", "Open blockers: " + "; ".join(score.blockers)]
    lines.append("")

    # 7. Assumptions
    assumptions = list(brief.get("assumptions", []))
    for out in outputs.values():
        assumptions += out.get("assumptions", [])
    lines += [f"## {n + 5}. Assumptions", "", _bullets(dict.fromkeys(assumptions)), ""]

    # 8. Review history
    lines += [f"## {n + 6}. Review history", "", "| Round | Decision | Score | Findings (severity) |", "| --- | --- | --- | --- |"]
    for h in history:
        f = ", ".join(f"{x.get('severity')}: {x.get('description','')[:60]}" for x in h["findings"]) or "none"
        lines.append(f"| {h['round']} | {h['decision']} | {h['overall']} | {f} |")
    return "\n".join(lines) + "\n"


def path_for(run_id: str) -> Path:
    # Run ids are 8 hex chars; anything else could escape the output directory.
    if not re.fullmatch(r"[0-9a-f]{8}", run_id):
        raise ValueError(f"Invalid run id: {run_id!r}")
    return Path(settings.output_dir) / f"recommendation_{run_id}.md"


def save(run_id: str, markdown: str) -> str:
    path = path_for(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return str(path)


def load(run_id: str) -> str | None:
    """The saved Markdown for a run, or None if there is no report file."""
    path = path_for(run_id)
    return path.read_text(encoding="utf-8") if path.exists() else None
