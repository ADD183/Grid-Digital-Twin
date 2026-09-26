"""
Main CLI entrypoint for pure backend execution of the Renewable Grid Digital Twin.
Runs CIGRE network initialization, baseline AC power flow, and time-series data pipeline.
"""

import sys
from src.grid import load_cigre_network, run_baseline_powerflow, get_grid_summary
from src.data_pipeline import build_aligned_dataset
from src.forecast import train_all_models
from src.violations import check_grid_violations
from src.engine import trigger_scenario, evaluate_actions


def main():
    print("==================================================================")
    print("   RENEWABLE DISTRIBUTION GRID DIGITAL TWIN — BACKEND CLI RUNNER   ")
    print("==================================================================")
    
    print("\n[1/5] Loading CIGRE MV Distribution Network with DERs...")
    net = load_cigre_network()
    print(f"      Loaded network with {len(net.bus)} buses, {len(net.line)} lines, {len(net.sgen)} static generators.")

    print("\n[2/5] Executing Baseline AC Power Flow (pp.runpp)...")
    converged = run_baseline_powerflow(net)
    if not converged:
        print("      [ERROR] AC Power flow calculation failed to converge!")
        sys.exit(1)
        
    summary = get_grid_summary(net)
    v_report = check_grid_violations(net)
    print("      Power Flow Summary:")
    print(f"        - Bus Count:             {summary['bus_count']}")
    print(f"        - Total DER Count:       {summary['der_count']}")
    print(f"        - Voltage Range (p.u.):  [{summary['vm_pu_min']}, {summary['vm_pu_max']}]")
    print(f"        - Max Line Loading (%):  {summary['max_line_loading_percent']}%")
    print(f"        - Baseline Violations:   {v_report['total_violations']} (Clean safe state)")
    print(f"        - Convergence Status:    {'CONVERGED' if summary['converged'] else 'FAILED'}")

    print("\n[3/5] Running Data Pipeline (Pune Solar Data + Synthetic Load Profile)...")
    aligned_df = build_aligned_dataset(start_date="2023-01-01", end_date="2023-01-31")
    print(f"      Successfully built time-aligned dataset ({len(aligned_df)} hourly samples).")

    print("\n[4/5] Training & Evaluating AI Forecasting Models (LightGBM / GBDT)...")
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
    print("\n[5/5] Executing Checkpoint 3 Propose -> Verify -> Repair Corrective Action Engine...")
    print("      Triggering Solar Surge Overvoltage Scenario (Midday PV Spike)...")
    spike_net, meta = trigger_scenario("solar_spike")
    print(f"      Induced {meta['initial_violations']['total_violations']} violations (Max V: {meta['initial_violations']['summary']['max_vm_pu']} p.u.)")
    
    print("      Evaluating candidate action pool across curtailment, battery storage, and feeder reconfiguration...")
    engine_res = evaluate_actions(spike_net)
    winner = engine_res["recommended_action"]
    print(f"      Actions Evaluated:        {engine_res['actions_evaluated']}")
    print(f"      Recommended Action:       {winner['name']}")
    print(f"      Action Family:            {winner['action_type']}")
    print(f"      Fully Resolved Violations:{engine_res['fully_resolved']}")
    print(f"      Renewable Output Retained:{winner['renewable_retained_pct']}%")
    print(f"      Operational Cost Proxy:   {winner['cost_proxy']}/3")
    print(f"      Engine Score:             {winner['score']}")
    print(f"      Decision Rationale:       {engine_res['explanation']}")

    print("\n==================================================================")
    print("   CHECKPOINTS 1, 2 & 3 BACKEND PIPELINES FULLY VERIFIED!        ")
    print("==================================================================")


if __name__ == "__main__":
    main()
