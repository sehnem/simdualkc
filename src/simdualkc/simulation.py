"""Daily simulation orchestrator — SIMDualKc Layer 1.

Implements the full daily loop.
"""

import datetime

import pandas as pd

from simdualkc.auxiliary import (
    adjust_cn_for_moisture,
    compute_cr_constant,
    compute_cr_parametric,
    compute_cr_parametric_complete,
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
from simdualkc.irrigation import (
    apply_delivery_constraints,
    compute_irrigation_depth,
    get_days_to_harvest,
    get_mad_for_day,
    get_min_interval_for_date,
    get_target_pct_taw_for_day,
    should_trigger_irrigation,
)
from simdualkc.kcb import (
    compute_kcb_density,
    compute_kcb_full,
    compute_kcb_with_groundcover,
    compute_kd,
    get_fc,
    get_forage_cycle_and_day,
    get_forage_stage,
    get_lai,
    get_stage,
    interpolate_forage_fc,
    interpolate_forage_kcb,
    interpolate_forage_param,
    interpolate_growth_param,
    interpolate_kcb,
    is_forage_cut_day,
)
from simdualkc.models import (
    ClimateRecord,
    CRMethod,
    CropParams,
    DailyResult,
    DPMethod,
    FarmPondConstraint,
    IrrigationEvent,
    SimulationConfig,
    SimulationResult,
)
from simdualkc.reporting import compute_simulation_summary
from simdualkc.water_balance import (
    compute_etc_act,
    compute_ks,
    compute_ks_salinity,
    compute_raw,
    compute_taw,
    compute_taw_multilayer,
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
    last_irrigation_day = 0

    pond_storage_mm = 0.0
    farm_pond: FarmPondConstraint | None = None
    if (
        config.irrigation_strategy.strategy_type == "mad_threshold"
        and config.irrigation_strategy.mad_threshold
        and config.irrigation_strategy.mad_threshold.delivery
    ):
        farm_pond = config.irrigation_strategy.mad_threshold.delivery.farm_pond
    elif (
        config.irrigation_strategy.strategy_type == "deficit"
        and config.irrigation_strategy.deficit
        and config.irrigation_strategy.deficit.delivery
    ):
        farm_pond = config.irrigation_strategy.deficit.delivery.farm_pond
    if farm_pond is not None:
        pond_storage_mm = farm_pond.initial_storage_mm

    t_act_sum = 0.0
    t_pot_sum = 0.0

    for day_idx, climate in enumerate(config.climate):
        day_of_sim = day_idx + 1  # 1-based
        date = climate.date
        eto = climate.eto
        precip = climate.precip
        u2 = climate.u2
        rh_min = climate.rh_min

        is_forage_mode = crop.is_forage and crop.forage_params is not None

        # Interpolate growth parameters (forage or standard)
        if is_forage_mode and crop.forage_params is not None:
            zr = interpolate_forage_param(day_of_sim, crop.forage_params, "zr")
            h = interpolate_forage_param(day_of_sim, crop.forage_params, "h")
            fc = interpolate_forage_fc(day_of_sim, crop.forage_params)
            p = interpolate_forage_param(day_of_sim, crop.forage_params, "p")
            cycle_idx, day_in_cycle = get_forage_cycle_and_day(day_of_sim, crop.forage_params)
            stg = get_forage_stage(
                day_in_cycle,
                crop.forage_params.cycles[min(cycle_idx, len(crop.forage_params.cycles) - 1)],
            )
            stage = stg
        else:
            zr = interpolate_growth_param(day_of_sim, crop, "zr")
            h = interpolate_growth_param(day_of_sim, crop, "h")
            fc = get_fc(day_of_sim, crop)
            p = interpolate_growth_param(day_of_sim, crop, "p")
            stage = get_stage(day_of_sim, crop)

        # Read met + interpolate / adjust Kcb (forage or standard)
        if is_forage_mode and crop.forage_params is not None:
            kcb = interpolate_forage_kcb(day_of_sim, crop.forage_params, u2, rh_min)
        else:
            kcb_tab = interpolate_kcb(day_of_sim, crop, u2, rh_min)
            kcb_full = compute_kcb_full(kcb_tab, u2, rh_min, h)
            kd_val = compute_kd(fc, h, crop.ml)
            if config.groundcover:
                kcb = compute_kcb_with_groundcover(kcb_full, config.groundcover.kcb_cover, kd_val)
            else:
                kcb = compute_kcb_density(crop.kc_min, kd_val, kcb_full)

        # Get irrigation for this day (manual + automated)
        irrig, fw = _get_irrigation(date, config.irrigation, config.fw_base)

        # Manual irrigation resets the interval timer for automated scheduling
        if irrig > 0.0:
            last_irrigation_day = day_of_sim

        if farm_pond is not None:
            for supply in farm_pond.supplies:
                if supply.date == date:
                    pond_storage_mm += supply.depth_mm
                    if farm_pond.max_storage_mm is not None:
                        pond_storage_mm = min(pond_storage_mm, farm_pond.max_storage_mm)

        # Automated irrigation (MAD threshold or deficit)
        strat = config.irrigation_strategy
        if strat.strategy_type == "mad_threshold" and strat.mad_threshold:
            mad = get_mad_for_day(day_of_sim, crop, strat.mad_threshold)
            days_to_harvest = get_days_to_harvest(day_of_sim, crop)
            taw_for_irrig = (
                compute_taw_multilayer(soil.layers, zr)
                if soil.uses_multilayer() and soil.layers
                else compute_taw(soil.theta_fc, soil.theta_wp, zr)
            )
            delivery = strat.mad_threshold.delivery
            min_interval = get_min_interval_for_date(
                date,
                delivery.interval_schedule if delivery else None,
                strat.mad_threshold.min_interval_days,
            )
            if should_trigger_irrigation(
                dr=dr,
                taw=taw_for_irrig,
                mad_fraction=mad,
                days_to_harvest=days_to_harvest,
                harvest_stop_days=strat.mad_threshold.days_before_harvest_stop,
                last_irrigation_day=last_irrigation_day,
                current_day=day_of_sim,
                min_interval=min_interval,
            ):
                target_pct = get_target_pct_taw_for_day(day_of_sim, crop, strat.mad_threshold)
                irrig_auto = compute_irrigation_depth(dr, taw_for_irrig, target_pct)
                irrig_auto = apply_delivery_constraints(irrig_auto, stage, delivery)
                if farm_pond is not None and irrig_auto > 0.0:
                    irrig_auto = min(irrig_auto, pond_storage_mm)
                    pond_storage_mm -= irrig_auto
                if irrig_auto > 0.0:
                    irrig += irrig_auto
                    last_irrigation_day = day_of_sim
        elif strat.strategy_type == "deficit" and strat.deficit:
            mad = get_mad_for_day(day_of_sim, crop, strat.deficit)
            days_to_harvest = get_days_to_harvest(day_of_sim, crop)
            taw_for_irrig = (
                compute_taw_multilayer(soil.layers, zr)
                if soil.uses_multilayer() and soil.layers
                else compute_taw(soil.theta_fc, soil.theta_wp, zr)
            )
            delivery = strat.deficit.delivery
            min_interval = get_min_interval_for_date(
                date,
                delivery.interval_schedule if delivery else None,
                strat.deficit.min_interval_days,
            )
            if should_trigger_irrigation(
                dr=dr,
                taw=taw_for_irrig,
                mad_fraction=mad,
                days_to_harvest=days_to_harvest,
                harvest_stop_days=strat.deficit.days_before_harvest_stop,
                last_irrigation_day=last_irrigation_day,
                current_day=day_of_sim,
                min_interval=min_interval,
            ):
                target_pct = get_target_pct_taw_for_day(day_of_sim, crop, strat.deficit)
                irrig_auto = compute_irrigation_depth(dr, taw_for_irrig, target_pct)
                irrig_auto = apply_delivery_constraints(irrig_auto, stage, delivery)
                if farm_pond is not None and irrig_auto > 0.0:
                    irrig_auto = min(irrig_auto, pond_storage_mm)
                    pond_storage_mm -= irrig_auto
                if irrig_auto > 0.0:
                    irrig += irrig_auto
                    last_irrigation_day = day_of_sim

        # Kc_max
        kc_max = compute_kc_max(kcb, u2, rh_min, h)

        # fewi, fewp, W, Kr coefficients
        f_mulch = config.mulch.f_mulch if config.mulch else 0.0
        kr_mulch = config.mulch.kr_mulch if config.mulch else 1.0
        fewi, fewp = compute_few(fc, fw, f_mulch=f_mulch, kr_mulch=kr_mulch)

        w = compute_evaporation_weight(fewi, fewp, soil.tew, dei, dep)

        kri = compute_kr(soil.tew, soil.rew, dei)
        krp = compute_kr(soil.tew, soil.rew, dep)

        # Ke coefficients
        kei, kep, ke = compute_ke(kri, krp, w, kc_max, kcb, fewi, fewp)

        # Surface balance: RO, then evaporative layer depletion
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

        # Ks (using previous day's Dr and salinity)
        if soil.uses_multilayer() and soil.layers:
            taw = compute_taw_multilayer(soil.layers, zr)
        else:
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

        # ETc_act
        etc_act = compute_etc_act(ks, kcb, ke, eto)
        transp_act = ks * kcb * eto
        evap_act = ke * eto

        t_act_sum += transp_act
        t_pot_sum += kcb * eto

        # Capillary rise
        cr = _compute_cr(config, dr, raw, climate, crop, day_of_sim)

        # Root-zone depletion update + deep percolation
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

        # Record and advance state
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

        # Cut day: cap depletion to post-cut TAW (root depth shrinks)
        if crop.is_forage:
            fp_cut = crop.forage_params
            if fp_cut is not None and is_forage_cut_day(day_of_sim, fp_cut):
                zr_next = fp_cut.min_root_m
                taw_next = (
                    compute_taw_multilayer(soil.layers, zr_next)
                    if soil.uses_multilayer() and soil.layers
                    else compute_taw(soil.theta_fc, soil.theta_wp, zr_next)
                )
                dr = min(dr, taw_next)

    y_a = None
    decrease_pct = None
    if config.yield_params:
        y_a, decrease_pct = compute_yield_decrease_transpiration(
            t_act_sum,
            t_pot_sum,
            config.yield_params.k_y,
            config.yield_params.y_m,
        )

    summary = compute_simulation_summary(
        results,
        config.yield_params,
        config.salinity,
    )
    return SimulationResult(
        daily_results=results,
        yield_act=y_a,
        yield_decrease_pct=decrease_pct,
        summary=summary,
    )


def _compute_cr(
    config: SimulationConfig,
    dr: float,
    raw: float,
    climate: ClimateRecord,
    crop: CropParams,
    day_of_sim: int,
) -> float:
    """Dispatch capillary rise computation based on configured method."""
    if config.cr_method == CRMethod.NONE:
        return 0.0

    if config.cr_method == CRMethod.CONSTANT:
        gmax = config.soil.gmax or 0.0
        return compute_cr_constant(gmax, dr, raw)

    if config.cr_method == CRMethod.PARAMETRIC:
        soil = config.soil
        has_full = all(
            getattr(soil, f"cr_{name}") is not None
            for name in ["a1", "b1", "a2", "b2", "a3", "b3", "a4", "b4"]
        )
        has_simplified = all(
            getattr(soil, f"cr_simplified_{name}") is not None for name in ["a", "b", "c", "d"]
        )
        lai = get_lai(day_of_sim, crop)
        wt_depth_m = climate.wt_depth_m
        if has_full and wt_depth_m is not None:
            assert soil.cr_a1 is not None
            assert soil.cr_b1 is not None
            assert soil.cr_a2 is not None
            assert soil.cr_b2 is not None
            assert soil.cr_a3 is not None
            assert soil.cr_b3 is not None
            assert soil.cr_a4 is not None
            assert soil.cr_b4 is not None
            return compute_cr_parametric_complete(
                z_wt=wt_depth_m,
                lai=lai,
                a1=soil.cr_a1,
                b1=soil.cr_b1,
                a2=soil.cr_a2,
                b2=soil.cr_b2,
                a3=soil.cr_a3,
                b3=soil.cr_b3,
                a4=soil.cr_a4,
                b4=soil.cr_b4,
            )
        if has_simplified and wt_depth_m is not None:
            assert soil.cr_simplified_a is not None
            assert soil.cr_simplified_b is not None
            assert soil.cr_simplified_c is not None
            assert soil.cr_simplified_d is not None
            return compute_cr_parametric(
                z_wt=wt_depth_m,
                lai=lai,
                a_c=soil.cr_simplified_a,
                b_c=soil.cr_simplified_b,
                c_c=soil.cr_simplified_c,
                d_c=soil.cr_simplified_d,
            )
        return 0.0
    return 0.0


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
