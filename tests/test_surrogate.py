"""
Unit tests for Checkpoint 6: Surrogate dataset generation, ensemble training,
calibration guard band, false-safe reduction, and evaluation reporting.
"""

from pathlib import Path
import json
import pytest
import numpy as np
import pandas as pd

from src.surrogate.sampling import (
    FEATURE_NAMES,
    TARGET_NAMES,
    generate_dataset_split,
    generate_all_checkpoint6_manifests,
)
from src.surrogate.train import (
    train_surrogate_ensemble,
    load_surrogate_ensemble,
    SurrogateEnsemble,
)
from src.surrogate.evaluate import evaluate_surrogate_full, compute_metrics_for_split


def test_sampling_and_manifest_generation():
    """Verify QMC sampling produces valid feature/target matrices and JSON manifest."""
    split = generate_dataset_split(
        split_name="test_mini_dev",
        sample_count=20,
        solar_range=(0.5, 1.5),
        load_range=(0.5, 1.5),
        seed=42,
    )
    df = split["dataframe"]
    manifest = split["manifest"]

    assert len(df) == 20
    assert df.shape[1] == 33 + 31  # 33 features + 31 targets
    assert manifest["split_name"] == "test_mini_dev"
    assert manifest["dropped_non_converged"] >= 0
    assert "unsafe_pct" in manifest


def test_surrogate_ensemble_training_and_calibration(tmp_path):
    """Verify training 3-seed ensemble produces calibrated guard band and valid predictions."""
    manifest_dir = str(tmp_path / "manifests")
    model_dir = str(tmp_path / "models")

    # Generate small manifests
    d_train = generate_dataset_split("dev_train", 30, (0.2, 2.0), (0.3, 1.8), seed=42)
    d_val = generate_dataset_split("dev_val", 20, (0.2, 2.0), (0.3, 1.8), seed=142)

    p_dir = Path(manifest_dir)
    p_dir.mkdir(parents=True, exist_ok=True)
    d_train["dataframe"].to_parquet(p_dir / "dev_train.parquet")
    d_val["dataframe"].to_parquet(p_dir / "dev_val.parquet")

    meta = train_surrogate_ensemble(manifest_dir=manifest_dir, model_save_dir=model_dir, seeds=[42, 43, 44])

    assert meta["trained"] is True
    assert meta["calibrated_guard_band"] > 0.0
    assert len(meta["ensemble_seeds"]) == 3

    # Load and test inference
    ensemble, load_meta = load_surrogate_ensemble(meta["checkpoint_path"])
    sample_x = d_val["features"][:5]
    preds = ensemble.predict_batch(sample_x)

    assert preds["vm_pu"].shape == (5, 15)
    assert preds["loading_pct"].shape == (5, 14)
    assert preds["min_margin"].shape == (5,)
    assert preds["disagreement"].shape == (5,)


def test_false_safe_reduction_by_guard_band():
    """Verify that guard band calibration reduces false-safe count on dev_val."""
    meta_path = Path("outputs/evidence/surrogate_model_metadata.json")
    eval_path = Path("outputs/evidence/surrogate_evaluation.json")

    if not meta_path.is_file() or not eval_path.is_file():
        train_surrogate_ensemble()
        evaluate_surrogate_full()

    with open(eval_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    dev_val_res = rep["split_evaluations"]["dev_val"]
    raw_false_safe = dev_val_res["false_safe"]["raw"]["false_safe_rate_pct"]
    gb_false_safe = dev_val_res["false_safe"]["with_guard_band"]["false_safe_rate_pct"]

    # Guard band must not increase false-safe rate
    assert gb_false_safe <= raw_false_safe


def test_artifact_reload_without_retraining():
    """Verify surrogate ensemble reloads from checkpoint and predicts without retraining."""
    checkpoint_path = "models/surrogate_ensemble.pt"
    if not Path(checkpoint_path).is_file():
        train_surrogate_ensemble()

    ensemble, meta = load_surrogate_ensemble(checkpoint_path)
    dummy_x = np.random.randn(3, 33)
    res = ensemble.predict_batch(dummy_x)

    assert res["min_margin"].shape == (3,)
    assert meta["calibrated_guard_band"] > 0.0


def test_naive_baseline_reported():
    """Verify evaluation report contains naive baseline metrics."""
    eval_path = Path("outputs/evidence/surrogate_evaluation.json")
    if not eval_path.is_file():
        evaluate_surrogate_full()

    with open(eval_path, "r", encoding="utf-8") as f:
        rep = json.load(f)

    for split_name, s_res in rep["split_evaluations"].items():
        assert "naive_baseline" in s_res
        assert "voltage_mae_pu" in s_res["naive_baseline"]
        assert "loading_mae_pct" in s_res["naive_baseline"]
