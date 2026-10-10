"""
Candidate Action Screener for VoltPredict (Checkpoint 7).
Contract defined in PRD Section 4:
screen(candidates) -> list[ScreenResult]:
    status in {'safe', 'unsafe', 'uncertain', 'unsupported'}, predicted_margin, disagreement, infer_ms.
NullScreener returns 'uncertain' for everything so every candidate reaches the solver (CP5 baseline).
SurrogateScreener uses the trained 3-seed PyTorch ensemble to screen risky states and drop unsafe candidates.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import time
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

from src.control.state import State, Action, LimitsConfig, load_limits_config
from src.grid import load_cigre_network


@dataclass
class ScreenResult:
    """
    Screener verdict for a single candidate action.
    - status: 'safe' (surrogate highly confident safe),
              'unsafe' (surrogate identified violation, drop candidate),
              'uncertain' (pass to physical solver),
              'unsupported' (outside operating range, pass to physical solver)
    - predicted_margin: Estimated signed distance to nearest limit
    - disagreement: Standard deviation across ensemble seeds
    - infer_ms: Neural network inference time in milliseconds
    """
    status: str
    predicted_margin: float
    disagreement: float
    infer_ms: float
    candidate_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": str(self.status),
            "predicted_margin": round(float(self.predicted_margin), 5),
            "disagreement": round(float(self.disagreement), 5),
            "infer_ms": round(float(self.infer_ms), 3),
            "candidate_index": int(self.candidate_index),
        }


@dataclass
class DisagreementEvent:
    """
    Log of a surrogate disagreement event where the surrogate predicted 'safe'
    but the physical solver rejected the candidate as unsafe or non-converged.
    """
    step: int
    action: Action
    predicted_margin: float
    solver_margin: float
    solver_is_safe: bool
    solver_violations: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": int(self.step),
            "action": self.action.to_dict(),
            "predicted_margin": round(float(self.predicted_margin), 5),
            "solver_margin": round(float(self.solver_margin), 5),
            "solver_is_safe": bool(self.solver_is_safe),
            "solver_violations_count": len(self.solver_violations),
            "solver_violations": self.solver_violations,
        }


class BaseScreener(ABC):
    """Abstract interface for candidate screening."""

    @abstractmethod
    def screen(
        self,
        candidates: List[Tuple[State, Action, Dict[str, Any]]],
    ) -> List[ScreenResult]:
        """Screen a batch of candidate actions."""
        pass


class NullScreener(BaseScreener):
    """
    Baseline screener for Checkpoint 5.
    Returns 'uncertain' for every candidate so that every candidate reaches
    the physical power-flow solver (pandapower) for evaluation.
    """

    def screen(
        self,
        candidates: List[Tuple[State, Action, Dict[str, Any]]],
    ) -> List[ScreenResult]:
        results = []
        for idx in range(len(candidates)):
            results.append(
                ScreenResult(
                    status="uncertain",
                    predicted_margin=0.0,
                    disagreement=0.0,
                    infer_ms=0.0,
                    candidate_index=idx,
                )
            )
        return results


class SurrogateScreener(BaseScreener):
    """
    Learned Surrogate Screener for Checkpoint 7.
    Evaluates candidate state/action pairs using PyTorch 3-seed ensemble.
    - 'unsafe': Candidate predicted to cause violation -> DROPPED without physical solver call.
    - 'safe': High-confidence safe (margin >= guard_band, low disagreement) -> Passed to physical solver for verification.
    - 'uncertain': Near-boundary or high disagreement -> Passed to physical solver for verification.
    - 'unsupported': Out of supported feature bounds -> Passed to physical solver as fallback.
    """

    def __init__(
        self,
        limits: Optional[LimitsConfig] = None,
        checkpoint_path: str = "models/surrogate_ensemble.pt",
    ):
        self.limits = limits or load_limits_config()
        self.checkpoint_path = checkpoint_path
        self.ensemble = None
        self.metadata = None
        self._load_model()

    def _load_model(self):
        try:
            from src.surrogate.train import load_surrogate_ensemble
            self.ensemble, self.metadata = load_surrogate_ensemble(self.checkpoint_path)
        except Exception:
            # Fallback if model checkpoint missing
            self.ensemble = None
            self.metadata = {
                "calibrated_guard_band": self.limits.surrogate.guard_band,
                "disagreement_ceiling": self.limits.surrogate.disagreement_ceiling,
                "supported_bounds": {},
            }

    def _build_candidate_features(
        self, state: State, action: Action, inputs: Dict[str, Any]
    ) -> Tuple[np.ndarray, bool]:
        """
        Build 33-dim feature vector for candidate state/action pair.
        Returns (features, is_out_of_bounds).
        """
        solar_scale = float(inputs.get("solar_scale", 1.0))
        load_scale = float(inputs.get("load_scale", 1.0))
        curtail_pct = float(action.curtail_pct)
        battery_mw = float(action.battery_mw)

        # Baseline CIGRE MV loads and sgen powers
        # Loads: Bus 1 (0.5MW), Bus 2 (0.4MW), Bus 3 (0.3MW), Bus 4 (0.6MW), Bus 5 (0.5MW), Bus 6 (0.2MW) ...
        # Standard synthetic scaling
        bus_p = np.zeros(15, dtype=np.float64)
        bus_q = np.zeros(15, dtype=np.float64)

        base_loads_p = {1: 0.5, 2: 0.4, 3: 0.3, 4: 0.6, 5: 0.5, 6: 0.2, 7: 0.4, 8: 0.3, 9: 0.2, 10: 0.3, 11: 0.3, 12: 0.4, 13: 0.3, 14: 0.2}
        base_loads_q = {k: v * 0.25 for k, v in base_loads_p.items()}

        for b, p in base_loads_p.items():
            bus_p[b] -= p * load_scale
            bus_q[b] -= base_loads_q[b] * load_scale

        # Solar DERs at Bus 3 (1.5MW), Bus 7 (2.0MW), Bus 10 (1.0MW), Bus 14 (1.5MW)
        effective_solar = solar_scale * (1.0 - curtail_pct / 100.0)
        base_solar_p = {3: 1.5, 7: 2.0, 10: 1.0, 14: 1.5}
        for b, p in base_solar_p.items():
            bus_p[b] += p * effective_solar

        # Battery storage at Bus 5: positive battery_mw = discharge (injects +MW)
        battery_bus = getattr(self.limits.battery, "bus_id", 5)
        bus_p[battery_bus] += battery_mw

        # Switches
        sw_dict = dict(state.switch_state)
        if action.switch_toggle is not None:
            sw_id = action.switch_toggle
            sw_dict[sw_id] = not sw_dict.get(sw_id, False)

        sw_feats = np.array([
            1.0 if sw_dict.get(1, False) else 0.0,
            1.0 if sw_dict.get(2, False) else 0.0,
            1.0 if sw_dict.get(4, False) else 0.0,
        ], dtype=np.float64)

        features = np.concatenate([bus_p, bus_q, sw_feats])

        # Supported range bounds check
        supp = self.metadata.get("supported_bounds", {})
        p_min = supp.get("p_mw_min", -8.0)
        p_max = supp.get("p_mw_max", 8.0)

        is_oob = bool(
            solar_scale > float(self.limits.surrogate.supported_range.solar_max_pu)
            or load_scale > float(self.limits.surrogate.supported_range.load_max_pu)
            or (bus_p < p_min).any()
            or (bus_p > p_max).any()
        )

        return features, is_oob

    def screen(
        self,
        candidates: List[Tuple[State, Action, Dict[str, Any]]],
    ) -> List[ScreenResult]:
        if not candidates:
            return []

        if self.ensemble is None:
            # Fallback to NullScreener behavior if model not loaded
            return NullScreener().screen(candidates)

        # Build feature matrix
        feats_list = []
        oob_flags = []
        for state, action, inputs in candidates:
            f_vec, is_oob = self._build_candidate_features(state, action, inputs)
            feats_list.append(f_vec)
            oob_flags.append(is_oob)

        x_raw = np.array(feats_list, dtype=np.float64)

        t0 = time.perf_counter()
        preds = self.ensemble.predict_batch(x_raw)
        t1 = time.perf_counter()

        batch_ms = (t1 - t0) * 1000.0
        single_ms = batch_ms / max(1, len(candidates))

        predicted_margins = preds["min_margin"]
        disagreements = preds["disagreement"]

        guard_band = float(self.metadata.get("calibrated_guard_band", self.limits.surrogate.guard_band))
        disagreement_ceiling = float(self.metadata.get("disagreement_ceiling", self.limits.surrogate.disagreement_ceiling))

        results = []
        for idx in range(len(candidates)):
            is_oob = oob_flags[idx]
            p_margin = float(predicted_margins[idx])
            disag = float(disagreements[idx])

            if is_oob:
                status = "unsupported"
            elif disag > disagreement_ceiling:
                status = "uncertain"
            elif p_margin >= guard_band:
                status = "safe"
            elif p_margin < 0.0:
                status = "unsafe"
            else:
                status = "uncertain"

            results.append(
                ScreenResult(
                    status=status,
                    predicted_margin=p_margin,
                    disagreement=disag,
                    infer_ms=single_ms,
                    candidate_index=idx,
                )
            )

        return results


def screen(
    candidates: List[Tuple[State, Action, Dict[str, Any]]],
    screener_instance: BaseScreener = NullScreener(),
) -> List[ScreenResult]:
    """Functional screening contract."""
    return screener_instance.screen(candidates)
