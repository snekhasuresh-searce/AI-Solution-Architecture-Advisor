"""Totals, timeline and capacity checks for the Estimator's output.

The model estimates effort per phase; the arithmetic is done here so totals
always add up, and a phase the assigned team cannot deliver in its stated
duration is flagged instead of silently trusted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DAYS_PER_WEEK = 5
DAYS_PER_MONTH = 20
CAPACITY_TOLERANCE = 1.15  # allow 15% over nominal capacity before flagging


@dataclass
class PhaseRow:
    phase: str
    start_week: float
    end_week: float
    duration_weeks: float
    low: float
    likely: float
    high: float
    roles: list[str]
    depends_on: list[str]


@dataclass
class EstimateSummary:
    phases: list[PhaseRow]
    effort_low: float
    effort_likely: float
    effort_high: float
    team_fte: float
    total_weeks: float
    weeks_low: float
    weeks_high: float
    warnings: list[str] = field(default_factory=list)

    @property
    def person_months_likely(self) -> float:
        return self.effort_likely / DAYS_PER_MONTH


def _norm(role: str) -> str:
    return " ".join(role.lower().split())


def summarize(estimate: dict) -> EstimateSummary | None:
    phases = estimate.get("phases") or []
    team = estimate.get("human_resources") or []
    if not phases:
        return None

    fte_by_role = {}
    for r in team:
        fte_by_role[_norm(r.get("role", ""))] = fte_by_role.get(_norm(r.get("role", "")), 0) + float(r.get("count", 0))
    team_fte = round(sum(fte_by_role.values()), 2)

    rows: list[PhaseRow] = []
    warnings: list[str] = []
    for p in phases:
        low, likely, high = (float(p.get(k, 0)) for k in ("effort_days_low", "effort_days_likely", "effort_days_high"))
        if not low <= likely <= high:
            warnings.append(f"{p.get('phase')}: effort range was not low <= likely <= high; it has been reordered.")
            low, likely, high = sorted((low, likely, high))
        start = float(p.get("start_week", 1))
        duration = float(p.get("duration_weeks", 1))
        roles = list(p.get("roles") or [])
        rows.append(PhaseRow(p.get("phase", "Phase"), start, start - 1 + duration, duration, low, likely, high,
                             roles, list(p.get("depends_on") or [])))

        # Capacity: can the roles assigned to this phase deliver its likely effort in time?
        known = [r for r in roles if _norm(r) in fte_by_role]
        unknown = [r for r in roles if _norm(r) not in fte_by_role]
        if unknown:
            warnings.append(f"{p.get('phase')}: role(s) {', '.join(unknown)} are not in the proposed team.")
        fte = sum(fte_by_role[_norm(r)] for r in known) if known else team_fte
        capacity = fte * DAYS_PER_WEEK * duration
        if capacity and likely > capacity * CAPACITY_TOLERANCE:
            warnings.append(
                f"{p.get('phase')}: {likely:g} person-days likely, but the assigned roles ({fte:g} FTE) provide "
                f"about {capacity:g} in {duration:g} weeks. Extend the phase or add people."
            )

    effort_low = sum(r.low for r in rows)
    effort_likely = sum(r.likely for r in rows)
    effort_high = sum(r.high for r in rows)
    total_weeks = max(r.end_week for r in rows)
    # Same team, so calendar time scales roughly with effort.
    ratio_low = effort_low / effort_likely if effort_likely else 1
    ratio_high = effort_high / effort_likely if effort_likely else 1
    return EstimateSummary(rows, effort_low, effort_likely, effort_high, team_fte, total_weeks,
                           round(total_weeks * ratio_low, 1), round(total_weeks * ratio_high, 1), warnings)


def gantt(row: PhaseRow, total_weeks: float, width: int = 24) -> str:
    """A one-line bar: filled for the weeks the phase runs."""
    scale = width / max(total_weeks, 1)
    start = int(round((row.start_week - 1) * scale))
    length = max(1, int(round(row.duration_weeks * scale)))
    start = min(start, width - 1)
    length = min(length, width - start)
    return "░" * start + "█" * length + "░" * (width - start - length)
