"""
Uncertainty propagation across multi-objective scenario realizations.

Propagates stochastic parameter realizations into objective distributions,
tail risk metrics, and counterfactual baseline performance deltas.
"""

from __future__ import annotations

from typing import Sequence

from nirnaya.domain.enums import LossConvention, ObjectiveDirection
from nirnaya.domain.models import (
    IDENTIFIER_REGEX,
    ObjectiveDefinition,
    RiskMetrics,
)
from nirnaya.uncertainty.risk import compute_risk_metrics


def propagate_scenario_uncertainty(
    strategy_id: str,
    scenario_evaluations: Sequence[dict[str, float]],
    objectives: Sequence[ObjectiveDefinition],
    confidence_level: float = 0.95,
    loss_thresholds: dict[str, float] | None = None,
    is_empirically_calibrated: bool = False,
    provenance_digest: str | None = None,
) -> dict[str, RiskMetrics]:
    """
    Propagate Monte Carlo or quasi-random scenario realizations into objective risk metrics.

    Parameters:
    -----------
    strategy_id:
        Identifier of the evaluated candidate strategy.
    scenario_evaluations:
        Sequence of objective evaluations, one dictionary per scenario realization:
        { "loss_mw": 12.4, "operating_cost": 420.0, ... }
    objectives:
        Registered objective definitions establishing optimization direction and units.
    confidence_level:
        Confidence level alpha for VaR and CVaR estimation (e.g. 0.95).
    loss_thresholds:
        Optional mapping of objective_id to statutory upper limit for robustness scoring.
    is_empirically_calibrated:
        Whether scenario inputs are certified against empirical sensor data.
    provenance_digest:
        Cryptographic digest verifying calibration provenance if calibrated is True.

    Returns:
    --------
    Mapping of objective_id to computed RiskMetrics.

    Fail-Closed Rules:
    ------------------
    - If scenario_evaluations is empty, raises ValueError.
    - If any scenario is missing an objective declared in objectives, raises ValueError.
    - Rejects invalid identifiers.
    """
    clean_strat = strategy_id.strip()
    if not clean_strat or not IDENTIFIER_REGEX.match(clean_strat):
        raise ValueError(f"strategy_id must match pattern '^[A-Za-z0-9_.-]+$', got '{strategy_id}'")

    if not objectives:
        raise ValueError("Must provide at least one ObjectiveDefinition")

    if not scenario_evaluations:
        raise ValueError(f"No scenario evaluations provided for strategy '{clean_strat}'")

    loss_thresholds = loss_thresholds or {}
    results: dict[str, RiskMetrics] = {}

    for obj in objectives:
        obj_id = obj.objective_id
        samples: list[float] = []

        for s_idx, scen in enumerate(scenario_evaluations):
            if obj_id not in scen:
                raise ValueError(
                    f"Scenario realization index {s_idx} is missing required objective '{obj_id}' "
                    f"for strategy '{clean_strat}'."
                )
            samples.append(scen[obj_id])

        # Directional mapping
        if obj.direction == ObjectiveDirection.MINIMIZE:
            convention = LossConvention.DIRECT_OBJECTIVE
        else:
            convention = LossConvention.NEGATIVE_OBJECTIVE

        threshold = loss_thresholds.get(obj_id)

        risk_res = compute_risk_metrics(
            objective_id=obj_id,
            samples=samples,
            confidence_level=confidence_level,
            unit=obj.unit,
            loss_convention=convention,
            loss_threshold=threshold,
            is_empirically_calibrated=is_empirically_calibrated,
            provenance_digest=provenance_digest,
        )
        results[obj_id] = risk_res

    return results


def propagate_counterfactual_uncertainty(
    candidate_strategy_id: str,
    baseline_id: str,
    candidate_scenario_evaluations: Sequence[dict[str, float]],
    baseline_scenario_evaluations: Sequence[dict[str, float]],
    objectives: Sequence[ObjectiveDefinition],
    confidence_level: float = 0.95,
) -> dict[str, RiskMetrics]:
    """
    Propagate scenario realizations through counterfactual delta comparisons:
    Delta f_k(x, s_j) = f_k(x, s_j) - f_k(x0, s_j).

    Parameters:
    -----------
    candidate_strategy_id:
        Identifier of the candidate operational strategy.
    baseline_id:
        Identifier of the counterfactual comparator.
    candidate_scenario_evaluations:
        Evaluations of the candidate strategy across scenarios.
    baseline_scenario_evaluations:
        Evaluations of the baseline strategy across the identical paired scenarios.
    objectives:
        Registered objective definitions.
    confidence_level:
        Risk confidence level alpha for delta tail estimation.

    Returns:
    --------
    Mapping of objective_id to RiskMetrics computed over the performance deltas.
    """
    clean_strat = candidate_strategy_id.strip()
    clean_base = baseline_id.strip()
    if not clean_strat or not IDENTIFIER_REGEX.match(clean_strat):
        raise ValueError(f"candidate_strategy_id must match pattern '^[A-Za-z0-9_.-]+$', got '{candidate_strategy_id}'")
    if not clean_base or not IDENTIFIER_REGEX.match(clean_base):
        raise ValueError(f"baseline_id must match pattern '^[A-Za-z0-9_.-]+$', got '{baseline_id}'")

    n_c = len(candidate_scenario_evaluations)
    n_b = len(baseline_scenario_evaluations)
    if n_c != n_b:
        raise ValueError(
            f"Mismatched paired scenario counts: candidate has {n_c} scenarios, "
            f"baseline has {n_b} scenarios."
        )

    delta_evaluations: list[dict[str, float]] = []
    for s_idx in range(n_c):
        c_scen = candidate_scenario_evaluations[s_idx]
        b_scen = baseline_scenario_evaluations[s_idx]
        delta_scen: dict[str, float] = {}

        for obj in objectives:
            obj_id = obj.objective_id
            if obj_id not in c_scen:
                raise ValueError(f"Candidate scenario {s_idx} missing objective '{obj_id}'")
            if obj_id not in b_scen:
                raise ValueError(f"Baseline scenario {s_idx} missing objective '{obj_id}'")

            # Delta convention: candidate - baseline
            delta_scen[obj_id] = float(c_scen[obj_id] - b_scen[obj_id])

        delta_evaluations.append(delta_scen)

    return propagate_scenario_uncertainty(
        strategy_id=clean_strat,
        scenario_evaluations=delta_evaluations,
        objectives=objectives,
        confidence_level=confidence_level,
        is_empirically_calibrated=False,
    )
