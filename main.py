"""
Main CLI entrypoint for pure backend execution of the Renewable Grid Digital Twin.
Runs CIGRE network initialization, baseline AC power flow, and time-series data pipeline.
"""

import sys
from src.grid import load_cigre_network, run_baseline_powerflow, get_grid_summary
from src.data_pipeline import build_aligned_dataset


def main():
    print("==================================================================")
    print("   RENEWABLE DISTRIBUTION GRID DIGITAL TWIN — BACKEND CLI RUNNER   ")
    print("==================================================================")
    
    print("\n[1/3] Loading CIGRE MV Distribution Network with DERs...")
    net = load_cigre_network()
    print(f"      Loaded network with {len(net.bus)} buses, {len(net.line)} lines, {len(net.sgen)} static generators.")

    print("\n[2/3] Executing Baseline AC Power Flow (pp.runpp)...")
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

    print("\n[3/3] Running Data Pipeline (Pune Solar Data + Synthetic Load Profile)...")
    aligned_df = build_aligned_dataset(start_date="2023-01-01", end_date="2023-01-31")
    print(f"      Successfully built time-aligned dataset ({len(aligned_df)} hourly samples).")
    print(f"      Sample Data Head:")
    print(aligned_df.head(5).to_string())

    print("\n==================================================================")
    print("   CHECKPOINT 1 BACKEND PIPELINE COMPLETED SUCCESSFULLY!         ")
    print("==================================================================")


if __name__ == "__main__":
    main()
