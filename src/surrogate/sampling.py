"""
Surrogate Dataset Generator and State Sampler (Checkpoint 6).
Generates physical labels using pandapower AC Newton-Raphson solver.
Samples operating conditions across distinct development and test split manifests
using scipy.stats.qmc (Latin Hypercube / Sobol sampling).
"""

import copy
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd
from scipy.stats import qmc
import pandapower as pp

from src.grid import load_cigre_network
from src.control.state import load_limits_config, LimitsConfig

FEATURE_NAMES = [f"p_mw_bus_{i}" for i in range(15)] + [f"q_mvar_bus_{i}" for i in range(15)] + ["switch_s1", "switch_s2", "switch_s4"]
TARGET_VM_NAMES = [f"vm_pu_bus_{i}" for i in range(15)]
TARGET_LOADING_NAMES = [f"loading_pct_line_{i}" for i in range(14)]
TARGET_NAMES = TARGET_VM_NAMES + TARGET_LOADING_NAMES + ["min_margin", "unsafe"]


def extract_features_and_targets(
    net: pp.pandapowerNet,
    limits: LimitsConfig,
    switch_states: Tuple[bool, bool, bool],
) -> Tuple[np.ndarray, np.ndarray, float, bool]:
    """
    Extract 33-dim feature vector and 31-dim target vector from a post-runpp network.
    
    Features (33):
      - 15 net P injections per bus (MW)
      - 15 net Q injections per bus (MVAr)
      - 3 switch states (s1, s2, s4 as 1.0/0.0)
      
    Targets (31):
      - 15 bus voltage magnitudes (vm_pu)
      - 14 line loading percentages (loading_percent)
      - 1 min_margin (signed headroom in p.u.)
      - 1 unsafe flag (boolean, True if min_margin < 0)
    """
    # 1. Bus net injections
    bus_p = np.zeros(15, dtype=np.float64)
    bus_q = np.zeros(15, dtype=np.float64)

    # Loads
    if hasattr(net, "load") and not net.load.empty:
        for _, row in net.load.iterrows():
            b = int(row["bus"])
            if 0 <= b < 15:
                bus_p[b] -= float(row["p_mw"])
                bus_q[b] -= float(row["q_mvar"])

    # Static Generators (sgen)
    if hasattr(net, "sgen") and not net.sgen.empty:
        for _, row in net.sgen.iterrows():
            b = int(row["bus"])
            if 0 <= b < 15:
                bus_p[b] += float(row["p_mw"])
                bus_q[b] += float(row["q_mvar"])

    # Storage (battery)
    if hasattr(net, "storage") and not net.storage.empty:
        for _, row in net.storage.iterrows():
            b = int(row["bus"])
            if 0 <= b < 15:
                # In pandapower storage: positive p_mw = charging (draws power), negative = discharging
                bus_p[b] -= float(row["p_mw"])

    # Switch features
    sw_s1, sw_s2, sw_s4 = switch_states
    switch_feats = np.array([1.0 if sw_s1 else 0.0, 1.0 if sw_s2 else 0.0, 1.0 if sw_s4 else 0.0], dtype=np.float64)

    features = np.concatenate([bus_p, bus_q, switch_feats])

    # 2. Targets from res_bus and res_line
    vm_arr = np.zeros(15, dtype=np.float64)
    for b in range(15):
        vm_arr[b] = float(net.res_bus.loc[b, "vm_pu"]) if b in net.res_bus.index else 1.0

    loading_arr = np.zeros(14, dtype=np.float64)
    for l in range(14):
        loading_arr[l] = float(net.res_line.loc[l, "loading_percent"]) if l in net.res_line.index else 0.0

    # Margin calculation
    v_margin_low = vm_arr - limits.grid.v_min
    v_margin_high = limits.grid.v_max - vm_arr
    load_margin = (limits.grid.max_loading_pct - loading_arr) / 100.0

    min_margin = float(np.min([np.min(v_margin_low), np.min(v_margin_high), np.min(load_margin)]))
    unsafe = bool(min_margin < 0.0)

    targets = np.concatenate([vm_arr, loading_arr, np.array([min_margin, 1.0 if unsafe else 0.0])])

    return features, targets, min_margin, unsafe


def generate_dataset_split(
    split_name: str,
    sample_count: int,
    solar_range: Tuple[float, float],
    load_range: Tuple[float, float],
    seed: int = 42,
    target_unsafe_min_pct: Optional[float] = None,
    near_limit_only: bool = False,
    limits: Optional[LimitsConfig] = None,
) -> Dict[str, Any]:
    """
    Generate a labeled dataset split using QMC Latin Hypercube Sampling.
    
    Args:
        split_name: Name of split ('dev_train', 'dev_val', 'test_unseen', 'test_extended', 'test_near_limit')
        sample_count: Desired number of converged samples
        solar_range: (min_scale, max_scale)
        load_range: (min_scale, max_scale)
        seed: Random seed for sampling reproducibility
        target_unsafe_min_pct: If specified, rejection sample to meet minimum % unsafe
        near_limit_only: If True, only keep states with min_margin in [-0.02, +0.02]
        limits: LimitsConfig instance
    """
    lims = limits or load_limits_config()
    base_net = load_cigre_network()

    # Create QMC sampler (4 dimensions: solar_scale, load_scale, battery_level_idx, switch_combo_idx)
    sampler = qmc.LatinHypercube(d=4, seed=seed)
    
    features_list = []
    targets_list = []
    metadata_rows = []

    dropped_non_converged = 0
    total_attempts = 0
    unsafe_count = 0

    # Discrete options for sampling
    battery_opts = lims.control.battery_levels  # [-1.0, -0.5, 0.0, 0.5, 1.0]
    curtail_opts = lims.control.curtail_levels  # [0.0, 10.0, 25.0, 50.0]
    switch_combos = [
        (False, False, False),
        (True, False, False),
        (False, True, False),
        (False, False, True),
        (True, True, False),
    ]

    max_attempts = sample_count * 10

    while len(features_list) < sample_count and total_attempts < max_attempts:
        # Sample batch from QMC sampler
        batch_size = max(50, sample_count - len(features_list))
        samples = sampler.random(n=batch_size)

        for u in samples:
            if len(features_list) >= sample_count:
                break

            total_attempts += 1

            s_scale = solar_range[0] + u[0] * (solar_range[1] - solar_range[0])
            l_scale = load_range[0] + u[1] * (load_range[1] - load_range[0])
            batt_mw = battery_opts[int(u[2] * len(battery_opts)) % len(battery_opts)]
            sw_tuple = switch_combos[int(u[3] * len(switch_combos)) % len(switch_combos)]
            curtail_pct = curtail_opts[int((u[0] + u[1]) * 0.5 * len(curtail_opts)) % len(curtail_opts)]

            # Mutate worker network copy
            net = copy.deepcopy(base_net)

            # Apply scaling
            if hasattr(net, "sgen") and not net.sgen.empty:
                mult = s_scale * (1.0 - curtail_pct / 100.0)
                net.sgen.loc[:, "p_mw"] = net.sgen.loc[:, "p_mw"] * mult

            if hasattr(net, "load") and not net.load.empty:
                net.load.loc[:, "p_mw"] = net.load.loc[:, "p_mw"] * l_scale
                net.load.loc[:, "q_mvar"] = net.load.loc[:, "q_mvar"] * l_scale

            # Apply battery storage
            if hasattr(net, "storage") and not net.storage.empty:
                # In pandapower storage: positive p_mw = charging (draws power)
                net.storage.loc[:, "p_mw"] = -batt_mw

            # Apply switches
            if hasattr(net, "switch") and not net.switch.empty:
                for idx_sw, sw_id in enumerate([1, 2, 4]):
                    sw_rows = net.switch[net.switch["name"] == f"S{sw_id}"]
                    if not sw_rows.empty:
                        net.switch.loc[sw_rows.index, "closed"] = bool(sw_tuple[idx_sw])

            # Run AC Power Flow
            try:
                pp.runpp(net, numba=False, max_iteration=50, tolerance_mva=1e-6)
                if not net.converged:
                    dropped_non_converged += 1
                    continue
            except Exception:
                dropped_non_converged += 1
                continue

            # Extract features and targets
            feats, targs, min_margin, is_unsafe = extract_features_and_targets(net, lims, sw_tuple)

            # Filtering criteria
            if near_limit_only and not (-0.02 <= min_margin <= 0.02):
                continue

            if target_unsafe_min_pct is not None and not is_unsafe:
                current_unsafe_pct = (unsafe_count / (len(features_list) + 1)) * 100.0
                if current_unsafe_pct < target_unsafe_min_pct and np.random.rand() > 0.3:
                    continue

            features_list.append(feats)
            targets_list.append(targs)
            if is_unsafe:
                unsafe_count += 1

            metadata_rows.append({
                "solar_scale": float(s_scale),
                "load_scale": float(l_scale),
                "battery_mw": float(batt_mw),
                "curtail_pct": float(curtail_pct),
                "switch_s1": bool(sw_tuple[0]),
                "switch_s2": bool(sw_tuple[1]),
                "switch_s4": bool(sw_tuple[2]),
                "min_margin": float(min_margin),
                "unsafe": bool(is_unsafe),
            })

    feats_arr = np.array(features_list, dtype=np.float64)
    targs_arr = np.array(targets_list, dtype=np.float64)

    df_feats = pd.DataFrame(feats_arr, columns=FEATURE_NAMES)
    df_targs = pd.DataFrame(targs_arr, columns=TARGET_NAMES)
    df_combined = pd.concat([df_feats, df_targs], axis=1)

    actual_unsafe_pct = (unsafe_count / len(features_list) * 100.0) if features_list else 0.0

    manifest = {
        "split_name": split_name,
        "sample_count": len(features_list),
        "requested_count": sample_count,
        "seed": seed,
        "solar_range": list(solar_range),
        "load_range": list(load_range),
        "dropped_non_converged": dropped_non_converged,
        "total_attempts": total_attempts,
        "safe_count": len(features_list) - unsafe_count,
        "unsafe_count": unsafe_count,
        "unsafe_pct": round(actual_unsafe_pct, 2),
        "near_limit_only": near_limit_only,
    }

    return {
        "dataframe": df_combined,
        "manifest": manifest,
        "features": feats_arr,
        "targets": targs_arr,
        "metadata": metadata_rows,
    }


def save_split_artifacts(split_name: str, split_data: Dict[str, Any], base_dir: str = "outputs/evidence/manifests") -> Tuple[str, str]:
    """Save split dataframe to Parquet and manifest info to JSON."""
    out_dir = Path(base_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = out_dir / f"{split_name}.parquet"
    json_path = out_dir / f"{split_name}_manifest.json"

    # Save DataFrame to Parquet
    split_data["dataframe"].to_parquet(parquet_path, index=False)

    # Save Manifest JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(split_data["manifest"], f, indent=2)

    return str(parquet_path), str(json_path)


def generate_all_checkpoint6_manifests(base_dir: str = "outputs/evidence/manifests") -> Dict[str, Any]:
    """
    Generate all 5 standardized Checkpoint 6 split manifests:
      1. dev_train: Development training set (500 samples, >=20% unsafe)
      2. dev_val: Development validation set (150 samples)
      3. test_unseen: Held-out solar/load parameter combinations (150 samples)
      4. test_extended: Wider operating range extrapolation (150 samples, solar up to 2.8 p.u.)
      5. test_near_limit: Near-limit states with margin in [-0.02, +0.02] (100 samples)
    """
    lims = load_limits_config()
    results = {}

    # 1. dev_train
    print("Generating dev_train split...")
    d_train = generate_dataset_split(
        split_name="dev_train",
        sample_count=500,
        solar_range=(0.2, 2.0),
        load_range=(0.3, 1.8),
        seed=42,
        target_unsafe_min_pct=22.0,
        limits=lims,
    )
    save_split_artifacts("dev_train", d_train, base_dir)
    results["dev_train"] = d_train["manifest"]

    # 2. dev_val
    print("Generating dev_val split...")
    d_val = generate_dataset_split(
        split_name="dev_val",
        sample_count=150,
        solar_range=(0.2, 2.0),
        load_range=(0.3, 1.8),
        seed=142,
        target_unsafe_min_pct=20.0,
        limits=lims,
    )
    save_split_artifacts("dev_val", d_val, base_dir)
    results["dev_val"] = d_val["manifest"]

    # 3. test_unseen (Held-out solar/load combinations: solar 2.0-2.4, load 1.8-2.2)
    print("Generating test_unseen split...")
    t_unseen = generate_dataset_split(
        split_name="test_unseen",
        sample_count=150,
        solar_range=(2.0, 2.4),
        load_range=(1.8, 2.2),
        seed=242,
        limits=lims,
    )
    save_split_artifacts("test_unseen", t_unseen, base_dir)
    results["test_unseen"] = t_unseen["manifest"]

    # 4. test_extended (Wider extrapolation range: solar 2.2-2.8, load 0.2-2.5)
    print("Generating test_extended split...")
    t_ext = generate_dataset_split(
        split_name="test_extended",
        sample_count=150,
        solar_range=(2.2, 2.8),
        load_range=(0.2, 2.5),
        seed=342,
        limits=lims,
    )
    save_split_artifacts("test_extended", t_ext, base_dir)
    results["test_extended"] = t_ext["manifest"]

    # 5. test_near_limit (Rejection-sampled near-limit margin in [-0.02, +0.02])
    print("Generating test_near_limit split...")
    t_near = generate_dataset_split(
        split_name="test_near_limit",
        sample_count=100,
        solar_range=(0.5, 2.3),
        load_range=(0.4, 2.0),
        seed=442,
        near_limit_only=True,
        limits=lims,
    )
    save_split_artifacts("test_near_limit", t_near, base_dir)
    results["test_near_limit"] = t_near["manifest"]

    return results


if __name__ == "__main__":
    manifests = generate_all_checkpoint6_manifests()
    print("Manifest generation complete!")
    print(json.dumps(manifests, indent=2))
