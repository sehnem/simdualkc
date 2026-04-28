# Basal Crop Coefficient (Kcb)

The basal crop coefficient represents transpiration by the crop, excluding soil evaporation.

## Growth Stage Interpolation

Kcb is interpolated through four FAO-56 growth stages:

| Stage | Kcb | Duration |
|---|---|---|
| 1 — Initial | $K_{cb,ini}$ (constant) | `stage_lengths[0]` days |
| 2 — Development | linear: $K_{cb,ini} \to K_{cb,mid}$ | `stage_lengths[1]` days |
| 3 — Mid-season | $K_{cb,mid}$ (constant, climate-adjusted) | `stage_lengths[2]` days |
| 4 — Late season | linear: $K_{cb,mid} \to K_{cb,end}$ | `stage_lengths[3]` days |

## Climate Adjustment

Tabulated Kcb values assume RHmin = 45% and u2 = 2 m/s. For different conditions (applied when $K_{cb} > 0.45$):

$$K_{cb,adj} = K_{cb,tab} + [0.04(u_2 - 2) - 0.004(RH_{min} - 45)] \cdot (h/3)^{0.3}$$

## Density Adjustment

Partial canopy cover reduces Kcb via the density coefficient $K_d$:

$$K_{cb} = K_{c,min} + K_d \cdot (K_{cb,full} - K_{c,min})$$

where $K_d$ is the minimum of three estimates:

$$K_{d,ml} = m_l \cdot f_c$$
$$K_{d,exp} = f_c^{1/(1+h)}$$
$$K_d = \min(1, K_{d,ml}, K_{d,exp})$$

## LAI-based Fraction Cover

When LAI measurements are available, fraction cover is derived:

$$f_c = 1 - \exp(-K_{ext} \cdot LAI)$$

where $K_{ext}$ is the light extinction coefficient (0.5–0.7, default 0.6).

## Groundcover (Orchards/Vineyards)

When active groundcover is present, the combined Kcb follows FAO-56:

$$K_{cb} = K_{cb,cover} + K_d \cdot \max(K_{cb,full} - K_{cb,cover}, \frac{K_{cb,full} - K_{cb,cover}}{2})$$

## Module: `kcb.py`

Key functions:

- `interpolate_kcb(day_of_sim, crop, u2, rh_min)` — full Kcb interpolation with climate correction
- `compute_kcb_full(kcb_tab, u2, rh_min, h)` — climate-adjusted Kcb at full cover
- `compute_kd(fc, h, ml)` — density coefficient
- `compute_kcb_density(kc_min, kd, kcb_full)` — Kcb adjusted for partial canopy
- `compute_kcb_with_groundcover(kcb_full, kcb_cover, kd)` — combined orchard Kcb
- `get_fc(day_of_sim, crop)` — fraction cover (LAI-based or interpolated)
- `get_stage(day_of_sim, crop)` — current growth stage (1–4)
- `interpolate_growth_param(day_of_sim, crop, param)` — zr, h, fc, p interpolation
