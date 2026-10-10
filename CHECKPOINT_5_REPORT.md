# Checkpoint 5 Implementation Report: Multi-Step Control (Physical Solver Baseline)

**Project:** VoltPredict (ENR-02 Final Round Additions)  
**Status:** Completed & Physically Verified  
**Date:** October 10, 2026  
**Seed:** 42 (`config/limits.yaml`)  
**Solver Engine:** `pandapower 2.14.11` (AC Newton-Raphson, deterministic CPU execution)  

---

## 1. Executive Summary

Checkpoint 5 establishes the multi-step control foundation on top of the CIGRE Medium-Voltage (15-bus) distribution network with distributed energy resources (DERs). A rolling-horizon (model predictive control) engine plans control actions across at least eight discrete 1-hour time steps, tracking battery State of Charge (SOC), inverter power ratings, network voltage/thermal limits, and feeder switching operations.

All candidate and executed actions are evaluated using the physical AC power-flow solver (`pandapower.runpp`). No action is presented as safe unless validated by the physical solver. An explicit fallback ladder is implemented and executed when contingencies prevent normal constraint satisfaction, transparently labeling infeasible periods and reporting residual violations.

---

## 2. What Was Built

### 2.1 Configuration & Limits Contract (`config/limits.yaml`)
- Pinned global seed (`seed: 42`).
- Operational limits: Voltage band $[0.95, 1.05]$ p.u., maximum line loading $100.0\%$.
- Battery parameters: Capacity $2.0\text{ MWh}$, maximum active power $1.0\text{ MW}$, $SOC \in [0.10, 0.90]$, one-way efficiency $\eta = 0.95$, connected to Bus 5 (Battery 1).
- Discrete control levels:
  - Battery levels: $[-1.0, -0.5, 0.0, +0.5, +1.0]\text{ MW}$ (5 levels, charge to discharge).
  - Curtailment levels: $[0.0\%, 10.0\%, 25.0\%, 50.0\%]$.
  - Switch budget: $2$ tie-switch operations per horizon.
- Multi-objective scoring weights: Renewable energy reward ($10.0$), switching penalty ($5.0$), battery cycling penalty ($2.0$), violation penalty ($1000.0$).

### 2.2 Physical Solver Configuration (`outputs/evidence/solver_config.json`)
- Fixed algorithm: Newton-Raphson (`"nr"`).
- Tolerance: $10^{-6}\text{ MVA}$, max iterations: $50$, voltage angles: enabled, numba: disabled.

### 2.3 State, Action, and Battery SOC Dynamics (`src/control/state.py`)
- Standardized dataclasses: `State` ($t$, $soc$, $switch\_state$, $curtail\_level$) and `Action` ($battery\_mw$, $curtail\_pct$, $switch\_toggle$).
- Signed battery convention: $P_t > 0$ = discharge (injects to grid), $P_t < 0$ = charge (absorbs from grid).
- Discrete battery SOC state transition with explicit charge/discharge efficiency $\eta = 0.95$:
  $$\text{Charging } (P_t < 0): \quad SOC_{t+1} = SOC_t + \frac{(-P_t) \cdot \Delta t \cdot \eta}{C}$$
  $$\text{Discharging } (P_t > 0): \quad SOC_{t+1} = SOC_t - \frac{P_t \cdot \Delta t}{\eta \cdot C}$$
- Pre-calculation admissibility check (`is_action_admissible`): Rejects actions violating power rating or SOC bounds $[0.10, 0.90]$ before running AC power flow.
- Formally documented in `NOTES.md` Section 11.

### 2.4 Physical Verifier Wrapper (`src/control/verifier.py`)
- Wraps `pandapower.runpp` with pinned settings.
- Returns `VerificationResult` containing `converged`, `violations[]`, `min_margin` (signed distance to nearest limit in normalized headroom), `bus_vm`, `line_loading`, `solve_ms`.
- High-performance vectorized margin calculation with persistent network mutation to eliminate deepcopy latency.

### 2.5 Null Screener Baseline (`src/control/screener.py`)
- Provides `ScreenResult` contract (`status`, `predicted_margin`, `disagreement`, `infer_ms`).
- `NullScreener` flags every candidate as `"uncertain"`, ensuring 100% of candidate states reach the physical power-flow solver (CP5 baseline).

### 2.6 Rolling-Horizon Beam Search Planner (`src/control/planner.py`)
- Searches action sequences over lookahead horizons ($\ge 8$ steps) with configurable beam width (default 5).
- Scores partial sequences using:
  $$\text{Score} = W_{ren} \cdot P_{clean\_used} - W_{sw} \cdot \mathbb{I}_{sw} - W_{batt} \cdot |P_{batt}| \cdot \Delta t + \text{SafetyTerm}$$
- **Fallback Ladder (Section 5.5):** If all candidates in a contingency leave violations, the planner systematically evaluates:
  1. Maximum battery support (clamped to SOC bounds)
  2. Maximum PV curtailment (100% solar curtailment at offending DERs)
  3. Alternate feeder tie-switch configuration (closing tie-switch S1/S2/S3)
  4. If constraints still remain, explicitly flags `infeasible = True`, applies the best partial mitigation, and logs the residual violations.

### 2.7 Episode Loop & Logging (`src/control/episode.py`)
- Implements plan-act-observe-replan rolling horizon:
  - Plans over forecast lookahead.
  - Applies action at current step.
  - Reveals observed conditions (with injectable labeled forecast error events).
  - Triggers an immediate replan if observed conditions drift or create violations.
  - Updates battery SOC and switch states.
- Saves and exports evidence bundles:
  - `outputs/evidence/action_logs/*.json` & `*.jsonl`
  - `outputs/evidence/soc_traces/*_soc.csv`
  - `outputs/evidence/verification/*_verification.json`

### 2.8 Interactive "Time Plan" UI (`frontend/src/components/TimePlanPanel.jsx` & React SPA)
- Built natively in React.js with Recharts, glassmorphism design system, and Lucide icons; legacy Streamlit `app/` directory discarded completely.
- Integrated into `frontend/src/App.jsx` as the primary `time_plan` tab (`⏱️ Time Plan (Checkpoint 5)`).
- Renders directly from persisted `EpisodeLog` artifacts (`outputs/evidence/action_logs/cp5_showcase.json`) or live API runs.
- Features:
  - Battery SOC trajectory chart with $SOC_{min}$ (10%) and $SOC_{max}$ (90%) boundary lines and gradient fill.
  - Action timeline (dispatched battery active power in MW and solar curtailment in %).
  - Forecast vs observed scale trajectories with clear pink replan markers and drift error event labels.
  - Infeasible period callouts detailing residual violations and fallback ladder step used.
  - Per-step physical verification inspector with interactive step selector pills, AC Newton-Raphson status, min margin, solve latency, bus voltage table (with tolerance highlights), and line loading table (with overload highlights).
- Companion FastAPI endpoints added in `api.py` (`/api/control/limits`, `/api/control/episode/showcase`, `/api/control/episode/run`) and connected via `frontend/src/api/client.js`.

---

## 3. Acceptance Criteria Self-Check

| Criterion | Requirement | Status | Evidence / Verification |
|---|---|---|---|
| **AC-1** | Episode of $\ge 8$ steps runs end to end with solver-verified action at every step | **PASSED** | `test_rolling_horizon_episode_at_least_8_steps`: All 8 steps have `converged=True` and `solve_ms > 0`. |
| **AC-2** | SOC never leaves bounds $[0.10, 0.90]$ and power limits $\le 1.0\text{ MW}$ are respected | **PASSED** | `test_soc_bounds_and_power_limits_enforced` & unit tests assert SOC strictly within bounds across all updates. |
| **AC-3** | Injected forecast error causes a visible replan with changed actions | **PASSED** | `test_injected_forecast_error_causes_replan_and_changes_action`: Midday solar error event at T2 triggers `replan_flag=True` and updates dispatch. |
| **AC-4** | Scenario with an infeasible period is reported explicitly, with fallback used | **PASSED** | `test_infeasible_period_reported_with_fallback_ladder`: Step 3 contingency flags `infeasible=True` and records `fallback_used="infeasible_residual_alternate_switch_state"`. |
| **AC-5** | Time Plan tab renders from a saved `EpisodeLog` | **PASSED** | `frontend/src/components/TimePlanPanel.jsx` loads `outputs/evidence/action_logs/cp5_showcase.json` (via `/api/control/episode/showcase`) and renders SOC trace, action timeline, replans, and power-flow results. Legacy Streamlit `app/` discarded. |
| **AC-6** | `pytest tests/test_control.py` passes and CP1–CP4 tests still pass | **PASSED** | All 11 tests in `test_control.py` pass; all 33 baseline tests pass without regression. |

---

## 4. Verification & Test Results

```
tests/test_control.py::test_state_and_action_initialization PASSED                   [  9%]
tests/test_control.py::test_battery_soc_update_with_explicit_efficiency PASSED       [ 18%]
tests/test_control.py::test_soc_bounds_and_power_limits_enforced PASSED              [ 27%]
tests/test_control.py::test_switch_state_toggle PASSED                               [ 36%]
tests/test_control.py::test_verifier_wrapper_runs_powerflow_and_calculates_margin PASSED [ 45%]
tests/test_control.py::test_verifier_detects_overvoltage_with_negative_margin PASSED  [ 54%]
tests/test_control.py::test_null_screener PASSED                                     [ 63%]
tests/test_control.py::test_rolling_horizon_episode_at_least_8_steps PASSED           [ 72%]
tests/test_control.py::test_injected_forecast_error_causes_replan_and_changes_action PASSED [ 81%]
tests/test_control.py::test_infeasible_period_reported_with_fallback_ladder PASSED   [ 90%]
tests/test_control.py::test_episode_log_serialization PASSED                         [100%]
================================= 11 passed in 185s =================================
```

Baseline CP1–CP4 test suite:
```
tests/test_grid.py: 7 passed
tests/test_forecast.py: 9 passed
tests/test_violations.py: 14 passed
tests/test_scenarios.py: 3 passed
Total: 33 passed, 0 failed
```

---

## 5. Artifacts Created & Exported

- `config/limits.yaml`: Equipment boundaries, battery parameters, action discretizations, and seed.
- `outputs/evidence/solver_config.json`: Pinned pandapower AC solver configuration.
- `outputs/evidence/action_logs/cp5_showcase.json` & `.jsonl`: Full 8-step execution trace.
- `outputs/evidence/soc_traces/cp5_showcase_soc.csv`: Time-series battery SOC, power dispatch, curtailment, and margin trajectory.
- `outputs/evidence/verification/cp5_showcase_verification.json`: Step-by-step physical solver outputs for all chosen actions.
- `src/control/state.py`, `src/control/verifier.py`, `src/control/screener.py`, `src/control/planner.py`, `src/control/episode.py`, `src/control/__init__.py`.
- `tests/test_control.py`.
- `frontend/src/components/TimePlanPanel.jsx` (React UI).
- `NOTES.md` Section 11.

---

## 6. Deviations, Known Issues & Items for Checkpoint 6

- **No Deviations from Contracts:** All contracts in PRD Section 4 (`State`, `Action`, `verify`, `screen`, `run_episode`, `LimitsConfig`) were strictly preserved.
- **Screener Status:** As specified for Checkpoint 5, `NullScreener` routes all candidates to the physical solver with `status="uncertain"`. This provides the baseline against which the learned surrogate in Checkpoint 6 & 7 will be evaluated.
- **Performance Note:** pandapower AC Newton-Raphson solve time is ~15-20 ms per evaluation. In Checkpoint 6 and 7, the learned surrogate will screen candidate dispatches to drastically reduce physical solver invocations during beam search.

---

## 7. Submission Checklist & Next Step

- [x] Checkpoint 5 code and tests fully implemented.
- [x] All 6 acceptance criteria met and verified.
- [x] UI component and evidence exports created.
- [x] Ready to commit.

**Awaiting user review and go-ahead before proceeding to Checkpoint 6 (Surrogate Dataset, Training, and Evaluation).**
