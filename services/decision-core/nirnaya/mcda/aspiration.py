"""
Chebyshev goal programming aspiration distance.

Calculates the minimax weighted distance from a candidate strategy's objective vector
to an ideal aspiration point f* normalized by the nadir range.
"""

from __future__ import annotations

import math
from typing import Sequence

from nirnaya.domain.models import CandidateStrategy, ObjectiveDefinition, validate_finite_number

DEFAULT_STABILIZATION_DELTA = 1e-9


def compute_chebyshev_aspiration_distance(
    strategy: CandidateStrategy,
    aspiration_point: dict[str, float],
    nadir_point: dict[str, float],
    weights: dict[str, float] | None = None,
    objectives: Sequence[ObjectiveDefinition] | None = None,
    delta: float = DEFAULT_STABILIZATION_DELTA,
) -> float:
    """
    Compute Chebyshev aspiration distance:
    D_inf(x) = max_k [ lambda_k * |f_k(x) - f_k*| / (|f_k^nadir - f_k*| + delta) ]

    Parameters:
    -----------
    strategy:
        Evaluated CandidateStrategy with objective metrics.
    aspiration_point:
        Ideal target values f_k* for each objective.
    nadir_point:
        Worst-case reference bounds f_k^nadir across the non-dominated set.
    weights:
        Optional positive objective weights lambda_k. Normalized to sum to 1.0.
    objectives:
        Optional sequence of ObjectiveDefinitions for validation.
    delta:
        Small positive constant to prevent division by zero when nadir == aspiration.

    Returns:
    --------
    Non-negative Chebyshev distance D_inf(x) in [0.0, inf).
    """
    if not aspiration_point:
        raise ValueError("Aspiration point cannot be empty")
    if not nadir_point:
        raise ValueError("Nadir point cannot be empty")

    delta_val = validate_finite_number(float(delta), "delta")
    if delta_val <= 0.0:
        raise ValueError(f"Stabilization delta must be strictly positive, got {delta}")

    # Determine objective keys to evaluate
    keys = list(aspiration_point.keys())
    for k in keys:
        if k not in nadir_point:
            raise ValueError(f"Objective '{k}' in aspiration_point is missing from nadir_point")
        if k not in strategy.objectives:
            raise ValueError(f"Objective '{k}' in aspiration_point is missing from strategy objectives")

    # Validate weights or create uniform
    k_count = len(keys)
    normalized_weights: dict[str, float] = {}
    if weights is not None:
        raw_weights = {}
        for k in keys:
            if k not in weights:
                raise ValueError(f"Missing weight for objective '{k}'")
            w = validate_finite_number(float(weights[k]), f"weights['{k}']")
            if w < 0.0:
                raise ValueError(f"Weight for objective '{k}' must be non-negative, got {w}")
            raw_weights[k] = w

        sum_w = sum(raw_weights.values())
        if sum_w <= 0.0:
            raise ValueError("Sum of weights must be strictly positive")
        for k in keys:
            normalized_weights[k] = raw_weights[k] / sum_w
    else:
        for k in keys:
            normalized_weights[k] = 1.0 / k_count

    max_dist = 0.0
    for k in keys:
        f_x = validate_finite_number(float(strategy.objectives[k]), f"strategy.objectives['{k}']")
        f_star = validate_finite_number(float(aspiration_point[k]), f"aspiration_point['{k}']")
        f_nadir = validate_finite_number(float(nadir_point[k]), f"nadir_point['{k}']")

        range_k = abs(f_nadir - f_star) + delta_val
        component_dist = normalized_weights[k] * (abs(f_x - f_star) / range_k)

        if component_dist > max_dist:
            max_dist = component_dist

    return float(max_dist)
