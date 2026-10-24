"""
Domain enumerations for NIRNAYA decision models.
"""

from enum import Enum


class FeasibilityStatus(str, Enum):
    """
    Canonical tri-state feasibility outcome.

    Invariants:
    - FEASIBLE: Strategy provably satisfies all physical and operational limits within verified tolerance.
    - INFEASIBLE: Strategy provably violates at least one constraint beyond tolerance.
    - UNKNOWN: Numerical validity cannot be proven (missing, stale, invalid evidence or non-convergence).
      FAIL-CLOSED: An UNKNOWN outcome must NEVER silently degrade into FEASIBLE.
    """
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"


class ConstraintOperator(str, Enum):
    """
    Mathematical comparison operator for hard constraints.
    """
    LEQ = "<="
    GEQ = ">="
    EQ = "=="
    IN_RANGE = "IN_RANGE"


class ConstraintCategory(str, Enum):
    """
    Standard categorization of power grid and operational physical constraints.
    """
    THERMAL_CURRENT_LIMIT = "THERMAL_CURRENT_LIMIT"
    VOLTAGE_STABILITY_BAND = "VOLTAGE_STABILITY_BAND"
    FREQUENCY_RESERVE_LIMIT = "FREQUENCY_RESERVE_LIMIT"
    GENERATOR_RAMP_LIMIT = "GENERATOR_RAMP_LIMIT"
    ISLAND_RESOURCE_ADEQUACY = "ISLAND_RESOURCE_ADEQUACY"


class TelemetryQuality(str, Enum):
    """
    Confidence classification of ingested evidence telemetry.
    """
    VALIDATED = "VALIDATED"
    DEGRADED = "DEGRADED"
    ESTIMATED = "ESTIMATED"
    UNRELIABLE = "UNRELIABLE"


class ObjectiveDirection(str, Enum):
    """
    Direction of optimization for an operational objective function.
    """
    MINIMIZE = "MINIMIZE"
    MAXIMIZE = "MAXIMIZE"


class DominanceRelation(str, Enum):
    """
    Pareto dominance relationship between two candidate objective vectors:
    - DOMINATES: Vector A strictly dominates Vector B (A < B).
    - DOMINATED: Vector B strictly dominates Vector A (B < A).
    - EQUAL: Vector A and Vector B are numerically identical across all objectives (A == B).
    - INCOMPARABLE: Neither dominates the other; trade-off exists (A is better on some, B on others).
    """
    DOMINATES = "DOMINATES"
    DOMINATED = "DOMINATED"
    EQUAL = "EQUAL"
    INCOMPARABLE = "INCOMPARABLE"


class BaselineType(str, Enum):
    """
    Classification of the reference comparator baseline.
    """
    STATUS_QUO = "STATUS_QUO"
    AUTONOMOUS_TRIP_DEFAULT = "AUTONOMOUS_TRIP_DEFAULT"
    HISTORICAL_BENCHMARK = "HISTORICAL_BENCHMARK"
    OPERATOR_PROPOSED = "OPERATOR_PROPOSED"


class DeltaImpact(str, Enum):
    """
    Directional assessment of relative performance against the counterfactual baseline:
    - IMPROVEMENT: Strategy outcome is strictly better than baseline for this objective.
    - DEGRADATION: Strategy outcome is strictly worse than baseline for this objective.
    - EQUAL: Outcome is numerically identical to baseline.
    - UNKNOWN: Delta cannot be mathematically established (missing or non-finite data).
    """
    IMPROVEMENT = "IMPROVEMENT"
    DEGRADATION = "DEGRADATION"
    EQUAL = "EQUAL"
    UNKNOWN = "UNKNOWN"


class RegretType(str, Enum):
    """
    Temporal and epistemic nature of regret quantification:
    - DECISION_TIME_ESTIMATE: Ex-ante model-simulated opportunity loss across the candidate set.
    - EX_POST_OBSERVED: Ex-post retrospectively measured opportunity loss after actual realization.
    """
    DECISION_TIME_ESTIMATE = "DECISION_TIME_ESTIMATE"
    EX_POST_OBSERVED = "EX_POST_OBSERVED"


class EpistemicCategory(str, Enum):
    """
    Epistemic boundary of the comparison data to prevent false causality claims:
    - SIMULATED_COUNTERFACTUAL: Predicted trajectory under model assumptions (not physically observed).
    - MODEL_ESTIMATE: Estimated statistical expectation or surrogate output.
    - MEASURED_OBSERVATION: Telemetry sampled directly from physical grid instrumentation.
    """
    SIMULATED_COUNTERFACTUAL = "SIMULATED_COUNTERFACTUAL"
    MODEL_ESTIMATE = "MODEL_ESTIMATE"
    MEASURED_OBSERVATION = "MEASURED_OBSERVATION"


class UncertaintyType(str, Enum):
    """
    Fundamental categorization of operational uncertainty:
    - ALEATORY_STOCHASTIC: Inherent random variability modeled by known probability distributions.
    - EPISTEMIC_BOUNDED: Lack of knowledge/data modeled by bounded intervals or sets without probability claims.
    """
    ALEATORY_STOCHASTIC = "ALEATORY_STOCHASTIC"
    EPISTEMIC_BOUNDED = "EPISTEMIC_BOUNDED"


class DistributionType(str, Enum):
    """
    Mathematical form of the uncertainty specification.
    """
    UNIFORM_INTERVAL = "UNIFORM_INTERVAL"
    NORMAL_GAUSSIAN = "NORMAL_GAUSSIAN"
    TRUNCATED_NORMAL = "TRUNCATED_NORMAL"
    DISCRETE_SCENARIO = "DISCRETE_SCENARIO"
    BOUNDED_INTERVAL_SET = "BOUNDED_INTERVAL_SET"


class LossConvention(str, Enum):
    """
    Directional mapping of objective values to risk losses:
    - DIRECT_OBJECTIVE: For minimization objectives (higher value = higher loss).
    - NEGATIVE_OBJECTIVE: For maximization objectives (lower value = higher loss, loss = -f_k).
    """
    DIRECT_OBJECTIVE = "DIRECT_OBJECTIVE"
    NEGATIVE_OBJECTIVE = "NEGATIVE_OBJECTIVE"


class AuthorizationState(str, Enum):
    """
    Lifecycle authorization state of an operational decision record:
    PROPOSED, UNDER_REVIEW, AUTHORIZED, REJECTED, REVOKED, SUPERSEDED.
    """
    PROPOSED = "PROPOSED"
    UNDER_REVIEW = "UNDER_REVIEW"
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"
    SUPERSEDED = "SUPERSEDED"


class OperationalDispatchStatus(str, Enum):
    """
    Execution handoff status to utility dispatchers or SCADA gateways:
    NOT_DISPATCHED, PENDING_OPERATOR_MANUAL_ENTRY, EXPORTED_TO_OPERATIONS, ACKNOWLEDGED_BY_SCADA.
    """
    NOT_DISPATCHED = "NOT_DISPATCHED"
    PENDING_OPERATOR_MANUAL_ENTRY = "PENDING_OPERATOR_MANUAL_ENTRY"
    EXPORTED_TO_OPERATIONS = "EXPORTED_TO_OPERATIONS"
    ACKNOWLEDGED_BY_SCADA = "ACKNOWLEDGED_BY_SCADA"


class SignatureAlgorithm(str, Enum):
    """
    Cryptographic digital signature algorithm for dual-control authorization:
    RSA-PSS-SHA256, ECDSA-P256-SHA256, ED25519.
    """
    RSA_PSS_SHA256 = "RSA-PSS-SHA256"
    ECDSA_P256_SHA256 = "ECDSA-P256-SHA256"
    ED25519 = "ED25519"
