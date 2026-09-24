"""
Main CLI entrypoint for pure backend execution of the Renewable Grid Digital Twin.
Runs CIGRE network initialization, baseline AC power flow, and time-series data pipeline.
"""

import sys
from src.grid import load_cigre_network, run_baseline_powerflow, get_grid_summary
from src.data_pipeline import build_aligned_dataset
from src.forecast import train_all_models


def main():
    print("==================================================================")
    print("   RENEWABLE DISTRIBUTION GRID DIGITAL TWIN — BACKEND CLI RUNNER   ")
    print("==================================================================")
    
    print("\n[1/4] Loading CIGRE MV Distribution Network with DERs...")
    net = load_cigre_network()
    print(f"      Loaded network with {len(net.bus)} buses, {len(net.line)} lines, {len(net.sgen)} static generators.")

    print("\n[2/4] Executing Baseline AC Power Flow (pp.runpp)...")
    converged = run_baseline_powerflow(net)
    if not converged:
        print("      [ERROR] AC Power flow calculation failed to converge!")
        sys.exit(1)
        
    summary = get_grid_summary(net)
    print("      Power Flow Summary:")
    print(f"        - Bus Count:             {summary['bus_count']}")
    print(f"        - Total DER Count:       {summary['der_count']}")
    print(f"        - Voltage Range (p.u.):  [{summary['vm_pu_min']}, {summary['vm_pu_max']}]")
    print(f"        - Max Line Loading (%):  {summary['max_line_loading_percent']}%")
    print(f"        - Convergence Status:    {'CONVERGED' if summary['converged'] else 'FAILED'}")

    print("\n[3/4] Running Data Pipeline (Pune Solar Data + Synthetic Load Profile)...")
    aligned_df = build_aligned_dataset(start_date="2023-01-01", end_date="2023-01-31")
    print(f"      Successfully built time-aligned dataset ({len(aligned_df)} hourly samples).")

    print("\n[4/4] Training & Evaluating AI Forecasting Models (LightGBM GBDT)...")
    train_res = train_all_models(save=True)
    f_sum = train_res["summary"]
    print(f"      Forecasting Engine: {f_sum['engine_used']}")
    print("      Solar Forecaster:")
    print(f"        - Model MAE:             {f_sum['solar']['model_metrics']['mae']} p.u. (Naive: {f_sum['solar']['naive_metrics']['mae']})")
    print(f"        - Model RMSE:            {f_sum['solar']['model_metrics']['rmse']} p.u. (Naive: {f_sum['solar']['naive_metrics']['rmse']})")
    print(f"        - MAE Improvement:       +{f_sum['solar']['mae_improvement_pct']}%")
    print(f"        - R² Score:              {round(f_sum['solar']['model_metrics']['r2'] * 100, 2)}%")
    print("      Load Forecaster:")
    print(f"        - Model MAE:             {f_sum['load']['model_metrics']['mae']} p.u. (Naive: {f_sum['load']['naive_metrics']['mae']})")
    print(f"        - Model RMSE:            {f_sum['load']['model_metrics']['rmse']} p.u. (Naive: {f_sum['load']['naive_metrics']['rmse']})")
    print(f"        - MAE Improvement:       +{f_sum['load']['mae_improvement_pct']}%")
    print(f"        - R² Score:              {round(f_sum['load']['model_metrics']['r2'] * 100, 2)}%")
    print(f"        - Chronological Holdout: {f_sum['solar']['test_samples']} test hours saved to data/processed/models/")

    print("\n==================================================================")
    print("   CHECKPOINT 1 & 2 BACKEND PIPELINES COMPLETED SUCCESSFULLY!    ")
    print("==================================================================")


if __name__ == "__main__":
    main()
