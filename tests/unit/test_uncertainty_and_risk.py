"""
Unit tests for Milestone 4: Uncertainty Quantification, Tail Risk Measures, and Sensitivity Analysis.

Verifies:
1. Exact mathematical hand-calculations for VaR and CVaR.
2. Risk invariant enforcement: CVaR_alpha >= VaR_alpha.
3. Fail-closed behavior on insufficient samples, non-finite values, and invalid confidence levels.
4. Fail-closed rejection of uncalibrated empirical claims lacking valid SHA-256 provenance.
5. Exact hand-calculations for raw sensitivity and normalized elasticity.
6. Scenario uncertainty propagation for multi-objective candidate evaluations and counterfactual deltas.
7. Semantic separation of aleatory and epistemic uncertainty representations.
8. Deterministic repeatability over repeated executions.
"""

from __future__ import annotations

import math
try:
    import pytest
except ImportError:
    from tests.compat import pytest

from nirnaya.domain.enums import (
    DistributionType,
    LossConvention,
    ObjectiveDirection,
    UncertaintyType,
)
from nirnaya.domain.models import (
    ObjectiveDefinition,
    RiskMetrics,
    SensitivityMetric,
    UncertaintyParameter,
)
from nirnaya.uncertainty.propagation import (
    propagate_counterfactual_uncertainty,
    propagate_scenario_uncertainty,
)
from nirnaya.uncertainty.risk import compute_risk_metrics
from nirnaya.uncertainty.sensitivity import compute_sensitivity


VALID_SHA256 = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


class TestRiskQuantification:
    """Mathematical verification and edge case handling for risk metrics and tail loss."""

    def test_risk_metrics_hand_calculated_discrete_20_samples(self) -> None:
        """
        Verify hand-calculated VaR and CVaR on 20 discrete samples: [1.0, 2.0, ..., 20.0].

        Hand-calculated values:
        N = 20
        mu = 10.5
        Variance = 35.0, std_dev = sqrt(35) ~= 5.916079783
        SEM = sqrt(1.75) ~= 1.322875655
        SEM / mu = 1.322875655 / 10.5 ~= 0.125988 > 0.05 -> sample_converged = False

        For alpha = 0.95:
        k_alpha = ceil(0.95 * 20) = 19
        0-based index: 18 -> L_(19) = 19.0
        VaR_0.95 = 19.0

        Tail samples: [19.0, 20.0]
        CVaR_0.95 = (19.0 + 20.0) / 2 = 19.5
        CVaR (19.5) >= VaR (19.0) holds strictly.
        """
        samples = [float(i) for i in range(1, 21)]
        res = compute_risk_metrics(
            objective_id="transmission_loss",
            samples=samples,
            confidence_level=0.95,
            unit="MW",
            loss_convention=LossConvention.DIRECT_OBJECTIVE,
            loss_threshold=15.0,
        )

        assert res.objective_id == "transmission_loss"
        assert res.sample_size == 20
        assert pytest.approx(res.mean, abs=1e-6) == 10.5
        assert pytest.approx(res.std_dev, abs=1e-6) == math.sqrt(35.0)
        assert pytest.approx(res.standard_error, abs=1e-6) == math.sqrt(1.75)
        assert res.sample_converged is False
        assert res.var == 19.0
        assert res.cvar == 19.5
        assert res.cvar >= res.var
        assert res.unit == "MW"
        assert res.loss_convention == LossConvention.DIRECT_OBJECTIVE
        # Threshold 15.0: samples 1..15 are <= 15.0 -> 15 / 20 = 0.75
        assert pytest.approx(res.robustness_score, abs=1e-6) == 0.75
        assert res.is_empirically_calibrated is False

    def test_risk_metrics_negative_objective_maximization(self) -> None:
        """
        Verify loss convention mapping for a maximization objective (e.g. reserve margin).
        Under NEGATIVE_OBJECTIVE, Loss = -f_k.
        """
        # 20 samples from 100 down to 5: [100, 95, 90, ..., 5]
        samples = [float(105 - 5 * i) for i in range(1, 21)]
        # Losses = -samples: [-100, -95, ..., -5]
        # Sorted losses: [-100, -95, ..., -10, -5]
        # At alpha = 0.95: k_alpha = 19 -> 0-based idx 18 -> loss is -10.0
        # Tail losses: [-10.0, -5.0] -> average = -7.5
        res = compute_risk_metrics(
            objective_id="reserve_margin",
            samples=samples,
            confidence_level=0.95,
            unit="MW",
            loss_convention=LossConvention.NEGATIVE_OBJECTIVE,
        )

        assert res.var == -10.0
        assert res.cvar == -7.5
        assert res.cvar >= res.var
        assert res.loss_convention == LossConvention.NEGATIVE_OBJECTIVE

    def test_risk_metrics_convergence_flag(self) -> None:
        """
        Verify convergence flag is True when SEM / |mean| <= 0.05.
        """
        # High sample size with low variance: N = 100, all around 100.0 with minor flutter
        samples = [100.0 + (i % 3) * 0.1 for i in range(100)]
        res = compute_risk_metrics(
            objective_id="bus_voltage",
            samples=samples,
            confidence_level=0.95,
            unit="kV",
        )
        assert res.sample_converged is True

    @pytest.mark.parametrize(
        "sample_list",
        [
            [5.0] * 25,  # Zero variance constant
            [1.0, 2.0, 3.0, 4.0, 5.0] * 5,  # Multimodal periodic
            [10.0] * 20 + [50.0, 100.0],  # Right-skewed extreme tail
        ],
    )
    def test_risk_metrics_invariant_cvar_ge_var(self, sample_list: list[float]) -> None:
        """
        Verify mathematical invariant CVaR_alpha >= VaR_alpha across varied distributions.
        """
        res = compute_risk_metrics(
            objective_id="test_distribution",
            samples=sample_list,
            confidence_level=0.95,
            unit="units",
        )
        assert res.cvar >= res.var - 1e-9

    def test_risk_metrics_rejects_insufficient_sample_size(self) -> None:
        """
        Verify fail-closed rejection when N < 2.
        """
        with pytest.raises(ValueError, match="Sample size N must be at least 2"):
            compute_risk_metrics("cost", [10.0], 0.95)

    def test_risk_metrics_rejects_sample_size_smaller_than_tail_resolution(self) -> None:
        """
        Verify fail-closed rejection when N < ceil(1 / (1 - alpha)).
        For alpha = 0.95, min_N = ceil(1 / 0.05) = 20.
        Testing N = 19 should fail closed.
        """
        samples_19 = [float(i) for i in range(19)]
        with pytest.raises(ValueError, match="Insufficient sample size N=19 for confidence level 0.95"):
            compute_risk_metrics("cost", samples_19, confidence_level=0.95)

    @pytest.mark.parametrize("invalid_alpha", [-0.5, 0.0, 1.0, 1.05])
    def test_risk_metrics_rejects_invalid_confidence_levels(self, invalid_alpha: float) -> None:
        """
        Verify fail-closed rejection for alpha outside (0.0, 1.0).
        """
        samples = [float(i) for i in range(25)]
        with pytest.raises(ValueError, match="confidence_level must be strictly between 0.0 and 1.0"):
            compute_risk_metrics("cost", samples, confidence_level=invalid_alpha)

    @pytest.mark.parametrize("bad_val", [math.nan, math.inf, -math.inf])
    def test_risk_metrics_rejects_non_finite_values(self, bad_val: float) -> None:
        """
        Verify fail-closed rejection when any sample realization is NaN or infinite.
        """
        samples = [1.0] * 24 + [bad_val]
        with pytest.raises(ValueError, match="must be a finite number"):
            compute_risk_metrics("cost", samples, confidence_level=0.95)

    def test_risk_metrics_rejects_uncalibrated_claim_without_provenance(self) -> None:
        """
        Verify fail-closed rejection when is_empirically_calibrated is True
        without a valid SHA-256 provenance digest.
        """
        samples = [float(i) for i in range(25)]
        with pytest.raises(ValueError, match="Uncalibrated claim"):
            compute_risk_metrics(
                "cost",
                samples,
                confidence_level=0.95,
                is_empirically_calibrated=True,
                provenance_digest=None,
            )

        with pytest.raises(ValueError, match="Uncalibrated claim"):
            compute_risk_metrics(
                "cost",
                samples,
                confidence_level=0.95,
                is_empirically_calibrated=True,
                provenance_digest="invalid_sha_string",
            )

    def test_risk_metrics_accepts_valid_calibration_provenance(self) -> None:
        """
        Verify that providing a valid SHA-256 digest allows is_empirically_calibrated=True.
        """
        samples = [float(i) for i in range(25)]
        res = compute_risk_metrics(
            "cost",
            samples,
            confidence_level=0.95,
            is_empirically_calibrated=True,
            provenance_digest=VALID_SHA256,
        )
        assert res.is_empirically_calibrated is True


class TestSensitivityAnalysis:
    """Deterministic first-order gradient sensitivity and normalized elasticity tests."""

    def test_sensitivity_hand_calculated_linear_gradient_and_elasticity(self) -> None:
        """
        Verify hand-calculated first-order sensitivity and normalized elasticity.

        Hand-calculated values:
        p0 = 100.0, p_pert = 110.0 -> Delta p = 10.0
        f0 = 50.0, f_pert = 60.0 -> Delta f = 10.0
        Raw sensitivity S = 10.0 / 10.0 = 1.0
        Normalized elasticity = 1.0 * (100.0 / 50.0) = 2.0
        """
        metric = compute_sensitivity(
            objective_id="line_loss",
            parameter_name="ambient_temp",
            base_objective_value=50.0,
            perturbed_objective_value=60.0,
            base_parameter_value=100.0,
            perturbed_parameter_value=110.0,
            objective_unit="MW",
            parameter_unit="degC",
        )

        assert metric.objective_id == "line_loss"
        assert metric.parameter_name == "ambient_temp"
        assert pytest.approx(metric.raw_sensitivity, abs=1e-9) == 1.0
        assert pytest.approx(metric.normalized_elasticity, abs=1e-9) == 2.0
        assert metric.unit == "MW/degC"

    def test_sensitivity_undefined_elasticity_at_zero_baseline(self) -> None:
        """
        Verify that elasticity is None when baseline parameter or baseline objective is 0.
        """
        metric = compute_sensitivity(
            objective_id="emissions",
            parameter_name="carbon_tax",
            base_objective_value=0.0,
            perturbed_objective_value=10.0,
            base_parameter_value=0.0,
            perturbed_parameter_value=5.0,
            objective_unit="tonCO2",
            parameter_unit="USD",
        )

        assert pytest.approx(metric.raw_sensitivity, abs=1e-9) == 2.0
        assert metric.normalized_elasticity is None

    def test_sensitivity_rejects_zero_parameter_delta(self) -> None:
        """
        Verify fail-closed rejection when parameter perturbation is numerically zero.
        """
        with pytest.raises(ValueError, match="Parameter perturbation delta for 'solar_capacity' is numerically zero"):
            compute_sensitivity(
                objective_id="generation",
                parameter_name="solar_capacity",
                base_objective_value=100.0,
                perturbed_objective_value=100.0,
                base_parameter_value=50.0,
                perturbed_parameter_value=50.0,
            )

    @pytest.mark.parametrize("bad_val", [math.nan, math.inf, -math.inf])
    def test_sensitivity_rejects_non_finite_inputs(self, bad_val: float) -> None:
        """
        Verify fail-closed rejection of non-finite numbers in sensitivity calculations.
        """
        with pytest.raises(ValueError, match="must be a finite number"):
            compute_sensitivity(
                objective_id="generation",
                parameter_name="solar_capacity",
                base_objective_value=bad_val,
                perturbed_objective_value=100.0,
                base_parameter_value=50.0,
                perturbed_parameter_value=55.0,
            )


class TestUncertaintyPropagation:
    """Multi-objective scenario propagation and counterfactual delta uncertainty tests."""

    def test_scenario_uncertainty_propagation_multi_objective(self) -> None:
        """
        Verify propagation across 25 Monte Carlo scenarios with multiple objectives.
        """
        objectives = [
            ObjectiveDefinition(
                objective_id="loss_mw",
                name="Transmission Loss",
                direction=ObjectiveDirection.MINIMIZE,
                unit="MW",
            ),
            ObjectiveDefinition(
                objective_id="reserve_margin",
                name="Operating Reserve Margin",
                direction=ObjectiveDirection.MAXIMIZE,
                unit="MW",
            ),
        ]

        scenarios = [
            {"loss_mw": 10.0 + i * 0.5, "reserve_margin": 100.0 - i * 1.0}
            for i in range(25)
        ]

        results = propagate_scenario_uncertainty(
            strategy_id="strat_topology_a",
            scenario_evaluations=scenarios,
            objectives=objectives,
            confidence_level=0.95,
            loss_thresholds={"loss_mw": 20.0},
        )

        assert "loss_mw" in results
        assert "reserve_margin" in results

        loss_res = results["loss_mw"]
        assert loss_res.loss_convention == LossConvention.DIRECT_OBJECTIVE
        assert loss_res.unit == "MW"
        assert loss_res.cvar >= loss_res.var

        reserve_res = results["reserve_margin"]
        assert reserve_res.loss_convention == LossConvention.NEGATIVE_OBJECTIVE
        assert reserve_res.cvar >= reserve_res.var

    def test_scenario_uncertainty_propagation_missing_objective_fails_closed(self) -> None:
        """
        Verify fail-closed error if any scenario realization is missing a declared objective.
        """
        objectives = [
            ObjectiveDefinition(
                objective_id="loss_mw",
                name="Loss",
                direction=ObjectiveDirection.MINIMIZE,
                unit="MW",
            ),
        ]
        # Missing 'loss_mw' in scenario index 2
        scenarios = [{"loss_mw": 10.0}, {"loss_mw": 11.0}, {"voltage": 1.02}]

        with pytest.raises(ValueError, match="is missing required objective 'loss_mw'"):
            propagate_scenario_uncertainty(
                strategy_id="strat_bad",
                scenario_evaluations=scenarios,
                objectives=objectives,
                confidence_level=0.95,
            )

    def test_counterfactual_uncertainty_propagation_paired_scenarios(self) -> None:
        """
        Verify counterfactual delta uncertainty propagation across paired scenarios:
        Delta f_k(x, s_j) = f_k(x, s_j) - f_k(x0, s_j).
        """
        objectives = [
            ObjectiveDefinition(
                objective_id="cost",
                name="Operational Cost",
                direction=ObjectiveDirection.MINIMIZE,
                unit="kUSD",
            ),
        ]

        # 20 paired scenarios
        # Candidate costs: 100 to 119
        # Baseline costs: 120 to 139
        # Delta (candidate - baseline) is uniformly -20.0 across all scenarios
        cand_scenarios = [{"cost": 100.0 + i} for i in range(20)]
        base_scenarios = [{"cost": 120.0 + i} for i in range(20)]

        results = propagate_counterfactual_uncertainty(
            candidate_strategy_id="cand_reconfiguration",
            baseline_id="base_status_quo",
            candidate_scenario_evaluations=cand_scenarios,
            baseline_scenario_evaluations=base_scenarios,
            objectives=objectives,
            confidence_level=0.95,
        )

        cost_delta_risk = results["cost"]
        # Delta is constant -20.0 -> mean = -20.0, VaR = -20.0, CVaR = -20.0
        assert pytest.approx(cost_delta_risk.mean, abs=1e-6) == -20.0
        assert pytest.approx(cost_delta_risk.var, abs=1e-6) == -20.0
        assert pytest.approx(cost_delta_risk.cvar, abs=1e-6) == -20.0
        assert cost_delta_risk.std_dev == 0.0

    def test_counterfactual_uncertainty_propagation_mismatched_lengths_fail_closed(self) -> None:
        """
        Verify fail-closed rejection if candidate and baseline scenario counts differ.
        """
        objectives = [
            ObjectiveDefinition(
                objective_id="cost",
                name="Cost",
                direction=ObjectiveDirection.MINIMIZE,
                unit="USD",
            ),
        ]
        with pytest.raises(ValueError, match="Mismatched paired scenario counts"):
            propagate_counterfactual_uncertainty(
                "cand",
                "base",
                [{"cost": 10.0}] * 20,
                [{"cost": 12.0}] * 21,
                objectives,
            )


class TestUncertaintySemantics:
    """Semantic distinction between aleatoric stochastic and epistemic bounded representations."""

    def test_uncertainty_parameter_aleatoric_representation(self) -> None:
        """
        Verify representation of aleatory stochastic parameter with Gaussian distribution.
        """
        param = UncertaintyParameter(
            parameter_name="wind_speed_hub",
            uncertainty_type=UncertaintyType.ALEATORY_STOCHASTIC,
            distribution_type=DistributionType.NORMAL_GAUSSIAN,
            parameters={"mean": 12.5, "std_dev": 2.1},
            unit="m/s",
            is_empirically_calibrated=True,
            provenance_digest=VALID_SHA256,
            description="Hub-height anemometer 10-minute aggregate forecast.",
        )

        assert param.uncertainty_type == UncertaintyType.ALEATORY_STOCHASTIC
        assert param.distribution_type == DistributionType.NORMAL_GAUSSIAN
        assert param.is_empirically_calibrated is True
        assert param.provenance_digest == VALID_SHA256

    def test_uncertainty_parameter_epistemic_bounded_interval(self) -> None:
        """
        Verify representation of epistemic uncertainty as a bounded interval without manufactured probabilities.
        """
        param = UncertaintyParameter(
            parameter_name="transformer_thermal_capacity",
            uncertainty_type=UncertaintyType.EPISTEMIC_BOUNDED,
            distribution_type=DistributionType.BOUNDED_INTERVAL_SET,
            parameters={"lower_bound": 85.0, "upper_bound": 115.0},
            unit="MVA",
            is_empirically_calibrated=False,
            provenance_digest=None,
            description="Nameplate degradation derating interval under missing historical oil test logs.",
        )

        assert param.uncertainty_type == UncertaintyType.EPISTEMIC_BOUNDED
        assert param.distribution_type == DistributionType.BOUNDED_INTERVAL_SET
        assert param.is_empirically_calibrated is False
        assert param.provenance_digest is None


class TestDeterminismAndReproducibility:
    """Bitwise identical repeatability over repeated invocations."""

    def test_risk_metrics_determinism_50_iterations(self) -> None:
        """
        Verify that 50 repeated executions produce bitwise identical RiskMetrics.
        """
        # Deterministic sequence
        samples = [float((i * 17) % 31 + 10) for i in range(25)]

        first_res = compute_risk_metrics(
            objective_id="bus_frequency",
            samples=samples,
            confidence_level=0.95,
            unit="Hz",
        )

        for _ in range(49):
            repeat_res = compute_risk_metrics(
                objective_id="bus_frequency",
                samples=samples,
                confidence_level=0.95,
                unit="Hz",
            )
            assert repeat_res.mean == first_res.mean
            assert repeat_res.std_dev == first_res.std_dev
            assert repeat_res.var == first_res.var
            assert repeat_res.cvar == first_res.cvar
            assert repeat_res.robustness_score == first_res.robustness_score

    def test_sensitivity_determinism_50_iterations(self) -> None:
        """
        Verify that 50 repeated executions produce bitwise identical SensitivityMetric.
        """
        first_res = compute_sensitivity(
            objective_id="curtailment",
            parameter_name="load_growth",
            base_objective_value=12.4,
            perturbed_objective_value=15.8,
            base_parameter_value=100.0,
            perturbed_parameter_value=105.0,
            objective_unit="MWh",
            parameter_unit="MW",
        )

        for _ in range(49):
            repeat_res = compute_sensitivity(
                objective_id="curtailment",
                parameter_name="load_growth",
                base_objective_value=12.4,
                perturbed_objective_value=15.8,
                base_parameter_value=100.0,
                perturbed_parameter_value=105.0,
                objective_unit="MWh",
                parameter_unit="MW",
            )
            assert repeat_res.raw_sensitivity == first_res.raw_sensitivity
            assert repeat_res.normalized_elasticity == first_res.normalized_elasticity
