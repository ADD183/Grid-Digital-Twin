# Renewable Distribution Grid Digital Twin — Project Knowledge Base
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
                                                                    │  Streamlit frontend │
                                                                    │  (interactive demo) │
                                                                    └───────────────────┘
```

**Backend (`src/`)** is pure Python, independently testable, no UI code inside it — this is what makes the project "defensible": a judge or a test suite can verify the logic works without touching the interface at all.

**Frontend (`app/`)** is a Streamlit app that only *renders* what the backend computes — it never contains simulation or decision logic itself.

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
6. **Live demo** (walk through Scenarios 1–3 via the Streamlit app)
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
