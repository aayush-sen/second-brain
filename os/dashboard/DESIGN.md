---
name: Agentic OS Dashboard
description: Hermes-derived command center — one cream ink on deep teal, Mondwest display, Courier Prime readouts, flat and quietly lit.
colors:
  bg: "#041c1c"
  ink: "#ffe6cb"
  card: "color-mix(in srgb, #ffe6cb 5%, #041c1c)"
  card2: "color-mix(in srgb, #ffe6cb 8%, #041c1c)"
  wash: "color-mix(in srgb, #ffe6cb 12%, #041c1c)"
  line: "color-mix(in srgb, #ffe6cb 14%, transparent)"
  line2: "color-mix(in srgb, #ffe6cb 26%, transparent)"
  ink2: "color-mix(in srgb, #ffe6cb 78%, #041c1c)"
  ink3: "color-mix(in srgb, #ffe6cb 58%, #041c1c)"
  amber: "#ffbd38"
  green: "#4ade80"
  red: "#ff6467"
  glow: "rgba(255, 189, 56, 0.35)"
typography:
  display:
    fontFamily: "'Mondwest', Georgia, serif"
    fontSize: "34px"
    fontWeight: 400
    lineHeight: 1.15
    letterSpacing: "0.01em"
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "0"
  readout:
    fontFamily: "'Courier Prime', ui-monospace, 'SF Mono', Menlo, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "0.05em"
  label:
    fontFamily: "'Courier Prime', ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "0.09em"
  # The four styles above are anchors, not the whole ramp. Implementation
  # steps: mono readouts 10.5–13px, sans content 13–15px (row titles 15/500),
  # Mondwest display 17/21/22/27/34px. Half-pixel steps are deliberate at
  # Courier Prime's small sizes.
rounded:
  xs: "6px"
  sm: "8px"
  md: "10px"
  lg: "12px"
spacing:
  row: "13px"
  card: "12px"
  section: "44px"
  gutter: "40px"
components:
  section-header:
    fontFamily: "'Courier Prime', monospace"
    textTransform: "uppercase"
    textColor: "{colors.ink3}"
    rule: "hairline extending right from the label ({colors.line})"
  kanban-card:
    backgroundColor: "{colors.card}"
    rounded: "{rounded.sm}"
    padding: "11px 13px"
    hover: "background steps to {colors.card2}"
  record-row:
    border: "1px {colors.line} bottom hairline only"
    padding: "13px 2px"
  button-default:
    backgroundColor: "transparent"
    border: "1px solid {colors.line2}"
    textColor: "{colors.ink2}"
    rounded: "{rounded.xs}"
    font: "12px Courier Prime"
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.bg}"
    rounded: "{rounded.xs}"
  dialog:
    backgroundColor: "{colors.card}"
    border: "1px solid {colors.line2}"
    rounded: "{rounded.lg}"
    shadow: "layered contact→ambient (--sh)"
  search-field:
    style: "borderless; bottom hairline only; underline brightens to {colors.ink} on focus"
---

# Design System: Agentic OS Dashboard

## 1. Overview

**Creative North Star: "One ink, quietly lit" — the Hermes system.**

v3 (2026-07-10) rebuilt the dashboard on the design language of Nous Research's
Hermes Agent, at Aayush's direction: deep teal void, a single warm cream ink that
carries every glyph, and surfaces that are nothing but tonal mixes of that ink into
the background. Mondwest (the Hermes signature pixel-serif, bundled in `app/fonts/`)
carries display moments; Courier Prime carries data readouts, labels, and timestamps;
the system sans stack carries body prose at 15px/1.55. A warm amber glow vignettes
the top of the page and a 2px conic grain sits over everything at 5% — atmosphere,
not decoration, both static.

Structure: a Today page (masthead date, morning briefing rendered as prose, suggested
actions extracted from the briefing's proposals, activity feed; rail with outbox
approvals, questions-for-me, deadlines, Google Calendar embed) plus one tab per area
(`areas.json`: Career, Academics, Business, Research, extensible from the composer).
Records open in a centered `<dialog>` drawer; a `+` composer creates records and areas.

**Key characteristics:**
- **One ink.** `#ffe6cb` cream is the only chromatic voice; card (5%), card2 (8%),
  wash (12%), hairlines (14%/26%), secondary text (78%), tertiary (58%) are all
  `color-mix` of it into `#041c1c`. No second neutral family exists.
- **Flat, not boxed** (inherited Hermes rule). No card-in-card, no full borders on
  list content; grouping is whitespace plus a single hairline. Section headers are
  Courier caps with a rule extending right.
- **Three status hues, one meaning each** — see Named Rules.
- Elevation exists only in the top layer: dialogs and the search results panel float
  on a layered shadow with a 26% hairline; everything in-flow is flat.

## 2. Colors

### Base
- **Teal void** (`#041c1c`, `bg`): page canvas. The Hermes Teal "LENS_0" background.
- **Psyche cream** (`#ffe6cb`, `ink`): all primary text, the wordmark, primary
  buttons' fill, focus underlines. Never pure white anywhere.
- **Tonal steps** (`card` 5% → `card2` 8% → `wash` 12%): kanban cards and hover
  states; `wash` is reserved for the update-flash pulse.
- **Hairlines**: `line` (14%, in-flow separators) and `line2` (26%, interactive
  borders — buttons, dialogs, segmented controls).
- **Text hierarchy**: `ink` → `ink2` (78%, body prose, secondary emphasis) →
  `ink3` (58%, labels/meta/timestamps; ~5.4:1 on bg, AA at readout sizes).

### Status (The One Meaning Rule)
- **Amber** (`#ffbd38`): *needs Aayush* — needs-review outbox items, ready-to-send
  outreach, deadlines ≤3 days, blocked lines, P1 markers, the nav attention dot,
  stale-briefing warnings. Also the hue of the page glow.
- **Green** (`#4ade80`): *resolved or moving forward* — replied/meeting/offer/live/
  done/approved statuses, redactor PASS, the all-clear needs line.
- **Red** (`#ff6467`): *destructive or overdue* — discard buttons, overdue day
  counts, redactor FAIL. Never used for emphasis.

Never repurpose a status hue, and never signal with hue alone — every status also
appears as a Courier word.

## 3. Typography

Three families, three jobs, no overlap:

- **Mondwest** (`display`): masthead date (34px), tab-page titles (34px), drawer
  titles (22px), briefing/prose h3s (17px). Weight 400 only — Mondwest has no bold,
  and nothing else may use the display face.
- **System sans** (`body`): 15px/1.55 prose and row titles (500 for titles); the
  register is product UI, so the scale is fixed rem-free px, tight (13–15px).
- **Courier Prime** (`readout`/`label`): everything that is *data about data* —
  section headers (12px caps, .09em tracking, ink3), nav tabs, statuses, timestamps,
  day counts (700), card meta lines, buttons, toasts, the search field and its
  result paths. If it's a readout, it's Courier; if it's content, it isn't.

Prose measure caps at 72ch. `text-wrap: balance` on display headings.

## 4. Elevation & Atmosphere

- **In-flow: flat.** Tonal steps and hairlines only — no shadows, no borders around
  sections, no panels-in-panels.
- **Top layer: one shadow token** (`--sh`, contact→ambient stack) shared by dialogs,
  the search results panel, and toasts, always paired with a `line2` hairline and a
  `rgba(1,10,10,.72)` backdrop scrim for modals.
- **Atmosphere**: fixed radial amber glow at the top of the viewport (opacity .34 of
  a .35-alpha amber) and a fixed 2px repeating-conic cream grain at 5% opacity.
  Both static, both pointer-transparent. Don't add more scenery.

## 5. Components

- **Section header** (`.sec`): Courier caps label + optional count + hairline rule
  flexing right + optional quiet action (`+ add`). This is the only section chrome.
- **Record row** (`.rows .row`): title (15px/500) + 2-line clamped description
  (ink3) + right-aligned Courier meta + status word. Bottom hairline; hover tints
  the row `card`. Terminal-status records collapse into an "archive (n) — show"
  text-button group.
- **Kanban card**: `card` tint, 8px radius, 11×13px padding, title + Courier meta
  line (P1 in amber, cpt, due). Drag targets brighten the column header; a moved
  card pulses `wash` once (1.4s). No colored side-stripes — priority is a typed
  amber "P1", not a border.
- **Outbox item**: title + status word, destination and redactor lines, then
  `approve` (primary) / `discard` (danger) at needs-review; `mark sent` / `reopen`
  once approved. Discard confirms.
- **Question item**: question text, asked-date readout, inline answer input +
  button; answering rewrites the line in `os/questions.md`.
- **Tell the OS** (Today rail, top): freeform textarea + primary post button +
  Courier hint line. Posts to episodic memory and triggers the headless ingest
  that folds the update into the records it touches (⌘/Ctrl-Enter submits).
- **Drag reorder**: every list item (rows, kanban cards within a column,
  questions) is draggable within its group; the insert point is a 2px inset
  cream hairline at the target's top edge, the dragged item drops to 45%
  opacity. Order persists to `dashboard/order.json` — presentation state only.
- **Drawer** (`<dialog>`): Mondwest title, Courier meta line, segmented status
  control (current = cream fill, destructive transitions confirm), markdown-rendered
  body, log-note input. Esc, ✕, and backdrop click all close.
- **Composer**: two Courier tabs (New record / New area); collection and area
  preselect from the active tab.
- **Search**: borderless header field (`/` focuses), debounced FTS5, results in a
  floating panel — Courier path, cream section, amber `<b>` match highlights;
  record paths open the drawer.
- **Buttons**: quiet outline (default), cream-filled primary, red-outline danger,
  borderless text — all 12px Courier, 6px radius. One vocabulary everywhere.
- **Empty states teach**: they name the skill that fills the section
  (`/venture-brief`, `/cold-outreach`) or point at `+`.

## 6. Motion

150–250ms, state-conveying only: dialog entrance (180ms rise + fade), toast slide,
kanban flash, hover/focus color shifts. No entrance choreography, no scroll effects.
`prefers-reduced-motion` kills all animation and transitions wholesale.

## 7. Do's and Don'ts

### Do:
- Build any new surface from the ink-mix ladder (5/8/12%) before inventing a color.
- Put every label, readout, and button in Courier Prime; reserve Mondwest for the
  few display moments; keep body in the system sans.
- Keep amber = needs-you, green = resolved/forward, red = destructive/overdue.
- Group with whitespace and one hairline; collapse terminal records into archive
  toggles instead of showing them.
- Keep the page legible to a screen-sharing second viewer.

### Don't:
- Don't box: no card grids, no nested containers, no borders around sections.
- Don't add a fourth status hue or use a status hue decoratively.
- Don't use Mondwest below 17px or for anything interactive.
- Don't add glow/grain layers, gradients on text, or shadows to in-flow elements.
- Don't reintroduce colored left-border stripes — v2's crutch, deliberately removed.
