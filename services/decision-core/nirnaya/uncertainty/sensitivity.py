"""
Parameter sensitivity analysis and elasticity quantification.

Provides deterministic first-order gradient sensitivity (dObj / dParam)
and normalized elasticity under reproducible parameter perturbations.
"""

from __future__ import annotations

import math

from nirnaya.domain.models import (
    IDENTIFIER_REGEX,
    SensitivityMetric,
    validate_finite_number,
)


def compute_sensitivity(
    objective_id: str,
    parameter_name: str,
    base_objective_value: float,
    perturbed_objective_value: float,
    base_parameter_value: float,
    perturbed_parameter_value: float,
    objective_unit: str = "",
    parameter_unit: str = "",
) -> SensitivityMetric:
    """
    Compute first-order parameter sensitivity and normalized elasticity.

    Mathematical Definitions:
    -------------------------
    1. Parameter Perturbation:
       Delta p = p_perturbed - p_0
    2. Objective Response:
       Delta f_k = f_{k, perturbed} - f_{k, 0}
    3. Raw Sensitivity (First-Order Gradient):
       S = Delta f_k / Delta p
    4. Normalized Elasticity (Dimensionless Sensitivity Index):
       epsilon = (Delta f_k / f_{k, 0}) / (Delta p / p_0) = S * (p_0 / f_{k, 0})
       (Defined if and only if |p_0| > 1e-12 and |f_{k, 0}| > 1e-12; otherwise None).

    Fail-Closed Rules:
    ------------------
    - Rejects invalid identifiers.
    - Rejects non-finite values for base or perturbed values.
    - Rejects zero parameter perturbation (|Delta p| < 1e-15).
    """
    clean_obj_id = objective_id.strip()
    if not clean_obj_id or not IDENTIFIER_REGEX.match(clean_obj_id):
        raise ValueError(f"objective_id must match pattern '^[A-Za-z0-9_.-]+$', got '{objective_id}'")

    clean_param_name = parameter_name.strip()
    if not clean_param_name or not IDENTIFIER_REGEX.match(clean_param_name):
        raise ValueError(f"parameter_name must match pattern '^[A-Za-z0-9_.-]+$', got '{parameter_name}'")

    f0 = validate_finite_number(float(base_objective_value), "base_objective_value")
    f_pert = validate_finite_number(float(perturbed_objective_value), "perturbed_objective_value")
    p0 = validate_finite_number(float(base_parameter_value), "base_parameter_value")
    p_pert = validate_finite_number(float(perturbed_parameter_value), "perturbed_parameter_value")

    delta_p = p_pert - p0
    if abs(delta_p) < 1e-15:
        raise ValueError(
            f"Parameter perturbation delta for '{clean_param_name}' is numerically zero "
            f"(|Delta p| = {abs(delta_p):.4e} < 1e-15). Cannot compute gradient."
        )

    delta_f = f_pert - f0
    raw_sens = float(delta_f / delta_p)

    # Elasticity: defined when base parameter and base objective are non-zero
    if abs(p0) > 1e-12 and abs(f0) > 1e-12:
        elasticity: float | None = float(raw_sens * (p0 / f0))
    else:
        elasticity = None

    # Construct unit string
    clean_obj_u = objective_unit.strip()
    clean_param_u = parameter_unit.strip()
    if clean_obj_u and clean_param_u:
        unit_str = f"{clean_obj_u}/{clean_param_u}"
    elif clean_obj_u:
        unit_str = clean_obj_u
    else:
        unit_str = "dimensionless"

    if elasticity is not None:
        explanation = (
            f"Sensitivity of '{clean_obj_id}' to '{clean_param_name}': "
            f"dF/dP = {raw_sens:.4g} {unit_str}, normalized elasticity = {elasticity:.4g}."
        )
    else:
        explanation = (
            f"Sensitivity of '{clean_obj_id}' to '{clean_param_name}': "
            f"dF/dP = {raw_sens:.4g} {unit_str} (elasticity undefined due to zero baseline)."
        )

    return SensitivityMetric(
        objective_id=clean_obj_id,
        parameter_name=clean_param_name,
        raw_sensitivity=raw_sens,
        normalized_elasticity=elasticity,
        unit=unit_str,
        explanation=explanation,
    )
