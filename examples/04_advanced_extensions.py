"""Scientific simulation and visualization: Advanced Extensions.

Demonstrates the impacts of Stewart's Yield Model, Mulches, and 
Salinity Stress on crop water balance and actual yield.
"""

import datetime
from copy import deepcopy
import matplotlib.pyplot as plt
import seaborn as sns

from simdualkc import run_simulation, to_dataframe
from simdualkc.models import (
    ClimateRecord,
    CropParams,
    InitialConditions,
    IrrigationEvent,
    MulchParams,
    SalinityParams,
    SimulationConfig,
    SoilParams,
    YieldParams,
)

# Plot styling
sns.set_theme(style="whitegrid", context="paper", palette="muted")
plt.rcParams.update({'font.size': 10})

def _create_base_config() -> SimulationConfig:
    plant_date = datetime.date(2026, 5, 1)

    soil = SoilParams(
        theta_fc=0.30, theta_wp=0.15, ze=0.10, rew=9.0, tew=20.0,
    )

    crop = CropParams(
        kcb_ini=0.15, kcb_mid=1.15, kcb_end=0.25,
        stage_lengths=[20, 30, 40, 20],  # 110 days total
        plant_date=plant_date, zr_max=1.2, h_max=2.0, p_tab=0.55, fc_max=0.9,
    )

    ic = InitialConditions(dr0=0.0, dei0=0.0, dep0=0.0)

    # Create 110 days of climate
    climate = [
        ClimateRecord(
            date=plant_date + datetime.timedelta(days=i),
            eto=4.0, precip=0.0, u2=2.0, rh_min=45.0
        ) for i in range(110)
    ]

    # Add irrigation causing significant water stress eventually
    irrigations = [
        IrrigationEvent(date=plant_date + datetime.timedelta(days=30), depth_mm=50.0),
        IrrigationEvent(date=plant_date + datetime.timedelta(days=60), depth_mm=50.0),
        IrrigationEvent(date=plant_date + datetime.timedelta(days=90), depth_mm=50.0),
    ]

    return SimulationConfig(
        soil=soil, crop=crop, climate=climate,
        initial_conditions=ic, irrigation=irrigations,
        yield_params=YieldParams(y_m=10000.0, k_y=1.2)
    )

def main():
    print("=== SIMDualKc Extensions Demo ===")
    
    baseline_cfg = _create_base_config()

    mulch_cfg = deepcopy(baseline_cfg)
    mulch_cfg.mulch = MulchParams(f_mulch=0.8, kr_mulch=0.2)

    salinity_cfg = deepcopy(baseline_cfg)
    salinity_cfg.salinity = SalinityParams(ec_e=6.0, ec_threshold=2.0, b=10.0, k_y=1.2)

    scenarios = {
        "Baseline": baseline_cfg,
        "With Mulch": mulch_cfg,
        "High Salinity": salinity_cfg,
    }

    results_data = {}
    yields = {}

    for name, config in scenarios.items():
        res = run_simulation(config)
        df = to_dataframe(res)
        results_data[name] = df
        yields[name] = (res.yield_act, res.yield_decrease_pct)

    # Multi-panel visualization
    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

    # 1. Stress Coefficient (Ks) Comparison
    for label, df in results_data.items():
        cols = {'Baseline': 'blue', 'With Mulch': 'green', 'High Salinity': 'red'}
        axes[0].plot(df.index, df['ks'], label=f'$K_s$ ({label})', lw=2, color=cols[label])

    axes[0].set_ylabel('Water Stress Coeff $K_s$ [—]')
    axes[0].set_title('Impact of Scenarios on Crop Water Status')
    axes[0].legend(loc='lower left')

    # 2. Daily Actual Transpiration
    for label, df in results_data.items():
        cols = {'Baseline': 'blue', 'With Mulch': 'green', 'High Salinity': 'red'}
        axes[1].plot(df.index, df['transp_act'], label=f'Transpiration ({label})', lw=1.5, color=cols[label])

    axes[1].set_ylabel('Transpiration [mm/day]')
    axes[1].set_title('Actual Crop Transpiration')
    axes[1].legend(loc='lower left')

    fig.autofmt_xdate(rotation=30)
    plt.tight_layout()

    # Save to plots directory
    import os
    os.makedirs("examples/plots", exist_ok=True)
    output = "examples/plots/advanced_extensions.png"
    plt.savefig(output, dpi=300)
    print(f"Plot saved to {output}\\n")

    print("Simulation Summary:")
    for name, df in results_data.items():
        y_act, y_dec = yields[name]
        print(f" - {name:15}: Total ETc = {df['etc_act'].sum():5.1f} mm | Yield = {y_act:7.1f} kg/ha (Decrease: {y_dec:4.1f}%)")

if __name__ == "__main__":
    main()
