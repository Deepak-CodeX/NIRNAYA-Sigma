"""
Pure, deterministic hard-constraint evaluation engine for NIRNAYA.

Adheres strictly to Phase 0 specifications:
- Pure functions: no randomness, no wall-clock lookups, no network calls, no global state.
- Explicit inputs and machine-readable outputs with evidence references and explanations.
- Distinguishes proven violations (INFEASIBLE) from unverified telemetry (UNKNOWN).
- Enforces fail-closed safety invariant: overall status is NEVER FEASIBLE if any constraint is UNKNOWN.
- Applies numerical tolerances strictly as authorized on each constraint (no arbitrary global epsilon).
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from nirnaya.domain.enums import (
    ConstraintOperator,
    FeasibilityStatus,
    TelemetryQuality,
)
from nirnaya.domain.models import (
    ConstraintEvaluation,
    DecisionVariable,
    EvidenceReference,
    HardConstraint,
    HardConstraintSummary,
)


def evaluate_hard_constraint(
    constraint: HardConstraint,
    variable: DecisionVariable | float | None,
    evidence: EvidenceReference | None = None,
    *,
    max_freshness_seconds: float = 120.0,
    require_evidence: bool = False,
) -> ConstraintEvaluation:
    """
    Evaluate a single hard constraint deterministically against an observed variable value and evidence.

    Parameters:
    - constraint: The validated HardConstraint definition.
    - variable: The observed state variable (DecisionVariable, float, or None if missing).
    - evidence: Optional EvidenceReference validating telemetry acquisition.
    - max_freshness_seconds: Telemetry lockout threshold in seconds (default 120.0s per ADR-010).
    - require_evidence: If True, missing evidence forces an UNKNOWN outcome.

    Returns:
    - ConstraintEvaluation with deterministic FeasibilityStatus, violation magnitude, and explanation.
    """
    evidence_refs: list[str] = []
    if evidence is not None:
        evidence_refs.append(evidence.cryptographic_digest)

    # 1. Check for missing variable
    if variable is None:
        return ConstraintEvaluation(
            constraint_id=constraint.constraint_id,
            target_element=constraint.target_variable,
            status=FeasibilityStatus.UNKNOWN,
            observed_value=None,
            limit_value=constraint.limit_value,
            violation_magnitude=0.0,
            unit=constraint.unit,
            evidence_refs=evidence_refs,
            explanation=(
                f"Evaluation UNKNOWN: Target variable '{constraint.target_variable}' "
                f"is missing from observed system state."
            ),
        )

    # 2. Extract and validate observed numeric value
    if isinstance(variable, DecisionVariable):
        if variable.unit != constraint.unit:
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.UNKNOWN,
                observed_value=variable.value,
                limit_value=constraint.limit_value,
                violation_magnitude=0.0,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"Evaluation UNKNOWN: Physical unit mismatch for '{constraint.target_variable}'. "
                    f"Constraint requires '{constraint.unit}', but variable provides '{variable.unit}'."
                ),
            )
        obs_value = variable.value
    elif isinstance(variable, (int, float)):
        obs_val_float = float(variable)
        if not math.isfinite(obs_val_float):
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.UNKNOWN,
                observed_value=None,
                limit_value=constraint.limit_value,
                violation_magnitude=0.0,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"Evaluation UNKNOWN: Non-finite observed value ({variable}) "
                    f"for target variable '{constraint.target_variable}'."
                ),
            )
        obs_value = obs_val_float
    else:
        return ConstraintEvaluation(
            constraint_id=constraint.constraint_id,
            target_element=constraint.target_variable,
            status=FeasibilityStatus.UNKNOWN,
            observed_value=None,
            limit_value=constraint.limit_value,
            violation_magnitude=0.0,
            unit=constraint.unit,
            evidence_refs=evidence_refs,
            explanation=(
                f"Evaluation UNKNOWN: Unsupported variable type '{type(variable).__name__}' "
                f"for target variable '{constraint.target_variable}'."
            ),
        )

    # 3. Evidence sufficiency and freshness verification
    if require_evidence and evidence is None:
        return ConstraintEvaluation(
            constraint_id=constraint.constraint_id,
            target_element=constraint.target_variable,
            status=FeasibilityStatus.UNKNOWN,
            observed_value=obs_value,
            limit_value=constraint.limit_value,
            violation_magnitude=0.0,
            unit=constraint.unit,
            evidence_refs=evidence_refs,
            explanation=(
                f"Evaluation UNKNOWN: Telemetry evidence reference required but missing "
                f"for '{constraint.target_variable}'."
            ),
        )

    if evidence is not None:
        if evidence.is_stale:
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.UNKNOWN,
                observed_value=obs_value,
                limit_value=constraint.limit_value,
                violation_magnitude=0.0,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"Evaluation UNKNOWN: Telemetry evidence '{evidence.source_id}' is marked stale."
                ),
            )

        if evidence.freshness_seconds is not None and evidence.freshness_seconds > max_freshness_seconds:
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.UNKNOWN,
                observed_value=obs_value,
                limit_value=constraint.limit_value,
                violation_magnitude=0.0,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"Evaluation UNKNOWN: Telemetry evidence '{evidence.source_id}' freshness "
                    f"({evidence.freshness_seconds:.1f}s) exceeds lockout threshold ({max_freshness_seconds:.1f}s)."
                ),
            )

        if evidence.telemetry_quality == TelemetryQuality.UNRELIABLE:
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.UNKNOWN,
                observed_value=obs_value,
                limit_value=constraint.limit_value,
                violation_magnitude=0.0,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"Evaluation UNKNOWN: Telemetry evidence '{evidence.source_id}' "
                    f"has quality UNRELIABLE."
                ),
            )

    # 4. Pure mathematical boundary evaluation with authorized tolerance
    tol = constraint.tolerance
    op = constraint.operator

    if op == ConstraintOperator.LEQ:
        limit = float(constraint.limit_value)  # type: ignore[arg-type]
        threshold = limit + tol
        if obs_value <= threshold:
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.FEASIBLE,
                observed_value=obs_value,
                limit_value=limit,
                violation_magnitude=0.0,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"FEASIBLE: Observed {obs_value:.6g} {constraint.unit} <= limit {limit:.6g} "
                    f"{constraint.unit} (tolerance {tol:.6g} {constraint.unit})."
                ),
            )
        else:
            magnitude = obs_value - limit
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.INFEASIBLE,
                observed_value=obs_value,
                limit_value=limit,
                violation_magnitude=magnitude,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"INFEASIBLE: Observed {obs_value:.6g} {constraint.unit} violates limit {limit:.6g} "
                    f"{constraint.unit} by {magnitude:.6g} {constraint.unit} (tolerance {tol:.6g} {constraint.unit})."
                ),
            )

    elif op == ConstraintOperator.GEQ:
        limit = float(constraint.limit_value)  # type: ignore[arg-type]
        threshold = limit - tol
        if obs_value >= threshold:
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.FEASIBLE,
                observed_value=obs_value,
                limit_value=limit,
                violation_magnitude=0.0,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"FEASIBLE: Observed {obs_value:.6g} {constraint.unit} >= limit {limit:.6g} "
                    f"{constraint.unit} (tolerance {tol:.6g} {constraint.unit})."
                ),
            )
        else:
            magnitude = limit - obs_value
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.INFEASIBLE,
                observed_value=obs_value,
                limit_value=limit,
                violation_magnitude=magnitude,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"INFEASIBLE: Observed {obs_value:.6g} {constraint.unit} violates lower limit {limit:.6g} "
                    f"{constraint.unit} by {magnitude:.6g} {constraint.unit} (tolerance {tol:.6g} {constraint.unit})."
                ),
            )

    elif op == ConstraintOperator.EQ:
        limit = float(constraint.limit_value)  # type: ignore[arg-type]
        diff = abs(obs_value - limit)
        if diff <= tol:
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.FEASIBLE,
                observed_value=obs_value,
                limit_value=limit,
                violation_magnitude=0.0,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"FEASIBLE: Observed {obs_value:.6g} {constraint.unit} == target {limit:.6g} "
                    f"{constraint.unit} within tolerance {tol:.6g} {constraint.unit} (diff {diff:.6g})."
                ),
            )
        else:
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.INFEASIBLE,
                observed_value=obs_value,
                limit_value=limit,
                violation_magnitude=diff,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"INFEASIBLE: Observed {obs_value:.6g} {constraint.unit} differs from target {limit:.6g} "
                    f"{constraint.unit} by {diff:.6g} {constraint.unit} exceeding tolerance {tol:.6g} {constraint.unit}."
                ),
            )

    elif op == ConstraintOperator.IN_RANGE:
        bounds = constraint.limit_value
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            raise ValueError(f"IN_RANGE operator requires 2 bounds, got {bounds}")
        lower, upper = float(bounds[0]), float(bounds[1])

        if (lower - tol) <= obs_value <= (upper + tol):
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.FEASIBLE,
                observed_value=obs_value,
                limit_value=(lower, upper),
                violation_magnitude=0.0,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"FEASIBLE: Observed {obs_value:.6g} {constraint.unit} is within closed interval "
                    f"[{lower:.6g}, {upper:.6g}] {constraint.unit} (tolerance {tol:.6g} {constraint.unit})."
                ),
            )
        elif obs_value < (lower - tol):
            magnitude = lower - obs_value
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.INFEASIBLE,
                observed_value=obs_value,
                limit_value=(lower, upper),
                violation_magnitude=magnitude,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"INFEASIBLE: Observed {obs_value:.6g} {constraint.unit} falls below lower bound "
                    f"{lower:.6g} {constraint.unit} by {magnitude:.6g} {constraint.unit}."
                ),
            )
        else:
            magnitude = obs_value - upper
            return ConstraintEvaluation(
                constraint_id=constraint.constraint_id,
                target_element=constraint.target_variable,
                status=FeasibilityStatus.INFEASIBLE,
                observed_value=obs_value,
                limit_value=(lower, upper),
                violation_magnitude=magnitude,
                unit=constraint.unit,
                evidence_refs=evidence_refs,
                explanation=(
                    f"INFEASIBLE: Observed {obs_value:.6g} {constraint.unit} exceeds upper bound "
                    f"{upper:.6g} {constraint.unit} by {magnitude:.6g} {constraint.unit}."
                ),
            )

    else:
        raise ValueError(f"Unsupported constraint operator: {op}")


def evaluate_hard_constraints(
    constraints: Sequence[HardConstraint],
    variables: Mapping[str, DecisionVariable | float],
    evidence_chain: Mapping[str, EvidenceReference] | Sequence[EvidenceReference] | None = None,
    *,
    max_freshness_seconds: float = 120.0,
    require_evidence: bool = False,
) -> HardConstraintSummary:
    """
    Deterministically evaluate a sequence of hard constraints against provided state variables and evidence.

    Invariants:
    - Pure function: order-preserving, deterministic, zero wall-clock lookup.
    - Aggregation rule:
        * Any INFEASIBLE -> overall status is INFEASIBLE.
        * Else if any UNKNOWN -> overall status is UNKNOWN (Fail-Closed).
        * Only if all are FEASIBLE -> overall status is FEASIBLE.
    """
    evaluations: list[ConstraintEvaluation] = []
    violations: list[ConstraintEvaluation] = []
    unknown_count = 0

    # Build evidence map if sequence was provided
    evidence_map: dict[str, EvidenceReference] = {}
    if evidence_chain is not None:
        if isinstance(evidence_chain, Mapping):
            evidence_map = dict(evidence_chain)
        else:
            for ev in evidence_chain:
                # Key by source_id as primary identifier
                evidence_map[ev.source_id] = ev

    for constraint in constraints:
        var = variables.get(constraint.target_variable)
        # Look up evidence by target_variable or constraint_id
        ev = evidence_map.get(constraint.target_variable) or evidence_map.get(constraint.constraint_id)

        eval_result = evaluate_hard_constraint(
            constraint=constraint,
            variable=var,
            evidence=ev,
            max_freshness_seconds=max_freshness_seconds,
            require_evidence=require_evidence,
        )
        evaluations.append(eval_result)

        if eval_result.status == FeasibilityStatus.INFEASIBLE:
            violations.append(eval_result)
        elif eval_result.status == FeasibilityStatus.UNKNOWN:
            unknown_count += 1

    violations_count = len(violations)
    if violations_count > 0:
        overall_status = FeasibilityStatus.INFEASIBLE
    elif unknown_count > 0:
        overall_status = FeasibilityStatus.UNKNOWN
    else:
        overall_status = FeasibilityStatus.FEASIBLE

    return HardConstraintSummary(
        total_evaluated=len(constraints),
        violations_count=violations_count,
        unknown_count=unknown_count,
        overall_status=overall_status,
        violations=violations,
        evaluations=evaluations,
    )
