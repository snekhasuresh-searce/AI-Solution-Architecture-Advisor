import type { User } from "../api";

interface Props {
  user: User;
  onSignOut: () => void;
}

function initials(user: User): string {
  const source = user.name || user.email;
  return source.split(/[\s@._-]+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("");
}

export function UserMenu({ user, onSignOut }: Props) {
  return (
    <div className="user-menu">
      {user.picture ? (
        <img className="avatar" src={user.picture} alt="" referrerPolicy="no-referrer" />
      ) : (
        <span className="avatar" aria-hidden="true">{initials(user)}</span>
      )}
      <span className="user-text">
        <span className="user-name" title={user.email}>{user.name || user.email}</span>
        <span className={`role-pill ${user.role}`}>{user.role}</span>
      </span>
      <button type="button" className="btn ghost" onClick={onSignOut}>Sign out</button>
    </div>
  );
}
