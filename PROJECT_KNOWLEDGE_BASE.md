# VoltPredict — Project Knowledge Base
**Reference document for PPT content, judge Q&A prep, and team onboarding. Sits alongside `PRD_renewable_grid_digital_twin.md` (the build-checkpoint spec) as project documentation.**

---

## 1. One-line pitch

A digital twin of a local power distribution grid that forecasts near-term solar generation and demand, detects when rising rooftop solar will push voltage or equipment limits out of safe range, and automatically compares corrective actions — curtailing solar, using battery storage, or switching feeders — to keep the grid safe while wasting as little clean energy as possible.

---

## 2. The problem, in plain English (no power-systems background needed)

Picture a residential street where a lot of houses have installed rooftop solar panels. On a sunny afternoon, all those panels are pushing electricity *back into* the grid at the same time that actual household demand is low (everyone's at work). Two things can go wrong:

- **Voltage rises too high.** The grid is built to deliver power *to* houses at a stable voltage. When many houses are pushing power *back*, voltage on that section of the network can rise above safe limits — this can damage appliances and trip safety equipment.
- **Equipment overloads.** Cables and transformers are rated to carry a certain amount of current. A sudden surge of solar export (or, in the evening, everyone switching on AC/EVs at once) can push that current above the rated limit, which causes overheating and accelerates equipment wear.

The utility's usual fix is conservative: cap how much solar a given area is allowed to export, regardless of whether it's actually needed on any given day. That wastes clean energy. Our project is a smarter middle ground: predict the problem before it happens, and choose the *least wasteful* fix available at that moment.

---

## 3. Our solution — how it works, step by step

1. **Forecast** — predict solar output and household demand for the next hour(s), using a real trained model validated against historical data (not just live snapshot readings).
2. **Simulate** — feed that forecast into a power-flow calculation (the actual physics engine of the grid — voltage drops, current flow) to see what conditions would result.
3. **Detect** — check the simulated results against safe operating limits (voltage band, equipment loading).
4. **Propose & compare** — if a violation is predicted, try multiple corrective actions (reduce solar export, use a battery, reroute via a different feeder), re-simulate each, and rank them by how well they fix the problem and how much clean energy they preserve.
5. **Report honestly** — show the recommended action, and in at least one scenario, show a case where *no* action can fully fix the problem — an honest limitation, not a hidden one.

Checkpoint 2 currently completes the first step with LightGBM/scikit-learn forecasting, chronological holdout evaluation, persisted model artifacts, and an interactive forecast panel in the React control room. The power-flow and corrective-action steps remain later checkpoints.

This loop (forecast → simulate → detect → propose → verify) is the whole "digital twin" — a live, predictive model of the grid rather than a static diagram.

---

## 4. System architecture

```
 ┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌───────────────────┐
 │  Data layer │ --> │  Forecaster  │ --> │  Power-flow     │ --> │  Corrective-action │
 │ (solar+load)│     │ (ML model)   │     │  engine         │     │  engine            │
 └─────────────┘     └──────────────┘     │ (pandapower)    │     │ (compare & rank)   │
                                            └────────────────┘     └───────────────────┘
                                                                              │
                                                                              v
                                                                    ┌───────────────────┐
                                                                    │ React/FastAPI UI  │
                                                                    │  (interactive demo) │
                                                                    └───────────────────┘
```

**Backend (`src/`)** is pure Python, independently testable, no UI code inside it — this is what makes the project "defensible": a judge or a test suite can verify the logic works without touching the interface at all.

**Frontend:** Checkpoint 1 established the active UI as a React/Vite SPA under `frontend/`, backed by the FastAPI server in `api.py`. The legacy Streamlit surface remains under `app/` for reference and compatibility. Both surfaces only render backend results; simulation and forecasting logic stays in `src/`.

This split is built checkpoint by checkpoint (see `PRD_renewable_grid_digital_twin.md`):
1. Grid + data foundation + live network diagram
2. Forecasting model + forecast-vs-actual chart
3. Violation detection + corrective-action engine + interactive trigger/comparison view
4. Full scenario suite + honest failure case + polished demo

---

## 5. Domain glossary (for PPT text and judge Q&A)

| Term | Plain-English meaning |
|---|---|
| **Distribution grid** | The "last mile" network delivering power from substations to homes/businesses — as opposed to long-distance transmission lines. |
| **DER (Distributed Energy Resource)** | Small-scale generation connected at the local level — rooftop solar, small wind, batteries. |
| **Power flow / `runpp`** | The core physics calculation: given generation and demand at every point, what is the resulting voltage and current everywhere in the network? |
| **Voltage (pu — per unit)** | Voltage expressed as a fraction of the network's nominal (design) voltage. 1.0 pu = exactly nominal. Our safe band is 0.95–1.05 pu (±5%), a standard distribution-grid tolerance. |
| **Line loading %** | How much current is flowing through a cable/transformer relative to its rated maximum. Over 100% means it's carrying more than it's rated for — a thermal/overload risk. |
| **Curtailment** | Deliberately reducing how much power a solar installation is allowed to export, to relieve a violation. Cheapest to implement, but wastes clean energy. |
| **Feeder** | A specific line/branch of the network supplying a group of customers. "Feeder reconfiguration" means switching which feeder supplies a section of the network, to rebalance load. |
| **Battery dispatch** | Charging a battery (absorbing excess solar) or discharging it (supporting demand) to relieve a violation without wasting the energy outright. |
| **CIGRE MV network** | A standardized, internationally recognized benchmark distribution network (published by CIGRE Task Force C6.04.02) used in academic/industry research specifically to study renewable integration. We use this instead of inventing our own topology because it's a defensible, peer-reviewed reference case. |
| **PVGIS** | A free, public solar-resource database (EU Joint Research Centre) providing historical solar generation estimates for any location worldwide, including India. |
| **Optimal power flow (OPF)** | A more advanced calculation that finds the mathematically optimal generation/action to minimize a cost — used here (if time allows) only as a benchmark to show how close our engine's recommendation is to the theoretical best. |

---

## 6. Data sources and why each was chosen

| Data | Source | Why this one |
|---|---|---|
| Grid topology | `pandapower`'s built-in CIGRE MV network with DER | No real Indian feeder data is publicly available at this granularity — every utility's actual network is proprietary/regulated. CIGRE's benchmark is the standard substitute used in published research on exactly this problem (renewable integration into MV distribution networks). |
| Solar generation history | PVGIS (via `pvlib`), Pune coordinates | Free, no API key, globally covers India, backed by a recognized institution (EU JRC), so it's defensible as "real data" rather than something we invented. |
| Load (demand) profile | Hand-built synthetic curve (morning ramp, evening peak, overnight trough) | Load profiles are inherently synthetic in nearly all published grid research — real per-household smart-meter data isn't publicly available either. We document the shape assumption transparently rather than pretending it's measured. |

---

## 7. Forecasting approach and why

- **Model:** gradient-boosted trees (LightGBM, or `GradientBoostingRegressor` as a fallback) on lagged values + calendar features (hour of day, day of year). Chosen over deep learning (LSTM) because it trains fast, is easy to explain in one sentence to a judge, and is a strong, standard baseline for this kind of short-horizon tabular forecasting problem.
- **Validation:** the model is tested against the *last 2–4 weeks* of historical data it never saw during training (a chronological, not random, split — this matters because shuffling time series data leaks future information into training). We report MAE/RMSE, and compare against a naive "predict = last known value" baseline, so the improvement is provable rather than asserted.
- **Why this satisfies the problem statement:** the PS explicitly asks for prediction validated against historical test periods, not just a live snapshot — the chronological holdout is exactly that.

---

## 8. The three corrective actions, explained

1. **Curtailment** — turn down solar export at the offending point. Fast and simple, but directly wastes clean energy — the "last resort" option philosophically, even though it's the easiest to implement.
2. **Battery dispatch** — charge a battery to absorb excess solar (fixing overvoltage) or discharge it to support demand (fixing undervoltage/overload). Preserves the clean energy, but limited by battery capacity and adds wear/cycling cost.
3. **Feeder reconfiguration** — reroute which line supplies a section of the network, rebalancing load without touching generation at all. Free from an energy-waste perspective, but only possible where the network topology actually allows a switch — not always available.

The engine tries all three (at a few magnitudes each), re-simulates, and ranks them on: does it fully resolve the violation, how much renewable output is preserved, and a simple cost proxy — this three-way comparison is a direct requirement from the problem statement ("compare at least a few corrective actions").

---

## 9. The four demo scenarios

1. **High solar / low load (midday, sunny)** — the classic overvoltage/export case. Demonstrates curtailment vs. battery trade-off.
2. **Evening peak load, low solar** — classic overload/undervoltage case, when solar can't help and the grid is under real demand stress.
3. **Cloudy day / rapid solar drop** — tests how fast-responding actions (battery) outperform slower ones when conditions change quickly, and shows the forecaster earning its keep.
4. **Deliberately infeasible scenario** — a violation large/widespread enough that no available action (or combination, within realistic limits) fully resolves it. The system reports this honestly: "unresolved, best partial mitigation was X, residual violation Y" — this is a direct, explicit requirement in the problem statement, and it's also good engineering practice to show rather than hide.

---

## 10. Problem-statement → deliverable mapping (use this to check completeness)

| PS requirement | Where it's satisfied |
|---|---|
| Connects a network model to time-based solar/demand data | Checkpoint 1 — CIGRE network + PVGIS + synthetic load, time-aligned |
| Predicts near-term generation and demand | Checkpoint 2 — LightGBM forecaster, chronologically validated |
| Runs power-flow calculations to detect problems | Checkpoint 1 & 3 — `pandapower.runpp`, voltage/loading checks |
| Compares at least a few corrective actions | Checkpoint 3 — curtailment, battery, feeder switching, ranked |
| Clear before/after demonstration across multiple scenarios | Checkpoint 4 — 4+ scenarios, before/after diagrams and metrics |
| Honestly reports a failure/infeasible scenario | Checkpoint 4 — dedicated infeasible scenario, clearly labeled |

---

## 11. Known limitations (say these proactively — it builds credibility)

- The network topology is a standard academic benchmark (CIGRE), not a real Indian feeder — because no public data exists at that granularity anywhere.
- The load profile is synthetic, shaped on typical residential/commercial demand patterns, not measured smart-meter data.
- The "battery" is a simplified model (documented in `NOTES.md`), not a full electrochemical/degradation model.
- The forecaster is a short-horizon (next-hour) model; it isn't attempting day-ahead or seasonal forecasting.
- Optimal power flow (`runopp`), if included, is a comparison benchmark only — not guaranteed to converge on every scenario, so it's not load-bearing for the core demo.

## 12. Future work (good for a "what's next" slide)

- Extend to a low-voltage (household-level) network for a more granular rooftop-solar story
- Add real smart-meter or DISCOM load-curve data if/when available
- Multi-hour/day-ahead forecasting horizon
- A genuine battery degradation/cost model for more realistic action scoring
- Multi-agent coordination across multiple feeders simultaneously

---

## 13. Suggested PPT structure (map slides to sections above)

1. **Title + one-liner** (§1)
2. **The problem, in plain English** (§2) — use the "sunny afternoon, everyone's panels exporting" framing, it's intuitive without jargon
3. **Our approach — the 5-step loop** (§3) — forecast → simulate → detect → propose → verify
4. **Architecture diagram** (§4)
5. **Data & model choices, briefly** (§6, §7) — 1 slide, keep technical detail light, this is what NOTES.md is for if asked
6. **Live demo** (walk through Scenarios 1–3 via the React control room)
7. **The honest failure case** (§9, scenario 4) — a dedicated slide; judges respond well to teams that show a limitation deliberately
8. **Problem-statement checklist** (§10) — a single slide directly mapping requirements to what was built; makes evaluation easy for judges
9. **Limitations + future work** (§11, §12)

---

## 14. Anticipated judge questions and short answers

- **"Why this network instead of a real Indian grid?"** → No public Indian feeder data exists at this granularity; CIGRE MV is the standard academic benchmark specifically built to study DER/renewable integration, so it's the defensible choice.
- **"Why 0.95–1.05 pu?"** → Standard distribution-grid voltage tolerance band (±5% of nominal).
- **"How do you know your forecaster is actually good, not just fit to the data?"** → Chronological holdout on 2–4 weeks the model never trained on, benchmarked against a naive baseline, MAE/RMSE reported.
- **"What happens when nothing can fix the problem?"** → We show this explicitly as one of our four scenarios — the system reports the best partial mitigation and the residual violation rather than pretending it solved it.
- **"Is this just calling a library, or did you build something?"** → The physics (`pandapower`) and data pulls (PVGIS) are libraries by design — reinventing power-flow math isn't the point of a 24-hour hackathon. What we built is the forecasting pipeline, the violation-detection logic, the propose→verify→repair corrective-action engine, and the scenario framework tying it together into a decision-support tool.
- **"Could this scale to a real utility?"** → The architecture (forecast → simulate → detect → compare actions) is topology-agnostic — swapping in a real feeder model and real smart-meter data wouldn't require redesigning the approach, just re-pointing the data layer.

---

# PART II — FINAL ROUND ADDITIONS
*(Append this to `PROJECT_KNOWLEDGE_BASE.md`. Numbers marked **[fill in]** should be replaced with real results from the evidence pack after Checkpoint 8.)*

---

## 15. What changed in the final round

Round 1 answered: *"Given a forecast, is the grid safe right now, and which single corrective action is best?"*

The final round asks a harder, more realistic question: *"Over the next several hours, what sequence of actions keeps the grid safe, given that batteries run out, forecasts are wrong, and some periods may be unfixable?"* It also asks us to make that decision process **fast** with a learned model, **without** giving up the safety guarantee of the physical solver.

The network, solar/load data and power-flow checks from round 1 are unchanged. Two things are added on top:

1. **Control across multiple time steps** — a planner that looks ahead at least 8 steps, tracks battery charge, and replans when reality differs from the forecast.
2. **A learned power-flow surrogate** — a small neural network that quickly estimates voltages and line loading, used to screen candidate actions before the physical solver verifies the ones we actually pick.

---

## 16. Addition 1 in plain English: planning over time

**Why one step isn't enough.** A battery is a limited resource. If we use it all at midday to absorb solar, it's empty when the evening peak arrives and we need it most. Likewise, switching a feeder or curtailing solar has consequences for later hours. Good decisions need lookahead.

**How it works.**
1. At each time step the planner looks ahead 8+ steps using the forecast.
2. It considers sequences of actions: battery charge/discharge level, curtailment level (0 / 10 / 25 / 50%), and permitted switching (limited by a switching budget).
3. It scores sequences by renewable energy used, minus penalties for switching, battery wear and any violations. Hard limits (battery charge range, power limits, network limits) can never be broken.
4. It executes **only the first action**, then observes what actually happened (real solar and load differ from the forecast), and **replans** from the new situation. This "plan, act, observe, replan" pattern is called a rolling horizon (also known as model predictive control).
5. Every action actually taken is checked by the physical power-flow solver before it's presented as safe.

**When nothing works.** If no action sequence keeps the grid within limits, the system doesn't pretend. It runs an explicit fallback ladder (maximum battery support, then maximum curtailment at the offending generator, then an alternate switch configuration). If problems remain, that time period is marked **infeasible**, with the residual violation reported.

**Why beam search.** The planner keeps only the best few partial plans at each step (the "beam") instead of exploring every combination. It is easy to explain, works with the physical solver inside the loop, and avoids the complexity of reformulating the network as a mathematical optimization problem. Trade-off: it is a heuristic and not guaranteed to find the global optimum, and we say so.

---

## 17. Addition 2 in plain English: the surrogate

**The problem it solves.** The physical solver is accurate but each run costs time, and a planner exploring many candidate sequences calls it thousands of times. A surrogate is a small neural network trained to imitate the solver: given the generation, load and switch settings, it predicts bus voltages and line loadings almost instantly.

**The critical rule: the surrogate screens, the solver decides.** The surrogate is allowed to throw out candidates that are clearly unsafe, saving solver calls. It is never allowed to declare an action safe on its own. Every action we present goes through the physical solver.

**Safety mechanisms around the surrogate.**
- **Guard band:** we only treat a candidate as "safe" if its predicted distance to the limit exceeds a margin calibrated from validation errors. Close calls go to the solver.
- **Ensemble disagreement:** three independently trained copies are used; if they disagree strongly, the candidate is treated as uncertain and sent to the solver.
- **Supported operating range:** the surrogate is only trusted for inputs inside the range it was trained on. Anything outside is routed straight to the solver ("unsupported input fallback").
- **Disagreement handling:** if the surrogate says safe but the solver says unsafe, we log it as a disagreement event, show the solver's response, and the planner moves to the next candidate.

**How we evaluate it honestly.**
- Training and testing use **different operating ranges or parameter combinations**, not a random split of the same data.
- Test sets: unseen combinations inside the training range, a wider extrapolation range, and a dedicated **near-limit set** (states close to equipment limits, where mistakes matter most).
- Metrics reported: prediction error (voltage in per-unit, loading in %), **unsafe states mistaken for safe** (count and rate, with and without the guard band), fraction of inputs flagged unsupported, and execution time versus the physical solver.
- Honest caveat on speed: on a small network the solver is already quick, so the surrogate's advantage appears mainly when many candidates are screened in a batch. We report single-state and batch timings separately.

---

## 18. Updated architecture (final round)

```
Forecaster -> Candidate generator (planner: beam search over 8+ steps, battery SOC, limits)
                  |
                  v
          Surrogate screener  -- unsupported / uncertain --> Physical solver (pandapower)
          (drops clearly unsafe)                                   |
                  |                                                v
                  +-------- chosen action --------------> Solver verification (mandatory)
                                                                   |
                                    apply action, observe real solar/load, replan
                                                                   |
                                         Streamlit: Time Plan tab + Surrogate tab
```

Build order (checkpoints): **CP5** multi-step control with solver only, **CP6** surrogate data/training/evaluation, **CP7** surrogate-screened planning with A/B comparison, **CP8** showcase scenario and evidence pack.

---

## 19. Additional glossary

| Term | Plain-English meaning |
|---|---|
| **State of charge (SOC)** | How full the battery is, as a percentage of its capacity. We keep it within configured minimum and maximum bounds. |
| **Battery saturation** | Battery is full, so it can no longer absorb excess solar; surplus must go somewhere else (e.g., curtailment). |
| **Battery depletion** | Battery is at its minimum charge and can't support the evening peak. |
| **Rolling horizon / MPC** | Plan several steps ahead, execute only the first step, observe, and plan again. |
| **Beam search** | A search that keeps only the best few partial plans at each step, rather than every possibility. |
| **Switching budget** | A limit on how many feeder switching operations are allowed in a planning window (switching is disruptive and wears equipment). |
| **Fallback ladder** | The ordered list of emergency measures tried when no normal action works. |
| **Infeasible period** | A time step where no allowed action can bring the network within limits. |
| **Surrogate model** | A fast learned approximation of the physical power-flow solver. |
| **Guard band** | A safety margin added when screening: the surrogate must predict "safe by at least this much" before we skip the solver's opinion on a close call. |
| **Ensemble disagreement** | Spread between predictions of several independently trained models; high spread signals low confidence. |
| **Supported operating range** | The region of inputs the surrogate was trained on and is trusted for. |
| **False-safe (unsafe mistaken for safe)** | The surrogate calls a state safe when the solver says it violates a limit. This is the most important surrogate error to measure. |
| **Near-limit state** | A network state with voltage or loading very close to a limit, where small errors flip the verdict. |
| **Forecast error (injected)** | A deliberate, labeled deviation between forecast and "observed" values used to demonstrate replanning. |

---

## 20. Final-round design decisions and why

| Decision | Reason |
|---|---|
| Keep the physical solver as the final judge | Required by the brief; also the only defensible way to claim an action is safe. |
| Solver-only planner built first (CP5), surrogate added after | Gives a measurable baseline, so we can show what the surrogate actually changes (solver calls, time) and always have a working demo. |
| Beam search rather than a mathematical optimization model | Works directly with the solver in the loop, is easy to explain, and avoids simplifying the network physics. |
| Small MLP ensemble for the surrogate | Many outputs (every bus and line) suit a single multi-output network; ensembles give a cheap uncertainty signal. |
| Separate dev/test ranges and held-out parameter combinations | The brief requires evaluation on unseen conditions; random splits would overstate performance. |
| Injected (not measured) forecast errors | Controlled, repeatable demonstration of replanning; always labeled as injected. |
| Everything seeded and logged as artifacts | Judges can reproduce results; the brief asks for configurations, splits, artifacts and logs. |

---

## 21. Final-round requirement mapping

| Brief requirement | Where it is satisfied |
|---|---|
| Plan over at least eight steps with SOC, power, network limits, switching/curtailment | CP5 planner, `config/limits.yaml` |
| Replan as observed differs from forecast; show state transitions and before/after power flow | CP5 episode loop, Time Plan tab |
| Identify infeasible periods and fallbacks; validate every action with the solver | CP5 fallback ladder, verification records |
| Generate solver-labeled states and train a surrogate | CP6 sampling and training |
| Use surrogate in candidate evaluation with final solver verification; declare range and fallback | CP7 screener, supported range metadata |
| Evaluate on unseen, near-limit conditions: error, unsafe-as-safe, runtime | CP6 evaluation, Surrogate tab |
| Demonstrate forecast error, battery depletion/saturation, near-limit state, infeasible period, surrogate disagreement | CP8 showcase episode |
| Submit solver configs, splits, artifacts, SOC traces, action logs, error/latency results, verification outputs | CP8 evidence pack and `EVIDENCE_INDEX.md` |

---

## 22. Additional known limitations (say them proactively)

- Beam search is a heuristic; it does not guarantee the globally optimal plan.
- Planning actions are discretized (a few battery and curtailment levels), which limits optimality but keeps the search tractable and explainable.
- The battery model is simplified (capacity, power limit, efficiency; no degradation or temperature effects).
- The surrogate is only valid inside its declared operating range; outside it we fall back to the solver.
- The surrogate is not a safety guarantee. Its false-safe rate is reported (**[fill in]**), which is exactly why the solver verifies every chosen action.
- On this small network the solver is already fast, so the surrogate's speed benefit is mostly in batched screening (**[fill in]** speedup).
- Forecast errors in the demo are injected, not drawn from a live forecasting service.

## 23. Additional future work

- Optimization-based planning (e.g., a mixed-integer formulation) as a comparison to beam search
- Surrogates for larger or multiple coupled feeders; graph-based models that respect network topology
- Active learning: sample more solver-labeled states near limits where the surrogate is least certain
- Battery degradation and cost models in the objective
- Probabilistic forecasts and chance-constrained planning
- Online retraining when observed behavior drifts from the training distribution

---

## 24. Presentation additions (slides for the final round)

1. **What's new:** two upgrades, planning over time and a learned fast screener, with the solver still in charge.
2. **Why one step isn't enough:** the battery-runs-out-in-the-evening story (use the SOC trace from the showcase).
3. **Plan, act, observe, replan:** one diagram of the rolling-horizon loop.
4. **Live demo, showcase episode:** forecast error → replan, battery saturation, battery depletion, near-limit state.
5. **The infeasible period:** show the fallback ladder and the residual violation honestly.
6. **The surrogate:** what it screens and the safety rails (guard band, ensemble, supported range, solver verification).
7. **Surrogate evidence:** parity plot, near-limit performance, false-safe rate, latency (single vs batch), **[fill in]** numbers.
8. **Disagreement moment:** surrogate said safe, solver said no, planner recovered.
9. **A/B result:** solver calls and time with and without the surrogate, same safety outcome.
10. **Requirement checklist** (section 21) and **limitations** (section 22).

---

## 25. Anticipated judge questions (final round)

- **"What if the surrogate is wrong?"** → It can't cause an unsafe recommendation: every chosen action is verified by the physical solver. The surrogate only decides which candidates to look at first. We also measure how often it mislabels unsafe states as safe and add a guard band to push that down.
- **"How do you know the surrogate generalizes?"** → Test sets come from different operating ranges and held-out parameter combinations than training, plus a dedicated near-limit set. Inputs outside the training range are rejected and sent to the solver.
- **"Why not just use the solver for everything?"** → We can, and the A/B comparison shows that. The surrogate reduces solver calls when many candidates are evaluated; the trade-off and measured speedup are reported honestly.
- **"What happens when the battery is empty or full?"** → The state-of-charge limits are hard constraints; saturation pushes the planner toward curtailment, depletion forces other actions, and unfixable cases are marked infeasible with a fallback.
- **"Are the forecast errors real?"** → They are injected and labeled as such, so the replanning behavior can be demonstrated repeatably. The forecaster itself is validated on held-out historical data from round 1.
- **"Is beam search optimal?"** → No, it's a heuristic. We chose it for transparency and solver compatibility; an optimization-based comparison is listed as future work.
- **"What is the surrogate's supported range?"** → The bounds of its development data, stored in the model metadata, plus an ensemble disagreement ceiling. Anything outside triggers solver fallback, and we report how often.