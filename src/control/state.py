"""
State and Action representations and battery dynamics for VoltPredict multi-step control.
Contract defined in PRD Section 4.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Union
import yaml


@dataclass(frozen=True)
class Action:
    """
    Control action applied at a single discrete time step.
    
    Signed battery dispatch convention (PRD Section 4):
    - battery_mw > 0: DISCHARGE (generator behavior, injects power into grid to relieve undervoltage/peak)
    - battery_mw < 0: CHARGE (load behavior, absorbs surplus solar from grid to relieve overvoltage)
    - battery_mw == 0: IDLE
    """
    battery_mw: float = 0.0
    curtail_pct: float = 0.0
    switch_toggle: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "battery_mw": round(float(self.battery_mw), 4),
            "curtail_pct": round(float(self.curtail_pct), 2),
            "switch_toggle": int(self.switch_toggle) if self.switch_toggle is not None else None,
        }


@dataclass(frozen=True)
class State:
    """
    Discrete operational state of the distribution grid at time step t.
    Contract defined in PRD Section 4:
    - t: discrete time step index (0, 1, ...)
    - soc: battery state of charge as a fraction in [0.0, 1.0]
    - switch_state: immutable mapping of switch_id -> is_closed (tuple of pairs)
    - curtail_level: current curtailment percentage applied to PV units
    """
    t: int
    soc: float
    switch_state: Tuple[Tuple[int, bool], ...]
    curtail_level: float = 0.0

    @property
    def switch_dict(self) -> Dict[int, bool]:
        return dict(self.switch_state)

    def is_switch_closed(self, switch_id: int) -> bool:
        return self.switch_dict.get(switch_id, False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "t": int(self.t),
            "soc": round(float(self.soc), 4),
            "switch_state": {int(k): bool(v) for k, v in self.switch_state},
            "curtail_level": round(float(self.curtail_level), 2),
        }


@dataclass
class GridLimits:
    v_min: float = 0.95
    v_max: float = 1.05
    max_loading_pct: float = 100.0


@dataclass
class BatteryLimits:
    capacity_mwh: float = 2.0
    max_power_mw: float = 1.0
    soc_min: float = 0.1
    soc_max: float = 0.9
    efficiency: float = 0.95
    bus_id: int = 5


@dataclass
class ControlWeights:
    renewable_weight: float = 10.0
    switching_penalty: float = 5.0
    battery_cycling_penalty: float = 2.0
    violation_penalty: float = 1000.0


@dataclass
class ControlConfig:
    dt_hours: float = 1.0
    horizon_steps: int = 8
    showcase_horizon_steps: int = 12
    beam_width: int = 5
    curtail_levels: List[float] = field(default_factory=lambda: [0.0, 10.0, 25.0, 50.0])
    battery_levels: List[float] = field(default_factory=lambda: [-1.0, -0.5, 0.0, 0.5, 1.0])
    switch_budget: int = 2
    weights: ControlWeights = field(default_factory=ControlWeights)


@dataclass
class SurrogateRange:
    solar_min_pu: float = 0.0
    solar_max_pu: float = 2.5
    load_min_pu: float = 0.2
    load_max_pu: float = 2.2


@dataclass
class SurrogateConfig:
    supported_range: SurrogateRange = field(default_factory=SurrogateRange)
    guard_band: float = 0.01
    disagreement_ceiling: float = 0.015


@dataclass
class LimitsConfig:
    seed: int = 42
    grid: GridLimits = field(default_factory=GridLimits)
    battery: BatteryLimits = field(default_factory=BatteryLimits)
    control: ControlConfig = field(default_factory=ControlConfig)
    surrogate: SurrogateConfig = field(default_factory=SurrogateConfig)


def load_limits_config(config_path: Union[str, Path] = "config/limits.yaml") -> LimitsConfig:
    """Load configuration from config/limits.yaml with type-safe defaults."""
    p = Path(config_path)
    if not p.is_file():
        # Fallback to root or default if path not resolved
        alt = Path(__file__).resolve().parent.parent.parent / "config" / "limits.yaml"
        if alt.is_file():
            p = alt
        else:
            return LimitsConfig()

    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    grid_data = data.get("grid", {})
    batt_data = data.get("battery", {})
    ctrl_data = data.get("control", {})
    weights_data = ctrl_data.get("weights", {})
    surr_data = data.get("surrogate", {})
    range_data = surr_data.get("supported_range", {})

    return LimitsConfig(
        seed=int(data.get("seed", 42)),
        grid=GridLimits(
            v_min=float(grid_data.get("v_min", 0.95)),
            v_max=float(grid_data.get("v_max", 1.05)),
            max_loading_pct=float(grid_data.get("max_loading_pct", 100.0)),
        ),
        battery=BatteryLimits(
            capacity_mwh=float(batt_data.get("capacity_mwh", 2.0)),
            max_power_mw=float(batt_data.get("max_power_mw", 1.0)),
            soc_min=float(batt_data.get("soc_min", 0.1)),
            soc_max=float(batt_data.get("soc_max", 0.9)),
            efficiency=float(batt_data.get("efficiency", 0.95)),
            bus_id=int(batt_data.get("bus_id", 5)),
        ),
        control=ControlConfig(
            dt_hours=float(ctrl_data.get("dt_hours", 1.0)),
            horizon_steps=int(ctrl_data.get("horizon_steps", 8)),
            showcase_horizon_steps=int(ctrl_data.get("showcase_horizon_steps", 12)),
            beam_width=int(ctrl_data.get("beam_width", 5)),
            curtail_levels=[float(x) for x in ctrl_data.get("curtail_levels", [0.0, 10.0, 25.0, 50.0])],
            battery_levels=[float(x) for x in ctrl_data.get("battery_levels", [-1.0, -0.5, 0.0, 0.5, 1.0])],
            switch_budget=int(ctrl_data.get("switch_budget", 2)),
            weights=ControlWeights(
                renewable_weight=float(weights_data.get("renewable_weight", 10.0)),
                switching_penalty=float(weights_data.get("switching_penalty", 5.0)),
                battery_cycling_penalty=float(weights_data.get("battery_cycling_penalty", 2.0)),
                violation_penalty=float(weights_data.get("violation_penalty", 1000.0)),
            ),
        ),
        surrogate=SurrogateConfig(
            supported_range=SurrogateRange(
                solar_min_pu=float(range_data.get("solar_min_pu", 0.0)),
                solar_max_pu=float(range_data.get("solar_max_pu", 2.5)),
                load_min_pu=float(range_data.get("load_min_pu", 0.2)),
                load_max_pu=float(range_data.get("load_max_pu", 2.2)),
            ),
            guard_band=float(surr_data.get("guard_band", 0.01)),
            disagreement_ceiling=float(surr_data.get("disagreement_ceiling", 0.015)),
        ),
    )


def update_soc(
    current_soc: float,
    battery_mw: float,
    dt_hours: float,
    capacity_mwh: float,
    efficiency: float,
) -> float:
    """
    Compute next battery State of Charge (SOC) with explicit charge/discharge efficiency.
    
    Physics Formula (documented in NOTES.md Section 11):
    - When charging (battery_mw < 0):
        Power drawn from grid = |battery_mw| = -battery_mw.
        Stored energy increment = (-battery_mw) * dt_hours * efficiency.
        SOC_{t+1} = SOC_t + [(-battery_mw) * dt_hours * efficiency] / capacity_mwh
    - When discharging (battery_mw > 0):
        Power injected to grid = battery_mw.
        Internal energy depleted = (battery_mw * dt_hours) / efficiency.
        SOC_{t+1} = SOC_t - [battery_mw * dt_hours / efficiency] / capacity_mwh
    - When idle (battery_mw == 0):
        SOC_{t+1} = SOC_t
        
    Args:
        current_soc: Current SOC as fraction in [0.0, 1.0]
        battery_mw: Signed dispatch (+ = discharge, - = charge)
        dt_hours: Step duration in hours
        capacity_mwh: Battery capacity in MWh
        efficiency: One-way electrical conversion efficiency (e.g. 0.95)
        
    Returns:
        float: Updated SOC value
    """
    if capacity_mwh <= 0.0:
        return current_soc

    if battery_mw < 0.0:
        # Charging: absorbs power from grid into battery
        delta_soc = (-battery_mw * dt_hours * efficiency) / capacity_mwh
        return float(current_soc + delta_soc)
    elif battery_mw > 0.0:
        # Discharging: injects power into grid from battery
        eff = max(efficiency, 1e-4)
        delta_soc = (battery_mw * dt_hours / eff) / capacity_mwh
        return float(current_soc - delta_soc)
    else:
        return float(current_soc)


def is_action_admissible(
    current_soc: float,
    action: Action,
    limits: LimitsConfig,
    tolerance: float = 1e-6,
) -> Tuple[bool, str]:
    """
    Validate whether an action satisfies hard constraints before physical power-flow calculation.
    
    Hard constraints checked:
    1. Maximum battery power rating (|battery_mw| <= max_power_mw)
    2. Next SOC within bounds (soc_min <= next_soc <= soc_max)
    3. Valid curtailment bounds (0 <= curtail_pct <= 100)
    
    Returns:
        Tuple[bool, str]: (is_admissible, reason_if_inadmissible)
    """
    # 1. Power limit
    if abs(action.battery_mw) > limits.battery.max_power_mw + tolerance:
        return False, (
            f"Power {action.battery_mw:+.2f} MW exceeds maximum battery rating "
            f"{limits.battery.max_power_mw:.2f} MW"
        )

    # 2. Curtailment range
    if action.curtail_pct < -tolerance or action.curtail_pct > 100.0 + tolerance:
        return False, f"Curtailment {action.curtail_pct:.1f}% out of valid bounds [0, 100]"

    # 3. Next SOC bounds
    next_soc = update_soc(
        current_soc=current_soc,
        battery_mw=action.battery_mw,
        dt_hours=limits.control.dt_hours,
        capacity_mwh=limits.battery.capacity_mwh,
        efficiency=limits.battery.efficiency,
    )

    if next_soc < limits.battery.soc_min - tolerance:
        return False, (
            f"Action would deplete battery SOC to {next_soc * 100:.1f}%, "
            f"below minimum bound {limits.battery.soc_min * 100:.1f}%"
        )

    if next_soc > limits.battery.soc_max + tolerance:
        return False, (
            f"Action would saturate battery SOC to {next_soc * 100:.1f}%, "
            f"above maximum bound {limits.battery.soc_max * 100:.1f}%"
        )

    return True, ""


def update_switch_state(
    current_state: Tuple[Tuple[int, bool], ...],
    toggle_id: Optional[int],
) -> Tuple[Tuple[int, bool], ...]:
    """Return new immutable switch state with toggle applied if specified."""
    if toggle_id is None:
        return current_state

    current_dict = dict(current_state)
    if toggle_id in current_dict:
        current_dict[toggle_id] = not current_dict[toggle_id]
    else:
        current_dict[toggle_id] = True

    return tuple(sorted(current_dict.items()))
