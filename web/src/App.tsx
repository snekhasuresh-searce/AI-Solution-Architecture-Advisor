import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api, ApiError, type Health, type RunSummary, type Scenario } from "./api";
import { Activity } from "./components/Activity";
import { Composer } from "./components/Composer";
import { Icon } from "./components/Icon";
import { Pipeline } from "./components/Pipeline";
import { ReportView } from "./components/ReportView";
import { RunHistory } from "./components/RunHistory";
import { initialState, reducer } from "./state";

const message = (err: unknown) => (err instanceof Error ? err.message : String(err));

export default function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [health, setHealth] = useState<Health | null>(null);
  const [apiDown, setApiDown] = useState(false);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [runsError, setRunsError] = useState<string | null>(null);
  const reportRef = useRef<HTMLDivElement>(null);

  const refreshRuns = useCallback(() => {
    api.runs()
      .then((r) => { setRuns(r); setRunsError(null); })
      .catch((err) => setRunsError(message(err)));
  }, []);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setApiDown(true));
    api.scenarios().then(setScenarios).catch(() => {});
    refreshRuns();
  }, [refreshRuns]);

  // Bring a newly produced (or newly opened) report into view.
  useEffect(() => {
    if (state.report) reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [state.report?.runId]);

  const submit = async (text: string) => {
    dispatch({ type: "submit", text });
    try {
      let sessionId = state.sessionId;
      if (!sessionId) {
        sessionId = await api.createSession();
        dispatch({ type: "session", id: sessionId });
      }
      try {
        for await (const event of api.send(sessionId, text)) dispatch({ type: "event", event });
      } catch (err) {
        if (!(err instanceof ApiError && err.status === 404)) throw err;
        // The API restarted and lost the in-memory session: continue in a fresh one.
        sessionId = await api.createSession();
        dispatch({ type: "session", id: sessionId });
        dispatch({ type: "fail", message: "The previous session expired, so this message started a new one." });
        for await (const event of api.send(sessionId, text)) dispatch({ type: "event", event });
      }
      setApiDown(false);
    } catch (err) {
      dispatch({ type: "fail", message: message(err) });
    } finally {
      dispatch({ type: "finish" });
      refreshRuns();
    }
  };

  const openRun = async (run: RunSummary) => {
    try {
      const { markdown } = await api.report(run.run_id);
      dispatch({ type: "open_report", report: { runId: run.run_id, status: run.status, markdown, live: false } });
    } catch (err) {
      dispatch({ type: "fail", message: `Could not open run ${run.run_id}: ${message(err)}` });
    }
  };

  const hasConversation = state.log.length > 0;
  const empty = !hasConversation && !state.report;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true">
            <svg viewBox="0 0 32 32" width="28" height="28"><rect width="32" height="32" rx="8" fill="currentColor" />
              <path d="M9 22l7-13 7 13M12 17h8" stroke="white" strokeWidth="2.5" fill="none"
                    strokeLinecap="round" strokeLinejoin="round" /></svg>
          </span>
          <span>Solution Architecture Advisor</span>
        </div>
        <div className="topbar-right">
          {health && (
            <span className="badges">
              <span className="badge" title="ADVISOR_PROVIDER">model: {health.provider}</span>
              <span className="badge" title="Run log storage">log: {health.database}</span>
            </span>
          )}
          <button type="button" className="btn" onClick={() => dispatch({ type: "reset" })}
                  disabled={state.busy || empty}>
            <Icon name="plus" /> New requirement
          </button>
        </div>
      </header>

      {apiDown && (
        <div className="banner" role="alert">
          <Icon name="alert" /> Cannot reach the advisor API. Start it with{" "}
          <code>uvicorn advisor.api:app --port 8080</code> from the project root, then reload.
        </div>
      )}

      <div className="layout">
        <main className="main">
          {empty && (
            <div className="intro">
              <h1>Turn a requirement into a reviewed architecture</h1>
              <p className="muted">
                An analyzer classifies your request, only the relevant specialist agents design their part in
                parallel, and a reviewer scores the result and sends weak areas back for rework. You get a
                recommendation you can export to Word or PDF.
              </p>
            </div>
          )}
          <Composer busy={state.busy} awaitingAnswer={state.awaitingAnswer} hasConversation={hasConversation}
                    scenarios={scenarios} onSubmit={submit} />
          <Pipeline state={state} />
          <Activity log={state.log} busy={state.busy} />
          <div ref={reportRef}>{state.report && <ReportView report={state.report} />}</div>
        </main>
        <RunHistory runs={runs} error={runsError} activeRunId={state.report?.runId} onOpen={openRun} />
      </div>
    </div>
  );
}
