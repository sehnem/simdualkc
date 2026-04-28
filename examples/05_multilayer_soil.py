"""Example: Multi-layer soil profile with dynamic TAW.

Demonstrates use of stratified soil (up to 5 layers) where TAW is computed
by integrating layer properties within the current root depth.
"""

import datetime
from pathlib import Path

import matplotlib.pyplot as plt

from simdualkc import run_simulation, to_dataframe
from simdualkc.models import (
    ClimateRecord,
    CropParams,
    InitialConditions,
    SimulationConfig,
    SoilLayer,
    SoilParams,
)

# Two-layer soil: sandy top (0-0.4m), clay loam below (0.4-1.2m)
soil = SoilParams(
    theta_fc=0.32,
    theta_wp=0.12,
    layers=[
        SoilLayer(depth_m=0.4, theta_fc=0.25, theta_wp=0.08),
        SoilLayer(depth_m=1.2, theta_fc=0.35, theta_wp=0.15),
    ],
    rew=9.0,
    tew=22.0,
)

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
)

climate = [
    ClimateRecord(
        date=datetime.date(2024, 4, 1) + datetime.timedelta(days=i),
        eto=5.0,
        precip=0.0,
        u2=2.0,
        rh_min=45.0,
    )
    for i in range(130)
]

config = SimulationConfig(
    soil=soil,
    crop=crop,
    climate=climate,
    initial_conditions=InitialConditions(dr0=30.0, dei0=5.0, dep0=5.0),
)
result = run_simulation(config)
df = to_dataframe(result)

print("Multi-layer soil simulation")
print(f"TAW early (day 10): {df['taw'].iloc[9]:.1f} mm")
print(f"TAW mid-season (day 70): {df['taw'].iloc[69]:.1f} mm")
print("TAW increases as roots grow into deeper layers")

# Plot TAW and root depth over time
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
ax1.plot(df.index, df["taw"], color="teal", lw=2, label="TAW")
ax1.plot(df.index, df["raw"], color="orange", lw=1.5, ls="--", label="RAW")
ax1.set_ylabel("Water [mm]")
ax1.set_title("Dynamic TAW as Roots Grow Through Soil Layers")
ax1.legend()
ax1.grid(True, alpha=0.3)

ax2.plot(df.index, df["zr"] * 1000, color="saddlebrown", lw=2)
ax2.set_ylabel("Root depth [mm]")
ax2.set_xlabel("Date")
ax2.set_title("Root Depth Growth")
ax2.grid(True, alpha=0.3)

plt.tight_layout()
Path("examples/plots").mkdir(parents=True, exist_ok=True)
plt.savefig("examples/plots/multilayer_soil.png", dpi=150)
print("Plot saved to examples/plots/multilayer_soil.png")
