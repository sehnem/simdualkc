"""Automated irrigation scheduling logic."""

from simdualkc.kcb import build_forage_cycle_map, get_stage
from simdualkc.models import (
    CropParams,
    DeficitIrrigationStrategy,
    MADThresholdStrategy,
)


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
    if last_irrigation_day > 0 and (current_day - last_irrigation_day) < min_interval:
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
    stage_keys = {1: "ini", 2: "dev", 3: "mid", 4: "late"}
    key = stage_keys.get(stage, "mid")
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
