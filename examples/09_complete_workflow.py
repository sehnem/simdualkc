"""Example: Complete workflow with ETo, LAI, irrigation, and summaries.

Demonstrates the full feature set in a single simulation.
"""

import datetime
from pathlib import Path

import matplotlib.pyplot as plt

from simdualkc import (
    format_irrigation_opportunity_table,
    format_yield_loss_table,
    run_simulation,
    to_dataframe,
    weather_to_climate_records,
)
from simdualkc.models import (
    CropParams,
    InitialConditions,
    IrrigationStrategy,
    MADThresholdStrategy,
    SimulationConfig,
    SoilLayer,
    SoilParams,
    YieldParams,
)

# 1. Build climate from raw weather
weather = [
    {
        "date": datetime.date(2024, 4, 1) + datetime.timedelta(days=i),
        "t_max": 22.0 + (i % 10),
        "t_min": 10.0 + (i % 5),
        "rh_max": 85.0,
        "rh_min": 35.0,
        "rs": 18.0 + (i % 8),
        "u2": 2.0,
        "precip": 2.0 if i % 15 == 0 else 0.0,
    }
    for i in range(120)
]
climate = weather_to_climate_records(weather, latitude=38.0, elevation=100.0)

# 2. Multi-layer soil
soil = SoilParams(
    theta_fc=0.32,
    theta_wp=0.12,
    layers=[
        SoilLayer(depth_m=0.5, theta_fc=0.30, theta_wp=0.10),
        SoilLayer(depth_m=1.2, theta_fc=0.34, theta_wp=0.14),
    ],
    rew=9.0,
    tew=22.0,
)

# 3. Crop with LAI-based cover
crop = CropParams(
    kcb_ini=0.15,
    kcb_mid=1.10,
    kcb_end=0.35,
    stage_lengths=[25, 35, 45, 25],
    plant_date=datetime.date(2024, 4, 1),
    zr_ini=0.15,
    zr_max=1.0,
    h_max=2.0,
    p_tab=0.55,
    fc_max=0.9,
    lai_values=[0.2, 2.5, 4.0, 2.0],
    lai_dates=[
        datetime.date(2024, 4, 1),
        datetime.date(2024, 5, 15),
        datetime.date(2024, 6, 20),
        datetime.date(2024, 7, 20),
    ],
    k_ext=0.6,
)

# 4. Automated irrigation
strategy = IrrigationStrategy(
    strategy_type="mad_threshold",
    mad_threshold=MADThresholdStrategy(mad_fraction=0.5, target_pct_taw=100.0),
)

# 5. Run
config = SimulationConfig(
    soil=soil,
    crop=crop,
    climate=climate,
    initial_conditions=InitialConditions(dr0=40.0, dei0=5.0, dep0=5.0),
    irrigation_strategy=strategy,
    yield_params=YieldParams(y_m=10000.0, k_y=1.25),
)
result = run_simulation(config)

# 6. Summaries
print(format_yield_loss_table(result.summary.stress))
print()
print(format_irrigation_opportunity_table(result.summary.irrigation))
print(f"\nActual yield: {result.yield_act:.0f} kg/ha")
print(f"Yield decrease: {result.yield_decrease_pct:.1f}%")

# 7. Multi-panel overview plot
df = to_dataframe(result)
fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)

axes[0, 0].plot(df.index, df["etc_act"].cumsum(), color="darkgreen", lw=2, label="Cum. ETa")
axes[0, 0].plot(df.index, df["precip"].cumsum(), color="blue", lw=1.5, label="Cum. precip")
axes[0, 0].plot(df.index, df["irrig"].cumsum(), color="cyan", lw=1.5, label="Cum. irrig")
axes[0, 0].set_ylabel("Cumulative [mm]")
axes[0, 0].set_title("Water Balance")
axes[0, 0].legend(fontsize=8)
axes[0, 0].grid(True, alpha=0.3)

axes[0, 1].plot(df.index, df["kcb"], color="green", lw=2, label="Kcb")
axes[0, 1].plot(df.index, df["fc"], color="olivedrab", lw=1.5, label="fc (from LAI)")
axes[0, 1].set_ylabel("Coefficient")
axes[0, 1].set_title("Crop Coefficients (LAI-based fc)")
axes[0, 1].legend(fontsize=8)
axes[0, 1].grid(True, alpha=0.3)

axes[1, 0].fill_between(df.index, 0, df["dr"], alpha=0.5, color="brown")
irrig_days = df[df["irrig"] > 0]
axes[1, 0].bar(irrig_days.index, irrig_days["irrig"], color="blue", alpha=0.6, width=1.5)
axes[1, 0].axhline(y=df["raw"].iloc[50], color="orange", ls="--", alpha=0.7)
axes[1, 0].set_ylabel("Dr [mm] / Irrigation")
axes[1, 0].set_title("Depletion and Auto-Irrigation")
axes[1, 0].grid(True, alpha=0.3)

axes[1, 1].plot(df.index, df["ks"], color="purple", lw=2)
axes[1, 1].axhline(y=1.0, color="gray", ls="--", alpha=0.5)
axes[1, 1].set_ylabel("Ks")
axes[1, 1].set_xlabel("Date")
axes[1, 1].set_title("Water Stress")
axes[1, 1].set_ylim(-0.05, 1.1)
axes[1, 1].grid(True, alpha=0.3)

plt.suptitle("Complete Workflow: ETo + LAI + Auto-Irrigation + Multi-Layer Soil", y=1.02)
plt.tight_layout()
Path("examples/plots").mkdir(parents=True, exist_ok=True)
plt.savefig("examples/plots/complete_workflow.png", dpi=150, bbox_inches="tight")
print("\nPlot saved to examples/plots/complete_workflow.png")
