from advisor.estimate import gantt, summarize
from advisor.report import _estimate_section

ESTIMATE = {
    "human_resources": [
        {"role": "Frontend developer", "count": 1, "seniority": "mid", "responsibilities": "UI", "phases": ["Build"]},
        {"role": "QA engineer", "count": 0.5, "seniority": "mid", "responsibilities": "Tests", "phases": ["Test"]},
    ],
    "technical_resources": [{"category": "hosting", "name": "Netlify", "purpose": "Static hosting", "sizing": "Pro"}],
    "phases": [
        {"phase": "Build", "roles": ["Frontend developer"], "effort_days_low": 12, "effort_days_likely": 15,
         "effort_days_high": 20, "start_week": 1, "duration_weeks": 3},
        {"phase": "Test", "roles": ["QA engineer"], "effort_days_low": 3, "effort_days_likely": 5,
         "effort_days_high": 6, "start_week": 3, "duration_weeks": 2},
    ],
}


def test_totals_and_timeline():
    s = summarize(ESTIMATE)
    assert (s.effort_low, s.effort_likely, s.effort_high) == (15, 20, 26)
    assert s.team_fte == 1.5 and s.total_weeks == 4  # Test overlaps Build in week 3
    assert s.person_months_likely == 1
    assert (s.weeks_low, s.weeks_high) == (3.0, 5.2)
    assert s.warnings == []


def test_capacity_and_role_checks():
    over = {**ESTIMATE, "phases": [{**ESTIMATE["phases"][0], "effort_days_likely": 40, "effort_days_high": 45},
                                   {**ESTIMATE["phases"][1], "roles": ["Data scientist"]}]}
    warnings = " ".join(summarize(over).warnings)
    assert "Build: 40 person-days likely" in warnings and "provide about 15" in warnings
    assert "Data scientist are not in the proposed team" in warnings


def test_reorders_bad_ranges():
    bad = {**ESTIMATE, "phases": [{**ESTIMATE["phases"][0], "effort_days_low": 20, "effort_days_high": 12}]}
    s = summarize(bad)
    assert (s.phases[0].low, s.phases[0].likely, s.phases[0].high) == (12, 15, 20)
    assert "reordered" in s.warnings[0]


def test_gantt_and_section():
    s = summarize(ESTIMATE)
    assert gantt(s.phases[0], s.total_weeks, width=8) == "██████░░"
    text = "\n".join(_estimate_section(ESTIMATE, 3))
    for heading in ("Required human resources", "Required AI and technical resources",
                    "Estimated development effort", "Estimated timeline"):
        assert f"### {heading}" in text
    assert "No AI models or services are needed" in text
    assert "**Total: about 4 weeks**" in text
    assert "not available" in "\n".join(_estimate_section({}, 3))
