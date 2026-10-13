import type { Theme } from "../theme";
import { Icon } from "./Icon";

/** Normal / Night segmented switch in the header. */
export function ThemeToggle({ theme, onChange }: { theme: Theme; onChange: (theme: Theme) => void }) {
  return (
    <div className="theme-toggle" role="group" aria-label="Colour mode">
      <button type="button" className={theme === "light" ? "active" : ""} aria-pressed={theme === "light"}
              onClick={() => onChange("light")}>
        <Icon name="sun" size={14} /> <span className="theme-label">Normal</span>
      </button>
      <button type="button" className={theme === "dark" ? "active" : ""} aria-pressed={theme === "dark"}
              onClick={() => onChange("dark")}>
        <Icon name="moon" size={14} /> <span className="theme-label">Night</span>
      </button>
    </div>
  );
}
