"""Unit tests for simdualkc.kcb."""

from __future__ import annotations

import datetime
from itertools import pairwise

import pytest

from simdualkc.kcb import (
    adjust_kcb_climate,
    compute_kcb_density,
    compute_kd,
    get_stage,
    interpolate_growth_param,
    interpolate_kcb,
)
from simdualkc.models import CropParams

# Shared crop fixture (avoids Pydantic construction overhead in each test)
_CROP = CropParams(
    kcb_ini=0.15,
    kcb_mid=1.10,
    kcb_end=0.35,
    stage_lengths=[30, 40, 50, 30],
    plant_date=datetime.date(2024, 4, 1),
    zr_ini=0.15,
    zr_max=1.20,
    h_max=2.50,
    p_tab=0.55,
    fc_max=0.90,
    ml=1.5,
    kc_min=0.15,
)


class TestAdjustKcbClimate:
    def test_standard_climate_returns_unchanged(self) -> None:
        """At RHmin=45%, u2=2 m/s the correction is zero."""
        result = adjust_kcb_climate(1.10, u2=2.0, rh_min=45.0, h=1.0)
        assert result == pytest.approx(1.10)

    def test_high_kcb_adjusted_upward_for_high_wind(self) -> None:
        result = adjust_kcb_climate(1.10, u2=4.0, rh_min=45.0, h=1.0)
        assert result > 1.10

    def test_low_kcb_tab_not_adjusted(self) -> None:
        """Values ≤ 0.45 are not corrected (FAO rule)."""
        result = adjust_kcb_climate(0.40, u2=4.0, rh_min=20.0, h=2.0)
        assert result == pytest.approx(0.40)

    def test_high_rh_reduces_kcb(self) -> None:
        result = adjust_kcb_climate(1.10, u2=2.0, rh_min=80.0, h=1.0)
        assert result < 1.10


class TestComputeKd:
    def test_zero_cover_gives_zero_kd(self) -> None:
        assert compute_kd(0.0, h=1.0, ml=1.5) == pytest.approx(0.0)

    def test_full_cover_gives_kd_le_1(self) -> None:
        kd = compute_kd(1.0, h=2.0, ml=1.5)
        assert 0.0 <= kd <= 1.0

    def test_kd_bounded_above_by_1(self) -> None:
        # High ML and high fc should never exceed 1
        kd = compute_kd(0.95, h=3.0, ml=2.0)
        assert kd <= 1.0 + 1e-9

    def test_kd_increases_with_fc(self) -> None:
        kd_low = compute_kd(0.3, h=1.0, ml=1.5)
        kd_high = compute_kd(0.7, h=1.0, ml=1.5)
        assert kd_high > kd_low


class TestComputeKcbDensity:
    def test_zero_kd_gives_kc_min(self) -> None:
        result = compute_kcb_density(kc_min=0.15, kd=0.0, kcb_full=1.10)
        assert result == pytest.approx(0.15)

    def test_kd_1_gives_kcb_full(self) -> None:
        result = compute_kcb_density(kc_min=0.15, kd=1.0, kcb_full=1.10)
        assert result == pytest.approx(1.10)

    def test_intermediate_kd(self) -> None:
        result = compute_kcb_density(kc_min=0.15, kd=0.5, kcb_full=1.15)
        assert result == pytest.approx(0.15 + 0.5 * (1.15 - 0.15))


class TestGetStage:
    def test_day_1_is_stage_1(self) -> None:
        assert get_stage(1, _CROP) == 1

    def test_day_30_is_stage_1(self) -> None:
        assert get_stage(30, _CROP) == 1

    def test_day_31_is_stage_2(self) -> None:
        assert get_stage(31, _CROP) == 2

    def test_stage_3_mid(self) -> None:
        # Stage 3 starts at day 30+40+1 = 71
        assert get_stage(71, _CROP) == 3

    def test_stage_4_late(self) -> None:
        # Stage 4 starts at day 30+40+50+1 = 121
        assert get_stage(121, _CROP) == 4

    def test_beyond_end_is_stage_4(self) -> None:
        assert get_stage(9999, _CROP) == 4


class TestInterpolateKcb:
    def test_stage_1_returns_kcb_ini(self) -> None:
        kcb = interpolate_kcb(1, _CROP, u2=2.0, rh_min=45.0)
        assert kcb == pytest.approx(_CROP.kcb_ini)

    def test_stage_3_returns_kcb_mid_adjusted(self) -> None:
        kcb = interpolate_kcb(80, _CROP, u2=2.0, rh_min=45.0)
        # At standard climate, kcb_mid needs no correction
        assert kcb == pytest.approx(_CROP.kcb_mid)

    def test_stage_2_is_monotonically_increasing(self) -> None:
        days = list(range(31, 71))  # stage 2: days 31–70
        kcbs = [interpolate_kcb(d, _CROP, u2=2.0, rh_min=45.0) for d in days]
        assert all(b >= a - 1e-9 for a, b in pairwise(kcbs))

    def test_stage_4_is_monotonically_decreasing(self) -> None:
        days = list(range(121, 151))  # stage 4: days 121–150
        kcbs = [interpolate_kcb(d, _CROP, u2=2.0, rh_min=45.0) for d in days]
        assert all(b <= a + 1e-9 for a, b in pairwise(kcbs))


class TestInterpolateGrowthParam:
    def test_zr_starts_at_ini(self) -> None:
        zr = interpolate_growth_param(1, _CROP, "zr")
        assert zr == pytest.approx(_CROP.zr_ini)

    def test_zr_reaches_max_at_stage_3_end(self) -> None:
        # Stage 3 ends at day 120
        zr = interpolate_growth_param(120, _CROP, "zr")
        assert zr == pytest.approx(_CROP.zr_max)

    def test_p_always_returns_p_tab(self) -> None:
        for day in [1, 50, 120, 200]:
            assert interpolate_growth_param(day, _CROP, "p") == pytest.approx(_CROP.p_tab)

    def test_invalid_param_raises(self) -> None:
        with pytest.raises(ValueError, match="param must be one of"):
            interpolate_growth_param(1, _CROP, "invalid")
