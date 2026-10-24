"""
Cryptographic append-only SHA-256 hash chaining and tamper-evident provenance.

Implements ADR-009 canonical decision record hashing and chain verification.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence

from nirnaya.domain.models import (
    SHA256_DIGEST_REGEX,
    DecisionRecord,
)

GENESIS_PREVIOUS_HASH = "sha256:" + "0" * 64


def canonical_json_dumps(data: Any) -> str:
    """
    Serialize data structure to deterministic canonical JSON (RFC 8785 principles).
    Sorted keys, compact separators, UTF-8 encoding.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_record_hash(
    record_id: str,
    problem_id: str,
    comparison_id: str,
    selected_scenario_id: str,
    previous_record_hash: str,
    schema_version: str = "v1.0.0",
    operator_id: str = "",
    primary_signer_id: str = "",
) -> str:
    """
    Compute immutable SHA-256 digest over the canonical decision record tuple:
    SHA256( CanonicalJSON(record_id, problem_id, comparison_id, selected_scenario_id, previous_record_hash, ...) )
    """
    clean_prev = previous_record_hash.strip().lower()
    if not SHA256_DIGEST_REGEX.match(clean_prev):
        raise ValueError(f"previous_record_hash must match pattern '^sha256:[a-f0-9]{{64}}$', got '{previous_record_hash}'")

    digest_payload = {
        "record_id": record_id.strip().lower(),
        "problem_id": problem_id.strip().lower(),
        "comparison_id": comparison_id.strip().lower(),
        "selected_scenario_id": selected_scenario_id.strip().lower(),
        "previous_record_hash": clean_prev,
        "schema_version": schema_version.strip(),
        "operator_id": operator_id.strip(),
        "primary_signer_id": primary_signer_id.strip(),
    }

    serialized = canonical_json_dumps(digest_payload)
    digest_hex = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"sha256:{digest_hex}"


def verify_decision_record_chain(
    records: Sequence[DecisionRecord],
) -> tuple[bool, str]:
    """
    Verify the cryptographic integrity of a sequence of DecisionRecords.

    Checks:
    -------
    1. Each record's internal record_hash matches its recomputed digest.
    2. For records at index >= 1, previous_record_hash strictly matches the record_hash of record[i-1].
    3. Detects any historical tampering or payload alteration.

    Returns:
    --------
    Tuple of (is_valid: bool, narrative_explanation: str).
    """
    if not records:
        return True, "Empty chain: 0 records evaluated."

    for idx, rec in enumerate(records):
        recomputed = compute_record_hash(
            record_id=rec.record_id,
            problem_id=rec.problem_id,
            comparison_id=rec.comparison_id,
            selected_scenario_id=rec.selected_scenario_id,
            previous_record_hash=rec.audit_trail.previous_record_hash,
            schema_version=rec.schema_version,
            operator_id=rec.human_review_log.operator_id,
            primary_signer_id=rec.dual_control_signatures.primary_sign_off.user_id,
        )

        if recomputed != rec.audit_trail.record_hash:
            return (
                False,
                f"Tamper detection: Record hash mismatch at index {idx} (record_id='{rec.record_id}'). "
                f"Recorded='{rec.audit_trail.record_hash}', recomputed='{recomputed}'."
            )

        if idx > 0:
            prev_expected = records[idx - 1].audit_trail.record_hash
            if rec.audit_trail.previous_record_hash != prev_expected:
                return (
                    False,
                    f"Hash chain broken at index {idx}: previous_record_hash '{rec.audit_trail.previous_record_hash}' "
                    f"does not match preceding record's hash '{prev_expected}'."
                )

    return True, f"Cryptographic provenance verified: chain of {len(records)} decision records is tamper-free."
