"""Final recommendation package as Markdown (9 parts: the 8 from the requirements plus resources and estimate)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .catalogue import load_catalogue, technologies_in
from .config import settings
from .consistency import find_conflicts
from .estimate import DAYS_PER_MONTH, gantt, summarize

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


def _cell(text) -> str:
    """Table-safe text: a '|' inside model output would split the cell."""
    return str(text).replace("|", "/").replace("\n", " ")


def _days(d: float) -> str:
    return f"{d:g}"


def _estimate_section(estimate: dict) -> list[str]:
    lines = ["## 3. Resources and estimate", ""]
    summary = summarize(estimate) if estimate else None
    if not estimate or summary is None:
        return lines + ["Estimate not available: the estimator did not return a result for this run.", ""]

    team = estimate.get("human_resources", [])
    lines += ["### Required human resources", "",
              "| Role | FTE | Seniority | Responsibilities | Phases |", "| --- | --- | --- | --- | --- |"]
    for r in team:
        lines.append(f"| {_cell(r.get('role', ''))} | {float(r.get('count', 0)):g} | {r.get('seniority', '')} | "
                     f"{_cell(r.get('responsibilities', ''))} | {_cell(', '.join(r.get('phases', [])))} |")
    lines += ["", f"**Team size:** {summary.team_fte:g} FTE across {len(team)} roles.", ""]

    tech = sorted(estimate.get("technical_resources", []),
                  key=lambda t: (not str(t.get("category", "")).startswith("ai_"), t.get("category", "")))
    lines += ["### Required AI and technical resources", "",
              "| Type | Resource | Purpose | Sizing |", "| --- | --- | --- | --- |"]
    for t in tech:
        kind = str(t.get("category", "")).replace("_", " ")
        lines.append(f"| {kind} | {_cell(t.get('name', ''))} | {_cell(t.get('purpose', ''))} | "
                     f"{_cell(t.get('sizing', ''))} |")
    if not any(str(t.get("category", "")).startswith("ai_") for t in tech):
        lines += ["", "_No AI models or services are needed for this solution._"]
    lines.append("")

    lines += ["### Estimated development effort", "",
              "| Phase | Roles | Low | Likely | High |", "| --- | --- | --- | --- | --- |"]
    for p in summary.phases:
        lines.append(f"| {_cell(p.phase)} | {_cell(', '.join(p.roles))} | {_days(p.low)} | {_days(p.likely)} | "
                     f"{_days(p.high)} |")
    lines.append(f"| **Total (person-days)** | | **{_days(summary.effort_low)}** | **{_days(summary.effort_likely)}** | "
                 f"**{_days(summary.effort_high)}** |")
    lines += ["", f"About **{summary.person_months_likely:.1f} person-months** likely "
                  f"({DAYS_PER_MONTH} working days per month).", ""]

    lines += ["### Estimated timeline", "",
              "| Phase | Weeks | Duration | Depends on | Schedule |", "| --- | --- | --- | --- | --- |"]
    for p in summary.phases:
        weeks = f"{p.start_week:g}" if p.end_week <= p.start_week else f"{p.start_week:g}–{p.end_week:g}"
        lines.append(f"| {_cell(p.phase)} | {weeks} | {p.duration_weeks:g} wk | "
                     f"{_cell(', '.join(p.depends_on)) or '-'} | {gantt(p, summary.total_weeks)} |")
    lines += ["", f"**Total: about {summary.total_weeks:g} weeks** with the team above "
                  f"(range {summary.weeks_low:g}–{summary.weeks_high:g} weeks, following the effort range).", ""]

    if summary.warnings:
        lines += ["> **Estimate checks:** " + " ".join(summary.warnings), ""]
    if estimate.get("risks_to_estimate"):
        lines += ["**What could change the estimate:**", "", _bullets(estimate["risks_to_estimate"]), ""]
    return lines


def build_markdown(*, run_id, status, brief, domains, plan_text, outputs, review, score, history, unknown_tech,
                   estimate: dict | None = None) -> str:
    estimate = estimate or {}
    title = brief.get("title", "Solution recommendation")
    lines: list[str] = [f"# {title}", ""]
    badge = {"APPROVED": "Approved by reviewer", "ESCALATED": "Escalated - needs human architect review"}[status]
    lines += [f"**Status:** {badge}  ", f"**Run:** {run_id} - {datetime.now():%Y-%m-%d %H:%M}  ",
              f"**Domains:** {', '.join(domains)}", ""]

    # 1. Executive summary
    lines += ["## 1. Executive summary", "", brief.get("summary", ""), ""]
    project_type = estimate.get("project_type") or {}
    if project_type:
        lines += [f"**Project type:** {project_type.get('label', '')} - {project_type.get('complexity', '')} "
                  f"complexity. {project_type.get('rationale', '')}", ""]
    summary = summarize(estimate) if estimate else None
    if summary:
        lines += [f"**At a glance:** {summary.team_fte:g} FTE team, about {summary.effort_likely:g} person-days "
                  f"of effort, about {summary.total_weeks:g} weeks to deliver.", ""]
    if review.get("summary"):
        lines += [f"**Reviewer:** {review['summary']}", ""]

    # 2. Solution design
    lines += ["## 2. Solution design", ""]
    arch = estimate.get("architecture") or {}
    if arch:
        lines += ["### Recommended architecture", "", f"**Style:** {arch.get('style', '')}", "",
                  arch.get("overview", ""), ""]
        if arch.get("layers"):
            lines += [_bullets(arch["layers"]), ""]
    lines += ["### Agents used", "", plan_text, ""]
    lines += ["### Components", "", "| Component | Responsibility | From |", "| --- | --- | --- |"]
    for c in _merge_components(outputs):
        lines.append(f"| {c['name']} | {c['responsibility']} | {', '.join(c['agents'])} |")
    lines += ["", "### Recommended technology stack", "", "| Category | Choice | Rationale | Alternatives | From |",
              "| --- | --- | --- | --- | --- |"]
    for t in _merge_choices(outputs):
        lines.append(f"| {t['category']} | {t['choice']} | {t['rationale']} | "
                     f"{', '.join(t['alternatives'])} | {', '.join(t['agents'])} |")
    conflicts = find_conflicts(outputs)
    if conflicts:
        lines += ["", "**Unresolved conflicts:**", "", _bullets(c["description"] for c in conflicts)]
    lines.append("")

    # 3. Resources and estimate
    lines += _estimate_section(estimate)

    # 4. Specialist findings
    lines += ["## 4. Specialist findings", ""]
    for agent, out in outputs.items():
        lines += [f"### {agent}", "", out.get("summary", ""), "", _bullets(out.get("design_notes", [])), ""]

    # 5. Alternatives (already per choice) -> pointer
    lines += ["## 5. Alternatives", "", "Listed per technology choice in section 2.", ""]

    # 6. Risks
    lines += ["## 6. Risks", "", "| Risk | Severity | Likelihood | Mitigation | From |", "| --- | --- | --- | --- | --- |"]
    risks = [(a, r) for a, o in outputs.items() for r in o.get("risks", [])]
    risks.sort(key=lambda x: SEV_ORDER.get(x[1].get("severity", "low"), 9))
    for agent, r in risks:
        lines.append(f"| {r.get('description','')} | {r.get('severity','')} | {r.get('likelihood','')} | "
                     f"{r.get('mitigation','')} | {agent} |")
    for t in unknown_tech:
        lines.append(f"| '{t}' is not in the approved catalogue | medium | - | Verify or add to catalogue | auto-check |")
    lines.append("")

    # 7. Score
    lines += ["## 7. Quality score", ""]
    if score:
        lines += [f"**Overall: {score.overall}/100**", "", "| Dimension | Weight % | Score |", "| --- | --- | --- |"]
        for dim, w in sorted(score.weights.items(), key=lambda x: -x[1]):
            lines.append(f"| {dim} | {w} | {score.scores.get(dim, '-')} |")
        if score.blockers:
            lines += ["", "Open blockers: " + "; ".join(score.blockers)]
    lines.append("")

    # 8. Assumptions
    assumptions = list(brief.get("assumptions", []))
    for out in outputs.values():
        assumptions += out.get("assumptions", [])
    assumptions += estimate.get("assumptions", [])
    lines += ["## 8. Assumptions", "", _bullets(dict.fromkeys(assumptions)), ""]

    # 9. Review history
    lines += ["## 9. Review history", "", "| Round | Decision | Score | Findings (severity) |", "| --- | --- | --- | --- |"]
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
