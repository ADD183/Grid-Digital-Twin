# Checkpoint 2 Report — Chronological Solar & Load Forecasting

**Date:** 2026-09-24  
**Status:** Completed and verified

## 1. Scope

Checkpoint 2 extends the Checkpoint 1 React/FastAPI digital twin with validated next-hour solar and demand forecasting. The backend remains UI-independent under `src/forecast.py`; the React control room renders the holdout comparison and benchmark metrics.

## 2. Delivered

- Added lagged features at t-1, t-2, t-3, and t-24, calendar/cyclical features, weekend indicators, and a 24-hour rolling mean.
- Added separate solar and load gradient-boosting models.
- Uses LightGBM when installed and `sklearn.ensemble.GradientBoostingRegressor` as the documented fallback.
- Uses a chronological 20% holdout; no random split or future rows are used for training.
- Computes MAE, RMSE, and R² for each model and compares them with previous-hour and previous-day persistence baselines.
- Persists model bundles and holdout evaluation data with `joblib` under `data/processed/models/`.
- Added FastAPI endpoints:
  - `GET /api/forecast/metrics`
  - `GET /api/forecast/chart?points=24..336`
  - `POST /api/forecast/train`
- Added a React forecast panel with solar/load selection, 48-hour/7-day/14-day windows, actual-vs-model-vs-naive lines, benchmark cards, retraining, and visible error/empty-state handling.
- Updated setup and architecture documentation to reflect the React/FastAPI implementation chosen in Checkpoint 1.

## 3. Verification

### Backend

```text
python -m pytest tests -q
14 passed
```

The existing seven Checkpoint 1 grid tests and seven Checkpoint 2 forecasting tests pass together. The forecasting tests cover feature generation, chronological ordering, metric calculation, model convergence, naive-baseline comparison, artifact persistence/reload, and chart payload formatting.

### Frontend

```text
cd frontend
npm run build
```

The Vite production build completes successfully with the forecast panel included.

## 4. Acceptance criteria

- [x] Chronological split, not random.
- [x] Model MAE/RMSE reported beside a naive persistence baseline.
- [x] Model is benchmarked against and required to match or beat the naive baseline in tests.
- [x] Models and evaluation artifacts are saved and reloadable without retraining.
- [x] Forecast-vs-actual chart is rendered in the active React control room.
- [x] `pytest tests/test_forecast.py` passes.

## 5. Known boundary

The PRD originally described a Streamlit frontend, but Checkpoint 1 explicitly established React/Vite plus FastAPI. Checkpoint 2 therefore implements the equivalent forecast experience in the active React surface; the backend remains compatible with the existing Streamlit reference app. Violation detection and corrective actions remain Checkpoint 3 scope.
