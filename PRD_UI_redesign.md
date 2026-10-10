# PRD — VoltPredict UI Redesign (Presentation Layer Only)

**Audience: the AI coding agent (Antigravity).** Read this whole file before touching any code. This is a **visual and structural restyle of the React frontend only**. Nothing the application *does* may change.

Companion files already in the repo: `README.md`, `PROJECT_KNOWLEDGE_BASE.md`, `NOTES.md`, the checkpoint PRDs and reports. Do not edit them except where Phase UI-4 says so.

---

## 0. Prime directive: zero functional change

The product works. Judges will evaluate the same behavior. The redesign must make it look sophisticated, calm and tidy, and must leave every function, number, endpoint and pipeline exactly as it is.

### 0.1 Frozen (never modify, move, rename, reformat or delete)

- Everything outside `frontend/`: `backend/`, `src/`, `api.py`, `main.py`, `tests/`, `config/`, `data/`, `models/`, `artifacts/`, `outputs/`, `requirements.txt`, `render.yaml`, `*.bat`, all existing `*.md` reports and PRDs.
- Inside `frontend/`: `src/api/client.js`, `src/config.js`, `vite.config.js`, `vercel.json`, `nginx.conf`, `Dockerfile`, `package.json` dependencies (do not add or remove packages unless section 6.4 explicitly allows it).
- In every component: state (`useState`, `useEffect`, `useMemo`, `useRef`), props and their names, event handlers, `fetch` calls, endpoint URLs and query parameters, polling intervals, request bodies, data transformations, sorting/filtering logic, threshold logic (for example voltage band 0.95–1.05, loading 70/100 breakpoints), conditional rendering that gates data or controls, and every `key`.
- Tab ids (`showcase`, `surrogate`, `time_plan`, `mpc`, `engine`, `forecast`, `grid`, `all`), the default tab (`showcase`), and the conditions that decide which panels render for each tab.
- Every number, unit, and label that carries information (for example `p.u.`, `MW`, `MVar`, `%`).

### 0.2 Allowed

- CSS, class names, design tokens, inline-style removal, layout wrappers, spacing, typography, icon choice, colors, shadows, borders, animations (reduction only), and chart styling props (stroke, fill, grid, tick, tooltip, legend styling).
- Moving purely presentational markup, regrouping elements inside a panel, and splitting a large JSX file into smaller presentational sub-components **only if** props, state and handlers pass through unchanged.
- Adding new presentational files: theme provider, theme toggle, app shell/navigation, UI primitives, stylesheets.
- Correcting **visibly stale or inaccurate copy** (for example the header chip that says "Checkpoints 1–3 Complete" while the app covers checkpoints 1–8). Every copy change must be listed in the report.

### 0.3 If in doubt

Do not change it. Record the doubt in the checkpoint report and wait for the user.

---

## 1. Audit of the current UI (what makes it feel cluttered)

Observed in the provided screenshots and the code at commit `bfb4ec8`:

1. **Stack:** React 19, Vite, Recharts, lucide-react, FastAPI backend. Dark theme only. Roughly 960 inline `style={{…}}` blocks across 15 files, about 600 hard-coded hex colors and about 300 `rgba()` literals. There is almost no shared styling, so the same element looks slightly different everywhere.
2. **Navigation:** eight flat tab buttons with emoji, long labels and checkpoint numbers (for example "⚡ Power-Flow Surrogate & Screening (CP6 & CP7)"), each in its own accent color. It wraps to two rows and reads as developer scaffolding, not product navigation.
3. **Header:** brand, a stale "Checkpoints 1–3 Complete" chip, a long tagline, two meta items and a status badge compete for attention in one box.
4. **Too many colors:** cyan, blue, emerald, amber, rose, purple, pink and violet are all used as decoration, so color stops meaning anything. Series colors differ between charts (solar is orange in one chart, yellow in another; load is blue in one, purple in another).
5. **Effects:** glassmorphism (blur), neon glows, gradient buttons, pulsing rings and animated dashed lines everywhere. Nested cards (card inside card inside card) in the Action Engine, Time Plan and Surrogate panels.
6. **Hierarchy:** panels start with a long colored banner plus description, then buttons, then banners, then tables. There is no consistent page header, KPI row, content grid pattern.
7. **Topology map:** straight edges cross across the whole canvas (the backend's fallback layout places buses in three horizontal rows and lines jump between them). It looks tangled even when the grid is healthy.
8. **Tables and charts:** inconsistent header styles, mixed alignment of numbers, heavy gradient area fills, dense axis labels, oversized point markers.
9. **Emoji in UI text** (🏆 ⚡ 🚨 🧠 🔄 ⏱️ …) instead of the icon library already installed.
10. **Always-visible long scroll lists** nested inside long pages (violation log), producing scroll-within-scroll.

## 2. Design direction

**Calm, focused, restrained.** The reference app (Pocketwise) is positioned as "calm, private, in focus". Apply that mindset: deep navy base, generous whitespace, one primary accent, color used only to carry meaning (status and data series), thin borders instead of glow, sentence-case copy, real hierarchy.

> **Reference limitation:** the reference site is a client-rendered app and its visual details could not be extracted automatically. The only recovered traits are the dark navy theme color (`#080f20`) and the calm/focused positioning. The tokens below are therefore a specified interpretation. **If the user supplies screenshots of the reference, they override token values where they conflict; the structural rules in this document still apply.**

Principles:
1. **One accent, semantic colors only for meaning.** Green/amber/red mean safe/warning/violation and nothing else.
2. **Hierarchy before decoration.** Every view: page header, KPI row, primary content, secondary details.
3. **Two levels of surface only:** page and card. No cards inside cards; use dividers and spacing inside a card.
4. **Numbers are the product.** Tabular figures, right-aligned, consistent precision exactly as currently displayed.
5. **Both themes are first-class.** Every component must be checked in light and dark.

---

## 3. Design system

### 3.1 Tokens (create `src/styles/tokens.css`)

Define all colors as CSS variables on `:root` for dark and override under `:root[data-theme="light"]`. Default theme follows `prefers-color-scheme`, user choice overrides and persists. The agent may adjust hex values **only** to satisfy the contrast rules in 3.7.

| Token | Dark | Light |
|---|---|---|
| `--bg` | `#080f20` | `#f5f7fb` |
| `--surface` | `#0d1630` | `#ffffff` |
| `--surface-raised` | `#121d3b` | `#f1f4fa` |
| `--surface-hover` | `#17244a` | `#e9eef8` |
| `--border` | `rgba(148,163,200,0.16)` | `#dde3ee` |
| `--border-strong` | `rgba(148,163,200,0.28)` | `#c5cee0` |
| `--text` | `#e8edf8` | `#0f172a` |
| `--text-muted` | `#9aa8c7` | `#475569` |
| `--text-faint` | `#7b8ab0` | `#64748b` |
| `--accent` (links, active states, focus) | `#5b9bff` | `#1d4ed8` |
| `--accent-solid` (primary button background; text on it is white) | `#2f6fe4` | `#2f6fe4` |
| `--accent-soft` | `rgba(91,155,255,0.14)` | `rgba(29,78,216,0.10)` |
| `--ok` / `--ok-soft` | `#34d399` / 14% alpha | `#047857` / 10% alpha |
| `--warn` / `--warn-soft` | `#fbbf24` / 14% alpha | `#b45309` / 10% alpha |
| `--danger` / `--danger-soft` | `#f87171` / 14% alpha | `#b91c1c` / 10% alpha |

Chart series tokens (one fixed meaning per color, identical in every chart in the app):

| Token | Meaning | Dark | Light |
|---|---|---|---|
| `--c-solar` | solar generation, PV | `#fbbf24` | `#d97706` |
| `--c-load` | demand / load | `#60a5fa` | `#2563eb` |
| `--c-forecast` | model forecast, surrogate prediction | `#2dd4bf` | `#0d9488` |
| `--c-baseline` | naive/baseline/unscreened (always dashed) | `#94a3b8` | `#64748b` |
| `--c-battery` | battery dispatch | `#a78bfa` | `#7c3aed` |
| `--c-curtail` | curtailment | `#fb7185` | `#e11d48` |
| `--c-soc` | state of charge | `#38bdf8` | `#0284c7` |
| `--c-grid` / `--c-axis` | gridlines (very faint) / tick labels | `--border` / `--text-faint` | same |

Rule for paired series: **forecast vs observed = same hue, forecast dashed, observed solid.** Never introduce a new hue for a series that already has a token.

Also define tokens for radius (`--r-sm 8px`, `--r-md 12px`, `--r-pill 999px`), spacing (`--s-1 4px … --s-8 48px` on a 4px scale), shadows (dark: none, borders only; light: `0 1px 2px rgba(15,23,42,.06), 0 4px 12px rgba(15,23,42,.04)`), `--font-sans` (Inter, already used), `--font-mono` (JetBrains Mono, already used), and `color-scheme` per theme.

### 3.2 Typography

- Scale: 12 / 13 / 14 (body) / 16 / 20 / 28 px. Weights 400, 500, 600 only. Line height 1.5 (1.25 for headings).
- Sentence case everywhere. Remove decorative ALL-CAPS micro-labels; keep uppercase only for tiny table column headers if needed (12px, letter-spacing 0.04em).
- All numeric values: `font-variant-numeric: tabular-nums`. Use the mono font only for IDs and code-like values where alignment matters, not for every number.
- Page title 28px/600, panel title 20px/600, card title 16px/600, body 14px, helper text 13px muted.

### 3.3 Layout and shell

- **App shell:** left sidebar (248px) on screens ≥ 1024px; top bar with a menu button and slide-over drawer below that. Sticky slim top bar (56px) holding the current view title, context chips and controls.
- **Sidebar:** brand mark and "VoltPredict" at top; navigation grouped into sections; backend status and theme toggle at the bottom or in the top bar (pick one place and keep it consistent).
- **Content:** centered, max width 1200px, horizontal padding 24px (16px on mobile), vertical rhythm 24px between sections.
- **Grids:** KPI rows use `repeat(auto-fit, minmax(200px, 1fr))` with 16px gap. Two-column content grids collapse to one column below 1024px.
- **Breakpoints:** 640, 1024, 1280. Verify at 375, 768, 1280 and 1920 widths.

### 3.4 Navigation (presentation only; state and ids unchanged)

Keep `activeTab` state in `App.jsx` and every rendering condition exactly as is. Replace the flat tab strip with a grouped sidebar using the **same eight ids**. Visible labels become short and jargon-free; keep the checkpoint reference as a `title` tooltip only.

| Group | id | Visible label | Tooltip |
|---|---|---|---|
| Overview | `showcase` | Showcase | Showcase and evidence (Checkpoint 8) |
| Overview | `all` | Full overview | Full digital twin view |
| Grid | `grid` | Grid and power flow | Checkpoint 1 |
| Grid | `forecast` | Forecaster | Checkpoint 2 |
| Control | `engine` | Action engine | Checkpoint 3 |
| Control | `time_plan` | Time plan | Checkpoint 5 |
| Control | `mpc` | Predictive MPC | Update 1 |
| Learning | `surrogate` | Surrogate and screening | Checkpoints 6 and 7 |

Active item: `--accent-soft` background, `--accent` text, a 2px accent bar on the left, `aria-current="page"`. Icons: lucide-react, one per item, 18px, no emoji. The default view on load remains `showcase`.

### 3.5 Primitives (create `src/styles/components.css` and, only if they simplify, small presentational components in `src/components/ui/`)

Define once, reuse everywhere. Replace inline styles with these.

- **Card:** `--surface`, 1px `--border`, `--r-md`, padding 20px (16px mobile). No blur, no glow. Hover changes border color only if the card is interactive.
- **Page header:** title, one-line description (13–14px muted), primary action on the right. Replaces the large colored banners at the top of panels.
- **KPI tile:** label (13px muted), value (28px/600 tabular), optional one-line helper with a small tone dot. Status tone shown by a 3px left border or a small dot, never a full colored background.
- **Button:** `primary` (solid `--accent-solid`, white text), `secondary` (1px `--border-strong`, transparent), `ghost`, and `danger-outline` (for "Trigger constraint scenario" only). Height 36px, radius 8px, no gradients, no glow. One primary button per view. Disabled and loading states required. Visible `:focus-visible` ring (2px `--accent`, 2px offset).
- **Badge/pill:** 12px, `*-soft` background with matching text color, 999px radius. Used for statuses (Normal, Overvoltage, Partial, Resolved…).
- **Segmented control / tabs (in-panel):** replaces the many ad-hoc toggle button groups. `aria-pressed` or `role="tablist"` as appropriate.
- **Field:** label above input, 36px height, `--surface-raised` background, 1px border, `--accent` focus ring. Native date input and range sliders must be themed (see 3.6).
- **Alert:** left 3px tone border, `*-soft` background, icon, title and body. Used for "Grid under stress", residual violations, errors and the physical-verification note. Banners keep their current content.
- **Table:** sticky header (`--surface-raised`), 13px muted column titles, 14px cells, row hover `--surface-hover`, 1px row dividers (no zebra), numeric columns right-aligned and tabular, wrapped in a horizontally scrollable container, long lists with a fixed max-height and the same scrollbar style.
- **Empty and loading states:** consistent skeleton or muted text block, same height as the content to avoid layout jumps.
- **Scrollbars:** thin, tokenized for both themes.

### 3.6 Theme system

- Add `src/theme/ThemeProvider.jsx` (or a small hook) with modes `system | light | dark`. Persist in `localStorage` under `voltpredict-theme` inside `try/catch`. Apply by setting `data-theme` on `document.documentElement` and `color-scheme` accordingly. Listen to `prefers-color-scheme` changes while in `system` mode.
- Add a **tiny inline script in `index.html`** that sets `data-theme` before first paint to prevent a flash of the wrong theme. Update `<meta name="theme-color">` per theme.
- Add a `ThemeToggle` (sun/moon/monitor icons from lucide-react, accessible label, keyboard operable) in the shell.
- Replace `input[type="date"] { color-scheme: dark; }` with a theme-aware rule; verify the calendar popup and the native `<select>` dropdowns in both themes.
- **Recharts and SVG:** use `var(--token)` strings for `stroke`, `fill` and `stopColor`. Where code currently builds colors by string concatenation (for example `` `${color}22` `` in the tab buttons) replace with `color-mix(in srgb, var(--token) 14%, transparent)` or the `*-soft` tokens. Where JS genuinely needs a literal color, read it once via `getComputedStyle(document.documentElement)` in a small `useThemeColors()` hook that re-reads on theme change.
- Charts, tooltips, legends, tables, inputs, the date picker, the chat widget and every alert must be verified in both themes.

### 3.7 Contrast and accessibility (required)

- Text contrast ≥ 4.5:1 (body) and ≥ 3:1 (large text, icons, chart lines against the card), in both themes.
- Status is never conveyed by color alone: keep or add the text label or icon next to every colored status.
- Focus styles on every interactive element; logical tab order; `aria-label` on icon-only buttons; `aria-current` on active nav; the chat widget remains keyboard operable.
- Respect `prefers-reduced-motion`: disable the pulse and dash-flow animations under that setting.
- Minimum touch target 40px on mobile.

### 3.8 Motion and effects

Remove: backdrop blur, glow shadows, gradient buttons and gradient brand tile, pulsing rings. Keep only: 150ms color/border transitions, the status-dot indicator, loading spinners/skeletons and chart entry animation if already provided by Recharts. If the dashed "flow" animation on topology lines is kept, apply it only to energized lines at low contrast and disable it for reduced motion.

---

## 4. Component-by-component spec

For each file: **keep** = logic untouched; **change** = presentation only.

1. **`App.jsx` / shell.** Keep all state, effects, fetches, the 5s polling, `fetchTimeSeries`, tab ids and render conditions. Change: new shell and grouped navigation (3.4), error banner becomes the Alert primitive (retry button keeps its handler), footer reduced to one quiet line (brand and short tagline; the long checkpoint sentence moves out of the footer, not deleted from the repo).
2. **`Header.jsx`.** Keep props (`apiOnline`) and the displayed facts (location, CIGRE MV 15-bus grid, backend status). Change: slim bar or sidebar footer; facts become small muted chips; the stale "Checkpoints 1–3 Complete" chip is corrected to the true scope or removed (list in report); status uses a dot plus text.
3. **`DateRangePicker.jsx`.** Keep presets, validation, day-count display and `onApply`. Change: compact toolbar card, primary "Update data" button, themed date inputs.
4. **`MetricCards.jsx`.** Keep the four metrics and their values and formulas. Change: KPI tiles (3.5), tone dot instead of full-colored accents, icons from lucide in neutral muted color.
5. **`NetworkTopologyCanvas.jsx`.** Keep: node/line data, voltage thresholds (0.95–1.05 safe; 0.90–0.95 and 1.05–1.10 warning; otherwise violation), loading thresholds (70/100), hover and click selection, the telemetry inspector and every value shown. Change: node and line colors come from tokens; lines thin and static (energized animation optional per 3.8); inspector becomes a clean side card with label/value pairs. **Tidy layout (presentation only):** compute a clean schematic placement on the frontend from the `lines` connectivity (root at the slack/highest-voltage bus, place buses by depth horizontally and spread subtrees vertically, use straight or right-angle edges, minimize crossings, keep consistent spacing and label offsets). If the graph is not connected, contains an unexpected structure or the computation fails, **fall back to the existing coordinate mapping**. Never modify backend coordinates. Add a short legend with tone dots. Everything must remain readable at 375px width (horizontal scroll inside the diagram container is acceptable; shrink labels, not nodes below 24px).
6. **`TimeSeriesChart.jsx`.** Keep data, units toggle (p.u. / raw), axes meaning and date handling. Change: tokenized series colors (solar `--c-solar`, load `--c-load`), 2px lines, a very light area fill (≤ 8% opacity) or none, faint dashed grid, 12px muted ticks with fewer labels, styled tooltip card.
7. **`TelemetryTables.jsx`.** Keep both tables, columns, values, the bus/line toggle and status logic. Change: Table primitive, Badge for status, right-aligned tabular numbers, sticky header, scroll container.
8. **`ForecastPanel.jsx`.** Keep model/series toggles, window selector, retrain action, metrics (MAE, RMSE, R², split info, naive comparison) and chart data. Change: page header, KPI row, one chart card, series tokens (actual solid `--c-load`/`--c-solar` per target, LightGBM `--c-forecast` dashed vs actual per the paired-series rule, naive `--c-baseline` dashed), brush/range slider themed.
9. **`ViolationEnginePanel.jsx`** (largest source of nesting). Keep scenario selection, "trigger" and "re-run" actions, before/after toggle, violation log with its filters, ranked action table, sandbox controls, simulated result and every displayed metric. Change: scenario choices become one row of equal-height selectable cards (selected = accent border and soft background); the "Grid under stress" block becomes an Alert plus a compact stat row; the violation log becomes a Table-like list with Badge per violation type (overvoltage, undervoltage, line overload, trafo overload) and right-aligned value and margin columns, fixed max height with themed scroll; action types in the ranking use neutral badges with a small icon (battery, switching, curtailment) coloured by the series tokens; sandbox becomes a simple form card with a themed slider.
10. **`MpcControlPanel.jsx`.** Keep all controls, requests and displayed results. Change: page header, form fields, KPI row, results in cards with the shared chart styling.
11. **`TimePlanPanel.jsx`** (largest file). Keep episode selection, run actions, per-step inspector with step buttons, all charts (SOC, dispatch and curtailment, forecast vs observed, replan markers) and tables. Change: numbered section titles become plain card titles (no numbering badges unless they are data); step selector becomes a segmented control that scrolls horizontally on small screens; charts use series tokens (`--c-soc`, `--c-battery`, `--c-curtail`, forecast/observed pairs); replan markers use a single `--danger` or `--accent` thin vertical line with a label.
12. **`SurrogatePanel.jsx` and `SurrogateScreeningPanel.jsx`.** Keep sub-tabs (screening/A-B benchmark and ensemble training/evaluation), controls (initial SoC slider, injection checkbox, mode select), run/retrain/refresh actions, every metric (solver-call reduction, speedup, filtered candidates, disagreements), parity plots, confusion matrix, error/latency tables and split descriptions. Change: sub-tabs become the segmented control; KPI row uses the KPI tile; the "Physical verification architecture" note becomes an info Alert; the confusion matrix becomes a tidy 2×2 grid with tone tinting (safe/unsafe) and counts; parity plots use `--c-forecast` points against a `--c-baseline` identity line; A/B comparison uses `--c-baseline` (unscreened, dashed) versus `--accent` (screened).
13. **`ShowcasePanel.jsx`.** Keep the 12-step run action, the six labeled events, the step data, downloads and evidence links. Change: page header with the run button as the single primary action; the six event cards become one consistent row/grid of equal cards with an icon and tone dot (replace the six different colored left borders with one neutral treatment plus the status icon); evidence and downloads become a tidy list.
14. **`ChatWidget.jsx` / `ChatWidget.css`.** Keep the operator/executive mode toggle, suggestion chips, message flow, tool-detail expand/collapse and all requests. Change: tokenized colors for both themes, solid accent floating button without glow or gradient, message bubbles (assistant on `--surface-raised`, user on `--accent-solid`), clean input row; add bottom padding to the main content so the floating button never covers content.
15. **Footer and global CSS.** Rewrite `index.css` to import the new token and base styles. Delete unused Vite template CSS in `App.css` only after confirming nothing references it. Keep the Inter and JetBrains Mono fonts; move the font loading from a CSS `@import` to `<link rel="preconnect">` plus `<link rel="stylesheet">` in `index.html` (same fonts, faster first paint).

---

## 5. Method and structure

- New files only under `frontend/src/styles/`, `frontend/src/theme/`, `frontend/src/components/ui/` and `frontend/src/components/layout/`.
- **Migration pattern:** replace an inline `style={{…}}` with a class from the shared stylesheet. For values that depend on data (status tone), use `data-tone="ok|warn|danger|info"` or `data-state` attributes and style them in CSS. Keep truly dynamic numeric styles (bar widths, positions) inline.
- Keep JSX element order, `key` props and conditional branches. Do not rewrite loops, mapping functions or computations to "clean them up".
- Do not change label strings that code compares against; before editing text, search the codebase for string comparisons that depend on it.
- Replace emoji in labels and buttons with lucide-react icons or plain text. Text that is logged, exported or sent to the backend must stay character-identical.
- Dependencies: no new packages unless a checkpoint report justifies it and the user approves. Prefer plain CSS and CSS variables. Recharts and lucide-react stay.

---

## 6. Build phases (checkpoints)

Work one phase at a time, exactly like the earlier checkpoints: finish, run the verification gate (section 7), write `UI_CHECKPOINT_<N>_REPORT.md` at the repo root, commit with a clear message, **stop and wait for the user's go-ahead**.

### Phase UI-0 — Baseline and preservation inventory (no visual changes)
1. Record baselines: `npm run build`, `npm run lint`, `pytest` results, and the current commit hash. (The build currently succeeds with a chunk-size warning; lint baseline must be recorded before any change.)
2. Create `UI_PRESERVATION_INVENTORY.md`: for each component, list every data field displayed, every control (inputs, toggles, buttons, sliders, selects), every `fetch` call with URL and parameters, every polling interval and every conditional that gates rendering.
3. Capture "before" screenshots of every tab at 1280px in the current dark theme into `docs/ui/before/`.
**Done when:** inventory and baselines are committed and no source file changed.

### Phase UI-1 — Foundation
Tokens, base styles, both themes, theme provider and toggle, no-flash script, primitives, app shell with grouped navigation, slim header, footer. Existing panels render inside the new shell with their old internals (they may look mixed until later phases).
**Done when:** theme switching works and persists, navigation reaches all eight views with identical content, polling and tab behavior unchanged.

### Phase UI-2 — Data display
KPI tiles, date range toolbar, time-series chart, telemetry tables, topology map (including the tidy layout with fallback), shared chart styling and tooltip.
**Done when:** the Grid and Forecast views are fully restyled in both themes and values match the pre-redesign values for the same date range.

### Phase UI-3 — Panels
Showcase, Surrogate (both sub-views), Time Plan, Predictive MPC, Action Engine, Forecaster.
**Done when:** every control in the inventory for these panels works identically and no panel contains inline color literals.

### Phase UI-4 — Chat, polish, QA
Chat widget, responsive pass (375/768/1280/1920), accessibility pass, motion/reduced-motion, removal of dead CSS, screenshots of every tab in both themes into `docs/ui/after/`, README section "UI" with two screenshots (dark and light).
**Done when:** the final gate in section 7 passes in full.

---

## 7. Verification gate (run at the end of every phase)

1. **Frozen files untouched:** `git diff --name-only <baseline-commit> -- . ':!frontend' ':!docs/ui' ':!UI_*.md'` prints nothing. Inside `frontend/`, `git diff <baseline-commit> -- frontend/src/api frontend/src/config.js frontend/vite.config.js frontend/package.json` shows no changes (except an approved dependency change).
2. **Build and lint:** `npm run build` succeeds and `npm run lint` has no new errors compared with the baseline.
3. **Backend tests:** `pytest` result identical to the baseline.
4. **Network parity:** the set of `fetch(` calls (URL patterns, methods, parameters, polling intervals) found by searching `frontend/src` is identical to the inventory. Run the app, open each view, and confirm the same requests occur.
5. **Functional parity:** exercise every control in the inventory for the views touched in the phase (presets, apply, retrain, scenario trigger, re-run, before/after toggle, sandbox simulate, step selector, run showcase, screened episode, mode select, chat modes and suggestions). Results must match the pre-redesign behavior.
6. **Logic diff review:** in each modified file, every changed hunk must be presentation (class names, style props, wrappers, icons, copy listed in the report). Any hunk touching state, effects, handlers, conditions, data mapping or thresholds must be reverted or called out in the report.
7. **Both themes:** screenshots of the touched views in dark and light, no unreadable text, no leftover hard-coded dark colors, charts and tables themed.
8. **Accessibility basics:** keyboard-only pass through navigation, theme toggle and primary actions; contrast spot checks on muted text and chart lines.
9. **Responsive:** no horizontal page scroll at 375px; wide tables and diagrams scroll inside their own containers.

### Report template (`UI_CHECKPOINT_<N>_REPORT.md`)
What changed; files touched; verification results for items 1–9; list of copy changes; any non-presentational hunk and why; anything skipped or uncertain; screenshots paths.

---

## 8. Definition of done

- Every function, number, endpoint and pipeline behaves exactly as before, proven by the gate.
- A single coherent visual language: one accent, semantic colors only for status, consistent series colors across all charts, two surface levels, consistent spacing and type.
- Light and dark themes both complete, persisted, no flash on load, all tables, charts, inputs and widgets themed.
- Eight views reachable from clear grouped navigation with short labels; default view unchanged.
- No emoji in the UI, no inline color literals left in components (tokens only), no backdrop blur, glow or gradient buttons.
- The topology diagram reads cleanly with minimal edge crossings, falling back to the original layout when needed.
- Mobile and desktop layouts verified; accessibility basics pass.

## 9. Do not

- Modify anything listed in 0.1, or any file outside `frontend/` other than the allowed docs and screenshots.
- Rename tab ids, props, state variables, endpoints or exported component names.
- Remove, hide behind a new interaction, or relocate-to-nowhere any data or control that is visible today.
- Change displayed precision, units, thresholds or sort orders.
- Introduce a UI framework, CSS framework, state library or charting library.
- "Fix" or refactor logic you notice while restyling; list it in the report instead.
- Start the next phase without the user's explicit go-ahead.
