"""Soil evaporation equations.

Implements the two-fraction SIMDualKc evaporation approach:
  - fewi: soil wet by irrigation AND precipitation
  - fewp: soil wet by precipitation only
"""


def compute_few(
    fc: float,
    fw: float,
    f_mulch: float = 0.0,
    kr_mulch: float = 1.0,
) -> tuple[float, float]:
    """Compute the two evaporative soil surface fractions.

    Args:
        fc: Fractional soil cover by the canopy [0–1].
        fw: Fraction of soil wetted by the irrigation system [0–1].
            Use 1.0 for sprinkler or flood, < 1.0 for drip.
        f_mulch: Fraction of the total ground surface covered by mulch [0–1].
        kr_mulch: Evaporation reduction factor for the mulched area [0–1].
            (e.g., 0.5 for organic, 0.1 for plastic. 1.0 means no reduction).

    Returns:
        ``(fewi, fewp)`` where:
          - ``fewi``: fraction wetted by irrigation AND precipitation [0–1].
          - ``fewp``: fraction wetted by precipitation only [0–1].
    """
    exposed = max(0.0, 1.0 - fc)

    # Mulch typically covers the exposed soil. We cap actual mulch cover to exposed.
    f_m_actual = min(exposed, f_mulch)

    # The effective exposed area is reduced by the mulch cover weighted by its
    # effectiveness (where kr_mulch=1.0 means no reduction, kr_mulch<1 means reduction).
    effective_exposed = exposed - f_m_actual * (1.0 - kr_mulch)
    effective_exposed = max(0.0, effective_exposed)

    fewi = min(effective_exposed, fw)
    fewp = max(0.0, effective_exposed - fewi)
    return fewi, fewp


def compute_kc_max(
    kcb: float,
    u2: float,
    rh_min: float,
    h: float,
) -> float:
    """Compute the upper limit for Kc.

    ``Kc_max = max({1.2 + [0.04(u2-2) - 0.004(RHmin-45)](h/3)^0.3}, {Kcb + 0.05})``

    Args:
        kcb: Current adjusted basal crop coefficient [—].
        u2: Wind speed at 2 m [m/s].
        rh_min: Minimum relative humidity [%].
        h: Plant height [m].

    Returns:
        Kc_max [—].
    """
    kc_base = 1.2 + (0.04 * (u2 - 2.0) - 0.004 * (rh_min - 45.0)) * (h / 3.0) ** 0.3
    return max(kc_base, kcb + 0.05)


def compute_evaporation_weight(
    fewi: float,
    fewp: float,
    tew: float,
    dei: float,
    dep: float,
) -> float:
    """Compute the energy partitioning weight W between the two fractions.

    ``W = 1 / (1 + fewp*(TEW - Dep) / (fewi*(TEW - Dei)))``

    When ``fewi == 0`` (no irrigation), returns 0.0 so that all energy
    goes to the precipitation-only fraction.

    Args:
        fewi: Irrigated+precip evaporative fraction [—].
        fewp: Precip-only evaporative fraction [—].
        tew: Total evaporable water [mm].
        dei: Current depletion of the irrigated fraction [mm].
        dep: Current depletion of the precipitation-only fraction [mm].

    Returns:
        W [0–1].
    """
    if fewi <= 0.0:
        return 0.0
    if fewp <= 0.0:
        return 1.0
    denom_ratio = (fewp * max(0.0, tew - dep)) / (fewi * max(1e-9, tew - dei))
    return 1.0 / (1.0 + denom_ratio)


def compute_kr(tew: float, rew: float, de_prev: float) -> float:
    """Compute the evaporation reduction coefficient Kr.

    ``Kr = (TEW - De) / (TEW - REW)``  clipped to [0, 1].

    When ``De <= REW``, stage-1 evaporation is at potential (Kr = 1).
    When ``De == TEW``, the layer is completely dry (Kr = 0).

    Args:
        tew: Total evaporable water [mm].
        rew: Readily evaporable water (stage-1 threshold) [mm].
        de_prev: Depletion of this fraction at the *end of the previous day* [mm].

    Returns:
        Kr [0–1].
    """
    if de_prev <= rew:
        return 1.0
    value = (tew - de_prev) / max(1e-9, tew - rew)
    return max(0.0, min(1.0, value))


def compute_ke(
    kri: float,
    krp: float,
    w: float,
    kc_max: float,
    kcb: float,
    fewi: float,
    fewp: float,
) -> tuple[float, float, float]:
    """Compute soil evaporation coefficients for both fractions.

    ``Kei = Kri * W * (Kc_max - Kcb)  ≤  fewi * Kc_max``
    ``Kep = Krp * (1-W) * (Kc_max - Kcb) ≤ fewp * Kc_max``

    Args:
        kri: Evaporation reduction coeff for the irrigated fraction [—].
        krp: Evaporation reduction coeff for the precip-only fraction [—].
        w: Energy-partitioning weight from :func:`compute_evaporation_weight` [—].
        kc_max: Upper limit for Kc [—].
        kcb: Basal crop coefficient [—].
        fewi: Irrigated+precip evaporative fraction [—].
        fewp: Precip-only evaporative fraction [—].

    Returns:
        ``(kei, kep, ke)`` — individual and total soil evaporation coefficients.
    """
    energy_available = max(0.0, kc_max - kcb)
    kei = kri * w * energy_available
    kei = min(kei, fewi * kc_max)

    kep = krp * (1.0 - w) * energy_available
    kep = min(kep, fewp * kc_max)

    return kei, kep, kei + kep


def update_evaporative_depletion(
    de_prev: float,
    precip: float,
    ro: float,
    irrig: float,
    fw: float,
    e_frac: float,
    few: float,
    tew: float,
    *,
    is_irrigated_fraction: bool,
) -> tuple[float, float]:
    """Update depletion of one evaporative layer fraction for day j.

    For the **irrigated fraction** (fewi)::

        De, i, j = De, i, j - 1 - (P - RO) - I / fw + Ei / fewi + DPe, i

    For the **precipitation-only fraction** (fewp)::

        De, p, j = De, p, j - 1 - (P - RO) + Ep / fewp + DPe, p

    Args:
        de_prev: Depletion at the end of day j-1 [mm].
        precip: Precipitation [mm].
        ro: Surface runoff [mm].
        irrig: Net irrigation applied [mm] (0 if no irrigation on this day).
        fw: Fraction of soil wetted by irrigation [—].
        e_frac: Evaporation from this specific fraction: E = K_e_frac * ETo [mm].
        few: Evaporative fraction area (fewi or fewp) [—].
        tew: Total evaporable water [mm].
        is_irrigated_fraction: ``True`` for the fewi fraction, ``False`` for fewp.

    Returns:
        ``(de_new, dp_e)`` — updated depletion [mm] and deep percolation
        from the evaporative layer [mm].
    """
    net_precip = max(0.0, precip - ro)
    evap_term = e_frac / max(1e-9, few) if few > 0.0 else 0.0

    de_new = de_prev - net_precip + evap_term
    if is_irrigated_fraction:
        irrig_term = irrig / max(1e-9, fw) if fw > 0.0 else 0.0
        de_new -= irrig_term

    # Deep percolation from the evaporative layer
    dp_e = max(0.0, -de_new)  # excess water beyond field capacity
    de_new = max(0.0, min(de_new, tew))

    return de_new, dp_e
