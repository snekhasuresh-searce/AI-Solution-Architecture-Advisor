import { useState } from "react";
import { apiUrl, type User } from "../api";

function initials(user: User): string {
  const source = user.name || user.email;
  return source.split(/[\s@._-]+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("");
}

/** The profile photo (uploaded or Google's), or the initials when there is none or it fails to load. */
export function Avatar({ user, large = false, size }: { user: User; large?: boolean; size?: number }) {
  const [failed, setFailed] = useState<string | null>(null);
  const cls = `avatar${large ? " large" : ""}`;
  const style = size ? { width: size, height: size, fontSize: Math.round(size / 3) } : undefined;
  return user.picture && failed !== user.picture
    ? <img className={cls} style={style} src={apiUrl(user.picture)} alt="" referrerPolicy="no-referrer"
           onError={() => setFailed(user.picture)} />
    : <span className={cls} style={style} aria-hidden="true">{initials(user)}</span>;
}
