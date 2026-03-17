"""Auxiliary flux models — RO (Curve Number), DP, CR (teoria.md §5).

Implements:
  §5.1  Surface runoff — SCS Curve Number method with moisture adjustment.
  §5.2  Deep percolation — simple excess and Liu et al. (2006) parametric.
  §5.3  Capillary rise — constant Gmax and Liu et al. (2006) parametric.

All functions are stateless and operate on scalar floats.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# §5.1 — Surface runoff (SCS Curve Number)
# ---------------------------------------------------------------------------

# AMC class boundaries (CN adjustment ratios):
#   AMC I  (dry):  CN_I  = CN_II / (2.281 - 0.01281 * CN_II)   [USDA NRCS]
#   AMC III (wet): CN_III = CN_II / (0.427 + 0.00573 * CN_II)
_AMC_I_A = 2.281
_AMC_I_B = 0.01281
_AMC_III_A = 0.427
_AMC_III_B = 0.00573


def cn_from_amc(cn2: float, *, amc_class: int) -> float:
    """Convert a CN_II number to AMC class I or III.

    Args:
        cn2: Curve Number for average antecedent moisture condition (AMC II).
        amc_class: Target moisture class — 1 (dry) or 3 (wet).

    Returns:
        Adjusted Curve Number.

    Raises:
        ValueError: If *amc_class* is not 1 or 3.
    """
    if amc_class == 1:
        return cn2 / (_AMC_I_A - _AMC_I_B * cn2)
    if amc_class == 3:
        return cn2 / (_AMC_III_A + _AMC_III_B * cn2)
    msg = f"amc_class must be 1 or 3, got {amc_class}"
    raise ValueError(msg)


def adjust_cn_for_moisture(cn2: float, dei: float, tew: float) -> float:
    """Adjust CN_II to local antecedent moisture based on surface depletion.

    Linearly interpolates between AMC I (dry, ``dei == tew``) and
    AMC III (wet, ``dei == 0``).  This links surface soil moisture
    state to the curve number adjustment (teoria.md §5.1).

    Args:
        cn2: Base Curve Number, AMC II.
        dei: Current surface evaporative layer depletion [mm].
        tew: Total evaporable water [mm].

    Returns:
        Moisture-adjusted Curve Number.
    """
    cn1 = cn_from_amc(cn2, amc_class=1)
    cn3 = cn_from_amc(cn2, amc_class=3)

    # Wetness fraction: 1.0 when field capacity (dei=0), 0.0 when fully dry (dei=tew)
    wetness = 1.0 - max(0.0, min(1.0, dei / max(1e-9, tew)))
    return cn1 + wetness * (cn3 - cn1)


def compute_runoff_cn(precip: float, cn: float) -> float:
    """Compute surface runoff using the SCS Curve Number method (teoria.md §5.1).

    ``q = (P - 0.2*S)² / (P + 0.8*S)``  where  ``S = 25400/CN - 254``  [mm]

    Args:
        precip: Daily precipitation [mm].
        cn: Curve Number (possibly moisture-adjusted).

    Returns:
        Surface runoff [mm]. Returns 0.0 when P ≤ 0.2*S (no runoff threshold).
    """
    if precip <= 0.0:
        return 0.0
    cn_safe = max(1.0, min(99.99, cn))  # avoid division by zero
    s = 25400.0 / cn_safe - 254.0  # potential maximum retention [mm]
    ia = 0.2 * s  # initial abstraction
    if precip <= ia:
        return 0.0
    return (precip - ia) ** 2 / (precip + 0.8 * s)


# ---------------------------------------------------------------------------
# §5.2 — Deep percolation
# ---------------------------------------------------------------------------


def compute_dp_simple(dr_before_dp: float) -> float:
    """Compute deep percolation using the simple excess-water method (teoria.md §5.2).

    Any water that would make the root zone exceed field capacity
    (i.e. ``Dr < 0``) immediately percolates.

    Note: the simulation orchestrator handles this via
    :func:`~simdualkc.water_balance.update_root_zone_depletion`.
    This function is provided for explicit calls when the orchestrator
    computes ``dr_new`` before capping.

    Args:
        dr_before_dp: Root-zone depletion *before* capping at 0 [mm].
            Negative values indicate excess water.

    Returns:
        Deep percolation [mm]. Returns 0.0 when dr_before_dp >= 0.
    """
    return max(0.0, -dr_before_dp)


def compute_dp_parametric(storage: float, a_d: float, b_d: float) -> float:
    """Compute deep percolation via Liu et al. (2006) parametric model (teoria.md §5.2).

    ``DP = a_D * Storage^b_D``

    Args:
        storage: Current soil water storage above the drainage threshold [mm].
        a_d: Empirical coefficient *a* dependent on soil texture [—].
        b_d: Empirical exponent *b* dependent on soil texture [—].

    Returns:
        Deep percolation [mm]. Returns 0.0 for non-positive storage.
    """
    if storage <= 0.0:
        return 0.0
    return a_d * (storage**b_d)


# ---------------------------------------------------------------------------
# §5.3 — Capillary rise
# ---------------------------------------------------------------------------


def compute_cr_constant(gmax: float, dr: float, raw: float) -> float:
    """Compute capillary rise using the constant Gmax approach (teoria.md §5.3).

    The full Gmax applies when the root zone is stressed (``Dr > RAW``).
    When the soil is adequately moist (``Dr ≤ RAW``), CR is reduced
    proportionally to prevent unrealistic upward flux.

    Args:
        gmax: Maximum daily capillary rise rate [mm/day].
        dr: Root-zone depletion [mm].
        raw: Readily available water [mm].

    Returns:
        Capillary rise [mm/day].
    """
    if dr <= 0.0:
        return 0.0
    if dr >= raw:
        return gmax
    # Partial upward flux proportional to stress level
    return gmax * (dr / max(1e-9, raw))


def compute_cr_parametric(
    z_wt: float,
    lai: float,
    a_c: float,
    b_c: float,
    c_c: float,
    d_c: float,
) -> float:
    """Compute capillary rise via Liu et al. (2006) parametric model (teoria.md §5.3).

    The functional form is typically:

    ``CR = a_c / (z_wt^b_c) * exp(-c_c * LAI^d_c)``

    The exact empirical coefficients are texture/depth-dependent and
    must be supplied by the caller from lookup tables.

    Args:
        z_wt: Distance from root zone base to water table [m].
        lai: Leaf area index [m²/m²].
        a_c: Empirical coefficient *a* [—].
        b_c: Empirical exponent for depth [—].
        c_c: Empirical coefficient *c* for LAI term [—].
        d_c: Empirical exponent for LAI [—].

    Returns:
        Capillary rise [mm/day]. Returns 0.0 for non-positive z_wt.
    """
    if z_wt <= 0.0:
        return 0.0
    return (a_c / (z_wt**b_c)) * math.exp(-c_c * lai**d_c)
