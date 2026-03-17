"""Tests for salinity impacts on water stress."""

from simdualkc.water_balance import compute_ks_salinity


def test_compute_ks_salinity_no_stress() -> None:
    ks = compute_ks_salinity(ec_e=1.5, ec_threshold=2.0, b=10.0, k_y=1.0)
    assert ks == 1.0


def test_compute_ks_salinity_moderate_stress() -> None:
    ks = compute_ks_salinity(ec_e=4.0, ec_threshold=2.0, b=10.0, k_y=1.0)
    assert abs(ks - 0.8) < 1e-6


def test_compute_ks_salinity_severe_stress() -> None:
    ks = compute_ks_salinity(ec_e=15.0, ec_threshold=2.0, b=10.0, k_y=1.0)
    assert ks == 0.0
