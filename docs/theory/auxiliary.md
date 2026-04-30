# Auxiliary Fluxes

## Surface Runoff (SCS Curve Number)

$$q = \frac{(P - 0.2S)^2}{P + 0.8S} \quad \text{where } S = \frac{25400}{CN} - 254$$

No runoff occurs when $P \le 0.2S$ (initial abstraction threshold).

### Moisture-adjusted CN

The base CN₂ (AMC II) is adjusted for surface soil moisture:

$$CN_{adj} = CN_I + w \cdot (CN_{III} - CN_I)$$

where $w = 1 - D_{e,i}/TEW$ (wetness fraction from evaporative depletion).

CN for dry (AMC I) and wet (AMC III) conditions:

$$CN_I = \frac{CN_{II}}{2.281 - 0.01281 \cdot CN_{II}}$$
$$CN_{III} = \frac{CN_{II}}{0.427 + 0.00573 \cdot CN_{II}}$$

## Capillary Rise

### Constant Method

$$CR = \begin{cases} G_{max} & D_r \ge RAW \\ G_{max} \cdot D_r / RAW & 0 < D_r < RAW \\ 0 & D_r \le 0 \end{cases}$$

### Full 8-parameter Method (Liu et al., 2006)

Six-step piecewise algorithm where $D_w$ is water table depth [m], $W$ is absolute root-zone
soil water storage [mm] (ASW + WWP), $ET_m = K_{cb} \cdot ET_0$ [mm/day], and coefficients
depend on soil texture:

1. $W_c = a_1 \cdot D_w^{b_1}$ — critical soil water storage [mm]
2. $W_s = a_2 \cdot D_w^{b_2}$ ($D_w \le 3$ m) or $3.57 \cdot D_w^{-0.705}$ ($D_w > 3$ m) — steady storage [mm]
3. $D_{wc} = a_3 \cdot ET_m + b_3$ if $ET_m \le 4$ else $1.4$ m — critical water-table depth [m]
4. $k = 1 - e^{-0.6\,LAI}$ if $ET_m \le 4$ else $3.8 / ET_m$ — transpiration factor
5. $CR_{max} = \min(k \cdot ET_m,\;3.8)$ if $D_w \le D_{wc}$, else $a_4 \cdot D_w^{b_4}$ — potential flux [mm/day]
6. $CR = CR_{max}$ if $W < W_s$; $\;CR_{max}(W_c - W)/(W_c - W_s)$ if $W_s \le W \le W_c$; $\;0$ if $W > W_c$

Coefficients $a_1, b_1$ (Wc), $a_2, b_2$ (Ws), $a_3, b_3$ (Dwc linear slope/intercept), and
$a_4, b_4$ (deep-zone CRmax) are read from the soil database (`T_asc_capilar`).

> **CR-specific field capacity (`cr_theta_fc`).**  The Liu et al. coefficients were calibrated
> using the soil's `teor_fc` from `T_asc_capilar`, which may differ from the general `theta_fc`
> used in the water-balance simulation.  When `soil.cr_theta_fc` is set, $W$ is computed as
> $W = \theta_{fc,CR} \cdot Z_r \cdot 1000 - D_r$ rather than deriving it from TAW and WWP.
> This eliminates a systematic bias caused by the wilting-point difference between the two
> parameter sources ($\theta_{wp,CR}$ vs $\theta_{wp,sim}$).

## Deep Percolation

### Simple Method

Excess water beyond field capacity drains instantly:

$$DP = \max(0, -D_r)$$

### Parametric Method (Liu et al., 2006)

$$DP = a_D \cdot Storage^{b_D}$$

## Module: `auxiliary.py`

Key functions:

- `compute_runoff_cn(precip, cn)` — SCS Curve Number runoff
- `adjust_cn_for_moisture(cn2, dei, tew)` — moisture-adjusted CN
- `cn_from_amc(cn2, amc_class)` — CN conversion between AMC classes
- `compute_dp_simple(dr_before_dp)` — simple deep percolation
- `compute_dp_parametric(storage, a_d, b_d)` — parametric DP
- `compute_cr_constant(gmax, dr, raw)` — constant capillary rise
- `compute_cr_parametric_complete(dw, w, lai, etm, a1..b4, zr_m=0.0)` — full parametric CR (Liu et al. 2006) with root-zone clipping and Dw>3m fallback; caller must pass $W$ computed with `cr_theta_fc` when available
