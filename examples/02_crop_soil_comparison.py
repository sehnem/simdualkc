"""Scientific simulation and visualization: Maize and Sorghum comparisons.

Compares crop behaviors across different soil types and generates 
high-fidelity scientific plots.
"""

import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from simdualkc import (
    load_crop_params, 
    load_soil_params, 
    run_simulation, 
    to_dataframe
)
from simdualkc.models import ClimateRecord, InitialConditions, SimulationConfig

# Plot styling
sns.set_theme(style="whitegrid", context="paper", palette="muted")
plt.rcParams.update({'font.size': 10})

plant_date = datetime.date(2024, 4, 15)
n_days = 150

scenarios = {
    "Maize (Clay)": ("MilhoAlvalade2005_IA", "Clay"),
    "Maize (Sand)": ("MilhoAlvalade2005_IA", "Sand"),
    "Sorghum (Clay)": ("SorgoAlvalade2008_IA", "Clay"),
}

results = {}
for name, (c_name, s_name) in scenarios.items():
    crop = load_crop_params(c_name)
    soil = load_soil_params(s_name)
    crop.plant_date = plant_date
    
    climate = [
        ClimateRecord(
            date=plant_date + datetime.timedelta(days=i),
            eto=6.5 if 30 <= i <= 90 else 4.0,
            precip=15.0 if i == 45 else 0.0,
            u2=2.0, rh_min=40.0
        ) for i in range(n_days)
    ]
    
    config = SimulationConfig(
        soil=soil, crop=crop, climate=climate, 
        initial_conditions=InitialConditions(dr0=10.0, dei0=5.0, dep0=5.0)
    )
    results[name] = to_dataframe(run_simulation(config))

# Multi-panel visualization
fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

# 1. Kc components for first scenario
name, df = next(iter(results.items()))
axes[0].plot(df.index, df['kcb'], label='Basal $K_{cb}$', lw=2, color='green')
axes[0].plot(df.index, df['ke'], label='Soil Evap $K_e$', lw=1.5, ls='--', color='orange')
axes[0].plot(df.index, (df['kcb'] * df['ks'] + df['ke']), label='Actual $K_c$', lw=1.5, color='blue', alpha=0.6)
axes[0].set_ylabel('Coefficient value [—]')
axes[0].set_title(f'Dual Crop Coefficients: {name}')
axes[0].legend(loc='upper right')

# 2. Water Balance
for label, df in results.items():
    axes[1].plot(df.index, df['dr'], label=f'Depletion $D_r$ ({label})')
    if label == name:
        axes[1].plot(df.index, df['taw'], color='black', lw=1, ls=':', label='TAW')

axes[1].set_ylabel('Water Depth [mm]')
axes[1].set_title('Root Zone Water Balance')
axes[1].invert_yaxis()
axes[1].legend(loc='lower left', ncol=2)

fig.autofmt_xdate(rotation=30)
plt.tight_layout()

output = "examples/plots/maize_sorghum_comparison.png"
plt.savefig(output, dpi=300)

print("Simulation Summary:")
for name, df in results.items():
    print(f" - {name:15}: Total ETc = {df['etc_act'].sum():5.1f} mm | Stress Days = {(df['ks'] < 1.0).sum()}")
