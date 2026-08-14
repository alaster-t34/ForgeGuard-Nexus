# External benchmark data and redistribution rules

ForgeGuard does not bundle third-party benchmark recordings. The adapters are code only. The user must obtain each dataset from its official source, preserve its terms, cite it, and confirm whether competition publication, commercial use, or derivative redistribution is allowed.

| Dataset | Intended ForgeGuard use | Redistribution policy in this repository | Declared/source status |
|---|---|---|---|
| ForgeGuard OpenEval-RM | Reproducible software, calibration, robustness, and Agent regression | Included | Project-generated, Apache-2.0; explicitly synthetic |
| CWRU Bearing Data Center | Known bearing-fault classification and load-shift evaluation | Download by user | Official source terms must be checked before redistribution |
| Paderborn Bearing DataCenter | Cross-condition bearing classification with vibration/current/context | Download by user | CC BY-NC 4.0 as stated by the source; non-commercial restriction applies |
| XJTU-SY | Run-to-failure degradation and RUL evaluation | Download by user | Public research dataset; source terms and citation must be verified |
| MVTec AD | Image anomaly detection and localization | Download by user | CC BY-NC-SA 4.0 |
| MVTec AD 2 | Visual anomaly detection under harder distribution shifts | Download by user | CC BY-NC-SA 4.0 |

## Required provenance record

Every external run must store:

- official source and download date;
- dataset/version or archive hash;
- license/terms snapshot;
- citation;
- files/categories actually evaluated;
- preprocessing and windowing;
- group-level train/validation/test policy;
- random seed and software commit;
- excluded samples and reasons;
- complete metric and latency report.

The repository ignores `data/external/` and `data/raw/` so accidental publication does not occur. This document is an engineering control, not legal advice.
