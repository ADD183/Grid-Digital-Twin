# VoltPredict

An interactive digital twin of a local power distribution network (CIGRE MV benchmark) connected to solar irradiance history for Pune, India (PVGIS) and synthetic customer demand profiles. The system features a defensible Python backend (`pandapower`, `pvlib`) with a FastAPI REST server and an ultra-modern **React.js Single Page Application (SPA)** frontend.

---

## 🚀 Key Features (Checkpoint 1)
- **React.js Control Room SPA:** High-tech glassmorphism dashboard built with React 18, Vite, Lucide Icons, and Recharts.
- **Calendar Date Range Picker:** Interactive HTML5 date picker allowing custom start and end date selection across 1 to 12+ months, with quick preset buttons ("1 Month", "2 Months", "3 Months", "6 Months").
- **Interactive SVG Grid Topology Canvas:** Color-coded node map of CIGRE 15-bus network displaying bus voltages (green = safe 0.95–1.05 p.u., amber/red = warning/violation), animated power flow lines, and telemetry side panel.
- **FastAPI REST Server:** UI-decoupled REST API exposing grid summary, network element DataFrames, and time-aligned solar/demand time-series data.
- **Defensible Clean Architecture:** `src/` backend is completely UI-independent and testable via `pytest` and CLI (`main.py`).

## 🧠 Checkpoint 2: Forecasting
- **Validated solar and load forecasters:** LightGBM gradient-boosted regressors with a scikit-learn `GradientBoostingRegressor` fallback.
- **Leakage-safe feature engineering:** t-1, t-2, t-3, and t-24 lag features plus calendar and rolling statistics.
- **Chronological holdout benchmark:** the latest 20% of the aligned time series is held out; model MAE/RMSE are shown beside a persistence baseline.
- **Persistent artifacts:** trained models and evaluation data are stored in `data/processed/models/` and reloaded by the API without retraining.
- **Forecast control-room panel:** the React SPA provides solar/load toggles, 48-hour/7-day/14-day windows, actual-vs-forecast-vs-naive charts, benchmark metrics, and retraining.

## Predictive Control and Assistant (Update1)
- **Telemetry manager:** Polls a configured read-only REST endpoint with `httpx`; uses a deterministic mock when no feed is configured or a request fails. Forecast drift above 15% or stale telemetry flags replanning.
- **Physical solver verifier:** Runs the existing CIGRE MV network through pandapower AC power flow and checks the PRD voltage/loading limits. A non-converged solve is always reported unsafe.
- **Power-flow surrogate:** LightGBM screens candidate operating points only when inputs are within the training hypercube. OOD or missing-model states fall back to the physical solver. The solver remains the safety authority.
- **Eight-step controller:** Plans eight 15-minute steps, tracks battery energy/efficiency limits, applies bounded curtailment/BESS/load-shedding fallbacks, and records per-step solver evidence. The current model is trained on hourly data; quarter-hour forecasts are interpolated and labeled as such.
- **Dual-audience assistant:** The floating widget supports operator and executive modes. OpenRouter tool calling uses bounded telemetry, solver, MPC, saved-scenario, and approved-document tools; deterministic evidence-backed responses are used when the provider is not configured or fails.
- **Evidence export:** `POST /api/export-artifacts` writes surrogate-vs-solver benchmarks, an eight-step MPC trace, the trained surrogate bundle, and train/test CSVs under `artifacts/`.


The new service modules live in `backend/app/` and are additive. Existing `api.py`, `src/`, React dashboard, CIGRE scenarios, and legacy API routes remain available. External telemetry is not connected until `GRID_API_URL` points to a feed implementing `{timestamp, solar_mw, load_mw, forecast_solar_mw}`.

---

## 🎨 UI Redesign & Design System (Phase UI-0 – UI-4)
The VoltPredict control room frontend was completely overhauled with an enterprise-grade VoltPredict Design System:
- **Design Tokens**: Standardized color tokens (`--color-accent`, `--color-bg-primary`, `--c-solar`, `--c-load`, `--c-forecast`, `--c-baseline`, `--c-soc`, `--c-battery`, `--c-curtail`), typography (Inter/Outfit), spacing, glassmorphism card surfaces, and segmented controls.
- **Theme Engine**: Seamless Light, Dark, and System preference theme switching via `ThemeProvider` with zero FOUC script.
- **Responsive Layout**: Fluid 375px/768px/1280px/1920px breakpoint support across mobile, tablet, desktop, and ultra-wide grid displays.
- **Accessibility & Motion**: WCAG AA color contrast compliance, keyboard focus rings (`:focus-visible`), standard `aria-label` attributes, and `prefers-reduced-motion` CSS animation fallbacks.
- **Draggable Assistant**: Interactive floating AI assistant widget with executive/operator persona switcher, tool calling evidence grounding, and smooth dragging.

---


## 📁 Repository Structure
```
voltpredict/
├── README.md                    # Setup and overview documentation
├── NOTES.md                     # Engineering assumptions log & judge Q&A prep
├── requirements.txt             # Python dependency specification
├── CHECKPOINT_1_REPORT.md       # Checkpoint 1 verification report
├── CHECKPOINT_2_REPORT.md       # Checkpoint 2 verification report
├── api.py                       # FastAPI REST Server
├── backend/app/                 # Update1 settings, telemetry, solver, surrogate, MPC, assistant, exports
├── main.py                      # CLI entrypoint for pure backend validation
├── data/
│   ├── raw/                     # Cached PVGIS solar data
│   └── processed/               # Aligned solar + load time series
├── src/                         # Pure backend logic
│   ├── grid.py                  # Network loading + baseline AC power flow
│   └── data_pipeline.py         # PVGIS fetch + synthetic load generator
├── frontend/                    # React.js SPA (Vite + Recharts + Lucide)
│   ├── src/
│   │   ├── components/          # React components (Header, DateRangePicker, TopologyCanvas, etc.)
│   │   ├── App.jsx              # Main React SPA container
│   │   └── index.css            # Dark mode glassmorphism styles
│   ├── package.json
│   └── vite.config.js
└── tests/
    └── test_grid.py             # Pytest unit test suite
```

---

## 🛠️ Quickstart & Execution

### 1. Install Dependencies
```bash
# Python dependencies
pip install -r requirements.txt

# Configure optional integrations: create .env only if it does not already exist.
# If .env exists, merge any needed names from .env.example; do not overwrite secrets.
if not exist .env copy .env.example .env

# Node.js dependencies
cd frontend
npm install
```

### 2. Start Backend REST API
```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

### 3. Launch React Frontend SPA
```bash
cd frontend
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

### 4. Run Automated Test Suite
```bash
python -m pytest tests -q
```

### 5. Build the React frontend
```bash
cd frontend
npm run build
```

The forecast panel is available from the **AI Forecaster (Checkpoint 2)** tab after the FastAPI server is running.

## Update1 API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Deployment health with UTC timestamp |
| `GET` | `/api/update1/telemetry` | Latest telemetry, drift, freshness, and fallback state |
| `GET` | `/api/update1/forecast/horizon?steps=8` | Recursive forecast inputs plus resolution/scaling provenance |
| `POST` | `/api/update1/solver/verify` | AC solver verification for one operating point |
| `POST` | `/api/update1/surrogate/train` | Generate CIGRE solver samples and train the surrogate |
| `GET` | `/api/update1/surrogate/status` | Model availability and validation metrics |
| `POST` | `/api/update1/mpc/plan` | Physically verified eight-step plan |
| `POST` | `/api/update1/assistant/chat` | Tool-grounded answer; select persona with `X-Audience-Mode: operator|executive` |
| `POST` | `/api/export-artifacts` | Export the hackathon evidence bundle |

The API and frontend can run in containers. From the repository root, build the backend with `docker build -f backend/Dockerfile -t voltpredict-api .`; build the frontend with `docker build -f frontend/Dockerfile --build-arg VITE_API_BASE_URL=http://localhost:8000 -t voltpredict-ui frontend`. For hosted deployments, set `VITE_API_BASE_URL` to the backend URL and replace the wildcard `CORS_ORIGINS` value in Render with the exact frontend origin.
