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

---

## Delivery Constraints

Both `MADThresholdStrategy` and `DeficitIrrigationStrategy` accept an optional `delivery` field of type `DeliveryConstraints`. Delivery constraints are applied **after** the MAD/deficit trigger decides that irrigation is needed, but **before** water is applied to the soil. They model real-world limitations such as rotational delivery schedules, fixed application depths, and finite on-farm water supplies.

### Rotational Delivery

In many irrigation schemes, water is delivered on a fixed rotation — e.g. every 15 days early in the season, every 5 days during peak demand. Use `IrrigationIntervalPeriod` entries in `interval_schedule` to override the strategy's base `min_interval_days` during specific date ranges:

```python
from simdualkc.models import (
    DeliveryConstraints,
    IrrigationIntervalPeriod,
    IrrigationStrategy,
    MADThresholdStrategy,
)

delivery = DeliveryConstraints(
    interval_schedule=[
        IrrigationIntervalPeriod(
            start_date=datetime.date(2024, 4, 1),
            end_date=datetime.date(2024, 5, 31),
            min_interval_days=15,  # Early season: every 15 days
        ),
        IrrigationIntervalPeriod(
            start_date=datetime.date(2024, 6, 1),
            end_date=datetime.date(2024, 8, 31),
            min_interval_days=5,   # Mid-season: every 5 days
        ),
    ],
)

strategy = IrrigationStrategy(
    strategy_type="mad_threshold",
    mad_threshold=MADThresholdStrategy(
        mad_fraction=0.55,
        target_pct_taw=100.0,
        delivery=delivery,
    ),
)
```

If the current date does not fall within any period, the strategy's base `min_interval_days` is used as a fallback.

### Maximum Depth per Event

To cap the irrigation depth applied in a single event (e.g. due to flow-rate or soil-infiltration limits), set `max_depth_mm`:

```python
delivery = DeliveryConstraints(
    max_depth_mm=40.0,  # Never apply more than 40 mm in one event
)

strategy = IrrigationStrategy(
    strategy_type="mad_threshold",
    mad_threshold=MADThresholdStrategy(
        mad_fraction=0.50,
        target_pct_taw=100.0,
        delivery=delivery,
    ),
)
```

If the computed irrigation depth exceeds `max_depth_mm`, it is capped. The remaining depletion stays in the root zone and may trigger another irrigation event on the next eligible day.

### Fixed Depth per Stage

Some delivery systems apply a fixed volume regardless of soil depletion. Use `stage_fixed_depth_mm` to specify a fixed depth per growth stage:

```python
delivery = DeliveryConstraints(
    stage_fixed_depth_mm={
        "ini": 20.0,
        "dev": 25.0,
        "mid": 30.0,
        "late": 25.0,
    },
)
```

When the crop is in the mid-season stage, each irrigation event applies exactly 30 mm. The depletion-based depth is ignored. To apply the same fixed depth in all stages, use `fixed_depth_mm` instead:

```python
delivery = DeliveryConstraints(
    fixed_depth_mm=25.0,  # Overrides stage_fixed_depth_mm
)
```

!!! note "Priority order"
    `fixed_depth_mm` takes priority over `stage_fixed_depth_mm`. If both are set, `fixed_depth_mm` wins. After the fixed depth is resolved, `max_depth_mm` is still applied as a cap.

### Stage-Variable Refill Target

`stage_target_pct_taw` overrides the strategy's base `target_pct_taw` per growth stage. This is useful when you want to refill to different percentages of TAW depending on the crop's sensitivity:

```python
delivery = DeliveryConstraints(
    stage_target_pct_taw={
        "ini": 100.0,  # Full refill during establishment
        "dev": 80.0,   # Mild deficit during development
        "mid": 100.0,  # Full refill at peak demand
        "late": 70.0,  # Deficit at late season
    },
)
```

When the crop is in a stage that has a key in `stage_target_pct_taw`, that value replaces the strategy-level `target_pct_taw`. Stages without an explicit key fall back to the strategy's base value.

### Farm Pond Supply

When irrigation water comes from a finite on-farm pond, `FarmPondConstraint` limits cumulative irrigation to the available storage. Supply refill events add water on specific dates:

```python
from simdualkc.models import FarmPondConstraint, FarmPondSupply

delivery = DeliveryConstraints(
    farm_pond=FarmPondConstraint(
        initial_storage_mm=150.0,  # 150 mm available at season start
        max_storage_mm=200.0,      # Pond capacity cap
        supplies=[
            FarmPondSupply(
                date=datetime.date(2024, 6, 15),
                depth_mm=80.0,  # Canal delivery adds 80 mm
            ),
            FarmPondSupply(
                date=datetime.date(2024, 7, 20),
                depth_mm=60.0,  # Second canal delivery
            ),
        ],
    ),
)

strategy = IrrigationStrategy(
    strategy_type="mad_threshold",
    mad_threshold=MADThresholdStrategy(
        mad_fraction=0.50,
        target_pct_taw=100.0,
        delivery=delivery,
    ),
)
```

Each time an automated irrigation event is triggered, the computed depth is capped to the remaining pond storage. After the event, storage is reduced by the applied depth. On supply refill dates, the specified depth is added to storage (capped at `max_storage_mm` if set). If pond storage reaches zero, no further automated irrigation occurs until a refill event adds water.

!!! warning "Farm pond only limits automated irrigation"
    Manual `IrrigationEvent` entries are **not** deducted from pond storage. The pond constraint applies only to irrigation triggered by the automated scheduler.

### Deficit Strategy with Delivery Constraints

`DeficitIrrigationStrategy` also supports `min_interval_days` and `delivery` constraints. Combine them to model deficit irrigation under rotational delivery:

```python
from simdualkc.models import (
    DeficitIrrigationStrategy,
    DeliveryConstraints,
    IrrigationIntervalPeriod,
    IrrigationStrategy,
)

strategy = IrrigationStrategy(
    strategy_type="deficit",
    deficit=DeficitIrrigationStrategy(
        stage_mad={"ini": 0.50, "dev": 0.70, "mid": 0.45, "late": 0.60},
        target_pct_taw=90.0,
        min_interval_days=7,
        delivery=DeliveryConstraints(
            interval_schedule=[
                IrrigationIntervalPeriod(
                    start_date=datetime.date(2024, 6, 1),
                    end_date=datetime.date(2024, 8, 31),
                    min_interval_days=5,
                ),
            ],
            max_depth_mm=35.0,
        ),
    ),
)
```

In this example, the base minimum interval is 7 days, but during June–August the rotational schedule overrides it to 5 days. Each event is capped at 35 mm, and the refill target is 90% of TAW (deficit).
