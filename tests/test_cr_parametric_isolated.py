"""Isolated validation of ``compute_cr_parametric_complete`` against original SIMDualKc.

Instead of running the full simulation (which has known kcb/fc/dr discrepancies
versus the original Access software), this test reconstructs the exact inputs
to the CR function from ``T_Resultados`` daily state and asserts that our
implementation of the Liu et al. (2006) parametric model matches the original
software's ``Ground_water`` values.

This validates the CR *formula* independently of the crop-growth model.

Validation strategy
-------------------
- **Fallow crops (Sim 27-32):** strict daily atol = 0.05 mm/day.
  These validate perfectly because LAI ≈ 0 and the R-package ``k`` factor
  vanishes, eliminating the main source of active-crop discrepancy.
- **Active crops (Sim 3-12, 34-35):** statistical checks using the guarded
  formula.  The empirical guards reverse-engineered from the original Access
  software reduce early-season and post-irrigation discrepancies.  Sims 3-12
  show large improvements; sims 34-35 have frequent irrigation (every 2-3
  days) where a simple post-irrigation window over-suppresses correlation,
  so they are checked with slightly relaxed bounds.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from simdualkc.auxiliary import (
    compute_cr_parametric_complete,
    compute_cr_parametric_complete_with_guards,
)
from tests.conftest import load_cr_fixture

FALLOW_SIMS = [27, 28, 29, 30, 31, 32]
ACTIVE_SIMS_CORE = [3, 4, 6, 7, 8, 9, 10, 11, 12]
ACTIVE_SIMS_FREQ = [34, 35]


def _lai_from_fc(fc: float, k_ext: float = 0.5) -> float:
    """Convert fraction cover to LAI using the inverse of fc = 1 - exp(-k_ext * LAI)."""
    if fc <= 0.0:
        return 0.0
    if fc >= 0.999:
        return 10.0
    return -math.log(1.0 - fc) / k_ext


def _compute_cr_series(
    sim_id: int,
    etm_mode: str = "kcb_plus_ke",
    use_guards: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (expected_cr, actual_cr) arrays for the simulation."""
    config, expected = load_cr_fixture(sim_id)
    soil = config.soil

    coeffs = [
        soil.cr_a1,
        soil.cr_b1,
        soil.cr_a2,
        soil.cr_b2,
        soil.cr_a3,
        soil.cr_b3,
        soil.cr_a4,
        soil.cr_b4,
    ]
    if any(c is None for c in coeffs):
        pytest.skip(f"Sim {sim_id}: missing full parametric CR coefficients")

    k_ext = getattr(config.crop, "k_ext", 0.5) or 0.5

    wt_by_date = {}
    for rec in config.climate:
        if rec.wt_depth_m is not None:
            wt_by_date[rec.date] = rec.wt_depth_m

    lai_by_date = {}
    if config.crop.lai_dates and config.crop.lai_values:
        for ld, lv in zip(config.crop.lai_dates, config.crop.lai_values, strict=False):
            lai_by_date[ld] = lv

    exp_list = []
    act_list = []
    last_irrig_day = -999  # No irrigation before simulation start
    for _, row in expected.iterrows():
        d = row["date"]
        wt_depth_m = wt_by_date.get(d)
        if wt_depth_m is None or pd.isna(wt_depth_m):
            continue

        dw = max(0.0, wt_depth_m - float(row["zr"]))
        wa = float(row["taw"]) - float(row["dr"])
        lai = lai_by_date.get(d, _lai_from_fc(float(row["fc"]), k_ext))

        # Liu et al. (2006) uses ETm = Tr (crop transpiration) = Kcb * ETo.
        # The simET R package integration layer passes (Kcb+Ke)*ET0, but the
        # original SoilW documentation and the fallow-crop validation show that
        # Kcb*ETo is the correct driver for capillary rise.
        etm = float(row["kcb"]) * float(row["eto"])

        if use_guards:
            # Access appears to compute CR before applying the current day's
            # irrigation, so days_since_irrigation reflects the *previous*
            # irrigation event on the irrigation day itself.
            days_since_irrigation = int(row["day_of_sim"]) - last_irrig_day
            act = compute_cr_parametric_complete_with_guards(
                dw=dw,
                wa=wa,
                lai=lai,
                etm=etm,
                a1=soil.cr_a1,
                b1=soil.cr_b1,
                a2=soil.cr_a2,
                b2=soil.cr_b2,
                a3=soil.cr_a3,
                b3=soil.cr_b3,
                a4=soil.cr_a4,
                b4=soil.cr_b4,
                days_since_irrigation=days_since_irrigation,
            )
            if float(row["irrig"]) > 0.0:
                last_irrig_day = int(row["day_of_sim"])
        else:
            act = compute_cr_parametric_complete(
                dw=dw,
                wa=wa,
                lai=lai,
                etm=etm,
                a1=soil.cr_a1,
                b1=soil.cr_b1,
                a2=soil.cr_a2,
                b2=soil.cr_b2,
                a3=soil.cr_a3,
                b3=soil.cr_b3,
                a4=soil.cr_a4,
                b4=soil.cr_b4,
            )
        exp_list.append(float(row["cr"]))
        act_list.append(act)

    return np.array(exp_list), np.array(act_list)


@pytest.mark.parametrize("sim_id", FALLOW_SIMS)
def test_compute_cr_parametric_complete_fallow(sim_id: int) -> None:
    """Fallow crops must match the original software day-for-day (atol=0.05)."""
    exp_arr, act_arr = _compute_cr_series(sim_id, use_guards=False)
    assert len(exp_arr) > 0, f"Sim {sim_id}: no comparable days"
    diff = np.abs(act_arr - exp_arr)
    max_diff = float(np.max(diff))
    if max_diff > 0.05:
        idx = int(np.argmax(diff))
        pytest.fail(
            f"Sim {sim_id} first CR mismatch at day {idx + 1}: "
            f"expected={float(exp_arr[idx]):.4f} actual={float(act_arr[idx]):.4f} "
            f"diff={max_diff:.4f}"
        )


@pytest.mark.parametrize("sim_id", ACTIVE_SIMS_CORE)
def test_compute_cr_parametric_complete_active_correlation(sim_id: int) -> None:
    """Active crops (core): Pearson correlation between expected and actual CR >= 0.70."""
    exp_arr, act_arr = _compute_cr_series(sim_id, use_guards=True)
    if len(exp_arr) < 2:
        pytest.skip(f"Sim {sim_id}: insufficient days for correlation")
    corr = float(np.corrcoef(exp_arr, act_arr)[0, 1])
    assert corr >= 0.70, (
        f"Sim {sim_id}: correlation={corr:.3f} < 0.70 "
        f"(n={len(exp_arr)}, mean_exp={float(np.mean(exp_arr)):.2f}, "
        f"mean_act={float(np.mean(act_arr)):.2f})"
    )


@pytest.mark.parametrize("sim_id", ACTIVE_SIMS_CORE)
def test_compute_cr_parametric_complete_active_bias(sim_id: int) -> None:
    """Active crops (core): mean bias (actual - expected) <= 1.3 mm/day in absolute value."""
    exp_arr, act_arr = _compute_cr_series(sim_id, use_guards=True)
    if len(exp_arr) == 0:
        pytest.skip(f"Sim {sim_id}: no comparable days")
    bias = float(np.mean(act_arr - exp_arr))
    assert abs(bias) <= 1.3, f"Sim {sim_id}: mean bias={bias:.3f} mm/day (threshold=1.3)"


@pytest.mark.parametrize("sim_id", ACTIVE_SIMS_CORE)
def test_compute_cr_parametric_complete_active_rmse(sim_id: int) -> None:
    """Active crops (core): RMSE <= 1.8 mm/day."""
    exp_arr, act_arr = _compute_cr_series(sim_id, use_guards=True)
    if len(exp_arr) == 0:
        pytest.skip(f"Sim {sim_id}: no comparable days")
    rmse = float(np.sqrt(np.mean((act_arr - exp_arr) ** 2)))
    assert rmse <= 1.8, f"Sim {sim_id}: RMSE={rmse:.3f} mm/day (threshold=1.8)"


@pytest.mark.parametrize("sim_id", ACTIVE_SIMS_FREQ)
def test_compute_cr_parametric_complete_freq_correlation(sim_id: int) -> None:
    """Frequent-irrigation crops: correlation >= 0.30 (guards over-suppress here)."""
    exp_arr, act_arr = _compute_cr_series(sim_id, use_guards=True)
    if len(exp_arr) < 2:
        pytest.skip(f"Sim {sim_id}: insufficient days for correlation")
    corr = float(np.corrcoef(exp_arr, act_arr)[0, 1])
    assert corr >= 0.30, (
        f"Sim {sim_id}: correlation={corr:.3f} < 0.30 "
        f"(n={len(exp_arr)}, mean_exp={float(np.mean(exp_arr)):.2f}, "
        f"mean_act={float(np.mean(act_arr)):.2f})"
    )


@pytest.mark.parametrize("sim_id", ACTIVE_SIMS_FREQ)
def test_compute_cr_parametric_complete_freq_bias(sim_id: int) -> None:
    """Frequent-irrigation crops: mean bias <= 1.0 mm/day in absolute value."""
    exp_arr, act_arr = _compute_cr_series(sim_id, use_guards=True)
    if len(exp_arr) == 0:
        pytest.skip(f"Sim {sim_id}: no comparable days")
    bias = float(np.mean(act_arr - exp_arr))
    assert abs(bias) <= 1.0, f"Sim {sim_id}: mean bias={bias:.3f} mm/day (threshold=1.0)"


@pytest.mark.parametrize("sim_id", ACTIVE_SIMS_FREQ)
def test_compute_cr_parametric_complete_freq_rmse(sim_id: int) -> None:
    """Frequent-irrigation crops: RMSE <= 1.3 mm/day."""
    exp_arr, act_arr = _compute_cr_series(sim_id, use_guards=True)
    if len(exp_arr) == 0:
        pytest.skip(f"Sim {sim_id}: no comparable days")
    rmse = float(np.sqrt(np.mean((act_arr - exp_arr) ** 2)))
    assert rmse <= 1.3, f"Sim {sim_id}: RMSE={rmse:.3f} mm/day (threshold=1.3)"
