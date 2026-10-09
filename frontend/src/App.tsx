import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api, ApiError, authApi, type AdvisorEvent, type AuthConfig, type Health, type RunSummary, type Scenario, type User } from "./api";
import { Activity } from "./components/Activity";
import { AdminUsers } from "./components/AdminUsers";
import { BrandLockup } from "./components/Brand";
import { Composer } from "./components/Composer";
import { Icon } from "./components/Icon";
import { Pipeline } from "./components/Pipeline";
import { ReportView } from "./components/ReportView";
import { LoginPage } from "./components/LoginPage";
import { RunHistory } from "./components/RunHistory";
import { UsageView } from "./components/UsageView";
import { UserMenu } from "./components/UserMenu";
import { initialState, reducer } from "./state";
import { useToast } from "./toast";

const message = (err: unknown) => (err instanceof Error ? err.message : String(err));
const isSignedOut = (err: unknown) => err instanceof ApiError && err.status === 401;

/** Reads (and removes) ?auth_error=... that the backend adds after a failed Google sign-in. */
function takeAuthError(): string | null {
  const params = new URLSearchParams(window.location.search);
  const error = params.get("auth_error");
  if (error) {
    params.delete("auth_error");
    const query = params.toString();
    window.history.replaceState(null, "", window.location.pathname + (query ? `?${query}` : ""));
  }
  return error;
}

export default function App() {
  // undefined = still checking the session, null = signed out
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [authError] = useState(takeAuthError);
  const [view, setView] = useState<"advisor" | "usage" | "users">("advisor");
  const [state, dispatch] = useReducer(reducer, initialState);
  const [health, setHealth] = useState<Health | null>(null);
  const [apiDown, setApiDown] = useState(false);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [runsError, setRunsError] = useState<string | null>(null);
  const reportRef = useRef<HTMLDivElement>(null);
  const toast = useToast();

  /** Back to the sign-in page; `expired` when the server rejected the session mid-use. */
  const signedOut = useCallback((expired = false) => {
    if (expired) toast.info("Your session has ended", { message: "Sign in again to continue." });
    setUser(null);
    setView("advisor");
    dispatch({ type: "reset" });
    setRuns(null);
  }, [toast]);

  const refreshRuns = useCallback(() => {
    api.runs()
      .then((r) => { setRuns(r); setRunsError(null); })
      .catch((err) => (isSignedOut(err) ? signedOut(true) : setRunsError(message(err))));
  }, [signedOut]);

  // Who is signed in (the session cookie is HttpOnly, so ask the server).
  useEffect(() => {
    api.health().then(setHealth).catch(() => setApiDown(true));
    authApi.config().then(setAuthConfig).catch(() => setApiDown(true));
    authApi.me().then(setUser).catch((err) => {
      if (!isSignedOut(err)) setApiDown(true);
      setUser(null);
    });
  }, []);

  useEffect(() => {
    if (!user) return;
    api.scenarios().then(setScenarios).catch(() => {});
    refreshRuns();
  }, [user, refreshRuns]);

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
      const handle = (event: AdvisorEvent) => {
        dispatch({ type: "event", event });
        if (event.type === "report") {
          if (event.status === "APPROVED") {
            toast.success("Recommendation ready", { message: "Approved by the reviewer. Export it to DOCX or PDF." });
          } else {
            toast.info("Recommendation escalated", { message: "It needs a human architect's review before use." });
          }
        } else if (event.type === "error") {
          toast.error("The run hit an error", { message: event.message });
        }
      };
      try {
        for await (const event of api.send(sessionId, text)) handle(event);
      } catch (err) {
        if (!(err instanceof ApiError && err.status === 404)) throw err;
        // The conversation is gone (e.g. deleted): continue in a fresh one.
        sessionId = await api.createSession();
        dispatch({ type: "session", id: sessionId });
        toast.info("Started a new conversation", { message: "The previous one was not found." });
        for await (const event of api.send(sessionId, text)) handle(event);
      }
      setApiDown(false);
    } catch (err) {
      if (isSignedOut(err)) return signedOut(true);
      dispatch({ type: "fail", message: message(err) });
      toast.error("The run failed", { message: message(err) });
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
      if (isSignedOut(err)) return signedOut(true);
      toast.error(`Could not open run ${run.run_id}`, { message: message(err) });
    }
  };

  /** Open a run by id (from the Usage page), reading its status from the report itself. */
  const openRunById = async (runId: string) => {
    setView("advisor");
    try {
      const { markdown } = await api.report(runId);
      const status = /\*\*Status:\*\*\s*Escalated/.test(markdown) ? "ESCALATED" : "APPROVED";
      dispatch({ type: "open_report", report: { runId, status, markdown, live: false } });
    } catch (err) {
      if (isSignedOut(err)) return signedOut(true);
      toast.error(`Could not open run ${runId}`, { message: message(err) });
    }
  };

  const signOut = async () => {
    try {
      await authApi.logout();
      toast.info("Signed out");
    } catch {
      toast.info("Signed out on this device", { message: "The server could not be reached to end the session." });
    } finally {
      signedOut();
    }
  };

  if (user === undefined && !apiDown) {
    return <div className="login-wrap"><p className="muted">Loading…</p></div>;
  }
  if (!user) {
    return (
      <>
        {apiDown && (
          <div className="banner" role="alert">
            <Icon name="alert" /> Cannot reach the advisor API. Start it with{" "}
            <code>cd backend && uvicorn advisor.api:app --port 8080</code>, then reload.
          </div>
        )}
        <LoginPage config={authConfig} error={authError} onSignedIn={setUser} />
      </>
    );
  }

  const hasConversation = state.log.length > 0;
  const empty = !hasConversation && !state.report;

  return (
    <div className="app">
      <header className="topbar">
        <BrandLockup />
        <div className="topbar-right">
          {health && (
            <span className="badges">
              <span className="badge" title="ADVISOR_PROVIDER">model: {health.provider}</span>
              <span className="badge" title="Run log storage">log: {health.database}</span>
            </span>
          )}
          {user.role !== "consultant" && (
            <nav className="tabs" aria-label="Sections">
              <button type="button" className={`tab ${view === "advisor" ? "active" : ""}`}
                      onClick={() => setView("advisor")}>Advisor</button>
              <button type="button" className={`tab ${view === "usage" ? "active" : ""}`}
                      onClick={() => setView("usage")}>Usage</button>
              {user.role === "admin" && (
                <button type="button" className={`tab ${view === "users" ? "active" : ""}`}
                        onClick={() => setView("users")}>Users</button>
              )}
            </nav>
          )}
          {view === "advisor" && (
            <button type="button" className="btn" onClick={() => dispatch({ type: "reset" })}
                    disabled={state.busy || empty}>
              <Icon name="plus" /> New requirement
            </button>
          )}
          <UserMenu user={user} onSignOut={signOut} />
        </div>
      </header>

      {apiDown && (
        <div className="banner" role="alert">
          <Icon name="alert" /> Cannot reach the advisor API. Start it with{" "}
          <code>cd backend && uvicorn advisor.api:app --port 8080</code>, then reload.
        </div>
      )}

      {view === "users" && user.role === "admin" ? (
        <div className="layout single"><AdminUsers me={user} /></div>
      ) : view === "usage" && user.role !== "consultant" ? (
        <div className="layout single"><UsageView onOpenRun={openRunById} /></div>
      ) : (
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
        <RunHistory runs={runs} error={runsError} activeRunId={state.report?.runId} onOpen={openRun}
                    currentEmail={user.role === "consultant" ? undefined : user.email} />
      </div>
      )}
    </div>
  );
}
