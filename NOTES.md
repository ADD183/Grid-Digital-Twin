# Engineering Assumptions & Judge Q&A Reference (`NOTES.md`)

This document captures key power-systems engineering assumptions and technical rationale for team members, pitch preparation, and judge Q&A.

---

## 1. Why 0.95–1.05 p.u. is used as the safe voltage band
In electrical power distribution systems, voltage is expressed in per-unit (`p.u.`) relative to nominal design voltage (e.g., 15 kV). Standard utility operating codes (EN 50160 / ANSI C84.1) mandate maintaining steady-state bus voltages within **±5% of nominal (0.95 to 1.05 p.u.)**. Voltages above 1.05 p.u. risk damaging household electronics and tripping inverter protection, while voltages below 0.95 p.u. cause brownouts and motor overheating.

## 2. Why line loading >100% matters (Thermal Overload Risk)
Line loading percentage reflects current flow relative to the thermal rating of conductors and transformers. Operating above 100% causes excessive conductor heating, accelerated insulation degradation, physical sag of overhead lines, and eventual thermal breakdown or protective breaker trips.

## 3. Battery Dispatch Simplification
Batteries are modeled as active power injection/absorption elements (`storage` or bidirectionally controlled `sgen`/`load` stand-in in pandapower). Positive dispatch injects power into the bus (discharging), while negative dispatch absorbs excess solar generation (charging).

## 4. Why CIGRE MV + DER Benchmark was chosen
No public Indian distribution feeder data exists at this level of topological detail due to utility regulatory and security constraints. The **CIGRE Medium-Voltage Distribution Network (with DERs)** published by CIGRE Task Force C6.04.02 is the globally recognized academic and industry benchmark specifically designed for studying renewable integration into distribution grids.

## 5. Why the load profile is synthetic
Granular smart-meter household demand data for specific feeders is proprietary to DISCOMs. We use a hand-built synthetic diurnal curve representing typical residential and commercial demand (morning ramp, evening peak 6–10 PM, overnight trough), augmented with realistic Gaussian noise.

## 6. Frontend architecture decision
The original PRD proposed Streamlit for rapid prototyping. Checkpoint 1 instead delivered a React/Vite control room backed by FastAPI, so the active demo surface is the React SPA while `app/streamlit_app.py` remains a lightweight legacy/reference surface. Backend physics, data, and forecasting stay UI-independent under `src/`.

## 7. Forecasting benchmark
Forecasts use a strictly chronological holdout: the final 20% of the time series is never used for fitting. Each model is compared with persistence baselines (the previous hour and the same hour on the previous day); the better naive score is the baseline shown in the UI. Artifacts are persisted with `joblib` so API reads do not retrain models.

## 8. Scenario Overview Notes
- **Scenario 1 (High Solar / Low Load):** Midday peak solar export causing localized overvoltage near feeder ends.
- **Scenario 2 (Evening Peak Load / Low Solar):** High evening residential demand causing voltage sags and line loading thermal stress.
- **Scenario 3 (Cloudy Day Rapid Drop):** Sudden solar drop testing fast-acting battery response and forecasting accuracy.
- **Scenario 4 (Infeasible Violation):** Severe multi-bus overload where no single action fully resolves the constraint, demonstrating honest partial mitigation reporting.
