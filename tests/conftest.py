"""Tests — conftest.py: shared fixtures for all test modules."""

import datetime
import json
from pathlib import Path

import pandas as pd
import pytest

from simdualkc.models import (
    ClimateRecord,
    CropParams,
    InitialConditions,
    IrrigationEvent,
    IrrigationStrategy,
    SimulationConfig,
    SoilParams,
)


def load_cr_fixture(sim_id: int) -> tuple[SimulationConfig, pd.DataFrame]:
    """Load a parametric-CR validation fixture pair.

    Args:
        sim_id: The SIMDualKc Simulacao_ID.

    Returns:
        ``(config, expected_df)`` where *expected_df* has columns matching
        :class:`~simdualkc.models.DailyResult` field names.
    """
    fixture_dir = Path(__file__).parent / "fixtures" / "cr_parametric_validation"
    config_path = fixture_dir / f"{sim_id}_config.json"
    expected_path = fixture_dir / f"{sim_id}_expected.parquet"

    with open(config_path) as f:
        raw = json.load(f)

    def _parse_date(d: str) -> datetime.date:
        return datetime.date.fromisoformat(d)

    soil = SoilParams(**raw["soil"])
    crop = CropParams(**{**raw["crop"], "plant_date": _parse_date(raw["crop"]["plant_date"])})
    climate = [
        ClimateRecord(
            date=_parse_date(r["date"]),
            eto=r["eto"],
            precip=r["precip"],
            u2=r["u2"],
            rh_min=r["rh_min"],
            wt_depth_m=r.get("wt_depth_m"),
        )
        for r in raw["climate"]
    ]
    ic = InitialConditions(**raw["initial_conditions"])

    config = SimulationConfig(
        soil=soil,
        crop=crop,
        climate=climate,
        initial_conditions=ic,
        irrigation=[
            IrrigationEvent(
                date=_parse_date(e["date"]),
                depth_mm=e["depth_mm"],
                fw=e["fw"],
            )
            for e in raw["irrigation"]
        ],
        irrigation_strategy=IrrigationStrategy(**raw["irrigation_strategy"]),
        fw_base=raw["fw_base"],
        dp_method=raw["dp_method"],
        cr_method=raw["cr_method"],
    )

    expected = pd.read_parquet(expected_path)
    return config, expected


@pytest.fixture()
def soil() -> SoilParams:
    """Standard sandy-loam soil for shared test use."""
    return SoilParams(
        theta_fc=0.32,
        theta_wp=0.12,
        ze=0.10,
        rew=9.0,
        tew=22.0,
        cn2=75.0,
    )


@pytest.fixture()
def crop() -> CropParams:
    """Maize-like crop parameters for shared test use."""
    return CropParams(
        kcb_ini=0.15,
        kcb_mid=1.10,
        kcb_end=0.35,
        stage_lengths=[30, 40, 50, 30],
        plant_date=datetime.date(2024, 4, 1),
        zr_ini=0.15,
        zr_max=1.20,
        h_max=2.50,
        p_tab=0.55,
        fc_max=0.90,
        ml=1.5,
        kc_min=0.15,
    )


@pytest.fixture()
def climate_day() -> ClimateRecord:
    """A single typical summer day."""
    return ClimateRecord(
        date=datetime.date(2024, 4, 1),
        eto=5.0,
        precip=2.0,
        u2=2.0,
        rh_min=45.0,
    )


@pytest.fixture()
def three_day_climate() -> list[ClimateRecord]:
    """Three chronological climate records for smoke tests."""
    base = datetime.date(2024, 4, 1)
    return [
        ClimateRecord(
            date=base + datetime.timedelta(days=i),
            eto=5.0,
            precip=0.0,
            u2=2.0,
            rh_min=45.0,
        )
        for i in range(3)
    ]


@pytest.fixture()
def initial_conditions() -> InitialConditions:
    return InitialConditions(dr0=30.0, dei0=5.0, dep0=5.0)


@pytest.fixture()
def sim_config(
    soil: SoilParams,
    crop: CropParams,
    three_day_climate: list[ClimateRecord],
    initial_conditions: InitialConditions,
) -> SimulationConfig:
    return SimulationConfig(
        soil=soil,
        crop=crop,
        climate=three_day_climate,
        initial_conditions=initial_conditions,
    )
