#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE="$ROOT_DIR/compose.yaml"
OUT_DIR="$ROOT_DIR/simulator/openeval_replay"
DATASET="$ROOT_DIR/data/openeval/ForgeGuard-OpenEval-RM-v0.1.0-waveform-csv/forgeguard_openeval_rm_v0_1.npz"
INDEX="$ROOT_DIR/data/openeval/index.csv"
mkdir -p "$OUT_DIR"

python3 - "$DATASET" "$INDEX" "$OUT_DIR" <<'PY'
import csv, json, sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

npz = np.load(sys.argv[1], allow_pickle=False)
index_path = Path(sys.argv[2])
if index_path.stat().st_size > 32 * 1024 * 1024:
    raise ValueError('OpenEval index.csv exceeds 32 MiB')
csv.field_size_limit(16_384)
with index_path.open(encoding='utf-8-sig', newline='') as handle:
    reader = csv.DictReader(handle)
    if not reader.fieldnames or len(reader.fieldnames) > 32:
        raise ValueError('OpenEval index.csv must contain 1 to 32 columns')
    required = {'sample_id', 'fault_mode', 'split', 'rpm', 'load_percent'}
    missing = sorted(required - set(reader.fieldnames))
    if missing:
        raise ValueError(f'OpenEval index.csv is missing columns: {missing}')
    rows = []
    for row_number, row in enumerate(reader, 1):
        if row_number > 100_000:
            raise ValueError('OpenEval index.csv exceeds 100,000 data rows')
        rows.append(row)
out = Path(sys.argv[3])
stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
for target in ('normal', 'outer_race'):
    index, row = next((i, r) for i, r in enumerate(rows) if r['fault_mode'] == target and r['split'] == 'test')
    with (out / f'{target}.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['acceleration_x'])
        writer.writerows((f'{float(value):.9g}',) for value in npz['signals'][index])
    manifest = {
        'campaign_id': f'OPENEVAL-{target.upper().replace("_", "-")}-{stamp}',
        'node_id': 'JETSON-AGX-ORIN-001', 'asset_id': 'FG-BRG-001',
        'title': f'OpenEval clean {target} replay', 'operator_id': 'forgeguard-replay',
        'specimen': {'specimen_id': row['sample_id'], 'condition': 'unknown', 'declared_fault_label': target, 'provenance': 'ForgeGuard OpenEval-RM synthetic replay; not physical evidence', 'fault_creation_method': None, 'post_test_inspection': None, 'photo_uris': []},
        'sensor': {'manufacturer': 'ForgeGuard', 'model': 'OpenEval replay', 'serial_number': None, 'sensitivity': None, 'sensitivity_unit': None, 'measurement_range': None, 'bandwidth_hz': '0-6000', 'axis': 'radial', 'position': 'simulated drive-end', 'mounting': 'not applicable', 'calibration': {'performed_at': None, 'method': 'deterministic replay', 'reference': row['sample_id'], 'sensitivity': None, 'unit': 'g', 'certificate_uri': None}},
        'daq': {'manufacturer': 'ForgeGuard', 'model': 'NPZ exporter', 'serial_number': None, 'bit_depth': 24, 'input_range': 'floating point', 'coupling': 'not applicable', 'anti_alias_filter': 'generator-defined', 'clock_source': 'dataset'},
        'safety': {'guard_installed': True, 'emergency_stop_verified': True, 'max_rpm': 3000, 'max_load_percent': 150, 'approved_by': 'synthetic-replay-fixture'},
        'operating_points': [{'rpm': float(row['rpm']), 'load_percent': float(row['load_percent']), 'duration_seconds': 2048/12000, 'repetitions': 1}],
        'protocol_version': 'forgeguard-rig-v0.2',
        'notes': 'Software replay only. Do not cite as a physical test-rig result.'
    }
    (out / f'{target}.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(target, row['rpm'], row['load_percent'])
PY

for label in normal outer_race; do
  rpm="$(python3 -c "import json; print(json.load(open('$OUT_DIR/$label.json', encoding='utf-8'))['operating_points'][0]['rpm'])")"
  load="$(python3 -c "import json; print(json.load(open('$OUT_DIR/$label.json', encoding='utf-8'))['operating_points'][0]['load_percent'])")"
  extra=()
  [[ "$label" == "outer_race" ]] && extra+=(--open-incident)
  sudo docker compose -f "$COMPOSE" run --rm --no-deps edge-replay \
    python3 -m forgeguard_edge.cli stream-csv "/workspace/simulator/openeval_replay/$label.csv" \
    --server http://api:8000 --node-id JETSON-AGX-ORIN-001 --asset-id FG-BRG-001 \
    --campaign-manifest "/workspace/simulator/openeval_replay/$label.json" \
    --spool-dir /workspace/runtime-data/edge-spool --window-size 2048 --hop-size 2048 \
    --sample-rate 12000 --rpm "$rpm" --load "$load" --max-frames 1 "${extra[@]}"
done
