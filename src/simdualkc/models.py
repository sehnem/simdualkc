"""Pydantic domain models for SIMDualKc Layer 1.

All models perform strict validation at construction time so that
downstream equation functions can assume clean, physically-plausible inputs.
"""

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal

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


class SoilLayer(BaseModel):
    """Single layer in a stratified soil profile.

    Layers are ordered by depth; each layer's depth_m is the bottom depth [m].
    The first layer extends from 0 to depth_m; subsequent layers from the
    previous layer's depth to this layer's depth.

    Attributes:
        depth_m: Bottom depth of layer [m] (top of layer is previous layer's bottom or 0).
        theta_fc: Volumetric water content at field capacity [m³/m³].
        theta_wp: Volumetric water content at wilting point [m³/m³].
        sand_pct: Optional sand percentage for pedotransfer functions.
        clay_pct: Optional clay percentage for pedotransfer functions.
    """

    depth_m: float = Field(gt=0.0, description="Bottom depth of layer [m]")
    theta_fc: float = Field(gt=0.0, lt=1.0, description="Field capacity [m³/m³]")
    theta_wp: float = Field(gt=0.0, lt=1.0, description="Wilting point [m³/m³]")
    sand_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    clay_pct: float | None = Field(default=None, ge=0.0, le=100.0)

    @model_validator(mode="after")
    def _theta_order(self) -> "SoilLayer":
        if self.theta_wp >= self.theta_fc:
            msg = "theta_wp must be less than theta_fc"
            raise ValueError(msg)
        return self


class SoilParams(BaseModel):
    """Soil hydraulic and surface properties.

    Supports either single-layer (theta_fc, theta_wp) or multi-layer (layers).
    When layers is provided and non-empty, multi-layer TAW is used; otherwise
    theta_fc and theta_wp define a uniform root zone.

    Attributes:
        theta_fc: Volumetric soil water content at field capacity [m³/m³].
            Used when layers is None.
        theta_wp: Volumetric soil water content at wilting point [m³/m³].
            Used when layers is None.
        layers: Up to 5 soil layers for stratified profiles. When provided,
            overrides theta_fc/theta_wp for TAW computation.
        ze: Depth of the surface evaporative layer [m].  Typically 0.10–0.15 m.
        rew: Readily evaporable water [mm].  Stage-1 evaporation capacity.
        tew: Total evaporable water [mm].  Maximum water extractable by evaporation.
        cn2: SCS Curve Number for average antecedent moisture conditions (AMC II).
        a_d: Parametric drainage coefficient *a* (Liu et al 2006) [—].
            Required when ``dp_method=DPMethod.PARAMETRIC``.
        b_d: Parametric drainage exponent *b* (Liu et al. 2006) [—].
            Required when ``dp_method=DPMethod.PARAMETRIC``.
        gmax: Maximum daily capillary rise rate [mm/day].
            Required when ``cr_method=CRMethod.CONSTANT``.
    """

    theta_fc: float = Field(gt=0.0, lt=1.0, description="Field capacity [m³/m³]")
    theta_wp: float = Field(gt=0.0, lt=1.0, description="Wilting point [m³/m³]")
    layers: list[SoilLayer] | None = Field(default=None, max_length=5)
    ze: float = Field(default=0.10, gt=0.0, le=0.30, description="Evaporative layer depth [m]")
    rew: float = Field(gt=0.0, description="Readily evaporable water [mm]")
    tew: float = Field(gt=0.0, description="Total evaporable water [mm]")
    cn2: float = Field(default=75.0, ge=1.0, le=100.0, description="Curve Number, AMC II")
    a_d: float | None = Field(default=None, description="Drainage coefficient a (Liu 2006)")
    b_d: float | None = Field(default=None, description="Drainage exponent b (Liu 2006)")
    gmax: float | None = Field(default=None, ge=0.0, description="Max capillary rise [mm/day]")
    cr_a1: float | None = Field(default=None, description="Liu CR param a1")
    cr_b1: float | None = Field(default=None, description="Liu CR param b1")
    cr_a2: float | None = Field(default=None, description="Liu CR param a2")
    cr_b2: float | None = Field(default=None, description="Liu CR param b2")
    cr_a3: float | None = Field(default=None, description="Liu CR param a3")
    cr_b3: float | None = Field(default=None, description="Liu CR param b3")
    cr_a4: float | None = Field(default=None, description="Liu CR param a4")
    cr_b4: float | None = Field(default=None, description="Liu CR param b4")
    cr_simplified_a: float | None = Field(default=None, description="Simplified Liu CR param a")
    cr_simplified_b: float | None = Field(default=None, description="Simplified Liu CR param b")
    cr_simplified_c: float | None = Field(default=None, description="Simplified Liu CR param c")
    cr_simplified_d: float | None = Field(default=None, description="Simplified Liu CR param d")

    @model_validator(mode="after")
    def _theta_order(self) -> "SoilParams":
        if self.theta_wp >= self.theta_fc:
            msg = "theta_wp must be less than theta_fc"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _tew_rew_order(self) -> "SoilParams":
        if self.rew >= self.tew:
            msg = "rew must be less than tew"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _layers_ordered(self) -> "SoilParams":
        if self.layers:
            depths = [layer.depth_m for layer in self.layers]
            if depths != sorted(depths):
                msg = "layers must be ordered by increasing depth_m"
                raise ValueError(msg)
        return self

    def uses_multilayer(self) -> bool:
        """Return True if this soil uses multi-layer TAW computation."""
        return bool(self.layers)


# ---------------------------------------------------------------------------
# Crop
# ---------------------------------------------------------------------------


class ForageCutCycle(BaseModel):
    """A single cutting cycle within a forage crop season.

    Attributes:
        stage_lengths: Four-element list [ini, dev, mid, late] day-counts for this cycle.
        cut_date: Calendar date on which the cut occurs (last day of the cycle).
    """

    stage_lengths: list[int] = Field(min_length=4, max_length=4)
    cut_date: datetime.date

    @field_validator("stage_lengths")
    @classmethod
    def _positive_stages(cls, v: list[int]) -> list[int]:
        if any(d <= 0 for d in v):
            msg = "All stage lengths must be positive integers"
            raise ValueError(msg)
        return v


class ForageParams(BaseModel):
    """Crop-level parameters for forage multi-cut simulation.

    Defines the Kcb, fc, root depth, and height envelope that each
    cutting cycle follows.  Individual cycles may have different stage
    durations (provided via cycles).

    Attributes:
        start_date: Calendar date the forage season begins (first planting).
        num_cuts: Number of cutting cycles in the season.
        max_height_m: Maximum plant height at peak growth [m].
        min_root_m: Root depth immediately after a cut [m].
        max_root_m: Maximum root depth reached during regrowth [m].
        days_to_max_root: Days from cut to reach ForagMaxRoot.
        p_fraction: Soil water depletion fraction for no stress [—].
        fc_start: Fraction cover at the start of each cycle [0–1].
        fc_peak: Fraction cover at mid-season peak [0–1].
        fc_before: Fraction cover just before cutting [0–1].
        fc_after: Fraction cover immediately after cutting [0–1].
        kcb_start: Kcb at the start of regrowth [—].
        kcb_peak: Kcb at mid-season peak [—].
        kcb_before: Kcb just before cutting [—].
        kcb_after: Kcb immediately after cutting [—].
        min_height_m: Plant height immediately after a cut [m].
        cycles: The sequence of cutting cycles with per-cycle durations and dates.
    """

    start_date: datetime.date
    num_cuts: int = Field(ge=1, le=20)
    max_height_m: float = Field(gt=0.0, le=20.0)
    min_root_m: float = Field(gt=0.0, le=3.0)
    max_root_m: float = Field(gt=0.0, le=3.0)
    days_to_max_root: int = Field(ge=1)
    p_fraction: float = Field(gt=0.0, lt=1.0)
    fc_start: float = Field(ge=0.0, le=1.0)
    fc_peak: float = Field(ge=0.0, le=1.0)
    fc_before: float = Field(ge=0.0, le=1.0)
    fc_after: float = Field(ge=0.0, le=1.0)
    kcb_start: float = Field(ge=0.0, le=3.0)
    kcb_peak: float = Field(ge=0.0, le=3.0)
    kcb_before: float = Field(ge=0.0, le=3.0)
    kcb_after: float = Field(ge=0.0, le=3.0)
    min_height_m: float = Field(ge=0.0, le=20.0)
    cycles: list[ForageCutCycle] = Field(min_length=1)

    @model_validator(mode="after")
    def _cycle_order(self) -> "ForageParams":
        dates = [c.cut_date for c in self.cycles]
        if dates != sorted(dates):
            msg = "forage cycles must be ordered by increasing cut_date"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _consistent_counts(self) -> "ForageParams":
        if len(self.cycles) != self.num_cuts:
            msg = f"cycles count ({len(self.cycles)}) must match num_cuts ({self.num_cuts})"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _fc_order(self) -> "ForageParams":
        if self.fc_after > self.fc_start:
            msg = "fc_after must be <= fc_start (cover after cut <= cover at regrowth start)"
            raise ValueError(msg)
        return self


class CropParams(BaseModel):
    """Tabulated crop parameters for the four FAO-56 growth stages.

    Stage lengths are provided as a list of four integer day-counts:
    [ini, dev, mid, late].  The simulation interpolates Kcb linearly
    through ini and dev, holds it constant at mid, then interpolates
    through late.

    For forage crops (``is_forage=True``), growth is governed by cut
    cycles and the standard stage_lengths / Kcb values are ignored in
    favour of :class:`ForageParams`.

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
        lai_values: Optional LAI at specific dates (alternative to fc_max).
        lai_dates: Dates corresponding to lai_values (must match length).
        k_ext: Light extinction coefficient for LAI→fc (0.5–0.7, default 0.6).
        is_forage: If True, forage multi-cut mode is active.
        forage_params: Forage-specific parameters (required if is_forage).
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
    lai_values: list[float] | None = Field(default=None, description="LAI at lai_dates")
    lai_dates: list[datetime.date] | None = Field(default=None, description="Dates for LAI")
    k_ext: float = Field(default=0.6, ge=0.5, le=0.7, description="Light extinction coef")
    is_forage: bool = Field(default=False, description="Enable forage multi-cut mode")
    forage_params: ForageParams | None = Field(
        default=None, description="Forage parameters (required if is_forage=True)"
    )

    @field_validator("stage_lengths")
    @classmethod
    def _positive_stages(cls, v: list[int]) -> list[int]:
        if any(d <= 0 for d in v):
            msg = "All stage lengths must be positive integers"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _lai_consistency(self) -> "CropParams":
        if (self.lai_values is None) != (self.lai_dates is None):
            msg = "lai_values and lai_dates must both be provided or both be None"
            raise ValueError(msg)
        if (
            self.lai_values is not None
            and self.lai_dates is not None
            and len(self.lai_values) != len(self.lai_dates)
        ):
            msg = "lai_values and lai_dates must have the same length"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _forage_consistency(self) -> "CropParams":
        if self.is_forage and self.forage_params is None:
            msg = "forage_params is required when is_forage=True"
            raise ValueError(msg)
        return self

    def uses_lai(self) -> bool:
        """Return True if LAI-based fraction cover should be used."""
        return bool(self.lai_values and self.lai_dates)


# ---------------------------------------------------------------------------
# Climate & Weather
# ---------------------------------------------------------------------------


class WeatherRecord(BaseModel):
    """Raw weather data for ETo calculation via FAO-56 Penman-Monteith.

    Use :func:`simdualkc.eto.compute_eto` or :func:`simdualkc.eto.weather_to_climate_records`
    to convert to ETo / ClimateRecord.

    Attributes:
        date: Calendar date.
        t_max: Maximum temperature [°C].
        t_min: Minimum temperature [°C].
        rh_max: Maximum relative humidity [%].
        rh_min: Minimum relative humidity [%].
        rs: Solar radiation [MJ/m²/day].
        u2: Wind speed at 2 m height [m/s].
        precip: Precipitation [mm], default 0.
    """

    date: datetime.date
    t_max: float = Field(description="Max temperature [°C]")
    t_min: float = Field(description="Min temperature [°C]")
    rh_max: float = Field(ge=0.0, le=100.0, description="Max relative humidity [%]")
    rh_min: float = Field(ge=0.0, le=100.0, description="Min relative humidity [%]")
    rs: float = Field(ge=0.0, description="Solar radiation [MJ/m²/day]")
    u2: float = Field(ge=0.0, description="Wind speed at 2 m [m/s]")
    precip: float = Field(default=0.0, ge=0.0, description="Precipitation [mm]")


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
    wt_depth_m: float | None = Field(
        default=None, ge=0.0, description="Water table depth from surface [m]"
    )


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


class IrrigationIntervalPeriod(BaseModel):
    """A date range with a minimum interval between irrigation events.

    Used for rotational delivery schedules where the minimum days between
    irrigations changes by season (e.g. every 15 days early, every 5 days mid).

    Attributes:
        start_date: First day of the period (inclusive).
        end_date: Last day of the period (inclusive).
        min_interval_days: Minimum days between irrigation events in this period.
    """

    start_date: datetime.date
    end_date: datetime.date
    min_interval_days: int = Field(ge=1, description="Min days between events")

    @model_validator(mode="after")
    def _date_order(self) -> "IrrigationIntervalPeriod":
        if self.start_date > self.end_date:
            msg = "start_date must not be after end_date"
            raise ValueError(msg)
        return self


class FarmPondSupply(BaseModel):
    """A water supply event that refills the on-farm pond.

    Attributes:
        date: Date the supply becomes available.
        depth_mm: Depth of water added to the pond [mm].
    """

    date: datetime.date
    depth_mm: float = Field(gt=0.0, description="Supply depth [mm]")


class FarmPondConstraint(BaseModel):
    """Finite on-farm water supply that limits total irrigation.

    Attributes:
        initial_storage_mm: Water in the pond at the start of the season [mm].
        supplies: Optional list of refill events during the season.
        max_storage_mm: Optional maximum pond capacity [mm].
    """

    initial_storage_mm: float = Field(ge=0.0, description="Initial pond storage [mm]")
    supplies: list[FarmPondSupply] = Field(default_factory=list)
    max_storage_mm: float | None = Field(
        default=None, gt=0.0, description="Maximum pond capacity [mm]"
    )

    @model_validator(mode="after")
    def _storage_capacity(self) -> "FarmPondConstraint":
        if self.max_storage_mm is not None and self.initial_storage_mm > self.max_storage_mm:
            msg = "initial_storage_mm must not exceed max_storage_mm"
            raise ValueError(msg)
        return self


_VALID_STAGES: frozenset = frozenset({"ini", "dev", "mid", "late"})


class DeliveryConstraints(BaseModel):
    """Optional delivery-side constraints on automated irrigation.

    These constraints are applied *after* the MAD/deficit trigger decides
    that irrigation is needed, and *before* the water is applied to the soil.

    Attributes:
        interval_schedule: Date-range-specific minimum intervals. If the
            current date falls within a range, that range's interval overrides
            the strategy's base min_interval_days.
        max_depth_mm: Maximum irrigation depth per event [mm]. Computed depth
            is capped to this value.
        fixed_depth_mm: If set, irrigation depth is fixed to this value
            regardless of soil depletion. Overrides stage_fixed_depth_mm.
        stage_fixed_depth_mm: Per-stage fixed depths keyed "ini", "dev",
            "mid", "late". Used only when fixed_depth_mm is not set.
        stage_target_pct_taw: Per-stage refill targets keyed "ini", "dev",
            "mid", "late". Overrides the strategy's base target_pct_taw.
        farm_pond: On-farm pond supply that limits cumulative irrigation.
    """

    interval_schedule: list[IrrigationIntervalPeriod] | None = Field(default=None)
    max_depth_mm: float | None = Field(default=None, gt=0.0)
    fixed_depth_mm: float | None = Field(default=None, gt=0.0)
    stage_fixed_depth_mm: dict[str, float] | None = Field(default=None)
    stage_target_pct_taw: dict[str, float] | None = Field(default=None)
    farm_pond: FarmPondConstraint | None = Field(default=None)

    @field_validator("stage_fixed_depth_mm", "stage_target_pct_taw")
    @classmethod
    def _stage_dict_keys(cls, v: dict[str, float] | None) -> dict[str, float] | None:
        if v is not None:
            invalid = set(v.keys()) - _VALID_STAGES
            if invalid:
                msg = f"Invalid stage keys: {invalid}. Must be subset of {_VALID_STAGES}"
                raise ValueError(msg)
        return v

    @field_validator("stage_fixed_depth_mm")
    @classmethod
    def _fixed_depth_values(cls, v: dict[str, float] | None) -> dict[str, float] | None:
        if v is not None and any(val <= 0.0 for val in v.values()):
            msg = "All stage_fixed_depth_mm values must be > 0.0"
            raise ValueError(msg)
        return v

    @field_validator("stage_target_pct_taw")
    @classmethod
    def _target_pct_values(cls, v: dict[str, float] | None) -> dict[str, float] | None:
        if v is not None and any(not (0.0 <= val <= 100.0) for val in v.values()):
            msg = "All stage_target_pct_taw values must be in [0.0, 100.0]"
            raise ValueError(msg)
        return v


class MADThresholdStrategy(BaseModel):
    """Management Allowed Depletion threshold strategy.

    Automatically triggers irrigation when root zone depletion exceeds
    MAD × TAW. Refills to target percentage of TAW.

    Attributes:
        mad_fraction: Irrigation trigger when Dr >= mad_fraction × TAW [0–1].
        target_pct_taw: Refill target as % of TAW (100 = full, <100 = deficit).
        days_before_harvest_stop: Stop irrigating N days before harvest.
        min_interval_days: Minimum days between irrigation events.
    """

    mad_fraction: float = Field(ge=0.0, le=1.0, description="MAD trigger fraction")
    target_pct_taw: float = Field(
        ge=0.0, le=100.0, default=100.0, description="Refill target % TAW"
    )
    days_before_harvest_stop: int = Field(
        ge=0, default=0, description="Stop irrigation N days before harvest"
    )
    min_interval_days: int = Field(ge=1, default=1, description="Min days between events")
    delivery: DeliveryConstraints | None = Field(
        default=None, description="Optional delivery-side constraints"
    )


class DeficitIrrigationStrategy(BaseModel):
    """Controlled deficit irrigation with stage-specific MAD.

    Attributes:
        stage_mad: MAD fraction by stage key ("ini", "dev", "mid", "late").
        target_pct_taw: Refill target % TAW.
        days_before_harvest_stop: Stop irrigation N days before harvest.
    """

    stage_mad: dict[str, float] = Field(description="MAD by growth stage")

    @field_validator("stage_mad")
    @classmethod
    def _validate_stage_mad(cls, v: dict[str, float]) -> dict[str, float]:
        invalid_keys = set(v.keys()) - _VALID_STAGES
        if invalid_keys:
            msg = f"Invalid stage keys: {invalid_keys}. Must be subset of {_VALID_STAGES}"
            raise ValueError(msg)
        if any(not (0.0 <= val <= 1.0) for val in v.values()):
            msg = "All stage_mad values must be in [0.0, 1.0]"
            raise ValueError(msg)
        return v

    target_pct_taw: float = Field(ge=0.0, le=100.0, default=100.0)
    days_before_harvest_stop: int = Field(ge=0, default=0)
    min_interval_days: int = Field(ge=1, default=1, description="Min days between events")
    delivery: DeliveryConstraints | None = Field(
        default=None, description="Optional delivery-side constraints"
    )


class IrrigationStrategy(BaseModel):
    """Irrigation scheduling strategy.

    When strategy_type is "manual", only pre-scheduled IrrigationEvents apply.
    When "mad_threshold" or "deficit", automated scheduling adds events.
    """

    strategy_type: Literal["manual", "mad_threshold", "deficit"] = "manual"
    mad_threshold: MADThresholdStrategy | None = None
    deficit: DeficitIrrigationStrategy | None = None


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


class GroundcoverParams(BaseModel):
    """Active groundcover (grass, weeds) competing with main crop.

    Used in orchards/vineyards where inter-row vegetation affects Kcb.
    Combines main crop and groundcover Kcb per FAO-56 Eq. 11-12.

    Attributes:
        kcb_cover: Kcb of groundcover for non-shaded soil [—].
        fc_cover: Fraction of ground covered by vegetation [0–1].
        h_cover: Height of groundcover [m].
    """

    kcb_cover: float = Field(ge=0.0, le=1.5, description="Kcb of groundcover")
    fc_cover: float = Field(ge=0.0, le=1.0, description="Groundcover fraction")
    h_cover: float = Field(ge=0.0, le=1.0, description="Groundcover height [m]")


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
    irrigation_strategy: IrrigationStrategy = Field(
        default_factory=lambda: IrrigationStrategy(),
        description="Automated irrigation scheduling strategy",
    )
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
    groundcover: GroundcoverParams | None = Field(
        default=None, description="Active groundcover parameters"
    )

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

    @model_validator(mode="after")
    def _cr_parametric_consistency(self) -> "SimulationConfig":
        if self.cr_method == CRMethod.PARAMETRIC:
            soil = self.soil
            has_full = all(
                getattr(soil, f"cr_{name}") is not None
                for name in ["a1", "b1", "a2", "b2", "a3", "b3", "a4", "b4"]
            )
            has_simplified = all(
                getattr(soil, f"cr_simplified_{name}") is not None for name in ["a", "b", "c", "d"]
            )
            if not has_full and not has_simplified:
                msg = (
                    "Parametric CR requires either all 8 full coefficients (cr_a1..cr_b4) "
                    "or all 4 simplified coefficients (cr_simplified_a..cr_simplified_d) on soil"
                )
                raise ValueError(msg)
            if not any(r.wt_depth_m is not None for r in self.climate):
                msg = "Parametric CR requires at least one ClimateRecord with wt_depth_m not None"
                raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Summary models
# ---------------------------------------------------------------------------


class StressSummary(BaseModel):
    """Seasonal stress accumulation summary."""

    total_transp_pot: float
    total_transp_act: float
    total_transp_deficit: float
    transp_deficit_pct: float
    days_with_stress: int
    days_severe_stress: int
    yield_decrease_water_pct: float
    yield_decrease_salinity_pct: float | None = None
    yield_decrease_total_pct: float


class IrrigationSummary(BaseModel):
    """Seasonal irrigation performance metrics."""

    total_irrigation: float
    total_precip: float
    total_etc_act: float
    total_etc_pot: float
    eta_etm_ratio: float
    irrigation_efficiency: float
    avg_pct_taw: float
    avg_pct_raw: float


class SimulationSummary(BaseModel):
    """Complete seasonal summary."""

    stress: StressSummary
    irrigation: IrrigationSummary
    n_days: int
    start_date: datetime.date
    end_date: datetime.date


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
        summary: Seasonal summary (stress, irrigation metrics).
    """

    daily_results: list[DailyResult]
    yield_act: float | None = None
    yield_decrease_pct: float | None = None
    summary: SimulationSummary | None = None

    if TYPE_CHECKING:
        import pandas as pd

    def to_dataframe(self) -> "pd.DataFrame":
        """Convert daily results to a pandas DataFrame (one row per day)."""

        return pd.DataFrame([r.model_dump() for r in self.daily_results])

    @property
    def n_days(self) -> int:
        """Number of simulated days."""
        return len(self.daily_results)


# Avoid circular import from type hint string annotation above
import pandas as pd  # noqa: E402, F401  (needed for the type hint at runtime)
