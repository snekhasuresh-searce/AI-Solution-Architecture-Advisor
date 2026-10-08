"""Architecture normalisation, diagram rendering, report section and exports."""

import io
import json
import os

os.environ["ADVISOR_PROVIDER"] = "mock"

from docx import Document  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from advisor import diagram  # noqa: E402
from advisor.architecture import normalize  # noqa: E402
from advisor.export import parse, to_docx, to_pdf  # noqa: E402
from advisor.mock_llm import _architect  # noqa: E402
from advisor.report import architecture_markdown  # noqa: E402

BRIEF = {"title": "Policy assistant", "functional_requirements": ["Answer questions", "Cite sources"],
         "non_functional_requirements": ["Secure"]}


def _arch(domains="aiml, backend, cloud"):
    system = f"## Domains\n{domains}\nCloud in scope: yes\n## Requirement brief\n{json.dumps(BRIEF)}\n## x"
    return normalize(_architect(system), brief=BRIEF, requirement_text="RAG assistant on Google Cloud",
                     chosen=["Next.js", "NestJS", "PostgreSQL", "Gemini", "pgvector", "Identity Platform", "REST"])


def test_normalize_cleans_model_output():
    raw = {
        "nodes": [
            {"id": "Web App", "label": "Web app", "layer": "application", "kind": "proposed",
             "technology": "Next.js", "status": "required", "purpose": "UI"},
            {"id": "web_app", "label": "Duplicate id", "layer": "nonsense", "kind": "??", "purpose": "x"},
            {"id": "kafka", "label": "Event bus", "layer": "api", "kind": "proposed",
             "technology": "Kafka", "status": "required", "purpose": "Invented by the model"},
        ],
        "flows": [{"name": "Main", "kind": "request", "steps": [
            {"source": "Web App", "target": "kafka", "label": "publish"},
            {"source": "Web App", "target": "missing", "label": "dropped"},
        ]}],
        "requirement_mapping": [{"requirement": "Answer  questions", "components": ["web_app", "nope"]}],
    }
    a = normalize(raw, brief=BRIEF, requirement_text="", chosen=["Next.js"])
    ids = [n["id"] for n in a["nodes"]]
    assert ids == ["web_app", "web_app_2", "kafka"]
    assert a["nodes"][1]["layer"] == "api" and a["nodes"][1]["kind"] == "proposed"
    # Not in the requirement nor chosen by a specialist -> shown as our recommendation.
    assert a["nodes"][2]["status"] == "recommended" and a["nodes"][0]["status"] == "required"
    assert a["flows"][0]["steps"] == [{"source": "web_app", "target": "kafka", "label": "publish"}]
    # Every brief requirement gets a traceability row; unmapped ones are listed.
    assert [m["requirement"] for m in a["requirement_mapping"]] == ["Answer questions", "Cite sources", "Secure"]
    assert a["requirement_mapping"][0]["components"] == ["web_app"]
    assert a["unmapped"] == ["Cite sources", "Secure"]
    assert a["technology_stack"]  # derived from the nodes when the model gave none


def test_diagram_renders_all_formats():
    a = _arch()
    svg = diagram.to_svg(a)
    assert svg.startswith("<svg") and "AI LAYER" in svg and "Vector store" in svg and ">A1<" in svg
    assert diagram.to_png(a).startswith(b"\x89PNG")
    d = diagram.to_drawing(a, 700, 500)
    assert d.width <= 700.5 and d.height <= 500.5


def test_frontend_only_has_no_ai_layer():
    svg = diagram.to_svg(_arch("frontend"))
    assert "AI LAYER" not in svg and "DATA LAYER" not in svg


def test_report_section_and_exports():
    a = _arch()
    md = "# Policy assistant\n\n" + "\n".join(architecture_markdown("abcd1234", a, 2))
    assert "### 2.1 High-level solution architecture diagram" in md
    assert "![High-level solution architecture](/api/runs/abcd1234/diagram.svg)" in md
    for heading in ("End-to-end data flow", "Major components", "Requirement traceability", "Key assumptions",
                    "Recommended technology stack", "Security considerations", "Scalability and future"):
        assert heading in md
    assert "**A1.** End users → Web application" in md
    assert "image" in [b.kind for b in parse(md)]

    doc = Document(io.BytesIO(to_docx(md, a)))
    assert len(doc.inline_shapes) == 1 and len(doc.sections) == 1
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(to_pdf(md, a))).pages)
    assert "Vector store" in text and "Requirement traceability" in text
    # Without an architecture the exports still work and say the diagram is missing.
    assert "not available" in "".join(p.extract_text() for p in PdfReader(io.BytesIO(to_pdf(md))).pages)
