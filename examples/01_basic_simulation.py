"""Example simulation: Maize in a Mediterranean climate.

Demonstrates simulation of Maize (Milho) under Mediterranean conditions,
referencing the Rosa et al. (2012) study.
"""

import datetime

from simdualkc import (
    list_crops,
    list_soils,
    load_crop_params,
    load_soil_params,
    run_simulation,
    to_dataframe,
)
from simdualkc.models import ClimateRecord, InitialConditions, SimulationConfig

# 1. List available materials
print("Available crops in database:", list_crops())
print("Available soils in database:", list_soils())

# 2. Load reference parameters
crop = load_crop_params("MilhoAlvalade2005_IA")
soil = load_soil_params("Clay")

# 2. Configure start
plant_date = datetime.date(2024, 5, 1)
crop.plant_date = plant_date

# 3. Climate sequence (120 days)
climate = [
    ClimateRecord(
        date=plant_date + datetime.timedelta(days=i), eto=6.0, precip=0.0, u2=2.0, rh_min=45.0
    )
    for i in range(120)
]

# 4. Initial conditions
ic = InitialConditions(dr0=10.0, dei0=5.0, dep0=5.0)

# 5. Run simulation
config = SimulationConfig(soil=soil, crop=crop, climate=climate, initial_conditions=ic)
result = run_simulation(config)
df = to_dataframe(result)

# Summary output
print(f"Simulation finished for {len(df)} days.")
stress_days = df[df["ks"] < 1.0]
if not stress_days.empty:
    print(f"First day of water stress: {stress_days.index[0].date()}")

print("\nSummary Totals (mm):")
print(f"  Precipitation: {df['precip'].sum():.1f}")
print(f"  Actual ETc:    {df['etc_act'].sum():.1f}")
print(f"  Final Depletion (Dr): {df['dr'].iloc[-1]:.1f}")
