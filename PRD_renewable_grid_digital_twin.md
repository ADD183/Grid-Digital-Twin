# PRD — Renewable Distribution Grid Digital Twin
**Backend + interactive frontend prototype for hackathon Round 1 (Git repo is the primary judged artifact)**

---

## 0. Ground rules for the AI coding agent

1. **Both a defensible backend and an interactive, engaging frontend are required.** The backend logic must be independently correct and testable; the frontend must let a judge click through scenarios live, not just look at static screenshots.
2. **This PRD is built in 4 checkpoints, strictly in order.** Each checkpoint delivers a working backend slice *and* the frontend piece that renders it — never backend-only for multiple checkpoints in a row. Do not start Checkpoint N+1 until the user has explicitly approved Checkpoint N.
3. **At the end of each checkpoint**, the agent must:
   - Run its own tests/sanity checks (backend) and manually confirm the frontend page loads and the new feature renders correctly
   - Write a `CHECKPOINT_<N>_REPORT.md` (template in §6) summarizing what was built, what was verified, and any deviations or open issues
   - Commit the work with a clear commit message
   - **Stop and wait** for the user's go-ahead before touching Checkpoint N+1 code
4. **Only use verified library APIs.** Libraries and exact function calls this PRD relies on are pinned in §1 and have been checked against current documentation. If a needed function isn't in §1, don't guess — flag it in the checkpoint report.
5. **No SimBench.** Use a hand-built synthetic load profile (Checkpoint 1) instead of the `simbench` package — unnecessary extra dependency for this timeline.
6. **Git hygiene matters as much as code.** Every checkpoint needs: meaningful commits (not one giant commit), an up-to-date `README.md` (with a screenshot/GIF of the frontend once it exists), a `requirements.txt`, docstrings on public functions, and a `NOTES.md` capturing engineering assumptions (§7) so the team can answer judges' questions without needing a power-systems background.

---

## 1. Tech stack (pinned — do not substitute)

| Purpose | Library | Verified API used |
|---|---|---|
| Grid topology + power flow | `pandapower` | `pandapower.networks.create_cigre_network_mv(with_der="all")`, `pandapower.runpp(net)`, `net.res_bus.vm_pu`, `net.res_line.loading_percent` |
| Solar irradiance/generation history | `pvlib` (wraps PVGIS) | `pvlib.iotools.get_pvgis_hourly(latitude, longitude, start, end)` |
| Forecasting model | `lightgbm` (fallback: `scikit-learn` `GradientBoostingRegressor`) | standard `.fit()` / `.predict()` |
| Data handling | `pandas`, `numpy` | — |
| **Frontend** | **`streamlit`** | interactive app; chosen over a separate React/FastAPI split for a 2-day timeline — it gets you live, clickable, engaging screens fast without a frontend build pipeline. Flag to user if you'd rather spend the extra hours on React instead — see note below. |
| Interactive network diagram / charts | `plotly` (via `streamlit.plotly_chart`) | color-coded bus/line diagrams, before/after toggle, forecast line charts |
| Testing | `pytest` | — |

**Note on the Streamlit choice:** this is the recommended default because it turns backend logic into a live, interactive UI (sliders, scenario dropdowns, real-time re-runs, colored diagrams) with almost no frontend-specific code — the "engaging" requirement is met through interactivity, not visual polish. If the team specifically wants a custom-branded React frontend instead, say so before Checkpoint 1 — it changes the repo structure and adds real build time.

Demo location: **Pune, India** (lat 18.52, lon 73.85).

---

## 2. Repo structure (create this at Checkpoint 1, keep it stable after)

```
renewable-grid-digital-twin/
├── README.md
├── NOTES.md                     # engineering assumptions / judge Q&A prep
├── requirements.txt
├── CHECKPOINT_1_REPORT.md
├── CHECKPOINT_2_REPORT.md       # added at checkpoint 2
├── CHECKPOINT_3_REPORT.md       # added at checkpoint 3
├── CHECKPOINT_4_REPORT.md       # added at checkpoint 4
├── data/
│   ├── raw/                     # cached PVGIS pulls
│   └── processed/               # aligned solar + load time series, saved models
├── src/                         # pure backend logic — no Streamlit imports here
│   ├── grid.py                  # Checkpoint 1: network loading + baseline power flow
│   ├── data_pipeline.py         # Checkpoint 1: PVGIS fetch + synthetic load generator
│   ├── forecast.py              # Checkpoint 2: model train/predict
│   ├── violations.py            # Checkpoint 3: limit checks
│   ├── actions.py               # Checkpoint 3: corrective action functions
│   ├── engine.py                # Checkpoint 3: propose→verify→repair loop
│   └── scenarios.py             # Checkpoint 4: scenario runner
├── app/
│   ├── streamlit_app.py         # main frontend entrypoint — imports only from src/
│   └── components/              # small reusable render functions (diagram, metrics, tables)
├── tests/
│   ├── test_grid.py
│   ├── test_forecast.py
│   ├── test_violations.py
│   └── test_scenarios.py
├── outputs/
│   ├── plots/
│   └── scenario_results/        # JSON/CSV per scenario, before/after
└── main.py                      # CLI entrypoint for the pure backend pipeline (useful for tests/CI, independent of the UI)
```

**Why `src/` never imports `streamlit`:** this keeps the backend independently testable and genuinely "defensible" — a judge (or `pytest`) can run the engine with zero UI involved, which is the strongest evidence the logic is real and not just UI-driven theater.

---

## 3. Checkpoint 1 — Grid + Data Foundation, with a live network diagram

**Goal:** a network that runs a clean baseline power flow, real solar + synthetic load data, aligned — **and** a Streamlit page that renders the network as an interactive, color-coded diagram so there's something to click through from day one.

**Backend build:**
1. `src/grid.py`: load `create_cigre_network_mv(with_der="all")`, run `pp.runpp(net)`, confirm convergence, expose a function returning bus coordinates + voltage results as a clean dataframe (frontend-ready).
2. `src/data_pipeline.py`: pull 1–2 months of hourly Pune solar via `pvlib.iotools.get_pvgis_hourly` (cache raw response), generate a synthetic hourly load profile (documented shape in `NOTES.md`), align both into one time-indexed dataframe.
3. `main.py`: CLI command running steps 1–2 end to end, printing a summary.

**Frontend build:**
1. `app/streamlit_app.py`: a page that loads the network and displays an interactive Plotly diagram of the buses/lines, colored by voltage (green = healthy, amber/red = near/over limit) — even though nothing will be red yet at baseline, this proves the rendering pipeline works before you need it for real violations.
2. A small sidebar panel showing baseline stats (number of buses, DER count, voltage range).
3. A simple line chart of the solar + load series for the loaded date range.

**Acceptance criteria:**
- [ ] `pp.runpp(net)` converges without exceptions
- [ ] All baseline `vm_pu` values are within [0.95, 1.05]
- [ ] PVGIS data pulled and cached (re-running doesn't re-fetch)
- [ ] Synthetic load profile shows a visible morning/evening pattern
- [ ] `streamlit run app/streamlit_app.py` loads without error and shows a colored network diagram + data chart
- [ ] `pytest tests/test_grid.py` passes

**Stop condition:** write `CHECKPOINT_1_REPORT.md`, commit, wait for approval.

---

## 4. Checkpoint 2 — Forecasting Model, with a forecast panel

**Goal:** a validated model predicting next-hour solar and load — visible in the UI as a real chart, not a hidden metric.

**Backend build (after Checkpoint 1 approved):**
1. `src/forecast.py`: lagged features (t-1, t-2, t-3, t-24) + calendar features; train solar and load forecasters (`lightgbm`, fallback `GradientBoostingRegressor`); **chronological** holdout of the last 2–4 weeks; compute MAE/RMSE for the model *and* a naive baseline (predict = last known value) so the improvement is provable.
2. Save trained models to `data/processed/models/` via `joblib`.

**Frontend build:**
1. New Streamlit tab/section: forecast vs. actual line chart (Plotly) for the holdout period, for both solar and load.
2. Metrics panel showing MAE/RMSE for the model next to the naive baseline, so the improvement is visually obvious.

**Acceptance criteria:**
- [ ] Chronological split, not random
- [ ] MAE/RMSE reported for model and naive baseline, model clearly better
- [ ] Models saved and reloadable without retraining
- [ ] Forecast chart renders correctly in the Streamlit app
- [ ] `pytest tests/test_forecast.py` passes

**Stop condition:** write `CHECKPOINT_2_REPORT.md`, commit, wait for approval.

---

## 5. Checkpoint 3 — Violation Detection + Corrective Action Engine, with an interactive comparison view

**Goal:** the core of the submission — detect problems, compare corrective actions, and let a judge *trigger* this live in the UI.

**Backend build (after Checkpoint 2 approved):**
1. `src/violations.py`: function taking a post-`runpp` `net`, returning structured violations (bus/line, type, margin over/under limit).
2. `src/actions.py` — at least 3 corrective actions, each a function returning a modified `net` copy:
   - **Curtailment** — reduce `sgen` output by X% at offending bus(es)
   - **Battery dispatch** — charge/discharge via a `storage` element or documented `sgen`/`load` stand-in
   - **Feeder reconfiguration** — toggle a `net.switch` where topology allows
3. `src/engine.py` — propose→verify→repair loop: try each action at a few magnitudes, re-run `pp.runpp`, check resolution, score on (resolved Y/N, renewable output retained %, simple 1–3 cost proxy). Return the full ranked comparison, not just the winner. Output must be structured data (dict/JSON) — the frontend renders this directly.

**Frontend build:**
1. A "Trigger scenario" control (button/dropdown) that forces a violation (e.g. spike one `sgen`) and re-renders the network diagram live, so buses visibly turn red.
2. A comparison table/cards showing each action tried, its score, and which one the engine picked — interactive enough that a judge can see *why* an action won, not just the final answer.
3. Before/after toggle on the network diagram.

**Acceptance criteria:**
- [ ] Violation detector correctly flags an artificially-forced violation
- [ ] All 3 action types independently runnable, each produces a valid post-action `runpp` result
- [ ] At least one case where the engine fully resolves a violation and explains the choice over alternatives
- [ ] Clicking "trigger" in the UI visibly changes the diagram and shows the action comparison
- [ ] `pytest tests/test_violations.py` passes

**Stop condition:** write `CHECKPOINT_3_REPORT.md`, commit, wait for approval.

---

## 6. Checkpoint 4 — Scenario Suite, Honest Failure Case, and Demo Polish

**Goal:** the full demoable product — multiple scenarios selectable in the UI, clear before/after, and the required failure case shown honestly.

**Backend build (after Checkpoint 3 approved):**
1. `src/scenarios.py` — at least 4 scenarios: high solar/low load, evening peak/low solar, cloudy-day rapid drop, and **one deliberately infeasible scenario** where no action (or combination, within realistic limits) fully resolves the violation. The engine must report "unresolved, best partial mitigation was X, residual violation Y" — never silently pick a bad answer or crash.
2. Each scenario's before/after state + action comparison saved to `outputs/scenario_results/`.

**Frontend build:**
1. A scenario picker (dropdown or tabs) driving the whole page — selecting a scenario updates the diagram, the action comparison table, and a before/after metrics summary.
2. The infeasible scenario is visually and textually flagged as unresolved (not hidden or styled to look like a success) — this is a specific ask in the problem statement, so make it impossible to miss on screen.
3. Polish pass: consistent layout, a title/intro panel explaining what the tool does, and a "how it works" expander (1 paragraph) for judges skimming quickly.

**Acceptance criteria:**
- [ ] All 4+ scenarios selectable and runnable live from the Streamlit app, no code editing required
- [ ] Each scenario has a saved artifact (plot + JSON/CSV) independent of the UI
- [ ] The infeasible scenario is clearly labeled as such, in both backend output and frontend display
- [ ] `streamlit run app/streamlit_app.py` → clicking through all scenarios works end-to-end with no errors
- [ ] README updated with setup instructions, a screenshot/GIF, and a results summary; a stranger can clone and run the demo in under 5 minutes
- [ ] `pytest tests/` passes in full

**Stop condition:** write `CHECKPOINT_4_REPORT.md`, commit. This is the submission-ready state.

---

## 7. `NOTES.md` — required content (fill incrementally, checkpoint by checkpoint)

Short entries (1–3 sentences), so the team can answer judge questions without a power-systems background:

- Why 0.95–1.05 pu is used as the voltage limit
- Why line loading >100% matters (thermal overload risk)
- What simplification was used for "battery" (which pandapower element, what it approximates)
- Why CIGRE MV + DER was chosen over a real feeder (no public Indian feeder data exists at this granularity; CIGRE is the standard academic benchmark for DER-integration studies)
- Why the load profile is synthetic
- Why Streamlit was chosen over a custom frontend framework (interactivity fast, no build pipeline, time-appropriate for 2 days)
- One sentence per scenario explaining why it's interesting

---

## 8. Explicit "do not" list

- Do not skip the frontend for any checkpoint after Checkpoint 1 — backend and UI ship together
- Do not put `pandapower`/model logic inside `streamlit_app.py` — keep `src/` UI-free and independently testable
- Do not use `simbench`
- Do not use an LSTM or any deep learning model — out of scope for the time budget
- Do not skip the chronological train/test split
- Do not let the engine silently fail on the infeasible scenario — it must be reported, not hidden
- Do not proceed to the next checkpoint without an explicit go-ahead, even if confident
- Do not fabricate a pandapower/pvlib/streamlit function that doesn't exist — if uncertain, say so in the checkpoint report instead of guessing
