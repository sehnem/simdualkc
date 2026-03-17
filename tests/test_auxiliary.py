"""Unit tests for simdualkc.auxiliary."""

from __future__ import annotations

from itertools import pairwise

import pytest

from simdualkc.auxiliary import (
    adjust_cn_for_moisture,
    cn_from_amc,
    compute_cr_constant,
    compute_dp_parametric,
    compute_dp_simple,
    compute_runoff_cn,
)


class TestCnFromAmc:
    def test_amc1_less_than_cn2(self) -> None:
        cn1 = cn_from_amc(75.0, amc_class=1)
        assert cn1 < 75.0

    def test_amc3_greater_than_cn2(self) -> None:
        cn3 = cn_from_amc(75.0, amc_class=3)
        assert cn3 > 75.0

    def test_invalid_class_raises(self) -> None:
        with pytest.raises(ValueError, match="amc_class must be 1 or 3"):
            cn_from_amc(75.0, amc_class=2)


class TestAdjustCnForMoisture:
    def test_dry_surface_gives_cn1(self) -> None:
        # dei == tew → fully dry → AMC I
        cn = adjust_cn_for_moisture(cn2=75.0, dei=22.0, tew=22.0)
        assert cn == pytest.approx(cn_from_amc(75.0, amc_class=1), rel=1e-5)

    def test_wet_surface_gives_cn3(self) -> None:
        # dei == 0 → fully wet → AMC III
        cn = adjust_cn_for_moisture(cn2=75.0, dei=0.0, tew=22.0)
        assert cn == pytest.approx(cn_from_amc(75.0, amc_class=3), rel=1e-5)

    def test_intermediate_cn_between_limits(self) -> None:
        cn2 = 75.0
        cn1 = cn_from_amc(cn2, amc_class=1)
        cn3 = cn_from_amc(cn2, amc_class=3)
        cn = adjust_cn_for_moisture(cn2=cn2, dei=11.0, tew=22.0)
        assert cn1 <= cn <= cn3

    def test_cn_monotonically_decreasing_with_dry(self) -> None:
        """CN decreases as the surface dries out (dei increases)."""
        tew = 22.0
        cns = [adjust_cn_for_moisture(75.0, dei=d, tew=tew) for d in range(0, 23, 2)]
        assert all(b <= a + 1e-9 for a, b in pairwise(cns))


class TestComputeRunoffCn:
    def test_no_precip_no_runoff(self) -> None:
        assert compute_runoff_cn(0.0, cn=75.0) == pytest.approx(0.0)

    def test_small_storm_no_runoff(self) -> None:
        # Very light rain — below initial abstraction threshold
        ro = compute_runoff_cn(precip=1.0, cn=60.0)
        assert ro == pytest.approx(0.0)

    def test_large_storm_positive_runoff(self) -> None:
        # 100mm on CN=90 soil → large runoff
        ro = compute_runoff_cn(precip=100.0, cn=90.0)
        assert ro > 0.0

    def test_runoff_less_than_precip(self) -> None:
        """Physical constraint: RO can never exceed precipitation."""
        for precip, cn in [(10.0, 70.0), (50.0, 80.0), (100.0, 95.0)]:
            ro = compute_runoff_cn(precip, cn)
            assert ro <= precip + 1e-9

    def test_higher_cn_more_runoff(self) -> None:
        """Higher curve number (less permeable) should produce more runoff."""
        ro_low = compute_runoff_cn(50.0, cn=60.0)
        ro_high = compute_runoff_cn(50.0, cn=85.0)
        assert ro_high > ro_low


class TestComputeDpSimple:
    def test_no_dp_when_dr_positive(self) -> None:
        assert compute_dp_simple(50.0) == pytest.approx(0.0)

    def test_dp_when_dr_negative(self) -> None:
        # dr_before_dp = -30 → DP = 30
        assert compute_dp_simple(-30.0) == pytest.approx(30.0)

    def test_dp_zero_when_dr_is_zero(self) -> None:
        assert compute_dp_simple(0.0) == pytest.approx(0.0)


class TestComputeDpParametric:
    def test_zero_storage_returns_zero(self) -> None:
        assert compute_dp_parametric(storage=0.0, a_d=2.0, b_d=1.5) == pytest.approx(0.0)

    def test_negative_storage_returns_zero(self) -> None:
        assert compute_dp_parametric(storage=-5.0, a_d=2.0, b_d=1.5) == pytest.approx(0.0)

    def test_positive_storage_positive_dp(self) -> None:
        dp = compute_dp_parametric(storage=10.0, a_d=2.0, b_d=1.5)
        assert dp > 0.0

    def test_increases_with_storage(self) -> None:
        dp_low = compute_dp_parametric(storage=10.0, a_d=2.0, b_d=1.5)
        dp_high = compute_dp_parametric(storage=20.0, a_d=2.0, b_d=1.5)
        assert dp_high > dp_low


class TestComputeCrConstant:
    def test_no_cr_when_dr_is_zero(self) -> None:
        assert compute_cr_constant(gmax=2.0, dr=0.0, raw=50.0) == pytest.approx(0.0)

    def test_full_gmax_when_dr_ge_raw(self) -> None:
        assert compute_cr_constant(gmax=3.0, dr=60.0, raw=50.0) == pytest.approx(3.0)

    def test_partial_cr_between_zero_and_gmax(self) -> None:
        cr = compute_cr_constant(gmax=3.0, dr=25.0, raw=50.0)
        assert 0.0 < cr < 3.0

    def test_cr_proportional_to_stress(self) -> None:
        cr_low = compute_cr_constant(gmax=3.0, dr=10.0, raw=50.0)
        cr_high = compute_cr_constant(gmax=3.0, dr=40.0, raw=50.0)
        assert cr_high > cr_low
