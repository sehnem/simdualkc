"""Validation test case matching Rosa et al. (2012) for Maize."""

import datetime

from simdualkc import load_crop_params, load_soil_params, run_simulation
from simdualkc.models import ClimateRecord, InitialConditions, SimulationConfig


def test_maize_validation_rosa_etal() -> None:
    """
    Run a simulation using Maize (Milho) reference data and check overall logic.
    Ref: Rosa et al. (2012)
    """
    # 1. Load reference parameters
    crop = load_crop_params("MilhoAlvalade2005_IA")
    soil = load_soil_params("Clay")

    # 2. Create a representative 30-day climate window for mid-season (Portuguese summer)
    base = datetime.date(2024, 7, 1)
    crop.plant_date = base  # Align planting with simulation start
    climate = [
        ClimateRecord(
            date=base + datetime.timedelta(days=i),
            eto=6.0,    # High ETo in Mediterranean summer
            precip=0.0, # Dry summer
            u2=2.0,
            rh_min=45.0
        )
        for i in range(100)
    ]

    # 3. Running with initial stress
    ic = InitialConditions(dr0=10, dei0=10, dep0=10)

    config = SimulationConfig(
        soil=soil,
        crop=crop,
        climate=climate,
        initial_conditions=ic
    )

    result = run_simulation(config)

    # Day 80 is mid-season (25+45+10 = 80)
    day_80 = result.daily_results[79]
    # In SIMDualKc, Kcb is adjusted by Kd (density).
    # For maize with fc=0.75, Kcb will be less than tabulated 1.15.
    # Obtained value was ~0.89.
    assert 0.85 < day_80.kcb < 1.15

    # Soil is dry and no rain/irrig: Ks should eventually drop below 1.0
    # Dr starts at 50. TAW = 180mm * 0.6m = 108mm.
    # RAW = p * TAW = 0.55 * 108 = 59.4mm.
    # ETc_adj is ~1.15 * 6 = 6.9mm/day.
    # After (59.4 - 50) / 6.9 = 1.3 days, stress should start.

    assert result.daily_results[0].ks == 1.0
    # By day 100, cumulative ET (approx 100mm) + initial 10mm should exceed RAW (59mm)
    assert result.daily_results[99].ks < 1.0

    # Verify the water balance returned correctly
    df = result.to_dataframe()
    assert len(df) == 100
    assert "etc_act" in df.columns
