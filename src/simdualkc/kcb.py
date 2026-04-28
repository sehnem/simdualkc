"""Basal crop coefficient (Kcb) equations.

All functions are stateless and operate on scalar floats.
"""

import datetime
import math

from simdualkc.models import CropParams, ForageCutCycle, ForageParams


def lai_to_fc(lai: float, k_ext: float = 0.6) -> float:
    """Convert Leaf Area Index to effective fraction cover (FAO-56).

    fc = 1 - exp(-K_ext × LAI)

    Where K_ext is the light extinction coefficient (typically 0.5–0.7
    depending on crop geometry).

    Args:
        lai: Leaf Area Index [m²/m²].
        k_ext: Light extinction coefficient [—], default 0.6.

    Returns:
        Effective fraction cover [0–1].
    """
    if lai <= 0.0:
        return 0.0
    fc = 1.0 - math.exp(-k_ext * lai)
    return min(1.0, fc)


def interpolate_lai(
    day_of_sim: int,
    lai_dates: list[datetime.date],
    lai_values: list[float],
    plant_date: datetime.date,
) -> float:
    """Linearly interpolate LAI from discrete measurements by date.

    Args:
        day_of_sim: 1-based day index from planting.
        lai_dates: Dates of LAI measurements (chronological).
        lai_values: LAI values at those dates.
        plant_date: Planting date.

    Returns:
        Interpolated LAI. Returns 0 before first date; holds last value after.
    """
    if not lai_dates or not lai_values:
        return 0.0
    current_date = plant_date + datetime.timedelta(days=day_of_sim - 1)

    # Before first measurement — use 0 (pre-emergence) or first value at exact match
    if current_date < lai_dates[0]:
        return 0.0
    if current_date == lai_dates[0]:
        return lai_values[0]

    # After last measurement — hold last value
    if current_date >= lai_dates[-1]:
        return lai_values[-1]

    # Find bracketing dates and interpolate
    for i in range(len(lai_dates) - 1):
        if lai_dates[i] < current_date <= lai_dates[i + 1]:
            d0 = (lai_dates[i] - plant_date).days + 1
            d1 = (lai_dates[i + 1] - plant_date).days + 1
            if d1 <= d0:
                return lai_values[i]
            fraction = (day_of_sim - d0) / (d1 - d0)
            return lai_values[i] + fraction * (lai_values[i + 1] - lai_values[i])

    return lai_values[-1]


def fc_to_lai(fc: float, k_ext: float = 0.6) -> float:
    """Invert fc = 1 - exp(-k_ext × LAI) to get LAI.

    LAI = -ln(1 - fc) / k_ext
    """
    if fc <= 0.0:
        return 0.0
    if fc >= 1.0:
        return 10.0  # Saturation, use large value
    return -math.log(1.0 - fc) / k_ext


def get_lai(day_of_sim: int, crop: CropParams) -> float:
    """Get Leaf Area Index for the day.

    If crop has LAI data, interpolates. Otherwise derives from fc.
    For forage crops, derives from the forage-specific fc interpolation.
    """
    if crop.uses_lai() and crop.lai_values and crop.lai_dates:
        return interpolate_lai(day_of_sim, crop.lai_dates, crop.lai_values, crop.plant_date)
    if crop.is_forage and crop.forage_params:
        fc = interpolate_forage_fc(day_of_sim, crop.forage_params)
    else:
        fc = interpolate_growth_param(day_of_sim, crop, "fc")
    return fc_to_lai(fc, crop.k_ext)


def get_fc(day_of_sim: int, crop: CropParams) -> float:
    """Get effective fraction cover for the day.

    If crop has LAI data (lai_values, lai_dates), interpolates LAI and converts
    to fc via fc = 1 - exp(-k_ext × LAI).  For forage crops uses the
    cut-cycle-based interpolation.  Otherwise uses standard growth interpolation
    of fc_max.

    Args:
        day_of_sim: 1-based simulation day.
        crop: Crop parameter set.

    Returns:
        Fraction cover [0–1].
    """
    if crop.uses_lai() and crop.lai_values and crop.lai_dates:
        lai = interpolate_lai(day_of_sim, crop.lai_dates, crop.lai_values, crop.plant_date)
        return lai_to_fc(lai, crop.k_ext)
    if crop.is_forage and crop.forage_params:
        return interpolate_forage_fc(day_of_sim, crop.forage_params)
    return interpolate_growth_param(day_of_sim, crop, "fc")


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


def compute_kcb_with_groundcover(
    kcb_full: float,
    kcb_cover: float,
    kd: float,
) -> float:
    """Combine main crop and groundcover Kcb (FAO-56 Eq. 11).

    Kcb = Kcb_cover + Kd × max(Kcb_full - Kcb_cover, (Kcb_full - Kcb_cover)/2)

    Args:
        kcb_full: Main crop Kcb at full cover [—].
        kcb_cover: Groundcover Kcb for non-shaded fraction [—].
        kd: Density coefficient for main crop [—].

    Returns:
        Combined Kcb [—].
    """
    diff = kcb_full - kcb_cover
    term = max(diff, diff / 2.0)
    return kcb_cover + kd * term


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


# ---------------------------------------------------------------------------
# Forage / multi-cut functions
# ---------------------------------------------------------------------------


def build_forage_cycle_map(
    forage_params: ForageParams,
) -> list[tuple[int, int, int]]:
    """Pre-compute (start_day, end_day, cycle_index) for each cutting cycle.

    Returns a list of triples, one per cycle. Day numbers are 1-based
    relative to the forage start date.

    Args:
        forage_params: Forage crop parameters with cycle definitions.

    Returns:
        List of ``(start, end, cycle_idx)`` where *end* is the cut day.
    """
    cycle_map: list[tuple[int, int, int]] = []
    day_cursor = 1
    for idx, cycle in enumerate(forage_params.cycles):
        total = sum(cycle.stage_lengths)
        start = day_cursor
        end = day_cursor + total - 1
        cycle_map.append((start, end, idx))
        day_cursor = end + 1
    return cycle_map


def get_forage_cycle_and_day(
    day_of_sim: int,
    forage_params: ForageParams,
) -> tuple[int, int]:
    """Determine which cutting cycle *day_of_sim* falls in.

    Args:
        day_of_sim: 1-based simulation day offset from forage start date.
        forage_params: Forage crop parameters.

    Returns:
        ``(cycle_index, day_within_cycle)``.
        If *day_of_sim* is past the last cut, returns the last cycle with
        a day-within-cycle one past its total length.
    """
    cmap = build_forage_cycle_map(forage_params)
    for start, end, idx in cmap:
        if start <= day_of_sim <= end:
            day_in_cycle = day_of_sim - start + 1
            return idx, day_in_cycle
    if day_of_sim > cmap[-1][0]:
        last_start = cmap[-1][0]
        overshoot = day_of_sim - last_start
        return len(cmap) - 1, overshoot + 1
    return 0, max(1, day_of_sim)


def is_forage_cut_day(day_of_sim: int, forage_params: ForageParams) -> bool:
    """Return True if *day_of_sim* is a cut day (last day of a cycle)."""
    cmap = build_forage_cycle_map(forage_params)
    return any(day_of_sim == end for _, end, _ in cmap)


def get_forage_stage(day_in_cycle: int, cycle: ForageCutCycle) -> int:
    """Return the FAO phenological stage (1–4) within a forage cut cycle.

    Args:
        day_in_cycle: 1-based day within the current cut cycle.
        cycle: The cut cycle.

    Returns:
        Stage 1–4 (same meaning as standard FAO stages).
    """
    ini, dev, mid, late = cycle.stage_lengths
    if day_in_cycle <= ini:
        return 1
    if day_in_cycle <= ini + dev:
        return 2
    if day_in_cycle <= ini + dev + mid:
        return 3
    return 4


def interpolate_forage_kcb(
    day_of_sim: int,
    forage_params: ForageParams,
    u2: float,
    rh_min: float,
) -> float:
    """Interpolate Kcb within the current forage cut cycle.

    Within each cycle Kcb follows:
      - Stage 1 (ini): constant ``kcb_start``.
      - Stage 2 (dev): linear to ``kcb_peak``.
      - Stage 3 (mid): constant ``kcb_peak`` (climate-adjusted).
      - Stage 4 (late): linear to ``kcb_before``.
      - Cut day (end of cycle): ``kcb_before``.
      - After last cycle: ``kcb_after``.

    Args:
        day_of_sim: 1-based simulation day.
        forage_params: Forage crop parameters.
        u2: Wind speed at 2 m [m/s].
        rh_min: Minimum relative humidity [%].

    Returns:
        Kcb for the day [—].
    """
    cycle_idx, day_in_cycle = get_forage_cycle_and_day(day_of_sim, forage_params)
    n_cycles = len(forage_params.cycles)

    if cycle_idx >= n_cycles:
        return forage_params.kcb_after

    cycle = forage_params.cycles[cycle_idx]
    ini, dev, mid, late = cycle.stage_lengths
    total = ini + dev + mid + late

    if day_in_cycle > total:
        if cycle_idx == n_cycles - 1:
            return forage_params.kcb_after
        return forage_params.kcb_before

    if day_in_cycle <= ini:
        return forage_params.kcb_start

    if day_in_cycle <= ini + dev:
        frac = (day_in_cycle - ini) / max(1.0, float(dev))
        return forage_params.kcb_start + frac * (forage_params.kcb_peak - forage_params.kcb_start)

    if day_in_cycle <= ini + dev + mid:
        h_mid = forage_params.max_height_m
        return adjust_kcb_climate(forage_params.kcb_peak, u2, rh_min, h_mid)

    if day_in_cycle < total:
        frac = (day_in_cycle - ini - dev - mid) / max(1.0, float(late))
        return forage_params.kcb_peak + frac * (forage_params.kcb_before - forage_params.kcb_peak)

    return forage_params.kcb_before


def interpolate_forage_fc(day_of_sim: int, forage_params: ForageParams) -> float:
    """Interpolate fraction cover within the current forage cut cycle.

    Args:
        day_of_sim: 1-based simulation day.
        forage_params: Forage crop parameters.

    Returns:
        Fraction cover [0–1].
    """
    cycle_idx, day_in_cycle = get_forage_cycle_and_day(day_of_sim, forage_params)
    n_cycles = len(forage_params.cycles)

    if cycle_idx >= n_cycles:
        return forage_params.fc_after

    cycle = forage_params.cycles[cycle_idx]
    ini, dev, mid, late = cycle.stage_lengths
    total = ini + dev + mid + late

    if day_in_cycle > total:
        if cycle_idx == n_cycles - 1:
            return forage_params.fc_after
        return forage_params.fc_before

    if day_in_cycle <= ini:
        return forage_params.fc_start

    if day_in_cycle <= ini + dev:
        frac = (day_in_cycle - ini) / max(1.0, float(dev))
        return forage_params.fc_start + frac * (forage_params.fc_peak - forage_params.fc_start)

    if day_in_cycle <= ini + dev + mid:
        return forage_params.fc_peak

    if day_in_cycle < total:
        frac = (day_in_cycle - ini - dev - mid) / max(1.0, float(late))
        return forage_params.fc_peak + frac * (forage_params.fc_before - forage_params.fc_peak)

    return forage_params.fc_before


def interpolate_forage_param(
    day_of_sim: int,
    forage_params: ForageParams,
    param: str,
) -> float:
    """Interpolate a growth parameter within the forage cut cycle framework.

    Supported parameters: ``"zr"``, ``"h"``, ``"p"``.

    - ``zr``: Grows from ``min_root_m`` to ``max_root_m`` over
      ``days_to_max_root`` days (resets each cycle).
    - ``h``: Grows from ``min_height_m`` to ``max_height_m`` over stages 1–3
      (same shape as standard crop height).
    - ``p``: Constant at ``p_fraction``.

    Args:
        day_of_sim: 1-based simulation day.
        forage_params: Forage crop parameters.
        param: One of ``"zr"``, ``"h"``, ``"p"``.

    Returns:
        Interpolated parameter value.
    """
    if param == "p":
        return forage_params.p_fraction

    cycle_idx, day_in_cycle = get_forage_cycle_and_day(day_of_sim, forage_params)
    cycle = forage_params.cycles[min(cycle_idx, len(forage_params.cycles) - 1)]

    if param == "zr":
        frac = min(1.0, (day_in_cycle - 1) / max(1.0, float(forage_params.days_to_max_root)))
        return forage_params.min_root_m + frac * (
            forage_params.max_root_m - forage_params.min_root_m
        )

    if param == "h":
        ini, dev, mid, _ = cycle.stage_lengths
        growth_end = ini + dev + mid
        if day_in_cycle >= growth_end:
            return forage_params.max_height_m
        frac = (day_in_cycle - 1) / max(1.0, float(growth_end - 1))
        frac = max(0.0, min(1.0, frac))
        return forage_params.min_height_m + frac * (
            forage_params.max_height_m - forage_params.min_height_m
        )

    msg = f"param must be one of {{'zr', 'h', 'p'}}, got {param!r}"
    raise ValueError(msg)


# Suppress unused import warning — math is used for potential callers
_ = math  # noqa: F841
