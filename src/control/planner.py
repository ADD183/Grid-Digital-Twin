"""
Rolling-Horizon Beam Search Planner for VoltPredict (Checkpoint 5).
Plans over horizon >= 8 steps, tracking battery SOC, equipment limits, and switching budget.
Implements the multi-objective score and explicit fallback ladder for infeasible periods.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import copy

from src.control.state import (
    State,
    Action,
    LimitsConfig,
    load_limits_config,
    update_soc,
    update_switch_state,
    is_action_admissible,
)
from src.control.verifier import Verifier, VerificationResult
from src.control.screener import BaseScreener, NullScreener, DisagreementEvent


@dataclass
class PlanResult:
    """Outcome of the rolling-horizon beam search."""
    best_action: Action
    best_sequence: List[Action]
    best_score: float
    solver_calls: int
    verification: VerificationResult
    infeasible: bool = False
    fallback_used: Optional[str] = None
    candidates_evaluated: int = 0
    all_step0_candidates: List[Dict[str, Any]] = field(default_factory=list)
    screener_safe_count: int = 0
    screener_unsafe_dropped_count: int = 0
    screener_uncertain_count: int = 0
    screener_unsupported_count: int = 0
    disagreement_events: List[DisagreementEvent] = field(default_factory=list)


class BeamSearchPlanner:
    """
    Rolling-horizon beam search planner.
    
    Hard constraints:
    - Battery power limit: |battery_mw| <= max_power_mw
    - State of charge bounds: soc_min <= next_soc <= soc_max
    - Feeder switching budget: total toggles in horizon <= switch_budget
    
    Multi-objective score (PRD Section 5):
    Score = renewable_energy_used - switching_penalty - battery_cycling_penalty - violation_penalty
    """

    def __init__(
        self,
        verifier: Optional[Verifier] = None,
        screener: Optional[BaseScreener] = None,
        limits: Optional[LimitsConfig] = None,
    ):
        self.limits = limits or load_limits_config()
        self.verifier = verifier or Verifier(self.limits)
        self.screener = screener or NullScreener()

    def generate_candidate_actions(
        self,
        current_state: State,
        remaining_switches: int,
        is_lookahead: bool = False,
    ) -> List[Action]:
        """Generate candidate actions spanning battery levels, curtailment levels, and switch toggles."""
        battery_levels = self.limits.control.battery_levels
        curtail_levels = self.limits.control.curtail_levels

        if is_lookahead:
            curtail_levels = sorted({min(curtail_levels), max(curtail_levels)})

        # At immediate step 0, explore tie-switches if budget allows; in lookahead keep switch fixed
        available_toggles: List[Optional[int]] = [None]
        if remaining_switches > 0 and not is_lookahead:
            available_toggles.extend([4, 1, 2])

        candidate_levels = [
            (b_mw, c_pct, None)
            for b_mw in battery_levels
            for c_pct in curtail_levels
        ]
        if len(available_toggles) > 1:
            switch_battery_levels = [
                level for level in battery_levels
                if level in {min(battery_levels), 0.0, max(battery_levels)}
            ]
            switch_curtail_levels = sorted({min(curtail_levels), max(curtail_levels)})
            candidate_levels.extend(
                (b_mw, c_pct, s_toggle)
                for b_mw in switch_battery_levels
                for c_pct in switch_curtail_levels
                for s_toggle in available_toggles[1:]
            )

        candidates = []
        for b_mw, c_pct, s_toggle in candidate_levels:
            action = Action(
                battery_mw=float(b_mw),
                curtail_pct=float(c_pct),
                switch_toggle=s_toggle,
            )
            admissible, _ = is_action_admissible(current_state.soc, action, self.limits)
            if admissible:
                candidates.append(action)

        return candidates

    def score_step_action(
        self,
        action: Action,
        verification: VerificationResult,
        solar_scale: float,
    ) -> float:
        """
        Compute step score:
        Score = renewable energy used - switching penalty - battery cycling penalty - violation penalty
        """
        weights = self.limits.control.weights
        dt = self.limits.control.dt_hours

        # 1. Renewable energy used (base PV capacity ~0.2 MW total across small rooftop DERs, scaled)
        clean_retained_factor = 1.0 - (action.curtail_pct / 100.0)
        renewable_used = solar_scale * clean_retained_factor * weights.renewable_weight

        # 2. Switching penalty
        switching_cost = weights.switching_penalty if action.switch_toggle is not None else 0.0

        # 3. Battery cycling penalty (cost on MWh throughput)
        battery_wear_cost = abs(action.battery_mw) * dt * weights.battery_cycling_penalty

        # 4. Physical safety term / violation penalty
        if verification.is_safe:
            # Reward safe state with additional positive headroom bonus
            safety_term = 500.0 + (verification.min_margin * 50.0)
        else:
            # Heavy penalty if violated
            viol_count = len(verification.violations)
            safety_term = -weights.violation_penalty * (1.0 + viol_count * 0.2 + abs(verification.min_margin) * 10.0)

        return renewable_used - switching_cost - battery_wear_cost + safety_term

    def execute_fallback_ladder(
        self,
        state: State,
        observed_inputs: Dict[str, Any],
        initial_violations: List[Dict[str, Any]],
    ) -> Tuple[Action, VerificationResult, bool, str]:
        """
        Execute the ordered fallback ladder when no normal candidate passes verification (PRD Section 5.5):
        (a) maximum battery support
        (b) maximum curtailment at the offending DER (plus battery)
        (c) alternate switch state
        
        If violations remain, mark infeasible=True, record residual violations and the fallback used.
        """
        # Determine violation nature
        is_overvoltage = any(v.get("violation_type") == "OVERVOLTAGE" for v in initial_violations)

        # Ladder Step (a): Maximum battery support respecting SOC bounds
        if is_overvoltage:
            # Need to absorb power -> charge battery (battery_mw < 0)
            max_charge = -self.limits.battery.max_power_mw
            # Check if admissible, else clamp
            test_act = Action(battery_mw=max_charge, curtail_pct=0.0, switch_toggle=None)
            admissible, _ = is_action_admissible(state.soc, test_act, self.limits)
            batt_a = max_charge if admissible else 0.0
        else:
            # Need to inject power -> discharge battery (battery_mw > 0)
            max_disch = self.limits.battery.max_power_mw
            test_act = Action(battery_mw=max_disch, curtail_pct=0.0, switch_toggle=None)
            admissible, _ = is_action_admissible(state.soc, test_act, self.limits)
            batt_a = max_disch if admissible else 0.0

        act_a = Action(battery_mw=batt_a, curtail_pct=0.0, switch_toggle=None)
        res_a = self.verifier.verify(state, act_a, observed_inputs)
        if res_a.is_safe:
            return act_a, res_a, False, "max_battery_support"

        # Ladder Step (b): Maximum curtailment at offending DER (plus battery)
        act_b = Action(battery_mw=batt_a, curtail_pct=100.0, switch_toggle=None)
        res_b = self.verifier.verify(state, act_b, observed_inputs)
        if res_b.is_safe:
            return act_b, res_b, False, "maximum_curtailment"

        # Ladder Step (c): Alternate switch state (e.g. tie switch S1 = 4)
        act_c = Action(battery_mw=batt_a, curtail_pct=100.0, switch_toggle=4)
        res_c = self.verifier.verify(state, act_c, observed_inputs)
        if res_c.is_safe:
            return act_c, res_c, False, "feeder_reconfiguration"

        # Ladder Step (d): Targeted Load shedding
        shed_inputs = copy.deepcopy(observed_inputs)
        orig_load = float(observed_inputs.get("load_scale", observed_inputs.get("load_pu", 1.0)))
        shed_inputs["load_scale"] = max(0.0, orig_load * 0.75)  # 25% targeted load shed
        shed_inputs["load_pu"] = max(0.0, float(observed_inputs.get("load_pu", orig_load)) * 0.75)
        act_d = Action(battery_mw=batt_a, curtail_pct=100.0, switch_toggle=4)
        res_d = self.verifier.verify(state, act_d, shed_inputs)
        if res_d.is_safe:
            return act_d, res_d, False, "load_shedding"

        # All 4 ladder levels tried; violations remain -> mark INFEASIBLE explicitly
        # Select best partial mitigation (highest min_margin / fewest violations)
        candidates = [
            (act_a, res_a, "max_battery_support"),
            (act_b, res_b, "maximum_curtailment"),
            (act_c, res_c, "feeder_reconfiguration"),
            (act_d, res_d, "load_shedding"),
        ]
        best_act, best_res, best_name = max(candidates, key=lambda c: c[1].min_margin)

        return best_act, best_res, True, f"infeasible_residual_{best_name}"

    def plan(
        self,
        current_state: State,
        forecast_horizon: List[Dict[str, Any]],
        beam_width: Optional[int] = None,
    ) -> PlanResult:
        """
        Execute rolling-horizon beam search over forecast_horizon.
        
        Args:
            current_state: State at start of horizon
            forecast_horizon: List of forecasts for at least horizon_steps
            beam_width: Number of paths to maintain (default from limits.yaml)
            
        Returns:
            PlanResult: Chosen verified action and full lookahead sequence
        """
        b_width = beam_width or self.limits.control.beam_width
        horizon_len = min(len(forecast_horizon), self.limits.control.horizon_steps)
        solver_calls = 0
        candidates_evaluated = 0

        # Each beam item: (cumulative_score, current_state, action_sequence, remaining_switch_budget, first_step_verification)
        beam: List[Tuple[float, State, List[Action], int, Optional[VerificationResult]]] = [
            (0.0, current_state, [], self.limits.control.switch_budget, None)
        ]

        step0_records: List[Dict[str, Any]] = []
        solve_cache: Dict[Tuple[int, float, float, Any, Any], VerificationResult] = {}

        screener_safe_count = 0
        screener_unsafe_dropped_count = 0
        screener_uncertain_count = 0
        screener_unsupported_count = 0
        disagreement_events: List[DisagreementEvent] = []

        for step_idx in range(horizon_len):
            step_forecast = forecast_horizon[step_idx]
            solar_scale = float(step_forecast.get("solar_scale", step_forecast.get("solar_pu", 1.0)))
            new_beam: List[Tuple[float, State, List[Action], int, Optional[VerificationResult]]] = []

            for cum_score, state_k, seq_k, rem_switches, first_verif in beam:
                candidates_k = self.generate_candidate_actions(state_k, rem_switches, is_lookahead=(step_idx > 0))
                candidates_evaluated += len(candidates_k)

                # Batch screening (NullScreener returns 'uncertain' for all; SurrogateScreener filters states)
                batch_for_screener = [(state_k, act, step_forecast) for act in candidates_k]
                screen_results = self.screener.screen(batch_for_screener)

                for act, s_res in zip(candidates_k, screen_results):
                    # Count screener statuses
                    if s_res.status == "unsafe":
                        screener_unsafe_dropped_count += 1
                        # Drop unsafe candidate without calling physical solver
                        continue
                    elif s_res.status == "safe":
                        screener_safe_count += 1
                    elif s_res.status == "unsupported":
                        screener_unsupported_count += 1
                    else:
                        screener_uncertain_count += 1

                    # Cache key for instantaneous grid electrical state
                    cache_key = (
                        step_idx,
                        round(float(act.battery_mw), 3),
                        round(float(act.curtail_pct), 1),
                        state_k.switch_state,
                        act.switch_toggle,
                    )
                    if cache_key in solve_cache:
                        verif = solve_cache[cache_key]
                    else:
                        verif = self.verifier.verify(state_k, act, step_forecast)
                        solver_calls += 1
                        solve_cache[cache_key] = verif

                    # Log disagreement event if surrogate predicted 'safe' but solver rejected candidate
                    if s_res.status == "safe" and not verif.is_safe:
                        disagreement_events.append(
                            DisagreementEvent(
                                step=step_idx,
                                action=act,
                                predicted_margin=s_res.predicted_margin,
                                solver_margin=verif.min_margin,
                                solver_is_safe=verif.is_safe,
                                solver_violations=verif.violations,
                            )
                        )

                    step_score = self.score_step_action(act, verif, solar_scale)
                    total_score = cum_score + step_score

                    # Advance state
                    next_soc = update_soc(
                        state_k.soc,
                        act.battery_mw,
                        self.limits.control.dt_hours,
                        self.limits.battery.capacity_mwh,
                        self.limits.battery.efficiency,
                    )
                    next_switches = update_switch_state(state_k.switch_state, act.switch_toggle)
                    next_state = State(
                        t=state_k.t + 1,
                        soc=next_soc,
                        switch_state=next_switches,
                        curtail_level=act.curtail_pct,
                    )
                    used_switch = 1 if act.switch_toggle is not None else 0
                    next_rem_switches = max(0, rem_switches - used_switch)

                    verif_to_carry = first_verif if first_verif is not None else verif

                    if step_idx == 0:
                        step0_records.append({
                            "action": act.to_dict(),
                            "is_safe": verif.is_safe,
                            "min_margin": verif.min_margin,
                            "violations_count": len(verif.violations),
                            "score": step_score,
                            "screener_status": s_res.status,
                        })

                    new_beam.append(
                        (total_score, next_state, seq_k + [act], next_rem_switches, verif_to_carry)
                    )

            # Prune beam to top b_width paths
            new_beam.sort(key=lambda item: item[0], reverse=True)
            beam = new_beam[:b_width]

        if not beam:
            raise RuntimeError("Beam search produced no admissible candidate paths.")

        # Best sequence from beam
        best_score, final_state, best_sequence, _, first_verif = beam[0]
        chosen_action = best_sequence[0] if best_sequence else Action()
        verification = first_verif or self.verifier.verify(current_state, chosen_action, forecast_horizon[0])

        # If best candidate is still unsafe, trigger the Fallback Ladder
        if not verification.is_safe:
            chosen_action, verification, infeasible, fallback_used = self.execute_fallback_ladder(
                current_state,
                forecast_horizon[0],
                verification.violations,
            )
            solver_calls += 3
            return PlanResult(
                best_action=chosen_action,
                best_sequence=[chosen_action] + best_sequence[1:],
                best_score=best_score,
                solver_calls=solver_calls,
                verification=verification,
                infeasible=infeasible,
                fallback_used=fallback_used,
                candidates_evaluated=candidates_evaluated,
                all_step0_candidates=step0_records,
                screener_safe_count=screener_safe_count,
                screener_unsafe_dropped_count=screener_unsafe_dropped_count,
                screener_uncertain_count=screener_uncertain_count,
                screener_unsupported_count=screener_unsupported_count,
                disagreement_events=disagreement_events,
            )

        return PlanResult(
            best_action=chosen_action,
            best_sequence=best_sequence,
            best_score=best_score,
            solver_calls=solver_calls,
            verification=verification,
            infeasible=False,
            fallback_used=None,
            candidates_evaluated=candidates_evaluated,
            all_step0_candidates=step0_records,
            screener_safe_count=screener_safe_count,
            screener_unsafe_dropped_count=screener_unsafe_dropped_count,
            screener_uncertain_count=screener_uncertain_count,
            screener_unsupported_count=screener_unsupported_count,
            disagreement_events=disagreement_events,
        )
