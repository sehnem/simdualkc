"""Daily simulation orchestrator — SIMDualKc Layer 1.

Implements the full daily loop from teoria.md §"Passo-a-Passo", steps 3.1–3.10.
"""

from __future__ import annotations

import datetime

import pandas as pd

from simdualkc.auxiliary import (
    adjust_cn_for_moisture,
    compute_cr_constant,
    compute_cr_parametric,
    compute_dp_parametric,
    compute_runoff_cn,
)
from simdualkc.evaporation import (
    compute_evaporation_weight,
    compute_few,
    compute_kc_max,
    compute_ke,
    compute_kr,
    update_evaporative_depletion,
)
from simdualkc.kcb import (
    compute_kcb_density,
    compute_kcb_full,
    compute_kd,
    get_stage,
    interpolate_growth_param,
    interpolate_kcb,
)
from simdualkc.models import (
    CRMethod,
    DailyResult,
    DPMethod,
    IrrigationEvent,
    SimulationConfig,
    SimulationResult,
)
from simdualkc.water_balance import (
    compute_etc_act,
    compute_ks,
    compute_ks_salinity,
    compute_raw,
    compute_taw,
    update_root_zone_depletion,
)
from simdualkc.yield_model import compute_yield_decrease_transpiration


def _get_irrigation(
    date: datetime.date,
    events: list[IrrigationEvent],
    fw_base: float,
) -> tuple[float, float]:
    """Return (total depth [mm], fw [—]) for irrigation on a given date.

    If multiple events occur on the same day they are summed.
    """
    day_events = [e for e in events if e.date == date]
    if not day_events:
        return 0.0, fw_base
    total_depth = sum(e.depth_mm for e in day_events)
    mean_fw = sum(e.fw for e in day_events) / len(day_events)
    return total_depth, mean_fw


def run_simulation(config: SimulationConfig) -> SimulationResult:
    """Run the SIMDualKc daily simulation loop.

    Implements teoria.md §Passo-a-Passo, steps 3.1–3.10 for each day.

    Args:
        config: Fully validated simulation configuration.

    Returns:
        :class:`~simdualkc.models.SimulationResult` containing one
        :class:`~simdualkc.models.DailyResult` per climate record.
    """
    soil = config.soil
    crop = config.crop
    ic = config.initial_conditions

    # Initialise state from initial conditions (day 0)
    dr = ic.dr0
    dei = ic.dei0
    dep = ic.dep0

    results: list[DailyResult] = []

    t_act_sum = 0.0
    t_pot_sum = 0.0

    for day_idx, climate in enumerate(config.climate):
        day_of_sim = day_idx + 1  # 1-based
        date = climate.date
        eto = climate.eto
        precip = climate.precip
        u2 = climate.u2
        rh_min = climate.rh_min

        # ------------------------------------------------------------------
        # Step 3.1 — Interpolate growth parameters
        # ------------------------------------------------------------------
        zr = interpolate_growth_param(day_of_sim, crop, "zr")
        h = interpolate_growth_param(day_of_sim, crop, "h")
        fc = interpolate_growth_param(day_of_sim, crop, "fc")
        p = interpolate_growth_param(day_of_sim, crop, "p")
        stage = get_stage(day_of_sim, crop)

        # ------------------------------------------------------------------
        # Step 3.2 — Read met + interpolate / adjust Kcb
        # ------------------------------------------------------------------
        kcb_tab = interpolate_kcb(day_of_sim, crop, u2, rh_min)
        kcb_full = compute_kcb_full(kcb_tab, u2, rh_min, h)
        kd = compute_kd(fc, h, crop.ml)
        kcb = compute_kcb_density(crop.kc_min, kd, kcb_full)

        # ------------------------------------------------------------------
        # Step 3.1 — Get irrigation for this day
        # ------------------------------------------------------------------
        irrig, fw = _get_irrigation(date, config.irrigation, config.fw_base)

        # ------------------------------------------------------------------
        # Step 3.3 — Kc_max
        # ------------------------------------------------------------------
        kc_max = compute_kc_max(kcb, u2, rh_min, h)

        # ------------------------------------------------------------------
        # Step 3.4 — fewi, fewp, W, Kr coefficients
        # ------------------------------------------------------------------
        f_mulch = config.mulch.f_mulch if config.mulch else 0.0
        kr_mulch = config.mulch.kr_mulch if config.mulch else 1.0
        fewi, fewp = compute_few(fc, fw, f_mulch=f_mulch, kr_mulch=kr_mulch)

        w = compute_evaporation_weight(fewi, fewp, soil.tew, dei, dep)

        kri = compute_kr(soil.tew, soil.rew, dei)
        krp = compute_kr(soil.tew, soil.rew, dep)

        # ------------------------------------------------------------------
        # Step 3.5 — Ke coefficients
        # ------------------------------------------------------------------
        kei, kep, ke = compute_ke(kri, krp, w, kc_max, kcb, fewi, fewp)

        # ------------------------------------------------------------------
        # Step 3.6 — Surface balance: RO, then evaporative layer depletion
        # ------------------------------------------------------------------
        cn_adj = adjust_cn_for_moisture(soil.cn2, dei, soil.tew)
        ro = compute_runoff_cn(precip, cn_adj)

        # Evaporation from each fraction [mm]
        ei = kei * eto  # irrigated fraction
        ep = kep * eto  # precip-only fraction

        new_dei, dp_ei = update_evaporative_depletion(
            de_prev=dei,
            precip=precip,
            ro=ro,
            irrig=irrig,
            fw=fw,
            e_frac=ei,
            few=fewi,
            tew=soil.tew,
            is_irrigated_fraction=True,
        )
        new_dep, dp_ep = update_evaporative_depletion(
            de_prev=dep,
            precip=precip,
            ro=ro,
            irrig=0.0,  # precipitation fraction receives no irrigation
            fw=fw,
            e_frac=ep,
            few=fewp,
            tew=soil.tew,
            is_irrigated_fraction=False,
        )

        # ------------------------------------------------------------------
        # Step 3.7 — Ks (using previous day's Dr and salinity)
        # ------------------------------------------------------------------
        taw = compute_taw(soil.theta_fc, soil.theta_wp, zr)
        raw = compute_raw(taw, p)
        ks = compute_ks(dr, taw, raw, p)
        
        if config.salinity:
            ks_sal = compute_ks_salinity(
                config.salinity.ec_e,
                config.salinity.ec_threshold,
                config.salinity.b,
                config.salinity.k_y,
            )
            ks *= ks_sal

        # ------------------------------------------------------------------
        # Step 3.8 — ETc_act
        # ------------------------------------------------------------------
        etc_act = compute_etc_act(ks, kcb, ke, eto)
        transp_act = ks * kcb * eto
        evap_act = ke * eto
        
        t_act_sum += transp_act
        t_pot_sum += kcb * eto

        # ------------------------------------------------------------------
        # Step 3.9 — Capillary rise
        # ------------------------------------------------------------------
        cr = _compute_cr(config, dr, raw)

        # ------------------------------------------------------------------
        # Step 3.9 — Root-zone depletion update + deep percolation
        # ------------------------------------------------------------------
        if config.dp_method == DPMethod.PARAMETRIC and soil.a_d and soil.b_d:
            # Parametric: compute storage above field capacity, then DP
            dr_tentative = dr - max(0.0, precip - ro) - irrig - cr + etc_act
            # Storage = amount above field capacity (dr < 0)
            storage = max(0.0, -dr_tentative)
            dp = compute_dp_parametric(storage, soil.a_d, soil.b_d)
            new_dr = max(0.0, min(dr_tentative + dp, taw))
        else:
            new_dr, dp = update_root_zone_depletion(
                dr_prev=dr,
                precip=precip,
                ro=ro,
                irrig=irrig,
                cr=cr,
                etc_act=etc_act,
                taw=taw,
            )

        # ------------------------------------------------------------------
        # Record and advance state
        # ------------------------------------------------------------------
        results.append(
            DailyResult(
                date=date,
                day_of_sim=day_of_sim,
                stage=stage,
                eto=eto,
                precip=precip,
                irrig=irrig,
                ro=ro,
                kcb=kcb,
                ke=ke,
                kei=kei,
                kep=kep,
                ks=ks,
                kc_max=kc_max,
                etc_act=etc_act,
                transp_act=transp_act,
                evap_act=evap_act,
                dr=new_dr,
                dei=new_dei,
                dep=new_dep,
                dp=dp,
                dp_ei=dp_ei,
                dp_ep=dp_ep,
                cr=cr,
                taw=taw,
                raw=raw,
                zr=zr,
                fc=fc,
                h=h,
                p=p,
            )
        )

        # Advance state for next day
        dr = new_dr
        dei = new_dei
        dep = new_dep

    y_a = None
    decrease_pct = None
    if config.yield_params:
        y_a, decrease_pct = compute_yield_decrease_transpiration(
            t_act_sum,
            t_pot_sum,
            config.yield_params.k_y,
            config.yield_params.y_m,
        )

    return SimulationResult(
        daily_results=results,
        yield_act=y_a,
        yield_decrease_pct=decrease_pct,
    )


def _compute_cr(config: SimulationConfig, dr: float, raw: float) -> float:
    """Dispatch capillary rise computation based on configured method."""
    if config.cr_method == CRMethod.NONE:
        return 0.0

    if config.cr_method == CRMethod.CONSTANT:
        gmax = config.soil.gmax or 0.0
        return compute_cr_constant(gmax, dr, raw)

    # PARAMETRIC — requires additional parameters not yet in SoilParams;
    # returns 0.0 as a safe stub until Liu et al. params are provided.
    return compute_cr_parametric(
        z_wt=1.0,  # stub: 1 m depth to water table
        lai=1.0,  # stub: LAI = 1
        a_c=0.0,
        b_c=1.0,
        c_c=0.0,
        d_c=1.0,
    )


def to_dataframe(result: SimulationResult) -> pd.DataFrame:
    """Convert a :class:`~simdualkc.models.SimulationResult` to a pandas DataFrame.

    Args:
        result: Simulation output.

    Returns:
        DataFrame with one row per simulated day and a DatetimeIndex.
    """
    df = result.to_dataframe()
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")
