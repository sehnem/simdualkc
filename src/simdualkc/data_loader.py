"""Data loading utilities for SIMDualKc reference datasets."""

from __future__ import annotations

import datetime
import importlib.resources
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from simdualkc.models import CropParams, SoilParams

if TYPE_CHECKING:
    pass

def _get_data_path() -> Path:
    """Get the path to the internal data directory."""
    # This works both in dev and when installed as a package
    return Path(str(importlib.resources.files("simdualkc") / "data"))

def list_crops() -> list[str]:
    """List all available crop names in the reference database."""
    df = pd.read_parquet(_get_data_path() / "T_Cultura.parquet")
    return df["Cultura"].dropna().unique().tolist()

def load_crop_params(name: str) -> CropParams:
    """Load crop parameters by name from the reference database."""
    df = pd.read_parquet(_get_data_path() / "T_Cultura.parquet")
    row = df[df["Cultura"] == name]
    if row.empty:
        raise ValueError(f"Crop '{name}' not found in database.")

    data = row.iloc[0].to_dict()

    # Map historical columns to CropParams
    return CropParams(
        kcb_ini=float(data["kcb_ini"]),
        kcb_mid=float(data["kcb_mid"]),
        kcb_end=float(data["kcb_end"]),
        # Note: If plant_date isn't in DB (it's often simulation-specific),
        # we might need to handle it or use a default.
        # T_Cultura has L_ini which is a date string in some cases,
        # but often we want to set it ourselves.
        plant_date=datetime.date(2024, 1, 1),  # Placeholder, should be overridden
        stage_lengths=[
            int(data["dur_inicio"]),
            int(data["dur_develop"]),
            int(data["dur_medio"]),
            int(data["dur_final"]),
        ],
        h_max=float(data["altura_midseason"]),
        zr_ini=float(data["raiz_plant"]),
        zr_max=float(data["raiz_mid"]),
        p_tab=float(data["p_factor_mid"]),
        fc_max=float(data["fr_cob_mid"]) if not pd.isna(data["fr_cob_mid"]) else 0.8,
        ml=float(data["ml"]) if not pd.isna(data["ml"]) else 1.5,
    )

def list_soils() -> list[str]:
    """List all available soil names in the reference database."""
    df = pd.read_parquet(_get_data_path() / "T_Solo.parquet")
    return df["Solo"].dropna().unique().tolist()

def load_soil_params(name: str) -> SoilParams:
    """Load soil parameters by name from the reference database."""
    df = pd.read_parquet(_get_data_path() / "T_Solo.parquet")
    row = df[df["Solo"] == name]
    if row.empty:
        raise ValueError(f"Soil '{name}' not found in database.")

    data = row.iloc[0].to_dict()

    # Map historical columns to SoilParams
    # TAW = Agua_disponivel_med (mm/m)
    taw_m = float(data["Agua_disponivel_med"]) / 1000.0

    # We use a standard theta_fc for the soil type if not provided,
    # and derive theta_wp from TAW.
    theta_fc = 0.35  # Default for Clay/Silt Loam
    if "pf20" in data and float(data["pf20"]) > 0:
        theta_fc = float(data["pf20"]) / 100.0

    theta_wp = theta_fc - taw_m

    return SoilParams(
        theta_fc=theta_fc,
        theta_wp=theta_wp,
        rew=float(data["REW_cal"]),
        tew=float(data["TEW_cal"]),
        ze=0.15,  # Default for most studies unless specified
        cn2=75.0, # Default, T_Solo doesn't seem to have CN2 directly (it's in T_Runoff)
    )
