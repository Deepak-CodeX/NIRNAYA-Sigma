"""
Unit tests for NIRNAYA counterfactual baseline comparison and regret quantification.

Covers:
- Typed CounterfactualBaseline comparator representation.
- Relative delta calculation with signed conventions: Delta f_k(x) = f_k(x) - f_k(x0).
- Directional impact: IMPROVEMENT, DEGRADATION, EQUAL, UNKNOWN.
- Physical units preservation and unit mismatch detection.
- Missing and non-finite value handling (fail-closed as UNKNOWN).
- Chained evidence provenance and epistemic boundary tagging (SIMULATED_COUNTERFACTUAL).
- Mathematical regret quantification against benchmark set (raw & normalized Chebyshev regret).
- Regret types: DECISION_TIME_ESTIMATE vs EX_POST_OBSERVED.
- Deterministic repeated execution.
"""

from __future__ import annotations

import math
try:
    import pytest
except ImportError:
    from tests.compat import pytest

from nirnaya.counterfactual.comparison import compute_baseline_comparison
from nirnaya.counterfactual.regret import compute_regret_metrics
from nirnaya.domain.enums import (
    BaselineType,
    DeltaImpact,
    EpistemicCategory,
    FeasibilityStatus,
    ObjectiveDirection,
    RegretType,
)
from nirnaya.domain.models import (
    CandidateStrategy,
    CounterfactualBaseline,
    ObjectiveDefinition,
)

DIGEST_BASE = "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
DIGEST_CAND = "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


@pytest.fixture
def power_grid_objectives() -> list[ObjectiveDefinition]:
    return [
        ObjectiveDefinition(
            objective_id="OBJ-EUE",
            name="Expected Unserved Energy",
            direction=ObjectiveDirection.MINIMIZE,
            unit="MWh",
        ),
        ObjectiveDefinition(
            objective_id="OBJ-COST",
            name="Operational Redispatch Cost",
            direction=ObjectiveDirection.MINIMIZE,
            unit="USD",
        ),
        ObjectiveDefinition(
            objective_id="OBJ-RESERVE",
            name="Available Spinning Reserve",
            direction=ObjectiveDirection.MAXIMIZE,
            unit="MW",
        ),
    ]


@pytest.fixture
def status_quo_baseline() -> CounterfactualBaseline:
    return CounterfactualBaseline(
        baseline_id="BASE-STATUS-QUO",
        name="Status Quo Do-Nothing Baseline",
        baseline_type=BaselineType.STATUS_QUO,
        feasibility_status=FeasibilityStatus.FEASIBLE,
        objectives={
            "OBJ-EUE": 100.0,
            "OBJ-COST": 0.0,
            "OBJ-RESERVE": 50.0,
        },
        objective_units={
            "OBJ-EUE": "MWh",
            "OBJ-COST": "USD",
            "OBJ-RESERVE": "MW",
        },
        evidence_refs=[DIGEST_BASE],
        epistemic_status=EpistemicCategory.SIMULATED_COUNTERFACTUAL,
        description="Autonomous trip default trajectory without coordinated intervention.",
    )


class TestBaselineComparison:
    """Tests for relative delta calculation and impact classification against counterfactual baseline."""

    def test_improvement_degradation_and_equal_outcomes(
        self, power_grid_objectives: list[ObjectiveDefinition], status_quo_baseline: CounterfactualBaseline
    ) -> None:
        # Candidate reduces EUE (improvement), incurs cost (degradation), keeps reserve equal
        cand = CandidateStrategy(
            strategy_id="STRAT-REDISPATCH-01",
            strategy_name="Generator Redispatch Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={
                "OBJ-EUE": 14.2,     # 14.2 - 100.0 = -85.8 (Improvement)
                "OBJ-COST": 4850.0,  # 4850.0 - 0.0 = +4850.0 (Degradation)
                "OBJ-RESERVE": 50.0, # 50.0 - 50.0 = 0.0 (Equal)
            },
            objective_units={
                "OBJ-EUE": "MWh",
                "OBJ-COST": "USD",
                "OBJ-RESERVE": "MW",
            },
            metadata={"evidence_refs": [DIGEST_CAND]},
        )

        res = compute_baseline_comparison(cand, status_quo_baseline, power_grid_objectives)

        assert res.candidate_strategy_id == "STRAT-REDISPATCH-01"
        assert res.baseline_id == "BASE-STATUS-QUO"
        assert res.epistemic_status == EpistemicCategory.SIMULATED_COUNTERFACTUAL
        assert res.net_improvements_count == 1
        assert res.net_degradations_count == 1
        assert res.equal_count == 1
        assert res.unknown_count == 0

        # OBJ-EUE (Minimization): Delta = -85.8 MWh -> IMPROVEMENT
        delta_eue = res.deltas["OBJ-EUE"]
        assert delta_eue.candidate_value == 14.2
        assert delta_eue.baseline_value == 100.0
        assert pytest.approx(delta_eue.raw_delta, 1e-6) == -85.8
        assert delta_eue.unit == "MWh"
        assert delta_eue.impact == DeltaImpact.IMPROVEMENT

        # OBJ-COST (Minimization): Delta = +4850.0 USD -> DEGRADATION
        delta_cost = res.deltas["OBJ-COST"]
        assert delta_cost.candidate_value == 4850.0
        assert delta_cost.baseline_value == 0.0
        assert pytest.approx(delta_cost.raw_delta, 1e-6) == 4850.0
        assert delta_cost.unit == "USD"
        assert delta_cost.impact == DeltaImpact.DEGRADATION

        # OBJ-RESERVE (Maximization): Delta = 0.0 MW -> EQUAL
        delta_res = res.deltas["OBJ-RESERVE"]
        assert delta_res.raw_delta == 0.0
        assert delta_res.impact == DeltaImpact.EQUAL

        # Evidence chaining: candidate + baseline digests preserved
        assert DIGEST_CAND in res.evidence_refs
        assert DIGEST_BASE in res.evidence_refs

    def test_maximization_improvement_and_degradation(
        self, power_grid_objectives: list[ObjectiveDefinition], status_quo_baseline: CounterfactualBaseline
    ) -> None:
        # Candidate increases reserve from 50.0 to 75.0 MW -> Delta = +25.0 MW (Improvement for MAXIMIZE)
        cand_boost = CandidateStrategy(
            strategy_id="STRAT-RESERVE-BOOST",
            strategy_name="Reserve Boost Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={
                "OBJ-EUE": 100.0,
                "OBJ-COST": 0.0,
                "OBJ-RESERVE": 75.0,  # 75 - 50 = +25 (Improvement for MAXIMIZE)
            },
        )
        res_boost = compute_baseline_comparison(cand_boost, status_quo_baseline, power_grid_objectives)
        assert res_boost.deltas["OBJ-RESERVE"].raw_delta == 25.0
        assert res_boost.deltas["OBJ-RESERVE"].impact == DeltaImpact.IMPROVEMENT

        # Candidate decreases reserve from 50.0 to 30.0 MW -> Delta = -20.0 MW (Degradation for MAXIMIZE)
        cand_drop = CandidateStrategy(
            strategy_id="STRAT-RESERVE-DROP",
            strategy_name="Reserve Drop Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={
                "OBJ-EUE": 100.0,
                "OBJ-COST": 0.0,
                "OBJ-RESERVE": 30.0,  # 30 - 50 = -20 (Degradation for MAXIMIZE)
            },
        )
        res_drop = compute_baseline_comparison(cand_drop, status_quo_baseline, power_grid_objectives)
        assert res_drop.deltas["OBJ-RESERVE"].raw_delta == -20.0
        assert res_drop.deltas["OBJ-RESERVE"].impact == DeltaImpact.DEGRADATION

    def test_missing_objective_in_candidate_fails_closed_to_unknown(
        self, power_grid_objectives: list[ObjectiveDefinition], status_quo_baseline: CounterfactualBaseline
    ) -> None:
        # Candidate is missing OBJ-COST
        cand_missing = CandidateStrategy(
            strategy_id="STRAT-INCOMPLETE",
            strategy_name="Incomplete Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ-EUE": 20.0, "OBJ-RESERVE": 60.0},
        )
        res = compute_baseline_comparison(cand_missing, status_quo_baseline, power_grid_objectives)

        assert res.unknown_count == 1
        delta_cost = res.deltas["OBJ-COST"]
        assert delta_cost.impact == DeltaImpact.UNKNOWN
        assert delta_cost.raw_delta is None
        assert delta_cost.candidate_value is None
        assert "missing or non-finite" in delta_cost.explanation

    def test_unit_mismatch_fails_closed_to_unknown(
        self, power_grid_objectives: list[ObjectiveDefinition], status_quo_baseline: CounterfactualBaseline
    ) -> None:
        # Candidate provides OBJ-COST in EUR instead of USD
        cand_mismatch = CandidateStrategy(
            strategy_id="STRAT-MISMATCH",
            strategy_name="Unit Mismatch Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ-EUE": 20.0, "OBJ-COST": 1000.0, "OBJ-RESERVE": 60.0},
            objective_units={"OBJ-COST": "EUR"},
        )
        res = compute_baseline_comparison(cand_mismatch, status_quo_baseline, power_grid_objectives)

        assert res.deltas["OBJ-COST"].impact == DeltaImpact.UNKNOWN
        assert res.deltas["OBJ-COST"].raw_delta is None
        assert "Unit mismatch" in res.deltas["OBJ-COST"].explanation


class TestRegretQuantification:
    """Tests for decision-theoretic regret quantification against benchmark sets."""

    def test_ideal_strategy_has_zero_regret(
        self, power_grid_objectives: list[ObjectiveDefinition]
    ) -> None:
        # Best achievable strategy in candidate pool
        s_best = CandidateStrategy(
            strategy_id="STRAT-BEST",
            strategy_name="Ideal Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ-EUE": 0.0, "OBJ-COST": 0.0, "OBJ-RESERVE": 100.0},
        )
        s_other = CandidateStrategy(
            strategy_id="STRAT-OTHER",
            strategy_name="Other Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ-EUE": 50.0, "OBJ-COST": 5000.0, "OBJ-RESERVE": 40.0},
        )

        regret = compute_regret_metrics(
            strategy=s_best,
            benchmark_set=[s_best, s_other],
            objectives=power_grid_objectives,
            regret_type=RegretType.DECISION_TIME_ESTIMATE,
        )

        assert regret.regret_type == RegretType.DECISION_TIME_ESTIMATE
        assert regret.max_regret == 0.0
        assert regret.objective_regrets["OBJ-EUE"] == 0.0
        assert regret.objective_regrets["OBJ-COST"] == 0.0
        assert regret.objective_regrets["OBJ-RESERVE"] == 0.0
        assert regret.normalized_regrets["OBJ-EUE"] == 0.0

    def test_worst_strategy_has_maximum_regret_one(
        self, power_grid_objectives: list[ObjectiveDefinition]
    ) -> None:
        s_best = CandidateStrategy(
            strategy_id="STRAT-BEST",
            strategy_name="Best Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ-EUE": 10.0, "OBJ-COST": 1000.0, "OBJ-RESERVE": 80.0},
        )
        s_worst = CandidateStrategy(
            strategy_id="STRAT-WORST",
            strategy_name="Worst Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ-EUE": 60.0, "OBJ-COST": 5000.0, "OBJ-RESERVE": 20.0},
        )

        regret = compute_regret_metrics(
            strategy=s_worst,
            benchmark_set=[s_best, s_worst],
            objectives=power_grid_objectives,
            regret_type=RegretType.EX_POST_OBSERVED,
        )

        assert regret.regret_type == RegretType.EX_POST_OBSERVED
        # Raw regrets in native physical units
        assert regret.objective_regrets["OBJ-EUE"] == 50.0  # 60 - 10
        assert regret.objective_regrets["OBJ-COST"] == 4000.0  # 5000 - 1000
        assert regret.objective_regrets["OBJ-RESERVE"] == 60.0  # 80 - 20 (Ideal is 80, strat has 20)

        # Normalized Chebyshev regret must be 1.0 (worst across normalized range)
        assert regret.normalized_regrets["OBJ-EUE"] == 1.0
        assert regret.normalized_regrets["OBJ-COST"] == 1.0
        assert regret.normalized_regrets["OBJ-RESERVE"] == 1.0
        assert regret.max_regret == 1.0

    def test_infeasible_benchmark_candidates_filtered_out(
        self, power_grid_objectives: list[ObjectiveDefinition]
    ) -> None:
        s_feas = CandidateStrategy(
            strategy_id="S_FEAS",
            strategy_name="Feasible Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ-EUE": 20.0, "OBJ-COST": 1000.0, "OBJ-RESERVE": 50.0},
        )
        s_infeas = CandidateStrategy(
            strategy_id="S_INFEAS",
            strategy_name="Infeasible Strategy",
            feasibility_status=FeasibilityStatus.INFEASIBLE,
            objectives={"OBJ-EUE": 0.0, "OBJ-COST": 0.0, "OBJ-RESERVE": 200.0},  # Falsely attractive!
        )

        # Infeasible candidate MUST NOT serve as ideal benchmark
        regret = compute_regret_metrics(
            strategy=s_feas,
            benchmark_set=[s_feas, s_infeas],
            objectives=power_grid_objectives,
        )

        # Since s_feas is the only feasible candidate in benchmark set, regret is 0.0
        assert regret.max_regret == 0.0
        assert "S_INFEAS" not in regret.benchmark_strategy_ids

    def test_empty_or_all_infeasible_benchmark_raises_error(
        self, power_grid_objectives: list[ObjectiveDefinition]
    ) -> None:
        s_feas = CandidateStrategy(
            strategy_id="S_FEAS",
            strategy_name="Feasible Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ-EUE": 20.0, "OBJ-COST": 1000.0, "OBJ-RESERVE": 50.0},
        )

        with pytest.raises(ValueError, match="Benchmark set cannot be empty"):
            compute_regret_metrics(s_feas, [], power_grid_objectives)

        s_inf = CandidateStrategy(
            strategy_id="S_INF",
            strategy_name="Inf",
            feasibility_status=FeasibilityStatus.INFEASIBLE,
            objectives={"OBJ-EUE": 0.0, "OBJ-COST": 0.0, "OBJ-RESERVE": 0.0},
        )
        with pytest.raises(ValueError, match="contains zero valid FEASIBLE candidates"):
            compute_regret_metrics(s_feas, [s_inf], power_grid_objectives)


class TestDeterminism:
    """Tests confirming strict determinism of counterfactual and regret functions."""

    def test_repeated_comparison_and_regret_is_identical(
        self, power_grid_objectives: list[ObjectiveDefinition], status_quo_baseline: CounterfactualBaseline
    ) -> None:
        cand = CandidateStrategy(
            strategy_id="STRAT-DET",
            strategy_name="Deterministic Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ-EUE": 15.5, "OBJ-COST": 3200.0, "OBJ-RESERVE": 65.0},
        )

        base_res = compute_baseline_comparison(cand, status_quo_baseline, power_grid_objectives)
        base_regret = compute_regret_metrics(cand, [cand, status_quo_baseline], power_grid_objectives)

        for _ in range(50):
            rep_res = compute_baseline_comparison(cand, status_quo_baseline, power_grid_objectives)
            rep_regret = compute_regret_metrics(cand, [cand, status_quo_baseline], power_grid_objectives)

            assert rep_res.net_improvements_count == base_res.net_improvements_count
            assert rep_res.net_degradations_count == base_res.net_degradations_count
            assert rep_res.deltas["OBJ-EUE"].raw_delta == base_res.deltas["OBJ-EUE"].raw_delta
            assert rep_regret.max_regret == base_regret.max_regret
            assert rep_regret.objective_regrets == base_regret.objective_regrets
