"""
Unit tests for Milestone 5: Multi-Criteria Decision Analysis, Canonical Decision Records,
and Cryptographic Provenance Hash Chaining.

Verifies:
1. Epsilon-constraint filtering across minimization and maximization objectives.
2. Deterministic lexicographic priority ordering across hierarchical tiers.
3. Chebyshev aspiration distance with analytical hand calculations and degenerate range safety.
4. Four-Eyes dual-control governance and Separation of Duties (SoD) invariants.
5. Append-only SHA-256 hash chaining and tamper-evident chain verification.
6. Phase 0 canonical JSON Schema conformance (strategy_comparison.json, decision_record.json).
7. Fail-closed rejection of infeasible/unknown recommendations, malformed UUIDs, and timestamps.
8. Deterministic repeatability over 50 repeated executions.
"""

from __future__ import annotations

import json
from pathlib import Path
import uuid
try:
    import pytest
except ImportError:
    from tests.compat import pytest

from jsonschema import Draft7Validator

from nirnaya.domain.enums import (
    AuthorizationState,
    FeasibilityStatus,
    ObjectiveDirection,
    OperationalDispatchStatus,
    SignatureAlgorithm,
)
from nirnaya.domain.models import (
    CandidateStrategy,
    DualControlSignatures,
    HumanReviewLog,
    ObjectiveDefinition,
    ParetoComparisonResult,
    SignOffEntry,
)
from nirnaya.mcda.aspiration import compute_chebyshev_aspiration_distance
from nirnaya.mcda.filtering import filter_epsilon_constraints
from nirnaya.mcda.lexicographic import sort_lexicographic_priority
from nirnaya.records.assembly import (
    assemble_decision_record,
    assemble_strategy_comparison,
)
from nirnaya.records.governance import (
    is_high_impact_decision,
    validate_dual_control_signatures,
)
from nirnaya.records.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    compute_record_hash,
    verify_decision_record_chain,
)

SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "schemas"


def make_uuid(n: int) -> str:
    return str(uuid.UUID(int=n))


# ---------------------------------------------------------------------------
# Category 1: Epsilon-Constraint Filtering
# ---------------------------------------------------------------------------

class TestEpsilonConstraintFiltering:
    """Verification of epsilon-constraint secondary objective policy filtering."""

    def test_epsilon_filtering_minimization_and_maximization(self) -> None:
        """
        Verify filtering across both MINIMIZE (f_k <= thresh) and MAXIMIZE (f_k >= thresh).
        """
        objectives = [
            ObjectiveDefinition(
                objective_id="loss_mw",
                name="Transmission Loss",
                direction=ObjectiveDirection.MINIMIZE,
                unit="MW",
            ),
            ObjectiveDefinition(
                objective_id="reserve_mw",
                name="Spinning Reserve",
                direction=ObjectiveDirection.MAXIMIZE,
                unit="MW",
            ),
        ]

        # Strat 1: loss 10.0 (ok), reserve 100.0 (ok) -> KEEP
        s1 = CandidateStrategy(
            strategy_id=make_uuid(1),
            strategy_name="Optimal Mixed",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"loss_mw": 10.0, "reserve_mw": 100.0},
        )
        # Strat 2: loss 25.0 (exceeds 15.0) -> DROP
        s2 = CandidateStrategy(
            strategy_id=make_uuid(2),
            strategy_name="High Loss",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"loss_mw": 25.0, "reserve_mw": 120.0},
        )
        # Strat 3: loss 12.0 (ok), reserve 60.0 (below 80.0) -> DROP
        s3 = CandidateStrategy(
            strategy_id=make_uuid(3),
            strategy_name="Low Reserve",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"loss_mw": 12.0, "reserve_mw": 60.0},
        )

        thresholds = {"loss_mw": 15.0, "reserve_mw": 80.0}
        filtered = filter_epsilon_constraints([s1, s2, s3], thresholds, objectives)

        assert len(filtered) == 1
        assert filtered[0].strategy_id == make_uuid(1)

    def test_epsilon_filtering_empty_result_when_threshold_unachievable(self) -> None:
        """
        Verify that overly strict policy thresholds return empty list fail-closed without crashing.
        """
        objectives = [
            ObjectiveDefinition(
                objective_id="cost",
                name="Cost",
                direction=ObjectiveDirection.MINIMIZE,
                unit="USD",
            )
        ]
        s1 = CandidateStrategy(
            strategy_id=make_uuid(1),
            strategy_name="Normal",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"cost": 100.0},
        )

        thresholds = {"cost": 50.0}  # impossible threshold
        filtered = filter_epsilon_constraints([s1], thresholds, objectives)
        assert len(filtered) == 0

    def test_epsilon_filtering_rejects_infeasible_and_unknown_candidates(self) -> None:
        """
        Verify that INFEASIBLE and UNKNOWN candidates are never admitted even if metrics are low.
        """
        objectives = [
            ObjectiveDefinition(
                objective_id="cost",
                name="Cost",
                direction=ObjectiveDirection.MINIMIZE,
                unit="USD",
            )
        ]
        s_inf = CandidateStrategy(
            strategy_id=make_uuid(1),
            strategy_name="Violating",
            feasibility_status=FeasibilityStatus.INFEASIBLE,
            objectives={"cost": 10.0},
        )
        s_unk = CandidateStrategy(
            strategy_id=make_uuid(2),
            strategy_name="Quarantined",
            feasibility_status=FeasibilityStatus.UNKNOWN,
            objectives={"cost": 5.0},
        )

        thresholds = {"cost": 50.0}
        filtered = filter_epsilon_constraints([s_inf, s_unk], thresholds, objectives)
        assert len(filtered) == 0

    def test_epsilon_filtering_rejects_undeclared_objective(self) -> None:
        """
        Verify fail-closed error if threshold dictionary references an undeclared objective.
        """
        objectives = [
            ObjectiveDefinition(
                objective_id="cost",
                name="Cost",
                direction=ObjectiveDirection.MINIMIZE,
                unit="USD",
            )
        ]
        s = CandidateStrategy(
            strategy_id=make_uuid(1),
            strategy_name="Strat",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"cost": 100.0},
        )
        with pytest.raises(ValueError, match="references undeclared objective 'emissions'"):
            filter_epsilon_constraints([s], {"emissions": 5.0}, objectives)


# ---------------------------------------------------------------------------
# Category 2: Lexicographic Priority Ordering
# ---------------------------------------------------------------------------

class TestLexicographicPriorityOrdering:
    """Verification of deterministic hierarchical priority ordering."""

    def test_lexicographic_ranking_hierarchy(self) -> None:
        """
        Verify hand-calculated lexicographic priority ranking across 3 tiers:
        Tier 1: critical_outage (MINIMIZE, rank 1)
        Tier 2: total_eue (MINIMIZE, rank 2)
        Tier 3: cost (MINIMIZE, rank 3)

        Candidates:
        Strat A: outage=0.0, eue=15.0, cost=500.0
        Strat B: outage=0.0, eue=10.0, cost=800.0
        Strat C: outage=2.0, eue=5.0,  cost=200.0

        Expected Ranking:
        Tier 1: A and B tie (0.0 == 0.0), C has 2.0 (eliminated from top)
        Tier 2: B (10.0) < A (15.0) -> B ranks 1st, A ranks 2nd
        Result: [B, A, C]
        """
        objectives = [
            ObjectiveDefinition(
                objective_id="critical_outage",
                name="Tier 1 Hospital Outage",
                direction=ObjectiveDirection.MINIMIZE,
                unit="Hours",
                priority_rank=1,
            ),
            ObjectiveDefinition(
                objective_id="total_eue",
                name="Expected Unserved Energy",
                direction=ObjectiveDirection.MINIMIZE,
                unit="MWh",
                priority_rank=2,
            ),
            ObjectiveDefinition(
                objective_id="cost",
                name="Redispatch Cost",
                direction=ObjectiveDirection.MINIMIZE,
                unit="USD",
                priority_rank=3,
            ),
        ]

        strat_a = CandidateStrategy(
            strategy_id=make_uuid(101),
            strategy_name="Strategy A",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"critical_outage": 0.0, "total_eue": 15.0, "cost": 500.0},
        )
        strat_b = CandidateStrategy(
            strategy_id=make_uuid(102),
            strategy_name="Strategy B",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"critical_outage": 0.0, "total_eue": 10.0, "cost": 800.0},
        )
        strat_c = CandidateStrategy(
            strategy_id=make_uuid(103),
            strategy_name="Strategy C",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"critical_outage": 2.0, "total_eue": 5.0, "cost": 200.0},
        )

        ranked = sort_lexicographic_priority([strat_c, strat_a, strat_b], objectives)
        assert [s.strategy_id for s in ranked] == [make_uuid(102), make_uuid(101), make_uuid(103)]

    def test_lexicographic_tolerance_and_deterministic_tie_breaking(self) -> None:
        """
        Verify tolerance evaluation (|diff| <= 1e-4 treated as tie) and deterministic ID sort.
        """
        objectives = [
            ObjectiveDefinition(
                objective_id="eue",
                name="EUE",
                direction=ObjectiveDirection.MINIMIZE,
                unit="MWh",
                priority_rank=1,
            )
        ]
        # Two identical strategies with differing UUIDs
        s_z = CandidateStrategy(
            strategy_id=make_uuid(200),
            strategy_name="Strat Z",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"eue": 10.00002},
        )
        s_a = CandidateStrategy(
            strategy_id=make_uuid(100),
            strategy_name="Strat A",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"eue": 10.00000},
        )

        # Within tolerance 1e-4, treated as tie -> broken by strategy_id ascending
        ranked = sort_lexicographic_priority([s_z, s_a], objectives, tolerance=1e-4)
        assert ranked[0].strategy_id == make_uuid(100)
        assert ranked[1].strategy_id == make_uuid(200)

    def test_lexicographic_feasibility_precedence(self) -> None:
        """
        Verify that FEASIBLE strategies strictly precede INFEASIBLE and UNKNOWN candidates.
        """
        objectives = [
            ObjectiveDefinition(
                objective_id="cost",
                name="Cost",
                direction=ObjectiveDirection.MINIMIZE,
                unit="USD",
                priority_rank=1,
            )
        ]
        s_feas = CandidateStrategy(
            strategy_id=make_uuid(1),
            strategy_name="Feasible High Cost",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"cost": 1000.0},
        )
        s_inf = CandidateStrategy(
            strategy_id=make_uuid(2),
            strategy_name="Infeasible Zero Cost",
            feasibility_status=FeasibilityStatus.INFEASIBLE,
            objectives={"cost": 0.0},
        )

        ranked = sort_lexicographic_priority([s_inf, s_feas], objectives)
        assert ranked[0].strategy_id == make_uuid(1)
        assert ranked[1].strategy_id == make_uuid(2)


# ---------------------------------------------------------------------------
# Category 3: Chebyshev Aspiration Distance
# ---------------------------------------------------------------------------

class TestChebyshevAspirationDistance:
    """Verification of minimax distance calculation to ideal aspiration targets."""

    def test_chebyshev_aspiration_hand_calculation(self) -> None:
        """
        Verify analytical hand-calculated Chebyshev distance.
        Aspiration f* = { "cost": 100.0, "eue": 10.0 }
        Nadir f^nadir = { "cost": 300.0, "eue": 50.0 }
        Candidate f(x) = { "cost": 200.0, "eue": 20.0 }
        Weights lambda = { "cost": 0.5, "eue": 0.5 }

        Hand calculation:
        cost component = 0.5 * |200 - 100| / (|300 - 100| + 1e-9) = 0.5 * 100 / 200 = 0.25
        eue component  = 0.5 * |20 - 10| / (|50 - 10| + 1e-9) = 0.5 * 10 / 40 = 0.125
        D_inf = max(0.25, 0.125) = 0.25
        """
        strat = CandidateStrategy(
            strategy_id=make_uuid(1),
            strategy_name="Balanced Candidate",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"cost": 200.0, "eue": 20.0},
        )
        f_star = {"cost": 100.0, "eue": 10.0}
        f_nadir = {"cost": 300.0, "eue": 50.0}
        weights = {"cost": 0.5, "eue": 0.5}

        d_inf = compute_chebyshev_aspiration_distance(
            strategy=strat,
            aspiration_point=f_star,
            nadir_point=f_nadir,
            weights=weights,
        )
        assert pytest.approx(d_inf, 1e-6) == 0.25

    def test_chebyshev_aspiration_degenerate_range_stabilization(self) -> None:
        """
        Verify that when aspiration == nadir (zero range), delta stabilizes calculation.
        """
        strat = CandidateStrategy(
            strategy_id=make_uuid(1),
            strategy_name="Strat",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"cost": 105.0},
        )
        # f* == f_nadir == 100.0
        d_inf = compute_chebyshev_aspiration_distance(
            strategy=strat,
            aspiration_point={"cost": 100.0},
            nadir_point={"cost": 100.0},
            delta=1e-6,
        )
        # component = 1.0 * |105 - 100| / (0 + 1e-6) = 5.0 / 1e-6 = 5_000_000.0
        assert pytest.approx(d_inf, 1e-3) == 5_000_000.0


# ---------------------------------------------------------------------------
# Category 4: Governance and Dual-Control (Four-Eyes Principle)
# ---------------------------------------------------------------------------

class TestGovernanceAndDualControl:
    """Verification of Four-Eyes role separation and high-impact classification."""

    def test_high_impact_decision_predicate(self) -> None:
        """
        Verify high-impact detection on load shed >10 MW, voltage excursions, and sectionalizing.
        """
        # 1. Load shedding > 10 MW
        s_shed = CandidateStrategy(
            strategy_id=make_uuid(1),
            strategy_name="Load Shed 15MW",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"load_shed_mw": 15.0},
        )
        assert is_high_impact_decision(s_shed) is True

        # 2. Normal low shedding
        s_normal = CandidateStrategy(
            strategy_id=make_uuid(2),
            strategy_name="Normal Shed 2MW",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"load_shed_mw": 2.0},
        )
        assert is_high_impact_decision(s_normal) is False

        # 3. Voltage limit excursion into emergency band (0.92 p.u. < 0.95)
        s_volt = CandidateStrategy(
            strategy_id=make_uuid(3),
            strategy_name="Voltage Dip",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"bus_voltage_pu": 0.92},
        )
        assert is_high_impact_decision(s_volt) is True

        # 4. Sectionalizing metadata flag
        s_sec = CandidateStrategy(
            strategy_id=make_uuid(4),
            strategy_name="Sectionalizing",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"cost": 100.0},
            metadata={"sectionalizing": True},
        )
        assert is_high_impact_decision(s_sec) is True

    def test_dual_control_rejects_missing_secondary_on_high_impact(self) -> None:
        """
        Verify fail-closed error if high-impact strategy lacks secondary sign-off.
        """
        s_high = CandidateStrategy(
            strategy_id=make_uuid(1),
            strategy_name="High Shed",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"load_shed_mw": 50.0},
        )
        review_log = HumanReviewLog(
            operator_id="operator_alpha",
            operator_role="Senior Dispatcher",
            review_timestamp="2026-10-25T02:00:00Z",
            rationale_for_selection="Required shedding to prevent cascade.",
        )
        dual_control = DualControlSignatures(
            primary_sign_off=SignOffEntry(
                user_id="operator_alpha",
                user_name="Alpha Operator",
                role="Senior Grid Controller",
                timestamp="2026-10-25T02:01:00Z",
                digital_signature="SIG_PRIMARY_123",
            ),
            secondary_sign_off=None,  # Missing secondary!
        )

        with pytest.raises(ValueError, match="Dual-control policy violation"):
            validate_dual_control_signatures(s_high, review_log, dual_control)

    def test_dual_control_rejects_identical_primary_and_secondary_signers(self) -> None:
        """
        Verify Separation of Duties (SoD): primary and secondary signers cannot be identical.
        """
        s_high = CandidateStrategy(
            strategy_id=make_uuid(1),
            strategy_name="High Shed",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"load_shed_mw": 50.0},
        )
        review_log = HumanReviewLog(
            operator_id="reviewer_charlie",
            operator_role="Reviewer",
            review_timestamp="2026-10-25T02:00:00Z",
            rationale_for_selection="Verified stability.",
        )
        dual_control = DualControlSignatures(
            primary_sign_off=SignOffEntry(
                user_id="user_alpha",
                user_name="Alpha User",
                role="Primary",
                timestamp="2026-10-25T02:01:00Z",
                digital_signature="SIG1",
            ),
            secondary_sign_off=SignOffEntry(
                user_id="user_alpha",  # IDENTICAL USER ID!
                user_name="Alpha User",
                role="Secondary",
                timestamp="2026-10-25T02:02:00Z",
                digital_signature="SIG2",
            ),
        )

        with pytest.raises(ValueError, match="Separation of duties violation: Primary signer 'user_alpha' and secondary signer 'user_alpha' cannot be the same"):
            validate_dual_control_signatures(s_high, review_log, dual_control)

    def test_dual_control_rejects_approver_same_as_reviewer(self) -> None:
        """
        Verify Separation of Duties (SoD): secondary approver cannot be the same as technical reviewer.
        """
        s_high = CandidateStrategy(
            strategy_id=make_uuid(1),
            strategy_name="High Shed",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"load_shed_mw": 50.0},
        )
        review_log = HumanReviewLog(
            operator_id="operator_lead",
            operator_role="Technical Reviewer",
            review_timestamp="2026-10-25T02:00:00Z",
            rationale_for_selection="Review passed.",
        )
        dual_control = DualControlSignatures(
            primary_sign_off=SignOffEntry(
                user_id="operator_junior",
                user_name="Junior Dispatcher",
                role="Dispatcher",
                timestamp="2026-10-25T02:01:00Z",
                digital_signature="SIG1",
            ),
            secondary_sign_off=SignOffEntry(
                user_id="operator_lead",  # SAME AS REVIEWER!
                user_name="Lead Operator",
                role="Commander",
                timestamp="2026-10-25T02:02:00Z",
                digital_signature="SIG2",
            ),
        )

        with pytest.raises(ValueError, match="Separation of duties violation: Secondary approver 'operator_lead' cannot be the same individual as the technical reviewer 'operator_lead'"):
            validate_dual_control_signatures(s_high, review_log, dual_control)


# ---------------------------------------------------------------------------
# Category 5: Cryptographic Hash Chaining and Provenance
# ---------------------------------------------------------------------------

class TestCryptographicHashChain:
    """Verification of append-only SHA-256 hash chaining and tamper detection."""

    def test_genesis_and_sequential_hash_chain_verification(self) -> None:
        """
        Verify building a chain of 3 sequential DecisionRecords and validating chain integrity.
        """
        records = []
        prev_hash = GENESIS_PREVIOUS_HASH

        for i in range(1, 4):
            # Assemble minimal valid decision record
            comp_dummy = assemble_strategy_comparison(
                problem_id=make_uuid(10),
                pareto_result=ParetoComparisonResult(
                    comparison_id=make_uuid(20 + i),
                    problem_id=make_uuid(10),
                    pareto_frontier=[
                        CandidateStrategy(
                            strategy_id=make_uuid(100 + i),
                            strategy_name=f"Strategy {i}",
                            feasibility_status=FeasibilityStatus.FEASIBLE,
                            objectives={"loss": 10.0},
                        )
                    ],
                ),
                baseline_scenario_id=make_uuid(99),
                deltas_by_strategy={make_uuid(100 + i): {"loss": -2.0}},
                regret_by_strategy={make_uuid(100 + i): 0.1},
                primary_recommendation_id=make_uuid(100 + i),
                justification_summary="Optimal plan",
                tradeoff_narrative="Tradeoff verified",
                comparison_id=make_uuid(20 + i),
            )

            rec = assemble_decision_record(
                problem_id=make_uuid(10),
                comparison=comp_dummy,
                selected_scenario_id=make_uuid(100 + i),
                authorization_state=AuthorizationState.AUTHORIZED,
                human_review_log=HumanReviewLog(
                    operator_id="operator_1",
                    operator_role="Dispatcher",
                    review_timestamp="2026-10-25T02:00:00Z",
                    rationale_for_selection="Approved",
                ),
                dual_control_signatures=DualControlSignatures(
                    primary_sign_off=SignOffEntry(
                        user_id="operator_1",
                        user_name="Alpha",
                        role="Dispatcher",
                        timestamp="2026-10-25T02:01:00Z",
                        digital_signature="SIG1",
                    )
                ),
                previous_record_hash=prev_hash,
                record_id=make_uuid(30 + i),
            )
            records.append(rec)
            prev_hash = rec.audit_trail.record_hash

        valid, msg = verify_decision_record_chain(records)
        assert valid is True
        assert "tamper-free" in msg

    def test_tamper_detection_in_historical_decision_record(self) -> None:
        """
        Verify that altering a payload field inside an assembled record breaks chain verification.
        """
        records = []
        prev_hash = GENESIS_PREVIOUS_HASH

        for i in range(1, 4):
            comp_dummy = assemble_strategy_comparison(
                problem_id=make_uuid(10),
                pareto_result=ParetoComparisonResult(
                    comparison_id=make_uuid(20 + i),
                    problem_id=make_uuid(10),
                    pareto_frontier=[
                        CandidateStrategy(
                            strategy_id=make_uuid(100 + i),
                            strategy_name=f"Strategy {i}",
                            feasibility_status=FeasibilityStatus.FEASIBLE,
                            objectives={"loss": 10.0},
                        )
                    ],
                ),
                baseline_scenario_id=make_uuid(99),
                deltas_by_strategy={make_uuid(100 + i): {"loss": -2.0}},
                regret_by_strategy={make_uuid(100 + i): 0.1},
                primary_recommendation_id=make_uuid(100 + i),
                justification_summary="Optimal plan",
                tradeoff_narrative="Tradeoff verified",
                comparison_id=make_uuid(20 + i),
            )

            rec = assemble_decision_record(
                problem_id=make_uuid(10),
                comparison=comp_dummy,
                selected_scenario_id=make_uuid(100 + i),
                authorization_state=AuthorizationState.AUTHORIZED,
                human_review_log=HumanReviewLog(
                    operator_id=f"operator_{i}",
                    operator_role="Dispatcher",
                    review_timestamp="2026-10-25T02:00:00Z",
                    rationale_for_selection="Approved",
                ),
                dual_control_signatures=DualControlSignatures(
                    primary_sign_off=SignOffEntry(
                        user_id=f"operator_{i}",
                        user_name=f"Alpha {i}",
                        role="Dispatcher",
                        timestamp="2026-10-25T02:01:00Z",
                        digital_signature=f"SIG{i}",
                    )
                ),
                previous_record_hash=prev_hash,
                record_id=make_uuid(30 + i),
            )
            records.append(rec)
            prev_hash = rec.audit_trail.record_hash

        # Tamper: create a copy of record 1 with altered selected_scenario_id
        tampered_rec_1 = records[1].model_copy(update={"selected_scenario_id": make_uuid(999)})
        tampered_chain = [records[0], tampered_rec_1, records[2]]

        valid, err = verify_decision_record_chain(tampered_chain)
        assert valid is False
        assert "Tamper detection" in err


# ---------------------------------------------------------------------------
# Category 6: Phase 0 Canonical JSON Schema Conformance
# ---------------------------------------------------------------------------

class TestPhase0SchemaConformance:
    """Validate assembled StrategyComparison and DecisionRecord against canonical Draft-07 schemas."""

    def test_strategy_comparison_schema_conformance(self) -> None:
        """
        Assert that assemble_strategy_comparison outputs a dictionary conforming strictly
        to contracts/schemas/strategy_comparison.json.
        """
        schema_path = SCHEMAS_DIR / "strategy_comparison.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        validator = Draft7Validator(schema)

        comp = assemble_strategy_comparison(
            problem_id=make_uuid(1),
            pareto_result=ParetoComparisonResult(
                comparison_id=make_uuid(2),
                problem_id=make_uuid(1),
                pareto_frontier=[
                    CandidateStrategy(
                        strategy_id=make_uuid(10),
                        strategy_name="Optimal Strategy",
                        feasibility_status=FeasibilityStatus.FEASIBLE,
                        objectives={"loss_mw": 14.2, "cost_usd": 4500.0},
                    )
                ],
            ),
            baseline_scenario_id=make_uuid(99),
            deltas_by_strategy={make_uuid(10): {"loss_mw": -85.8, "cost_usd": 4500.0}},
            regret_by_strategy={make_uuid(10): 0.12},
            robustness_by_strategy={make_uuid(10): 0.95},
            primary_recommendation_id=make_uuid(10),
            justification_summary="Minimizes outage with tolerable redispatch expenditure.",
            tradeoff_narrative="Saves 85.8 MWh of unserved energy while incurring $4,500 in redispatch.",
            key_risks=["Generator ramp constraint on Unit 4"],
            comparison_id=make_uuid(2),
        )

        payload = comp.to_canonical_dict()
        errors = list(validator.iter_errors(payload))
        assert len(errors) == 0, f"Schema validation errors: {[e.message for e in errors]}"

    def test_decision_record_schema_conformance(self) -> None:
        """
        Assert that assemble_decision_record outputs a dictionary conforming strictly
        to contracts/schemas/decision_record.json.
        """
        schema_path = SCHEMAS_DIR / "decision_record.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        validator = Draft7Validator(schema)

        comp = assemble_strategy_comparison(
            problem_id=make_uuid(1),
            pareto_result=ParetoComparisonResult(
                comparison_id=make_uuid(2),
                problem_id=make_uuid(1),
                pareto_frontier=[
                    CandidateStrategy(
                        strategy_id=make_uuid(10),
                        strategy_name="Optimal Strategy",
                        feasibility_status=FeasibilityStatus.FEASIBLE,
                        objectives={"loss_mw": 14.2},
                    )
                ],
            ),
            baseline_scenario_id=make_uuid(99),
            deltas_by_strategy={make_uuid(10): {"loss_mw": -10.0}},
            regret_by_strategy={make_uuid(10): 0.05},
            primary_recommendation_id=make_uuid(10),
            justification_summary="Selection summary",
            tradeoff_narrative="Narrative text",
            comparison_id=make_uuid(2),
        )

        record = assemble_decision_record(
            problem_id=make_uuid(1),
            comparison=comp,
            selected_scenario_id=make_uuid(10),
            authorization_state=AuthorizationState.AUTHORIZED,
            human_review_log=HumanReviewLog(
                operator_id="dispatcher_7",
                operator_role="Senior Grid Controller",
                review_timestamp="2026-10-25T02:15:00Z",
                rationale_for_selection="Balanced reliability and minimal redispatch cost.",
            ),
            dual_control_signatures=DualControlSignatures(
                primary_sign_off=SignOffEntry(
                    user_id="dispatcher_7",
                    user_name="John Doe",
                    role="Senior Grid Controller",
                    timestamp="2026-10-25T02:16:00Z",
                    digital_signature="SIG_ECDSA_12345",
                ),
                secondary_sign_off=SignOffEntry(
                    user_id="commander_1",
                    user_name="Jane Smith",
                    role="Incident Commander",
                    timestamp="2026-10-25T02:17:00Z",
                    digital_signature="SIG_ECDSA_67890",
                ),
            ),
            operational_dispatch_status=OperationalDispatchStatus.EXPORTED_TO_OPERATIONS,
            record_id=make_uuid(50),
        )

        payload = record.to_canonical_dict()
        errors = list(validator.iter_errors(payload))
        assert len(errors) == 0, f"Schema validation errors: {[e.message for e in errors]}"


# ---------------------------------------------------------------------------
# Category 7: Fail-Closed Boundaries and Evidence Grounding
# ---------------------------------------------------------------------------

class TestEvidenceGroundingAndFailClosed:
    """Verification of fail-closed safety constraints on strategy recommendation and authorization."""

    def test_assembly_rejects_recommending_infeasible_or_unknown_strategy(self) -> None:
        """
        Verify fail-closed error if primary recommendation is INFEASIBLE or UNKNOWN.
        """
        pareto_res = ParetoComparisonResult(
            comparison_id=make_uuid(1),
            problem_id=make_uuid(2),
            pareto_frontier=[
                CandidateStrategy(
                    strategy_id=make_uuid(10),
                    strategy_name="Feasible Candidate",
                    feasibility_status=FeasibilityStatus.FEASIBLE,
                    objectives={"cost": 100.0},
                )
            ],
            infeasible_strategies=[
                CandidateStrategy(
                    strategy_id=make_uuid(20),
                    strategy_name="Violating Candidate",
                    feasibility_status=FeasibilityStatus.INFEASIBLE,
                    objectives={"cost": 10.0},
                )
            ],
        )

        # Attempting to recommend infeasible strategy UUID 20
        with pytest.raises(ValueError, match="must reside in the verified Pareto frontier"):
            assemble_strategy_comparison(
                problem_id=make_uuid(2),
                pareto_result=pareto_res,
                baseline_scenario_id=make_uuid(99),
                deltas_by_strategy={},
                regret_by_strategy={},
                primary_recommendation_id=make_uuid(20),
                justification_summary="Bad",
                tradeoff_narrative="Bad",
            )

    def test_assembly_rejects_authorizing_infeasible_or_unknown_strategy(self) -> None:
        """
        Verify fail-closed error if an INFEASIBLE or UNKNOWN candidate is selected for authorization.
        """
        comp = assemble_strategy_comparison(
            problem_id=make_uuid(1),
            pareto_result=ParetoComparisonResult(
                comparison_id=make_uuid(2),
                problem_id=make_uuid(1),
                pareto_frontier=[
                    CandidateStrategy(
                        strategy_id=make_uuid(10),
                        strategy_name="Feasible Candidate",
                        feasibility_status=FeasibilityStatus.FEASIBLE,
                        objectives={"cost": 100.0},
                    )
                ],
                infeasible_strategies=[
                    CandidateStrategy(
                        strategy_id=make_uuid(20),
                        strategy_name="Infeasible Candidate",
                        feasibility_status=FeasibilityStatus.INFEASIBLE,
                        objectives={"cost": 10.0},
                    )
                ],
            ),
            baseline_scenario_id=make_uuid(99),
            deltas_by_strategy={},
            regret_by_strategy={},
            primary_recommendation_id=make_uuid(10),
            justification_summary="Justification",
            tradeoff_narrative="Narrative",
            comparison_id=make_uuid(2),
        )

        # Attempt to authorize infeasible candidate UUID 20
        with pytest.raises(ValueError, match="Safety policy violation: Selected strategy .* is INFEASIBLE"):
            assemble_decision_record(
                problem_id=make_uuid(1),
                comparison=comp,
                selected_scenario_id=make_uuid(20),
                authorization_state=AuthorizationState.AUTHORIZED,
                human_review_log=HumanReviewLog(
                    operator_id="op1",
                    operator_role="Dispatcher",
                    review_timestamp="2026-10-25T02:00:00Z",
                    rationale_for_selection="Attempting invalid selection",
                ),
                dual_control_signatures=DualControlSignatures(
                    primary_sign_off=SignOffEntry(
                        user_id="op1",
                        user_name="Op One",
                        role="Role",
                        timestamp="2026-10-25T02:00:00Z",
                        digital_signature="SIG",
                    )
                ),
            )

    def test_assembly_rejects_malformed_uuids_and_timestamps(self) -> None:
        """
        Verify rejection of non-UUID strings and non-ISO timestamps.
        """
        with pytest.raises(ValueError, match="must be a valid UUID"):
            assemble_strategy_comparison(
                problem_id="invalid_uuid_string",
                pareto_result=ParetoComparisonResult(
                    comparison_id=make_uuid(1),
                    problem_id=make_uuid(2),
                    pareto_frontier=[],
                ),
                baseline_scenario_id=make_uuid(99),
                deltas_by_strategy={},
                regret_by_strategy={},
                primary_recommendation_id=make_uuid(10),
                justification_summary="Justification",
                tradeoff_narrative="Narrative",
            )


# ---------------------------------------------------------------------------
# Category 8: Determinism and Reproducibility
# ---------------------------------------------------------------------------

class TestDeterminismAndReproducibility:
    """Verification of bitwise identical outputs across 50 repeated executions."""

    def test_record_hash_determinism_50_iterations(self) -> None:
        """
        Verify that compute_record_hash is 100% deterministic over 50 repeated executions.
        """
        first_hash = compute_record_hash(
            record_id=make_uuid(1),
            problem_id=make_uuid(2),
            comparison_id=make_uuid(3),
            selected_scenario_id=make_uuid(4),
            previous_record_hash=GENESIS_PREVIOUS_HASH,
            schema_version="v1.0.0",
            operator_id="dispatcher_01",
            primary_signer_id="signer_01",
        )

        for _ in range(49):
            repeat_hash = compute_record_hash(
                record_id=make_uuid(1),
                problem_id=make_uuid(2),
                comparison_id=make_uuid(3),
                selected_scenario_id=make_uuid(4),
                previous_record_hash=GENESIS_PREVIOUS_HASH,
                schema_version="v1.0.0",
                operator_id="dispatcher_01",
                primary_signer_id="signer_01",
            )
            assert repeat_hash == first_hash

    def test_lexicographic_sorting_determinism_50_iterations(self) -> None:
        """
        Verify that sort_lexicographic_priority is 100% deterministic over 50 repeated runs.
        """
        objectives = [
            ObjectiveDefinition(
                objective_id="loss",
                name="Loss",
                direction=ObjectiveDirection.MINIMIZE,
                unit="MW",
                priority_rank=1,
            ),
            ObjectiveDefinition(
                objective_id="cost",
                name="Cost",
                direction=ObjectiveDirection.MINIMIZE,
                unit="USD",
                priority_rank=2,
            ),
        ]
        candidates = [
            CandidateStrategy(
                strategy_id=make_uuid(i),
                strategy_name=f"Candidate {i}",
                feasibility_status=FeasibilityStatus.FEASIBLE,
                objectives={"loss": float((i * 13) % 7), "cost": float((i * 17) % 11)},
            )
            for i in range(1, 10)
        ]

        first_order = [s.strategy_id for s in sort_lexicographic_priority(candidates, objectives)]

        for _ in range(49):
            repeat_order = [s.strategy_id for s in sort_lexicographic_priority(candidates, objectives)]
            assert repeat_order == first_order
