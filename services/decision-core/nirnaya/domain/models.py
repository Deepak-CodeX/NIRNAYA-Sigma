"""
Validated domain types for NIRNAYA decision models.

Strict domain representations adhering to Phase 0 contracts:
- Rejects non-finite numbers (NaN, +Inf, -Inf).
- Enforces ADR-011 interval ordering (lower_bound <= upper_bound).
- Enforces ADR-012 closed schemas (model_config = ConfigDict(extra='forbid')).
- Enforces strict SHA-256 cryptographic digest formats.
"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any, Sequence

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from nirnaya.domain.enums import (
    AuthorizationState,
    BaselineType,
    ConstraintCategory,
    ConstraintOperator,
    DeltaImpact,
    DistributionType,
    DominanceRelation,
    EpistemicCategory,
    FeasibilityStatus,
    LossConvention,
    ObjectiveDirection,
    OperationalDispatchStatus,
    RegretType,
    SignatureAlgorithm,
    TelemetryQuality,
    UncertaintyType,
)

IDENTIFIER_REGEX = re.compile(r"^[A-Za-z0-9_.-]+$")
SHA256_DIGEST_REGEX = re.compile(r"^sha256:[a-f0-9]{64}$")
SCHEMA_VERSION_REGEX = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+$")
UUID_REGEX = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
ISO_DATETIME_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


def validate_uuid_string(v: str, field_name: str) -> str:
    """Validate that a string conforms to canonical UUID representation."""
    s = v.strip()
    if not UUID_REGEX.match(s):
        raise ValueError(f"'{field_name}' must be a valid UUID, got '{v}'")
    return s.lower()


def validate_finite_number(value: float, field_name: str) -> float:
    """Validate that a float value is finite and not NaN or infinite."""
    if not isinstance(value, (int, float)):
        raise TypeError(f"'{field_name}' must be a numeric value, got {type(value).__name__}")
    f_val = float(value)
    if not math.isfinite(f_val):
        raise ValueError(f"'{field_name}' must be a finite number; got {value}")
    return f_val


class DecisionVariable(BaseModel):
    """
    Physical or operational decision/state variable.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    variable_id: str = Field(..., description="Stable unique variable identifier.")
    name: str = Field(..., min_length=1, description="Human-readable variable name.")
    unit: str = Field(..., min_length=1, description="Physical unit of measurement.")
    value: float = Field(..., description="Observed or simulated numerical value.")

    @field_validator("variable_id")
    @classmethod
    def validate_variable_id(cls, v: str) -> str:
        s = v.strip()
        if not s or not IDENTIFIER_REGEX.match(s):
            raise ValueError(f"variable_id must be non-empty and match pattern '^[A-Za-z0-9_-]+$', got '{v}'")
        return s

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("unit cannot be blank")
        return s

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: float) -> float:
        return validate_finite_number(v, "value")


class EvidenceReference(BaseModel):
    """
    Cryptographic and provenance reference for telemetry or model evidence.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(..., min_length=1, description="Source system or sensor identifier.")
    evidence_type: str = Field(..., min_length=1, description="Category of evidence (e.g. SCADA_PMU).")
    timestamp: datetime = Field(..., description="ISO 8601 acquisition timestamp.")
    cryptographic_digest: str = Field(
        ...,
        description="Lowercase SHA-256 digest formatted as 'sha256:<64_hex_digits>'."
    )
    freshness_seconds: float | None = Field(
        default=None,
        ge=0.0,
        description="Elapsed duration in seconds between source sampling and evaluation."
    )
    is_stale: bool = Field(
        default=False,
        description="Explicit flag marking evidence as stale or expired."
    )
    telemetry_quality: TelemetryQuality | None = Field(
        default=None,
        description="Confidence classification of the evidence source."
    )

    @field_validator("source_id", "evidence_type")
    @classmethod
    def validate_non_blank_strings(cls, v: str, info: Any) -> str:
        s = v.strip()
        if not s:
            raise ValueError(f"{info.field_name} cannot be blank")
        return s

    @field_validator("cryptographic_digest")
    @classmethod
    def validate_digest(cls, v: str) -> str:
        s = v.strip()
        if not SHA256_DIGEST_REGEX.match(s):
            raise ValueError(
                f"cryptographic_digest must be lowercase 'sha256:<64_hex_digits>', got '{v}'"
            )
        return s

    @field_validator("freshness_seconds")
    @classmethod
    def validate_freshness(cls, v: float | None) -> float | None:
        if v is not None:
            return validate_finite_number(v, "freshness_seconds")
        return v


class HardConstraint(BaseModel):
    """
    Physical law, statutory limit, or operational hard constraint.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    constraint_id: str = Field(..., description="Stable unique constraint identifier.")
    category: ConstraintCategory | str = Field(..., description="Constraint domain category.")
    target_variable: str = Field(..., description="Target decision/state variable identifier.")
    operator: ConstraintOperator = Field(..., description="Inequality/equality or interval operator.")
    limit_value: float | tuple[float, float] = Field(
        ...,
        description="Scalar limit for <=, >=, ==; or (lower, upper) for IN_RANGE where lower <= upper."
    )
    unit: str = Field(..., min_length=1, description="Physical unit of the constraint limit.")
    tolerance: float = Field(
        default=0.0,
        ge=0.0,
        description="Authorized numerical tolerance in physical units (must be >= 0.0)."
    )

    @field_validator("constraint_id", "target_variable")
    @classmethod
    def validate_ids(cls, v: str, info: Any) -> str:
        s = v.strip()
        if not s or not IDENTIFIER_REGEX.match(s):
            raise ValueError(
                f"{info.field_name} must be non-empty and match pattern '^[A-Za-z0-9_-]+$', got '{v}'"
            )
        return s

    @field_validator("unit")
    @classmethod
    def validate_unit(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("unit cannot be blank")
        return s

    @field_validator("tolerance")
    @classmethod
    def validate_tolerance(cls, v: float) -> float:
        return validate_finite_number(v, "tolerance")

    @model_validator(mode="before")
    @classmethod
    def normalize_and_validate_limits(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        op = data.get("operator")
        limit = data.get("limit_value")

        if op is None or limit is None:
            return data

        # Normalize operator if passed as string
        if isinstance(op, ConstraintOperator):
            op_val = op.value
        else:
            op_val = str(op)

        if op_val == ConstraintOperator.IN_RANGE.value:
            if not isinstance(limit, (list, tuple)):
                raise ValueError(
                    f"Operator '{op_val}' requires a 2-element sequence [lower_bound, upper_bound]; "
                    f"got {type(limit).__name__}"
                )
            if len(limit) != 2:
                raise ValueError(
                    f"Operator '{op_val}' requires exactly 2 bounds [lower_bound, upper_bound]; "
                    f"got {len(limit)} elements"
                )
            lower = validate_finite_number(limit[0], "limit_value[0]")
            upper = validate_finite_number(limit[1], "limit_value[1]")
            if lower > upper:
                raise ValueError(
                    f"Operator '{op_val}' invalid bounds: lower_bound ({lower}) must be <= "
                    f"upper_bound ({upper})"
                )
            # Store as immutable tuple of floats
            data["limit_value"] = (lower, upper)
        elif op_val in (
            ConstraintOperator.LEQ.value,
            ConstraintOperator.GEQ.value,
            ConstraintOperator.EQ.value,
        ):
            if isinstance(limit, (list, tuple)):
                raise ValueError(
                    f"Operator '{op_val}' requires a scalar numeric limit, got sequence: {limit}"
                )
            data["limit_value"] = validate_finite_number(limit, "limit_value")
        else:
            raise ValueError(f"Unsupported constraint operator '{op}'")

        return data


class ConstraintEvaluation(BaseModel):
    """
    Deterministic result of evaluating a single hard constraint against observed evidence.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    constraint_id: str = Field(..., description="Evaluated constraint identifier.")
    target_element: str = Field(..., description="Target variable or element identifier.")
    status: FeasibilityStatus = Field(..., description="Evaluation outcome state.")
    observed_value: float | None = Field(
        default=None,
        description="Observed numeric value, or None if missing or non-finite."
    )
    limit_value: float | tuple[float, float] | None = Field(
        default=None,
        description="Limit value or reference interval applied during evaluation."
    )
    violation_magnitude: float = Field(
        default=0.0,
        ge=0.0,
        description="Positive numerical violation magnitude beyond boundary (0.0 if feasible/unknown)."
    )
    unit: str = Field(..., description="Physical unit of measurement.")
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Digest or source identifiers of evidence consulted."
    )
    explanation: str = Field(..., description="Deterministic machine-readable explanation.")

    @field_validator("observed_value")
    @classmethod
    def validate_observed(cls, v: float | None) -> float | None:
        if v is not None:
            return validate_finite_number(v, "observed_value")
        return v

    @field_validator("violation_magnitude")
    @classmethod
    def validate_magnitude(cls, v: float) -> float:
        return validate_finite_number(v, "violation_magnitude")


class HardConstraintSummary(BaseModel):
    """
    Summary aggregation of hard constraint evaluations for a scenario.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    total_evaluated: int = Field(..., ge=0, description="Total count of hard constraints evaluated.")
    violations_count: int = Field(..., ge=0, description="Count of proven constraint violations.")
    unknown_count: int = Field(..., ge=0, description="Count of constraints with unverified/unknown status.")
    overall_status: FeasibilityStatus = Field(..., description="Aggregate feasibility outcome.")
    violations: list[ConstraintEvaluation] = Field(
        default_factory=list,
        description="Detailed evaluations for all INFEASIBLE constraints."
    )
    evaluations: list[ConstraintEvaluation] = Field(
        default_factory=list,
        description="Complete list of all constraint evaluations."
    )

    @model_validator(mode="after")
    def verify_fail_closed_invariant(self) -> HardConstraintSummary:
        """
        Enforce the canonical Phase 0 safety invariant:
        - If violations_count > 0: overall_status must be INFEASIBLE.
        - Else if unknown_count > 0: overall_status must be UNKNOWN (fail-closed).
        - Only if violations_count == 0 and unknown_count == 0: overall_status may be FEASIBLE.
        """
        if self.violations_count > 0:
            if self.overall_status != FeasibilityStatus.INFEASIBLE:
                raise ValueError(
                    f"Overall status must be INFEASIBLE when violations_count > 0 "
                    f"(violations={self.violations_count}); got {self.overall_status}"
                )
        elif self.unknown_count > 0:
            if self.overall_status != FeasibilityStatus.UNKNOWN:
                raise ValueError(
                    f"Safety invariant violated: overall status must be UNKNOWN when any "
                    f"constraint is unverified (unknown={self.unknown_count}); got {self.overall_status}"
                )
        else:
            if self.overall_status != FeasibilityStatus.FEASIBLE:
                raise ValueError(
                    f"Overall status must be FEASIBLE when violations_count=0 and unknown_count=0; "
                    f"got {self.overall_status}"
                )
        return self


class DecisionProblem(BaseModel):
    """
    Canonical representation of a structured decision problem instance: D = (S, A, C, O, M, U, E).
    """
    model_config = ConfigDict(extra="forbid")

    problem_id: str = Field(..., description="Unique decision problem instance identifier.")
    schema_version: str = Field(..., description="Schema version identifier (e.g. 'v1.0.0').")
    created_at: datetime = Field(..., description="Timestamp when decision problem was created.")
    decision_maker_context: dict[str, Any] = Field(..., description="Context of requesting human operator.")
    state_snapshot_id: str = Field(..., description="Referenced system state snapshot UUID.")
    incident_context_ids: list[str] = Field(
        default_factory=list,
        description="Referenced incident context identifiers."
    )
    candidate_actions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Candidate operational actions under evaluation."
    )
    hard_constraints: list[HardConstraint] = Field(
        default_factory=list,
        description="Hard physical and operational constraints that must be satisfied."
    )
    soft_constraints: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Soft operational preferences and penalty weights."
    )
    objectives: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Optimization objectives with physical units and directions."
    )
    domain_model_references: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Domain physics models referenced for simulation."
    )
    uncertainty_parameters: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Aleatory and epistemic uncertainty specifications."
    )
    evidence_chain: list[EvidenceReference] = Field(
        default_factory=list,
        description="Cryptographic provenance references for state and input data."
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        s = v.strip()
        if not SCHEMA_VERSION_REGEX.match(s):
            raise ValueError(f"schema_version must match pattern '^v[0-9]+\\.[0-9]+\\.[0-9]+$', got '{v}'")
        return s

    @field_validator("problem_id", "state_snapshot_id")
    @classmethod
    def validate_ids(cls, v: str, info: Any) -> str:
        s = v.strip()
        if not s:
            raise ValueError(f"{info.field_name} cannot be blank")
        return s


class ObjectiveDefinition(BaseModel):
    """
    Formal specification of an operational objective function.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    objective_id: str = Field(..., description="Unique objective identifier.")
    name: str = Field(..., min_length=1, description="Descriptive objective name.")
    direction: ObjectiveDirection = Field(..., description="Optimization direction (MINIMIZE or MAXIMIZE).")
    unit: str = Field(..., min_length=1, description="Physical unit of measurement.")
    priority_rank: int | None = Field(
        default=None,
        ge=1,
        description="Hierarchical lexicographic priority rank (1 = highest priority)."
    )
    evaluation_expression: str | None = Field(
        default=None,
        description="Mathematical or algorithmic evaluation formula."
    )

    @field_validator("objective_id")
    @classmethod
    def validate_objective_id(cls, v: str) -> str:
        s = v.strip()
        if not s or not IDENTIFIER_REGEX.match(s):
            raise ValueError(f"objective_id must match pattern '^[A-Za-z0-9_.-]+$', got '{v}'")
        return s

    @field_validator("name", "unit")
    @classmethod
    def validate_non_blank(cls, v: str, info: Any) -> str:
        s = v.strip()
        if not s:
            raise ValueError(f"{info.field_name} cannot be blank")
        return s


class CandidateStrategy(BaseModel):
    """
    Evaluated operational candidate strategy with feasibility state and objective metrics.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_id: str = Field(..., description="Unique strategy scenario identifier.")
    strategy_name: str = Field(..., min_length=1, description="Human-readable operational strategy name.")
    feasibility_status: FeasibilityStatus = Field(
        ...,
        description="Feasibility determination. Only FEASIBLE strategies enter Pareto ranking."
    )
    objectives: dict[str, float] = Field(
        ...,
        description="Evaluated numerical metrics for each objective in the decision problem."
    )
    objective_units: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of objective_id to physical unit for auditing."
    )
    delta_vs_baseline: dict[str, float] = Field(
        default_factory=dict,
        description="Relative deltas vs counterfactual baseline (f_k(x) - f_k(x0))."
    )
    max_regret: float | None = Field(
        default=None,
        ge=0.0,
        description="Maximum performance regret under bounded uncertainty."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional execution metadata (e.g. action count, solve time)."
    )

    @field_validator("strategy_id")
    @classmethod
    def validate_strategy_id(cls, v: str) -> str:
        s = v.strip()
        if not s or not IDENTIFIER_REGEX.match(s):
            raise ValueError(f"strategy_id must match pattern '^[A-Za-z0-9_.-]+$', got '{v}'")
        return s

    @field_validator("objectives", "delta_vs_baseline")
    @classmethod
    def validate_finite_objective_values(cls, v: dict[str, float], info: Any) -> dict[str, float]:
        validated = {}
        for k, val in v.items():
            k_clean = k.strip()
            if not k_clean:
                raise ValueError(f"Objective ID in {info.field_name} cannot be blank")
            validated[k_clean] = validate_finite_number(val, f"{info.field_name}['{k}']")
        return validated

    @field_validator("max_regret")
    @classmethod
    def validate_regret(cls, v: float | None) -> float | None:
        if v is not None:
            return validate_finite_number(v, "max_regret")
        return v


class ParetoFront(BaseModel):
    """
    A single non-dominated front generated by non-dominated sorting.
    Front rank 1 represents the true Pareto frontier P*.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int = Field(..., ge=1, description="Front rank (1 = Pareto optimal non-dominated set).")
    strategies: list[CandidateStrategy] = Field(
        default_factory=list,
        description="Strategies belonging to this non-dominated front."
    )


class ParetoComparisonResult(BaseModel):
    """
    Canonical result of multi-objective Pareto trade-off analysis.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_id: str = Field(..., description="Unique comparison run identifier.")
    problem_id: str = Field(..., description="Referenced decision problem identifier.")
    pareto_frontier: list[CandidateStrategy] = Field(
        ...,
        description="Verified mathematically non-dominated feasible strategies (Front 1)."
    )
    dominated_strategies: list[CandidateStrategy] = Field(
        default_factory=list,
        description="Feasible strategies strictly dominated by at least one other feasible strategy."
    )
    infeasible_strategies: list[CandidateStrategy] = Field(
        default_factory=list,
        description="Strategies disqualified due to proven hard physical constraint violations."
    )
    unknown_strategies: list[CandidateStrategy] = Field(
        default_factory=list,
        description="Strategies quarantined due to unverified feasibility or missing/non-finite objectives."
    )
    all_fronts: list[ParetoFront] = Field(
        default_factory=list,
        description="Complete non-dominated sorting fronts for all feasible candidates."
    )
    incomparable_pairs_count: int = Field(
        default=0,
        ge=0,
        description="Count of pairwise strategy evaluations that resulted in a trade-off."
    )
    equal_pairs_count: int = Field(
        default=0,
        ge=0,
        description="Count of pairwise strategy evaluations that were numerically identical."
    )


class CounterfactualBaseline(BaseModel):
    """
    Explicit, typed reference comparator representing the counterfactual default trajectory
    (e.g., status-quo or autonomous trip default without operator intervention).
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    baseline_id: str = Field(..., description="Unique comparator baseline identifier.")
    name: str = Field(..., min_length=1, description="Descriptive comparator baseline name.")
    baseline_type: BaselineType = Field(..., description="Classification category of the baseline comparator.")
    feasibility_status: FeasibilityStatus = Field(
        default=FeasibilityStatus.FEASIBLE,
        description="Feasibility of the baseline scenario itself."
    )
    objectives: dict[str, float] = Field(
        ...,
        description="Simulated or estimated objective values under the counterfactual baseline."
    )
    objective_units: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of objective_id to physical unit."
    )
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Cryptographic digests of baseline model assumptions and initial telemetry."
    )
    epistemic_status: EpistemicCategory = Field(
        default=EpistemicCategory.SIMULATED_COUNTERFACTUAL,
        description="Epistemic nature of baseline outcomes (not physically observed)."
    )
    description: str | None = Field(
        default=None,
        description="Operational context of what this counterfactual trajectory simulates."
    )

    @field_validator("baseline_id")
    @classmethod
    def validate_baseline_id(cls, v: str) -> str:
        s = v.strip()
        if not s or not IDENTIFIER_REGEX.match(s):
            raise ValueError(f"baseline_id must match pattern '^[A-Za-z0-9_.-]+$', got '{v}'")
        return s

    @field_validator("objectives")
    @classmethod
    def validate_finite_objectives(cls, v: dict[str, float]) -> dict[str, float]:
        validated = {}
        for k, val in v.items():
            k_clean = k.strip()
            if not k_clean:
                raise ValueError("Objective ID in baseline cannot be blank")
            validated[k_clean] = validate_finite_number(val, f"baseline.objectives['{k}']")
        return validated


class ObjectiveDelta(BaseModel):
    """
    Objective-wise relative difference between candidate strategy and counterfactual baseline.
    Delta sign convention: Delta f_k(x) = f_k(x) - f_k(x0).
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    objective_id: str = Field(..., description="Evaluated objective identifier.")
    candidate_value: float | None = Field(..., description="Strategy evaluated metric, or None if unknown.")
    baseline_value: float | None = Field(..., description="Baseline comparator metric, or None if unknown.")
    raw_delta: float | None = Field(
        ...,
        description="Natural arithmetic difference: candidate_value - baseline_value (None if unknown)."
    )
    unit: str = Field(..., description="Physical unit of measurement.")
    direction: ObjectiveDirection = Field(..., description="Optimization direction.")
    impact: DeltaImpact = Field(
        ...,
        description="Directional impact assessment (IMPROVEMENT, DEGRADATION, EQUAL, UNKNOWN)."
    )
    explanation: str = Field(..., description="Clear explanation of the relative performance.")


class BaselineComparisonResult(BaseModel):
    """
    Complete counterfactual comparison between a candidate strategy and the reference baseline.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_strategy_id: str = Field(..., description="Candidate strategy identifier.")
    baseline_id: str = Field(..., description="Counterfactual baseline comparator identifier.")
    deltas: dict[str, ObjectiveDelta] = Field(
        ...,
        description="Objective-by-objective deltas with sign conventions and physical units."
    )
    net_improvements_count: int = Field(..., ge=0, description="Count of objectives showing strictly improved performance.")
    net_degradations_count: int = Field(..., ge=0, description="Count of objectives showing degraded performance.")
    equal_count: int = Field(..., ge=0, description="Count of objectives identical to baseline.")
    unknown_count: int = Field(..., ge=0, description="Count of objectives where delta cannot be proven.")
    evidence_refs: list[str] = Field(
        default_factory=list,
        description="Chained cryptographic evidence references from candidate and baseline."
    )
    epistemic_status: EpistemicCategory = Field(
        default=EpistemicCategory.SIMULATED_COUNTERFACTUAL,
        description="Epistemic status explicitly flagging simulated/predicted nature."
    )
    summary_explanation: str = Field(..., description="Audit-ready natural language comparison summary.")


class RegretMetrics(BaseModel):
    """
    Mathematical regret quantification against an explicit benchmark set.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    strategy_id: str = Field(..., description="Strategy identifier.")
    regret_type: RegretType = Field(
        ...,
        description="Epistemic classification: DECISION_TIME_ESTIMATE or EX_POST_OBSERVED."
    )
    objective_regrets: dict[str, float] = Field(
        ...,
        description="Raw regret in native physical units: f_k(x) - Ideal_k (min) or Ideal_k - f_k(x) (max) >= 0."
    )
    normalized_regrets: dict[str, float] = Field(
        ...,
        description="Normalized dimensionless regret in [0.0, 1.0] scaled by benchmark range."
    )
    max_regret: float = Field(
        ...,
        ge=0.0,
        description="Maximum normalized Chebyshev regret across all evaluated objectives: max_k NormRegret_k."
    )
    benchmark_strategy_ids: list[str] = Field(
        ...,
        description="Identifiers of strategies comprising the reference benchmark set."
    )
    explanation: str = Field(..., description="Machine-readable justification of regret metrics.")


class UncertaintyParameter(BaseModel):
    """
    Formal representation of an uncertain operational parameter (e.g. wind speed, line rating).
    Strictly distinguishes aleatoric stochastic distributions from epistemic bounded intervals.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    parameter_name: str = Field(..., description="Unique parameter identifier.")
    uncertainty_type: UncertaintyType = Field(..., description="Aleatory stochastic vs epistemic bounded.")
    distribution_type: DistributionType = Field(..., description="Distribution or interval specification.")
    parameters: dict[str, Any] = Field(..., description="Distribution/interval bounds dictionary.")
    unit: str | None = Field(default=None, description="Physical unit of parameter measurement.")
    is_empirically_calibrated: bool = Field(
        default=False,
        description="Flag certifying whether distribution is anchored to verified historical empirical telemetry."
    )
    provenance_digest: str | None = Field(
        default=None,
        description="Cryptographic SHA-256 digest of calibration dataset."
    )
    description: str | None = Field(default=None, description="Operational context of parameter uncertainty.")

    @field_validator("parameter_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        s = v.strip()
        if not s or not IDENTIFIER_REGEX.match(s):
            raise ValueError(f"parameter_name must match pattern '^[A-Za-z0-9_.-]+$', got '{v}'")
        return s

    @field_validator("provenance_digest")
    @classmethod
    def validate_digest(cls, v: str | None) -> str | None:
        if v is not None:
            s = v.strip()
            if not SHA256_DIGEST_REGEX.match(s):
                raise ValueError(f"provenance_digest must match lowercase SHA-256 pattern, got '{v}'")
            return s
        return v


class RiskMetrics(BaseModel):
    """
    Statistical risk and tail-loss evaluation for an objective under stochastic uncertainty.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    objective_id: str = Field(..., description="Target objective identifier.")
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0, description="Risk confidence level alpha (e.g. 0.95).")
    var: float = Field(..., description="Value at Risk (VaR_alpha) in native physical units.")
    cvar: float = Field(..., description="Conditional Value at Risk / Expected Shortfall (CVaR_alpha) in physical units.")
    unit: str = Field(..., description="Physical unit of measurement.")
    sample_size: int = Field(..., ge=2, description="Number of evaluated Monte Carlo/quasi-random realizations.")
    mean: float = Field(..., description="Sample empirical mean.")
    std_dev: float = Field(..., ge=0.0, description="Sample standard deviation.")
    standard_error: float = Field(..., ge=0.0, description="Standard error of the mean (SEM = sigma / sqrt(N)).")
    sample_converged: bool = Field(..., description="True if SEM / mean <= 0.05 (for mean > 0).")
    confidence_interval_95: tuple[float, float] = Field(..., description="Empirical 95% quantile interval [q_0.025, q_0.975].")
    robustness_score: float = Field(..., ge=0.0, le=1.0, description="Fraction of samples satisfying statutory threshold or 1 - MaxRegret.")
    loss_convention: LossConvention = Field(..., description="Loss convention mapping: DIRECT_OBJECTIVE or NEGATIVE_OBJECTIVE.")
    is_empirically_calibrated: bool = Field(default=False, description="Explicit flag: True only if validated by physical calibration data.")
    explanation: str = Field(..., description="Machine-readable narrative explaining risk and tail loss.")

    @model_validator(mode="after")
    def verify_risk_invariants(self) -> RiskMetrics:
        """
        Verify mathematical risk invariants:
        CVaR_alpha must be >= VaR_alpha under standard loss conventions.
        """
        # For loss distributions, expected shortfall in the worst tail is at least as large as the quantile threshold
        if self.cvar < self.var - 1e-9:
            raise ValueError(
                f"Mathematical risk invariant violated: CVaR ({self.cvar:.6g}) cannot be strictly less "
                f"than VaR ({self.var:.6g}) for objective '{self.objective_id}'."
            )
        return self


class SensitivityMetric(BaseModel):
    """
    First-order parameter sensitivity and elasticity index.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    objective_id: str = Field(..., description="Target objective identifier.")
    parameter_name: str = Field(..., description="Perturbed parameter identifier.")
    raw_sensitivity: float = Field(..., description="First-order gradient dObjective / dParam.")
    normalized_elasticity: float | None = Field(
        default=None,
        description="Dimensionless elasticity: (dObj / Obj_0) / (dParam / Param_0)."
    )
    unit: str = Field(..., description="Sensitivity unit ratio [unit(Obj) / unit(Param)].")
    explanation: str = Field(..., description="Machine-readable narrative explaining sensitivity.")


class TradeoffMatrixEntry(BaseModel):
    """
    Evaluated multi-objective strategy metrics entry for strategy comparison trade-off matrix.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario_id: str = Field(..., description="Candidate strategy UUID.")
    strategy_name: str = Field(..., min_length=1, description="Human-readable operational strategy name.")
    objective_values: dict[str, float] = Field(..., description="Evaluated objective metrics.")
    delta_vs_baseline: dict[str, float] = Field(..., description="Relative deltas f_k(x) - f_k(x0).")
    max_regret: float = Field(..., ge=0.0, description="Normalized Chebyshev maximum regret.")
    robustness_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Empirical constraint satisfaction probability under uncertainty."
    )

    @field_validator("scenario_id")
    @classmethod
    def validate_scenario_uuid(cls, v: str) -> str:
        return validate_uuid_string(v, "scenario_id")

    @field_validator("objective_values", "delta_vs_baseline")
    @classmethod
    def validate_finite_metrics(cls, v: dict[str, float], info: Any) -> dict[str, float]:
        validated = {}
        for k, val in v.items():
            k_clean = k.strip()
            if not k_clean:
                raise ValueError(f"Objective ID in {info.field_name} cannot be blank")
            validated[k_clean] = validate_finite_number(val, f"{info.field_name}['{k}']")
        return validated


class EvidenceExplanation(BaseModel):
    """
    Evidence-grounded rationale synthesis for multi-objective strategy comparison.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_recommendation_scenario_id: str = Field(..., description="Recommended strategy UUID.")
    justification_summary: str = Field(..., min_length=1, description="Concise selection justification.")
    tradeoff_narrative: str = Field(..., min_length=1, description="Detailed trade-off narrative.")
    key_risks: list[str] = Field(default_factory=list, description="Enumeration of key operational risks.")

    @field_validator("primary_recommendation_scenario_id")
    @classmethod
    def validate_rec_uuid(cls, v: str) -> str:
        return validate_uuid_string(v, "primary_recommendation_scenario_id")


class StrategyComparison(BaseModel):
    """
    Canonical StrategyComparison contract representation conforming to strategy_comparison.json.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_id: str = Field(..., description="Unique comparison evaluation UUID.")
    problem_id: str = Field(..., description="Associated DecisionProblem UUID.")
    schema_version: str = Field(default="v1.0.0", description="Semantic contract schema version.")
    generated_at: str = Field(..., description="ISO 8601 UTC evaluation generation timestamp.")
    baseline_scenario_id: str = Field(..., description="Counterfactual baseline comparator UUID.")
    pareto_frontier_scenario_ids: list[str] = Field(
        ...,
        description="UUIDs of strategies verified non-dominated across all defined objectives."
    )
    dominated_scenario_ids: list[str] = Field(
        default_factory=list,
        description="UUIDs of feasible strategies strictly dominated by at least one other strategy."
    )
    infeasible_scenario_ids: list[str] = Field(
        default_factory=list,
        description="UUIDs of candidate strategies violating one or more hard physical constraints."
    )
    unknown_scenario_ids: list[str] = Field(
        default_factory=list,
        description="UUIDs of candidate strategies quarantined due to solver timeout or unverified feasibility."
    )
    tradeoff_matrix: list[TradeoffMatrixEntry] = Field(
        ...,
        description="Objective and delta performance metrics across evaluated candidate scenarios."
    )
    evidence_explanation: EvidenceExplanation = Field(
        ...,
        description="Evidence-grounded narrative justification and operational risk summary."
    )

    @field_validator("comparison_id", "problem_id", "baseline_scenario_id")
    @classmethod
    def validate_uuids(cls, v: str, info: Any) -> str:
        return validate_uuid_string(v, info.field_name)

    @field_validator(
        "pareto_frontier_scenario_ids",
        "dominated_scenario_ids",
        "infeasible_scenario_ids",
        "unknown_scenario_ids",
    )
    @classmethod
    def validate_uuid_lists(cls, v: list[str], info: Any) -> list[str]:
        return [validate_uuid_string(uid, f"{info.field_name} element") for uid in v]

    @field_validator("schema_version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        s = v.strip()
        if not SCHEMA_VERSION_REGEX.match(s):
            raise ValueError(f"schema_version must match pattern '^v[0-9]+\\.[0-9]+\\.[0-9]+$', got '{v}'")
        return s

    @field_validator("generated_at")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        s = v.strip()
        if not ISO_DATETIME_REGEX.match(s):
            raise ValueError(f"generated_at must be valid ISO 8601 UTC timestamp, got '{v}'")
        return s

    def to_canonical_dict(self) -> dict[str, Any]:
        """Convert to canonical dictionary excluding null optional fields for JSON Schema Draft-07 conformance."""
        return self.model_dump(mode="json", exclude_none=True)


class HumanReviewLog(BaseModel):
    """
    Formal human operator technical review log.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    operator_id: str = Field(..., min_length=1, description="Authenticated dispatcher/reviewer user ID.")
    operator_role: str = Field(..., min_length=1, description="Operational role (e.g. Senior Grid Controller).")
    review_timestamp: str = Field(..., description="ISO 8601 review timestamp.")
    rationale_for_selection: str = Field(..., min_length=1, description="Human operational justification.")
    overridden_recommendation: bool | None = Field(
        default=None,
        description="True if operator selected a candidate other than the primary recommendation."
    )
    override_justification: str | None = Field(
        default=None,
        description="Required explanation if recommendation was overridden."
    )

    @field_validator("review_timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        s = v.strip()
        if not ISO_DATETIME_REGEX.match(s):
            raise ValueError(f"review_timestamp must be valid ISO 8601 UTC timestamp, got '{v}'")
        return s


class SignOffEntry(BaseModel):
    """
    Digital sign-off entry for dual-control decision authorization.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(..., min_length=1, description="Signer user identifier.")
    user_name: str = Field(..., min_length=1, description="Signer full legal name.")
    role: str = Field(..., min_length=1, description="Operational or executive role.")
    timestamp: str = Field(..., description="ISO 8601 signature timestamp.")
    digital_signature: str = Field(..., min_length=1, description="Cryptographic digital signature string.")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        s = v.strip()
        if not ISO_DATETIME_REGEX.match(s):
            raise ValueError(f"timestamp must be valid ISO 8601 UTC timestamp, got '{v}'")
        return s


class DualControlSignatures(BaseModel):
    """
    Four-Eyes dual-control authorization signatures container.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_sign_off: SignOffEntry = Field(..., description="Primary operator/controller signature.")
    secondary_sign_off: SignOffEntry | None = Field(
        default=None,
        description="Mandatory secondary signature for high-impact/emergency actions."
    )


class AuditTrail(BaseModel):
    """
    Append-only cryptographic SHA-256 provenance hash chain record.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    record_hash: str = Field(..., description="Immutable SHA-256 digest of this decision record.")
    previous_record_hash: str = Field(..., description="SHA-256 digest of preceding decision record in chain.")
    signature_algorithm: SignatureAlgorithm = Field(
        ...,
        description="Cryptographic signature algorithm: RSA-PSS-SHA256, ECDSA-P256-SHA256, ED25519."
    )

    @field_validator("record_hash", "previous_record_hash")
    @classmethod
    def validate_hashes(cls, v: str, info: Any) -> str:
        s = v.strip()
        if not SHA256_DIGEST_REGEX.match(s):
            raise ValueError(f"'{info.field_name}' must match pattern '^sha256:[a-f0-9]{{64}}$', got '{v}'")
        return s


class DecisionRecord(BaseModel):
    """
    Canonical DecisionRecord contract representation conforming to decision_record.json.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str = Field(..., description="Unique decision record UUID.")
    problem_id: str = Field(..., description="Associated DecisionProblem UUID.")
    comparison_id: str = Field(..., description="Associated StrategyComparison UUID.")
    schema_version: str = Field(default="v1.0.0", description="Semantic contract schema version.")
    created_at: str = Field(..., description="ISO 8601 UTC record creation timestamp.")
    selected_scenario_id: str = Field(..., description="Authorized operational strategy scenario UUID.")
    authorization_state: AuthorizationState = Field(..., description="Lifecycle authorization state.")
    human_review_log: HumanReviewLog = Field(..., description="Formal human review and selection rationale.")
    dual_control_signatures: DualControlSignatures = Field(..., description="Dual-control authorization signatures.")
    operational_dispatch_status: OperationalDispatchStatus = Field(
        default=OperationalDispatchStatus.NOT_DISPATCHED,
        description="Operational dispatch status to SCADA/EMS gateway."
    )
    audit_trail: AuditTrail = Field(..., description="Cryptographic hash-chained provenance trail.")

    @field_validator("record_id", "problem_id", "comparison_id", "selected_scenario_id")
    @classmethod
    def validate_uuids(cls, v: str, info: Any) -> str:
        return validate_uuid_string(v, info.field_name)

    @field_validator("schema_version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        s = v.strip()
        if not SCHEMA_VERSION_REGEX.match(s):
            raise ValueError(f"schema_version must match pattern '^v[0-9]+\\.[0-9]+\\.[0-9]+$', got '{v}'")
        return s

    @field_validator("created_at")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        s = v.strip()
        if not ISO_DATETIME_REGEX.match(s):
            raise ValueError(f"created_at must be valid ISO 8601 UTC timestamp, got '{v}'")
        return s

    def to_canonical_dict(self) -> dict[str, Any]:
        """Convert to canonical dictionary excluding null optional fields for JSON Schema Draft-07 conformance."""
        return self.model_dump(mode="json", exclude_none=True)
