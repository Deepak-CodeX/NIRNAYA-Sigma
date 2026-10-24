"""
Unit tests for NIRNAYA domain models.

Covers:
- Valid model construction and attribute immutability/types.
- Strict rejection of non-finite numbers (NaN, +Inf, -Inf).
- Constraint operator and limit value bounds validation (ADR-011).
- Cryptographic SHA-256 digest format enforcement.
- Strict closed schema validation (extra='forbid', ADR-012).
- HardConstraintSummary fail-closed safety invariant verification.
- JSON serialization roundtrip and schema consistency.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
try:
    import pytest
except ImportError:
    from tests.compat import pytest
from pydantic import ValidationError

from nirnaya.domain.enums import (
    ConstraintCategory,
    ConstraintOperator,
    FeasibilityStatus,
    TelemetryQuality,
)
from nirnaya.domain.models import (
    ConstraintEvaluation,
    DecisionProblem,
    DecisionVariable,
    EvidenceReference,
    HardConstraint,
    HardConstraintSummary,
)

VALID_SHA256 = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class TestDecisionVariable:
    """Tests for DecisionVariable model."""

    def test_valid_construction(self) -> None:
        var = DecisionVariable(
            variable_id="V_BUS_01",
            name="Bus 01 Voltage Magnitude",
            unit="p.u.",
            value=1.02,
        )
        assert var.variable_id == "V_BUS_01"
        assert var.name == "Bus 01 Voltage Magnitude"
        assert var.unit == "p.u."
        assert var.value == 1.02

    @pytest.mark.parametrize("invalid_val", [float("nan"), float("inf"), float("-inf")])
    def test_reject_non_finite_values(self, invalid_val: float) -> None:
        with pytest.raises(ValidationError, match="must be a finite number"):
            DecisionVariable(
                variable_id="V_TEST",
                name="Non finite variable",
                unit="kV",
                value=invalid_val,
            )

    @pytest.mark.parametrize("bad_id", ["", "   ", "bus id with space", "bus@123", "bus#4"])
    def test_reject_malformed_variable_ids(self, bad_id: str) -> None:
        with pytest.raises(ValidationError):
            DecisionVariable(
                variable_id=bad_id,
                name="Malformed variable",
                unit="MW",
                value=100.0,
            )

    def test_reject_extra_fields(self) -> None:
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            DecisionVariable(  # type: ignore[call-arg]
                variable_id="P_GEN_01",
                name="Generator 1 Real Power",
                unit="MW",
                value=250.0,
                extra_metadata="forbidden",
            )


class TestEvidenceReference:
    """Tests for EvidenceReference model."""

    def test_valid_construction(self) -> None:
        now = datetime.now(timezone.utc)
        ev = EvidenceReference(
            source_id="SCADA-RTU-4001",
            evidence_type="PMU_TELEMETRY",
            timestamp=now,
            cryptographic_digest=VALID_SHA256,
            freshness_seconds=12.5,
            is_stale=False,
            telemetry_quality=TelemetryQuality.VALIDATED,
        )
        assert ev.source_id == "SCADA-RTU-4001"
        assert ev.freshness_seconds == 12.5
        assert ev.is_stale is False
        assert ev.telemetry_quality == TelemetryQuality.VALIDATED

    @pytest.mark.parametrize(
        "bad_digest",
        [
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # missing prefix
            "sha256:E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855",  # uppercase
            "sha256:short_digest",  # too short
            "sha256:" + "a" * 63,  # 63 chars
            "sha256:" + "a" * 65,  # 65 chars
            "md5:e3b0c44298fc1c149afbf4c8996fb924",  # wrong algorithm
        ],
    )
    def test_reject_invalid_digest(self, bad_digest: str) -> None:
        with pytest.raises(ValidationError, match="cryptographic_digest must be lowercase"):
            EvidenceReference(
                source_id="SCADA-01",
                evidence_type="PMU",
                timestamp=datetime.now(timezone.utc),
                cryptographic_digest=bad_digest,
            )

    @pytest.mark.parametrize("invalid_freshness", [float("nan"), float("inf"), -1.0])
    def test_reject_invalid_freshness(self, invalid_freshness: float) -> None:
        with pytest.raises(ValidationError):
            EvidenceReference(
                source_id="SCADA-01",
                evidence_type="PMU",
                timestamp=datetime.now(timezone.utc),
                cryptographic_digest=VALID_SHA256,
                freshness_seconds=invalid_freshness,
            )


class TestHardConstraint:
    """Tests for HardConstraint model."""

    def test_valid_scalar_constraint(self) -> None:
        c = HardConstraint(
            constraint_id="C_THERMAL_LINE_1",
            category=ConstraintCategory.THERMAL_CURRENT_LIMIT,
            target_variable="FLOW_LINE_1",
            operator=ConstraintOperator.LEQ,
            limit_value=400.0,
            unit="MVA",
            tolerance=0.005,
        )
        assert c.constraint_id == "C_THERMAL_LINE_1"
        assert c.operator == ConstraintOperator.LEQ
        assert c.limit_value == 400.0
        assert c.tolerance == 0.005

    def test_valid_interval_constraint_adr011(self) -> None:
        c = HardConstraint(
            constraint_id="C_VOLT_BAND_BUS_2",
            category=ConstraintCategory.VOLTAGE_STABILITY_BAND,
            target_variable="VOLT_BUS_2",
            operator=ConstraintOperator.IN_RANGE,
            limit_value=(0.95, 1.05),
            unit="p.u.",
            tolerance=0.001,
        )
        assert c.operator == ConstraintOperator.IN_RANGE
        assert c.limit_value == (0.95, 1.05)

    def test_reject_inverted_interval_bounds(self) -> None:
        with pytest.raises(ValidationError, match="lower_bound .* must be <= upper_bound"):
            HardConstraint(
                constraint_id="C_VOLT_BAD",
                category=ConstraintCategory.VOLTAGE_STABILITY_BAND,
                target_variable="VOLT_BUS_2",
                operator=ConstraintOperator.IN_RANGE,
                limit_value=[1.05, 0.95],  # Inverted!
                unit="p.u.",
            )

    @pytest.mark.parametrize(
        "bad_limit",
        [
            [],
            [1.0],
            [0.90, 1.00, 1.10],
            "0.95..1.05",
        ],
    )
    def test_reject_malformed_interval_limit(self, bad_limit: object) -> None:
        with pytest.raises(ValidationError):
            HardConstraint(
                constraint_id="C_BAD_RANGE",
                category=ConstraintCategory.VOLTAGE_STABILITY_BAND,
                target_variable="V",
                operator=ConstraintOperator.IN_RANGE,
                limit_value=bad_limit,  # type: ignore[arg-type]
                unit="p.u.",
            )

    def test_reject_array_limit_for_scalar_operator(self) -> None:
        with pytest.raises(ValidationError, match="requires a scalar numeric limit"):
            HardConstraint(
                constraint_id="C_SCALAR_BAD",
                category=ConstraintCategory.THERMAL_CURRENT_LIMIT,
                target_variable="FLOW",
                operator=ConstraintOperator.LEQ,
                limit_value=[100.0, 200.0],
                unit="MVA",
            )

    @pytest.mark.parametrize("bad_tol", [-0.01, float("nan"), float("inf")])
    def test_reject_invalid_tolerance(self, bad_tol: float) -> None:
        with pytest.raises(ValidationError):
            HardConstraint(
                constraint_id="C_TOL",
                category=ConstraintCategory.THERMAL_CURRENT_LIMIT,
                target_variable="FLOW",
                operator=ConstraintOperator.LEQ,
                limit_value=100.0,
                unit="MVA",
                tolerance=bad_tol,
            )


class TestHardConstraintSummary:
    """Tests for HardConstraintSummary fail-closed safety invariant."""

    def test_valid_feasible_summary(self) -> None:
        summary = HardConstraintSummary(
            total_evaluated=2,
            violations_count=0,
            unknown_count=0,
            overall_status=FeasibilityStatus.FEASIBLE,
            violations=[],
            evaluations=[],
        )
        assert summary.overall_status == FeasibilityStatus.FEASIBLE

    def test_valid_infeasible_summary(self) -> None:
        summary = HardConstraintSummary(
            total_evaluated=2,
            violations_count=1,
            unknown_count=0,
            overall_status=FeasibilityStatus.INFEASIBLE,
            violations=[],
            evaluations=[],
        )
        assert summary.overall_status == FeasibilityStatus.INFEASIBLE

    def test_valid_unknown_summary(self) -> None:
        summary = HardConstraintSummary(
            total_evaluated=2,
            violations_count=0,
            unknown_count=1,
            overall_status=FeasibilityStatus.UNKNOWN,
            violations=[],
            evaluations=[],
        )
        assert summary.overall_status == FeasibilityStatus.UNKNOWN

    def test_fail_closed_invariant_rejects_feasible_when_unknown(self) -> None:
        with pytest.raises(ValidationError, match="Safety invariant violated: overall status must be UNKNOWN"):
            HardConstraintSummary(
                total_evaluated=2,
                violations_count=0,
                unknown_count=1,
                overall_status=FeasibilityStatus.FEASIBLE,  # FORBIDDEN: Cannot be FEASIBLE if UNKNOWN
                violations=[],
                evaluations=[],
            )

    def test_rejects_feasible_when_violations_exist(self) -> None:
        with pytest.raises(ValidationError, match="Overall status must be INFEASIBLE when violations_count > 0"):
            HardConstraintSummary(
                total_evaluated=2,
                violations_count=1,
                unknown_count=0,
                overall_status=FeasibilityStatus.FEASIBLE,
                violations=[],
                evaluations=[],
            )


class TestDecisionProblemSerialization:
    """Tests for DecisionProblem model and JSON serialization."""

    def test_serialization_roundtrip(self) -> None:
        now = datetime.now(timezone.utc)
        problem = DecisionProblem(
            problem_id="PROB-2026-001",
            schema_version="v1.0.0",
            created_at=now,
            decision_maker_context={
                "role": "SENIOR_CONTROLLER",
                "jurisdiction": "REGIONAL_DISPATCH",
                "operator_id": "OP-981",
            },
            state_snapshot_id="550e8400-e29b-41d4-a716-446655440000",
            incident_context_ids=["6ba7b810-9dad-11d1-80b4-00c04fd430c8"],
            hard_constraints=[
                HardConstraint(
                    constraint_id="C_MAX_FLOW",
                    category=ConstraintCategory.THERMAL_CURRENT_LIMIT,
                    target_variable="LINE_01_FLOW",
                    operator=ConstraintOperator.LEQ,
                    limit_value=500.0,
                    unit="MW",
                    tolerance=0.01,
                )
            ],
            evidence_chain=[
                EvidenceReference(
                    source_id="EMS-INGRESS-01",
                    evidence_type="STATE_ESTIMATION",
                    timestamp=now,
                    cryptographic_digest=VALID_SHA256,
                    freshness_seconds=5.0,
                )
            ],
        )

        json_str = problem.model_dump_json()
        data = json.loads(json_str)
        assert data["problem_id"] == "PROB-2026-001"
        assert data["schema_version"] == "v1.0.0"
        assert len(data["hard_constraints"]) == 1
        assert data["hard_constraints"][0]["limit_value"] == 500.0

        # Validate roundtrip parse
        reconstructed = DecisionProblem.model_validate_json(json_str)
        assert reconstructed.problem_id == problem.problem_id
        assert reconstructed.hard_constraints[0].constraint_id == "C_MAX_FLOW"

    def test_parse_phase0_decision_problem_example(self) -> None:
        """Verify that canonical Phase 0 example payload parses cleanly into DecisionProblem."""
        import os
        example_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "contracts", "examples", "decision_problem.example.json"
        )
        with open(example_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        problem = DecisionProblem.model_validate(data)
        assert problem.problem_id == "c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f"
        assert problem.schema_version == "v1.0.0"
        assert len(problem.hard_constraints) == 2
        assert problem.hard_constraints[0].operator == ConstraintOperator.LEQ
        assert problem.hard_constraints[0].limit_value == 100.0
        assert problem.hard_constraints[1].operator == ConstraintOperator.IN_RANGE
        assert problem.hard_constraints[1].limit_value == (0.95, 1.05)
        assert len(problem.evidence_chain) == 1
        assert problem.evidence_chain[0].source_id == "VAJRA-Ω-EMS"

    def test_schema_conformance_with_jsonschema(self) -> None:
        """Verify that serialized DecisionProblem conforms strictly to contracts/schemas/decision_problem.json."""
        import os
        import jsonschema

        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "contracts", "schemas", "decision_problem.json"
        )
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        now = datetime.now(timezone.utc)
        problem = DecisionProblem(
            problem_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            schema_version="v1.0.0",
            created_at=now,
            decision_maker_context={
                "role": "DISPATCHER",
                "jurisdiction": "WEST_GRID",
                "operator_id": "OP-101",
            },
            state_snapshot_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
            incident_context_ids=[],
            hard_constraints=[
                HardConstraint(
                    constraint_id="C_MAX_FLOW",
                    category=ConstraintCategory.THERMAL_CURRENT_LIMIT,
                    target_variable="LINE_01_FLOW",
                    operator=ConstraintOperator.LEQ,
                    limit_value=500.0,
                    unit="MW",
                    tolerance=0.01,
                )
            ],
            evidence_chain=[
                EvidenceReference(
                    source_id="EMS-01",
                    evidence_type="TELEMETRY",
                    timestamp=now,
                    cryptographic_digest=VALID_SHA256,
                )
            ],
        )

        dumped = problem.model_dump(mode="json")
        # Assert jsonschema validation passes with zero errors
        jsonschema.validate(instance=dumped, schema=schema)
