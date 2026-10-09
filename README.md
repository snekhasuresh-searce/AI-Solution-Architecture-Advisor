# AI Solution Architecture Advisor — POC boilerplate

A multi-agent advisor that turns a plain-language requirement into a reviewed
solution recommendation. Built with Google's Agent Development Kit (ADK) and
runs entirely on your laptop: **no GCP project needed**.

```
requirement ─► Analyzer ─► Agent Selector ─► Specialists (parallel) ─► Reviewer ─┬─► Recommendation (.md + SQLite log)
                  │          (rule table)          ▲                            │
                  └─ clarifying questions          └──── rework (High/Critical) ┘  max 3 rounds, then escalate
```

## Repository layout

Two independent projects:

```
backend/     Python API + agents (FastAPI, Google ADK) - its own venv, .env, Dockerfile
frontend/    React + TypeScript web app (Vite)        - its own package.json, Dockerfile
docker-compose.yml   runs both together
```

The frontend talks to the backend only over HTTP (`/api/...`), so each can be
developed, tested and deployed on its own.

## Backend quick start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # starts in mock mode

uvicorn advisor.api:app --port 8080 --reload   # API at http://localhost:8080/api/health
python scripts/run.py --all          # 4 demo scenarios from the command line
pytest                               # unit + end-to-end tests (mock model)
adk web .                            # ADK's debug chat UI -> pick "advisor"
```

Exports also work from the command line: `python scripts/export.py <run_id> [--format docx|pdf]`.

## Frontend quick start

You enter or upload a requirement, watch the agents work, answer clarifying
questions, read the recommendation and **export it to DOCX or PDF**. Past runs are
listed on the right.

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173, forwards /api to :8080
```

| Setting (`frontend/.env.local`) | Default | Purpose |
| --- | --- | --- |
| `API_PROXY_TARGET` | `http://localhost:8080` | Dev server only: where `/api` is forwarded |
| `VITE_API_URL` | empty (same origin) | Build time: backend URL when it is on another host |

If the frontend calls the backend on another origin, add that origin to
`ADVISOR_CORS_ORIGINS` in `backend/.env`.

## Sign-in and roles

Everyone signs in with their **Google Workspace** account. Only verified accounts
of `ADVISOR_ALLOWED_DOMAINS` (default `searce.com`) get in.

| Role | Can |
| --- | --- |
| consultant (default) | Run the advisor; see and export their own runs |
| reviewer | Also see and export everyone's runs |
| admin | All of the above, plus the **Users** page (change roles, deactivate people) |

Accounts listed in `ADVISOR_ADMIN_EMAILS` are always admin; use this for the first
admin. Login sessions, users and the agents' conversations are stored in the
database (Postgres when `ADVISOR_DATABASE_URL` is set), so they survive restarts.

**Google setup (once):** Google Cloud console → APIs & Services → Credentials →
*Create OAuth client ID* → type *Web application*. Under *Authorized redirect URIs*,
add `http://localhost:5173/api/auth/callback` (plus your production URL). If the
consent screen asks, choose *Internal* so only your Workspace can use it. Then set
`ADVISOR_AUTH_MODE=google`, `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`
in `backend/.env`.

**Local development without Google:** `ADVISOR_AUTH_MODE=dev` shows an email form
instead (any allowed-domain address, optional role). Never enable it on a shared server.

## Traces, token use and cost

Every run is traced: each turn, agent and model call is stored (table `trace_spans`)
with its duration, tokens (input, cached, output, thinking) and estimated cost.

- **Run details** (on every report): totals, plain-language reasons for the time and
  cost (slowest step, most expensive step, rework rounds, clarifying turns, long
  calls), a per-turn timeline and a per-agent table.
- **Run history** shows time, tokens and cost per run.
- **Usage** (reviewers and admins): totals for 7/30/90 days by person, model and
  agent, plus the slowest and most expensive runs.
- **Logs:** one line per model call, agent and run, tagged with `run_id`, `trace_id`
  and `agent`. `ADVISOR_LOG_FORMAT=json` writes JSON for Cloud Logging.

Costs come from `backend/advisor/data/pricing.json` (USD per 1M tokens, with dated
price periods; thinking tokens bill as output). Models missing from it show
"price n/a". Update it when prices change. `ADVISOR_MOCK_DELAY_MS=1500` makes the mock
model slow enough to demo the timeline offline.

## Run both with Docker

```bash
docker compose up --build            # frontend http://localhost:8000, API :8080
```

The frontend image is nginx serving the built app and forwarding `/api` to the
backend (`BACKEND_URL`). Each folder's `Dockerfile` also builds on its own.

## Choose a model (one line in `backend/.env`)

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

## Backend layout

```
backend/advisor/
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
backend/scenarios/      Demo inputs (1-4 = one per requirement type, 5 = vague)
backend/scripts/run.py  CLI runner
backend/scripts/export.py     Export a saved run to DOCX / PDF
backend/scripts/list_runs.py  Show logged runs
backend/tests/          Selector, scoring, catalogue, API, end-to-end (mock)
backend/outputs/        Generated reports, diagrams and the SQLite log (not committed)

frontend/src/
  api.ts                Typed API client (streams agent progress)
  state.ts              Run state: agent progress, log, report
  components/           Composer, Pipeline, Activity, ReportView, RunHistory
```

## How it maps to the requirements

Paths below are inside `backend/advisor/`.

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
- **Change thresholds or rework rounds:** edit `backend/.env` (`ADVISOR_*`).
- **Change scoring weights:** `scoring.WEIGHTS`.
- **Log runs to Postgres:** `createdb solution_advisor`, then set
  `ADVISOR_DATABASE_URL=postgresql://localhost:5432/solution_advisor` in `backend/.env`. The
  `runs` table is created on first use.
- **Use a file as input:** `python scripts/run.py --file requirement.pdf`.

## Notes

- In `adk web`, the left-hand event panel shows each agent's raw JSON; the final
  chat message is the full recommendation.
- With the Ollama option, uploads in the web UI are not read by the model; use
  the CLI `--file` option, which extracts text first.
- Move to GCP later: set `GOOGLE_GENAI_USE_VERTEXAI=TRUE`, `GOOGLE_CLOUD_PROJECT`
  and `GOOGLE_CLOUD_LOCATION`, then deploy `backend/` and `frontend/` as two Cloud Run
  services (set the frontend's `BACKEND_URL` to the backend's URL).
- The API keeps chat sessions in memory. A restart starts new sessions, but saved
  runs and reports are kept.
