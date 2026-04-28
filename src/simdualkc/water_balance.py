"""Root zone water balance and water stress.

All functions are stateless and operate on scalar floats.
"""

from simdualkc.models import SoilLayer


def compute_taw(theta_fc: float, theta_wp: float, zr: float) -> float:
    """Compute Total Available Water in the root zone.

    ``TAW = 1000 * (θ_FC - θ_WP) * Zr``

    Args:
        theta_fc: Volumetric water content at field capacity [m³/m³].
        theta_wp: Volumetric water content at wilting point [m³/m³].
        zr: Root zone depth [m].

    Returns:
        TAW [mm].
    """
    return 1000.0 * (theta_fc - theta_wp) * zr


def compute_taw_multilayer(layers: list[SoilLayer], zr: float) -> float:
    """Compute Total Available Water by integrating layers up to root depth.

    TAW = Σ[1000 × (θ_FC,i - θ_WP,i) × Δz_i,active]

    Where Δz_i,active is the portion of layer i within the root zone.
    As root depth Zr grows, TAW increases as more layers contribute.

    Args:
        layers: Soil layers ordered by bottom depth [m]. Each layer has
            depth_m (bottom), theta_fc, theta_wp.
        zr: Current root zone depth [m].

    Returns:
        TAW [mm].
    """
    if zr <= 0.0:
        return 0.0

    taw = 0.0
    depth_top = 0.0

    for layer in layers:
        depth_bottom = layer.depth_m
        if depth_top >= zr:
            break
        # Active thickness: portion of this layer within root zone
        dz_active = min(depth_bottom, zr) - depth_top
        if dz_active > 0:
            taw += 1000.0 * (layer.theta_fc - layer.theta_wp) * dz_active
        depth_top = depth_bottom

    return taw


def compute_raw(taw: float, p: float) -> float:
    """Compute Readily Available Water.

    ``RAW = p * TAW``

    Args:
        taw: Total available water [mm].
        p: Fraction of TAW that a crop can extract before stress begins [0–1].

    Returns:
        RAW [mm].
    """
    return p * taw


def compute_ks_salinity(ec_e: float, ec_threshold: float, b: float, k_y: float) -> float:
    """Compute the salinity stress coefficient Ks_salinity (FAO-56 / Mass-Hoffman).

    ``Ks_salinity = 1 - (b / (100 * Ky)) * (ECe - EC_threshold)``

    Args:
        ec_e: Current soil salinity ECe [dS/m].
        ec_threshold: Crop specific salinity threshold [dS/m].
        b: Yield loss slope b [% per dS/m].
        k_y: Yield response factor [—].

    Returns:
        Salinity stress multiplier Ks_salinity [0–1].
    """
    if ec_e <= ec_threshold:
        return 1.0

    k_y_safe = max(0.001, k_y)
    ks_salinity = 1.0 - (b / (100.0 * k_y_safe)) * (ec_e - ec_threshold)
    return max(0.0, min(1.0, ks_salinity))


def compute_ks(dr: float, taw: float, raw: float, p: float) -> float:
    """Compute the water stress coefficient Ks.

    - If ``Dr ≤ RAW``: ``Ks = 1`` (no stress).
    - If ``Dr > RAW``: ``Ks = (TAW - Dr) / ((1 - p) * TAW)``.
    - If ``Dr ≥ TAW``: ``Ks = 0`` (wilting point reached).

    Args:
        dr: Root-zone depletion at the *end of the previous day* [mm].
        taw: Total available water [mm].
        raw: Readily available water [mm].
        p: Depletion fraction for no stress [—].

    Returns:
        Ks [0–1].
    """
    if dr <= raw:
        return 1.0
    if dr >= taw:
        return 0.0
    denominator = (1.0 - p) * taw
    if denominator <= 0.0:
        return 0.0
    return max(0.0, (taw - dr) / denominator)


def compute_etc_act(ks: float, kcb: float, ke: float, eto: float) -> float:
    """Compute actual crop evapotranspiration.

    ``ETc_act = (Ks * Kcb + Ke) * ETo``

    Args:
        ks: Water stress coefficient [—].
        kcb: Adjusted basal crop coefficient [—].
        ke: Soil evaporation coefficient [—].
        eto: Reference evapotranspiration [mm/day].

    Returns:
        ETc_act [mm/day].
    """
    return (ks * kcb + ke) * eto


def update_root_zone_depletion(
    dr_prev: float,
    precip: float,
    ro: float,
    irrig: float,
    cr: float,
    etc_act: float,
    taw: float,
) -> tuple[float, float]:
    """Update root-zone soil water depletion for day i.

    ``Dr,i = Dr,i-1 - (P - RO) - I - CR + ETc_act + DP``

    Deep percolation (DP) occurs when inputs push Dr below zero (soil
    exceeds field capacity). The function resolves DP implicitly:
    any negative Dr before capping is returned as DP and Dr is reset to 0.

    Args:
        dr_prev: Root-zone depletion at end of day i-1 [mm].
        precip: Precipitation [mm].
        ro: Surface runoff [mm].
        irrig: Net irrigation applied [mm].
        cr: Capillary rise contribution [mm].
        etc_act: Actual crop ET (computed for the same day) [mm].
        taw: Total available water for the current root depth [mm].

    Returns:
        ``(dr_new, dp)`` — updated depletion [mm] and deep percolation [mm].
    """
    net_precip = max(0.0, precip - ro)
    dr_new = dr_prev - net_precip - irrig - cr + etc_act

    # Excess water beyond field capacity becomes deep percolation
    dp = max(0.0, -dr_new)
    dr_new = max(0.0, min(dr_new, taw))

    return dr_new, dp
