"""Example: Compute ETo from raw weather data using FAO-56 Penman-Monteith.

When ETo is not available, compute it from Tmax, Tmin, RH, Rs, u2.
"""

import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from simdualkc import compute_eto, run_simulation, to_dataframe, weather_to_climate_records
from simdualkc.models import (
    CropParams,
    InitialConditions,
    SimulationConfig,
    SoilParams,
)

# Raw weather data (typically from a weather station)
latitude = 38.7  # degrees N
elevation = 50.0  # m
weather = [
    {
        "date": datetime.date(2024, 7, 1) + datetime.timedelta(days=i),
        "t_max": 28.0 + (i % 5),
        "t_min": 16.0 + (i % 3),
        "rh_max": 80.0,
        "rh_min": 40.0,
        "rs": 24.0,
        "u2": 2.5,
        "precip": 0.0,
    }
    for i in range(30)
]

# Convert to ClimateRecord with computed ETo
climate = weather_to_climate_records(weather, latitude=latitude, elevation=elevation)

# Or compute ETo for a single day
single_eto = compute_eto(
    t_max=30.0,
    t_min=18.0,
    rh_max=75.0,
    rh_min=45.0,
    rs=25.0,
    u2=2.0,
    latitude=latitude,
    elevation=elevation,
    date=datetime.date(2024, 7, 15),
)
print(f"Single-day ETo: {single_eto:.2f} mm/day")

# Run simulation with computed ETo
config = SimulationConfig(
    soil=SoilParams(theta_fc=0.32, theta_wp=0.12, rew=9.0, tew=22.0),
    crop=CropParams(
        kcb_ini=0.15,
        kcb_mid=1.10,
        kcb_end=0.35,
        stage_lengths=[20, 30, 40, 20],
        plant_date=datetime.date(2024, 7, 1),
        zr_ini=0.15,
        zr_max=1.0,
        h_max=2.0,
        p_tab=0.55,
        fc_max=0.9,
    ),
    climate=climate,
    initial_conditions=InitialConditions(dr0=20.0, dei0=5.0, dep0=5.0),
)
result = run_simulation(config)
print(f"Simulation with computed ETo: {len(result.daily_results)} days")

# Plot ETo and weather inputs
df = to_dataframe(result)
weather_df = pd.DataFrame(weather)
weather_df.index = pd.to_datetime(weather_df["date"])

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
ax1.plot(df.index, df["eto"], color="darkblue", lw=2, label="ETo (computed)")
ax1.set_ylabel("ETo [mm/day]")
ax1.set_title("FAO-56 Penman-Monteith Reference ET from Raw Weather")
ax1.legend()
ax1.grid(True, alpha=0.3)

ax2_twin = ax2.twinx()
ax2.plot(weather_df.index, weather_df["t_max"], color="red", alpha=0.8, label="Tmax")
ax2.plot(weather_df.index, weather_df["t_min"], color="blue", alpha=0.8, label="Tmin")
ax2_twin.plot(weather_df.index, weather_df["rs"], color="orange", alpha=0.7, label="Rs")
ax2.set_ylabel("Temperature [°C]")
ax2_twin.set_ylabel("Solar radiation [MJ/m²/day]")
ax2.set_xlabel("Date")
ax2.set_title("Weather Inputs")
ax2.legend(loc="upper left")
ax2_twin.legend(loc="upper right")
ax2.grid(True, alpha=0.3)

plt.tight_layout()
Path("examples/plots").mkdir(parents=True, exist_ok=True)
plt.savefig("examples/plots/eto_calculation.png", dpi=150)
print("Plot saved to examples/plots/eto_calculation.png")
