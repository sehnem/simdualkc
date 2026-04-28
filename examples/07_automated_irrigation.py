"""Example: Automated irrigation scheduling (MAD threshold).

Irrigation is triggered when depletion exceeds Management Allowed Depletion.
Irrigation depth brings soil back to target % TAW.
"""

import datetime
from pathlib import Path

import matplotlib.pyplot as plt

from simdualkc import run_simulation, to_dataframe
from simdualkc.models import (
    ClimateRecord,
    CropParams,
    InitialConditions,
    IrrigationStrategy,
    MADThresholdStrategy,
    SimulationConfig,
    SoilParams,
)

# MAD strategy: irrigate when depletion >= 50% of TAW, refill to 100%
strategy = IrrigationStrategy(
    strategy_type="mad_threshold",
    mad_threshold=MADThresholdStrategy(
        mad_fraction=0.5,
        target_pct_taw=100.0,
        days_before_harvest_stop=10,
        min_interval_days=5,
    ),
)

config = SimulationConfig(
    soil=SoilParams(theta_fc=0.32, theta_wp=0.12, rew=9.0, tew=22.0),
    crop=CropParams(
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
    ),
    climate=[
        ClimateRecord(
            date=datetime.date(2024, 4, 1) + datetime.timedelta(days=i),
            eto=6.0,
            precip=0.0,
            u2=2.0,
            rh_min=45.0,
        )
        for i in range(130)
    ],
    initial_conditions=InitialConditions(dr0=50.0, dei0=5.0, dep0=5.0),
    irrigation_strategy=strategy,
)

result = run_simulation(config)
df = to_dataframe(result)

irrig_days = df[df["irrig"] > 0]
print(f"Automated irrigation: {len(irrig_days)} events")
print(f"Total irrigation: {df['irrig'].sum():.1f} mm")
if not irrig_days.empty:
    print("First 3 irrigation dates:", irrig_days.index[:3].tolist())

# Plot depletion, irrigation events, and stress
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
ax1.fill_between(df.index, 0, df["dr"], alpha=0.5, color="brown", label="Dr (depletion)")
ax1.axhline(y=df["raw"].iloc[50], color="orange", ls="--", lw=1.5, label="RAW")
ax1.axhline(y=df["taw"].iloc[50], color="red", ls=":", lw=1.5, label="TAW")
ax1.bar(
    irrig_days.index,
    irrig_days["irrig"],
    color="blue",
    alpha=0.6,
    width=2,
    label="Irrigation",
)
ax1.set_ylabel("Water [mm]")
ax1.set_title("MAD-Based Irrigation: Depletion vs Thresholds")
ax1.legend(loc="upper right", fontsize=8)
ax1.grid(True, alpha=0.3)

ax2.plot(df.index, df["ks"], color="green", lw=2)
ax2.axhline(y=1.0, color="gray", ls="--", alpha=0.5)
ax2.set_ylabel("Ks (stress coeff)")
ax2.set_xlabel("Date")
ax2.set_title("Water Stress Coefficient (Ks < 1 indicates stress)")
ax2.set_ylim(-0.05, 1.1)
ax2.grid(True, alpha=0.3)

plt.tight_layout()
Path("examples/plots").mkdir(parents=True, exist_ok=True)
plt.savefig("examples/plots/automated_irrigation.png", dpi=150)
print("Plot saved to examples/plots/automated_irrigation.png")
