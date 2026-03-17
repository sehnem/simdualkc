"""Basal crop coefficient (Kcb) equations.

All functions are stateless and operate on scalar floats.
"""

import math

from simdualkc.models import CropParams


def adjust_kcb_climate(
    kcb_tab: float,
    u2: float,
    rh_min: float,
    h: float,
) -> float:
    """Adjust a tabulated Kcb value for local climate conditions.

    The standard FAO-56 table values assume RHmin=45 % and u2=2 m/s.
    Adjustment is only applied when ``kcb_tab > 0.45``.

    Args:
        kcb_tab: Tabulated Kcb value (mid or late stage) [—].
        u2: Mean daily wind speed at 2 m height [m/s].
        rh_min: Minimum daily relative humidity [%].
        h: Mean crop height [m].

    Returns:
        Climate-adjusted Kcb [—].
    """
    if kcb_tab <= 0.45:
        return kcb_tab
    correction = (0.04 * (u2 - 2.0) - 0.004 * (rh_min - 45.0)) * (h / 3.0) ** 0.3
    return kcb_tab + correction


def compute_kcb_full(
    kcb_tab: float,
    u2: float,
    rh_min: float,
    h: float,
) -> float:
    """Estimate Kcb at full canopy cover after climate adjustment.

    Convenience wrapper — identical to :func:`adjust_kcb_climate`.

    Args:
        kcb_tab: Tabulated Kcb for peak / mid-stage [—].
        u2: Mean daily wind speed at 2 m height [m/s].
        rh_min: Minimum daily relative humidity [%].
        h: Crop height [m].

    Returns:
        Kcb full [—].
    """
    return adjust_kcb_climate(kcb_tab, u2, rh_min, h)


def compute_kd(
    fc_eff: float,
    h: float,
    ml: float,
) -> float:
    """Compute the crop density coefficient Kd.

    Args:
        fc_eff: Effective fractional soil cover [0–1].
        h: Crop height [m].
        ml: Canopy light extinction / density multiplier (1.5–2.0) [—].

    Returns:
        Kd [0–1].
    """
    if fc_eff <= 0.0:
        return 0.0
    kd_ml = ml * fc_eff
    kd_exp = fc_eff ** (1.0 / (1.0 + h))
    return float(min(1.0, kd_ml, kd_exp))


def compute_kcb_density(
    kc_min: float,
    kd: float,
    kcb_full: float,
) -> float:
    """Compute Kcb adjusted for partial canopy cover.

    Formula: ``Kcb = Kc_min + Kd * (Kcb_full - Kc_min)``

    Args:
        kc_min: Minimum Kc for bare/dry conditions (≈0.15) [—].
        kd: Density coefficient from :func:`compute_kd` [—].
        kcb_full: Climate-adjusted Kcb at full cover [—].

    Returns:
        Adjusted Kcb [—].
    """
    return kc_min + kd * (kcb_full - kc_min)


def _stage_day_bounds(crop: CropParams) -> list[tuple[int, int]]:
    """Return (start_day, end_day) inclusive for each of the 4 stages.

    Day indexing is 1-based, relative to plant_date.
    """
    lengths = crop.stage_lengths
    boundaries: list[tuple[int, int]] = []
    start = 1
    for length in lengths:
        boundaries.append((start, start + length - 1))
        start += length
    return boundaries


def get_stage(day_of_sim: int, crop: CropParams) -> int:
    """Return the FAO phenological stage (1–4) for the given simulation day.

    Stages:
      1 = Initial, 2 = Crop development, 3 = Mid-season, 4 = Late season.

    Args:
        day_of_sim: 1-based day counter from planting.
        crop: Crop parameter set.

    Returns:
        Stage number in [1, 2, 3, 4]. Returns 4 for days beyond total length.
    """
    bounds = _stage_day_bounds(crop)
    for stage, (start, end) in enumerate(bounds, start=1):
        if start <= day_of_sim <= end:
            return stage
    return 4  # Beyond simulation — stay at end stage


def interpolate_kcb(
    day_of_sim: int,
    crop: CropParams,
    u2: float,
    rh_min: float,
) -> float:
    """Interpolate Kcb through FAO-56 growth stages with climate correction.

    - Stage 1 (ini): constant ``kcb_ini``.
    - Stage 2 (dev): linear interpolation from ``kcb_ini`` to climate-adjusted ``kcb_mid``.
    - Stage 3 (mid): constant climate-adjusted ``kcb_mid``.
    - Stage 4 (late): linear interpolation from ``kcb_mid`` to climate-adjusted ``kcb_end``.

    Args:
        day_of_sim: 1-based day counter from planting.
        crop: Crop parameter set.
        u2: Wind speed at 2 m [m/s] (for climate correction of mid/end values).
        rh_min: Minimum relative humidity [%] (for climate correction).

    Returns:
        Interpolated Kcb for the given day [—].
    """
    bounds = _stage_day_bounds(crop)
    h = crop.h_max  # Use max height for mid/end correction (conservative)
    kcb_mid_adj = adjust_kcb_climate(crop.kcb_mid, u2, rh_min, h)
    kcb_end_adj = adjust_kcb_climate(crop.kcb_end, u2, rh_min, h)

    stage = get_stage(day_of_sim, crop)

    if stage == 1:
        return crop.kcb_ini

    if stage == 2:
        # Linear from kcb_ini (end of stage 1) to kcb_mid_adj (start of stage 3)
        s2_start, s2_end = bounds[1]
        fraction = (day_of_sim - s2_start) / max(1, s2_end - s2_start)
        return crop.kcb_ini + fraction * (kcb_mid_adj - crop.kcb_ini)

    if stage == 3:
        return kcb_mid_adj

    # Stage 4 — linear from kcb_mid_adj to kcb_end_adj
    s4_start, s4_end = bounds[3]
    fraction = (day_of_sim - s4_start) / max(1, s4_end - s4_start)
    return kcb_mid_adj + fraction * (kcb_end_adj - kcb_mid_adj)


def interpolate_growth_param(
    day_of_sim: int,
    crop: CropParams,
    param: str,
) -> float:
    """Linearly interpolate a crop growth parameter from planting to maximum.

    Supported parameters: ``"zr"``, ``"h"``, ``"fc"``, ``"p"``.

    - ``zr``: Root depth from ``zr_ini`` → ``zr_max`` over stages 1–3; constant at stage 4.
    - ``h``: Plant height from 0 → ``h_max`` over stages 1–3; constant at stage 4.
    - ``fc``: Fractional cover from 0 → ``fc_max`` over stages 1–3; constant at stage 4.
    - ``p``: Depletion fraction, held constant at ``p_tab`` for all stages.

    Args:
        day_of_sim: 1-based simulation day.
        crop: Crop parameter set.
        param: One of ``"zr"``, ``"h"``, ``"fc"``, ``"p"``.

    Returns:
        Interpolated value for the given day.

    Raises:
        ValueError: If *param* is not one of the supported options.
    """
    supported = {"zr", "h", "fc", "p"}
    if param not in supported:
        msg = f"param must be one of {supported}, got {param!r}"
        raise ValueError(msg)

    if param == "p":
        return crop.p_tab

    bounds = _stage_day_bounds(crop)
    # Total days for full growth (stages 1–3)
    growth_end_day = bounds[2][1]  # end of stage 3

    ini_values = {"zr": crop.zr_ini, "h": 0.0, "fc": 0.0}
    max_values = {"zr": crop.zr_max, "h": crop.h_max, "fc": crop.fc_max}

    v_ini = ini_values[param]
    v_max = max_values[param]

    if day_of_sim >= growth_end_day:
        return v_max

    start_day = 1
    fraction = (day_of_sim - start_day) / max(1, growth_end_day - start_day)
    fraction = max(0.0, min(1.0, fraction))
    return v_ini + fraction * (v_max - v_ini)


# Suppress unused import warning — math is used for potential callers
_ = math  # noqa: F841
