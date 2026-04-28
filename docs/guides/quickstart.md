# Quick Start

## Installation

```bash
pip install simdualkc-core
```

Or with visualization extras:

```bash
pip install simdualkc-core[viz]
```

## Basic Simulation

```python
import datetime
from simdualkc import run_simulation
from simdualkc.models import (
    SimulationConfig, SoilParams, CropParams,
    ClimateRecord, InitialConditions,
)

# Define soil
soil = SoilParams(
    theta_fc=0.35,   # Field capacity [m³/m³]
    theta_wp=0.20,   # Wilting point [m³/m³]
    rew=8.0,         # Readily evaporable water [mm]
    tew=25.0,        # Total evaporable water [mm]
    ze=0.10,         # Evaporative layer depth [m]
    cn2=75.0,        # Curve Number (AMC II)
)

# Define crop (e.g., tomato)
crop = CropParams(
    kcb_ini=0.15,
    kcb_mid=1.10,
    kcb_end=0.60,
    stage_lengths=[25, 30, 60, 25],  # ini, dev, mid, late [days]
    plant_date=datetime.date(2024, 3, 15),
    zr_ini=0.15,     # Initial root depth [m]
    zr_max=1.0,      # Maximum root depth [m]
    h_max=0.5,       # Maximum plant height [m]
    p_tab=0.55,      # Depletion fraction (no stress)
    fc_max=0.85,     # Maximum fraction cover
)

# Create climate records (one per day)
climate = [
    ClimateRecord(
        date=datetime.date(2024, 3, 15) + datetime.timedelta(days=i),
        eto=5.0,        # Reference ET [mm/day]
        precip=0.0,     # Precipitation [mm]
        u2=2.0,         # Wind speed [m/s]
        rh_min=45.0,    # Min relative humidity [%]
    )
    for i in range(140)  # Full season
]

# Initial conditions
ic = InitialConditions(dr0=20.0, dei0=5.0, dep0=5.0)

# Run
config = SimulationConfig(
    soil=soil, crop=crop, climate=climate,
    initial_conditions=ic,
)
result = run_simulation(config)

# Access results
df = result.to_dataframe()
print(f"Season length: {result.n_days} days")
print(f"Yield decrease: {result.summary.stress.yield_decrease_total_pct:.1f}%")
```

## Using Reference Data

```python
from simdualkc import list_crops, load_crop_params, list_soils, load_soil_params

# Browse available crops
print(list_crops())

# Load a crop from the database
crop = load_crop_params("Tomato")
crop.plant_date = datetime.date(2024, 3, 15)  # Override default

# Browse and load soil
print(list_soils())
soil = load_soil_params("Loam")
```

## Adding Irrigation

```python
from simdualkc.models import IrrigationEvent

# Manual irrigation events
irrigation = [
    IrrigationEvent(date=datetime.date(2024, 4, 1), depth_mm=40.0, fw=1.0),
    IrrigationEvent(date=datetime.date(2024, 4, 15), depth_mm=35.0, fw=1.0),
]

config = SimulationConfig(
    soil=soil, crop=crop, climate=climate,
    initial_conditions=ic,
    irrigation=irrigation,
)
```

## Automated Irrigation (MAD Threshold)

```python
from simdualkc.models import IrrigationStrategy, MADThresholdStrategy

strategy = IrrigationStrategy(
    strategy_type="mad_threshold",
    mad_threshold=MADThresholdStrategy(
        mad_fraction=0.55,          # Trigger at 55% TAW depletion
        target_pct_taw=100.0,       # Refill to field capacity
        days_before_harvest_stop=10, # Stop 10 days before harvest
        min_interval_days=5,         # At least 5 days between irrigations
    ),
)

config = SimulationConfig(
    soil=soil, crop=crop, climate=climate,
    initial_conditions=ic,
    irrigation_strategy=strategy,
)
```
