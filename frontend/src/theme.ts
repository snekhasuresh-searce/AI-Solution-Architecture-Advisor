import { useEffect, useState } from "react";

// Normal (light) and Night (dark) modes. index.html applies the saved choice before the first paint;
// with no saved choice the operating system's preference decides.
export type Theme = "light" | "dark";

const THEME_KEY = "advisor.theme";

function initialTheme(): Theme {
  const current = document.documentElement.dataset.theme;
  if (current === "light" || current === "dark") return current;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#080B22" : "#F8FAFC");
  }, [theme]);
  const choose = (next: Theme) => {
    try { localStorage.setItem(THEME_KEY, next); } catch { /* private mode: keep it for this page only */ }
    setTheme(next);
  };
  return [theme, choose];
}
