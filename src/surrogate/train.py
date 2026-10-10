"""
Surrogate Model Training, Ensemble Architecture & Calibration Engine (Checkpoint 6).
Trains a multi-task PyTorch Neural Network ensemble across 3 random seeds.
Calibrates the safety guard band on dev_val to minimize false-safe rate.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import TensorDataset, DataLoader
    HAS_TORCH = True
except (ImportError, ModuleNotFoundError):
    torch = None
    nn = type("nn", (), {"Module": object})
    optim = None
    TensorDataset = None
    DataLoader = None
    HAS_TORCH = False

from src.surrogate.sampling import FEATURE_NAMES, TARGET_VM_NAMES, TARGET_LOADING_NAMES, TARGET_NAMES
from src.control.state import load_limits_config


class PowerFlowSurrogateMLP(nn.Module):

    """
    Multi-task PyTorch Neural Network for power flow surrogate estimation.
    Features (33): Bus P/Q net injections + switch states.
    Targets: 15 bus voltages (vm_pu), 14 line loadings (%), 1 min_margin, 1 unsafe logit.
    """

    def __init__(self, input_dim: int = 33, hidden_dim: int = 128):
        super().__init__()
        self.shared_backbone = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.SiLU(),
            nn.Linear(hidden_dim, 64),
            nn.SiLU(),
        )

        # Multi-task heads
        self.vm_head = nn.Linear(64, 15)
        self.loading_head = nn.Linear(64, 14)
        self.margin_head = nn.Linear(64, 1)
        self.unsafe_head = nn.Linear(64, 1)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        feat = self.shared_backbone(x)
        vm = self.vm_head(feat)
        loading = self.loading_head(feat)
        margin = self.margin_head(feat)
        unsafe_logit = self.unsafe_head(feat)
        return vm, loading, margin, unsafe_logit


class StandardScalerNumpy:
    """Simple NumPy/PyTorch scaler for feature standardization."""

    def __init__(self):
        self.mean = None
        self.std = None

    def fit(self, x: np.ndarray):
        self.mean = np.mean(x, axis=0, keepdims=True)
        self.std = np.std(x, axis=0, keepdims=True)
        self.std[self.std < 1e-8] = 1.0  # Prevent division by zero

    def transform(self, x: np.ndarray) -> np.ndarray:
        return (x - self.mean) / self.std

    def fit_transform(self, x: np.ndarray) -> np.ndarray:
        self.fit(x)
        return self.transform(x)

    def to_dict(self) -> Dict[str, List[float]]:
        return {
            "mean": self.mean.flatten().tolist(),
            "std": self.std.flatten().tolist(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, List[float]]) -> "StandardScalerNumpy":
        scaler = cls()
        scaler.mean = np.array(data["mean"], dtype=np.float64).reshape(1, -1)
        scaler.std = np.array(data["std"], dtype=np.float64).reshape(1, -1)
        return scaler


class SurrogateEnsemble:
    """
    Ensemble wrapper containing 3 independently trained surrogate models (seeds 42, 43, 44).
    Provides joint predictions and ensemble disagreement (std dev of min_margin across seeds).
    """

    def __init__(self, models: List[PowerFlowSurrogateMLP], scaler: StandardScalerNumpy):
        self.models = models
        self.scaler = scaler
        for m in self.models:
            m.eval()

    def predict_batch(self, x_raw: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Run inference over a batch of 33-dim raw feature vectors.
        Returns dictionary of ensemble means and margin disagreement std dev.
        """
        x_scaled = self.scaler.transform(x_raw)
        x_tensor = torch.tensor(x_scaled, dtype=torch.float32)

        vm_preds = []
        loading_preds = []
        margin_preds = []
        unsafe_prob_preds = []

        with torch.no_grad():
            for m in self.models:
                vm, loading, margin, unsafe_logit = m(x_tensor)
                vm_preds.append(vm.numpy())
                loading_preds.append(loading.numpy())
                margin_preds.append(margin.numpy())
                unsafe_prob_preds.append(torch.sigmoid(unsafe_logit).numpy())

        vm_ensemble = np.mean(vm_preds, axis=0)
        loading_ensemble = np.mean(loading_preds, axis=0)
        margin_ensemble = np.mean(margin_preds, axis=0).flatten()
        unsafe_prob_ensemble = np.mean(unsafe_prob_preds, axis=0).flatten()

        # Disagreement = standard deviation of min_margin prediction across ensemble seeds
        disagreement = np.std(np.squeeze(margin_preds), axis=0)
        if disagreement.ndim == 0:
            disagreement = np.array([float(disagreement)])

        return {
            "vm_pu": vm_ensemble,
            "loading_pct": loading_ensemble,
            "min_margin": margin_ensemble,
            "unsafe_prob": unsafe_prob_ensemble,
            "disagreement": disagreement,
        }


def train_single_seed_model(
    x_train: np.ndarray,
    y_train: np.ndarray,
    scaler: StandardScalerNumpy,
    seed: int = 42,
    epochs: int = 120,
    batch_size: int = 32,
    lr: float = 1e-3,
) -> PowerFlowSurrogateMLP:
    """Train one seed model instance using PyTorch."""
    torch.manual_seed(seed)
    np.random.seed(seed)

    x_scaled = scaler.transform(x_train)
    
    vm_target = y_train[:, :15]
    loading_target = y_train[:, 15:29]
    margin_target = y_train[:, 29:30]
    unsafe_target = y_train[:, 30:31]

    dataset = TensorDataset(
        torch.tensor(x_scaled, dtype=torch.float32),
        torch.tensor(vm_target, dtype=torch.float32),
        torch.tensor(loading_target, dtype=torch.float32),
        torch.tensor(margin_target, dtype=torch.float32),
        torch.tensor(unsafe_target, dtype=torch.float32),
    )
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model = PowerFlowSurrogateMLP(input_dim=33, hidden_dim=128)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

    mse_loss_fn = nn.MSELoss()
    bce_loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([2.0]))

    model.train()
    for epoch in range(epochs):
        for bx, b_vm, b_load, b_margin, b_unsafe in dataloader:
            optimizer.zero_grad()
            p_vm, p_load, p_margin, p_unsafe = model(bx)

            l_vm = mse_loss_fn(p_vm, b_vm)
            l_load = mse_loss_fn(p_load, b_load)
            l_margin = mse_loss_fn(p_margin, b_margin)
            l_unsafe = bce_loss_fn(p_unsafe, b_unsafe)

            total_loss = l_vm * 100.0 + l_load * 0.1 + l_margin * 10.0 + l_unsafe * 1.0
            total_loss.backward()
            optimizer.step()

    model.eval()
    return model


def train_surrogate_ensemble(
    manifest_dir: str = "outputs/evidence/manifests",
    model_save_dir: str = "models",
    seeds: List[int] = [42, 43, 44],
) -> Dict[str, Any]:
    """
    Train 3-seed surrogate ensemble on dev_train split and calibrate guard band on dev_val.
    """
    lims = load_limits_config()
    p_dir = Path(manifest_dir)
    train_parquet = p_dir / "dev_train.parquet"
    val_parquet = p_dir / "dev_val.parquet"

    if not train_parquet.is_file():
        from src.surrogate.sampling import generate_all_checkpoint6_manifests
        generate_all_checkpoint6_manifests(manifest_dir)

    df_train = pd.read_parquet(train_parquet)
    df_val = pd.read_parquet(val_parquet)

    x_train = df_train[FEATURE_NAMES].values
    y_train = df_train[TARGET_NAMES].values

    x_val = df_val[FEATURE_NAMES].values
    y_val = df_val[TARGET_NAMES].values

    # Fit scaler
    scaler = StandardScalerNumpy()
    scaler.fit(x_train)

    # Train ensemble seeds
    models = []
    print(f"Training {len(seeds)}-seed surrogate ensemble...")
    for s in seeds:
        print(f"  - Training seed {s}...")
        m = train_single_seed_model(x_train, y_train, scaler, seed=s, epochs=120)
        models.append(m)

    ensemble = SurrogateEnsemble(models, scaler)

    # Calibrate guard band on dev_val
    val_preds = ensemble.predict_batch(x_val)
    val_margin_actual = y_val[:, 29]
    val_margin_pred = val_preds["min_margin"]

    # Margin error: underestimation occurs when actual < predicted (pred is overly optimistic)
    underestimation_errors = val_margin_pred - val_margin_actual
    positive_underestimations = np.maximum(0.0, underestimation_errors)

    # 99th percentile guard band calibration
    calibrated_guard_band = float(np.percentile(positive_underestimations, 99))
    calibrated_guard_band = max(calibrated_guard_band, float(lims.surrogate.guard_band))

    disagreement_ceiling = float(lims.surrogate.disagreement_ceiling)

    # Supported feature bounds from dev_train
    supported_bounds = {
        "p_mw_min": float(np.min(x_train[:, :15])),
        "p_mw_max": float(np.max(x_train[:, :15])),
        "q_mvar_min": float(np.min(x_train[:, 15:30])),
        "q_mvar_max": float(np.max(x_train[:, 15:30])),
    }

    # Save ensemble checkpoint file
    m_dir = Path(model_save_dir)
    m_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = m_dir / "surrogate_ensemble.pt"

    state_dicts = [m.state_dict() for m in models]
    torch.save(
        {
            "seeds": seeds,
            "state_dicts": state_dicts,
            "scaler": scaler.to_dict(),
            "calibrated_guard_band": calibrated_guard_band,
            "disagreement_ceiling": disagreement_ceiling,
            "supported_bounds": supported_bounds,
            "feature_names": FEATURE_NAMES,
            "target_names": TARGET_NAMES,
        },
        checkpoint_path,
    )

    meta_path = Path("outputs/evidence") / "surrogate_model_metadata.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = {
        "trained": True,
        "ensemble_seeds": seeds,
        "train_samples": len(df_train),
        "val_samples": len(df_val),
        "calibrated_guard_band": round(calibrated_guard_band, 5),
        "disagreement_ceiling": round(disagreement_ceiling, 5),
        "checkpoint_path": str(checkpoint_path),
        "supported_bounds": supported_bounds,
    }

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Ensemble training complete! Checkpoint saved to {checkpoint_path}")
    return metadata


def load_surrogate_ensemble(checkpoint_path: str = "models/surrogate_ensemble.pt") -> Tuple[SurrogateEnsemble, Dict[str, Any]]:
    """Load persisted PyTorch surrogate ensemble model and metadata."""
    p = Path(checkpoint_path)
    if not p.is_file():
        raise FileNotFoundError(f"Surrogate ensemble checkpoint not found at {checkpoint_path}")

    checkpoint = torch.load(p, map_location=torch.device("cpu"), weights_only=False)
    scaler = StandardScalerNumpy.from_dict(checkpoint["scaler"])

    models = []
    for s_dict in checkpoint["state_dicts"]:
        m = PowerFlowSurrogateMLP(input_dim=33, hidden_dim=128)
        m.load_state_dict(s_dict)
        m.eval()
        models.append(m)

    ensemble = SurrogateEnsemble(models, scaler)
    meta = {
        "calibrated_guard_band": float(checkpoint.get("calibrated_guard_band", 0.01)),
        "disagreement_ceiling": float(checkpoint.get("disagreement_ceiling", 0.015)),
        "supported_bounds": checkpoint.get("supported_bounds", {}),
        "seeds": checkpoint.get("seeds", [42, 43, 44]),
    }
    return ensemble, meta


if __name__ == "__main__":
    train_surrogate_ensemble()
