"""Automated irrigation scheduling logic."""

import datetime

from simdualkc.kcb import build_forage_cycle_map, get_stage
from simdualkc.models import (
    CropParams,
    DeficitIrrigationStrategy,
    DeliveryConstraints,
    IrrigationIntervalPeriod,
    MADThresholdStrategy,
)

_STAGE_KEYS: dict[int, str] = {1: "ini", 2: "dev", 3: "mid", 4: "late"}


def should_trigger_irrigation(
    dr: float,
    taw: float,
    mad_fraction: float,
    days_to_harvest: int,
    harvest_stop_days: int,
    last_irrigation_day: int,
    current_day: int,
    min_interval: int,
) -> bool:
    """Check if irrigation should be triggered (MAD threshold).

    Args:
        dr: Current root zone depletion [mm].
        taw: Total available water [mm].
        mad_fraction: Trigger when Dr >= mad_fraction × TAW.
        days_to_harvest: Days until harvest (1-based from current).
        harvest_stop_days: Do not irrigate if days_to_harvest <= this.
        last_irrigation_day: Day index of last irrigation (0 if never).
        current_day: Current simulation day index.
        min_interval: Minimum days between irrigations.

    Returns:
        True if irrigation should be applied.
    """
    if taw <= 0.0:
        return False
    if harvest_stop_days > 0 and days_to_harvest <= harvest_stop_days:
        return False
    mad_threshold = mad_fraction * taw
    if (current_day - last_irrigation_day) < min_interval:
        return False
    return not (dr < mad_threshold)


def compute_irrigation_depth(
    dr: float,
    taw: float,
    target_pct_taw: float,
) -> float:
    """Compute irrigation depth to reach target TAW.

    I = Dr - (TAW × (1 - target_%TAW/100))

    Brings depletion down so that (TAW - Dr_after) / TAW = target_%TAW/100,
    i.e. Dr_after = TAW × (1 - target_%TAW/100).

    Args:
        dr: Current root zone depletion [mm].
        taw: Total available water [mm].
        target_pct_taw: Target as percentage of TAW (100 = full refill).

    Returns:
        Irrigation depth [mm].
    """
    if taw <= 0.0:
        return 0.0
    target_depletion = taw * (1.0 - target_pct_taw / 100.0)
    depth = dr - target_depletion
    return max(0.0, depth)


def get_mad_for_day(
    day_of_sim: int,
    crop: CropParams,
    strategy: MADThresholdStrategy | DeficitIrrigationStrategy,
) -> float:
    """Get MAD fraction for the current day.

    For MADThresholdStrategy returns constant mad_fraction.
    For DeficitIrrigationStrategy returns stage-specific value.
    """
    if isinstance(strategy, MADThresholdStrategy):
        return strategy.mad_fraction
    stage = get_stage(day_of_sim, crop)
    key = _STAGE_KEYS.get(stage, "mid")
    return strategy.stage_mad.get(key, strategy.stage_mad.get("mid", 0.5))


def get_days_to_harvest(day_of_sim: int, crop: CropParams) -> int:
    """Days until harvest (harvest at end of stage 4).

    For forage crops, returns days until the next cut date.
    Returns positive integer when before harvest, 0 or negative when at/past.
    """
    if crop.is_forage and crop.forage_params:
        cmap = build_forage_cycle_map(crop.forage_params)
        for _, end, _ in cmap:
            if day_of_sim <= end:
                return end - day_of_sim
        return 0
    total_days = sum(crop.stage_lengths)
    return total_days - day_of_sim


def get_min_interval_for_date(
    date: datetime.date,
    interval_schedule: list[IrrigationIntervalPeriod] | None,
    fallback: int,
) -> int:
    """Return the minimum interval for a given date.

    If the date falls within any period in ``interval_schedule``, returns
    that period's ``min_interval_days``.  If multiple periods match, the
    first match wins.  If no period matches, returns ``fallback``.

    Args:
        date: Current simulation date.
        interval_schedule: List of date-range intervals (may be None).
        fallback: Default interval when no range matches.

    Returns:
        Minimum days between irrigation events.
    """
    if interval_schedule is None:
        return fallback
    for period in interval_schedule:
        if period.start_date <= date <= period.end_date:
            return period.min_interval_days
    return fallback


def get_target_pct_taw_for_day(
    day_of_sim: int,
    crop: CropParams,
    strategy: MADThresholdStrategy | DeficitIrrigationStrategy,
) -> float:
    """Resolve the target % TAW for the current day.

    If ``strategy.delivery`` has ``stage_target_pct_taw``, the stage-specific
    value is returned. Otherwise the strategy's base ``target_pct_taw`` is
    returned.

    Args:
        day_of_sim: 1-based day index.
        crop: Crop parameters.
        strategy: MAD or deficit strategy.

    Returns:
        Target percentage of TAW [0–100].
    """
    delivery = strategy.delivery
    if delivery is not None and delivery.stage_target_pct_taw is not None:
        stage = get_stage(day_of_sim, crop)
        key = _STAGE_KEYS.get(stage, "mid")
        return delivery.stage_target_pct_taw.get(key, strategy.target_pct_taw)
    return strategy.target_pct_taw


def resolve_stage_fixed_depth(
    stage: int,
    delivery: DeliveryConstraints | None,
) -> float | None:
    """Return the fixed depth for a growth stage if configured.

    Checks ``delivery.fixed_depth_mm`` first. If not set, checks
    ``delivery.stage_fixed_depth_mm`` for the stage key.

    Args:
        stage: Growth stage 1–4.
        delivery: Delivery constraints (may be None).

    Returns:
        Fixed depth [mm] or None if not configured.
    """
    if delivery is None:
        return None
    if delivery.fixed_depth_mm is not None:
        return delivery.fixed_depth_mm
    if delivery.stage_fixed_depth_mm is not None:
        key = _STAGE_KEYS.get(stage, "mid")
        return delivery.stage_fixed_depth_mm.get(key)
    return None


def apply_delivery_constraints(
    depth: float,
    stage: int,
    delivery: DeliveryConstraints | None,
) -> float:
    """Apply delivery-side constraints to a computed irrigation depth.

    Applied in order:
    1. If ``delivery.fixed_depth_mm`` is set, use it.
    2. Else if ``delivery.stage_fixed_depth_mm`` has a key for ``stage``,
       use that.
    3. If ``delivery.max_depth_mm`` is set, cap to it.
    4. Return ``max(0.0, depth)``.

    Args:
        depth: Computed irrigation depth [mm].
        stage: Current growth stage 1–4.
        delivery: Delivery constraints (may be None).

    Returns:
        Constrained depth [mm].
    """
    if delivery is not None:
        if delivery.fixed_depth_mm is not None:
            depth = delivery.fixed_depth_mm
        elif delivery.stage_fixed_depth_mm is not None:
            key = _STAGE_KEYS.get(stage, "mid")
            stage_depth = delivery.stage_fixed_depth_mm.get(key)
            if stage_depth is not None:
                depth = stage_depth
        if delivery.max_depth_mm is not None:
            depth = min(depth, delivery.max_depth_mm)
    return max(0.0, depth)
