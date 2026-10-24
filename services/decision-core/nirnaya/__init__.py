"""
NIRNAYA Decision Core.

Deterministic, reproducible AI decision-intelligence foundation.
"""

__version__ = "0.1.0"

from nirnaya.counterfactual.comparison import compute_baseline_comparison
from nirnaya.counterfactual.regret import compute_regret_metrics
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
from nirnaya.domain.models import (
    AuditTrail,
    BaselineComparisonResult,
    CandidateStrategy,
    ConstraintEvaluation,
    CounterfactualBaseline,
    DecisionProblem,
    DecisionRecord,
    DecisionVariable,
    DualControlSignatures,
    EvidenceExplanation,
    EvidenceReference,
    HardConstraint,
    HardConstraintSummary,
    HumanReviewLog,
    ObjectiveDefinition,
    ObjectiveDelta,
    ParetoComparisonResult,
    ParetoFront,
    RegretMetrics,
    RiskMetrics,
    SensitivityMetric,
    SignOffEntry,
    StrategyComparison,
    TradeoffMatrixEntry,
    UncertaintyParameter,
)
from nirnaya.evaluator.hard_constraint_evaluator import (
    evaluate_hard_constraint,
    evaluate_hard_constraints,
)
from nirnaya.mcda.aspiration import compute_chebyshev_aspiration_distance
from nirnaya.mcda.filtering import filter_epsilon_constraints
from nirnaya.mcda.lexicographic import sort_lexicographic_priority
from nirnaya.pareto.dominance import check_pareto_dominance
from nirnaya.pareto.sorting import compute_pareto_comparison
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
    canonical_json_dumps,
    compute_record_hash,
    verify_decision_record_chain,
)
from nirnaya.uncertainty.propagation import (
    propagate_counterfactual_uncertainty,
    propagate_scenario_uncertainty,
)
from nirnaya.uncertainty.risk import compute_risk_metrics
from nirnaya.uncertainty.sensitivity import compute_sensitivity

__all__ = [
    "__version__",
    "AuditTrail",
    "AuthorizationState",
    "BaselineComparisonResult",
    "BaselineType",
    "CandidateStrategy",
    "ConstraintCategory",
    "ConstraintEvaluation",
    "ConstraintOperator",
    "CounterfactualBaseline",
    "DecisionProblem",
    "DecisionRecord",
    "DecisionVariable",
    "DeltaImpact",
    "DistributionType",
    "DominanceRelation",
    "DualControlSignatures",
    "EpistemicCategory",
    "EvidenceExplanation",
    "EvidenceReference",
    "FeasibilityStatus",
    "GENESIS_PREVIOUS_HASH",
    "HardConstraint",
    "HardConstraintSummary",
    "HumanReviewLog",
    "LossConvention",
    "ObjectiveDefinition",
    "ObjectiveDelta",
    "ObjectiveDirection",
    "OperationalDispatchStatus",
    "ParetoComparisonResult",
    "ParetoFront",
    "RegretMetrics",
    "RegretType",
    "RiskMetrics",
    "SensitivityMetric",
    "SignOffEntry",
    "SignatureAlgorithm",
    "StrategyComparison",
    "TelemetryQuality",
    "TradeoffMatrixEntry",
    "UncertaintyParameter",
    "UncertaintyType",
    "assemble_decision_record",
    "assemble_strategy_comparison",
    "canonical_json_dumps",
    "check_pareto_dominance",
    "compute_baseline_comparison",
    "compute_chebyshev_aspiration_distance",
    "compute_pareto_comparison",
    "compute_record_hash",
    "compute_regret_metrics",
    "compute_risk_metrics",
    "compute_sensitivity",
    "evaluate_hard_constraint",
    "evaluate_hard_constraints",
    "filter_epsilon_constraints",
    "is_high_impact_decision",
    "propagate_counterfactual_uncertainty",
    "propagate_scenario_uncertainty",
    "sort_lexicographic_priority",
    "validate_dual_control_signatures",
    "verify_decision_record_chain",
]
