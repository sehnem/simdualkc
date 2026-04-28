"""Tests for FAO-56 Penman-Monteith ETo calculator."""

import datetime

from simdualkc.eto import (
    compute_actual_vapor_pressure,
    compute_eto,
    compute_psychrometric_constant,
    compute_saturation_vapor_pressure,
    compute_slope_vapor_pressure_curve,
    weather_to_climate_records,
)
from simdualkc.models import ClimateRecord, WeatherRecord


class TestSaturationVaporPressure:
    def test_known_value(self) -> None:
        """At T=20°C, e° ≈ 2.34 kPa (FAO-56 Table)."""
        e = compute_saturation_vapor_pressure(20.0)
        assert 2.3 <= e <= 2.4

    def test_increases_with_temperature(self) -> None:
        """Saturation VP increases with temperature."""
        e_cold = compute_saturation_vapor_pressure(10.0)
        e_warm = compute_saturation_vapor_pressure(30.0)
        assert e_warm > e_cold


class TestActualVaporPressure:
    def test_from_rh(self) -> None:
        """ea from RHmax/RHmin formula."""
        # Tmax=25, Tmin=15, RHmax=80, RHmin=40
        ea = compute_actual_vapor_pressure(25.0, 15.0, 80.0, 40.0)
        # e°(15)≈1.705, e°(25)≈3.168
        # ea = (1.705*80/100 + 3.168*40/100)/2 = (1.364 + 1.267)/2 ≈ 1.32
        assert 1.2 <= ea <= 1.5


class TestSlopeVaporPressureCurve:
    def test_positive(self) -> None:
        """Slope is always positive."""
        delta = compute_slope_vapor_pressure_curve(20.0)
        assert delta > 0

    def test_increases_with_temperature(self) -> None:
        """Slope increases with temperature."""
        d1 = compute_slope_vapor_pressure_curve(15.0)
        d2 = compute_slope_vapor_pressure_curve(25.0)
        assert d2 > d1


class TestPsychrometricConstant:
    def test_sea_level(self) -> None:
        """At sea level γ ≈ 0.0665 kPa/°C."""
        gamma = compute_psychrometric_constant(0.0)
        assert 0.065 <= gamma <= 0.068

    def test_decreases_with_elevation(self) -> None:
        """Psychrometric constant decreases with elevation."""
        g0 = compute_psychrometric_constant(0.0)
        g1000 = compute_psychrometric_constant(1000.0)
        assert g1000 < g0


class TestComputeEto:
    def test_returns_positive(self) -> None:
        """ETo should be non-negative."""
        eto = compute_eto(
            t_max=25.0,
            t_min=15.0,
            rh_max=70.0,
            rh_min=40.0,
            rs=22.0,
            u2=2.0,
            latitude=40.0,
            elevation=0.0,
            date=datetime.date(2024, 7, 15),
        )
        assert eto >= 0.0
        assert 3.0 <= eto <= 8.0  # Reasonable daily ETo range

    def test_higher_temp_higher_eto(self) -> None:
        """Warmer days generally yield higher ETo."""
        eto_cool = compute_eto(
            t_max=20.0,
            t_min=10.0,
            rh_max=70.0,
            rh_min=40.0,
            rs=20.0,
            u2=2.0,
            latitude=40.0,
            elevation=0.0,
            date=datetime.date(2024, 5, 15),
        )
        eto_warm = compute_eto(
            t_max=30.0,
            t_min=20.0,
            rh_max=70.0,
            rh_min=40.0,
            rs=25.0,
            u2=2.0,
            latitude=40.0,
            elevation=0.0,
            date=datetime.date(2024, 7, 15),
        )
        assert eto_warm > eto_cool

    def test_higher_wind_higher_eto(self) -> None:
        """Higher wind speed generally yields higher ETo."""
        eto_low = compute_eto(
            t_max=25.0,
            t_min=15.0,
            rh_max=70.0,
            rh_min=40.0,
            rs=22.0,
            u2=1.0,
            latitude=40.0,
            elevation=0.0,
            date=datetime.date(2024, 7, 15),
        )
        eto_high = compute_eto(
            t_max=25.0,
            t_min=15.0,
            rh_max=70.0,
            rh_min=40.0,
            rs=22.0,
            u2=4.0,
            latitude=40.0,
            elevation=0.0,
            date=datetime.date(2024, 7, 15),
        )
        assert eto_high > eto_low


class TestWeatherToClimateRecords:
    def test_converts_dict_list(self) -> None:
        """Convert list of dicts to ClimateRecords."""
        weather = [
            {
                "date": datetime.date(2024, 7, 1),
                "t_max": 28.0,
                "t_min": 16.0,
                "rh_max": 80.0,
                "rh_min": 45.0,
                "rs": 24.0,
                "u2": 2.5,
                "precip": 0.0,
            },
        ]
        records = weather_to_climate_records(weather, latitude=38.0, elevation=0.0)
        assert len(records) == 1
        assert isinstance(records[0], ClimateRecord)
        assert records[0].date == datetime.date(2024, 7, 1)
        assert records[0].eto > 0.0
        assert records[0].precip == 0.0

    def test_converts_weather_record_list(self) -> None:
        """Convert list of WeatherRecord to ClimateRecords."""
        weather = [
            WeatherRecord(
                date=datetime.date(2024, 7, 1),
                t_max=28.0,
                t_min=16.0,
                rh_max=80.0,
                rh_min=45.0,
                rs=24.0,
                u2=2.5,
            ),
        ]
        records = weather_to_climate_records(weather, latitude=38.0)
        assert len(records) == 1
        assert isinstance(records[0], ClimateRecord)
