# ETo — FAO-56 Penman-Monteith

Reference evapotranspiration is computed using the standard FAO-56 equation:

$$ET_o = \frac{0.408 \Delta (R_n - G) + \gamma \frac{900}{T+273} u_2 (e_s - e_a)}{\Delta + \gamma(1 + 0.34 u_2)}$$

## Component Equations

### Saturation Vapor Pressure

$$e^{\circ}(T) = 0.6108 \cdot \exp\left(\frac{17.27 T}{T + 237.3}\right) \quad \text{[kPa]}$$

### Actual Vapor Pressure

$$e_a = \frac{e^{\circ}(T_{min}) \cdot RH_{max}/100 + e^{\circ}(T_{max}) \cdot RH_{min}/100}{2}$$

### Slope of Saturation Vapor Pressure Curve

$$\Delta = \frac{4098 \cdot e^{\circ}(T)}{(T + 237.3)^2} \quad \text{[kPa/°C]}$$

### Psychrometric Constant

$$\gamma = 0.000665 \cdot P$$

where atmospheric pressure $P$ is derived from elevation:

$$P = 101.3 \cdot \left(\frac{293 - 0.0065 z}{293}\right)^{5.26} \quad \text{[kPa]}$$

### Extraterrestrial Radiation

$$R_a = \frac{24 \times 60}{\pi} G_{sc} d_r [\omega_s \sin\varphi \sin\delta + \cos\varphi \cos\delta \sin\omega_s]$$

### Net Radiation

$$R_n = R_{ns} - R_{nl}$$

where $R_{ns} = (1 - \alpha) R_s$ (albedo = 0.23 for grass reference) and $R_{nl}$ is net outgoing longwave radiation (FAO-56 Eq. 39).

## Soil Heat Flux

For daily time steps: $G = 0$ (FAO-56 standard assumption).

## Module: `eto.py`

Key functions:

- `compute_eto(t_max, t_min, rh_max, rh_min, rs, u2, latitude, elevation, date)` — full ETo computation
- `weather_to_climate_records(weather, latitude, elevation)` — batch conversion from raw weather to `ClimateRecord` list
- `compute_saturation_vapor_pressure(t)` — $e^{\circ}(T)$
- `compute_actual_vapor_pressure(t_max, t_min, rh_max, rh_min)` — $e_a$
- `compute_slope_vapor_pressure_curve(t)` — $\Delta$
- `compute_psychrometric_constant(elevation)` — $\gamma$
- `compute_extraterrestrial_radiation(latitude, day_of_year)` — $R_a$
- `compute_net_radiation(rs, t_max, t_min, ea, latitude, day_of_year, elevation)` — $R_n$
