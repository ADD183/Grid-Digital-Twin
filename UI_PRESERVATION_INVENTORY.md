# UI Preservation Inventory (Phase UI-0 Baseline)

This document establishes the exhaustive inventory of all data fields, controls, API endpoints, polling intervals, and rendering conditions in the VoltPredict React frontend before starting the visual redesign (PRD Section 0.1 & Phase UI-0).

---

## 1. Environment & Technical Baselines
- **Baseline Git Commit Hash:** `3c66e736e58f9cfa2ab1d9fa10b23359928b8270`
- **Build Status (`npm run build`):** Success (Vite v8.3.0 bundle generated in 2.62s)
- **Lint Status (`npm run lint`):** 58 warnings, 0 errors
- **Backend Test Status (`pytest`):** 87 collected items

---

## 2. Component Inventory

### 2.1 `App.jsx` & Shell Navigation
- **Tab IDs (Frozen):** `showcase` (Default), `surrogate`, `time_plan`, `mpc`, `engine`, `forecast`, `grid`, `all`
- **State Variables:** `activeTab`, `dateRange`, `timeSeriesData`, `powerflowResult`, `topologyData`, `loading`, `error`, `apiOnline`, `metricsData`
- **API Endpoints & Polling:**
  - `GET /api/health` (Polling interval: 5,000ms)
  - `POST /api/pipeline/timeseries` (Payload: `{ start_date, end_date }`)
  - `GET /api/grid/topology`
  - `GET /api/grid/powerflow`
  - `GET /api/pipeline/metrics`
- **Render Gates:**
  - If `loading` && `!topologyData`, renders full-screen loading spinner.
  - If `!apiOnline`, renders offline warning banner with retry button (`fetchInitialData`).
  - Active panel rendered conditionally based on `activeTab`.

### 2.2 `Header.jsx`
- **Props:** `apiOnline`
- **Displayed Facts:** Location ("Pune, Maharashtra, India"), Benchmark Grid ("CIGRE MV 15-Bus Grid"), Status ("Backend API Online" / "Backend Offline").

### 2.3 `DateRangePicker.jsx`
- **Props:** `dateRange`, `onApplyDateRange`, `loading`
- **Controls:** Start Date picker, End Date picker, Quick Presets ("7 Days", "14 Days", "30 Days"), "Apply Date Range" button.
- **Displayed Data:** Active range day count calculation.

### 2.4 `MetricCards.jsx`
- **Props:** `metricsData`, `loading`
- **Displayed KPIs:**
  - Solar Generation (`solar_generation_mwh` / `peak_solar_mw`)
  - Grid Demand (`total_demand_mwh` / `peak_load_mw`)
  - Max Voltage (`max_voltage_pu` p.u.)
  - Line Loading (`max_line_loading_pct` %)

### 2.5 `NetworkTopologyCanvas.jsx`
- **Props:** `topologyData`, `powerflowResult`, `onSelectElement`
- **State & Controls:** Bus hover/click selection, Line hover/click selection, Telemetry inspector drawer, Zoom/Pan controls.
- **Thresholds & Status Logic:**
  - Voltage: Safe (`0.95 <= v <= 1.05`), Warning (`0.90 <= v < 0.95` or `1.05 < v <= 1.10`), Violation (`v < 0.90` or `v > 1.10`).
  - Line Loading: Safe (`< 70%`), Warning (`70% - 100%`), Overload (`> 100%`).

### 2.6 `TimeSeriesChart.jsx`
- **Props:** `timeSeriesData`, `loading`
- **Controls:** Units Toggle (`p.u.` vs `Raw MW`), Series Toggle checkboxes (Solar, Load, Net).
- **Displayed Series:** Solar generation, Demand profile, Net load profile.

### 2.7 `TelemetryTables.jsx`
- **Props:** `powerflowResult`, `topologyData`
- **Controls:** View Mode Switcher ("Buses (15)" vs "Lines (15)").
- **Columns:**
  - Buses: Bus ID, Type, Voltage (p.u.), Voltage (kV), Active Power P (MW), Reactive Power Q (MVAr), Violation Status.
  - Lines: Line ID, From Bus, To Bus, Loading (%), Current (A), Active Losses (kW), Status.

### 2.8 `ForecastPanel.jsx`
- **State & Controls:** Target Variable Toggle ("Solar PV" vs "Grid Load"), Window Filter slider/buttons (24h, 48h, 72h, 168h), "Retrain Forecasters" button.
- **API Endpoints:**
  - `GET /api/forecast/chart?target={target}&hours={hours}`
  - `POST /api/forecast/train`
- **Displayed Metrics:** MAE (p.u.), RMSE (p.u.), Naive Baseline MAE, Improvement %, $R^2$ Score.

### 2.9 `ViolationEnginePanel.jsx`
- **State & Controls:**
  - Scenario Selector Cards ("Solar Spike", "Evening Peak", "Cloud Drop", "Infeasible Stress")
  - "Trigger Scenario" button, "Re-run Solver" button
  - Before/After Mitigation Toggle
  - Violation Category Filter ("ALL", "VOLTAGE", "LOADING")
  - Sandbox Controls: Solar Scale slider, Load Scale slider, Battery MW slider, Curtailment % slider, Switch toggles
  - "Simulate Custom Sandbox" button
- **API Endpoints:**
  - `POST /api/control/trigger-scenario`
  - `POST /api/control/evaluate-actions`
- **Displayed Metrics:** Resolved Status, Residual Violations Count, Recommended Action, Ranked Actions List, Before vs After Grid Stats.

### 2.10 `MpcControlPanel.jsx`
- **State & Controls:** Horizon slider (4 - 24 steps), Weighting Sliders (Renewable weight, Battery cycling penalty, Switching penalty, Violation penalty), "Run Predictive MPC Plan" button.
- **API Endpoints:** `POST /api/mpc/plan`
- **Displayed Results:** Optimized dispatch schedule, predicted bus voltages, battery SOC trajectory.

### 2.11 `TimePlanPanel.jsx`
- **State & Controls:**
  - Episode Selector ("Standard 8-Step", "Midday Surge", "Infeasible Stress")
  - "Run Episode" button
  - Interactive Step Selector Slider/Buttons (T0 - T7)
  - Detailed Step Inspector Drawer
- **API Endpoints:** `POST /api/control/episode/run`
- **Displayed Charts & Tables:** SOC Trajectory Chart (Bar + Line), Power Dispatch Breakdown Chart, Replan Event Flags, Step Log Table.

### 2.12 `SurrogatePanel.jsx` & `SurrogateScreeningPanel.jsx`
- **State & Controls:**
  - Sub-tabs: "Surrogate Screening & A/B Benchmark" vs "Model Architecture & Training"
  - Initial SOC Slider, Inject Error checkbox, Mode Select
  - "Run Screened Episode" button, "Run A/B Benchmark" button, "Train Surrogate Ensemble" button
- **API Endpoints:**
  - `GET /api/surrogate/evaluation`
  - `GET /api/control/ab-test`
  - `POST /api/control/episode/run-screened`
  - `POST /api/surrogate/train`
- **Displayed Metrics:** Physical Solver Call Reduction %, Planning Speedup Factor, Action Agreement %, Confusion Matrix (2x2), Parity Plots, Validation MAE/RMSE.

### 2.13 `ShowcasePanel.jsx`
- **State & Controls:**
  - "Run Showcase Episode" refresh button
  - "Download Full Evidence Table (Excel CSV)" button
  - Per-artifact "Open / Download" file action links
- **API Endpoints:**
  - `GET /api/control/episode/showcase12`
  - `GET /api/evidence/index`
  - `GET /api/evidence/export-csv`
  - `GET /api/evidence/download?file_path=...`
- **Displayed Data:** 6 Labeled Event Cards, 12-Step Trajectory Chart (SOC %, V_min, V_max), Step Details Table, Evidence Artifact Map Table.

### 2.14 `ChatWidget.jsx`
- **State & Controls:**
  - Open/Close Floating Toggle
  - Audience Mode Switcher ("Operator / Operator-Friendly" vs "Engineer / Technical Deep-Dive")
  - Prompt Suggestion Chips
  - Message Input & Send Button
  - Tool Details Expand/Collapse Toggle
- **API Endpoints:** `POST /api/assistant/chat`
