"""
Dual-control Four-Eyes authorization governance and high-impact classification.

Enforces Separation of Duties (SoD) across Requester, Reviewer, and Approver roles
per ADR-005 and ADR-013.
"""

from __future__ import annotations

from typing import Any

from nirnaya.domain.models import (
    CandidateStrategy,
    DualControlSignatures,
    HumanReviewLog,
)


def is_high_impact_decision(
    strategy: CandidateStrategy,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """
    Determine whether an operational candidate strategy constitutes a safety-critical
    high-impact action requiring mandatory secondary dual-control sign-off.

    High-Impact Thresholds (ADR-005):
    ---------------------------------
    1. Emergency load shedding > 10.0 MW (e.g. unserved energy or load shed metric > 10 MW).
    2. Intentional bus sectionalizing or transmission line tripping.
    3. Operating within emergency voltage bands (< 0.95 p.u. or > 1.05 p.u.).
    """
    meta = metadata or strategy.metadata or {}

    # 1. Load shedding check (> 10 MW)
    for key in ("load_shed_mw", "unserved_energy_mw", "shed_mw", "eue_mw"):
        if key in strategy.objectives and strategy.objectives[key] > 10.0:
            return True
        if key in meta and float(meta[key]) > 10.0:
            return True

    # 2. Sectionalizing or line switching checks
    if meta.get("sectionalizing", False) or meta.get("is_emergency", False):
        return True
    if meta.get("switching_actions_count", 0) > 0 and meta.get("requires_dual_control", False):
        return True

    # 3. Voltage limit excursions into emergency bands
    for key, val in strategy.objectives.items():
        if "voltage" in key.lower() or "v_pu" in key.lower():
            if val < 0.95 or val > 1.05:
                return True

    return False


def validate_dual_control_signatures(
    strategy: CandidateStrategy,
    review_log: HumanReviewLog,
    dual_control: DualControlSignatures,
    is_high_impact: bool | None = None,
) -> None:
    """
    Validate dual-control signatures against Separation of Duties (SoD) invariants.

    Fail-Closed Rules:
    ------------------
    - If decision is high-impact, secondary_sign_off is strictly required.
    - If secondary_sign_off is present:
      - primary_sign_off.user_id must NOT equal secondary_sign_off.user_id (cannot sign own secondary approval).
      - secondary_sign_off.user_id must NOT equal review_log.operator_id (Approver cannot be the same as Reviewer).
    """
    high_impact = is_high_impact if is_high_impact is not None else is_high_impact_decision(strategy)

    if high_impact and dual_control.secondary_sign_off is None:
        raise ValueError(
            f"Dual-control policy violation: Strategy '{strategy.strategy_id}' is classified as "
            "HIGH-IMPACT (>10 MW shedding, emergency voltage, or bus sectionalizing). "
            "A secondary authorized signature is mandatory."
        )

    if dual_control.secondary_sign_off is not None:
        primary_id = dual_control.primary_sign_off.user_id.strip()
        secondary_id = dual_control.secondary_sign_off.user_id.strip()
        reviewer_id = review_log.operator_id.strip()

        if primary_id.lower() == secondary_id.lower():
            raise ValueError(
                f"Separation of duties violation: Primary signer '{primary_id}' and secondary signer "
                f"'{secondary_id}' cannot be the same individual."
            )

        if secondary_id.lower() == reviewer_id.lower():
            raise ValueError(
                f"Separation of duties violation: Secondary approver '{secondary_id}' cannot be "
                f"the same individual as the technical reviewer '{reviewer_id}'."
            )
