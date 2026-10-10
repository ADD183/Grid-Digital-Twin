# Checkpoint 8 Evidence Index (VoltPredict Digital Twin)

This document provides a mapping of all required project evidence items to their exact file paths.

---

## 1. Physical Power Flow Solver & Configuration
- **Pandapower AC Solver Configuration:** [`outputs/evidence/solver_config.json`](file:///c:/Downloads/Enr02/outputs/evidence/solver_config.json)

---

## 2. 12-Step Showcase Episode Artifacts
- **Showcase Episode Action Log (JSON):** [`outputs/evidence/action_logs/cp8_showcase_12step.json`](file:///c:/Downloads/Enr02/outputs/evidence/action_logs/cp8_showcase_12step.json)
- **Showcase Episode Action Log (JSONL):** [`outputs/evidence/action_logs/cp8_showcase_12step.jsonl`](file:///c:/Downloads/Enr02/outputs/evidence/action_logs/cp8_showcase_12step.jsonl)
- **State of Charge (SOC) Trace (CSV):** [`outputs/evidence/soc_traces/cp8_showcase_12step_soc.csv`](file:///c:/Downloads/Enr02/outputs/evidence/soc_traces/cp8_showcase_12step_soc.csv)
- **Physical Verification Log (JSON):** [`outputs/evidence/verification/cp8_showcase_12step_verification.json`](file:///c:/Downloads/Enr02/outputs/evidence/verification/cp8_showcase_12step_verification.json)

---

## 3. Neural Surrogate Model & Dataset Manifests
- **Surrogate Model Metadata & Guard Band:** [`outputs/evidence/surrogate/surrogate_metadata.json`](file:///c:/Downloads/Enr02/outputs/evidence/surrogate/surrogate_metadata.json)
- **Full Split Evaluation Report (JSON):** [`outputs/evidence/metrics/surrogate_evaluation.json`](file:///c:/Downloads/Enr02/outputs/evidence/metrics/surrogate_evaluation.json)
- **Dataset Split Manifests:**
  - `dev_train`: [`outputs/evidence/splits/dev_train_manifest.json`](file:///c:/Downloads/Enr02/outputs/evidence/splits/dev_train_manifest.json)
  - `dev_val`: [`outputs/evidence/splits/dev_val_manifest.json`](file:///c:/Downloads/Enr02/outputs/evidence/splits/dev_val_manifest.json)
  - `test_unseen`: [`outputs/evidence/splits/test_unseen_manifest.json`](file:///c:/Downloads/Enr02/outputs/evidence/splits/test_unseen_manifest.json)
  - `test_extended`: [`outputs/evidence/splits/test_extended_manifest.json`](file:///c:/Downloads/Enr02/outputs/evidence/splits/test_extended_manifest.json)
  - `test_near_limit`: [`outputs/evidence/splits/test_near_limit_manifest.json`](file:///c:/Downloads/Enr02/outputs/evidence/splits/test_near_limit_manifest.json)

---

## 4. Surrogate Screening A/B Benchmarks
- **A/B Screening Comparison Report:** [`outputs/evidence/metrics/ab_screening_comparison.json`](file:///c:/Downloads/Enr02/outputs/evidence/metrics/ab_screening_comparison.json)

---

## 5. Required Showcase Events Summary (12-Step Episode)
1. **Injected Forecast Error:** Step 2 (Midday solar surge +120%)
2. **Battery Saturation:** Step 4 (SOC reached maximum limit 0.90)
3. **Infeasible Period with Fallback:** Step 6 (Extreme load stress & fallback ladder invocation)
4. **Near-Limit Network State:** Step 7 (Minimum bus voltage V = 0.952 pu)
5. **Surrogate Disagreement Event:** Step 8 (Surrogate predicted safe, solver rejected with violation)
6. **Battery Depletion:** Step 11 (SOC reached minimum reserve limit 0.10)
