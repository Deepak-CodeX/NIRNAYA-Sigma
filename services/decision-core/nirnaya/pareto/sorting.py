"""
Deterministic Non-Dominated Sorting and Pareto Comparison Engine.

Implements the canonical Fast Non-Dominated Sort (NSGA-II core) for NIRNAYA:
- Partitions candidates by feasibility status: FEASIBLE, INFEASIBLE, UNKNOWN.
- Evaluates Pareto dominance ONLY over verified FEASIBLE strategies.
- Quarantines strategies with missing or non-finite objective metrics.
- Deterministic front assignment and stable tie-breaking across equal and incomparable vectors.
- Strict separation of objective Pareto dominance from subjective weighting.
"""

from __future__ import annotations

import math
from typing import Sequence

from nirnaya.domain.enums import (
    DominanceRelation,
    FeasibilityStatus,
)
from nirnaya.domain.models import (
    CandidateStrategy,
    ObjectiveDefinition,
    ParetoComparisonResult,
    ParetoFront,
)
from nirnaya.pareto.dominance import check_pareto_dominance


def compute_pareto_comparison(
    candidates: Sequence[CandidateStrategy],
    objectives: Sequence[ObjectiveDefinition],
    *,
    problem_id: str,
    comparison_id: str,
) -> ParetoComparisonResult:
    """
    Perform multi-objective Pareto trade-off analysis over a set of evaluated candidates.

    Parameters:
    - candidates: Sequence of evaluated CandidateStrategy instances.
    - objectives: Sequence of ObjectiveDefinition instances defining comparison dimensions.
    - problem_id: Unique identifier of the decision problem.
    - comparison_id: Unique identifier for this comparison run.

    Returns:
    - ParetoComparisonResult containing:
        * pareto_frontier (Front 1 non-dominated feasible candidates)
        * dominated_strategies (Dominated feasible candidates, Fronts 2+)
        * infeasible_strategies (Strategies failing hard physical constraints)
        * unknown_strategies (Strategies with unverified feasibility or missing metrics)
        * all_fronts (Complete rank-ordered Pareto fronts)
        * incomparable_pairs_count and equal_pairs_count
    """
    if not objectives:
        raise ValueError("At least one ObjectiveDefinition is required for Pareto comparison.")

    # 1. Partition candidates strictly by feasibility policy
    feasible_candidates: list[CandidateStrategy] = []
    infeasible_candidates: list[CandidateStrategy] = []
    unknown_candidates: list[CandidateStrategy] = []

    for c in candidates:
        if c.feasibility_status == FeasibilityStatus.INFEASIBLE:
            infeasible_candidates.append(c)
        elif c.feasibility_status == FeasibilityStatus.UNKNOWN:
            unknown_candidates.append(c)
        elif c.feasibility_status == FeasibilityStatus.FEASIBLE:
            # Verify that all required objectives are present, have valid units, and are finite
            is_valid = True
            for obj in objectives:
                val = c.objectives.get(obj.objective_id)
                if val is None or not math.isfinite(val):
                    is_valid = False
                    break
                # Unit check if provided on candidate
                unit = c.objective_units.get(obj.objective_id)
                if unit is not None and unit != obj.unit:
                    is_valid = False
                    break

            if is_valid:
                feasible_candidates.append(c)
            else:
                # Missing or non-finite objective metrics fail-closed into unknown set
                unknown_candidates.append(c)
        else:
            raise ValueError(f"Unknown feasibility status '{c.feasibility_status}' on '{c.strategy_id}'.")

    # Sort non-feasible partitions deterministically by strategy_id
    infeasible_candidates.sort(key=lambda s: s.strategy_id)
    unknown_candidates.sort(key=lambda s: s.strategy_id)

    # 2. Fast Non-Dominated Sort over feasible candidates
    n_feasible = len(feasible_candidates)
    if n_feasible == 0:
        return ParetoComparisonResult(
            comparison_id=comparison_id,
            problem_id=problem_id,
            pareto_frontier=[],
            dominated_strategies=[],
            infeasible_strategies=infeasible_candidates,
            unknown_strategies=unknown_candidates,
            all_fronts=[],
            incomparable_pairs_count=0,
            equal_pairs_count=0,
        )

    # S_p: list of strategy indices that strategy p dominates
    dominates_map: list[list[int]] = [[] for _ in range(n_feasible)]
    # n_p: number of strategies that dominate strategy p
    domination_count: list[int] = [0] * n_feasible

    incomparable_pairs = 0
    equal_pairs = 0

    for i in range(n_feasible):
        for j in range(i + 1, n_feasible):
            rel = check_pareto_dominance(
                feasible_candidates[i],
                feasible_candidates[j],
                objectives,
            )
            if rel == DominanceRelation.DOMINATES:
                dominates_map[i].append(j)
                domination_count[j] += 1
            elif rel == DominanceRelation.DOMINATED:
                dominates_map[j].append(i)
                domination_count[i] += 1
            elif rel == DominanceRelation.INCOMPARABLE:
                incomparable_pairs += 1
            elif rel == DominanceRelation.EQUAL:
                equal_pairs += 1

    # Front 1: All candidates with domination_count == 0
    front_1_indices = [i for i in range(n_feasible) if domination_count[i] == 0]
    # Stable deterministic tie-breaking by strategy_id
    front_1_indices.sort(key=lambda idx: feasible_candidates[idx].strategy_id)

    all_fronts: list[ParetoFront] = []
    current_front_indices = front_1_indices
    current_rank = 1

    while current_front_indices:
        current_strategies = [feasible_candidates[idx] for idx in current_front_indices]
        all_fronts.append(ParetoFront(rank=current_rank, strategies=current_strategies))

        next_front_indices: list[int] = []
        for p_idx in current_front_indices:
            for q_idx in dominates_map[p_idx]:
                domination_count[q_idx] -= 1
                if domination_count[q_idx] == 0:
                    next_front_indices.append(q_idx)

        # Stable deterministic tie-breaking by strategy_id
        next_front_indices.sort(key=lambda idx: feasible_candidates[idx].strategy_id)
        current_front_indices = next_front_indices
        current_rank += 1

    pareto_frontier = all_fronts[0].strategies
    dominated_strategies = [
        s for front in all_fronts[1:] for s in front.strategies
    ]

    return ParetoComparisonResult(
        comparison_id=comparison_id,
        problem_id=problem_id,
        pareto_frontier=pareto_frontier,
        dominated_strategies=dominated_strategies,
        infeasible_strategies=infeasible_candidates,
        unknown_strategies=unknown_candidates,
        all_fronts=all_fronts,
        incomparable_pairs_count=incomparable_pairs,
        equal_pairs_count=equal_pairs,
    )
