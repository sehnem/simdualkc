"""Feature demonstration: Soil Evaporation Physics.

Compares 'Sprinkler' (fw=1.0) vs 'Drip' (fw=0.3) to show how the
wetting fraction logic reduces soil water loss.
"""

import datetime

import matplotlib.pyplot as plt
import seaborn as sns

from simdualkc import load_crop_params, load_soil_params, run_simulation, to_dataframe
from simdualkc.models import ClimateRecord, InitialConditions, IrrigationEvent, SimulationConfig

sns.set_theme(style="ticks", context="talk")

crop = load_crop_params("MilhoAlvalade2005_IA")
soil = load_soil_params("Clay")
plant_date = datetime.date(2024, 6, 1)
crop.plant_date = plant_date

climate = [
    ClimateRecord(
        date=plant_date + datetime.timedelta(days=i), eto=5.0, precip=0.0, u2=1.5, rh_min=50.0
    )
    for i in range(60)
]

# Run scenarios with persistent fw_base
results = {}
for fw in [1.0, 0.3]:
    irr = [
        IrrigationEvent(date=plant_date + datetime.timedelta(days=5), depth_mm=30.0, fw=fw),
        IrrigationEvent(date=plant_date + datetime.timedelta(days=25), depth_mm=30.0, fw=fw),
    ]
    # Start with dry soil so that only the wetted area evaporates significantly
    config = SimulationConfig(
        soil=soil,
        crop=crop,
        climate=climate,
        fw_base=fw,
        initial_conditions=InitialConditions(dr0=30, dei0=soil.tew, dep0=soil.tew),
        irrigation=irr,
    )
    results[fw] = to_dataframe(run_simulation(config))

df_sprinkler = results[1.0]
df_drip = results[0.3]

# Plotting
fig, ax = plt.subplots(1, 1, figsize=(10, 6))
ax.plot(
    df_sprinkler.index,
    df_sprinkler["evap_act"].cumsum(),
    label="Sprinkler ($f_w$=1.0)",
    color="red",
    lw=2.5,
)
ax.plot(
    df_drip.index, df_drip["evap_act"].cumsum(), label="Drip ($f_w$=0.3)", color="blue", lw=2.5
)

ax.set_ylabel("Cumulative Soil Evaporation [mm]")
ax.set_title("Impact of Irrigation System on Soil Water Loss ($E_s$)")
ax.legend()

fig.autofmt_xdate(rotation=30)
plt.tight_layout()

output = "examples/plots/evaporation_comparison.png"
plt.savefig(output, dpi=300)

print("Comparison Result:")
print(f" - Sprinkler Evaporation: {df_sprinkler['evap_act'].sum():.1f} mm")
print(f" - Drip Evaporation:      {df_drip['evap_act'].sum():.1f} mm")
