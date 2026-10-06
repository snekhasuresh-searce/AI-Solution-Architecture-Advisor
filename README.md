# AI Solution Architecture Advisor — POC boilerplate

A multi-agent advisor that turns a plain-language requirement into a reviewed
solution recommendation. Built with Google's Agent Development Kit (ADK) and
runs entirely on your laptop: **no GCP project needed**.

```
requirement ─► Analyzer ─► Agent Selector ─► Specialists (parallel) ─► Reviewer ─┬─► Recommendation (.md + SQLite log)
                  │          (rule table)          ▲                            │
                  └─ clarifying questions          └──── rework (High/Critical) ┘  max 3 rounds, then escalate
```

## Quick start (5 minutes)

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # starts in mock mode

python scripts/run.py --all          # 4 demo scenarios, no model needed
adk web .                            # chat UI at http://localhost:8000 -> pick "advisor"
pytest                               # 12 tests
```

## Choose a model (one line in `.env`)

| `ADVISOR_PROVIDER` | Needs | Use it for |
| --- | --- | --- |
| `mock` | Nothing | Testing the wiring, selection logic, rework loop, reports |
| `gemini` | Free API key from [Google AI Studio](https://aistudio.google.com/apikey) in `GOOGLE_API_KEY` | Real results; recommended |
| `ollama` | [Ollama](https://ollama.com) running locally + `ollama pull qwen2.5:14b` and `qwen2.5:7b` | Fully offline; needs 16 GB+ RAM |

Check current Gemini model codes at https://ai.google.dev/gemini-api/docs/models
and set `GEMINI_STRONG_MODEL` / `GEMINI_FAST_MODEL`. The strong model runs the
Analyzer and Reviewer; the fast model runs the specialists.

## Project layout

```
advisor/
  agent.py              ADK entry point (root_agent)
  orchestrator.py       Coordinator: analyze -> select -> parallel specialists -> review/rework -> report
  selector.py           Rule table: domain -> agents (explainable, deterministic)
  scoring.py            Weights per project type + approval rules
  catalogue.py          Approved-technology check (hallucination guard)
  data/catalogue.json   The approved technology list - edit freely
  agents/
    analyzer.py         Requirement Analyzer / Classifier
    specialists.py      8 specialists from one template
    reviewer.py         Reviewer: findings, severity, scores
  prompts.py            All prompt text
  schemas.py            Pydantic output schemas for every agent
  models.py             gemini | ollama | mock switch
  mock_llm.py           Canned responses for offline testing
  report.py             8-part recommendation package (Markdown)
  storage.py            SQLite run log
  intake.py             .txt / .md / .pdf / .docx reader
scenarios/              Demo inputs (1-4 = one per requirement type, 5 = vague)
scripts/run.py          CLI runner
scripts/list_runs.py    Show logged runs
tests/                  Selector, scoring, catalogue, end-to-end (mock)
```

## How it maps to the requirements

| Requirement | Where |
| --- | --- |
| FR-1 Intake, clarifying questions | `agents/analyzer.py`, `intake.py`, orchestrator step 1 |
| FR-2 Classification, explainable plan | `schemas.AnalyzerOutput`, `selector.py` |
| FR-3 Dynamic, parallel orchestration | `orchestrator._run_parallel` |
| FR-4 Design with rationale + alternatives | `schemas.SpecialistOutput` |
| FR-5 Security fitted to solution type | `prompts.SPECIALIST_FOCUS["security"]` |
| FR-6 Only relevant analysis | `selector.py` (cloud agent gated on `cloud_relevant`) |
| FR-7 Review, severity, rework cap, escalate | `agents/reviewer.py`, orchestrator step 4 |
| Approval criteria + quality score | `scoring.py` |
| NFR-2 / NFR-9 Catalogue + hallucination guard | `catalogue.py`, `data/catalogue.json` |
| NFR-5 Auditability | `storage.py` (`outputs/runs.sqlite`) |
| Final recommendation package | `report.py` (`outputs/recommendation_<run>.md`) |

## Common tasks

- **Add a specialist:** add its focus text in `prompts.SPECIALIST_FOCUS`, its name in
  `selector.SPECIALISTS`, and map it to domains in `selector.DOMAIN_RULES`.
- **Change thresholds or rework rounds:** edit `.env` (`ADVISOR_*`).
- **Change scoring weights:** `scoring.WEIGHTS`.
- **Use a file as input:** `python scripts/run.py --file requirement.pdf`.

## Notes

- In `adk web`, the left-hand event panel shows each agent's raw JSON; the final
  chat message is the full recommendation.
- With the Ollama option, uploads in the web UI are not read by the model; use
  the CLI `--file` option, which extracts text first.
- Move to GCP later: set `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, `GOOGLE_CLOUD_PROJECT`
  and `GOOGLE_CLOUD_LOCATION`, then deploy the Dockerfile to Cloud Run.
