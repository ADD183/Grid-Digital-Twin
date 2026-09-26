# Checkpoint 3 Report - Violation Detection and Corrective Action Engine

**Date:** 2026-09-26  
**Source commit:** `c8d20df` - `Checkpoint 3 udpate`  
**Status:** Completed in the committed Checkpoint 3 update

## 1. Executive Summary

Checkpoint 3 adds the core grid-defense workflow to the Renewable Distribution Grid Digital Twin. The backend can now detect voltage and thermal violations after an AC power flow, apply independent corrective actions to isolated network copies, verify each action with a fresh power flow, and return a ranked comparison with an explainable recommendation.

The active React/FastAPI control room exposes this workflow through selectable trigger scenarios, a before/after topology view, an action comparison matrix, and a custom action sandbox. The implementation stays UI-independent under `src/`, so the physics and decision logic can be tested without the browser.

## 2. Deliverables

### Backend

- Added `src/violations.py` with structured detection for:
  - Bus overvoltage and undervoltage
  - Line thermal overload
  - Transformer thermal overload
  - Power-flow non-convergence
- Added `src/actions.py` with isolated-copy corrective actions:
  - Solar curtailment by percentage, optionally targeted to a bus or generator set
  - Battery dispatch using pandapower storage elements, supporting charging and discharging
  - Feeder reconfiguration by closing CIGRE MV tie switches `S1`, `S2`, or `S3`
- Added `src/engine.py` with the propose -> verify -> repair loop:
  - Triggers realistic demo constraint scenarios
  - Generates candidates across multiple magnitudes and action families
  - Runs `pandapower.runpp` for every candidate
  - Checks residual violations
  - Ranks candidates using resolution, renewable retention, and operational cost
  - Returns structured ranked actions, before/after summaries, topology, and rationale
- Added FastAPI endpoints for scenario listing, triggering, evaluation, and custom actions.

### Frontend

- Added the Checkpoint 3 action-engine panel to the React control room.
- Added three selectable live scenarios:
  - Midday solar surge / overvoltage risk
  - Evening demand peak / voltage sag
  - Feeder line overload
- Added controls to trigger a scenario and rerun the decision engine.
- Added before/after/custom topology views with voltage- and loading-coded buses and lines.
- Added an action comparison table showing rank, action family, resolution status, residual violations, renewable retention, cost proxy, and score.
- Added a plain-English recommendation and scoring rationale.
- Added a custom action sandbox for feeder switching, battery MW dispatch, and curtailment percentage.

### Documentation and tests

- Extended `NOTES.md` with Checkpoint 3 scoring rationale and CIGRE tie-switch assumptions.
- Added `tests/test_violations.py` covering detector logic, action isolation, power-flow validity, scenario induction, scoring, engine ranking, resolution, and API behavior.
- Updated the project documentation and API integration for the React/FastAPI architecture.

## 3. Corrective Action Design

The engine uses the following priority order:

1. Fully eliminate all constraints: `+1000` points.
2. Preserve renewable output: `+2` points per retained percentage point.
3. Penalize operational cost: `-15` points per cost-proxy unit.
4. Penalize unresolved violation count and residual voltage/loading severity.

The cost proxy is intentionally simple and explainable:

| Action | Cost proxy | Renewable retention | Engineering interpretation |
|---|---:|---:|---|
| Feeder reconfiguration | 1 | 100% | Network switching with no generation waste |
| Battery dispatch | 2 | 100% | Preserves energy but incurs battery cycling wear |
| Solar curtailment | 3 | Depends on curtailment | Reliable fallback that wastes clean generation |

Every action operates on a deep copy of the network. The original scenario remains available for the before/after comparison.

## 4. API Surface

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/violations/scenarios` | List selectable demo scenarios |
| `POST` | `/api/violations/trigger` | Induce a scenario and return its violated topology |
| `POST` | `/api/violations/evaluate` | Run and rank the full corrective-action engine |
| `POST` | `/api/violations/apply-custom-action` | Test one manually selected action |

The evaluation response includes `initial_violations`, `ranked_actions`, `recommended_action`, `fully_resolved`, `explanation`, `before_topology`, and `after_topology`, allowing the frontend to render the result without embedding power-system logic.

## 5. Verification Evidence

The committed Checkpoint 3 test suite verifies:

- Nominal CIGRE MV operation has no violations.
- Artificial bus overvoltage and undervoltage are detected with the correct margins.
- Artificial line overload is detected above the 100% thermal limit.
- Curtailment, battery dispatch, and feeder reconfiguration each return an isolated network and a converged post-action power flow.
- The solar-spike and evening-peak scenarios create violations.
- The scoring formula prefers resolved actions, renewable retention, and lower cost.
- The engine evaluates a multi-action candidate pool, returns monotonic ranking, and resolves the solar-spike scenario with an explanation.
- FastAPI scenario, trigger, evaluation, and custom-action endpoints return the expected structured payloads.

The frontend implementation provides the required live interaction path: choose a scenario, trigger it, inspect the red/amber violation state, run the engine, compare candidates, and toggle to the recommended after-state.

## 6. Acceptance Criteria

- [x] Violation detector flags artificially forced voltage and line-loading violations.
- [x] All three required corrective action types are independently runnable and produce valid post-action power-flow results.
- [x] The engine tries multiple candidate magnitudes and returns the full ranked comparison.
- [x] At least one scenario is fully resolved and includes a plain-English explanation of the recommendation.
- [x] The React UI can trigger scenarios and display the before/after topology comparison.
- [x] The UI exposes the action comparison and custom-action controls.
- [x] `tests/test_violations.py` covers the Checkpoint 3 backend and API behavior.

## 7. Scope Boundary and Known Deviations

- Checkpoint 3 contains three triggerable scenarios. The PRD's four-scenario suite, including a deliberately infeasible case with honest partial mitigation, is explicitly Checkpoint 4 scope and is not claimed here.
- The implementation uses `0.94 p.u.` as the lower operating threshold (`DEFAULT_V_MIN_PU`), consistent with the existing Checkpoint 1 baseline and the Checkpoint 3 UI labels. The PRD and project knowledge base also describe the conventional `0.95-1.05 p.u.` band. This threshold should be standardized in a later cleanup so the code, UI, tests, and documentation use one agreed limit.
- The battery is an operational storage stand-in, not an electrochemical degradation model. Its cycling cost is represented by the documented cost proxy.
- The scenario multipliers are deterministic demonstration inputs, not a full scenario/time-series runner. Scenario persistence and the explicit infeasible case remain Checkpoint 4 work.

## 8. Next Checkpoint

Checkpoint 4 should add the complete scenario suite, including the deliberately infeasible case, persist scenario artifacts, make unresolved outcomes impossible to mistake for success, and complete the final demo/readme polish pass.