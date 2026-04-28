# ETo from Weather

When you have raw weather data (temperature, humidity, radiation, wind) instead of pre-computed ETo, use the FAO-56 Penman-Monteith calculator.

## Single Day

```python
import datetime
from simdualkc.eto import compute_eto

eto = compute_eto(
    t_max=32.0,       # Max temperature [°C]
    t_min=18.0,       # Min temperature [°C]
    rh_max=80.0,      # Max relative humidity [%]
    rh_min=35.0,      # Min relative humidity [%]
    rs=22.0,          # Solar radiation [MJ/m²/day]
    u2=2.5,           # Wind speed at 2 m [m/s]
    latitude=38.0,    # Site latitude [degrees]
    elevation=50.0,   # Site elevation [m]
    date=datetime.date(2024, 6, 15),
)
print(f"ETo = {eto:.2f} mm/day")
```

## Batch Conversion

```python
from simdualkc.eto import weather_to_climate_records
from simdualkc.models import WeatherRecord

weather = [
    WeatherRecord(
        date=datetime.date(2024, 3, 15),
        t_max=25.0, t_min=12.0,
        rh_max=75.0, rh_min=40.0,
        rs=18.0, u2=2.0,
        precip=0.0,
    ),
    # ... more days
]

climate = weather_to_climate_records(
    weather=weather,
    latitude=38.0,
    elevation=50.0,
)

# climate is a list of ClimateRecord ready for SimulationConfig
config = SimulationConfig(
    soil=soil, crop=crop, climate=climate,
    initial_conditions=ic,
)
```

## Component Functions

The `eto` module exposes all intermediate calculations for debugging or educational use:

| Function | Returns |
|---|---|
| `compute_saturation_vapor_pressure(t)` | $e^{\circ}(T)$ [kPa] |
| `compute_actual_vapor_pressure(...)` | $e_a$ [kPa] |
| `compute_slope_vapor_pressure_curve(t)` | $\Delta$ [kPa/°C] |
| `compute_psychrometric_constant(elevation)` | $\gamma$ [kPa/°C] |
| `compute_extraterrestrial_radiation(lat, doy)` | $R_a$ [MJ/m²/day] |
| `compute_net_radiation(...)` | $R_n$ [MJ/m²/day] |
