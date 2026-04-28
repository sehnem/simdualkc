"""Tests for automated irrigation scheduling."""

import datetime

import pytest

from simdualkc.irrigation import (
    apply_delivery_constraints,
    compute_irrigation_depth,
    get_mad_for_day,
    get_min_interval_for_date,
    get_target_pct_taw_for_day,
    resolve_stage_fixed_depth,
    should_trigger_irrigation,
)
from simdualkc.models import (
    ClimateRecord,
    CropParams,
    DeficitIrrigationStrategy,
    DeliveryConstraints,
    InitialConditions,
    IrrigationIntervalPeriod,
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


class TestGetMinIntervalForDate:
    def test_none_schedule_returns_fallback(self) -> None:
        date = datetime.date(2024, 6, 15)
        assert get_min_interval_for_date(date, None, 5) == 5

    def test_date_inside_period(self) -> None:
        period = IrrigationIntervalPeriod(
            start_date=datetime.date(2024, 6, 1),
            end_date=datetime.date(2024, 6, 30),
            min_interval_days=10,
        )
        date = datetime.date(2024, 6, 15)
        assert get_min_interval_for_date(date, [period], 5) == 10

    def test_date_outside_period_returns_fallback(self) -> None:
        period = IrrigationIntervalPeriod(
            start_date=datetime.date(2024, 6, 1),
            end_date=datetime.date(2024, 6, 30),
            min_interval_days=10,
        )
        date = datetime.date(2024, 7, 15)
        assert get_min_interval_for_date(date, [period], 5) == 5

    def test_boundary_start_date(self) -> None:
        period = IrrigationIntervalPeriod(
            start_date=datetime.date(2024, 6, 1),
            end_date=datetime.date(2024, 6, 30),
            min_interval_days=10,
        )
        date = datetime.date(2024, 6, 1)
        assert get_min_interval_for_date(date, [period], 5) == 10

    def test_boundary_end_date(self) -> None:
        period = IrrigationIntervalPeriod(
            start_date=datetime.date(2024, 6, 1),
            end_date=datetime.date(2024, 6, 30),
            min_interval_days=10,
        )
        date = datetime.date(2024, 6, 30)
        assert get_min_interval_for_date(date, [period], 5) == 10

    def test_first_match_wins(self) -> None:
        period1 = IrrigationIntervalPeriod(
            start_date=datetime.date(2024, 6, 1),
            end_date=datetime.date(2024, 6, 30),
            min_interval_days=10,
        )
        period2 = IrrigationIntervalPeriod(
            start_date=datetime.date(2024, 6, 15),
            end_date=datetime.date(2024, 7, 15),
            min_interval_days=20,
        )
        date = datetime.date(2024, 6, 20)
        assert get_min_interval_for_date(date, [period1, period2], 5) == 10


class TestGetTargetPctTawForDay:
    @staticmethod
    def _crop() -> CropParams:
        return CropParams(
            kcb_ini=0.15,
            kcb_mid=1.10,
            kcb_end=0.35,
            stage_lengths=[15, 30, 60, 25],
            plant_date=datetime.date(2024, 4, 1),
            zr_max=1.0,
            h_max=2.0,
            p_tab=0.55,
            fc_max=0.9,
        )

    def test_mad_without_delivery(self) -> None:
        crop = self._crop()
        strategy = MADThresholdStrategy(mad_fraction=0.5, target_pct_taw=80.0)
        assert get_target_pct_taw_for_day(30, crop, strategy) == 80.0

    def test_deficit_with_stage_target_hit(self) -> None:
        crop = self._crop()
        strategy = DeficitIrrigationStrategy(
            stage_mad={"ini": 0.5, "dev": 0.5, "mid": 0.5, "late": 0.5},
            target_pct_taw=100.0,
            delivery=DeliveryConstraints(stage_target_pct_taw={"mid": 80.0}),
        )
        # day 60 falls in the mid stage (46–105)
        assert get_target_pct_taw_for_day(60, crop, strategy) == 80.0

    def test_deficit_with_stage_target_miss(self) -> None:
        crop = self._crop()
        strategy = DeficitIrrigationStrategy(
            stage_mad={"ini": 0.5, "dev": 0.5, "mid": 0.5, "late": 0.5},
            target_pct_taw=100.0,
            delivery=DeliveryConstraints(stage_target_pct_taw={"mid": 80.0}),
        )
        # day 10 falls in the ini stage (1–15)
        assert get_target_pct_taw_for_day(10, crop, strategy) == 100.0

    def test_none_delivery(self) -> None:
        crop = self._crop()
        strategy = MADThresholdStrategy(mad_fraction=0.5, target_pct_taw=70.0)
        assert get_target_pct_taw_for_day(60, crop, strategy) == 70.0


class TestGetMadForDay:
    @staticmethod
    def _crop() -> CropParams:
        return CropParams(
            kcb_ini=0.15,
            kcb_mid=1.10,
            kcb_end=0.35,
            stage_lengths=[25, 35, 45, 25],
            plant_date=datetime.date(2024, 4, 1),
            zr_max=1.0,
            h_max=2.0,
            p_tab=0.55,
            fc_max=0.9,
        )

    def test_mad_strategy_returns_constant(self) -> None:
        crop = self._crop()
        strategy = MADThresholdStrategy(mad_fraction=0.55)
        assert get_mad_for_day(10, crop, strategy) == 0.55

    def test_deficit_strategy_ini_stage(self) -> None:
        crop = self._crop()
        strategy = DeficitIrrigationStrategy(
            stage_mad={"ini": 0.50, "dev": 0.60, "mid": 0.40, "late": 0.55}
        )
        assert get_mad_for_day(10, crop, strategy) == 0.50

    def test_deficit_strategy_dev_stage(self) -> None:
        crop = self._crop()
        strategy = DeficitIrrigationStrategy(
            stage_mad={"ini": 0.50, "dev": 0.60, "mid": 0.40, "late": 0.55}
        )
        assert get_mad_for_day(30, crop, strategy) == 0.60

    def test_deficit_strategy_mid_stage(self) -> None:
        crop = self._crop()
        strategy = DeficitIrrigationStrategy(
            stage_mad={"ini": 0.50, "dev": 0.60, "mid": 0.40, "late": 0.55}
        )
        assert get_mad_for_day(65, crop, strategy) == 0.40

    def test_deficit_strategy_late_stage(self) -> None:
        crop = self._crop()
        strategy = DeficitIrrigationStrategy(
            stage_mad={"ini": 0.50, "dev": 0.60, "mid": 0.40, "late": 0.55}
        )
        assert get_mad_for_day(120, crop, strategy) == 0.55

    def test_deficit_missing_key_fallback(self) -> None:
        crop = self._crop()
        strategy = DeficitIrrigationStrategy(stage_mad={"mid": 0.40})
        assert get_mad_for_day(10, crop, strategy) == 0.40

    def test_deficit_missing_key_and_mid_fallback(self) -> None:
        crop = self._crop()
        strategy = DeficitIrrigationStrategy(stage_mad={})
        assert get_mad_for_day(10, crop, strategy) == 0.5


class TestResolveStageFixedDepth:
    def test_none_delivery(self) -> None:
        assert resolve_stage_fixed_depth(3, None) is None

    def test_fixed_depth_mm_set(self) -> None:
        delivery = DeliveryConstraints(fixed_depth_mm=30.0)
        assert resolve_stage_fixed_depth(1, delivery) == 30.0
        assert resolve_stage_fixed_depth(3, delivery) == 30.0

    def test_stage_fixed_depth_hit(self) -> None:
        delivery = DeliveryConstraints(stage_fixed_depth_mm={"mid": 25.0})
        assert resolve_stage_fixed_depth(3, delivery) == 25.0

    def test_stage_fixed_depth_miss(self) -> None:
        delivery = DeliveryConstraints(stage_fixed_depth_mm={"mid": 25.0})
        assert resolve_stage_fixed_depth(1, delivery) is None

    def test_fixed_depth_overrides_stage(self) -> None:
        delivery = DeliveryConstraints(
            fixed_depth_mm=30.0,
            stage_fixed_depth_mm={"mid": 25.0},
        )
        assert resolve_stage_fixed_depth(3, delivery) == 30.0

    def test_invalid_stage_falls_back_to_mid(self) -> None:
        delivery = DeliveryConstraints(stage_fixed_depth_mm={"mid": 20.0})
        assert resolve_stage_fixed_depth(0, delivery) == 20.0

    def test_invalid_stage_five_falls_back_to_mid(self) -> None:
        delivery = DeliveryConstraints(stage_fixed_depth_mm={"mid": 20.0})
        assert resolve_stage_fixed_depth(5, delivery) == 20.0


class TestApplyDeliveryConstraints:
    def test_no_delivery_returns_original(self) -> None:
        assert apply_delivery_constraints(50.0, 3, None) == 50.0

    def test_max_depth_cap(self) -> None:
        delivery = DeliveryConstraints(max_depth_mm=20.0)
        assert apply_delivery_constraints(50.0, 3, delivery) == 20.0

    def test_fixed_depth_override(self) -> None:
        delivery = DeliveryConstraints(fixed_depth_mm=30.0)
        assert apply_delivery_constraints(50.0, 3, delivery) == 30.0

    def test_stage_fixed_depth_override(self) -> None:
        delivery = DeliveryConstraints(stage_fixed_depth_mm={"mid": 25.0})
        assert apply_delivery_constraints(50.0, 3, delivery) == 25.0

    def test_max_depth_applied_after_fixed(self) -> None:
        delivery = DeliveryConstraints(fixed_depth_mm=40.0, max_depth_mm=20.0)
        assert apply_delivery_constraints(50.0, 3, delivery) == 20.0

    def test_negative_depth_clamped_to_zero(self) -> None:
        assert apply_delivery_constraints(-5.0, 3, None) == 0.0
