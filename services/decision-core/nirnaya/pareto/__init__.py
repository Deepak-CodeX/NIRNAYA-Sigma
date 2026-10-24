"""
Pareto multi-objective optimization and dominance analysis engine.
"""

from nirnaya.pareto.dominance import check_pareto_dominance
from nirnaya.pareto.sorting import compute_pareto_comparison

__all__ = [
    "check_pareto_dominance",
    "compute_pareto_comparison",
]
