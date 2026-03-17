"""Integration tests using reference data from the original database."""

from __future__ import annotations

import pytest

from simdualkc import load_crop_params, load_soil_params
from simdualkc.models import CropParams, SoilParams


def test_load_maize_reference_data() -> None:
    """Verify we can load the maize parameters from Rosa et al. (2012) era data."""
    # This matches the 'MilhoAlvalade2005_IA' record we found
    crop = load_crop_params("MilhoAlvalade2005_IA")

    assert isinstance(crop, CropParams)
    assert crop.kcb_mid == 1.15
    assert crop.stage_lengths == [25, 45, 50, 29]
    assert crop.zr_max == pytest.approx(0.6)
    assert crop.h_max == pytest.approx(2.0)


def test_load_soil_reference_data() -> None:
    """Verify we can load standard soil parameters."""
    soil = load_soil_params("Clay")

    assert isinstance(soil, SoilParams)
    assert soil.rew == 10.0
    assert soil.tew == 24.0
    # Agua_disponivel_med was 180 -> TAW = 0.18 m/m
    # theta_fc default 0.35 -> theta_wp = 0.17
    assert pytest.approx(soil.theta_fc - soil.theta_wp) == 0.18


def test_list_data_assets() -> None:
    """Verify listing functions work."""
    from simdualkc import list_crops, list_soils

    crops = list_crops()
    soils = list_soils()

    assert "MilhoAlvalade2005_IA" in crops
    assert "Clay" in soils
