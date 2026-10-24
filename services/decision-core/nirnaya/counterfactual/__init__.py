"""
Counterfactual baseline comparison and regret quantification package.
"""

from nirnaya.counterfactual.comparison import compute_baseline_comparison
from nirnaya.counterfactual.regret import compute_regret_metrics

__all__ = [
    "compute_baseline_comparison",
    "compute_regret_metrics",
]
