import { useCallback, useEffect, useState } from "react";
import { adminApi, ROLES, type ManagedUser, type Role, type User } from "../api";
import { useToast } from "../toast";
import { Icon, Spinner } from "./Icon";
import { PasswordDialog } from "./PasswordDialog";

const dateFmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

const ROLE_HELP: Record<Role, string> = {
  consultant: "Creates runs and sees their own",
  reviewer: "Sees everyone's runs",
  admin: "Everything, plus managing users",
};

export function AdminUsers({ me, passwordEnabled }: { me: User; passwordEnabled: boolean }) {
  const [users, setUsers] = useState<ManagedUser[] | null>(null);
  const [passwordFor, setPasswordFor] = useState<ManagedUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const toast = useToast();

  const load = useCallback(() => {
    adminApi.users().then(setUsers).catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, []);
  useEffect(load, [load]);

  const change = async (user: ManagedUser, update: { role?: Role; active?: boolean }) => {
    setSaving(user.id);
    try {
      const saved = await adminApi.update(user.id, update);
      setUsers((list) => list?.map((u) => (u.id === saved.id ? { ...u, ...saved } : u)) ?? null);
      const who = user.name || user.email;
      if (update.role) toast.success(`${who} is now ${saved.role}`, { message: ROLE_HELP[saved.role] + "." });
      else if (update.active && user.pending) toast.success(`${who} approved`, { message: "They can sign in now." });
      else if (update.active === false) toast.success(`${who} deactivated`, { message: "They have been signed out everywhere." });
      else toast.success(`${who} restored`, { message: "They can sign in again." });
    } catch (err) {
      toast.error(`Could not update ${user.email}`, { message: err instanceof Error ? err.message : String(err) });
    } finally {
      setSaving(null);
    }
  };

  const shown = users?.filter((u) => `${u.email} ${u.name ?? ""} ${u.role} ${u.pending ? "pending" : ""}`.toLowerCase()
    .includes(filter.trim().toLowerCase()))
    .sort((a, b) => Number(b.pending) - Number(a.pending));  // signups waiting for approval first
  const pendingCount = users?.filter((u) => u.pending).length ?? 0;

  return (
    <section className="card admin-users" aria-label="Users">
      <div className="admin-head">
        <div>
          <h1>Users</h1>
          <p className="muted small">
            People appear here after their first sign-in. {ROLES.map((r) => `${r}: ${ROLE_HELP[r].toLowerCase()}`).join(" · ")}.
          </p>
        </div>
        <input className="search" type="search" placeholder="Filter by name, email or role" value={filter}
               onChange={(e) => setFilter(e.target.value)} aria-label="Filter users" />
      </div>
      {pendingCount > 0 && (
        <p className="auth-notice pending-notice" role="status">
          <Icon name="info" size={14} /> {pendingCount} account{pendingCount > 1 ? "s are" : " is"} waiting for approval.
        </p>
      )}
      {error && <p className="inline-error" role="alert"><Icon name="alert" size={14} /> {error}</p>}
      {!users && !error && <p className="muted"><Spinner /> Loading users…</p>}
      {shown && (
        <div className="table-wrap">
          <table className="users-table">
            <thead>
              <tr><th>User</th><th>Role</th><th>Status</th><th>Last sign-in</th></tr>
            </thead>
            <tbody>
              {shown.map((u) => (
                <tr key={u.id} className={u.active ? "" : "inactive"}>
                  <td>
                    <span className="user-name">{u.name || u.email}</span>
                    <span className="muted small block">
                      {u.email}{u.id === me.id && " (you)"}
                      {u.has_password && <span className="tag mono sign-in-tag" title="Can sign in with a password">password</span>}
                    </span>
                  </td>
                  <td>
                    <select value={u.role} disabled={saving === u.id} aria-label={`Role for ${u.email}`}
                            onChange={(e) => change(u, { role: e.target.value as Role })}>
                      {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td>
                    <span className="status-cell">
                      <span className={`pill ${u.active ? "ok" : "warn"}`}>
                        {u.pending ? "Pending approval" : u.active ? "Active" : "Inactive"}
                      </span>
                      {u.id !== me.id && (
                        <button type="button" className={`btn small-btn${u.pending ? " primary" : ""}`}
                                disabled={saving === u.id} onClick={() => change(u, { active: !u.active })}>
                          {saving === u.id ? <Spinner /> : null}
                          {u.pending ? "Approve" : u.active ? "Deactivate" : "Restore"}
                        </button>
                      )}
                      {passwordEnabled && u.id !== me.id && (
                        <button type="button" className="btn ghost small-btn" onClick={() => setPasswordFor(u)}
                                title={`Set a new password for ${u.email}`}>
                          <Icon name="key" size={14} /> Set password
                        </button>
                      )}
                    </span>
                  </td>
                  <td className="muted small">{u.last_login_at ? dateFmt.format(new Date(u.last_login_at)) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {passwordFor && (
        <PasswordDialog
          title={`Set a password for ${passwordFor.name || passwordFor.email}`}
          description="They are signed out everywhere and can then sign in with their email and this password. Tell them the new password in person or over a secure channel."
          needsCurrent={false}
          submitLabel="Set password"
          onSubmit={async (password) => {
            await adminApi.setPassword(passwordFor.id, password);
            toast.success(`New password set for ${passwordFor.email}`, { message: "They have been signed out everywhere." });
            load();
          }}
          onClose={() => setPasswordFor(null)}
        />
      )}
    </section>
  );
}
