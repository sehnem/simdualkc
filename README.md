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
└── simulation.py       # Daily simulation orchestrator
```
