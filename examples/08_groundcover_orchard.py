"""Example: Orchard/vineyard with active groundcover.

Inter-row grass competes with the main crop for water.
Combined Kcb = Kcb_cover + Kd * (Kcb_full - Kcb_cover).
"""

import datetime
from pathlib import Path

import matplotlib.pyplot as plt

from simdualkc import run_simulation, to_dataframe
from simdualkc.models import (
    ClimateRecord,
    CropParams,
    GroundcoverParams,
    InitialConditions,
    SimulationConfig,
    SoilParams,
)

# Sparse orchard canopy (fc_max low) with grass between rows
crop = CropParams(
    kcb_ini=0.20,
    kcb_mid=0.95,
    kcb_end=0.85,
    stage_lengths=[60, 90, 120, 90],
    plant_date=datetime.date(2024, 2, 1),
    zr_ini=0.5,
    zr_max=1.5,
    h_max=3.0,
    p_tab=0.45,
    fc_max=0.35,
)

groundcover = GroundcoverParams(
    kcb_cover=0.25,
    fc_cover=0.4,
    h_cover=0.15,
)

config = SimulationConfig(
    soil=SoilParams(theta_fc=0.32, theta_wp=0.12, rew=9.0, tew=22.0),
    crop=crop,
    climate=[
        ClimateRecord(
            date=datetime.date(2024, 2, 1) + datetime.timedelta(days=i),
            eto=4.0,
            precip=0.0,
            u2=2.0,
            rh_min=50.0,
        )
        for i in range(180)
    ],
    initial_conditions=InitialConditions(dr0=30.0, dei0=5.0, dep0=5.0),
    groundcover=groundcover,
)

result = run_simulation(config)
df = to_dataframe(result)

print("Orchard with groundcover")
print(f"Typical Kcb (mid-season): {df['kcb'].iloc[100]:.2f}")
print("Combined main crop + grass Kcb")

# Plot Kcb and fractional cover over season
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
ax1.plot(df.index, df["kcb"], color="forestgreen", lw=2)
ax1.axhline(y=0.25, color="gray", ls="--", alpha=0.7, label="Kcb_cover (grass)")
ax1.set_ylabel("Kcb")
ax1.set_title("Combined Kcb: Orchard + Groundcover")
ax1.legend()
ax1.grid(True, alpha=0.3)

ax2.plot(df.index, df["fc"], color="green", lw=2, label="fc (main crop)")
ax2.plot(df.index, df["zr"], color="saddlebrown", lw=1.5, label="Root depth [m]")
ax2.set_ylabel("Fraction / Depth [m]")
ax2.set_xlabel("Date")
ax2.set_title("Fractional Cover and Root Depth")
ax2.legend()
ax2.grid(True, alpha=0.3)

plt.tight_layout()
Path("examples/plots").mkdir(parents=True, exist_ok=True)
plt.savefig("examples/plots/groundcover_orchard.png", dpi=150)
print("Plot saved to examples/plots/groundcover_orchard.png")
