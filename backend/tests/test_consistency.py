import pytest
from pydantic import ValidationError

from advisor.consistency import find_conflicts
from advisor.report import _merge_choices, _merge_components
from advisor.schemas import TechnologyChoice


def _out(*choices, components=()):
    return {
        "technology_choices": [{"category": c, "choice": ch, "rationale": f"{ch} rationale", "alternatives": alt}
                               for c, ch, alt in choices],
        "components": [{"name": n, "responsibility": f"{n} job"} for n in components],
    }


# Hosting split 2-2 across agents, as seen in a real Gemini run.
SPLIT_HOSTING = {
    "frontend": _out(("frontend_framework", "Astro", ["Next.js"]), ("hosting_static", "Netlify", ["Vercel"]),
                     components=["Contact Form"]),
    "uiux": _out(("frontend_framework", "Astro", ["React"]), ("hosting_static", "Vercel", ["Netlify"]),
                 components=["Contact form"]),
    "security": _out(("hosting_static", "Netlify", ["Firebase Hosting"])),
    "performance": _out(("hosting_static", "Vercel", ["Netlify"]), ("testing_quality", "Lighthouse", [])),
}


def test_owner_wins_and_dissenters_get_high_findings():
    findings = find_conflicts(SPLIT_HOSTING)
    assert sorted(f["responsible_agent"] for f in findings) == ["performance", "uiux"]
    assert all(f["severity"] == "high" and "Netlify" in f["recommendation"] for f in findings)


def test_cloud_agent_owns_hosting_when_present():
    outputs = {"frontend": _out(("hosting_static", "Netlify", [])),
               "cloud": _out(("hosting_static", "Firebase Hosting", []))}
    [finding] = find_conflicts(outputs)
    assert finding["responsible_agent"] == "frontend"
    assert "Firebase Hosting" in finding["recommendation"]


def test_overlapping_or_multi_choice_categories_are_not_conflicts():
    outputs = {"frontend": _out(("frontend_framework", "Next.js (React)", []), ("testing_quality", "Playwright", [])),
               "uiux": _out(("frontend_framework", "React", [])),
               "performance": _out(("testing_quality", "Lighthouse", []))}
    assert find_conflicts(outputs) == []


def test_category_must_be_a_catalogue_key():
    TechnologyChoice(category="hosting_static", choice="Netlify", rationale="r")
    with pytest.raises(ValidationError):
        TechnologyChoice(category="Hosting", choice="Netlify", rationale="r")


def test_report_merges_duplicate_rows():
    rows = _merge_choices(SPLIT_HOSTING)
    astro = [r for r in rows if r["choice"] == "Astro"]
    assert len(astro) == 1 and astro[0]["agents"] == ["frontend", "uiux"]
    assert astro[0]["alternatives"] == ["Next.js", "React"]
    netlify = next(r for r in rows if r["choice"] == "Netlify")
    assert netlify["agents"] == ["frontend", "security"]
    assert "Vercel" not in netlify["alternatives"]  # chosen in another row, so not an alternative
    assert [r["category"] for r in rows][0] == "frontend_framework"  # catalogue order

    [form] = _merge_components(SPLIT_HOSTING)
    assert form["agents"] == ["frontend", "uiux"]
