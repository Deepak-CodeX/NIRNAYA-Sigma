"""
Canonical decision records, Four-Eyes governance, and cryptographic provenance hash chaining.
"""

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

__all__ = [
    "GENESIS_PREVIOUS_HASH",
    "assemble_decision_record",
    "assemble_strategy_comparison",
    "canonical_json_dumps",
    "compute_record_hash",
    "is_high_impact_decision",
    "validate_dual_control_signatures",
    "verify_decision_record_chain",
]
