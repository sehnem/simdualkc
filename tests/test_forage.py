"""Tests for forage multi-cut logic.

Covers model validation, cycle mapping, Kcb/fc/param interpolation,
cut day behaviour, and full simulation smoke tests.
"""

import datetime

import pytest
from pydantic import ValidationError

from simdualkc.kcb import (
    build_forage_cycle_map,
    get_forage_cycle_and_day,
    get_forage_stage,
    interpolate_forage_fc,
    interpolate_forage_kcb,
    interpolate_forage_param,
    is_forage_cut_day,
)
from simdualkc.models import (
    ClimateRecord,
    CropParams,
    ForageCutCycle,
    ForageParams,
    InitialConditions,
    IrrigationEvent,
    SimulationConfig,
    SoilParams,
)
from simdualkc.simulation import run_simulation

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

PLANT_DATE = datetime.date(2024, 4, 1)
CUT1_DATE = datetime.date(2024, 5, 15)
CUT2_DATE = datetime.date(2024, 7, 9)
CUT3_DATE = datetime.date(2024, 8, 23)

FORAGE_CYCLES = [
    ForageCutCycle(stage_lengths=[15, 40, 15, 5], cut_date=CUT1_DATE),
    ForageCutCycle(stage_lengths=[10, 30, 10, 5], cut_date=CUT2_DATE),
    ForageCutCycle(stage_lengths=[5, 25, 10, 5], cut_date=CUT3_DATE),
]

FORAGE_PARAMS = ForageParams(
    start_date=PLANT_DATE,
    num_cuts=3,
    max_height_m=1.1,
    min_root_m=0.2,
    max_root_m=0.7,
    days_to_max_root=80,
    p_fraction=0.55,
    fc_start=0.30,
    fc_peak=0.90,
    fc_before=0.80,
    fc_after=0.10,
    kcb_start=0.30,
    kcb_peak=1.10,
    kcb_before=1.00,
    kcb_after=0.15,
    min_height_m=0.10,
    cycles=FORAGE_CYCLES,
)


def _make_forage_crop() -> CropParams:
    return CropParams(
        kcb_ini=0.15,
        kcb_mid=1.10,
        kcb_end=0.35,
        stage_lengths=[30, 40, 50, 30],
        plant_date=PLANT_DATE,
        zr_ini=0.15,
        zr_max=1.20,
        h_max=2.50,
        p_tab=0.55,
        fc_max=0.90,
        ml=1.5,
        kc_min=0.15,
        is_forage=True,
        forage_params=FORAGE_PARAMS,
    )


def _make_soil() -> SoilParams:
    return SoilParams(
        theta_fc=0.32,
        theta_wp=0.12,
        ze=0.10,
        rew=9.0,
        tew=22.0,
        cn2=75.0,
    )


# ===========================================================================
# Model validation
# ===========================================================================


class TestForageModels:
    """Pydantic model creation and validation."""

    def test_foragecutcycle_valid(self) -> None:
        c = ForageCutCycle(stage_lengths=[10, 20, 30, 10], cut_date=CUT1_DATE)
        assert sum(c.stage_lengths) == 70

    def test_foragecutcycle_negative_stage_rejected(self) -> None:
        with pytest.raises(ValidationError, match="positive"):
            ForageCutCycle(stage_lengths=[-1, 20, 30, 10], cut_date=CUT1_DATE)

    def test_foragecutcycle_wrong_length_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ForageCutCycle(stage_lengths=[10, 20, 30], cut_date=CUT1_DATE)

    def test_forageparams_valid(self) -> None:
        fp = FORAGE_PARAMS
        assert fp.num_cuts == 3
        assert len(fp.cycles) == 3

    def test_forageparams_cycle_count_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError, match="num_cuts"):
            ForageParams(
                **FORAGE_PARAMS.model_dump(exclude={"num_cuts"}),
                num_cuts=2,
            )

    def test_forageparams_invalid_fc_order_rejected(self) -> None:
        with pytest.raises(ValidationError, match="fc_after"):
            ForageParams(
                **FORAGE_PARAMS.model_dump(exclude={"fc_after", "fc_start"}),
                fc_after=0.50,
                fc_start=0.30,
            )

    def test_cropparams_forage_requires_params(self) -> None:
        with pytest.raises(ValidationError, match="forage_params"):
            CropParams(
                kcb_ini=0.15,
                kcb_mid=1.10,
                kcb_end=0.35,
                stage_lengths=[30, 40, 50, 30],
                plant_date=PLANT_DATE,
                zr_ini=0.15,
                zr_max=1.20,
                h_max=2.50,
                p_tab=0.55,
                fc_max=0.90,
                is_forage=True,
            )

    def test_cropparams_is_forage_flag_works(self) -> None:
        crop = _make_forage_crop()
        assert crop.is_forage
        assert crop.forage_params is not None


# ===========================================================================
# Cycle mapping
# ===========================================================================


class TestBuildForageCycleMap:
    """build_forage_cycle_map pre-computes (start, end, idx) per cycle."""

    def test_three_cycles(self) -> None:
        cmap = build_forage_cycle_map(FORAGE_PARAMS)
        assert len(cmap) == 3
        # Cycle 1: days 1-75 (sum = 15+40+15+5 = 75)
        assert cmap[0] == (1, 75, 0)
        # Cycle 2: days 76-130 (75+1 .. 75+55)
        assert cmap[1] == (76, 130, 1)
        # Cycle 3: days 131-175 (131 .. 131+45-1)
        assert cmap[2] == (131, 175, 2)


class TestGetForageCycleAndDay:
    """Mapping from day_of_sim to (cycle_idx, day_in_cycle)."""

    def test_day_1_cycle_0_day_1(self) -> None:
        assert get_forage_cycle_and_day(1, FORAGE_PARAMS) == (0, 1)

    def test_day_75_cycle_0_day_75(self) -> None:
        assert get_forage_cycle_and_day(75, FORAGE_PARAMS) == (0, 75)

    def test_day_76_cycle_1_day_1(self) -> None:
        assert get_forage_cycle_and_day(76, FORAGE_PARAMS) == (1, 1)

    def test_day_130_cycle_1_day_55(self) -> None:
        assert get_forage_cycle_and_day(130, FORAGE_PARAMS) == (1, 55)

    def test_day_131_cycle_2_day_1(self) -> None:
        assert get_forage_cycle_and_day(131, FORAGE_PARAMS) == (2, 1)

    def test_past_last_cut_last_cycle_overshoot(self) -> None:
        idx, day = get_forage_cycle_and_day(200, FORAGE_PARAMS)
        assert idx == 2
        assert day == 70  # 200 - 131 + 1


class TestIsForageCutDay:
    """Detection of cut days (last day of each cycle)."""

    def test_day_75_is_cut(self) -> None:
        assert is_forage_cut_day(75, FORAGE_PARAMS) is True

    def test_day_130_is_cut(self) -> None:
        assert is_forage_cut_day(130, FORAGE_PARAMS) is True

    def test_day_175_is_cut(self) -> None:
        assert is_forage_cut_day(175, FORAGE_PARAMS) is True

    def test_day_74_not_cut(self) -> None:
        assert is_forage_cut_day(74, FORAGE_PARAMS) is False

    def test_day_1_not_cut(self) -> None:
        assert is_forage_cut_day(1, FORAGE_PARAMS) is False


class TestGetForageStage:
    """Stage within a cut cycle."""

    def test_day_1_stage_1(self) -> None:
        cyc = FORAGE_CYCLES[0]
        assert get_forage_stage(1, cyc) == 1

    def test_day_15_stage_1(self) -> None:
        cyc = FORAGE_CYCLES[0]
        assert get_forage_stage(15, cyc) == 1

    def test_day_16_stage_2(self) -> None:
        cyc = FORAGE_CYCLES[0]
        assert get_forage_stage(16, cyc) == 2

    def test_day_55_stage_2(self) -> None:
        cyc = FORAGE_CYCLES[0]
        assert get_forage_stage(55, cyc) == 2

    def test_day_56_stage_3(self) -> None:
        cyc = FORAGE_CYCLES[0]
        assert get_forage_stage(56, cyc) == 3

    def test_day_70_stage_3(self) -> None:
        cyc = FORAGE_CYCLES[0]
        assert get_forage_stage(70, cyc) == 3

    def test_day_71_stage_4(self) -> None:
        cyc = FORAGE_CYCLES[0]
        assert get_forage_stage(71, cyc) == 4

    def test_day_75_stage_4(self) -> None:
        cyc = FORAGE_CYCLES[0]
        assert get_forage_stage(75, cyc) == 4


# ===========================================================================
# Kcb interpolation
# ===========================================================================


class TestInterpolateForageKcb:
    """Kcb sawtooth across cut cycles."""

    def test_day_1_kcb_start(self) -> None:
        kcb = interpolate_forage_kcb(1, FORAGE_PARAMS, u2=2.0, rh_min=45.0)
        assert kcb == pytest.approx(0.30)

    def test_day_15_kcb_start_constant(self) -> None:
        kcb = interpolate_forage_kcb(15, FORAGE_PARAMS, u2=2.0, rh_min=45.0)
        assert kcb == pytest.approx(0.30)

    def test_day_55_kcb_peak(self) -> None:
        # Mid stage of cycle 1 → kcb_peak
        kcb = interpolate_forage_kcb(56, FORAGE_PARAMS, u2=2.0, rh_min=45.0)
        assert kcb == pytest.approx(1.10)

    def test_day_75_kcb_before(self) -> None:
        # End of late stage / cut day → kcb_before
        kcb = interpolate_forage_kcb(75, FORAGE_PARAMS, u2=2.0, rh_min=45.0)
        assert kcb == pytest.approx(1.00)

    def test_day_76_kcb_cycle2_start(self) -> None:
        # Start of cycle 2 → kcb_start again
        kcb = interpolate_forage_kcb(76, FORAGE_PARAMS, u2=2.0, rh_min=45.0)
        assert kcb == pytest.approx(0.30)

    def test_sawtooth_cycle2_peak(self) -> None:
        kcb = interpolate_forage_kcb(95, FORAGE_PARAMS, u2=2.0, rh_min=45.0)
        # At day 95: cycle 2 day 20, which is in dev (ini=10, dev=30)
        # day_in_cycle=20, ini=10, so dev fraction = (20-10)/30 = 0.333
        # kcb = 0.30 + 0.333 * (1.10 - 0.30) = 0.567
        assert kcb == pytest.approx(0.5667, abs=0.001)

    def test_climate_adjustment_high_wind(self) -> None:
        kcb = interpolate_forage_kcb(56, FORAGE_PARAMS, u2=4.0, rh_min=45.0)
        # Mid stage with u2=4 should be > 1.10 due to climate adjustment
        assert kcb > 1.10
        assert kcb < 1.30

    def test_past_last_cycle_returns_after_value(self) -> None:
        kcb = interpolate_forage_kcb(200, FORAGE_PARAMS, u2=2.0, rh_min=45.0)
        assert kcb == pytest.approx(0.15)


class TestInterpolateForageFc:
    """Fraction cover across cut cycles."""

    def test_day_1_fc_start(self) -> None:
        assert interpolate_forage_fc(1, FORAGE_PARAMS) == pytest.approx(0.30)

    def test_day_56_fc_peak(self) -> None:
        assert interpolate_forage_fc(56, FORAGE_PARAMS) == pytest.approx(0.90)

    def test_day_75_fc_before(self) -> None:
        assert interpolate_forage_fc(75, FORAGE_PARAMS) == pytest.approx(0.80)

    def test_day_76_fc_start_again(self) -> None:
        assert interpolate_forage_fc(76, FORAGE_PARAMS) == pytest.approx(0.30)

    def test_past_last_cycle_fc_after(self) -> None:
        assert interpolate_forage_fc(200, FORAGE_PARAMS) == pytest.approx(0.10)
        # Day 176 (day after last cut) → fc_after
        assert interpolate_forage_fc(176, FORAGE_PARAMS) == pytest.approx(0.10)


class TestInterpolateForageParam:
    """Root depth, height, depletion fraction."""

    def test_day_1_zr_min(self) -> None:
        assert interpolate_forage_param(1, FORAGE_PARAMS, "zr") == pytest.approx(0.20)

    def test_day_81_zr_cycle2(self) -> None:
        # Day 81 = cycle 2, day 6. days_to_max_root=80, so zr still near min
        zr = interpolate_forage_param(81, FORAGE_PARAMS, "zr")
        assert zr == pytest.approx(0.23125, abs=1e-5)

    def test_zr_resets_cycle2(self) -> None:
        # Cycle 2 day 1 = sim day 76
        # day_in_cycle=1, zr should be near min_root (starts regrowth)
        zr = interpolate_forage_param(76, FORAGE_PARAMS, "zr")
        assert zr == pytest.approx(0.20)

    def test_day_1_h_min(self) -> None:
        assert interpolate_forage_param(1, FORAGE_PARAMS, "h") == pytest.approx(0.10)

    def test_day_71_h_max(self) -> None:
        # End of development + mid in cycle 1:
        # ini=15, dev=40, mid=15 → day 71 = day after mid ends
        assert interpolate_forage_param(71, FORAGE_PARAMS, "h") == pytest.approx(1.10)

    def test_p_constant(self) -> None:
        assert interpolate_forage_param(1, FORAGE_PARAMS, "p") == pytest.approx(0.55)
        assert interpolate_forage_param(75, FORAGE_PARAMS, "p") == pytest.approx(0.55)
        assert interpolate_forage_param(200, FORAGE_PARAMS, "p") == pytest.approx(0.55)

    def test_invalid_param_raises(self) -> None:
        with pytest.raises(ValueError, match="param"):
            interpolate_forage_param(1, FORAGE_PARAMS, "zzz")


# ===========================================================================
# Full simulation smoke tests
# ===========================================================================


class TestForageSimulationSmoke:
    """End-to-end simulation with forage crops."""

    def test_forage_simulation_runs(self) -> None:
        crop = _make_forage_crop()
        soil = _make_soil()
        climate = [
            ClimateRecord(
                date=PLANT_DATE + datetime.timedelta(days=i),
                eto=4.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(180)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=10.0, dei0=5.0, dep0=5.0),
        )
        result = run_simulation(config)
        assert result.n_days == 180
        assert result.summary is not None

    def test_sawtooth_kcb_pattern(self) -> None:
        """Kcb should rise and fall across cuts (sawtooth)."""
        crop = _make_forage_crop()
        soil = _make_soil()
        climate = [
            ClimateRecord(
                date=PLANT_DATE + datetime.timedelta(days=i),
                eto=4.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(180)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=10.0, dei0=5.0, dep0=5.0),
        )
        result = run_simulation(config)

        # Extract Kcb
        kcbs = [r.kcb for r in result.daily_results]

        # Before cut 1 (day 75): rising Kcb
        assert kcbs[0] == pytest.approx(0.30, abs=0.01)  # day 1
        assert kcbs[54] > kcbs[0]  # day 55, in dev
        assert kcbs[74] == pytest.approx(1.00, abs=0.01)  # day 75 = cut 1

        # After cut 1 (day 76): reset low
        assert kcbs[75] == pytest.approx(0.30, abs=0.01)  # start cycle 2

        # Before cut 2 (day 130): rising again
        assert kcbs[129] == pytest.approx(1.00, abs=0.01)  # day 130 = cut 2

        # After cut 2 (day 131): reset low
        assert kcbs[130] == pytest.approx(0.30, abs=0.01)  # start cycle 3

    def test_cut_day_dr_cap(self) -> None:
        """Dr should be capped to new TAW after a cut."""
        crop = _make_forage_crop()
        soil = _make_soil()
        climate = [
            ClimateRecord(
                date=PLANT_DATE + datetime.timedelta(days=i),
                eto=6.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(180)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=50.0, dei0=5.0, dep0=5.0),
        )
        result = run_simulation(config)

        # On cut day 75, zr resets from ~0.7m to 0.2m
        # TAW with zr=0.7: 1000*(0.32-0.12)*0.7 = 140mm
        # TAW with zr=0.2: 1000*(0.32-0.12)*0.2 = 40mm
        # dr on day 76 must be <= 40
        assert result.daily_results[75].dr <= 40.0 + 1e-9

    def test_forage_with_irrigation(self) -> None:
        """Forage simulation with manual irrigation events."""
        crop = _make_forage_crop()
        soil = _make_soil()
        climate = [
            ClimateRecord(
                date=PLANT_DATE + datetime.timedelta(days=i),
                eto=5.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(180)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=30.0, dei0=5.0, dep0=5.0),
            irrigation=[
                IrrigationEvent(date=PLANT_DATE + datetime.timedelta(days=20), depth_mm=40.0),
                IrrigationEvent(date=PLANT_DATE + datetime.timedelta(days=60), depth_mm=30.0),
                IrrigationEvent(date=PLANT_DATE + datetime.timedelta(days=100), depth_mm=40.0),
            ],
        )
        result = run_simulation(config)
        irrig_totals = [r.irrig for r in result.daily_results]
        assert sum(irrig_totals) > 0

    def test_physical_bounds(self) -> None:
        """Forage simulation should respect physical bounds."""
        crop = _make_forage_crop()
        soil = _make_soil()
        climate = [
            ClimateRecord(
                date=PLANT_DATE + datetime.timedelta(days=i),
                eto=5.0,
                precip=2.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(180)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=10.0, dei0=5.0, dep0=5.0),
        )
        result = run_simulation(config)

        for r in result.daily_results:
            assert 0.0 <= r.ks <= 1.0 + 1e-9
            assert r.ke >= -1e-9
            assert r.etc_act >= -1e-9
            assert 0.0 <= r.dr <= r.taw + 1e-9
            assert abs(r.transp_act + r.evap_act - r.etc_act) < 1e-9

    def test_zr_resets_on_cut(self) -> None:
        """Root depth drops after cut day."""
        crop = _make_forage_crop()
        soil = _make_soil()
        climate = [
            ClimateRecord(
                date=PLANT_DATE + datetime.timedelta(days=i),
                eto=4.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(180)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=10.0, dei0=5.0, dep0=5.0),
        )
        result = run_simulation(config)

        zr_before = result.daily_results[74].zr  # day 75 (pre-cut)
        zr_after = result.daily_results[75].zr  # day 76 (post-cut)
        assert zr_after < zr_before
        assert zr_after == pytest.approx(0.20, abs=0.001)

    def test_fc_resets_after_cut(self) -> None:
        """Fraction cover drops after cut then regrows."""
        crop = _make_forage_crop()
        soil = _make_soil()
        climate = [
            ClimateRecord(
                date=PLANT_DATE + datetime.timedelta(days=i),
                eto=4.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(180)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=10.0, dei0=5.0, dep0=5.0),
        )
        result = run_simulation(config)

        # Day 75 is cut 1 (fc = 0.80), day 76 starts cycle 2 (fc = 0.30)
        fc_cut = result.daily_results[74].fc
        fc_next = result.daily_results[75].fc
        assert fc_next < fc_cut
        assert fc_next == pytest.approx(0.30, abs=0.001)

        # fc should regrow in cycle 2
        fc_grown = result.daily_results[100].fc  # cycle 2, day 25
        assert fc_grown > fc_next

    def test_forage_with_mulch(self) -> None:
        """Forage + mulch combination works."""
        crop = _make_forage_crop()
        soil = _make_soil()
        from simdualkc.models import MulchParams

        climate = [
            ClimateRecord(
                date=PLANT_DATE + datetime.timedelta(days=i),
                eto=4.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(100)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=10.0, dei0=5.0, dep0=5.0),
            mulch=MulchParams(f_mulch=0.3, kr_mulch=0.5),
        )
        result = run_simulation(config)
        assert result.n_days == 100
        assert result.summary is not None

    def test_forage_with_yield_params(self) -> None:
        """Forage simulation with Stewart yield model."""
        crop = _make_forage_crop()
        soil = _make_soil()
        from simdualkc.models import YieldParams

        climate = [
            ClimateRecord(
                date=PLANT_DATE + datetime.timedelta(days=i),
                eto=4.0,
                precip=0.0,
                u2=2.0,
                rh_min=45.0,
            )
            for i in range(180)
        ]
        config = SimulationConfig(
            soil=soil,
            crop=crop,
            climate=climate,
            initial_conditions=InitialConditions(dr0=10.0, dei0=5.0, dep0=5.0),
            yield_params=YieldParams(y_m=10000.0, k_y=1.0),
        )
        result = run_simulation(config)
        assert result.yield_act is not None
        assert result.yield_decrease_pct is not None
        assert 0.0 <= result.yield_decrease_pct <= 100.0
