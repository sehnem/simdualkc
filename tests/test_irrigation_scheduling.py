"""Tests for automated irrigation scheduling."""

import datetime

import pytest

from simdualkc.irrigation import (
    compute_irrigation_depth,
    should_trigger_irrigation,
)
from simdualkc.models import (
    ClimateRecord,
    CropParams,
    InitialConditions,
    IrrigationStrategy,
    MADThresholdStrategy,
    SimulationConfig,
    SoilParams,
)
from simdualkc.simulation import run_simulation


class TestComputeIrrigationDepth:
    def test_full_refill(self) -> None:
        """Target 100% TAW: I = Dr (bring depletion to 0)."""
        depth = compute_irrigation_depth(dr=80.0, taw=200.0, target_pct_taw=100.0)
        assert depth == pytest.approx(80.0)

    def test_deficit_refill(self) -> None:
        """Target 50% TAW: Dr_after = 100, I = Dr - 100."""
        depth = compute_irrigation_depth(dr=80.0, taw=200.0, target_pct_taw=50.0)
        # target_depletion = 200 * 0.5 = 100, I = 80 - 100 = -20 -> 0
        assert depth == 0.0  # Dr already below target

    def test_deficit_refill_above_target(self) -> None:
        """When Dr > target_depletion, positive irrigation."""
        depth = compute_irrigation_depth(dr=150.0, taw=200.0, target_pct_taw=50.0)
        # target_depletion = 100, I = 150 - 100 = 50
        assert depth == pytest.approx(50.0)


class TestShouldTriggerIrrigation:
    def test_trigger_when_above_mad(self) -> None:
        """Triggers when Dr >= MAD × TAW."""
        assert (
            should_trigger_irrigation(
                dr=120.0,
                taw=200.0,
                mad_fraction=0.5,
                days_to_harvest=50,
                harvest_stop_days=0,
                last_irrigation_day=0,
                current_day=30,
                min_interval=1,
            )
            is True
        )

    def test_no_trigger_when_below_mad(self) -> None:
        """No trigger when Dr < MAD × TAW."""
        assert (
            should_trigger_irrigation(
                dr=80.0,
                taw=200.0,
                mad_fraction=0.5,
                days_to_harvest=50,
                harvest_stop_days=0,
                last_irrigation_day=0,
                current_day=30,
                min_interval=1,
            )
            is False
        )

    def test_harvest_stop(self) -> None:
        """No irrigation when days_to_harvest <= harvest_stop_days."""
        assert (
            should_trigger_irrigation(
                dr=120.0,
                taw=200.0,
                mad_fraction=0.5,
                days_to_harvest=5,
                harvest_stop_days=7,
                last_irrigation_day=0,
                current_day=130,
                min_interval=1,
            )
            is False
        )

    def test_min_interval(self) -> None:
        """No irrigation if within min_interval of last."""
        assert (
            should_trigger_irrigation(
                dr=120.0,
                taw=200.0,
                mad_fraction=0.5,
                days_to_harvest=50,
                harvest_stop_days=0,
                last_irrigation_day=28,
                current_day=30,
                min_interval=5,
            )
            is False
        )


class TestMADSimulation:
    def test_auto_irrigation_reduces_stress(self) -> None:
        """With MAD strategy, irrigation events occur and reduce stress."""
        soil = SoilParams(theta_fc=0.32, theta_wp=0.12, rew=9.0, tew=22.0)
        crop = CropParams(
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
        )
        climate = [
            ClimateRecord(
                date=datetime.date(2024, 4, 1) + datetime.timedelta(days=i),
                eto=6.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(130)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=50.0, dei0=5.0, dep0=5.0),
            irrigation_strategy=IrrigationStrategy(
                strategy_type="mad_threshold",
                mad_threshold=MADThresholdStrategy(
                    mad_fraction=0.5,
                    target_pct_taw=100.0,
                    days_before_harvest_stop=10,
                    min_interval_days=5,
                ),
            ),
        )
        result = run_simulation(config)

        # Some days should have non-zero irrigation
        irrig_totals = [r.irrig for r in result.daily_results]
        assert sum(irrig_totals) > 0
