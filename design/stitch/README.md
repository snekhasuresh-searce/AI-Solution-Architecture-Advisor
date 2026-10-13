# Stitch export

Exported from the Stitch project **Nexora AI Architecture Advisor** (`projects/3250213965799987144`) on 2026-10-12.

| File | What it is |
| --- | --- |
| `DESIGN.md` | The "Cyber Mission Control" design system: colours, type, spacing, elevation, components |
| `advisor-night-normal.html` / `.png` | Main advisor screen with Night and Normal modes (the screen the web UI follows) |
| `advisor-redesign.html` / `.jpg` | Earlier variant of the same screen (header and runs rail only) |
| `reference-current-ui.png` | Screenshot of the UI before the redesign, uploaded to Stitch as the brief |

The HTML files are Stitch's static mockups (Tailwind CDN, sample data). They are reference only; the
real UI lives in `frontend/src` and implements the design in `frontend/src/styles.css`.
Sample-only parts of the mockup (budget figures, sub-agent readiness, live log console, ⌘K search)
were not built, because the backend has no data for them.
