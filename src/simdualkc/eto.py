"""FAO-56 Penman-Monteith reference evapotranspiration (ETo) calculator.

Implements the standard FAO-56 equation for computing ETo from raw weather data.
Reference: Allen et al. (1998) FAO Irrigation and Drainage Paper 56.
"""

import datetime
import math


def compute_saturation_vapor_pressure(t: float) -> float:
    """Compute saturation vapor pressure at temperature T.

    e°(T) = 0.6108 × exp(17.27×T / (T + 237.3))

    Args:
        t: Air temperature [°C].

    Returns:
        Saturation vapor pressure [kPa].
    """
    return 0.6108 * math.exp(17.27 * t / (t + 237.3))


def compute_actual_vapor_pressure(
    t_max: float,
    t_min: float,
    rh_max: float,
    rh_min: float,
) -> float:
    """Compute actual vapor pressure from max/min temperature and humidity.

    ea = (e°(Tmin)×RHmax/100 + e°(Tmax)×RHmin/100) / 2

    This is the FAO-56 preferred method when RHmax and RHmin are available.

    Args:
        t_max: Daily maximum temperature [°C].
        t_min: Daily minimum temperature [°C].
        rh_max: Daily maximum relative humidity [%].
        rh_min: Daily minimum relative humidity [%].

    Returns:
        Actual vapor pressure [kPa].
    """
    e_min = compute_saturation_vapor_pressure(t_min)
    e_max = compute_saturation_vapor_pressure(t_max)
    return (e_min * rh_max / 100.0 + e_max * rh_min / 100.0) / 2.0


def compute_slope_vapor_pressure_curve(t: float) -> float:
    """Compute slope of saturation vapor pressure curve.

    Δ = 4098 × e°(T) / (T + 237.3)²

    Args:
        t: Mean air temperature [°C].

    Returns:
        Slope [kPa/°C].
    """
    e = compute_saturation_vapor_pressure(t)
    return 4098.0 * e / (t + 237.3) ** 2


def compute_psychrometric_constant(elevation: float) -> float:
    """Compute psychrometric constant from elevation.

    γ = 0.000665 × P

    where P = 101.3 × ((293 - 0.0065×z) / 293)^5.26

    Args:
        elevation: Site elevation above sea level [m].

    Returns:
        Psychrometric constant [kPa/°C].
    """
    p = 101.3 * ((293.0 - 0.0065 * elevation) / 293.0) ** 5.26
    return 0.000665 * p


def compute_extraterrestrial_radiation(latitude: float, day_of_year: int) -> float:
    """Compute extraterrestrial radiation for horizontal surface.

    Ra = (24×60/π) × Gsc × dr × [ωs×sin(φ)×sin(δ) + cos(φ)×cos(δ)×sin(ωs)]

    Simplified per FAO-56 Eq. 21.

    Args:
        latitude: Site latitude [degrees] (positive north, negative south).
        day_of_year: Day of year [1-366].

    Returns:
        Extraterrestrial radiation [MJ/m²/day].
    """
    phi = math.radians(latitude)
    j = day_of_year

    # Solar declination (Eq. 24)
    delta = 0.409 * math.sin(2 * math.pi * j / 365 - 1.39)

    # Inverse relative distance Earth-Sun (Eq. 23)
    dr = 1 + 0.033 * math.cos(2 * math.pi * j / 365)

    # Sunset hour angle (Eq. 25)
    omega_s = math.acos(-math.tan(phi) * math.tan(delta))

    # Solar constant = 0.0820 MJ/(m²·min)
    gsc = 0.0820
    ra = (
        (24.0 * 60.0 / math.pi)
        * gsc
        * dr
        * (
            omega_s * math.sin(phi) * math.sin(delta)
            + math.cos(phi) * math.cos(delta) * math.sin(omega_s)
        )
    )
    return max(0.0, ra)


def compute_net_radiation(
    rs: float,
    t_max: float,
    t_min: float,
    ea: float,
    latitude: float,
    day_of_year: int,
    elevation: float = 0.0,
) -> float:
    """Compute net radiation at crop surface.

    Rn = Rns - Rnl

    where Rns = (1 - α)×Rs and Rnl is net outgoing longwave radiation.

    Args:
        rs: Incoming solar radiation [MJ/m²/day].
        t_max: Daily maximum temperature [°C].
        t_min: Daily minimum temperature [°C].
        ea: Actual vapor pressure [kPa].
        latitude: Site latitude [degrees].
        day_of_year: Day of year [1-366].
        elevation: Site elevation [m] for clear-sky radiation.

    Returns:
        Net radiation [MJ/m²/day].
    """
    # Albedo for grass reference = 0.23
    alpha = 0.23
    rns = (1.0 - alpha) * rs

    # Net outgoing longwave radiation (Eq. 39)
    sigma = 4.903e-9  # MJ/(K⁴·m²·day)
    t_max_k = t_max + 273.16
    t_min_k = t_min + 273.16

    ra = compute_extraterrestrial_radiation(latitude, day_of_year)
    rso = (0.75 + 2e-5 * elevation) * ra
    if rso <= 0.0:
        rso = 0.0001
    r_s_rso = min(1.0, rs / rso)

    rnl = (
        sigma
        * ((t_max_k**4 + t_min_k**4) / 2.0)
        * (0.34 - 0.14 * math.sqrt(ea))
        * (1.35 * r_s_rso - 0.35)
    )

    rn = rns - rnl
    return max(0.0, rn)


def compute_eto(
    t_max: float,
    t_min: float,
    rh_max: float,
    rh_min: float,
    rs: float,
    u2: float,
    latitude: float,
    elevation: float,
    date: datetime.date,
) -> float:
    """Compute reference evapotranspiration (ETo) using FAO-56 Penman-Monteith.

    ETo = [0.408Δ(Rn - G) + γ(900/(T+273))u2(es - ea)] / [Δ + γ(1 + 0.34u2)]

    Args:
        t_max: Daily maximum temperature [°C].
        t_min: Daily minimum temperature [°C].
        rh_max: Daily maximum relative humidity [%].
        rh_min: Daily minimum relative humidity [%].
        rs: Solar radiation [MJ/m²/day].
        u2: Wind speed at 2 m height [m/s].
        latitude: Site latitude [degrees] (positive north, negative south).
        elevation: Site elevation above sea level [m].
        date: Calendar date (for day of year).

    Returns:
        ETo [mm/day].
    """
    t_mean = (t_max + t_min) / 2.0
    day_of_year = date.timetuple().tm_yday

    # Soil heat flux G = 0 for daily time step (FAO-56)
    g = 0.0

    # Saturation vapor pressure
    es = (
        compute_saturation_vapor_pressure(t_max) + compute_saturation_vapor_pressure(t_min)
    ) / 2.0

    # Actual vapor pressure
    ea = compute_actual_vapor_pressure(t_max, t_min, rh_max, rh_min)

    # Slope of saturation vapor pressure curve
    delta = compute_slope_vapor_pressure_curve(t_mean)

    # Psychrometric constant
    gamma = compute_psychrometric_constant(elevation)

    # Net radiation
    rn = compute_net_radiation(rs, t_max, t_min, ea, latitude, day_of_year, elevation)

    # Penman-Monteith numerator and denominator
    numerator = 0.408 * delta * (rn - g) + gamma * (900.0 / (t_mean + 273.0)) * u2 * (es - ea)
    denominator = delta + gamma * (1.0 + 0.34 * u2)

    if denominator <= 0.0:
        return 0.0

    eto = numerator / denominator
    return max(0.0, eto)


def weather_to_climate_records(
    weather: list[dict] | list,
    latitude: float,
    elevation: float = 0.0,
) -> list:
    """Convert raw weather data to ClimateRecord list with computed ETo.

    Accepts list of dicts with keys: date, t_max, t_min, rh_max, rh_min, rs, u2,
    precip (optional). Also accepts list of WeatherRecord objects.

    Args:
        weather: List of daily weather dicts or WeatherRecord.
        latitude: Site latitude [degrees].
        elevation: Site elevation [m], default 0.

    Returns:
        List of ClimateRecord objects with computed ETo.
    """
    from simdualkc.models import ClimateRecord, WeatherRecord

    result: list = []
    for w in weather:
        if isinstance(w, WeatherRecord):
            wr = w
        else:
            wr = WeatherRecord(
                date=w["date"],
                t_max=w["t_max"],
                t_min=w["t_min"],
                rh_max=w["rh_max"],
                rh_min=w["rh_min"],
                rs=w["rs"],
                u2=w["u2"],
                precip=w.get("precip", 0.0),
            )
        eto = compute_eto(
            t_max=wr.t_max,
            t_min=wr.t_min,
            rh_max=wr.rh_max,
            rh_min=wr.rh_min,
            rs=wr.rs,
            u2=wr.u2,
            latitude=latitude,
            elevation=elevation,
            date=wr.date,
        )
        result.append(
            ClimateRecord(
                date=wr.date,
                eto=eto,
                precip=wr.precip,
                u2=wr.u2,
                rh_min=wr.rh_min,
            )
        )
    return result
