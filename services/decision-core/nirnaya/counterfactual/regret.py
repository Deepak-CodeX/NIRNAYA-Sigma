"""
Mathematical regret quantification engine for NIRNAYA decision strategies.

Implements decision-theoretic opportunity loss quantification:
- Raw objective-wise regret in native physical units:
    * MINIMIZE: Regret_k(x) = max(0, f_k(x) - min_{x' in B} f_k(x'))
    * MAXIMIZE: Regret_k(x) = max(0, max_{x' in B} f_k(x') - f_k(x))
- Normalized Chebyshev regret in [0.0, 1.0] scaled by benchmark range.
- Maximum Regret: max_k NormRegret_k(x).
- Distinguishes DECISION_TIME_ESTIMATE from EX_POST_OBSERVED regret types.
- Pure function with explicit benchmark inputs, zero solver dependency, and zero randomness.
"""

from __future__ import annotations

import math
from typing import Sequence

from nirnaya.domain.enums import (
    FeasibilityStatus,
    ObjectiveDirection,
    RegretType,
)
from nirnaya.domain.models import (
    CandidateStrategy,
    CounterfactualBaseline,
    ObjectiveDefinition,
    RegretMetrics,
)


def compute_regret_metrics(
    strategy: CandidateStrategy,
    benchmark_set: Sequence[CandidateStrategy | CounterfactualBaseline],
    objectives: Sequence[ObjectiveDefinition],
    *,
    regret_type: RegretType = RegretType.DECISION_TIME_ESTIMATE,
) -> RegretMetrics:
    """
    Quantify mathematical regret of choosing a strategy compared against an explicit benchmark set.

    Parameters:
    - strategy: The evaluated CandidateStrategy whose regret is being quantified.
    - benchmark_set: Admissible benchmark comparators (must contain at least 1 FEASIBLE candidate).
    - objectives: Sequence of ObjectiveDefinition dimensions.
    - regret_type: Temporal classification (DECISION_TIME_ESTIMATE or EX_POST_OBSERVED).

    Returns:
    - RegretMetrics containing raw objective regrets, normalized dimensionless regrets,
      and maximum normalized Chebyshev regret.

    Raises:
    - ValueError: If benchmark_set is empty, has no feasible candidates, or if required metrics are missing.
    """
    if not objectives:
        raise ValueError("At least one ObjectiveDefinition is required for regret quantification.")
    if not benchmark_set:
        raise ValueError("Benchmark set cannot be empty for regret quantification.")

    # 1. Filter benchmark set to verified FEASIBLE candidates with complete metrics
    valid_benchmarks: list[CandidateStrategy | CounterfactualBaseline] = []
    for b in benchmark_set:
        if b.feasibility_status != FeasibilityStatus.FEASIBLE:
            continue
        # Verify finite values across all objectives
        is_complete = True
        for obj in objectives:
            val = b.objectives.get(obj.objective_id)
            if val is None or not math.isfinite(val):
                is_complete = False
                break
        if is_complete:
            valid_benchmarks.append(b)

    if not valid_benchmarks:
        raise ValueError(
            "Benchmark set contains zero valid FEASIBLE candidates with complete objective metrics."
        )

    # 2. Strategy objective completeness check
    for obj in objectives:
        val = strategy.objectives.get(obj.objective_id)
        if val is None or not math.isfinite(val):
            raise ValueError(
                f"Strategy '{strategy.strategy_id}' lacks finite value for objective '{obj.objective_id}'."
            )

    objective_regrets: dict[str, float] = {}
    normalized_regrets: dict[str, float] = {}
    primary_driver = ""
    max_norm_regret = 0.0

    benchmark_ids = [
        getattr(b, "strategy_id", None) or getattr(b, "baseline_id", "UNKNOWN_BENCHMARK")
        for b in valid_benchmarks
    ]

    # 3. Calculate objective-wise raw and normalized regret
    for obj in objectives:
        obj_id = obj.objective_id
        strat_val = strategy.objectives[obj_id]
        benchmark_values = [b.objectives[obj_id] for b in valid_benchmarks]

        min_val = min(benchmark_values)
        max_val = max(benchmark_values)
        val_range = max_val - min_val

        if obj.direction == ObjectiveDirection.MINIMIZE:
            ideal_val = min_val
            raw_regret = max(0.0, strat_val - ideal_val)
        elif obj.direction == ObjectiveDirection.MAXIMIZE:
            ideal_val = max_val
            raw_regret = max(0.0, ideal_val - strat_val)
        else:
            raise ValueError(f"Unsupported objective direction '{obj.direction}' for '{obj_id}'.")

        # Normalize regret: in [0.0, 1.0] if range > 0, else 0.0
        if val_range > 0.0:
            norm_regret = min(1.0, max(0.0, raw_regret / val_range))
        else:
            norm_regret = 0.0

        objective_regrets[obj_id] = raw_regret
        normalized_regrets[obj_id] = norm_regret

        if norm_regret >= max_norm_regret:
            max_norm_regret = norm_regret
            primary_driver = obj_id

    explanation = (
        f"Regret ({regret_type.value}) for '{strategy.strategy_id}' across {len(valid_benchmarks)} benchmarks: "
        f"Max normalized regret is {max_norm_regret:.4f} driven by '{primary_driver}'."
    )

    return RegretMetrics(
        strategy_id=strategy.strategy_id,
        regret_type=regret_type,
        objective_regrets=objective_regrets,
        normalized_regrets=normalized_regrets,
        max_regret=max_norm_regret,
        benchmark_strategy_ids=benchmark_ids,
        explanation=explanation,
    )
