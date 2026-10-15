import { useState } from "react";
import { authApi, ROLES, type AuthConfig, type Role, type User } from "../api";
import { ArchpilotMark, PRODUCT_DESCRIPTOR, Wordmark } from "./Brand";
import { Icon, Spinner } from "./Icon";

const ERRORS: Record<string, string> = {
  domain: "Sign in with your company Google Workspace account.",
  inactive: "Your account has been deactivated. Ask an admin to restore it.",
  expired: "The sign-in took too long or was already used. Please try again.",
  cancelled: "Sign-in was cancelled.",
  failed: "Sign-in failed. Please try again.",
};

interface Props {
  config: AuthConfig | null;
  error: string | null;
  onSignedIn: (user: User) => void;
}

function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}

const MIN_PASSWORD = 10;

/** Email + password: sign in, or create an account that an admin then approves. */
function PasswordForm({ domain, onSignedIn }: { domain: string; onSignedIn: (user: User) => void }) {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const switchTo = (next: "signin" | "signup") => {
    setMode(next);
    setError(null);
    setNotice(null);
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    if (mode === "signup" && password !== confirm) return setError("The passwords do not match.");
    setBusy(true);
    try {
      if (mode === "signin") {
        onSignedIn(await authApi.passwordLogin(email.trim(), password));
        return;
      }
      const result = await authApi.signup(email.trim(), password, name.trim() || undefined);
      if (result.user) return onSignedIn(result.user);  // a bootstrap admin is signed in at once
      setMode("signin");
      setPassword("");
      setConfirm("");
      setNotice("Account created. An admin needs to approve it before you can sign in; you can then sign in here.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const signup = mode === "signup";
  return (
    <form className="password-login" onSubmit={submit} noValidate>
      <div className="auth-tabs" role="tablist" aria-label="Email and password">
        <button type="button" role="tab" aria-selected={!signup} className={!signup ? "active" : ""}
                onClick={() => switchTo("signin")}>Sign in</button>
        <button type="button" role="tab" aria-selected={signup} className={signup ? "active" : ""}
                onClick={() => switchTo("signup")}>Create account</button>
      </div>
      {notice && <p className="auth-notice" role="status"><Icon name="check" size={14} /> {notice}</p>}
      {signup && (
        <label>
          <span>Name <span className="muted">(optional)</span></span>
          <input value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={200} />
        </label>
      )}
      <label>
        Work email
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
               placeholder={`name@${domain}`} autoComplete={signup ? "email" : "username"} />
      </label>
      <label>
        Password
        <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
               autoComplete={signup ? "new-password" : "current-password"} minLength={signup ? MIN_PASSWORD : undefined} />
      </label>
      {signup && (
        <>
          <label>
            Confirm password
            <input type="password" required value={confirm} onChange={(e) => setConfirm(e.target.value)}
                   autoComplete="new-password" />
          </label>
          <p className="muted small field-hint">At least {MIN_PASSWORD} characters. New accounts are approved by an admin.</p>
        </>
      )}
      {error && <p className="inline-error" role="alert"><Icon name="alert" size={14} /> {error}</p>}
      <button type="submit" className="btn primary"
              disabled={busy || !email.trim() || !password || (signup && password.length < MIN_PASSWORD)}>
        {busy ? <Spinner /> : <Icon name="send" />} {signup ? "Create account" : "Sign in"}
      </button>
    </form>
  );
}

export function LoginPage({ config, error, onSignedIn }: Props) {
  const domain = config?.allowed_domains[0] ?? "your company";
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role | "">("");
  const [busy, setBusy] = useState(false);
  const [devError, setDevError] = useState<string | null>(null);

  const devSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setDevError(null);
    try {
      onSignedIn(await authApi.devLogin(email.trim(), role || undefined));
    } catch (err) {
      setDevError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const next = window.location.pathname + window.location.search.replace(/[?&]auth_error=[^&]*/, "");

  return (
    <div className="login-wrap">
      <section className="card login" aria-labelledby="login-title">
        <span className="login-logo"><ArchpilotMark size={96} /></span>
        <h1 id="login-title" className="login-wordmark"><Wordmark height={44} /></h1>
        <p className="login-descriptor">{PRODUCT_DESCRIPTOR}</p>
        <p className="muted">
          {config?.password_enabled
            ? `Sign in with your ${domain} account.`
            : `Sign in with your ${domain} Google Workspace account.`}
        </p>

        {error && <p className="inline-error" role="alert"><Icon name="alert" size={14} /> {ERRORS[error] ?? ERRORS.failed}</p>}

        {config?.mode === "google" && (
          config.google_configured ? (
            <a className="btn google" href={authApi.googleLoginUrl(next || "/")}>
              <GoogleMark /> Sign in with Google
            </a>
          ) : (
            <p className="inline-error"><Icon name="alert" size={14} /> Google sign-in is not configured on the server
              (GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET).</p>
          )
        )}

        {config?.password_enabled && (
          <>
            {config.mode === "google" && (
              <div className="auth-divider" role="separator"><span>or use email and password</span></div>
            )}
            <PasswordForm domain={domain} onSignedIn={onSignedIn} />
          </>
        )}

        {config?.mode === "dev" && (
          <form className="dev-login" onSubmit={devSignIn}>
            <p className="dev-note">
              <strong>Development sign-in.</strong> Google is bypassed (ADVISOR_AUTH_MODE=dev); never use this on a
              shared server.
            </p>
            <label>
              Email
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                     placeholder={`name@${domain}`} autoComplete="email" />
            </label>
            <label>
              <span>Role <span className="muted">(optional)</span></span>
              <select value={role} onChange={(e) => setRole(e.target.value as Role | "")}>
                <option value="">Keep current role</option>
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
            {devError && <p className="inline-error"><Icon name="alert" size={14} /> {devError}</p>}
            <button type="submit" className="btn primary" disabled={busy || !email.trim()}>
              {busy ? <Spinner /> : <Icon name="send" />} Sign in
            </button>
          </form>
        )}

        {!config && <p className="muted"><Spinner /> Loading…</p>}
      </section>
    </div>
  );
}
