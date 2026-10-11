# VoltPredict: Features, Functions, and AI Systems

This guide describes the major user-facing features and the models actually implemented in the repository. It distinguishes learned models from optimization algorithms and physical simulation so that a model's role is not overstated.

## 1. System Overview

VoltPredict is a React/Vite control-room interface backed by a FastAPI service and Python power-system modules. The electrical network is the pandapower CIGRE medium-voltage benchmark with distributed energy resources (DERs). Solar history is sourced from PVGIS where available; customer demand includes a deterministic synthetic profile.

The main layers are:

| Layer | Main implementation | Responsibility |
|---|---|---|
| Frontend | `frontend/src/App.jsx`, `frontend/src/components/` | Dashboard, forecasts, grid actions, MPC, model screens, showcase, and assistant UI |
| API | `api.py` | REST endpoints connecting the interface to forecasting, planning, verification, scenarios, assistant, and evidence export |
| Legacy grid/control core | `src/grid.py`, `src/engine.py`, `src/control/` | CIGRE network, candidate actions, rolling-horizon controller, screening, and episodes |
| Update1 services | `backend/app/` | Telemetry, LightGBM operating-point surrogate, eight-step MPC, grounded assistant, and artifact export |
| Data and artifacts | `data/`, `models/`, `backend/models/`, `outputs/`, `artifacts/` | Training data, saved models, scenarios, and verification evidence |

## 2. User-Facing Features

The primary navigation and screen composition are defined in [AppShell.jsx](frontend/src/components/layout/AppShell.jsx) and [App.jsx](frontend/src/App.jsx).

| Screen | What it does | Main implementation |
|---|---|---|
| **Daily story** | Runs and displays a 12-step grid showcase with labeled operating events and evidence. | [ShowcasePanel.jsx](frontend/src/components/ShowcasePanel.jsx), [showcase.py](src/control/showcase.py) |
| **Dashboard** | Combines summary/status views for the grid and available dashboard panels. | [DashboardOverview.jsx](frontend/src/components/layout/DashboardOverview.jsx) |
| **Grid status** | Shows CIGRE bus, line, and DER information, voltage/loading status, topology, and solar/load time series for a selected date range. | [NetworkTopologyCanvas.jsx](frontend/src/components/NetworkTopologyCanvas.jsx), [TimeSeriesChart.jsx](frontend/src/components/TimeSeriesChart.jsx), [grid.py](src/grid.py) |
| **Forecasts** | Displays solar and load predictions against observations and naive baselines, with forecast evaluation and retraining controls. | [ForecastPanel.jsx](frontend/src/components/ForecastPanel.jsx), [forecast.py](src/forecast.py) |
| **Grid actions** | Triggers operating scenarios, evaluates candidate corrective actions, compares outcomes, and reports residual violations. | [ViolationEnginePanel.jsx](frontend/src/components/ViolationEnginePanel.jsx), [engine.py](src/engine.py), [scenarios.py](src/scenarios.py) |
| **Plan over time** | Runs an eight-step rolling-horizon control episode, with battery state-of-charge, action, verification, and replanning results. | [TimePlanPanel.jsx](frontend/src/components/TimePlanPanel.jsx), [episode.py](src/control/episode.py) |
| **Plan settings** | Lets the operator set initial battery energy, request an eight-step 15-minute MPC plan, inspect each step, update the surrogate, and export evidence. | [MpcControlPanel.jsx](frontend/src/components/MpcControlPanel.jsx), [mpc_engine.py](backend/app/mpc_engine.py) |
| **Prediction quality** | Runs model screening/evaluation and baseline-versus-screened comparisons; shows candidate classifications and plan details. | [SurrogatePanel.jsx](frontend/src/components/SurrogatePanel.jsx), [SurrogateScreeningPanel.jsx](frontend/src/components/SurrogateScreeningPanel.jsx) |
| **Digital Grid Assistant** | Answers operator/executive questions using bounded project tools and evidence-backed fallback responses. | [ChatWidget.jsx](frontend/src/components/ChatWidget.jsx), [agent_orchestrator.py](backend/app/agent_orchestrator.py) |
| **Theme and responsive layout** | Provides light/dark/system theme preferences, desktop/mobile navigation, and responsive chart/panel layout. | [ThemeToggle.jsx](frontend/src/components/layout/ThemeToggle.jsx), `frontend/src/theme/` |

## 3. Machine-Learning Models

There are three separate power/forecast model implementations. They have different feature schemas, model artifacts, APIs, and jobs; they are not interchangeable.

### 3.1 Hourly solar and load forecasting

**Exact estimator:** `LightGBMForecaster` in [src/forecast.py](src/forecast.py).

- Trains two separate gradient-boosted decision-tree regressors: one for `solar_pu`, one for `load_pu`.
- When LightGBM is installed, uses `lightgbm`'s native `lgb.train` with `objective="regression"`, `boosting_type="gbdt"`, 150 boosting rounds, learning rate `0.05`, 31 leaves, and seed `42`.
- If LightGBM cannot be imported, uses `sklearn.ensemble.GradientBoostingRegressor` with 150 estimators, depth 3, Huber loss, and seed `42`.
- Features include hourly lags `t-1`, `t-2`, `t-3`, and `t-24`; hour, weekday, day-of-year, month, weekend flag; cyclical hour/day-of-year encodings; and a trailing 24-hour mean.
- Uses a chronological split, defaulting to the latest 20% as holdout. Reports MAE, RMSE, and R-squared alongside lag-1 persistence and lag-24 seasonal-persistence baselines.
- Saves solar/load models and metrics under `data/processed/models/`; the forecast API reloads them rather than training on every request.

**Important resolution note:** `backend/app/forecast_adapter.py` recursively predicts hourly values and interpolates them into eight 15-minute MPC points. The model is hourly-trained; it is not a quarter-hour-trained neural network. The response includes provenance and 90% uncertainty bounds.

### 3.2 Checkpoint 6 neural power-flow ensemble

**Exact architecture:** `PowerFlowSurrogateMLP`, a PyTorch `torch.nn.Module`, in [src/surrogate/train.py](src/surrogate/train.py).

- A three-model ensemble uses random seeds `42`, `43`, and `44` (`SurrogateEnsemble`).
- Input is 33 features: 15 bus active-power injections, 15 bus reactive-power injections, and three tie-switch states.
- The shared MLP has 128-unit and 128-unit SiLU layers, then a 64-unit SiLU layer.
- Four output heads predict 15 bus voltages, 14 line loadings, a minimum safety margin, and an unsafe logit.
- The ensemble averages predictions and estimates uncertainty using disagreement in minimum-margin prediction across its three models.
- Training samples are labeled by the pandapower AC solver. `src/surrogate/sampling.py` uses SciPy `qmc.LatinHypercube` sampling and produces development/validation and test manifests, including unseen, extended, and near-limit splits.
- The saved checkpoint is normally `models/surrogate_ensemble.pt`; the screener loads it through `load_surrogate_ensemble`.

**How it is used:** `SurrogateScreener` in [src/control/screener.py](src/control/screener.py) classifies candidates as `safe`, `unsafe`, `uncertain`, or `unsupported`. Only an `unsafe` candidate is dropped before AC verification. `safe` candidates still go through the physical verifier before they can be selected. `uncertain` and `unsupported` candidates also go to the solver. If PyTorch or the checkpoint cannot load, the screener falls back to uncertain/unsupported results rather than claiming learned screening.

### 3.3 Update1 LightGBM power-flow surrogate

**Exact estimator:** `backend.app.surrogate.PowerFlowSurrogate`, which trains independent `lightgbm.LGBMRegressor` estimators.

- Trains one regressor for each output: 15 bus-voltage outputs and 14 line-loading outputs (29 regressors total).
- Input features are `solar_mw`, `load_mw`, `curtailment_fraction`, `battery_charge_mw`, `battery_discharge_mw`, and `load_shed_mw`.
- Training inputs are labeled with pandapower solver results. Training records include boundary operating cases as well as randomized cases; feature minima/maxima are saved for out-of-distribution (OOD) checks.
- The class is persisted as a joblib bundle at `backend/models/surrogate.joblib` by default. `POST /api/update1/surrogate/train` retrains it; `GET /api/update1/surrogate/status` reports availability and metrics.
- `backend.app.mpc_engine.MpcEngine` can use predictions to score candidate controls. If the model is unavailable, a candidate is OOD, or a prediction cannot be used, it falls back to a conservative heuristic cost. Regardless of prediction, every selected MPC step is checked by the AC solver.

This model is **not** the Checkpoint 6 PyTorch ensemble. The two models have different features, output shapes, artifact files, training routes, and screen/controller integrations.

## 4. Assistant and Other AI

### 4.1 Tool-grounded language assistant

**Exact integration:** LangChain `StructuredTool` plus `langchain_openai.ChatOpenAI`, sent through OpenRouter.

- Default configured model: `openai/gpt-4o-mini` (`OPENROUTER_MODEL` can override it).
- Default OpenRouter-compatible base URL: `https://openrouter.ai/api/v1`; an API key is optional for local operation.
- The model is used to interpret and explain questions, not to calculate power flow or directly choose dispatch actions.
- Bounded tools include `get_telemetry_status`, `verify_state_with_solver`, `run_8step_mpc_plan`, `export_hackathon_artifacts`, `search_project_knowledge`, `get_scenario_result`, and `list_available_scenarios`.
- The provider/tool loop is limited to four rounds. When the API key is missing or the provider fails, deterministic keyword-based responses invoke local tools and expose the returned evidence.
- Operator mode preserves engineering measurements and IDs; executive mode summarizes impacts in plain language.

### 4.2 Not used for grid control

The forecasting and planning code does not use an LSTM, Transformer, generative model, or reinforcement-learning policy. The language model is an assistant interface only. The control decisions are made by deterministic candidate scoring/beam search and then checked against the power-system solver.

## 5. Deterministic Planning, Grid Physics, and Safety

These are important AI-adjacent features, but they are algorithms and simulation rather than trained ML models.

### 5.1 CIGRE network and AC solver

- `src.grid.load_cigre_network()` loads pandapower's `create_cigre_network_mv(with_der="all")` network.
- `src.control.verifier.Verifier` and `backend.app.solver_verifier.SolverVerifier` run AC power flow using pandapower's Newton-Raphson (`algorithm="nr"`) method.
- The configured safe voltage band is `0.95–1.05 p.u.` and the maximum line/transformer loading is `100%`.
- Non-converged solver results are reported as unsafe/failure, not as a safe prediction.
- The neural and LightGBM surrogates do not replace this solver as the final authority for selected actions.

### 5.2 Corrective-action ranking

`src.engine` implements a propose → verify → rank workflow. It detects voltage/thermal violations, generates candidate setpoints and control actions, runs the AC solver for each candidate, and ranks results based on constraint resolution, renewable retention, and a cost proxy. `src.actions` applies isolated modifications such as PV curtailment, battery dispatch, feeder reconfiguration, and voltage-setpoint changes.

### 5.3 Rolling-horizon episode planner

`src.control.planner.BeamSearchPlanner` runs a configurable-width beam search over battery, curtailment, and (at the immediate step) switch actions. It tracks battery SOC and switch budget, screens candidate states when a screener is supplied, and uses a fallback ladder when normal candidates are unsafe. `src.control.episode.run_episode` applies actions, verifies the observed step, records SOC and evidence, and replans for injected forecast changes or unsafe observations.

### 5.4 Update1 MPC

`backend.app.mpc_engine.MpcEngine` searches eight 15-minute forecast steps (two hours) with beam search. It respects a 4 MWh battery capacity, 2 MW maximum charge/discharge, 95% charge/discharge efficiency, and 15-minute step duration. Candidate controls include curtailment, battery dispatch, and load shedding. A sequential fallback ladder attempts battery support, curtailment, and load shedding if a selected step fails physical verification.

### 5.5 Scenarios and showcase

The scenario runner supports `solar_spike`, `evening_peak`, `cloudy_drop`, and `infeasible`. The engine also defines `line_congestion` as an action-engine scenario. The deliberately infeasible case is reported as unresolved when residual violations remain.

The 12-step showcase is a deterministic demonstration, not a live operating trace. It labels forecast error, battery saturation/depletion, near-limit voltage, infeasibility/fallback, and a surrogate disagreement demonstration. Some showcase event values are deliberately constructed or forced to make the demonstration repeatable; consult its source and evidence before interpreting them as measured field data.

## 6. Data Sources and Forecasting Pipeline

- **Solar:** Pune coordinates (18.52° N, 73.85° E). `src.data_pipeline.fetch_pune_solar_data` first uses PVGIS through `pvlib`; if unavailable it tries the Open-Meteo archive/forecast API, then a deterministic clear-sky approximation. Responses are cached under `data/raw/`.
- **Demand:** `generate_synthetic_load_profile` creates a seeded diurnal residential demand series; this is synthetic unless a configured telemetry feed is used.
- **Alignment:** solar and demand are aligned into a processed time series under `data/processed/aligned_solar_load.csv` for forecasting/training.
- **Telemetry:** `TelemetryManager` reads a configured read-only `GRID_API_URL`. If no URL is configured or the feed fails, it returns deterministic mock telemetry. Stale readings or forecast drift above the configured threshold (default 15%) flag a replan.
- **MPC forecast:** the hourly forecasters recursively produce future points; the adapter maps per-unit solar/load values to aggregate CIGRE MW values and attaches uncertainty intervals/provenance.

## 7. Major Backend Functions and API Groups

| Function or endpoint | Purpose |
|---|---|
| `src.forecast.create_feature_matrix` | Builds lag, calendar, cyclical, and rolling-statistic forecasting features. |
| `src.forecast.train_and_evaluate_forecaster` | Trains a solar/load regressor and compares it with persistence baselines. |
| `src.forecast.train_all_models` | Trains, evaluates, and optionally saves both hourly forecasters. |
| `backend.app.forecast_adapter.generate_mpc_forecasts` | Converts recursive hourly predictions to eight 15-minute forecast inputs and uncertainty/provenance. |
| `src.engine.trigger_scenario` / `evaluate_actions` | Applies a scenario and ranks physically checked corrective actions. |
| `src.control.planner.BeamSearchPlanner.plan` | Searches legacy rolling-horizon control actions and returns a solver-verified first action. |
| `src.control.episode.run_episode` | Executes and records a multi-step episode, including SOC, replan, and screening counts. |
| `src.control.ab_testing.run_ab_screening_benchmark` | Compares baseline and surrogate-screened episodes using actual solver/search measurements. |
| `backend.app.mpc_engine.MpcEngine.plan` | Generates and physically verifies the two-hour, eight-step MPC plan. |
| `backend.app.agent_orchestrator.AssistantOrchestrator.answer` | Runs bounded tool calling or the deterministic evidence-backed assistant fallback. |
| `backend.app.artifact_exporter.generate_evidence_bundle` | Trains/loads the Update1 surrogate, runs MPC, and exports model/plan/dataset evidence. |

The main FastAPI endpoint groups are grid and solar/load data (`/api/grid/*`, `/api/data/*`), forecasting (`/api/forecast/*`), corrective actions/scenarios (`/api/violations/*`, `/api/scenarios/run`), multi-step control (`/api/control/episode/*`), surrogate training/status/evaluation (`/api/surrogate/*`), Update1 telemetry/solver/MPC (`/api/update1/*`), assistant (`/api/chat` and `/api/update1/assistant/chat`), and evidence (`/api/evidence/*`, `/api/export-artifacts`). The parameterized comparison route is `POST /api/control/ab-test`; `GET /api/control/ab-test` returns the saved benchmark report when present.

## 8. Evidence, Configuration, and Limitations

- Forecast model files and metrics: `data/processed/models/`.
- Checkpoint 6 PyTorch ensemble: `models/surrogate_ensemble.pt` (requires a compatible PyTorch install and checkpoint).
- Update1 LightGBM surrogate: `backend/models/surrogate.joblib` by default; path is configurable through `Settings.surrogate_model_path`.
- Episode logs and verification/SOC exports: `outputs/evidence/action_logs/`, `outputs/evidence/verification/`, and `outputs/evidence/soc_traces/`.
- Update1 evidence bundle: `artifacts/`, including a LightGBM surrogate bundle, solver benchmark, train/test CSVs, and MPC execution trace.
- Voltage, loading, telemetry, CORS, model paths, and OpenRouter settings are configurable through `backend/app/config.py` and environment variables. See [README.md](README.md) for installation and local startup commands.
- A model being trained or present on disk does not guarantee that it is loaded for a particular screen. Check the screen's status response, model path, OOD/fallback reason, and run evidence. In particular, the Checkpoint 6 PyTorch screener and Update1 LightGBM MPC surrogate are separate systems.
