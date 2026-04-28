# Multi-layer Soil

The model supports up to 5 soil layers with different hydraulic properties. As root depth grows, TAW increases as deeper layers become active.

## Defining Multi-layer Soil

```python
from simdualkc.models import SoilParams, SoilLayer

soil = SoilParams(
    theta_fc=0.35,  # Default (overridden by layers for TAW)
    theta_wp=0.20,  # Default (overridden by layers for TAW)
    rew=8.0,
    tew=25.0,
    layers=[
        SoilLayer(depth_m=0.20, theta_fc=0.38, theta_wp=0.22),  # Topsoil
        SoilLayer(depth_m=0.50, theta_fc=0.35, theta_wp=0.20),  # Subsoil 1
        SoilLayer(depth_m=0.80, theta_fc=0.32, theta_wp=0.18),  # Subsoil 2
        SoilLayer(depth_m=1.20, theta_fc=0.30, theta_wp=0.16),  # Deep layer
    ],
)
```

## How It Works

Each `SoilLayer` specifies:

- `depth_m`: Bottom depth of the layer [m]
- `theta_fc`: Field capacity [m³/m³]
- `theta_wp`: Wilting point [m³/m³]

TAW is computed by integrating over the active root zone:

$$TAW = \sum_i 1000 \cdot (\theta_{FC,i} - \theta_{WP,i}) \cdot \Delta z_{i,active}$$

When root depth $Z_r = 0.3$ m, only the top 0.3 m contributes. When $Z_r = 1.0$ m, all four layers contribute (partially for the last one).

## Dynamic TAW

As the crop develops (stages 1–3), root depth grows from `zr_ini` to `zr_max`. The simulation automatically recomputes TAW each day based on the current root depth and the layer structure.

## Validation

- Layers must be ordered by increasing `depth_m`
- Maximum 5 layers
- `theta_wp < theta_fc` for each layer
