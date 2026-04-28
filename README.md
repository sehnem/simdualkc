# simdualkc-core

> **Layer 1** of the SIMDualKc ecosystem — the mathematical core library.

Implementation of the **Dual Crop Coefficient** water balance model (FAO-56) as described by Rosa et al.
No database, no API, no GUI. Pure Python functions that receive validated data and return simulation results.

## Model Overview

The model computes daily actual evapotranspiration:

```
ETc_act = (Ks · Kcb + Ke) · ETo
```

Split into:
- **Kcb** — basal crop coefficient (transpiration)
- **Ke** — soil evaporation coefficient (two-fraction approach: irrigated + rain-only)
- **Ks** — water stress coefficient (root zone depletion)

## Features

- **Multi-layer soil**: Up to 5 layers with dynamic TAW by root depth
- **ETo calculator**: FAO-56 Penman-Monteith from raw weather (Tmax, Tmin, RH, Rs, u2)
- **LAI-based fraction cover**: fc = 1 - exp(-k_ext × LAI)
- **Automated irrigation**: MAD threshold and deficit strategies
- **Active groundcover**: Combined Kcb for orchards/vineyards with inter-row vegetation
- **Parametric groundwater**: Liu et al. (2006) capillary rise and deep percolation
- **Yield summaries**: Stewart water-yield, stress and irrigation metrics

## Quick Start

```python
from simdualkc import run_simulation
from simdualkc.models import SimulationConfig, SoilParams, CropParams, ClimateRecord, InitialConditions

# Build inputs (your data ingestion layer goes here)
config = SimulationConfig(
    soil=SoilParams(...),
    crop=CropParams(...),
    climate=[ClimateRecord(...)],  # one per day
    initial_conditions=InitialConditions(...),
)

result = run_simulation(config)
df = result.to_dataframe()
```

## Development

```bash
# Install with dev extras
uv sync --extra dev

# Run tests
uv run pytest

# Lint + format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type check
uv run ty check src/

# Set up pre-commit hooks
uv run pre-commit install
```

## Architecture

```
src/simdualkc/
├── __init__.py         # Public API
├── models.py           # Pydantic domain models (inputs + outputs)
├── kcb.py              # Basal crop coefficient equations (§2)
├── evaporation.py      # Soil evaporation equations (§3)
├── water_balance.py    # Root zone water balance + Ks (§4)
├── auxiliary.py        # RO (Curve Number), DP, CR models (§5)
├── eto.py              # FAO-56 Penman-Monteith ETo calculator
├── irrigation.py       # Automated irrigation scheduling
├── yield_model.py      # Stewart water-yield model
├── reporting.py        # Yield loss and irrigation summaries
├── data_loader.py      # Database helpers (list_crops, list_soils, load_*)
└── simulation.py       # Daily simulation orchestrator
```

## Examples

- `examples/01_basic_simulation.py` — Basic single-crop run
- `examples/02_crop_soil_comparison.py` — Compare crop/soil combinations
- `examples/03_evaporation_physics.py` — Evaporation layer deep-dive
- `examples/04_advanced_extensions.py` — Groundwater and advanced config
- `examples/05_multilayer_soil.py` — Multi-layer TAW
- `examples/06_eto_calculation.py` — Compute ETo from weather
- `examples/07_automated_irrigation.py` — MAD threshold scheduling
- `examples/08_groundcover_orchard.py` — Orchard with groundcover
- `examples/09_complete_workflow.py` — Full feature set
