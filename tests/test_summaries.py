"""Tests for yield loss summaries and irrigation metrics."""

import datetime

from simdualkc.models import (
    ClimateRecord,
    CropParams,
    InitialConditions,
    SimulationConfig,
    SoilParams,
    YieldParams,
)
from simdualkc.reporting import (
    compute_stress_summary,
    format_yield_loss_table,
)
from simdualkc.simulation import run_simulation


class TestComputeStressSummary:
    def test_from_daily_results(self) -> None:
        """Stress summary computed from daily results."""
        config = SimulationConfig(
            soil=SoilParams(theta_fc=0.32, theta_wp=0.12, rew=9.0, tew=22.0),
            crop=CropParams(
                kcb_ini=0.15,
                kcb_mid=1.10,
                kcb_end=0.35,
                stage_lengths=[25, 35, 45, 25],
                plant_date=datetime.date(2024, 4, 1),
                zr_ini=0.15,
                zr_max=1.0,
                h_max=2.0,
                p_tab=0.55,
                fc_max=0.9,
            ),
            climate=[
                ClimateRecord(
                    date=datetime.date(2024, 4, 1) + datetime.timedelta(days=i),
                    eto=5.0,
                    precip=0.0,
                    u2=2.0,
                    rh_min=45.0,
                )
                for i in range(50)
            ],
            initial_conditions=InitialConditions(dr0=80.0, dei0=5.0, dep0=5.0),
        )
        result = run_simulation(config)
        summary = compute_stress_summary(
            result.daily_results, config.yield_params, config.salinity
        )
        assert summary.total_transp_pot > 0
        assert summary.total_transp_act >= 0
        assert summary.days_with_stress >= 0


class TestSimulationResultSummary:
    def test_result_has_summary(self) -> None:
        """SimulationResult includes summary."""
        config = SimulationConfig(
            soil=SoilParams(theta_fc=0.32, theta_wp=0.12, rew=9.0, tew=22.0),
            crop=CropParams(
                kcb_ini=0.15,
                kcb_mid=1.10,
                kcb_end=0.35,
                stage_lengths=[25, 35, 45, 25],
                plant_date=datetime.date(2024, 4, 1),
                zr_ini=0.15,
                zr_max=1.0,
                h_max=2.0,
                p_tab=0.55,
                fc_max=0.9,
            ),
            climate=[
                ClimateRecord(
                    date=datetime.date(2024, 4, 1) + datetime.timedelta(days=i),
                    eto=5.0,
                    precip=0.0,
                    u2=2.0,
                    rh_min=45.0,
                )
                for i in range(30)
            ],
            initial_conditions=InitialConditions(dr0=20.0, dei0=5.0, dep0=5.0),
            yield_params=YieldParams(y_m=10000.0, k_y=1.25),
        )
        result = run_simulation(config)
        assert result.summary is not None
        assert result.summary.stress.total_transp_pot > 0
        assert result.summary.irrigation.total_etc_act > 0


class TestFormatTables:
    def test_format_yield_loss_table(self) -> None:
        """Format yield loss table produces readable output."""
        from simdualkc.models import StressSummary

        stress = StressSummary(
            total_transp_pot=200.0,
            total_transp_act=180.0,
            total_transp_deficit=20.0,
            transp_deficit_pct=10.0,
            days_with_stress=5,
            days_severe_stress=0,
            yield_decrease_water_pct=12.5,
            yield_decrease_salinity_pct=None,
            yield_decrease_total_pct=12.5,
        )
        table = format_yield_loss_table(stress)
        assert "Yield Loss" in table
        assert "12.5" in table
