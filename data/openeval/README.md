# ForgeGuard OpenEval-RM 0.1.0

Deterministic physics-informed rotating-machinery evaluation set for model, agent and robustness regression. It is openly redistributable but must not be represented as experimental plant data.

## Contents

- `forgeguard_openeval_rm_v0_1.npz`: waveform tensor, integer labels, split names and label names.
- `index.csv`: compact human-readable sample index.
- `metadata.jsonl`: complete per-sample generation metadata.
- `manifest.json`: provenance, hash, split policy and external benchmark registry.

## Labels

- `normal`
- `imbalance`
- `misalignment`
- `outer_race`
- `inner_race`
- `ball`
- `lubrication`
- `looseness`

## Split policy

Machine-group split: simulated machine IDs 00-08 train, 09-10 validation, 11-13 test. No window from a machine appears in multiple splits.

## License and scientific boundary

The generator and generated OpenEval-RM data are Apache-2.0. This dataset is intended for
software regression, robustness testing and open benchmark demonstrations. It is synthetic,
although its fault signatures use transparent rotating-machinery formulas. It must not be used
to claim real-factory accuracy. Real-data claims require separate evaluation on the external
public datasets listed in `manifest.json` and on a disclosed physical test rig.

SHA-256: `768b1f7c4cee7082e7a415e23252f82b5f1ebef100cce96a954acf849835845d`
