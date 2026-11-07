"""Monte Carlo exposure matrix X (spec A2.5, v2 empirical-Bayes prior)."""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from waykin.constants import DIRICHLET_KAPPA, N_DRAWS, PRIOR_STRENGTH, SEED


def simulate(A: sp.csr_matrix, counts: np.ndarray, n_draws: int = N_DRAWS, seed: int = SEED, radius_m: int = 100,
             kappa: float = DIRICHLET_KAPPA, prior_strength: float = PRIOR_STRENGTH) -> np.ndarray:
    """Return X with shape (E, n_draws), float32.

    `counts` has one entry per row of A: published counts first, then zeros for the prior nodes.
    Each draw samples
      * a rate per location from the Gamma posterior Gamma(count + alpha, rate = 1 + prior_strength),
        where alpha = prior_strength * (mean count per location): honest about small counts, and a
        street with no reports gets a small uncertain rate instead of a certain zero;
      * a Dirichlet split of each location over its nearby edges around the allocation weights:
        honest about police data being snapped to intersections.
    With this prior the expected total exposure equals the observed total.
    """
    A = sp.csr_matrix(A)
    L, E = A.shape
    counts = np.asarray(counts, dtype=np.float64)
    if counts.shape != (L,):
        raise ValueError("counts must have one entry per row of A")
    row_of_nnz = np.repeat(np.arange(L), np.diff(A.indptr))
    mu = max(counts.sum() / max(L, 1), 1e-6)
    alpha = prior_strength * mu
    scale = 1.0 / (1.0 + prior_strength)
    rng = np.random.default_rng([seed, radius_m])
    X = np.empty((E, n_draws), dtype=np.float32)
    dir_shape = kappa * A.data + 1e-3
    for s in range(n_draws):
        lam = rng.gamma(shape=counts + alpha, scale=scale)
        g = rng.gamma(shape=dir_shape, scale=1.0)
        row_sum = np.bincount(row_of_nnz, weights=g, minlength=L)
        g_norm = g / row_sum[row_of_nnz]
        X[:, s] = np.bincount(A.indices, weights=g_norm * lam[row_of_nnz], minlength=E)
    return X
