# PRD — Final Round Additions (ENR-02): Multi-Step Control + Power-Flow Surrogate

**Audience: the AI coding agent building this project.** Read this file fully, then read `PRD_renewable_grid_digital_twin.md` (CP1–CP4 spec) and `PROJECT_KNOWLEDGE_BASE.md` (domain context). This document specifies **Checkpoints 5–8**, built on top of the existing CP1–CP4 codebase.

---

## 0. Working protocol (follow exactly)

1. **Build one checkpoint at a time**, only the one the user asks for. Do not start the next checkpoint on your own, even if you are confident.
2. **At the end of each checkpoint:**
   - Run the tests and manually confirm the UI renders the new feature.
   - Self-check every acceptance criterion of that checkpoint and mark each as passed or failed.
   - Write `CHECKPOINT_<N>_REPORT.md` (what was built, what was verified, criteria status, deviations, known issues, anything you were unsure about).
   - Commit with a clear message.
   - **Stop and wait** for the user's review and go-ahead.
3. **Each checkpoint must stay in sync with the previous ones.** Reuse the contracts in section 4 exactly; do not rename or reshape them without flagging it in the report.
4. **Finish what you start.** Prefer a smaller feature that is complete and tested over a larger one that is half built. Anything you deliberately skip must be listed in the checkpoint report.
5. **Never break existing behavior.** CP1–CP4 tests must still pass after every checkpoint.
6. **Only use APIs you are sure exist** (pandapower, pandas, numpy, scipy, torch, scikit-learn, pyyaml, pyarrow, streamlit, plotly, pytest). If unsure about a function or parameter, say so in the report instead of guessing.
7. **`src/` must stay UI-free.** Streamlit code lives only in `app/` and only renders outputs produced by `src/`.
8. **Everything is seeded and reproducible.** One global seed in `config/limits.yaml`. Every saved artifact records seed, library versions and timestamp.

## 1. Objective and non-negotiable principles

Preserve the electrical network, solar/load inputs and physical power-flow checks. Add:

- **Addition 1 — Control across multiple time steps:** plan over at least eight time steps while tracking battery state of charge (SOC), power limits, network limits and permitted switching/curtailment; replan when observed solar/load differ from forecasts; show state transitions and before/after power-flow results; identify infeasible periods and fallbacks explicitly.
- **Addition 2 — Learned power-flow surrogate:** train a surrogate on solver-labeled operating states to estimate node voltages and line loading or screen risky states; use it to screen candidate actions; declare its supported range and fallback; evaluate on separately generated unseen conditions including near-limit states; report prediction error, unsafe states mistaken for safe, and execution time.

**Principles that override convenience:**
- pandapower is the source of truth. **No action is ever presented as safe unless the physical solver verified it.** The surrogate only screens.
- Report failures honestly (non-converged samples, false-safe cases, infeasible periods, bad metrics).
- Injected forecast errors are always labeled as injected, never described as real measurements.

## 2. Technology stack (pinned; do not substitute)

**Carried over unchanged from CP1–CP4:** Python and `pandapower`, `pandas`, `numpy`, `pvlib` (PVGIS), `lightgbm` (forecaster), `streamlit`, `plotly`, `pytest`. Use the same Python and library versions already in `requirements.txt`; do not upgrade them.

**Added for CP5–CP8:**

| Purpose | Technology | Specific usage |
|---|---|---|
| Physical solver | `pandapower` | `pp.runpp(net, algorithm=..., tolerance_mva=..., max_iteration=..., init=...)`; read `net.res_bus.vm_pu`, `net.res_line.loading_percent` and, if present, `net.res_trafo.loading_percent`. Save the exact arguments in `solver_config.json`. |
| Battery element | `pandapower` | `pp.create_storage(...)` with `p_mw` set each step by the controller. pandapower does not carry SOC across steps, so SOC is tracked in our own `State`. If `create_storage` causes problems, use the documented sgen/load stand-in and record it in `NOTES.md`. |
| Curtailment | `pandapower` | Scale or reduce the sgen output at the chosen DER (`net.sgen`). |
| Switching | `pandapower` | Change `net.switch.closed` for the chosen switch, then re-run power flow. |
| Sampling operating states | `scipy.stats.qmc` | `LatinHypercube` or `Sobol` with a fixed seed. |
| Surrogate model | `torch` (CPU only) | `torch.nn.Module` MLP; save with `torch.save`. Fallback only if torch cannot be installed: `scikit-learn` `MLPRegressor` with `joblib`. |
| Config and limits | `pyyaml` | Single `config/limits.yaml` loaded into plain dataclasses. |
| Data storage | `pyarrow` via `pandas` | Parquet for split manifests and datasets; JSON for metrics and metadata; JSONL for action logs; CSV for SOC traces. |
| Timing | Python `time.perf_counter` | Latency for solver and surrogate. State hardware in the report. |
| Reproducibility | `numpy`, `torch` seeds; `importlib.metadata` | Seed every random source; record library versions in each artifact's metadata. |
| UI | `streamlit` + `plotly` | Two new tabs ("Time Plan", "Surrogate"); render only from saved logs and metrics. |
| Tests | `pytest` | Seeded tests for SOC bounds, verifier, screener safety and surrogate reload. |

Dependency rules: add every new package to `requirements.txt` with its exact installed version; no new external APIs, services, databases or frontend frameworks.

## 3. Repository additions

```
config/limits.yaml            # equipment limits, battery params, action levels, ranges, guard band, seed
src/control/state.py          # State, Action dataclasses
src/control/verifier.py       # pandapower verification wrapper
src/control/screener.py       # NullScreener (CP5) -> SurrogateScreener (CP7)
src/control/planner.py        # rolling-horizon beam search
src/control/episode.py        # run_episode(): plan, apply, observe, replan, log
src/surrogate/sampling.py     # state sampling + solver labeling
src/surrogate/train.py        # training + calibration
src/surrogate/evaluate.py     # error, false-safe, latency
tests/test_control.py  tests/test_surrogate.py  tests/test_screening.py
app/                          # new tabs: "Time Plan" and "Surrogate"
outputs/evidence/             # see CP8
```

## 4. Contracts (keep stable across checkpoints)

- **`config/limits.yaml`:** `v_min=0.95`, `v_max=1.05`, `max_loading_pct=100`; battery (`capacity_mwh`, `max_power_mw`, `soc_min`, `soc_max`, `efficiency`); `curtail_levels=[0,10,25,50]`; `battery_levels` (5 levels from full charge to full discharge); `switch_budget` per horizon; `dt_hours`; `horizon_steps` (default 8; showcase 12); `seed`; surrogate `supported_range`, `guard_band`, `disagreement_ceiling`.
- **`State`:** `t`, `soc`, `switch_state`, `curtail_level`.
- **`Action`:** `battery_mw` (positive = discharge, negative = charge), `curtail_pct`, `switch_toggle` (None or switch id).
- **`verify(state, action, observed_inputs) -> VerificationResult`:** `converged`, `violations[]`, `min_margin` (signed distance to nearest limit; negative = violated), `bus_vm`, `line_loading`, `solve_ms`.
- **`screen(candidates) -> list[ScreenResult]`:** `status` in {`safe`, `unsafe`, `uncertain`, `unsupported`}, `predicted_margin`, `disagreement`, `infer_ms`. `NullScreener` returns `uncertain` for everything so every candidate reaches the solver.
- **`run_episode(...) -> EpisodeLog`:** per step: state before/after, chosen action, forecast vs observed, SOC, verification result, replan flag, infeasible flag, fallback used, screener status.

---

## 5. Checkpoint 5 — Multi-step control with the physical solver only

**Goal:** a working rolling-horizon controller that uses only pandapower for evaluation, with a UI timeline. This is the baseline the surrogate will later be compared against.

**Build**
1. `State`/`Action` and the battery SOC update with explicit charge/discharge efficiency. Document the formula in `NOTES.md`. Reject actions that violate SOC bounds or power limits before running any power flow.
2. Verifier wrapper around `pp.runpp`. Pin solver settings (algorithm, tolerance, max iterations) in `outputs/evidence/solver_config.json`. Apply the action (battery as a storage element or a documented stand-in, curtailment on sgen, switch toggle), run power flow, return a `VerificationResult`.
3. Planner: rolling-horizon **beam search** over action sequences, horizon of at least 8 steps, configurable beam width (default 5). Score = renewable energy used − switching penalty − battery cycling penalty − violation penalty. Hard constraints: SOC bounds, power limits, switching budget. The action executed at each step is verified by the solver.
4. `run_episode`: each step, plan on forecasts, apply the first action, reveal **observed** solar/load (forecast plus an injectable, labeled error event), then replan from the new state.
5. **Infeasibility and fallback ladder:** if no candidate passes verification, try in order (a) maximum battery support, (b) maximum curtailment at the offending DER, (c) alternate switch state. If violations remain, mark the period `infeasible`, record the residual violation and the fallback used.
6. UI **"Time Plan" tab:** SOC trace, action timeline, forecast vs observed, replan markers, infeasible periods highlighted, before/after voltage and loading per step. It renders from a saved `EpisodeLog`.

**Acceptance criteria**
- [ ] An episode of at least 8 steps runs end to end with a solver-verified action at every step
- [ ] SOC never leaves bounds and power limits are respected (unit tests)
- [ ] An injected forecast error causes a visible replan with changed actions
- [ ] A scenario with an infeasible period is reported explicitly, with the fallback used
- [ ] Time Plan tab renders from a saved `EpisodeLog`
- [ ] `pytest tests/test_control.py` passes and CP1–CP4 tests still pass

**Out of scope:** MILP or LinDistFlow optimization, multi-feeder switching optimization.

**Stop:** write `CHECKPOINT_5_REPORT.md`, commit, wait for approval.

---

## 6. Checkpoint 6 — Surrogate dataset, training and evaluation

**Goal:** a trained, calibrated surrogate with an honest evaluation on separately generated unseen conditions.

**Build**
1. **Features:** per-bus net P and Q injection after the action (solar after curtailment, load, battery) plus a switch-state encoding. **Targets:** every bus `vm_pu`, every line `loading_percent` (and transformer loading if present), derived `min_margin`, and an `unsafe` flag. Store `converged` for every sample.
2. **Sampling** with `scipy.stats.qmc` (Latin hypercube or Sobol, seeded): vary solar scale, load scale, per-bus variation, battery power, curtailment and switch state. Label each state with the same solver configuration as CP5. Exclude non-converged states from training but **record how many were dropped**.
3. **Splits, saved as manifests (parquet plus JSON with seeds and ranges):**
   - `dev_train`, `dev_val`: the declared **development range**. It must contain both safe and unsafe states (target at least 20% unsafe), otherwise the classifier cannot learn.
   - `test_unseen`: new samples from **held-out parameter combinations** (hold out grid cells of solar × load), not a random split.
   - `test_extended`: a **distinct, wider operating range** than development (for example higher solar and load scales) to probe extrapolation.
   - `test_near_limit`: states with margin within about 2% of a limit, found by rejection sampling.
   Choose concrete ranges against the actual network so every split is non-trivial; record them in `config/limits.yaml`.
4. **Model:** small MLP (2–3 hidden layers, 64–128 units), standardized inputs and outputs, regression heads for voltages and loadings plus an `unsafe` logit head with class weighting. Train **3 seeds** as an ensemble; disagreement = standard deviation across seeds of the predicted margin.
5. **Calibration:** on `dev_val` only, set the guard band so the false-safe rate is minimized (for example the 99th percentile of margin error). Declare the **supported operating range** = development feature bounds plus a disagreement ceiling. Save both in the artifact metadata.
6. **Evaluation on every test split:** MAE, RMSE and max error for voltage (pu) and loading (%); confusion matrix for unsafe/safe; **unsafe-mistaken-for-safe count and rate with and without the guard band**; near-limit subset metrics reported separately; fraction of test inputs flagged `unsupported`; latency of the surrogate per state and batched (1, 100, 1000 states) versus `runpp` per state, with hardware stated. Include a naive baseline (for example predicting the development-set mean). Never tune on any test split.
7. UI **"Surrogate" tab:** parity plots (predicted vs solver), error histograms, confusion matrix, latency table, split descriptions.

**Acceptance criteria**
- [ ] Development and test splits come from distinct ranges or parameter combinations, documented in manifests
- [ ] Metrics JSON contains error, false-safe (with and without guard band), near-limit results and latency
- [ ] Artifacts reload and predict without retraining
- [ ] Naive baseline reported alongside the surrogate
- [ ] Dropped non-converged sample counts reported
- [ ] `pytest tests/test_surrogate.py` passes and earlier tests still pass

**Out of scope:** hyperparameter search, ONNX export, graph neural networks.

**Stop:** write `CHECKPOINT_6_REPORT.md`, commit, wait for approval.

---

## 7. Checkpoint 7 — Surrogate-screened planning

**Goal:** integrate the surrogate into candidate evaluation while the solver still verifies every selected action.

**Build**
1. `SurrogateScreener`: for each candidate, check the supported range first (`unsupported` → solver). Otherwise predict the margin: `safe` only if the predicted margin exceeds the guard band and ensemble disagreement is below the ceiling; `unsafe` if clearly violating; otherwise `uncertain`.
2. Planner integration: `unsafe` candidates are dropped without a solver call; `safe` and `uncertain` ones proceed; **the chosen action is always solver-verified**. If the solver rejects a surrogate-`safe` candidate, log a **disagreement event** (surrogate margin, solver margin, solver response) and move to the next-best candidate.
3. A/B run on identical episodes with `NullScreener` versus `SurrogateScreener`. Report solver calls, wall time, chosen-action agreement and final safety (there must be zero unverified actions in both).
4. Log the screener status for every candidate and every step, including fallback to the solver on unsupported inputs.
5. UI: per-step screener status, disagreement events with the solver response, A/B comparison of solver calls and time.

**Acceptance criteria**
- [ ] Every presented action carries a solver verification record
- [ ] At least one logged disagreement event with the solver response shown
- [ ] At least one step where unsupported input falls back to the solver
- [ ] A/B comparison table (solver calls, time, outcome)
- [ ] A test proving a surrogate-approved unsafe action is never presented as safe
- [ ] `pytest tests/test_screening.py` passes and earlier tests still pass

**Stop:** write `CHECKPOINT_7_REPORT.md`, commit, wait for approval.

---

## 8. Checkpoint 8 — Showcase scenario and evidence pack

**Goal:** a reproducible demonstration of every required event and a complete evidence package.

**Build**
1. One deterministic **12-step showcase episode** (roughly late morning to evening) that triggers and labels each required event: injected **forecast error**, battery **saturation** (SOC at maximum around midday), battery **depletion** (SOC at minimum in the evening), a **near-limit network state**, an **infeasible period** with its fallback, and a **surrogate disagreement** with the solver response.
2. `main.py --final-demo` reproduces the showcase and regenerates the evidence pack from a clean clone.
3. **Evidence pack** in `outputs/evidence/`:
   - `solver_config.json`
   - `splits/` (manifests for dev_train, dev_val, test_unseen, test_extended, test_near_limit)
   - `surrogate/` (model files, scalers, metadata with supported range, guard band, seeds, versions)
   - `soc_traces/*.csv`
   - `action_logs/*.jsonl`
   - `metrics/` (error, false-safe, near-limit, latency as JSON plus plots)
   - `verification/` (final solver verification output for every selected action)
   - `EVIDENCE_INDEX.md` mapping each required evidence item to its file path
4. Update `README.md` (run instructions, screenshots) and add a "Final round" section to `PROJECT_KNOWLEDGE_BASE.md` with a presentation outline and likely judge questions (for example "what if the surrogate is wrong?" → solver verification, guard band, supported range, fallback).

**Acceptance criteria**
- [ ] A clean-clone run reproduces the showcase and the evidence pack
- [ ] `EVIDENCE_INDEX.md` lists a file for every item the brief requires
- [ ] All six required events are visible in the UI and labeled in the logs
- [ ] `pytest tests/` passes in full

**Stop:** write `CHECKPOINT_8_REPORT.md`, commit. This is the submission-ready state.

---

## 9. Do not

- Present any action as safe without a solver verification record
- Tune the surrogate, guard band or ranges using any test split
- Hide non-converged samples, failures or false-safe cases
- Let SOC leave its bounds or exceed the switching budget
- Add MILP, sequence models, new external APIs or a new frontend framework
- Describe injected forecast errors as real measurements
- Proceed past a checkpoint without the user's explicit go-ahead