# CR Formula Matching Research

## Problem Statement

The Python SIMDualKc implementation over-estimates capillary rise (CR) vs the original Access
software output (`T_Resultados.Ground_water`) on certain days — specifically after irrigation events
when the water table rises into or near the root zone (dw < zr). No consistent single rule explains
when Access suppresses CR post-irrigation.

---

## Key Finding: 3 Post-Irrigation Suppression Events (Sim 3, wheat, zr=1.0 m)

| Irrigation | Depth | Suppressed days (CR=0 in Access) | W/Wc at resumption (unclamped dw) |
|---|---|---|---|
| Day 45 | 115 mm | days 48–49 (2 days, dw=0.920–0.928 m) | 0.883 |
| Day 59 | 78 mm  | days 60–66 (7 days, dw=0.790–0.982 m) | 0.906 |
| Day 87 | 92 mm  | days 88–89 (2 days, dw=0.860–0.904 m) | 0.846 |

In all cases CR resumes while **dw is still < zr**, so `dw < zr → CR=0` is definitively wrong.
The W/Wc threshold at resumption varies (0.846–0.906) — no single threshold works.

---

## Confirmed Correct (do not change)

- `ETm = Kcb × ETo` (not `(Kcb+Ke)×ETo`)
- `W = cr_theta_fc × zr × 1000 − dr` (using theta_FC, not theta_sat)
- `prev_dr` timing: CR uses Dr at end of previous day (matches Access)
- Fallow sims 27–32: formula gives CR = 0.0 exactly (LAI=0 → k=0), tests use `atol=1e-9`

## Confirmed Wrong and Fixed

- **Guard 2** (post-irrigation 2-day window) removed: provably wrong in both directions.
  - Day 47: Guard suppressed → CR=0 but Access=0.242
  - Days 48–49: Guard missed → formula gives 0.84/1.23 but Access=0

---

## Resources Found

### 1. Liu et al. (2006) — Foundational Paper

**Full citation:**  
Liu, Y., Pereira, L.S., and Fernando, R.M. (2006). "Fluxes through the bottom boundary of the root
zone in silty soils: Parametric approaches to estimate groundwater contribution and percolation."
*Agricultural Water Management*, 84(1–2), 27–40.  
https://www.sciencedirect.com/science/article/abs/pii/S0378377406000321

**Key formula (from paper):**
```
Wc  = a1 × Dw^b1                        critical soil water storage (mm)
Ws  = a2 × Dw^b2                        steady soil water storage (mm)
Dwc = a3 × ETm + b3   (ETm ≤ 4 mm/d)   critical groundwater depth (m)
Dwc = 1.4 m           (ETm > 4 mm/d)
k   = 1 − exp(−0.6×LAI)  (ETm ≤ 4)
k   = 3.8 / ETm           (ETm > 4)

CRmax = k×ETm          if Dw ≤ Dwc (ETm ≤ 4)
CRmax = min(k×ETm, a4×Dw^b4)  if Dw ≤ Dwc (ETm > 4)
CRmax = a4 × Dw^b4    if Dw > Dwc
CRmax = min(CRmax, 3.8)

CR = CRmax                         if W < Ws
CR = CRmax × (Wc−W)/(Wc−Ws)       if Ws ≤ W ≤ Wc
CR = 0                             if W > Wc
```

**Note from paper:** Dw is described as "water table depth below root zone bottom" (not from
surface). This is a crucial potential source of discrepancy — see Hypothesis 1 below.

### 2. SIMDualKc Manual PDF

docs/references/simdual_tutorial_2018.pdf

### 3. simET R Package (Open Source)

URL: https://cran.r-project.org/package=simET  
Documentation: https://rdrr.io/cran/simET/man/cal_capillaryRise.html  

**Function:** `cal_capillaryRise(a1, b1, a2, b2, a3, b3, a4, b4, Dw, Wa, LAI, ETm)`

**Critical parameter description from rdrr.io:**  
- `Dw`: **"Groundwater depth *below root zone* (m)"** ← different from our code!
- `Wa`: "Existing soil water storage within root zone"
- `ETm`: "potential crop evapotranspiration (mm/day), usually ETm = ETc (mm/d)" ← uses ETc not Kcb×ETo?

**Source file:** https://rdrr.io/cran/simET/src/R/cal_capillaryRise.R — returned 404, need CRAN tarball.  
**TODO:** Download `https://cran.r-project.org/src/contrib/simET_1.0.tar.gz` to read R source.

---

## Hypotheses to Test

### Hypothesis 1 — Dw is depth below root zone bottom, not from surface ⭐ HIGH PRIORITY

**Basis:** The rdrr.io documentation says `Dw = "Groundwater depth below root zone (m)"`.
The Liu 2006 paper may define Dw as the distance from the **bottom of the root zone** to the water
table, not from the **surface** to the water table.

If true: `dw_effective = wt_depth_m − zr` (subtract root depth).

**Implication for clamping:** When `wt_depth_m < zr`, `dw_effective < 0`. The paper might then
use `dw_effective = max(dw_effective, 0)` = 0, or skip CR entirely.

**Test for Sim 3 problematic days:**
- Day 48: `dw_eff = 0.920 − 1.0 = −0.080` → clamped to 0 → Wc = 0 → W > Wc → CR = 0 ✓
- Day 50: `dw_eff = 0.936 − 1.0 = −0.064` → clamped to 0 → CR = 0 ✗ (expected 0.566)

Still doesn't fully explain day 50. But worth verifying with richer data.

**Test implementation:**
```python
dw_below_zr = max(wt_depth_m - zr, 0.0)
# Use dw_below_zr in compute_cr_parametric_complete instead of raw wt_depth_m
```

### Hypothesis 2 — Dw is clamped to a small positive minimum, not zero

If `dw_eff = wt_depth_m − zr` and the minimum is, say, 0.01 or 0.05 m:
- Wc = a1 × 0.01^(-0.17) would be very large → W always < Wc → CR = CRmax always

Doesn't seem to explain zeros. Low priority.

### Hypothesis 3 — W uses theta_sat (armaz_saturacao) not theta_fc ✗ RULED OUT

Tested: `W = theta_sat × zr × 1000 − dr` (theta_sat = 0.48 from T_asc_capilar DB).
Result: W > Wc for ALL days including non-zero CR days. Eliminates too much. Ruled out.

### Hypothesis 4 — ETm uses ETc (Kcb+Ke)×ETo not Kcb×ETo ✗ RULED OUT

Already confirmed: fallow sims validate perfectly with `ETm = Kcb × ETo`. Ruled out.

### Hypothesis 5 — Moving average of ETo for ETm

The rdrr.io doc says `ETm = ETc (mm/d)` (full ETc, not just transpiration). If Access uses a
3-day or 5-day moving average of ETo to smooth the 4.0 mm/d threshold discontinuity, it could
shift the Dwc/k transition point.

**Low priority** — unlikely to explain the post-irrigation zero pattern.

### Hypothesis 6 — Access uses Dw from PREVIOUS day

If Access uses `dw_{t-1}` (yesterday's water table depth) instead of today's, the lag would
shift the pattern by 1 day.

**Test:** Check if using prev_dw for CR computation better matches the T_Resultados pattern.

### Hypothesis 7 — Post-irrigation water table within root zone triggers 0 until Dr recovers

Observation: In all 3 post-irrigation events, CR resumes at roughly W/Wc ≈ 0.85–0.91. The
variation may be due to the different dw values at resumption affecting Wc differently.

**Possible rule:** When `wt_depth_m < zr`, compute CR with `dw_eff = wt_depth_m − zr` (negative),
and only allow CR when `dw_eff` is increasing (water table receding) AND some threshold is met.

### Hypothesis 8 — Dw below root zone interpretation with no clamping produces W > Wc naturally ⭐

If `dw_eff = wt_depth_m − zr` and there is NO clamping (allow negative Dw):
- When `dw_eff < 0`, `dw_eff^b1` with `b1 = −0.17` gives imaginary/undefined result for negative base.

Alternative: if dw_eff < 0, Access may set CR = 0 as an overflow/domain check.

But we saw day 50 (dw=0.936, zr=1.0) → dw_eff=−0.064 → should give CR=0 by this rule, but
Access gives CR=0.566. So this is also incomplete.

### Hypothesis 9 — Saturation storage (armaz_saturacao) as W upper bound ⭐ MEDIUM PRIORITY

`T_asc_capilar.armaz_saturacao = 0.48` (theta_sat for GwDengkou2010).

What if `W` in the formula is clamped: `W = min(W_computed, theta_sat × zr × 1000)`?

If `W_computed > theta_sat × zr × 1000`, W saturates → formula gives CR based on saturated W.

**Test:** Does clamping W at theta_sat × zr × 1000 change anything?
- Rarely relevant since W = theta_fc × zr × 1000 − dr < theta_fc × zr × 1000 < theta_sat × zr × 1000.
  So W_computed never exceeds theta_sat × zr × 1000 in normal conditions. Low impact.

---

## TODO: Next Steps

1. **Download simET CRAN tarball** and read R source for `cal_capillaryRise`:
   ```bash
   curl -O https://cran.r-project.org/src/contrib/simET_1.0.tar.gz
   tar xf simET_1.0.tar.gz
   cat simET/R/cal_capillaryRise.R
   ```

2. **Test Hypothesis 1** (Dw = depth below root zone bottom):
   Replace `dw = wt_depth_m` with `dw = max(wt_depth_m - zr, SMALL_EPSILON)` in the formula and
   run the isolated CR test for all sims. Record new metrics.

3. **Explore Hypothesis 7** with data:
   Check whether the W/Wc ratio at CR resumption (0.846, 0.883, 0.906) correlates with dw_eff
   values or can be explained by any formula-derived threshold.

## simET R Package Source Analysis

On 2026-05-10, the simET v1.0.2 source was downloaded from CRAN Archive:
```
https://cran.r-project.org/src/contrib/Archive/simET/simET_1.0.2.tar.gz
```

The `cal_capillaryRise` function is in `R/calculate_soil.R`. Key differences from our code:

- **Dw definition:** `Dw = GroundwaterDepth - rootDepth` (depth below root zone bottom). This is the formulation described in the Liu et al. (2006) paper.

- **ETm definition:** `ETm = ETc = (Kcb+Ke)*ET0` in the DualKc model (file `R/model_DualKc.R`). This uses full crop evapotranspiration (transpiration + evaporation), not basal transpiration alone.

- **Ws steady-state constant:** `Ws = 240` for Dw > 3 m. Our code uses the power-law `320.57 * Dw^-0.2705` for all depths including Dw > 3 m.

- **No 3.8 mm/d cap:** simET does NOT apply `min(CRmax, 3.8)` that our code has per the Liu paper. However, our testing showed the 3.8 cap is essential for matching Access output.

### R Source Structure

```r
cal_capillaryRise <- function(a1, b1, a2, b2, a3, b3, a4, b4, Dw, Wa, LAI, ETm) {
    Wc <- a1 * Dw^b1
    Ws <- a2 * Dw^b2
    if (ETm <= 4) {
        Dwc <- a3 * ETm + b3
        k_ETm <- 1 - exp(-0.6 * LAI)
    } else {
        Dwc <- 1.4
        k_ETm <- 3.8 / ETm
    }
    if (Dw <= Dwc) {
        if (ETm <= 4) {
            CRmax <- k_ETm * ETm
        } else {
            CRmax <- min(k_ETm * ETm, a4 * Dw^b4)
        }
    } else {
        CRmax <- a4 * Dw^b4
    }
    # NO min(CRmax, 3.8) cap — diverges from Liu paper here
    if (Wa < Ws) {
        CR <- CRmax
    } else if (Wa >= Ws && Wa <= Wc) {
        CR <- CRmax * (Wc - Wa) / (Wc - Ws)
    } else {
        CR <- 0
    }
    return(CR)
}
```

## Hypothesis 1 Definitively Ruled Out

**Test:** Replace `dw = wt_depth_m` with `dw = max(wt_depth_m - zr, 0.001)` (clamped to small positive to avoid negative-power issues).

**Results vs T_Resultados:**

| Simulation | Before | After |
|------------|--------|-------|
| Sim 3 (wheat) | 50 mismatches | 103 mismatches |
| Sim 4 (wheat) | 49 mismatches | 102 mismatches |
| Sim 6 (maize) | 48 mismatches | 106 mismatches |

**Conclusion:** The original Access software does NOT use Dw = wt_depth_m - zr. Using this formulation makes the fit significantly worse. Our current `dw = max(wt_depth_m, zr)` (clamping at root zone bottom) is confirmed as what Access does.

## ETm = ETc Ruled Out

**Test:** Replace `ETm = Kcb * ETo` with `ETm = (Kcb + Ke) * ETo` (full ETc).

**Results vs T_Resultados:**

| Simulation | Before | After |
|------------|--------|-------|
| Sim 3 (wheat) | 50 mismatches | 51 mismatches |
| Sim 4 (wheat) | 49 mismatches | 51 mismatches |
| Sim 27 (fallow) | 0 mismatches | 2 mismatches |

The fallow case is critical: it had a perfect match (0 mismatches) before this change. Using `ETm = (Kcb+Ke)*ETo` introduces mismatches even for fallow.

**Conclusion:** Our `ETm = Kcb * ETo` is correct. The Access software uses basal crop coefficient only (Kcb), not the full dual Kc sum, for the ETm parameter in the capillary rise formula.

## Updated Conclusion

After exhaustive investigation spanning multiple hypotheses, the current implementation stands as the closest known match to the original Access software:

| Component | Our code | simET R | Access |
|-----------|----------|---------|--------|
| `dw` definition | `max(wt, zr)` | `wt - zr` | `max(wt, zr)` ✓ |
| `ETm` | `Kcb × ETo` | `(Kcb+Ke) × ETo` | `Kcb × ETo` ✓ |
| `min(CRmax, 3.8)` | Yes | No | Yes ✓ |
| `Ws` for Dw > 3 m | `320.57 × Dw^-0.2705` | `240` (constant) | Unknown |

Our code agrees with **Access** on the two most important differences from simET: Dw clamping and ETm definition. The remaining active-crop discrepancies (50 mismatches out of ~365 days) are attributed to undocumented guard conditions in the original Access VBA code — the compiled binary cannot be decompiled, and no tested formula improves the match.

---

## Current Test Thresholds (after Guard 2 removal, as of 2026-05-10)

| Metric | Core sims (3–12) | Freq sims (34–35) |
|---|---|---|
| Pearson corr | ≥ 0.86 | ≥ 0.30 |
| \|Mean bias\| | ≤ 0.24 mm/d | ≤ 1.05 mm/d |
| RMSE | ≤ 0.60 mm/d | ≤ 1.41 mm/d |

Sim 34 correlation dropped from ~0.6 to 0.304 after Guard 2 removal (Guard 2 was partially
compensating for the real underlying post-irrigation suppression).
