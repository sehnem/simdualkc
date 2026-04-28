# Yield Model — Stewart Water-Yield

The Stewart model relates transpiration deficit to yield loss:

$$Y_a = Y_m \left(1 - K_y \left(1 - \frac{T_{act}}{T_{pot}}\right)\right)$$

where:

| Symbol | Meaning | Units |
|---|---|---|
| $Y_a$ | Actual yield | kg/ha |
| $Y_m$ | Maximum expected yield | kg/ha |
| $K_y$ | Yield response factor | — |
| $T_{act}$ | Seasonal actual transpiration | mm |
| $T_{pot}$ | Seasonal potential transpiration ($K_s = 1$) | mm |

## Yield Decrease

$$\text{Yield decrease [\%]} = K_y \cdot \left(1 - \frac{T_{act}}{T_{pot}}\right) \times 100$$

## Combined Water + Salinity Stress

When salinity stress is present, total yield decrease combines both:

$$\text{Total decrease} = \text{Water decrease} + \text{Salinity decrease}$$

capped at 100%.

## Module: `yield_model.py`

- `compute_yield_decrease_transpiration(t_act_sum, t_pot_sum, k_y, y_m)` — returns `(y_a, decrease_pct)`
