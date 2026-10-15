import { useEffect, useId, useRef, useState } from "react";
import { authApi, type User } from "../api";
import { Avatar } from "./Avatar";
import { useToast } from "../toast";
import { Icon } from "./Icon";
import { PasswordDialog } from "./PasswordDialog";
import { PhotoDialog } from "./PhotoDialog";

interface Props {
  user: User;
  /** Email + password sign-in is on: offer "Set password" / "Change password". */
  passwordEnabled: boolean;
  /** The account changed (photo, password): the new state from the server. */
  onUserChange: (user: User) => void;
  onSignOut: () => void;
}

/** Profile button that opens a menu with the account details and Sign out. */
export function UserMenu({ user, passwordEnabled, onUserChange, onSignOut }: Props) {
  const [open, setOpen] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [photoOpen, setPhotoOpen] = useState(false);
  const toast = useToast();
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
          <button ref={firstItem} type="button" role="menuitem" className="menu-item"
                  onClick={() => { setOpen(false); setPhotoOpen(true); }}>
            <Icon name="camera" size={16} /> {user.has_custom_picture ? "Change photo" : "Upload a photo"}
          </button>
          {passwordEnabled && (
            <button type="button" role="menuitem" className="menu-item"
                    onClick={() => { setOpen(false); setPasswordOpen(true); }}>
              <Icon name="key" size={16} /> {user.has_password ? "Change password" : "Set a password"}
            </button>
          )}
          <button
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

      {passwordOpen && (
        <PasswordDialog
          title={user.has_password ? "Change password" : "Set a password"}
          description={user.has_password
            ? "Your other signed-in browsers will be signed out."
            : "Then you can also sign in with your email and this password, not only with Google."}
          needsCurrent={user.has_password}
          submitLabel={user.has_password ? "Change password" : "Set password"}
          onSubmit={async (next, current) => {
            await authApi.changePassword(next, current);
            toast.success(user.has_password ? "Password changed" : "Password set",
                          { message: "Other signed-in browsers have been signed out." });
            authApi.me().then(onUserChange).catch(() => {});
          }}
          onClose={() => { setPasswordOpen(false); trigger.current?.focus(); }}
        />
      )}

      {photoOpen && (
        <PhotoDialog
          user={user}
          onSaved={(updated, message) => { onUserChange(updated); toast.success(message); }}
          onClose={() => { setPhotoOpen(false); trigger.current?.focus(); }}
        />
      )}
    </div>
  );
}
