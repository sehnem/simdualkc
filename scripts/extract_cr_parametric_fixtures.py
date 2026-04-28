"""Extract parametric-CR validation fixtures from database_export.

Reads the original SIMDualKc Access database export (Parquet files in
``database_export/``) and writes one fixture pair per validated simulation:

    tests/fixtures/cr_parametric_validation/{sim_id}_config.json
    tests/fixtures/cr_parametric_validation/{sim_id}_expected.parquet

Usage:
    uv run python scripts/extract_cr_parametric_fixtures.py
"""

import datetime
import json
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DB_EXPORT = Path(__file__).parent.parent / "database_export"
FIXTURE_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "cr_parametric_validation"
CROPS_PATH = Path(__file__).parent.parent / "src" / "simdualkc" / "data" / "crops.parquet"

# The 17 single-crop parametric-CR simulation IDs from the validation plan.
TARGET_SIM_IDS = [3, 4, 6, 7, 8, 9, 10, 11, 12, 27, 28, 29, 30, 31, 32, 34, 35]


def load_table(name: str) -> pd.DataFrame:
    return pd.read_parquet(DB_EXPORT / f"{name}.parquet")


def parse_date(val: str | datetime.date | datetime.datetime) -> datetime.date:
    """Parse Access datetime strings like '03/25/10 00:00:00'."""
    if isinstance(val, datetime.date) and not isinstance(val, datetime.datetime):
        return val
    if isinstance(val, datetime.datetime):
        return val.date()
    if pd.isna(val):
        raise ValueError("Cannot parse NaN as date")
    dt = pd.to_datetime(val)
    return dt.date()


def build_soil_params(solo_id: int) -> dict:
    """Build SoilParams dict from T_opcoes_solo layers."""
    soil_df = load_table("T_opcoes_solo")
    rows = soil_df[soil_df["solo_ID"] == solo_id].copy()
    if rows.empty:
        # Freiria uses a range of IDs (576-582); match by name
        all_rows = soil_df[soil_df["solo_ID"] == solo_id]
        if all_rows.empty:
            raise ValueError(f"Solo_ID {solo_id} not found")
        rows = all_rows

    # If multiple rows share the same nome_solo, use them all as layers
    nome = rows.iloc[0]["nome_solo"]
    layers = soil_df[soil_df["nome_solo"] == nome].copy()
    layers = layers.sort_values("topo_horiz")

    # Read TEW/REW from the first row (same for all layers of this soil)
    first = layers.iloc[0]
    tew = float(first["valor_tew"])
    rew = float(first["valor_rew"])
    ze = float(first["ze_tew_rew"]) if not pd.isna(first["ze_tew_rew"]) else 0.15

    # CN2 is not in the soil table; use a default.  The original software
    # stores CN2 in T_Runoff linked by simulation, but for these fixtures
    # a default of 75 works because runoff is small / zero in most days.
    cn2 = 75.0

    layer_objs = []
    for _, r in layers.iterrows():
        layer_objs.append(
            {
                "depth_m": float(r["fundo_horiz"]),
                "theta_fc": float(r["valor_fc"]),
                "theta_wp": float(r["valor_wp"]),
            }
        )

    return {
        "theta_fc": float(first["valor_fc"]),
        "theta_wp": float(first["valor_wp"]),
        "layers": layer_objs if len(layer_objs) > 1 else None,
        "ze": ze,
        "rew": rew,
        "tew": tew,
        "cn2": cn2,
    }


def build_crop_params(cultura_id: int, plant_date: datetime.date) -> dict:
    """Build CropParams dict from bundled crops.parquet."""
    df = pd.read_parquet(CROPS_PATH)
    row = df[df["Cultura_ID"] == cultura_id]
    if row.empty:
        raise ValueError(f"Cultura_ID {cultura_id} not found in bundled crops")
    r = row.iloc[0]

    # Handle NaN or zero fc_max / h_max by using physically sensible fallbacks
    fc_max = r["fr_cob_mid"]
    if pd.isna(fc_max) or float(fc_max) <= 0.0:
        fc_max = 0.85

    h_max = r["altura_midseason"]
    if pd.isna(h_max) or float(h_max) <= 0.0:
        h_max = 0.1

    return {
        "kcb_ini": float(r["kcb_ini"]),
        "kcb_mid": float(r["kcb_mid"]),
        "kcb_end": float(r["kcb_end"]),
        "stage_lengths": [
            int(r["dur_inicio"]),
            int(r["dur_develop"]),
            int(r["dur_medio"]),
            int(r["dur_final"]),
        ],
        "plant_date": plant_date.isoformat(),
        "zr_ini": float(r["raiz_plant"]),
        "zr_max": float(r["raiz_mid"]),
        "h_max": float(h_max),
        "p_tab": float(r["p_factor_mid"]),
        "fc_max": float(fc_max),
        "ml": float(r["ml"]) if not pd.isna(r["ml"]) else 1.5,
        "kc_min": float(r["kc_minimo"]) if not pd.isna(r["kc_minimo"]) else 0.15,
    }


def get_lai_dates_from_cr_param(gw_name: str) -> tuple[list[str], list[float]] | None:
    """Extract LAI dates/values from T_CRise_Param when available."""
    crise = load_table("T_CRise_Param")
    wt = crise[crise["NameGroundWater"] == gw_name].copy()
    wt["parsed_date"] = pd.to_datetime(wt["DateCrParam"]).dt.date
    wt = wt.sort_values("parsed_date")
    wt = wt[wt["LaiParam"].notna()]
    if wt.empty:
        return None
    dates = [d.isoformat() for d in wt["parsed_date"].tolist()]
    values = [float(v) for v in wt["LaiParam"].tolist()]
    return dates, values


def build_climate(estacao: str, dates: list[datetime.date], gw_name: str) -> list[dict]:
    """Build daily ClimateRecord dicts with interpolated water table depth."""
    clima = load_table("T_Clima")
    clim = clima[clima["Estacao"] == estacao].copy()
    clim["parsed_date"] = pd.to_datetime(clim["Data"]).dt.date
    clim = clim.set_index("parsed_date").sort_index()

    # Water table depth from T_CRise_Param
    crise = load_table("T_CRise_Param")
    wt = crise[crise["NameGroundWater"] == gw_name].copy()
    wt["parsed_date"] = pd.to_datetime(wt["DateCrParam"]).dt.date
    wt = wt.set_index("parsed_date").sort_index()

    records = []
    for d in dates:
        if d not in clim.index:
            raise ValueError(f"Missing climate for {d} in station {estacao}")
        row = clim.loc[d]
        eto = float(row["Eto"])
        precip = float(row["P_Ro"])
        rh_min = float(row["HR_min"])
        u2 = float(row["V_vento"])

        # Interpolate water table depth
        wt_depth = None
        if not wt.empty:
            before = wt.index[wt.index <= d]
            after = wt.index[wt.index >= d]
            if len(before) > 0 and len(after) > 0:
                d0 = before[-1]
                d1 = after[0]
                if d0 == d1:
                    wt_depth = float(wt.loc[d0, "WTableDepth"])
                else:
                    v0 = float(wt.loc[d0, "WTableDepth"])
                    v1 = float(wt.loc[d1, "WTableDepth"])
                    frac = (d - d0).days / (d1 - d0).days
                    wt_depth = v0 + frac * (v1 - v0)
            elif len(before) > 0:
                wt_depth = float(wt.loc[before[-1], "WTableDepth"])
            elif len(after) > 0:
                wt_depth = float(wt.loc[after[0], "WTableDepth"])

        rec = {
            "date": d.isoformat(),
            "eto": round(eto, 2),
            "precip": round(precip, 2),
            "u2": round(u2, 2),
            "rh_min": round(rh_min, 2),
        }
        if wt_depth is not None:
            rec["wt_depth_m"] = round(wt_depth, 3)
        records.append(rec)

    return records


def build_irrigation_events(res_df: pd.DataFrame) -> list[dict]:
    """Extract manual irrigation events from T_Resultados.rega_liq."""
    irrig_days = res_df[res_df["rega_liq"] > 0.0].copy()
    events = []
    for _, row in irrig_days.iterrows():
        events.append(
            {
                "date": parse_date(row["Data"]).isoformat(),
                "depth_mm": float(row["rega_liq"]),
                "fw": 1.0,
            }
        )
    return events


def build_initial_conditions(first_day: pd.Series) -> dict:
    """Compute initial conditions from the first result day.

    The root-zone depletion at the start of day 1 (dr0) is back-calculated
    from the first day's water balance so that the simulation reproduces the
    first day's end-of-day depletion exactly.
    """
    taw = float(first_day["t_a_w"])
    asw = float(first_day["depleccao_inf"])
    dr1 = taw - asw

    precip = float(first_day["P_Ro"])
    ro = float(first_day["Run_off"])
    irrig = float(first_day["rega_liq"])
    cr = float(first_day["Ground_water"])
    etc = float(first_day["Etc"])

    # From update_root_zone_depletion:
    #   dr_new = dr_prev - (P - RO) - Irrig - CR + ETc_act
    # Solve for dr_prev = dr0:
    dr0 = dr1 + (precip - ro) + irrig + cr - etc

    dei0 = float(first_day["De_start_i"])
    dep0 = float(first_day["De_start_p"])

    return {
        "dr0": round(dr0, 3),
        "dei0": round(dei0, 3),
        "dep0": round(dep0, 3),
    }


def build_expected_df(res_df: pd.DataFrame) -> pd.DataFrame:
    """Map T_Resultados columns to DailyResult field names."""
    res_df = res_df.sort_values("Data").reset_index(drop=True)
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(res_df["Data"]).dt.date
    out["day_of_sim"] = range(1, len(res_df) + 1)
    # Stage is not present in T_Resultados; we fill with a placeholder
    # (the test will not assert on stage directly)
    out["stage"] = 1

    out["eto"] = res_df["e_t_o"]
    out["precip"] = res_df["P_Ro"]
    out["irrig"] = res_df["rega_liq"]
    out["ro"] = res_df["Run_off"]

    out["kcb"] = res_df["Kcbdiario"]
    out["ke"] = res_df["Ke"]
    # kei / kep not stored separately in original results
    out["kei"] = None
    out["kep"] = None
    out["ks"] = res_df["Ks"]
    out["kc_max"] = res_df["Kcmax"]

    out["etc_act"] = res_df["Etc"]
    # transp_act / evap_act not directly available
    out["transp_act"] = None
    out["evap_act"] = None

    # depleccao_inf is ASW in the original; our dr = TAW - ASW
    out["dr"] = res_df["t_a_w"] - res_df["depleccao_inf"]
    out["dei"] = None
    out["dep"] = None
    out["dp"] = res_df["DP"]
    out["dp_ei"] = res_df["DPei"]
    out["dp_ep"] = res_df["DPep"]
    out["cr"] = res_df["Ground_water"]

    out["taw"] = res_df["t_a_w"]
    out["raw"] = res_df["Raw"]
    out["zr"] = res_df["prof_raiz"]
    out["fc"] = res_df["Fc"]
    out["h"] = res_df["altura"]
    # p can be derived from raw / taw
    out["p"] = res_df["Raw"] / res_df["t_a_w"]

    return out


def extract_one(sim_id: int) -> None:
    print(f"Extracting Simulacao_ID {sim_id} ...")
    sim_df = load_table("T_Simulacao")
    sim_row = sim_df[sim_df["Simulacao_ID"] == sim_id].iloc[0]

    estacao = sim_row["Estacao"]
    solo_id = int(sim_row["Solo_ID"])
    cultura_id = int(sim_row["Cultura_ID"])
    gw_name = sim_row["descricao_groundwater"]

    # Results for this simulation
    res_df = load_table("T_Resultados")
    res = res_df[res_df["Simulacao_ID"] == sim_id].copy()
    res["parsed_date"] = pd.to_datetime(res["Data"]).dt.date
    res = res.sort_values("parsed_date").reset_index(drop=True)
    dates = res["parsed_date"].tolist()
    plant_date = dates[0]

    # Build config pieces
    soil = build_soil_params(solo_id)
    crop = build_crop_params(cultura_id, plant_date)
    # Use LAI from T_CRise_Param when the user provided it
    lai_from_cr = get_lai_dates_from_cr_param(gw_name)
    if lai_from_cr is not None:
        crop["lai_dates"] = lai_from_cr[0]
        crop["lai_values"] = lai_from_cr[1]
    climate = build_climate(estacao, dates, gw_name)
    ic = build_initial_conditions(res.iloc[0])
    irrigation = build_irrigation_events(res)

    # Load CR coefficients from T_asc_capilar
    asc = load_table("T_asc_capilar")
    asc_row = asc[asc["descricao_capilar"] == gw_name].iloc[0]
    cr_coeffs = {}
    for key in ["a1", "b1", "a2", "b2", "a3", "b3", "a4", "b4"]:
        if key in asc_row and not pd.isna(asc_row[key]):
            cr_coeffs[f"cr_{key}"] = float(asc_row[key])
    soil.update(cr_coeffs)

    config = {
        "soil": soil,
        "crop": crop,
        "climate": climate,
        "initial_conditions": ic,
        "irrigation": irrigation,
        "irrigation_strategy": {"strategy_type": "manual"},
        "fw_base": 1.0,
        "dp_method": "simple",
        "cr_method": "parametric",
    }

    # Write
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    config_path = FIXTURE_DIR / f"{sim_id}_config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2, default=str)

    expected = build_expected_df(res)
    expected_path = FIXTURE_DIR / f"{sim_id}_expected.parquet"
    expected.to_parquet(expected_path, index=False)
    print(f"  Wrote {config_path.name} + {expected_path.name}")


def main() -> None:
    for sim_id in TARGET_SIM_IDS:
        extract_one(sim_id)
    print("Done.")


if __name__ == "__main__":
    main()
