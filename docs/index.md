# simdualkc-core

**Layer 1** of the SIMDualKc ecosystem — the mathematical simulation engine.

Implements the **FAO-56 Dual Crop Coefficient** daily water balance model as described by Rosa et al. (2012) and the SIMDualKc v1 methodology.

## Core Equation

$$ETc_{act} = (K_s \cdot K_{cb} + K_e) \cdot ET_o$$

Split into three components:

| Coefficient | Role | Module |
|---|---|---|
| $K_{cb}$ | Basal crop coefficient (transpiration) | `kcb.py` |
| $K_e$ | Soil evaporation coefficient (two-fraction) | `evaporation.py` |
| $K_s$ | Water stress coefficient (root zone depletion) | `water_balance.py` |

## Features

- **Multi-layer soil**: Up to 5 layers with dynamic TAW as root depth grows
- **ETo calculator**: FAO-56 Penman-Monteith from raw weather data
- **LAI-based fraction cover**: $f_c = 1 - \exp(-K_{ext} \cdot LAI)$
- **Automated irrigation**: MAD threshold and deficit strategies
- **Active groundcover**: Combined Kcb for orchards/vineyards
- **Parametric groundwater**: Liu et al. (2006) capillary rise and deep percolation
- **Mulch effects**: Evaporation reduction from surface cover
- **Salinity stress**: Mass-Hoffman reduction factor
- **Yield estimation**: Stewart water-yield model
- **Seasonal reporting**: Stress summary, irrigation opportunity metrics

## Quick Start

```python
from simdualkc import run_simulation
from simdualkc.models import (
    SimulationConfig, SoilParams, CropParams,
    ClimateRecord, InitialConditions,
)

config = SimulationConfig(
    soil=SoilParams(
        theta_fc=0.35, theta_wp=0.20, rew=8.0, tew=25.0,
    ),
    crop=CropParams(
        kcb_ini=0.15, kcb_mid=1.10, kcb_end=0.60,
        stage_lengths=[25, 30, 60, 25],
        plant_date="2024-03-15",
        zr_max=1.0, h_max=0.5, p_tab=0.55, fc_max=0.85,
    ),
    climate=[ClimateRecord(...)],  # one per day
    initial_conditions=InitialConditions(dr0=20.0, dei0=5.0, dep0=5.0),
)

result = run_simulation(config)
df = result.to_dataframe()
print(result.summary.stress.yield_decrease_total_pct)
```

## Architecture

```
src/simdualkc/
├── __init__.py         # Public API
├── models.py           # Pydantic domain models (inputs + outputs)
├── kcb.py              # Basal crop coefficient equations
├── evaporation.py      # Soil evaporation equations (two-fraction)
├── water_balance.py    # Root zone water balance + Ks
├── auxiliary.py        # RO (Curve Number), DP, CR models
├── eto.py              # FAO-56 Penman-Monteith ETo calculator
├── irrigation.py       # Automated irrigation scheduling
├── yield_model.py      # Stewart water-yield model
├── reporting.py        # Yield loss and irrigation summaries
├── data_loader.py      # Database helpers (list_crops, list_soils, load_*)
└── simulation.py       # Daily simulation orchestrator
```

## Design Principles

1. **`run_simulation` is a pure function** — no global state, no file I/O, no logging. Safe for parallel execution.
2. **Stateless math modules** — `kcb.py`, `evaporation.py`, `water_balance.py`, `auxiliary.py`, `eto.py` contain pure functions: floats in, floats out.
3. **Pydantic at all external boundaries** — `SimulationConfig` in, `SimulationResult` out.
4. **No DB, no API, no plotting** — this library computes; others present.

## References

- Rosa et al. (2012) — *Dual approach for computing ETc*
- Allen et al. (1998) — *FAO Irrigation and Drainage Paper 56*
- Liu et al. (2006) — *Parametric groundwater models*
- FAO-66 — *Crop yield response to water*
