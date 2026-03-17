"""Tests for the Stewart yield model."""

from simdualkc.yield_model import compute_yield_decrease_transpiration

def test_compute_yield_decrease():
    y_a, decrease_pct = compute_yield_decrease_transpiration(
        t_act_sum=80.0,
        t_pot_sum=100.0,
        k_y=1.2,
        y_m=10000.0,
    )
    assert abs(y_a - 7600.0) < 1e-6
    assert abs(decrease_pct - 24.0) < 1e-6


def test_compute_yield_decrease_no_stress():
    y_a, decrease_pct = compute_yield_decrease_transpiration(
        t_act_sum=100.0,
        t_pot_sum=100.0,
        k_y=1.0,
        y_m=5000.0,
    )
    assert y_a == 5000.0
    assert decrease_pct == 0.0


def test_compute_yield_extreme_stress():
    y_a, decrease_pct = compute_yield_decrease_transpiration(
        t_act_sum=0.0,
        t_pot_sum=100.0,
        k_y=2.0,  # Will cap at 1.0 fraction
        y_m=5000.0,
    )
    assert y_a == 0.0
    assert decrease_pct == 100.0
