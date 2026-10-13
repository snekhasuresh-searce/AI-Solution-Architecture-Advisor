---
name: Cyber Mission Control
colors:
  surface: '#0e1128'
  surface-dim: '#0e1128'
  surface-bright: '#353750'
  surface-container-lowest: '#090c23'
  surface-container-low: '#171a31'
  surface-container: '#1b1e35'
  surface-container-high: '#252840'
  surface-container-highest: '#30334c'
  on-surface: '#dfe0ff'
  on-surface-variant: '#cbc3d9'
  inverse-surface: '#dfe0ff'
  inverse-on-surface: '#2c2f47'
  outline: '#948da2'
  outline-variant: '#494456'
  surface-tint: '#cebdff'
  primary: '#cebdff'
  on-primary: '#380094'
  primary-container: '#6317ee'
  on-primary-container: '#d4c4ff'
  inverse-primary: '#6b28f6'
  secondary: '#b7f2ff'
  on-secondary: '#00363e'
  secondary-container: '#00e0fd'
  on-secondary-container: '#005f6c'
  tertiary: '#e9b3ff'
  on-tertiary: '#510074'
  tertiary-container: '#8b00c4'
  on-tertiary-container: '#ecbcff'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  background: '#0e1128'
  on-background: '#dfe0ff'
  surface-variant: '#30334c'
typography:
  headline-xl: { fontFamily: Space Grotesk, fontSize: 36px, fontWeight: '700', lineHeight: 44px, letterSpacing: -0.03em }
  headline-lg: { fontFamily: Space Grotesk, fontSize: 24px, fontWeight: '600', lineHeight: 32px, letterSpacing: -0.02em }
  headline-md: { fontFamily: Space Grotesk, fontSize: 18px, fontWeight: '600', lineHeight: 26px, letterSpacing: -0.01em }
  body-lg: { fontFamily: Plus Jakarta Sans, fontSize: 16px, fontWeight: '400', lineHeight: 26px }
  body-md: { fontFamily: Plus Jakarta Sans, fontSize: 14px, fontWeight: '400', lineHeight: 22px }
  body-sm: { fontFamily: Plus Jakarta Sans, fontSize: 12px, fontWeight: '400', lineHeight: 18px }
  label-lg: { fontFamily: Space Grotesk, fontSize: 13px, fontWeight: '600', lineHeight: 18px, letterSpacing: 0.06em }
  label-md: { fontFamily: Plus Jakarta Sans, fontSize: 12px, fontWeight: '600', lineHeight: 16px, letterSpacing: 0.02em }
  telemetry-md: { fontFamily: JetBrains Mono, fontSize: 13px, fontWeight: '500', lineHeight: 18px, letterSpacing: -0.01em }
  telemetry-sm: { fontFamily: JetBrains Mono, fontSize: 11px, fontWeight: '400', lineHeight: 16px, letterSpacing: 0.01em }
rounded: { sm: 0.25rem, DEFAULT: 0.5rem, md: 0.75rem, lg: 1rem, xl: 1.5rem, full: 9999px }
spacing:
  gutter: 1.25rem
  gutter-sm: 0.75rem
  margin: 1.5rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

<!-- Exported from Stitch project "Nexora AI Architecture Advisor" (projects/3250213965799987144) on 2026-10-12. -->

## Brand & Style

An ultra-modern mission-control environment for AI systems engineering and enterprise architecture.
Cyber-refined glassmorphism with high-density technical utility: precise, luminous, authoritative.
Dense multi-agent telemetry stays legible against deep cosmic layers, while a radiant spectrum
(Hyper Magenta through Neon Cyan) marks agent status, live inference and active execution paths.

## Colors

Dark mode by default, on an abyssal `#080B22` cosmic navy base.

### Surface hierarchy & translucency
- **Canvas base**: `#080B22`.
- **Surface level 1**: `rgba(16, 20, 58, 0.72)`, 20px backdrop blur — primary panels.
- **Surface level 2**: `rgba(24, 29, 74, 0.65)`, 16px blur — nested cards, prompt dock, side rail.
- **Surface level 3**: `rgba(40, 48, 110, 0.45)` — floating pills, tooltips.
- **Specular border**: `rgba(255, 255, 255, 0.08)`, rising to `rgba(0, 225, 254, 0.35)` or `rgba(187, 51, 253, 0.40)` on hover/active.

### Radiant spectrum
- **Hyper Magenta** `#BB33FD` — synthesis, generative output.
- **Electric Violet** `#6317EE` — primary brand, focus, structural accents.
- **Electric Indigo** `#2F2AFD` — substrate flows.
- **Azure Blue** `#0091FD` — active session states, secondary buttons.
- **Neon Cyan** `#00E1FE` — telemetry readouts, active agent loops, glow highlights.

### Semantic status
- **Jade Emerald** `#10B981` — approved, healthy.
- **Amber Gold** `#F59E0B` — rework needed, escalated.
- **Rose Crimson** `#EF4444` — error, failure.

### Text
- High `#FFFFFF`, mid `rgba(255,255,255,0.75)`, muted `rgba(255,255,255,0.42)`.

### Normal (light) mode
Slate canvas `#F8FAFC` with a faint grid, white glass cards `rgba(255,255,255,0.88)`,
borders `rgba(226,232,240,0.9)`, text `#1E293B`, indigo/sky ambient glows.

## Typography

1. **Space Grotesk** — section headers, brand, agent identifiers, panel headers. Section headers are uppercase with `+0.05em`–`+0.08em` tracking.
2. **Plus Jakarta Sans** — conversation, advisor dialogue, general UI labels.
3. **JetBrains Mono** — token counts, latency, cost, model names, statuses, code. Use tabular figures.

## Layout & Spacing

- **Top utility deck**: 64px, with model selector pill, token meter, log route, theme toggle, primary action, profile.
- **Command canvas**: runs rail + primary workspace (prompt, agent stage, conversation timeline).
- 8px baseline; 4px sub-rhythm for pills.
- **Tablet (768–1279px)**: rail stacks; gutters compress to 0.75rem. **Mobile (<768px)**: single column, 1rem margins.

## Elevation & Depth

No opaque drop shadows: luminous layering, back-lit 1px borders, frosted glass.
- Z-0 substrate `#080B22` with off-canvas radial glows (violet 8–18%, cyan 4–12%).
- Z-1 panels `rgba(16,20,58,0.70)` + 20px blur + 1px `rgba(255,255,255,0.08)`.
- Z-2 interactive cards `rgba(24,29,74,0.65)`; hover border cyan with `0 8px 24px -4px rgba(0,225,254,0.12)`.
- Z-3 overlays `rgba(14,18,50,0.92)` + 32px blur, 1px `rgba(187,51,253,0.35)` border, `0 16px 48px -8px rgba(99,23,238,0.30)`.

All borders are strictly 1px.

## Shapes

- Containers/cards: 12–16px radius. Inputs: 12px. Pills/badges: full. Utility buttons: 8px; primary actions: 10px to full.

## Components

- **Primary gradient button**: `#BB33FD → #6317EE → #0091FD`, white 600 text, glow `0 0 20px rgba(187,51,253,0.45)` on hover.
- **Secondary glass button**: `rgba(255,255,255,0.05)` bg, `rgba(255,255,255,0.12)` border; cyan border on hover.
- **Ghost button**: borderless muted label, cyan on hover.
- **Prompt deck**: glass container; bottom shelf with upload trigger, supported file types, `⌘/Ctrl + Enter` legend in mono; focus ring violet → cyan.
- **Agent step cards**: numbered `01 · ANALYZE` mono label, agent name, status line; done = emerald, active = amber glow, queued = muted.
- **Telemetry pills**: `rgba(24,29,74,0.70)` bg, 1px border, JetBrains Mono 11–12px, key values in cyan.
- **Run cards**: status dot, score pill, domain tags, footer metrics in mono (duration · tokens · cost).
- **Conversation**: user bubble tinted indigo `rgba(47,42,253,0.12)`; advisor response in an open card with an "Advisor" marker.
