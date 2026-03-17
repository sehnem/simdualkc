"""Stewart Yield Model — FAO-56 / tutorial.

Implements yield decrease functions based on transpiration deficits.
"""

from __future__ import annotations


def compute_yield_decrease_transpiration(
    t_act_sum: float,
    t_pot_sum: float,
    k_y: float,
    y_m: float,
) -> tuple[float, float]:
    """Compute the actual yield based on the crop transpiration deficit.

    Stewart water-yield approach adapted for transpiration:
        Ya = Ym - (Ym * Ky * (1 - Tact / Tpot))
    or:
        Ya = Ym - (Ym * Ky * Td / Tc)
    where Td = Tc - Ta (deficit).

    Args:
        t_act_sum: Sum of actual transpiration over the season [mm].
        t_pot_sum: Sum of potential transpiration (Ks=1) over the season [mm].
        k_y: Yield response factor [—].
        y_m: Maximum expected yield (e.g., kg/ha).

    Returns:
        `(y_a, decrease_pct)`
        - `y_a`: Actual computed yield [same units as y_m].
        - `decrease_pct`: Percentage of yield decrease [%].
    """
    if t_pot_sum <= 0.0:
        return y_m, 0.0

    relative_t_deficit = 1.0 - (t_act_sum / t_pot_sum)
    relative_t_deficit = max(0.0, min(1.0, relative_t_deficit))

    decrease_fraction = k_y * relative_t_deficit
    decrease_fraction = max(0.0, min(1.0, decrease_fraction))

    y_a = y_m * (1.0 - decrease_fraction)
    decrease_pct = decrease_fraction * 100.0

    return y_a, decrease_pct
