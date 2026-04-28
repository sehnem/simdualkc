# Soil Evaporation (Ke)

The model uses a **two-fraction evaporation approach** separating soil wetted by irrigation from soil wetted only by precipitation.

## Evaporative Fractions

The exposed (uncovered) soil surface is split:

$$fewi = \min(f_{eff,exposed}, f_w)$$
$$fewp = f_{eff,exposed} - fewi$$

where $f_{eff,exposed} = (1 - f_c) - f_{mulch} \cdot (1 - K_{r,mulch})$ accounts for mulch reduction.

## Evaporation Reduction Coefficient (Kr)

$$K_r = \frac{TEW - D_e}{TEW - REW} \quad \text{clipped to } [0, 1]$$

- When $D_e \le REW$: Stage-1 evaporation, $K_r = 1$ (energy-limited)
- When $D_e > REW$: Stage-2 evaporation, $K_r < 1$ (soil-limited)

## Energy Partitioning Weight (W)

$$W = \frac{1}{1 + \frac{fewp \cdot (TEW - D_{e,p})}{fewi \cdot (TEW - D_{e,i})}}$$

When $fewi = 0$ (no irrigation), $W = 0$ and all energy goes to the precip-only fraction.

## Ke Computation

$$K_{e,i} = K_{r,i} \cdot W \cdot (K_{c,max} - K_{cb}) \quad \le fewi \cdot K_{c,max}$$
$$K_{e,p} = K_{r,p} \cdot (1-W) \cdot (K_{c,max} - K_{cb}) \quad \le fewp \cdot K_{c,max}$$
$$K_e = K_{e,i} + K_{e,p}$$

## Kc_max (Upper Bound)

$$K_{c,max} = \max\left(1.2 + [0.04(u_2-2) - 0.004(RH_{min}-45)](h/3)^{0.3}, \; K_{cb} + 0.05\right)$$

## Evaporative Layer Balance

For the **irrigated fraction**:

$$D_{e,i,j} = D_{e,i,j-1} - (P - RO) - \frac{I}{f_w} + \frac{E_i}{fewi} + DP_{e,i}$$

For the **precipitation-only fraction**:

$$D_{e,p,j} = D_{e,p,j-1} - (P - RO) + \frac{E_p}{fewp} + DP_{e,p}$$

Deep percolation from the evaporative layer occurs when depletion goes negative (excess water).

## Module: `evaporation.py`

Key functions:

- `compute_few(fc, fw, f_mulch, kr_mulch)` — evaporative fractions (fewi, fewp)
- `compute_kc_max(kcb, u2, rh_min, h)` — upper bound for Kc
- `compute_evaporation_weight(fewi, fewp, tew, dei, dep)` — energy partitioning weight W
- `compute_kr(tew, rew, de_prev)` — evaporation reduction coefficient
- `compute_ke(kri, krp, w, kc_max, kcb, fewi, fewp)` — soil evaporation coefficients
- `update_evaporative_depletion(...)` — daily evaporative layer balance
