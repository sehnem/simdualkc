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

### Parametric Method (Liu et al., 2006)

$$CR = (a_1 \cdot z_{wt}^{b_1} + a_2 \cdot z_{wt}^{b_2}) \cdot \exp(-(a_3 \cdot z_{wt}^{b_3} + a_4 \cdot z_{wt}^{b_4}) \cdot LAI)$$

where $z_{wt}$ is the water table depth from the surface [m] and coefficients depend on soil texture.

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
- `compute_cr_parametric_complete(z_wt, lai, a1..b4)` — full parametric CR
