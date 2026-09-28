# 📊 Presentation Slide Content: Technical Approach
**Project Name:** Renewable Distribution Grid Digital Twin  
**Problem Statement:** ENR-02 · HackMatrix 5.0  

---

## 🎯 Slide Title: Technical Approach & End-to-End System Architecture
**Subtitle:** A Physics-Grounded, Predictive, Optimization Engine Paired with a Zero-Hallucination Dual-Audience Assistant

---


## 🚀 4 Core Pillars of Technical Approach

### 1️⃣ Physics-Grounded Digital Twin Engine (`pandapower` & `pvlib`)
* **Benchmark Network Modeling:** Built on the internationally recognized **CIGRE MV 15-bus benchmark grid** with Distributed Energy Resource (DER) solar generators.
* **Exact Power-System Physics:** Executes non-linear **AC Power Flow calculations (`pandapower.runpp`)** to calculate exact per-unit bus voltages ($p.u.$), voltage phase angles, line loading percentages ($\%$), and transformer stress.
* **Real & Synthetic Data Pipeline:** Ingests hourly solar irradiance data for Pune, India ($18.52^\circ\text{ N}, 73.85^\circ\text{ E}$) via `pvlib` (PVGIS), time-aligned with synthetic residential/commercial demand curves.

### 2️⃣ Chronological ML Forecaster (`LightGBM`)
* **Predictive Grid Defense:** Forecasts solar generation and demand profiles $1\text{ to }24\text{ hours}$ ahead to anticipate grid violations *before* physical constraints occur.
* **Feature Engineering:** Extracts historical lag features ($t-1, t-2, t-3, t-24$), 24-hour rolling averages, and trigonometric calendar encodings ($\sin/\cos$ of hour & day-of-year).
* **Leakage-Free Chronological Holdout:** Strictly validates models using chronological split holdouts (never random shuffle) benchmarked against seasonal persistence baselines ($t-24$) using MAE and RMSE metrics.

### 3️⃣ Deterministic Propose $\rightarrow$ Verify $\rightarrow$ Repair Engine (`src/engine.py`)
* **Multi-Strategy Candidate Generation:** Automatically formulates candidate corrective actions across 3 physics strategies:
  1. **Feeder Reconfiguration:** Toggling CIGRE MV tie-switches ($S1, S2, S3$) to rebalance power flow without generation loss.
  2. **Battery Dispatch:** Absorbing excess solar during overvoltage; injecting power during peak loads.
  3. **Solar Curtailment:** Throttling PV output as a reliable fallback.
  4. **Hybrid Actions:** Combining reconfigurations with storage dispatch.
* **Closed-Loop Verification:** Re-simulates AC power flow on isolated network copies for *every candidate* to mathematically verify violation resolution.
* **Multi-Objective Explainable Scoring:** Ranks actions by:
  $$\text{Score} = +1000 \text{ (if resolved)} + 2 \times (\% \text{ Renewable Retained}) - 15 \times (\text{Cost Proxy}) - \text{Residual Penalty}$$
* **Honest Infeasibility Surfacing:** Transparently surfaces when severe stress exceeds physical mitigation envelopes instead of producing false success claims or failing silently.

### 4️⃣ Dual-Audience Agentic Assistant (`src/chatbot/`, LangGraph + OpenRouter LLM)
* **Dual-Audience Communication Layer:** Tailors natural-language explanations for non-technical users while preserving uncompromised technical data ($p.u.$ voltages, line loadings, bus IDs) for power engineers.
* **Strict Engine vs. Assistant Separation:** 
  * *Deterministic Engine:* Ground truth physics calculations (No LLM).
  * *Digital Grid Assistant:* Agentic conversational layer for user interaction.
* **Function-Calling & Grounding Contract:** Operates under a zero-hallucination contract where the LLM executes real system tools (Category A: system state lookups; Category B: project knowledge) and attaches verifiable JSON evidence to every answer.

---

## 📌 Presenter Bullet Points / Key Takeaways for Judges
* **Physics over Generative Guesswork:** Core grid decisions are driven by deterministic AC power flow, not LLM guesses.
* **Proactive vs. Reactive:** Machine learning forecasting transforms grid management from reactive tripping to proactive constraint prevention.
* **Clean Energy First:** The multi-objective engine prioritizes network switching and battery absorption over solar curtailment to minimize clean energy waste.
* **Zero-Hallucination AI:** The conversational assistant only communicates data retrieved from verified system tools and documented knowledge.
