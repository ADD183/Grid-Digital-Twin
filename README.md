# Renewable Distribution Grid Digital Twin

An interactive digital twin of a local power distribution network (CIGRE MV benchmark) connected to solar irradiance history for Pune, India (PVGIS) and synthetic customer demand profiles. The system features a defensible Python backend (`pandapower`, `pvlib`) with a FastAPI REST server and an ultra-modern **React.js Single Page Application (SPA)** frontend.

---

## 🚀 Key Features (Checkpoint 1)
- **React.js Control Room SPA:** High-tech glassmorphism dashboard built with React 18, Vite, Lucide Icons, and Recharts.
- **Calendar Date Range Picker:** Interactive HTML5 date picker allowing custom start and end date selection across 1 to 12+ months, with quick preset buttons ("1 Month", "2 Months", "3 Months", "6 Months").
- **Interactive SVG Grid Topology Canvas:** Color-coded node map of CIGRE 15-bus network displaying bus voltages (green = safe 0.95–1.05 p.u., amber/red = warning/violation), animated power flow lines, and telemetry side panel.
- **FastAPI REST Server:** UI-decoupled REST API exposing grid summary, network element DataFrames, and time-aligned solar/demand time-series data.
- **Defensible Clean Architecture:** `src/` backend is completely UI-independent and testable via `pytest` and CLI (`main.py`).

---

## 📁 Repository Structure
```
renewable-grid-digital-twin/
├── README.md                    # Setup and overview documentation
├── NOTES.md                     # Engineering assumptions log & judge Q&A prep
├── requirements.txt             # Python dependency specification
├── CHECKPOINT_1_REPORT.md       # Checkpoint 1 verification report
├── api.py                       # FastAPI REST Server
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
python -m pytest tests/test_grid.py
```
