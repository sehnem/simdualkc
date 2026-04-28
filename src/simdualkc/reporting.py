"""Seasonal summary and yield loss reporting.

Computes aggregated stress metrics, irrigation statistics, and yield loss tables.
"""

import datetime

from simdualkc.models import (
    DailyResult,
    IrrigationSummary,
    SalinityParams,
    SimulationSummary,
    StressSummary,
    YieldParams,
)


def compute_stress_summary(
    daily_results: list[DailyResult],
    yield_params: YieldParams | None,
    salinity_params: SalinityParams | None,
) -> StressSummary:
    """Compute seasonal stress metrics from daily results."""
    total_transp_pot = sum(r.kcb * r.eto for r in daily_results)
    total_transp_act = sum(r.transp_act for r in daily_results)
    total_transp_deficit = total_transp_pot - total_transp_act
    transp_deficit_pct = (
        100.0 * total_transp_deficit / total_transp_pot if total_transp_pot > 0 else 0.0
    )

    days_with_stress = sum(1 for r in daily_results if r.ks < 1.0)
    days_severe_stress = sum(1 for r in daily_results if r.ks < 0.5)

    # Yield decrease from water stress (Stewart: 1 - Ya/Ym = Ky * (1 - Ta/Tc))
    if total_transp_pot > 0 and yield_params:
        yield_decrease_water_pct = (
            yield_params.k_y * (1.0 - total_transp_act / total_transp_pot) * 100.0
        )
        yield_decrease_water_pct = max(0.0, min(100.0, yield_decrease_water_pct))
    else:
        yield_decrease_water_pct = 0.0

    # Salinity component (if salinity params)
    yield_decrease_salinity_pct = None
    if salinity_params and salinity_params.ec_e > salinity_params.ec_threshold:
        yield_decrease_salinity_pct = (
            salinity_params.b
            * (salinity_params.ec_e - salinity_params.ec_threshold)
            / salinity_params.k_y
        )
        yield_decrease_salinity_pct = max(0.0, min(100.0, yield_decrease_salinity_pct))

    # Total (combined water + salinity)
    if yield_decrease_salinity_pct is not None:
        yield_decrease_total_pct = min(
            100.0,
            yield_decrease_water_pct + yield_decrease_salinity_pct,
        )
    else:
        yield_decrease_total_pct = yield_decrease_water_pct

    return StressSummary(
        total_transp_pot=total_transp_pot,
        total_transp_act=total_transp_act,
        total_transp_deficit=total_transp_deficit,
        transp_deficit_pct=transp_deficit_pct,
        days_with_stress=days_with_stress,
        days_severe_stress=days_severe_stress,
        yield_decrease_water_pct=yield_decrease_water_pct,
        yield_decrease_salinity_pct=yield_decrease_salinity_pct,
        yield_decrease_total_pct=yield_decrease_total_pct,
    )


def compute_irrigation_summary(daily_results: list[DailyResult]) -> IrrigationSummary:
    """Compute seasonal irrigation metrics from daily results."""
    total_irrigation = sum(r.irrig for r in daily_results)
    total_precip = sum(r.precip for r in daily_results)
    total_etc_act = sum(r.etc_act for r in daily_results)
    total_etc_pot = sum(r.kcb * r.eto for r in daily_results)
    eta_etm_ratio = total_etc_act / total_etc_pot if total_etc_pot > 0 else 0.0
    irrigation_efficiency = (
        (total_etc_act - total_precip) / total_irrigation if total_irrigation > 0 else 0.0
    )

    # Average % TAW depleted: 100 * dr / taw
    pct_taw_values = [100.0 * r.dr / r.taw for r in daily_results if r.taw > 0]
    avg_pct_taw = sum(pct_taw_values) / len(pct_taw_values) if pct_taw_values else 0.0

    pct_raw_values = [100.0 * r.dr / r.raw for r in daily_results if r.raw > 0]
    avg_pct_raw = sum(pct_raw_values) / len(pct_raw_values) if pct_raw_values else 0.0

    return IrrigationSummary(
        total_irrigation=total_irrigation,
        total_precip=total_precip,
        total_etc_act=total_etc_act,
        total_etc_pot=total_etc_pot,
        eta_etm_ratio=eta_etm_ratio,
        irrigation_efficiency=irrigation_efficiency,
        avg_pct_taw=avg_pct_taw,
        avg_pct_raw=avg_pct_raw,
    )


def compute_simulation_summary(
    daily_results: list[DailyResult],
    yield_params: YieldParams | None,
    salinity_params: SalinityParams | None,
) -> SimulationSummary:
    """Compute full seasonal summary from daily results."""
    stress = compute_stress_summary(daily_results, yield_params, salinity_params)
    irrigation = compute_irrigation_summary(daily_results)
    n_days = len(daily_results)
    start_date = daily_results[0].date if daily_results else datetime.date.today()
    end_date = daily_results[-1].date if daily_results else datetime.date.today()
    return SimulationSummary(
        stress=stress,
        irrigation=irrigation,
        n_days=n_days,
        start_date=start_date,
        end_date=end_date,
    )


def format_yield_loss_table(stress: StressSummary) -> str:
    """Format yield loss table matching tutorial output."""
    lines = [
        "=== Yield Loss Summary (Stewart Water-Yield) ===",
        f"  Total potential transpiration: {stress.total_transp_pot:.1f} mm",
        f"  Total actual transpiration:    {stress.total_transp_act:.1f} mm",
        (
            f"  Transpiration deficit:         {stress.total_transp_deficit:.1f} mm"
            f" ({stress.transp_deficit_pct:.1f}%)"
        ),
        f"  Days with water stress:        {stress.days_with_stress}",
        f"  Days with severe stress:       {stress.days_severe_stress}",
        f"  Yield decrease (water):       {stress.yield_decrease_water_pct:.1f}%",
    ]
    if stress.yield_decrease_salinity_pct is not None:
        lines.append(f"  Yield decrease (salinity):   {stress.yield_decrease_salinity_pct:.1f}%")
    lines.append(f"  Total yield decrease:        {stress.yield_decrease_total_pct:.1f}%")
    return "\n".join(lines)


def format_irrigation_opportunity_table(irrigation: IrrigationSummary) -> str:
    """Format irrigation metrics table."""
    return "\n".join(
        [
            "=== Irrigation Opportunity Statistics ===",
            f"  Total irrigation:     {irrigation.total_irrigation:.1f} mm",
            f"  Total precipitation:  {irrigation.total_precip:.1f} mm",
            f"  Total ETa:            {irrigation.total_etc_act:.1f} mm",
            f"  Total ETm:            {irrigation.total_etc_pot:.1f} mm",
            f"  ETa/ETm ratio:        {irrigation.eta_etm_ratio:.2f}",
            f"  Irrigation efficiency: {irrigation.irrigation_efficiency:.2f}",
            f"  Avg % TAW depleted:   {irrigation.avg_pct_taw:.1f}%",
            f"  Avg % RAW depleted:   {irrigation.avg_pct_raw:.1f}%",
        ]
    )
