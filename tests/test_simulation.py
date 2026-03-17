"""Integration / smoke tests for simdualkc.simulation.run_simulation."""

import datetime

import pytest

from simdualkc.models import (
    ClimateRecord,
    CRMethod,
    DPMethod,
    InitialConditions,
    IrrigationEvent,
    SimulationConfig,
    SimulationResult,
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
