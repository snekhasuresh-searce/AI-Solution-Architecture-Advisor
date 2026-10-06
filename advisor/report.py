"""Final recommendation package as Markdown (8 parts from the requirements)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import settings

SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _bullets(items) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "- None stated"


def build_markdown(*, run_id, status, brief, domains, plan_text, outputs, review, score, history, unknown_tech) -> str:
    title = brief.get("title", "Solution recommendation")
    lines: list[str] = [f"# {title}", ""]
    badge = {"APPROVED": "Approved by reviewer", "ESCALATED": "Escalated - needs human architect review"}[status]
    lines += [f"**Status:** {badge}  ", f"**Run:** {run_id} - {datetime.now():%Y-%m-%d %H:%M}  ",
              f"**Domains:** {', '.join(domains)}", ""]

    # 1. Executive summary
    lines += ["## 1. Executive summary", "", brief.get("summary", ""), ""]
    if review.get("summary"):
        lines += [f"**Reviewer:** {review['summary']}", ""]

    # 2. Solution design
    lines += ["## 2. Solution design", "", "### Agents used", "", plan_text, ""]
    lines += ["### Components", "", "| Component | Responsibility | From |", "| --- | --- | --- |"]
    for agent, out in outputs.items():
        for c in out.get("components", []):
            lines.append(f"| {c.get('name','')} | {c.get('responsibility','')} | {agent} |")
    lines += ["", "### Technology choices", "", "| Category | Choice | Rationale | Alternatives | From |",
              "| --- | --- | --- | --- | --- |"]
    for agent, out in outputs.items():
        for t in out.get("technology_choices", []):
            lines.append(f"| {t.get('category','')} | {t.get('choice','')} | {t.get('rationale','')} | "
                         f"{', '.join(t.get('alternatives', []))} | {agent} |")
    lines.append("")

    # 3. Specialist findings
    lines += ["## 3. Specialist findings", ""]
    for agent, out in outputs.items():
        lines += [f"### {agent}", "", out.get("summary", ""), "", _bullets(out.get("design_notes", [])), ""]

    # 4. Alternatives (already per choice) -> pointer
    lines += ["## 4. Alternatives", "", "Listed per technology choice in section 2.", ""]

    # 5. Risks
    lines += ["## 5. Risks", "", "| Risk | Severity | Likelihood | Mitigation | From |", "| --- | --- | --- | --- | --- |"]
    risks = [(a, r) for a, o in outputs.items() for r in o.get("risks", [])]
    risks.sort(key=lambda x: SEV_ORDER.get(x[1].get("severity", "low"), 9))
    for agent, r in risks:
        lines.append(f"| {r.get('description','')} | {r.get('severity','')} | {r.get('likelihood','')} | "
                     f"{r.get('mitigation','')} | {agent} |")
    for t in unknown_tech:
        lines.append(f"| '{t}' is not in the approved catalogue | medium | - | Verify or add to catalogue | auto-check |")
    lines.append("")

    # 6. Score
    lines += ["## 6. Quality score", ""]
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
    lines += ["## 7. Assumptions", "", _bullets(dict.fromkeys(assumptions)), ""]

    # 8. Review history
    lines += ["## 8. Review history", "", "| Round | Decision | Score | Findings (severity) |", "| --- | --- | --- | --- |"]
    for h in history:
        f = ", ".join(f"{x.get('severity')}: {x.get('description','')[:60]}" for x in h["findings"]) or "none"
        lines.append(f"| {h['round']} | {h['decision']} | {h['overall']} | {f} |")
    return "\n".join(lines) + "\n"


def save(run_id: str, markdown: str) -> str:
    out = Path(settings.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"recommendation_{run_id}.md"
    path.write_text(markdown, encoding="utf-8")
    return str(path)
