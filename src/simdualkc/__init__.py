"""SIMDualKc — Layer 1: Mathematical Core.

Public API surface for the dual crop coefficient water balance model (FAO-56).
"""

from importlib.metadata import version

from simdualkc.data_loader import (
    list_crops,
    list_soils,
    load_crop_params,
    load_soil_params,
)
from simdualkc.eto import compute_eto, weather_to_climate_records
from simdualkc.models import (
    ClimateRecord,
    CropParams,
    DailyResult,
    InitialConditions,
    IrrigationEvent,
    SimulationConfig,
    SimulationResult,
    SoilParams,
    WeatherRecord,
)
from simdualkc.reporting import (
    compute_irrigation_summary,
    compute_simulation_summary,
    compute_stress_summary,
    format_irrigation_opportunity_table,
    format_yield_loss_table,
)
from simdualkc.simulation import run_simulation, to_dataframe

__version__ = version("simdualkc-core")

__all__ = [
    # Models
    "ClimateRecord",
    "CropParams",
    "DailyResult",
    "InitialConditions",
    "IrrigationEvent",
    "SimulationConfig",
    "SimulationResult",
    "SoilParams",
    "WeatherRecord",
    # ETo calculator
    "compute_eto",
    "weather_to_climate_records",
    # Reporting
    "compute_irrigation_summary",
    "compute_simulation_summary",
    "compute_stress_summary",
    "format_irrigation_opportunity_table",
    "format_yield_loss_table",
    # Simulation entry-points
    "run_simulation",
    "to_dataframe",
    # Data loaders
    "list_crops",
    "list_soils",
    "load_crop_params",
    "load_soil_params",
]
