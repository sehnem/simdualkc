"""Integration / smoke tests for simdualkc.simulation.run_simulation."""

import datetime

import pytest

from simdualkc.models import (
    ClimateRecord,
    CRMethod,
    DeficitIrrigationStrategy,
    DeliveryConstraints,
    DPMethod,
    FarmPondConstraint,
    FarmPondSupply,
    InitialConditions,
    IrrigationEvent,
    IrrigationIntervalPeriod,
    IrrigationStrategy,
    MADThresholdStrategy,
    SimulationConfig,
    SimulationResult,
    SoilParams,
)
from simdualkc.simulation import run_simulation, to_dataframe


class TestRunSimulationSmoke:
    def test_runs_without_error(self, sim_config: SimulationConfig) -> None:
        result = run_simulation(sim_config)
        assert isinstance(result, SimulationResult)

    def test_returns_correct_number_of_days(self, sim_config: SimulationConfig) -> None:
        result = run_simulation(sim_config)
        assert result.n_days == len(sim_config.climate)

    def test_to_dataframe_shape(self, sim_config: SimulationConfig) -> None:
        result = run_simulation(sim_config)
        df = to_dataframe(result)
        assert len(df) == result.n_days
        # Key columns present
        for col in ("kcb", "ke", "ks", "etc_act", "dr", "dei", "dep"):
            assert col in df.columns

    def test_day_index_starts_at_1(self, sim_config: SimulationConfig) -> None:
        result = run_simulation(sim_config)
        assert result.daily_results[0].day_of_sim == 1

    def test_dates_match_climate_input(self, sim_config: SimulationConfig) -> None:
        result = run_simulation(sim_config)
        for r, c in zip(result.daily_results, sim_config.climate, strict=True):
            assert r.date == c.date


class TestPhysicalBounds:
    def test_ks_bounded_between_0_and_1(self, sim_config: SimulationConfig) -> None:
        result = run_simulation(sim_config)
        for r in result.daily_results:
            assert 0.0 <= r.ks <= 1.0 + 1e-9

    def test_ke_non_negative(self, sim_config: SimulationConfig) -> None:
        result = run_simulation(sim_config)
        for r in result.daily_results:
            assert r.ke >= -1e-9

    def test_etc_act_non_negative(self, sim_config: SimulationConfig) -> None:
        result = run_simulation(sim_config)
        for r in result.daily_results:
            assert r.etc_act >= -1e-9

    def test_dr_bounded(self, sim_config: SimulationConfig) -> None:
        result = run_simulation(sim_config)
        for r in result.daily_results:
            assert 0.0 <= r.dr <= r.taw + 1e-9

    def test_transp_plus_evap_equals_etc(self, sim_config: SimulationConfig) -> None:
        result = run_simulation(sim_config)
        for r in result.daily_results:
            assert r.transp_act + r.evap_act == pytest.approx(r.etc_act, abs=1e-6)


class TestIrrigationScenario:
    def test_irrigation_reduces_root_zone_depletion(
        self,
        soil,  # noqa: ANN001
        crop,  # noqa: ANN001
    ) -> None:
        """Under identical climate, irrigated run should have lower Dr across the season."""
        base = datetime.date(2024, 5, 1)
        # Use mid-season days (day ~80) so that Zr is near max and TAW is large,
        # making the irrigation signal clearly visible in Dr.
        mid_season_offset = 80  # day-of-sim at which we create a 5-day window
        climate = [
            ClimateRecord(
                date=base + datetime.timedelta(days=i),
                eto=3.0,  # modest ET so stress doesn't overwhelm the signal
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(mid_season_offset + 5)
        ]
        # Start partially depleted — well within TAW so Dr can clearly decrease
        ic = InitialConditions(dr0=50.0, dei0=5.0, dep0=5.0)
        irrig_date = base + datetime.timedelta(days=mid_season_offset)

        config_dry = SimulationConfig(soil=soil, crop=crop, climate=climate, initial_conditions=ic)
        config_irr = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=ic,
            irrigation=[IrrigationEvent(date=irrig_date, depth_mm=40.0, fw=1.0)],
        )

        result_dry = run_simulation(config_dry)
        result_irr = run_simulation(config_irr)

        # On the irrigation day (index mid_season_offset) Dr in the irrigated run
        # must be strictly lower than in the dry run.
        dr_dry = result_dry.daily_results[mid_season_offset].dr
        dr_irr = result_irr.daily_results[mid_season_offset].dr
        assert dr_irr < dr_dry

    def test_no_stress_when_soil_full(self, soil, crop) -> None:  # noqa: ANN001
        """Starting at field capacity with daily rain: Ks should stay 1."""
        base = datetime.date(2024, 5, 1)
        # No-stress test
        ic = InitialConditions(dr0=0.0, dei0=0.0, dep0=0.0)
        climate = [
            ClimateRecord(
                date=base + datetime.timedelta(days=i),
                eto=3.0,
                precip=10.0,  # adequate rainfall
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(5)
        ]
        config = SimulationConfig(soil=soil, crop=crop, climate=climate, initial_conditions=ic)
        result = run_simulation(config)
        for r in result.daily_results:
            assert r.ks == pytest.approx(1.0)


class TestMethodOptions:
    def test_parametric_dp_runs(self, soil, crop, three_day_climate) -> None:  # noqa: ANN001
        """Verify parametric DP method runs without errors when params provided."""

        from simdualkc.models import SoilParams

        soil_with_dp = SoilParams(
            theta_fc=soil.theta_fc,
            theta_wp=soil.theta_wp,
            ze=soil.ze,
            rew=soil.rew,
            tew=soil.tew,
            cn2=soil.cn2,
            a_d=2.0,
            b_d=1.5,
        )
        ic = InitialConditions(dr0=30.0, dei0=5.0, dep0=5.0)
        config = SimulationConfig(
            soil=soil_with_dp,
            crop=crop,
            climate=three_day_climate,
            initial_conditions=ic,
            dp_method=DPMethod.PARAMETRIC,
        )
        result = run_simulation(config)
        assert result.n_days == 3

    def test_constant_cr_runs(self, soil, crop, three_day_climate) -> None:  # noqa: ANN001
        from simdualkc.models import SoilParams

        soil_cr = SoilParams(
            theta_fc=soil.theta_fc,
            theta_wp=soil.theta_wp,
            ze=soil.ze,
            rew=soil.rew,
            tew=soil.tew,
            cn2=soil.cn2,
            gmax=1.5,
        )
        ic = InitialConditions(dr0=30.0, dei0=5.0, dep0=5.0)
        config = SimulationConfig(
            soil=soil_cr,
            crop=crop,
            climate=three_day_climate,
            initial_conditions=ic,
            cr_method=CRMethod.CONSTANT,
        )
        result = run_simulation(config)
        assert result.n_days == 3


class TestParametricCrIntegration:
    def test_parametric_cr_runs_and_reduces_dr(self, crop) -> None:  # noqa: ANN001
        """Parametric CR with real 8 coefficients should produce CR > 0 and lower Dr."""
        base = datetime.date(2024, 6, 1)
        climate = [
            ClimateRecord(
                date=base + datetime.timedelta(days=i),
                eto=5.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
                wt_depth_m=1.0,
            )
            for i in range(5)
        ]
        soil_cr = SoilParams(
            theta_fc=0.32,
            theta_wp=0.12,
            ze=0.10,
            rew=9.0,
            tew=22.0,
            cn2=75.0,
            cr_a1=380.0,
            cr_b1=-0.17,
            cr_a2=300.0,
            cr_b2=-0.27,
            cr_a3=-1.3,
            cr_b3=6.6,
            cr_a4=4.60,
            cr_b4=-0.65,
        )
        # Use a high-Kcb crop planted on the first climate date so that day_of_sim=1
        # already has large Kcb and non-zero LAI, giving material CR.
        mid_crop = crop.model_copy(
            update={
                "plant_date": base,
                "kcb_ini": 1.0,
                "kcb_mid": 1.0,
                "kcb_end": 1.0,
                "stage_lengths": [1, 1, 50, 1],
                "lai_dates": [base],
                "lai_values": [2.0],
            }
        )
        ic = InitialConditions(dr0=20.0, dei0=5.0, dep0=5.0)

        config_cr = SimulationConfig(
            soil=soil_cr,
            crop=mid_crop,
            climate=climate,
            initial_conditions=ic,
            cr_method=CRMethod.PARAMETRIC,
        )
        config_none = SimulationConfig(
            soil=soil_cr.model_copy(update={"cr_a1": None}),  # drop CR coefficients
            crop=mid_crop,
            climate=climate,
            initial_conditions=ic,
            cr_method=CRMethod.NONE,
        )

        result_cr = run_simulation(config_cr)
        result_none = run_simulation(config_none)

        # At least one day with positive CR
        assert any(r.cr > 0.0 for r in result_cr.daily_results)

        # Dr should be lower (or equal on guard days) with CR than without
        days_strictly_lower = 0
        for r_cr, r_none in zip(result_cr.daily_results, result_none.daily_results, strict=True):
            assert r_cr.dr <= r_none.dr
            if r_cr.dr < r_none.dr:
                days_strictly_lower += 1
        assert days_strictly_lower > 0


class TestDeliveryConstraints:
    def test_rotational_interval_blocks_then_allows(self, soil, crop, initial_conditions) -> None:  # noqa: ANN001
        """A 10-day rotational interval prevents irrigation on day 5, allows on day 10."""
        base = datetime.date(2024, 4, 1)
        # 15 days of high ET, no rain -> depletion will exceed MAD quickly
        climate = [
            ClimateRecord(
                date=base + datetime.timedelta(days=i),
                eto=8.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(15)
        ]
        strategy = IrrigationStrategy(
            strategy_type="mad_threshold",
            mad_threshold=MADThresholdStrategy(
                mad_fraction=0.3,  # low threshold so it triggers early
                target_pct_taw=100.0,
                min_interval_days=1,
                delivery=DeliveryConstraints(
                    interval_schedule=[
                        IrrigationIntervalPeriod(
                            start_date=base,
                            end_date=base + datetime.timedelta(days=14),
                            min_interval_days=10,
                        )
                    ]
                ),
            ),
        )
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=initial_conditions,
            irrigation_strategy=strategy,
        )
        result = run_simulation(config)
        irrig_days = [r.day_of_sim for r in result.daily_results if r.irrig > 0.0]
        # First irrigation should happen on day 10 or later, not before
        assert min(irrig_days) >= 10
        # There should be at least one irrigation event
        assert len(irrig_days) >= 1

    def test_max_depth_mm_caps_irrigation(self, soil, crop, initial_conditions) -> None:  # noqa: ANN001
        """max_depth_mm=20 caps a computed 35 mm depth to 20 mm."""
        base = datetime.date(2024, 4, 1)
        climate = [
            ClimateRecord(
                date=base + datetime.timedelta(days=i),
                eto=8.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(20)
        ]
        strategy = IrrigationStrategy(
            strategy_type="mad_threshold",
            mad_threshold=MADThresholdStrategy(
                mad_fraction=0.3,
                target_pct_taw=100.0,
                min_interval_days=1,
                delivery=DeliveryConstraints(max_depth_mm=20.0),
            ),
        )
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=initial_conditions,
            irrigation_strategy=strategy,
        )
        result = run_simulation(config)
        irrig_depths = [r.irrig for r in result.daily_results if r.irrig > 0.0]
        assert all(d <= 20.0 + 1e-6 for d in irrig_depths)
        # Make sure irrigation actually happened (so the cap was applied)
        assert len(irrig_depths) >= 1

    def test_stage_fixed_depth_mid_stage(self, soil, crop, initial_conditions) -> None:  # noqa: ANN001
        """stage_fixed_depth_mm={"mid": 30} applies 30 mm during mid-stage."""
        base = datetime.date(2024, 4, 1)
        # Crop stage_lengths=[30,40,50,30]; mid stage = days 71-120
        climate = [
            ClimateRecord(
                date=base + datetime.timedelta(days=i),
                eto=6.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(120)
        ]
        strategy = IrrigationStrategy(
            strategy_type="mad_threshold",
            mad_threshold=MADThresholdStrategy(
                mad_fraction=0.3,
                target_pct_taw=100.0,
                min_interval_days=1,
                delivery=DeliveryConstraints(stage_fixed_depth_mm={"mid": 30.0}),
            ),
        )
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=initial_conditions,
            irrigation_strategy=strategy,
        )
        result = run_simulation(config)
        # Find irrigation events in mid-stage (days 71-120)
        mid_irrig = [
            r.irrig for r in result.daily_results if 71 <= r.day_of_sim <= 120 and r.irrig > 0.0
        ]
        # There should be some mid-stage irrigations
        assert len(mid_irrig) >= 1
        # Each should be exactly 30 mm (within tolerance)
        for d in mid_irrig:
            assert d == pytest.approx(30.0, abs=1e-3)

    def test_farm_pond_limits_irrigation(self, soil, crop, initial_conditions) -> None:  # noqa: ANN001
        """Farm pond with small initial storage limits total irrigation."""
        base = datetime.date(2024, 4, 1)
        climate = [
            ClimateRecord(
                date=base + datetime.timedelta(days=i),
                eto=8.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(20)
        ]
        strategy = IrrigationStrategy(
            strategy_type="mad_threshold",
            mad_threshold=MADThresholdStrategy(
                mad_fraction=0.3,
                target_pct_taw=100.0,
                min_interval_days=1,
                delivery=DeliveryConstraints(
                    farm_pond=FarmPondConstraint(
                        initial_storage_mm=25.0,
                    )
                ),
            ),
        )
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=initial_conditions,
            irrigation_strategy=strategy,
        )
        result = run_simulation(config)
        total_irrig = sum(r.irrig for r in result.daily_results)
        # Total irrigation should not exceed initial pond storage
        assert total_irrig <= 25.0 + 1e-3
        # There should be at least one irrigation event
        assert total_irrig > 0.0

    def test_farm_pond_supply_refill(self, soil, crop, initial_conditions) -> None:  # noqa: ANN001
        """Farm pond supply on a specific date refills storage."""
        base = datetime.date(2024, 4, 1)
        climate = [
            ClimateRecord(
                date=base + datetime.timedelta(days=i),
                eto=8.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(20)
        ]
        strategy = IrrigationStrategy(
            strategy_type="mad_threshold",
            mad_threshold=MADThresholdStrategy(
                mad_fraction=0.3,
                target_pct_taw=100.0,
                min_interval_days=1,
                delivery=DeliveryConstraints(
                    farm_pond=FarmPondConstraint(
                        initial_storage_mm=10.0,
                        supplies=[
                            FarmPondSupply(
                                date=base + datetime.timedelta(days=5),
                                depth_mm=20.0,
                            )
                        ],
                    )
                ),
            ),
        )
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=initial_conditions,
            irrigation_strategy=strategy,
        )
        result = run_simulation(config)
        total_irrig = sum(r.irrig for r in result.daily_results)
        # Total should exceed initial 10 mm because of the 20 mm refill on day 5
        assert total_irrig > 10.0 + 1e-3
        # But should not exceed 30 mm total (10 + 20)
        assert total_irrig <= 30.0 + 1e-3

    def test_deficit_with_delivery_constraints(self, soil, crop, initial_conditions) -> None:  # noqa: ANN001
        """Deficit strategy respects min_interval_days and max_depth_mm from delivery."""
        base = datetime.date(2024, 4, 1)
        climate = [
            ClimateRecord(
                date=base + datetime.timedelta(days=i),
                eto=8.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(20)
        ]
        strategy = IrrigationStrategy(
            strategy_type="deficit",
            deficit=DeficitIrrigationStrategy(
                stage_mad={"ini": 0.3, "dev": 0.5, "mid": 0.4, "late": 0.5},
                target_pct_taw=100.0,
                min_interval_days=5,  # NEW: no longer hardcoded to 1
                delivery=DeliveryConstraints(max_depth_mm=15.0),
            ),
        )
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=initial_conditions,
            irrigation_strategy=strategy,
        )
        result = run_simulation(config)
        irrig_days = [r.day_of_sim for r in result.daily_results if r.irrig > 0.0]
        # Minimum interval of 5 days should be respected
        for i in range(1, len(irrig_days)):
            assert irrig_days[i] - irrig_days[i - 1] >= 5
        # All depths should be capped at 15 mm
        irrig_depths = [r.irrig for r in result.daily_results if r.irrig > 0.0]
        assert all(d <= 15.0 + 1e-6 for d in irrig_depths)
