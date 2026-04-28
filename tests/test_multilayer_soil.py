"""Tests for multi-layer soil support and TAW computation."""

import datetime

import pytest

from simdualkc.models import (
    ClimateRecord,
    CropParams,
    InitialConditions,
    SimulationConfig,
    SoilLayer,
    SoilParams,
)
from simdualkc.simulation import run_simulation
from simdualkc.water_balance import compute_taw, compute_taw_multilayer


class TestComputeTawMultilayer:
    """Tests for compute_taw_multilayer function."""

    def test_single_layer_equals_standard_taw(self) -> None:
        """Single layer should match standard TAW formula."""
        layers = [
            SoilLayer(depth_m=1.0, theta_fc=0.32, theta_wp=0.12),
        ]
        zr = 1.0
        expected = compute_taw(0.32, 0.12, 1.0)
        assert compute_taw_multilayer(layers, zr) == pytest.approx(expected)

    def test_root_below_first_layer(self) -> None:
        """When zr < first layer bottom, only partial layer contributes."""
        layers = [
            SoilLayer(depth_m=1.0, theta_fc=0.30, theta_wp=0.10),
        ]
        # zr=0.5 m: half the layer
        taw = compute_taw_multilayer(layers, 0.5)
        expected = 1000.0 * (0.30 - 0.10) * 0.5  # 100 mm
        assert taw == pytest.approx(expected)

    def test_two_layers_full_depth(self) -> None:
        """Two layers, full root depth reaches both."""
        layers = [
            SoilLayer(depth_m=0.5, theta_fc=0.35, theta_wp=0.15),
            SoilLayer(depth_m=1.0, theta_fc=0.28, theta_wp=0.10),
        ]
        zr = 1.0
        # Layer 1: 0.5 m * (0.35-0.15) * 1000 = 100 mm
        # Layer 2: 0.5 m * (0.28-0.10) * 1000 = 90 mm
        # Total: 190 mm
        taw = compute_taw_multilayer(layers, zr)
        assert taw == pytest.approx(190.0)

    def test_two_layers_partial_second(self) -> None:
        """Root in middle of second layer."""
        layers = [
            SoilLayer(depth_m=0.5, theta_fc=0.35, theta_wp=0.15),
            SoilLayer(depth_m=1.0, theta_fc=0.28, theta_wp=0.10),
        ]
        zr = 0.75  # 0.5 m in first layer, 0.25 m in second
        # Layer 1: 100 mm
        # Layer 2 partial: 0.25 * 180 = 45 mm
        # Total: 145 mm
        taw = compute_taw_multilayer(layers, zr)
        assert taw == pytest.approx(145.0)

    def test_zero_root_depth_returns_zero(self) -> None:
        """zr=0 should return 0."""
        layers = [SoilLayer(depth_m=1.0, theta_fc=0.32, theta_wp=0.12)]
        assert compute_taw_multilayer(layers, 0.0) == 0.0

    def test_root_above_all_layers(self) -> None:
        """zr very small only gets first layer portion."""
        layers = [
            SoilLayer(depth_m=0.3, theta_fc=0.30, theta_wp=0.10),
        ]
        zr = 0.1
        taw = compute_taw_multilayer(layers, zr)
        assert taw == pytest.approx(20.0)  # 0.1 * 200


class TestSoilParamsMultilayer:
    """Tests for SoilParams with layers."""

    def test_layers_ordered_validation(self) -> None:
        """Layers must be ordered by depth."""
        with pytest.raises(ValueError, match="ordered by increasing depth"):
            SoilParams(
                theta_fc=0.32,
                theta_wp=0.12,
                layers=[
                    SoilLayer(depth_m=0.6, theta_fc=0.30, theta_wp=0.10),
                    SoilLayer(depth_m=0.3, theta_fc=0.28, theta_wp=0.08),
                ],
                rew=9.0,
                tew=22.0,
            )

    def test_uses_multilayer_true_when_layers(self) -> None:
        """uses_multilayer returns True when layers provided."""
        soil = SoilParams(
            theta_fc=0.32,
            theta_wp=0.12,
            layers=[
                SoilLayer(depth_m=1.0, theta_fc=0.32, theta_wp=0.12),
            ],
            rew=9.0,
            tew=22.0,
        )
        assert soil.uses_multilayer() is True

    def test_uses_multilayer_false_when_no_layers(self) -> None:
        """uses_multilayer returns False when layers is None."""
        soil = SoilParams(theta_fc=0.32, theta_wp=0.12, rew=9.0, tew=22.0)
        assert soil.uses_multilayer() is False


class TestSimulationWithMultilayer:
    """Integration tests: full simulation with multi-layer soil."""

    def test_multilayer_simulation_runs(self) -> None:
        """Simulation with multi-layer soil completes without error."""
        soil = SoilParams(
            theta_fc=0.32,
            theta_wp=0.12,
            layers=[
                SoilLayer(depth_m=0.5, theta_fc=0.35, theta_wp=0.15),
                SoilLayer(depth_m=1.2, theta_fc=0.30, theta_wp=0.12),
            ],
            rew=9.0,
            tew=22.0,
        )
        crop = CropParams(
            kcb_ini=0.15,
            kcb_mid=1.10,
            kcb_end=0.35,
            stage_lengths=[30, 40, 50, 30],
            plant_date=datetime.date(2024, 4, 1),
            zr_ini=0.15,
            zr_max=1.0,
            h_max=2.0,
            p_tab=0.55,
            fc_max=0.90,
        )
        climate = [
            ClimateRecord(
                date=datetime.date(2024, 4, 1) + datetime.timedelta(days=i),
                eto=5.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(50)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=30.0, dei0=5.0, dep0=5.0),
        )
        result = run_simulation(config)
        assert len(result.daily_results) == 50

    def test_multilayer_taw_varies_with_root_depth(self) -> None:
        """TAW in output should increase as root depth grows (multi-layer)."""
        soil = SoilParams(
            theta_fc=0.32,
            theta_wp=0.12,
            layers=[
                SoilLayer(depth_m=0.4, theta_fc=0.25, theta_wp=0.08),
                SoilLayer(depth_m=1.0, theta_fc=0.35, theta_wp=0.15),
            ],
            rew=9.0,
            tew=22.0,
        )
        crop = CropParams(
            kcb_ini=0.15,
            kcb_mid=1.10,
            kcb_end=0.35,
            stage_lengths=[15, 25, 30, 20],
            plant_date=datetime.date(2024, 4, 1),
            zr_ini=0.15,
            zr_max=0.9,
            h_max=2.0,
            p_tab=0.55,
            fc_max=0.90,
        )
        climate = [
            ClimateRecord(
                date=datetime.date(2024, 4, 1) + datetime.timedelta(days=i),
                eto=5.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(90)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=20.0, dei0=5.0, dep0=5.0),
        )
        result = run_simulation(config)

        # Early days: shallow roots, lower TAW
        taw_early = result.daily_results[10].taw
        # Late development: roots deeper, TAW should be higher
        taw_late = result.daily_results[50].taw
        assert taw_late > taw_early
