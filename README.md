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
pytest                               # unit + end-to-end tests (mock model)
```

## Web app (React + TypeScript)

`web/` is a React + TypeScript app (Vite) for the advisor. You enter or upload a
requirement, watch the agents work, answer clarifying questions, read the
recommendation, and **export it to DOCX or PDF**. Past runs are listed on the right.

```bash
# terminal 1 - API (project root, venv active)
uvicorn advisor.api:app --port 8080 --reload

# terminal 2 - web app with hot reload, proxies /api to :8080
cd web && npm install && npm run dev       # http://localhost:5173
```

For a single server, run `cd web && npm run build` once. `uvicorn advisor.api:app --port 8080`
then also serves the app at http://localhost:8080. The Dockerfile does this.

Exports also work from the command line: `python scripts/export.py <run_id> [--format docx|pdf]`.

## Choose a model (one line in `.env`)

| `ADVISOR_PROVIDER` | Needs | Use it for |
| --- | --- | --- |
| `mock` | Nothing | Testing the wiring, selection logic, rework loop, reports |
| `gemini` | Free API key from [Google AI Studio](https://aistudio.google.com/apikey) in `GOOGLE_API_KEY` | Real results; recommended |
| `claude` | Anthropic API key from the [Claude Console](https://console.anthropic.com) in `ANTHROPIC_API_KEY` | Real results with Claude (Opus 5.5 by default) |
| `ollama` | [Ollama](https://ollama.com) running locally + `ollama pull qwen2.5:14b` and `qwen2.5:7b` | Fully offline; needs 16 GB+ RAM |

Check current Gemini model codes at https://ai.google.dev/gemini-api/docs/models
and set `GEMINI_STRONG_MODEL` / `GEMINI_FAST_MODEL`. The strong model runs the
Analyzer and Reviewer; the fast model runs the specialists.

With `claude`, every agent gets Claude's structured output, so replies always match
the Pydantic schemas in `schemas.py`. `CLAUDE_STRONG_MODEL` / `CLAUDE_FAST_MODEL` and
`CLAUDE_*_EFFORT` set the model and reasoning depth for each role.

## Project layout

```
advisor/
  agent.py              ADK entry point (root_agent)
  api.py                HTTP API for the web app (streams progress, exports)
  export.py             Recommendation Markdown -> DOCX / PDF
  consistency.py        Cross-agent conflict check (e.g. two different hosts)
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
  models.py             gemini | claude | ollama | mock switch
  claude_llm.py         Claude provider (ADK AnthropicLlm + structured output)
  mock_llm.py           Canned responses for offline testing
  report.py             8-part recommendation package (Markdown)
  storage.py            Run log: Postgres (ADVISOR_DATABASE_URL) or SQLite
  intake.py             .txt / .md / .pdf / .docx reader
scenarios/              Demo inputs (1-4 = one per requirement type, 5 = vague)
web/                    React + TypeScript web app (Vite)
scripts/run.py          CLI runner
scripts/export.py       Export a saved run to DOCX / PDF
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
| NFR-5 Auditability | `storage.py` (Postgres via `ADVISOR_DATABASE_URL`, else `outputs/runs.sqlite`) |
| Final recommendation package | `report.py` (`outputs/recommendation_<run>.md`) |

## Common tasks

- **Add a specialist:** add its focus text in `prompts.SPECIALIST_FOCUS`, its name in
  `selector.SPECIALISTS`, and map it to domains in `selector.DOMAIN_RULES`.
- **Change thresholds or rework rounds:** edit `.env` (`ADVISOR_*`).
- **Change scoring weights:** `scoring.WEIGHTS`.
- **Log runs to Postgres:** `createdb solution_advisor`, then set
  `ADVISOR_DATABASE_URL=postgresql://localhost:5432/solution_advisor` in `.env`. The
  `runs` table is created on first use.
- **Use a file as input:** `python scripts/run.py --file requirement.pdf`.

## Notes

- In `adk web`, the left-hand event panel shows each agent's raw JSON; the final
  chat message is the full recommendation.
- With the Ollama option, uploads in the web UI are not read by the model; use
  the CLI `--file` option, which extracts text first.
- Move to GCP later: set `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, `GOOGLE_CLOUD_PROJECT`
  and `GOOGLE_CLOUD_LOCATION`, then deploy the Dockerfile to Cloud Run. The container
  serves the web app and API on `$PORT`. `adk web .` still works for debugging agents.
- The API keeps chat sessions in memory. A restart starts new sessions, but saved
  runs and reports are kept.
