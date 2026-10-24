"""
Mathematical risk quantification and tail-loss estimation.

Provides pure-function implementations for Value at Risk (VaR),
Conditional Value at Risk (CVaR / Expected Shortfall), and empirical
convergence diagnostics under stochastic uncertainty.
"""

from __future__ import annotations

import math
from typing import Sequence

from nirnaya.domain.enums import LossConvention
from nirnaya.domain.models import (
    IDENTIFIER_REGEX,
    SHA256_DIGEST_REGEX,
    RiskMetrics,
    validate_finite_number,
)


def compute_risk_metrics(
    objective_id: str,
    samples: Sequence[float],
    confidence_level: float = 0.95,
    unit: str = "",
    loss_convention: LossConvention = LossConvention.DIRECT_OBJECTIVE,
    loss_threshold: float | None = None,
    is_empirically_calibrated: bool = False,
    provenance_digest: str | None = None,
) -> RiskMetrics:
    """
    Compute rigorous statistical risk metrics and tail loss for an objective distribution.

    Mathematical Definitions:
    -------------------------
    1. Loss Convention:
       - DIRECT_OBJECTIVE (Minimization): Loss L_i = f_{k, i}. Higher objective is worse.
       - NEGATIVE_OBJECTIVE (Maximization): Loss L_i = -f_{k, i}. Lower objective is worse.
    2. Sample Mean:
       mu = (1 / N) * sum(f_{k, i})
    3. Sample Standard Deviation (Bessel-corrected, N - 1 dof):
       sigma = sqrt( (1 / (N - 1)) * sum((f_{k, i} - mu)^2) )
    4. Standard Error of the Mean:
       SEM = sigma / sqrt(N)
    5. Convergence Criterion:
       Converged if (SEM / |mu|) <= 0.05 (for |mu| > 1e-9).
    6. Value at Risk (VaR_alpha):
       Let sorted losses be L_(1) <= L_(2) <= ... <= L_(N).
       Rank index: k_alpha = ceil(alpha * N).
       VaR_alpha = L_(k_alpha).
    7. Conditional Value at Risk (CVaR_alpha / Expected Shortfall):
       Tail expectation of losses exceeding or equal to VaR_alpha:
       CVaR_alpha = (1 / (N - k_alpha + 1)) * sum_{i = k_alpha}^N L_(i).
       Mathematical Invariant: CVaR_alpha >= VaR_alpha for all distributions.
    8. Robustness Score:
       If loss_threshold is specified:
         Score = (1 / N) * count(L_i <= loss_threshold) in [0.0, 1.0].
       Else:
         Score = (k_alpha) / N in [0.0, 1.0].

    Fail-Closed Rules:
    ------------------
    - If confidence_level is not strictly in (0.0, 1.0), raises ValueError.
    - If sample size N < 2, raises ValueError.
    - If sample size N < ceil(1 / (1 - alpha)), raises ValueError (insufficient samples for tail).
    - If any sample value is non-finite (NaN, inf, -inf), raises ValueError.
    - If is_empirically_calibrated is True without a valid provenance_digest, raises ValueError.
    """
    clean_id = objective_id.strip()
    if not clean_id or not IDENTIFIER_REGEX.match(clean_id):
        raise ValueError(f"objective_id must match pattern '^[A-Za-z0-9_.-]+$', got '{objective_id}'")

    if not (0.0 < confidence_level < 1.0):
        raise ValueError(
            f"confidence_level must be strictly between 0.0 and 1.0, got {confidence_level}"
        )

    n = len(samples)
    if n < 2:
        raise ValueError(f"Sample size N must be at least 2 to compute variance, got {n}")

    min_required_samples = math.ceil(1.0 / (1.0 - confidence_level))
    if n < min_required_samples:
        raise ValueError(
            f"Insufficient sample size N={n} for confidence level {confidence_level}. "
            f"Tail estimation requires at least ceil(1 / (1 - alpha)) = {min_required_samples} samples."
        )

    # Validate finite values
    validated_samples: list[float] = []
    for idx, s in enumerate(samples):
        validated_samples.append(validate_finite_number(float(s), f"samples[{idx}]"))

    # Empirical calibration validation
    if is_empirically_calibrated:
        if not provenance_digest or not SHA256_DIGEST_REGEX.match(provenance_digest.strip()):
            raise ValueError(
                "Uncalibrated claim: cannot claim empirical calibration without a valid "
                f"cryptographic provenance_digest (got '{provenance_digest}')."
            )

    # Compute loss mapping
    if loss_convention == LossConvention.DIRECT_OBJECTIVE:
        losses = [val for val in validated_samples]
    elif loss_convention == LossConvention.NEGATIVE_OBJECTIVE:
        losses = [-val for val in validated_samples]
    else:
        raise ValueError(f"Unsupported loss convention: {loss_convention}")

    # Objective statistics
    mean_val = sum(validated_samples) / n
    variance = sum((x - mean_val) ** 2 for x in validated_samples) / (n - 1)
    std_dev = math.sqrt(variance)
    sem = std_dev / math.sqrt(n)

    if abs(mean_val) > 1e-9:
        sample_converged = (sem / abs(mean_val)) <= 0.05
    else:
        sample_converged = sem <= 1e-4

    # 95% Quantile Interval of the objective [q_0.025, q_0.975]
    sorted_obj = sorted(validated_samples)
    idx_low = max(0, min(n - 1, math.floor(0.025 * (n - 1))))
    idx_high = max(0, min(n - 1, math.ceil(0.975 * (n - 1))))
    ci_95 = (float(sorted_obj[idx_low]), float(sorted_obj[idx_high]))

    # Tail Risk (VaR and CVaR)
    sorted_losses = sorted(losses)
    # 1-based rank: ceil(alpha * N)
    k_alpha_1based = math.ceil(confidence_level * n)
    # Python 0-based index:
    k_alpha_0based = min(n - 1, max(0, k_alpha_1based - 1))

    var_val = float(sorted_losses[k_alpha_0based])

    tail_losses = sorted_losses[k_alpha_0based:]
    cvar_val = float(sum(tail_losses) / len(tail_losses))

    # Invariant enforcement
    if cvar_val < var_val:
        cvar_val = var_val

    # Robustness score calculation
    if loss_threshold is not None:
        threshold_finite = validate_finite_number(float(loss_threshold), "loss_threshold")
        satisfying_count = sum(1 for loss in losses if loss <= threshold_finite)
        robustness_score = float(satisfying_count / n)
    else:
        # Default robustness: proportion of samples below VaR_alpha
        robustness_score = float((k_alpha_0based + 1) / n)

    robustness_score = max(0.0, min(1.0, robustness_score))

    explanation = (
        f"Objective '{clean_id}': N={n} realizations, mean={mean_val:.4g} {unit}, "
        f"std={std_dev:.4g}, SEM={sem:.4g} (converged={sample_converged}). "
        f"VaR_{confidence_level:.2f}={var_val:.4g} {unit}, "
        f"CVaR_{confidence_level:.2f}={cvar_val:.4g} {unit} under {loss_convention.value}. "
        f"Robustness score={robustness_score:.4f}. Calibrated={is_empirically_calibrated}."
    )

    return RiskMetrics(
        objective_id=clean_id,
        confidence_level=confidence_level,
        var=var_val,
        cvar=cvar_val,
        unit=unit.strip() if unit else "dimensionless",
        sample_size=n,
        mean=mean_val,
        std_dev=std_dev,
        standard_error=sem,
        sample_converged=sample_converged,
        confidence_interval_95=ci_95,
        robustness_score=robustness_score,
        loss_convention=loss_convention,
        is_empirically_calibrated=is_empirically_calibrated,
        explanation=explanation,
    )
