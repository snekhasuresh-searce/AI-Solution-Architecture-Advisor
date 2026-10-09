import { useCallback, useEffect, useState } from "react";
import { adminApi, ROLES, type ManagedUser, type Role, type User } from "../api";
import { useToast } from "../toast";
import { Icon, Spinner } from "./Icon";

const dateFmt = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

const ROLE_HELP: Record<Role, string> = {
  consultant: "Creates runs and sees their own",
  reviewer: "Sees everyone's runs",
  admin: "Everything, plus managing users",
};

export function AdminUsers({ me }: { me: User }) {
  const [users, setUsers] = useState<ManagedUser[] | null>(null);
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
      else if (update.active === false) toast.success(`${who} deactivated`, { message: "They have been signed out everywhere." });
      else toast.success(`${who} restored`, { message: "They can sign in again." });
    } catch (err) {
      toast.error(`Could not update ${user.email}`, { message: err instanceof Error ? err.message : String(err) });
    } finally {
      setSaving(null);
    }
  };

  const shown = users?.filter((u) => `${u.email} ${u.name ?? ""} ${u.role}`.toLowerCase()
    .includes(filter.trim().toLowerCase()));

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
                    <span className="muted small block">{u.email}{u.id === me.id && " (you)"}</span>
                  </td>
                  <td>
                    <select value={u.role} disabled={saving === u.id} aria-label={`Role for ${u.email}`}
                            onChange={(e) => change(u, { role: e.target.value as Role })}>
                      {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </td>
                  <td>
                    <span className="status-cell">
                      <span className={`pill ${u.active ? "ok" : "warn"}`}>{u.active ? "Active" : "Inactive"}</span>
                      {u.id !== me.id && (
                        <button type="button" className="btn small-btn" disabled={saving === u.id}
                                onClick={() => change(u, { active: !u.active })}>
                          {saving === u.id ? <Spinner /> : null}
                          {u.active ? "Deactivate" : "Restore"}
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
    </section>
  );
}
