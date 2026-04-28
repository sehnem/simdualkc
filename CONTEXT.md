# simdualkc — Project Context

## Mission

**simdualkc-core** is the mathematical simulation engine of the SIMDualKc ecosystem. It implements the **FAO-56 Dual Crop Coefficient (Dual Kc) daily water balance model** as described by Rosa et al. (2012) and the SIMDualKc v1 (2018) methodology.

The library is **Layer 1** of a planned multi-layer system:

| Layer | Role | Status |
|-------|------|--------|
| 1 — Core (this repo) | Pure Python simulation engine | Active development |
| 2 — API | REST/RPC wrapper over Layer 1 | Planned |
| 3 — Frontend | Web/mobile UI consuming Layer 2 | Planned |

Layer 1 must have no knowledge of Layer 2 or 3. The boundary is `run_simulation(config: SimulationConfig) -> SimulationResult`.

---

## Goals

1. **Full SIMDualKc v1 feature parity** — every feature described in `docs/simdual_tutorial_2018.pdf` must be implementable via the Python API.
2. **Irrigation scenario simulation** — compare strategies (MAD thresholds, deficit, rainfed baseline) within a single call or across batch runs; answer "when and how much to irrigate" from soil/crop/climate inputs.
3. **Data-adaptive simulation types** — support multiple simulation modes depending on available inputs (raw weather → ETo, pre-computed ETo, LAI measurements, multi-layer soil profiles, etc.).
4. **Modular, frontend-ready design** — clean Pydantic boundaries everywhere so Layer 2 can serialize/deserialize without touching the math.
5. **Regional simulation (future)** — batch `run_simulation` calls over spatial grids or multiple farm parcels; the pure-function design enables trivial parallelism.

---

## Scientific Foundations

These documents in `docs/` are **authoritative ground truth**. When an equation is ambiguous, read the source before implementing.

| Document | Key content |
|----------|-------------|
| `docs/rosa_et_al_dual_kc.pdf` | Primary reference. Two-fraction evaporation model, `ETc_act = (Ks·Kcb + Ke)·ETo`, Ks from `Dr/TAW/RAW`, parametric CR/DP (Liu et al. 2006) |
| `docs/simdual_tutorial_2018.pdf` | SIMDualKc v1 feature reference. Multi-layer soil profile, input/output format, forages, intercropping, delivery constraints |
| `docs/fao_66_crop_yield_response_water.pdf` | FAO-66. Stewart yield-water stress model `Ya/Ym = 1 − Ky(1 − ETa/ETm)`, crop Ky values, Mass-Hoffman salinity model |
| FAO-56 (Allen et al. 1998) | Penman-Monteith ETo, Kcb/Kc tables, Dual Kc §6, TAW/RAW/Dr balance — no local PDF, fetch from `http://www.fao.org/4/x0490e/` |

Use the `doc-reader` agent to extract equations, table values, and citations from these PDFs before implementing any formula.

---

## Architecture Invariants

**Keep these inviolable.** Violations make Layer 2/3 integration harder and compound over time.

### Module responsibilities

| Module | Role | May it hold state? |
|--------|------|--------------------|
| `models.py` | Pydantic input/output models, validation | No |
| `kcb.py` | Basal crop coefficient equations | No |
| `evaporation.py` | Soil evaporation, two-fraction model | No |
| `water_balance.py` | TAW, RAW, Ks, Dr update | No |
| `auxiliary.py` | Runoff (CN), deep percolation, capillary rise | No |
| `eto.py` | FAO-56 Penman-Monteith ETo | No |
| `irrigation.py` | Automated scheduling logic | No |
| `yield_model.py` | Stewart water-yield model | No |
| `reporting.py` | Seasonal summaries, yield loss | No |
| `data_loader.py` | Load bundled crop/soil reference data | No |
| `simulation.py` | Daily loop — the only orchestrator | **Yes — owns dr, dei, dep** |

### Rules

- **Stateless math modules.** `kcb.py`, `evaporation.py`, `water_balance.py`, `auxiliary.py`, `eto.py`, `irrigation.py` contain pure functions: floats in, floats out. No module-level state, no side effects.
- **`simulation.py` is the only stateful orchestrator.** All time-indexed state (`dr`, `dei`, `dep`, daily accumulators) lives here and only here.
- **`run_simulation` is a pure function.** No global state. Calling it N times concurrently with different configs is safe and correct — this is how batch/regional simulation works.
- **Pydantic at all external boundaries.** `SimulationConfig` in, `SimulationResult` out. Internal simulation state uses plain Python types (float, int, bool).
- **No DB, no API, no plotting.** This library computes; others present. Do not add matplotlib, database connections, or HTTP clients to the core.

---

## Simulation Types

The library must support these modes, controlled by `SimulationConfig`:

| Mode | Key config fields |
|------|-------------------|
| Rainfed (no irrigation) | `irrigation=None` |
| Manual irrigation | `irrigation.events: list[IrrigationEvent]` |
| MAD threshold scheduling | `irrigation.strategy: MADThresholdStrategy` |
| Stage-varying deficit | `irrigation.strategy: DeficitIrrigationStrategy` |
| Raw weather → ETo | Use `eto.weather_to_climate_records()` before `run_simulation` |
| Multi-layer soil | `SoilParams.layers: list[SoilLayer]` (up to 5) |
| LAI-based fraction cover | `CropParams.lai_values + lai_dates` |
| Orchard + groundcover | `SimulationConfig.groundcover: GroundcoverParams` |
| Salinity stress | `SimulationConfig.salinity: SalinityParams` |
| Yield estimation | `SimulationConfig.yield_params: YieldParams` |

Multi-scenario comparison: call `run_simulation` once per config variant, then compare `SimulationResult` objects.

---

## Current State

### Implemented
- Multi-layer soil (5 layers, dynamic TAW as root depth grows)
- FAO-56 Penman-Monteith ETo from raw weather
- LAI-based fraction cover
- Automated irrigation: MAD threshold, deficit strategies, harvest-stop, minimum interval
- Groundcover/orchard (active inter-row vegetation)
- Yield summaries (Stewart model)
- Salinity stress (Mass-Hoffman)
- Mulch effects
- Seasonal reporting: stress summary, irrigation opportunity metrics

### Missing (see `gap_analysis.md` for full detail)

Priority order:

1. **Forage crops with multiple cuts** — cutting cycles, root depth reset between cuts, varying Kcb after cut
2. **Irrigation delivery constraints** — rotational delivery schedules, minimum irrigation intervals beyond simple `min_interval`
3. **Full parametric capillary rise** — `compute_cr_parametric` is a stub; needs water table depth input integrated into `ClimateRecord` and the simulation loop
4. **Intercropping** — overlapping or contiguous crops sharing the same soil profile
5. **Climate data validation** — Jan 1 → Dec 31 completeness check, auto-padding with mean values
6. **Pedotransfer functions** — soil texture (sand/clay %) → θ_fc, θ_wp, TEW, REW estimation
7. **Regional/batch simulation** — multi-field or multi-location runner (pure function design already supports this; needs a thin orchestration layer)

---

## Reference Database (`database_export/`)

`database_export/` contains a full export of the original SIMDualKc Access database as Parquet files. It is **gitignored** (not shipped with the package). The bundled `src/simdualkc/data/` holds only `crops.parquet` and `soils.parquet` — curated subsets for `data_loader.py`.

Use `database_export/` for: understanding the original data model, extracting real-world parameter values, and building validation fixtures.

### Soil parameters
| Table | Rows | Key columns |
|-------|------|-------------|
| `T_opcoes_solo` | 175 | `nome_solo`, `num_horiz`, `topo_horiz`–`espessura_horiz` (multi-layer), `valor_taw/fc/wp`, `perc_agros/afina/limo/arg` (texture %), `valor_tew/rew`, `densi_apar` |
| `T_aux_TAW` | 12 | `Solo`, `TAW_min`, `TAW_max` — lookup ranges by texture class |
| `T_aux_TEW` | 9 | `Solo`, `TEW_max/min_baixo/alto` — TEW ranges by texture and bulk density |
| `T_aux_REW` | 9 | `Solo`, `Rew_max`, `REW_min` — REW ranges by texture |

`T_opcoes_solo` contains real sand/clay/silt percentages and multi-layer horizon data — **the ground truth for implementing PTF-based TAW/TEW/REW estimation**.

### Climate data
| Table | Rows | Key columns |
|-------|------|-------------|
| `T_Clima` | 40 400 | `Estacao`, `Data`, `T_max/min`, `HR_min`, `V_vento` (wind), `Rn`, `ea/es`, `Eto`, `P_Ro` |
| `T_Estacao` | 26 | `Estacao`, `Altitude`, `Altura_Anemometro`, `Latitude`, `hemisf` |

Real multi-station historical weather series — useful for ETo validation and climate data validation tests.

### Features with real data (useful for upcoming implementation)
| Feature | Tables |
|---------|--------|
| **Forages / multi-cut** | `T_Forragens` (5 rows): `DurIni/Dev/Mid/Late`, `CutDate`, `NumOrdCiclo`, `StartDate` — cut cycle structure |
| **LAI / fc at dates** | `T_Lai_Dates` (14 rows): `LaiDate`, `LaiValue`; `T_fc_date` (21 rows): `fc_data`, `fc_valor`; `T_KcbAdj_LAI` (20 rows): Kcb adjusted from LAI |
| **Irrigation options** | `T_irrigation_options` (71 rows): MAD per stage (`mad_men/mai_pini/pdev/pmid/plate`), upper limits, fixed depths, farm pond; `T_IrrigFrequency`: rotational delivery intervals; `T_UserSchedule` (750 rows): user-defined schedules |
| **Groundcover** | `T_groundcover` (6 rows): `FrCcIntRowIni/RowIni`, `CcMaxHeight`, `CcKcbFull`, density/height by row and inter-row; `T_GCover_Manag` (22 rows): management operations with before/after density; `T_GCover_NoManag` (2 rows) |
| **Capillary rise / groundwater** | `T_asc_capilar` (10 rows): parametric coefficients `a1–b4`, single/variable/parametric options; `T_CRise_Param` (232 rows): `WTableDepth`, `LaiParam` by date; `T_CRiseDates` (6 rows): `DatesPotCR`, `ValuePotCR`; `T_wt_depht` (0 rows, schema only): water table depth time series |
| **Intercropping** | `T_intercropping` (5 rows): `opcao_contiguous/overlap`, two crop IDs, `fraccao_primeira/segunda` |
| **Salinity** | `T_Salinity` (15 rows): `EceThreshold_cult`, `param_b` (Mass-Hoffman), single/interval options; `T_MultipleSoilEce/WaterEce`: time-varying ECe series |
| **Mulch** | `T_mulch` (10 rows): plastic/organic options, `Fc_mulch`, evap reduction %, hole/row spacing |

### Result tables (validation fixtures)
| Table | Rows | Use |
|-------|------|-----|
| `T_Resultados` | 4 186 | Full daily output from original SIMDualKc runs — ground truth for regression tests |
| `T_WaterBal_result` | 35 | Seasonal water balance totals |
| `T_yield_results` | 10 | Stewart yield loss per period |
| `T_UserSchedule_result` | 590 | Irrigation scheduling outputs (ETa/ETm, %TAW, %RAW) |

`T_Resultados` columns map directly to `DailyResult` fields — use it to validate the simulation loop against original software.

---

## Roadmap

**Short term** (next features to implement):
- Full CR parametric (water table depth in `ClimateRecord`)
- Delivery constraints in `IrrigationStrategy`

**Mid term**:
- Intercropping support
- Climate data validation and padding
- PTF-based soil parameter estimation

**Long term**:
- Regional batch runner (parallel `run_simulation` over a grid)
- Layer 2: REST API wrapping the core
- Export formats for irrigation scheduling reports

---

## Quality Standards

These are non-negotiable:

1. **Public documentation is required, not optional.** Scientific software that doesn't explain its equations cannot be trusted. The `doc-writer` agent owns `docs/` and `mkdocs.yml` — it writes the public-facing MkDocs site, not code comments. When implementing a feature, notify the doc-writer so it can cover the new equations and parameters. In source code: write no comments or docstrings unless the *why* is non-obvious from the names alone. A variable named `ks_stress` with a physically meaningful range check needs no comment. A workaround for a floating-point edge case does.

2. **Precision first.** Floating-point errors in a daily balance accumulate over 180+ simulation days. No shortcuts. Use `numpy` for vectorized operations; avoid unnecessary precision loss.

2. **Tests required.** Every new equation needs a unit test. Where possible, validate against worked examples in FAO-56, FAO-66, or the SIMDualKc tutorial. Regression tests for the full simulation loop.

3. **Units in names.** `depth_mm`, `eto_mm_day`, `theta_fc` (dimensionless fraction), `zr_m` (meters). Never `value`, `d`, `x`.

4. **No magic numbers.** Every equation constant must be traceable — either named (`REW_DEFAULT = 8.0`) or cited inline (`# FAO-56 Eq. 21`).

5. **FAO docs are ground truth.** When an equation in code diverges from the PDF, the PDF wins. Fix the code.

6. **`run_simulation` stays pure.** No global state. No file I/O. No logging side effects. It must be safe to call in parallel threads or processes.

7. **Verify before done.** Run the full check suite before any commit:
   ```bash
   uv run pytest --tb=short -v
   uv run ty check src/
   uv run ruff check src/
   ```
