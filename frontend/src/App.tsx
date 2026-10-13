import { lazy, Suspense, useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api, ApiError, authApi, type AdvisorEvent, type AuthConfig, type Health, type ModelsInfo, type ModelUsage, type RunSummary, type Scenario, type User } from "./api";
import { Activity } from "./components/Activity";
import { AdminUsers } from "./components/AdminUsers";
import { BrandLockup } from "./components/Brand";
import { Composer } from "./components/Composer";
import { Icon } from "./components/Icon";
import { ModelMenu } from "./components/ModelMenu";
import { Pipeline } from "./components/Pipeline";
import { LoginPage } from "./components/LoginPage";
import { CollapsedRail, RunHistory } from "./components/RunHistory";
import { ThemeToggle } from "./components/ThemeToggle";
import { UsageMeter } from "./components/UsageMeter";
import { UsageView } from "./components/UsageView";
import { UserMenu } from "./components/UserMenu";
import { initialState, reducer } from "./state";
import { useTheme } from "./theme";
import { useToast } from "./toast";

// The document editor (TipTap) is most of the bundle: load it when a report is first opened.
const ReportView = lazy(() => import("./components/ReportView").then((m) => ({ default: m.ReportView })));

const PROVIDER_KEY = "advisor.provider";
const RAIL_KEY = "advisor.runsRail";
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
  const [models, setModels] = useState<ModelsInfo | null>(null);
  const [provider, setProvider] = useState<string | null>(() => localStorage.getItem(PROVIDER_KEY));
  const [modelUsage, setModelUsage] = useState<ModelUsage | null>(null);
  const [live, setLive] = useState({ input: 0, output: 0 });
  const [docWide, setDocWide] = useState(false);  // document editor without the run history column
  const reportRef = useRef<HTMLDivElement>(null);
  const [theme, setTheme] = useTheme();
  const [railOpen, setRailOpen] = useState(() => {
    try { return localStorage.getItem(RAIL_KEY) !== "closed"; } catch { return true; }
  });
  const railButton = useRef<HTMLButtonElement>(null);
  const toast = useToast();

  /** Back to the sign-in page; `expired` when the server rejected the session mid-use. */
  const signedOut = useCallback((expired = false) => {
    if (expired) toast.info("Your session has ended", { message: "Sign in again to continue." });
    setUser(null);
    setView("advisor");
    dispatch({ type: "reset" });
    setRuns(null);
  }, [toast]);

  const expireSession = useCallback(() => signedOut(true), [signedOut]);

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
    api.models().then(setModels).catch(() => {});
    refreshRuns();
  }, [user, refreshRuns]);

  const toggleRail = useCallback((fromRail = false) => {
    setRailOpen((open) => {
      try { localStorage.setItem(RAIL_KEY, open ? "closed" : "open"); } catch { /* keep it for this page only */ }
      return !open;
    });
    // The collapse button disappears with the rail, so hand focus to the header toggle.
    if (fromRail) railButton.current?.focus();
  }, []);

  // ⌘B / Ctrl+B shows or hides the runs rail on the Advisor page.
  useEffect(() => {
    if (!user || view !== "advisor") return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggleRail();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [user, view, toggleRail]);

  const refreshUsage = useCallback(() => {
    api.modelUsage().then((u) => { setModelUsage(u); setLive({ input: 0, output: 0 }); }).catch(() => {});
  }, []);
  useEffect(() => { if (user) refreshUsage(); }, [user, refreshUsage]);

  // The model for the next run: the saved choice if still offered and usable, else the server default.
  const usable = models?.providers.filter((p) => p.configured) ?? [];
  const activeProvider = usable.find((p) => p.id === provider)?.id ?? usable.find((p) => p.id === models?.default)?.id
    ?? usable[0]?.id ?? models?.default ?? health?.provider ?? "";

  const chooseProvider = (id: string) => {
    if (id === activeProvider) return;
    if (state.sessionId && state.log.length > 0 &&
        !window.confirm("Switching model starts a new conversation. The current one will be cleared. Continue?")) return;
    localStorage.setItem(PROVIDER_KEY, id);
    setProvider(id);
    dispatch({ type: "reset" }); // a conversation belongs to one model
  };

  // Bring a newly produced (or newly opened) report into view.
  useEffect(() => {
    if (state.report) reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [state.report?.runId]);

  const submit = async (text: string) => {
    dispatch({ type: "submit", text });
    try {
      let sessionId = state.sessionId;
      if (!sessionId) {
        sessionId = await api.createSession(activeProvider);
        dispatch({ type: "session", id: sessionId });
      }
      const handle = (event: AdvisorEvent) => {
        dispatch({ type: "event", event });
        if (event.type === "usage") setLive({ input: event.input, output: event.output });
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
        sessionId = await api.createSession(activeProvider);
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
      refreshUsage();
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
        <div className="topbar-left">
          <BrandLockup />
          {view === "advisor" && (
            <button ref={railButton} type="button" className={`btn rail-toggle${railOpen ? " active" : ""}`}
                    onClick={() => toggleRail()} aria-pressed={railOpen} aria-controls="runs-rail"
                    title={`${railOpen ? "Hide" : "Show"} recent runs (⌘/Ctrl + B)`}>
              <Icon name="sidebar" /> <span className="rail-label">Runs</span> <kbd>⌘B</kbd>
            </button>
          )}
        </div>
        <div className="topbar-right">
          {health && (
            <span className="badges">
              {models && usable.length > 0 ? (
                <ModelMenu providers={models.providers} selected={activeProvider} disabled={state.busy}
                           onSelect={chooseProvider} />
              ) : (
                <span className="badge" title="ADVISOR_PROVIDER">model: <b>{health.provider}</b></span>
              )}
              <UsageMeter provider={activeProvider} usage={modelUsage?.providers[activeProvider]} live={live} />
              <span className="badge" title="Run log storage">log: <b>{health.database}</b></span>
            </span>
          )}
          <ThemeToggle theme={theme} onChange={setTheme} />
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
            <button type="button" className="btn primary" onClick={() => dispatch({ type: "reset" })}
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
      <div className={`layout${railOpen ? "" : " rail-closed"}${docWide && state.report ? " doc-wide" : ""}`}>
        {!(docWide && state.report) && (
          <div className="rail-slot">
            {railOpen ? (
              <RunHistory runs={runs} error={runsError} activeRunId={state.report?.runId} onOpen={openRun}
                          onCollapse={() => toggleRail(true)}
                          currentEmail={user.role === "consultant" ? undefined : user.email} />
            ) : (
              <CollapsedRail runs={runs} onExpand={() => toggleRail(true)} />
            )}
          </div>
        )}
        <main className="main">
          {empty && (
            <div className="intro">
              <span className="eyebrow mono">Multi-agent solution architecture</span>
              <h1>Turn a requirement into a reviewed architecture</h1>
              <p className="muted">
                An analyzer classifies your request, only the relevant specialist agents design their part in
                parallel, and a reviewer scores the result and sends weak areas back for rework. You get a
                recommendation you can export to Word or PDF.
              </p>
            </div>
          )}
          <div className="no-print contents">
            <Pipeline state={state} />
            <Activity log={state.log} busy={state.busy} />
            <Composer busy={state.busy} awaitingAnswer={state.awaitingAnswer} hasConversation={hasConversation}
                      scenarios={scenarios} onSubmit={submit} />
          </div>
          <div ref={reportRef} className="report-anchor">
            {state.report && (
              <Suspense fallback={<section className="card report"><p className="doc-loading muted">Loading the editor…</p></section>}>
                <ReportView report={state.report} expanded={docWide} onToggleExpand={() => setDocWide((w) => !w)}
                            onSaved={refreshRuns} onSignedOut={expireSession} />
              </Suspense>
            )}
          </div>
        </main>
      </div>
      )}

      <footer className="statusbar mono">
        <span className={apiDown ? "down" : "up"}>
          <span className={`dot ${apiDown ? "warn" : "ok"}`} /> Advisor API: {apiDown ? "unreachable" : "online"}
        </span>
        {health && <span className="statusbar-extra">model: {activeProvider || health.provider} · log: {health.database}</span>}
        <span className="statusbar-right">Archpilot · by Searce</span>
      </footer>
    </div>
  );
}
