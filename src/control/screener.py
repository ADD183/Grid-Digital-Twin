"""
Candidate Action Screener for VoltPredict.
Contract defined in PRD Section 4:
screen(candidates) -> list[ScreenResult]:
    status in {'safe', 'unsafe', 'uncertain', 'unsupported'}, predicted_margin, disagreement, infer_ms.
NullScreener returns 'uncertain' for everything so every candidate reaches the solver (CP5 baseline).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from src.control.state import State, Action


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


def screen(
    candidates: List[Tuple[State, Action, Dict[str, Any]]],
    screener_instance: BaseScreener = NullScreener(),
) -> List[ScreenResult]:
    """Functional screening contract."""
    return screener_instance.screen(candidates)
