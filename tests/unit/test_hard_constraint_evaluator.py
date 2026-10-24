"""
Unit tests for NIRNAYA deterministic hard-constraint evaluator.

Covers:
- All constraint operators: <=, >=, ==, IN_RANGE.
- Boundary conditions and values just inside/outside authorized tolerances.
- Distinguishing proven violations (INFEASIBLE) from unverified telemetry (UNKNOWN).
- Missing telemetry, stale evidence, freshness lockout (>120s), and UNRELIABLE quality.
- Unit mismatches and non-finite numbers (NaN, Inf).
- Aggregation semantics across mixed constraint sets (Fail-Closed).
- Strict determinism across repeated executions.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
try:
    import pytest
except ImportError:
    from tests.compat import pytest

from nirnaya.domain.enums import (
    ConstraintCategory,
    ConstraintOperator,
    FeasibilityStatus,
    TelemetryQuality,
)
from nirnaya.domain.models import (
    DecisionVariable,
    EvidenceReference,
    HardConstraint,
)
from nirnaya.evaluator.hard_constraint_evaluator import (
    evaluate_hard_constraint,
    evaluate_hard_constraints,
)

SAMPLE_DIGEST = "sha256:11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff"


@pytest.fixture
def valid_evidence() -> EvidenceReference:
    return EvidenceReference(
        source_id="SENSOR-PMU-01",
        evidence_type="PMU_TELEMETRY",
        timestamp=datetime.now(timezone.utc),
        cryptographic_digest=SAMPLE_DIGEST,
        freshness_seconds=5.0,
        is_stale=False,
        telemetry_quality=TelemetryQuality.VALIDATED,
    )


class TestInequalityLEQ:
    """Tests for '<=' upper bound operator."""

    def test_strictly_below_limit(self, valid_evidence: EvidenceReference) -> None:
        c = HardConstraint(
            constraint_id="C1",
            category=ConstraintCategory.THERMAL_CURRENT_LIMIT,
            target_variable="FLOW_1",
            operator=ConstraintOperator.LEQ,
            limit_value=100.0,
            unit="MW",
            tolerance=0.5,
        )
        res = evaluate_hard_constraint(c, 90.0, valid_evidence)
        assert res.status == FeasibilityStatus.FEASIBLE
        assert res.violation_magnitude == 0.0
        assert res.observed_value == 90.0
        assert res.evidence_refs == [SAMPLE_DIGEST]

    def test_exactly_at_limit(self, valid_evidence: EvidenceReference) -> None:
        c = HardConstraint(
            constraint_id="C1",
            category=ConstraintCategory.THERMAL_CURRENT_LIMIT,
            target_variable="FLOW_1",
            operator=ConstraintOperator.LEQ,
            limit_value=100.0,
            unit="MW",
            tolerance=0.0,
        )
        res = evaluate_hard_constraint(c, 100.0, valid_evidence)
        assert res.status == FeasibilityStatus.FEASIBLE
        assert res.violation_magnitude == 0.0

    def test_within_tolerance(self, valid_evidence: EvidenceReference) -> None:
        c = HardConstraint(
            constraint_id="C1",
            category=ConstraintCategory.THERMAL_CURRENT_LIMIT,
            target_variable="FLOW_1",
            operator=ConstraintOperator.LEQ,
            limit_value=100.0,
            unit="MW",
            tolerance=0.5,
        )
        # 100.4 is > 100.0 but <= 100.0 + 0.5 = 100.5
        res = evaluate_hard_constraint(c, 100.4, valid_evidence)
        assert res.status == FeasibilityStatus.FEASIBLE
        assert res.violation_magnitude == 0.0

    def test_exceeding_tolerance(self, valid_evidence: EvidenceReference) -> None:
        c = HardConstraint(
            constraint_id="C1",
            category=ConstraintCategory.THERMAL_CURRENT_LIMIT,
            target_variable="FLOW_1",
            operator=ConstraintOperator.LEQ,
            limit_value=100.0,
            unit="MW",
            tolerance=0.5,
        )
        # 100.6 > 100.5
        res = evaluate_hard_constraint(c, 100.6, valid_evidence)
        assert res.status == FeasibilityStatus.INFEASIBLE
        assert pytest.approx(res.violation_magnitude, 1e-6) == 0.6


class TestInequalityGEQ:
    """Tests for '>=' lower bound operator."""

    def test_strictly_above_limit(self, valid_evidence: EvidenceReference) -> None:
        c = HardConstraint(
            constraint_id="C2",
            category=ConstraintCategory.FREQUENCY_RESERVE_LIMIT,
            target_variable="FREQ_RES",
            operator=ConstraintOperator.GEQ,
            limit_value=50.0,
            unit="MW",
            tolerance=0.1,
        )
        res = evaluate_hard_constraint(c, 55.0, valid_evidence)
        assert res.status == FeasibilityStatus.FEASIBLE
        assert res.violation_magnitude == 0.0

    def test_within_tolerance(self, valid_evidence: EvidenceReference) -> None:
        c = HardConstraint(
            constraint_id="C2",
            category=ConstraintCategory.FREQUENCY_RESERVE_LIMIT,
            target_variable="FREQ_RES",
            operator=ConstraintOperator.GEQ,
            limit_value=50.0,
            unit="MW",
            tolerance=0.2,
        )
        # 49.85 >= 50.0 - 0.2 = 49.80
        res = evaluate_hard_constraint(c, 49.85, valid_evidence)
        assert res.status == FeasibilityStatus.FEASIBLE
        assert res.violation_magnitude == 0.0

    def test_exceeding_tolerance(self, valid_evidence: EvidenceReference) -> None:
        c = HardConstraint(
            constraint_id="C2",
            category=ConstraintCategory.FREQUENCY_RESERVE_LIMIT,
            target_variable="FREQ_RES",
            operator=ConstraintOperator.GEQ,
            limit_value=50.0,
            unit="MW",
            tolerance=0.2,
        )
        # 49.7 < 49.8
        res = evaluate_hard_constraint(c, 49.7, valid_evidence)
        assert res.status == FeasibilityStatus.INFEASIBLE
        assert pytest.approx(res.violation_magnitude, 1e-6) == 0.3


class TestEqualityEQ:
    """Tests for '==' exact target operator."""

    def test_exact_match(self, valid_evidence: EvidenceReference) -> None:
        c = HardConstraint(
            constraint_id="C_FREQ",
            category=ConstraintCategory.FREQUENCY_RESERVE_LIMIT,
            target_variable="GRID_FREQ",
            operator=ConstraintOperator.EQ,
            limit_value=50.0,
            unit="Hz",
            tolerance=0.05,
        )
        res = evaluate_hard_constraint(c, 50.0, valid_evidence)
        assert res.status == FeasibilityStatus.FEASIBLE
        assert res.violation_magnitude == 0.0

    def test_within_tolerance(self, valid_evidence: EvidenceReference) -> None:
        c = HardConstraint(
            constraint_id="C_FREQ",
            category=ConstraintCategory.FREQUENCY_RESERVE_LIMIT,
            target_variable="GRID_FREQ",
            operator=ConstraintOperator.EQ,
            limit_value=50.0,
            unit="Hz",
            tolerance=0.05,
        )
        # 50.04 differs by 0.04 <= 0.05
        res = evaluate_hard_constraint(c, 50.04, valid_evidence)
        assert res.status == FeasibilityStatus.FEASIBLE

    def test_outside_tolerance(self, valid_evidence: EvidenceReference) -> None:
        c = HardConstraint(
            constraint_id="C_FREQ",
            category=ConstraintCategory.FREQUENCY_RESERVE_LIMIT,
            target_variable="GRID_FREQ",
            operator=ConstraintOperator.EQ,
            limit_value=50.0,
            unit="Hz",
            tolerance=0.05,
        )
        # 50.08 differs by 0.08 > 0.05
        res = evaluate_hard_constraint(c, 50.08, valid_evidence)
        assert res.status == FeasibilityStatus.INFEASIBLE
        assert pytest.approx(res.violation_magnitude, 1e-6) == 0.08


class TestIntervalInRange:
    """Tests for 'IN_RANGE' interval bounds operator."""

    @pytest.fixture
    def voltage_band_constraint(self) -> HardConstraint:
        return HardConstraint(
            constraint_id="C_VOLT_BAND",
            category=ConstraintCategory.VOLTAGE_STABILITY_BAND,
            target_variable="BUS_VOLT",
            operator=ConstraintOperator.IN_RANGE,
            limit_value=(0.95, 1.05),
            unit="p.u.",
            tolerance=0.005,
        )

    def test_inside_interval(self, voltage_band_constraint: HardConstraint, valid_evidence: EvidenceReference) -> None:
        res = evaluate_hard_constraint(voltage_band_constraint, 1.00, valid_evidence)
        assert res.status == FeasibilityStatus.FEASIBLE
        assert res.violation_magnitude == 0.0

    def test_lower_boundary_inside_tolerance(
        self, voltage_band_constraint: HardConstraint, valid_evidence: EvidenceReference
    ) -> None:
        # 0.948 >= 0.95 - 0.005 = 0.945
        res = evaluate_hard_constraint(voltage_band_constraint, 0.948, valid_evidence)
        assert res.status == FeasibilityStatus.FEASIBLE
        assert res.violation_magnitude == 0.0

    def test_lower_boundary_breach(
        self, voltage_band_constraint: HardConstraint, valid_evidence: EvidenceReference
    ) -> None:
        # 0.940 < 0.945
        res = evaluate_hard_constraint(voltage_band_constraint, 0.940, valid_evidence)
        assert res.status == FeasibilityStatus.INFEASIBLE
        assert pytest.approx(res.violation_magnitude, 1e-6) == 0.010

    def test_upper_boundary_inside_tolerance(
        self, voltage_band_constraint: HardConstraint, valid_evidence: EvidenceReference
    ) -> None:
        # 1.053 <= 1.05 + 0.005 = 1.055
        res = evaluate_hard_constraint(voltage_band_constraint, 1.053, valid_evidence)
        assert res.status == FeasibilityStatus.FEASIBLE

    def test_upper_boundary_breach(
        self, voltage_band_constraint: HardConstraint, valid_evidence: EvidenceReference
    ) -> None:
        # 1.058 > 1.055
        res = evaluate_hard_constraint(voltage_band_constraint, 1.058, valid_evidence)
        assert res.status == FeasibilityStatus.INFEASIBLE
        assert pytest.approx(res.violation_magnitude, 1e-6) == 0.008


class TestEvidenceAndUnknownHandling:
    """Tests for unknown states, evidence degradation, and missing data."""

    @pytest.fixture
    def thermal_constraint(self) -> HardConstraint:
        return HardConstraint(
            constraint_id="C_LINE",
            category=ConstraintCategory.THERMAL_CURRENT_LIMIT,
            target_variable="LINE_FLOW",
            operator=ConstraintOperator.LEQ,
            limit_value=200.0,
            unit="MW",
            tolerance=0.0,
        )

    def test_missing_variable_returns_unknown(self, thermal_constraint: HardConstraint) -> None:
        res = evaluate_hard_constraint(thermal_constraint, None)
        assert res.status == FeasibilityStatus.UNKNOWN
        assert res.observed_value is None
        assert "missing from observed system state" in res.explanation

    def test_non_finite_variable_returns_unknown(self, thermal_constraint: HardConstraint) -> None:
        res = evaluate_hard_constraint(thermal_constraint, float("nan"))
        assert res.status == FeasibilityStatus.UNKNOWN
        assert "Non-finite observed value" in res.explanation

    def test_unit_mismatch_returns_unknown(self, thermal_constraint: HardConstraint) -> None:
        # Variable provided in kV instead of MW
        var = DecisionVariable(variable_id="LINE_FLOW", name="Line Flow", unit="kV", value=150.0)
        res = evaluate_hard_constraint(thermal_constraint, var)
        assert res.status == FeasibilityStatus.UNKNOWN
        assert "Physical unit mismatch" in res.explanation

    def test_stale_evidence_returns_unknown(self, thermal_constraint: HardConstraint) -> None:
        ev = EvidenceReference(
            source_id="S1",
            evidence_type="PMU",
            timestamp=datetime.now(timezone.utc),
            cryptographic_digest=SAMPLE_DIGEST,
            is_stale=True,  # Mark stale
        )
        res = evaluate_hard_constraint(thermal_constraint, 150.0, ev)
        assert res.status == FeasibilityStatus.UNKNOWN
        assert "marked stale" in res.explanation

    def test_freshness_lockout_returns_unknown(self, thermal_constraint: HardConstraint) -> None:
        ev = EvidenceReference(
            source_id="S1",
            evidence_type="PMU",
            timestamp=datetime.now(timezone.utc),
            cryptographic_digest=SAMPLE_DIGEST,
            freshness_seconds=130.0,  # Exceeds 120s lockout threshold
        )
        res = evaluate_hard_constraint(thermal_constraint, 150.0, ev, max_freshness_seconds=120.0)
        assert res.status == FeasibilityStatus.UNKNOWN
        assert "exceeds lockout threshold" in res.explanation

    def test_unreliable_telemetry_quality_returns_unknown(self, thermal_constraint: HardConstraint) -> None:
        ev = EvidenceReference(
            source_id="S1",
            evidence_type="PMU",
            timestamp=datetime.now(timezone.utc),
            cryptographic_digest=SAMPLE_DIGEST,
            telemetry_quality=TelemetryQuality.UNRELIABLE,
        )
        res = evaluate_hard_constraint(thermal_constraint, 150.0, ev)
        assert res.status == FeasibilityStatus.UNKNOWN
        assert "UNRELIABLE" in res.explanation

    def test_missing_required_evidence_returns_unknown(self, thermal_constraint: HardConstraint) -> None:
        res = evaluate_hard_constraint(thermal_constraint, 150.0, evidence=None, require_evidence=True)
        assert res.status == FeasibilityStatus.UNKNOWN
        assert "required but missing" in res.explanation


class TestAggregationAndFailClosed:
    """Tests for multi-constraint aggregation and safety invariants."""

    @pytest.fixture
    def constraints(self) -> list[HardConstraint]:
        return [
            HardConstraint(
                constraint_id="C1",
                category=ConstraintCategory.THERMAL_CURRENT_LIMIT,
                target_variable="FLOW_1",
                operator=ConstraintOperator.LEQ,
                limit_value=100.0,
                unit="MW",
            ),
            HardConstraint(
                constraint_id="C2",
                category=ConstraintCategory.VOLTAGE_STABILITY_BAND,
                target_variable="VOLT_1",
                operator=ConstraintOperator.IN_RANGE,
                limit_value=(0.95, 1.05),
                unit="p.u.",
            ),
        ]

    def test_all_feasible_produces_feasible(self, constraints: list[HardConstraint]) -> None:
        variables = {
            "FLOW_1": DecisionVariable(variable_id="FLOW_1", name="Flow 1", unit="MW", value=80.0),
            "VOLT_1": DecisionVariable(variable_id="VOLT_1", name="Volt 1", unit="p.u.", value=1.01),
        }
        summary = evaluate_hard_constraints(constraints, variables)
        assert summary.overall_status == FeasibilityStatus.FEASIBLE
        assert summary.violations_count == 0
        assert summary.unknown_count == 0
        assert len(summary.violations) == 0

    def test_one_violation_produces_infeasible(self, constraints: list[HardConstraint]) -> None:
        variables = {
            "FLOW_1": DecisionVariable(variable_id="FLOW_1", name="Flow 1", unit="MW", value=120.0),  # Violates C1
            "VOLT_1": DecisionVariable(variable_id="VOLT_1", name="Volt 1", unit="p.u.", value=1.01),
        }
        summary = evaluate_hard_constraints(constraints, variables)
        assert summary.overall_status == FeasibilityStatus.INFEASIBLE
        assert summary.violations_count == 1
        assert summary.unknown_count == 0
        assert len(summary.violations) == 1
        assert summary.violations[0].constraint_id == "C1"

    def test_fail_closed_unknown_prevents_feasible(self, constraints: list[HardConstraint]) -> None:
        # FLOW_1 is feasible, but VOLT_1 is missing!
        variables = {
            "FLOW_1": DecisionVariable(variable_id="FLOW_1", name="Flow 1", unit="MW", value=80.0),
        }
        summary = evaluate_hard_constraints(constraints, variables)
        assert summary.overall_status == FeasibilityStatus.UNKNOWN
        assert summary.violations_count == 0
        assert summary.unknown_count == 1

    def test_violation_overrides_unknown(self, constraints: list[HardConstraint]) -> None:
        # FLOW_1 is proven INFEASIBLE, and VOLT_1 is UNKNOWN
        variables = {
            "FLOW_1": DecisionVariable(variable_id="FLOW_1", name="Flow 1", unit="MW", value=150.0),  # INFEASIBLE
        }
        summary = evaluate_hard_constraints(constraints, variables)
        # Proven physical violation MUST be classified INFEASIBLE
        assert summary.overall_status == FeasibilityStatus.INFEASIBLE
        assert summary.violations_count == 1
        assert summary.unknown_count == 1


class TestDeterminism:
    """Tests confirming strict determinism of evaluation functions."""

    def test_repeated_evaluation_produces_identical_results(self) -> None:
        c = HardConstraint(
            constraint_id="C_DET",
            category=ConstraintCategory.THERMAL_CURRENT_LIMIT,
            target_variable="FLOW",
            operator=ConstraintOperator.LEQ,
            limit_value=300.0,
            unit="MW",
            tolerance=0.01,
        )
        var = DecisionVariable(variable_id="FLOW", name="Flow", unit="MW", value=300.005)

        first_eval = evaluate_hard_constraint(c, var)

        for _ in range(100):
            repeated = evaluate_hard_constraint(c, var)
            assert repeated.status == first_eval.status
            assert repeated.violation_magnitude == first_eval.violation_magnitude
            assert repeated.explanation == first_eval.explanation
