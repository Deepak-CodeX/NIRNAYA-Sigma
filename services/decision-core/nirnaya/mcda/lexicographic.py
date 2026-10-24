"""
Deterministic lexicographic priority ordering.

Ranks candidate strategies across hierarchical operational tiers (e.g. Life-Safety > EUE > Cost)
without arbitrary linear scalarization.
"""

from __future__ import annotations

from functools import cmp_to_key
from typing import Sequence

from nirnaya.domain.enums import FeasibilityStatus, ObjectiveDirection
from nirnaya.domain.models import CandidateStrategy, ObjectiveDefinition, validate_finite_number

DEFAULT_LEXICOGRAPHIC_TOLERANCE = 1e-4


def sort_lexicographic_priority(
    strategies: Sequence[CandidateStrategy],
    objectives: Sequence[ObjectiveDefinition],
    tolerance: float = DEFAULT_LEXICOGRAPHIC_TOLERANCE,
) -> list[CandidateStrategy]:
    """
    Sort candidate strategies by hierarchical objective priority.

    Precedence Hierarchy:
    ----------------------
    1. Feasibility: FEASIBLE strategies strictly precede INFEASIBLE and UNKNOWN candidates.
    2. Priority Rank Tiers: Evaluated from priority_rank 1 upward.
       At the first priority tier where |f_k(x) - f_k(y)| > tolerance:
       - MINIMIZE: Lower value ranks first.
       - MAXIMIZE: Higher value ranks first.
    3. Unranked Objectives: Objectives with priority_rank=None are evaluated after ranked ones,
       ordered deterministically by objective_id.
    4. Deterministic Tie-Breaking: Co-equal strategies break ties by strategy_id ascending,
       eliminating runtime floating-point non-determinism.
    """
    tol = validate_finite_number(float(tolerance), "tolerance")
    if tol < 0.0:
        raise ValueError(f"Tolerance must be non-negative, got {tolerance}")

    # Sort objectives: ranked first (by priority_rank ascending), then unranked (by objective_id)
    ordered_objectives: list[ObjectiveDefinition] = sorted(
        objectives,
        key=lambda obj: (
            0 if obj.priority_rank is not None else 1,
            obj.priority_rank if obj.priority_rank is not None else 0,
            obj.objective_id,
        ),
    )

    def compare_strategies(x: CandidateStrategy, y: CandidateStrategy) -> int:
        # Feasibility check: FEASIBLE precedes non-FEASIBLE
        x_feas = x.feasibility_status == FeasibilityStatus.FEASIBLE
        y_feas = y.feasibility_status == FeasibilityStatus.FEASIBLE
        if x_feas and not y_feas:
            return -1
        if not x_feas and y_feas:
            return 1

        # Compare objective by objective according to priority rank
        for obj in ordered_objectives:
            obj_id = obj.objective_id
            if obj_id not in x.objectives or obj_id not in y.objectives:
                continue

            val_x = x.objectives[obj_id]
            val_y = y.objectives[obj_id]
            diff = val_x - val_y

            if abs(diff) > tol:
                if obj.direction == ObjectiveDirection.MINIMIZE:
                    return -1 if diff < 0 else 1
                else:  # MAXIMIZE
                    return -1 if diff > 0 else 1

        # All objectives co-equal within tolerance: break tie deterministically by strategy_id
        if x.strategy_id < y.strategy_id:
            return -1
        elif x.strategy_id > y.strategy_id:
            return 1
        return 0

    return sorted(strategies, key=cmp_to_key(compare_strategies))
