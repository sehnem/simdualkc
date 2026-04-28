# Automated Irrigation

The model supports two automated irrigation strategies triggered by soil water depletion.

## MAD Threshold Strategy

Irrigation is triggered when root zone depletion exceeds a fraction of TAW:

```python
from simdualkc.models import IrrigationStrategy, MADThresholdStrategy

strategy = IrrigationStrategy(
    strategy_type="mad_threshold",
    mad_threshold=MADThresholdStrategy(
        mad_fraction=0.55,           # Trigger at 55% TAW depletion
        target_pct_taw=100.0,        # Refill to 100% TAW (field capacity)
        days_before_harvest_stop=10, # Stop 10 days before harvest
        min_interval_days=5,         # Min 5 days between irrigations
    ),
)
```

### How It Works

1. Each day, the model checks if $D_r \ge MAD \times TAW$
2. If triggered, irrigation depth is computed: $I = D_r - TAW \times (1 - target\%/100)$
3. The irrigation is rejected if:
   - Days to harvest ≤ `days_before_harvest_stop`
   - Days since last irrigation < `min_interval_days`

## Deficit Irrigation Strategy

Stage-specific MAD allows controlled deficit (e.g., less water during development):

```python
from simdualkc.models import IrrigationStrategy, DeficitIrrigationStrategy

strategy = IrrigationStrategy(
    strategy_type="deficit",
    deficit=DeficitIrrigationStrategy(
        stage_mad={
            "ini": 0.50,   # 50% depletion allowed in initial stage
            "dev": 0.70,   # 70% — more stress during development
            "mid": 0.45,   # 45% — keep well-watered at mid-season
            "late": 0.60,  # 60% — moderate stress at late season
        },
        target_pct_taw=90.0,         # Refill to 90% (deficit)
        days_before_harvest_stop=15,
    ),
)
```

## Combining Manual + Automated

Manual irrigation events and automated scheduling can coexist. Manual events are applied first; the automated scheduler then checks if additional irrigation is needed.

```python
config = SimulationConfig(
    soil=soil, crop=crop, climate=climate,
    initial_conditions=ic,
    irrigation=[
        IrrigationEvent(date=datetime.date(2024, 4, 1), depth_mm=30.0),
    ],
    irrigation_strategy=strategy,
)
```

## Irrigation Output

Automated irrigation events appear in `DailyResult.irrig` alongside manual events. The `IrrigationSummary` reports total irrigation, efficiency, and average depletion levels.
