# Salinity & Yield

## Salinity Stress

When soil salinity exceeds the crop tolerance threshold, transpiration is reduced via the Mass-Hoffman model:

```python
from simdualkc.models import SalinityParams

salinity = SalinityParams(
    ec_e=6.0,           # Soil salinity ECe [dS/m]
    ec_threshold=2.0,   # Crop threshold [dS/m]
    b=12.0,             # Yield loss slope [% per dS/m]
    k_y=1.0,            # Yield response factor
)

config = SimulationConfig(
    soil=soil, crop=crop, climate=climate,
    initial_conditions=ic,
    salinity=salinity,
)
```

The salinity stress coefficient:

$$K_{s,salinity} = 1 - \frac{b}{100 \cdot K_y} \cdot (EC_e - EC_{threshold})$$

Combined with water stress: $K_s = K_{s,water} \cdot K_{s,salinity}$

## Yield Estimation

The Stewart water-yield model estimates yield loss from seasonal transpiration deficit:

```python
from simdualkc.models import YieldParams

yield_params = YieldParams(
    y_m=12000.0,   # Maximum expected yield [kg/ha]
    k_y=1.05,      # Yield response factor
)

config = SimulationConfig(
    soil=soil, crop=crop, climate=climate,
    initial_conditions=ic,
    yield_params=yield_params,
)

result = run_simulation(config)
print(f"Actual yield: {result.yield_act:.0f} kg/ha")
print(f"Yield decrease: {result.yield_decrease_pct:.1f}%")
```

## Yield + Salinity Combined

When both `yield_params` and `salinity` are provided, the summary reports separate water and salinity yield decreases:

```python
result = run_simulation(config)
summary = result.summary.stress
print(f"Water stress yield decrease: {summary.yield_decrease_water_pct:.1f}%")
print(f"Salinity yield decrease:     {summary.yield_decrease_salinity_pct:.1f}%")
print(f"Total yield decrease:        {summary.yield_decrease_total_pct:.1f}%")
```

## Typical Ky Values

| Crop | Ky |
|---|---|
| Alfalfa | 0.90 |
| Maize | 1.25 |
| Tomato | 1.05 |
| Wheat | 1.15 |
| Potato | 1.10 |
