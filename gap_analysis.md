# Gap Analysis: Python Implementation vs. SIMDualKc Tutorial

This document tracks the implementation status of features from the official SIMDualKc tutorial (`docs/simdual_tutorial_2018.pdf`).

## 1. Mandatory Input Data

### Soil Data Profile
- **[DONE] Multi-layer Soil Support**: Up to 5 layers in `models.py` / `water_balance.py` with dynamic TAW by root depth.
- **[MISSING] TAW Computation via PTF**: Built-in pedotransfer functions (sand/clay % → θ_fc, θ_wp, TAW) not implemented. Sand/clay % are stored in `SoilLayer` but not used for estimation.
- **[MISSING] TEW/REW from Texture**: Sand/clay percentages for the evaporable layer (used to estimate TEW/REW) are not used automatically.

### Climate Data Profile
- **[DONE] ETo Calculator**: FAO-56 Penman-Monteith in `eto.py` — `compute_eto` and `weather_to_climate_records`.
- **[MISSING] Climate Data Validation**: Jan 1 → Dec 31 completeness check and auto-padding with mean values.

### Crop Characterization Profile
- **[DONE] Forages with Multiple Cuts**: `ForageParams` and `ForageCutCycle` in `models.py`, sawtooth Kcb/fc/h/zr interpolation in `kcb.py`, cut-day Dr cap in `simulation.py`. Cutting cycles, root depth reset between cuts, varying Kcb after cut.
- **[DONE] LAI-based Fraction Cover**: `lai_values` + `lai_dates` on `CropParams`, `interpolate_lai` in `kcb.py`, `lai_to_fc` with configurable `k_ext`.

### Irrigation Management Profile
- **[DONE] Automated Irrigation Scheduling**: MAD threshold and deficit strategies in `irrigation.py`.
- **[DONE] Harvest-relative Stop**: `days_before_harvest_stop` on `MADThresholdStrategy` and `DeficitIrrigationStrategy`.
- **[DONE] Minimum Interval**: `min_interval_days` on `MADThresholdStrategy` and `DeficitIrrigationStrategy`.
- **[DONE] Delivery Constraints**: `DeliveryConstraints` in `models.py` with rotational interval schedules (`IrrigationIntervalPeriod`), per-event max depth, fixed/stage-fixed depths, per-stage refill targets, and farm pond with refill events and capacity limits. Applied in `irrigation.py` (`apply_delivery_constraints`) and `simulation.py`.

## 2. Optional Input Data (Extensions)

- **[DONE] Active Groundcover**: `GroundcoverParams` in `models.py`, `compute_kcb_with_groundcover` in `kcb.py`. Combined Kcb for orchards/vineyards with inter-row vegetation.
- **[DONE] Mulch**: `MulchParams` in `models.py`, mulch effects in `compute_few` (`evaporation.py`).
- **[DONE] Salinity Stress**: `SalinityParams` in `models.py`, `compute_ks_salinity` in `water_balance.py` (Mass-Hoffman).
- **[DONE] Yield Estimation**: `YieldParams` in `models.py`, Stewart model in `yield_model.py`.
- **[MISSING] Intercropping**: Only one crop at a time. Overlapping or contiguous intercropping not supported.
- **[DONE] Groundwater**:
    - Constant CR: `compute_cr_constant` in `auxiliary.py` — fully implemented.
    - Parametric CR (Liu et al., 2006): `compute_cr_parametric_complete` in `auxiliary.py` — fully implemented with 8-coefficient and 4-coefficient simplified forms, `SimulationConfig` validation, water table depth interpolation helper, reference data loader.
    - Water table depth: `wt_depth_m` on `ClimateRecord` — fully integrated into simulation loop via `_compute_cr` dispatcher.
    - Deep percolation parametric: `compute_dp_parametric` in `auxiliary.py` — implemented, needs validation.

## 3. Workflow & Results

- **[DONE] Yield Loss Summaries**: `format_yield_loss_table` and `compute_stress_summary` in `reporting.py`.
- **[DONE] Irrigation Opportunity Stats**: `format_irrigation_opportunity_table` and `compute_irrigation_summary` in `reporting.py`.
- **[DONE] Simulation Summary**: `SimulationSummary` combining stress + irrigation metrics, auto-computed by `run_simulation`.
- **[MISSING] Graphics Generation**: No built-in plotting. Relies on external pandas/matplotlib (examples show how).

## 4. Data Access

- **[DONE] Database Auxiliary Functions**: `list_crops`, `list_soils`, `load_crop_params`, `load_soil_params` in `data_loader.py`.
- **[DONE] Crop/Soil Parquet Files**: Bundled in `src/simdualkc/data/`.

---

## Implementation Roadmap

### Done
- ETo calculator (FAO-56 Penman-Monteith)
- LAI-based fraction cover (interpolation + fc conversion)
- Automated irrigation scheduling (MAD and deficit strategies)
- Harvest-relative irrigation stop + minimum interval
- Irrigation delivery constraints (rotational intervals, fixed/stage-fixed depths, max depth, per-stage targets, farm pond)
- Active groundcover (orchard/vineyard combined Kcb)
- Mulch effects (evaporation reduction)
- Salinity stress (Mass-Hoffman)
- Yield estimation (Stewart water-yield model)
- Yield loss and irrigation summaries
- Database helpers for crop/soil selection
- Multi-layer soil (up to 5 layers, dynamic TAW)
- Parametric capillary rise (Liu et al., 2006)
- Parametric deep percolation (Liu et al., 2006)
- Forage multi-cut logic (cutting cycles, root depth reset, Kcb sawtooth, Dr cap on cut day)

### Short-term (next)
- Full CR parametric validation against `T_Resultados`

### Mid-term
- Climate data validation and gap padding
- PTF-based soil parameter estimation (sand/clay → θ_fc, θ_wp, TEW, REW)
- Regression tests against `T_Resultados` (4186 rows of daily output)

### Long-term
- Intercropping support
- Regional batch runner (parallel `run_simulation` over grids)
- Layer 2: REST API wrapping the core
- Export formats for irrigation scheduling reports
