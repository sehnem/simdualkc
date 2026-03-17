"""Pydantic domain models for SIMDualKc Layer 1.

All models perform strict validation at construction time so that
downstream equation functions can assume clean, physically-plausible inputs.
"""

from __future__ import annotations

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DPMethod(StrEnum):
    """Method used to compute deep percolation."""

    SIMPLE = "simple"
    """Instantaneous drainage — excess water beyond field capacity becomes DP."""

    PARAMETRIC = "parametric"
    """Liu et al. (2006) parametric drainage model."""


class CRMethod(StrEnum):
    """Method used to compute capillary rise."""

    NONE = "none"
    """No capillary rise (default)."""

    CONSTANT = "constant"
    """Fixed Gmax value reduced when Dr < RAW."""

    PARAMETRIC = "parametric"
    """Liu et al. (2006) parametric approach."""


# ---------------------------------------------------------------------------
# Soil
# ---------------------------------------------------------------------------


class SoilParams(BaseModel):
    """Soil hydraulic and surface properties.

    Attributes:
        theta_fc: Volumetric soil water content at field capacity [m³/m³].
        theta_wp: Volumetric soil water content at wilting point [m³/m³].
        ze: Depth of the surface evaporative layer [m].  Typically 0.10–0.15 m.
        rew: Readily evaporable water [mm].  Stage-1 evaporation capacity.
        tew: Total evaporable water [mm].  Maximum water extractable by evaporation.
        cn2: SCS Curve Number for average antecedent moisture conditions (AMC II).
        a_d: Parametric drainage coefficient *a* (Liu et al. 2006) [—].
            Required when ``dp_method=DPMethod.PARAMETRIC``.
        b_d: Parametric drainage exponent *b* (Liu et al. 2006) [—].
            Required when ``dp_method=DPMethod.PARAMETRIC``.
        gmax: Maximum daily capillary rise rate [mm/day].
            Required when ``cr_method=CRMethod.CONSTANT``.
    """

    theta_fc: float = Field(gt=0.0, lt=1.0, description="Field capacity [m³/m³]")
    theta_wp: float = Field(gt=0.0, lt=1.0, description="Wilting point [m³/m³]")
    ze: float = Field(default=0.10, gt=0.0, le=0.30, description="Evaporative layer depth [m]")
    rew: float = Field(gt=0.0, description="Readily evaporable water [mm]")
    tew: float = Field(gt=0.0, description="Total evaporable water [mm]")
    cn2: float = Field(default=75.0, ge=1.0, le=100.0, description="Curve Number, AMC II")
    a_d: float | None = Field(default=None, description="Drainage coefficient a (Liu 2006)")
    b_d: float | None = Field(default=None, description="Drainage exponent b (Liu 2006)")
    gmax: float | None = Field(default=None, ge=0.0, description="Max capillary rise [mm/day]")

    @model_validator(mode="after")
    def _theta_order(self) -> SoilParams:
        if self.theta_wp >= self.theta_fc:
            msg = "theta_wp must be less than theta_fc"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _tew_rew_order(self) -> SoilParams:
        if self.rew >= self.tew:
            msg = "rew must be less than tew"
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Crop
# ---------------------------------------------------------------------------


class CropParams(BaseModel):
    """Tabulated crop parameters for the four FAO-56 growth stages.

    Stage lengths are provided as a list of four integer day-counts:
    [ini, dev, mid, late].  The simulation interpolates Kcb linearly
    through ini and dev, holds it constant at mid, then interpolates
    through late.

    Attributes:
        kcb_ini: Basal crop coefficient — initial stage [—].
        kcb_mid: Basal crop coefficient — mid stage [—].
        kcb_end: Basal crop coefficient — late/end stage [—].
        stage_lengths: Day-lengths for [ini, dev, mid, late] stages.
        plant_date: Calendar date the crop is planted / simulation starts.
        zr_ini: Root depth at the start of the initial stage [m].
        zr_max: Maximum root depth (reached at end of development) [m].
        h_max: Maximum plant height [m].
        p_tab: Tabulated soil water depletion fraction for no stress [—].
        fc_max: Maximum fraction of soil surface covered by vegetation [—].
        ml: Canopy light extinction / density multiplier (1.5–2.0) [—].
        kc_min: Minimum Kc for bare/dry soil (default 0.15) [—].
    """

    kcb_ini: float = Field(ge=0.0, le=3.0)
    kcb_mid: float = Field(ge=0.0, le=3.0)
    kcb_end: float = Field(ge=0.0, le=3.0)
    stage_lengths: list[int] = Field(min_length=4, max_length=4)
    plant_date: datetime.date
    zr_ini: float = Field(default=0.15, gt=0.0, le=1.0, description="Initial root depth [m]")
    zr_max: float = Field(gt=0.0, le=3.0, description="Max root depth [m]")
    h_max: float = Field(gt=0.0, le=20.0, description="Max plant height [m]")
    p_tab: float = Field(gt=0.0, lt=1.0, description="Depletion fraction (no stress)")
    fc_max: float = Field(gt=0.0, le=1.0, description="Max fraction of soil covered")
    ml: float = Field(default=1.5, ge=1.5, le=2.0, description="Canopy density multiplier")
    kc_min: float = Field(default=0.15, ge=0.0, le=0.5, description="Min Kc (bare soil)")

    @field_validator("stage_lengths")
    @classmethod
    def _positive_stages(cls, v: list[int]) -> list[int]:
        if any(d <= 0 for d in v):
            msg = "All stage lengths must be positive integers"
            raise ValueError(msg)
        return v


# ---------------------------------------------------------------------------
# Climate
# ---------------------------------------------------------------------------


class ClimateRecord(BaseModel):
    """Daily meteorological observation.

    Attributes:
        date: Calendar date.
        eto: Reference evapotranspiration [mm/day] (FAO-56 Penman-Monteith).
        precip: Total daily precipitation [mm].
        u2: Mean daily wind speed at 2 m height [m/s].
        rh_min: Minimum daily relative humidity [%].
    """

    date: datetime.date
    eto: float = Field(ge=0.0, description="Reference ET [mm/day]")
    precip: float = Field(ge=0.0, description="Precipitation [mm]")
    u2: float = Field(ge=0.0, description="Wind speed at 2 m [m/s]")
    rh_min: float = Field(ge=1.0, le=100.0, description="Min relative humidity [%]")


# ---------------------------------------------------------------------------
# Irrigation
# ---------------------------------------------------------------------------


class IrrigationEvent(BaseModel):
    """A single irrigation application.

    Attributes:
        date: Calendar date of the irrigation.
        depth_mm: Net water applied at the field surface [mm].
        fw: Fraction of soil surface effectively wetted [—].
            1.0 for sprinkler/flood, <1 for drip.
    """

    date: datetime.date
    depth_mm: float = Field(gt=0.0, description="Net irrigation depth [mm]")
    fw: float = Field(default=1.0, gt=0.0, le=1.0, description="Wetted fraction [—]")


# ---------------------------------------------------------------------------
# Initial conditions
# ---------------------------------------------------------------------------


class InitialConditions(BaseModel):
    """Water depletion values at the start of the simulation (day 0).

    Attributes:
        dr0: Root-zone depletion [mm].  0 means soil is at field capacity.
        dei0: Surface evaporative layer depletion — irrigated fraction [mm].
        dep0: Surface evaporative layer depletion — precipitation-only fraction [mm].
    """

    dr0: float = Field(ge=0.0, description="Initial root-zone depletion [mm]")
    dei0: float = Field(ge=0.0, description="Initial surface depletion (irrigated) [mm]")
    dep0: float = Field(ge=0.0, description="Initial surface depletion (precip-only) [mm]")


# ---------------------------------------------------------------------------
# Extensions (Yield, Salinity, Mulches)
# ---------------------------------------------------------------------------


class YieldParams(BaseModel):
    """Parameters for the Stewart water-yield model.

    Attributes:
        y_m: Maximum expected yield [kg/ha].
        k_y: Yield response factor [—].
    """

    y_m: float = Field(gt=0.0, description="Maximum expected yield [kg/ha]")
    k_y: float = Field(gt=0.0, description="Yield response factor [—]")


class SalinityParams(BaseModel):
    """Parameters for computing salinity stress (FAO-56 / Mass-Hoffman).

    Attributes:
        ec_e: Soil salinity (electrical conductivity of saturation extract) [dS/m].
        ec_threshold: Crop specific salinity threshold [dS/m].
        b: Yield loss per unit increase in salinity [% per dS/m].
        k_y: Yield response factor used to relate salinity yield reduction
            to transpiration reduction [—].
    """

    ec_e: float = Field(ge=0.0, description="Soil salinity ECe [dS/m]")
    ec_threshold: float = Field(ge=0.0, description="Crop threshold ECe [dS/m]")
    b: float = Field(ge=0.0, description="Yield loss slope b [% per dS/m]")
    k_y: float = Field(default=1.0, gt=0.0, description="Yield response factor Ky [—]")


class MulchParams(BaseModel):
    """Parameters for surface mulch coverage.

    Attributes:
        f_mulch: Fraction of the total ground surface covered by mulch [0–1].
        kr_mulch: Evaporation reduction factor for the mulched area
            (e.g., 0.5 for organic, 0.1 for plastic) [0–1].
    """

    f_mulch: float = Field(ge=0.0, le=1.0, description="Fraction of ground covered by mulch [0–1]")
    kr_mulch: float = Field(
        ge=0.0, le=1.0, description="Mulch evaporation reduction multiplier [0–1]"
    )


# ---------------------------------------------------------------------------
# Simulation configuration
# ---------------------------------------------------------------------------


class SimulationConfig(BaseModel):
    """Top-level input bundle that fully specifies a simulation run.

    Attributes:
        soil: Soil hydraulic parameters.
        crop: Crop growth and coefficient parameters.
        climate: Ordered sequence of daily climate records.
        initial_conditions: Depletion state at day 0.
        irrigation: Optional sequence of irrigation events.
        dp_method: Method to compute deep percolation.
        cr_method: Method to compute capillary rise.
    """

    soil: SoilParams
    crop: CropParams
    climate: list[ClimateRecord]
    initial_conditions: InitialConditions
    irrigation: list[IrrigationEvent] = Field(default_factory=list)
    fw_base: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Default irrigation wetting fraction"
    )
    dp_method: DPMethod = Field(default=DPMethod.SIMPLE)
    cr_method: CRMethod = CRMethod.NONE
    yield_params: YieldParams | None = Field(
        default=None, description="Stewart yield model parameters"
    )
    salinity: SalinityParams | None = Field(default=None, description="Salinity stress parameters")
    mulch: MulchParams | None = Field(default=None, description="Mulch surface cover parameters")

    @field_validator("climate")
    @classmethod
    def _climate_not_empty(cls, v: list[ClimateRecord]) -> list[ClimateRecord]:
        if not v:
            msg = "climate must contain at least one record"
            raise ValueError(msg)
        return v

    @field_validator("climate")
    @classmethod
    def _climate_sorted(cls, v: list[ClimateRecord]) -> list[ClimateRecord]:
        dates = [r.date for r in v]
        if dates != sorted(dates):
            msg = "climate records must be in chronological order"
            raise ValueError(msg)
        return v


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class DailyResult(BaseModel):
    """All computed outputs for a single simulation day.

    Attributes:
        date: Calendar date.
        day_of_sim: Sequential day index (1-based).
        stage: FAO phenological stage (1=ini, 2=dev, 3=mid, 4=late).
        eto: Reference ET from input [mm].
        precip: Precipitation from input [mm].
        irrig: Net irrigation applied on this day [mm].
        ro: Surface runoff (Curve Number) [mm].
        kcb: Adjusted basal crop coefficient [—].
        ke: Total soil evaporation coefficient [—].
        kei: Ke — irrigated fraction [—].
        kep: Ke — precipitation-only fraction [—].
        ks: Water stress coefficient [—].
        kc_max: Upper bound for Kc [—].
        etc_act: Actual crop ET = (Ks·Kcb + Ke)·ETo [mm].
        transp_act: Actual transpiration = Ks·Kcb·ETo [mm].
        evap_act: Actual soil evaporation = Ke·ETo [mm].
        dr: Root-zone depletion at end of day [mm].
        dei: Surface layer depletion — irrigated fraction [mm].
        dep: Surface layer depletion — precip-only fraction [mm].
        dp: Deep percolation below root zone [mm].
        dp_ei: Deep percolation from surface evaporative layer (irrigated) [mm].
        dp_ep: Deep percolation from surface evaporative layer (precip) [mm].
        cr: Capillary rise [mm].
        taw: Total available water for current root depth [mm].
        raw: Readily available water [mm].
        zr: Root depth on this day [m].
        fc: Fractional cover on this day [—].
        h: Plant height on this day [m].
        p: Depletion fraction for no stress on this day [—].
    """

    date: datetime.date
    day_of_sim: int
    stage: int

    eto: float
    precip: float
    irrig: float
    ro: float

    kcb: float
    ke: float
    kei: float
    kep: float
    ks: float
    kc_max: float

    etc_act: float
    transp_act: float
    evap_act: float

    dr: float
    dei: float
    dep: float
    dp: float
    dp_ei: float
    dp_ep: float
    cr: float

    taw: float
    raw: float
    zr: float
    fc: float
    h: float
    p: float


class SimulationResult(BaseModel):
    """Container for the full simulation output.

    Attributes:
        daily_results: List of daily time-step results.
        yield_act: Actual crop yield [kg/ha] computed via Stewart model
            (if `yield_params` provided).
        yield_decrease_pct: Percentage yield decrease due to water stress [%]
            (if `yield_params` provided).
    """

    daily_results: list[DailyResult]
    yield_act: float | None = None
    yield_decrease_pct: float | None = None

    if TYPE_CHECKING:
        import pandas as pd

    def to_dataframe(self) -> pd.DataFrame:
        """Convert daily results to a pandas DataFrame (one row per day)."""
        import pandas as pd

        return pd.DataFrame([r.model_dump() for r in self.daily_results])

    @property
    def n_days(self) -> int:
        """Number of simulated days."""
        return len(self.daily_results)


# Avoid circular import from type hint string annotation above
import pandas as pd  # noqa: E402, F401  (needed for the type hint at runtime)
