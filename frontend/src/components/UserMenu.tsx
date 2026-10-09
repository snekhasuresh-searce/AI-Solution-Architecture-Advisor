import { useEffect, useId, useRef, useState } from "react";
import type { User } from "../api";
import { Icon } from "./Icon";

interface Props {
  user: User;
  onSignOut: () => void;
}

function initials(user: User): string {
  const source = user.name || user.email;
  return source.split(/[\s@._-]+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("");
}

function Avatar({ user, large = false }: { user: User; large?: boolean }) {
  const cls = `avatar${large ? " large" : ""}`;
  return user.picture
    ? <img className={cls} src={user.picture} alt="" referrerPolicy="no-referrer" />
    : <span className={cls} aria-hidden="true">{initials(user)}</span>;
}

/** Profile button that opens a menu with the account details and Sign out. */
export function UserMenu({ user, onSignOut }: Props) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const firstItem = useRef<HTMLButtonElement>(null);
  const menuId = useId();

  // Close on a click outside or Escape; Escape returns focus to the profile button.
  useEffect(() => {
    if (!open) return;
    firstItem.current?.focus();
    const onPointer = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const name = user.name || user.email;
  return (
    <div className="user-menu" ref={root}>
      <button
        ref={trigger}
        type="button"
        className={`profile-button ${open ? "open" : ""}`}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={`Account: ${name}`}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setOpen(true);
          }
        }}
      >
        <Avatar user={user} />
        <span className="user-text">
          <span className="user-name">{name}</span>
          <span className={`role-pill ${user.role}`}>{user.role}</span>
        </span>
        <span className="chevron" aria-hidden="true"><Icon name="chevron" size={14} /></span>
      </button>

      {open && (
        <div id={menuId} className="menu" role="menu" aria-label="Account">
          <div className="menu-profile" role="presentation">
            <Avatar user={user} large />
            <div className="menu-profile-text">
              <span className="menu-name">{name}</span>
              <span className="menu-email">{user.email}</span>
              <span className={`role-pill ${user.role}`}>{user.role}</span>
            </div>
          </div>
          <div className="menu-separator" role="separator" />
          <button
            ref={firstItem}
            type="button"
            role="menuitem"
            className="menu-item"
            onClick={() => {
              setOpen(false);
              onSignOut();
            }}
          >
            <Icon name="logout" size={16} /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}
