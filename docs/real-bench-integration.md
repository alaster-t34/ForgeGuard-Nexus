# Real test-rig integration

ForgeGuard 0.2 contains a hardware-neutral evidence gateway. It does not assume RV1126B, IIS3DWB, RKNN, NVIDIA, Intel, or a particular DAQ vendor.

## Implemented path

```text
accelerometer / DAQ / microcontroller
        ↓ CSV replay or newline-delimited serial samples
ForgeGuard Edge client
        ↓ retry + ordered crash-safe local spool
HTTP(S) frame contract
        ↓ idempotent node/sequence ingestion
BenchGateway
        ↓ signal-integrity gates → selected model → evidence archive
optional incident opening → Agent maintenance loop
```

The current executable acquisition adapters are CSV and serial. MQTT and OPC UA are declared optional extension dependencies and must implement the same frame contract before they can be claimed as supported integrations.

The API records node identity, asset identity, campaign/specimen identity, channel, sample rate, sensor position, mounting method, calibration metadata, DAQ configuration, safety approval, operating points, RPM, load, temperature, timestamp, and monotonic sequence. Anonymous arrays are therefore not presented as traceable physical evidence.

## Register and stream a recorded capture

```bash
PYTHONPATH=edge-node python -m forgeguard_edge.cli stream-csv capture.csv \
  --server http://127.0.0.1:8000 \
  --node-id BENCH-DAQ-001 \
  --asset-id FG-BRG-001 \
  --sample-rate 25600 \
  --window-size 4096 \
  --hop-size 2048 \
  --rpm 1800 \
  --load 70 \
  --sensor-position 'drive-end bearing housing, radial' \
  --sensor-mounting 'stud-mounted' \
  --spool-dir runtime-data/bench-001-spool \
  --campaign-manifest simulator/rig_campaign.demo.json
```

## Stream a real serial DAQ

The serial device emits one float or comma-separated floats per newline. Copy `simulator/rig_campaign.example.json`, replace every placeholder, obtain the named safety approval, and then install the optional dependency and start streaming:

```bash
python -m pip install -e 'edge-node[serial]'
PYTHONPATH=edge-node python -m forgeguard_edge.cli stream-serial \
  --port /dev/ttyUSB0 \
  --baudrate 921600 \
  --server http://127.0.0.1:8000 \
  --node-id BENCH-DAQ-001 \
  --asset-id FG-BRG-001 \
  --sample-rate 25600 \
  --window-size 4096 \
  --rpm 1800 \
  --load 70 \
  --sensor-position 'drive-end bearing housing, radial' \
  --sensor-mounting 'stud-mounted' \
  --campaign-manifest path/to/completed-rig-campaign.json
```

## Transport reliability and evidence integrity

- HTTP calls use bounded exponential retries.
- Failed frames enter an atomic local JSON spool instead of being discarded.
- Spool replay preserves sequence order, because later frames must not overtake failed frames.
- The next sequence number is persisted across edge-process restarts.
- Server ingestion is idempotent for an exact `(node_id, sequence, payload)` retry.
- Reusing a sequence with different content is rejected.
- A processing failure rolls the server sequence state back so the frame can be retried.
- Raw waveform and metadata are archived separately; source-controlled releases exclude plant evidence by default.

## Physical validation checklist

Before a result enters a competition report, record:

1. rig drawing, guards, emergency stop, and operating envelope;
2. asset, shaft, bearing, coupling, and specimen identifiers;
3. sensor make, serial number, sensitivity, range, axis, and bandwidth;
4. sensor position, orientation, mounting method, and mounting torque where applicable;
5. calibration date, reference, and certificate;
6. DAQ make, input range, coupling, anti-alias filter, sample rate, bit depth, and clock source;
7. tachometer source, pulses per revolution, and vibration/RPM synchronization;
8. load, temperature, lubrication, alignment, and operating duration;
9. specimen provenance, injected fault method, and post-test physical inspection;
10. raw-file hash, acquisition time, software version, operator, and deviations from protocol.

## Acceptance sequence for the first physical run

1. stationary sensor/noise-floor capture;
2. healthy unloaded run;
3. healthy runs across at least three speeds and three loads;
4. repeatability capture after remounting the sensor;
5. seeded or naturally damaged specimen under a guarded protocol;
6. blind-label inference;
7. post-run inspection and label reconciliation;
8. report false alarms, missed detections, abstentions, data-quality rejections, and latency.

## Current honesty boundary

The code path, idempotent ingestion, offline spool, CSV end-to-end transport, model inference, and evidence persistence are tested. This execution environment cannot connect to an external physical rig, so no physical-validation claim is made. The first on-rig run must preserve evidence under `artifacts/bench-evidence/` outside public version control and add photographs plus a signed acquisition record.
