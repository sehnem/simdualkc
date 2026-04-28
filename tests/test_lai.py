"""Tests for LAI-based fraction cover."""

import datetime

import pytest

from simdualkc.kcb import get_fc, interpolate_lai, lai_to_fc
from simdualkc.models import (
    ClimateRecord,
    CropParams,
    InitialConditions,
    SimulationConfig,
    SoilParams,
)
from simdualkc.simulation import run_simulation


class TestLaiToFc:
    def test_zero_lai_gives_zero_fc(self) -> None:
        """fc = 0 when LAI = 0."""
        assert lai_to_fc(0.0) == 0.0

    def test_standard_formula(self) -> None:
        """fc = 1 - exp(-k_ext * LAI)."""
        # LAI=2, k_ext=0.6 → fc = 1 - exp(-1.2) ≈ 0.699
        fc = lai_to_fc(2.0, 0.6)
        assert 0.69 <= fc <= 0.71

    def test_high_lai_saturates(self) -> None:
        """Very high LAI approaches fc=1."""
        fc = lai_to_fc(10.0, 0.6)
        assert fc >= 0.99

    def test_k_ext_affects_result(self) -> None:
        """Higher k_ext gives higher fc for same LAI."""
        fc_low = lai_to_fc(2.0, 0.5)
        fc_high = lai_to_fc(2.0, 0.7)
        assert fc_high > fc_low


class TestInterpolateLai:
    def test_before_first_date_returns_zero(self) -> None:
        """Before first measurement date returns 0."""
        plant = datetime.date(2024, 4, 1)
        lai_dates = [datetime.date(2024, 5, 1), datetime.date(2024, 6, 1)]
        lai_values = [2.0, 4.0]
        # Day 15 is before May 1
        lai = interpolate_lai(15, lai_dates, lai_values, plant)
        assert lai == 0.0

    def test_at_first_date_returns_first_value(self) -> None:
        """At first measurement returns first value."""
        plant = datetime.date(2024, 4, 1)
        lai_dates = [datetime.date(2024, 5, 1), datetime.date(2024, 6, 1)]
        lai_values = [2.0, 4.0]
        # May 1 = day 31
        lai = interpolate_lai(31, lai_dates, lai_values, plant)
        assert lai == 2.0

    def test_after_last_date_holds_value(self) -> None:
        """After last measurement holds last value."""
        plant = datetime.date(2024, 4, 1)
        lai_dates = [datetime.date(2024, 5, 1), datetime.date(2024, 6, 1)]
        lai_values = [2.0, 4.0]
        lai = interpolate_lai(90, lai_dates, lai_values, plant)
        assert lai == 4.0

    def test_interpolates_between_dates(self) -> None:
        """Linear interpolation between two dates."""
        plant = datetime.date(2024, 4, 1)
        lai_dates = [datetime.date(2024, 4, 1), datetime.date(2024, 5, 1)]
        lai_values = [0.5, 2.5]
        # Day 16 = halfway between day 1 and day 31
        lai = interpolate_lai(16, lai_dates, lai_values, plant)
        assert 1.4 <= lai <= 1.6


class TestGetFc:
    def test_fc_max_path_when_no_lai(self) -> None:
        """Uses fc_max interpolation when no LAI data."""
        crop = CropParams(
            kcb_ini=0.15,
            kcb_mid=1.10,
            kcb_end=0.35,
            stage_lengths=[30, 40, 50, 30],
            plant_date=datetime.date(2024, 4, 1),
            zr_ini=0.15,
            zr_max=1.2,
            h_max=2.0,
            p_tab=0.55,
            fc_max=0.9,
        )
        fc = get_fc(50, crop)  # Mid development
        assert fc > 0.3
        assert fc <= 0.9

    def test_lai_path_when_lai_provided(self) -> None:
        """Uses LAI conversion when lai_values and lai_dates provided."""
        crop = CropParams(
            kcb_ini=0.15,
            kcb_mid=1.10,
            kcb_end=0.35,
            stage_lengths=[30, 40, 50, 30],
            plant_date=datetime.date(2024, 4, 1),
            zr_ini=0.15,
            zr_max=1.2,
            h_max=2.0,
            p_tab=0.55,
            fc_max=0.9,
            lai_values=[1.0, 4.0],
            lai_dates=[datetime.date(2024, 4, 1), datetime.date(2024, 5, 15)],
        )
        fc = get_fc(46, crop)
        lai = interpolate_lai(46, crop.lai_dates, crop.lai_values, crop.plant_date)
        expected = lai_to_fc(lai, crop.k_ext)
        assert fc == pytest.approx(expected)


class TestSimulationWithLai:
    def test_simulation_with_lai_runs(self) -> None:
        """Simulation with LAI-based fc completes."""
        crop = CropParams(
            kcb_ini=0.15,
            kcb_mid=1.10,
            kcb_end=0.35,
            stage_lengths=[25, 35, 45, 25],
            plant_date=datetime.date(2024, 4, 1),
            zr_ini=0.15,
            zr_max=1.2,
            h_max=2.0,
            p_tab=0.55,
            fc_max=0.85,
            lai_values=[0.1, 2.0, 4.0, 3.0],
            lai_dates=[
                datetime.date(2024, 4, 1),
                datetime.date(2024, 5, 1),
                datetime.date(2024, 6, 15),
                datetime.date(2024, 7, 15),
            ],
        )
        soil = SoilParams(theta_fc=0.32, theta_wp=0.12, rew=9.0, tew=22.0)
        climate = [
            ClimateRecord(
                date=datetime.date(2024, 4, 1) + datetime.timedelta(days=i),
                eto=5.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(60)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=20.0, dei0=5.0, dep0=5.0),
        )
        result = run_simulation(config)
        assert len(result.daily_results) == 60
