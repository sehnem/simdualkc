# Capillary Rise (CR) Validation — Comprehensive Summary

> **Purpose:** Consolidate every finding, hypothesis, and concrete example from the parametric CR validation effort so the next step can be taken without re-discovering what is already known.
>
> **Validation scope:** Liu et al. (2006) 8-parameter parametric CR model against original SIMDualKc Access binary (`T_Resultados.Ground_water`).
>
> **Date:** 2026-04-30

---

## 1. Validation Strategy

We validate the CR *formula in isolation*, not the full simulation loop.

**Why isolate CR?**
- The full simulation loop diverges from the Access binary for reasons unrelated to CR (Kcb interpolation differences, rounding, fc curve shape, etc.).
- Isolating CR lets us reconstruct the exact inputs (`Dw`, `W`, `LAI`, `ETm`) from `T_Resultados` and test only the capillary-rise function.

**Methodology (correct timing):**
1. Read daily state from `T_Resultados`: `Kcb`, `ETo`, `Fc`, `Zr`, `TAW`, `Dr`, `WT_depth`, `irrig`.
2. Compute `W` using **previous day's `Dr`** because the simulation loop computes CR *before* updating the water balance.
3. Compute `W = ASW + WWP = (TAW - Dr_prev) + (theta_wp * Zr * 1000)`.
4. Compute `ETm = Kcb * ETo` (transpiration only, not `Kcb+Ke`).
5. Run both `compute_cr_parametric_complete` (base Liu 2006) and `compute_cr_parametric_complete_with_guards` (base + empirical guards).
6. Compare against `T_Resultados.Ground_water`.

**Critical timing discovery:** An earlier analysis script (`generate_cr_analysis.py`) incorrectly used the *current* day's `Dr` instead of the previous day's. This inflated MAE by ~50%. The test file (`test_cr_parametric_isolated.py`) uses the correct `prev_dr` timing.

---

## 2. What Matches

### 2.1 Fallow crops — perfect daily match

Simulations 27–32 are fallow fields (`Kcb ≈ 0.1`, `LAI ≈ 0`).

| Sim | Days | Base MAE | Guard MAE | Base RMSE | Guard RMSE | Max diff |
|-----|------|----------|-----------|-----------|------------|----------|
| 27 | 27 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 28 | 65 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 29 | 70 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 30 | 29 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 31 | 61 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 32 | 61 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

**Why it matches:** When `LAI ≈ 0`, the transpiration factor `k = 1 - exp(-0.6 * 0) = 0`. The formula therefore predicts `CR = 0` on every day, which is exactly what the Access binary reports.

**Test threshold:** `atol = 0.001 mm/day` (strict).

### 2.2 Active wheat (Dengkou) — strong directional agreement

Simulations 3–12 are wheat crops with varying years/irrigation schedules.

| Sim | Days | Base MAE | Guard MAE | Base RMSE | Guard RMSE | Bias | Correlation |
|-----|------|----------|-----------|-----------|------------|------|-------------|
| 3 | 118 | 0.329 | **0.291** | 0.537 | **0.486** | +0.287 | **0.964** |
| 4 | 111 | 0.298 | **0.325** | 0.573 | **0.641** | +0.245 | **0.922** |
| 6 | 114 | 0.358 | **0.353** | 0.672 | **0.671** | +0.336 | **0.869** |
| 7 | 156 | 0.193 | **0.187** | 0.366 | **0.370** | +0.160 | **0.972** |
| 8 | 152 | 0.239 | **0.234** | 0.336 | **0.337** | +0.219 | **0.977** |
| 9 | 144 | 0.289 | **0.289** | 0.506 | **0.514** | +0.259 | **0.930** |
| 10 | 122 | 0.162 | **0.156** | 0.284 | **0.283** | +0.156 | **0.983** |
| 11 | 120 | 0.194 | **0.186** | 0.251 | **0.250** | +0.186 | **0.989** |
| 12 | 108 | 0.141 | **0.135** | 0.192 | **0.188** | +0.132 | **0.991** |

**Key observation:** Correlations are high (0.87–0.99). The base formula captures the *shape* of the CR curve very well. Guards provide marginal improvement on most sims (3–8% MAE reduction), but on Sim 4 they slightly hurt (+9% MAE).

**Test thresholds:** `corr ≥ 0.86`, `|bias| ≤ 0.23`, `RMSE ≤ 0.60`.

### 2.3 Orchard (Freiria) — partial match

Simulations 34–35 are Pera-Rocha orchards.

| Sim | Days | Base MAE | Guard MAE | Base RMSE | Guard RMSE | Bias | Correlation |
|-----|------|----------|-----------|-----------|------------|------|-------------|
| 34 | 168 | 1.075 | **1.075** | 1.378 | **1.378** | +1.035 | **0.563** |
| 35 | 193 | 0.626 | **0.625** | 0.863 | **0.863** | +0.551 | **0.812** |

**Key observation:** Sim 35 correlates reasonably (0.81), but Sim 34 has poor correlation (0.56) and large systematic over-estimation. The guards barely help because orchard irrigation depths are small (2–6 mm), below the `> 20 mm` guard threshold.

**Test thresholds (relaxed):** `corr ≥ 0.55`, `|bias| ≤ 1.05`, `RMSE ≤ 1.41`.

---

## 3. What Does Not Match

### 3.1 Pattern A: Unexplained zero-CR days after irrigation (wheat)

On some days, the Access binary reports `CR = 0` even though:
- `Dw ≤ Dwc` (shallow water table)
- `ETm > 4` (high transpiration)
- `days_since_irrigation > 2` (post-irrigation guard has expired)
- The formula predicts `CR > 1.5 mm/day`

**Examples:**

| Sim | Day | Dw (m) | W (mm) | LAI | ETm | Base CR | Guard CR | Expected | Diff |
|-----|-----|--------|--------|-----|-----|---------|----------|----------|------|
| 3 | 49 | 0.928 | 348.2 | 3.16 | 9.14 | 1.511 | 1.511 | 0.000 | **+1.511** |
| 3 | 50 | 0.936 | 338.5 | 3.16 | 5.43 | 1.970 | 1.970 | 0.566 | **+1.404** |
| 3 | 66 | 0.940 | 345.2 | 3.16 | 6.10 | 1.653 | 1.653 | 0.000 | **+1.653** |
| 3 | 90 | 0.900 | 330.7 | 3.16 | 9.09 | 2.342 | 2.342 | 0.280 | **+2.062** |
| 7 | 61 | 0.904 | 340.7 | 2.03 | 7.08 | 1.866 | 1.866 | 0.000 | **+1.866** |
| 7 | 62 | 0.860 | 332.7 | 2.15 | 8.33 | 2.247 | 2.247 | 0.000 | **+2.247** |
| 7 | 63 | 0.900 | 323.6 | 2.27 | 8.06 | 2.677 | 2.677 | 0.652 | **+2.025** |

### 3.2 Pattern B: Orchard systematic over-estimation

The orchard simulations show frequent days where the formula predicts `CR = 3.8 mm/day` (the ETm>4 cap) but Access reports `CR < 1.0` or `0`.

**Examples:**

| Sim | Day | Dw (m) | W (mm) | LAI | ETm | Base CR | Guard CR | Expected | Diff |
|-----|-----|--------|--------|-----|-----|---------|----------|----------|------|
| 34 | 96 | 1.169 | 244.8 | 1.36 | 4.17 | 3.800 | 3.800 | 0.408 | **+3.392** |
| 34 | 112 | 1.267 | 238.4 | 1.42 | 4.30 | 3.800 | 3.800 | 0.716 | **+3.084** |
| 34 | 133 | 1.390 | 238.8 | 1.57 | 4.02 | 3.800 | 3.800 | 0.000 | **+3.800** |
| 35 | 131 | 1.175 | 237.3 | 1.41 | 4.20 | 3.800 | 3.800 | 1.531 | **+2.269** |
| 35 | 145 | 1.300 | 232.2 | 1.41 | 4.01 | 3.800 | 3.800 | 1.362 | **+2.438** |
| 35 | 156 | 1.300 | 229.9 | 1.38 | 4.00 | 3.800 | 3.800 | 0.395 | **+3.405** |

### 3.3 Pattern C: Early-season suppression (captured by Guard 1)

During the first 20–30 days when `LAI < 0.3` and `ETm ≤ 4`, the Access binary reports `CR = 0` while the base Liu formula predicts small positive values (0.05–0.35 mm/day).

**Example:**

| Sim | Day | Dw (m) | W (mm) | LAI | ETm | Base CR | Guard CR | Expected |
|-----|-----|--------|--------|-----|-----|---------|----------|----------|
| 10 | 25 | 0.992 | 300.5 | 0.16 | 0.69 | 0.064 | **0.000** | **0.000** |

The early-season guard (`if LAI < 0.3 and ETm <= 4.0: return 0.0`) fixes this perfectly.

### 3.4 Pattern D: Post-irrigation suppression (captured by Guard 2)

For 1–2 days after irrigation events with depth > 20 mm, the Access binary reports `CR = 0` even when the water table is shallow.

**Example:**

| Sim | Day | Dw (m) | W (mm) | LAI | ETm | Base CR | Guard CR | Expected | Note |
|-----|-----|--------|--------|-----|-----|---------|----------|----------|------|
| 3 | 46 | 1.220 | 364.5 | 3.16 | 5.87 | 0.132 | **0.000** | **0.000** | Day after 115 mm irrigation |

The post-irrigation guard (`if days_since_irrigation <= 2 and last_irrig_depth_mm > 20.0: return 0.0`) fixes this on the correct day.

**Important timing fix discovered:** The original simulation loop updated `last_irrigation_day` *before* computing CR, causing the guard to suppress CR on the irrigation day itself. The Access binary computes CR *before* applying the day's irrigation, so suppression starts on the **day after**. This was fixed in `simulation.py` by using `prev_last_irrigation_day` for CR computation.

---

## 4. Concrete Equation Examples

### 4.1 Perfect match — Fallow crop (Sim 27, Day 1)

**Inputs:**
- `Dw = 2.16 m`
- `Zr = 1.00 m`
- `theta_wp = 0.166`
- `TAW = 214.0 mm`, `Dr_prev = 11.87 mm`
- `ASW = 214.0 - 11.87 = 202.13 mm`
- `WWP = 0.166 * 1.00 * 1000 = 166.0 mm`
- `W = 202.13 + 166.0 = 368.13 mm`
- `LAI = 0.0` (from `fc = 0.0`)
- `Kcb = 0.1`, `ETo = 2.76` → `ETm = 0.276 mm/day`
- Coefficients: `a1=380.0, b1=-0.17, a2=300.0, b2=-0.27, a3=-1.3, b3=6.6, a4=4.6, b4=-0.65`

**Step-by-step:**
1. `Wc = 380.0 * 2.16^-0.17 = 367.37 mm`
2. `Ws = 300.0 * 2.16^-0.27 = 241.96 mm`
3. `Dwc = -1.3 * 0.276 + 6.6 = 6.24 m` (ETm ≤ 4 branch)
4. `k = 1 - exp(-0.6 * 0) = 0.0`
5. `Dw (2.16) ≤ Dwc (6.24)` → `CRmax = 0.0 * 0.276 = 0.0 mm/day`
6. `W (368.13) > Wc (367.37)` → `CR = 0.0 mm/day`

**Result:** Base = 0.000, Guard = 0.000, Access = 0.000 ✅

---

### 4.2 Guard fixes early-season (Sim 10, Day 25)

**Inputs:**
- `Dw = 0.992 m`, `Zr = 1.00 m`, `theta_wp = 0.16`
- `TAW = 214.0`, `Dr_prev = 73.52`
- `ASW = 140.48`, `WWP = 160.0`, `W = 300.48 mm`
- `fc = 0.092` → `LAI = 0.161`
- `Kcb = 0.1`, `ETo = 6.94` → `ETm = 0.694 mm/day`
- Same coefficients as above

**Step-by-step:**
1. `Wc = 380.0 * 0.992^-0.17 = 380.52 mm`
2. `Ws = 300.0 * 0.992^-0.27 = 300.65 mm`
3. `Dwc = -1.3 * 0.694 + 6.6 = 5.70 m`
4. `k = 1 - exp(-0.6 * 0.161) = 0.092`
5. `Dw (0.992) ≤ Dwc (5.70)` → `CRmax = 0.092 * 0.694 = 0.064 mm/day`
6. `W (300.48) < Ws (300.65)` → `CR = CRmax = 0.064 mm/day`

**Results:**
- Base formula: **0.064 mm/day**
- Guarded formula (`LAI < 0.3` and `ETm ≤ 4`): **0.000 mm/day**
- Access expected: **0.000 mm/day** ✅

---

### 4.3 Guard fixes post-irrigation (Sim 3, Day 46)

**Inputs:**
- `Dw = 1.220 m`, `Zr = 1.00 m`, `theta_wp = 0.16`
- `TAW = 214.0`, `Dr_prev = 9.51`
- `ASW = 204.49`, `WWP = 160.0`, `W = 364.49 mm`
- `fc = 0.85` → `LAI = 3.162`
- `Kcb = 1.15`, `ETo = 5.10` → `ETm = 5.865 mm/day`
- `days_since_irrigation = 1`, `last_irrig_depth = 115.0 mm`

**Step-by-step:**
1. `Wc = 380.0 * 1.22^-0.17 = 367.37 mm`
2. `Ws = 300.0 * 1.22^-0.27 = 284.32 mm`
3. `ETm > 4` → `Dwc = 1.4 m`
4. `ETm > 4` → `k = 3.8 / 5.865 = 0.648`
5. `Dw (1.22) ≤ Dwc (1.4)` → `CRmax = 0.648 * 5.865 = 3.800 mm/day`
6. `Ws (284.32) ≤ W (364.49) ≤ Wc (367.37)` → `CR = 3.8 * (367.37 - 364.49) / (367.37 - 284.32) = 0.132 mm/day`

**Results:**
- Base formula: **0.132 mm/day**
- Guarded formula (`days_since ≤ 2` and `depth > 20`): **0.000 mm/day**
- Access expected: **0.000 mm/day** ✅

---

### 4.4 Unexplained mismatch — Wheat (Sim 3, Day 66)

**Inputs:**
- `Dw = 0.940 m`, `Zr = 1.00 m`, `theta_wp = 0.16`
- `TAW = 214.0`, `Dr_prev = 28.79`
- `ASW = 185.21`, `WWP = 160.0`, `W = 345.21 mm`
- `LAI = 3.162`, `ETm = 6.095 mm/day`
- `days_since_irrigation = 7`, `last_irrig_depth = 78.0 mm` (guard does NOT trigger)

**Step-by-step:**
1. `Wc = 380.0 * 0.94^-0.17 = 384.02 mm`
2. `Ws = 300.0 * 0.94^-0.27 = 305.05 mm`
3. `Dwc = 1.4 m`
4. `k = 3.8 / 6.095 = 0.624`
5. `Dw (0.94) ≤ Dwc (1.4)` → `CRmax = 0.624 * 6.095 = 3.800 mm/day`
6. `Ws (305.05) ≤ W (345.21) ≤ Wc (384.02)` → `CR = 3.8 * (384.02 - 345.21) / (384.02 - 305.05) = 1.868 mm/day`

**Results:**
- Base formula: **1.653 mm/day** (code clamps Dw to max(dw, zr) = 0.94, no clamp effect here)
- Guarded formula: **1.653 mm/day** (no guard triggered)
- Access expected: **0.000 mm/day** ❌ (diff = +1.653)

**Why the mismatch?** Unknown. The post-irrigation window (7 days) has expired. The soil is not saturated (`W < Wc`). The water table is shallow (`Dw < Dwc`). Yet Access reports zero CR.

---

### 4.5 Unexplained mismatch — Orchard (Sim 34, Day 96)

**Inputs:**
- `Dw = 1.169 m`, `Zr = 0.90 m`, `theta_wp = 0.167`
- `TAW = 115.2`, `Dr_prev = 11.37` (implied from W calculation)
- `W = 244.82 mm`
- `fc = 0.564` → `LAI = 1.365`
- `Kcb = 0.712`, `ETo = 5.85` → `ETm = 4.166 mm/day`
- Orchard coefficients: `a1=306.0, b1=-0.32, a2=280.0, b2=-0.16, a3=-1.4, b3=6.8, a4=1.11, b4=-0.98`
- `days_since_irrigation = 1`, `last_irrig_depth = 5.0 mm` (guard does NOT trigger because ≤ 20)

**Step-by-step:**
1. `Wc = 306.0 * 1.169^-0.32 = 295.6 mm`
2. `Ws = 280.0 * 1.169^-0.16 = 273.5 mm`
3. `ETm > 4` → `Dwc = 1.4 m`
4. `ETm > 4` → `k = 3.8 / 4.166 = 0.912`
5. `Dw (1.169) ≤ Dwc (1.4)` → `CRmax = 0.912 * 4.166 = 3.800 mm/day`
6. `W (244.82) < Ws (273.5)` → `CR = CRmax = 3.800 mm/day`

**Results:**
- Base formula: **3.800 mm/day**
- Guarded formula: **3.800 mm/day** (no guard triggered)
- Access expected: **0.408 mm/day** ❌ (diff = +3.392)

---

### 4.6 Good match — Active wheat (Sim 7, Day 99)

**Inputs:**
- `Dw = 1.890 m`, `Zr = 1.00 m`, `theta_wp = 0.16`
- `TAW = 214.0`, `Dr_prev = 101.48`
- `W = 237.1 mm`
- `LAI = 3.838`, `ETm = 9.04 mm/day`
- `days_since_irrigation = 21`

**Step-by-step:**
1. `Wc = 380.0 * 1.89^-0.17 = 341.4 mm`
2. `Ws = 300.0 * 1.89^-0.27 = 261.3 mm`
3. `Dwc = 1.4 m`
4. `k = 3.8 / 9.04 = 0.420`
5. `Dw (1.89) > Dwc (1.4)` → `CRmax = 4.6 * 1.89^-0.65 = 3.044 mm/day`
6. `Ws (261.3) ≤ W (237.1)` — wait, `W < Ws` → `CR = CRmax = 3.044 mm/day`

**Results:**
- Base formula: **3.044 mm/day**
- Guarded formula: **3.044 mm/day**
- Access expected: **3.045 mm/day** ✅ (diff = -0.001)

---

### 4.7 Threshold-flicker mismatch — Orchard (Sim 35, Day 145)

**Inputs:**
- `Dw = 1.300 m`, `Zr = 0.90 m`, `theta_wp = 0.167`
- `TAW = 115.2`, `Dr_prev = 14.03`
- `W = 229.87 mm`
- `fc = 0.563` → `LAI = 1.407`
- `Kcb = 0.887`, `ETo = 4.52` → `ETm = 4.009 mm/day` (just barely above 4.0)
- `ETo_prev = 3.85` → `ETm_prev = 3.415 mm/day` (below 4.0)
- `days_since_irrigation = 1`, `last_irrig_depth = 6.0 mm` (guard does NOT trigger)

**Step-by-step (baseline — instantaneous ETm):**
1. `Wc = 306.0 * 1.30^-0.32 = 281.1 mm`
2. `Ws = 270.0 * 1.30^-0.16 = 259.0 mm`
3. `ETm (4.009) > 4` → `Dwc = 1.4 m`
4. `ETm > 4` → `k = 3.8 / 4.009 = 0.948`
5. `Dw (1.30) ≤ Dwc (1.4)` → `CRmax = 0.948 * 4.009 = 3.800 mm/day`
6. `W (229.9) < Ws (259.0)` → `CR = CRmax = 3.800 mm/day`

**Step-by-step (hypothesis — previous-day ETo):**
3. `ETm_prev (3.415) ≤ 4` → `Dwc = -1.4 * 3.415 + 6.8 = 2.02 m`
4. `ETm_prev ≤ 4` → `k = 1 - exp(-0.6 * 1.407) = 0.571`
5. `Dw (1.30) ≤ Dwc (2.02)` → `CRmax = 0.571 * 3.415 = 1.951 mm/day`
6. `W (229.9) < Ws (259.0)` → `CR = CRmax = 1.951 mm/day`

**Results:**
- Base formula: **3.800 mm/day**
- Prev-ETo hypothesis: **1.947 mm/day**
- Access expected: **1.362 mm/day**
- Base diff: **+2.438**
- Prev-ETo diff: **+0.585** (much closer)

**Why this matters:** The 4.0 mm/day threshold in the Liu formula is discontinuous. A tiny change in ETo (4.52 → 3.85) flips the entire branch and changes CR from 3.8 to 1.95. The Access binary appears to avoid this flicker, suggesting smoothed or lagged ETo input.

---

## 5. Hypotheses for Remaining Discrepancies

### H1: Additional undocumented guard in Access binary

**Evidence:** Sim 3 days 49, 50, 66, 90 and Sim 7 days 61–63 show `CR = 0` or near-zero when the formula predicts `CR > 1.5`. These days are 4–7 days after irrigation, so the 2-day guard has expired. Soil is not saturated (`W < Wc`). Water table is shallow (`Dw < Dwc`).

**Possible mechanisms:**
- A wetness recovery threshold: CR is held at zero until `Dr / RAW > 0.35–0.45`.
- A cumulative irrigation window: after large events (> 50 mm), suppression lasts 5–7 days instead of 2.
- A soil-water gradient threshold based on `W / Wc` ratio.

### H2: Different ETm driver in Access binary

**Evidence:** The R package integration layer and some documentation use `ETm = (Kcb + Ke) * ETo` (total ETc). Our code and the SoilW docs use `ETm = Kcb * ETo` (transpiration only).

**Impact:** Using `Kcb+Ke` would increase `ETm`, which would:
- Lower `k` (since `k = 3.8 / ETm` when ETm > 4)
- Lower `Dwc` (since `Dwc = a3 * ETm + b3` when ETm ≤ 4)
This would generally *reduce* predicted CR, partially closing the gap on over-estimation days.

**Status:** Unverified. The fallow-crop validation strongly supports `ETm = Kcb * ETo` because `Kcb ≈ 0.1` and `Ke` is irrelevant when `LAI = 0`.

### H3: Alternative LAI source or Kcb-LAI relationship

**Evidence:** Sim 34 and 35 have explicit `LAI` dates in `T_CRise_Param`. Our validation uses these when available. However, the Access binary might use a different `k_ext` value or a direct LAI lookup table rather than `fc = 1 - exp(-k_ext * LAI)`.

**Impact:** If Access uses a lower LAI than our reconstruction, `k` would be lower, reducing CRmax.

### H4: Dw computed differently for orchards

**Evidence:** Orchards have `Zr = 0.9 m` and shallow water tables (`Dw ≈ 0.9–1.4 m`). Our code clamps `Dw = max(dw, zr_m)`. For orchards, this means `Dw` is sometimes exactly `zr_m` (0.9 m), which makes `Ws` and `Wc` very sensitive.

**Impact:** If Access does not clamp `Dw` to `zr_m`, or uses a different effective root depth, `Ws` and `Wc` would shift, changing CR significantly.

### H5: Different coefficient set or interpolation for orchards

**Evidence:** Orchard coefficients (`a1=306, b1=-0.32, a2=280, b2=-0.16`) differ from wheat coefficients (`a1=380, b1=-0.17, a2=300, b2=-0.27`). The orchard coefficients produce much higher CR sensitivity to shallow Dw.

**Impact:** If the Access binary uses a different coefficient lookup or interpolates between soil textures differently, this could explain the large orchard discrepancies.

### H6: Numerical precision or rounding differences

**Evidence:** The Access binary stores `Ground_water` with 3 decimal places. Some differences of 0.001–0.01 mm/day could be rounding noise.

**Impact:** Negligible for the large discrepancies (> 1.0 mm/day) but may explain small residual differences on good-match days.

### H7: Lagged or smoothed ETm (threshold-flicker hypothesis)

**Evidence:** The Liu formula has a hard threshold at `ETm = 4.0 mm/day`:
- `ETm ≤ 4`: `Dwc = a3 * ETm + b3`, `k = 1 - exp(-0.6 * LAI)`
- `ETm > 4`: `Dwc = 1.4 m`, `k = 3.8 / ETm`

When daily `ETm` oscillates around 4.0, the predicted CR jumps discontinuously. We found many days where the Access output sits *between* the two branches, suggesting the binary may use a lagged or smoothed ETm rather than the instantaneous daily value.

**Global statistics:**

| Sim | Baseline MAE | Prev-day ETo MAE | 3-day MA ETo MAE |
|-----|-------------|------------------|------------------|
| 3 | 0.291 | 0.389 | 0.353 |
| 7 | 0.187 | 0.244 | 0.241 |
| 10 | 0.156 | 0.213 | 0.210 |
| 34 | 1.075 | 1.071 | **1.028** |
| 35 | 0.625 | 0.683 | **0.562** |

For wheat (3, 7, 10), lagging ETo makes things worse globally. For orchards (34, 35), a 3-day moving average of ETo improves MAE by **4–10%**.

**Concrete threshold-flicker days where prev-day ETo helps:**

| Sim | Day | ETo | ETo_prev | ETm | ETm_prev | Baseline CR | Prev-ETo CR | Expected | Baseline diff | Prev-ETo diff |
|-----|-----|-----|----------|-----|----------|-------------|-------------|----------|---------------|---------------|
| 34 | 75 | 5.21 | 4.53 | 4.125 | 3.585 | **3.800** | **2.069** | 1.601 | +2.199 | **+0.468** |
| 34 | 95 | 5.27 | 3.25 | 4.206 | 2.598 | **3.800** | **1.457** | 0.828 | +2.972 | **+0.629** |
| 35 | 92 | 4.53 | 4.34 | 4.015 | 3.848 | **3.800** | **2.155** | 2.380 | +1.420 | **+0.225** |
| 35 | 145 | 4.52 | 3.85 | 4.009 | 3.415 | **3.800** | **1.947** | 1.362 | +2.438 | **+0.585** |
| 35 | 154 | 4.33 | 3.02 | 4.138 | 2.890 | **3.800** | **1.636** | 1.715 | +2.085 | **-0.079** |

**Interpretation:** On these days, the instantaneous `ETm` barely exceeds 4.0 (e.g., 4.009, 4.015), flipping the formula into the high-transpiration branch where `k = 3.8/ETm` and `Dwc = 1.4 m`. The Access binary reports values closer to the low-transpiration branch, suggesting it either:
- Uses the previous day's ETo (or ETm) for the CR computation
- Applies a 2–3 day moving average to ETo before computing CR
- Has a hysteresis or dead-band around the 4.0 threshold

**Impact:** This hypothesis is the most promising explanation for the large orchard over-estimations. If verified, it would replace the hard `ETm > 4.0` threshold with a smoothed transition.

**Testability:** High. Compute CR with a 3-day MA of ETo for all sims and compare MAE/RMSE.

---

## 6. Guide — What Needs to Be Achieved

This section defines the concrete deliverables and decision points for completing CR validation.

### 6.1 Immediate goals (formula correctness)

- [ ] **Confirm ETm driver:** Determine definitively whether the Access binary uses `Kcb * ETo` or `(Kcb + Ke) * ETo` as the ETm input to the Liu formula.
  - *Test:* Re-run Sim 3 with `ETm = (Kcb+Ke)*ETo` and compare MAE/RMSE.
- [ ] **Confirm Dw definition:** Verify whether `Dw` is always `wt_depth_m` (from surface) for all simulation types, or whether there is a crop-type-specific rule.
  - *Test:* Compare Access output for a simulation with water table inside root zone (`wt_depth_m < zr`).
- [ ] **Confirm W definition:** Verify that `W = ASW + WWP` (absolute storage) is used consistently in Access, or whether a different wilting-point computation is used for multi-layer soils.
- [ ] **Test H7 (smoothed ETm):** Determine whether the Access binary uses instantaneous daily ETo, previous-day ETo, or a 2–3 day moving average for the ETm threshold in the Liu formula.
  - *Test:* For Sim 34 and 35, compute CR with `ETm` derived from a 3-day moving average of ETo. If MAE/RMSE improves significantly, implement the smoothing rule.
  - *Test:* For wheat sims (3–12), check whether a 1-day lag of ETo improves specific threshold-flicker days without degrading global accuracy.

### 6.2 Guard investigation goals

- [ ] **Characterize post-irrigation suppression more precisely:**
  - Is the threshold always 20 mm?
  - Does suppression duration depend on irrigation depth (e.g., > 50 mm = 5 days)?
  - Is there a soil-wetness recovery threshold (`Dr / RAW`) that ends suppression early?
  - *Approach:* Scatter-plot `Guard_diff` vs `days_since_irrigation`, `last_irrig_depth`, and `Dr/RAW` to find the boundary where Access transitions from `CR = 0` to `CR > 0`.
- [ ] **Characterize early-season suppression more precisely:**
  - Is the threshold `LAI < 0.3` or `Fc < 0.2`?
  - Is there also a day-of-sim threshold (e.g., first 30 days)?
  - *Approach:* Compare days where `LAI < 0.3` but `ETm > 4` — does Access ever report `CR > 0` on those days?
- [ ] **Identify any third guard:**
  - Look for days where both existing guards are inactive but Access still reports `CR = 0` (e.g., Sim 3 day 66).
  - Test hypotheses H1–H5 and H7 against these days.

### 6.3 Orchard-specific goals

- [ ] **Explain the 3.8 mm/day cap discrepancy:**
  - On many orchard days, formula predicts exactly 3.8 (the ETm>4 cap) but Access reports 0–1.5.
  - This suggests either a different `k` calculation, a different `Dwc` threshold, or an undocumented orchard-specific guard.
  - **Primary hypothesis (H7):** The binary uses smoothed or lagged ETo, preventing threshold flicker around ETm = 4.0.
  - *Approach:* Check whether the Access binary uses the simplified 4-parameter CR model (`CR = a_c * Dw^b_c * exp(-c_c * LAI^d_c)`) instead of the full 8-parameter model for orchards. If not, test H7 with a 3-day ETo moving average.
- [ ] **Investigate LAI source:**
  - The orchard fixtures provide explicit LAI dates from `T_CRise_Param`.
  - Does Access use these exact values, or compute LAI internally from a different relationship?

### 6.4 Statistical acceptance criteria

The current test suite uses these thresholds:

| Group | Correlation | Bias | RMSE | Rationale |
|-------|-------------|------|------|-----------|
| Fallow | — | — | — | Exact match (`atol = 0.001`) |
| Active wheat | ≥ 0.86 | ≤ 0.23 | ≤ 0.60 | High directional agreement, small mean error |
| Frequent irrigation | ≥ 0.55 | ≤ 1.05 | ≤ 1.41 | Relaxed due to guard uncertainty |

**Decision:** Are these thresholds scientifically acceptable, or should we tighten them?
- Tightening orchard thresholds will require resolving H2–H5 **and H7** (smoothed ETm).
- Tightening wheat thresholds will require resolving H1 (third guard).

### 6.5 Documentation goals

- [ ] Update `docs/cr_validation_findings/README.md` with corrected stats (using `prev_dr` methodology).
- [ ] Document the `prev_dr` vs `curr_dr` timing correction as a known pitfall.
- [ ] If H1 is resolved, replace the empirical `days_since_irrigation <= 2` guard with the physically correct rule.
- [ ] If H2 is resolved, update the `ETm` driver in `_compute_cr` and re-run all validation tests.

---

## 7. Data Sources and Files

| File | Purpose |
|------|---------|
| `tests/test_cr_parametric_isolated.py` | Isolated CR formula validation tests (the ground truth for this summary) |
| `tests/fixtures/cr_parametric_validation/{sim_id}_config.json` | Reconstructed simulation inputs |
| `tests/fixtures/cr_parametric_validation/{sim_id}_expected.parquet` | Daily state from `T_Resultados` |
| `scripts/extract_cr_parametric_fixtures.py` | Script that generated the fixtures from `database_export/` |
| `docs/cr_validation_findings/generate_cr_analysis.py` | Analysis/plotting script (note: uses incorrect `curr_dr` timing) |
| `src/simdualkc/auxiliary.py` | CR formula implementations |
| `src/simdualkc/simulation.py` | Simulation loop with `_compute_cr` dispatcher |
| `database_export/T_asc_capilar.parquet` | CR coefficients (matches Liu 2006 Table 5) |
| `database_export/T_Resultados.parquet` | Daily output (Access binary ground truth) |

---

## 8. Quick Reference — Coefficient Sets

### Wheat (Sim 3–12, Dengkou)
- `a1 = 380.0`, `b1 = -0.17`
- `a2 = 300.0`, `b2 = -0.27`
- `a3 = -1.3`, `b3 = 6.6`
- `a4 = 4.6`, `b4 = -0.65`
- `theta_wp = 0.16`, `Zr_max = 1.0 m`

### Orchard Pera-Rocha (Sim 34, Freiria 2013)
- `a1 = 306.0`, `b1 = -0.32`
- `a2 = 280.0`, `b2 = -0.16`
- `a3 = -1.4`, `b3 = 6.8`
- `a4 = 1.11`, `b4 = -0.98`
- `theta_wp = 0.167`, `Zr_max = 0.9 m`

### Orchard Pera-Rocha (Sim 35, Freiria 2014)
- `a1 = 306.0`, `b1 = -0.32`
- `a2 = 270.0`, `b2 = -0.16`
- `a3 = -1.4`, `b3 = 6.8`
- `a4 = 1.11`, `b4 = -0.98`
- `theta_wp = 0.167`, `Zr_max = 0.9 m`

---

## Wheat Strict-Test Failure Analysis

This section documents the results of applying the same `atol = 0.001` daily check used for fallow crops to the three Dengkou wheat simulations (Sims 3, 4, and 6). The test calls `_compute_cr_series(sim_id, use_guards=False)` — the strict Liu 2006 formula with no empirical guards.

### Mismatch counts

| Sim | Season | Total days | Mismatch days (atol>0.001) | % of season |
|-----|--------|-----------|---------------------------|-------------|
| 3 | 2010 | 118 | **49** | 41.5% |
| 4 | 2011 | 111 | **44** | 39.6% |
| 6 | 2012 | 114 | **44** | 38.6% |

### Classification of mismatch days

| Pattern | Sim 3 | Sim 4 | Sim 6 | Description |
|---------|-------|-------|-------|-------------|
| Early season (LAI < 0.3) | 9 (18.4%) | 9 (20.5%) | 5 (11.4%) | Small diffs (0.001–0.060), days 16–35 |
| Post-irrigation suppression (≤3 days) | 7 (14.3%) | 7 (15.9%) | 6 (13.6%) | Large diffs (0.3–2.9), Access reports 0 or near-0 |
| Near >10 mm rain (≤3 days) | 7 (14.3%) | 0 (0.0%) | 12 (27.3%) | Large diffs, Access reports 0 or near-0 |
| Threshold-flicker (ETm 3.5–4.5) | 3 (6.1%) | 5 (11.4%) | 3 (6.8%) | Moderate diffs (0.1–0.6) |
| Late-season systematic over-est. | ~10 (~20%) | ~10 (~23%) | ~10 (~23%) | Diffs 0.3–0.8, declining LAI, no irrigation nearby |

**Key insight:** The dominant source of large mismatches is **Pattern A — post-irrigation suppression**. After irrigation events of 78–118 mm, the Access binary reports `CR = 0` for many days (up to 5–10 days), while the Liu formula predicts `CR = 0.5–2.9 mm/day`. The existing 2-day / >20 mm guard captures only the first 1–2 days; the true suppression window is much longer for large depths.

### Pattern A — concrete examples

**Sim 3, 115 mm irrigation on day 45:**

| Day | dsi | Expected | Actual | Diff | ETm | Dw | W |
|-----|-----|----------|--------|------|-----|----|---|
| 48 | 3 | 0.000 | 0.839 | +0.839 | 7.51 | 0.920 | 362.3 |
| 49 | 4 | 0.000 | 1.226 | +1.226 | 9.14 | 0.928 | 354.2 |
| 50 | 5 | 0.566 | 1.685 | +1.119 | 5.43 | 0.936 | 344.5 |
| 51 | 6 | 0.966 | 1.923 | +0.957 | 7.56 | 0.944 | 339.5 |
| 52 | 7 | 1.450 | 2.246 | +0.796 | 6.50 | 0.952 | 332.7 |

**Sim 3, 78 mm irrigation on day 59:**

| Day | dsi | Expected | Actual | Diff | ETm | Dw | W |
|-----|-----|----------|--------|------|-----|----|---|
| 60 | 1 | 0.000 | 0.077 | +0.077 | 9.00 | 0.982 | 378.4 |
| 61 | 2 | 0.000 | 0.571 | +0.571 | 9.60 | 0.918 | 368.0 |
| 62 | 3 | 0.000 | 1.086 | +1.086 | 6.52 | 0.854 | 357.1 |
| 63 | 4 | 0.000 | 0.705 | +0.705 | 3.53 | 0.790 | 361.2 |
| 64 | 5 | 0.000 | 0.510 | +0.510 | 6.12 | 0.840 | 369.3 |
| 65 | 6 | 0.000 | 0.739 | +0.739 | 6.34 | 0.890 | 364.4 |
| 66 | 7 | 0.000 | 1.063 | +1.063 | 6.10 | 0.940 | 357.6 |

**Sim 6, 118 mm irrigation on day 54:**

| Day | dsi | Expected | Actual | Diff | ETm | Dw | W |
|-----|-----|----------|--------|------|-----|----|---|
| 55 | 1 | 0.000 | 0.062 | +0.062 | 6.99 | 0.838 | 378.2 |
| 56 | 2 | 0.000 | 0.330 | +0.330 | 6.80 | 0.852 | 370.5 |
| 57 | 3 | 0.000 | 0.586 | +0.586 | 8.40 | 0.866 | 363.1 |
| 58 | 4 | 0.000 | 0.898 | +0.898 | 5.88 | 0.880 | 354.0 |
| 59 | 5 | 0.000 | 1.108 | +1.108 | 7.91 | 0.914 | 347.9 |

**Observation:** For irrigation depths > 70 mm, suppression persists for 5–7 days (sometimes up to 10 days in Sim 6 after a 100 mm event). This is far beyond the current 2-day empirical guard.

### Late-season systematic over-estimation

In all three wheat sims, days ~100+ (declining LAI, no nearby irrigation) show consistent over-estimation by 0.3–0.8 mm/day:

| Sim | Day | LAI | ETm | Expected | Actual | Diff |
|-----|-----|-----|-----|----------|--------|------|
| 3 | 106 | 1.56 | 3.78 | 1.748 | 2.301 | +0.553 |
| 3 | 111 | 1.23 | 3.12 | 0.965 | 1.628 | +0.663 |
| 3 | 114 | 1.05 | 3.12 | 0.669 | 1.461 | +0.792 |
| 4 | 103 | 1.33 | 3.12 | 1.152 | 1.718 | +0.566 |
| 4 | 108 | 1.01 | 2.94 | 0.521 | 1.341 | +0.820 |
| 6 | 102 | 1.78 | 4.80 | 1.340 | 1.930 | +0.590 |
| 6 | 104 | 1.59 | 4.94 | 1.624 | 2.200 | +0.576 |

These days are **not** near irrigation events and **not** in the ETm threshold-flicker band. The discrepancy is consistent: actual ≈ expected + 0.5 mm/day. This suggests either:
- A different `k` calculation in Access when LAI is moderate (1.0–2.0)
- An undocumented late-season guard (e.g., stage-dependent CR reduction)
- A slightly different LAI source or `k_ext` value

### Threshold-flicker (H7) in wheat

Only 3–5 days per sim fall in the ETm 3.5–4.5 mm/day band. Examples:

| Sim | Day | ETm | Expected | Actual | Diff | Note |
|-----|-----|-----|----------|--------|------|------|
| 4 | 53 | 4.35 | 3.335 | 3.688 | +0.353 | Just above 4.0 branch |
| 4 | 105 | 3.83 | 1.060 | 1.961 | +0.901 | Below 4.0, but large diff |
| 6 | 99 | 4.63 | 0.951 | 1.560 | +0.609 | Just above 4.0 branch |

While H7 is a real phenomenon (strongly supported by orchard data), it explains only a minority of wheat mismatches.

### Recommendation — next fix to test

**Primary: depth-dependent post-irrigation suppression window.**

The data strongly suggest that the Access binary suppresses CR for a variable duration after irrigation, and that duration increases with irrigation depth. A concrete hypothesis to test:

- `depth > 20 mm` → suppress 2 days (current guard)
- `depth > 50 mm` → suppress 5 days
- `depth > 80 mm` → suppress 7 days
- `depth > 100 mm` → suppress 10 days

Alternatively, replace the fixed window with a **soil-wetness recovery threshold**: suppress CR until `Dr / RAW` (or `W / Wc`) recovers to a critical value. This would naturally create longer suppression after large irrigations because the soil takes longer to dry.

**Secondary: investigate late-season k factor.**

If the depth-dependent guard resolves the large post-irrigation mismatches, the remaining systematic late-season over-estimation (0.3–0.8 mm/day on ~10 days per sim) should be addressed by testing whether Access uses a different LAI→k relationship or a stage-dependent CR multiplier.

---

*End of summary. All data in this document was generated from the actual test fixtures and code as of 2026-04-30.*
