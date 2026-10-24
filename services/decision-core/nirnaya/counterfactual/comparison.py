"""
Counterfactual baseline comparison engine for NIRNAYA decision strategies.

Implements explicit baseline-vs-candidate delta quantification:
- Signed difference convention: Delta f_k(x) = f_k(x) - f_k(x0).
- Directional impact assessment: IMPROVEMENT, DEGRADATION, EQUAL, UNKNOWN.
- Preserves explicit physical units for every delta.
- Enforces epistemic boundary (flags comparisons as SIMULATED_COUNTERFACTUAL).
- Chains cryptographic evidence provenance between candidate and baseline.
- Handles missing or non-finite values fail-closed as UNKNOWN.
"""

from __future__ import annotations

import math
from typing import Sequence

from nirnaya.domain.enums import (
    DeltaImpact,
    EpistemicCategory,
    ObjectiveDirection,
)
from nirnaya.domain.models import (
    BaselineComparisonResult,
    CandidateStrategy,
    CounterfactualBaseline,
    ObjectiveDefinition,
    ObjectiveDelta,
)


def compute_baseline_comparison(
    candidate: CandidateStrategy,
    baseline: CounterfactualBaseline,
    objectives: Sequence[ObjectiveDefinition],
) -> BaselineComparisonResult:
    """
    Compute objective-wise relative differences between a candidate strategy and a counterfactual baseline.

    Parameters:
    - candidate: The evaluated CandidateStrategy.
    - baseline: The typed CounterfactualBaseline comparator.
    - objectives: Ordered sequence of ObjectiveDefinition instances.

    Returns:
    - BaselineComparisonResult with exact signed deltas, directional impact classifications,
      and chained evidence provenance.
    """
    if not objectives:
        raise ValueError("At least one ObjectiveDefinition is required for baseline comparison.")

    deltas: dict[str, ObjectiveDelta] = {}
    net_improvements = 0
    net_degradations = 0
    equal_count = 0
    unknown_count = 0

    for obj in objectives:
        obj_id = obj.objective_id
        cand_val = candidate.objectives.get(obj_id)
        base_val = baseline.objectives.get(obj_id)

        # 1. Missing or non-finite value check
        if (
            cand_val is None
            or base_val is None
            or not math.isfinite(cand_val)
            or not math.isfinite(base_val)
        ):
            deltas[obj_id] = ObjectiveDelta(
                objective_id=obj_id,
                candidate_value=cand_val if (cand_val is not None and math.isfinite(cand_val)) else None,
                baseline_value=base_val if (base_val is not None and math.isfinite(base_val)) else None,
                raw_delta=None,
                unit=obj.unit,
                direction=obj.direction,
                impact=DeltaImpact.UNKNOWN,
                explanation=(
                    f"UNKNOWN: Objective '{obj_id}' is missing or non-finite in candidate or baseline "
                    f"(candidate={cand_val}, baseline={base_val})."
                ),
            )
            unknown_count += 1
            continue

        # 2. Unit mismatch check
        cand_unit = candidate.objective_units.get(obj_id)
        base_unit = baseline.objective_units.get(obj_id)
        if (cand_unit is not None and cand_unit != obj.unit) or (
            base_unit is not None and base_unit != obj.unit
        ):
            deltas[obj_id] = ObjectiveDelta(
                objective_id=obj_id,
                candidate_value=cand_val,
                baseline_value=base_val,
                raw_delta=None,
                unit=obj.unit,
                direction=obj.direction,
                impact=DeltaImpact.UNKNOWN,
                explanation=(
                    f"UNKNOWN: Unit mismatch on objective '{obj_id}'. "
                    f"Expected '{obj.unit}', candidate has '{cand_unit}', baseline has '{base_unit}'."
                ),
            )
            unknown_count += 1
            continue

        # 3. Arithmetic delta calculation: Delta = Candidate - Baseline
        raw_delta = cand_val - base_val

        # 4. Directional impact assessment
        if obj.direction == ObjectiveDirection.MINIMIZE:
            if raw_delta < 0:
                impact = DeltaImpact.IMPROVEMENT
                net_improvements += 1
                explanation = f"Improvement: {abs(raw_delta):.6g} {obj.unit} lower than baseline."
            elif raw_delta > 0:
                impact = DeltaImpact.DEGRADATION
                net_degradations += 1
                explanation = f"Degradation: {raw_delta:.6g} {obj.unit} higher than baseline."
            else:
                impact = DeltaImpact.EQUAL
                equal_count += 1
                explanation = f"Equal: identical to baseline ({cand_val:.6g} {obj.unit})."

        elif obj.direction == ObjectiveDirection.MAXIMIZE:
            if raw_delta > 0:
                impact = DeltaImpact.IMPROVEMENT
                net_improvements += 1
                explanation = f"Improvement: {raw_delta:.6g} {obj.unit} higher than baseline."
            elif raw_delta < 0:
                impact = DeltaImpact.DEGRADATION
                net_degradations += 1
                explanation = f"Degradation: {abs(raw_delta):.6g} {obj.unit} lower than baseline."
            else:
                impact = DeltaImpact.EQUAL
                equal_count += 1
                explanation = f"Equal: identical to baseline ({cand_val:.6g} {obj.unit})."

        else:
            raise ValueError(f"Unsupported objective direction '{obj.direction}' for '{obj_id}'.")

        deltas[obj_id] = ObjectiveDelta(
            objective_id=obj_id,
            candidate_value=cand_val,
            baseline_value=base_val,
            raw_delta=raw_delta,
            unit=obj.unit,
            direction=obj.direction,
            impact=impact,
            explanation=explanation,
        )

    # 5. Chained evidence references
    candidate_refs = candidate.metadata.get("evidence_refs", []) if isinstance(candidate.metadata, dict) else []
    chained_refs = list(dict.fromkeys(candidate_refs + baseline.evidence_refs))

    summary_explanation = (
        f"Counterfactual comparison of '{candidate.strategy_id}' against '{baseline.baseline_id}' "
        f"({baseline.baseline_type.value}): {net_improvements} improvements, {net_degradations} degradations, "
        f"{equal_count} equal, {unknown_count} unknown. Epistemic status: SIMULATED_COUNTERFACTUAL."
    )

    return BaselineComparisonResult(
        candidate_strategy_id=candidate.strategy_id,
        baseline_id=baseline.baseline_id,
        deltas=deltas,
        net_improvements_count=net_improvements,
        net_degradations_count=net_degradations,
        equal_count=equal_count,
        unknown_count=unknown_count,
        evidence_refs=chained_refs,
        epistemic_status=EpistemicCategory.SIMULATED_COUNTERFACTUAL,
        summary_explanation=summary_explanation,
    )
