"""Unit tests for simdualkc.water_balance."""

import pytest

from simdualkc.water_balance import (
    compute_etc_act,
    compute_ks,
    compute_raw,
    compute_taw,
    update_root_zone_depletion,
)


class TestComputeTaw:
    def test_known_value(self) -> None:
        # 1000 * (0.32 - 0.12) * 1.0 = 200 mm
        assert compute_taw(0.32, 0.12, 1.0) == pytest.approx(200.0)

    def test_scales_with_root_depth(self) -> None:
        taw_1m = compute_taw(0.32, 0.12, 1.0)
        taw_2m = compute_taw(0.32, 0.12, 2.0)
        assert taw_2m == pytest.approx(2 * taw_1m)


class TestComputeRaw:
    def test_known_value(self) -> None:
        # p=0.5, taw=200 → RAW=100
        assert compute_raw(200.0, 0.5) == pytest.approx(100.0)

    def test_full_depletion_allowed(self) -> None:
        assert compute_raw(200.0, 1.0) == pytest.approx(200.0)


class TestComputeKs:
    def test_no_stress_when_dr_le_raw(self) -> None:
        taw = 200.0
        raw = 100.0
        p = 0.5
        ks = compute_ks(dr=80.0, taw=taw, raw=raw, p=p)
        assert ks == pytest.approx(1.0)

    def test_ks_zero_at_wilting_point(self) -> None:
        taw = 200.0
        raw = 100.0
        p = 0.5
        ks = compute_ks(dr=200.0, taw=taw, raw=raw, p=p)
        assert ks == pytest.approx(0.0)

    def test_ks_between_0_and_1_under_stress(self) -> None:
        taw = 200.0
        raw = 100.0
        p = 0.5
        ks = compute_ks(dr=150.0, taw=taw, raw=raw, p=p)
        assert 0.0 < ks < 1.0

    def test_ks_decreases_as_dr_increases(self) -> None:
        taw = 200.0
        raw = 100.0
        p = 0.5
        ks_low = compute_ks(dr=110.0, taw=taw, raw=raw, p=p)
        ks_high = compute_ks(dr=180.0, taw=taw, raw=raw, p=p)
        assert ks_high < ks_low

    def test_ks_exactly_at_raw_boundary(self) -> None:
        # Exactly at RAW → no stress
        ks = compute_ks(dr=100.0, taw=200.0, raw=100.0, p=0.5)
        assert ks == pytest.approx(1.0)


class TestComputeEtcAct:
    def test_no_stress_full_et(self) -> None:
        # Ks=1, Kcb=1, Ke=0, ETo=5 → ETc_act=5
        assert compute_etc_act(ks=1.0, kcb=1.0, ke=0.0, eto=5.0) == pytest.approx(5.0)

    def test_full_stress_only_evaporation(self) -> None:
        # Ks=0 → only evaporation component
        assert compute_etc_act(ks=0.0, kcb=1.0, ke=0.5, eto=4.0) == pytest.approx(2.0)

    def test_combined(self) -> None:
        # ETc = (0.8*1.1 + 0.3)*5.0 = (0.88+0.3)*5 = 5.9
        result = compute_etc_act(ks=0.8, kcb=1.1, ke=0.3, eto=5.0)
        assert result == pytest.approx((0.8 * 1.1 + 0.3) * 5.0)

    def test_zero_eto_gives_zero(self) -> None:
        assert compute_etc_act(ks=1.0, kcb=1.2, ke=0.5, eto=0.0) == pytest.approx(0.0)


class TestUpdateRootZoneDepletion:
    def test_heavy_rain_reduces_depletion(self) -> None:
        dr_new, dp = update_root_zone_depletion(
            dr_prev=100.0,
            precip=80.0,
            ro=0.0,
            irrig=0.0,
            cr=0.0,
            etc_act=5.0,
            taw=200.0,
        )
        assert dr_new < 100.0
        assert dp == pytest.approx(0.0)

    def test_excess_water_becomes_dp(self) -> None:
        # Very large rainfall → Dr goes negative → DP generated
        dr_new, dp = update_root_zone_depletion(
            dr_prev=20.0,
            precip=200.0,
            ro=0.0,
            irrig=0.0,
            cr=0.0,
            etc_act=5.0,
            taw=200.0,
        )
        assert dr_new == pytest.approx(0.0)
        assert dp > 0.0

    def test_depletion_never_exceeds_taw(self) -> None:
        # Very high ET, no water input
        dr_new, dp = update_root_zone_depletion(
            dr_prev=195.0,
            precip=0.0,
            ro=0.0,
            irrig=0.0,
            cr=0.0,
            etc_act=50.0,
            taw=200.0,
        )
        assert dr_new <= 200.0

    def test_depletion_never_negative(self) -> None:
        dr_new, dp = update_root_zone_depletion(
            dr_prev=10.0,
            precip=100.0,
            ro=0.0,
            irrig=0.0,
            cr=0.0,
            etc_act=0.0,
            taw=200.0,
        )
        assert dr_new >= 0.0
        assert dp > 0.0  # excess becomes DP
