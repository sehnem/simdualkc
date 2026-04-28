# References

The following scientific documents are the authoritative ground truth for this implementation.

## Primary References

| Document | Key Content |
|---|---|
| **Rosa et al. (2012)** | Two-fraction evaporation model, $ETc_{act} = (K_s \cdot K_{cb} + K_e) \cdot ET_o$, Ks from $D_r/TAW/RAW$, parametric CR/DP (Liu et al. 2006) |
| **FAO-56 (Allen et al. 1998)** | Penman-Monteith ETo, Kcb/Kc tables, Dual Kc §6, TAW/RAW/Dr balance |
| **SIMDualKc Tutorial (2018)** | v1 feature reference: multi-layer soil, input/output format, forages, intercropping, delivery constraints |
| **FAO-66** | Stewart yield-water stress model $Y_a/Y_m = 1 - K_y(1 - ET_a/ET_m)$, crop Ky values, Mass-Hoffman salinity model |

## PDF Files

The PDF files are included in the `docs/references/` directory:

- `rosa_et_al_dual_kc.pdf` — Rosa et al. (2012)
- `simdual_tutorial_2018.pdf` — SIMDualKc v1 tutorial
- `fao_66_crop_yield_response_water.pdf` — FAO-66

FAO-56 is available online at [http://www.fao.org/4/x0490e/](http://www.fao.org/4/x0490e/).

## Citation

When equations in code diverge from the PDFs, the PDF wins. Fix the code.
