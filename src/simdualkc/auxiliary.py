"""Auxiliary flux models — RO (Curve Number), DP, CR.

All functions are stateless and operate on scalar floats.
"""

import datetime
import math
from pathlib import Path

import pandas as pd

from simdualkc.models import ClimateRecord

# AMC class boundaries (CN adjustment ratios):
#   AMC I  (dry):  CN_I  = CN_II / (2.281 - 0.01281 * CN_II)   [USDA NRCS]
#   AMC III (wet): CN_III = CN_II / (0.427 + 0.00573 * CN_II)
_AMC_I_A = 2.281
_AMC_I_B = 0.01281
_AMC_III_A = 0.427
_AMC_III_B = 0.00573

# Liu et al. (2006) parametric CR fallback constants
_CR_DW_STEADY_THRESHOLD_M = 3.0  # depth limit for a2*Dw^b2 steady storage
# Ws fallback for Dw > 3 m: Liu 2006 Eq. 5 fit gives 320.57*Dw^-0.2705 ≈ 240 mm constant.
# Previous values (3.57, -0.705) were a transcription error producing ~2 mm instead of ~240 mm.
_CR_WS_FALLBACK_A = 320.57
_CR_WS_FALLBACK_B = -0.2705
_CR_ETM_THRESHOLD_MM_DAY = 4.0  # ETm limit for low-stress parametric branch
_CR_DWC_FALLBACK_M = 1.4  # fixed critical depth when ETm > 4 mm/day
_CR_K_FALLBACK_NUMERATOR = 3.8  # transpiration factor numerator when ETm > 4 mm/day


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
    state to the curve number adjustment.

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
    """Compute surface runoff using the SCS Curve Number method.

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


def compute_dp_simple(dr_before_dp: float) -> float:
    """Compute deep percolation using the simple excess-water method.

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
    """Compute deep percolation via Liu et al. (2006) parametric model.

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


def compute_cr_constant(gmax: float, dr: float, raw: float) -> float:
    """Compute capillary rise using the constant Gmax approach.

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
    """Compute capillary rise via Liu et al. (2006) parametric model.

    The functional form is:

    ``CR = a_c * z_wt^b_c * exp(-c_c * LAI^d_c)``

    The exact empirical coefficients are texture/depth-dependent and
    must be supplied by the caller from lookup tables.

    Args:
        z_wt: Water table depth from surface [m].
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
    return (a_c * (z_wt**b_c)) * math.exp(-c_c * lai**d_c)


def compute_cr_parametric_complete(
    dw: float,
    w: float,
    lai: float,
    etm: float,
    a1: float,
    b1: float,
    a2: float,
    b2: float,
    a3: float,
    b3: float,
    a4: float,
    b4: float,
    zr_m: float = 0.0,
) -> float:
    """Compute capillary rise via Liu et al. (2006) full parametric model.

    Liu, Y., Pereira, L.S., Fernando, R.M., 2006. Fluxes through the bottom
    boundary of the root zone in silty soils: Parametric approaches to
    estimate groundwater contribution and percolation. Agricultural Water
    Management, 84(1-2), 27-40.

    Steps:
      1. Wc = a1 * Dw^b1                     (critical soil water storage)
      2. Ws = a2 * Dw^b2  (Dw <= 3 m)
              3.57 * Dw^-0.705  (Dw > 3 m)   (steady soil water storage)
      3. Dwc = a3 * ETm + b3   (ETm <= 4 mm/day)
              1.4 m            (ETm > 4 mm/day)   (critical groundwater depth)
      4. k = 1 - exp(-0.6 * LAI)  (ETm <= 4 mm/day)
             3.8 / ETm         (ETm > 4 mm/day)   (transpiration factor)
      5. CRmax = k * ETm  if Dw <= Dwc else a4 * Dw^b4
      6. CR = CRmax                     if W < Ws
              CRmax * (Wc-W)/(Wc-Ws)   if Ws <= W <= Wc
              0                         if W > Wc

    Dw should be limited to a depth below the root zone (Liu 2006).

    Args:
        dw: Water table depth from surface [m].
        w: Absolute soil water storage in root zone [mm] (ASW + WWP).
        lai: Leaf area index [m²/m²].
        etm: Potential crop transpiration [mm/day] (Kcb * ETo).
        a1, b1, a2, b2, a3, b3, a4, b4: Soil texture coefficients.
        zr_m: Root depth [m].  Dw is clamped to max(dw, zr_m) so that the
            water table is always evaluated at or below the root zone.

    Returns:
        Capillary rise [mm/day].
    """
    dw = max(dw, zr_m)

    # 1. Critical soil water storage
    wc = a1 * (dw**b1)

    # 2. Steady soil water storage
    if dw <= _CR_DW_STEADY_THRESHOLD_M:
        ws = a2 * (dw**b2)
    else:
        ws = _CR_WS_FALLBACK_A * (dw**_CR_WS_FALLBACK_B)

    # 3 & 4. Critical depth and transpiration factor (Liu 2006 piecewise on ETm)
    if etm <= _CR_ETM_THRESHOLD_MM_DAY:
        dwc = a3 * etm + b3
        k = 1.0 - math.exp(-0.6 * lai)
    else:
        dwc = _CR_DWC_FALLBACK_M  # 1.4 m fixed for high transpiration
        k = _CR_K_FALLBACK_NUMERATOR / etm  # 3.8/ETm so k·ETm = 3.8 cap

    # 5. Potential capillary flux.
    # For ETm > 4, Dwc is fixed at 1.4 m (Liu Eq. 6) and k = 3.8/ETm (silt-loam
    # calibrated).  This produces a discontinuity at Dwc for soils with small a4:
    # the Dw<=Dwc branch gives 3.8 mm/d while the Dw>Dwc branch gives a4*Dwc^b4,
    # which for clay-loam orchards (a4=1.11, b4=-0.98) is only ~0.80 mm/d — a 3 mm/d
    # jump that is physically impossible.  Capping at the soil's hydraulic supply
    # (a4*Dw^b4) for the ETm>4 case restores continuity and keeps the formula
    # soil-specific.  For ETm<=4, Dwc = a3*ETm+b3 is already soil-specific and the
    # k*ETm formula is appropriate (water table is well below Dwc so supply isn't
    # limiting for the ETm<=4 case).
    if dw <= dwc:
        if etm > _CR_ETM_THRESHOLD_MM_DAY:
            cr_max = min(k * etm, a4 * (dw**b4))
        else:
            cr_max = k * etm
    else:
        cr_max = a4 * (dw**b4)
    cr_max = min(cr_max, _CR_K_FALLBACK_NUMERATOR)

    # 6. Actual capillary rise
    if w < ws:
        return cr_max
    if w <= wc:
        if wc == ws:
            return cr_max
        return cr_max * ((wc - w) / (wc - ws))
    return 0.0


def compute_cr_parametric_complete_with_guards(
    dw: float,
    w: float,
    lai: float,
    etm: float,
    a1: float,
    b1: float,
    a2: float,
    b2: float,
    a3: float,
    b3: float,
    a4: float,
    b4: float,
    zr_m: float = 0.0,
) -> float:
    """Liu et al. (2006) parametric CR + Guard 1 (early-season suppression).

    Guard (empirical, from original SIMDualKc T_Resultados):
    1. Early-season: if LAI < 0.3 and ETm <= 4.0, return 0.

    Note: a post-irrigation guard (Guard 2) was removed because it was provably
    wrong in both directions — it suppressed days with expected CR > 0 and missed
    days that Access suppresses.  The correct post-irrigation suppression rule
    requires Access VBA source to implement precisely.
    """
    if lai < 0.3 and etm <= 4.0:
        return 0.0
    return compute_cr_parametric_complete(
        dw=dw,
        zr_m=zr_m,
        w=w,
        lai=lai,
        etm=etm,
        a1=a1,
        b1=b1,
        a2=a2,
        b2=b2,
        a3=a3,
        b3=b3,
        a4=a4,
        b4=b4,
    )


def get_crop_list() -> pd.DataFrame:
    """Return a summary table of all crops in the database.

    Returns:
        DataFrame with columns: Cultura_ID, Cultura.
    """
    data_path = Path(__file__).parent / "data" / "crops.parquet"
    df = pd.read_parquet(data_path)
    return df[["Cultura_ID", "Cultura"]]


def get_crop_details(crop_id: int) -> pd.Series:
    """Return detailed parameters for a specific crop by ID.

    Args:
        crop_id: The unique Cultura_ID.

    Returns:
        Series containing all 107 columns for the selected crop.

    Raises:
        ValueError: If crop_id is not found.
    """
    data_path = Path(__file__).parent / "data" / "crops.parquet"
    df = pd.read_parquet(data_path)
    match = df[df["Cultura_ID"] == crop_id]
    if match.empty:
        msg = f"Crop ID {crop_id} not found in database."
        raise ValueError(msg)
    return match.iloc[0]


def get_soil_list() -> pd.DataFrame:
    """Return a summary table of all soil types in the database.

    Returns:
        DataFrame with columns: Solo_ID, Solo.
    """
    data_path = Path(__file__).parent / "data" / "soils.parquet"
    df = pd.read_parquet(data_path)
    return df[["Solo_ID", "Solo"]]


def interpolate_water_table_depth(
    climate: list[ClimateRecord],
    wt_dates: list[datetime.date],
    wt_depths: list[float],
) -> list[ClimateRecord]:
    """Linearly interpolate sparse water table depth measurements onto the daily climate sequence.

    Returns new :class:`~simdualkc.models.ClimateRecord` objects with ``wt_depth_m`` filled.
    Holds the first measured value before the earliest date and the last measured value
    after the latest date.

    Args:
        climate: Ordered daily climate records.
        wt_dates: Dates on which water table depth was measured.
        wt_depths: Measured water table depths [m].

    Returns:
        New list of climate records with ``wt_depth_m`` populated.

    Raises:
        ValueError: If ``wt_dates`` and ``wt_depths`` are empty or of unequal length.
    """
    if not wt_dates or not wt_depths or len(wt_dates) != len(wt_depths):
        msg = "wt_dates and wt_depths must be non-empty and of equal length"
        raise ValueError(msg)

    sorted_pairs = sorted(zip(wt_dates, wt_depths, strict=True))
    dates = [p[0] for p in sorted_pairs]
    depths = [p[1] for p in sorted_pairs]

    result: list[ClimateRecord] = []
    for record in climate:
        d = record.date
        if d <= dates[0]:
            new_depth = depths[0]
        elif d >= dates[-1]:
            new_depth = depths[-1]
        else:
            # Linear search for interval (dates is small)
            new_depth = depths[-1]
            for i in range(len(dates) - 1):
                if dates[i] <= d <= dates[i + 1]:
                    delta = (dates[i + 1] - dates[i]).days
                    if delta == 0:
                        new_depth = depths[i]
                    else:
                        frac = (d - dates[i]).days / delta
                        new_depth = depths[i] + frac * (depths[i + 1] - depths[i])
                    break
        result.append(
            ClimateRecord(
                date=record.date,
                eto=record.eto,
                precip=record.precip,
                u2=record.u2,
                rh_min=record.rh_min,
                wt_depth_m=new_depth,
            )
        )
    return result
