# Water Balance & Stress

## Total Available Water (TAW)

Single layer:

$$TAW = 1000 \cdot (\theta_{FC} - \theta_{WP}) \cdot Z_r \quad \text{[mm]}$$

Multi-layer (up to 5 layers):

$$TAW = \sum_i 1000 \cdot (\theta_{FC,i} - \theta_{WP,i}) \cdot \Delta z_{i,active}$$

where $\Delta z_{i,active}$ is the portion of layer $i$ within the current root depth $Z_r$.

## Readily Available Water (RAW)

$$RAW = p \cdot TAW$$

where $p$ is the depletion fraction for no stress (crop-specific, typically 0.4–0.6).

## Water Stress Coefficient (Ks)

$$K_s = \begin{cases} 1 & D_r \le RAW \\ \frac{TAW - D_r}{(1-p) \cdot TAW} & RAW < D_r < TAW \\ 0 & D_r \ge TAW \end{cases}$$

## Salinity Stress (Mass-Hoffman)

When salinity exceeds the crop threshold:

$$K_{s,salinity} = 1 - \frac{b}{100 \cdot K_y} \cdot (EC_e - EC_{threshold})$$

Combined stress: $K_s = K_{s,water} \cdot K_{s,salinity}$

## Root Zone Depletion Update

$$D_{r,i} = D_{r,i-1} - (P - RO) - I - CR + ETc_{act} + DP$$

Deep percolation occurs when inputs push $D_r$ below zero (soil exceeds field capacity):

$$DP = \max(0, -D_r)$$
$$D_r = \max(0, \min(D_r, TAW))$$

## Parametric Deep Percolation (Liu et al., 2006)

$$DP = a_D \cdot Storage^{b_D}$$

where $Storage$ is the water above field capacity (negative $D_r$).

## Module: `water_balance.py`

Key functions:

- `compute_taw(theta_fc, theta_wp, zr)` — single-layer TAW
- `compute_taw_multilayer(layers, zr)` — multi-layer TAW
- `compute_raw(taw, p)` — readily available water
- `compute_ks(dr, taw, raw, p)` — water stress coefficient
- `compute_ks_salinity(ec_e, ec_threshold, b, k_y)` — salinity stress
- `compute_etc_act(ks, kcb, ke, eto)` — actual crop ET
- `update_root_zone_depletion(...)` — daily root zone balance
