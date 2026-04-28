# Groundcover & Orchards

In orchards and vineyards, inter-row vegetation (groundcover) affects the combined Kcb.

## Configuration

```python
from simdualkc.models import GroundcoverParams

groundcover = GroundcoverParams(
    kcb_cover=0.30,   # Kcb of the groundcover vegetation
    fc_cover=0.50,     # Fraction of ground covered by groundcover
    h_cover=0.15,      # Groundcover height [m]
)

config = SimulationConfig(
    soil=soil, crop=crop, climate=climate,
    initial_conditions=ic,
    groundcover=groundcover,
)
```

## Combined Kcb

When groundcover is active, the combined Kcb follows FAO-56:

$$K_{cb} = K_{cb,cover} + K_d \cdot \max(K_{cb,full} - K_{cb,cover}, \frac{K_{cb,full} - K_{cb,cover}}{2})$$

This accounts for the additional transpiration from the inter-row vegetation while the main crop (trees/vines) contributes through the density coefficient $K_d$.

## Typical Values

| Groundcover Type | kcb_cover | fc_cover | h_cover |
|---|---|---|---|
| Grass strip | 0.30 | 0.40 | 0.15 |
| Clover | 0.35 | 0.50 | 0.10 |
| Natural weeds | 0.25 | 0.30 | 0.20 |
