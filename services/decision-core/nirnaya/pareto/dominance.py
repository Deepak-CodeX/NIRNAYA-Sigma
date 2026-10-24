"""
Deterministic Pareto dominance evaluator for NIRNAYA decision strategies.

Implements strict Pareto dominance semantics:
- Evaluates dominance ONLY between FEASIBLE strategies.
- Evaluates multi-directional objectives (MINIMIZE and MAXIMIZE).
- Distinguishes strict dominance (DOMINATES, DOMINATED), equality (EQUAL),
  and multi-criteria trade-offs (INCOMPARABLE).
- Rejects missing, invalid, or non-finite objective metrics.
- Preserves explicit physical units.
"""

from __future__ import annotations

import math
from typing import Sequence

from nirnaya.domain.enums import (
    DominanceRelation,
    FeasibilityStatus,
    ObjectiveDirection,
)
from nirnaya.domain.models import (
    CandidateStrategy,
    ObjectiveDefinition,
)


def check_pareto_dominance(
    strategy_a: CandidateStrategy,
    strategy_b: CandidateStrategy,
    objectives: Sequence[ObjectiveDefinition],
) -> DominanceRelation:
    """
    Compare two candidate strategies to determine their Pareto dominance relationship.

    Parameters:
    - strategy_a: First candidate strategy (must be FEASIBLE).
    - strategy_b: Second candidate strategy (must be FEASIBLE).
    - objectives: Ordered sequence of objective definitions with physical units and directions.

    Returns:
    - DominanceRelation:
        * DOMINATES: strategy_a is at least as good on all objectives, and strictly better on >= 1.
        * DOMINATED: strategy_b is at least as good on all objectives, and strictly better on >= 1.
        * EQUAL: Numerically identical on all evaluated objectives.
        * INCOMPARABLE: Trade-off exists (strategy_a better on some, strategy_b better on others).

    Raises:
    - ValueError: If either strategy is not FEASIBLE, if required objectives are missing,
      or if units are inconsistent.
    """
    # 1. Feasibility policy enforcement
    if strategy_a.feasibility_status != FeasibilityStatus.FEASIBLE:
        raise ValueError(
            f"Pareto dominance is only defined for FEASIBLE strategies. "
            f"Strategy '{strategy_a.strategy_id}' has status {strategy_a.feasibility_status}."
        )
    if strategy_b.feasibility_status != FeasibilityStatus.FEASIBLE:
        raise ValueError(
            f"Pareto dominance is only defined for FEASIBLE strategies. "
            f"Strategy '{strategy_b.strategy_id}' has status {strategy_b.feasibility_status}."
        )

    # 2. Objectives presence and validity check
    if not objectives:
        raise ValueError("At least one ObjectiveDefinition is required for Pareto comparison.")

    better_a = 0
    better_b = 0

    for obj in objectives:
        obj_id = obj.objective_id

        if obj_id not in strategy_a.objectives:
            raise ValueError(
                f"Strategy '{strategy_a.strategy_id}' is missing required objective '{obj_id}'."
            )
        if obj_id not in strategy_b.objectives:
            raise ValueError(
                f"Strategy '{strategy_b.strategy_id}' is missing required objective '{obj_id}'."
            )

        # Check unit consistency if provided
        unit_a = strategy_a.objective_units.get(obj_id)
        if unit_a is not None and unit_a != obj.unit:
            raise ValueError(
                f"Physical unit mismatch on '{obj_id}' for strategy '{strategy_a.strategy_id}': "
                f"objective expects '{obj.unit}', strategy provides '{unit_a}'."
            )
        unit_b = strategy_b.objective_units.get(obj_id)
        if unit_b is not None and unit_b != obj.unit:
            raise ValueError(
                f"Physical unit mismatch on '{obj_id}' for strategy '{strategy_b.strategy_id}': "
                f"objective expects '{obj.unit}', strategy provides '{unit_b}'."
            )

        val_a = strategy_a.objectives[obj_id]
        val_b = strategy_b.objectives[obj_id]

        if not math.isfinite(val_a) or not math.isfinite(val_b):
            raise ValueError(
                f"Non-finite objective value detected on '{obj_id}': "
                f"val_a={val_a}, val_b={val_b}."
            )

        if obj.direction == ObjectiveDirection.MINIMIZE:
            if val_a < val_b:
                better_a += 1
            elif val_b < val_a:
                better_b += 1
        elif obj.direction == ObjectiveDirection.MAXIMIZE:
            if val_a > val_b:
                better_a += 1
            elif val_b > val_a:
                better_b += 1
        else:
            raise ValueError(f"Unsupported objective direction '{obj.direction}' for '{obj_id}'.")

    # 3. Determine Pareto relation
    if better_a > 0 and better_b == 0:
        return DominanceRelation.DOMINATES
    elif better_b > 0 and better_a == 0:
        return DominanceRelation.DOMINATED
    elif better_a == 0 and better_b == 0:
        return DominanceRelation.EQUAL
    else:
        # better_a > 0 and better_b > 0
        return DominanceRelation.INCOMPARABLE
