"""Tests for mulch effects on surface evaporation."""

from simdualkc.evaporation import compute_few


def test_compute_few_with_mulch() -> None:
    fewi, fewp = compute_few(fc=0.4, fw=1.0, f_mulch=0.3, kr_mulch=0.5)
    assert abs(fewi - 0.45) < 1e-6
    assert fewp == 0.0


def test_compute_few_plastic_mulch() -> None:
    fewi, fewp = compute_few(fc=0.1, fw=1.0, f_mulch=0.9, kr_mulch=0.1)
    assert abs(fewi - 0.09) < 1e-6
    assert fewp == 0.0
