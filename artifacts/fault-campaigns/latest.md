# ForgeGuard fault-injection campaign

Run: `FCR-20260723T125118Z`

- Clean physical-fault accuracy: **1.000**
- Corrupted-signal safe-response rate: **1.000**
- Workflow-fault containment rate: **1.000**

## Signal campaign

| Case | Physical | Sensor fault | Predicted | Confidence | Quality | Safe gate |
|---|---|---|---|---:|---:|---:|
| `clean-normal` | normal | none | normal | 0.876 | 0.998 | no |
| `clean-imbalance` | imbalance | none | imbalance | 0.873 | 0.998 | no |
| `clean-misalignment` | misalignment | none | misalignment | 0.899 | 0.998 | no |
| `clean-outer_race` | outer_race | none | outer_race | 0.579 | 0.998 | yes |
| `clean-inner_race` | inner_race | none | inner_race | 0.815 | 0.748 | no |
| `clean-ball` | ball | none | ball | 0.739 | 0.998 | no |
| `clean-lubrication` | lubrication | none | lubrication | 0.851 | 0.748 | no |
| `clean-looseness` | looseness | none | looseness | 0.879 | 0.998 | no |
| `sensor-low_snr` | normal | low_snr | normal | 0.653 | 0.834 | yes |
| `sensor-dropout` | normal | dropout | normal | 0.859 | 0.535 | yes |
| `sensor-drift` | normal | drift | normal | 0.850 | 0.755 | yes |
| `sensor-clipping` | normal | clipping | normal | 0.781 | 0.543 | yes |
| `sensor-quantization` | normal | quantization | normal | 0.869 | 0.817 | yes |
| `sensor-speed_shift` | normal | speed_shift | normal | 0.872 | 0.878 | yes |
| `sensor-impulse_interference` | normal | impulse_interference | ball | 0.649 | 0.528 | yes |

## Workflow campaign

| Tool fault | Status | Contained | Error |
|---|---|---:|---|
| error | failed | yes | RuntimeError: fault-campaign-error |
| timeout | failed | yes | TimeoutError: fault-campaign-timeout |
| empty_result | succeeded | yes | - |

## Boundary

This campaign uses reproducible signal and software fault injection. It is evidence for
regression and safety behavior, not a substitute for a physical test rig or a plant safety case.
