"""Tests for active groundcover support."""

import datetime

import pytest

from simdualkc.kcb import compute_kcb_with_groundcover
from simdualkc.models import (
    ClimateRecord,
    CropParams,
    GroundcoverParams,
    InitialConditions,
    SimulationConfig,
    SoilParams,
)
from simdualkc.simulation import run_simulation


class TestComputeKcbWithGroundcover:
    def test_kd_zero_gives_kcb_cover(self) -> None:
        """When Kd=0 (no main crop), Kcb = Kcb_cover."""
        kcb = compute_kcb_with_groundcover(kcb_full=1.1, kcb_cover=0.25, kd=0.0)
        assert kcb == pytest.approx(0.25)

    def test_kd_one_gives_kcb_full(self) -> None:
        """When Kd=1 (full main crop), Kcb = Kcb_full."""
        kcb = compute_kcb_with_groundcover(kcb_full=1.1, kcb_cover=0.25, kd=1.0)
        assert kcb == pytest.approx(1.1)

    def test_intermediate_kd(self) -> None:
        """Kcb between cover and full for 0 < Kd < 1."""
        kcb = compute_kcb_with_groundcover(kcb_full=1.1, kcb_cover=0.25, kd=0.5)
        assert 0.25 < kcb < 1.1


class TestSimulationWithGroundcover:
    def test_groundcover_simulation_runs(self) -> None:
        """Simulation with groundcover completes."""
        soil = SoilParams(theta_fc=0.32, theta_wp=0.12, rew=9.0, tew=22.0)
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
            fc_max=0.4,
        )
        climate = [
            ClimateRecord(
                date=datetime.date(2024, 4, 1) + datetime.timedelta(days=i),
                eto=5.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(100)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=30.0, dei0=5.0, dep0=5.0),
            groundcover=GroundcoverParams(
                kcb_cover=0.20,
                fc_cover=0.3,
                h_cover=0.15,
            ),
        )
        result = run_simulation(config)
        assert len(result.daily_results) == 100
