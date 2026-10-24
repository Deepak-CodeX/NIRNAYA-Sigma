"""
Canonical decision artifact assembly.

Builds fully validated, schema-compliant StrategyComparison and DecisionRecord payloads
conforming to Phase 0 contracts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence
import uuid

from nirnaya.domain.enums import (
    AuthorizationState,
    OperationalDispatchStatus,
    SignatureAlgorithm,
)
from nirnaya.domain.models import (
    AuditTrail,
    CandidateStrategy,
    DecisionRecord,
    DualControlSignatures,
    EvidenceExplanation,
    HumanReviewLog,
    ParetoComparisonResult,
    StrategyComparison,
    TradeoffMatrixEntry,
    validate_uuid_string,
)
from nirnaya.records.governance import (
    is_high_impact_decision,
    validate_dual_control_signatures,
)
from nirnaya.records.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    compute_record_hash,
)


def get_current_iso_timestamp() -> str:
    """Generate canonical ISO 8601 UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def assemble_strategy_comparison(
    problem_id: str,
    pareto_result: ParetoComparisonResult,
    baseline_scenario_id: str,
    deltas_by_strategy: dict[str, dict[str, float]],
    regret_by_strategy: dict[str, float],
    primary_recommendation_id: str,
    justification_summary: str,
    tradeoff_narrative: str,
    robustness_by_strategy: dict[str, float] | None = None,
    key_risks: list[str] | None = None,
    comparison_id: str | None = None,
    schema_version: str = "v1.0.0",
    generated_at: str | None = None,
) -> StrategyComparison:
    """
    Assemble a canonical StrategyComparison domain model.

    Fail-Closed Rules:
    ------------------
    - primary_recommendation_id must be in pareto_frontier_scenario_ids. Recommending dominated,
      infeasible, or quarantined strategies is strictly forbidden.
    - All IDs must be valid UUID strings.
    """
    comp_id = validate_uuid_string(comparison_id or str(uuid.uuid4()), "comparison_id")
    prob_id = validate_uuid_string(problem_id, "problem_id")
    base_id = validate_uuid_string(baseline_scenario_id, "baseline_scenario_id")
    rec_id = validate_uuid_string(primary_recommendation_id, "primary_recommendation_id")

    pareto_ids = [validate_uuid_string(s.strategy_id, "pareto_strategy_id") for s in pareto_result.pareto_frontier]
    dominated_ids = [validate_uuid_string(s.strategy_id, "dominated_strategy_id") for s in pareto_result.dominated_strategies]
    infeasible_ids = [validate_uuid_string(s.strategy_id, "infeasible_strategy_id") for s in pareto_result.infeasible_strategies]
    unknown_ids = [validate_uuid_string(s.strategy_id, "unknown_strategy_id") for s in pareto_result.unknown_strategies]

    if rec_id not in pareto_ids:
        raise ValueError(
            f"Primary recommendation strategy '{rec_id}' must reside in the verified Pareto frontier. "
            f"Available non-dominated candidate IDs: {pareto_ids}"
        )

    robustness_map = robustness_by_strategy or {}

    # Build tradeoff matrix across all evaluated feasible candidates
    tradeoff_matrix: list[TradeoffMatrixEntry] = []
    all_evaluated = list(pareto_result.pareto_frontier) + list(pareto_result.dominated_strategies)

    for strat in all_evaluated:
        s_id = strat.strategy_id
        tradeoff_matrix.append(
            TradeoffMatrixEntry(
                scenario_id=s_id,
                strategy_name=strat.strategy_name,
                objective_values=strat.objectives,
                delta_vs_baseline=deltas_by_strategy.get(s_id, {}),
                max_regret=regret_by_strategy.get(s_id, 0.0),
                robustness_score=robustness_map.get(s_id),
            )
        )

    explanation = EvidenceExplanation(
        primary_recommendation_scenario_id=rec_id,
        justification_summary=justification_summary.strip(),
        tradeoff_narrative=tradeoff_narrative.strip(),
        key_risks=key_risks or [],
    )

    timestamp = generated_at or get_current_iso_timestamp()

    return StrategyComparison(
        comparison_id=comp_id,
        problem_id=prob_id,
        schema_version=schema_version,
        generated_at=timestamp,
        baseline_scenario_id=base_id,
        pareto_frontier_scenario_ids=pareto_ids,
        dominated_scenario_ids=dominated_ids,
        infeasible_scenario_ids=infeasible_ids,
        unknown_scenario_ids=unknown_ids,
        tradeoff_matrix=tradeoff_matrix,
        evidence_explanation=explanation,
    )


def assemble_decision_record(
    problem_id: str,
    comparison: StrategyComparison,
    selected_scenario_id: str,
    authorization_state: AuthorizationState,
    human_review_log: HumanReviewLog,
    dual_control_signatures: DualControlSignatures,
    strategy_candidate: CandidateStrategy | None = None,
    previous_record_hash: str = GENESIS_PREVIOUS_HASH,
    signature_algorithm: SignatureAlgorithm = SignatureAlgorithm.ECDSA_P256_SHA256,
    operational_dispatch_status: OperationalDispatchStatus = OperationalDispatchStatus.NOT_DISPATCHED,
    record_id: str | None = None,
    schema_version: str = "v1.0.0",
    created_at: str | None = None,
) -> DecisionRecord:
    """
    Assemble a canonical DecisionRecord with cryptographic hash chaining and Four-Eyes governance.

    Fail-Closed Rules:
    ------------------
    - selected_scenario_id cannot be INFEASIBLE or UNKNOWN.
    - If strategy_candidate is provided, executes full Separation of Duties (SoD) validation.
    - Computes immutable SHA-256 digest over the canonical decision tuple.
    """
    rec_uuid = validate_uuid_string(record_id or str(uuid.uuid4()), "record_id")
    prob_uuid = validate_uuid_string(problem_id, "problem_id")
    comp_uuid = validate_uuid_string(comparison.comparison_id, "comparison_id")
    sel_uuid = validate_uuid_string(selected_scenario_id, "selected_scenario_id")

    if sel_uuid in comparison.infeasible_scenario_ids:
        raise ValueError(
            f"Safety policy violation: Selected strategy '{sel_uuid}' is INFEASIBLE. "
            "Cannot authorize a strategy with confirmed physical constraint violations."
        )

    if sel_uuid in comparison.unknown_scenario_ids:
        raise ValueError(
            f"Fail-closed policy violation: Selected strategy '{sel_uuid}' is in UNKNOWN state. "
            "Quarantined strategies cannot be authorized."
        )

    # Validate governance and Four-Eyes signatures
    if strategy_candidate is not None:
        validate_dual_control_signatures(
            strategy=strategy_candidate,
            review_log=human_review_log,
            dual_control=dual_control_signatures,
        )

    timestamp = created_at or get_current_iso_timestamp()

    # Compute immutable SHA-256 record hash
    rec_hash = compute_record_hash(
        record_id=rec_uuid,
        problem_id=prob_uuid,
        comparison_id=comp_uuid,
        selected_scenario_id=sel_uuid,
        previous_record_hash=previous_record_hash,
        schema_version=schema_version,
        operator_id=human_review_log.operator_id,
        primary_signer_id=dual_control_signatures.primary_sign_off.user_id,
    )

    audit_trail = AuditTrail(
        record_hash=rec_hash,
        previous_record_hash=previous_record_hash,
        signature_algorithm=signature_algorithm,
    )

    return DecisionRecord(
        record_id=rec_uuid,
        problem_id=prob_uuid,
        comparison_id=comp_uuid,
        schema_version=schema_version,
        created_at=timestamp,
        selected_scenario_id=sel_uuid,
        authorization_state=authorization_state,
        human_review_log=human_review_log,
        dual_control_signatures=dual_control_signatures,
        operational_dispatch_status=operational_dispatch_status,
        audit_trail=audit_trail,
    )
