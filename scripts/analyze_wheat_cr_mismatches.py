"""Analyze wheat CR mismatches in detail.

For Sims 3, 4, and 6, this script prints every day where the base Liu 2006
parametric formula diverges from the original Access binary by > 0.001 mm/day,
along with all contextual variables needed to classify the mismatch.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "tests"))
from conftest import load_cr_fixture  # noqa: E402
from simdualkc.auxiliary import compute_cr_parametric_complete
from simdualkc.water_balance import compute_wwp_mm, compute_wwp_mm_multilayer

WHEAT_SIMS = [3, 4, 6]


def _lai_from_fc(fc: float, k_ext: float = 0.5) -> float:
    if fc <= 0.0:
        return 0.0
    if fc >= 0.999:
        return 10.0
    return -math.log(1.0 - fc) / k_ext


def analyze_sim(sim_id: int) -> None:
    config, expected = load_cr_fixture(sim_id)
    soil = config.soil

    wt_by_date = {}
    for rec in config.climate:
        if rec.wt_depth_m is not None:
            wt_by_date[rec.date] = rec.wt_depth_m

    precip_by_date = {}
    for rec in config.climate:
        precip_by_date[rec.date] = rec.precip

    lai_by_date = {}
    if config.crop.lai_dates and config.crop.lai_values:
        for ld, lv in zip(config.crop.lai_dates, config.crop.lai_values, strict=False):
            lai_by_date[ld] = lv

    k_ext = getattr(config.crop, "k_ext", 0.5) or 0.5
    prev_dr = config.initial_conditions.dr0
    last_irrig_day = 0
    last_irrig_depth = 0.0

    rows = []
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
            wwp_mm = (
                compute_wwp_mm_multilayer(soil.layers, zr)
                if soil.uses_multilayer() and soil.layers
                else compute_wwp_mm(soil.theta_wp, zr)
            )
            w = wa + wwp_mm

        lai = lai_by_date.get(d, _lai_from_fc(float(row["fc"]), k_ext))
        etm = float(row["kcb"]) * float(row["eto"])
        days_since_irrigation = int(row["day_of_sim"]) - last_irrig_day
        precip = precip_by_date.get(d, 0.0)
        irrig = float(row["irrig"])

        act = compute_cr_parametric_complete(
            dw=dw,
            zr_m=zr,
            w=w,
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

        exp_cr = float(row["cr"])
        diff = abs(act - exp_cr)

        if diff > 0.001:
            rows.append(
                {
                    "sim_id": sim_id,
                    "day": int(row["day_of_sim"]),
                    "date": d,
                    "expected": exp_cr,
                    "actual": act,
                    "diff": diff,
                    "dw": dw,
                    "w": w,
                    "lai": lai,
                    "etm": etm,
                    "days_since_irrigation": days_since_irrigation,
                    "last_irrig_depth_mm": last_irrig_depth,
                    "precip": precip,
                    "irrig": irrig,
                }
            )

        if irrig > 0.0:
            last_irrig_day = int(row["day_of_sim"])
            last_irrig_depth = irrig

        prev_dr = float(row["dr"])

    df = pd.DataFrame(rows)
    print(f"\n{'='*100}")
    print(f"Sim {sim_id}: {len(df)} mismatch days (atol=0.001)")
    print(f"{'='*100}")
    if len(df) == 0:
        return

    for _, r in df.iterrows():
        print(
            f"day={r['day']:3d} date={r['date']}  "
            f"exp={r['expected']:7.4f} act={r['actual']:7.4f} diff={r['diff']:7.4f}  |  "
            f"Dw={r['dw']:.3f} W={r['w']:.1f} LAI={r['lai']:.2f} ETm={r['etm']:.2f}  |  "
            f"dsi={r['days_since_irrigation']:2d} last_irr={r['last_irrig_depth_mm']:.1f}  |  "
            f"P={r['precip']:.1f} I={r['irrig']:.1f}"
        )

    # Summary stats
    irrig_dates = set()
    big_rain_dates = set()
    for _, row in expected.iterrows():
        if float(row["irrig"]) > 0.0:
            irrig_dates.add(int(row["day_of_sim"]))
        if float(row["precip"]) > 10.0:
            big_rain_dates.add(int(row["day_of_sim"]))

    def near_event(day: int, event_days: set[int], window: int = 3) -> bool:
        return any(abs(day - ed) <= window for ed in event_days)

    near_irrig = df["day"].apply(lambda d: near_event(d, irrig_dates)).sum()
    near_rain = df["day"].apply(lambda d: near_event(d, big_rain_dates)).sum()
    near_either = df["day"].apply(lambda d: near_event(d, irrig_dates | big_rain_dates)).sum()
    threshold_flicker = df["etm"].apply(lambda e: 3.5 <= e <= 4.5).sum()
    early_lai = df["lai"].apply(lambda lv: lv < 0.3).sum()

    print(f"\n--- Summary for Sim {sim_id} ---")
    print(f"Total mismatch days: {len(df)}")
    print(f"Near irrigation (<=3 days): {near_irrig} ({100*near_irrig/len(df):.1f}%)")
    print(f"Near >10 mm rain (<=3 days): {near_rain} ({100*near_rain/len(df):.1f}%)")
    print(f"Near either event: {near_either} ({100*near_either/len(df):.1f}%)")
    tf_pct = 100 * threshold_flicker / len(df)
    print(f"ETm in 3.5-4.5 band (threshold-flicker): {threshold_flicker} ({tf_pct:.1f}%)")
    print(f"LAI < 0.3 (early season): {early_lai} ({100*early_lai/len(df):.1f}%)")


def main() -> None:
    for sim_id in WHEAT_SIMS:
        analyze_sim(sim_id)


if __name__ == "__main__":
    main()
