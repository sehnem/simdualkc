# Model Overview

The SIMDualKc model computes daily actual crop evapotranspiration using the FAO-56 Dual Crop Coefficient approach:

$$ETc_{act} = (K_s \cdot K_{cb} + K_e) \cdot ET_o$$

## Daily Loop

Each simulation day follows this sequence:

1. **Interpolate growth parameters** — root depth $Z_r$, plant height $h$, fraction cover $f_c$, depletion fraction $p$ from crop stage lengths
2. **Compute Kcb** — basal crop coefficient adjusted for climate, density, and optional groundcover
3. **Determine irrigation** — from manual events and/or automated scheduling (MAD threshold)
4. **Compute Kc_max** — upper bound for the crop coefficient
5. **Compute evaporation fractions** — fewi (irrigated), fewp (precip-only), with optional mulch reduction
6. **Compute Kr and Ke** — evaporation reduction and soil evaporation coefficient for each fraction
7. **Surface balance** — runoff (Curve Number), evaporative layer depletion update
8. **Compute Ks** — water stress coefficient from root zone depletion (and optional salinity)
9. **Compute ETc_act** — actual evapotranspiration
10. **Capillary rise** — from groundwater (constant or parametric)
11. **Root zone balance** — update depletion, compute deep percolation
12. **Accumulate** — transpiration sums for yield model

## State Variables

The simulation maintains three depletion state variables that advance day-to-day:

| Variable | Meaning | Layer |
|---|---|---|
| $D_r$ | Root zone depletion [mm] | Full root depth |
| $D_{e,i}$ | Evaporative layer depletion (irrigated fraction) [mm] | Surface layer ($Z_e$) |
| $D_{e,p}$ | Evaporative layer depletion (precip-only fraction) [mm] | Surface layer ($Z_e$) |

All three are initialized from `InitialConditions` and updated each day.

## Two-Fraction Evaporation

The model splits the exposed soil surface into two fractions:

- **fewi**: soil wetted by irrigation *and* precipitation
- **fewp**: soil wetted by precipitation only

Energy partitioning between the fractions uses a weight $W$ based on their relative wetness:

$$W = \frac{1}{1 + \frac{fewp \cdot (TEW - D_{e,p})}{fewi \cdot (TEW - D_{e,i})}}$$

This prevents the drier fraction from "stealing" energy from the wetter one.
