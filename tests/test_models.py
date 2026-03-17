"""Unit tests for simdualkc.models."""

from __future__ import annotations

import datetime

import pytest
from pydantic import ValidationError

from simdualkc.models import (
    ClimateRecord,
    CropParams,
    InitialConditions,
    SimulationConfig,
    SoilParams,
)


class TestSoilParams:
    def test_valid(self) -> None:
        s = SoilParams(theta_fc=0.35, theta_wp=0.12, rew=8.0, tew=20.0)
        assert s.theta_fc == pytest.approx(0.35)

    def test_theta_wp_must_be_less_than_fc(self) -> None:
        with pytest.raises(ValidationError, match="theta_wp must be less than theta_fc"):
            SoilParams(theta_fc=0.10, theta_wp=0.20, rew=8.0, tew=20.0)

    def test_tew_must_be_greater_than_rew(self) -> None:
        with pytest.raises(ValidationError, match="rew must be less than tew"):
            SoilParams(theta_fc=0.35, theta_wp=0.12, rew=25.0, tew=20.0)

    def test_fc_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            SoilParams(theta_fc=1.5, theta_wp=0.12, rew=8.0, tew=20.0)

    def test_negative_rew(self) -> None:
        with pytest.raises(ValidationError):
            SoilParams(theta_fc=0.35, theta_wp=0.12, rew=-1.0, tew=20.0)


class TestCropParams:
    def test_valid(self) -> None:
        c = CropParams(
            kcb_ini=0.15,
            kcb_mid=1.10,
            kcb_end=0.35,
            stage_lengths=[30, 40, 50, 30],
            plant_date=datetime.date(2024, 4, 1),
            zr_max=1.2,
            h_max=2.5,
            p_tab=0.55,
            fc_max=0.90,
        )
        assert c.stage_lengths == [30, 40, 50, 30]

    def test_stage_lengths_must_contain_4_elements(self) -> None:
        with pytest.raises(ValidationError):
            CropParams(
                kcb_ini=0.15,
                kcb_mid=1.10,
                kcb_end=0.35,
                stage_lengths=[30, 40, 50],  # only 3
                plant_date=datetime.date(2024, 4, 1),
                zr_max=1.2,
                h_max=2.5,
                p_tab=0.55,
                fc_max=0.90,
            )

    def test_negative_stage_length_rejected(self) -> None:
        with pytest.raises(ValidationError, match="positive integers"):
            CropParams(
                kcb_ini=0.15,
                kcb_mid=1.10,
                kcb_end=0.35,
                stage_lengths=[30, -5, 50, 30],
                plant_date=datetime.date(2024, 4, 1),
                zr_max=1.2,
                h_max=2.5,
                p_tab=0.55,
                fc_max=0.90,
            )

    def test_fc_max_gt_1_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CropParams(
                kcb_ini=0.15,
                kcb_mid=1.10,
                kcb_end=0.35,
                stage_lengths=[30, 40, 50, 30],
                plant_date=datetime.date(2024, 4, 1),
                zr_max=1.2,
                h_max=2.5,
                p_tab=0.55,
                fc_max=1.5,  # invalid
            )


class TestClimateRecord:
    def test_negative_eto_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ClimateRecord(
                date=datetime.date(2024, 1, 1),
                eto=-1.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )

    def test_rh_min_out_of_range(self) -> None:
        with pytest.raises(ValidationError):
            ClimateRecord(
                date=datetime.date(2024, 1, 1),
                eto=5.0,
                precip=0.0,
                u2=2.0,
                rh_min=120.0,  # > 100
            )


class TestSimulationConfig:
    def test_empty_climate_rejected(self, soil: SoilParams, crop: CropParams) -> None:
        with pytest.raises(ValidationError, match="at least one record"):
            SimulationConfig(
                soil=soil,
                crop=crop,
                climate=[],
                initial_conditions=InitialConditions(dr0=0, dei0=0, dep0=0),
            )

    def test_unsorted_climate_rejected(self, soil: SoilParams, crop: CropParams) -> None:
        with pytest.raises(ValidationError, match="chronological"):
            SimulationConfig(
                soil=soil,
                crop=crop,
                climate=[
                    ClimateRecord(
                        date=datetime.date(2024, 4, 2),
                        eto=5.0,
                        precip=0.0,
                        u2=2.0,
                        rh_min=45.0,
                    ),
                    ClimateRecord(
                        date=datetime.date(2024, 4, 1),
                        eto=5.0,
                        precip=0.0,
                        u2=2.0,
                        rh_min=45.0,
                    ),
                ],
                initial_conditions=InitialConditions(dr0=0, dei0=0, dep0=0),
            )
