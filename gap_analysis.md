# Gap Analysis: Python Implementation vs. SIMDualKc Tutorial

This document tracks the implementation status of features from the official SIMDualKc tutorial.

## 1. Mandatory Input Data

### Soil Data Profile
- **[PARTIAL] Multi-layer Soil Support**: Up to 5 layers are supported in `models.py` and `water_balance.py` with dynamic TAW by root depth. TAW computation via weight fractions or pedo-transfer functions (PTF) remains external pre-processing.
- **[MISSING] TAW Computation Methods**: Built-in support for computing TAW via weight fractions or PTF is not implemented.
- **[MISSING] Soil Texture Details**: Sand/clay percentages for the evaporable layer (used to estimate TEW/REW) are not stored or used.

### Climate Data Profile
- **[DONE] ETo Calculator**: FAO-56 Penman-Monteith implemented in `eto.py` — `compute_eto` and `weather_to_climate_records`.
- **[MISSING] Climate Data Validation**: The "Jan 1st to Dec 31st" rule and automatic padding of missing days are not implemented.

### Crop Characterization Profile
- **[MISSING] Forages with Multiple Cuts**: Logic for cutting cycles, varying root depths, and growth stages between cuts is missing.
- **[MISSING] LAI-based Fraction Cover**: Full derivation of fc from LAI at specific dates is not yet implemented. Current model uses simplified interpolation.

### Irrigation Management Profile
- **[DONE] Automated Irrigation Scheduling**: MAD threshold and deficit irrigation strategies implemented in `irrigation.py`.
- **[MISSING] Delivery Constraints**: Rotational deliveries and minimum interval constraints are not implemented.
- **[MISSING] Harvest-relative Stop**: Option to stop irrigation N days before harvest is not implemented.

## 2. Optional Input Data (Extensions)

- **[MISSING] Active Groundcover**: No support for row/inter-row management, tillage effects, or groundcover growth dynamics.
- **[MISSING] Intercropping**: Only one crop at a time. Overlapping or contiguous intercropping is not supported.
- **[PARTIAL] Groundwater**:
    - Capillary rise parametric method (Liu et al., 2006) is stubbed and requires water table depth inputs.
    - Deep percolation parametric method is partially implemented but needs verification.

## 3. Workflow & Results

- **[DONE] Yield Loss Summaries**: `format_yield_loss_table` and `compute_stress_summary` in `reporting.py`.
- **[DONE] Irrigation Opportunity Stats**: `format_irrigation_opportunity_table` and `compute_irrigation_summary` in `reporting.py`.
- **[MISSING] Graphics Generation**: No built-in plotting. Relies on external pandas/matplotlib.

## 4. Data Access

- **[DONE] Database Auxiliary Functions**: `list_crops`, `list_soils`, `load_crop_params`, `load_soil_params` in `data_loader.py`.

---

## Implementation Roadmap

### Done
- ETo calculator (FAO-56 Penman-Monteith)
- Automated irrigation scheduling (MAD and deficit strategies)
- Yield loss and irrigation summaries
- Database helpers for crop/soil selection
- Multi-layer soil (partial — model layer, not PTF)

### Mid-term
- Full LAI-based fraction cover derivation
- Climate data validation and gap padding
- Delivery constraints (rotational, harvest-relative stop)

### Long-term
- Active groundcover dynamics
- Intercropping support
- Full groundwater model (capillary rise verification)
- Built-in graphics generation
