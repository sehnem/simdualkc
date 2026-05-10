"""Investigate CR mismatch hypotheses and compare metrics across all active sims.

Hypotheses tested:
  baseline  - current guards (LAI<0.3+ETm<=4, 2-day post-irrig for >20mm)
  H-A1-88   - W/Wc > 0.88 suppresses CR after irrigation or rain
  H-A1-90   - W/Wc > 0.90 suppresses CR after irrigation or rain
  H-A1-92   - W/Wc > 0.92 suppresses CR after irrigation or rain
  H-A2      - depth-tiered day guard (2/5/7/10 days by irrigation depth)
  H-Rain-3  - post-rain suppression (P>10mm => 3 days)
  H-Rain-5  - post-rain suppression (P>10mm => 5 days)
  H-Rain-7  - post-rain suppression (P>10mm => 7 days)
  H-A1+Rain - best W/Wc combined with post-rain suppression
  H7        - orchard-only 3-day smoothed ETm for threshold test only
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "tests"))
from conftest import load_cr_fixture
from simdualkc.auxiliary import compute_cr_parametric_complete
from simdualkc.water_balance import compute_wwp_mm, compute_wwp_mm_multilayer

WHEAT_SIMS = [3, 4, 6, 7, 8, 9, 10, 11, 12]
ORCHARD_SIMS = [34, 35]
ALL_ACTIVE = WHEAT_SIMS + ORCHARD_SIMS

RAIN_THRESH_MM = 10.0


def _lai_from_fc(fc: float, k_ext: float = 0.5) -> float:
    if fc <= 0.0:
        return 0.0
    if fc >= 0.999:
        return 10.0
    return -math.log(1.0 - fc) / k_ext


def _suppress_days_tiered(depth_mm: float) -> int:
    """H-A2 depth-tiered day guard."""
    if depth_mm > 100:
        return 10
    if depth_mm > 80:
        return 7
    if depth_mm > 50:
        return 5
    if depth_mm > 20:
        return 2
    return 0


def _metrics(exp: np.ndarray, act: np.ndarray) -> dict:
    bias = float(np.mean(act - exp))
    mae = float(np.mean(np.abs(act - exp)))
    rmse = float(np.sqrt(np.mean((act - exp) ** 2)))
    if len(exp) >= 2 and np.std(exp) > 1e-9 and np.std(act) > 1e-9:
        corr = float(np.corrcoef(exp, act)[0, 1])
    else:
        corr = float("nan")
    return {"bias": bias, "mae": mae, "rmse": rmse, "corr": corr, "n": len(exp)}


def _compute_cr_series_all_hypotheses(sim_id: int) -> dict[str, dict]:
    """Compute CR under all hypotheses for a single sim.
    Returns dict of hypothesis_name -> metrics dict.
    """
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
        print(f"  Sim {sim_id}: skipping (missing CR coefficients)")
        return {}

    k_ext = getattr(config.crop, "k_ext", 0.5) or 0.5

    wt_by_date = {rec.date: rec.wt_depth_m for rec in config.climate if rec.wt_depth_m is not None}

    # Collect daily data
    rows = []
    prev_dr = config.initial_conditions.dr0
    for _, row in expected.iterrows():
        d = row["date"]
        wt_depth_m = wt_by_date.get(d)
        if wt_depth_m is None or pd.isna(wt_depth_m):
            prev_dr = float(row["dr"])
            continue

        zr = float(row["zr"])
        dw = wt_depth_m

        if soil.cr_theta_fc is not None:
            w = soil.cr_theta_fc * zr * 1000.0 - prev_dr
        else:
            wa = float(row["taw"]) - prev_dr
            if soil.uses_multilayer() and soil.layers:
                wwp_mm = compute_wwp_mm_multilayer(soil.layers, zr)
            else:
                wwp_mm = compute_wwp_mm(soil.theta_wp, zr)
            w = wa + wwp_mm

        lai = _lai_from_fc(float(row["fc"]), k_ext)
        etm = float(row["kcb"]) * float(row["eto"])
        day_of_sim = int(row["day_of_sim"])
        irrig = float(row["irrig"])
        precip = float(row.get("precip", 0.0))
        cr_exp = float(row["cr"])

        # Compute wc for H-A1
        a1, b1 = soil.cr_a1, soil.cr_b1
        dw_clamped = max(dw, zr)
        wc = a1 * (dw_clamped**b1)

        rows.append(
            {
                "day_of_sim": day_of_sim,
                "dw": dw,
                "zr": zr,
                "w": w,
                "wc": wc,
                "lai": lai,
                "etm": etm,
                "irrig": irrig,
                "precip": precip,
                "cr_exp": cr_exp,
            }
        )
        prev_dr = float(row["dr"])

    if not rows:
        return {}

    df = pd.DataFrame(rows)

    # Precompute CR base (no guards)
    cr_base = np.array(
        [
            compute_cr_parametric_complete(
                dw=r["dw"],
                w=r["w"],
                lai=r["lai"],
                etm=r["etm"],
                a1=soil.cr_a1,
                b1=soil.cr_b1,
                a2=soil.cr_a2,
                b2=soil.cr_b2,
                a3=soil.cr_a3,
                b3=soil.cr_b3,
                a4=soil.cr_a4,
                b4=soil.cr_b4,
                zr_m=r["zr"],
            )
            for r in rows
        ]
    )
    cr_exp = df["cr_exp"].values

    # Now compute per-hypothesis CR arrays
    results = {}

    # ---- BASELINE ----
    last_irrig_day = 0
    last_irrig_depth = 0.0
    cr_baseline = np.zeros(len(rows))
    for i, r in enumerate(rows):
        days_since_irrig = r["day_of_sim"] - last_irrig_day
        lai = r["lai"]
        etm = r["etm"]
        cr = cr_base[i]
        if lai < 0.3 and etm <= 4.0 or days_since_irrig <= 2 and last_irrig_depth > 20.0:
            cr = 0.0
        cr_baseline[i] = cr
        if r["irrig"] > 0.0:
            last_irrig_depth = r["irrig"]
            last_irrig_day = r["day_of_sim"]
    results["baseline"] = _metrics(cr_exp, cr_baseline)

    # ---- H-A1 (W/Wc threshold) ----
    for thresh in [0.88, 0.90, 0.92]:
        name = f"H-A1-{int(thresh*100)}"
        last_irrig_day = 0
        last_irrig_depth = 0.0
        cr_arr = np.zeros(len(rows))
        for i, r in enumerate(rows):
            days_since_irrig = r["day_of_sim"] - last_irrig_day
            lai = r["lai"]
            etm = r["etm"]
            w = r["w"]
            wc = r["wc"]
            cr = cr_base[i]
            # Guard 1: early season
            if lai < 0.3 and etm <= 4.0:
                cr = 0.0
            else:
                # Guard 2 (H-A1): W/Wc > threshold suppresses CR
                # This covers both post-irrigation and post-rain
                if wc > 0 and (w / wc) > thresh:
                    cr = 0.0
            cr_arr[i] = cr
            if r["irrig"] > 0.0:
                last_irrig_depth = r["irrig"]
                last_irrig_day = r["day_of_sim"]
        results[name] = _metrics(cr_exp, cr_arr)

    # ---- H-A2 (depth-tiered day guard) ----
    last_irrig_day = 0
    last_irrig_depth = 0.0
    cr_arr = np.zeros(len(rows))
    for i, r in enumerate(rows):
        days_since_irrig = r["day_of_sim"] - last_irrig_day
        lai = r["lai"]
        etm = r["etm"]
        cr = cr_base[i]
        if lai < 0.3 and etm <= 4.0:
            cr = 0.0
        else:
            suppress = _suppress_days_tiered(last_irrig_depth)
            if days_since_irrig <= suppress:
                cr = 0.0
        cr_arr[i] = cr
        if r["irrig"] > 0.0:
            last_irrig_depth = r["irrig"]
            last_irrig_day = r["day_of_sim"]
    results["H-A2"] = _metrics(cr_exp, cr_arr)

    # ---- H-Rain (post-rain suppression) ----
    for n_days in [3, 5, 7]:
        name = f"H-Rain-{n_days}"
        last_irrig_day = 0
        last_irrig_depth = 0.0
        last_rain_day = 0
        last_rain_mm = 0.0
        cr_arr = np.zeros(len(rows))
        for i, r in enumerate(rows):
            days_since_irrig = r["day_of_sim"] - last_irrig_day
            days_since_rain = r["day_of_sim"] - last_rain_day
            lai = r["lai"]
            etm = r["etm"]
            precip = r["precip"]
            cr = cr_base[i]
            if (
                lai < 0.3
                and etm <= 4.0
                or days_since_irrig <= 2
                and last_irrig_depth > 20.0
                or days_since_rain <= n_days
                and last_rain_mm > RAIN_THRESH_MM
            ):
                cr = 0.0
            cr_arr[i] = cr
            if r["irrig"] > 0.0:
                last_irrig_depth = r["irrig"]
                last_irrig_day = r["day_of_sim"]
            if precip > RAIN_THRESH_MM:
                last_rain_day = r["day_of_sim"]
                last_rain_mm = precip
        results[name] = _metrics(cr_exp, cr_arr)

    # ---- H-A1+Rain combined (W/Wc=0.90 + H-Rain-5) ----
    last_irrig_day = 0
    last_irrig_depth = 0.0
    last_rain_day = 0
    last_rain_mm = 0.0
    cr_arr = np.zeros(len(rows))
    for i, r in enumerate(rows):
        days_since_irrig = r["day_of_sim"] - last_irrig_day
        days_since_rain = r["day_of_sim"] - last_rain_day
        lai = r["lai"]
        etm = r["etm"]
        w = r["w"]
        wc = r["wc"]
        precip = r["precip"]
        cr = cr_base[i]
        if lai < 0.3 and etm <= 4.0:
            cr = 0.0
        else:
            if (
                wc > 0
                and (w / wc) > 0.90
                or days_since_rain <= 5
                and last_rain_mm > RAIN_THRESH_MM
            ):
                cr = 0.0
        cr_arr[i] = cr
        if r["irrig"] > 0.0:
            last_irrig_depth = r["irrig"]
            last_irrig_day = r["day_of_sim"]
        if precip > RAIN_THRESH_MM:
            last_rain_day = r["day_of_sim"]
            last_rain_mm = precip
    results["H-A1+Rain"] = _metrics(cr_exp, cr_arr)

    # ---- H7 (orchard-only 3-day smoothed ETm for guard test) ----
    # Only relevant for orchard sims; for wheat it's same as baseline
    last_irrig_day = 0
    last_irrig_depth = 0.0
    etm_arr = df["etm"].values
    cr_arr = np.zeros(len(rows))
    for i, r in enumerate(rows):
        days_since_irrig = r["day_of_sim"] - last_irrig_day
        lai = r["lai"]
        etm = r["etm"]
        # 3-day moving average ETm (inclusive)
        etm_smooth = float(np.mean(etm_arr[max(0, i - 2) : i + 1]))
        cr = cr_base[i]
        if lai < 0.3 and etm_smooth <= 4.0 or days_since_irrig <= 2 and last_irrig_depth > 20.0:
            cr = 0.0
        cr_arr[i] = cr
        if r["irrig"] > 0.0:
            last_irrig_depth = r["irrig"]
            last_irrig_day = r["day_of_sim"]
    results["H7"] = _metrics(cr_exp, cr_arr)

    # ---- H-A2+Rain (tiered days + post-rain) ----
    last_irrig_day = 0
    last_irrig_depth = 0.0
    last_rain_day = 0
    last_rain_mm = 0.0
    cr_arr = np.zeros(len(rows))
    for i, r in enumerate(rows):
        days_since_irrig = r["day_of_sim"] - last_irrig_day
        days_since_rain = r["day_of_sim"] - last_rain_day
        lai = r["lai"]
        etm = r["etm"]
        precip = r["precip"]
        cr = cr_base[i]
        if lai < 0.3 and etm <= 4.0:
            cr = 0.0
        else:
            suppress = _suppress_days_tiered(last_irrig_depth)
            if (
                days_since_irrig <= suppress
                or days_since_rain <= 5
                and last_rain_mm > RAIN_THRESH_MM
            ):
                cr = 0.0
        cr_arr[i] = cr
        if r["irrig"] > 0.0:
            last_irrig_depth = r["irrig"]
            last_irrig_day = r["day_of_sim"]
        if precip > RAIN_THRESH_MM:
            last_rain_day = r["day_of_sim"]
            last_rain_mm = precip
    results["H-A2+Rain"] = _metrics(cr_exp, cr_arr)

    return results


def main() -> None:
    hypotheses = [
        "baseline",
        "H-A1-88",
        "H-A1-90",
        "H-A1-92",
        "H-A2",
        "H-Rain-3",
        "H-Rain-5",
        "H-Rain-7",
        "H-A1+Rain",
        "H7",
        "H-A2+Rain",
    ]

    print("\n" + "=" * 100)
    print("CR HYPOTHESIS INVESTIGATION")
    print("=" * 100)

    # Per-sim results
    all_results: dict[int, dict[str, dict]] = {}
    for sim_id in ALL_ACTIVE:
        print(f"\n--- Sim {sim_id} ---")
        results = _compute_cr_series_all_hypotheses(sim_id)
        all_results[sim_id] = results

        if not results:
            continue

        # Print header
        col_w = 12
        header = f"{'Hypothesis':<14}" + "".join(
            f"{'bias':>{col_w}}{'mae':>{col_w}}{'rmse':>{col_w}}{'corr':>{col_w}}"
        )
        print(f"{'Hypothesis':<14}  {'bias':>8}  {'mae':>8}  {'rmse':>8}  {'corr':>8}")
        print("-" * 60)
        for hyp in hypotheses:
            if hyp not in results:
                continue
            m = results[hyp]
            base = results.get("baseline", {})
            mae_diff = (
                (m["mae"] - base.get("mae", m["mae"])) / base.get("mae", 1.0) * 100 if base else 0
            )
            flag = " *" if abs(mae_diff) >= 5 else ""
            print(
                f"  {hyp:<14} "
                f"bias={m['bias']:+7.3f}  "
                f"mae={m['mae']:6.3f}{flag}  "
                f"rmse={m['rmse']:6.3f}  "
                f"corr={m['corr']:6.3f}"
            )

    # Aggregate summary table
    print("\n\n" + "=" * 100)
    print("AGGREGATE SUMMARY (mean across all active sims)")
    print("=" * 100)
    print(
        f"{'Hypothesis':<14}  {'mean_bias':>10}  {'mean_mae':>10}  {'mean_rmse':>10}  {'mean_corr':>10}  {'mae_vs_baseline':>16}"
    )

    agg: dict[str, list] = {h: [] for h in hypotheses}
    for sim_id, results in all_results.items():
        for hyp in hypotheses:
            if hyp in results:
                agg[hyp].append(results[hyp])

    baseline_mean_mae = np.mean([m["mae"] for m in agg["baseline"]]) if agg["baseline"] else 1.0

    for hyp in hypotheses:
        if not agg[hyp]:
            continue
        m_list = agg[hyp]
        mb = np.mean([m["bias"] for m in m_list])
        mm = np.mean([m["mae"] for m in m_list])
        mr = np.mean([m["rmse"] for m in m_list])
        mc = np.nanmean([m["corr"] for m in m_list])
        mae_pct = (mm - baseline_mean_mae) / baseline_mean_mae * 100
        flag = (
            " ***"
            if mae_pct <= -15
            else (" **" if mae_pct <= -10 else (" *" if mae_pct <= -5 else ""))
        )
        print(
            f"  {hyp:<14}  "
            f"{mb:>+10.3f}  "
            f"{mm:>10.3f}  "
            f"{mr:>10.3f}  "
            f"{mc:>10.3f}  "
            f"{mae_pct:>+14.1f}%{flag}"
        )

    # Wheat-only and orchard-only aggregates
    for group_name, group_ids in [("WHEAT (3-12)", WHEAT_SIMS), ("ORCHARD (34-35)", ORCHARD_SIMS)]:
        print(f"\n--- {group_name} ---")
        print(
            f"{'Hypothesis':<14}  {'mean_bias':>10}  {'mean_mae':>10}  {'mean_rmse':>10}  {'mean_corr':>10}  {'mae_vs_baseline':>16}"
        )
        group_results = {sid: all_results[sid] for sid in group_ids if sid in all_results}
        base_mae_grp = np.mean(
            [
                group_results[sid]["baseline"]["mae"]
                for sid in group_ids
                if sid in group_results and "baseline" in group_results[sid]
            ]
        )
        for hyp in hypotheses:
            vals = [
                group_results[sid][hyp]
                for sid in group_ids
                if sid in group_results and hyp in group_results[sid]
            ]
            if not vals:
                continue
            mb = np.mean([m["bias"] for m in vals])
            mm = np.mean([m["mae"] for m in vals])
            mr = np.mean([m["rmse"] for m in vals])
            mc = np.nanmean([m["corr"] for m in vals])
            mae_pct = (mm - base_mae_grp) / base_mae_grp * 100
            flag = (
                " ***"
                if mae_pct <= -15
                else (" **" if mae_pct <= -10 else (" *" if mae_pct <= -5 else ""))
            )
            print(
                f"  {hyp:<14}  "
                f"{mb:>+10.3f}  "
                f"{mm:>10.3f}  "
                f"{mr:>10.3f}  "
                f"{mc:>10.3f}  "
                f"{mae_pct:>+14.1f}%{flag}"
            )

    # Winner determination
    print("\n\n" + "=" * 100)
    print("WINNER ANALYSIS")
    print("=" * 100)

    # Best for wheat
    wheat_results = {sid: all_results[sid] for sid in WHEAT_SIMS if sid in all_results}
    base_wheat_mae = np.mean(
        [
            wheat_results[sid]["baseline"]["mae"]
            for sid in WHEAT_SIMS
            if sid in wheat_results and "baseline" in wheat_results[sid]
        ]
    )

    best_wheat_hyp = None
    best_wheat_improvement = 0.0
    for hyp in hypotheses:
        if hyp == "baseline":
            continue
        vals = [
            wheat_results[sid][hyp]
            for sid in WHEAT_SIMS
            if sid in wheat_results and hyp in wheat_results[sid]
        ]
        if not vals:
            continue
        mm = np.mean([m["mae"] for m in vals])
        improvement = (base_wheat_mae - mm) / base_wheat_mae * 100
        if improvement > best_wheat_improvement:
            best_wheat_improvement = improvement
            best_wheat_hyp = hyp

    print(f"\nBest for wheat: {best_wheat_hyp} ({best_wheat_improvement:+.1f}% MAE reduction)")

    # Best for orchard
    orch_results = {sid: all_results[sid] for sid in ORCHARD_SIMS if sid in all_results}
    base_orch_mae = np.mean(
        [
            orch_results[sid]["baseline"]["mae"]
            for sid in ORCHARD_SIMS
            if sid in orch_results and "baseline" in orch_results[sid]
        ]
    )

    best_orch_hyp = None
    best_orch_improvement = 0.0
    for hyp in hypotheses:
        if hyp == "baseline":
            continue
        vals = [
            orch_results[sid][hyp]
            for sid in ORCHARD_SIMS
            if sid in orch_results and hyp in orch_results[sid]
        ]
        if not vals:
            continue
        mm = np.mean([m["mae"] for m in vals])
        improvement = (base_orch_mae - mm) / base_orch_mae * 100
        if improvement > best_orch_improvement:
            best_orch_improvement = improvement
            best_orch_hyp = hyp

    print(f"Best for orchard: {best_orch_hyp} ({best_orch_improvement:+.1f}% MAE reduction)")


if __name__ == "__main__":
    main()
