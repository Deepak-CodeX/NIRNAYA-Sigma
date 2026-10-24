"""
Unit tests for NIRNAYA Pareto dominance and multi-objective non-dominated sorting.

Covers:
- Strict Pareto dominance (DOMINATES, DOMINATED).
- Equal objective vectors (EQUAL).
- Multi-criteria operational trade-offs (INCOMPARABLE).
- Optimization directions: MINIMIZE, MAXIMIZE, and mixed dimensions.
- Feasibility policy: infeasible strategies strictly excluded from Pareto front.
- UNKNOWN feasibility policy: quarantined candidates strictly excluded from Pareto front.
- Missing or non-finite objective metrics fail-closed into unknown set.
- Deterministic Fast Non-Dominated Sorting and stable tie-breaking across 100 runs.
- Multi-front decomposition (Front 1, Front 2, Front 3).
- Schema compatibility against contracts/schemas/strategy_comparison.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
try:
    import pytest
except ImportError:
    from tests.compat import pytest

from nirnaya.domain.enums import (
    DominanceRelation,
    FeasibilityStatus,
    ObjectiveDirection,
)
from nirnaya.domain.models import (
    CandidateStrategy,
    ObjectiveDefinition,
)
from nirnaya.pareto.dominance import check_pareto_dominance
from nirnaya.pareto.sorting import compute_pareto_comparison


@pytest.fixture
def canonical_objectives() -> list[ObjectiveDefinition]:
    return [
        ObjectiveDefinition(
            objective_id="OBJ_EUE",
            name="Expected Unserved Energy",
            direction=ObjectiveDirection.MINIMIZE,
            unit="MWh",
        ),
        ObjectiveDefinition(
            objective_id="OBJ_COST",
            name="Operational Redispatch Cost",
            direction=ObjectiveDirection.MINIMIZE,
            unit="USD",
        ),
    ]


@pytest.fixture
def mixed_objectives() -> list[ObjectiveDefinition]:
    return [
        ObjectiveDefinition(
            objective_id="OBJ_EUE",
            name="Expected Unserved Energy",
            direction=ObjectiveDirection.MINIMIZE,
            unit="MWh",
        ),
        ObjectiveDefinition(
            objective_id="OBJ_RESERVE",
            name="Available Spinning Reserve",
            direction=ObjectiveDirection.MAXIMIZE,
            unit="MW",
        ),
    ]


class TestParetoDominance:
    """Tests for pairwise Pareto dominance comparisons."""

    def test_strict_dominance_minimization(self, canonical_objectives: list[ObjectiveDefinition]) -> None:
        # Strategy A has lower EUE and lower Cost -> A dominates B
        strat_a = CandidateStrategy(
            strategy_id="STRAT_A",
            strategy_name="Strategy A",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0, "OBJ_COST": 1000.0},
        )
        strat_b = CandidateStrategy(
            strategy_id="STRAT_B",
            strategy_name="Strategy B",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 20.0, "OBJ_COST": 2000.0},
        )

        assert check_pareto_dominance(strat_a, strat_b, canonical_objectives) == DominanceRelation.DOMINATES
        assert check_pareto_dominance(strat_b, strat_a, canonical_objectives) == DominanceRelation.DOMINATED

    def test_strict_dominance_with_one_equal_objective(self, canonical_objectives: list[ObjectiveDefinition]) -> None:
        # Strategy A has equal EUE but strictly lower Cost -> A dominates B
        strat_a = CandidateStrategy(
            strategy_id="STRAT_A",
            strategy_name="Strategy A",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0, "OBJ_COST": 1000.0},
        )
        strat_b = CandidateStrategy(
            strategy_id="STRAT_B",
            strategy_name="Strategy B",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0, "OBJ_COST": 1500.0},
        )

        assert check_pareto_dominance(strat_a, strat_b, canonical_objectives) == DominanceRelation.DOMINATES
        assert check_pareto_dominance(strat_b, strat_a, canonical_objectives) == DominanceRelation.DOMINATED

    def test_equal_objective_vectors(self, canonical_objectives: list[ObjectiveDefinition]) -> None:
        # Identical objective metrics
        strat_a = CandidateStrategy(
            strategy_id="STRAT_A",
            strategy_name="Strategy A",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0, "OBJ_COST": 1000.0},
        )
        strat_b = CandidateStrategy(
            strategy_id="STRAT_B",
            strategy_name="Strategy B",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0, "OBJ_COST": 1000.0},
        )

        assert check_pareto_dominance(strat_a, strat_b, canonical_objectives) == DominanceRelation.EQUAL
        assert check_pareto_dominance(strat_b, strat_a, canonical_objectives) == DominanceRelation.EQUAL

    def test_incomparable_trade_off(self, canonical_objectives: list[ObjectiveDefinition]) -> None:
        # Strategy A has lower EUE but higher Cost than B -> Incomparable trade-off
        strat_a = CandidateStrategy(
            strategy_id="STRAT_A",
            strategy_name="Strategy A",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 5.0, "OBJ_COST": 3000.0},
        )
        strat_b = CandidateStrategy(
            strategy_id="STRAT_B",
            strategy_name="Strategy B",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 15.0, "OBJ_COST": 1000.0},
        )

        assert check_pareto_dominance(strat_a, strat_b, canonical_objectives) == DominanceRelation.INCOMPARABLE
        assert check_pareto_dominance(strat_b, strat_a, canonical_objectives) == DominanceRelation.INCOMPARABLE

    def test_mixed_objective_directions(self, mixed_objectives: list[ObjectiveDefinition]) -> None:
        # OBJ_EUE is MINIMIZE, OBJ_RESERVE is MAXIMIZE
        # Strategy A has lower EUE (better) and higher reserve (better) -> A dominates B
        strat_a = CandidateStrategy(
            strategy_id="STRAT_A",
            strategy_name="Strategy A",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 5.0, "OBJ_RESERVE": 100.0},
        )
        strat_b = CandidateStrategy(
            strategy_id="STRAT_B",
            strategy_name="Strategy B",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0, "OBJ_RESERVE": 50.0},
        )

        assert check_pareto_dominance(strat_a, strat_b, mixed_objectives) == DominanceRelation.DOMINATES
        assert check_pareto_dominance(strat_b, strat_a, mixed_objectives) == DominanceRelation.DOMINATED

    def test_infeasible_strategy_rejected_from_direct_dominance(
        self, canonical_objectives: list[ObjectiveDefinition]
    ) -> None:
        strat_feas = CandidateStrategy(
            strategy_id="STRAT_OK",
            strategy_name="Feasible Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0, "OBJ_COST": 1000.0},
        )
        strat_inf = CandidateStrategy(
            strategy_id="STRAT_INF",
            strategy_name="Infeasible Strategy",
            feasibility_status=FeasibilityStatus.INFEASIBLE,
            objectives={"OBJ_EUE": 5.0, "OBJ_COST": 500.0},  # Even if values look better!
        )

        with pytest.raises(ValueError, match="Pareto dominance is only defined for FEASIBLE strategies"):
            check_pareto_dominance(strat_feas, strat_inf, canonical_objectives)

    def test_unknown_strategy_rejected_from_direct_dominance(
        self, canonical_objectives: list[ObjectiveDefinition]
    ) -> None:
        strat_feas = CandidateStrategy(
            strategy_id="STRAT_OK",
            strategy_name="Feasible Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0, "OBJ_COST": 1000.0},
        )
        strat_unk = CandidateStrategy(
            strategy_id="STRAT_UNK",
            strategy_name="Unknown Strategy",
            feasibility_status=FeasibilityStatus.UNKNOWN,
            objectives={"OBJ_EUE": 5.0, "OBJ_COST": 500.0},
        )

        with pytest.raises(ValueError, match="Pareto dominance is only defined for FEASIBLE strategies"):
            check_pareto_dominance(strat_feas, strat_unk, canonical_objectives)

    def test_missing_objective_raises_error(self, canonical_objectives: list[ObjectiveDefinition]) -> None:
        strat_a = CandidateStrategy(
            strategy_id="STRAT_A",
            strategy_name="Strategy A",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0},  # Missing OBJ_COST
        )
        strat_b = CandidateStrategy(
            strategy_id="STRAT_B",
            strategy_name="Strategy B",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 20.0, "OBJ_COST": 2000.0},
        )

        with pytest.raises(ValueError, match="missing required objective"):
            check_pareto_dominance(strat_a, strat_b, canonical_objectives)


class TestNonDominatedSorting:
    """Tests for multi-objective non-dominated sorting and candidate partitioning."""

    def test_partition_infeasible_and_unknown_strategies(
        self, canonical_objectives: list[ObjectiveDefinition]
    ) -> None:
        s1 = CandidateStrategy(
            strategy_id="STRAT_FEAS_1",
            strategy_name="Feasible Strategy 1",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0, "OBJ_COST": 2000.0},
        )
        s2 = CandidateStrategy(
            strategy_id="STRAT_FEAS_2",
            strategy_name="Feasible Strategy 2",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 20.0, "OBJ_COST": 1000.0},
        )
        s_inf = CandidateStrategy(
            strategy_id="STRAT_INFEAS",
            strategy_name="Overloaded Strategy",
            feasibility_status=FeasibilityStatus.INFEASIBLE,
            objectives={"OBJ_EUE": 1.0, "OBJ_COST": 100.0},
        )
        s_unk = CandidateStrategy(
            strategy_id="STRAT_UNCONV",
            strategy_name="Unconverged Strategy",
            feasibility_status=FeasibilityStatus.UNKNOWN,
            objectives={"OBJ_EUE": 2.0, "OBJ_COST": 200.0},
        )

        result = compute_pareto_comparison(
            candidates=[s1, s_inf, s2, s_unk],
            objectives=canonical_objectives,
            problem_id="PROB_001",
            comparison_id="COMP_001",
        )

        # Infeasible and unknown strategies MUST be excluded from the Pareto frontier
        frontier_ids = [s.strategy_id for s in result.pareto_frontier]
        assert "STRAT_INFEAS" not in frontier_ids
        assert "STRAT_UNCONV" not in frontier_ids

        # Assert correct partition placement
        assert len(result.infeasible_strategies) == 1
        assert result.infeasible_strategies[0].strategy_id == "STRAT_INFEAS"
        assert len(result.unknown_strategies) == 1
        assert result.unknown_strategies[0].strategy_id == "STRAT_UNCONV"

        # Feasible strategies s1 and s2 are incomparable trade-offs -> both in Pareto frontier
        assert len(result.pareto_frontier) == 2
        assert frontier_ids == ["STRAT_FEAS_1", "STRAT_FEAS_2"]
        assert len(result.dominated_strategies) == 0

    def test_missing_objective_quarantined_to_unknown(
        self, canonical_objectives: list[ObjectiveDefinition]
    ) -> None:
        s1 = CandidateStrategy(
            strategy_id="STRAT_1",
            strategy_name="Complete Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0, "OBJ_COST": 2000.0},
        )
        s_missing = CandidateStrategy(
            strategy_id="STRAT_INCOMPLETE",
            strategy_name="Incomplete Strategy",
            feasibility_status=FeasibilityStatus.FEASIBLE,  # Marked feasible, but missing metrics!
            objectives={"OBJ_EUE": 5.0},  # Missing OBJ_COST
        )

        result = compute_pareto_comparison(
            candidates=[s1, s_missing],
            objectives=canonical_objectives,
            problem_id="PROB_001",
            comparison_id="COMP_001",
        )

        # Incomplete strategy must fail-closed into unknown_strategies
        assert len(result.pareto_frontier) == 1
        assert result.pareto_frontier[0].strategy_id == "STRAT_1"
        assert len(result.unknown_strategies) == 1
        assert result.unknown_strategies[0].strategy_id == "STRAT_INCOMPLETE"

    def test_multi_front_decomposition(self, canonical_objectives: list[ObjectiveDefinition]) -> None:
        # Construct a 3-tier hierarchy:
        # Tier 1 (Pareto Frontier): s1 and s2 (incomparable trade-off)
        # Tier 2: s3 (dominated by s1, but dominates s4)
        # Tier 3: s4 (dominated by s3)
        s1 = CandidateStrategy(
            strategy_id="S1",
            strategy_name="Strategy 1",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 5.0, "OBJ_COST": 2000.0},
        )
        s2 = CandidateStrategy(
            strategy_id="S2",
            strategy_name="Strategy 2",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 15.0, "OBJ_COST": 500.0},
        )
        s3 = CandidateStrategy(
            strategy_id="S3",
            strategy_name="Strategy 3",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0, "OBJ_COST": 3000.0},  # Dominated by S1
        )
        s4 = CandidateStrategy(
            strategy_id="S4",
            strategy_name="Strategy 4",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 25.0, "OBJ_COST": 4000.0},  # Dominated by S1, S2, and S3
        )

        result = compute_pareto_comparison(
            candidates=[s4, s2, s3, s1],  # Passed in scrambled order
            objectives=canonical_objectives,
            problem_id="PROB_001",
            comparison_id="COMP_001",
        )

        assert len(result.all_fronts) == 3
        # Front 1 (Pareto optimal)
        front_1_ids = [s.strategy_id for s in result.all_fronts[0].strategies]
        assert front_1_ids == ["S1", "S2"]
        assert [s.strategy_id for s in result.pareto_frontier] == ["S1", "S2"]

        # Front 2
        front_2_ids = [s.strategy_id for s in result.all_fronts[1].strategies]
        assert front_2_ids == ["S3"]

        # Front 3
        front_3_ids = [s.strategy_id for s in result.all_fronts[2].strategies]
        assert front_3_ids == ["S4"]

        # Dominated strategies collection contains S3 and S4
        dominated_ids = [s.strategy_id for s in result.dominated_strategies]
        assert "S3" in dominated_ids
        assert "S4" in dominated_ids
        assert "S1" not in dominated_ids
        assert "S2" not in dominated_ids

    def test_equal_vectors_in_front(self, canonical_objectives: list[ObjectiveDefinition]) -> None:
        # Two strategies with identical objective values
        s1 = CandidateStrategy(
            strategy_id="S_ALPHA",
            strategy_name="Alpha",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0, "OBJ_COST": 1000.0},
        )
        s2 = CandidateStrategy(
            strategy_id="S_BETA",
            strategy_name="Beta",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 10.0, "OBJ_COST": 1000.0},
        )

        result = compute_pareto_comparison(
            candidates=[s2, s1],
            objectives=canonical_objectives,
            problem_id="PROB_001",
            comparison_id="COMP_001",
        )

        # Both belong to Front 1, ordered deterministically by strategy_id
        assert len(result.pareto_frontier) == 2
        assert [s.strategy_id for s in result.pareto_frontier] == ["S_ALPHA", "S_BETA"]
        assert result.equal_pairs_count == 1

    def test_deterministic_sorting_repeatability(
        self, canonical_objectives: list[ObjectiveDefinition]
    ) -> None:
        # Generate 10 candidate strategies
        candidates = [
            CandidateStrategy(
                strategy_id=f"STRAT_{i:02d}",
                strategy_name=f"Strategy {i}",
                feasibility_status=FeasibilityStatus.FEASIBLE if i % 4 != 0 else FeasibilityStatus.INFEASIBLE,
                objectives={"OBJ_EUE": float((i * 7) % 23), "OBJ_COST": float((i * 13) % 47 * 100)},
            )
            for i in range(12)
        ]

        # Run comparison 100 times; assert identical ordering on every execution
        baseline = compute_pareto_comparison(
            candidates=candidates,
            objectives=canonical_objectives,
            problem_id="P1",
            comparison_id="C1",
        )

        for _ in range(100):
            repeated = compute_pareto_comparison(
                candidates=candidates,
                objectives=canonical_objectives,
                problem_id="P1",
                comparison_id="C1",
            )
            assert [s.strategy_id for s in repeated.pareto_frontier] == [s.strategy_id for s in baseline.pareto_frontier]
            assert [s.strategy_id for s in repeated.dominated_strategies] == [s.strategy_id for s in baseline.dominated_strategies]
            assert [s.strategy_id for s in repeated.infeasible_strategies] == [s.strategy_id for s in baseline.infeasible_strategies]
            assert len(repeated.all_fronts) == len(baseline.all_fronts)
            assert repeated.incomparable_pairs_count == baseline.incomparable_pairs_count
            assert repeated.equal_pairs_count == baseline.equal_pairs_count


class TestStrategyComparisonSchemaConformance:
    """Tests confirming JSON output compatibility with contracts/schemas/strategy_comparison.json."""

    def test_schema_conformance(self, canonical_objectives: list[ObjectiveDefinition]) -> None:
        import os
        import jsonschema

        schema_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "contracts", "schemas", "strategy_comparison.json"
        )
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        s1 = CandidateStrategy(
            strategy_id="d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a",
            strategy_name="STRAT-HYDRO-REDISPATCH-AND-CURTAIL",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 14.2, "OBJ_COST": 4850.0},
            delta_vs_baseline={"OBJ_EUE": -85.8, "OBJ_COST": 4850.0},
            max_regret=120.0,
        )
        s2 = CandidateStrategy(
            strategy_id="22222222-3333-4444-5555-666666666666",
            strategy_name="STRAT-DOMINATED",
            feasibility_status=FeasibilityStatus.FEASIBLE,
            objectives={"OBJ_EUE": 25.0, "OBJ_COST": 6000.0},
            delta_vs_baseline={"OBJ_EUE": -75.0, "OBJ_COST": 6000.0},
            max_regret=300.0,
        )
        s_inf = CandidateStrategy(
            strategy_id="33333333-4444-5555-6666-777777777777",
            strategy_name="STRAT-OVERLOADED",
            feasibility_status=FeasibilityStatus.INFEASIBLE,
            objectives={"OBJ_EUE": 0.0, "OBJ_COST": 0.0},
        )

        res = compute_pareto_comparison(
            candidates=[s1, s2, s_inf],
            objectives=canonical_objectives,
            problem_id="c3d4e5f6-a7b8-4c9d-0e1f-2a3b4c5d6e7f",
            comparison_id="f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c",
        )

        # Assemble full payload matching strategy_comparison.json
        payload = {
            "comparison_id": res.comparison_id,
            "problem_id": res.problem_id,
            "schema_version": "v1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "baseline_scenario_id": "00000000-0000-0000-0000-000000000001",
            "pareto_frontier_scenario_ids": [s.strategy_id for s in res.pareto_frontier],
            "dominated_scenario_ids": [s.strategy_id for s in res.dominated_strategies],
            "infeasible_scenario_ids": [s.strategy_id for s in res.infeasible_strategies],
            "unknown_scenario_ids": [s.strategy_id for s in res.unknown_strategies],
            "tradeoff_matrix": [
                {
                    "scenario_id": s.strategy_id,
                    "strategy_name": s.strategy_name,
                    "objective_values": s.objectives,
                    "delta_vs_baseline": s.delta_vs_baseline or {"OBJ_EUE": 0.0, "OBJ_COST": 0.0},
                    "max_regret": s.max_regret or 0.0,
                    "robustness_score": 0.95,
                }
                for s in res.pareto_frontier
            ],
            "evidence_explanation": {
                "primary_recommendation_scenario_id": res.pareto_frontier[0].strategy_id,
                "justification_summary": "Mathematically non-dominated trade-off.",
                "tradeoff_narrative": "Non-dominated across unserved energy and cost.",
                "key_risks": ["Risk assessment active."],
            },
        }

        # Assert zero jsonschema validation errors
        jsonschema.validate(instance=payload, schema=schema)
