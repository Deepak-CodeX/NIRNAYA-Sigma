"""
Multi-criteria epsilon-constraint filtering.

Enforces statutory and policy thresholds on secondary objectives across candidate strategies
without universal scalarization.
"""

from __future__ import annotations

from typing import Sequence

from nirnaya.domain.enums import FeasibilityStatus, ObjectiveDirection
from nirnaya.domain.models import (
    CandidateStrategy,
    ObjectiveDefinition,
    validate_finite_number,
)

DEFAULT_EPSILON_TOLERANCE = 1e-4


def filter_epsilon_constraints(
    strategies: Sequence[CandidateStrategy],
    thresholds: dict[str, float],
    objectives: Sequence[ObjectiveDefinition],
    tolerance: float = DEFAULT_EPSILON_TOLERANCE,
) -> list[CandidateStrategy]:
    """
    Filter candidate strategies against strict policy thresholds:
    - MINIMIZE objectives: f_k(x) <= threshold_k + tolerance
    - MAXIMIZE objectives: f_k(x) >= threshold_k - tolerance

    Safety Invariants:
    ------------------
    - Only FEASIBLE strategies are eligible for selection. Infeasible and unknown strategies
      are excluded unconditionally.
    - Rejects undeclared or non-finite threshold objectives fail-closed.
    - If no strategy satisfies all policy limits, returns an empty list without crashing.
    """
    if not thresholds:
        return [s for s in strategies if s.feasibility_status == FeasibilityStatus.FEASIBLE]

    obj_map: dict[str, ObjectiveDefinition] = {obj.objective_id: obj for obj in objectives}

    # Validate all threshold keys and values fail-closed
    validated_thresholds: dict[str, float] = {}
    for obj_id, thresh_val in thresholds.items():
        clean_id = obj_id.strip()
        if clean_id not in obj_map:
            raise ValueError(
                f"Epsilon threshold references undeclared objective '{clean_id}'. "
                f"Registered objectives: {list(obj_map.keys())}"
            )
        validated_thresholds[clean_id] = validate_finite_number(
            float(thresh_val), f"thresholds['{clean_id}']"
        )

    tol = validate_finite_number(float(tolerance), "tolerance")
    if tol < 0.0:
        raise ValueError(f"Tolerance must be non-negative, got {tolerance}")

    surviving: list[CandidateStrategy] = []

    for strat in strategies:
        # Feasibility gate: only FEASIBLE strategies are admitted
        if strat.feasibility_status != FeasibilityStatus.FEASIBLE:
            continue

        satisfies_all = True
        for obj_id, threshold in validated_thresholds.items():
            if obj_id not in strat.objectives:
                satisfies_all = False
                break

            val = strat.objectives[obj_id]
            direction = obj_map[obj_id].direction

            if direction == ObjectiveDirection.MINIMIZE:
                if val > threshold + tol:
                    satisfies_all = False
                    break
            elif direction == ObjectiveDirection.MAXIMIZE:
                if val < threshold - tol:
                    satisfies_all = False
                    break

        if satisfies_all:
            surviving.append(strat)

    return surviving
