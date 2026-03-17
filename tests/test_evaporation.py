"""Unit tests for simdualkc.evaporation."""

import pytest

from simdualkc.evaporation import (
    compute_few,
    compute_kc_max,
    compute_ke,
    compute_kr,
    update_evaporative_depletion,
)


class TestComputeFew:
    def test_full_cover_no_exposed(self) -> None:
        fewi, fewp = compute_few(fc=1.0, fw=1.0)
        assert fewi == pytest.approx(0.0)
        assert fewp == pytest.approx(0.0)

    def test_bare_soil_sprinkler(self) -> None:
        # fc=0, fw=1 → fewi=1, fewp=0
        fewi, fewp = compute_few(fc=0.0, fw=1.0)
        assert fewi == pytest.approx(1.0)
        assert fewp == pytest.approx(0.0)

    def test_bare_soil_drip(self) -> None:
        # fc=0, fw=0.3 → fewi=0.3, fewp=0.7
        fewi, fewp = compute_few(fc=0.0, fw=0.3)
        assert fewi == pytest.approx(0.3)
        assert fewp == pytest.approx(0.7)

    def test_partial_cover_sprinkler(self) -> None:
        # fc=0.5, fw=1 → exposed=0.5, fewi=0.5, fewp=0
        fewi, fewp = compute_few(fc=0.5, fw=1.0)
        assert fewi == pytest.approx(0.5)
        assert fewp == pytest.approx(0.0)

    def test_partial_cover_drip(self) -> None:
        # fc=0.5, fw=0.3 → exposed=0.5, fewi=min(0.5,0.3)=0.3, fewp=0.2
        fewi, fewp = compute_few(fc=0.5, fw=0.3)
        assert fewi == pytest.approx(0.3)
        assert fewp == pytest.approx(0.2)

    def test_fractions_sum_to_exposed(self) -> None:
        for fc, fw in [(0.3, 0.5), (0.7, 0.2), (0.0, 1.0), (0.9, 0.4)]:
            fewi, fewp = compute_few(fc=fc, fw=fw)
            expected_exposed = max(0.0, 1.0 - fc)
            assert fewi + fewp == pytest.approx(expected_exposed, abs=1e-9)


class TestComputeKcMax:
    def test_standard_conditions(self) -> None:
        # At u2=2, RHmin=45, h=0.5 → kc_base = 1.2, must be ≥ kcb+0.05
        kc_max = compute_kc_max(kcb=0.15, u2=2.0, rh_min=45.0, h=0.5)
        assert kc_max >= 0.15 + 0.05

    def test_always_at_least_kcb_plus_005(self) -> None:
        for kcb in [0.15, 0.5, 1.0, 1.2]:
            kc_max = compute_kc_max(kcb=kcb, u2=2.0, rh_min=45.0, h=0.5)
            assert kc_max >= kcb + 0.05 - 1e-9

    def test_increases_with_wind(self) -> None:
        kc_low = compute_kc_max(kcb=0.5, u2=1.0, rh_min=45.0, h=1.0)
        kc_high = compute_kc_max(kcb=0.5, u2=4.0, rh_min=45.0, h=1.0)
        assert kc_high > kc_low


class TestComputeKr:
    def test_kr_1_when_fully_wet(self) -> None:
        # de_prev < rew → stage 1, Kr=1
        assert compute_kr(tew=22.0, rew=9.0, de_prev=5.0) == pytest.approx(1.0)

    def test_kr_0_when_fully_dry(self) -> None:
        # de_prev == tew
        assert compute_kr(tew=22.0, rew=9.0, de_prev=22.0) == pytest.approx(0.0)

    def test_kr_between_0_and_1(self) -> None:
        kr = compute_kr(tew=22.0, rew=9.0, de_prev=15.0)
        assert 0.0 <= kr <= 1.0

    def test_kr_decreases_with_depletion(self) -> None:
        kr_low = compute_kr(tew=22.0, rew=9.0, de_prev=10.0)
        kr_high = compute_kr(tew=22.0, rew=9.0, de_prev=18.0)
        assert kr_high < kr_low


class TestComputeKe:
    def test_ke_bounded_by_few_times_kcmax(self) -> None:
        kei, kep, ke = compute_ke(
            kri=1.0,
            krp=1.0,
            w=0.5,
            kc_max=1.2,
            kcb=0.15,
            fewi=0.4,
            fewp=0.2,
        )
        assert kei <= 0.4 * 1.2 + 1e-9
        assert kep <= 0.2 * 1.2 + 1e-9

    def test_ke_equals_kei_plus_kep(self) -> None:
        kei, kep, ke = compute_ke(
            kri=0.8,
            krp=0.5,
            w=0.6,
            kc_max=1.2,
            kcb=0.4,
            fewi=0.3,
            fewp=0.2,
        )
        assert ke == pytest.approx(kei + kep)

    def test_ke_zero_when_kcmax_equals_kcb(self) -> None:
        kei, kep, ke = compute_ke(
            kri=1.0,
            krp=1.0,
            w=0.5,
            kc_max=0.5,
            kcb=0.5,
            fewi=0.5,
            fewp=0.3,
        )
        assert ke == pytest.approx(0.0)

    def test_ke_zero_when_both_fractions_zero(self) -> None:
        kei, kep, ke = compute_ke(
            kri=1.0,
            krp=1.0,
            w=0.5,
            kc_max=1.2,
            kcb=0.5,
            fewi=0.0,
            fewp=0.0,
        )
        assert ke == pytest.approx(0.0)


class TestUpdateEvaporativeDepletion:
    def test_depletion_decreases_with_irrigation(self) -> None:
        de_new, dp_e = update_evaporative_depletion(
            de_prev=10.0,
            precip=0.0,
            ro=0.0,
            irrig=20.0,
            fw=1.0,
            e_frac=0.0,
            few=1.0,
            tew=22.0,
            is_irrigated_fraction=True,
        )
        assert de_new < 10.0

    def test_excess_becomes_deep_percolation(self) -> None:
        # Large irrigation on a wet soil → de goes negative → dp_e > 0
        _, dp_e = update_evaporative_depletion(
            de_prev=2.0,
            precip=0.0,
            ro=0.0,
            irrig=50.0,
            fw=1.0,
            e_frac=0.0,
            few=1.0,
            tew=22.0,
            is_irrigated_fraction=True,
        )
        assert dp_e > 0.0

    def test_depletion_never_negative(self) -> None:
        de_new, _ = update_evaporative_depletion(
            de_prev=0.0,
            precip=100.0,
            ro=0.0,
            irrig=0.0,
            fw=1.0,
            e_frac=0.0,
            few=0.5,
            tew=22.0,
            is_irrigated_fraction=False,
        )
        assert de_new >= 0.0

    def test_depletion_never_exceeds_tew(self) -> None:
        # High evaporation, no water input
        de_new, _ = update_evaporative_depletion(
            de_prev=20.0,
            precip=0.0,
            ro=0.0,
            irrig=0.0,
            fw=1.0,
            e_frac=10.0,
            few=0.5,
            tew=22.0,
            is_irrigated_fraction=False,
        )
        assert de_new <= 22.0 + 1e-9
